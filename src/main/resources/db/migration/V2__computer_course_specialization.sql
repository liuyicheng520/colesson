ALTER TABLE projects
    ADD COLUMN subject_mode VARCHAR(32) NOT NULL DEFAULT 'general',
    ADD COLUMN course_type VARCHAR(64),
    ADD COLUMN programming_language VARCHAR(64),
    ADD COLUMN teaching_goal TEXT;

ALTER TABLE learning_records
    ADD COLUMN question_type VARCHAR(32),
    ADD COLUMN resource_id VARCHAR(120),
    ADD COLUMN error_type VARCHAR(120),
    ADD COLUMN hint_level VARCHAR(32),
    ADD COLUMN resolved TINYINT(1) NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS project_resources (
    id VARCHAR(120) PRIMARY KEY,
    project_id VARCHAR(120) NOT NULL,
    resource_type VARCHAR(32) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    language VARCHAR(64),
    raw_content LONGTEXT,
    structured_content TEXT,
    created_at VARCHAR(64),
    INDEX idx_project_resources_project(project_id),
    INDEX idx_project_resources_type(resource_type),
    CONSTRAINT fk_project_resources_project
        FOREIGN KEY (project_id) REFERENCES projects(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
