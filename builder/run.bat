@echo off
cd /d "%~dp0"
python builder.py
if %errorlevel% neq 0 (
  echo.
  echo 如果提示找不到 python，请先安装 Python 3.8+ 并勾选“Add to PATH”。
  pause
)
