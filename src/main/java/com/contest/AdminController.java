package com.contest;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CookieValue;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
public class AdminController {

    private static final String AUTH_COOKIE = "AI_TEACHER_SESSION";

    private final AuthService authService;
    private final ProjectService projectService;

    public AdminController(AuthService authService, ProjectService projectService) {
        this.authService = authService;
        this.projectService = projectService;
    }

    @GetMapping("/admin-api/overview")
    public ResponseEntity<ApiResponse<Map<String, Object>>> overview(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @RequestParam(value = "projectLimit", required = false, defaultValue = "20") int projectLimit,
            @RequestParam(value = "learningLimit", required = false, defaultValue = "12") int learningLimit
    ) {
        AuthService.AuthUserView operator;
        try {
            operator = authService.requireAdmin(sessionId);
        } catch (AuthService.AuthException ex) {
            return authError(ex);
        }
        boolean contentOnly = AuthService.ADMIN_LEVEL_CONTENT.equals(operator.getAdminLevel());

        List<AuthService.AuthUserView> users = authService.listUsersForAdmin();
        List<ProjectService.ProjectRecord> projects = projectService.listAllProjectsForAdmin();
        int safeProjectLimit = clamp(projectLimit, 1, 100);
        int safeLearningLimit = clamp(learningLimit, 1, 100);

        int publishedCount = 0;
        int learningRecordCount = 0;
        int teacherCount = 0;
        int studentCount = 0;
        int adminCount = 0;
        int disabledCount = 0;
        Map<String, Integer> roleCounts = new LinkedHashMap<>();
        Map<String, Integer> teacherProjectCounts = new LinkedHashMap<>();
        List<Map<String, Object>> projectRows = new ArrayList<>();
        List<Map<String, Object>> learningRows = new ArrayList<>();

        for (AuthService.AuthUserView item : users) {
            if (item.isDisabled()) {
                disabledCount += 1;
            }
            boolean isTeacher = false;
            boolean isStudent = false;
            boolean isAdmin = false;
            for (String role : item.getRoles()) {
                roleCounts.put(role, roleCounts.getOrDefault(role, 0) + 1);
                if (AuthService.ROLE_TEACHER.equals(role)) isTeacher = true;
                if (AuthService.ROLE_STUDENT.equals(role)) isStudent = true;
                if (AuthService.ROLE_ADMIN.equals(role)) isAdmin = true;
            }
            if (isTeacher) teacherCount += 1;
            if (isStudent) studentCount += 1;
            if (isAdmin) adminCount += 1;
        }

        for (ProjectService.ProjectRecord project : projects) {
            if (project.isPublished()) {
                publishedCount += 1;
            }
            List<ProjectService.LearningRecord> records = project.getLearningRecords();
            int recordCount = records == null ? 0 : records.size();
            learningRecordCount += recordCount;
            teacherProjectCounts.put(project.getUsername(), teacherProjectCounts.getOrDefault(project.getUsername(), 0) + 1);

            Map<String, Object> row = new LinkedHashMap<>();
            row.put("id", project.getId());
            row.put("username", project.getUsername());
            row.put("name", project.getName());
            row.put("published", project.isPublished());
            row.put("publishedAt", project.getPublishedAt());
            row.put("updatedAt", project.getUpdatedAt());
            row.put("lessonTitle", project.getLessonTitle());
            row.put("learningRecordCount", recordCount);
            row.put("hasScript", project.getScript() != null && !project.getScript().trim().isEmpty());
            row.put("hasPptText", project.getPptRawText() != null && !project.getPptRawText().trim().isEmpty());
            projectRows.add(row);

            if (records != null) {
                for (ProjectService.LearningRecord record : records) {
                    Map<String, Object> learning = new LinkedHashMap<>();
                    learning.put("projectId", project.getId());
                    learning.put("projectName", project.getName());
                    learning.put("learnerUsername", record.getLearnerUsername());
                    learning.put("currentSectionId", record.getCurrentSectionId());
                    learning.put("progressPercent", record.getProgressPercent());
                    learning.put("question", record.getQuestion());
                    learning.put("action", record.getAction());
                    learning.put("createdAt", record.getCreatedAt());
                    learningRows.add(learning);
                }
            }
        }

        learningRows.sort((a, b) -> String.valueOf(b.get("createdAt")).compareTo(String.valueOf(a.get("createdAt"))));
        if (projectRows.size() > safeProjectLimit) {
            projectRows = new ArrayList<>(projectRows.subList(0, safeProjectLimit));
        }
        if (learningRows.size() > safeLearningLimit) {
            learningRows = new ArrayList<>(learningRows.subList(0, safeLearningLimit));
        }

        int pendingResets = 0;
        try {
            for (AuthService.PasswordResetRequest req : authService.listPasswordResetRequests(sessionId, "pending")) {
                pendingResets += 1;
            }
        } catch (AuthService.AuthException ignored) {
            pendingResets = 0;
        }

        Map<String, Object> data = new HashMap<>();
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("userCount", users.size());
        summary.put("teacherCount", teacherCount);
        summary.put("studentCount", studentCount);
        summary.put("adminCount", adminCount);
        summary.put("disabledCount", disabledCount);
        summary.put("projectCount", projects.size());
        summary.put("publishedCount", publishedCount);
        summary.put("learningRecordCount", learningRecordCount);
        summary.put("pendingResetCount", pendingResets);
        summary.put("roleCounts", roleCounts);
        summary.put("teacherProjectCounts", teacherProjectCounts);

        data.put("summary", summary);
        data.put("users", contentOnly ? new ArrayList<AuthService.AuthUserView>() : users);
        data.put("projects", projectRows);
        data.put("recentLearningRecords", learningRows);
        return ResponseEntity.ok(ApiResponse.success("获取管理员概览成功", data));
    }

