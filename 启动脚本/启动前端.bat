@echo off
chcp 65001 >nul
title 招聘平台 - 前端服务 (React :3000)
echo ============================================
echo   招聘大数据可视化分析平台 - 前端启动
echo ============================================
echo.

REM 切换到前端目录
cd /d "%~dp0..\frontend"

REM 检查 node_modules 是否已安装
if not exist "node_modules" (
    echo [提示] 首次运行，正在安装前端依赖（可能需要几分钟）...
    echo.
    call npm install
    echo.
)

echo [启动] 正在启动前端服务 http://localhost:3000
echo [提示] 后端需先启动（默认 http://localhost:5000）
echo [提示] 按 Ctrl+C 或关闭窗口可停止服务
echo.
call npm start

pause
