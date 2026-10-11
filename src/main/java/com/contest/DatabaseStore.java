package com.contest;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import org.flywaydb.core.Flyway;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.annotation.PreDestroy;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Component
public class DatabaseStore {

    private static final Logger log = LoggerFactory.getLogger(DatabaseStore.class);

    @Value("${app.storage:mysql}")
    private String storageMode;

    @Value("${app.mysql.url:jdbc:mysql://127.0.0.1:3306/zhike_gongsheng?useUnicode=true&characterEncoding=utf8&serverTimezone=Asia/Shanghai&useSSL=false&allowPublicKeyRetrieval=true}")
    private String url;

    @Value("${app.mysql.username:root}")
    private String username;

    @Value("${app.mysql.password:}")
    private String password;

    @Value("${app.mysql.pool.maximum-pool-size:10}")
    private int maximumPoolSize;

    @Value("${app.mysql.pool.minimum-idle:1}")
    private int minimumIdle;

    @Value("${app.mysql.pool.connection-timeout-ms:5000}")
    private long connectionTimeoutMs;

    @Value("${app.mysql.pool.idle-timeout-ms:600000}")
    private long idleTimeoutMs;

    @Value("${app.mysql.pool.max-lifetime-ms:1800000}")
    private long maxLifetimeMs;

    private volatile HikariDataSource dataSource;
    private volatile boolean schemaInitialized;

    public boolean isEnabled() {
        return "mysql".equalsIgnoreCase(storageMode);
    }

    public synchronized void configureForCli(String jdbcUrl, String databaseUsername, String databasePassword) {
        close();
        dataSource = null;
        schemaInitialized = false;
        storageMode = "mysql";
        url = jdbcUrl;
        username = databaseUsername;
        password = databasePassword;
    }

    public synchronized void markSchemaInitializedForCli() {
        schemaInitialized = true;
    }

    public Connection connection() throws SQLException {
        return getDataSource().getConnection();
    }

    @PreDestroy
    public void close() {
        HikariDataSource current = dataSource;
        if (current != null) {
            current.close();
        }
    }

    private HikariDataSource getDataSource() {
        HikariDataSource current = dataSource;
        if (current != null) {
            return current;
        }
        synchronized (this) {
            if (dataSource == null) {
                HikariConfig config = new HikariConfig();
                config.setJdbcUrl(url);
                config.setUsername(username);
                config.setPassword(password == null ? "" : password);
                config.setPoolName("ai-teacher-mysql");
                config.setMaximumPoolSize(Math.max(1, maximumPoolSize));
                config.setMinimumIdle(Math.max(0, Math.min(minimumIdle, Math.max(1, maximumPoolSize))));
                config.setConnectionTimeout(Math.max(1000, connectionTimeoutMs));
                config.setIdleTimeout(Math.max(10000, idleTimeoutMs));
                config.setMaxLifetime(Math.max(30000, maxLifetimeMs));
                dataSource = new HikariDataSource(config);
            }
            return dataSource;
        }
    }

    public synchronized void initSchema() throws SQLException {
        if (schemaInitialized) {
            return;
        }
        try {
            Flyway.configure()
                    .dataSource(getDataSource())
                    .locations("classpath:db/migration")
                    .baselineOnMigrate(true)
                    .load()
                    .migrate();
            schemaInitialized = true;
        } catch (RuntimeException e) {
            log.error("数据库迁移失败，已停止使用 MySQL 存储", e);
            SQLException sqlException = new SQLException("数据库迁移失败", e);
            throw sqlException;
        }
    }

    public Map<String, AuthService.AuthUserRecord> loadUsers() throws SQLException {
        Map<String, AuthService.AuthUserRecord> users = new LinkedHashMap<>();
        try (Connection conn = connection();
             PreparedStatement ps = conn.prepareStatement("SELECT username,password_hash,salt,password_algo,admin_level,created_at FROM auth_users ORDER BY username");
             ResultSet rs = ps.executeQuery()) {
            while (rs.next()) {
                AuthService.AuthUserRecord record = new AuthService.AuthUserRecord();
                String user = rs.getString("username");
                record.setUsername(user);
                record.setPasswordHash(rs.getString("password_hash"));
                record.setSalt(rs.getString("salt"));
                record.setPasswordAlgo(rs.getString("password_algo"));
                record.setAdminLevel(rs.getString("admin_level"));
                record.setCreatedAt(rs.getString("created_at"));
                record.setRoles(new ArrayList<>());
                users.put(user, record);
            }
        }
        try (Connection conn = connection();
             PreparedStatement ps = conn.prepareStatement("SELECT username,role FROM auth_user_roles ORDER BY username,role");
             ResultSet rs = ps.executeQuery()) {
            while (rs.next()) {
                AuthService.AuthUserRecord record = users.get(rs.getString("username"));
                if (record != null) {
                    record.getRoles().add(rs.getString("role"));
                }
            }
        }
        return users;
    }