    @GetMapping("/admin-api/users")
    public ResponseEntity<ApiResponse<Map<String, Object>>> listUsers(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @RequestParam(value = "role", required = false, defaultValue = "all") String role,
            @RequestParam(value = "q", required = false, defaultValue = "") String q
    ) {
        try {
            authService.requireAdmin(sessionId);
            authService.requireAdminLevel(sessionId, AuthService.ADMIN_LEVEL_SUPER, AuthService.ADMIN_LEVEL_OPS);
        } catch (AuthService.AuthException ex) {
            return authError(ex);
        }
        String roleFilter = role == null ? "all" : role.trim().toLowerCase();
        String query = q == null ? "" : q.trim().toLowerCase();
        List<AuthService.AuthUserView> all = authService.listUsersForAdmin();
        List<AuthService.AuthUserView> filtered = new ArrayList<>();
        for (AuthService.AuthUserView user : all) {
            if (!"all".equals(roleFilter) && !user.getRoles().contains(roleFilter)) {
                continue;
            }
            if (!query.isEmpty() && !String.valueOf(user.getUsername()).toLowerCase().contains(query)) {
                continue;
            }
            filtered.add(user);
        }
        Map<String, Object> data = new HashMap<>();
        data.put("users", filtered);
        data.put("total", filtered.size());
        return ResponseEntity.ok(ApiResponse.success("获取用户列表成功", data));
    }

    @PostMapping("/admin-api/users")
    public ResponseEntity<ApiResponse<Map<String, Object>>> createUser(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @RequestBody Map<String, Object> body
    ) {
        try {
            @SuppressWarnings("unchecked")
            List<String> roles = body.get("roles") instanceof List ? (List<String>) body.get("roles") : null;
            AuthService.AuthUserView created = authService.createUserByAdmin(
                    sessionId,
                    stringVal(body.get("username")),
                    stringVal(body.get("password")),
                    roles,
                    stringVal(body.get("adminLevel"))
            );
            Map<String, Object> data = new HashMap<>();
            data.put("user", created);
            return ResponseEntity.ok(ApiResponse.success("账号创建成功", data));
        } catch (AuthService.AuthException ex) {
            return authError(ex);
        }
    }

