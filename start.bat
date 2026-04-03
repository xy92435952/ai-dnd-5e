@echo off
chcp 65001 >nul
echo.
echo  ==========================================
echo   AI TRPG - DnD 5e
echo  ==========================================
echo.

:: 清理旧进程（防止端口占用）
echo [0/2] 清理旧进程...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8002 "') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":3000 "') do (
    taskkill /F /PID %%a >nul 2>&1
)

:: 检查虚拟环境
if not exist "%~dp0backend\.venv\Scripts\python.exe" (
    echo [准备] 虚拟环境不存在，正在创建...
    C:\Python314\python.exe -m venv "%~dp0backend\.venv"
    "%~dp0backend\.venv\Scripts\pip.exe" install -r "%~dp0backend\requirements.txt" -q
)

:: 启动后端（端口 8002）
echo [1/2] 启动后端服务 (http://localhost:8002) ...
start "AI-TRPG Backend" cmd /k "pushd %~dp0backend && .venv\Scripts\python.exe -m uvicorn main:app --port 8002"

:: 等待后端启动
timeout /t 3 /nobreak >nul

:: 启动前端
echo [2/2] 启动前端服务 (http://localhost:3000) ...
start "AI-TRPG Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo  启动完成！访问：http://localhost:3000
echo.
pause
