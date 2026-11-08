@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0..\zhixueti-backend"

if not exist ".env" (
  if exist ".env.example" copy /Y ".env.example" ".env" >nul
)

if not exist "venv\Scripts\python.exe" (
  echo 创建 venv ...
  python -m venv venv
  if errorlevel 1 (
    echo [错误] 创建 venv 失败，请确认已安装 Python 3.10+
    exit /b 1
  )
)

call venv\Scripts\activate.bat
python -m pip install -U pip
pip install -r requirements.txt
echo.
echo 智学体后端依赖已就绪。之后直接运行仓库根目录 start.bat 即可。
endlocal