    public void saveUsers(Map<String, AuthService.AuthUserRecord> users) throws SQLException {
        try (Connection conn = connection()) {
            conn.setAutoCommit(false);
            try (PreparedStatement userPs = conn.prepareStatement("INSERT INTO auth_users(username,password_hash,salt,password_algo,admin_level,created_at) VALUES(?,?,?,?,?,?) ON DUPLICATE KEY UPDATE password_hash=VALUES(password_hash), salt=VALUES(salt), password_algo=VALUES(password_algo), admin_level=VALUES(admin_level), created_at=VALUES(created_at)");
                 PreparedStatement deleteRolePs = conn.prepareStatement("DELETE FROM auth_user_roles WHERE username=?");
                 PreparedStatement rolePs = conn.prepareStatement("INSERT INTO auth_user_roles(username,role) VALUES(?,?)")) {
                List<String> usernames = new ArrayList<>();
                for (AuthService.AuthUserRecord record : users.values()) {
                    usernames.add(record.getUsername());

                    bindUser(userPs, record);
                    userPs.addBatch();

                    deleteRolePs.setString(1, record.getUsername());
                    deleteRolePs.addBatch();

                    for (String role : safeList(record.getRoles())) {
                        rolePs.setString(1, record.getUsername());
                        rolePs.setString(2, role);
                        rolePs.addBatch();
                    }
                }
                userPs.executeBatch();
                deleteRolePs.executeBatch();
                rolePs.executeBatch();
                deleteRowsNotIn(conn, "auth_users", "username", usernames);
                conn.commit();
            } catch (SQLException e) {
                rollbackQuietly(conn);
                throw e;
            }
        }
    }

    public Map<String, AuthService.SessionRecord> loadSessions() throws SQLException {
        Map<String, AuthService.SessionRecord> sessions = new LinkedHashMap<>();
        try (Connection conn = connection();
             PreparedStatement ps = conn.prepareStatement("SELECT session_id,username,login_at,expire_at,active_role FROM auth_sessions ORDER BY login_at DESC");
             ResultSet rs = ps.executeQuery()) {
            while (rs.next()) {
                AuthService.SessionRecord record = new AuthService.SessionRecord();
                record.setUsername(rs.getString("username"));
                record.setLoginAt(rs.getString("login_at"));
                record.setExpireAt(rs.getString("expire_at"));
                record.setActiveRole(rs.getString("active_role"));
                sessions.put(rs.getString("session_id"), record);
            }
        }
        return sessions;
    }

    public void saveSessions(Map<String, AuthService.SessionRecord> sessions) throws SQLException {
        try (Connection conn = connection()) {
            conn.setAutoCommit(false);
            try (PreparedStatement ps = conn.prepareStatement("INSERT INTO auth_sessions(session_id,username,login_at,expire_at,active_role) VALUES(?,?,?,?,?) ON DUPLICATE KEY UPDATE username=VALUES(username), login_at=VALUES(login_at), expire_at=VALUES(expire_at), active_role=VALUES(active_role)")) {
                List<String> sessionIds = new ArrayList<>();
                for (Map.Entry<String, AuthService.SessionRecord> entry : sessions.entrySet()) {
                    AuthService.SessionRecord record = entry.getValue();
                    sessionIds.add(entry.getKey());
                    ps.setString(1, entry.getKey());
                    ps.setString(2, record.getUsername());
                    ps.setString(3, record.getLoginAt());
                    ps.setString(4, record.getExpireAt());
                    ps.setString(5, record.getActiveRole());
                    ps.addBatch();
                }
                ps.executeBatch();
                deleteRowsNotIn(conn, "auth_sessions", "session_id", sessionIds);
                conn.commit();
            } catch (SQLException e) {
                rollbackQuietly(conn);
                throw e;
            }
        }
    }

