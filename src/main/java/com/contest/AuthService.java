package com.contest;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;

import javax.annotation.PostConstruct;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.security.SecureRandom;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Base64;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class AuthService {

    public static final String ROLE_TEACHER = "teacher";
    public static final String ROLE_STUDENT = "student";
    public static final String ROLE_ADMIN = "admin";

    public static final String ADMIN_LEVEL_SUPER = "super";
    public static final String ADMIN_LEVEL_OPS = "ops";
    public static final String ADMIN_LEVEL_CONTENT = "content";

    private static final TypeReference<Map<String, AuthUserRecord>> USER_MAP_TYPE = new TypeReference<Map<String, AuthUserRecord>>() {};
    private static final TypeReference<Map<String, SessionRecord>> SESSION_MAP_TYPE = new TypeReference<Map<String, SessionRecord>>() {};
    private static final TypeReference<List<PasswordResetRequest>> RESET_LIST_TYPE = new TypeReference<List<PasswordResetRequest>>() {};
    private static final TypeReference<List<AdminAuditEntry>> AUDIT_LIST_TYPE = new TypeReference<List<AdminAuditEntry>>() {};
    private static final SecureRandom SECURE_RANDOM = new SecureRandom();
    private static final String PASSWORD_ALGO_BCRYPT = "bcrypt";
    private static final String PASSWORD_ALGO_SHA256 = "sha256";
    private static final List<String> VALID_ROLES = Arrays.asList(ROLE_TEACHER, ROLE_STUDENT, ROLE_ADMIN);
    private static final List<String> VALID_ADMIN_LEVELS = Arrays.asList(ADMIN_LEVEL_SUPER, ADMIN_LEVEL_OPS, ADMIN_LEVEL_CONTENT);

    /** 单一账号体系：宿主新建/改密后同步到学生与管理服务；由 Spring 注入。 */
    private ZhixuetiAuthBridge authBridge;

    @org.springframework.beans.factory.annotation.Autowired(required = false)
    public void setAuthBridge(ZhixuetiAuthBridge authBridge) {
        this.authBridge = authBridge;
    }

    /** 账号变更后推送镜像（失败不阻断主流程，登录时会再补一次）。 */
    private void syncAccountToBackend(String username, String password, List<String> roles) {
        if (authBridge == null) {
            return;
        }
        try {
            int userType = roles != null && roles.contains(ROLE_ADMIN) ? 3
                    : (roles != null && roles.contains(ROLE_TEACHER) ? 2 : 1);
            authBridge.ensureAccountTokens(username, password, userType);
        } catch (Exception ex) {
            // 后台服务未就绪时忽略：用户首次登录仍会触发同步
        }
    }

    private final ObjectMapper objectMapper = new ObjectMapper();
    private final BCryptPasswordEncoder passwordEncoder = new BCryptPasswordEncoder();
    private final Map<String, AuthUserRecord> users = new LinkedHashMap<>();
    private final Map<String, SessionRecord> sessions = new ConcurrentHashMap<>();
    private final DatabaseStore databaseStore;
    private boolean databaseReady;

    public AuthService(DatabaseStore databaseStore) {
        this.databaseStore = databaseStore;
    }

    @Value("${auth.store-file:data/auth-users.json}")
    private String authStoreFile;

    @Value("${auth.session-store-file:data/auth-sessions.json}")
    private String sessionStoreFile;

    @Value("${auth.session-hours:12}")
    private long sessionHours;

    @Value("${auth.admin-usernames:}")
    private String adminUsernames;

    @Value("${auth.reset-request-file:data/password-reset-requests.json}")
    private String resetRequestFile;

    /** 是否允许匿名自选教师角色注册；生产部署建议置 false，由管理员在后台授角色。 */
    @Value("${auth.allow-teacher-self-register:true}")
    private boolean allowTeacherSelfRegister;

    @Value("${auth.admin-audit-file:data/admin-audit.json}")
    private String adminAuditFile;

    private Path userStorePath;
    private Path sessionStorePath;
    private Path resetRequestPath;
    private Path adminAuditPath;
    private final List<PasswordResetRequest> resetRequests = new ArrayList<>();
    private final List<AdminAuditEntry> adminAudits = new ArrayList<>();

    @PostConstruct
    public synchronized void init() throws IOException {
        this.userStorePath = prepareStorePath(authStoreFile);
        this.sessionStorePath = prepareStorePath(sessionStoreFile);
        this.resetRequestPath = prepareStorePath(resetRequestFile);
        this.adminAuditPath = prepareStorePath(adminAuditFile);

        databaseReady = prepareDatabase();

        users.clear();
        Map<String, AuthUserRecord> loadedUsers = loadUsers();
        for (Map.Entry<String, AuthUserRecord> entry : loadedUsers.entrySet()) {
            String normalizedUsername = normalizeUsername(entry.getKey());
            if (normalizedUsername.isEmpty()) {
                continue;
            }
            AuthUserRecord record = entry.getValue() == null ? new AuthUserRecord() : entry.getValue();
            record.setUsername(normalizedUsername);
            record.setRoles(normalizeRoles(record.getRoles(), true));
            record.setAdminLevel(normalizeAdminLevel(record.getAdminLevel(), record.getRoles()));
            users.put(normalizedUsername, record);
        }
        applyConfiguredAdminRoles();

        sessions.clear();
        Map<String, SessionRecord> loadedSessions = loadSessions();
        for (Map.Entry<String, SessionRecord> entry : loadedSessions.entrySet()) {
            String sessionId = str(entry.getKey());
            SessionRecord record = entry.getValue();
            if (sessionId.isEmpty() || record == null) {
                continue;
            }
            String username = normalizeUsername(record.getUsername());
            if (username.isEmpty()) {
                continue;
            }
            record.setUsername(username);
            record.setActiveRole(resolveSessionRole(users.get(username), record.getActiveRole()));
            sessions.put(sessionId, record);
        }
        removeExpiredSessions();

        resetRequests.clear();
        resetRequests.addAll(loadListStore(resetRequestPath, RESET_LIST_TYPE));
        adminAudits.clear();
        adminAudits.addAll(loadListStore(adminAuditPath, AUDIT_LIST_TYPE));

        persistUsers();
        persistSessions();
    }

    public synchronized AuthResult register(String username, String password, String role) {
        String normalized = normalizeUsername(username);
        validateCredential(normalized, password);
        String normalizedRole = normalizeRegisterRole(role);
        if (users.containsKey(normalized)) {
            throw new AuthException("账号已存在");
        }

        AuthUserRecord record = new AuthUserRecord();
        record.setUsername(normalized);
        record.setPasswordHash(passwordEncoder.encode(password));
        record.setPasswordAlgo(PASSWORD_ALGO_BCRYPT);
        record.setSalt("");
        record.setCreatedAt(Instant.now().toString());
        record.setRoles(Collections.singletonList(normalizedRole));
        users.put(normalized, record);
        persistUsers();
        syncAccountToBackend(normalized, password, Collections.singletonList(normalizedRole));
        return createSessionFor(normalized, normalizedRole);
    }

    public synchronized AuthResult login(String username, String password, String entryRole) {
        String normalized = normalizeUsername(username);
        validateCredential(normalized, password);
        String normalizedRole = normalizeLoginRole(entryRole);
        AuthUserRecord record = users.get(normalized);
        if (record == null) {
            throw new AuthException("账号或密码错误");
        }
        if (record.isDisabled()) {
            throw new AuthException("账号已被禁用，请联系管理员");
        }

        if (!matchesPassword(password, record)) {
            throw new AuthException("账号或密码错误");
        }
        upgradeLegacyPasswordIfNeeded(record, normalized, password);

        List<String> roles = normalizeRoles(record.getRoles(), true);
        if (!roles.contains(normalizedRole)) {
            throw new AuthException("当前账号无权从该入口登录");
        }
        record.setRoles(roles);
        users.put(normalized, record);
        persistUsers();
        return createSessionFor(normalized, normalizedRole);
    }

    public synchronized void changePassword(String sessionId, String oldPassword, String newPassword) {
        AuthUserView user = getUserBySession(sessionId);
        if (user == null) {
            throw new AuthException("未登录或登录已过期");
        }
        if (oldPassword == null || oldPassword.trim().isEmpty()) {
            throw new AuthException("请输入当前密码");
        }
        if (newPassword == null || newPassword.trim().isEmpty()) {
            throw new AuthException("请输入新密码");
        }
        if (newPassword.length() < 6) {
            throw new AuthException("新密码至少 6 位");
        }
        if (oldPassword.equals(newPassword)) {
            throw new AuthException("新密码不能与当前密码相同");
        }

        String username = normalizeUsername(user.getUsername());
        AuthUserRecord record = users.get(username);
        if (record == null) {
            throw new AuthException("账号不存在");
        }
        if (!matchesPassword(oldPassword, record)) {
            throw new AuthException("当前密码不正确");
        }

        record.setPasswordHash(passwordEncoder.encode(newPassword));
        record.setSalt("");
        record.setPasswordAlgo("bcrypt");
        users.put(username, record);
        persistUsers();
        // 改密后吊销该账号的全部会话，防止旧会话继续有效
        boolean changed = sessions.values().removeIf(s -> username.equals(normalizeUsername(s.getUsername())));
        if (changed) {
            persistSessions();
        }
    }

    /** 教师查看班级成员时的轻量资料（不含密码） */
    public synchronized Map<String, Object> describeUserBrief(String username) {
        String key = normalizeUsername(username);
        AuthUserRecord record = users.get(key);
        Map<String, Object> info = new LinkedHashMap<>();
        info.put("username", key);
        if (record == null) {
            info.put("exists", false);
            info.put("displayName", key);
            info.put("roles", Collections.emptyList());
            info.put("disabled", false);
            info.put("createdAt", "");
            info.put("status", "未注册账号");
            return info;
        }
        info.put("exists", true);
        info.put("displayName", record.getUsername());
        info.put("roles", normalizeRoles(record.getRoles(), true));
        info.put("disabled", record.isDisabled());
        info.put("createdAt", record.getCreatedAt() == null ? "" : record.getCreatedAt());
        info.put("status", record.isDisabled() ? "已停用" : "正常");
        return info;
    }

    public AuthUserView getUserBySession(String sessionId) {
        if (sessionId == null || sessionId.trim().isEmpty()) {
            return null;
        }
        SessionRecord record = sessions.get(sessionId);
        if (record == null) {
            return null;
        }
        if (record.expireAtInstant().isBefore(Instant.now())) {
            sessions.remove(sessionId);
            persistSessions();
            return null;
        }
        AuthUserRecord userRecord = users.get(normalizeUsername(record.getUsername()));
        if (userRecord == null) {
            sessions.remove(sessionId);
            persistSessions();
            return null;
        }
        if (userRecord.isDisabled()) {
            sessions.remove(sessionId);
            persistSessions();
            return null;
        }

        List<String> roles = normalizeRoles(userRecord.getRoles(), true);
        String activeRole = resolveSessionRole(userRecord, record.getActiveRole());
        if (!roles.equals(userRecord.getRoles())) {
            userRecord.setRoles(roles);
            users.put(userRecord.getUsername(), userRecord);
            persistUsers();
        }
        if (!activeRole.equals(str(record.getActiveRole()))) {
            record.setActiveRole(activeRole);
            sessions.put(sessionId, record);
            persistSessions();
        }

        return new AuthUserView(
                userRecord.getUsername(),
                record.getLoginAt(),
                new ArrayList<>(roles),
                activeRole,
                getHomePathForRole(activeRole),
                resolveAdminLevel(userRecord),
                userRecord.isDisabled()
        );
    }

    public boolean hasActiveRole(String sessionId, String... allowedRoles) {
        AuthUserView user = getUserBySession(sessionId);
        if (user == null || allowedRoles == null || allowedRoles.length == 0) {
            return false;
        }
        for (String allowedRole : allowedRoles) {
            if (user.hasActiveRole(allowedRole)) {
                return true;
            }
        }
        return false;
    }

    /** 账号是否具备教师/管理员身份（用于学情统计排除，避免老师预览混入学生名单）。 */
    public synchronized boolean usernameHasStaffRole(String username) {
        String key = normalizeUsername(username);
        if (key.isEmpty()) {
            return false;
        }
        AuthUserRecord record = users.get(key);
        if (record == null) {
            return false;
        }
        List<String> roles = normalizeRoles(record.getRoles(), true);
        return roles.contains(ROLE_TEACHER) || roles.contains(ROLE_ADMIN);
    }

    public synchronized void logout(String sessionId) {
        if (sessionId == null || sessionId.trim().isEmpty()) {
            return;
        }
        sessions.remove(sessionId);
        persistSessions();
    }

    public synchronized List<AuthUserView> listUsersForAdmin() {
        List<AuthUserView> items = new ArrayList<>();
        for (AuthUserRecord record : users.values()) {
            List<String> roles = normalizeRoles(record.getRoles(), true);
            String activeRole = roles.contains(ROLE_ADMIN) ? ROLE_ADMIN : roles.get(0);
            items.add(toUserView(record, record.getCreatedAt(), activeRole));
        }
        items.sort((a, b) -> String.valueOf(a.getUsername()).compareTo(String.valueOf(b.getUsername())));
        return items;
    }

    public static String getHomePathForRole(String role) {
        String normalizedRole = normalizeRole(role);
        if (ROLE_STUDENT.equals(normalizedRole)) {
            return "/student/home";
        }
        if (ROLE_ADMIN.equals(normalizedRole)) {
            return "/admin/home.html";
        }
        return "/teacher/home.html";
    }

    public AuthUserView requireAdmin(String sessionId) {
        AuthUserView user = getUserBySession(sessionId);
        if (user == null) {
            throw new AuthException("未登录或登录已过期");
        }
        if (!ROLE_ADMIN.equals(user.getActiveRole())) {
            throw new AuthException("请使用管理员入口登录后再操作");
        }
        return user;
    }

    public void requireAdminLevel(String sessionId, String... allowedLevels) {
        AuthUserView user = requireAdmin(sessionId);
        String level = str(user.getAdminLevel());
        if (allowedLevels == null || allowedLevels.length == 0) {
            return;
        }
        for (String allowed : allowedLevels) {
            if (level.equals(str(allowed))) {
                return;
            }
            if (ADMIN_LEVEL_SUPER.equals(level)) {
                return;
            }
        }
        throw new AuthException("当前管理员级别无权执行该操作");
    }

    public synchronized AuthUserView createUserByAdmin(
            String sessionId,
            String username,
            String password,
            List<String> roles,
            String adminLevel
    ) {
        AuthUserView operator = requireAdmin(sessionId);
        String normalized = normalizeUsername(username);
        validateCredential(normalized, password);
        if (users.containsKey(normalized)) {
            throw new AuthException("账号已存在");
        }

        List<String> normalizedRoles = normalizeRoles(roles, false);
        if (normalizedRoles.isEmpty()) {
            throw new AuthException("请至少选择一个角色");
        }
        String level = "";
        if (normalizedRoles.contains(ROLE_ADMIN)) {
            requireAdminLevel(sessionId, ADMIN_LEVEL_SUPER);
            level = normalizeAdminLevel(adminLevel, normalizedRoles);
            if (level.isEmpty()) {
                level = ADMIN_LEVEL_OPS;
            }
            if (ADMIN_LEVEL_SUPER.equals(level) && !ADMIN_LEVEL_SUPER.equals(str(operator.getAdminLevel()))) {
                throw new AuthException("仅超级管理员可以创建超级管理员");
            }
        } else {
            requireAdminLevel(sessionId, ADMIN_LEVEL_SUPER, ADMIN_LEVEL_OPS);
        }

        AuthUserRecord record = new AuthUserRecord();
        record.setUsername(normalized);
        record.setPasswordHash(passwordEncoder.encode(password));
        record.setPasswordAlgo(PASSWORD_ALGO_BCRYPT);
        record.setSalt("");
        record.setCreatedAt(Instant.now().toString());
        record.setRoles(normalizedRoles);
        record.setAdminLevel(normalizedRoles.contains(ROLE_ADMIN) ? level : "");
        record.setDisabled(false);
        users.put(normalized, record);
        persistUsers();
        appendAudit(operator.getUsername(), "create_user", normalized, "roles=" + normalizedRoles + ",adminLevel=" + level);
        syncAccountToBackend(normalized, password, normalizedRoles);
        return toUserView(record, record.getCreatedAt(), normalizedRoles.get(0));
    }

    public synchronized AuthUserView updateUserByAdmin(
            String sessionId,
            String username,
            List<String> roles,
            String adminLevel,
            Boolean disabled
    ) {
        AuthUserView operator = requireAdmin(sessionId);
        requireAdminLevel(sessionId, ADMIN_LEVEL_SUPER, ADMIN_LEVEL_OPS);
        String normalized = normalizeUsername(username);
        AuthUserRecord record = users.get(normalized);
        if (record == null) {
            throw new AuthException("账号不存在");
        }
        if (normalized.equals(operator.getUsername()) && Boolean.TRUE.equals(disabled)) {
            throw new AuthException("不能禁用当前登录账号");
        }

        if (roles != null) {
            List<String> normalizedRoles = normalizeRoles(roles, false);
            if (normalizedRoles.isEmpty()) {
                throw new AuthException("请至少保留一个角色");
            }
            if (normalizedRoles.contains(ROLE_ADMIN)) {
                requireAdminLevel(sessionId, ADMIN_LEVEL_SUPER);
                String level = normalizeAdminLevel(adminLevel, normalizedRoles);
                if (level.isEmpty()) {
                    level = normalizeAdminLevel(record.getAdminLevel(), normalizedRoles);
                }
                if (level.isEmpty()) {
                    level = ADMIN_LEVEL_OPS;
                }
                if (ADMIN_LEVEL_SUPER.equals(str(record.getAdminLevel()))
                        && !ADMIN_LEVEL_SUPER.equals(str(operator.getAdminLevel()))) {
                    throw new AuthException("无权修改超级管理员");
                }
                record.setAdminLevel(level);
            } else {
                record.setAdminLevel("");
            }
            record.setRoles(normalizedRoles);
        } else if (adminLevel != null && !adminLevel.trim().isEmpty()) {
            requireAdminLevel(sessionId, ADMIN_LEVEL_SUPER);
            if (!normalizeRoles(record.getRoles(), true).contains(ROLE_ADMIN)) {
                throw new AuthException("该账号不是管理员，无法设置管理员级别");
            }
            record.setAdminLevel(normalizeAdminLevel(adminLevel, record.getRoles()));
        }

        if (disabled != null) {
            record.setDisabled(disabled);
        }
        users.put(normalized, record);
        persistUsers();
        appendAudit(operator.getUsername(), "update_user", normalized,
                "roles=" + record.getRoles() + ",adminLevel=" + record.getAdminLevel() + ",disabled=" + record.isDisabled());
        return toUserView(record, record.getCreatedAt(),
                record.getRoles().contains(ROLE_ADMIN) ? ROLE_ADMIN : record.getRoles().get(0));
    }

    public synchronized String resetPasswordByAdmin(String sessionId, String username, String newPassword) {
        AuthUserView operator = requireAdmin(sessionId);
        requireAdminLevel(sessionId, ADMIN_LEVEL_SUPER, ADMIN_LEVEL_OPS);
        String normalized = normalizeUsername(username);
        AuthUserRecord record = users.get(normalized);
        if (record == null) {
            throw new AuthException("账号不存在");
        }
        String password = (newPassword == null || newPassword.trim().isEmpty())
                ? randomReadablePassword()
                : newPassword.trim();
        if (password.length() < 6) {
            throw new AuthException("新密码至少 6 位");
        }
        record.setPasswordHash(passwordEncoder.encode(password));
        record.setSalt("");
        record.setPasswordAlgo(PASSWORD_ALGO_BCRYPT);
        users.put(normalized, record);
        persistUsers();
        appendAudit(operator.getUsername(), "reset_password", normalized, "password_reset");
        return password;
    }

    public synchronized PasswordResetRequest submitPasswordResetRequest(String username, String roleHint, String reason, String contact) {
        String normalized = normalizeUsername(username);
        if (normalized.isEmpty()) {
            throw new AuthException("请填写账号");
        }
        PasswordResetRequest request = new PasswordResetRequest();
        request.setId(UUID.randomUUID().toString().replace("-", ""));
        request.setUsername(normalized);
        request.setRoleHint(str(roleHint));
        request.setReason(str(reason));
        request.setContact(str(contact));
        request.setStatus("pending");
        request.setCreatedAt(Instant.now().toString());
        resetRequests.add(0, request);
        persistResetRequests();
        return request;
    }

    public synchronized List<PasswordResetRequest> listPasswordResetRequests(String sessionId, String status) {
        requireAdmin(sessionId);
        requireAdminLevel(sessionId, ADMIN_LEVEL_SUPER, ADMIN_LEVEL_OPS);
        String filter = str(status).toLowerCase();
        List<PasswordResetRequest> items = new ArrayList<>();
        for (PasswordResetRequest item : resetRequests) {
            if (filter.isEmpty() || "all".equals(filter) || filter.equals(str(item.getStatus()).toLowerCase())) {
                items.add(item);
            }
        }
        return items;
    }

    public synchronized PasswordResetRequest resolvePasswordResetRequest(
            String sessionId,
            String requestId,
            String action,
            String newPassword
    ) {
        AuthUserView operator = requireAdmin(sessionId);
        requireAdminLevel(sessionId, ADMIN_LEVEL_SUPER, ADMIN_LEVEL_OPS);
        PasswordResetRequest target = null;
        for (PasswordResetRequest item : resetRequests) {
            if (str(requestId).equals(item.getId())) {
                target = item;
                break;
            }
        }
        if (target == null) {
            throw new AuthException("申请不存在");
        }
        if (!"pending".equals(str(target.getStatus()))) {
            throw new AuthException("该申请已处理");
        }
        String normalizedAction = str(action).toLowerCase();
        if ("reject".equals(normalizedAction)) {
            target.setStatus("rejected");
            target.setResolvedAt(Instant.now().toString());
            target.setResolvedBy(operator.getUsername());
            persistResetRequests();
            appendAudit(operator.getUsername(), "reject_reset_request", target.getUsername(), target.getId());
            return target;
        }
        if (!"approve".equals(normalizedAction)) {
            throw new AuthException("不支持的处理动作");
        }
        String password = resetPasswordByAdmin(sessionId, target.getUsername(), newPassword);
        target.setStatus("done");
        target.setResolvedAt(Instant.now().toString());
        target.setResolvedBy(operator.getUsername());
        target.setTempPassword(password);
        persistResetRequests();
        appendAudit(operator.getUsername(), "approve_reset_request", target.getUsername(), target.getId());
        return target;
    }

    public synchronized List<AdminAuditEntry> listAdminAudits(String sessionId, int limit) {
        requireAdmin(sessionId);
        int safe = Math.max(1, Math.min(limit <= 0 ? 50 : limit, 200));
        if (adminAudits.size() <= safe) {
            return new ArrayList<>(adminAudits);
        }
        return new ArrayList<>(adminAudits.subList(0, safe));
    }

    private synchronized void persistUsers() {
        if (databaseReady) {
            try {
                databaseStore.saveUsers(users);
                return;
            } catch (Exception e) {
                databaseReady = false;
            }
        }
        try {
            objectMapper.writerWithDefaultPrettyPrinter().writeValue(userStorePath.toFile(), users);
        } catch (IOException e) {
            throw new AuthException("账号数据保存失败，请稍后重试");
        }
    }

    private synchronized void persistSessions() {
        if (databaseReady) {
            try {
                databaseStore.saveSessions(sessions);
                return;
            } catch (Exception e) {
                databaseReady = false;
            }
        }
        try {
            objectMapper.writerWithDefaultPrettyPrinter().writeValue(sessionStorePath.toFile(), sessions);
        } catch (IOException e) {
            throw new AuthException("会话数据保存失败，请稍后重试");
        }
    }

    private synchronized AuthResult createSessionFor(String username, String activeRole) {
        String sessionId = UUID.randomUUID().toString().replace("-", "") + randomToken(12);
        Instant now = Instant.now();
        SessionRecord session = new SessionRecord();
        session.setUsername(username);
        session.setLoginAt(now.toString());
        session.setExpireAt(now.plus(Duration.ofHours(Math.max(1, sessionHours))).toString());
        session.setActiveRole(resolveSessionRole(users.get(username), activeRole));
        sessions.put(sessionId, session);
        persistSessions();

        AuthUserRecord record = users.get(username);
        List<String> roles = record == null ? Collections.singletonList(ROLE_TEACHER) : normalizeRoles(record.getRoles(), true);
        return new AuthResult(
                sessionId,
                toUserView(record == null ? syntheticTeacher(username) : record, session.getLoginAt(), session.getActiveRole())
        );
    }

    private AuthUserRecord syntheticTeacher(String username) {
        AuthUserRecord record = new AuthUserRecord();
        record.setUsername(username);
        record.setRoles(Collections.singletonList(ROLE_TEACHER));
        record.setAdminLevel("");
        record.setDisabled(false);
        return record;
    }

    private AuthUserView toUserView(AuthUserRecord record, String loginAt, String activeRole) {
        List<String> roles = normalizeRoles(record.getRoles(), true);
        String role = normalizeRole(activeRole);
        if (!roles.contains(role)) {
            role = roles.get(0);
        }
        return new AuthUserView(
                record.getUsername(),
                loginAt,
                new ArrayList<>(roles),
                role,
                getHomePathForRole(role),
                resolveAdminLevel(record),
                record.isDisabled()
        );
    }

    private synchronized void removeExpiredSessions() {
        Instant now = Instant.now();
        sessions.entrySet().removeIf(entry -> entry.getValue() == null || entry.getValue().expireAtInstant().isBefore(now));
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

    private Map<String, AuthUserRecord> loadUsers() throws IOException {
        if (databaseReady) {
            try {
                Map<String, AuthUserRecord> fromDb = databaseStore.loadUsers();
                if (!fromDb.isEmpty()) {
                    return fromDb;
                }
            } catch (Exception e) {
                databaseReady = false;
            }
        }
        return loadStoreSafely(userStorePath, USER_MAP_TYPE);
    }

    private Map<String, SessionRecord> loadSessions() throws IOException {
        if (databaseReady) {
            try {
                Map<String, SessionRecord> fromDb = databaseStore.loadSessions();
                if (!fromDb.isEmpty()) {
                    return fromDb;
                }
            } catch (Exception e) {
                databaseReady = false;
            }
        }
        return loadStoreSafely(sessionStorePath, SESSION_MAP_TYPE);
    }

    private synchronized void applyConfiguredAdminRoles() {
        for (String raw : str(adminUsernames).split(",")) {
            String username = normalizeUsername(raw);
            if (username.isEmpty()) {
                continue;
            }
            AuthUserRecord record = users.get(username);
            if (record == null) {
                continue;
            }
            List<String> roles = normalizeRoles(record.getRoles(), true);
            if (!roles.contains(ROLE_ADMIN)) {
                roles.add(ROLE_ADMIN);
            }
            record.setRoles(roles);
            // Configured bootstrap admins are always super (MySQL store does not historically persist level).
            record.setAdminLevel(ADMIN_LEVEL_SUPER);
            users.put(username, record);
        }
    }

    private Path prepareStorePath(String file) throws IOException {
        Path path = Paths.get(file).toAbsolutePath();
        Path parent = path.getParent();
        if (parent != null) {
            Files.createDirectories(parent);
        }
        return path;
    }

    private <T> Map<String, T> loadStoreSafely(Path path, TypeReference<Map<String, T>> type) throws IOException {
        if (!Files.exists(path)) {
            return new LinkedHashMap<>();
        }
        try {
            Map<String, T> loaded = objectMapper.readValue(path.toFile(), type);
            return loaded == null ? new LinkedHashMap<>() : new LinkedHashMap<>(loaded);
        } catch (IOException ex) {
            backupCorruptedStore(path);
            return new LinkedHashMap<>();
        }
    }

    private void backupCorruptedStore(Path path) throws IOException {
        String backupName = path.getFileName().toString() + ".broken-" + System.currentTimeMillis();
        Path backup = path.resolveSibling(backupName);
        Files.move(path, backup, StandardCopyOption.REPLACE_EXISTING);
    }

    private void validateCredential(String username, String password) {
        if (username == null || username.trim().isEmpty()) {
            throw new AuthException("账号不能为空");
        }
        if (password == null || password.trim().isEmpty()) {
            throw new AuthException("密码不能为空");
        }
        if (password.length() < 6) {
            throw new AuthException("密码至少 6 位");
        }
    }

    private String normalizeUsername(String username) {
        return username == null ? "" : username.trim().toLowerCase();
    }

    private boolean matchesPassword(String password, AuthUserRecord record) {
        String algo = record.getPasswordAlgo();
        if (algo == null || algo.trim().isEmpty()) {
            algo = record.getSalt() == null || record.getSalt().trim().isEmpty() ? PASSWORD_ALGO_BCRYPT : PASSWORD_ALGO_SHA256;
        }
        if (PASSWORD_ALGO_BCRYPT.equalsIgnoreCase(algo)) {
            return passwordEncoder.matches(password, record.getPasswordHash());
        }
        if (PASSWORD_ALGO_SHA256.equalsIgnoreCase(algo)) {
            return legacySha256(password, record.getSalt()).equals(record.getPasswordHash());
        }
        throw new AuthException("不支持的密码算法");
    }

    private void upgradeLegacyPasswordIfNeeded(AuthUserRecord record, String username, String rawPassword) {
        String algo = record.getPasswordAlgo();
        if (PASSWORD_ALGO_BCRYPT.equalsIgnoreCase(algo)) {
            return;
        }
        record.setPasswordHash(passwordEncoder.encode(rawPassword));
        record.setPasswordAlgo(PASSWORD_ALGO_BCRYPT);
        record.setSalt("");
        users.put(username, record);
        persistUsers();
    }

    private String normalizeRegisterRole(String role) {
        String normalized = normalizeRole(role);
        if (ROLE_STUDENT.equals(normalized)) {
            return normalized;
        }
        if (ROLE_TEACHER.equals(normalized)) {
            if (!allowTeacherSelfRegister) {
                throw new AuthException("教师账号暂不支持自助注册，请联系管理员开通");
            }
            return normalized;
        }
        throw new AuthException("注册角色不合法");
    }

    private String normalizeLoginRole(String role) {
        String normalized = normalizeRole(role);
        if (normalized.isEmpty()) {
            throw new AuthException("请选择登录入口");
        }
        return normalized;
    }

    private static String normalizeRole(String role) {
        String normalized = role == null ? "" : role.trim().toLowerCase();
        return VALID_ROLES.contains(normalized) ? normalized : "";
    }

    private List<String> normalizeRoles(List<String> roles, boolean fallbackTeacher) {
        Set<String> normalized = new LinkedHashSet<>();
        if (roles != null) {
            for (String role : roles) {
                String item = normalizeRole(role);
                if (!item.isEmpty()) {
                    normalized.add(item);
                }
            }
        }
        if (normalized.isEmpty() && fallbackTeacher) {
            normalized.add(ROLE_TEACHER);
        }
        return new ArrayList<>(normalized);
    }

    private String resolveSessionRole(AuthUserRecord record, String activeRole) {
        List<String> roles = record == null ? Collections.singletonList(ROLE_TEACHER) : normalizeRoles(record.getRoles(), true);
        String normalized = normalizeRole(activeRole);
        if (roles.contains(normalized)) {
            return normalized;
        }
        return roles.get(0);
    }

    private String legacySha256(String password, String salt) {
        try {
            java.security.MessageDigest digest = java.security.MessageDigest.getInstance("SHA-256");
            byte[] bytes = digest.digest(((salt == null ? "" : salt) + "::" + password).getBytes());
            return Base64.getEncoder().encodeToString(bytes);
        } catch (Exception e) {
            throw new AuthException("密码处理失败");
        }
    }

    private static String randomToken(int length) {
        byte[] bytes = new byte[length];
        SECURE_RANDOM.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    private static String str(String value) {
        return value == null ? "" : value.trim();
    }

    private String normalizeAdminLevel(String adminLevel, List<String> roles) {
        List<String> normalizedRoles = normalizeRoles(roles, false);
        if (!normalizedRoles.contains(ROLE_ADMIN)) {
            return "";
        }
        String level = str(adminLevel).toLowerCase();
        if (VALID_ADMIN_LEVELS.contains(level)) {
            return level;
        }
        return ADMIN_LEVEL_OPS;
    }

    private String resolveAdminLevel(AuthUserRecord record) {
        if (record == null) {
            return "";
        }
        return normalizeAdminLevel(record.getAdminLevel(), record.getRoles());
    }

    private void appendAudit(String actor, String action, String target, String detail) {
        AdminAuditEntry entry = new AdminAuditEntry();
        entry.setId(UUID.randomUUID().toString().replace("-", ""));
        entry.setActor(str(actor));
        entry.setAction(str(action));
        entry.setTarget(str(target));
        entry.setDetail(str(detail));
        entry.setCreatedAt(Instant.now().toString());
        adminAudits.add(0, entry);
        if (adminAudits.size() > 500) {
            adminAudits.subList(500, adminAudits.size()).clear();
        }
        persistAdminAudits();
    }

    private void persistResetRequests() {
        try {
            // 明文临时密码只在审批响应中出现一次，不允许落盘留存
            List<PasswordResetRequest> safeCopy = new ArrayList<>(resetRequests.size());
            for (PasswordResetRequest r : resetRequests) {
                if (r.getTempPassword() == null) {
                    safeCopy.add(r);
                    continue;
                }
                PasswordResetRequest copy = objectMapper.readValue(objectMapper.writeValueAsString(r), PasswordResetRequest.class);
                copy.setTempPassword(null);
                safeCopy.add(copy);
            }
            objectMapper.writerWithDefaultPrettyPrinter().writeValue(resetRequestPath.toFile(), safeCopy);
        } catch (IOException e) {
            throw new AuthException("密码重置申请保存失败");
        }
    }

    private void persistAdminAudits() {
        try {
            objectMapper.writerWithDefaultPrettyPrinter().writeValue(adminAuditPath.toFile(), adminAudits);
        } catch (IOException e) {
            throw new AuthException("管理审计日志保存失败");
        }
    }

    private <T> List<T> loadListStore(Path path, TypeReference<List<T>> type) {
        if (!Files.exists(path)) {
            return new ArrayList<>();
        }
        try {
            List<T> loaded = objectMapper.readValue(path.toFile(), type);
            return loaded == null ? new ArrayList<>() : new ArrayList<>(loaded);
        } catch (IOException e) {
            return new ArrayList<>();
        }
    }

    private String randomReadablePassword() {
        String alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 10; i++) {
            sb.append(alphabet.charAt(SECURE_RANDOM.nextInt(alphabet.length())));
        }
        return sb.toString();
    }

    public static class AuthResult {
        private final String sessionId;
        private final AuthUserView user;

        public AuthResult(String sessionId, AuthUserView user) {
            this.sessionId = sessionId;
            this.user = user;
        }

        public String getSessionId() {
            return sessionId;
        }

        public AuthUserView getUser() {
            return user;
        }
    }

    public static class AuthUserView {
        private final String username;
        private final String loginAt;
        private final List<String> roles;
        private final String activeRole;
        private final String homePath;
        private final String adminLevel;
        private final boolean disabled;

        public AuthUserView(
                String username,
                String loginAt,
                List<String> roles,
                String activeRole,
                String homePath,
                String adminLevel,
                boolean disabled
        ) {
            this.username = username;
            this.loginAt = loginAt;
            this.roles = roles == null ? Collections.emptyList() : roles;
            this.activeRole = activeRole;
            this.homePath = homePath;
            this.adminLevel = adminLevel == null ? "" : adminLevel;
            this.disabled = disabled;
        }

        public String getUsername() {
            return username;
        }

        public String getLoginAt() {
            return loginAt;
        }

        public List<String> getRoles() {
            return roles;
        }

        public String getActiveRole() {
            return activeRole;
        }

        public String getHomePath() {
            return homePath;
        }

        public String getAdminLevel() {
            return adminLevel;
        }

        public boolean isDisabled() {
            return disabled;
        }

        public boolean hasActiveRole(String role) {
            return normalizeRole(role).equals(activeRole);
        }
    }

    public static class AuthUserRecord {
        private String username;
        private String passwordHash;
        private String salt;
        private String passwordAlgo;
        private String createdAt;
        private List<String> roles;
        private String adminLevel;
        private boolean disabled;

        public String getUsername() {
            return username;
        }

        public void setUsername(String username) {
            this.username = username;
        }

        public String getPasswordHash() {
            return passwordHash;
        }

        public void setPasswordHash(String passwordHash) {
            this.passwordHash = passwordHash;
        }

        public String getSalt() {
            return salt;
        }

        public void setSalt(String salt) {
            this.salt = salt;
        }

        public String getCreatedAt() {
            return createdAt;
        }

        public void setCreatedAt(String createdAt) {
            this.createdAt = createdAt;
        }

        public String getPasswordAlgo() {
            return passwordAlgo;
        }

        public void setPasswordAlgo(String passwordAlgo) {
            this.passwordAlgo = passwordAlgo;
        }

        public List<String> getRoles() {
            return roles;
        }

        public void setRoles(List<String> roles) {
            this.roles = roles;
        }

        public String getAdminLevel() {
            return adminLevel;
        }

        public void setAdminLevel(String adminLevel) {
            this.adminLevel = adminLevel;
        }

        public boolean isDisabled() {
            return disabled;
        }

        public void setDisabled(boolean disabled) {
            this.disabled = disabled;
        }
    }

    public static class PasswordResetRequest {
        private String id;
        private String username;
        private String roleHint;
        private String reason;
        private String contact;
        private String status;
        private String createdAt;
        private String resolvedAt;
        private String resolvedBy;
        private String tempPassword;

        public String getId() { return id; }
        public void setId(String id) { this.id = id; }
        public String getUsername() { return username; }
        public void setUsername(String username) { this.username = username; }
        public String getRoleHint() { return roleHint; }
        public void setRoleHint(String roleHint) { this.roleHint = roleHint; }
        public String getReason() { return reason; }
        public void setReason(String reason) { this.reason = reason; }
        public String getContact() { return contact; }
        public void setContact(String contact) { this.contact = contact; }
        public String getStatus() { return status; }
        public void setStatus(String status) { this.status = status; }
        public String getCreatedAt() { return createdAt; }
        public void setCreatedAt(String createdAt) { this.createdAt = createdAt; }
        public String getResolvedAt() { return resolvedAt; }
        public void setResolvedAt(String resolvedAt) { this.resolvedAt = resolvedAt; }
        public String getResolvedBy() { return resolvedBy; }
        public void setResolvedBy(String resolvedBy) { this.resolvedBy = resolvedBy; }
        public String getTempPassword() { return tempPassword; }
        public void setTempPassword(String tempPassword) { this.tempPassword = tempPassword; }
    }

    public static class AdminAuditEntry {
        private String id;
        private String actor;
        private String action;
        private String target;
        private String detail;
        private String createdAt;

        public String getId() { return id; }
        public void setId(String id) { this.id = id; }
        public String getActor() { return actor; }
        public void setActor(String actor) { this.actor = actor; }
        public String getAction() { return action; }
        public void setAction(String action) { this.action = action; }
        public String getTarget() { return target; }
        public void setTarget(String target) { this.target = target; }
        public String getDetail() { return detail; }
        public void setDetail(String detail) { this.detail = detail; }
        public String getCreatedAt() { return createdAt; }
        public void setCreatedAt(String createdAt) { this.createdAt = createdAt; }
    }

    public static class SessionRecord {
        private String username;
        private String loginAt;
        private String expireAt;
        private String activeRole;

        public String getUsername() {
            return username;
        }

        public void setUsername(String username) {
            this.username = username;
        }

        public String getLoginAt() {
            return loginAt;
        }

        public void setLoginAt(String loginAt) {
            this.loginAt = loginAt;
        }

        public String getExpireAt() {
            return expireAt;
        }

        public Instant expireAtInstant() {
            if (expireAt == null || expireAt.trim().isEmpty()) {
                return Instant.EPOCH;
            }
            return Instant.parse(expireAt);
        }

        public void setExpireAt(String expireAt) {
            this.expireAt = expireAt;
        }

        public String getActiveRole() {
            return activeRole;
        }

        public void setActiveRole(String activeRole) {
            this.activeRole = activeRole;
        }
    }

    public static class AuthException extends RuntimeException {
        public AuthException(String message) {
            super(message);
        }
    }
}
