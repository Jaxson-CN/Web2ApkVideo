@echo off
setlocal
cd /d "%~dp0"

set TOOLS=%~dp0tools
if not exist "%TOOLS%" mkdir "%TOOLS%"

REM ===== 版本号（如下载失败，到 GitHub 确认最新版后改这里）=====
set APKTOOL_VER=2.11.1
set SIGNER_VER=1.3.0

echo 正在下载 apktool ...
powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://github.com/iBotPeaches/Apktool/releases/download/v%APKTOOL_VER%/apktool_%APKTOOL_VER%.jar' -OutFile '%TOOLS%\apktool.jar'"
if not exist "%TOOLS%\apktool.jar" (
  echo [失败] apktool 下载未成功，请检查网络或版本号。
  goto :end
)

echo 正在下载 uber-apk-signer ...
powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://github.com/patrickfav/uber-apk-signer/releases/download/v%SIGNER_VER%/uber-apk-signer-%SIGNER_VER%.jar' -OutFile '%TOOLS%\uber-apk-signer.jar'"
if not exist "%TOOLS%\uber-apk-signer.jar" (
  echo [失败] 签名器下载未成功，请检查网络或版本号。
  goto :end
)

echo 正在生成签名密钥 ...
where keytool >nul 2>nul
if %errorlevel%==0 (
  if not exist "%TOOLS%\web2apk.keystore" (
    keytool -genkeypair -v -keystore "%TOOLS%\web2apk.keystore" -alias web2apk -keyalg RSA -keysize 2048 -validity 10000 -storepass web2apk123 -keypass web2apk123 -dname "CN=Web2Apk, OU=Tool, O=Web2Apk, L=Local, ST=Local, C=CN"
    echo [完成] 密钥已生成：tools\web2apk.keystore
  ) else (
    echo [提示] 密钥已存在，跳过。
  )
) else (
  echo [警告] 未找到 keytool（需要 JDK）。请安装 Android Studio 或 JDK 后重跑本脚本生成密钥。
)

echo.
echo ===== 工具就绪 =====
echo 接下来请把 android-base 编译出的 base.apk 放到本目录（builder\）下，然后运行 run.bat。
:end
pause
