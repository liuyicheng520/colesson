#!/usr/bin/env python3
"""打包 CoLesson 部署产物到 deploy/bundle/，并压缩为 colesson-bundle.zip。

产物布局（服务器部署目录即按此布局）：
  bundle/
    ai-teacher.jar                    # 宿主 Spring Boot（内嵌学生/管理 SPA + 教师多页静态）
    zhixueti-backend/                 # FastAPI 后端（app 代码 + requirements + .env + KB 数据）
    config/application-local.properties
    colesson.service                  # systemd 单元
    server_setup.sh                   # 服务器端一键安装/更新脚本

用法：python deploy/package_deploy.py
"""
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "bundle"
ZIP = Path(__file__).resolve().parent / "colesson-bundle.zip"

BACKEND_SRC = ROOT / "zhixueti-backend"
BACKEND_COPY = ["app", "requirements.txt", ".env", "start.sh"]
BACKEND_DATA = ["knowledge", "vector_kb"]  # 位于 zhixueti-backend/data/
JAR_SRC = ROOT / "target" / "ai-teacher-1.0-SNAPSHOT.jar"
CONFIG_SRC = ROOT / "config" / "application-local.properties"


def main() -> int:
    if not JAR_SRC.exists():
        print("缺少 JAR：请先执行 mvn package", file=sys.stderr)
        return 1

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    # 1. JAR
    shutil.copy2(JAR_SRC, OUT / "ai-teacher.jar")
    print("[1/5] JAR 复制完成")

    # 2. Python 后端代码（排除 venv / __pycache__ / 本地 db）
    bk = OUT / "zhixueti-backend"
    for item in BACKEND_COPY:
        src = BACKEND_SRC / item
        dst = bk / item
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        elif src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    for item in BACKEND_DATA:
        src = BACKEND_SRC / "data" / item
        if src.is_dir():
            shutil.copytree(src, bk / "data" / item, ignore=shutil.ignore_patterns("__pycache__"))
    print("[2/5] zhixueti-backend 复制完成（app + .env + KB 语料 + 向量库）")

    # 3. 宿主配置 + 评测报告（运营看板数据）
    (OUT / "config").mkdir(exist_ok=True)
    if CONFIG_SRC.exists():
        shutil.copy2(CONFIG_SRC, OUT / "config" / "application-local.properties")
    reports_src = ROOT / "reports"
    if reports_src.is_dir():
        shutil.copytree(reports_src, OUT / "reports", ignore=shutil.ignore_patterns(".DS_Store"))
    print("[3/5] 宿主配置 + reports 评测报告复制完成")

    # 4. systemd 单元 + 服务器脚本（由本仓库 deploy/ 原样带入）
    for name in ("colesson.service", "server_setup.sh"):
        src = Path(__file__).resolve().parent / name
        if src.exists():
            shutil.copy2(src, OUT / name)
    print("[4/5] systemd / setup 脚本带入")

    # 5. 压缩
    if ZIP.exists():
        ZIP.unlink()
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for p in OUT.rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(OUT.parent))
    size_mb = ZIP.stat().st_size / 1024 / 1024
    print(f"[5/5] 打包完成：{ZIP}  ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
