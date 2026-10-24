"""清空演示/脏业务数据，保留管理员与系统配置，便于正式面向真实用户。

用法（在 backend 目录）:
  .\\venv\\Scripts\\python.exe scripts\\reset_for_production.py

保留:
  - 管理员账号 (user_type=3) 及其角色绑定
  - 角色 / 权限 / 菜单权限绑定
  - 资源类型定义、智能体定义、画像维度定义
  - 敏感词库、知识点目录、系统配置 (sys_config)

清空:
  - 学生/教师等非管理员用户及其画像、学习、答疑、资源、路径
  - 智能体任务/运行/LLM 日志
  - 公告、反馈、操作日志、异常日志、内容审核记录
  - uploads 下的用户上传文件
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

# 允许从 backend 根目录直接运行
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.db.init_db import init_database

settings = get_settings()

# 子表 → 父表，按依赖从深到浅删除
BUSINESS_TABLES = [
    # resources
    "res_resource_citation",
    "res_document",
    "res_mindmap",
    "res_reading",
    "res_video",
    "res_code_case",
    "res_question",
    "res_resource",
    # path
    "pth_node_progress",
    "pth_node_resource",
    "pth_path_node_edge",
    "pth_path_node",
    "pth_learning_path",
    # tutor
    "tut_tutor_message",
    "tut_tutor_session",
    # profile user data
    "usr_profile_dialogue_message",
    "usr_profile_dialogue_session",
    "usr_profile_evolution_log",
    "usr_profile_dimension_value",
    "usr_profile",
    # learning
    "lrn_behavior_event",
    "lrn_learning_session",
    "lrn_user_progress_summary",
    # agents runtime
    "agt_collaboration_log",
    "agt_llm_call_log",
    "agt_agent_run",
    "agt_task_stage",
    "agt_task",
    # security / ops noise
    "sec_content_audit",
    "sys_operation_log",
    "sys_exception_log",
    "sys_feedback",
    "sys_announcement",
]

KEEP_TABLES_HINT = [
    "sys_role",
    "sys_permission",
    "sys_role_permission",
    "sys_config",
    "res_resource_type_def",
    "agt_agent_definition",
    "usr_profile_dimension_def",
    "sec_sensitive_word",
    "pth_knowledge_point",
]


def backup_sqlite() -> Path | None:
    if not settings.use_sqlite:
        return None
    db_path = Path(settings.sqlite_path)
    if not db_path.is_absolute():
        db_path = ROOT / db_path
    if not db_path.exists():
        raise FileNotFoundError(f"数据库不存在: {db_path}")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = db_path.with_name(f"{db_path.stem}.bak_{stamp}{db_path.suffix}")
    shutil.copy2(db_path, bak)
    return bak


def existing_tables(conn) -> set[str]:
    rows = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
    return {r[0] for r in rows}


def clear_uploads() -> int:
    uploads = ROOT / "uploads"
    removed = 0
    if not uploads.exists():
        return 0
    for p in uploads.rglob("*"):
        if p.is_file():
            p.unlink(missing_ok=True)
            removed += 1
    # 清掉空目录（保留 uploads 根）
    for p in sorted(uploads.rglob("*"), reverse=True):
        if p.is_dir():
            try:
                p.rmdir()
            except OSError:
                pass
    return removed


def main() -> None:
    print("=== EduNexus 生产前数据重置 ===")
    print(f"DB: {settings.sqlite_path if settings.use_sqlite else settings.database_url}")

    bak = backup_sqlite()
    if bak:
        print(f"已备份数据库 -> {bak}")

    db = SessionLocal()
    try:
        with engine.begin() as conn:
            tables = existing_tables(conn)
            # 关闭外键以便按序清理
            conn.execute(text("PRAGMA foreign_keys = OFF"))

            for table in BUSINESS_TABLES:
                if table not in tables:
                    continue
                n = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0
                conn.execute(text(f"DELETE FROM {table}"))
                print(f"  cleared {table}: {n}")

            # 额外可能存在的配置型扩展表（有则清用户侧数据）
            for table in (
                "usr_profile_tag",
                "usr_profile_guide_question",
                "usr_profile_questionnaire",
                "usr_profile_assessment",
            ):
                if table in tables:
                    n = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0
                    # 指南题等可能是配置：若表名含 guide 且无 user_id 则跳过
                    cols = {
                        r[1]
                        for r in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
                    }
                    if "user_id" in cols or table.endswith("_assessment"):
                        conn.execute(text(f"DELETE FROM {table}"))
                        print(f"  cleared {table}: {n}")

            # 删除非管理员用户及其角色绑定
            if "sys_user" in tables:
                admin_ids = [
                    r[0]
                    for r in conn.execute(
                        text("SELECT id FROM sys_user WHERE user_type = 3 AND deleted_at IS NULL")
                    ).fetchall()
                ]
                if not admin_ids:
                    # 若没有超管，先不删任何用户，交给 init_database 重建
                    print("  warn: 未找到管理员账号，将在 init 后重建默认超管")
                else:
                    placeholders = ",".join(str(int(i)) for i in admin_ids)
                    if "sys_user_role" in tables:
                        n = conn.execute(
                            text(f"SELECT COUNT(*) FROM sys_user_role WHERE user_id NOT IN ({placeholders})")
                        ).scalar() or 0
                        conn.execute(text(f"DELETE FROM sys_user_role WHERE user_id NOT IN ({placeholders})"))
                        print(f"  cleared sys_user_role (non-admin): {n}")
                    n = conn.execute(
                        text(f"SELECT COUNT(*) FROM sys_user WHERE id NOT IN ({placeholders})")
                    ).scalar() or 0
                    conn.execute(text(f"DELETE FROM sys_user WHERE id NOT IN ({placeholders})"))
                    print(f"  cleared sys_user (non-admin): {n}")
                    # 确保管理员状态正常
                    conn.execute(
                        text(
                            f"UPDATE sys_user SET status=1, deleted_at=NULL WHERE id IN ({placeholders})"
                        )
                    )

            conn.execute(text("PRAGMA foreign_keys = ON"))

        removed_files = clear_uploads()
        print(f"  cleared upload files: {removed_files}")

        # 幂等补齐角色/权限/默认超管/配置
        init_database()
        print("已重新确保 RBAC / 默认超管 / 系统配置")

        # 汇总
        with engine.connect() as conn:
            users = conn.execute(text("SELECT id, username, user_type FROM sys_user")).fetchall()
            res = conn.execute(text("SELECT COUNT(*) FROM res_resource")).scalar()
            tasks = conn.execute(text("SELECT COUNT(*) FROM agt_task")).scalar()
            tutors = conn.execute(text("SELECT COUNT(*) FROM tut_tutor_session")).scalar()
            print("--- 重置后状态 ---")
            print(f"用户: {list(users)}")
            print(f"资源={res}, 任务={tasks}, 答疑会话={tutors}")
            print(f"保留配置表: {', '.join(KEEP_TABLES_HINT)}")
        print("完成。请用管理员账号重新登录管理端；学生需重新注册。")
    finally:
        db.close()


if __name__ == "__main__":
    main()
