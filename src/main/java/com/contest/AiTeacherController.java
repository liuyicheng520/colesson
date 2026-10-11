package com.contest;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import javax.servlet.http.Cookie;
import javax.servlet.http.HttpServletRequest;
import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

/**
 * 核心接口控制器
 */
@RestController
public class AiTeacherController {

    private static final double QA_DATASET_HIT_THRESHOLD = 55.0;
    private static final String AUTH_COOKIE = "AI_TEACHER_SESSION";
    private static final int CLOUD_FAST_TIMEOUT_MS = 1500;
    private static final int CLOUD_FAST_POLL_ATTEMPTS = 1;
    private static final int CLOUD_FAST_POLL_INTERVAL_MS = 200;

    @Value("${ai.api.signature-required:false}")
    private boolean signatureRequired;

    @Value("${ai.api.static-key:}")
    private String staticKey;

    @Value("${ai.vision.enabled:true}")
    private boolean visionEnabled;

    @Value("${ai.vision.api-url:https://ark.cn-beijing.volces.com/api/v3/chat/completions}")
    private String visionApiUrl;

    @Value("${ai.vision.api-key:}")
    private String visionApiKey;

    @Value("${ai.vision.model:}")
    private String visionModel;

    @Value("${ai.vision.max-slides:6}")
    private int visionMaxSlides;

    @Value("${ai.vision.max-image-bytes:5242880}")
    private int visionMaxImageBytes;

    @Value("${ai.digital.mode:auto}")
    private String digitalMode;

    @Value("${ai.digital.cloud.enabled:false}")
    private boolean digitalCloudEnabled;

    @Value("${ai.digital.cloud.url:}")
    private String digitalCloudUrl;

    @Value("${ai.digital.cloud.api-key:}")
    private String digitalCloudApiKey;

    @Value("${ai.digital.cloud.auth-header:Authorization}")
    private String digitalCloudAuthHeader;

    @Value("${ai.digital.cloud.auth-prefix:Bearer}")
    private String digitalCloudAuthPrefix;

    @Value("${ai.digital.cloud.timeout-ms:8000}")
    private int digitalCloudTimeoutMs;

    @Value("${ai.digital.cloud.req-key:realman_avatar_creation_task}")
    private String digitalCloudReqKey;

    @Value("${ai.digital.cloud.resource-id:}")
    private String digitalCloudResourceId;

    @Value("${ai.digital.cloud.poll-attempts:12}")
    private int digitalCloudPollAttempts;

    @Value("${ai.digital.cloud.poll-interval-ms:3000}")
    private int digitalCloudPollIntervalMs;

    @Value("${ai.digital.cloud.default-audio-url:}")
    private String digitalCloudDefaultAudioUrl;

    @Value("${ai.digital.cloud.ak:}")
    private String digitalCloudAk;

    @Value("${ai.digital.cloud.sk:}")
    private String digitalCloudSk;

    @Value("${ai.digital.cloud.region:cn-north-1}")
    private String digitalCloudRegion;

    @Value("${ai.digital.cloud.service:cv}")
    private String digitalCloudService;

    @Value("${app.generated-static-dir:data/generated-static}")
    private String generatedStaticDir;

    private final QaSearchService qaSearchService;
    private final AuthService authService;
    private final ProjectService projectService;
    private final ComputerCoursePromptService computerCoursePromptService;
    private final KnowledgeRetrievalService knowledgeRetrievalService;
    private final AtomicLong requestCounter = new AtomicLong(1);
    private final AtomicLong trackCounter = new AtomicLong(1);
    private final Map<String, Map<String, Object>> progressStore = new ConcurrentHashMap<>();

    public AiTeacherController(
            QaSearchService qaSearchService,
            AuthService authService,
            ProjectService projectService,
            ComputerCoursePromptService computerCoursePromptService,
            KnowledgeRetrievalService knowledgeRetrievalService
    ) {
        this.qaSearchService = qaSearchService;
        this.authService = authService;
        this.projectService = projectService;
        this.computerCoursePromptService = computerCoursePromptService;
        this.knowledgeRetrievalService = knowledgeRetrievalService;
    }

    @GetMapping("/")
    public ResponseEntity<Void> index() {
        return ResponseEntity.status(HttpStatus.FOUND)
                .header("Location", "/login.html")
                .build();
    }

