"""Initialize database schema and seed data (SQLite dev / first run)."""

import logging
from decimal import Decimal
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine
import app.models  # noqa: F401 — register all ORM tables before create_all
from app.models.agent import AgtAgentDefinition
from app.models.path import PthKnowledgePoint, SecSensitiveWord
from app.models.profile import UsrProfileDimensionDef
from app.models.resource import ResResourceTypeDef
from app.models.sys import SysRole, SysUser, SysUserRole
from app.core.security import hash_password
from app.services.permission_service import PermissionService
from app.services.config_service import ConfigService
from app.services.admin_content_service import AdminProfileConfigService

logger = logging.getLogger(__name__)
settings = get_settings()

_SQLITE_USER_COLUMNS: dict[str, str] = {
    "real_name": "VARCHAR(32)",
    "student_no": "VARCHAR(32)",
    "bio": "VARCHAR(50)",
}


def _upgrade_sqlite_schema() -> None:
    """Add columns introduced after first SQLite bootstrap (create_all does not alter tables)."""
    if not settings.use_sqlite:
        return

    inspector = inspect(engine)
    if "sys_user" not in inspector.get_table_names():
        return

    existing = {col["name"] for col in inspector.get_columns("sys_user")}
    with engine.begin() as conn:
        for name, col_type in _SQLITE_USER_COLUMNS.items():
            if name in existing:
                continue
            conn.execute(text(f"ALTER TABLE sys_user ADD COLUMN {name} {col_type}"))
            logger.info("SQLite migration: added sys_user.%s", name)


def init_database() -> None:
    db_path = Path(engine.url.database or "")
    if db_path.parent and str(db_path.parent) not in (".", ""):
        db_path.parent.mkdir(parents=True, exist_ok=True)

    Base.metadata.create_all(bind=engine)
    _upgrade_sqlite_schema()
    with Session(engine) as db:
        if db.query(SysRole).count() == 0:
            _seed_roles(db)
            _seed_profile_dimensions(db)
            _seed_resource_types(db)
            _seed_agents(db)
            _seed_knowledge_points(db)
            _seed_sensitive_words(db)
            db.commit()
            logger.info("Database seeded successfully")
        _ensure_admin_rbac(db)
        ConfigService(db).seed_defaults()
        AdminProfileConfigService(db).seed_guide_questions()
        from app.services.admin_audit_service import AdminAuditService, LOG_RETENTION_DAYS

        AdminAuditService(db).purge_old_logs(days=LOG_RETENTION_DAYS)
        db.commit()
        logger.info("Database RBAC ensured")


def _ensure_admin_rbac(db: Session) -> None:
    """确保管理员角色、权限与默认超管账号存在（幂等）。"""
    extra_roles = [
        ("ROLE_SUPER_ADMIN", "超级管理员", "拥有全部后台权限"),
        ("ROLE_CONTENT_ADMIN", "内容管理员", "用户与内容审核管理"),
        ("ROLE_OPS_ADMIN", "运维管理员", "系统配置与智能体运维"),
    ]
    existing_codes = {r.role_code for r in db.query(SysRole).all()}
    for code, name, desc in extra_roles:
        if code not in existing_codes:
            db.add(SysRole(role_code=code, role_name=name, description=desc))
    db.flush()
    PermissionService(db).seed_permissions()

    super_role = db.query(SysRole).filter(SysRole.role_code == "ROLE_SUPER_ADMIN").first()
    if not super_role:
        return

    existing_super = (
        db.query(SysUser)
        .join(SysUserRole, SysUserRole.user_id == SysUser.id)
        .filter(SysUserRole.role_id == super_role.id, SysUser.user_type == 3, SysUser.deleted_at.is_(None))
        .first()
    )
    if existing_super:
        return

    default_password = "admin123"
    for username in ("admin", "superadmin", "sysadmin"):
        occupant = db.query(SysUser).filter(SysUser.username == username, SysUser.deleted_at.is_(None)).first()
        if occupant and occupant.user_type != 3:
            continue
        if occupant:
            occupant.user_type = 3
            occupant.password_hash = hash_password(default_password)
            occupant.status = 1
            db.flush()
            has_role = (
                db.query(SysUserRole)
                .filter(SysUserRole.user_id == occupant.id, SysUserRole.role_id == super_role.id)
                .first()
            )
            if not has_role:
                db.add(SysUserRole(user_id=occupant.id, role_id=super_role.id))
            logger.info("Default super admin ensured: %s / %s", username, default_password)
            return

        user = SysUser(
            username=username,
            password_hash=hash_password(default_password),
            nickname="超级管理员",
            real_name="系统管理员",
            user_type=3,
            status=1,
        )
        db.add(user)
        db.flush()
        db.add(SysUserRole(user_id=user.id, role_id=super_role.id))
        logger.info("Default super admin created: %s / %s", username, default_password)
        return


