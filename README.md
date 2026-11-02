# Web2ApkVideo —— 把网站/视频站打包成安卓 APK

一个**本地、低门槛**的工具：在 Windows 上输入网址，一键生成可在安卓手机安装的 APK。
专门针对**视频网站**做了播放兼容与操作优化。

> 想**在手机上直接操作、电脑零安装**？看 [`cloud/` 云端一键打包方案](cloud/README.md)：手机浏览器填网址 → GitHub 免费云编译 → 下载独立 APK。

---

## 它能做什么

- 把任意网站（B 站、YouTube、各类视频站、普通网页）打包成独立安卓 App。
- 视频增强（全部可在打包时勾选/关闭）：
  - **全屏沉浸播放 + 手势操作**：横滑调亮度、竖滑调音量，像原生播放器。
  - **画中画（PiP）**：按Home键自动小窗继续看。
  - **后台音频**：退出 App 也能继续听声音（尽力而为，见下方说明）。
  - **广告 / 弹窗拦截**：内置常见广告追踪域名表，并拦截网页弹窗。
  - **视频检测与下载**：App 内「⤓」按钮可下载检测到的视频到下载目录。
  - **自定义 UA**：可切桌面版网页，规避移动端阉割。
- 免 Android SDK 日常打包（只需要 Java 运行时）。

---

## 目录结构

```
Web2ApkVideo/
├── android-base/        # 安卓基础工程源码（只用来一次性生成 base.apk）
│   └── build_base_apk.bat
├── builder/             # Windows 打包工具
│   ├── builder.py       # 图形界面
│   ├── repack.py        # 改包核心逻辑（反编译→注入→回编→签名）
│   ├── get_tools.bat    # 一键获取 apktool / 签名器 / 密钥
│   ├── tools/           # 下载的工具放这里（apktool.jar / uber-apk-signer.jar / web2apk.keystore）
│   ├── output/          # 生成的 APK 输出到这里
│   └── work/            # 中间临时文件
├── cloud/              # 云端一键打包方案（手机浏览器操作，GitHub Actions 编译）
│   ├── index.html      # 手机前端：填网址/触发/下载
│   ├── inject_config.py# 云端配置注入脚本（被 workflow 调用）
│   └── README.md       # 云端部署与使用说明
└── README.md
```

---

## 使用流程

### 第一步（一次性）：生成基础包 base.apk

> 这一步**只需要做一次**。之后日常打包完全不需要 Android SDK。

方式 A（推荐，最简单）：
1. 安装 [Android Studio](https://developer.android.com/studio)。
2. 用 Android Studio 打开 `android-base` 目录。
3. 菜单 `Build → Build APK(s)`（或 `Make Project`）。
4. 找到生成的 `app-debug.apk`（一般在 `android-base/app/build/outputs/apk/debug/`）。
5. 把它**改名为 `base.apk`**，放到 `builder\` 目录下。

方式 B（有 gradle 命令行）：
- 双击运行 `android-base\build_base_apk.bat`。

### 第二步（一次性）：获取打包工具

双击运行 `builder\get_tools.bat`：
- 自动下载 `apktool.jar`、`uber-apk-signer.jar` 到 `builder\tools\`。
- 自动用 `keytool` 生成签名密钥 `web2apk.keystore`（需要 JDK；装了 Android Studio 就自带）。
- 若提示找不到 keytool：装好 JDK 后重跑一次即可。

> 注意：本机还需要 **Java 运行时（JRE 8+）**，因为 apktool 和签名器都靠它跑。
> 下载如失败，多半是版本号变了，到 GitHub 确认最新版后改 `get_tools.bat` 顶部的版本号即可。

### 第三步（日常）：打包

1. 双击 `builder\run.bat`（或直接 `python builder.py`）。
2. 填网址、应用名、选主题色、勾选要的功能、可选换图标。
3. 点「▶ 开始打包」。
4. 生成的 APK 在 `builder\output\<应用名>\<应用名>.apk`，拷到手机安装即可。

---

## 云端一键打包（手机可操作）

不想在电脑上装任何东西、希望**手机上直接出 APK**？`cloud/` 目录提供一套云端方案：

- 手机浏览器打开一个网页，填网址、名称、勾选视频功能；
- 后端用 GitHub Actions 免费云服务器，自动编译 `android-base`（我们的视频优化模板）、签名、出包；
- 前端自动拉取并下载 APK，安装即用。

**优点**：电脑零安装、手机可操作、编译最可靠（云端有完整 Android SDK）。
**代价**：需要一个 GitHub 账号（Actions 免费额度足够），前端托管用 GitHub Pages（免费）。

详细部署与使用步骤见 [cloud/README.md](cloud/README.md)。

---

## 常见问题 / 说明

- **后台音频是「尽力而为」**：靠一条前台通知把进程优先级提起来，绝大多数情况可用，
  但部分机型/视频站的策略可能仍会暂停。画中画（PiP）需要 Android 8.0+。
- **想同时装多个网站 App**：勾选「允许同手机装多个」，会自动改包名互不冲突。
- **想加更多广告拦截规则**：编辑 `android-base/app/src/main/assets/adblock.txt`
  （每行一个域名，支持 `ad.example.com` 形式的子域名匹配），重新生成 base.apk 即可生效。
- **为什么需要 base.apk**：所有可定制项（网址/功能/颜色）都在运行时从 `config.json` 读取，
  打包只是把配置注进 APK 再签名，因此日常完全免 SDK。
- **签名是调试密钥**：个人自用没问题；若要上架应用商店，请用你自己的密钥（改 `get_tools.bat`
  里的密钥口令，或自行 `keytool` 生成并替换 `tools/web2apk.keystore`）。

---

## 技术要点

- 基础 App 是一个高度定制的 `WebView`：
  - `WebChromeClient.onShowCustomView/onHideCustomView` 处理 HTML5 全屏视频；
  - `shouldInterceptRequest` 做广告域名拦截与视频地址嗅探；
  - `onUserLeaveHint → enterPictureInPictureMode` 实现退出即小窗；
  - 前台服务 `KeepAliveService` 维持后台音频；
  - JS 桥 `Web2ApkSniffer` 把页面 `<video>` 地址回传用于下载。
- 打包端 `repack.py`：apktool 反编译 → 替换 `assets/config.json`、应用名、主题色、图标
  （可选改包名）→ apktool 回编 → uber-apk-signer 对齐+签名。全程纯 Java 运行时，无 SDK 依赖。
