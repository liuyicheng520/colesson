package com.contest;

import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Service
public class ComputerResourceParser {

    private static final int MAX_BYTES = 1024 * 1024;
    private static final Pattern JAVA_CLASS = Pattern.compile("\\b(class|interface|enum)\\s+([A-Za-z_$][\\w$]*)");
    private static final Pattern JAVA_METHOD = Pattern.compile(
            "(?m)^\\s*(?:public|protected|private|static|final|synchronized|abstract|native|\\s)+[\\w<>\\[\\], ?]+\\s+([A-Za-z_$][\\w$]*)\\s*\\([^;{}]*\\)\\s*(?:throws\\s+[^{]+)?\\{"
    );
    private static final Pattern SQL_TABLE = Pattern.compile("(?i)\\b(?:create\\s+table|from|join|update|into)\\s+[`\"]?([\\w.]+)");
    private static final Pattern ERROR = Pattern.compile(
            "(?m)([\\w.$]+(?:Exception|Error))(?::\\s*([^\\r\\n]+))?|\\bat\\s+([\\w.$]+)\\(([^)]+:\\d+)\\)"
    );

    public ProjectService.ProjectResource parse(MultipartFile file, String requestedType, String requestedLanguage) {
        try {
            if (file == null || file.isEmpty()) {
                throw new ProjectService.ProjectException("请选择需要上传的计算机课程资料");
            }
            if (file.getSize() > MAX_BYTES) {
                throw new ProjectService.ProjectException("单个专项资料请控制在 1MB 以内");
            }
            String fileName = file.getOriginalFilename() == null ? "resource.txt" : file.getOriginalFilename();
            String extension = extension(fileName);
            if (!List.of("java", "sql", "js", "py", "txt", "log", "xml", "json", "html", "css").contains(extension)) {
                throw new ProjectService.ProjectException("暂不支持该文件格式，请上传 Java、SQL、JS、Python、文本或日志文件");
            }
            String content = new String(file.getBytes(), StandardCharsets.UTF_8).trim();
            if (content.isEmpty()) {
                throw new ProjectService.ProjectException("文件中没有可解析的文本内容");
            }

            String type = normalizeType(requestedType, extension, content);
            String language = normalizeLanguage(requestedLanguage, extension);
            ProjectService.ProjectResource resource = new ProjectService.ProjectResource();
            resource.setId("res_" + UUID.randomUUID().toString().replace("-", ""));
            resource.setResourceType(type);
            resource.setFileName(fileName);
            resource.setLanguage(language);
            resource.setRawContent(content.length() > 50000 ? content.substring(0, 50000) : content);
            resource.setStructuredContent(buildSummary(type, content));
            resource.setCreatedAt(Instant.now().toString());
            return resource;
        } catch (ProjectService.ProjectException e) {
            throw e;
        } catch (Exception e) {
            throw new ProjectService.ProjectException("专项资料解析失败：" + e.getMessage());
        }
    }

    private String buildSummary(String type, String content) {
        if ("source_code".equals(type)) {
            List<String> classes = collect(JAVA_CLASS, content, 2, 8);
            List<String> methods = collect(JAVA_METHOD, content, 1, 12);
            methods.removeIf(value -> List.of(
                    "if", "for", "while", "switch", "catch", "synchronized"
            ).contains(value));
            return "代码结构：" + label("类/接口", classes) + "；" + label("方法", methods)
                    + "；共 " + content.split("\\R", -1).length + " 行";
        }
        if ("sql".equals(type)) {
            List<String> tables = collect(SQL_TABLE, content, 1, 12);
            return "SQL结构：" + label("涉及表", tables)
                    + "；语句类型：" + sqlOperations(content);
        }
        if ("error_log".equals(type)) {
            List<String> errors = collect(ERROR, content, 1, 8);
            return "错误摘要：" + (errors.isEmpty() ? firstLine(content) : String.join("、", errors));
        }
        return "文本资料：" + firstLine(content) + "；共 " + content.split("\\R", -1).length + " 行";
    }

    private List<String> collect(Pattern pattern, String content, int group, int limit) {
        List<String> values = new ArrayList<>();
        Matcher matcher = pattern.matcher(content);
        while (matcher.find() && values.size() < limit) {
            String value = matcher.group(group);
            if (value != null && !value.isBlank() && !values.contains(value)) {
                values.add(value.trim());
            }
        }
        return values;
    }

    private String label(String name, List<String> values) {
        return name + " " + (values.isEmpty() ? "未识别" : String.join("、", values));
    }

    private String sqlOperations(String content) {
        String upper = content.toUpperCase(Locale.ROOT);
        List<String> ops = new ArrayList<>();
        for (String op : List.of("CREATE", "SELECT", "INSERT", "UPDATE", "DELETE", "ALTER")) {
            if (upper.contains(op)) {
                ops.add(op);
            }
        }
        return ops.isEmpty() ? "未识别" : String.join("、", ops);
    }

    private String normalizeType(String requested, String extension, String content) {
        if (requested != null && List.of("source_code", "sql", "error_log", "lab_document").contains(requested)) {
            return requested;
        }
        if ("sql".equals(extension)) return "sql";
        if ("log".equals(extension) || ERROR.matcher(content).find()) return "error_log";
        if (List.of("java", "js", "py", "xml", "json", "html", "css").contains(extension)) return "source_code";
        return "lab_document";
    }

    private String normalizeLanguage(String requested, String extension) {
        String detected = switch (extension) {
            case "java" -> "Java";
            case "sql" -> "SQL";
            case "js" -> "JavaScript";
            case "py" -> "Python";
            case "html" -> "HTML";
            case "css" -> "CSS";
            case "xml" -> "XML";
            case "json" -> "JSON";
            default -> "";
        };
        if (!detected.isEmpty()) return detected;
        return requested == null || requested.isBlank() ? "Text" : requested.trim();
    }

    private String extension(String fileName) {
        int index = fileName.lastIndexOf('.');
        return index < 0 ? "" : fileName.substring(index + 1).toLowerCase(Locale.ROOT);
    }

    private String firstLine(String content) {
        String value = content.split("\\R", 2)[0].trim();
        return value.length() > 100 ? value.substring(0, 100) : value;
    }
}
