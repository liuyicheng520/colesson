package com.contest;

import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
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

import java.nio.file.Path;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
public class ClassRoomController {

    private static final String AUTH_COOKIE = "AI_TEACHER_SESSION";

    private final AuthService authService;
    private final ClassRoomService classRoomService;
    private final ProjectService projectService;

    public ClassRoomController(AuthService authService, ClassRoomService classRoomService, ProjectService projectService) {
        this.authService = authService;
        this.classRoomService = classRoomService;
        this.projectService = projectService;
    }

    @GetMapping({"/api/v1/classes", "/classes-api"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> listTeacherClasses(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        List<ClassRoomService.ClassRoom> rooms = classRoomService.listByTeacher(user.getUsername());
        List<Map<String, Object>> items = new java.util.ArrayList<>();
        for (ClassRoomService.ClassRoom room : rooms) {
            Map<String, Object> card = new HashMap<>();
            card.put("class", room);
            try {
                card.put("overview", classRoomService.classAnalytics(room.teacherUsername, room.id));
            } catch (Exception e) {
                Map<String, Object> ov = new HashMap<>();
                ov.put("memberCount", room.memberUsernames == null ? 0 : room.memberUsernames.size());
                ov.put("homeworkCount", 0);
                ov.put("boundProjectCount", room.projectIds == null ? 0 : room.projectIds.size());
                ov.put("classPublishedCount", room.publishedProjectIds == null ? 0 : room.publishedProjectIds.size());
                card.put("overview", ov);
            }
            items.add(card);
        }
        Map<String, Object> data = new HashMap<>();
        data.put("items", items);
        return ResponseEntity.ok(ApiResponse.success("ok", data));
    }

    @PostMapping({"/api/v1/classes", "/classes-api"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> createClass(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @RequestBody Map<String, String> request
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        ClassRoomService.ClassRoom room = classRoomService.createClass(
                user.getUsername(),
                str(request.get("name")),
                str(request.get("subject")),
                str(request.get("description"))
        );
        Map<String, Object> data = new HashMap<>();
        data.put("class", room);
        return ResponseEntity.ok(ApiResponse.success("班级已创建", data));
    }

    @GetMapping({"/api/v1/classes/{classId}", "/classes-api/{classId}"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> getClass(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN, AuthService.ROLE_STUDENT);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        ClassRoomService.ClassRoom room = classRoomService.getForMember(user.getUsername(), classId);
        final String classTeacher = room.teacherUsername;
        boolean isOwner = user.getUsername() != null
                && user.getUsername().equalsIgnoreCase(classTeacher);
        boolean isAssistant = room.assistantUsernames != null
                && room.assistantUsernames.stream().anyMatch(a -> a.equalsIgnoreCase(user.getUsername()));
        // Drop stale project refs so橱窗 never shows「课程模型不可用」placeholders.
        java.util.function.Predicate<String> alive = pid -> {
            try {
                projectService.getProject(classTeacher, pid);
                return true;
            } catch (Exception e) {
                return false;
            }
        };
        try {
            room = classRoomService.pruneMissingProjects(classTeacher, classId, alive);
        } catch (Exception ignored) {
            // Students / non-staff still get filtered resolveProjects below.
        }
        Map<String, Object> data = new HashMap<>();
        data.put("class", room);
        data.put("isTeacher", isOwner);
        data.put("isAssistant", isAssistant);
        data.put("isStaff", isOwner || isAssistant);
        data.put("projects", resolveProjects(room.teacherUsername, room.projectIds));
        data.put("publishedProjects", resolveProjects(room.teacherUsername, room.publishedProjectIds));
        Map<String, Object> overview = new HashMap<>();
        Map<String, Long> byStudent = new HashMap<>();
        try {
            overview = classRoomService.classAnalytics(room.teacherUsername, classId);
            @SuppressWarnings("unchecked")
            Map<String, Long> map = (Map<String, Long>) overview.get("submissionByStudent");
            if (map != null) {
                byStudent = map;
            }
        } catch (Exception ignored) {
            overview.put("memberCount", room.memberUsernames == null ? 0 : room.memberUsernames.size());
            overview.put("boundProjectCount", room.projectIds == null ? 0 : room.projectIds.size());
            overview.put("classPublishedCount", room.publishedProjectIds == null ? 0 : room.publishedProjectIds.size());
        }
        data.put("overview", overview);
        List<Map<String, Object>> members = new java.util.ArrayList<>();
        if (room.memberUsernames != null) {
            for (String name : room.memberUsernames) {
                Map<String, Object> brief = authService.describeUserBrief(name);
                brief.put("roleLabel", "学生");
                brief.put("submissionCount", byStudent.getOrDefault(name, 0L));
                members.add(brief);
            }
        }
        data.put("members", members);
        List<Map<String, Object>> assistants = new java.util.ArrayList<>();
        if (room.assistantUsernames != null) {
            for (String name : room.assistantUsernames) {
                Map<String, Object> brief = authService.describeUserBrief(name);
                brief.put("roleLabel", "助教");
                assistants.add(brief);
            }
        }
        data.put("assistants", assistants);
        return ResponseEntity.ok(ApiResponse.success("ok", data));
    }

    @PutMapping({"/api/v1/classes/{classId}", "/classes-api/{classId}"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> updateClass(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId,
            @RequestBody Map<String, String> request
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        ClassRoomService.ClassRoom room = classRoomService.updateClass(
                user.getUsername(), classId,
                request.get("name"), request.get("subject"), request.get("description")
        );
        Map<String, Object> data = new HashMap<>();
        data.put("class", room);
        return ResponseEntity.ok(ApiResponse.success("已更新", data));
    }

    @DeleteMapping({"/api/v1/classes/{classId}", "/classes-api/{classId}"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> deleteClass(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        classRoomService.deleteClass(user.getUsername(), classId);
        return ResponseEntity.ok(ApiResponse.success("已删除班级", new HashMap<>()));
    }

    @PostMapping({"/api/v1/classes/{classId}/invite-code", "/classes-api/{classId}/invite-code"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> regenerateCode(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        ClassRoomService.ClassRoom room = classRoomService.regenerateInviteCode(user.getUsername(), classId);
        Map<String, Object> data = new HashMap<>();
        data.put("class", room);
        return ResponseEntity.ok(ApiResponse.success("邀请码已刷新", data));
    }

    @PostMapping({"/api/v1/classes/{classId}/projects", "/classes-api/{classId}/projects"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> bindProject(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId,
            @RequestBody Map<String, String> request
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        String projectId = str(request.get("projectId"));
        projectService.getProject(user.getUsername(), projectId);
        ClassRoomService.ClassRoom room = classRoomService.bindProject(user.getUsername(), classId, projectId);
        Map<String, Object> data = new HashMap<>();
        data.put("class", room);
        data.put("projects", resolveProjects(user.getUsername(), room.projectIds));
        return ResponseEntity.ok(ApiResponse.success("已绑定课程模型", data));
    }

    @DeleteMapping({"/api/v1/classes/{classId}/projects/{projectId}", "/classes-api/{classId}/projects/{projectId}"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> unbindProject(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId,
            @PathVariable String projectId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        ClassRoomService.ClassRoom room = classRoomService.unbindProject(user.getUsername(), classId, projectId);
        Map<String, Object> data = new HashMap<>();
        data.put("class", room);
        return ResponseEntity.ok(ApiResponse.success("已解除绑定", data));
    }

    @GetMapping({"/api/v1/classes/{classId}/homeworks", "/classes-api/{classId}/homeworks"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> listClassHomeworks(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN, AuthService.ROLE_STUDENT);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        boolean teacher = authService.hasActiveRole(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        List<ClassRoomService.Homework> items = classRoomService.listHomeworksForClass(user.getUsername(), classId, teacher);
        Map<String, Object> data = new HashMap<>();
        data.put("items", items);
        return ResponseEntity.ok(ApiResponse.success("ok", data));
    }

    @PostMapping({"/api/v1/classes/{classId}/homeworks", "/classes-api/{classId}/homeworks"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> createHomeworkJson(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId,
            @RequestBody Map<String, Object> request
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        ClassRoomService.Homework hw = classRoomService.createHomework(
                user.getUsername(),
                classId,
                str(request.get("title")),
                str(request.get("content")),
                str(request.get("dueAt")),
                bool(request.get("allowText"), true),
                bool(request.get("allowFile"), true),
                bool(request.get("allowImage"), true),
                str(request.get("projectId"))
        );
        Map<String, Object> data = new HashMap<>();
        data.put("homework", hw);
        return ResponseEntity.ok(ApiResponse.success("作业已布置", data));
    }

    @PostMapping(
            value = {"/api/v1/classes/{classId}/homeworks/upload", "/classes-api/{classId}/homeworks/upload"},
            consumes = MediaType.MULTIPART_FORM_DATA_VALUE
    )
    public ResponseEntity<ApiResponse<Map<String, Object>>> createHomeworkWithFiles(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId,
            @RequestParam("title") String title,
            @RequestParam(value = "content", required = false) String content,
            @RequestParam(value = "dueAt", required = false) String dueAt,
            @RequestParam(value = "allowText", required = false, defaultValue = "true") boolean allowText,
            @RequestParam(value = "allowFile", required = false, defaultValue = "true") boolean allowFile,
            @RequestParam(value = "allowImage", required = false, defaultValue = "true") boolean allowImage,
            @RequestParam(value = "projectId", required = false) String projectId,
            @RequestParam(value = "files", required = false) List<MultipartFile> files
    ) throws Exception {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        ClassRoomService.Homework hw = classRoomService.createHomework(
                user.getUsername(), classId, title, content, dueAt,
                allowText, allowFile, allowImage, projectId, files
        );
        Map<String, Object> data = new HashMap<>();
        data.put("homework", hw);
        return ResponseEntity.ok(ApiResponse.success("作业已布置", data));
    }

    @GetMapping({"/api/v1/classes/{classId}/materials", "/classes-api/{classId}/materials"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> listMaterials(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN, AuthService.ROLE_STUDENT);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        Map<String, Object> data = new HashMap<>();
        data.put("items", classRoomService.listMaterials(user.getUsername(), classId));
        return ResponseEntity.ok(ApiResponse.success("ok", data));
    }

    @PostMapping(
            value = {"/api/v1/classes/{classId}/materials", "/classes-api/{classId}/materials"},
            consumes = MediaType.MULTIPART_FORM_DATA_VALUE
    )
    public ResponseEntity<ApiResponse<Map<String, Object>>> uploadMaterial(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId,
            @RequestParam(value = "title", required = false) String title,
            @RequestParam(value = "description", required = false) String description,
            @RequestParam("file") MultipartFile file
    ) throws Exception {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        Map<String, Object> data = new HashMap<>();
        data.put("material", classRoomService.uploadMaterial(user.getUsername(), classId, title, description, file));
        return ResponseEntity.ok(ApiResponse.success("资料已上传", data));
    }

    @DeleteMapping({"/api/v1/classes/{classId}/materials/{materialId}", "/classes-api/{classId}/materials/{materialId}"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> deleteMaterial(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId,
            @PathVariable String materialId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        classRoomService.deleteMaterial(user.getUsername(), classId, materialId);
        return ResponseEntity.ok(ApiResponse.success("资料已删除", new HashMap<>()));
    }

    @GetMapping({"/api/v1/classes/{classId}/chat", "/classes-api/{classId}/chat"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> listChat(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId,
            @RequestParam(value = "limit", required = false, defaultValue = "80") int limit
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN, AuthService.ROLE_STUDENT);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        Map<String, Object> data = new HashMap<>();
        data.put("items", classRoomService.listChat(user.getUsername(), classId, limit));
        return ResponseEntity.ok(ApiResponse.success("ok", data));
    }

    @PostMapping({"/api/v1/classes/{classId}/chat", "/classes-api/{classId}/chat"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> postChat(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId,
            @RequestBody Map<String, String> request
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN, AuthService.ROLE_STUDENT);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        Map<String, Object> data = new HashMap<>();
        data.put("message", classRoomService.postChat(user.getUsername(), classId, str(request.get("content"))));
        return ResponseEntity.ok(ApiResponse.success("已发送", data));
    }

    @GetMapping({"/api/v1/classes/{classId}/homeworks/{homeworkId}/submissions", "/classes-api/{classId}/homeworks/{homeworkId}/submissions"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> listSubmissions(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId,
            @PathVariable String homeworkId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        List<ClassRoomService.Submission> items = classRoomService.listSubmissions(user.getUsername(), classId, homeworkId);
        Map<String, Object> data = new HashMap<>();
        data.put("items", items);
        return ResponseEntity.ok(ApiResponse.success("ok", data));
    }

    @PostMapping({"/api/v1/classes/join/request-code", "/classes-api/join/request-code"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> requestJoinEmailCode(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @RequestBody Map<String, String> request
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_STUDENT, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        return ResponseEntity.ok(ApiResponse.success("验证码已发送",
                classRoomService.issueJoinEmailCode(str(request.get("inviteCode")), str(request.get("email")))));
    }

    @PostMapping({"/api/v1/classes/join", "/classes-api/join"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> joinClass(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @RequestBody Map<String, String> request
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_STUDENT, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        ClassRoomService.ClassRoom room = classRoomService.joinByInviteCode(
                user.getUsername(),
                str(request.get("inviteCode")),
                str(request.get("email")),
                str(request.get("emailCode"))
        );
        Map<String, Object> data = new HashMap<>();
        data.put("class", room);
        return ResponseEntity.ok(ApiResponse.success("已加入班级", data));
    }

    @GetMapping({"/api/v1/student/classes", "/student-classes-api"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> listStudentClasses(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_STUDENT, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        Map<String, Object> data = new HashMap<>();
        data.put("items", classRoomService.listByStudent(user.getUsername()));
        return ResponseEntity.ok(ApiResponse.success("ok", data));
    }

    @GetMapping({"/api/v1/student/homeworks", "/student-homeworks-api"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> listStudentHomeworks(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_STUDENT, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        Map<String, Object> data = new HashMap<>();
        data.put("items", classRoomService.listStudentHomeworkViews(user.getUsername()));
        return ResponseEntity.ok(ApiResponse.success("ok", data));
    }

    @PostMapping(
            value = {"/api/v1/student/homeworks/{homeworkId}/submit", "/student-homeworks-api/{homeworkId}/submit"},
            consumes = MediaType.MULTIPART_FORM_DATA_VALUE
    )
    public ResponseEntity<ApiResponse<Map<String, Object>>> submitHomework(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String homeworkId,
            @RequestParam(value = "textContent", required = false) String textContent,
            @RequestParam(value = "files", required = false) List<MultipartFile> files
    ) throws Exception {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_STUDENT, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        ClassRoomService.Submission sub = classRoomService.submitHomework(user.getUsername(), homeworkId, textContent, files);
        Map<String, Object> data = new HashMap<>();
        data.put("submission", sub);
        return ResponseEntity.ok(ApiResponse.success("作业已提交", data));
    }

    @GetMapping({"/api/v1/homework-attachments/{attachmentId}", "/homework-attachments/{attachmentId}"})
    public ResponseEntity<Resource> downloadAttachment(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String attachmentId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN, AuthService.ROLE_STUDENT);
        if (user == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        }
        ClassRoomService.AttachmentContext ctx = classRoomService.findAttachmentContext(attachmentId);
        if (ctx == null || ctx.attachment == null) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).build();
        }
        boolean isAdmin = "admin".equals(user.getActiveRole())
                || (user.getAdminLevel() != null && !user.getAdminLevel().isEmpty());
        if (!classRoomService.canAccessAttachment(ctx, user.getUsername(), isAdmin)) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).build();
        }
        ClassRoomService.Attachment att = ctx.attachment;
        Path file = classRoomService.resolveAttachmentFile(att.relativePath);
        FileSystemResource resource = new FileSystemResource(file);
        String rawName = att.name == null ? "file" : att.name.replace("\"", "").replace("\r", "").replace("\n", "");
        String asciiName = rawName.replaceAll("[^\\x20-\\x7E]", "_");
        if (asciiName.isBlank()) {
            asciiName = "file";
        }
        String encodedName;
        try {
            encodedName = java.net.URLEncoder.encode(rawName, java.nio.charset.StandardCharsets.UTF_8)
                    .replace("+", "%20");
        } catch (Exception e) {
            encodedName = asciiName;
        }
        // 仅白名单类型允许内联预览；其余强制下载并按二进制处理，防止上传 text/html 造成存储型 XSS
        String contentType = att.contentType == null ? "" : att.contentType.toLowerCase();
        boolean inlineSafe = contentType.startsWith("image/")
                || contentType.equals("application/pdf")
                || contentType.equals("text/plain");
        String disposition = inlineSafe ? "inline" : "attachment";
        MediaType mediaType = inlineSafe && !contentType.isEmpty()
                ? MediaType.parseMediaType(att.contentType)
                : MediaType.APPLICATION_OCTET_STREAM;
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION,
                        disposition + "; filename=\"" + asciiName + "\"; filename*=UTF-8''" + encodedName)
                .contentType(mediaType)
                .body(resource);
    }

    @PostMapping({"/api/v1/classes/{classId}/submissions/{submissionId}/grade", "/classes-api/{classId}/submissions/{submissionId}/grade"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> gradeSubmission(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId,
            @PathVariable String submissionId,
            @RequestBody Map<String, Object> request
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        Double score = null;
        if (request.get("score") != null && !str(request.get("score")).isEmpty()) {
            score = Double.parseDouble(str(request.get("score")));
        }
        Boolean featured = request.containsKey("featured") ? bool(request.get("featured"), false) : null;
        ClassRoomService.Submission sub = classRoomService.gradeSubmission(
                user.getUsername(), classId, submissionId, score, str(request.get("feedback")), featured);
        Map<String, Object> data = new HashMap<>();
        data.put("submission", sub);
        return ResponseEntity.ok(ApiResponse.success("批改已保存", data));
    }

    @GetMapping({"/api/v1/classes/{classId}/featured", "/classes-api/{classId}/featured"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> listFeatured(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN, AuthService.ROLE_STUDENT);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        classRoomService.getForMember(user.getUsername(), classId);
        Map<String, Object> data = new HashMap<>();
        data.put("items", classRoomService.listFeatured(classId));
        return ResponseEntity.ok(ApiResponse.success("ok", data));
    }

    @PostMapping({"/api/v1/classes/{classId}/publish-lesson", "/classes-api/{classId}/publish-lesson"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> publishLessonToClass(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId,
            @RequestBody Map<String, String> request
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        String projectId = str(request.get("projectId"));
        projectService.getProject(user.getUsername(), projectId);
        String lessonTitle = str(request.get("lessonTitle"));
        String lessonIntro = str(request.get("lessonIntro"));
        String audioUrl = str(request.get("audioUrl"));
        String digitalUrl = str(request.get("digitalUrl"));
        boolean needMeta = !lessonTitle.isEmpty() || !lessonIntro.isEmpty()
                || !audioUrl.isEmpty() || !digitalUrl.isEmpty();
        if (!projectService.getProject(user.getUsername(), projectId).isPublished() || needMeta) {
            projectService.publishProject(
                    user.getUsername(),
                    projectId,
                    lessonTitle.isEmpty() ? null : lessonTitle,
                    lessonIntro.isEmpty() ? null : lessonIntro,
                    audioUrl.isEmpty() ? null : audioUrl,
                    digitalUrl.isEmpty() ? null : digitalUrl
            );
        }
        ClassRoomService.ClassRoom room = classRoomService.publishProjectToClass(user.getUsername(), classId, projectId);
        Map<String, Object> data = new HashMap<>();
        data.put("class", room);
        data.put("inviteCode", room.inviteCode == null ? "" : room.inviteCode);
        data.put("studentJoinPath", "/student/course-center?invite="
                + (room.inviteCode == null ? "" : room.inviteCode)
                + "&classId=" + classId
                + "&projectId=" + projectId);
        return ResponseEntity.ok(ApiResponse.success("已按班发布（仅本班可见）", data));
    }

    @DeleteMapping({"/api/v1/classes/{classId}/publish-lesson/{projectId}", "/classes-api/{classId}/publish-lesson/{projectId}"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> unpublishLesson(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId,
            @PathVariable String projectId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        Map<String, Object> data = new HashMap<>();
        data.put("class", classRoomService.unpublishProjectFromClass(user.getUsername(), classId, projectId));
        return ResponseEntity.ok(ApiResponse.success("已取消按班发布", data));
    }

    @GetMapping({"/api/v1/classes/{classId}/announcements", "/classes-api/{classId}/announcements"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> listAnnouncements(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN, AuthService.ROLE_STUDENT);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        Map<String, Object> data = new HashMap<>();
        data.put("items", classRoomService.listAnnouncements(user.getUsername(), classId));
        return ResponseEntity.ok(ApiResponse.success("ok", data));
    }

    @PostMapping({"/api/v1/classes/{classId}/announcements", "/classes-api/{classId}/announcements"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> createAnnouncement(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId,
            @RequestBody Map<String, String> request
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        Map<String, Object> data = new HashMap<>();
        data.put("announcement", classRoomService.createAnnouncement(
                user.getUsername(), classId, str(request.get("title")), str(request.get("content"))));
        return ResponseEntity.ok(ApiResponse.success("公告已发布", data));
    }

    @GetMapping({"/api/v1/classes/{classId}/checkins", "/classes-api/{classId}/checkins"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> listCheckins(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN, AuthService.ROLE_STUDENT);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        Map<String, Object> data = new HashMap<>();
        data.put("items", classRoomService.listCheckins(user.getUsername(), classId));
        return ResponseEntity.ok(ApiResponse.success("ok", data));
    }

    @PostMapping({"/api/v1/classes/{classId}/checkins", "/classes-api/{classId}/checkins"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> openCheckin(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId,
            @RequestBody Map<String, String> request
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        Map<String, Object> data = new HashMap<>();
        data.put("checkin", classRoomService.openCheckin(user.getUsername(), classId, str(request.get("title"))));
        return ResponseEntity.ok(ApiResponse.success("签到已开启", data));
    }

    @PostMapping({"/api/v1/classes/{classId}/checkins/{checkinId}/close", "/classes-api/{classId}/checkins/{checkinId}/close"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> closeCheckin(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId,
            @PathVariable String checkinId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        Map<String, Object> data = new HashMap<>();
        data.put("checkin", classRoomService.closeCheckin(user.getUsername(), classId, checkinId));
        return ResponseEntity.ok(ApiResponse.success("签到已结束", data));
    }

    @PostMapping({"/api/v1/classes/{classId}/checkins/{checkinId}/sign", "/classes-api/{classId}/checkins/{checkinId}/sign"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> studentSign(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId,
            @PathVariable String checkinId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_STUDENT, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        Map<String, Object> data = new HashMap<>();
        data.put("record", classRoomService.studentCheckin(user.getUsername(), classId, checkinId));
        return ResponseEntity.ok(ApiResponse.success("签到成功", data));
    }

    @GetMapping({"/api/v1/classes/{classId}/checkins/{checkinId}/records", "/classes-api/{classId}/checkins/{checkinId}/records"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> checkinRecords(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId,
            @PathVariable String checkinId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        Map<String, Object> data = new HashMap<>();
        data.put("items", classRoomService.listCheckinRecords(user.getUsername(), classId, checkinId));
        return ResponseEntity.ok(ApiResponse.success("ok", data));
    }

    @GetMapping({"/api/v1/classes/{classId}/analytics", "/classes-api/{classId}/analytics"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> analytics(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        return ResponseEntity.ok(ApiResponse.success("ok", classRoomService.classAnalytics(user.getUsername(), classId)));
    }

    @GetMapping({
            "/api/v1/classes/{classId}/students/{username}",
            "/classes-api/{classId}/students/{username}"
    })
    public ResponseEntity<ApiResponse<Map<String, Object>>> studentLearningDetail(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId,
            @PathVariable String username
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        Map<String, Object> data = classRoomService.studentLearningProfile(user.getUsername(), classId, username);
        data.put("profile", authService.describeUserBrief(username));

        @SuppressWarnings("unchecked")
        List<String> publishedIds = (List<String>) data.get("publishedProjectIds");
        ClassRoomService.ClassRoom room = classRoomService.getForMember(user.getUsername(), classId);
        List<Map<String, Object>> lessons = resolveProjects(room.teacherUsername, publishedIds);
        data.put("lessons", lessons);

        @SuppressWarnings("unchecked")
        List<String> boundIds = (List<String>) data.get("boundProjectIds");
        data.put("boundLessons", resolveProjects(room.teacherUsername, boundIds));

        // Learning path timeline: lessons then homework nodes by time-ish order.
        List<Map<String, Object>> timeline = new java.util.ArrayList<>();
        for (Map<String, Object> lesson : lessons) {
            Map<String, Object> node = new HashMap<>();
            node.put("type", "lesson");
            node.put("title", lesson.get("lessonTitle") != null && !String.valueOf(lesson.get("lessonTitle")).isBlank()
                    ? lesson.get("lessonTitle") : lesson.get("name"));
            node.put("id", lesson.get("id"));
            node.put("at", lesson.get("publishedAt"));
            node.put("digitalUrl", lesson.get("digitalUrl"));
            timeline.add(node);
        }
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> hwPath = (List<Map<String, Object>>) data.get("homeworkPath");
        if (hwPath != null) {
            for (Map<String, Object> hw : hwPath) {
                Map<String, Object> node = new HashMap<>();
                node.put("type", "homework");
                node.put("title", hw.get("title"));
                node.put("id", hw.get("homeworkId"));
                node.put("at", hw.get("createdAt"));
                node.put("status", hw.get("status"));
                node.put("submitted", hw.get("submitted"));
                node.put("score", hw.get("score"));
                timeline.add(node);
            }
        }
        data.put("learningPath", timeline);
        return ResponseEntity.ok(ApiResponse.success("ok", data));
    }

    @PostMapping({"/api/v1/classes/{classId}/assistants", "/classes-api/{classId}/assistants"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> addAssistant(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId,
            @RequestBody Map<String, String> request
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        Map<String, Object> data = new HashMap<>();
        data.put("class", classRoomService.addAssistant(user.getUsername(), classId, str(request.get("username"))));
        return ResponseEntity.ok(ApiResponse.success("助教已添加", data));
    }

    @DeleteMapping({"/api/v1/classes/{classId}/assistants/{username}", "/classes-api/{classId}/assistants/{username}"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> removeAssistant(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId,
            @PathVariable String username
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        Map<String, Object> data = new HashMap<>();
        data.put("class", classRoomService.removeAssistant(user.getUsername(), classId, username));
        return ResponseEntity.ok(ApiResponse.success("已移除助教", data));
    }

    @PostMapping({"/api/v1/classes/{classId}/members/import", "/classes-api/{classId}/members/import"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> importMembers(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId,
            @RequestBody Map<String, String> request
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        return ResponseEntity.ok(ApiResponse.success("导入完成",
                classRoomService.importMembers(user.getUsername(), classId, str(request.get("names")))));
    }

    @PostMapping(
            value = {"/api/v1/classes/{classId}/members/import-file", "/classes-api/{classId}/members/import-file"},
            consumes = org.springframework.http.MediaType.MULTIPART_FORM_DATA_VALUE
    )
    public ResponseEntity<ApiResponse<Map<String, Object>>> importMembersFile(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId,
            @PathVariable String classId,
            @RequestParam("file") MultipartFile file
    ) throws Exception {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        return ResponseEntity.ok(ApiResponse.success("导入完成",
                classRoomService.importMembersFromFile(user.getUsername(), classId, file)));
    }

    @GetMapping({"/api/v1/student/class-lessons", "/student-class-lessons-api"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> studentClassLessons(
            @CookieValue(value = AUTH_COOKIE, required = false) String sessionId
    ) {
        AuthService.AuthUserView user = requireUser(sessionId, AuthService.ROLE_STUDENT, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN);
        if (user == null) {
            return forbiddenOrUnauthorized(sessionId);
        }
        List<String> ids = classRoomService.listClassOnlyProjectIdsForStudent(user.getUsername());
        List<Map<String, Object>> items = new java.util.ArrayList<>();
        for (String pid : ids) {
            try {
                ProjectService.PublishedLessonView view = projectService.getPublishedLessonView(pid);
                ProjectService.ProjectRecord record = projectService.getPublishedProject(pid);
                Map<String, Object> item = new HashMap<>();
                item.put("id", view.getId());
                item.put("name", view.getName());
                item.put("lessonTitle", view.getLessonTitle());
                item.put("lessonIntro", view.getLessonIntro());
                item.put("teacherUsername", record.getUsername());
                item.put("publishedAt", view.getPublishedAt());
                item.put("digitalUrl", view.getDigitalUrl());
                item.put("classOnly", true);
                items.add(item);
            } catch (Exception ignored) {
                // skip
            }
        }
        Map<String, Object> data = new HashMap<>();
        data.put("items", items);
        return ResponseEntity.ok(ApiResponse.success("ok", data));
    }

    @org.springframework.web.bind.annotation.ExceptionHandler(ClassRoomService.ClassRoomException.class)
    public ResponseEntity<ApiResponse<Map<String, Object>>> handleClassEx(ClassRoomService.ClassRoomException ex) {
        return ResponseEntity.badRequest().body(ApiResponse.error(ex.getMessage()));
    }

    @org.springframework.web.bind.annotation.ExceptionHandler(ProjectService.ProjectException.class)
    public ResponseEntity<ApiResponse<Map<String, Object>>> handleProjectEx(ProjectService.ProjectException ex) {
        return ResponseEntity.badRequest().body(ApiResponse.error(ex.getMessage()));
    }

    private List<Map<String, Object>> resolveProjects(String teacherUsername, List<String> projectIds) {
        List<Map<String, Object>> list = new java.util.ArrayList<>();
        if (projectIds == null) {
            return list;
        }
        for (String pid : projectIds) {
            try {
                ProjectService.ProjectRecord p = projectService.getProject(teacherUsername, pid);
                Map<String, Object> item = new HashMap<>();
                item.put("id", p.getId());
                item.put("name", p.getName());
                item.put("lessonTitle", p.getLessonTitle());
                item.put("lessonIntro", p.getLessonIntro());
                item.put("teacherUsername", p.getUsername() == null || p.getUsername().isEmpty()
                        ? teacherUsername : p.getUsername());
                item.put("published", p.isPublished());
                item.put("publishedAt", p.getPublishedAt());
                item.put("digitalUrl", p.getDigitalUrl());
                item.put("audioUrl", p.getAudioUrl());
                list.add(item);
            } catch (Exception ignored) {
                // Skip missing/unauthorized projects — never surface「课程模型不可用」tiles.
            }
        }
        return list;
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

    private ResponseEntity<ApiResponse<Map<String, Object>>> forbiddenOrUnauthorized(String sessionId) {
        if (authService.getUserBySession(sessionId) == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(ApiResponse.error("未登录"));
        }
        return ResponseEntity.status(HttpStatus.FORBIDDEN).body(ApiResponse.error("当前身份无权访问"));
    }

    private static String str(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private static boolean bool(Object value, boolean defaultValue) {
        if (value == null) {
            return defaultValue;
        }
        if (value instanceof Boolean) {
            return (Boolean) value;
        }
        String s = String.valueOf(value).trim().toLowerCase();
        if ("true".equals(s) || "1".equals(s) || "yes".equals(s)) {
            return true;
        }
        if ("false".equals(s) || "0".equals(s) || "no".equals(s)) {
            return false;
        }
        return defaultValue;
    }
}
