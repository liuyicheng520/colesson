#!/bin/bash
# 推送到 GitHub + Gitee 双平台（传智杯要求代码托管）
#
# 使用前一次性配置：
#   1. GitHub: 在 https://github.com/new 创建空仓库 colesson（不要勾选初始化 README）
#      然后登录: gh auth login   （或用 HTTPS + 用户名/Token）
#   2. Gitee:  在 https://gitee.com/projects/new 创建空仓库 colesson
#      并把下面两个 REMOTE_* 改成你的实际地址
#
# 之后每次推送只需: bash scripts/push-remotes.sh "提交说明"

set -e
cd "$(dirname "$0")/.."

GH_URL="${GH_URL:-https://github.com/<你的GitHub账号>/colesson.git}"
GITEE_URL="${GITEE_URL:-https://gitee.com/<你的Gitee账号>/colesson.git}"

git remote remove origin 2>/dev/null || true
git remote add origin "$GH_URL"
git remote add gitee "$GITEE_URL" 2>/dev/null || true

BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "推送到 GitHub: $GH_URL"
git push -u origin "$BRANCH"
git push origin --tags

echo "推送到 Gitee: $GITEE_URL"
git push -u gitee "$BRANCH"
git push gitee --tags

echo "完成：双平台已同步。"
