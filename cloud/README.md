# Web2Apk 云端一键打包

把你填的网址，在 GitHub 的免费云服务器上自动编译成一个**独立可安装的 Android APK**。
全程手机浏览器操作，电脑零安装。复用 `android-base` 里针对视频网站优化过的 WebView 模板
（全屏手势、画中画、后台播放、广告拦截、视频下载、自定义 UA）。

---

## 架构

```
手机浏览器 (cloud/index.html)
      │  填网址/名称/功能，点「开始打包」
      │  POST 触发 workflow_dispatch
      ▼
GitHub Actions (build.yml)
      ├─ 注入 config.json / 应用名 / 主题色 / 图标 / 包名   (cloud/inject_config.py)
      ├─ gradle 编译 android-base（Java 视频优化模板）
      ├─ apksigner 用密钥签名
      └─ 上传 APK 产物（artifact，保留 7 天）
      │  前端轮询状态 + 拉取 artifact 自动下载
      ▼
手机下载并安装 APK
```

- 前端 `cloud/index.html` 部署到 **GitHub Pages**（免费），手机浏览器打开即用。
- 构建逻辑 `cloud/inject_config.py` + 根目录 `.github/workflows/build.yml`。
- 签名密钥由 `.github/workflows/gen-keystore.yml` 一次性生成。

---

## 部署步骤（一次性，约 10 分钟）

### 1. Fork 本仓库
右上角 Fork 到你的 GitHub 账号。

### 2. 生成签名密钥
- 仓库 → **Actions** → 选 `Generate Keystore` → **Run workflow**。
- 填写：密钥别名（如 `release`）、密钥密码（≥6 位）、Keystore 密码（≥6 位）、DN（如 `CN=MyApp,O=MyOrg,C=CN`）。
- 运行完成后，展开日志，复制 `KEYSTORE_BASE64 START` 与 `END` 之间的整段字符串，以及日志末尾的别名/密码。

### 3. 配置 Secrets
仓库 → **Settings → Secrets and variables → Actions → New repository secret**，添加：

| 名称 | 值 |
|---|---|
| `KEYSTORE_BASE64` | 第 2 步复制的 base64 整段 |
| `KEYSTORE_PASSWORD` | Keystore 密码 |
| `KEY_ALIAS` | 密钥别名 |
| `KEY_PASSWORD` | 密钥密码 |

> 不配置也能出包，但会用临时 debug 密钥签名（无法覆盖安装 / 上架）。建议配置。

### 4. 开启 GitHub Pages 托管前端
仓库 → **Settings → Pages → Build and deployment → Source** 选 `Deploy from a branch`：
- Branch 选 `main`，目录选 **`/cloud`**（GitHub Pages 支持子目录部署）。
- 保存后得到地址：`https://<你的用户名>.github.io/Web2ApkVideo/`，手机浏览器打开即用。

> 若你的 Pages 版本不支持 `/cloud` 子目录，可把 `cloud/index.html` 复制到仓库根目录，
> 或改用任意静态托管（Vercel / Netlify / 自己的服务器）托管这个单文件即可。

---

## 手机上使用

1. 手机浏览器打开上面得到的 Pages 地址。
2. 首次填写 GitHub 配置（Owner / Repo / PAT），会自动记住在本机浏览器：
   - **PAT 权限**：经典令牌需勾选 `repo` 与 `workflow`；细粒度令牌需 Actions 与 Workflows 的读写权限。
   - PAT 仅存于本机 localStorage，不会上传任何服务器。
3. 填写**目标网址**（自动补 `https`）、**应用名称**，按需：
   - 选主题色、UA 模式（手机版 / 桌面版，桌面版可规避移动端阉割）；
   - 勾选视频功能（全屏手势 / 画中画 / 后台音频 / 广告拦截 / 视频下载）；
   - 可选填自定义包名、勾选「允许同手机装多个」、填图标图片 URL。
4. 点「🚀 开始打包」→ 等待 3–6 分钟 → 前端自动下载 APK → 安装即可。

---

## 与 Windows 生成器（`builder/`）的区别

| | `builder/`（Windows 生成器） | `cloud/`（云端） |
|---|---|---|
| 操作设备 | 电脑 | 手机浏览器 |
| 本地依赖 | 需 Java + apktool + 签名器 | 仅需 GitHub 账号 |
| 编译方式 | apktool 反编译改包（免 SDK） | gradle 源码编译（云端有完整 SDK） |
| 可靠性 | 依赖改包，偶有兼容问题 | 源码编译，最稳 |
| 适合 | 不愿用 GitHub、想本地掌控 | 想手机一键、零安装 |

两者共用同一套 `android-base` 视频优化模板，视频特性完全一致。

---

## 注意事项

- APK 产物保留 **7 天**，请及时下载。
- 后台音频 / 画中画依赖系统与视频站策略，部分情况可能仍会暂停（PiP 需 Android 8.0+）。
- 自定义包名需合法（如 `com.my.app`）；勾选「允许同手机装多个」会自动加后缀，互不冲突。
- 图标建议提供正方形高清 PNG 的 URL；不填则用默认蓝色图标。
- 想加更多广告拦截规则：编辑 `android-base/app/src/main/assets/adblock.txt`（每行一个域名，支持子域名匹配），重新触发构建即生效。
