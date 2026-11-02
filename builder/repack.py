#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
repack.py —— 免 SDK 把「基础 APK」改造成任意网站的独立 APK。

原理：基础 APK（android-base 工程编译出的 base.apk）里所有可定制项都通过
assets/config.json 在运行时读取，所以打包时只需要：
  1. apktool 反编译 base.apk
  2. 替换 assets/config.json（网址/功能/主题色等）
  3. 替换 res 里的应用名、主题色、启动图标
  4. （可选）改包名，让多个网站 App 能同手机共存
  5. apktool 回编译 + uber-apk-signer 对齐签名
全程不需要 Android SDK，只需要 Java 运行时 + apktool.jar + uber-apk-signer.jar。
"""

import os
import re
import json
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "tools")
WORK = os.path.join(HERE, "work")
OUTPUT = os.path.join(HERE, "output")

BASE_PACKAGE = "com.web2apk.video"

# 签名用的调试密钥（个人工具，固定口令即可；如需上线商店请自建密钥）
KS_PASS = "web2apk123"
KS_ALIAS = "web2apk"


class RepackError(Exception):
    pass


def log(msg):
    print(msg, flush=True)


def find_tools(base_apk=None):
    apktool = os.path.join(TOOLS, "apktool.jar")
    signer = os.path.join(TOOLS, "uber-apk-signer.jar")
    keystore = os.path.join(TOOLS, "web2apk.keystore")
    if base_apk and os.path.isfile(base_apk):
        base = base_apk
    else:
        cand = os.path.join(HERE, "base.apk")
        base = cand if os.path.isfile(cand) else None
    missing = []
    if not os.path.isfile(apktool):
        missing.append(apktool)
    if not os.path.isfile(signer):
        missing.append(signer)
    if base is None:
        missing.append("base.apk (基础包未找到)")
    return {
        "apktool": apktool,
        "signer": signer,
        "keystore": keystore,
        "base_apk": base,
        "missing": missing,
    }


def build_config(url, app_name, ua_mode, custom_ua, features, theme_color):
    url = (url or "").strip()
    if url and not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    cfg = {
        "startUrl": url,
        "appName": app_name,
        "uaMode": ua_mode,
        "customUserAgent": custom_ua or "",
        "features": {
            "fullscreenGesture": bool(features.get("fullscreenGesture", True)),
            "pip": bool(features.get("pip", True)),
            "backgroundAudio": bool(features.get("backgroundAudio", True)),
            "adBlock": bool(features.get("adBlock", True)),
            "videoDownload": bool(features.get("videoDownload", True)),
        },
        "themeColor": theme_color or "#1f6feb",
    }
    return json.dumps(cfg, ensure_ascii=False, indent=2)


def run_cmd(cmd, cwd=None):
    log(">>> " + " ".join(cmd))
    proc = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                          errors="replace")
    out = proc.stdout or ""
    if out.strip():
        for line in out.splitlines():
            log("    " + line)
    if proc.returncode != 0:
        raise RepackError("命令执行失败 (exit %d):\n%s" % (proc.returncode, out))
    return out


def decode_apk(apktool, base_apk, out_dir):
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(os.path.dirname(out_dir), exist_ok=True)
    run_cmd(["java", "-jar", apktool, "d", base_apk, "-o", out_dir, "-f"])


def patch_decoded(decoded, config_str, app_name, theme_color, icon_path, new_package):
    # 1) config.json
    assets_dir = os.path.join(decoded, "assets")
    os.makedirs(assets_dir, exist_ok=True)
    with open(os.path.join(assets_dir, "config.json"), "w", encoding="utf-8") as f:
        f.write(config_str)

    # 2) 应用名
    strings_path = os.path.join(decoded, "res", "values", "strings.xml")
    if os.path.isfile(strings_path):
        with open(strings_path, "r", encoding="utf-8") as f:
            s = f.read()
        s = re.sub(r'(<string name="app_name">)[^<]*(</string>)',
                   lambda m: m.group(1) + app_name + m.group(2), s)
        with open(strings_path, "w", encoding="utf-8") as f:
            f.write(s)

    # 3) 主题色
    colors_path = os.path.join(decoded, "res", "values", "colors.xml")
    if os.path.isfile(colors_path):
        with open(colors_path, "r", encoding="utf-8") as f:
            c = f.read()
        c = re.sub(r'(<color name="colorPrimary">)#[0-9A-Fa-f]{6}(</color>)',
                   lambda m: m.group(1) + theme_color + m.group(2), c)
        c = re.sub(r'(<color name="colorAccent">)#[0-9A-Fa-f]{6}(</color>)',
                   lambda m: m.group(1) + theme_color + m.group(2), c)
        with open(colors_path, "w", encoding="utf-8") as f:
            f.write(c)

    # 4) 图标（直接覆盖各密度，用户应提供方形的高清图）
    if icon_path and os.path.isfile(icon_path):
        for d in os.listdir(os.path.join(decoded, "res")):
            if d.startswith("mipmap-"):
                dp = os.path.join(decoded, "res", d)
                for name in ("ic_launcher.png", "ic_launcher_round.png"):
                    dst = os.path.join(dp, name)
                    shutil.copyfile(icon_path, dst)

    # 5) 改包名（可选，让多站点 App 共存）
    if new_package and new_package != BASE_PACKAGE:
        rename_package(decoded, new_package)


def rename_package(decoded, new_package):
    new_slash = new_package.replace(".", "/")
    # manifest
    manifest = os.path.join(decoded, "AndroidManifest.xml")
    if os.path.isfile(manifest):
        with open(manifest, "r", encoding="utf-8") as f:
            m = f.read()
        # 一次性整体替换（新包名以旧包名为前缀，分两步会重复替换）
        m = m.replace(BASE_PACKAGE, new_package)
        with open(manifest, "w", encoding="utf-8") as f:
            f.write(m)
    # smali：移动目录 + 替换引用
    for entry in os.listdir(decoded):
        if not entry.startswith("smali"):
            continue
        smali_dir = os.path.join(decoded, entry)
        old_sub = os.path.join(smali_dir, "com", "web2apk", "video")
        if os.path.isdir(old_sub):
            new_sub = os.path.join(smali_dir, *new_package.split("."))
            os.makedirs(os.path.dirname(new_sub), exist_ok=True)
            shutil.move(old_sub, new_sub)
        for root, _, files in os.walk(smali_dir):
            for fn in files:
                if fn.endswith(".smali"):
                    p = os.path.join(root, fn)
                    with open(p, "r", encoding="utf-8", errors="replace") as f:
                        t = f.read()
                    t = t.replace("L%s/" % BASE_PACKAGE.replace(".", "/"),
                                  "L%s/" % new_slash)
                    t = t.replace(BASE_PACKAGE, new_package)
                    with open(p, "w", encoding="utf-8") as f:
                        f.write(t)


def build_apk(apktool, decoded, out_apk):
    os.makedirs(os.path.dirname(out_apk), exist_ok=True)
    run_cmd(["java", "-jar", apktool, "b", decoded, "-o", out_apk])


def sign_apk(signer, keystore, unsigned_apk, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    # uber-apk-signer：对齐 + v1/v2 签名一步完成，仅需 JRE
    run_cmd(["java", "-jar", signer,
             "--apks", unsigned_apk,
             "--ks", keystore,
             "--ksPass", KS_PASS,
             "--ksKeyAlias", KS_ALIAS,
             "--ksKeyPass", KS_PASS,
             "--out", out_dir])
    # 找到签名后的产物
    apks = [os.path.join(out_dir, f) for f in os.listdir(out_dir)
            if f.endswith(".apk") and os.path.isfile(os.path.join(out_dir, f))]
    if not apks:
        raise RepackError("签名后未找到输出 APK")
    apks.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return apks[0]


def safe_name(name):
    s = re.sub(r'[\\/:*?"<>| ]+', '_', name.strip())
    return s or "WebApp"


def repack(params):
    """
    params 字段：
      url, app_name, theme_color, ua_mode, custom_ua, features(dict),
      icon_path(可选), base_apk(可选), output_dir(可选),
      allow_multiple(bool), name_suffix(可选)
    返回：最终 APK 路径
    """
    tools = find_tools(params.get("base_apk"))
    if tools["missing"]:
        raise RepackError("缺少必要文件：\n  - " + "\n  - ".join(tools["missing"])
                          + "\n先运行 get_tools.bat 获取 apktool/签名器，并准备好 base.apk。")

    url = (params.get("url") or "").strip()
    if not url:
        raise RepackError("网址不能为空")
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    app_name = (params.get("app_name") or "WebApp").strip() or "WebApp"
    theme_color = (params.get("theme_color") or "#1f6feb").strip()
    if not re.match(r'^#[0-9A-Fa-f]{6}$', theme_color):
        theme_color = "#1f6feb"
    ua_mode = params.get("ua_mode") or "mobile"
    custom_ua = params.get("custom_ua") or ""
    features = params.get("features") or {}

    sn = safe_name(app_name)
    work_dir = os.path.join(WORK, sn + "_" + str(int(time.time())))
    decoded = os.path.join(work_dir, "decoded")
    unsigned = os.path.join(work_dir, sn + "_unsigned.apk")
    out_dir = params.get("output_dir") or OUTPUT
    final_dir = os.path.join(out_dir, sn)
    os.makedirs(final_dir, exist_ok=True)

    new_package = None
    if params.get("allow_multiple"):
        suf = (params.get("name_suffix") or "").strip()
        if not suf:
            suf = "%04x" % (int(time.time()) & 0xffff)
        # 后缀必须能拼成合法 Java 标识符（不能以数字开头）
        if not suf or not suf[0].isalpha():
            suf = "a" + suf
        parts = BASE_PACKAGE.split(".")
        parts[-1] = parts[-1] + suf
        new_package = ".".join(parts)

    log("【1/5】反编译基础包……")
    decode_apk(tools["apktool"], tools["base_apk"], decoded)

    log("【2/5】注入配置（网址/功能/主题/图标）……")
    cfg = build_config(url, app_name, ua_mode, custom_ua, features, theme_color)
    patch_decoded(decoded, cfg, app_name, theme_color,
                  params.get("icon_path"), new_package)

    log("【3/5】回编译 APK……")
    build_apk(tools["apktool"], decoded, unsigned)

    log("【4/5】对齐并签名……")
    signed = sign_apk(tools["signer"], tools["keystore"], unsigned, final_dir)

    log("【5/5】整理产物……")
    final_name = sn + ".apk"
    final_path = os.path.join(final_dir, final_name)
    if os.path.abspath(signed) != os.path.abspath(final_path):
        shutil.move(signed, final_path)

    # 清理中间产物
    try:
        shutil.rmtree(work_dir)
    except Exception:
        pass

    log("完成！APK 已生成：%s" % final_path)
    return final_path


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Web2ApkVideo 免SDK改包")
    ap.add_argument("--url", required=True)
    ap.add_argument("--name", default="WebApp")
    ap.add_argument("--theme", default="#1f6feb")
    ap.add_argument("--ua", default="mobile", choices=["mobile", "desktop", "custom"])
    ap.add_argument("--custom-ua", default="")
    ap.add_argument("--icon", default="")
    ap.add_argument("--base", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--no-gesture", action="store_true")
    ap.add_argument("--no-pip", action="store_true")
    ap.add_argument("--no-bg", action="store_true")
    ap.add_argument("--no-adblock", action="store_true")
    ap.add_argument("--no-download", action="store_true")
    ap.add_argument("--allow-multiple", action="store_true")
    a = ap.parse_args()
    features = {
        "fullscreenGesture": not a.no_gesture,
        "pip": not a.no_pip,
        "backgroundAudio": not a.no_bg,
        "adBlock": not a.no_adblock,
        "videoDownload": not a.no_download,
    }
    params = {
        "url": a.url, "app_name": a.name, "theme_color": a.theme,
        "ua_mode": a.ua, "custom_ua": a.custom_ua, "features": features,
        "icon_path": a.icon or None, "base_apk": a.base or None,
        "output_dir": a.out or None, "allow_multiple": a.allow_multiple,
    }
    try:
        print(repack(params))
    except RepackError as e:
        print("ERROR: " + str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