    public Map<String, ProjectService.ProjectRecord> loadProjects() throws SQLException {
        Map<String, ProjectService.ProjectRecord> projects = new LinkedHashMap<>();
        try (Connection conn = connection();
             PreparedStatement ps = conn.prepareStatement("SELECT * FROM projects ORDER BY updated_at DESC");
             ResultSet rs = ps.executeQuery()) {
            while (rs.next()) {
                ProjectService.ProjectRecord record = new ProjectService.ProjectRecord();
                record.setId(rs.getString("id"));
                record.setUsername(rs.getString("username"));
                record.setName(rs.getString("name"));
                record.setMeta(rs.getString("meta"));
                record.setCreatedAt(rs.getString("created_at"));
                record.setUpdatedAt(rs.getString("updated_at"));
                record.setPptRawText(rs.getString("ppt_raw_text"));
                record.setScript(rs.getString("script"));
                record.setSummary(rs.getString("summary"));
                record.setPublished(rs.getBoolean("published"));
                record.setPublishedAt(rs.getString("published_at"));
                record.setLessonTitle(rs.getString("lesson_title"));
                record.setLessonIntro(rs.getString("lesson_intro"));
                record.setAudioUrl(rs.getString("audio_url"));
                record.setDigitalUrl(rs.getString("digital_url"));
                record.setSubjectMode(rs.getString("subject_mode"));
                record.setCourseType(rs.getString("course_type"));
                record.setProgrammingLanguage(rs.getString("programming_language"));
                record.setTeachingGoal(rs.getString("teaching_goal"));
                record.setResources(new ArrayList<>());
                record.setLearningRecords(new ArrayList<>());
                record.setLabTasks(new ArrayList<>());
                record.setCodeSubmissions(new ArrayList<>());
                projects.put(record.getId(), record);
            }
        }
        try (Connection conn = connection();
             PreparedStatement ps = conn.prepareStatement("SELECT * FROM project_resources ORDER BY created_at ASC");
             ResultSet rs = ps.executeQuery()) {
            while (rs.next()) {
                ProjectService.ProjectRecord project = projects.get(rs.getString("project_id"));
                if (project == null) {
                    continue;
                }
                ProjectService.ProjectResource resource = new ProjectService.ProjectResource();
                resource.setId(rs.getString("id"));
                resource.setResourceType(rs.getString("resource_type"));
                resource.setFileName(rs.getString("file_name"));
                resource.setLanguage(rs.getString("language"));
                resource.setRawContent(rs.getString("raw_content"));
                resource.setStructuredContent(rs.getString("structured_content"));
                resource.setCreatedAt(rs.getString("created_at"));
                project.getResources().add(resource);
            }
        }
        try (Connection conn = connection();
             PreparedStatement ps = conn.prepareStatement("SELECT * FROM learning_records ORDER BY created_at ASC");
             ResultSet rs = ps.executeQuery()) {
            while (rs.next()) {
                ProjectService.ProjectRecord project = projects.get(rs.getString("project_id"));
                if (project == null) {
                    continue;
                }
                ProjectService.LearningRecord record = new ProjectService.LearningRecord();
                record.setId(rs.getString("id"));
                record.setLearnerUsername(rs.getString("learner_username"));
                record.setCurrentSectionId(rs.getString("current_section_id"));
                record.setProgressPercent(rs.getDouble("progress_percent"));
                record.setQuestion(rs.getString("question"));
                record.setAnswer(rs.getString("answer"));
                record.setUnderstandingLevel(rs.getString("understanding_level"));
                record.setAction(rs.getString("action"));
                record.setQuestionType(rs.getString("question_type"));
                record.setResourceId(rs.getString("resource_id"));
                record.setErrorType(rs.getString("error_type"));
                record.setHintLevel(rs.getString("hint_level"));
                record.setResolved(rs.getBoolean("resolved"));
                record.setCreatedAt(rs.getString("created_at"));
                project.getLearningRecords().add(record);
            }
        }
        Map<String, ProjectService.LabTask> tasks = new LinkedHashMap<>();
        try (Connection conn = connection();
             PreparedStatement ps = conn.prepareStatement("SELECT * FROM lab_tasks ORDER BY created_at ASC");
             ResultSet rs = ps.executeQuery()) {
            while (rs.next()) {
                ProjectService.ProjectRecord project = projects.get(rs.getString("project_id"));
                if (project == null) continue;
                ProjectService.LabTask task = new ProjectService.LabTask();
                task.setId(rs.getString("id"));
                task.setTitle(rs.getString("title"));
                task.setDescription(rs.getString("description"));
                task.setLanguage(rs.getString("language"));
                task.setJudgeMode(rs.getString("judge_mode"));
                task.setStarterCode(rs.getString("starter_code"));
                task.setSampleInput(rs.getString("sample_input"));
                task.setSampleOutput(rs.getString("sample_output"));
                task.setTimeLimitMs(rs.getInt("time_limit_ms"));
                task.setPublished(rs.getBoolean("published"));
                task.setCreatedAt(rs.getString("created_at"));
                task.setTestCases(new ArrayList<>());
                project.getLabTasks().add(task);
                tasks.put(task.getId(), task);
            }
        }
        try (Connection conn = connection();
             PreparedStatement ps = conn.prepareStatement("SELECT * FROM lab_test_cases ORDER BY task_id,sort_order");
             ResultSet rs = ps.executeQuery()) {
            while (rs.next()) {
                ProjectService.LabTask task = tasks.get(rs.getString("task_id"));
                if (task == null) continue;
                ProjectService.LabTestCase testCase = new ProjectService.LabTestCase();
                testCase.setId(rs.getString("id"));
                testCase.setInputText(rs.getString("input_text"));
                testCase.setExpectedOutput(rs.getString("expected_output"));
                testCase.setSortOrder(rs.getInt("sort_order"));
                task.getTestCases().add(testCase);
            }
        }
        try (Connection conn = connection();
             PreparedStatement ps = conn.prepareStatement("SELECT * FROM code_submissions ORDER BY created_at ASC");
             ResultSet rs = ps.executeQuery()) {
            while (rs.next()) {
                ProjectService.ProjectRecord project = projects.get(rs.getString("project_id"));
                if (project == null) continue;
                ProjectService.CodeSubmission submission = new ProjectService.CodeSubmission();
                submission.setId(rs.getString("id"));
                submission.setTaskId(rs.getString("task_id"));
                submission.setLearnerUsername(rs.getString("learner_username"));
                submission.setLanguage(rs.getString("language"));
                submission.setSourceCode(rs.getString("source_code"));
                submission.setStatus(rs.getString("status"));
                submission.setScore(rs.getInt("score"));
                submission.setPassedCases(rs.getInt("passed_cases"));
                submission.setTotalCases(rs.getInt("total_cases"));
                submission.setOutputText(rs.getString("output_text"));
                submission.setErrorText(rs.getString("error_text"));
                submission.setDurationMs(rs.getLong("duration_ms"));
                submission.setCreatedAt(rs.getString("created_at"));
                project.getCodeSubmissions().add(submission);
            }
        }
        return projects;
    }