def _seed_roles(db: Session) -> None:
    for code, name, desc in [
        ("ROLE_STUDENT", "学生", "普通学生用户"),
        ("ROLE_TEACHER", "教师", "高校教师用户"),
        ("ROLE_ADMIN", "管理员", "系统管理员"),
    ]:
        db.add(SysRole(role_code=code, role_name=name, description=desc))


def _seed_profile_dimensions(db: Session) -> None:
    dims = [
        ("D1", "知识基础", "dialogue", 1),
        ("D2", "认知风格", "questionnaire", 2),
        ("D3", "学习目标", "dialogue", 3),
        ("D4", "学习历史", "behavior", 4),
        ("D5", "易错点偏好", "assessment", 5),
        ("D6", "学习节奏", "dialogue", 6),
        ("D7", "模态偏好", "behavior", 7),
        ("D8", "专业背景", "import", 8),
    ]
    for code, name, method, order in dims:
        db.add(
            UsrProfileDimensionDef(
                dimension_code=code,
                dimension_name=name,
                value_schema={"type": "object"},
                collect_method=method,
                weight=Decimal("1.0"),
                sort_order=order,
            )
        )


def _seed_resource_types(db: Session) -> None:
    types = [
        ("document", "专业课程文档", "res_document", 1),
        ("mindmap", "思维导图", "res_mindmap", 2),
        ("reading", "拓展阅读", "res_reading", 3),
        ("video", "教学视频动画", "res_video", 4),
        ("code", "代码案例", "res_code_case", 5),
        ("question", "题库测验", "res_question", 6),
    ]
    for code, name, table, order in types:
        db.add(ResResourceTypeDef(type_code=code, type_name=name, extension_table=table, sort_order=order))


def _seed_agents(db: Session) -> None:
    agents = [
        ("orchestrator", "总协调智能体", "orchestrator", "spark-pro"),
        ("learning_analysis", "学情分析智能体", "assessor", "spark-pro"),
        ("document", "课程讲义智能体", "generator", "spark-ultra"),
        ("question", "习题命题智能体", "generator", "spark-pro"),
        ("mindmap", "知识图谱智能体", "generator", "spark-pro"),
        ("extension", "拓展资源智能体", "generator", "spark-pro"),
        ("animation", "教学动画智能体", "generator", "spark-pro"),
        ("consistency", "一致性校验智能体", "validator", "spark-pro"),
        ("fact_check", "事实核查智能体", "validator", "spark-pro"),
        ("safety", "安全审核智能体", "validator", "spark-pro"),
        ("profile", "画像Agent", "generator", "spark-pro"),
        ("path_planner", "路径规划Agent", "generator", "spark-ultra"),
        ("tutor", "辅导Agent", "tutor", "spark-ultra"),
        ("path_replanner", "路径重规划Agent", "generator", "spark-ultra"),
    ]
    for code, name, atype, model in agents:
        db.add(AgtAgentDefinition(agent_code=code, agent_name=name, agent_type=atype, default_model=model))


def _seed_knowledge_points(db: Session) -> None:
    points = [
        ("ML_001", "机器学习概述", 1, 30),
        ("ML_002", "线性回归", 2, 45),
        ("ML_003", "逻辑回归", 2, 45),
        ("ML_004", "决策树", 3, 60),
        ("ML_005", "神经网络基础", 3, 90),
        ("ML_006", "卷积神经网络", 4, 120),
        ("ML_007", "模型评估与调优", 3, 60),
        ("ML_008", "集成学习", 4, 90),
    ]
    for code, name, diff, mins in points:
        db.add(
            PthKnowledgePoint(
                point_code=code,
                point_name=name,
                domain="machine_learning",
                difficulty=diff,
                estimated_min=mins,
            )
        )


def _seed_sensitive_words(db: Session) -> None:
    words = [
        ("暴力恐怖", "block", "violence"),
        ("色情", "block", "porn"),
        ("赌博", "block", "other"),
        ("毒品", "block", "other"),
        ("反动", "block", "politics"),
        ("代写论文", "block", "academic"),
        ("考试作弊", "block", "academic"),
    ]
    for word, wtype, cat in words:
        db.add(SecSensitiveWord(word=word, word_type=wtype, category=cat, status=1))
