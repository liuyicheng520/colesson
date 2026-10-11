package com.contest;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CookieValue;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
public class KnowledgeAdminController {

    private static final String AUTH_COOKIE = "AI_TEACHER_SESSION";

    private final AuthService authService;
    private final KnowledgeCatalogImporter importer;
    private final KnowledgeRetrievalService retrievalService;
    private final KnowledgeEvaluationService evaluationService;

    public KnowledgeAdminController(
            AuthService authService,
            KnowledgeCatalogImporter importer,
            KnowledgeRetrievalService retrievalService,
            KnowledgeEvaluationService evaluationService
    ) {
        this.authService = authService;
        this.importer = importer;
        this.retrievalService = retrievalService;
        this.evaluationService = evaluationService;
    }

    @GetMapping("/admin-api/knowledge/stats")
    public ResponseEntity<ApiResponse<Map<String, Object>>> stats(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId
    ) {
        ResponseEntity<ApiResponse<Map<String, Object>>> auth = requireAdmin(sessionId);
        if (auth != null) {
            return auth;
        }
        try {
            return ResponseEntity.ok(ApiResponse.success("获取知识库统计成功", importer.catalogSummary()));
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(ApiResponse.error("获取知识库统计失败：" + e.getMessage()));
        }
    }

    @PostMapping("/admin-api/knowledge/import")
    public ResponseEntity<ApiResponse<Map<String, Object>>> importCatalog(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId
    ) {
        ResponseEntity<ApiResponse<Map<String, Object>>> auth = requireAdmin(sessionId);
        if (auth != null) {
            return auth;
        }
        try {
            KnowledgeCatalogImporter.ImportReport report = importer.importCatalog();
            Map<String, Object> data = new LinkedHashMap<>();
            data.put("documentCount", report.documentCount());
            data.put("chunkCount", report.chunkCount());
            data.put("evaluationCaseCount", report.evaluationCaseCount());
            data.put("warnings", report.warnings());
            return ResponseEntity.ok(ApiResponse.success("知识库导入完成", data));
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(ApiResponse.error("知识库导入失败：" + e.getMessage()));
        }
    }

    @PostMapping("/admin-api/knowledge/search")
    public ResponseEntity<ApiResponse<Map<String, Object>>> search(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @RequestBody Map<String, Object> request
    ) {
        ResponseEntity<ApiResponse<Map<String, Object>>> auth = requireAdmin(sessionId);
        if (auth != null) {
            return auth;
        }
        String courseCode = String.valueOf(request.getOrDefault("courseCode", ""));
        String question = String.valueOf(request.getOrDefault("question", ""));
        int topK = parseInt(request.get("topK"), 5);
        List<KnowledgeRetrievalService.Hit> hits = retrievalService.search(courseCode, question, topK);
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("courseCode", retrievalService.normalizeCourseCode(courseCode));
        data.put("question", question);
        data.put("sources", retrievalService.sourceViews(hits));
        data.put("context", retrievalService.formatContext(hits));
        return ResponseEntity.ok(ApiResponse.success("知识库检索完成", data));
    }

    @PostMapping("/admin-api/knowledge/evaluate")
    public ResponseEntity<ApiResponse<Map<String, Object>>> evaluate(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId
    ) {
        ResponseEntity<ApiResponse<Map<String, Object>>> auth = requireAdmin(sessionId);
        if (auth != null) {
            return auth;
        }
        try {
            return ResponseEntity.ok(ApiResponse.success("知识库评测完成", evaluationService.run()));
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(ApiResponse.error("知识库评测失败：" + e.getMessage()));
        }
    }

    private ResponseEntity<ApiResponse<Map<String, Object>>> requireAdmin(String sessionId) {
        AuthService.AuthUserView user = authService.getUserBySession(sessionId);
        if (user == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(ApiResponse.error("未登录"));
        }
        if (!authService.hasActiveRole(sessionId, AuthService.ROLE_ADMIN)) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body(ApiResponse.error("当前身份无权访问该资源"));
        }
        return null;
    }

    private int parseInt(Object value, int fallback) {
        try {
            return Math.max(1, Math.min(20, Integer.parseInt(String.valueOf(value))));
        } catch (Exception ignored) {
            return fallback;
        }
    }
}
