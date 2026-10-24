"""确保存在超级管理员 lyc / admin123（用户指定），并绑定 ROLE_SUPER_ADMIN。"""
import sys

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.sys import SysRole, SysUser, SysUserRole

USERNAME = "lyc"
PASSWORD = "admin123"


def main() -> int:
    db = SessionLocal()
    try:
        super_role = db.query(SysRole).filter(SysRole.role_code == "ROLE_SUPER_ADMIN").first()
        if not super_role:
            print("ROLE_SUPER_ADMIN 角色不存在，终止")
            return 1

        user = db.query(SysUser).filter(SysUser.username == USERNAME).first()
        if user:
            user.password_hash = hash_password(PASSWORD)
            user.user_type = 3
            user.status = 1
            print(f"已重置现有账号 {USERNAME} 的密码")
        else:
            user = SysUser(
                username=USERNAME,
                password_hash=hash_password(PASSWORD),
                nickname="超级管理员",
                real_name="系统管理员",
                user_type=3,
                status=1,
            )
            db.add(user)
            db.flush()
            print(f"已创建账号 {USERNAME}")

        has_role = (
            db.query(SysUserRole)
            .filter(SysUserRole.user_id == user.id, SysUserRole.role_id == super_role.id)
            .first()
        )
        if not has_role:
            db.add(SysUserRole(user_id=user.id, role_id=super_role.id))
            print("已绑定 ROLE_SUPER_ADMIN")
        db.commit()
        print(f"完成：{USERNAME} / {PASSWORD}（user_type=3, status=1）")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
