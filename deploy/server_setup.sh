#!/usr/bin/env bash
# CoLesson 服务器端安装/更新脚本（在部署目录内执行，如 /www/colesson）
# 用法：bash server_setup.sh [部署目录]
# 前置要求：Java 17+（java -version）、Python 3.10+
set -euo pipefail

DEPLOY_DIR="${1:-$(pwd)}"
cd "$DEPLOY_DIR"

echo "==> 部署目录：$DEPLOY_DIR"

# 1. Python 虚拟环境
if [ ! -f zhixueti-backend/venv/bin/python ]; then
  echo "==> 创建 Python venv ..."
  python3 -m venv zhixueti-backend/venv
fi
echo "==> 安装后端依赖（首次较慢）..."
zhixueti-backend/venv/bin/pip install -q --upgrade pip
zhixueti-backend/venv/bin/pip install -q -r zhixueti-backend/requirements.txt

# 2. 目录与权限
mkdir -p reports data/generated-static
chmod +x server_setup.sh || true

# 3. systemd 服务
if command -v systemctl >/dev/null 2>&1; then
  echo "==> 安装 systemd 服务 ..."
  sed "s|__DEPLOY_DIR__|$DEPLOY_DIR|g" colesson.service > /tmp/colesson.service
  install -m 644 /tmp/colesson.service /etc/systemd/system/colesson.service
  systemctl daemon-reload
  systemctl enable colesson >/dev/null 2>&1 || true
  echo "==> 启动服务 ..."
  systemctl restart colesson
  sleep 12
  systemctl --no-pager -l status colesson | head -12 || true
else
  echo "==> 无 systemd，前台启动（Ctrl+C 停止）："
  echo "    java -jar ai-teacher.jar"
fi

echo "==> 完成。验证：curl http://127.0.0.1:8082/login.html"
