package com.contest;

import org.springframework.http.HttpStatus;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseCookie;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CookieValue;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import javax.servlet.http.HttpServletRequest;
import java.time.Duration;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

@RestController
public class ProjectController {

    private static final String AUTH_COOKIE = "AI_TEACHER_SESSION";
    private static final String GUEST_COOKIE = "AI_TEACHER_GUEST";

    private final AuthService authService;
    private final ProjectService projectService;
    private final ClassRoomService classRoomService;
    private final ComputerResourceParser computerResourceParser;
    private final ComputerCoursePromptService computerCoursePromptService;
    private final LabTaskTemplateService labTaskTemplateService;
    private final CodeJudgeService codeJudgeService;

    /** 匿名写接口固定窗口频控：key = bucket:identity，value = [窗口起始, 计数] */
    private static final long ANON_RATE_WINDOW_MS = 60_000L;
    private static final int ANON_RATE_LIMIT_TRACK = 30;
    private static final int ANON_RATE_LIMIT_JUDGE = 10;
    private final ConcurrentHashMap<String, long[]> anonRateCounters = new ConcurrentHashMap<>();

    private boolean anonRateLimited(String bucket, String identity, int limit) {
        if (identity == null || identity.isBlank()) {
            return false;
        }
        long now = System.currentTimeMillis();
        long[] slot = anonRateCounters.compute(bucket + ":" + identity, (k, v) -> {
            if (v == null || now - v[0] >= ANON_RATE_WINDOW_MS) {
                return new long[]{now, 1};
            }
            v[1]++;
            return v;
        });
        if (anonRateCounters.size() > 10_000) {
            anonRateCounters.entrySet().removeIf(e -> now - e.getValue()[0] >= ANON_RATE_WINDOW_MS);
        }
        return slot[1] > limit;
    }

    private String clientIp(HttpServletRequest request) {
        String xff = request.getHeader("X-Forwarded-For");
        return (xff == null || xff.isBlank()) ? request.getRemoteAddr() : xff.split(",")[0].trim();
    }

    public ProjectController(
            AuthService authService,
            ProjectService projectService,
            ClassRoomService classRoomService,
            ComputerResourceParser computerResourceParser,
            ComputerCoursePromptService computerCoursePromptService,
            LabTaskTemplateService labTaskTemplateService,
            CodeJudgeService codeJudgeService
    ) {
        this.authService = authService;
        this.projectService = projectService;
        this.classRoomService = classRoomService;
        this.computerResourceParser = computerResourceParser;
        this.computerCoursePromptService = computerCoursePromptService;
        this.labTaskTemplateService = labTaskTemplateService;
        this.codeJudgeService = codeJudgeService;
    }

