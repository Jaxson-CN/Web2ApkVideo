#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
builder.py —— Web2ApkVideo 的 Windows 图形打包工具（ tkinter ）。

把任意网站一键打包成安卓 APK，重点优化了视频站的播放体验
（全屏沉浸+手势、画中画、后台播放、广告拦截、视频下载）。
日常使用免 Android SDK，只需：Java 运行时 + apktool.jar + uber-apk-signer.jar + base.apk。
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, colorchooser, messagebox

import repack

HERE = os.path.dirname(os.path.abspath(__file__))


class App:
    def __init__(self, root):
        self.root = root
        root.title("Web2ApkVideo · 网站打包成 APK")
        root.geometry("640x720")
        root.resizable(True, True)

        # 让 ttk 控件字体更清晰
        style = ttk.Style()
        try:
            style.configure(".", font=("Microsoft YaHei", 10))
        except Exception:
            pass

        self.build_ui()
        self.check_env()

    # ---------------- UI ----------------
    def build_ui(self):
        f = ttk.Frame(self.root, padding=12)
        f.pack(fill="both", expand=True)

        title = ttk.Label(f, text="网站 → 安卓 APK（视频站增强版）",
                          font=("Microsoft YaHei", 14, "bold"))
        title.pack(anchor="w", pady=(0, 8))
        hint = ttk.Label(f, text="首次使用前：运行 get_tools.bat 获取工具，并把 android-base 编译出的 base.apk 放到本目录。",
                         foreground="#666")
        hint.pack(anchor="w", pady=(0, 10))

        # 网址
        self.add_entry(f, "网站网址", "url", "https://www.bilibili.com")

        # 应用名称
        self.add_entry(f, "应用名称", "name", "我的视频站")

        # 主题色
        row = ttk.Frame(f)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="主题色", width=12).pack(side="left")
        self.theme_var = tk.StringVar(value="#1f6feb")
        self.theme_entry = ttk.Entry(row, textvariable=self.theme_var, width=12)
        self.theme_entry.pack(side="left", padx=(0, 6))
        ttk.Button(row, text="选择颜色", command=self.pick_color).pack(side="left")

        # UA
        row = ttk.Frame(f)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="浏览器UA", width=12).pack(side="left")
        self.ua_var = tk.StringVar(value="mobile")
        cb = ttk.Combobox(row, textvariable=self.ua_var, state="readonly", width=14,
                         values=["mobile", "desktop", "custom"])
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", self.on_ua_change)
        self.custom_ua_var = tk.StringVar()
        self.custom_ua_entry = ttk.Entry(row, textvariable=self.custom_ua_var, width=30)
        self.custom_ua_entry.pack(side="left", padx=6)
        self.custom_ua_entry.configure(state="disabled")

        # 功能勾选
        feat_frame = ttk.LabelFrame(f, text="视频增强功能", padding=8)
        feat_frame.pack(fill="x", pady=8)
        self.feat = {}
        for key, label in [
            ("fullscreenGesture", "全屏沉浸 + 手势调亮度/音量"),
            ("pip", "画中画（小窗）播放"),
            ("backgroundAudio", "后台音频（退出 App 继续放）"),
            ("adBlock", "广告 / 弹窗拦截"),
            ("videoDownload", "视频检测与下载"),
        ]:
            v = tk.BooleanVar(value=True)
            self.feat[key] = v
            ttk.Checkbutton(feat_frame, text=label, variable=v).pack(anchor="w")

        # 图标
        row = ttk.Frame(f)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="启动图标", width=12).pack(side="left")
        self.icon_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.icon_var, width=40).pack(side="left", padx=(0, 6))
        ttk.Button(row, text="浏览", command=self.pick_icon).pack(side="left")

        # 多包共存
        self.multi_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="允许同手机装多个（自动改包名）",
                        variable=self.multi_var).pack(anchor="w", pady=4)

        # 高级：base.apk / 输出目录
        adv = ttk.LabelFrame(f, text="高级（一般不用改）", padding=8)
        adv.pack(fill="x", pady=8)
        row = ttk.Frame(adv)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="基础APK", width=10).pack(side="left")
        self.base_var = tk.StringVar(value=os.path.join(HERE, "base.apk"))
        ttk.Entry(row, textvariable=self.base_var, width=42).pack(side="left", padx=(0, 6))
        ttk.Button(row, text="浏览", command=self.pick_base).pack(side="left")
        row = ttk.Frame(adv)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="输出目录", width=10).pack(side="left")
        self.out_var = tk.StringVar(value=os.path.join(HERE, "output"))
        ttk.Entry(row, textvariable=self.out_var, width=42).pack(side="left", padx=(0, 6))
        ttk.Button(row, text="浏览", command=self.pick_out).pack(side="left")

        # 按钮
        btn_row = ttk.Frame(f)
        btn_row.pack(fill="x", pady=(10, 4))
        self.start_btn = ttk.Button(btn_row, text="▶ 开始打包", command=self.start)
        self.start_btn.pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="打开输出文件夹", command=self.open_out).pack(side="left")

        # 日志
        ttk.Label(f, text="运行日志").pack(anchor="w", pady=(6, 2))
        self.log = tk.Text(f, height=12, bg="#0f1115", fg="#d6e0ff",
                           font=("Consolas", 9))
        self.log.pack(fill="both", expand=True)
        self.log.insert("1.0", "就绪。\n")

    def add_entry(self, parent, label, attr, default):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text=label, width=12).pack(side="left")
        var = tk.StringVar(value=default)
        setattr(self, attr + "_var", var)
        ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)

    # ---------------- 交互 ----------------
    def pick_color(self):
        c = colorchooser.askcolor(initialcolor=self.theme_var.get())
        if c and c[1]:
            self.theme_var.set(c[1])

    def on_ua_change(self, e):
        if self.ua_var.get() == "custom":
            self.custom_ua_entry.configure(state="normal")
        else:
            self.custom_ua_entry.configure(state="disabled")

    def pick_icon(self):
        p = filedialog.askopenfilename(title="选择图标（建议方形高清 PNG）",
                                      filetypes=[("PNG", "*.png")])
        if p:
            self.icon_var.set(p)

    def pick_base(self):
        p = filedialog.askopenfilename(title="选择 base.apk",
                                      filetypes=[("APK", "*.apk")])
        if p:
            self.base_var.set(p)

    def pick_out(self):
        p = filedialog.askdirectory(title="选择输出目录")
        if p:
            self.out_var.set(p)

    def open_out(self):
        d = self.out_var.get()
        if os.path.isdir(d):
            os.startfile(d)

    def check_env(self):
        tools = repack.find_tools(self.base_var.get())
        miss = tools["missing"]
        if miss:
            self.log.insert("end", "⚠ 环境未就绪：\n  - " + "\n  - ".join(miss) + "\n"
                            "请先运行 get_tools.bat，并把 base.apk 放到本目录。\n")
            self.log.see("end")

    def gui_log(self, msg):
        self.root.after(0, lambda: self._append(msg))

    def _append(self, msg):
        self.log.insert("end", msg + "\n")
        self.log.see("end")

    def collect(self):
        return {
            "url": self.url_var.get(),
            "app_name": self.name_var.get(),
            "theme_color": self.theme_var.get(),
            "ua_mode": self.ua_var.get(),
            "custom_ua": self.custom_ua_var.get(),
            "features": {k: v.get() for k, v in self.feat.items()},
            "icon_path": self.icon_var.get() or None,
            "base_apk": self.base_var.get() or None,
            "output_dir": self.out_var.get() or None,
            "allow_multiple": self.multi_var.get(),
        }

    def start(self):
        params = self.collect()
        if not params["url"].strip():
            messagebox.showerror("提示", "请先填写网站网址")
            return
        self.start_btn.configure(state="disabled", text="打包中…")
        self._append("开始打包：" + params["app_name"])
        threading.Thread(target=self._run, args=(params,), daemon=True).start()

    def _run(self, params):
        try:
            repack.log = self.gui_log
            out = repack.repack(params)
            self.gui_log("✅ 完成！APK：" + out)
            self.root.after(0, lambda: messagebox.showinfo("完成", "APK 已生成：\n" + out))
        except repack.RepackError as e:
            self.gui_log("❌ " + str(e))
        except Exception as e:
            self.gui_log("❌ 异常：" + repr(e))
        finally:
            self.root.after(0, lambda: self.start_btn.configure(
                state="normal", text="▶ 开始打包"))


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