    public void saveProjects(Map<String, ProjectService.ProjectRecord> projects) throws SQLException {
        try (Connection conn = connection()) {
            conn.setAutoCommit(false);
            try (PreparedStatement projectPs = conn.prepareStatement("INSERT INTO projects(id,username,name,meta,created_at,updated_at,ppt_raw_text,script,summary,published,published_at,lesson_title,lesson_intro,audio_url,digital_url,subject_mode,course_type,programming_language,teaching_goal) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON DUPLICATE KEY UPDATE username=VALUES(username), name=VALUES(name), meta=VALUES(meta), created_at=VALUES(created_at), updated_at=VALUES(updated_at), ppt_raw_text=VALUES(ppt_raw_text), script=VALUES(script), summary=VALUES(summary), published=VALUES(published), published_at=VALUES(published_at), lesson_title=VALUES(lesson_title), lesson_intro=VALUES(lesson_intro), audio_url=VALUES(audio_url), digital_url=VALUES(digital_url), subject_mode=VALUES(subject_mode), course_type=VALUES(course_type), programming_language=VALUES(programming_language), teaching_goal=VALUES(teaching_goal)");
                 PreparedStatement deleteResourcePs = conn.prepareStatement("DELETE FROM project_resources WHERE project_id=?");
                 PreparedStatement resourcePs = conn.prepareStatement("INSERT INTO project_resources(id,project_id,resource_type,file_name,language,raw_content,structured_content,created_at) VALUES(?,?,?,?,?,?,?,?) ON DUPLICATE KEY UPDATE resource_type=VALUES(resource_type), file_name=VALUES(file_name), language=VALUES(language), raw_content=VALUES(raw_content), structured_content=VALUES(structured_content), created_at=VALUES(created_at)");
                 PreparedStatement deleteLearningPs = conn.prepareStatement("DELETE FROM learning_records WHERE project_id=?");
                 PreparedStatement learningPs = conn.prepareStatement("INSERT INTO learning_records(id,project_id,learner_username,current_section_id,progress_percent,question,answer,understanding_level,action,question_type,resource_id,error_type,hint_level,resolved,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON DUPLICATE KEY UPDATE learner_username=VALUES(learner_username), current_section_id=VALUES(current_section_id), progress_percent=VALUES(progress_percent), question=VALUES(question), answer=VALUES(answer), understanding_level=VALUES(understanding_level), action=VALUES(action), question_type=VALUES(question_type), resource_id=VALUES(resource_id), error_type=VALUES(error_type), hint_level=VALUES(hint_level), resolved=VALUES(resolved), created_at=VALUES(created_at)")) {
                List<String> projectIds = new ArrayList<>();
                for (ProjectService.ProjectRecord record : projects.values()) {
                    projectIds.add(record.getId());

                    bindProject(projectPs, record);
                    projectPs.addBatch();

                    deleteResourcePs.setString(1, record.getId());
                    deleteResourcePs.addBatch();
                    for (ProjectService.ProjectResource resource : safeList(record.getResources())) {
                        bindProjectResource(resourcePs, record.getId(), resource);
                        resourcePs.addBatch();
                    }

                    deleteLearningPs.setString(1, record.getId());
                    deleteLearningPs.addBatch();

                    for (ProjectService.LearningRecord item : safeList(record.getLearningRecords())) {
                        bindLearningRecord(learningPs, record.getId(), item);
                        learningPs.addBatch();
                    }
                }
                deleteRowsNotIn(conn, "projects", "id", projectIds);
                projectPs.executeBatch();
                deleteResourcePs.executeBatch();
                resourcePs.executeBatch();
                deleteLearningPs.executeBatch();
                learningPs.executeBatch();
                replaceLabData(conn, projects);
                conn.commit();
            } catch (SQLException e) {
                rollbackQuietly(conn);
                throw e;
            }
        }
    }

