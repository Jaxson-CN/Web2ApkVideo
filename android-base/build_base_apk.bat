@echo off
setlocal
cd /d "%~dp0"

echo 正在尝试用 gradle 编译基础包（需要 JDK 17 + Gradle）...
where gradle >nul 2>nul
if %errorlevel%==0 (
  call gradle assembleDebug
  echo.
  echo 编译完成，APK 在：app\build\outputs\apk\debug\app-debug.apk
  echo 请把它改名为 base.apk，放到 ..\builder\ 目录下。
) else (
  echo.
  echo 未检测到 gradle 命令。推荐使用 Android Studio：
  echo   1. 用 Android Studio 打开本 android-base 目录
  echo   2. 菜单 Build - Build APK(s)
  echo   3. 把生成的 app-debug.apk 改名为 base.apk，放到 ..\builder\
  echo.
  echo 注意：AGP 8.1 需要 JDK 17（Android Studio 自带）。
)
pause
