CREATE TABLE IF NOT EXISTS lab_tasks (
    id VARCHAR(120) PRIMARY KEY,
    project_id VARCHAR(120) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    language VARCHAR(64) NOT NULL,
    judge_mode VARCHAR(32) NOT NULL DEFAULT 'io',
    starter_code LONGTEXT,
    sample_input TEXT,
    sample_output TEXT,
    time_limit_ms INT NOT NULL DEFAULT 2000,
    published TINYINT(1) NOT NULL DEFAULT 1,
    created_at VARCHAR(64),
    INDEX idx_lab_tasks_project(project_id),
    CONSTRAINT fk_lab_tasks_project
        FOREIGN KEY (project_id) REFERENCES projects(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS lab_test_cases (
    id VARCHAR(120) PRIMARY KEY,
    task_id VARCHAR(120) NOT NULL,
    input_text TEXT,
    expected_output TEXT,
    sort_order INT NOT NULL DEFAULT 0,
    INDEX idx_lab_test_cases_task(task_id),
    CONSTRAINT fk_lab_test_cases_task
        FOREIGN KEY (task_id) REFERENCES lab_tasks(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS code_submissions (
    id VARCHAR(120) PRIMARY KEY,
    project_id VARCHAR(120) NOT NULL,
    task_id VARCHAR(120) NOT NULL,
    learner_username VARCHAR(120) NOT NULL,
    language VARCHAR(64) NOT NULL,
    source_code LONGTEXT NOT NULL,
    status VARCHAR(32) NOT NULL,
    score INT NOT NULL DEFAULT 0,
    passed_cases INT NOT NULL DEFAULT 0,
    total_cases INT NOT NULL DEFAULT 0,
    output_text TEXT,
    error_text TEXT,
    duration_ms BIGINT NOT NULL DEFAULT 0,
    created_at VARCHAR(64),
    INDEX idx_code_submissions_project(project_id),
    INDEX idx_code_submissions_task(task_id),
    INDEX idx_code_submissions_learner(learner_username),
    CONSTRAINT fk_code_submissions_project
        FOREIGN KEY (project_id) REFERENCES projects(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_code_submissions_task
        FOREIGN KEY (task_id) REFERENCES lab_tasks(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
