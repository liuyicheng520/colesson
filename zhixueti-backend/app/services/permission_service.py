"""Admin permission & menu service."""

from __future__ import annotations

from app.repositories.permission_repository import PermissionRepository

# 内置菜单定义（与前端路由一致）
MENU_DEFS: list[dict] = [
    {"perm_code": "menu:dashboard", "path": "/admin/dashboard", "title": "数据大盘", "icon": "DataBoard", "sort": 10},
    {"perm_code": "menu:users", "path": "/admin/users", "title": "用户管理", "icon": "User", "sort": 20},
    {"perm_code": "menu:admins", "path": "/admin/admins", "title": "管理员账号", "icon": "UserFilled", "sort": 25},
    {"perm_code": "menu:menus", "path": "/admin/menus", "title": "菜单配置", "icon": "Menu", "sort": 26},
    {"perm_code": "menu:resources", "path": "/admin/resources", "title": "资源管理", "icon": "FolderOpened", "sort": 30},
    {"perm_code": "menu:profile-config", "path": "/admin/profile-config", "title": "画像配置", "icon": "PieChart", "sort": 32},
    {"perm_code": "menu:learning-paths", "path": "/admin/learning-paths", "title": "学习路径", "icon": "Share", "sort": 34},
    {"perm_code": "menu:generated-content", "path": "/admin/generated-content", "title": "生成内容", "icon": "PictureFilled", "sort": 36},
    {"perm_code": "menu:documents", "path": "/admin/documents", "title": "文档审核", "icon": "Document", "sort": 38},
    {"perm_code": "menu:content-audit", "path": "/admin/content-audit", "title": "内容安全", "icon": "Lock", "sort": 40},
    {"perm_code": "menu:agents", "path": "/admin/agents", "title": "智能体配置", "icon": "Cpu", "sort": 50},
    {"perm_code": "menu:settings", "path": "/admin/settings", "title": "系统设置", "icon": "Setting", "sort": 60},
    {"perm_code": "menu:operation-logs", "path": "/admin/operation-logs", "title": "操作日志", "icon": "DocumentCopy", "sort": 70},
    {"perm_code": "menu:exception-monitor", "path": "/admin/exception-monitor", "title": "异常监控", "icon": "Warning", "sort": 72},
]

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "ROLE_SUPER_ADMIN": [m["perm_code"] for m in MENU_DEFS]
    + [
        "btn:user:disable",
        "btn:user:reset_password",
        "btn:user:edit_profile",
        "btn:admin:create",
        "btn:admin:edit",
        "btn:admin:disable",
        "btn:menu:edit",
        "btn:resource:publish",
        "btn:resource:delete",
        "btn:profile-config:edit",
        "btn:path:edit",
        "btn:content:delete",
        "btn:document:audit",
        "btn:settings:edit",
        "btn:log:purge",
        "btn:user:batch",
    ],
    "ROLE_CONTENT_ADMIN": [
        "menu:dashboard",
        "menu:users",
        "menu:resources",
        "menu:profile-config",
        "menu:learning-paths",
        "menu:generated-content",
        "menu:documents",
        "menu:content-audit",
        "btn:user:disable",
        "btn:user:edit_profile",
        "btn:resource:publish",
        "btn:resource:delete",
        "btn:profile-config:edit",
        "btn:path:edit",
        "btn:content:delete",
        "btn:document:audit",
    ],
    "ROLE_OPS_ADMIN": [
        "menu:dashboard",
        "menu:users",
        "menu:agents",
        "menu:settings",
        "menu:operation-logs",
        "menu:exception-monitor",
        "btn:user:reset_password",
        "btn:settings:edit",
        "btn:log:purge",
        "btn:user:batch",
    ],
    # 兼容旧角色
    "ROLE_ADMIN": [m["perm_code"] for m in MENU_DEFS]
    + ["btn:user:disable", "btn:user:reset_password", "btn:user:edit_profile", "btn:admin:create", "btn:admin:edit", "btn:admin:disable"],
}


