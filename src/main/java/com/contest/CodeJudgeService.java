package com.contest;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.TimeUnit;

@Service
public class CodeJudgeService {

    private static final int MAX_SOURCE_LENGTH = 30000;
    private static final int MAX_OUTPUT_BYTES = 32768;

    @Value("${code.judge.execution-enabled:true}")
    private boolean executionEnabled;

    @Value("${code.judge.use-macos-sandbox:true}")
    private boolean useMacSandbox;

    public JudgeResult judge(ProjectService.LabTask task, String sourceCode) {
        if (task == null) {
            throw new ProjectService.ProjectException("实验任务不存在");
        }
        String source = sourceCode == null ? "" : sourceCode.trim();
        if (source.isEmpty()) {
            throw new ProjectService.ProjectException("请输入需要提交的代码");
        }
        if (source.length() > MAX_SOURCE_LENGTH) {
            throw new ProjectService.ProjectException("单次提交代码请控制在 30000 字符以内");
        }
        if ("sql_rules".equals(task.getJudgeMode()) || "SQL".equalsIgnoreCase(task.getLanguage())) {
            return judgeSql(task, source);
        }
        if (!executionEnabled) {
            throw new ProjectService.ProjectException("当前环境未开启代码运行能力");
        }
        return judgeExecutable(task, source);
    }

    private JudgeResult judgeSql(ProjectService.LabTask task, String source) {
        String normalized = source.toLowerCase(Locale.ROOT).replaceAll("\\s+", " ");
        int passed = 0;
        List<String> details = new ArrayList<>();
        List<ProjectService.LabTestCase> cases = safeCases(task);
        for (ProjectService.LabTestCase testCase : cases) {
            boolean ok = true;
            for (String token : testCase.getInputText().toLowerCase(Locale.ROOT).split("\\R")) {
                if (!token.isBlank() && !normalized.contains(token.trim().replaceAll("\\s+", " "))) {
                    ok = false;
                    details.add("缺少结构：" + token.trim());
                }
            }
            if (ok) passed++;
        }
        return result(passed, cases.size(), String.join("\n", details), 0);
    }

    private JudgeResult judgeExecutable(ProjectService.LabTask task, String source) {
        long started = System.nanoTime();
        Path directory = null;
        try {
            directory = createJudgeDirectory();
            String language = normalizeLanguage(task.getLanguage());
            List<String> runCommand;
            if ("Python".equals(language)) {
                Files.writeString(directory.resolve("main.py"), source, StandardCharsets.UTF_8);
                runCommand = List.of(resolveExecutable("python3"), "main.py");
            } else if ("JavaScript".equals(language)) {
                Files.writeString(directory.resolve("main.js"), source, StandardCharsets.UTF_8);
                runCommand = List.of(resolveExecutable("node"), "main.js");
            } else {
                Files.writeString(directory.resolve("Main.java"), source, StandardCharsets.UTF_8);
                ProcessResult compile = execute(
                        directory,
                        List.of(resolveExecutable("javac"), "-J-XX:-UsePerfData", "Main.java"),
                        "",
                        5000
                );
                if (compile.timedOut) {
                    return failed("COMPILE_ERROR", "编译超时", elapsedMs(started));
                }
                if (compile.exitCode != 0) {
                    return failed("COMPILE_ERROR", compile.output, elapsedMs(started));
                }
                runCommand = List.of(
                        resolveExecutable("java"),
                        "-XX:-UsePerfData",
                        "-Xms16m",
                        "-Xmx64m",
                        "Main"
                );
            }

            int passed = 0;
            StringBuilder details = new StringBuilder();
            List<ProjectService.LabTestCase> cases = safeCases(task);
            int limit = Math.min(Math.max(task.getTimeLimitMs(), 500), 5000);
            for (int i = 0; i < cases.size(); i++) {
                ProjectService.LabTestCase testCase = cases.get(i);
                ProcessResult run = execute(directory, runCommand, testCase.getInputText(), limit);
                if (run.timedOut) {
                    details.append("用例 ").append(i + 1).append("：运行超时\n");
                    continue;
                }
                String actual = normalizeOutput(run.output);
                String expected = normalizeOutput(testCase.getExpectedOutput());
                if (run.exitCode == 0 && actual.equals(expected)) {
                    passed++;
                } else {
                    details.append("用例 ").append(i + 1)
                            .append("：期望 ").append(expected)
                            .append("，实际 ").append(actual.isEmpty() ? "无输出" : actual)
                            .append("\n");
                }
            }
            return result(passed, cases.size(), details.toString().trim(), elapsedMs(started));
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return failed("SYSTEM_ERROR", "判题环境异常：" + e.getMessage(), elapsedMs(started));
        } catch (IOException e) {
            return failed("SYSTEM_ERROR", "判题环境异常：" + e.getMessage(), elapsedMs(started));
        } finally {
            deleteDirectory(directory);
        }
    }

