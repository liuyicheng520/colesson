package com.contest;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

import javax.annotation.PreDestroy;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * 启动宿主时顺带拉起内部智学体 FastAPI，关闭宿主时一并结束。
 * 浏览器仍只访问 8082；页面与业务逻辑不变。
 */
@Component
public class ZhixuetiBackendLauncher {

    private static final Logger log = LoggerFactory.getLogger(ZhixuetiBackendLauncher.class);

    @Value("${zhixueti.auto-start:true}")
    private boolean autoStart;

    @Value("${zhixueti.backend-base:http://127.0.0.1:8000}")
    private String backendBase;

    @Value("${zhixueti.backend-dir:}")
    private String backendDir;

    @Value("${zhixueti.python-exe:}")
    private String pythonExe;

    @Value("${zhixueti.cors-origins:http://localhost:8082,http://127.0.0.1:8082}")
    private String corsOrigins;

    private Process process;
    private final AtomicBoolean startedByUs = new AtomicBoolean(false);

    @EventListener(ApplicationReadyEvent.class)
    public void onReady() {
        if (!autoStart) {
            return;
        }
        if (isHealthy()) {
            log.info("智学体已在运行：{}", trimSlash(backendBase));
            return;
        }
        Path dir = resolveBackendDir();
        if (dir == null) {
            log.warn("未找到智学体后端目录，跳过自动启动。可配置 zhixueti.backend-dir");
            return;
        }
        String python = resolvePythonCommand(dir);
        if (python == null) {
            log.warn("未找到 Python，无法自动启动智学体：{}", dir);
            return;
        }
        try {
            startProcess(dir, python);
            if (waitUntilHealthy(45)) {
                startedByUs.set(true);
                log.info("智学体已随宿主启动：{} （目录 {}）", trimSlash(backendBase), dir);
            } else {
                log.warn("智学体进程已拉起，但健康检查未通过：{}", trimSlash(backendBase));
            }
        } catch (Exception ex) {
            log.warn("自动启动智学体失败：{}", ex.getMessage());
        }
    }

    @PreDestroy
    public void onShutdown() {
        if (!startedByUs.get() || process == null) {
            return;
        }
        try {
            process.destroy();
            if (!process.waitFor(5, TimeUnit.SECONDS)) {
                process.destroyForcibly();
            }
            log.info("已停止由宿主拉起的智学体进程");
        } catch (Exception ex) {
            log.debug("停止智学体进程时忽略：{}", ex.getMessage());
        }
    }

    private void startProcess(Path dir, String python) throws Exception {
        List<String> cmd = new ArrayList<>();
        cmd.add(python);
        cmd.add("-m");
        cmd.add("uvicorn");
        cmd.add("app.main:app");
        cmd.add("--host");
        cmd.add("127.0.0.1");
        cmd.add("--port");
        cmd.add(String.valueOf(extractPort(backendBase)));

        ProcessBuilder pb = new ProcessBuilder(cmd);
        pb.directory(dir.toFile());
        pb.redirectErrorStream(true);
        pb.environment().put("USE_SQLITE", "true");
        pb.environment().put("CORS_ORIGINS", corsOrigins);
        process = pb.start();

        Thread t = new Thread(() -> {
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    if (line.contains("Application startup complete")
                            || line.contains("ERROR")
                            || line.contains("Error")) {
                        log.info("[zhixueti] {}", line);
                    }
                }
            } catch (Exception ignored) {
                // process ended
            }
        }, "zhixueti-stdout");
        t.setDaemon(true);
        t.start();
    }

    private Path resolveBackendDir() {
        List<Path> candidates = new ArrayList<>();
        Path hostRoot = Paths.get("").toAbsolutePath();
        if (backendDir != null && !backendDir.trim().isEmpty()) {
            Path configured = Paths.get(backendDir.trim());
            candidates.add(configured.isAbsolute() ? configured : hostRoot.resolve(configured).normalize());
        }
        candidates.add(hostRoot.resolve("zhixueti-backend").normalize());
        for (Path p : candidates) {
            if (p != null && Files.isDirectory(p) && Files.isRegularFile(p.resolve("app").resolve("main.py"))) {
                return p.toAbsolutePath().normalize();
            }
        }
        return null;
    }

    private String resolvePythonCommand(Path dir) {
        if (pythonExe != null && !pythonExe.trim().isEmpty()) {
            Path custom = Paths.get(pythonExe.trim());
            if (Files.isRegularFile(custom)) {
                return custom.toAbsolutePath().normalize().toString();
            }
            return pythonExe.trim();
        }
        Path venvPy = dir.resolve("venv").resolve("Scripts").resolve("python.exe");
        if (Files.isRegularFile(venvPy)) {
            return venvPy.toAbsolutePath().normalize().toString();
        }
        Path venvPyUnix = dir.resolve("venv").resolve("bin").resolve("python");
        if (Files.isRegularFile(venvPyUnix)) {
            return venvPyUnix.toAbsolutePath().normalize().toString();
        }
        for (String cmd : new String[]{"python", "py"}) {
            try {
                ProcessBuilder probe = new ProcessBuilder(cmd, "--version");
                probe.redirectErrorStream(true);
                Process p = probe.start();
                if (p.waitFor(3, TimeUnit.SECONDS) && p.exitValue() == 0) {
                    return cmd;
                }
            } catch (Exception ignored) {
                // try next
            }
        }
        return null;
    }

    private boolean waitUntilHealthy(int seconds) {
        long deadline = System.currentTimeMillis() + seconds * 1000L;
        while (System.currentTimeMillis() < deadline) {
            if (isHealthy()) {
                return true;
            }
            if (process != null && !process.isAlive()) {
                return false;
            }
            try {
                Thread.sleep(500);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return false;
            }
        }
        return false;
    }

    private boolean isHealthy() {
        HttpURLConnection conn = null;
        try {
            URI uri = URI.create(trimSlash(backendBase) + "/health");
            conn = (HttpURLConnection) uri.toURL().openConnection();
            conn.setConnectTimeout(1500);
            conn.setReadTimeout(2000);
            conn.setRequestMethod("GET");
            int code = conn.getResponseCode();
            return code >= 200 && code < 500;
        } catch (Exception ex) {
            return false;
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
    }

    private static int extractPort(String base) {
        try {
            int port = URI.create(base.trim()).getPort();
            return port > 0 ? port : 8000;
        } catch (Exception ex) {
            return 8000;
        }
    }

    private static String trimSlash(String base) {
        if (base == null || base.isEmpty()) {
            return "http://127.0.0.1:8000";
        }
        return base.endsWith("/") ? base.substring(0, base.length() - 1) : base;
    }
}
