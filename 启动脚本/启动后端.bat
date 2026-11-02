@echo off
chcp 65001 >nul
title 招聘平台 - 后端服务 (Flask :5000)
echo ============================================
echo   招聘大数据可视化分析平台 - 后端启动
echo ============================================
echo.

REM 切换到项目根目录
cd /d "%~dp0.."

REM 优先使用项目虚拟环境
set "PYTHON=python"
if exist ".venv\Scripts\python.exe" (
    echo [提示] 使用虚拟环境 .venv
    set "PYTHON=.venv\Scripts\python.exe"
)

REM 检查依赖是否已安装
"%PYTHON%" -c "import flask" 2>nul
if errorlevel 1 (
    echo [错误] 后端依赖未安装，正在自动安装...
    echo.
    "%PYTHON%" -m pip install -r requirements.txt
    echo.
)

echo [启动] 正在启动后端服务 http://localhost:5000
echo [提示] 按 Ctrl+C 或关闭窗口可停止服务
echo.
"%PYTHON%" -m backend.main

pause
