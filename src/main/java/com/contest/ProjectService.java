package com.contest;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import javax.annotation.PostConstruct;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class ProjectService {

    private static final TypeReference<Map<String, ProjectRecord>> PROJECT_MAP_TYPE = new TypeReference<Map<String, ProjectRecord>>() {};

    private final ObjectMapper objectMapper = new ObjectMapper();
    private final Map<String, ProjectRecord> projects = new LinkedHashMap<>();
    private final DatabaseStore databaseStore;
    private boolean databaseReady;

    public ProjectService(DatabaseStore databaseStore) {
        this.databaseStore = databaseStore;
    }

    @Value("${project.store-file:data/projects.json}")
    private String projectStoreFile;

    private Path projectStorePath;

    @PostConstruct
    public synchronized void init() throws IOException {
        projectStorePath = Paths.get(projectStoreFile).toAbsolutePath();
        Path parent = projectStorePath.getParent();
        if (parent != null) {
            Files.createDirectories(parent);
        }
        databaseReady = prepareDatabase();
        Map<String, ProjectRecord> fromDb = new LinkedHashMap<>();
        if (databaseReady) {
            try {
                Map<String, ProjectRecord> loaded = databaseStore.loadProjects();
                if (loaded != null) {
                    fromDb.putAll(loaded);
                }
            } catch (Exception e) {
                databaseReady = false;
            }
        }
        Map<String, ProjectRecord> fromFile = new LinkedHashMap<>();
        if (Files.exists(projectStorePath)) {
            try {
                Map<String, ProjectRecord> loaded = objectMapper.readValue(projectStorePath.toFile(), PROJECT_MAP_TYPE);
                if (loaded != null) {
                    fromFile.putAll(loaded);
                }
            } catch (IOException e) {
                // 解析失败：备份原文件（含时间戳）供人工恢复，而不是静默清空
                Path backup = projectStorePath.resolveSibling(
                        projectStorePath.getFileName() + ".corrupt_" + System.currentTimeMillis());
                try {
                    Files.copy(projectStorePath, backup, java.nio.file.StandardCopyOption.REPLACE_EXISTING);
                    System.err.println("projects.json 解析失败，已备份到: " + backup);
                } catch (IOException ignored2) { /* 尽力而为 */ }
            }
        }
        projects.clear();
        // 以较新 updatedAt 为准合并，避免 MySQL/JSON 单边丢项目导致「项目不存在」
        Map<String, ProjectRecord> merged = new LinkedHashMap<>();
        merged.putAll(fromFile);
        for (Map.Entry<String, ProjectRecord> e : fromDb.entrySet()) {
            ProjectRecord dbRec = e.getValue();
            ProjectRecord fileRec = merged.get(e.getKey());
            if (fileRec == null || isNewer(dbRec.getUpdatedAt(), fileRec.getUpdatedAt())) {
                merged.put(e.getKey(), dbRec);
            }
        }
        projects.putAll(merged);
        if (projects.isEmpty()) {
            // 空载启动时不要把空 Map 写回磁盘/数据库，避免覆盖或误删已有项目
            if (!Files.exists(projectStorePath)) {
                persistProjectsToFile();
            }
            return;
        }
        persistProjectsToFile();
        if (databaseReady) {
            try {
                databaseStore.saveProjects(projects);
            } catch (Exception e) {
                databaseReady = false;
            }
        }
    }

    private static boolean isNewer(String a, String b) {
        if (a == null || a.isBlank()) {
            return false;
        }
        if (b == null || b.isBlank()) {
            return true;
        }
        return a.compareTo(b) >= 0;
    }

    private synchronized void persistProjectsToFile() {
        try {
            // 原子写：先写临时文件再原子替换，防止进程中断导致数据文件损坏或被清空
            Path tmp = projectStorePath.resolveSibling(projectStorePath.getFileName() + ".tmp");
            objectMapper.writerWithDefaultPrettyPrinter().writeValue(tmp.toFile(), projects);
            Files.move(tmp, projectStorePath, java.nio.file.StandardCopyOption.REPLACE_EXISTING, java.nio.file.StandardCopyOption.ATOMIC_MOVE);
        } catch (IOException e) {
            throw new ProjectException("项目数据保存失败，请稍后重试");
        }
    }

    public synchronized ProjectRecord createProject(
            String username,
            String name,
            String meta,
            String subjectMode,
            String courseType,
            String programmingLanguage,
            String teachingGoal
    ) {
        if (username == null || username.trim().isEmpty()) {
            throw new ProjectException("当前用户不能为空");
        }
        String finalName = name == null || name.trim().isEmpty() ? "未命名项目" : name.trim();
        ProjectRecord record = new ProjectRecord();
        record.setId("proj_" + UUID.randomUUID().toString().replace("-", ""));
        record.setUsername(username.trim().toLowerCase());
        record.setName(finalName);
        record.setMeta(meta == null ? "" : meta.trim());
        record.setSubjectMode(normalizeSubjectMode(subjectMode));
        record.setCourseType(clean(courseType));
        record.setProgrammingLanguage(clean(programmingLanguage));
        record.setTeachingGoal(clean(teachingGoal));
        record.setResources(new ArrayList<>());
        record.setLearningRecords(new ArrayList<>());
        record.setLabTasks(new ArrayList<>());
        record.setCodeSubmissions(new ArrayList<>());
        record.setCreatedAt(Instant.now().toString());
        record.setUpdatedAt(record.getCreatedAt());
        projects.put(record.getId(), record);
        persistProject(record);
        return record;
    }

    public synchronized List<ProjectRecord> listProjects(String username) {
        List<ProjectRecord> items = new ArrayList<>();
        String normalized = username == null ? "" : username.trim().toLowerCase();
        for (ProjectRecord record : projects.values()) {
            if (normalized.equals(record.getUsername())) {
                items.add(record);
            }
        }
        items.sort(Comparator.comparing(ProjectRecord::getUpdatedAt, Comparator.nullsLast(String::compareTo)).reversed());
        return items;
    }

    public synchronized List<ProjectRecord> listAllProjectsForAdmin() {
        List<ProjectRecord> items = new ArrayList<>(projects.values());
        items.sort(Comparator.comparing(ProjectRecord::getUpdatedAt, Comparator.nullsLast(String::compareTo)).reversed());
        return items;
    }

    public synchronized ProjectRecord getProject(String username, String projectId) {
        ProjectRecord record = projects.get(projectId);
        if (record == null) {
            throw new ProjectException("项目不存在");
        }
        String normalized = username == null ? "" : username.trim().toLowerCase();
        if (!normalized.equals(record.getUsername())) {
            throw new ProjectException("无权访问该项目");
        }
        return record;
    }

    public synchronized ProjectRecord updateProjectContent(
            String username,
            String projectId,
            String pptRawText,
            String script,
            String summary,
            String audioUrl,
            String digitalUrl,
            String lessonTitle,
            String lessonIntro,
            String subjectMode,
            String courseType,
            String programmingLanguage,
            String teachingGoal,
            String name,
            String meta
    ) {
        ProjectRecord record = getProject(username, projectId);
        if (name != null) {
            String trimmed = name.trim();
            if (!trimmed.isEmpty()) {
                record.setName(trimmed);
            }
        }
        if (meta != null) {
            record.setMeta(meta.trim());
        }
        if (pptRawText != null) {
          record.setPptRawText(pptRawText);
        }
        if (script != null) {
          record.setScript(script);
        }
        if (summary != null) {
          record.setSummary(summary);
        }
        if (audioUrl != null) {
          record.setAudioUrl(audioUrl);
        }
        if (digitalUrl != null) {
          record.setDigitalUrl(digitalUrl);
        }
        if (lessonTitle != null) {
          record.setLessonTitle(lessonTitle);
        }
        if (lessonIntro != null) {
          record.setLessonIntro(lessonIntro);
        }
        if (subjectMode != null) {
          record.setSubjectMode(normalizeSubjectMode(subjectMode));
        }
        if (courseType != null) {
          record.setCourseType(clean(courseType));
        }
        if (programmingLanguage != null) {
          record.setProgrammingLanguage(clean(programmingLanguage));
        }
        if (teachingGoal != null) {
          record.setTeachingGoal(clean(teachingGoal));
        }
        record.setUpdatedAt(Instant.now().toString());
        projects.put(projectId, record);
        persistProject(record);
        return record;
    }

    public synchronized ProjectRecord publishProject(
            String username,
            String projectId,
            String lessonTitle,
            String lessonIntro,
            String audioUrl,
            String digitalUrl
    ) {
        ProjectRecord record = getProject(username, projectId);
        record.setPublished(true);
        record.setPublishedAt(Instant.now().toString());
        record.setLessonTitle(isBlank(lessonTitle) ? record.getName() : lessonTitle.trim());
        record.setLessonIntro(isBlank(lessonIntro) ? record.getSummary() : lessonIntro.trim());
        if (audioUrl != null) {
            record.setAudioUrl(audioUrl.trim());
        }
        if (digitalUrl != null) {
            record.setDigitalUrl(digitalUrl.trim());
        }
        record.setUpdatedAt(Instant.now().toString());
        projects.put(projectId, record);
        persistProject(record);
        return record;
    }

    public synchronized List<ProjectRecord> listPublishedProjects() {
        List<ProjectRecord> items = new ArrayList<>();
        for (ProjectRecord record : projects.values()) {
            if (record.isPublished()) {
                items.add(record);
            }
        }
        items.sort(Comparator.comparing(ProjectRecord::getPublishedAt, Comparator.nullsLast(String::compareTo)).reversed());
        return items;
    }

    public synchronized List<PublishedLessonView> listPublishedLessonViews() {
        List<PublishedLessonView> items = new ArrayList<>();
        for (ProjectRecord record : listPublishedProjects()) {
            items.add(PublishedLessonView.from(record, false));
        }
        return items;
    }

    public synchronized ProjectRecord getPublishedProject(String projectId) {
        ProjectRecord record = projects.get(projectId);
        if (record == null || !record.isPublished()) {
            throw new ProjectException("智课不存在或尚未发布");
        }
        return record;
    }

    public synchronized PublishedLessonView getPublishedLessonView(String projectId) {
        return PublishedLessonView.from(getPublishedProject(projectId), true);
    }

    /**
     * 教师学情视图：完整项目字段，但学习记录仅保留学生（排除项目所有者与教师/管理员账号）。
     * 返回副本，不改写内存中的原始项目。
     */
    public ProjectRecord toTeacherInsightProject(ProjectRecord source, AuthService authService) {
        if (source == null) {
            return null;
        }
        ProjectRecord view = objectMapper.convertValue(source, ProjectRecord.class);
        List<LearningRecord> filtered = new ArrayList<>();
        String owner = source.getUsername() == null ? "" : source.getUsername().trim().toLowerCase();
        List<LearningRecord> raw = source.getLearningRecords();
        if (raw != null) {
            for (LearningRecord item : raw) {
                if (item == null) {
                    continue;
                }
                String learner = item.getLearnerUsername() == null ? "" : item.getLearnerUsername().trim().toLowerCase();
                if (!learner.isEmpty() && !owner.isEmpty() && owner.equals(learner)) {
                    continue;
                }
                if (!learner.isEmpty() && authService != null && authService.usernameHasStaffRole(learner)) {
                    continue;
                }
                filtered.add(item);
            }
        }
        view.setLearningRecords(filtered);
        return view;
    }

    public synchronized ProjectRecord appendLearningRecord(
            String learnerUsername,
            String projectId,
            String currentSectionId,
            double progressPercent,
            String question,
            String answer,
            String understandingLevel,
            String action,
            String questionType,
            String resourceId,
            String errorType,
            String hintLevel,
            boolean resolved
    ) {
        ProjectRecord record = getPublishedProject(projectId);
        if (record.getLearningRecords() == null) {
            record.setLearningRecords(new ArrayList<>());
        }
        LearningRecord item = new LearningRecord();
        item.setId("lrn_" + UUID.randomUUID().toString().replace("-", ""));
        item.setLearnerUsername(learnerUsername == null ? "" : learnerUsername.trim().toLowerCase());
        item.setCurrentSectionId(currentSectionId == null ? "" : currentSectionId.trim());
        item.setProgressPercent(Math.min(Math.max(progressPercent, 0), 100));
        item.setQuestion(question == null ? "" : question.trim());
        item.setAnswer(answer == null ? "" : answer.trim());
        item.setUnderstandingLevel(understandingLevel == null ? "" : understandingLevel.trim());
        item.setAction(action == null ? "" : action.trim());
        item.setQuestionType(clean(questionType));
        item.setResourceId(clean(resourceId));
        item.setErrorType(clean(errorType));
        item.setHintLevel(clean(hintLevel));
        item.setResolved(resolved);
        item.setCreatedAt(Instant.now().toString());
        record.getLearningRecords().add(item);
        record.setUpdatedAt(Instant.now().toString());
        projects.put(projectId, record);
        persistLearningRecord(record, item);
        return record;
    }

    public synchronized ProjectRecord resolveLatestQuestion(
            String learnerUsername,
            String projectId,
            String resourceId
    ) {
        ProjectRecord record = getPublishedProject(projectId);
        String normalizedLearner = clean(learnerUsername).toLowerCase();
        List<LearningRecord> learningRecords = record.getLearningRecords();
        if (learningRecords == null || learningRecords.isEmpty()) {
            throw new ProjectException("当前还没有可标记为已解决的问题");
        }
        for (int index = learningRecords.size() - 1; index >= 0; index--) {
            LearningRecord item = learningRecords.get(index);
            boolean sameLearner = normalizedLearner.equals(clean(item.getLearnerUsername()).toLowerCase());
            boolean sameResource = isBlank(resourceId) || clean(resourceId).equals(clean(item.getResourceId()));
            if (sameLearner && sameResource && !isBlank(item.getQuestion()) && !item.isResolved()) {
                item.setResolved(true);
                record.setUpdatedAt(Instant.now().toString());
                projects.put(projectId, record);
                persistLearningRecord(record, item);
                return record;
            }
        }
        throw new ProjectException("未找到尚未解决的问题");
    }

    private boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }

    public synchronized ProjectRecord addResource(
            String username,
            String projectId,
            ProjectResource resource
    ) {
        ProjectRecord record = getProject(username, projectId);
        if (!record.isComputerMode()) {
            throw new ProjectException("仅计算机课程专项项目支持代码与实验资源");
        }
        if (record.getResources() == null) {
            record.setResources(new ArrayList<>());
        }
        record.getResources().add(resource);
        record.setUpdatedAt(Instant.now().toString());
        projects.put(projectId, record);
        persistProject(record);
        return record;
    }

    public synchronized ProjectRecord deleteResource(String username, String projectId, String resourceId) {
        ProjectRecord record = getProject(username, projectId);
        if (record.getResources() != null) {
            record.getResources().removeIf(item -> resourceId.equals(item.getId()));
        }
        record.setUpdatedAt(Instant.now().toString());
        projects.put(projectId, record);
        persistProject(record);
        return record;
    }

    public synchronized ProjectRecord addLabTask(
            String username,
            String projectId,
            LabTask task
    ) {
        ProjectRecord record = getProject(username, projectId);
        if (!record.isComputerMode()) {
            throw new ProjectException("仅计算机课程专项项目支持实验任务");
        }
        if (task == null || isBlank(task.getTitle())) {
            throw new ProjectException("实验任务标题不能为空");
        }
        if (task.getTestCases() == null || task.getTestCases().isEmpty()) {
            throw new ProjectException("实验任务至少需要一个测试用例");
        }
        if (record.getLabTasks() == null) {
            record.setLabTasks(new ArrayList<>());
        }
        if (isBlank(task.getId())) {
            task.setId("task_" + UUID.randomUUID().toString().replace("-", ""));
        }
        if (isBlank(task.getCreatedAt())) {
            task.setCreatedAt(Instant.now().toString());
        }
        task.setTimeLimitMs(Math.min(Math.max(task.getTimeLimitMs(), 500), 5000));
        int order = 0;
        for (LabTestCase testCase : task.getTestCases()) {
            if (isBlank(testCase.getId())) {
                testCase.setId("case_" + UUID.randomUUID().toString().replace("-", ""));
            }
            testCase.setSortOrder(order++);
        }
        record.getLabTasks().add(task);
        record.setUpdatedAt(Instant.now().toString());
        projects.put(projectId, record);
        persistLabTask(record, task);
        return record;
    }

    public synchronized ProjectRecord deleteLabTask(String username, String projectId, String taskId) {
        ProjectRecord record = getProject(username, projectId);
        if (record.getLabTasks() != null) {
            record.getLabTasks().removeIf(item -> clean(taskId).equals(item.getId()));
        }
        if (record.getCodeSubmissions() != null) {
            record.getCodeSubmissions().removeIf(item -> clean(taskId).equals(item.getTaskId()));
        }
        record.setUpdatedAt(Instant.now().toString());
        projects.put(projectId, record);
        removeLabTask(record, taskId);
        return record;
    }

    public synchronized LabTask getPublishedLabTask(String projectId, String taskId) {
        ProjectRecord record = getPublishedProject(projectId);
        if (!record.isComputerMode() || record.getLabTasks() == null) {
            throw new ProjectException("实验任务不存在");
        }
        for (LabTask task : record.getLabTasks()) {
            if (clean(taskId).equals(task.getId()) && task.isPublished()) {
                return task;
            }
        }
        throw new ProjectException("实验任务不存在或尚未发布");
    }

    public synchronized CodeSubmission addCodeSubmission(
            String learnerUsername,
            String projectId,
            LabTask task,
            String sourceCode,
            CodeJudgeService.JudgeResult result
    ) {
        ProjectRecord record = getPublishedProject(projectId);
        if (record.getCodeSubmissions() == null) {
            record.setCodeSubmissions(new ArrayList<>());
        }
        CodeSubmission submission = new CodeSubmission();
        submission.setId("sub_" + UUID.randomUUID().toString().replace("-", ""));
        submission.setTaskId(task.getId());
        submission.setLearnerUsername(clean(learnerUsername).toLowerCase());
        submission.setLanguage(task.getLanguage());
        submission.setSourceCode(sourceCode == null ? "" : sourceCode.trim());
        submission.setStatus(result.getStatus());
        submission.setScore(result.getScore());
        submission.setPassedCases(result.getPassedCases());
        submission.setTotalCases(result.getTotalCases());
        submission.setOutputText(result.getOutputText());
        submission.setErrorText(result.getErrorText());
        submission.setDurationMs(result.getDurationMs());
        submission.setCreatedAt(Instant.now().toString());
        record.getCodeSubmissions().add(submission);
        record.setUpdatedAt(Instant.now().toString());
        projects.put(projectId, record);
        persistCodeSubmission(record, submission);
        return submission;
    }

    public String buildComputerContext(ProjectRecord record, String preferredResourceId) {
        return buildComputerContext(record, preferredResourceId, true);
    }

    public String buildPublishedComputerContext(ProjectRecord record, String preferredResourceId) {
        return buildComputerContext(record, preferredResourceId, false);
    }

    private String buildComputerContext(
            ProjectRecord record,
            String preferredResourceId,
            boolean includeRawErrorLogs
    ) {
        if (record == null || record.getResources() == null || record.getResources().isEmpty()) {
            return "";
        }
        StringBuilder context = new StringBuilder();
        for (ProjectResource resource : record.getResources()) {
            if (preferredResourceId != null && !preferredResourceId.isBlank()
                    && !preferredResourceId.equals(resource.getId())) {
                continue;
            }
            appendResourceContext(context, resource, includeRawErrorLogs);
        }
        if (context.length() == 0 && preferredResourceId != null && !preferredResourceId.isBlank()) {
            for (ProjectResource resource : record.getResources()) {
                appendResourceContext(context, resource, includeRawErrorLogs);
            }
        }
        return context.length() > 12000 ? context.substring(0, 12000) : context.toString();
    }

    private void appendResourceContext(
            StringBuilder context,
            ProjectResource resource,
            boolean includeRawErrorLogs
    ) {
        context.append("\n【资源：").append(clean(resource.getFileName())).append("】")
                .append("\n类型：").append(clean(resource.getResourceType()))
                .append("，语言：").append(clean(resource.getLanguage()))
                .append("\n结构摘要：").append(clean(resource.getStructuredContent()));
        if (includeRawErrorLogs || !"error_log".equals(resource.getResourceType())) {
            context.append("\n内容：\n").append(clean(resource.getRawContent()));
        } else {
            context.append("\n内容：公开学习模式下已隐藏错误日志原文");
        }
        context.append("\n");
    }

    private String normalizeSubjectMode(String value) {
        return "computer".equalsIgnoreCase(clean(value)) ? "computer" : "general";
    }

    private static String clean(String value) {
        return value == null ? "" : value.trim();
    }

    public synchronized void deleteProject(String username, String projectId) {
        ProjectRecord record = projects.get(projectId);
        if (record == null) {
            return;
        }
        String normalized = username == null ? "" : username.trim().toLowerCase();
        if (!normalized.equals(record.getUsername())) {
            throw new ProjectException("无权删除该项目");
        }
        projects.remove(projectId);
        removeProject(projectId);
    }

    private synchronized void persistProjects() {
        if (projects.isEmpty()) {
            // 禁止用空集合去同步 MySQL（旧逻辑会清空整表）
            persistProjectsToFile();
            return;
        }
        // 始终写本地 JSON 作兜底；MySQL 可用时同步写入
        persistProjectsToFile();
        if (databaseReady) {
            try {
                databaseStore.saveProjects(projects);
            } catch (Exception e) {
                databaseReady = false;
            }
        }
    }

    private synchronized void persistProject(ProjectRecord record) {
        if (databaseReady) {
            try {
                databaseStore.upsertProject(record);
                return;
            } catch (Exception e) {
                databaseReady = false;
            }
        }
        persistProjects();
    }

    private synchronized void persistLearningRecord(ProjectRecord project, LearningRecord item) {
        if (databaseReady) {
            try {
                databaseStore.insertLearningRecord(project.getId(), project.getUpdatedAt(), item);
                return;
            } catch (Exception e) {
                databaseReady = false;
            }
        }
        persistProjects();
    }

    private synchronized void persistLabTask(ProjectRecord project, LabTask task) {
        if (databaseReady) {
            try {
                databaseStore.upsertLabTask(project.getId(), project.getUpdatedAt(), task);
                return;
            } catch (Exception e) {
                databaseReady = false;
            }
        }
        persistProjects();
    }

    private synchronized void persistCodeSubmission(ProjectRecord project, CodeSubmission submission) {
        if (databaseReady) {
            try {
                databaseStore.insertCodeSubmission(project.getId(), project.getUpdatedAt(), submission);
                return;
            } catch (Exception e) {
                databaseReady = false;
            }
        }
        persistProjects();
    }

    private synchronized void removeLabTask(ProjectRecord project, String taskId) {
        if (databaseReady) {
            try {
                databaseStore.deleteLabTask(project.getId(), project.getUpdatedAt(), taskId);
                return;
            } catch (Exception e) {
                databaseReady = false;
            }
        }
        persistProjects();
    }

    private synchronized void removeProject(String projectId) {
        if (databaseReady) {
            try {
                databaseStore.deleteProject(projectId);
                return;
            } catch (Exception e) {
                databaseReady = false;
            }
        }
        persistProjects();
    }

    private boolean prepareDatabase() {
        if (databaseStore == null || !databaseStore.isEnabled()) {
            return false;
        }
        try {
            databaseStore.initSchema();
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class ProjectRecord {
        private String id;
        private String username;
        private String name;
        private String meta;
        private String createdAt;
        private String updatedAt;
        private String pptRawText;
        private String script;
        private String summary;
        private boolean published;
        private String publishedAt;
        private String lessonTitle;
        private String lessonIntro;
        private String audioUrl;
        private String digitalUrl;
        private String subjectMode = "general";
        private String courseType;
        private String programmingLanguage;
        private String teachingGoal;
        private List<ProjectResource> resources;
        private List<LearningRecord> learningRecords;
        private List<LabTask> labTasks;
        private List<CodeSubmission> codeSubmissions;

        public String getId() {
            return id;
        }

        public void setId(String id) {
            this.id = id;
        }

        public String getUsername() {
            return username;
        }

        public void setUsername(String username) {
            this.username = username;
        }

        public String getName() {
            return name;
        }

        public void setName(String name) {
            this.name = name;
        }

        public String getMeta() {
            return meta;
        }

        public void setMeta(String meta) {
            this.meta = meta;
        }

        public String getCreatedAt() {
            return createdAt;
        }

        public void setCreatedAt(String createdAt) {
            this.createdAt = createdAt;
        }

        public String getUpdatedAt() {
            return updatedAt;
        }

        public void setUpdatedAt(String updatedAt) {
            this.updatedAt = updatedAt;
        }

        public String getPptRawText() {
            return pptRawText;
        }

        public void setPptRawText(String pptRawText) {
            this.pptRawText = pptRawText;
        }

        public String getScript() {
            return script;
        }

        public void setScript(String script) {
            this.script = script;
        }

        public String getSummary() {
            return summary;
        }

        public void setSummary(String summary) {
            this.summary = summary;
        }

        public boolean isPublished() {
            return published;
        }

        public void setPublished(boolean published) {
            this.published = published;
        }

        public String getPublishedAt() {
            return publishedAt;
        }

        public void setPublishedAt(String publishedAt) {
            this.publishedAt = publishedAt;
        }

        public String getLessonTitle() {
            return lessonTitle;
        }

        public void setLessonTitle(String lessonTitle) {
            this.lessonTitle = lessonTitle;
        }

        public String getLessonIntro() {
            return lessonIntro;
        }

        public void setLessonIntro(String lessonIntro) {
            this.lessonIntro = lessonIntro;
        }

        public String getAudioUrl() {
            return audioUrl;
        }

        public void setAudioUrl(String audioUrl) {
            this.audioUrl = audioUrl;
        }

        public String getDigitalUrl() {
            return digitalUrl;
        }

        public void setDigitalUrl(String digitalUrl) {
            this.digitalUrl = digitalUrl;
        }

        public String getSubjectMode() {
            return subjectMode == null || subjectMode.isBlank() ? "general" : subjectMode;
        }

        public void setSubjectMode(String subjectMode) {
            this.subjectMode = subjectMode;
        }

        public boolean isComputerMode() {
            return "computer".equalsIgnoreCase(getSubjectMode());
        }

        public String getCourseType() {
            return courseType;
        }

        public void setCourseType(String courseType) {
            this.courseType = courseType;
        }

        public String getProgrammingLanguage() {
            return programmingLanguage;
        }

        public void setProgrammingLanguage(String programmingLanguage) {
            this.programmingLanguage = programmingLanguage;
        }

        public String getTeachingGoal() {
            return teachingGoal;
        }

        public void setTeachingGoal(String teachingGoal) {
            this.teachingGoal = teachingGoal;
        }

        public List<ProjectResource> getResources() {
            return resources;
        }

        public void setResources(List<ProjectResource> resources) {
            this.resources = resources;
        }

        public List<LearningRecord> getLearningRecords() {
            return learningRecords;
        }

        public void setLearningRecords(List<LearningRecord> learningRecords) {
            this.learningRecords = learningRecords;
        }

        public List<LabTask> getLabTasks() {
            return labTasks;
        }

        public void setLabTasks(List<LabTask> labTasks) {
            this.labTasks = labTasks;
        }

        public List<CodeSubmission> getCodeSubmissions() {
            return codeSubmissions;
        }

        public void setCodeSubmissions(List<CodeSubmission> codeSubmissions) {
            this.codeSubmissions = codeSubmissions;
        }
    }

    public static class PublishedLessonView {
        private String id;
        private String name;
        private String meta;
        private String updatedAt;
        private String pptRawText;
        private String script;
        private String summary;
        private boolean published;
        private String publishedAt;
        private String lessonTitle;
        private String lessonIntro;
        private String audioUrl;
        private String digitalUrl;
        private String subjectMode;
        private String courseType;
        private String programmingLanguage;
        private String teachingGoal;
        private List<PublishedResourceView> resources = new ArrayList<>();
        private List<LearningRecord> learningRecords = new ArrayList<>();
        private List<PublishedLabTaskView> labTasks = new ArrayList<>();

        public static PublishedLessonView from(ProjectRecord record, boolean includeLessonContent) {
            PublishedLessonView view = new PublishedLessonView();
            view.id = record.getId();
            view.name = record.getName();
            view.meta = record.getMeta();
            view.updatedAt = record.getUpdatedAt();
            view.summary = record.getSummary();
            view.published = record.isPublished();
            view.publishedAt = record.getPublishedAt();
            view.lessonTitle = record.getLessonTitle();
            view.lessonIntro = record.getLessonIntro();
            view.subjectMode = record.getSubjectMode();
            view.courseType = record.getCourseType();
            view.programmingLanguage = record.getProgrammingLanguage();
            view.teachingGoal = record.getTeachingGoal();
            if (includeLessonContent) {
                view.pptRawText = record.getPptRawText();
                view.script = record.getScript();
                view.audioUrl = record.getAudioUrl();
                view.digitalUrl = record.getDigitalUrl();
                if (record.getResources() != null) {
                    for (ProjectResource resource : record.getResources()) {
                        view.resources.add(PublishedResourceView.from(resource));
                    }
                }
                if (record.getLabTasks() != null) {
                    for (LabTask task : record.getLabTasks()) {
                        if (task.isPublished()) {
                            view.labTasks.add(PublishedLabTaskView.from(task));
                        }
                    }
                }
            }
            return view;
        }

        public String getId() { return id; }
        public String getName() { return name; }
        public String getMeta() { return meta; }
        public String getUpdatedAt() { return updatedAt; }
        public String getPptRawText() { return pptRawText; }
        public String getScript() { return script; }
        public String getSummary() { return summary; }
        public boolean isPublished() { return published; }
        public String getPublishedAt() { return publishedAt; }
        public String getLessonTitle() { return lessonTitle; }
        public String getLessonIntro() { return lessonIntro; }
        public String getAudioUrl() { return audioUrl; }
        public String getDigitalUrl() { return digitalUrl; }
        public String getSubjectMode() { return subjectMode; }
        public String getCourseType() { return courseType; }
        public String getProgrammingLanguage() { return programmingLanguage; }
        public String getTeachingGoal() { return teachingGoal; }
        public List<PublishedResourceView> getResources() { return resources; }
        public List<LearningRecord> getLearningRecords() { return learningRecords; }
        public List<PublishedLabTaskView> getLabTasks() { return labTasks; }
    }

    public static class PublishedResourceView {
        private String id;
        private String resourceType;
        private String fileName;
        private String language;
        private String rawContent;
        private String structuredContent;

        public static PublishedResourceView from(ProjectResource resource) {
            PublishedResourceView view = new PublishedResourceView();
            view.id = resource.getId();
            view.resourceType = resource.getResourceType();
            view.fileName = resource.getFileName();
            view.language = resource.getLanguage();
            view.structuredContent = resource.getStructuredContent();
            view.rawContent = "error_log".equals(resource.getResourceType()) ? "" : resource.getRawContent();
            return view;
        }

        public String getId() { return id; }
        public String getResourceType() { return resourceType; }
        public String getFileName() { return fileName; }
        public String getLanguage() { return language; }
        public String getRawContent() { return rawContent; }
        public String getStructuredContent() { return structuredContent; }
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class LearningRecord {
        private String id;
        private String learnerUsername;
        private String currentSectionId;
        private double progressPercent;
        private String question;
        private String answer;
        private String understandingLevel;
        private String action;
        private String questionType;
        private String resourceId;
        private String errorType;
        private String hintLevel;
        private boolean resolved;
        private String createdAt;

        public String getId() {
            return id;
        }

        public void setId(String id) {
            this.id = id;
        }

        public String getLearnerUsername() {
            return learnerUsername;
        }

        public void setLearnerUsername(String learnerUsername) {
            this.learnerUsername = learnerUsername;
        }

        public String getCurrentSectionId() {
            return currentSectionId;
        }

        public void setCurrentSectionId(String currentSectionId) {
            this.currentSectionId = currentSectionId;
        }

        public double getProgressPercent() {
            return progressPercent;
        }

        public void setProgressPercent(double progressPercent) {
            this.progressPercent = progressPercent;
        }

        public String getQuestion() {
            return question;
        }

        public void setQuestion(String question) {
            this.question = question;
        }

        public String getAnswer() {
            return answer;
        }

        public void setAnswer(String answer) {
            this.answer = answer;
        }

        public String getUnderstandingLevel() {
            return understandingLevel;
        }

        public void setUnderstandingLevel(String understandingLevel) {
            this.understandingLevel = understandingLevel;
        }

        public String getAction() {
            return action;
        }

        public void setAction(String action) {
            this.action = action;
        }

        public String getQuestionType() {
            return questionType;
        }

        public void setQuestionType(String questionType) {
            this.questionType = questionType;
        }

        public String getResourceId() {
            return resourceId;
        }

        public void setResourceId(String resourceId) {
            this.resourceId = resourceId;
        }

        public String getErrorType() {
            return errorType;
        }

        public void setErrorType(String errorType) {
            this.errorType = errorType;
        }

        public String getHintLevel() {
            return hintLevel;
        }

        public void setHintLevel(String hintLevel) {
            this.hintLevel = hintLevel;
        }

        public boolean isResolved() {
            return resolved;
        }

        public void setResolved(boolean resolved) {
            this.resolved = resolved;
        }

        public String getCreatedAt() {
            return createdAt;
        }

        public void setCreatedAt(String createdAt) {
            this.createdAt = createdAt;
        }
    }

    public static class PublishedLabTaskView {
        private String id;
        private String title;
        private String description;
        private String language;
        private String judgeMode;
        private String starterCode;
        private String sampleInput;
        private String sampleOutput;
        private int timeLimitMs;
        private int testCaseCount;

        public static PublishedLabTaskView from(LabTask task) {
            PublishedLabTaskView view = new PublishedLabTaskView();
            view.id = task.getId();
            view.title = task.getTitle();
            view.description = task.getDescription();
            view.language = task.getLanguage();
            view.judgeMode = task.getJudgeMode();
            view.starterCode = task.getStarterCode();
            view.sampleInput = task.getSampleInput();
            view.sampleOutput = task.getSampleOutput();
            view.timeLimitMs = task.getTimeLimitMs();
            view.testCaseCount = task.getTestCases() == null ? 0 : task.getTestCases().size();
            return view;
        }

        public String getId() { return id; }
        public String getTitle() { return title; }
        public String getDescription() { return description; }
        public String getLanguage() { return language; }
        public String getJudgeMode() { return judgeMode; }
        public String getStarterCode() { return starterCode; }
        public String getSampleInput() { return sampleInput; }
        public String getSampleOutput() { return sampleOutput; }
        public int getTimeLimitMs() { return timeLimitMs; }
        public int getTestCaseCount() { return testCaseCount; }
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class LabTask {
        private String id;
        private String title;
        private String description;
        private String language;
        private String judgeMode = "io";
        private String starterCode;
        private String sampleInput;
        private String sampleOutput;
        private int timeLimitMs = 2000;
        private boolean published = true;
        private String createdAt;
        private List<LabTestCase> testCases;

        public String getId() { return id; }
        public void setId(String id) { this.id = id; }
        public String getTitle() { return title; }
        public void setTitle(String title) { this.title = title; }
        public String getDescription() { return description; }
        public void setDescription(String description) { this.description = description; }
        public String getLanguage() { return language; }
        public void setLanguage(String language) { this.language = language; }
        public String getJudgeMode() { return judgeMode; }
        public void setJudgeMode(String judgeMode) { this.judgeMode = judgeMode; }
        public String getStarterCode() { return starterCode; }
        public void setStarterCode(String starterCode) { this.starterCode = starterCode; }
        public String getSampleInput() { return sampleInput; }
        public void setSampleInput(String sampleInput) { this.sampleInput = sampleInput; }
        public String getSampleOutput() { return sampleOutput; }
        public void setSampleOutput(String sampleOutput) { this.sampleOutput = sampleOutput; }
        public int getTimeLimitMs() { return timeLimitMs; }
        public void setTimeLimitMs(int timeLimitMs) { this.timeLimitMs = timeLimitMs; }
        public boolean isPublished() { return published; }
        public void setPublished(boolean published) { this.published = published; }
        public String getCreatedAt() { return createdAt; }
        public void setCreatedAt(String createdAt) { this.createdAt = createdAt; }
        public List<LabTestCase> getTestCases() { return testCases; }
        public void setTestCases(List<LabTestCase> testCases) { this.testCases = testCases; }
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class LabTestCase {
        private String id;
        private String inputText;
        private String expectedOutput;
        private int sortOrder;

        public String getId() { return id; }
        public void setId(String id) { this.id = id; }
        public String getInputText() { return inputText; }
        public void setInputText(String inputText) { this.inputText = inputText; }
        public String getExpectedOutput() { return expectedOutput; }
        public void setExpectedOutput(String expectedOutput) { this.expectedOutput = expectedOutput; }
        public int getSortOrder() { return sortOrder; }
        public void setSortOrder(int sortOrder) { this.sortOrder = sortOrder; }
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class CodeSubmission {
        private String id;
        private String taskId;
        private String learnerUsername;
        private String language;
        private String sourceCode;
        private String status;
        private int score;
        private int passedCases;
        private int totalCases;
        private String outputText;
        private String errorText;
        private long durationMs;
        private String createdAt;

        public String getId() { return id; }
        public void setId(String id) { this.id = id; }
        public String getTaskId() { return taskId; }
        public void setTaskId(String taskId) { this.taskId = taskId; }
        public String getLearnerUsername() { return learnerUsername; }
        public void setLearnerUsername(String learnerUsername) { this.learnerUsername = learnerUsername; }
        public String getLanguage() { return language; }
        public void setLanguage(String language) { this.language = language; }
        public String getSourceCode() { return sourceCode; }
        public void setSourceCode(String sourceCode) { this.sourceCode = sourceCode; }
        public String getStatus() { return status; }
        public void setStatus(String status) { this.status = status; }
        public int getScore() { return score; }
        public void setScore(int score) { this.score = score; }
        public int getPassedCases() { return passedCases; }
        public void setPassedCases(int passedCases) { this.passedCases = passedCases; }
        public int getTotalCases() { return totalCases; }
        public void setTotalCases(int totalCases) { this.totalCases = totalCases; }
        public String getOutputText() { return outputText; }
        public void setOutputText(String outputText) { this.outputText = outputText; }
        public String getErrorText() { return errorText; }
        public void setErrorText(String errorText) { this.errorText = errorText; }
        public long getDurationMs() { return durationMs; }
        public void setDurationMs(long durationMs) { this.durationMs = durationMs; }
        public String getCreatedAt() { return createdAt; }
        public void setCreatedAt(String createdAt) { this.createdAt = createdAt; }
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class ProjectResource {
        private String id;
        private String resourceType;
        private String fileName;
        private String language;
        private String rawContent;
        private String structuredContent;
        private String createdAt;

        public String getId() {
            return id;
        }

        public void setId(String id) {
            this.id = id;
        }

        public String getResourceType() {
            return resourceType;
        }

        public void setResourceType(String resourceType) {
            this.resourceType = resourceType;
        }

        public String getFileName() {
            return fileName;
        }

        public void setFileName(String fileName) {
            this.fileName = fileName;
        }

        public String getLanguage() {
            return language;
        }

        public void setLanguage(String language) {
            this.language = language;
        }

        public String getRawContent() {
            return rawContent;
        }

        public void setRawContent(String rawContent) {
            this.rawContent = rawContent;
        }

        public String getStructuredContent() {
            return structuredContent;
        }

        public void setStructuredContent(String structuredContent) {
            this.structuredContent = structuredContent;
        }

        public String getCreatedAt() {
            return createdAt;
        }

        public void setCreatedAt(String createdAt) {
            this.createdAt = createdAt;
        }
    }

    public static class ProjectException extends RuntimeException {
        public ProjectException(String message) {
            super(message);
        }
    }
}