    private ProcessResult execute(
            Path directory,
            List<String> command,
            String input,
            int timeoutMs
    ) throws IOException, InterruptedException {
        List<String> finalCommand = wrapSandbox(directory, command);
        ProcessBuilder builder = new ProcessBuilder(finalCommand);
        builder.directory(directory.toFile());
        builder.redirectErrorStream(true);
        builder.environment().clear();
        builder.environment().put("PATH", "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin");
        builder.environment().put("HOME", directory.toString());
        Process process = builder.start();
        try (OutputStream stdin = process.getOutputStream()) {
            stdin.write((input == null ? "" : input).getBytes(StandardCharsets.UTF_8));
        }
        BoundedReader reader = new BoundedReader(process.getInputStream());
        Thread readerThread = new Thread(reader, "code-judge-output");
        readerThread.setDaemon(true);
        readerThread.start();
        boolean finished = process.waitFor(timeoutMs, TimeUnit.MILLISECONDS);
        if (!finished) {
            terminateProcessTree(process);
            process.waitFor(500, TimeUnit.MILLISECONDS);
        }
        readerThread.join(Duration.ofSeconds(1).toMillis());
        return new ProcessResult(finished ? process.exitValue() : -1, reader.text(), !finished);
    }

    private List<String> wrapSandbox(Path directory, List<String> command) throws IOException {
        // 安全底线：学生提交的代码只允许在 macOS sandbox-exec 隔离下执行；
        // 其余平台（Windows/Linux）一律拒绝，绝不无沙箱裸跑（否则等同未认证 RCE）。
        if (!System.getProperty("os.name", "").toLowerCase(Locale.ROOT).contains("mac")) {
            throw new IOException("代码判题沙箱当前仅支持 macOS；本机已拒绝执行学生代码");
        }
        Path sandboxExecutable = Path.of("/usr/bin/sandbox-exec");
        if (!Files.isExecutable(sandboxExecutable)) {
            throw new IOException("未找到可用的 macOS sandbox-exec，已拒绝无隔离执行");
        }
        String path = directory.toAbsolutePath().toString().replace("\\", "\\\\").replace("\"", "\\\"");
        String profile = "(version 1)(deny default)(allow process-exec)"
                + "(allow file-read-metadata)"
                + "(allow file-read-data"
                + " (literal \"/\")"
                + " (literal \"/private\")"
                + " (literal \"/private/tmp\"))"
                + "(allow file-read*"
                + " (subpath \"/System\")"
                + " (subpath \"/usr\")"
                + " (subpath \"/Library\")"
                + " (subpath \"/opt/homebrew\")"
                + " (subpath \"" + path + "\"))"
                + "(allow file-write* (subpath \"" + path + "\"))"
                + "(allow sysctl-read)(allow mach-lookup)(deny network*)";
        List<String> wrapped = new ArrayList<>();
        wrapped.add(sandboxExecutable.toString());
        wrapped.add("-p");
        wrapped.add(profile);
        wrapped.addAll(command);
        return wrapped;
    }

    private Path createJudgeDirectory() throws IOException {
        Path preferredRoot = Path.of("/private/tmp");
        if (Files.isDirectory(preferredRoot) && Files.isWritable(preferredRoot)) {
            return Files.createTempDirectory(preferredRoot, "ai-teacher-judge-");
        }
        return Files.createTempDirectory("ai-teacher-judge-");
    }

    private String resolveExecutable(String name) throws IOException {
        List<String> directories = new ArrayList<>();
        if ("java".equals(name) || "javac".equals(name)) {
            directories.add(Path.of(System.getProperty("java.home", ""), "bin").toString());
        }
        directories.addAll(List.of(
                "/opt/homebrew/bin",
                "/usr/local/bin",
                "/Library/Frameworks/Python.framework/Versions/Current/bin",
                "/usr/bin",
                "/bin"
        ));
        for (String directory : directories) {
            Path candidate = Path.of(directory, name);
            if (Files.isExecutable(candidate)) {
                return candidate.toString();
            }
        }
        throw new IOException("判题运行环境缺少命令：" + name);
    }

