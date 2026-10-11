package com.contest;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import javax.annotation.PostConstruct;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.security.SecureRandom;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.locks.ReentrantReadWriteLock;
import java.util.stream.Collectors;

/**
 * 班级中心：一师多班、绑定课程模型、布置/提交作业。
 * 文件存储，便于本地与演示环境即开即用。
 */
@Service
public class ClassRoomService {

    private static final Logger log = LoggerFactory.getLogger(ClassRoomService.class);
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final TypeReference<StoreRoot> ROOT_TYPE = new TypeReference<StoreRoot>() {};
    private static final SecureRandom RANDOM = new SecureRandom();

    private final ObjectMapper mapper = new ObjectMapper()
            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);
    private final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();
    /** 入班邮箱验证码：key = inviteCode|email */
    private final Map<String, JoinCode> joinCodes = new ConcurrentHashMap<>();

    @Value("${classroom.store-file:data/classrooms.json}")
    private String storeFile;

    @Value("${classroom.upload-dir:data/homework-uploads}")
    private String uploadDir;

    private Path storePath;
    private Path uploadRoot;
    private StoreRoot root = new StoreRoot();

    @PostConstruct
    public void init() throws Exception {
        storePath = Paths.get(storeFile).toAbsolutePath().normalize();
        uploadRoot = Paths.get(uploadDir).toAbsolutePath().normalize();
        Files.createDirectories(storePath.getParent() != null ? storePath.getParent() : Paths.get("."));
        Files.createDirectories(uploadRoot);
        load();
    }

    public List<ClassRoom> listByTeacher(String teacherUsername) {
        String teacher = norm(teacherUsername);
        lock.readLock().lock();
        try {
            return root.classes.stream()
                    .filter(c -> teacher.equals(norm(c.teacherUsername))
                            || (c.assistantUsernames != null && c.assistantUsernames.contains(teacher)))
                    .sorted((a, b) -> String.valueOf(b.updatedAt).compareTo(String.valueOf(a.updatedAt)))
                    .collect(Collectors.toList());
        } finally {
            lock.readLock().unlock();
        }
    }

    public List<ClassRoom> listByStudent(String studentUsername) {
        String student = norm(studentUsername);
        lock.readLock().lock();
        try {
            return root.classes.stream()
                    .filter(c -> c.memberUsernames != null && c.memberUsernames.contains(student))
                    .sorted((a, b) -> String.valueOf(b.updatedAt).compareTo(String.valueOf(a.updatedAt)))
                    .collect(Collectors.toList());
        } finally {
            lock.readLock().unlock();
        }
    }

    public ClassRoom createClass(String teacherUsername, String name, String subject, String description) {
        requireUser(teacherUsername);
        String title = requireText(name, "班级名称不能为空");
        lock.writeLock().lock();
        try {
            ClassRoom room = new ClassRoom();
            room.id = "cls_" + uuid();
            room.name = title;
            room.subject = trim(subject);
            room.description = trim(description);
            room.teacherUsername = trim(teacherUsername);
            room.inviteCode = newInviteCode();
            room.memberUsernames = new ArrayList<>();
            room.assistantUsernames = new ArrayList<>();
            room.projectIds = new ArrayList<>();
            room.publishedProjectIds = new ArrayList<>();
            room.createdAt = now();
            room.updatedAt = room.createdAt;
            root.classes.add(room);
            persist();
            return copy(room);
        } finally {
            lock.writeLock().unlock();
        }
    }

    public ClassRoom getForTeacher(String teacherUsername, String classId) {
        lock.readLock().lock();
        try {
            return copy(requireOwned(teacherUsername, classId));
        } finally {
            lock.readLock().unlock();
        }
    }

    public ClassRoom getForMember(String username, String classId) {
        lock.readLock().lock();
        try {
            return copy(requireMemberOrStaff(username, classId));
        } finally {
            lock.readLock().unlock();
        }
    }

    public ClassRoom updateClass(String teacherUsername, String classId, String name, String subject, String description) {
        lock.writeLock().lock();
        try {
            ClassRoom room = requireOwned(teacherUsername, classId);
            if (name != null && !name.trim().isEmpty()) {
                room.name = name.trim();
            }
            if (subject != null) {
                room.subject = subject.trim();
            }
            if (description != null) {
                room.description = description.trim();
            }
            room.updatedAt = now();
            persist();
            return copy(room);
        } finally {
            lock.writeLock().unlock();
        }
    }

    public void deleteClass(String teacherUsername, String classId) {
        lock.writeLock().lock();
        try {
            ClassRoom room = requireOwned(teacherUsername, classId);
            root.classes.removeIf(c -> room.id.equals(c.id));
            root.homeworks.removeIf(h -> room.id.equals(h.classId));
            root.submissions.removeIf(s -> room.id.equals(s.classId));
            if (root.materials != null) {
                root.materials.removeIf(m -> room.id.equals(m.classId));
            }
            if (root.chatMessages != null) {
                root.chatMessages.removeIf(m -> room.id.equals(m.classId));
            }
            persist();
        } finally {
            lock.writeLock().unlock();
        }
    }

    public ClassRoom regenerateInviteCode(String teacherUsername, String classId) {
        lock.writeLock().lock();
        try {
            ClassRoom room = requireOwned(teacherUsername, classId);
            room.inviteCode = newInviteCode();
            room.updatedAt = now();
            persist();
            return copy(room);
        } finally {
            lock.writeLock().unlock();
        }
    }

    public Map<String, Object> issueJoinEmailCode(String inviteCode, String email) {
        String code = requireText(inviteCode, "请输入班级邀请码").toUpperCase(Locale.ROOT);
        String mail = requireText(email, "请输入邮箱").toLowerCase(Locale.ROOT);
        if (!mail.matches("^[\\w.+-]+@[\\w.-]+\\.[A-Za-z]{2,}$")) {
            throw new ClassRoomException("邮箱格式不正确");
        }
        lock.readLock().lock();
        try {
            boolean ok = root.classes.stream().anyMatch(c -> code.equalsIgnoreCase(trim(c.inviteCode)));
            if (!ok) {
                throw new ClassRoomException("邀请码无效或班级不存在");
            }
        } finally {
            lock.readLock().unlock();
        }
        String otp = String.format("%06d", RANDOM.nextInt(1_000_000));
        JoinCode jc = new JoinCode();
        jc.code = otp;
        jc.expiresAt = System.currentTimeMillis() + 10 * 60 * 1000L;
        joinCodes.put(code + "|" + mail, jc);
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("email", mail);
        data.put("expiresInSec", 600);
        // 本地演示：无独立邮件通道时回传验证码，便于联调
        data.put("hint", "验证码已生成，请向班级老师索取");
        data.put("hint", "验证码已生成（演示环境直接显示，正式环境将发送到邮箱）");
        return data;
    }

    public ClassRoom joinByInviteCode(String studentUsername, String inviteCode, String email, String emailCode) {
        String student = requireUser(studentUsername);
        String code = requireText(inviteCode, "请输入班级邀请码").toUpperCase(Locale.ROOT);
        String mail = requireText(email, "请输入邮箱以完成验证").toLowerCase(Locale.ROOT);
        String otp = requireText(emailCode, "请输入邮箱验证码");
        if (!mail.matches("^[\\w.+-]+@[\\w.-]+\\.[A-Za-z]{2,}$")) {
            throw new ClassRoomException("邮箱格式不正确");
        }
        {
            JoinCode jc = joinCodes.get(code + "|" + mail);
            if (jc == null || jc.expiresAt < System.currentTimeMillis() || !otp.equals(jc.code)) {
                throw new ClassRoomException("邮箱验证码错误或已过期，请重新获取");
            }
            joinCodes.remove(code + "|" + mail);
        }
        lock.writeLock().lock();
        try {
            ClassRoom room = root.classes.stream()
                    .filter(c -> code.equalsIgnoreCase(trim(c.inviteCode)))
                    .findFirst()
                    .orElseThrow(() -> new ClassRoomException("邀请码无效或班级不存在"));
            if (student.equals(norm(room.teacherUsername))) {
                throw new ClassRoomException("教师无需加入自己的班级");
            }
            if (room.memberUsernames == null) {
                room.memberUsernames = new ArrayList<>();
            }
            if (!room.memberUsernames.contains(student)) {
                room.memberUsernames.add(student);
                room.updatedAt = now();
                persist();
            }
            return copy(room);
        } finally {
            lock.writeLock().unlock();
        }
    }

    public static class JoinCode {
        public String code;
        public long expiresAt;
    }

    public ClassRoom bindProject(String teacherUsername, String classId, String projectId) {
        String pid = requireText(projectId, "请选择课程模型");
        lock.writeLock().lock();
        try {
            ClassRoom room = requireStaff(teacherUsername, classId);
            if (room.projectIds == null) {
                room.projectIds = new ArrayList<>();
            }
            if (!room.projectIds.contains(pid)) {
                room.projectIds.add(pid);
                room.updatedAt = now();
                persist();
            }
            return copy(room);
        } finally {
            lock.writeLock().unlock();
        }
    }

    public ClassRoom unbindProject(String teacherUsername, String classId, String projectId) {
        lock.writeLock().lock();
        try {
            ClassRoom room = requireStaff(teacherUsername, classId);
            if (room.projectIds != null) {
                room.projectIds.removeIf(id -> id.equals(projectId));
                room.updatedAt = now();
                persist();
            }
            return copy(room);
        } finally {
            lock.writeLock().unlock();
        }
    }

    /**
     * Remove bound/published project IDs that no longer resolve for the teacher.
     * Keeps class showcase and publish counts free of stale placeholders.
     */
    /** 删除项目后，遍历该教师全部班级，清理指向已不存在项目的绑定与发布引用。 */
    public void pruneMissingProjectsForTeacher(String teacherUsername, java.util.function.Predicate<String> alive) {
        lock.writeLock().lock();
        try {
            boolean changed = false;
            for (ClassRoom room : root.classes) {
                if (!teacherUsername.equals(room.teacherUsername)) continue;
                if (room.projectIds != null) {
                    int before = room.projectIds.size();
                    room.projectIds.removeIf(id -> id == null || id.isBlank() || !alive.test(id));
                    changed = changed || room.projectIds.size() != before;
                }
                if (room.publishedProjectIds != null) {
                    int before = room.publishedProjectIds.size();
                    room.publishedProjectIds.removeIf(id -> id == null || id.isBlank() || !alive.test(id));
                    changed = changed || room.publishedProjectIds.size() != before;
                }
            }
            if (changed) persist();
        } finally {
            lock.writeLock().unlock();
        }
    }

    public ClassRoom pruneMissingProjects(String teacherUsername, String classId, java.util.function.Predicate<String> alive) {
        lock.writeLock().lock();
        try {
            ClassRoom room = requireStaff(teacherUsername, classId);
            boolean changed = false;
            if (room.projectIds != null) {
                int before = room.projectIds.size();
                room.projectIds.removeIf(id -> id == null || id.isBlank() || alive == null || !alive.test(id));
                changed = changed || room.projectIds.size() != before;
            }
            if (room.publishedProjectIds != null) {
                int before = room.publishedProjectIds.size();
                room.publishedProjectIds.removeIf(id -> id == null || id.isBlank() || alive == null || !alive.test(id));
                changed = changed || room.publishedProjectIds.size() != before;
            }
            if (changed) {
                room.updatedAt = now();
                persist();
            }
            return copy(room);
        } finally {
            lock.writeLock().unlock();
        }
    }

    public Homework createHomework(
            String teacherUsername,
            String classId,
            String title,
            String content,
            String dueAt,
            boolean allowText,
            boolean allowFile,
            boolean allowImage,
            String projectId
    ) {
        try {
            return createHomework(teacherUsername, classId, title, content, dueAt,
                    allowText, allowFile, allowImage, projectId, null);
        } catch (ClassRoomException e) {
            throw e;
        } catch (Exception e) {
            throw new ClassRoomException("布置作业失败：" + e.getMessage());
        }
    }

    public Homework createHomework(
            String teacherUsername,
            String classId,
            String title,
            String content,
            String dueAt,
            boolean allowText,
            boolean allowFile,
            boolean allowImage,
            String projectId,
            List<MultipartFile> files
    ) throws Exception {
        String hwTitle = requireText(title, "作业标题不能为空");
        if (!allowText && !allowFile && !allowImage) {
            allowText = true;
        }
        lock.writeLock().lock();
        try {
            ClassRoom room = requireStaff(teacherUsername, classId);
            Homework hw = new Homework();
            hw.id = "hw_" + uuid();
            hw.classId = room.id;
            hw.teacherUsername = norm(teacherUsername);
            hw.title = hwTitle;
            hw.content = trim(content);
            hw.dueAt = trim(dueAt);
            hw.allowText = allowText;
            hw.allowFile = allowFile;
            hw.allowImage = allowImage;
            hw.projectId = trim(projectId);
            hw.attachments = new ArrayList<>();
            hw.createdAt = now();
            hw.updatedAt = hw.createdAt;
            List<MultipartFile> safeFiles = files == null ? Collections.emptyList() : files.stream()
                    .filter(f -> f != null && !f.isEmpty())
                    .collect(Collectors.toList());
            if (!safeFiles.isEmpty()) {
                Path dir = uploadRoot.resolve("hw_" + hw.id);
                Files.createDirectories(dir);
                for (MultipartFile file : safeFiles) {
                    hw.attachments.add(storeAttachment(dir, "hw_" + hw.id, file));
                }
            }
            root.homeworks.add(hw);
            room.updatedAt = now();
            persist();
            return copy(hw);
        } finally {
            lock.writeLock().unlock();
        }
    }

    public ClassMaterial uploadMaterial(
            String teacherUsername,
            String classId,
            String title,
            String description,
            MultipartFile file
    ) throws Exception {
        if (file == null || file.isEmpty()) {
            throw new ClassRoomException("请选择要上传的资料文件");
        }
        lock.writeLock().lock();
        try {
            ClassRoom room = requireStaff(teacherUsername, classId);
            if (root.materials == null) {
                root.materials = new ArrayList<>();
            }
            ClassMaterial mat = new ClassMaterial();
            mat.id = "mat_" + uuid();
            mat.classId = room.id;
            mat.title = trim(title).isEmpty() ? sanitizeFileName(
                    file.getOriginalFilename() == null ? "资料" : file.getOriginalFilename()) : trim(title);
            mat.description = trim(description);
            mat.uploaderUsername = norm(teacherUsername);
            mat.createdAt = now();
            Path dir = uploadRoot.resolve("mat_" + mat.id);
            Files.createDirectories(dir);
            mat.attachment = storeAttachment(dir, "mat_" + mat.id, file);
            root.materials.add(mat);
            room.updatedAt = now();
            persist();
            return copy(mat);
        } finally {
            lock.writeLock().unlock();
        }
    }

    public List<ClassMaterial> listMaterials(String username, String classId) {
        lock.readLock().lock();
        try {
            requireMemberOrStaff(username, classId);
            if (root.materials == null) {
                return Collections.emptyList();
            }
            return root.materials.stream()
                    .filter(m -> classId.equals(m.classId))
                    .sorted((a, b) -> String.valueOf(b.createdAt).compareTo(String.valueOf(a.createdAt)))
                    .map(this::copy)
                    .collect(Collectors.toList());
        } finally {
            lock.readLock().unlock();
        }
    }

    public void deleteMaterial(String teacherUsername, String classId, String materialId) {
        lock.writeLock().lock();
        try {
            requireStaff(teacherUsername, classId);
            if (root.materials == null) {
                throw new ClassRoomException("资料不存在");
            }
            boolean removed = root.materials.removeIf(m -> materialId.equals(m.id) && classId.equals(m.classId));
            if (!removed) {
                throw new ClassRoomException("资料不存在");
            }
            persist();
        } finally {
            lock.writeLock().unlock();
        }
    }

    public ClassChatMessage postChat(String username, String classId, String content) {
        String text = requireText(content, "消息不能为空");
        if (text.length() > 2000) {
            throw new ClassRoomException("消息过长（最多 2000 字）");
        }
        lock.writeLock().lock();
        try {
            requireMemberOrStaff(username, classId);
            if (root.chatMessages == null) {
                root.chatMessages = new ArrayList<>();
            }
            ClassChatMessage msg = new ClassChatMessage();
            msg.id = "chat_" + uuid();
            msg.classId = classId;
            msg.username = norm(username);
            msg.content = text;
            msg.createdAt = now();
            root.chatMessages.add(msg);
            // 控制单班消息上限
            List<ClassChatMessage> mine = root.chatMessages.stream()
                    .filter(m -> classId.equals(m.classId))
                    .collect(Collectors.toList());
            if (mine.size() > 300) {
                Set<String> drop = mine.subList(0, mine.size() - 300).stream()
                        .map(m -> m.id).collect(Collectors.toSet());
                root.chatMessages.removeIf(m -> drop.contains(m.id));
            }
            persist();
            return copy(msg);
        } finally {
            lock.writeLock().unlock();
        }
    }

    public List<ClassChatMessage> listChat(String username, String classId, int limit) {
        lock.readLock().lock();
        try {
            requireMemberOrStaff(username, classId);
            if (root.chatMessages == null) {
                return Collections.emptyList();
            }
            int n = limit <= 0 ? 80 : Math.min(limit, 200);
            List<ClassChatMessage> list = root.chatMessages.stream()
                    .filter(m -> classId.equals(m.classId))
                    .sorted((a, b) -> String.valueOf(a.createdAt).compareTo(String.valueOf(b.createdAt)))
                    .map(this::copy)
                    .collect(Collectors.toList());
            if (list.size() <= n) {
                return list;
            }
            return list.subList(list.size() - n, list.size());
        } finally {
            lock.readLock().unlock();
        }
    }

    public List<Homework> listHomeworksForClass(String username, String classId, boolean teacherView) {
        lock.readLock().lock();
        try {
            ClassRoom room = requireClass(classId);
            String user = norm(username);
            boolean ok = teacherView
                    ? user.equals(norm(room.teacherUsername))
                    : user.equals(norm(room.teacherUsername))
                    || (room.memberUsernames != null && room.memberUsernames.contains(user));
            if (!ok) {
                throw new ClassRoomException("无权查看该班作业");
            }
            return root.homeworks.stream()
                    .filter(h -> classId.equals(h.classId))
                    .sorted((a, b) -> String.valueOf(b.createdAt).compareTo(String.valueOf(a.createdAt)))
                    .map(this::copy)
                    .collect(Collectors.toList());
        } finally {
            lock.readLock().unlock();
        }
    }

    public List<HomeworkView> listStudentHomeworkViews(String studentUsername) {
        String student = norm(studentUsername);
        lock.readLock().lock();
        try {
            LinkedHashSet<String> classIds = root.classes.stream()
                    .filter(c -> c.memberUsernames != null && c.memberUsernames.contains(student))
                    .map(c -> c.id)
                    .collect(Collectors.toCollection(LinkedHashSet::new));
            List<HomeworkView> views = new ArrayList<>();
            for (Homework hw : root.homeworks) {
                if (!classIds.contains(hw.classId)) {
                    continue;
                }
                ClassRoom room = root.classes.stream().filter(c -> c.id.equals(hw.classId)).findFirst().orElse(null);
                Submission sub = root.submissions.stream()
                        .filter(s -> hw.id.equals(s.homeworkId) && student.equals(norm(s.studentUsername)))
                        .max((a, b) -> String.valueOf(a.submittedAt).compareTo(String.valueOf(b.submittedAt)))
                        .orElse(null);
                HomeworkView view = new HomeworkView();
                view.homework = copy(hw);
                view.className = room == null ? "" : room.name;
                view.classId = hw.classId;
                view.submitted = sub != null;
                view.submission = sub == null ? null : copy(sub);
                views.add(view);
            }
            views.sort((a, b) -> String.valueOf(b.homework.createdAt).compareTo(String.valueOf(a.homework.createdAt)));
            return views;
        } finally {
            lock.readLock().unlock();
        }
    }

    public Homework getHomework(String homeworkId) {
        lock.readLock().lock();
        try {
            return copy(requireHomework(homeworkId));
        } finally {
            lock.readLock().unlock();
        }
    }

    public List<Submission> listSubmissions(String teacherUsername, String classId, String homeworkId) {
        lock.readLock().lock();
        try {
            requireStaff(teacherUsername, classId);
            Homework hw = requireHomework(homeworkId);
            if (!classId.equals(hw.classId)) {
                throw new ClassRoomException("作业不属于该班级");
            }
            return root.submissions.stream()
                    .filter(s -> homeworkId.equals(s.homeworkId))
                    .sorted((a, b) -> String.valueOf(b.submittedAt).compareTo(String.valueOf(a.submittedAt)))
                    .map(this::copy)
                    .collect(Collectors.toList());
        } finally {
            lock.readLock().unlock();
        }
    }

    public Submission submitHomework(
            String studentUsername,
            String homeworkId,
            String textContent,
            List<MultipartFile> files
    ) throws Exception {
        String student = requireUser(studentUsername);
        lock.writeLock().lock();
        try {
            Homework hw = requireHomework(homeworkId);
            ClassRoom room = requireClass(hw.classId);
            if (room.memberUsernames == null || !room.memberUsernames.contains(student)) {
                throw new ClassRoomException("请先加入该班级再提交作业");
            }

            String text = textContent == null ? "" : textContent.trim();
            List<MultipartFile> safeFiles = files == null ? Collections.emptyList() : files.stream()
                    .filter(f -> f != null && !f.isEmpty())
                    .collect(Collectors.toList());

            if (!hw.allowText && !text.isEmpty()) {
                throw new ClassRoomException("本作业不接受文字作答");
            }
            if (!hw.allowFile && !hw.allowImage && !safeFiles.isEmpty()) {
                throw new ClassRoomException("本作业不接受附件");
            }
            Submission existing = root.submissions.stream()
                    .filter(s -> homeworkId.equals(s.homeworkId) && student.equals(norm(s.studentUsername)))
                    .findFirst()
                    .orElse(null);
            boolean hasPrevFiles = existing != null && existing.attachments != null && !existing.attachments.isEmpty();
            boolean hasPrevText = existing != null && existing.textContent != null && !existing.textContent.isBlank();
            if (text.isEmpty() && safeFiles.isEmpty() && !hasPrevFiles && !hasPrevText) {
                throw new ClassRoomException("请填写文字或上传附件");
            }
            if (text.isEmpty() && safeFiles.isEmpty()) {
                throw new ClassRoomException("请修改文字或上传新文件后再补交");
            }

            Submission sub = existing == null ? new Submission() : existing;
            if (existing == null) {
                sub.id = "sub_" + uuid();
                sub.homeworkId = hw.id;
                sub.classId = hw.classId;
                sub.studentUsername = student;
                sub.createdAt = now();
                root.submissions.add(sub);
            }
            if (hw.allowText) {
                // 补交仅上传文件时保留原文字；显式提交的文字（含清空为空白）以本次为准
                if (!text.isEmpty() || existing == null || safeFiles.isEmpty()) {
                    sub.textContent = text;
                }
            } else {
                sub.textContent = "";
            }
            sub.submittedAt = now();
            sub.status = "submitted";
            if (sub.attachments == null) {
                sub.attachments = new ArrayList<>();
            }

            Path dir = uploadRoot.resolve(sub.id);
            Files.createDirectories(dir);
            for (MultipartFile file : safeFiles) {
                String original = file.getOriginalFilename() == null ? "file" : file.getOriginalFilename();
                checkAttachmentExtension(original);
                String lower = original.toLowerCase(Locale.ROOT);
                boolean image = lower.matches(".*\\.(png|jpg|jpeg|gif|webp|bmp)$");
                if (image && !hw.allowImage) {
                    throw new ClassRoomException("本作业不接受图片附件：" + original);
                }
                if (!image && !hw.allowFile) {
                    throw new ClassRoomException("本作业不接受文件附件：" + original);
                }
                String safeName = sanitizeFileName(original);
                String stored = System.currentTimeMillis() + "_" + safeName;
                Path target = dir.resolve(stored).normalize();
                if (!target.startsWith(dir)) {
                    throw new ClassRoomException("非法文件名");
                }
                file.transferTo(target.toFile());
                Attachment att = new Attachment();
                att.id = "att_" + uuid();
                att.name = safeName;
                att.contentType = file.getContentType() == null ? "application/octet-stream" : file.getContentType();
                att.size = Files.size(target);
                att.relativePath = sub.id + "/" + stored;
                att.kind = image ? "image" : "file";
                sub.attachments.add(att);
            }
            persist();
            return copy(sub);
        } finally {
            lock.writeLock().unlock();
        }
    }

    public Path resolveAttachmentFile(String relativePath) {
        if (relativePath == null || relativePath.trim().isEmpty()) {
            throw new ClassRoomException("附件不存在");
        }
        Path file = uploadRoot.resolve(relativePath.trim()).normalize();
        if (!file.startsWith(uploadRoot) || !Files.isRegularFile(file)) {
            throw new ClassRoomException("附件不存在");
        }
        return file;
    }

    /** 附件及其归属上下文，用于下载时的班级归属校验。 */
    public static class AttachmentContext {
        public Attachment attachment;
        public String classId;
        public String ownerUsername;
        public String kind; // submission | homework | material
    }

    /** 判断用户能否访问该附件：管理员/任课教师/助教可看全部；学生仅本班，且作业提交附件仅本人。 */
    public boolean canAccessAttachment(AttachmentContext ctx, String username, boolean isAdmin) {
        if (ctx == null || ctx.attachment == null) {
            return false;
        }
        if (isAdmin || ctx.classId == null) {
            return isAdmin;
        }
        for (ClassRoom c : root.classes) {
            if (!ctx.classId.equals(c.id)) {
                continue;
            }
            boolean isTeacher = username != null && username.equals(c.teacherUsername);
            boolean isAssistant = username != null && c.assistantUsernames != null && c.assistantUsernames.contains(username);
            boolean isMember = username != null && c.memberUsernames != null && c.memberUsernames.contains(username);
            if (isTeacher || isAssistant) {
                return true;
            }
            if (!isMember) {
                return false;
            }
            if ("submission".equals(ctx.kind)) {
                return username.equals(ctx.ownerUsername);
            }
            return true;
        }
        return false;
    }

    public AttachmentContext findAttachmentContext(String attachmentId) {
        lock.readLock().lock();
        try {
            for (Submission sub : root.submissions) {
                if (sub.attachments == null) {
                    continue;
                }
                for (Attachment att : sub.attachments) {
                    if (attachmentId.equals(att.id)) {
                        AttachmentContext ctx = new AttachmentContext();
                        ctx.attachment = copy(att);
                        ctx.classId = sub.classId;
                        ctx.ownerUsername = sub.studentUsername;
                        ctx.kind = "submission";
                        return ctx;
                    }
                }
            }
            for (Homework hw : root.homeworks) {
                if (hw.attachments == null) {
                    continue;
                }
                for (Attachment att : hw.attachments) {
                    if (attachmentId.equals(att.id)) {
                        AttachmentContext ctx = new AttachmentContext();
                        ctx.attachment = copy(att);
                        ctx.classId = hw.classId;
                        ctx.ownerUsername = hw.teacherUsername;
                        ctx.kind = "homework";
                        return ctx;
                    }
                }
            }
            if (root.materials != null) {
                for (ClassMaterial mat : root.materials) {
                    if (mat.attachment != null && attachmentId.equals(mat.attachment.id)) {
                        AttachmentContext ctx = new AttachmentContext();
                        ctx.attachment = copy(mat.attachment);
                        ctx.classId = mat.classId;
                        ctx.ownerUsername = mat.uploaderUsername;
                        ctx.kind = "material";
                        return ctx;
                    }
                }
            }
            return null;
        } finally {
            lock.readLock().unlock();
        }
    }

    public Attachment findAttachment(String attachmentId) {
        AttachmentContext ctx = findAttachmentContext(attachmentId);
        if (ctx == null) {
            throw new ClassRoomException("附件不存在");
        }
        return ctx.attachment;
    }

    public Submission gradeSubmission(
            String operator,
            String classId,
            String submissionId,
            Double score,
            String feedback,
            Boolean featured
    ) {
        lock.writeLock().lock();
        try {
            requireStaff(operator, classId);
            Submission sub = root.submissions.stream()
                    .filter(s -> submissionId.equals(s.id) && classId.equals(s.classId))
                    .findFirst()
                    .orElseThrow(() -> new ClassRoomException("提交不存在"));
            if (score != null) {
                double v = Math.max(0, Math.min(100, score));
                sub.score = v;
            }
            if (feedback != null) {
                sub.feedback = feedback.trim();
            }
            if (featured != null) {
                sub.featured = featured;
            }
            sub.status = "graded";
            sub.gradedAt = now();
            sub.gradedBy = norm(operator);
            persist();
            return copy(sub);
        } finally {
            lock.writeLock().unlock();
        }
    }

    public List<Submission> listFeatured(String classId) {
        lock.readLock().lock();
        try {
            requireClass(classId);
            return root.submissions.stream()
                    .filter(s -> classId.equals(s.classId) && s.featured)
                    .sorted((a, b) -> String.valueOf(b.gradedAt == null ? b.submittedAt : b.gradedAt)
                            .compareTo(String.valueOf(a.gradedAt == null ? a.submittedAt : a.gradedAt)))
                    .map(this::copy)
                    .collect(Collectors.toList());
        } finally {
            lock.readLock().unlock();
        }
    }

    public ClassRoom publishProjectToClass(String operator, String classId, String projectId) {
        String pid = requireText(projectId, "请选择课程模型");
        lock.writeLock().lock();
        try {
            ClassRoom room = requireStaff(operator, classId);
            if (room.publishedProjectIds == null) {
                room.publishedProjectIds = new ArrayList<>();
            }
            if (!room.publishedProjectIds.contains(pid)) {
                room.publishedProjectIds.add(pid);
            }
            if (room.projectIds == null) {
                room.projectIds = new ArrayList<>();
            }
            if (!room.projectIds.contains(pid)) {
                room.projectIds.add(pid);
            }
            room.updatedAt = now();
            persist();
            return copy(room);
        } finally {
            lock.writeLock().unlock();
        }
    }

    public ClassRoom unpublishProjectFromClass(String operator, String classId, String projectId) {
        lock.writeLock().lock();
        try {
            ClassRoom room = requireStaff(operator, classId);
            if (room.publishedProjectIds != null) {
                room.publishedProjectIds.removeIf(id -> id.equals(projectId));
                room.updatedAt = now();
                persist();
            }
            return copy(room);
        } finally {
            lock.writeLock().unlock();
        }
    }

    public boolean isClassOnlyPublished(String projectId) {
        if (projectId == null || projectId.trim().isEmpty()) {
            return false;
        }
        lock.readLock().lock();
        try {
            return root.classes.stream().anyMatch(c ->
                    c.publishedProjectIds != null && c.publishedProjectIds.contains(projectId));
        } finally {
            lock.readLock().unlock();
        }
    }

    public List<String> listClassOnlyProjectIdsForStudent(String studentUsername) {
        String student = norm(studentUsername);
        lock.readLock().lock();
        try {
            LinkedHashSet<String> ids = new LinkedHashSet<>();
            for (ClassRoom c : root.classes) {
                boolean inClass = student.equals(norm(c.teacherUsername))
                        || (c.memberUsernames != null && c.memberUsernames.contains(student))
                        || (c.assistantUsernames != null && c.assistantUsernames.contains(student));
                if (!inClass || c.publishedProjectIds == null) {
                    continue;
                }
                ids.addAll(c.publishedProjectIds);
            }
            return new ArrayList<>(ids);
        } finally {
            lock.readLock().unlock();
        }
    }

    public Announcement createAnnouncement(String operator, String classId, String title, String content) {
        lock.writeLock().lock();
        try {
            requireStaff(operator, classId);
            Announcement a = new Announcement();
            a.id = "ann_" + uuid();
            a.classId = classId;
            a.title = requireText(title, "公告标题不能为空");
            a.content = trim(content);
            a.authorUsername = norm(operator);
            a.createdAt = now();
            root.announcements.add(a);
            persist();
            return copy(a);
        } finally {
            lock.writeLock().unlock();
        }
    }

    public List<Announcement> listAnnouncements(String username, String classId) {
        lock.readLock().lock();
        try {
            requireMemberOrStaff(username, classId);
            return root.announcements.stream()
                    .filter(a -> classId.equals(a.classId))
                    .sorted((x, y) -> String.valueOf(y.createdAt).compareTo(String.valueOf(x.createdAt)))
                    .map(this::copy)
                    .collect(Collectors.toList());
        } finally {
            lock.readLock().unlock();
        }
    }

    public CheckinSession openCheckin(String operator, String classId, String title) {
        lock.writeLock().lock();
        try {
            requireStaff(operator, classId);
            // 关闭旧的进行中签到
            for (CheckinSession s : root.checkins) {
                if (classId.equals(s.classId) && "open".equals(s.status)) {
                    s.status = "closed";
                    s.closedAt = now();
                }
            }
            CheckinSession session = new CheckinSession();
            session.id = "ck_" + uuid();
            session.classId = classId;
            session.title = title == null || title.trim().isEmpty() ? ("签到 " + now()) : title.trim();
            session.status = "open";
            session.createdBy = norm(operator);
            session.createdAt = now();
            root.checkins.add(session);
            persist();
            return copy(session);
        } finally {
            lock.writeLock().unlock();
        }
    }

    public CheckinSession closeCheckin(String operator, String classId, String checkinId) {
        lock.writeLock().lock();
        try {
            requireStaff(operator, classId);
            CheckinSession session = requireCheckin(classId, checkinId);
            session.status = "closed";
            session.closedAt = now();
            persist();
            return copy(session);
        } finally {
            lock.writeLock().unlock();
        }
    }

    public List<CheckinSession> listCheckins(String username, String classId) {
        lock.readLock().lock();
        try {
            requireMemberOrStaff(username, classId);
            return root.checkins.stream()
                    .filter(c -> classId.equals(c.classId))
                    .sorted((a, b) -> String.valueOf(b.createdAt).compareTo(String.valueOf(a.createdAt)))
                    .map(this::copy)
                    .collect(Collectors.toList());
        } finally {
            lock.readLock().unlock();
        }
    }

    public CheckinRecord studentCheckin(String studentUsername, String classId, String checkinId) {
        String student = requireUser(studentUsername);
        lock.writeLock().lock();
        try {
            ClassRoom room = requireClass(classId);
            if (room.memberUsernames == null || !room.memberUsernames.contains(student)) {
                throw new ClassRoomException("仅本班学生可签到");
            }
            CheckinSession session = requireCheckin(classId, checkinId);
            if (!"open".equals(session.status)) {
                throw new ClassRoomException("签到已结束");
            }
            CheckinRecord existing = root.checkinRecords.stream()
                    .filter(r -> checkinId.equals(r.checkinId) && student.equals(norm(r.studentUsername)))
                    .findFirst()
                    .orElse(null);
            if (existing != null) {
                return copy(existing);
            }
            CheckinRecord record = new CheckinRecord();
            record.id = "cr_" + uuid();
            record.checkinId = checkinId;
            record.classId = classId;
            record.studentUsername = student;
            record.checkedAt = now();
            root.checkinRecords.add(record);
            persist();
            return copy(record);
        } finally {
            lock.writeLock().unlock();
        }
    }

    public List<CheckinRecord> listCheckinRecords(String operator, String classId, String checkinId) {
        lock.readLock().lock();
        try {
            requireStaff(operator, classId);
            requireCheckin(classId, checkinId);
            return root.checkinRecords.stream()
                    .filter(r -> checkinId.equals(r.checkinId))
                    .sorted((a, b) -> String.valueOf(b.checkedAt).compareTo(String.valueOf(a.checkedAt)))
                    .map(this::copy)
                    .collect(Collectors.toList());
        } finally {
            lock.readLock().unlock();
        }
    }

    public Map<String, Object> classAnalytics(String operator, String classId) {
        lock.readLock().lock();
        try {
            ClassRoom room = requireStaff(operator, classId);
            int members = room.memberUsernames == null ? 0 : room.memberUsernames.size();
            List<Homework> hws = root.homeworks.stream().filter(h -> classId.equals(h.classId)).collect(Collectors.toList());
            List<Submission> subs = root.submissions.stream().filter(s -> classId.equals(s.classId)).collect(Collectors.toList());
            long graded = subs.stream().filter(s -> s.score != null).count();
            double avg = subs.stream().filter(s -> s.score != null).mapToDouble(s -> s.score).average().orElse(0);
            long featured = subs.stream().filter(s -> s.featured).count();
            long openCheckins = root.checkins.stream().filter(c -> classId.equals(c.classId) && "open".equals(c.status)).count();
            long announcements = root.announcements.stream().filter(a -> classId.equals(a.classId)).count();
            Map<String, Object> data = new LinkedHashMap<>();
            data.put("memberCount", members);
            data.put("assistantCount", room.assistantUsernames == null ? 0 : room.assistantUsernames.size());
            data.put("homeworkCount", hws.size());
            data.put("submissionCount", subs.size());
            data.put("gradedCount", graded);
            data.put("averageScore", Math.round(avg * 10) / 10.0);
            data.put("featuredCount", featured);
            data.put("openCheckinCount", openCheckins);
            data.put("announcementCount", announcements);
            data.put("classPublishedCount", room.publishedProjectIds == null ? 0 : room.publishedProjectIds.size());
            data.put("boundProjectCount", room.projectIds == null ? 0 : room.projectIds.size());
            // 按学生聚合提交数
            Map<String, Long> byStudent = subs.stream()
                    .collect(Collectors.groupingBy(s -> s.studentUsername == null ? "" : s.studentUsername, Collectors.counting()));
            data.put("submissionByStudent", byStudent);
            return data;
        } finally {
            lock.readLock().unlock();
        }
    }

    /**
     * Teacher-facing per-student learning dossier for a class:
     * homework path, submissions/scores, check-ins, materials, chat activity, lesson IDs.
     */
    public Map<String, Object> studentLearningProfile(String operator, String classId, String studentUsername) {
        lock.readLock().lock();
        try {
            ClassRoom room = requireStaff(operator, classId);
            String student = norm(studentUsername);
            boolean isMember = room.memberUsernames != null
                    && room.memberUsernames.stream().anyMatch(u -> student.equals(norm(u)));
            if (!isMember) {
                throw new ClassRoomException("该学生不在本班");
            }

            List<Homework> hws = root.homeworks.stream()
                    .filter(h -> classId.equals(h.classId))
                    .sorted((a, b) -> String.valueOf(a.createdAt).compareTo(String.valueOf(b.createdAt)))
                    .collect(Collectors.toList());
            List<Submission> mySubs = root.submissions.stream()
                    .filter(s -> classId.equals(s.classId) && student.equals(norm(s.studentUsername)))
                    .sorted((a, b) -> String.valueOf(b.submittedAt).compareTo(String.valueOf(a.submittedAt)))
                    .collect(Collectors.toList());
            Map<String, Submission> latestByHw = new LinkedHashMap<>();
            for (Submission s : mySubs) {
                if (s.homeworkId != null && !latestByHw.containsKey(s.homeworkId)) {
                    latestByHw.put(s.homeworkId, s);
                }
            }

            List<Map<String, Object>> homeworkPath = new ArrayList<>();
            int submittedHw = 0;
            int gradedHw = 0;
            for (Homework hw : hws) {
                Submission sub = latestByHw.get(hw.id);
                Map<String, Object> row = new LinkedHashMap<>();
                row.put("homeworkId", hw.id);
                row.put("title", hw.title);
                row.put("content", hw.content);
                row.put("dueAt", hw.dueAt);
                row.put("createdAt", hw.createdAt);
                row.put("projectId", hw.projectId);
                row.put("attachmentCount", hw.attachments == null ? 0 : hw.attachments.size());
                if (sub == null) {
                    row.put("status", "未提交");
                    row.put("submitted", false);
                } else {
                    submittedHw++;
                    row.put("submitted", true);
                    row.put("status", submissionStatusLabel(sub));
                    row.put("submissionId", sub.id);
                    row.put("submittedAt", sub.submittedAt);
                    row.put("score", sub.score);
                    row.put("feedback", sub.feedback);
                    row.put("featured", sub.featured);
                    row.put("textPreview", sub.textContent == null ? ""
                            : (sub.textContent.length() > 120 ? sub.textContent.substring(0, 120) + "…" : sub.textContent));
                    row.put("fileCount", sub.attachments == null ? 0 : sub.attachments.size());
                    if (sub.score != null) {
                        gradedHw++;
                    }
                }
                homeworkPath.add(row);
            }

            List<CheckinSession> sessions = root.checkins.stream()
                    .filter(c -> classId.equals(c.classId))
                    .sorted((a, b) -> String.valueOf(b.createdAt).compareTo(String.valueOf(a.createdAt)))
                    .collect(Collectors.toList());
            Set<String> checkedIds = root.checkinRecords.stream()
                    .filter(r -> classId.equals(r.classId) && student.equals(norm(r.studentUsername)))
                    .map(r -> r.checkinId)
                    .collect(Collectors.toSet());
            Map<String, String> checkedAtById = new HashMap<>();
            for (CheckinRecord r : root.checkinRecords) {
                if (classId.equals(r.classId) && student.equals(norm(r.studentUsername))) {
                    checkedAtById.put(r.checkinId, r.checkedAt);
                }
            }
            List<Map<String, Object>> checkinPath = new ArrayList<>();
            int checkedCount = 0;
            for (CheckinSession s : sessions) {
                Map<String, Object> row = new LinkedHashMap<>();
                row.put("checkinId", s.id);
                row.put("title", s.title);
                row.put("sessionStatus", s.status);
                row.put("createdAt", s.createdAt);
                boolean ok = checkedIds.contains(s.id);
                row.put("checkedIn", ok);
                row.put("checkedAt", checkedAtById.get(s.id));
                if (ok) {
                    checkedCount++;
                }
                checkinPath.add(row);
            }

            List<Map<String, Object>> materials = root.materials == null ? new ArrayList<>()
                    : root.materials.stream()
                    .filter(m -> classId.equals(m.classId))
                    .sorted((a, b) -> String.valueOf(b.createdAt).compareTo(String.valueOf(a.createdAt)))
                    .map(m -> {
                        Map<String, Object> row = new LinkedHashMap<>();
                        row.put("id", m.id);
                        row.put("title", m.title);
                        row.put("description", m.description);
                        row.put("createdAt", m.createdAt);
                        row.put("uploaderUsername", m.uploaderUsername);
                        if (m.attachment != null) {
                            row.put("fileName", m.attachment.name);
                            row.put("fileSize", m.attachment.size);
                            row.put("contentType", m.attachment.contentType);
                            row.put("attachmentId", m.attachment.id);
                        }
                        return row;
                    })
                    .collect(Collectors.toList());

            List<Map<String, Object>> chat = root.chatMessages == null ? new ArrayList<>()
                    : root.chatMessages.stream()
                    .filter(m -> classId.equals(m.classId) && student.equals(norm(m.username)))
                    .sorted((a, b) -> String.valueOf(b.createdAt).compareTo(String.valueOf(a.createdAt)))
                    .limit(30)
                    .map(m -> {
                        Map<String, Object> row = new LinkedHashMap<>();
                        row.put("id", m.id);
                        row.put("content", m.content);
                        row.put("createdAt", m.createdAt);
                        return row;
                    })
                    .collect(Collectors.toList());
            long chatTotal = root.chatMessages == null ? 0
                    : root.chatMessages.stream()
                    .filter(m -> classId.equals(m.classId) && student.equals(norm(m.username)))
                    .count();

            double avgScore = mySubs.stream().filter(s -> s.score != null).mapToDouble(s -> s.score).average().orElse(0);
            long featuredCount = mySubs.stream().filter(s -> s.featured).count();
            String lastActive = "";
            for (Submission s : mySubs) {
                if (s.submittedAt != null && !s.submittedAt.isEmpty()) {
                    lastActive = s.submittedAt;
                    break;
                }
            }
            if (lastActive.isEmpty()) {
                for (Map<String, Object> c : checkinPath) {
                    if (Boolean.TRUE.equals(c.get("checkedIn")) && c.get("checkedAt") != null) {
                        lastActive = String.valueOf(c.get("checkedAt"));
                        break;
                    }
                }
            }

            int hwTotal = hws.size();
            int ckTotal = sessions.size();
            int completionRate = hwTotal == 0 ? 0 : (int) Math.round(submittedHw * 100.0 / hwTotal);
            int checkinRate = ckTotal == 0 ? 0 : (int) Math.round(checkedCount * 100.0 / ckTotal);
            // Simple effect score: completion 40% + avgScore 40% + checkin 20%
            double effect = completionRate * 0.4
                    + (avgScore) * 0.4
                    + checkinRate * 0.2;

            Map<String, Object> stats = new LinkedHashMap<>();
            stats.put("homeworkTotal", hwTotal);
            stats.put("homeworkSubmitted", submittedHw);
            stats.put("homeworkGraded", gradedHw);
            stats.put("homeworkCompletionRate", completionRate);
            stats.put("submissionCount", mySubs.size());
            stats.put("averageScore", Math.round(avgScore * 10) / 10.0);
            stats.put("featuredCount", featuredCount);
            stats.put("checkinTotal", ckTotal);
            stats.put("checkinCount", checkedCount);
            stats.put("checkinRate", checkinRate);
            stats.put("materialCount", materials.size());
            stats.put("chatMessageCount", chatTotal);
            stats.put("lessonCount", room.publishedProjectIds == null ? 0 : room.publishedProjectIds.size());
            stats.put("lastActiveAt", lastActive);
            stats.put("effectScore", Math.round(effect * 10) / 10.0);

            Map<String, Object> data = new LinkedHashMap<>();
            data.put("username", student);
            data.put("classId", classId);
            data.put("className", room.name);
            data.put("stats", stats);
            data.put("homeworkPath", homeworkPath);
            data.put("submissions", mySubs.stream().map(this::copy).collect(Collectors.toList()));
            data.put("checkinPath", checkinPath);
            data.put("materials", materials);
            data.put("chatMessages", chat);
            data.put("publishedProjectIds", room.publishedProjectIds == null
                    ? new ArrayList<String>() : new ArrayList<>(room.publishedProjectIds));
            data.put("boundProjectIds", room.projectIds == null
                    ? new ArrayList<String>() : new ArrayList<>(room.projectIds));
            return data;
        } finally {
            lock.readLock().unlock();
        }
    }

    public ClassRoom addAssistant(String owner, String classId, String assistantUsername) {
        String assistant = requireUser(assistantUsername);
        lock.writeLock().lock();
        try {
            ClassRoom room = requireOwned(owner, classId);
            if (assistant.equals(norm(room.teacherUsername))) {
                throw new ClassRoomException("教师本人无需设为助教");
            }
            if (room.assistantUsernames == null) {
                room.assistantUsernames = new ArrayList<>();
            }
            if (!room.assistantUsernames.contains(assistant)) {
                room.assistantUsernames.add(assistant);
                room.updatedAt = now();
                persist();
            }
            return copy(room);
        } finally {
            lock.writeLock().unlock();
        }
    }

    public ClassRoom removeAssistant(String owner, String classId, String assistantUsername) {
        lock.writeLock().lock();
        try {
            ClassRoom room = requireOwned(owner, classId);
            if (room.assistantUsernames != null) {
                room.assistantUsernames.removeIf(u -> u.equals(norm(assistantUsername)));
                room.updatedAt = now();
                persist();
            }
            return copy(room);
        } finally {
            lock.writeLock().unlock();
        }
    }

    public Map<String, Object> importMembers(String operator, String classId, String rawNames) {
        return importMemberNames(operator, classId, splitMemberNames(rawNames));
    }

    public Map<String, Object> importMembersFromFile(String operator, String classId, MultipartFile file) throws Exception {
        if (file == null || file.isEmpty()) {
            throw new ClassRoomException("请选择要导入的文件");
        }
        String original = file.getOriginalFilename() == null ? "" : file.getOriginalFilename().trim();
        checkAttachmentExtension(original);
        String lower = original.toLowerCase(Locale.ROOT);
        List<String> names;
        if (lower.endsWith(".xlsx") || lower.endsWith(".xls")) {
            names = readMemberNamesFromExcel(file);
        } else if (lower.endsWith(".csv") || lower.endsWith(".txt") || lower.endsWith(".tsv") || lower.isEmpty()) {
            names = splitMemberNames(readUploadText(file));
        } else {
            // Try text first; fall back to excel magic if needed.
            try {
                names = splitMemberNames(readUploadText(file));
            } catch (Exception textErr) {
                names = readMemberNamesFromExcel(file);
            }
        }
        if (names.isEmpty()) {
            throw new ClassRoomException("文件里没有识别到可用的学生账号（请放在首列，或每行一个）");
        }
        Map<String, Object> data = importMemberNames(operator, classId, names);
        data.put("fileName", original.isEmpty() ? "upload" : original);
        data.put("parsedCount", names.size());
        return data;
    }

    private Map<String, Object> importMemberNames(String operator, String classId, List<String> names) {
        lock.writeLock().lock();
        try {
            ClassRoom room = requireStaff(operator, classId);
            if (room.memberUsernames == null) {
                room.memberUsernames = new ArrayList<>();
            }
            int added = 0;
            int skipped = 0;
            List<String> imported = new ArrayList<>();
            for (String part : names) {
                String name = norm(part);
                if (name.isEmpty()) {
                    continue;
                }
                if (name.equals(norm(room.teacherUsername))) {
                    skipped++;
                    continue;
                }
                if (room.memberUsernames.contains(name)) {
                    skipped++;
                    continue;
                }
                room.memberUsernames.add(name);
                imported.add(name);
                added++;
            }
            if (added > 0) {
                room.updatedAt = now();
                persist();
            }
            Map<String, Object> data = new LinkedHashMap<>();
            data.put("added", added);
            data.put("skipped", skipped);
            data.put("imported", imported);
            data.put("class", copy(room));
            return data;
        } finally {
            lock.writeLock().unlock();
        }
    }

    private List<String> splitMemberNames(String rawNames) {
        String text = rawNames == null ? "" : rawNames;
        String[] parts = text.split("[\\s,;，；、\\n\\r\\t]+");
        List<String> names = new ArrayList<>();
        for (String part : parts) {
            String name = norm(part);
            if (!name.isEmpty() && !isMemberNameHeader(name)) {
                names.add(name);
            }
        }
        return names;
    }

    private boolean isMemberNameHeader(String name) {
        String n = name.toLowerCase(Locale.ROOT);
        return "username".equals(n) || "user".equals(n) || "account".equals(n)
                || "账号".equals(name) || "用户名".equals(name) || "学号".equals(name)
                || "姓名".equals(name) || "name".equals(n) || "student".equals(n)
                || "studentid".equals(n) || "学号/账号".equals(name);
    }

    private String readUploadText(MultipartFile file) throws Exception {
        byte[] bytes = file.getBytes();
        if (bytes.length >= 3 && (bytes[0] & 0xFF) == 0xEF && (bytes[1] & 0xFF) == 0xBB && (bytes[2] & 0xFF) == 0xBF) {
            return new String(bytes, 3, bytes.length - 3, java.nio.charset.StandardCharsets.UTF_8);
        }
        String utf8 = new String(bytes, java.nio.charset.StandardCharsets.UTF_8);
        if (utf8.contains("\uFFFD")) {
            return new String(bytes, java.nio.charset.Charset.forName("GBK"));
        }
        return utf8;
    }

    private List<String> readMemberNamesFromExcel(MultipartFile file) throws Exception {
        List<String> names = new ArrayList<>();
        try (java.io.InputStream in = file.getInputStream();
             org.apache.poi.ss.usermodel.Workbook workbook = org.apache.poi.ss.usermodel.WorkbookFactory.create(in)) {
            org.apache.poi.ss.usermodel.Sheet sheet = workbook.getNumberOfSheets() > 0 ? workbook.getSheetAt(0) : null;
            if (sheet == null) {
                return names;
            }
            org.apache.poi.ss.usermodel.DataFormatter formatter = new org.apache.poi.ss.usermodel.DataFormatter();
            int nameCol = 0;
            org.apache.poi.ss.usermodel.Row header = sheet.getRow(sheet.getFirstRowNum());
            if (header != null) {
                for (org.apache.poi.ss.usermodel.Cell cell : header) {
                    String v = norm(formatter.formatCellValue(cell));
                    if ("username".equalsIgnoreCase(v) || "账号".equals(v) || "用户名".equals(v)
                            || "学号".equals(v) || "account".equalsIgnoreCase(v)) {
                        nameCol = cell.getColumnIndex();
                        break;
                    }
                }
            }
            for (org.apache.poi.ss.usermodel.Row row : sheet) {
                if (row == null) {
                    continue;
                }
                org.apache.poi.ss.usermodel.Cell cell = row.getCell(nameCol);
                if (cell == null && nameCol != 0) {
                    cell = row.getCell(0);
                }
                if (cell == null) {
                    continue;
                }
                String name = norm(formatter.formatCellValue(cell));
                if (!name.isEmpty() && !isMemberNameHeader(name)) {
                    names.add(name);
                }
            }
        }
        return names;
    }

    private String submissionStatusLabel(Submission sub) {
        if (sub == null) {
            return "未提交";
        }
        if (sub.score != null || "graded".equalsIgnoreCase(String.valueOf(sub.status))) {
            return "已批改";
        }
        if (sub.featured) {
            return "已提交（优秀）";
        }
        return "已提交";
    }

    private ClassRoom requireOwned(String teacherUsername, String classId) {
        ClassRoom room = requireClass(classId);
        if (!norm(teacherUsername).equals(norm(room.teacherUsername))) {
            throw new ClassRoomException("仅班主任可执行该操作");
        }
        return room;
    }

    private ClassRoom requireStaff(String username, String classId) {
        ClassRoom room = requireClass(classId);
        String user = norm(username);
        boolean ok = user.equals(norm(room.teacherUsername))
                || (room.assistantUsernames != null && room.assistantUsernames.contains(user));
        if (!ok) {
            throw new ClassRoomException("仅教师或助教可操作");
        }
        return room;
    }

    private ClassRoom requireMemberOrStaff(String username, String classId) {
        ClassRoom room = requireClass(classId);
        String user = norm(username);
        boolean ok = user.equals(norm(room.teacherUsername))
                || (room.assistantUsernames != null && room.assistantUsernames.contains(user))
                || (room.memberUsernames != null && room.memberUsernames.contains(user));
        if (!ok) {
            throw new ClassRoomException("你不在该班级中");
        }
        return room;
    }

    private CheckinSession requireCheckin(String classId, String checkinId) {
        return root.checkins.stream()
                .filter(c -> checkinId != null && checkinId.equals(c.id) && classId.equals(c.classId))
                .findFirst()
                .orElseThrow(() -> new ClassRoomException("签到场次不存在"));
    }

    private ClassRoom requireClass(String classId) {
        return root.classes.stream()
                .filter(c -> classId != null && classId.equals(c.id))
                .findFirst()
                .orElseThrow(() -> new ClassRoomException("班级不存在"));
    }

    private Homework requireHomework(String homeworkId) {
        return root.homeworks.stream()
                .filter(h -> homeworkId != null && homeworkId.equals(h.id))
                .findFirst()
                .orElseThrow(() -> new ClassRoomException("作业不存在"));
    }

    private void load() {
        try {
            if (!Files.isRegularFile(storePath)) {
                root = new StoreRoot();
                persistUnlocked();
                return;
            }
            byte[] bytes = Files.readAllBytes(storePath);
            StoreRoot loaded = mapper.readValue(bytes, ROOT_TYPE);
            root = loaded == null ? new StoreRoot() : loaded;
            if (root.classes == null) {
                root.classes = new ArrayList<>();
            }
            if (root.homeworks == null) {
                root.homeworks = new ArrayList<>();
            }
            if (root.submissions == null) {
                root.submissions = new ArrayList<>();
            }
            if (root.announcements == null) {
                root.announcements = new ArrayList<>();
            }
            if (root.checkins == null) {
                root.checkins = new ArrayList<>();
            }
            if (root.checkinRecords == null) {
                root.checkinRecords = new ArrayList<>();
            }
            if (root.materials == null) {
                root.materials = new ArrayList<>();
            }
            if (root.chatMessages == null) {
                root.chatMessages = new ArrayList<>();
            }
            for (ClassRoom c : root.classes) {
                if (c.assistantUsernames == null) {
                    c.assistantUsernames = new ArrayList<>();
                }
                if (c.publishedProjectIds == null) {
                    c.publishedProjectIds = new ArrayList<>();
                }
            }
            for (Homework h : root.homeworks) {
                if (h.attachments == null) {
                    h.attachments = new ArrayList<>();
                }
            }
        } catch (Exception e) {
            // Never silently replace a non-empty store file with {} — that wipes classes/homework.
            log.error("加载班级数据失败，保留空内存但不覆盖已有文件: {}", storePath, e);
            root = new StoreRoot();
        }
    }

    private void persist() {
        try {
            persistUnlocked();
        } catch (Exception e) {
            throw new ClassRoomException("保存班级数据失败：" + e.getMessage());
        }
    }

    private void persistUnlocked() throws Exception {
        // Guard: do not overwrite a non-empty on-disk store with an empty in-memory root
        // (e.g. after a failed load). Empty root is only allowed when the file is missing/empty.
        if ((root.classes == null || root.classes.isEmpty())
                && (root.homeworks == null || root.homeworks.isEmpty())
                && Files.isRegularFile(storePath)
                && Files.size(storePath) > 32) {
            log.error("拒绝用空班级库覆盖已有文件: {}", storePath);
            throw new ClassRoomException("班级数据未加载成功，已阻止覆盖已有班级文件，请检查 classrooms.json");
        }
        Path tmp = storePath.resolveSibling(storePath.getFileName() + ".tmp");
        mapper.writerWithDefaultPrettyPrinter().writeValue(tmp.toFile(), root);
        Files.move(tmp, storePath, java.nio.file.StandardCopyOption.REPLACE_EXISTING);
    }

    private String newInviteCode() {
        final String alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
        StringBuilder sb = new StringBuilder(6);
        for (int i = 0; i < 6; i++) {
            sb.append(alphabet.charAt(RANDOM.nextInt(alphabet.length())));
        }
        String code = sb.toString();
        boolean exists = root.classes.stream().anyMatch(c -> code.equalsIgnoreCase(trim(c.inviteCode)));
        return exists ? newInviteCode() : code;
    }

    private static String now() {
        return LocalDateTime.now().format(TS);
    }

    private static String uuid() {
        return UUID.randomUUID().toString().replace("-", "");
    }

    private static String norm(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
    }

    private static String trim(String value) {
        return value == null ? "" : value.trim();
    }

    private static String requireUser(String username) {
        String u = trim(username);
        if (u.isEmpty()) {
            throw new ClassRoomException("未登录");
        }
        return norm(u);
    }

    private static String requireText(String value, String message) {
        String t = trim(value);
        if (t.isEmpty()) {
            throw new ClassRoomException(message);
        }
        return t;
    }

    private static String sanitizeFileName(String name) {
        String base = Paths.get(name).getFileName().toString();
        base = base.replaceAll("[\\\\/:*?\"<>|]", "_");
        return base.length() > 80 ? base.substring(base.length() - 80) : base;
    }

    /** 附件扩展名白名单：拦截可执行/脚本类危险类型（exe/bat/html/svg/js 等） */
    private static final java.util.Set<String> ALLOWED_ATTACHMENT_EXT = java.util.Set.of(
            "pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "csv", "txt", "md",
            "jpg", "jpeg", "png", "gif", "webp", "bmp",
            "zip", "rar", "7z",
            "mp3", "wav", "mp4", "webm",
            "py", "java", "c", "cpp", "h", "ipynb"
    );

    private void checkAttachmentExtension(String originalFilename) {
        String lower = (originalFilename == null ? "" : originalFilename).toLowerCase(Locale.ROOT);
        int dot = lower.lastIndexOf('.');
        String ext = dot < 0 ? "" : lower.substring(dot + 1);
        if (ext.isEmpty() || !ALLOWED_ATTACHMENT_EXT.contains(ext)) {
            throw new ClassRoomException("不支持的附件类型：" + originalFilename
                    + "（允许：文档/图片/压缩包/音视频/常用代码文件）");
        }
    }

    private Attachment storeAttachment(Path dir, String relativePrefix, MultipartFile file) throws Exception {
        String original = file.getOriginalFilename() == null ? "file" : file.getOriginalFilename();
        checkAttachmentExtension(original);
        String safeName = sanitizeFileName(original);
        String stored = System.currentTimeMillis() + "_" + safeName;
        Path target = dir.resolve(stored).normalize();
        if (!target.startsWith(dir)) {
            throw new ClassRoomException("非法文件名");
        }
        file.transferTo(target.toFile());
        String lower = safeName.toLowerCase(Locale.ROOT);
        boolean image = lower.matches(".*\\.(png|jpg|jpeg|gif|webp|bmp)$");
        Attachment att = new Attachment();
        att.id = "att_" + uuid();
        att.name = safeName;
        att.contentType = file.getContentType() == null ? "application/octet-stream" : file.getContentType();
        att.size = Files.size(target);
        att.relativePath = relativePrefix + "/" + stored;
        att.kind = image ? "image" : "file";
        return att;
    }

    private ClassRoom copy(ClassRoom src) {
        ClassRoom c = new ClassRoom();
        c.id = src.id;
        c.name = src.name;
        c.subject = src.subject;
        c.description = src.description;
        c.teacherUsername = src.teacherUsername;
        c.inviteCode = src.inviteCode;
        c.memberUsernames = src.memberUsernames == null ? new ArrayList<>() : new ArrayList<>(src.memberUsernames);
        c.assistantUsernames = src.assistantUsernames == null ? new ArrayList<>() : new ArrayList<>(src.assistantUsernames);
        c.projectIds = src.projectIds == null ? new ArrayList<>() : new ArrayList<>(src.projectIds);
        c.publishedProjectIds = src.publishedProjectIds == null ? new ArrayList<>() : new ArrayList<>(src.publishedProjectIds);
        c.createdAt = src.createdAt;
        c.updatedAt = src.updatedAt;
        return c;
    }

    private Homework copy(Homework src) {
        Homework h = new Homework();
        h.id = src.id;
        h.classId = src.classId;
        h.teacherUsername = src.teacherUsername;
        h.title = src.title;
        h.content = src.content;
        h.dueAt = src.dueAt;
        h.allowText = src.allowText;
        h.allowFile = src.allowFile;
        h.allowImage = src.allowImage;
        h.projectId = src.projectId;
        h.createdAt = src.createdAt;
        h.updatedAt = src.updatedAt;
        h.attachments = new ArrayList<>();
        if (src.attachments != null) {
            for (Attachment a : src.attachments) {
                h.attachments.add(copy(a));
            }
        }
        return h;
    }

    private ClassMaterial copy(ClassMaterial src) {
        ClassMaterial m = new ClassMaterial();
        m.id = src.id;
        m.classId = src.classId;
        m.title = src.title;
        m.description = src.description;
        m.uploaderUsername = src.uploaderUsername;
        m.createdAt = src.createdAt;
        m.attachment = src.attachment == null ? null : copy(src.attachment);
        return m;
    }

    private ClassChatMessage copy(ClassChatMessage src) {
        ClassChatMessage m = new ClassChatMessage();
        m.id = src.id;
        m.classId = src.classId;
        m.username = src.username;
        m.content = src.content;
        m.createdAt = src.createdAt;
        return m;
    }

    private Submission copy(Submission src) {
        Submission s = new Submission();
        s.id = src.id;
        s.homeworkId = src.homeworkId;
        s.classId = src.classId;
        s.studentUsername = src.studentUsername;
        s.textContent = src.textContent;
        s.status = src.status;
        s.score = src.score;
        s.feedback = src.feedback;
        s.featured = src.featured;
        s.gradedAt = src.gradedAt;
        s.gradedBy = src.gradedBy;
        s.createdAt = src.createdAt;
        s.submittedAt = src.submittedAt;
        s.attachments = new ArrayList<>();
        if (src.attachments != null) {
            for (Attachment a : src.attachments) {
                s.attachments.add(copy(a));
            }
        }
        return s;
    }

    private Attachment copy(Attachment src) {
        Attachment a = new Attachment();
        a.id = src.id;
        a.name = src.name;
        a.contentType = src.contentType;
        a.size = src.size;
        a.relativePath = src.relativePath;
        a.kind = src.kind;
        return a;
    }

    private Announcement copy(Announcement src) {
        Announcement a = new Announcement();
        a.id = src.id;
        a.classId = src.classId;
        a.title = src.title;
        a.content = src.content;
        a.authorUsername = src.authorUsername;
        a.createdAt = src.createdAt;
        return a;
    }

    private CheckinSession copy(CheckinSession src) {
        CheckinSession s = new CheckinSession();
        s.id = src.id;
        s.classId = src.classId;
        s.title = src.title;
        s.status = src.status;
        s.createdBy = src.createdBy;
        s.createdAt = src.createdAt;
        s.closedAt = src.closedAt;
        return s;
    }

    private CheckinRecord copy(CheckinRecord src) {
        CheckinRecord r = new CheckinRecord();
        r.id = src.id;
        r.checkinId = src.checkinId;
        r.classId = src.classId;
        r.studentUsername = src.studentUsername;
        r.checkedAt = src.checkedAt;
        return r;
    }

    public static class StoreRoot {
        public List<ClassRoom> classes = new ArrayList<>();
        public List<Homework> homeworks = new ArrayList<>();
        public List<Submission> submissions = new ArrayList<>();
        public List<Announcement> announcements = new ArrayList<>();
        public List<CheckinSession> checkins = new ArrayList<>();
        public List<CheckinRecord> checkinRecords = new ArrayList<>();
        public List<ClassMaterial> materials = new ArrayList<>();
        public List<ClassChatMessage> chatMessages = new ArrayList<>();
    }

    public static class ClassRoom {
        public String id;
        public String name;
        public String subject;
        public String description;
        public String teacherUsername;
        public String inviteCode;
        public List<String> memberUsernames = new ArrayList<>();
        public List<String> assistantUsernames = new ArrayList<>();
        public List<String> projectIds = new ArrayList<>();
        public List<String> publishedProjectIds = new ArrayList<>();
        public String createdAt;
        public String updatedAt;
    }

    public static class Homework {
        public String id;
        public String classId;
        public String teacherUsername;
        public String title;
        public String content;
        public String dueAt;
        public boolean allowText = true;
        public boolean allowFile = true;
        public boolean allowImage = true;
        public boolean allowLate = true;
        public String projectId;
        public List<Attachment> attachments = new ArrayList<>();
        public String createdAt;
        public String updatedAt;
    }

    public static class ClassMaterial {
        public String id;
        public String classId;
        public String title;
        public String description;
        public String uploaderUsername;
        public Attachment attachment;
        public String createdAt;
    }

    public static class ClassChatMessage {
        public String id;
        public String classId;
        public String username;
        public String content;
        public String createdAt;
    }

    public static class Submission {
        public String id;
        public String homeworkId;
        public String classId;
        public String studentUsername;
        public String textContent;
        public String status;
        public Double score;
        public String feedback;
        public boolean featured;
        public boolean late;
        public String gradedAt;
        public String gradedBy;
        public List<Attachment> attachments = new ArrayList<>();
        public String createdAt;
        public String submittedAt;
    }

    public static class Announcement {
        public String id;
        public String classId;
        public String title;
        public String content;
        public String authorUsername;
        public String createdAt;
    }

    public static class CheckinSession {
        public String id;
        public String classId;
        public String title;
        public String status;
        public String createdBy;
        public String createdAt;
        public String closedAt;
    }

    public static class CheckinRecord {
        public String id;
        public String checkinId;
        public String classId;
        public String studentUsername;
        public String checkedAt;
    }

    public static class Attachment {
        public String id;
        public String name;
        public String contentType;
        public long size;
        public String relativePath;
        public String kind;
    }

    public static class HomeworkView {
        public Homework homework;
        public String classId;
        public String className;
        public boolean submitted;
        public Submission submission;
    }

    public static class ClassRoomException extends RuntimeException {
        public ClassRoomException(String message) {
            super(message);
        }
    }
}