    @GetMapping("/projects-api")
    public ResponseEntity<ApiResponse<Map<String, Object>>> listProjects(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        }
        List<ProjectService.ProjectRecord> items = projectService.listProjects(user.getUsername());
        Map<String, Object> data = new HashMap<>();
        data.put("items", items);
        return ResponseEntity.ok(ApiResponse.success("获取项目成功", data));
    }

    @PostMapping("/projects-api")
    public ResponseEntity<ApiResponse<Map<String, Object>>> createProject(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @RequestBody Map<String, String> request
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        }
        ProjectService.ProjectRecord record = projectService.createProject(
                user.getUsername(),
                request.get("name"),
                request.get("meta"),
                request.get("subjectMode"),
                request.get("courseType"),
                request.get("programmingLanguage"),
                request.get("teachingGoal")
        );
        Map<String, Object> data = new HashMap<>();
        data.put("project", record);
        return ResponseEntity.ok(ApiResponse.success("项目创建成功", data));
    }

    @GetMapping("/projects-api/{projectId}")
    public ResponseEntity<ApiResponse<Map<String, Object>>> getProject(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String projectId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        }
        ProjectService.ProjectRecord record = projectService.getProject(user.getUsername(), projectId);
        Map<String, Object> data = new HashMap<>();
        data.put("project", record);
        return ResponseEntity.ok(ApiResponse.success("获取项目详情成功", data));
    }

    @PutMapping("/projects-api/{projectId}")
    public ResponseEntity<ApiResponse<Map<String, Object>>> updateProject(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String projectId,
            @RequestBody Map<String, String> request
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        }
        ProjectService.ProjectRecord record = projectService.updateProjectContent(
                user.getUsername(),
                projectId,
                request.get("pptRawText"),
                request.get("script"),
                request.get("summary"),
                request.get("audioUrl"),
                request.get("digitalUrl"),
                request.get("lessonTitle"),
                request.get("lessonIntro"),
                request.get("subjectMode"),
                request.get("courseType"),
                request.get("programmingLanguage"),
                request.get("teachingGoal"),
                request.get("name"),
                request.get("meta")
        );
        Map<String, Object> data = new HashMap<>();
        data.put("project", record);
        return ResponseEntity.ok(ApiResponse.success("项目更新成功", data));
    }

    @PostMapping("/projects-api/{projectId}/publish")
    public ResponseEntity<ApiResponse<Map<String, Object>>> publishProject(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String projectId,
            @RequestBody Map<String, String> request
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        }
        ProjectService.ProjectRecord record = projectService.publishProject(
                user.getUsername(),
                projectId,
                request.get("lessonTitle"),
                request.get("lessonIntro"),
                request.get("audioUrl"),
                request.get("digitalUrl")
        );
        Map<String, Object> data = new HashMap<>();
        data.put("project", record);
        return ResponseEntity.ok(ApiResponse.success("智课发布成功", data));
    }

    @GetMapping("/published-lessons")
    public ResponseEntity<ApiResponse<Map<String, Object>>> listPublishedLessons(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_STUDENT, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_STUDENT, AuthService.ROLE_ADMIN);
        }
        if (isStaff(user)) {
            Map<String, Object> data = new HashMap<>();
            data.put("items", projectService.listPublishedProjects());
            return ResponseEntity.ok(ApiResponse.success("获取已发布智课成功", data));
        }
        List<ProjectService.PublishedLessonView> views = projectService.listPublishedLessonViews().stream()
                .filter(v -> !classRoomService.isClassOnlyPublished(v.getId())
                        || classRoomService.listClassOnlyProjectIdsForStudent(user.getUsername()).contains(v.getId()))
                .collect(java.util.stream.Collectors.toList());
        Map<String, Object> data = new HashMap<>();
        data.put("items", views);
        return ResponseEntity.ok(ApiResponse.success("获取已发布智课成功", data));
    }

    @GetMapping("/public/published-lessons")
    public ResponseEntity<ApiResponse<Map<String, Object>>> listPublishedLessonsPublic() {
        List<ProjectService.PublishedLessonView> items = projectService.listPublishedLessonViews().stream()
                .filter(v -> !classRoomService.isClassOnlyPublished(v.getId()))
                .collect(java.util.stream.Collectors.toList());
        Map<String, Object> data = new HashMap<>();
        data.put("items", items);
        return ResponseEntity.ok(ApiResponse.success("获取已发布智课成功", data));
    }

    @GetMapping("/published-lessons/{projectId}")
    public ResponseEntity<ApiResponse<Map<String, Object>>> getPublishedLesson(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String projectId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_STUDENT, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_STUDENT, AuthService.ROLE_ADMIN);
        }
        Object record = isStaff(user)
                ? projectService.toTeacherInsightProject(projectService.getPublishedProject(projectId), authService)
                : projectService.getPublishedLessonView(projectId);
        Map<String, Object> data = new HashMap<>();
        data.put("project", record);
        return ResponseEntity.ok(ApiResponse.success("获取智课详情成功", data));
    }

    @GetMapping("/public/published-lessons/{projectId}")
    public ResponseEntity<ApiResponse<Map<String, Object>>> getPublishedLessonPublic(
            @PathVariable String projectId
    ) {
        ProjectService.PublishedLessonView record = projectService.getPublishedLessonView(projectId);
        Map<String, Object> data = new HashMap<>();
        data.put("project", record);
        return ResponseEntity.ok(ApiResponse.success("获取智课详情成功", data));
    }

    @PostMapping("/published-lessons/{projectId}/track")
    public ResponseEntity<ApiResponse<Map<String, Object>>> trackLearning(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String projectId,
            @RequestBody Map<String, Object> request
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_STUDENT, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_STUDENT, AuthService.ROLE_ADMIN);
        }
        // 教师/管理员预览学生端时不写入学情，避免把老师算进学生学习名单
        if (isStaff(user)) {
            Map<String, Object> data = new HashMap<>();
            data.put("project", projectService.toTeacherInsightProject(
                    projectService.getPublishedProject(projectId), authService));
            data.put("tracked", false);
            data.put("skippedReason", "staff_preview");
            return ResponseEntity.ok(ApiResponse.success("教师预览不计入学情", data));
        }
        ProjectService.ProjectRecord record = appendLearningRecordForUser(user.getUsername(), projectId, request);
        Map<String, Object> data = new HashMap<>();
        data.put("project", projectService.getPublishedLessonView(projectId));
        data.put("tracked", true);
        return ResponseEntity.ok(ApiResponse.success("学习记录保存成功", data));
    }

    @PostMapping("/public/published-lessons/{projectId}/track")
    public ResponseEntity<ApiResponse<Map<String, Object>>> trackLearningPublic(
            @CookieValue(value = GUEST_COOKIE, required = false) String guestCookie,
            @PathVariable String projectId,
            @RequestBody Map<String, Object> request,
            HttpServletRequest servletRequest
    ) {
        String guestId = validGuestId(guestCookie)
                ? guestCookie
                : UUID.randomUUID().toString().replace("-", "");
        if (anonRateLimited("track", guestId + "|" + clientIp(servletRequest), ANON_RATE_LIMIT_TRACK)) {
            return ResponseEntity.status(429)
                    .body(ApiResponse.<Map<String, Object>>error("学习记录上报过于频繁，请稍后再试"));
        }
        ProjectService.ProjectRecord record = appendLearningRecordForUser(
                "guest_" + guestId,
                projectId,
                request
        );
        Map<String, Object> data = new HashMap<>();
        data.put("project", projectService.getPublishedLessonView(projectId));
        data.put("saved", record != null);
        ResponseCookie cookie = ResponseCookie.from(GUEST_COOKIE, guestId)
                .httpOnly(true)
                .sameSite("Lax")
                .path("/")
                .maxAge(Duration.ofDays(180))
                .build();
        return ResponseEntity.ok()
                .header(HttpHeaders.SET_COOKIE, cookie.toString())
                .body(ApiResponse.success("学习记录保存成功", data));
    }

    @PostMapping("/projects-api/{projectId}/resources")
    public ResponseEntity<ApiResponse<Map<String, Object>>> uploadProjectResource(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String projectId,
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "resourceType", required = false) String resourceType,
            @RequestParam(value = "language", required = false) String language
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        }
        ProjectService.ProjectResource resource = computerResourceParser.parse(file, resourceType, language);
        ProjectService.ProjectRecord record = projectService.addResource(user.getUsername(), projectId, resource);
        Map<String, Object> data = new HashMap<>();
        data.put("resource", resource);
        data.put("project", record);
        return ResponseEntity.ok(ApiResponse.success("计算机课程资料解析成功", data));
    }

    @DeleteMapping("/projects-api/{projectId}/resources/{resourceId}")
    public ResponseEntity<ApiResponse<Map<String, Object>>> deleteProjectResource(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String projectId,
            @PathVariable String resourceId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        }
        ProjectService.ProjectRecord record = projectService.deleteResource(user.getUsername(), projectId, resourceId);
        Map<String, Object> data = new HashMap<>();
        data.put("project", record);
        return ResponseEntity.ok(ApiResponse.success("专项资料已删除", data));
    }

    @PostMapping("/projects-api/{projectId}/lab-tasks/generate")
    public ResponseEntity<ApiResponse<Map<String, Object>>> generateLabTask(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String projectId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        }
        ProjectService.ProjectRecord project = projectService.getProject(user.getUsername(), projectId);
        ProjectService.LabTask task = labTaskTemplateService.generate(project);
        ProjectService.ProjectRecord record = projectService.addLabTask(user.getUsername(), projectId, task);
        Map<String, Object> data = new HashMap<>();
        data.put("task", task);
        data.put("project", record);
        return ResponseEntity.ok(ApiResponse.success("实验任务生成成功", data));
    }

    @DeleteMapping("/projects-api/{projectId}/lab-tasks/{taskId}")
    public ResponseEntity<ApiResponse<Map<String, Object>>> deleteLabTask(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String projectId,
            @PathVariable String taskId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        }
        ProjectService.ProjectRecord record = projectService.deleteLabTask(user.getUsername(), projectId, taskId);
        Map<String, Object> data = new HashMap<>();
        data.put("project", record);
        return ResponseEntity.ok(ApiResponse.success("实验任务已删除", data));
    }

    @PostMapping("/published-lessons/{projectId}/lab-tasks/{taskId}/submit")
    public ResponseEntity<ApiResponse<Map<String, Object>>> submitLabTask(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String projectId,
            @PathVariable String taskId,
            @RequestBody Map<String, String> request
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_STUDENT);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId, AuthService.ROLE_STUDENT);
        }
        return judgeSubmission(user.getUsername(), projectId, taskId, request.get("sourceCode"), null);
    }

    @PostMapping("/public/published-lessons/{projectId}/lab-tasks/{taskId}/submit")
    public ResponseEntity<ApiResponse<Map<String, Object>>> submitLabTaskPublic(
            @CookieValue(value = GUEST_COOKIE, required = false) String guestCookie,
            @PathVariable String projectId,
            @PathVariable String taskId,
            @RequestBody Map<String, String> request,
            HttpServletRequest servletRequest
    ) {
        String guestId = validGuestId(guestCookie)
                ? guestCookie
                : UUID.randomUUID().toString().replace("-", "");
        if (anonRateLimited("judge", guestId + "|" + clientIp(servletRequest), ANON_RATE_LIMIT_JUDGE)) {
            return ResponseEntity.status(429)
                    .body(ApiResponse.<Map<String, Object>>error("提交过于频繁，请稍后再试"));
        }
        ResponseCookie cookie = ResponseCookie.from(GUEST_COOKIE, guestId)
                .httpOnly(true)
                .sameSite("Lax")
                .path("/")
                .maxAge(Duration.ofDays(180))
                .build();
        return judgeSubmission(
                "guest_" + guestId,
                projectId,
                taskId,
                request.get("sourceCode"),
                cookie
        );
    }

    @DeleteMapping("/projects-api/{projectId}")
    public ResponseEntity<ApiResponse<Map<String, Object>>> deleteProject(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String projectId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        }
        projectService.deleteProject(user.getUsername(), projectId);
        // 删除项目后清理所有班级里的悬空绑定与发布引用
        classRoomService.pruneMissingProjectsForTeacher(user.getUsername(), id -> projectService.getProject(user.getUsername(), id) != null);
        return ResponseEntity.ok(ApiResponse.success("项目删除成功", new HashMap<>()));
    }

    private AuthService.AuthUserView requireUser(String sessionId, String... allowedRoles) {
        AuthService.AuthUserView user = authService.getUserBySession(sessionId);
        if (user == null) {
            return null;
        }
        if (allowedRoles == null || allowedRoles.length == 0) {
            return user;
        }
        return authService.hasActiveRole(sessionId, allowedRoles) ? user : null;
    }

    private ResponseEntity<ApiResponse<Map<String, Object>>> forbiddenOrUnauthorized(String sessionId, String... allowedRoles) {
        if (authService.getUserBySession(sessionId) == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(ApiResponse.error("未登录"));
        }
        return ResponseEntity.status(HttpStatus.FORBIDDEN).body(ApiResponse.error("当前身份无权访问该资源"));
    }

    private ProjectService.ProjectRecord appendLearningRecordForUser(
            String learnerUsername,
            String projectId,
            Map<String, Object> request
    ) {
        double progressPercent = 0;
        Object rawProgress = request.get("progressPercent");
        if (rawProgress instanceof Number) {
            progressPercent = ((Number) rawProgress).doubleValue();
        } else if (rawProgress != null) {
            try {
                progressPercent = Double.parseDouble(String.valueOf(rawProgress));
            } catch (NumberFormatException ignored) {
                progressPercent = 0;
            }
        }

        String finalLearner = learnerUsername == null || learnerUsername.trim().isEmpty()
                ? "guest"
                : learnerUsername.trim();
        String action = normalizeAction(String.valueOf(request.getOrDefault("action", "study")));
        String resourceId = limitText(String.valueOf(request.getOrDefault("resourceId", "")), 120);
        if ("resolve-question".equals(action)) {
            return projectService.resolveLatestQuestion(finalLearner, projectId, resourceId);
        }
        String question = limitText(String.valueOf(request.getOrDefault("question", "")), 4000);
        String questionType = computerCoursePromptService.classifyQuestionType(
                String.valueOf(request.getOrDefault("questionType", "")),
                question
        );
        String errorType = "debug".equals(questionType)
                ? computerCoursePromptService.detectErrorType(question)
                : "";
        return projectService.appendLearningRecord(
                finalLearner,
                projectId,
                limitText(String.valueOf(request.getOrDefault("currentSectionId", "")), 120),
                progressPercent,
                question,
                limitText(String.valueOf(request.getOrDefault("answer", "")), 8000),
                limitText(String.valueOf(request.getOrDefault("understandingLevel", "")), 64),
                action,
                questionType,
                resourceId,
                errorType,
                "debug".equals(questionType) ? "1" : "0",
                false
        );
    }

    private boolean isStaff(AuthService.AuthUserView user) {
        return user != null && (user.hasActiveRole(AuthService.ROLE_TEACHER)
                || user.hasActiveRole(AuthService.ROLE_ADMIN));
    }

    private boolean validGuestId(String value) {
        return value != null && value.matches("[a-f0-9]{32}");
    }

    private ResponseEntity<ApiResponse<Map<String, Object>>> judgeSubmission(
            String learnerUsername,
            String projectId,
            String taskId,
            String sourceCode,
            ResponseCookie guestCookie
    ) {
        ProjectService.LabTask task = projectService.getPublishedLabTask(projectId, taskId);
        CodeJudgeService.JudgeResult result = codeJudgeService.judge(task, sourceCode);
        ProjectService.CodeSubmission submission = projectService.addCodeSubmission(
                learnerUsername,
                projectId,
                task,
                sourceCode,
                result
        );
        Map<String, Object> data = new HashMap<>();
        data.put("submission", submission);
        ResponseEntity.BodyBuilder response = ResponseEntity.ok();
        if (guestCookie != null) {
            response.header(HttpHeaders.SET_COOKIE, guestCookie.toString());
        }
        return response.body(ApiResponse.success("代码判题完成", data));
    }

    private String normalizeAction(String action) {
        return List.of("study", "enter-lesson", "ask-question", "continue-lecture", "resolve-question")
                .contains(action) ? action : "study";
    }

    private String limitText(String value, int maxLength) {
        String text = value == null ? "" : value.trim();
        return text.length() > maxLength ? text.substring(0, maxLength) : text;
    }

    @org.springframework.web.bind.annotation.ExceptionHandler(ProjectService.ProjectException.class)
    public ResponseEntity<ApiResponse<Map<String, Object>>> handleProjectException(ProjectService.ProjectException ex) {
        return ResponseEntity.badRequest().body(ApiResponse.error(ex.getMessage()));
    }
}
