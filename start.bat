@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo.
echo ========================================
echo   CoLesson 智课共生（教师端+学生端）
echo   http://127.0.0.1:8082
echo ========================================
echo.

if not exist "config\application-local.properties" (
  if exist "config\application-local.properties.example" (
    copy /Y "config\application-local.properties.example" "config\application-local.properties" >nul
    echo [提示] 已生成 config\application-local.properties，请填写 MySQL 密码与 AI_API_KEY
  )
)

where mvn >nul 2>nul
if errorlevel 1 (
  echo [错误] 未找到 mvn，请先安装 Maven 并加入 PATH
  exit /b 1
)

mvn -q spring-boot:run
endlocal
