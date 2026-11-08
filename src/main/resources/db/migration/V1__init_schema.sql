CREATE TABLE IF NOT EXISTS auth_users (
    username VARCHAR(120) PRIMARY KEY,
    password_hash VARCHAR(255) NOT NULL,
    salt VARCHAR(255) DEFAULT '',
    password_algo VARCHAR(32) NOT NULL DEFAULT 'bcrypt',
    created_at VARCHAR(64) DEFAULT ''
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS auth_user_roles (
    username VARCHAR(120) NOT NULL,
    role VARCHAR(32) NOT NULL,
    PRIMARY KEY(username, role),
    CONSTRAINT fk_auth_user_roles_user
        FOREIGN KEY (username) REFERENCES auth_users(username)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS auth_sessions (
    session_id VARCHAR(120) PRIMARY KEY,
    username VARCHAR(120) NOT NULL,
    login_at VARCHAR(64) NOT NULL,
    expire_at VARCHAR(64) NOT NULL,
    active_role VARCHAR(32) NOT NULL,
    INDEX idx_auth_sessions_username(username),
    INDEX idx_auth_sessions_expire_at(expire_at),
    CONSTRAINT fk_auth_sessions_user
        FOREIGN KEY (username) REFERENCES auth_users(username)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS projects (
    id VARCHAR(120) PRIMARY KEY,
    username VARCHAR(120) NOT NULL,
    name VARCHAR(255) NOT NULL,
    meta TEXT,
    created_at VARCHAR(64),
    updated_at VARCHAR(64),
    ppt_raw_text LONGTEXT,
    script LONGTEXT,
    summary TEXT,
    published TINYINT(1) NOT NULL DEFAULT 0,
    published_at VARCHAR(64),
    lesson_title VARCHAR(255),
    lesson_intro TEXT,
    audio_url TEXT,
    digital_url TEXT,
    INDEX idx_projects_username(username),
    INDEX idx_projects_published(published),
    INDEX idx_projects_updated_at(updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS learning_records (
    id VARCHAR(120) PRIMARY KEY,
    project_id VARCHAR(120) NOT NULL,
    learner_username VARCHAR(120),
    current_section_id VARCHAR(120),
    progress_percent DOUBLE NOT NULL DEFAULT 0,
    question TEXT,
    answer TEXT,
    understanding_level VARCHAR(64),
    action VARCHAR(64),
    created_at VARCHAR(64),
    INDEX idx_learning_project(project_id),
    INDEX idx_learning_learner(learner_username),
    CONSTRAINT fk_learning_project
        FOREIGN KEY (project_id) REFERENCES projects(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
