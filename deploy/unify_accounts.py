"""账号体系合并（一次性迁移）：把学生服务的账号镜像补进宿主账号库。

合并后的约定：**宿主 data/auth-users.json 是唯一账号源**。
宿主登录成功后通过 /api/v1/auth/sync-account 按真实身份（1/2/3）同步到 Python 侧，
Python 侧只做镜像，不再单独维护管理员。

本脚本只做"补齐"：宿主缺的账号从 Python 侧补进来（沿用同一 bcrypt 密码哈希，
两边密码保持一致），已存在的账号不覆盖。
"""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent           # CoLesson/
HOST_USERS = ROOT / "data" / "auth-users.json"
PY_DB = ROOT / "zhixueti-backend" / "data" / "edunexus.db"

ROLE_BY_TYPE = {1: ["student"], 2: ["teacher"], 3: ["admin"]}
LEVEL_BY_TYPE = {3: "super", 2: "", 1: ""}


def main() -> int:
    users = json.loads(HOST_USERS.read_text(encoding="utf-8"))
    conn = sqlite3.connect(str(PY_DB))
    cur = conn.cursor()
    cur.execute(
        "SELECT u.id, u.username, u.password_hash, u.user_type, u.status, u.nickname "
        "FROM sys_user u WHERE u.deleted_at IS NULL"
    )
    rows = cur.fetchall()
    conn.close()

    added = 0
    for uid, username, pwd_hash, user_type, status, nickname in rows:
        if not username or not pwd_hash:
            continue
        if username in users:
            continue
        users[username] = {
            "username": username,
            "passwordHash": pwd_hash,
            "salt": "",
            "passwordAlgo": "bcrypt",
            "createdAt": "2026-11-04T00:00:00.000Z",
            "roles": ROLE_BY_TYPE.get(int(user_type or 1), ["student"]),
            "adminLevel": LEVEL_BY_TYPE.get(int(user_type or 1), ""),
            "disabled": int(status or 0) != 1,
        }
        added += 1
        print(f"  补入宿主: {username} (user_type={user_type})")

    HOST_USERS.write_text(json.dumps(users, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"完成：新增 {added} 个账号，宿主现有 {len(users)} 个账号")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
