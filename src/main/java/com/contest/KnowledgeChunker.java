package com.contest;

import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Component
public class KnowledgeChunker {

    private static final int MAX_CHARS = 1400;
    private static final int OVERLAP_CHARS = 180;
    private static final Pattern MARKDOWN_HEADING = Pattern.compile("^#{1,6}\\s+(.+)$");
    private static final Pattern NUMBERED_HEADING = Pattern.compile("^\\d+(?:\\.\\d+)*\\.?\\s+[A-Z][A-Za-z0-9 ,()/:\\-]+$");
    private static final Pattern SGML_TITLE = Pattern.compile("(?is)<title>(.*?)</title>");
    private static final Pattern SGML_PROGRAM = Pattern.compile("(?is)<programlisting[^>]*>(.*?)</programlisting>");
    private static final Pattern JAVA_CLASS = Pattern.compile(
            "(?m)^\\s*(?:public\\s+|protected\\s+|private\\s+)?(?:abstract\\s+|final\\s+)?"
                    + "(?:class|interface|enum|record)\\s+([A-Za-z_$][\\w$]*)"
    );
    private static final Pattern JAVA_METHOD = Pattern.compile(
            "(?m)^\\s*(?:public|protected|private|static|final|synchronized|abstract|native|default|\\s)+"
                    + "[\\w<>\\[\\], ?.@]+\\s+([A-Za-z_$][\\w$]*)\\s*\\([^;{}]*\\)"
                    + "\\s*(?:throws\\s+[^{]+)?\\{"
    );
    private static final Pattern ERROR_PATTERN = Pattern.compile(
            "(?m)([\\w.$]+(?:Exception|Error))(?::\\s*([^\\r\\n]+))?"
    );

    public List<Chunk> chunk(String content, String format) {
        String normalized = normalize(content);
        if (normalized.isBlank()) {
            return List.of();
        }
        String normalizedFormat = format == null ? "" : format.toLowerCase(Locale.ROOT);
        if ("java".equals(normalizedFormat)) {
            return chunkJava(normalized);
        }
        if ("sql".equals(normalizedFormat)) {
            return chunkSql(normalized);
        }
        if ("sgml".equals(normalizedFormat)) {
            return chunkSgml(normalized);
        }
        if ("log".equals(normalizedFormat)) {
            return chunkErrors(normalized);
        }
        return chunkSections(normalized);
    }

    private List<Chunk> chunkJava(String content) {
        List<Chunk> chunks = new ArrayList<>();
        Matcher classMatcher = JAVA_CLASS.matcher(content);
        while (classMatcher.find()) {
            String className = classMatcher.group(1);
            String block = surroundingBlock(content, classMatcher.start(), MAX_CHARS);
            chunks.add(new Chunk("code_class", "Class " + className, block));
        }
        Matcher methodMatcher = JAVA_METHOD.matcher(content);
        while (methodMatcher.find()) {
            String methodName = methodMatcher.group(1);
            if (List.of("if", "for", "while", "switch", "catch").contains(methodName)) {
                continue;
            }
            String block = surroundingBlock(content, methodMatcher.start(), MAX_CHARS);
            chunks.add(new Chunk("code_method", "Method " + methodName, block));
        }
        if (chunks.isEmpty()) {
            chunks.addAll(splitLong("code_class", "Java source", content));
        }
        return deduplicate(chunks);
    }

    private List<Chunk> chunkSql(String content) {
        List<Chunk> chunks = new ArrayList<>();
        String plain = content.replaceAll("(?s)<[^>]+>", " ").replaceAll("\\s+", " ").trim();
        for (String statement : plain.split(";")) {
            String value = statement.trim();
            if (value.length() < 30) {
                continue;
            }
            String upper = value.toUpperCase(Locale.ROOT);
            if (upper.contains("SELECT") || upper.contains("CREATE TABLE") || upper.contains("INSERT")
                    || upper.contains("UPDATE") || upper.contains("DELETE") || upper.contains("JOIN")) {
                chunks.add(new Chunk("sql_statement", sqlTitle(upper), value + ";"));
            }
        }
        if (chunks.isEmpty()) {
            chunks.addAll(chunkSections(content));
        }
        return chunks;
    }

    private List<Chunk> chunkErrors(String content) {
        List<Chunk> chunks = new ArrayList<>();
        Matcher matcher = ERROR_PATTERN.matcher(content);
        while (matcher.find()) {
            chunks.add(new Chunk(
                    "error_case",
                    matcher.group(1),
                    surroundingBlock(content, matcher.start(), MAX_CHARS)
            ));
        }
        if (chunks.isEmpty()) {
            chunks.addAll(splitLong("error_case", "Error log", content));
        }
        return chunks;
    }

