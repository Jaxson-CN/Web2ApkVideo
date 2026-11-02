#!/usr/bin/env python3
"""
云端打包用的配置注入脚本（针对 android-base 源码树，而非 apktool 解码树）。
在 GitHub Actions 中于 gradle 编译前运行：把用户输入写进 android-base 的
assets/config.json、strings.xml、colors.xml，可选替换图标、可选改包名。

与 Windows 生成器 repack.py 的区别：这里改的是"源码"，包名改动要移动
src/main/java 下的目录并替换 .java 文件里的 package 声明，而非 smali。
"""
import argparse
import json
import os
import re
import shutil
import sys
import urllib.request

BASE_DIR = "android-base"
APP_DIR = os.path.join(BASE_DIR, "app")
SRC_JAVA_DIR = os.path.join(APP_DIR, "src", "main", "java")
RES_DIR = os.path.join(APP_DIR, "src", "main", "res")
ASSETS_DIR = os.path.join(APP_DIR, "src", "main", "assets")
MANIFEST = os.path.join(APP_DIR, "src", "main", "AndroidManifest.xml")
BASE_PACKAGE = "com.web2apk.video"

KNOWN_FEATURES = [
    "fullscreenGesture",
    "pip",
    "backgroundAudio",
    "adBlock",
    "videoDownload",
]

MIPMAP_SIZES = {
    "mdpi": 48,
    "hdpi": 72,
    "xhdpi": 96,
    "xxhdpi": 144,
    "xxxhdpi": 192,
}


def normalize_url(u):
    u = (u or "").strip()
    if not u:
        return ""
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", u):
        u = "https://" + u
    return u


def write_config(url, name, theme, ua, custom_ua, features):
    cfg = {
        "startUrl": normalize_url(url),
        "appName": name,
        "uaMode": ua,
        "customUserAgent": custom_ua or "",
        "features": {f: (f in features) for f in KNOWN_FEATURES},
        "themeColor": theme or "#1f6feb",
    }
    os.makedirs(ASSETS_DIR, exist_ok=True)
    with open(os.path.join(ASSETS_DIR, "config.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return cfg


def read_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_text(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def replace_in_file(path, mapping):
    if not os.path.isfile(path):
        return False
    c = read_text(path)
    for old, new in mapping.items():
        c = c.replace(old, new)
    write_text(path, c)
    return True


def patch_meta(name, theme):
    # 应用名
    sp = os.path.join(RES_DIR, "values", "strings.xml")
    if os.path.isfile(sp):
        c = read_text(sp)
        c = re.sub(
            r'(<string name="app_name">)[^<]*(</string>)',
            r"\g<1>%s\g<2>" % name,
            c,
        )
        write_text(sp, c)
    # 主题色（colorPrimary / colorAccent 都是默认蓝，一并替换）
    cp = os.path.join(RES_DIR, "values", "colors.xml")
    if os.path.isfile(cp):
        c = read_text(cp)
        c = c.replace("#1f6feb", theme or "#1f6feb")
        write_text(cp, c)


def process_icon(icon_url):
    if not icon_url:
        return
    try:
        import io

        from PIL import Image

        data = urllib.request.urlopen(icon_url, timeout=30).read()
        im = Image.open(io.BytesIO(data)).convert("RGBA")
        for d, size in MIPMAP_SIZES.items():
            dp = os.path.join(RES_DIR, "mipmap-" + d)
            if not os.path.isdir(dp):
                continue
            thumb = im.resize((size, size), Image.LANCZOS)
            for name in ("ic_launcher.png", "ic_launcher_round.png"):
                thumb.save(os.path.join(dp, name))
        print("icon replaced from", icon_url)
    except Exception as e:
        print("icon process failed, keep default icon:", e)


def valid_package(p):
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z0-9_]+)+$", p))


def rename_package(target):
    # 1) build.gradle 的 namespace + applicationId
    bg = os.path.join(APP_DIR, "build.gradle")
    if os.path.isfile(bg):
        c = read_text(bg)
        c = re.sub(r"namespace '[^\']*'", "namespace '%s'" % target, c)
        c = re.sub(r"applicationId '[^\']*'", "applicationId '%s'" % target, c)
        write_text(bg, c)

    # 2) Manifest 的 package 属性（AGP 8 忽略它，但改了更干净）
    replace_in_file(MANIFEST, {'package="%s"' % BASE_PACKAGE: 'package="%s"' % target})

    # 3) 移动 Java 源码目录：基于 target 全路径重建，避免嵌套
    old_dir = os.path.join(SRC_JAVA_DIR, *BASE_PACKAGE.split("."))
    new_dir = os.path.join(SRC_JAVA_DIR, *target.split("."))
    if os.path.isdir(old_dir) and old_dir != new_dir:
        os.makedirs(new_dir, exist_ok=True)
        for fn in os.listdir(old_dir):
            if fn.endswith(".java"):
                src = os.path.join(old_dir, fn)
                dst = os.path.join(new_dir, fn)
                cc = read_text(src)
                cc = cc.replace("package %s;" % BASE_PACKAGE, "package %s;" % target)
                cc = cc.replace(BASE_PACKAGE + ".", target + ".")
                write_text(dst, cc)
        shutil.rmtree(old_dir)

    # 4) 布局文件里若有全限定包名引用
    layout_dir = os.path.join(RES_DIR, "layout")
    if os.path.isdir(layout_dir):
        for fn in os.listdir(layout_dir):
            if fn.endswith(".xml"):
                replace_in_file(
                    os.path.join(layout_dir, fn),
                    {BASE_PACKAGE + ".": target + "."},
                )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--theme", default="#1f6feb")
    ap.add_argument("--ua", default="mobile")
    ap.add_argument("--custom-ua", default="")
    ap.add_argument("--features", default=",".join(KNOWN_FEATURES))
    ap.add_argument("--package", default="")
    ap.add_argument("--allow-multiple", default="false")
    ap.add_argument("--icon-url", default="")
    a = ap.parse_args()

    feats = [x.strip() for x in a.features.split(",") if x.strip()]
    cfg = write_config(a.url, a.name, a.theme, a.ua, a.custom_ua, feats)
    patch_meta(a.name, a.theme)
    process_icon(a.icon_url)

    target = None
    if a.package and valid_package(a.package):
        target = a.package
    elif a.allow_multiple.lower() in ("1", "true", "yes", "on"):
        suf = "%04x" % (os.getpid() & 0xFFFF)
        target = BASE_PACKAGE + suf

    if target and target != BASE_PACKAGE:
        rename_package(target)

    print(
        "INJECT_DONE url=%s name=%s pkg=%s"
        % (cfg["startUrl"], cfg["appName"], target or BASE_PACKAGE)
    )


if __name__ == "__main__":
    main()
