# -*- coding: utf-8 -*-
"""演示数据清理脚本：移除开发期的 QA 测试残留，保留干净的演示环境。

默认 dry-run（只打印将要做的变更）；确认无误后加 --apply 真正执行。
执行前会自动把 data/ 完整备份到 data-backup-<时间戳>/，可随时还原。

保留（演示承诺账号，见 仓库地址.txt）：
  lyc/admin123（超级管理员）、admin（管理员）、stu01~stu06（学生）
  项目 proj_ecd54394195c4c56873083095f52430e（机器学习入门）、知识库目录、管理审计日志
移除：
  9 个 QA 账号（teacheck1/spalocal1/3/666/secfix1/teachreg1/stureg1/李元/uaudit01）
  4 个 QA 班级（软件测试/QA测试班/过期会话测试班/过期会话班2）及其作业、提交、上传文件
  全部过期会话令牌（auth-sessions.json）

用法：
  python scripts/cleanup-demo-data.py           # 预览
  python scripts/cleanup-demo-data.py --apply   # 执行（先自动备份）
"""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

QA_ACCOUNTS = {"teacheck1", "spalocal1", "3", "666", "secfix1",
               "teachreg1", "stureg1", "李元", "uaudit01"}
QA_CLASS_NAMES = {"软件测试", "QA测试班", "过期会话测试班", "过期会话班2"}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, obj):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正执行（默认仅预览）")
    args = ap.parse_args()

    plan = []

    users = load(DATA / "auth-users.json")
    drop_users = sorted(k for k in users if k in QA_ACCOUNTS)
    keep_users = sorted(k for k in users if k not in QA_ACCOUNTS)
    plan.append(("auth-users.json", f"移除 {len(drop_users)} 个 QA 账号: {', '.join(drop_users)}"))
    plan.append(("auth-users.json", f"保留 {len(keep_users)} 个账号: {', '.join(keep_users)}"))

    rooms = load(DATA / "classrooms.json")
    classes = rooms.get("classes", [])
    drop_classes = [c for c in classes if c.get("name") in QA_CLASS_NAMES]
    keep_classes = [c for c in classes if c.get("name") not in QA_CLASS_NAMES]
    plan.append(("classrooms.json", f"移除 {len(drop_classes)} 个 QA 班级: "
                 + ", ".join(c.get("name", "?") for c in drop_classes)))

    drop_homework_ids = {h.get("id") for h in rooms.get("homeworks", [])
                         if h.get("classId") in {c.get("id") for c in drop_classes}}
    plan.append(("classrooms.json", f"移除 {len(drop_homework_ids)} 个关联作业、"
                 f"{sum(1 for s in rooms.get('submissions', []) if s.get('homeworkId') in drop_homework_ids)} 份提交"))

    sessions = load(DATA / "auth-sessions.json")
    plan.append(("auth-sessions.json", f"清除 {len(sessions)} 个过期会话令牌"))

    uploads = DATA / "homework-uploads"
    plan.append(("homework-uploads/", f"清除其中 QA 作业材料与提交文件（当前 {len(list(uploads.glob('*'))) if uploads.exists() else 0} 项）"))

    for tag, desc in plan:
        print(f"[将{'执行' if args.apply else '变更'}] {tag}: {desc}")

    if not args.apply:
        print("\n以上为预览（dry-run）。确认后执行: python scripts/cleanup-demo-data.py --apply")
        return

    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = ROOT / f"data-backup-{stamp}"
    shutil.copytree(DATA, backup)
    print(f"\n已备份 data/ -> {backup.name}")

    for k in drop_users:
        users.pop(k, None)
    save(DATA / "auth-users.json", users)

    rooms["classes"] = keep_classes
    rooms["homeworks"] = [h for h in rooms.get("homeworks", [])
                          if h.get("id") not in drop_homework_ids]
    rooms["submissions"] = [s for s in rooms.get("submissions", [])
                            if s.get("homeworkId") not in drop_homework_ids]
    save(DATA / "classrooms.json", rooms)

    save(DATA / "auth-sessions.json", {})

    if uploads.exists():
        shutil.rmtree(uploads)
        uploads.mkdir()

    print("清理完成。说明：")
    print("- 智能服务(SQLite)侧的镜像账号为惰性数据，无法再从宿主登录，如需彻底清除可后续重建数据库。")
    print("- 如需还原: 关闭服务后，用 " + backup.name + " 覆盖 data/ 即可。")


if __name__ == "__main__":
    sys.exit(main())