    private void terminateProcessTree(Process process) {
        List<ProcessHandle> descendants = process.descendants().toList();
        for (int i = descendants.size() - 1; i >= 0; i--) {
            descendants.get(i).destroyForcibly();
        }
        process.destroyForcibly();
    }

    private JudgeResult result(int passed, int total, String details, long durationMs) {
        JudgeResult result = new JudgeResult();
        result.setPassedCases(passed);
        result.setTotalCases(total);
        result.setScore(total == 0 ? 0 : (int) Math.round(passed * 100.0 / total));
        result.setStatus(total > 0 && passed == total ? "ACCEPTED" : "WRONG_ANSWER");
        result.setOutputText(details == null || details.isBlank() ? "全部测试通过" : details);
        result.setDurationMs(durationMs);
        return result;
    }

    private JudgeResult failed(String status, String error, long durationMs) {
        JudgeResult result = new JudgeResult();
        result.setStatus(status);
        result.setErrorText(trimOutput(error));
        result.setDurationMs(durationMs);
        return result;
    }

    private List<ProjectService.LabTestCase> safeCases(ProjectService.LabTask task) {
        return task.getTestCases() == null ? List.of() : task.getTestCases();
    }

    private String normalizeLanguage(String value) {
        String language = value == null ? "" : value.toLowerCase(Locale.ROOT);
        if (language.contains("python")) return "Python";
        if (language.contains("javascript") || language.equals("js")) return "JavaScript";
        return "Java";
    }

    private String normalizeOutput(String value) {
        if (value == null) return "";
        return value.replace("\r\n", "\n").stripTrailing();
    }

    private long elapsedMs(long started) {
        return TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - started);
    }

    private String trimOutput(String value) {
        if (value == null) return "";
        return value.length() > MAX_OUTPUT_BYTES ? value.substring(0, MAX_OUTPUT_BYTES) : value;
    }

    private void deleteDirectory(Path directory) {
        if (directory == null) return;
        try (var paths = Files.walk(directory)) {
            paths.sorted((a, b) -> b.compareTo(a)).forEach(path -> {
                try {
                    Files.deleteIfExists(path);
                } catch (IOException ignored) {
                    // Temporary judge files are best-effort cleanup.
                }
            });
        } catch (IOException ignored) {
            // Temporary judge files are best-effort cleanup.
        }
    }

    private static class ProcessResult {
        private final int exitCode;
        private final String output;
        private final boolean timedOut;

        private ProcessResult(int exitCode, String output, boolean timedOut) {
            this.exitCode = exitCode;
            this.output = output;
            this.timedOut = timedOut;
        }
    }

    private static class BoundedReader implements Runnable {
        private final InputStream input;
        private final ByteArrayOutputStream output = new ByteArrayOutputStream();

        private BoundedReader(InputStream input) {
            this.input = input;
        }

        @Override
        public void run() {
            byte[] buffer = new byte[1024];
            try {
                int count;
                while ((count = input.read(buffer)) >= 0) {
                    int remaining = MAX_OUTPUT_BYTES - output.size();
                    if (remaining > 0) {
                        output.write(buffer, 0, Math.min(count, remaining));
                    }
                }
            } catch (IOException ignored) {
                // Process termination may close the stream.
            }
        }

        private String text() {
            return output.toString(StandardCharsets.UTF_8);
        }
    }

    public static class JudgeResult {
        private String status;
        private int score;
        private int passedCases;
        private int totalCases;
        private String outputText;
        private String errorText;
        private long durationMs;

        public String getStatus() { return status; }
        public void setStatus(String status) { this.status = status; }
        public int getScore() { return score; }
        public void setScore(int score) { this.score = score; }
        public int getPassedCases() { return passedCases; }
        public void setPassedCases(int passedCases) { this.passedCases = passedCases; }
        public int getTotalCases() { return totalCases; }
        public void setTotalCases(int totalCases) { this.totalCases = totalCases; }
        public String getOutputText() { return outputText; }
        public void setOutputText(String outputText) { this.outputText = outputText; }
        public String getErrorText() { return errorText; }
        public void setErrorText(String errorText) { this.errorText = errorText; }
        public long getDurationMs() { return durationMs; }
        public void setDurationMs(long durationMs) { this.durationMs = durationMs; }
    }
}