    public void upsertProject(ProjectService.ProjectRecord record) throws SQLException {
        try (Connection conn = connection()) {
            conn.setAutoCommit(false);
            try (PreparedStatement projectPs = conn.prepareStatement("INSERT INTO projects(id,username,name,meta,created_at,updated_at,ppt_raw_text,script,summary,published,published_at,lesson_title,lesson_intro,audio_url,digital_url,subject_mode,course_type,programming_language,teaching_goal) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON DUPLICATE KEY UPDATE username=VALUES(username), name=VALUES(name), meta=VALUES(meta), created_at=VALUES(created_at), updated_at=VALUES(updated_at), ppt_raw_text=VALUES(ppt_raw_text), script=VALUES(script), summary=VALUES(summary), published=VALUES(published), published_at=VALUES(published_at), lesson_title=VALUES(lesson_title), lesson_intro=VALUES(lesson_intro), audio_url=VALUES(audio_url), digital_url=VALUES(digital_url), subject_mode=VALUES(subject_mode), course_type=VALUES(course_type), programming_language=VALUES(programming_language), teaching_goal=VALUES(teaching_goal)");
                 PreparedStatement deletePs = conn.prepareStatement("DELETE FROM project_resources WHERE project_id=?");
                 PreparedStatement insertPs = conn.prepareStatement("INSERT INTO project_resources(id,project_id,resource_type,file_name,language,raw_content,structured_content,created_at) VALUES(?,?,?,?,?,?,?,?)")) {
                bindProject(projectPs, record);
                projectPs.executeUpdate();
                replaceProjectResources(conn, deletePs, insertPs, record.getId(), record.getResources());
                conn.commit();
            } catch (SQLException e) {
                rollbackQuietly(conn);
                throw e;
            }
        }
    }

    public void deleteProject(String projectId) throws SQLException {
        try (Connection conn = connection();
             PreparedStatement ps = conn.prepareStatement("DELETE FROM projects WHERE id=?")) {
            ps.setString(1, projectId);
            ps.executeUpdate();
        }
    }