    @PostMapping("/admin-api/users/{username}/update")
    public ResponseEntity<ApiResponse<Map<String, Object>>> updateUser(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable("username") String username,
            @RequestBody Map<String, Object> body
    ) {
        try {
            @SuppressWarnings("unchecked")
            List<String> roles = body.containsKey("roles") && body.get("roles") instanceof List
                    ? (List<String>) body.get("roles") : null;
            Boolean disabled = null;
            if (body.containsKey("disabled")) {
                disabled = Boolean.TRUE.equals(body.get("disabled")) || "true".equalsIgnoreCase(stringVal(body.get("disabled")));
            }
            AuthService.AuthUserView updated = authService.updateUserByAdmin(
                    sessionId,
                    username,
                    roles,
                    body.containsKey("adminLevel") ? stringVal(body.get("adminLevel")) : null,
                    disabled
            );
            Map<String, Object> data = new HashMap<>();
            data.put("user", updated);
            return ResponseEntity.ok(ApiResponse.success("账号更新成功", data));
        } catch (AuthService.AuthException ex) {
            return authError(ex);
        }
    }

    @PostMapping("/admin-api/users/{username}/reset-password")
    public ResponseEntity<ApiResponse<Map<String, Object>>> resetPassword(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable("username") String username,
            @RequestBody(required = false) Map<String, String> body
    ) {
        try {
            String newPassword = body == null ? "" : body.get("newPassword");
            String password = authService.resetPasswordByAdmin(sessionId, username, newPassword);
            Map<String, Object> data = new HashMap<>();
            data.put("username", username);
            data.put("tempPassword", password);
            return ResponseEntity.ok(ApiResponse.success("密码已重置", data));
        } catch (AuthService.AuthException ex) {
            return authError(ex);
        }
    }

    @GetMapping("/admin-api/password-resets")
    public ResponseEntity<ApiResponse<Map<String, Object>>> listResets(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @RequestParam(value = "status", required = false, defaultValue = "pending") String status
    ) {
        try {
            List<AuthService.PasswordResetRequest> items = authService.listPasswordResetRequests(sessionId, status);
            Map<String, Object> data = new HashMap<>();
            data.put("items", items);
            data.put("total", items.size());
            return ResponseEntity.ok(ApiResponse.success("获取重置申请成功", data));
        } catch (AuthService.AuthException ex) {
            return authError(ex);
        }
    }

    @PostMapping("/admin-api/password-resets/{id}/resolve")
    public ResponseEntity<ApiResponse<Map<String, Object>>> resolveReset(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable("id") String id,
            @RequestBody Map<String, String> body
    ) {
        try {
            AuthService.PasswordResetRequest item = authService.resolvePasswordResetRequest(
                    sessionId,
                    id,
                    body.get("action"),
                    body.get("newPassword")
            );
            Map<String, Object> data = new HashMap<>();
            data.put("item", item);
            return ResponseEntity.ok(ApiResponse.success("申请已处理", data));
        } catch (AuthService.AuthException ex) {
            return authError(ex);
        }
    }

    @GetMapping("/admin-api/audits")
    public ResponseEntity<ApiResponse<Map<String, Object>>> audits(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @RequestParam(value = "limit", required = false, defaultValue = "80") int limit
    ) {
        try {
            List<AuthService.AdminAuditEntry> items = authService.listAdminAudits(sessionId, limit);
            Map<String, Object> data = new HashMap<>();
            data.put("items", items);
            return ResponseEntity.ok(ApiResponse.success("获取审计日志成功", data));
        } catch (AuthService.AuthException ex) {
            return authError(ex);
        }
    }

    private ResponseEntity<ApiResponse<Map<String, Object>>> authError(AuthService.AuthException ex) {
        String message = ex.getMessage() == null ? "操作失败" : ex.getMessage();
        if (message.contains("未登录")) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(ApiResponse.error(message));
        }
        if (message.contains("无权") || message.contains("管理员")) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body(ApiResponse.error(message));
        }
        return ResponseEntity.badRequest().body(ApiResponse.error(message));
    }

    private String stringVal(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private int clamp(int value, int min, int max) {
        return Math.max(min, Math.min(max, value));
    }
}
