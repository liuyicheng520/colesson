"""Application configuration via environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "智学体 API"
    app_version: str = "1.0.0"
    debug: bool = False
    api_prefix: str = "/api/v1"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    use_sqlite: bool = False
    sqlite_path: str = "data/edunexus.db"
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "edunexus"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    @property
    def database_url(self) -> str:
        if self.use_sqlite:
            return f"sqlite:///{self.sqlite_path}"
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    # Redis
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # JWT
    jwt_secret_key: str = "change-me-in-production-use-long-random-string"
    # 宿主桥接共享密钥：/auth/sync-student 必须携带 X-Host-Secret 头且与本值一致；为空时该接口直接拒绝
    host_bridge_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24
    jwt_refresh_token_expire_days: int = 7

    # CORS
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # Rate limit
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    # LLM providers
    llm_default_provider: Literal["qwen", "deepseek", "spark", "mock"] = "deepseek"
    llm_fallback_provider: Literal["qwen", "deepseek", "spark", "mock"] = "mock"

    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-plus"

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    spark_app_id: str = ""
    spark_api_key: str = ""
    spark_api_secret: str = ""
    spark_base_url: str = "https://spark-api-open.xf-yun.com/v1"
    spark_model: str = "generalv3.5"

    # Content safety
    content_safety_enabled: bool = True
    profile_min_completeness: float = 0.80

    # Uploads
    upload_dir: str = "uploads"

    # Web search (optional Serper key; proxy falls back to HTTP_PROXY env)
    web_search_proxy: str = ""
    serper_api_key: str = ""

    # Local vector knowledge base
    kb_enabled: bool = True
    local_kb_dir: str = ""
    vector_db_path: str = "data/vector_kb"
    kb_include_dirs: str = "01_Documents"  # 逗号分隔；留空表示索引整个目录
    kb_max_files: int = 0
    kb_top_k: int = 6
    kb_min_score: float = 0.05
    kb_embedding_provider: Literal["fastembed", "qwen"] = "fastembed"
    kb_embedding_model: str = "BAAI/bge-small-zh-v1.5"

    # 可执行文件/安装包模式：由后端直接托管 frontend/dist，避免静态站无 API 代理卡顿
    serve_frontend: bool = False
    frontend_dist: str = ""  # 空则自动解析为项目根/frontend/dist



@lru_cache
def get_settings() -> Settings:
    return Settings()