    public void insertLearningRecord(
            String projectId,
            String projectUpdatedAt,
            ProjectService.LearningRecord item
    ) throws SQLException {
        try (Connection conn = connection()) {
            conn.setAutoCommit(false);
            try (PreparedStatement projectPs = conn.prepareStatement("UPDATE projects SET updated_at=? WHERE id=?");
                 PreparedStatement learningPs = conn.prepareStatement("INSERT INTO learning_records(id,project_id,learner_username,current_section_id,progress_percent,question,answer,understanding_level,action,question_type,resource_id,error_type,hint_level,resolved,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON DUPLICATE KEY UPDATE learner_username=VALUES(learner_username), current_section_id=VALUES(current_section_id), progress_percent=VALUES(progress_percent), question=VALUES(question), answer=VALUES(answer), understanding_level=VALUES(understanding_level), action=VALUES(action), question_type=VALUES(question_type), resource_id=VALUES(resource_id), error_type=VALUES(error_type), hint_level=VALUES(hint_level), resolved=VALUES(resolved), created_at=VALUES(created_at)")) {
                projectPs.setString(1, projectUpdatedAt);
                projectPs.setString(2, projectId);
                projectPs.executeUpdate();
                bindLearningRecord(learningPs, projectId, item);
                learningPs.executeUpdate();
                conn.commit();
            } catch (SQLException e) {
                rollbackQuietly(conn);
                throw e;
            }
        }
    }

    public void upsertLabTask(
            String projectId,
            String projectUpdatedAt,
            ProjectService.LabTask task
    ) throws SQLException {
        try (Connection conn = connection()) {
            conn.setAutoCommit(false);
            try (PreparedStatement projectPs = conn.prepareStatement("UPDATE projects SET updated_at=? WHERE id=?");
                 PreparedStatement taskPs = conn.prepareStatement("INSERT INTO lab_tasks(id,project_id,title,description,language,judge_mode,starter_code,sample_input,sample_output,time_limit_ms,published,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON DUPLICATE KEY UPDATE title=VALUES(title),description=VALUES(description),language=VALUES(language),judge_mode=VALUES(judge_mode),starter_code=VALUES(starter_code),sample_input=VALUES(sample_input),sample_output=VALUES(sample_output),time_limit_ms=VALUES(time_limit_ms),published=VALUES(published)");
                 PreparedStatement deleteCasesPs = conn.prepareStatement("DELETE FROM lab_test_cases WHERE task_id=?");
                 PreparedStatement casePs = conn.prepareStatement("INSERT INTO lab_test_cases(id,task_id,input_text,expected_output,sort_order) VALUES(?,?,?,?,?)")) {
                projectPs.setString(1, projectUpdatedAt);
                projectPs.setString(2, projectId);
                projectPs.executeUpdate();
                bindLabTask(taskPs, projectId, task);
                taskPs.executeUpdate();
                deleteCasesPs.setString(1, task.getId());
                deleteCasesPs.executeUpdate();
                for (ProjectService.LabTestCase testCase : safeList(task.getTestCases())) {
                    bindLabTestCase(casePs, task.getId(), testCase);
                    casePs.addBatch();
                }
                casePs.executeBatch();
                conn.commit();
            } catch (SQLException e) {
                rollbackQuietly(conn);
                throw e;
            }
        }
    }

    public void insertCodeSubmission(
            String projectId,
            String projectUpdatedAt,
            ProjectService.CodeSubmission submission
    ) throws SQLException {
        try (Connection conn = connection()) {
            conn.setAutoCommit(false);
            try (PreparedStatement projectPs = conn.prepareStatement("UPDATE projects SET updated_at=? WHERE id=?");
                 PreparedStatement submissionPs = conn.prepareStatement("INSERT INTO code_submissions(id,project_id,task_id,learner_username,language,source_code,status,score,passed_cases,total_cases,output_text,error_text,duration_ms,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)")) {
                projectPs.setString(1, projectUpdatedAt);
                projectPs.setString(2, projectId);
                projectPs.executeUpdate();
                bindCodeSubmission(submissionPs, projectId, submission);
                submissionPs.executeUpdate();
                conn.commit();
            } catch (SQLException e) {
                rollbackQuietly(conn);
                throw e;
            }
        }
    }

    public void deleteLabTask(String projectId, String projectUpdatedAt, String taskId) throws SQLException {
        try (Connection conn = connection()) {
            conn.setAutoCommit(false);
            try (PreparedStatement projectPs = conn.prepareStatement("UPDATE projects SET updated_at=? WHERE id=?");
                 PreparedStatement taskPs = conn.prepareStatement("DELETE FROM lab_tasks WHERE id=? AND project_id=?")) {
                projectPs.setString(1, projectUpdatedAt);
                projectPs.setString(2, projectId);
                projectPs.executeUpdate();
                taskPs.setString(1, taskId);
                taskPs.setString(2, projectId);
                taskPs.executeUpdate();
                conn.commit();
            } catch (SQLException e) {
                rollbackQuietly(conn);
                throw e;
            }
        }
    }

