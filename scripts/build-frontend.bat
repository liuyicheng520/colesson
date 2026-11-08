@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0..\zhixueti-frontend"

if not exist "node_modules" (
  call npm install
)

call npm run build
echo 前端已构建并同步到 src\main\resources\static
endlocal
