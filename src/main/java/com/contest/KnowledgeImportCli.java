package com.contest;

import com.fasterxml.jackson.databind.ObjectMapper;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;

public final class KnowledgeImportCli {

    private KnowledgeImportCli() {
    }

    public static void main(String[] args) throws Exception {
        String url = env(
                "APP_MYSQL_URL",
                "jdbc:mysql://127.0.0.1:3306/zhike_gongsheng"
                        + "?useUnicode=true&characterEncoding=utf8"
                        + "&serverTimezone=Asia/Shanghai&useSSL=false"
                        + "&allowPublicKeyRetrieval=true"
        );
        String username = env("APP_MYSQL_USERNAME", "root");
        String password = env("APP_MYSQL_PASSWORD", "");
        String catalogFile = env("KNOWLEDGE_CATALOG_FILE", "data/knowledge/catalog.json");

        DatabaseStore databaseStore = new DatabaseStore();
        databaseStore.configureForCli(url, username, password);
        // The guarded shell runner applies V4 before invoking this process.
        databaseStore.markSchemaInitializedForCli();

        KnowledgeRepository repository = new KnowledgeRepository(databaseStore);
        KnowledgeRetrievalService retrievalService = new KnowledgeRetrievalService(repository);
        KnowledgeCatalogImporter importer = new KnowledgeCatalogImporter(
                databaseStore,
                new KnowledgeChunker(),
                repository,
                retrievalService
        );
        importer.setCatalogFile(catalogFile);
        KnowledgeEvaluationService evaluationService = new KnowledgeEvaluationService(
                repository,
                retrievalService
        );

        try {
            KnowledgeCatalogImporter.ImportReport importReport = importer.importCatalog();
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("import", importReport);
            result.put("stats", repository.stats());
            result.put("evaluation", evaluationService.run());
            String json = new ObjectMapper().writerWithDefaultPrettyPrinter().writeValueAsString(result);
            String reportFile = System.getenv("KNOWLEDGE_IMPORT_REPORT_FILE");
            if (reportFile != null && !reportFile.isBlank()) {
                Path reportPath = Path.of(reportFile).toAbsolutePath().normalize();
                Files.createDirectories(reportPath.getParent());
                Files.writeString(reportPath, json, StandardCharsets.UTF_8);
                System.out.println("Knowledge import report written to " + reportPath);
            } else {
                System.out.println(json);
            }
        } finally {
            databaseStore.close();
        }
    }

    private static String env(String name, String fallback) {
        String value = System.getenv(name);
        return value == null || value.isBlank() ? fallback : value.trim();
    }
}