    private void bindProject(PreparedStatement ps, ProjectService.ProjectRecord record) throws SQLException {
        ps.setString(1, record.getId());
        ps.setString(2, record.getUsername());
        ps.setString(3, record.getName());
        ps.setString(4, record.getMeta());
        ps.setString(5, record.getCreatedAt());
        ps.setString(6, record.getUpdatedAt());
        ps.setString(7, record.getPptRawText());
        ps.setString(8, record.getScript());
        ps.setString(9, record.getSummary());
        ps.setBoolean(10, record.isPublished());
        ps.setString(11, record.getPublishedAt());
        ps.setString(12, record.getLessonTitle());
        ps.setString(13, record.getLessonIntro());
        ps.setString(14, record.getAudioUrl());
        ps.setString(15, record.getDigitalUrl());
        ps.setString(16, record.getSubjectMode());
        ps.setString(17, record.getCourseType());
        ps.setString(18, record.getProgrammingLanguage());
        ps.setString(19, record.getTeachingGoal());
    }

    private void bindUser(PreparedStatement ps, AuthService.AuthUserRecord record) throws SQLException {
        ps.setString(1, record.getUsername());
        ps.setString(2, record.getPasswordHash());
        ps.setString(3, nullToEmpty(record.getSalt()));
        ps.setString(4, nullToEmpty(record.getPasswordAlgo()));
        ps.setString(5, nullToEmpty(record.getAdminLevel()));
        ps.setString(6, nullToEmpty(record.getCreatedAt()));
    }

    private void bindLearningRecord(PreparedStatement ps, String projectId, ProjectService.LearningRecord item) throws SQLException {
        ps.setString(1, item.getId());
        ps.setString(2, projectId);
        ps.setString(3, item.getLearnerUsername());
        ps.setString(4, item.getCurrentSectionId());
        ps.setDouble(5, item.getProgressPercent());
        ps.setString(6, item.getQuestion());
        ps.setString(7, item.getAnswer());
        ps.setString(8, item.getUnderstandingLevel());
        ps.setString(9, item.getAction());
        ps.setString(10, item.getQuestionType());
        ps.setString(11, item.getResourceId());
        ps.setString(12, item.getErrorType());
        ps.setString(13, item.getHintLevel());
        ps.setBoolean(14, item.isResolved());
        ps.setString(15, item.getCreatedAt());
    }

    private void replaceLabData(
            Connection conn,
            Map<String, ProjectService.ProjectRecord> projects
    ) throws SQLException {
        try (PreparedStatement deleteTasksPs = conn.prepareStatement("DELETE FROM lab_tasks WHERE project_id=?");
             PreparedStatement taskPs = conn.prepareStatement("INSERT INTO lab_tasks(id,project_id,title,description,language,judge_mode,starter_code,sample_input,sample_output,time_limit_ms,published,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)");
             PreparedStatement casePs = conn.prepareStatement("INSERT INTO lab_test_cases(id,task_id,input_text,expected_output,sort_order) VALUES(?,?,?,?,?)");
             PreparedStatement submissionPs = conn.prepareStatement("INSERT INTO code_submissions(id,project_id,task_id,learner_username,language,source_code,status,score,passed_cases,total_cases,output_text,error_text,duration_ms,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)")) {
            for (ProjectService.ProjectRecord project : projects.values()) {
                deleteTasksPs.setString(1, project.getId());
                deleteTasksPs.addBatch();
            }
            deleteTasksPs.executeBatch();
            for (ProjectService.ProjectRecord project : projects.values()) {
                for (ProjectService.LabTask task : safeList(project.getLabTasks())) {
                    bindLabTask(taskPs, project.getId(), task);
                    taskPs.addBatch();
                    for (ProjectService.LabTestCase testCase : safeList(task.getTestCases())) {
                        bindLabTestCase(casePs, task.getId(), testCase);
                        casePs.addBatch();
                    }
                }
            }
            taskPs.executeBatch();
            casePs.executeBatch();
            for (ProjectService.ProjectRecord project : projects.values()) {
                for (ProjectService.CodeSubmission submission : safeList(project.getCodeSubmissions())) {
                    bindCodeSubmission(submissionPs, project.getId(), submission);
                    submissionPs.addBatch();
                }
            }
            submissionPs.executeBatch();
        }
    }