class PermissionService:
    def __init__(self, db) -> None:
        self.db = db
        self.repo = PermissionRepository(db)

    def get_user_permissions(self, user_id: int) -> list[str]:
        return sorted(self.repo.get_user_permission_codes(user_id))

    def get_user_menus(self, user_id: int) -> list[dict]:
        perms = self.repo.get_user_permission_codes(user_id)
        db_menus = {p.perm_code: p for p in self.repo.get_menu_permissions()}
        menus: list[dict] = []
        for m in MENU_DEFS:
            if m["perm_code"] not in perms:
                continue
            db_row = db_menus.get(m["perm_code"])
            menus.append(
                {
                    "perm_code": m["perm_code"],
                    "path": m["path"],
                    "title": db_row.perm_name if db_row else m["title"],
                    "icon": m["icon"],
                    "sort": db_row.sort_order if db_row else m["sort"],
                }
            )
        return sorted(menus, key=lambda x: x["sort"])

    def list_menu_config(self) -> list[dict]:
        db_menus = {p.perm_code: p for p in self.repo.get_menu_permissions()}
        out: list[dict] = []
        for m in MENU_DEFS:
            db_row = db_menus.get(m["perm_code"])
            out.append(
                {
                    "perm_code": m["perm_code"],
                    "path": m["path"],
                    "title": db_row.perm_name if db_row else m["title"],
                    "icon": m["icon"],
                    "sort": db_row.sort_order if db_row else m["sort"],
                }
            )
        return sorted(out, key=lambda x: x["sort"])

    def update_menu_config(self, operator_id: int, perm_code: str, *, title: str, sort: int) -> dict:
        if "btn:menu:edit" not in self.repo.get_user_permission_codes(operator_id):
            from app.core.exceptions import ForbiddenException

            raise ForbiddenException("缺少权限: btn:menu:edit")
        updated = self.repo.update_menu(perm_code, title=title, sort_order=sort)
        if not updated:
            from app.core.exceptions import ValidationException

            raise ValidationException(f"未知菜单: {perm_code}")
        base = next(m for m in MENU_DEFS if m["perm_code"] == perm_code)
        return {
            "perm_code": perm_code,
            "path": base["path"],
            "title": updated.perm_name,
            "icon": base["icon"],
            "sort": updated.sort_order,
        }

    def user_has_permission(self, user_id: int, perm_code: str) -> bool:
        return perm_code in self.repo.get_user_permission_codes(user_id)

    def seed_permissions(self) -> None:
        from app.models.sys import SysPermission

        existing = {p.perm_code for p in self.db.query(SysPermission.perm_code).all()}
        sort = 0
        for m in MENU_DEFS:
            sort += 1
            if m["perm_code"] not in existing:
                self.db.add(
                    SysPermission(
                        perm_code=m["perm_code"],
                        perm_name=m["title"],
                        resource_type="menu",
                        resource_path=m["path"],
                        parent_id=0,
                        sort_order=m["sort"],
                    )
                )
        button_perms = [
            ("btn:user:disable", "禁用/启用用户", 100),
            ("btn:user:reset_password", "重置用户密码", 101),
            ("btn:user:edit_profile", "修正用户画像", 102),
            ("btn:admin:create", "创建管理员", 110),
            ("btn:admin:edit", "编辑管理员", 111),
            ("btn:admin:disable", "禁用管理员", 112),
            ("btn:menu:edit", "编辑菜单配置", 113),
            ("btn:resource:publish", "发布/下架资源", 120),
            ("btn:resource:delete", "删除资源", 121),
            ("btn:profile-config:edit", "编辑画像配置", 130),
            ("btn:path:edit", "编辑学习路径配置", 131),
            ("btn:content:delete", "删除生成内容", 132),
            ("btn:document:audit", "文档审核与配置", 133),
            ("btn:settings:edit", "编辑系统设置", 140),
            ("btn:log:purge", "清理过期日志", 141),
            ("btn:user:batch", "批量操作用户", 142),
        ]
        for code, name, order in button_perms:
            if code not in existing:
                self.db.add(
                    SysPermission(
                        perm_code=code,
                        perm_name=name,
                        resource_type="button",
                        resource_path=None,
                        parent_id=0,
                        sort_order=order,
                    )
                )
        self.db.flush()
        for role_code, codes in ROLE_PERMISSIONS.items():
            self.repo.assign_role_permissions(role_code, codes)