    private List<Chunk> chunkSgml(String content) {
        List<Chunk> chunks = new ArrayList<>();
        Matcher titleMatcher = SGML_TITLE.matcher(content);
        List<Integer> starts = new ArrayList<>();
        List<String> titles = new ArrayList<>();
        while (titleMatcher.find()) {
            starts.add(titleMatcher.start());
            titles.add(cleanSgml(titleMatcher.group(1)));
        }
        for (int i = 0; i < starts.size(); i++) {
            int start = starts.get(i);
            int end = i + 1 < starts.size() ? starts.get(i + 1) : content.length();
            String section = cleanSgml(content.substring(start, end));
            if (!section.isBlank()) {
                chunks.addAll(splitLong("concept", titles.get(i), section));
            }
        }
        Matcher programMatcher = SGML_PROGRAM.matcher(content);
        while (programMatcher.find()) {
            String program = cleanSgml(programMatcher.group(1));
            if (!program.isBlank()) {
                String type = looksLikeSql(program) ? "sql_statement" : "code_method";
                chunks.addAll(splitLong(type, type.equals("sql_statement") ? "SQL example" : "Code example", program));
            }
        }
        if (chunks.isEmpty()) {
            chunks.addAll(chunkSections(cleanSgml(content)));
        }
        return deduplicate(chunks);
    }

    private List<Chunk> chunkSections(String content) {
        String[] lines = content.split("\\R");
        List<Chunk> chunks = new ArrayList<>();
        String section = "Introduction";
        StringBuilder body = new StringBuilder();

        for (int i = 0; i < lines.length; i++) {
            String line = lines[i].trim();
            String heading = heading(lines, i);
            if (heading != null) {
                flushSection(chunks, section, body);
                section = heading;
                body.setLength(0);
                if (i + 1 < lines.length && isRstUnderline(lines[i + 1].trim())) {
                    i++;
                }
                continue;
            }
            if (isDirective(line)) {
                continue;
            }
            body.append(lines[i]).append('\n');
        }
        flushSection(chunks, section, body);
        return chunks;
    }

    private void flushSection(List<Chunk> chunks, String section, StringBuilder body) {
        String value = body.toString().trim();
        if (value.isBlank()) {
            return;
        }
        String cleaned = value
                .replaceAll("(?m)^\\s*:\\w+(?:-\\w+)*:\\s*.*$", "")
                .replaceAll("(?m)^\\s*\\.\\.\\s+_[^:]+:\\s*$", "")
                .replaceAll("\\n{3,}", "\n\n")
                .trim();
        if (!cleaned.isBlank()) {
            chunks.addAll(splitLong("concept", section, cleaned));
        }
    }

    private List<Chunk> splitLong(String type, String section, String content) {
        List<Chunk> chunks = new ArrayList<>();
        int start = 0;
        while (start < content.length()) {
            int end = Math.min(content.length(), start + MAX_CHARS);
            if (end < content.length()) {
                int paragraph = content.lastIndexOf("\n\n", end);
                if (paragraph > start + MAX_CHARS / 2) {
                    end = paragraph;
                }
            }
            String part = content.substring(start, end).trim();
            if (!part.isBlank()) {
                chunks.add(new Chunk(type, section, part));
            }
            if (end >= content.length()) {
                break;
            }
            start = Math.max(start + 1, end - OVERLAP_CHARS);
        }
        return chunks;
    }

    private String heading(String[] lines, int index) {
        String line = lines[index].trim();
        Matcher markdown = MARKDOWN_HEADING.matcher(line);
        if (markdown.matches()) {
            return markdown.group(1).trim();
        }
        if (NUMBERED_HEADING.matcher(line).matches()) {
            return line;
        }
        if (index + 1 < lines.length && !line.isBlank() && line.length() <= 180
                && isRstUnderline(lines[index + 1].trim())) {
            return line;
        }
        return null;
    }

    private boolean isRstUnderline(String line) {
        return line.matches("[=\\-~^+*#]{3,}");
    }

    private boolean isDirective(String line) {
        return line.startsWith(".. ") || line.startsWith(":") || line.equals("|");
    }

    private String surroundingBlock(String content, int start, int maxChars) {
        int from = Math.max(0, content.lastIndexOf('\n', Math.max(0, start - 1)));
        int to = Math.min(content.length(), from + maxChars);
        return content.substring(from, to).trim();
    }

    private String sqlTitle(String upper) {
        for (String keyword : List.of("CREATE TABLE", "SELECT", "INSERT", "UPDATE", "DELETE")) {
            if (upper.contains(keyword)) {
                return keyword;
            }
        }
        return "SQL statement";
    }

    private boolean looksLikeSql(String content) {
        String upper = content.toUpperCase(Locale.ROOT);
        return upper.contains("SELECT ") || upper.contains("CREATE TABLE") || upper.contains("<COMMAND");
    }

    private String cleanSgml(String value) {
        return value
                .replace("&lt;", "<")
                .replace("&gt;", ">")
                .replace("&amp;", "&")
                .replace("&quot;", "\"")
                .replaceAll("(?is)<[^>]+>", " ")
                .replaceAll("[ \\t]+", " ")
                .replaceAll("\\n{3,}", "\n\n")
                .trim();
    }

    private List<Chunk> deduplicate(List<Chunk> chunks) {
        List<Chunk> result = new ArrayList<>();
        for (Chunk chunk : chunks) {
            boolean exists = result.stream().anyMatch(item -> item.content().equals(chunk.content()));
            if (!exists) {
                result.add(chunk);
            }
        }
        return result;
    }

    private String normalize(String content) {
        return content == null ? "" : content.replace("\r\n", "\n").replace('\r', '\n').trim();
    }

    public record Chunk(String chunkType, String sectionTitle, String content) {
    }
}
