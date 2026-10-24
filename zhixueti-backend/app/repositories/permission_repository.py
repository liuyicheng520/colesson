"""Permission & menu repository."""

from sqlalchemy.orm import Session

from app.models.sys import SysPermission, SysRole, SysRolePermission, SysUserRole


class PermissionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_user_permission_codes(self, user_id: int) -> set[str]:
        rows = (
            self.db.query(SysPermission.perm_code)
            .join(SysRolePermission, SysRolePermission.permission_id == SysPermission.id)
            .join(SysUserRole, SysUserRole.role_id == SysRolePermission.role_id)
            .filter(SysUserRole.user_id == user_id, SysPermission.status == 1)
            .all()
        )
        return {r[0] for r in rows}

    def get_menu_permissions(self) -> list[SysPermission]:
        return (
            self.db.query(SysPermission)
            .filter(SysPermission.resource_type == "menu", SysPermission.status == 1)
            .order_by(SysPermission.sort_order)
            .all()
        )

    def get_by_code(self, perm_code: str) -> SysPermission | None:
        return self.db.query(SysPermission).filter(SysPermission.perm_code == perm_code).first()

    def update_menu(self, perm_code: str, *, title: str | None = None, sort_order: int | None = None) -> SysPermission | None:
        perm = self.get_by_code(perm_code)
        if not perm or perm.resource_type != "menu":
            return None
        if title is not None:
            perm.perm_name = title
        if sort_order is not None:
            perm.sort_order = sort_order
        self.db.commit()
        self.db.refresh(perm)
        return perm

    def assign_role_permissions(self, role_code: str, perm_codes: list[str]) -> None:
        role = self.db.query(SysRole).filter(SysRole.role_code == role_code).first()
        if not role:
            return
        self.db.query(SysRolePermission).filter(SysRolePermission.role_id == role.id).delete()
        for code in perm_codes:
            perm = self.get_by_code(code)
            if perm:
                self.db.add(SysRolePermission(role_id=role.id, permission_id=perm.id))