    private void bindLabTask(
            PreparedStatement ps,
            String projectId,
            ProjectService.LabTask task
    ) throws SQLException {
        ps.setString(1, task.getId());
        ps.setString(2, projectId);
        ps.setString(3, task.getTitle());
        ps.setString(4, task.getDescription());
        ps.setString(5, task.getLanguage());
        ps.setString(6, task.getJudgeMode());
        ps.setString(7, task.getStarterCode());
        ps.setString(8, task.getSampleInput());
        ps.setString(9, task.getSampleOutput());
        ps.setInt(10, task.getTimeLimitMs());
        ps.setBoolean(11, task.isPublished());
        ps.setString(12, task.getCreatedAt());
    }

    private void bindLabTestCase(
            PreparedStatement ps,
            String taskId,
            ProjectService.LabTestCase testCase
    ) throws SQLException {
        ps.setString(1, testCase.getId());
        ps.setString(2, taskId);
        ps.setString(3, testCase.getInputText());
        ps.setString(4, testCase.getExpectedOutput());
        ps.setInt(5, testCase.getSortOrder());
    }

    private void bindCodeSubmission(
            PreparedStatement ps,
            String projectId,
            ProjectService.CodeSubmission submission
    ) throws SQLException {
        ps.setString(1, submission.getId());
        ps.setString(2, projectId);
        ps.setString(3, submission.getTaskId());
        ps.setString(4, submission.getLearnerUsername());
        ps.setString(5, submission.getLanguage());
        ps.setString(6, submission.getSourceCode());
        ps.setString(7, submission.getStatus());
        ps.setInt(8, submission.getScore());
        ps.setInt(9, submission.getPassedCases());
        ps.setInt(10, submission.getTotalCases());
        ps.setString(11, submission.getOutputText());
        ps.setString(12, submission.getErrorText());
        ps.setLong(13, submission.getDurationMs());
        ps.setString(14, submission.getCreatedAt());
    }

    private void replaceProjectResources(
            Connection conn,
            PreparedStatement deletePs,
            PreparedStatement insertPs,
            String projectId,
            List<ProjectService.ProjectResource> resources
    ) throws SQLException {
        deletePs.setString(1, projectId);
        deletePs.executeUpdate();
        for (ProjectService.ProjectResource resource : safeList(resources)) {
            bindProjectResource(insertPs, projectId, resource);
            insertPs.addBatch();
        }
        insertPs.executeBatch();
    }

    private void bindProjectResource(
            PreparedStatement ps,
            String projectId,
            ProjectService.ProjectResource resource
    ) throws SQLException {
        ps.setString(1, resource.getId());
        ps.setString(2, projectId);
        ps.setString(3, resource.getResourceType());
        ps.setString(4, resource.getFileName());
        ps.setString(5, resource.getLanguage());
        ps.setString(6, resource.getRawContent());
        ps.setString(7, resource.getStructuredContent());
        ps.setString(8, resource.getCreatedAt());
    }

    private static String nullToEmpty(String value) {
        return value == null ? "" : value;
    }

    private static void rollbackQuietly(Connection conn) {
        try {
            conn.rollback();
        } catch (SQLException ignored) {
            // Keep the original database error visible to the caller.
        }
    }

    private static void deleteRowsNotIn(Connection conn, String table, String column, List<String> keepValues) throws SQLException {
        // 空 keep 列表表示「本次没有可同步的主键」，绝不能理解为「清空整表」。
        // 旧逻辑 DELETE FROM table 会在进程空载启动时把全部项目/用户删光，导致工作台「项目不存在」。
        if (keepValues == null || keepValues.isEmpty()) {
            log.warn("skip mass-delete on empty keep-list: table={}", table);
            return;
        }

        StringBuilder sql = new StringBuilder("DELETE FROM ");
        sql.append(table).append(" WHERE ").append(column).append(" NOT IN (");
        for (int i = 0; i < keepValues.size(); i++) {
            if (i > 0) {
                sql.append(",");
            }
            sql.append("?");
        }
        sql.append(")");

        try (PreparedStatement ps = conn.prepareStatement(sql.toString())) {
            for (int i = 0; i < keepValues.size(); i++) {
                ps.setString(i + 1, keepValues.get(i));
            }
            ps.executeUpdate();
        }
    }

    private static <T> List<T> safeList(List<T> items) {
        return items == null ? new ArrayList<>() : items;
    }
}
