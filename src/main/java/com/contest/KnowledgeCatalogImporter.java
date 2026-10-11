package com.contest;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import javax.annotation.PostConstruct;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class KnowledgeCatalogImporter {

    private static final Logger log = LoggerFactory.getLogger(KnowledgeCatalogImporter.class);

    private final ObjectMapper objectMapper = new ObjectMapper();
    private final DatabaseStore databaseStore;
    private final KnowledgeChunker chunker;
    private final KnowledgeRepository repository;
    private final KnowledgeRetrievalService retrievalService;

    @Value("${knowledge.catalog-file:data/knowledge/catalog.json}")
    private String catalogFile;

    @Value("${knowledge.auto-import:true}")
    private boolean autoImport;

    public KnowledgeCatalogImporter(
            DatabaseStore databaseStore,
            KnowledgeChunker chunker,
            KnowledgeRepository repository,
            KnowledgeRetrievalService retrievalService
    ) {
        this.databaseStore = databaseStore;
        this.chunker = chunker;
        this.repository = repository;
        this.retrievalService = retrievalService;
    }

    @PostConstruct
    public void autoImport() {
        if (!autoImport) {
            return;
        }
        try {
            if (!databaseStore.isEnabled()) {
                log.info("当前未启用 MySQL，跳过计算机课程知识库自动导入");
                return;
            }
            databaseStore.initSchema();
            ImportReport report = importCatalog();
            if (report.documentCount() > 0) {
                log.info("计算机课程知识库已导入: documents={}, chunks={}, evalCases={}",
                        report.documentCount(), report.chunkCount(), report.evaluationCaseCount());
            }
        } catch (Exception e) {
            log.warn("知识库自动导入暂未完成，将在数据库可用后重试: {}", e.getMessage());
        }
    }

    public ImportReport importCatalog() throws Exception {
        Path catalogPath = Paths.get(catalogFile).toAbsolutePath().normalize();
        if (!Files.exists(catalogPath)) {
            return new ImportReport(0, 0, 0, List.of("目录文件不存在: " + catalogPath));
        }
        JsonNode root = objectMapper.readTree(Files.readString(catalogPath, StandardCharsets.UTF_8));
        int documentCount = 0;
        int chunkCount = 0;
        int evaluationCaseCount = 0;
        List<String> warnings = new ArrayList<>();

        for (JsonNode node : root.path("documents")) {
            Path localPath = resolveLocalPath(catalogPath, text(node, "localPath"));
            if (!Files.exists(localPath)) {
                warnings.add("资料文件不存在: " + localPath);
                continue;
            }
            byte[] bytes = Files.readAllBytes(localPath);
            String content = new String(bytes, StandardCharsets.UTF_8);
            String checksum = sha256(bytes);
            String sourceUrl = text(node, "sourceUrl");
            String documentId = "doc_" + sha256(sourceUrl.getBytes(StandardCharsets.UTF_8)).substring(0, 32);
            String now = Instant.now().toString();
            String courseCode = retrievalService.normalizeCourseCode(text(node, "courseCode"));
            String qualityTier = textOr(node, "qualityTier", "official");
            int qualityScore = qualityScore(qualityTier, intValue(node, "qualityScore", 90));

            KnowledgeRepository.Document document = new KnowledgeRepository.Document(
                    documentId,
                    courseCode,
                    text(node, "title"),
                    sourceUrl,
                    textOr(node, "sourceType", "official"),
                    text(node, "publisher"),
                    text(node, "versionLabel"),
                    text(node, "licenseName"),
                    text(node, "licenseUrl"),
                    qualityTier,
                    qualityScore,
                    text(node, "sourceUpdatedAt"),
                    textOr(node, "fetchedAt", now),
                    checksum,
                    localPath.toString(),
                    textOr(node, "format", extension(localPath)),
                    now,
                    now
            );

            List<KnowledgeChunker.Chunk> parsed = chunker.chunk(content, document.contentFormat());
            List<KnowledgeRepository.ChunkRow> rows = new ArrayList<>();
            for (int i = 0; i < parsed.size(); i++) {
                KnowledgeChunker.Chunk chunk = parsed.get(i);
                String chunkHash = sha256((
                        documentId + "|" + i + "|" + chunk.chunkType() + "|" + chunk.content()
                ).getBytes(StandardCharsets.UTF_8));
                rows.add(new KnowledgeRepository.ChunkRow(
                        "chk_" + chunkHash.substring(0, 32),
                        chunk.chunkType(),
                        chunk.sectionTitle(),
                        i,
                        chunk.content(),
                        buildSearchText(document, chunk),
                        estimateTokens(chunk.content())
                ));
            }
            repository.upsertDocument(document, rows);
            documentCount++;
            chunkCount += rows.size();
        }

        for (JsonNode node : root.path("evaluationCases")) {
            String question = text(node, "question");
            String id = text(node, "id");
            if (id.isBlank()) {
                id = "eval_" + sha256(question.getBytes(StandardCharsets.UTF_8)).substring(0, 32);
            }
            repository.upsertEvaluationCase(new KnowledgeRepository.EvaluationCase(
                    id,
                    retrievalService.normalizeCourseCode(text(node, "courseCode")),
                    textOr(node, "questionType", "concept"),
                    question,
                    objectMapper.writeValueAsString(node.path("expectedKeywords")),
                    text(node, "expectedSourceUrl"),
                    intValue(node, "topK", 5)
            ));
            evaluationCaseCount++;
        }
        return new ImportReport(documentCount, chunkCount, evaluationCaseCount, warnings);
    }

    public void setCatalogFile(String catalogFile) {
        if (catalogFile != null && !catalogFile.isBlank()) {
            this.catalogFile = catalogFile;
        }
    }

    public Map<String, Object> catalogSummary() throws Exception {
        Map<String, Object> result = new LinkedHashMap<>(repository.stats());
        result.put("catalogFile", Paths.get(catalogFile).toAbsolutePath().normalize().toString());
        return result;
    }

    private Path resolveLocalPath(Path catalogPath, String value) {
        Path path = Paths.get(value);
        if (path.isAbsolute()) {
            return path.normalize();
        }
        Path fromWorkingDirectory = Paths.get(value).toAbsolutePath().normalize();
        if (Files.exists(fromWorkingDirectory)) {
            return fromWorkingDirectory;
        }
        return catalogPath.getParent().resolve(path).normalize();
    }

    private String buildSearchText(
            KnowledgeRepository.Document document,
            KnowledgeChunker.Chunk chunk
    ) {
        return document.title() + " " + document.courseCode() + " "
                + chunk.sectionTitle() + " " + chunk.chunkType() + " " + chunk.content();
    }

    private int estimateTokens(String value) {
        if (value == null || value.isBlank()) {
            return 0;
        }
        int cjk = value.replaceAll("[^\\p{IsHan}]", "").length();
        int words = value.trim().split("\\s+").length;
        return cjk + words;
    }

    private String extension(Path path) {
        String fileName = path.getFileName().toString();
        int index = fileName.lastIndexOf('.');
        return index < 0 ? "txt" : fileName.substring(index + 1).toLowerCase();
    }

    private int intValue(JsonNode node, String field, int fallback) {
        return node.path(field).isNumber() ? node.path(field).asInt() : fallback;
    }

    private int qualityScore(String tier, int requested) {
        int bounded = Math.max(0, Math.min(100, requested));
        return switch (tier) {
            case "official", "standard" -> 100;
            case "teacher_reviewed" -> Math.max(90, Math.min(98, bounded));
            case "academic_open" -> Math.max(80, Math.min(95, bounded));
            case "community" -> Math.min(70, bounded);
            case "web" -> Math.min(50, bounded);
            default -> Math.min(60, bounded);
        };
    }

    private String text(JsonNode node, String field) {
        return node.path(field).asText("").trim();
    }

    private String textOr(JsonNode node, String field, String fallback) {
        String value = text(node, field);
        return value.isBlank() ? fallback : value;
    }

    private String sha256(byte[] bytes) throws Exception {
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(bytes);
        StringBuilder hex = new StringBuilder();
        for (byte value : digest) {
            hex.append(String.format("%02x", value));
        }
        return hex.toString();
    }

    public record ImportReport(
            int documentCount,
            int chunkCount,
            int evaluationCaseCount,
            List<String> warnings
    ) {
    }
}
