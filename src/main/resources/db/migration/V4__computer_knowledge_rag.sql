CREATE TABLE IF NOT EXISTS knowledge_documents (
    id VARCHAR(120) PRIMARY KEY,
    course_code VARCHAR(64) NOT NULL,
    title VARCHAR(500) NOT NULL,
    source_url TEXT NOT NULL,
    source_type VARCHAR(32) NOT NULL DEFAULT 'official',
    publisher VARCHAR(255),
    version_label VARCHAR(255),
    license_name VARCHAR(255),
    license_url TEXT,
    quality_tier VARCHAR(32) NOT NULL DEFAULT 'official',
    quality_score INT NOT NULL DEFAULT 90,
    source_updated_at VARCHAR(64),
    fetched_at VARCHAR(64),
    checksum_sha256 VARCHAR(64) NOT NULL,
    local_path TEXT,
    content_format VARCHAR(32),
    active TINYINT(1) NOT NULL DEFAULT 1,
    created_at VARCHAR(64),
    updated_at VARCHAR(64),
    INDEX idx_knowledge_documents_course(course_code, active),
    INDEX idx_knowledge_documents_quality(quality_score),
    INDEX idx_knowledge_documents_checksum(checksum_sha256)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id VARCHAR(120) PRIMARY KEY,
    document_id VARCHAR(120) NOT NULL,
    course_code VARCHAR(64) NOT NULL,
    chunk_type VARCHAR(32) NOT NULL,
    section_title VARCHAR(500),
    chunk_index INT NOT NULL,
    content LONGTEXT NOT NULL,
    search_text LONGTEXT,
    token_count INT NOT NULL DEFAULT 0,
    quality_score INT NOT NULL DEFAULT 90,
    active TINYINT(1) NOT NULL DEFAULT 1,
    created_at VARCHAR(64),
    INDEX idx_knowledge_chunks_course(course_code, active),
    INDEX idx_knowledge_chunks_document(document_id, active),
    INDEX idx_knowledge_chunks_type(chunk_type),
    CONSTRAINT fk_knowledge_chunks_document
        FOREIGN KEY (document_id) REFERENCES knowledge_documents(id)
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS knowledge_eval_cases (
    id VARCHAR(120) PRIMARY KEY,
    course_code VARCHAR(64) NOT NULL,
    question_type VARCHAR(32) NOT NULL,
    question TEXT NOT NULL,
    expected_keywords TEXT NOT NULL,
    expected_source_url TEXT,
    top_k INT NOT NULL DEFAULT 5,
    enabled TINYINT(1) NOT NULL DEFAULT 1,
    created_at VARCHAR(64),
    updated_at VARCHAR(64),
    INDEX idx_knowledge_eval_course(course_code, enabled),
    INDEX idx_knowledge_eval_type(question_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS knowledge_eval_runs (
    id VARCHAR(120) PRIMARY KEY,
    case_id VARCHAR(120) NOT NULL,
    passed TINYINT(1) NOT NULL,
    matched_keywords TEXT,
    top_document_id VARCHAR(120),
    top_score DOUBLE NOT NULL DEFAULT 0,
    details TEXT,
    created_at VARCHAR(64),
    INDEX idx_knowledge_eval_runs_case(case_id),
    INDEX idx_knowledge_eval_runs_created(created_at),
    CONSTRAINT fk_knowledge_eval_runs_case
        FOREIGN KEY (case_id) REFERENCES knowledge_eval_cases(id)
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