    @GetMapping(value = "/digital-human-{resourceId}.html", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> generatedDigitalHumanPage(@PathVariable String resourceId) {
        String fileName = "digital-human-" + resourceId + ".html";
        try {
            for (Path dir : generatedStaticReadDirs()) {
                Path file = dir.resolve(fileName).normalize();
                if (Files.exists(file) && Files.isRegularFile(file)) {
                    return ResponseEntity.ok()
                            .contentType(MediaType.TEXT_HTML)
                            .body(new String(Files.readAllBytes(file), StandardCharsets.UTF_8));
                }
            }

            String expectedUrl = "/" + fileName;
            for (ProjectService.ProjectRecord project : projectService.listAllProjectsForAdmin()) {
                if (expectedUrl.equals(str(project.getDigitalUrl()))
                        && project.getScript() != null
                        && !project.getScript().trim().isEmpty()) {
                    String html = TtsUtil.generateDigitalHumanHtml(project.getScript(), str(project.getAudioUrl()));
                    return ResponseEntity.ok()
                            .contentType(MediaType.TEXT_HTML)
                            .body(html);
                }
            }
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .contentType(MediaType.TEXT_PLAIN)
                    .body("数字人页面不存在，请重新生成语音和数字人后发布。");
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .contentType(MediaType.TEXT_PLAIN)
                    .body("数字人页面加载失败：" + e.getMessage());
        }
    }

    @PostMapping({"/parse-ppt", "/api/v1/lesson/parse"})
    public ResponseEntity<ApiResponse<Map<String, String>>> parsePpt(
            @RequestParam(value = "file", required = false) MultipartFile file,
            @RequestParam(value = "enc", required = false) String enc,
            @RequestParam(value = "time", required = false) String time,
            @RequestParam Map<String, String> params,
            HttpServletRequest httpRequest
    ) {
        String requestId = nextRequestId();

        try {
            ResponseEntity<ApiResponse<Map<String, String>>> authError = requireAuth(
                    requestId, httpRequest, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN
            );
            if (authError != null) {
                return authError;
            }
            if (file == null || file.isEmpty()) {
                return badRequest("文件为空，请先选择PPT文件", requestId);
            }

            String fileName = file.getOriginalFilename();
            String lowerFileName = fileName == null ? "" : fileName.toLowerCase();
            if (!lowerFileName.endsWith(".ppt") && !lowerFileName.endsWith(".pptx")) {
                return badRequest("文件格式错误，请上传PPT/PPTX", requestId);
            }

            ResponseEntity<ApiResponse<Map<String, String>>> signError = validateSignature(params, requestId);
            if (signError != null) {
                return signError;
            }

            // 秒级解析：流式读取 + 只抽文字（pptx 走 ZIP/XML，不加载图片进内存）
            String rawText;
            try (InputStream in = file.getInputStream()) {
                rawText = PptParserUtil.extractRawText(in, fileName);
            }
            if (PptParserUtil.isParseFailure(rawText)) {
                return serverError(PptParserUtil.cleanParseFailureMessage(rawText), requestId);
            }

            Map<String, String> data = new HashMap<>();
            data.put("html", "");
            data.put("rawText", rawText);
            return ok("PPT解析成功", data, requestId);
        } catch (Exception e) {
            e.printStackTrace();
            return serverError("解析失败：" + e.getMessage(), requestId);
        }
    }

    @PostMapping({"/generate-script", "/api/v1/lesson/generateScript"})
    public ResponseEntity<ApiResponse<Map<String, String>>> generateScript(@RequestBody Map<String, String> request, HttpServletRequest httpRequest) {
        String requestId = nextRequestId();

        try {
            ResponseEntity<ApiResponse<Map<String, String>>> authError = requireAuth(
                    requestId, httpRequest, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN
            );
            if (authError != null) {
                return authError;
            }
            ResponseEntity<ApiResponse<Map<String, String>>> signError = validateSignature(request, requestId);
            if (signError != null) {
                return signError;
            }

            String pptText = request.get("pptText");
            if (pptText == null || pptText.trim().isEmpty()) {
                String parseId = request.get("parseId");
                if (parseId != null && !parseId.trim().isEmpty()) {
                    return badRequest("当前版本暂未实现 parseId 反查，请传入 pptText", requestId);
                }
                return badRequest("请先解析PPT并获取有效内容", requestId);
            }

            // 请求体过大时会拖慢前后端，先做裁剪确保快速返回
            String normalized = pptText.trim();
            if (normalized.length() > 12000) {
                normalized = normalized.substring(0, 12000);
            }

            ProjectService.ProjectRecord project = resolveOwnedProject(request.get("projectId"), httpRequest);
            String script;
            if (project != null && project.isComputerMode()) {
                String resourceContext = projectService.buildComputerContext(project, request.get("resourceId"));
                script = computerCoursePromptService.generateLectureScript(project, normalized, resourceContext);
            } else {
                script = AiApiUtil.generateLectureScript(normalized);
            }
            String source = "ai";
            if (isAiCallFailure(script) || looksLikePptEcho(script, normalized)
                    || AiApiUtil.looksLikeBadTeachingScript(script)) {
                // 禁止复读 PPT / 套话模板 / 书目教务杂质
                script = AiApiUtil.localTeachingScript(normalized);
                source = "local_template";
            }

            Map<String, String> data = new HashMap<>();
            data.put("script", script);
            data.put("scriptId", "script" + System.currentTimeMillis());
            data.put("source", source);
            return ok("ai".equals(source) ? "讲稿生成成功" : "讲稿已按本地模板生成（AI 调用未成功，非 AI 生成）", data, requestId);
        } catch (Exception e) {
            e.printStackTrace();
            String text = request.getOrDefault("pptText", "");
            String fallback = AiApiUtil.localTeachingScript(text == null ? "" : text);
            Map<String, String> data = new HashMap<>();
            data.put("script", fallback);
            data.put("scriptId", "script" + System.currentTimeMillis());
            data.put("source", "local_template");
            return ok("讲稿已按本地模板生成（AI 调用失败，非 AI 生成）", data, requestId);
        }
    }

    @PostMapping({"/answer-question", "/api/v1/qa/interact"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> answerQuestion(@RequestBody Map<String, Object> request, HttpServletRequest httpRequest) {
        String requestId = nextRequestId();

        try {
            ResponseEntity<ApiResponse<Map<String, Object>>> authError = requireAuthObj(requestId, httpRequest);
            if (authError != null) {
                return authError;
            }
            ResponseEntity<ApiResponse<Map<String, Object>>> signError = validateSignatureObj(request, requestId);
            if (signError != null) {
                return signError;
            }

            ProjectService.ProjectRecord project = resolveOwnedProject(str(request.get("projectId")), httpRequest);
            return buildAnswerResponse(request, requestId, project, false);
        } catch (Exception e) {
            e.printStackTrace();
            return serverErrorObj("回答失败：" + e.getMessage(), requestId);
        }
    }

    @PostMapping({"/public/answer-question", "/public/api/v1/qa/interact"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> publicAnswerQuestion(@RequestBody Map<String, Object> request) {
        String requestId = nextRequestId();

        try {
            ProjectService.ProjectRecord project = requirePublishedProject(request);
            return buildAnswerResponse(request, requestId, project, true);
        } catch (ProjectService.ProjectException e) {
            return badRequestObj(e.getMessage(), requestId);
        } catch (Exception e) {
            e.printStackTrace();
            return serverErrorObj("回答失败：" + e.getMessage(), requestId);
        }
    }

    /**
     * TopK检索问答（基于 qa_dataset.jsonl）
     */
    @PostMapping({"/qa/search", "/api/v1/qa/search"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> qaSearch(@RequestBody Map<String, Object> request, HttpServletRequest httpRequest) {
        String requestId = nextRequestId();

        try {
            ResponseEntity<ApiResponse<Map<String, Object>>> authError = requireAuthObj(requestId, httpRequest);
            if (authError != null) {
                return authError;
            }
            ResponseEntity<ApiResponse<Map<String, Object>>> signError = validateSignatureObj(request, requestId);
            if (signError != null) {
                return signError;
            }

            String question = str(request.get("question"));
            if (question.isEmpty()) {
                return badRequestObj("question 不能为空", requestId);
            }

            int topK = 5;
            Object k = request.get("topK");
            if (k != null) {
                try {
                    topK = Integer.parseInt(String.valueOf(k));
                } catch (Exception ignored) {
                    topK = 5;
                }
            }
            topK = Math.min(Math.max(topK, 1), 20);

            List<Map<String, Object>> hits = qaSearchService.search(question, topK);
            Map<String, Object> data = new HashMap<>();
            data.put("question", question);
            data.put("topK", topK);
            data.put("total", hits.size());
            data.put("hits", hits);

            return okObj("检索成功", data, requestId);
        } catch (Exception e) {
            e.printStackTrace();
            return serverErrorObj("检索失败：" + e.getMessage(), requestId);
        }
    }

    @PostMapping({"/generate-audio", "/api/v1/lesson/generateAudio"})
    public ResponseEntity<ApiResponse<Map<String, String>>> generateAudio(
            @RequestBody Map<String, Object> request,
            HttpServletRequest httpRequest
    ) {
        String requestId = nextRequestId();

        try {
            ResponseEntity<ApiResponse<Map<String, String>>> authError = requireAuth(
                    requestId, httpRequest, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN
            );
            if (authError != null) {
                return authError;
            }
            ResponseEntity<ApiResponse<Map<String, Object>>> signError = validateSignatureObj(request, requestId);
            if (signError != null) {
                return ResponseEntity.status(signError.getStatusCode()).body(
                        ApiResponse.error(signError.getBody() == null ? "签名校验失败" : signError.getBody().getMessage(), requestId)
                );
            }

            String script = str(request.get("script"));
            if (script.isEmpty() && request.get("scriptId") != null) {
                return badRequest("当前版本暂未实现 scriptId 反查，请传入 script 文本", requestId);
            }
            if (script.isEmpty()) {
                return badRequest("请先生成讲稿", requestId);
            }

            String resourceId = "lecture_script_" + System.currentTimeMillis();
            String audioFileName = resourceId + ".mp3";
            Path runtimeStaticDir = runtimeStaticDir();
            Path runtimeAudioDir = runtimeStaticDir.resolve("audio");
            Files.createDirectories(runtimeAudioDir);

            String audioPath = runtimeAudioDir.resolve(audioFileName).toString();
            String voiceStyle = str(request.get("voiceStyle"));
            String filePath = TtsUtil.textToSpeech(script, audioPath, voiceStyle);
            if (filePath == null || filePath.trim().isEmpty()) {
                String detail = TtsUtil.getLastError();
                if (detail == null || detail.trim().isEmpty()) {
                    detail = "未知原因";
                }
                return gatewayError("语音合成失败：" + detail, requestId);
            }

            Path produced = Paths.get(filePath);
            String producedName = produced.getFileName().toString();
            if (!producedName.equals(audioFileName)) {
                audioFileName = producedName;
            }
            String audioUrl = "/audio/" + audioFileName;
            copyGeneratedStaticFile("audio/" + audioFileName, produced);

            // 教师端产物改为学生端同款「讲解视频」，不再生成静止数字人页
            String projectId = str(request.get("projectId"));
            String topic = str(request.get("lessonTitle"));
            if (topic.isEmpty()) {
                topic = str(request.get("topic"));
            }
            if (topic.isEmpty()) {
                topic = "课程讲解";
            }
            String lectureId = projectId.isEmpty() ? ("host-" + resourceId) : ("host-" + projectId);
            Map<String, Object> lecture = TeacherLectureVideoUtil.buildLecture(
                    lectureId,
                    topic,
                    str(request.get("pptRawText")),
                    script
            );
            TeacherLectureVideoUtil.writeLectureFile(runtimeStaticDir, lectureId, lecture);
            // 同步一份到 data/lectures，便于发布后读取
            try {
                Path dataRoot = Paths.get("data").toAbsolutePath().normalize();
                TeacherLectureVideoUtil.writeLectureFile(dataRoot, lectureId, lecture);
            } catch (Exception ignored) {
                // 运行时目录已写入即可
            }
            String lectureUrl = TeacherLectureVideoUtil.openUrl(lectureId, projectId);

            Map<String, String> data = new HashMap<>();
            data.put("audioUrl", audioUrl);
            data.put("audioId", resourceId);
            data.put("digitalMode", "lecture-video");
            data.put("ttsProvider", TtsUtil.getLastProvider());
            data.put("lectureId", lectureId);
            data.put("lectureUrl", lectureUrl);
            // 兼容旧字段：发布/学生端仍读 digitalUrl
            data.put("digitalUrl", lectureUrl);

            String provider = TtsUtil.getLastProvider();
            String providerHint = "edge-tts-free".equals(provider)
                    ? "免费Edge语音"
                    : ("windows-sapi-free".equals(provider) ? "免费Windows朗读" : ("baidu".equals(provider) ? "百度语音" : "本地"));
            return ok("语音合成成功（" + providerHint + "），已生成讲解视频", data, requestId);
        } catch (Exception e) {
            e.printStackTrace();
            return serverError("语音合成失败：" + e.getMessage(), requestId);
        }
    }

    /** 教师端/学生端打开讲解视频时加载讲义（与学生端 TutorLecture 同结构）。 */
    @GetMapping({"/api/v1/lesson/host-lecture/{lectureId}", "/public/host-lecture/{lectureId}"})
    public ResponseEntity<ApiResponse<Map<String, Object>>> getHostLecture(
            @PathVariable String lectureId,
            @RequestParam(value = "projectId", required = false) String projectId
    ) {
        String requestId = nextRequestId();
        try {
            Map<String, Object> lecture = resolveHostLecture(lectureId, projectId);
            if (lecture == null) {
                return ResponseEntity.status(HttpStatus.NOT_FOUND)
                        .body(ApiResponse.error("讲解视频不存在，请在教师工作台重新生成", requestId));
            }
            return okObj("ok", lecture, requestId);
        } catch (Exception e) {
            return serverErrorObj("读取讲解视频失败：" + e.getMessage(), requestId);
        }
    }

    /**
     * 宿主讲解视频旁路提问（无 tutor session_no 时使用）
     */
    @PostMapping({
            "/api/v1/lesson/host-lecture/{lectureId}/ask",
            "/public/host-lecture/{lectureId}/ask"
    })
    public ResponseEntity<ApiResponse<Map<String, Object>>> askHostLecture(
            @PathVariable String lectureId,
            @RequestBody Map<String, Object> request
    ) {
        String requestId = nextRequestId();
        try {
            String question = str(request.get("question"));
            if (question.isEmpty()) {
                return badRequestObj("请输入问题", requestId);
            }
            String projectId = str(request.get("projectId"));
            Map<String, Object> lecture = resolveHostLecture(lectureId, projectId);
            if (lecture == null) {
                return ResponseEntity.status(HttpStatus.NOT_FOUND)
                        .body(ApiResponse.error("讲解视频不存在", requestId));
            }

            int slideIndex = 0;
            Object si = request.get("slide_index");
            if (si == null) {
                si = request.get("slideIndex");
            }
            if (si != null) {
                try {
                    slideIndex = Integer.parseInt(String.valueOf(si));
                } catch (Exception ignored) {
                    slideIndex = 0;
                }
            }

            String context = buildHostLectureAskContext(lecture, slideIndex);
            String answer = AiApiUtil.answerStudentQuestion(question, context);
            if (answer == null || answer.trim().isEmpty()) {
                answer = "结合当前页讲解，你可以先回顾要点，再把具体不懂的地方拆成一个小问题问我。";
            }

            Map<String, Object> data = new HashMap<>();
            data.put("answer", answer.trim());
            data.put("slide_index", slideIndex);
            return okObj("ok", data, requestId);
        } catch (Exception e) {
            e.printStackTrace();
            return serverErrorObj("回答失败：" + e.getMessage(), requestId);
        }
    }

    private Map<String, Object> resolveHostLecture(String lectureId, String projectId) throws Exception {
        Map<String, Object> lecture = null;
        if (lectureId != null && !lectureId.trim().isEmpty()) {
            for (Path root : hostLectureRoots()) {
                lecture = TeacherLectureVideoUtil.readLectureFile(root, lectureId.trim());
                if (lecture != null) {
                    return lecture;
                }
            }
        }
        if (projectId != null && !projectId.trim().isEmpty()) {
            for (Path root : hostLectureRoots()) {
                lecture = TeacherLectureVideoUtil.readLectureFile(root, "host-" + projectId.trim());
                if (lecture != null) {
                    return lecture;
                }
            }
        }
        return null;
    }

    @SuppressWarnings("unchecked")
    private String buildHostLectureAskContext(Map<String, Object> lecture, int slideIndex) {
        StringBuilder sb = new StringBuilder();
        String topic = str(lecture.get("topic"));
        if (!topic.isEmpty()) {
            sb.append("课程主题：").append(topic).append("\n\n");
        }
        Object slidesObj = lecture.get("slides");
        if (!(slidesObj instanceof List)) {
            return sb.length() > 0 ? sb.toString() : "课堂讲解内容";
        }
        List<?> slides = (List<?>) slidesObj;
        if (slideIndex >= 0 && slideIndex < slides.size() && slides.get(slideIndex) instanceof Map) {
            Map<String, Object> cur = (Map<String, Object>) slides.get(slideIndex);
            sb.append("【当前页】\n");
            appendSlideContext(sb, cur, slideIndex + 1);
            sb.append("\n");
        }
        sb.append("【全文要点】\n");
        int limit = Math.min(slides.size(), 12);
        for (int i = 0; i < limit; i++) {
            Object item = slides.get(i);
            if (!(item instanceof Map)) {
                continue;
            }
            appendSlideContext(sb, (Map<String, Object>) item, i + 1);
        }
        String text = sb.toString().trim();
        return text.isEmpty() ? "课堂讲解内容" : text;
    }

    private void appendSlideContext(StringBuilder sb, Map<String, Object> slide, int pageNo) {
        String type = str(slide.get("type"));
        String title = str(slide.get("title"));
        String narration = str(slide.get("narration"));
        if (narration.isEmpty()) {
            narration = str(slide.get("question"));
        }
        if (narration.isEmpty() && title.isEmpty()) {
            return;
        }
        sb.append("第").append(pageNo).append("页");
        if (!type.isEmpty()) {
            sb.append("(").append(type).append(")");
        }
        if (!title.isEmpty()) {
            sb.append(" ").append(title);
        }
        sb.append("\n");
        if (!narration.isEmpty()) {
            String clipped = narration.length() > 500 ? narration.substring(0, 500) : narration;
            sb.append(clipped).append("\n");
        }
    }

    private List<Path> hostLectureRoots() throws Exception {
        List<Path> roots = new ArrayList<>();
        roots.add(runtimeStaticDir());
        roots.add(Paths.get("data").toAbsolutePath().normalize());
        Path cwdStatic = Paths.get("src/main/resources/static").toAbsolutePath().normalize();
        if (Files.isDirectory(cwdStatic)) {
            roots.add(cwdStatic);
        }
        return roots;
    }

    /**
     * 学习进度追踪（规范预留接口）
     */
    private Path runtimeStaticDir() throws Exception {
        Path dir = generatedStaticRoot();
        Files.createDirectories(dir);
        return dir;
    }

    private void writeGeneratedStaticFile(String relativePath, String content) throws Exception {
        Path target = runtimeStaticDir().resolve(relativePath).normalize();
        Files.createDirectories(target.getParent());
        Files.write(target, content.getBytes(StandardCharsets.UTF_8));
    }

    private void copyGeneratedStaticFile(String relativePath, Path source) throws Exception {
        Path normalizedSource = source.toAbsolutePath().normalize();
        Path target = runtimeStaticDir().resolve(relativePath).normalize();
        Files.createDirectories(target.getParent());
        if (!normalizedSource.equals(target.toAbsolutePath().normalize())) {
            Files.copy(normalizedSource, target, StandardCopyOption.REPLACE_EXISTING);
        }
    }

    private Path generatedStaticRoot() {
        String configured = generatedStaticDir == null || generatedStaticDir.trim().isEmpty()
                ? "data/generated-static"
                : generatedStaticDir.trim();
        return Paths.get(configured).toAbsolutePath().normalize();
    }

    private List<Path> generatedStaticReadDirs() {
        List<Path> dirs = new ArrayList<>();
        dirs.add(generatedStaticRoot());
        dirs.add(Paths.get("target/classes/static").toAbsolutePath().normalize());
        dirs.add(Paths.get("src/main/resources/static").toAbsolutePath().normalize());
        return dirs;
    }

    @PostMapping("/api/v1/progress/track")
    public ResponseEntity<ApiResponse<Map<String, Object>>> progressTrack(@RequestBody Map<String, Object> request, HttpServletRequest httpRequest) {
        String requestId = nextRequestId();

        ResponseEntity<ApiResponse<Map<String, Object>>> authError = requireAuthObj(requestId, httpRequest);
        if (authError != null) {
            return authError;
        }
        ResponseEntity<ApiResponse<Map<String, Object>>> signError = validateSignatureObj(request, requestId);
        if (signError != null) {
            return signError;
        }

        String userId = str(request.get("userId"));
        String lessonId = str(request.get("lessonId"));
        String currentSectionId = str(request.get("currentSectionId"));

        if (userId.isEmpty() || lessonId.isEmpty() || currentSectionId.isEmpty()) {
            return badRequestObj("userId/lessonId/currentSectionId 不能为空", requestId);
        }

        double progressPercent = parseDouble(request.get("progressPercent"), 0);
        progressPercent = Math.min(Math.max(progressPercent, 0), 100);

        String key = userId + "::" + lessonId;
        Map<String, Object> record = new HashMap<>();
        record.put("trackId", "track" + trackCounter.getAndIncrement());
        record.put("userId", userId);
        record.put("lessonId", lessonId);
        record.put("currentSectionId", currentSectionId);
        record.put("progressPercent", progressPercent);
        record.put("lastOperateTime", str(request.get("lastOperateTime")));
        record.put("qaRecordId", str(request.get("qaRecordId")));
        progressStore.put(key, record);

        Map<String, Object> data = new HashMap<>();
        data.put("trackId", record.get("trackId"));
        data.put("totalProgress", progressPercent);
        data.put("nextSectionSuggest", currentSectionId);
        return okObj("进度追踪成功", data, requestId);
    }

    /**
     * 学习节奏调整（规范预留接口）
     */
    @PostMapping("/api/v1/progress/adjust")
    public ResponseEntity<ApiResponse<Map<String, Object>>> progressAdjust(@RequestBody Map<String, Object> request, HttpServletRequest httpRequest) {
        String requestId = nextRequestId();

        ResponseEntity<ApiResponse<Map<String, Object>>> authError = requireAuthObj(requestId, httpRequest);
        if (authError != null) {
            return authError;
        }
        ResponseEntity<ApiResponse<Map<String, Object>>> signError = validateSignatureObj(request, requestId);
        if (signError != null) {
            return signError;
        }

        return buildProgressAdjustResponse(request, requestId);
    }

    @PostMapping("/public/api/v1/progress/adjust")
    public ResponseEntity<ApiResponse<Map<String, Object>>> publicProgressAdjust(@RequestBody Map<String, Object> request) {
        String requestId = nextRequestId();

        try {
            requirePublishedProject(request);
            return buildProgressAdjustResponse(request, requestId);
        } catch (ProjectService.ProjectException e) {
            return badRequestObj(e.getMessage(), requestId);
        } catch (Exception e) {
            e.printStackTrace();
            return serverErrorObj("节奏调整失败：" + e.getMessage(), requestId);
        }
    }

    private ResponseEntity<ApiResponse<Map<String, Object>>> buildProgressAdjustResponse(Map<String, Object> request, String requestId) {
        String userId = str(request.get("userId"));
        String lessonId = str(request.get("lessonId"));
        String currentSectionId = str(request.get("currentSectionId"));
        String understandingLevel = str(request.get("understandingLevel"));

        if (userId.isEmpty() || lessonId.isEmpty() || currentSectionId.isEmpty() || understandingLevel.isEmpty()) {
            return badRequestObj("userId/lessonId/currentSectionId/understandingLevel 不能为空", requestId);
        }

        Map<String, Object> adjustPlan = new LinkedHashMap<>();
        adjustPlan.put("continueSectionId", currentSectionId);

        if ("partial".equalsIgnoreCase(understandingLevel) || "none".equalsIgnoreCase(understandingLevel)) {
            adjustPlan.put("adjustType", "supplement");
            Map<String, Object> supplement = new LinkedHashMap<>();
            supplement.put("content", "检测到理解不充分，已触发补充讲解。建议结合例题重新说明关键知识点。");
            supplement.put("duration", 30);
            supplement.put("relatedExample", "建议补充一个与当前章节相关的工程应用案例。");
            adjustPlan.put("supplementContent", supplement);
        } else {
            adjustPlan.put("adjustType", "normal");
        }

        List<Map<String, Object>> nextSections = new ArrayList<>();
        Map<String, Object> sec = new LinkedHashMap<>();
        sec.put("sectionId", currentSectionId);
        sec.put("adjustedDuration", "supplement".equals(adjustPlan.get("adjustType")) ? 75 : 45);
        sec.put("isKeyPointStrengthen", "supplement".equals(adjustPlan.get("adjustType")));
        nextSections.add(sec);
        adjustPlan.put("nextSections", nextSections);

        Map<String, Object> data = new HashMap<>();
        data.put("adjustPlan", adjustPlan);
        return okObj("节奏调整成功", data, requestId);
    }

    private ResponseEntity<ApiResponse<Map<String, Object>>> buildAnswerResponse(
            Map<String, Object> request,
            String requestId,
            ProjectService.ProjectRecord project,
            boolean publicAccess
    ) {
        String question = str(request.get("question"));
        if (question.isEmpty()) {
            question = str(request.get("questionContent"));
        }

        String pptText = str(request.get("pptText"));
        if (pptText.isEmpty() && project != null) {
            pptText = str(project.getPptRawText());
            if (pptText.isEmpty()) {
                pptText = str(project.getScript());
            }
        }
        if (pptText.isEmpty()) {
            pptText = "课堂问答上下文";
        }

        if (question.isEmpty()) {
            return badRequestObj("请输入问题", requestId);
        }

        if (project != null && project.isComputerMode()) {
            String resourceId = str(request.get("resourceId"));
            String resourceContext = publicAccess
                    ? projectService.buildPublishedComputerContext(project, resourceId)
                    : projectService.buildComputerContext(project, resourceId);
            List<KnowledgeRetrievalService.Hit> knowledgeHits = knowledgeRetrievalService.search(
                    project.getCourseType(),
                    question,
                    5
            );
            String knowledgeContext = knowledgeRetrievalService.formatContext(knowledgeHits);
            Map<String, String> result = computerCoursePromptService.answer(
                    project,
                    str(request.get("questionType")),
                    question,
                    pptText,
                    resourceContext,
                    knowledgeContext,
                    resourceId
            );
            if (isAiCallFailure(result.get("answer"))) {
                return gatewayErrorObj(result.get("answer"), requestId);
            }
            Map<String, Object> data = new HashMap<>();
            data.put("question", question);
            data.put("answer", result.get("answer"));
            data.put("source", "computer_project");
            data.put("sourceLabel", result.get("sourceLabel"));
            data.put("questionType", result.get("questionType"));
            data.put("resourceId", result.get("resourceId"));
            data.put("errorType", result.get("errorType"));
            data.put("hintLevel", result.get("hintLevel"));
            data.put("knowledgeSources", knowledgeRetrievalService.sourceViews(knowledgeHits));
            data.put("knowledgeHitCount", knowledgeHits.size());
            data.put("understandingLevel", "debug".equals(result.get("questionType")) ? "partial" : "full");
            return okObj("计算机课程专项问答成功", data, requestId);
        }

        List<Map<String, Object>> hits = qaSearchService.search(question, 3);
        if (!hits.isEmpty()) {
            Map<String, Object> top1 = hits.get(0);
            double score = parseScore(top1.get("score"));

            if (score >= QA_DATASET_HIT_THRESHOLD) {
                Map<String, Object> data = new HashMap<>();
                data.put("question", question);
                data.put("answer", str(top1.get("answer")));
                data.put("source", "dataset");
                data.put("hitScore", score);
                data.put("topHits", hits);
                data.put("understandingLevel", "full");
                return okObj("问答成功（命中知识库）", data, requestId);
            }
        }

        String answer = AiApiUtil.answerStudentQuestion(question, pptText);
        if (isAiCallFailure(answer)) {
            return gatewayErrorObj(answer, requestId);
        }

        Map<String, Object> data = new HashMap<>();
        data.put("question", question);
        data.put("answer", answer);
        data.put("source", "llm");
        data.put("topHits", hits);
        data.put("understandingLevel", "partial");
        return okObj("问答成功", data, requestId);
    }

    private ProjectService.ProjectRecord requirePublishedProject(Map<String, Object> request) {
        String projectId = str(request.get("projectId"));
        if (projectId.isEmpty()) {
            projectId = str(request.get("lessonId"));
        }
        if (projectId.isEmpty()) {
            throw new ProjectService.ProjectException("缺少已发布智课标识");
        }
        return projectService.getPublishedProject(projectId);
    }

    private ProjectService.ProjectRecord resolveOwnedProject(String projectId, HttpServletRequest request) {
        if (projectId == null || projectId.trim().isEmpty()) {
            return null;
        }
        AuthService.AuthUserView user = authService.getUserBySession(getSessionId(request));
        if (user == null) {
            return null;
        }
        try {
            return projectService.getProject(user.getUsername(), projectId.trim());
        } catch (ProjectService.ProjectException ignored) {
            return null;
        }
    }

    /**
     * 平台课程同步（规范预留接口）
     */
    @PostMapping("/api/v1/platform/syncCourse")
    public ResponseEntity<ApiResponse<Map<String, Object>>> syncCourse(@RequestBody Map<String, Object> request, HttpServletRequest httpRequest) {
        String requestId = nextRequestId();

        ResponseEntity<ApiResponse<Map<String, Object>>> authError = requireAuthObj(requestId, httpRequest);
        if (authError != null) {
            return authError;
        }
        ResponseEntity<ApiResponse<Map<String, Object>>> roleError = requireRoleObj(
                requestId, httpRequest, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN
        );
        if (roleError != null) {
            return roleError;
        }
        ResponseEntity<ApiResponse<Map<String, Object>>> signError = validateSignatureObj(request, requestId);
        if (signError != null) {
            return signError;
        }

        String platformId = str(request.get("platformId"));
        if (platformId.isEmpty()) {
            return badRequestObj("platformId 不能为空", requestId);
        }

        Map<String, Object> data = new HashMap<>();
        data.put("internalCourseId", "cou" + System.currentTimeMillis());
        data.put("syncStatus", "success");
        data.put("syncTime", LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")));
        return okObj("课程同步成功", data, requestId);
    }

    /**
     * 平台用户同步（规范预留接口）
     */
    @PostMapping("/api/v1/platform/syncUser")
    public ResponseEntity<ApiResponse<Map<String, Object>>> syncUser(@RequestBody Map<String, Object> request, HttpServletRequest httpRequest) {
        String requestId = nextRequestId();

        ResponseEntity<ApiResponse<Map<String, Object>>> authError = requireAuthObj(requestId, httpRequest);
        if (authError != null) {
            return authError;
        }
        ResponseEntity<ApiResponse<Map<String, Object>>> roleError = requireRoleObj(
                requestId, httpRequest, AuthService.ROLE_TEACHER, AuthService.ROLE_ADMIN
        );
        if (roleError != null) {
            return roleError;
        }
        ResponseEntity<ApiResponse<Map<String, Object>>> signError = validateSignatureObj(request, requestId);
        if (signError != null) {
            return signError;
        }

        String platformId = str(request.get("platformId"));
        if (platformId.isEmpty()) {
            return badRequestObj("platformId 不能为空", requestId);
        }

        Map<String, Object> data = new HashMap<>();
        data.put("internalUserId", "usr" + System.currentTimeMillis());
        data.put("syncStatus", "success");
        return okObj("用户同步成功", data, requestId);
    }

    private <T> ResponseEntity<ApiResponse<T>> ok(String msg, T data, String requestId) {
        return ResponseEntity.ok(ApiResponse.success(msg, data, requestId));
    }

    private <T> ResponseEntity<ApiResponse<T>> badRequest(String msg, String requestId) {
        return ResponseEntity.badRequest().body(ApiResponse.error(msg, requestId));
    }

    private <T> ResponseEntity<ApiResponse<T>> serverError(String msg, String requestId) {
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(ApiResponse.error(msg, requestId));
    }

    private <T> ResponseEntity<ApiResponse<T>> gatewayError(String msg, String requestId) {
        return ResponseEntity.status(HttpStatus.BAD_GATEWAY).body(ApiResponse.error(msg, requestId));
    }

    private ResponseEntity<ApiResponse<Map<String, Object>>> okObj(String msg, Map<String, Object> data, String requestId) {
        return ResponseEntity.ok(ApiResponse.success(msg, data, requestId));
    }

    private ResponseEntity<ApiResponse<Map<String, Object>>> badRequestObj(String msg, String requestId) {
        return ResponseEntity.badRequest().body(ApiResponse.error(msg, requestId));
    }

    private ResponseEntity<ApiResponse<Map<String, Object>>> serverErrorObj(String msg, String requestId) {
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(ApiResponse.error(msg, requestId));
    }

    private ResponseEntity<ApiResponse<Map<String, Object>>> gatewayErrorObj(String msg, String requestId) {
        return ResponseEntity.status(HttpStatus.BAD_GATEWAY).body(ApiResponse.error(msg, requestId));
    }

    private String nextRequestId() {
        return "req" + LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMddHHmmss")) + String.format("%05d", requestCounter.getAndIncrement());
    }

    private ResponseEntity<ApiResponse<Map<String, String>>> requireAuth(String requestId, HttpServletRequest request, String... allowedRoles) {
        String sessionId = getSessionId(request);
        if (authService.getUserBySession(sessionId) == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(ApiResponse.error("未登录或登录已失效", requestId));
        }
        if (allowedRoles != null && allowedRoles.length > 0 && !authService.hasActiveRole(sessionId, allowedRoles)) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body(ApiResponse.error("当前身份无权访问该资源", requestId));
        }
        return null;
    }

    private ResponseEntity<ApiResponse<Map<String, Object>>> requireAuthObj(String requestId, HttpServletRequest request) {
        String sessionId = getSessionId(request);
        if (authService.getUserBySession(sessionId) == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(ApiResponse.error("未登录或登录已失效", requestId));
        }
        return null;
    }

    private ResponseEntity<ApiResponse<Map<String, Object>>> requireRoleObj(String requestId, HttpServletRequest request, String... allowedRoles) {
        String sessionId = getSessionId(request);
        if (authService.getUserBySession(sessionId) == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(ApiResponse.error("未登录或登录已失效", requestId));
        }
        if (allowedRoles != null && allowedRoles.length > 0 && !authService.hasActiveRole(sessionId, allowedRoles)) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body(ApiResponse.error("当前身份无权访问该资源", requestId));
        }
        return null;
    }

    private String getSessionId(HttpServletRequest request) {
        if (request == null || request.getCookies() == null) {
            return "";
        }
        for (Cookie cookie : request.getCookies()) {
            if (AUTH_COOKIE.equals(cookie.getName())) {
                return str(cookie.getValue());
            }
        }
        return "";
    }

    private double parseScore(Object scoreObj) {
        if (scoreObj == null) {
            return 0.0;
        }
        try {
            return Double.parseDouble(String.valueOf(scoreObj));
        } catch (Exception ignored) {
            return 0.0;
        }
    }

    private double parseDouble(Object obj, double defaultVal) {
        if (obj == null) {
            return defaultVal;
        }
        try {
            return Double.parseDouble(String.valueOf(obj));
        } catch (Exception ignored) {
            return defaultVal;
        }
    }

    private String str(Object obj) {
        return obj == null ? "" : String.valueOf(obj).trim();
    }

    private boolean isAiCallFailure(String text) {
        if (text == null || text.trim().isEmpty()) {
            return true;
        }
        return text.startsWith("API调用失败")
                || text.startsWith("网络异常")
                || text.startsWith("❌")
                || text.startsWith("⚠️");
    }

    /** 检测讲稿是否大量复读 PPT 提纲原文。 */
    private boolean looksLikePptEcho(String script, String pptText) {
        if (script == null || pptText == null || script.length() < 40) {
            return false;
        }
        int hit = 0;
        int total = 0;
        for (String row : pptText.split("\\r?\\n")) {
            String line = row == null ? "" : row.trim();
            if (line.length() < 6 || line.matches("^=+\\s*第\\d+页\\s*=+$")) {
                continue;
            }
            total++;
            if (script.contains(line)) {
                hit++;
            }
            if (total >= 20) {
                break;
            }
        }
        return total >= 4 && hit * 1.0 / total >= 0.55;
    }

    private boolean isPublicHttpUrl(String url) {
        if (url == null) {
            return false;
        }
        String v = url.trim().toLowerCase();
        return v.startsWith("http://") || v.startsWith("https://");
    }

    private String resolveMode(String requestMode) {
        String mode = requestMode;
        if (mode == null || mode.isEmpty()) {
            mode = normalizeMode(digitalMode);
        }
        if (mode.isEmpty()) {
            return "auto";
        }
        return mode;
    }

    private String normalizeMode(String mode) {
        String m = mode == null ? "" : mode.trim().toLowerCase();
        if ("local".equals(m) || "cloud".equals(m) || "auto".equals(m)) {
            return m;
        }
        return "";
    }

    private Map<String, String> tryCloudDigitalHumanFast(String audioUrl) {
        Map<String, String> result = new HashMap<>();
        result.put("success", "false");

        if (!digitalCloudEnabled) {
            result.put("error", "cloud.enabled=false");
            return result;
        }

        Map<String, String> cloud = DigitalHumanCloudUtil.createVideo(
                digitalCloudUrl,
                digitalCloudApiKey,
                digitalCloudAuthHeader,
                digitalCloudAuthPrefix,
                digitalCloudAk,
                digitalCloudSk,
                digitalCloudRegion,
                digitalCloudService,
                digitalCloudReqKey,
                digitalCloudResourceId,
                audioUrl,
                Math.min(Math.max(digitalCloudTimeoutMs, 800), CLOUD_FAST_TIMEOUT_MS),
                Math.min(Math.max(digitalCloudPollAttempts, 1), CLOUD_FAST_POLL_ATTEMPTS),
                Math.min(Math.max(digitalCloudPollIntervalMs, 100), CLOUD_FAST_POLL_INTERVAL_MS)
        );

        if (cloud == null) {
            result.put("error", "云端返回为空");
            return result;
        }

        return cloud;
    }

    private ResponseEntity<ApiResponse<Map<String, String>>> validateSignature(Map<String, String> params, String requestId) {
        if (!signatureRequired) {
            return null;
        }

        String enc = params.get("enc");
        String time = params.get("time");
        if (enc == null || enc.trim().isEmpty() || time == null || time.trim().isEmpty()) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body(ApiResponse.error("签名校验失败：缺少 enc/time", requestId));
        }

        Map<String, String> copied = new HashMap<>(params);
        copied.remove("enc");
        copied.remove("file");
        String expected = buildSignature(copied, time);
        if (!enc.equalsIgnoreCase(expected)) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body(ApiResponse.error("签名校验失败：enc 不匹配", requestId));
        }

        return null;
    }

    private ResponseEntity<ApiResponse<Map<String, Object>>> validateSignatureObj(Map<String, Object> params, String requestId) {
        if (!signatureRequired) {
            return null;
        }

        String enc = str(params.get("enc"));
        String time = str(params.get("time"));
        if (enc.isEmpty() || time.isEmpty()) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body(ApiResponse.error("签名校验失败：缺少 enc/time", requestId));
        }

        Map<String, String> copied = new HashMap<>();
        for (Map.Entry<String, Object> e : params.entrySet()) {
            copied.put(e.getKey(), str(e.getValue()));
        }
        copied.remove("enc");
        String expected = buildSignature(copied, time);
        if (!enc.equalsIgnoreCase(expected)) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body(ApiResponse.error("签名校验失败：enc 不匹配", requestId));
        }

        return null;
    }

    private String buildSignature(Map<String, String> params, String time) {
        List<Map.Entry<String, String>> entries = new ArrayList<>(params.entrySet());
        entries.removeIf(e -> e.getValue() == null || e.getValue().trim().isEmpty() || "time".equals(e.getKey()));
        entries.sort(Comparator.comparing(Map.Entry::getKey));

        StringBuilder sb = new StringBuilder();
        for (Map.Entry<String, String> e : entries) {
            sb.append(e.getKey()).append(e.getValue());
        }
        sb.append(staticKey).append(time);

        return md5Hex(sb.toString());
    }

    private String md5Hex(String src) {
        try {
            MessageDigest md = MessageDigest.getInstance("MD5");
            byte[] digest = md.digest(src.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            for (byte b : digest) {
                sb.append(String.format("%02X", b));
            }
            return sb.toString();
        } catch (Exception e) {
            return "";
        }
    }
}
