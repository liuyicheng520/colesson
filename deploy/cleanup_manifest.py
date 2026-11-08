#!/usr/bin/env python3
"""测试数据清理清单（dry-run 只读；加 --execute 才真正删除）。

列出各存储中的账号/班级/项目/资源，并标记疑似测试数据。
删除范围以清单确认为准——真实教师/管理员账号一律不动。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXECUTE = "--execute" in sys.argv

TEST_USER_PAT = {"stu01", "stu02", "stu03", "stu04", "stu05", "stu06", "uaudit01",
                 "teacheck1", "spalocal1", "secfix1", "stureg1", "teachreg1", "3", "666"}


def load_json(p: Path, default):
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def main() -> int:
    print("=" * 64)
    print("CoLesson 测试数据清理清单（dry-run%s）" % ("，执行模式" if EXECUTE else "，只读"))
    print("=" * 64)

    # 1. 宿主账号
    users_path = ROOT / "data" / "auth-users.json"
    users = load_json(users_path, {})
    items = list(users.values()) if isinstance(users, dict) else list(users)
    print(f"\n[宿主账号] data/auth-users.json 共 {len(items)} 个：")
    keep, test = [], []
    for u in items:
        name = u.get("username", "?")
        (test if name in TEST_USER_PAT else keep).append(name)
    print("  建议删除（测试账号）:", ", ".join(sorted(test)))
    print("  保留（疑似真实账号）:", ", ".join(sorted(keep)))

    # 2. 宿主班级
    store = load_json(ROOT / "data" / "classrooms.json", {})
    items = store.get("classes", []) if isinstance(store, dict) else store
    print(f"\n[宿主班级] 共 {len(items)} 个：")
    for c in items:
        print(f"  - {c.get('name', '?')} (id={str(c.get('id', '?'))[:26]}, 教师={c.get('teacherUsername', '?')}, 成员={len(c.get('memberUsernames') or [])})")

    # 3. 宿主项目
    proj = load_json(ROOT / "data" / "projects.json", [])
    items = proj if isinstance(proj, list) else list(proj.values())
    print(f"\n[宿主项目] 共 {len(items)} 个：")
    for p in items:
        p = p.get("project", p) if isinstance(p, dict) else {}
        print(f"  - {p.get('name', '?')} (id={str(p.get('id', '?'))[:26]}, 教师={p.get('teacherUsername', '?')})")

    # 4. 学生端 SQLite
    import sqlite3
    db = ROOT / "zhixueti-backend" / "data" / "edunexus.db"
    if db.exists():
        conn = sqlite3.connect(str(db))
        cur = conn.cursor()
        try:
            cur.execute("SELECT id, username, user_type FROM sys_user ORDER BY id")
            rows = cur.fetchall()
            print(f"\n[学生端账号] zhixueti edunexus.db 共 {len(rows)} 个：")
            for uid, uname, ut in rows:
                mark = "测试" if uname in TEST_USER_PAT else "保留"
                print(f"  - [{mark}] {uname} (id={uid}, type={ut})")
            cur.execute(
                "SELECT r.id, t.type_code, r.title FROM res_resource r "
                "LEFT JOIN res_resource_type_def t ON t.id = r.type_id ORDER BY r.id DESC LIMIT 15"
            )
            rows = cur.fetchall()
            print(f"\n[学生端资源] 最近 {len(rows)} 条：")
            for rid, tc, title in rows:
                mark = "演示/测试" if rid in (1, 29, 30, 31) or (title or "").startswith("越权") else "        "
                print(f"  - {mark} id={rid} type={tc} title={str(title)[:28]}")
        finally:
            conn.close()
    else:
        print("\n[学生端 SQLite] 未找到", db)

    if EXECUTE:
        print("\n[执行模式] 尚未实现自动删除——确认范围后由助手按清单逐项执行。")
    else:
        print("\n（只读模式：未做任何修改。确认删除范围后告知助手执行。）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
