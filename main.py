# main.py — 招聘猫 主程序（GUI 入口）
import sys
import os
import threading
import logging
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

from models import ScanResult, Notice
from scraper import WebScraper
from storage import Storage
from comparator import compare, summarize_results
from formatter import export_to_excel, export_to_csv

# ── 日志配置 ────────────────────────────────────────────────────────────
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

APP_NAME = "招聘猫"
APP_VERSION = "1.0.0"

# ── 界面主题 ────────────────────────────────────────────────────────────
FONT = "Microsoft YaHei UI"

BG_COLOR       = "#F5F7FA"
PRIMARY        = "#2E75B6"
ACCENT         = "#E63946"
PRIMARY_HOVER  = "#1A5276"   # 按钮悬停深蓝
ACCENT_HOVER   = "#C0392B"   # 强调按钮悬停红
LIGHT_BLUE_FG  = "#AED6F1"   # 标题栏浅蓝文字
STATUS_BG      = "#DDE3EE"   # 状态栏背景
STATUS_FG      = "#2C3E50"   # 状态栏文字
DIM_FG         = "#7F8C8D"   # 次要/倒计时文字
WARN_COLOR     = "#E67E22"   # 警告/错误橙
NEW_COLOR      = "#27AE60"
GONE_COLOR     = "#E74C3C"
UNCHANGED_COLOR = "#95A5A6"
NEW_BG         = "#E8F8F0"   # 新增行背景
GONE_BG        = "#FDEDEC"   # 消失行背景
ERROR_BG       = "#FDF2E9"   # 错误行背景
LOG_BG         = "#1E1E1E"   # 日志区背景
LOG_FG         = "#D4D4D4"   # 日志区文字


# ══════════════════════════════════════════════════════════════════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME}  v{APP_VERSION}")
        self.geometry("1100x740")
        self.minsize(900, 600)
        self.configure(bg=BG_COLOR)

        # 设置字体
        self.default_font = (FONT, 10)
        self.option_add("*Font", self.default_font)

        # 设置图标（打包后用）
        self._set_icon()

        self.storage = Storage()
        self.scraper = WebScraper()
        self.scan_results: List[ScanResult] = []
        self._scan_thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()

        # 定时扫描状态
        self._auto_scan_enabled = False
        self._auto_scan_after_id = None   # tkinter after() 句柄
        self._auto_scan_countdown = 0     # 剩余秒数
        self._countdown_after_id = None

        self._build_ui()
        self._apply_style()
        self._load_url_list()   # 启动时恢复上次的网址列表
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── 图标 ──────────────────────────────────────────────────────────────
    def _set_icon(self):
        icon_path = Path(getattr(sys, "_MEIPASS", ".")) / "icon.ico"
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                pass

    # ── 样式 ──────────────────────────────────────────────────────────────
    def _apply_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=BG_COLOR)
        style.configure("TLabel", background=BG_COLOR, font=self.default_font)
        style.configure("TButton", font=self.default_font, padding=5)
        style.configure("Primary.TButton", background=PRIMARY, foreground="white",
                        font=(FONT, 10, "bold"))
        style.map("Primary.TButton", background=[("active", PRIMARY_HOVER)])
        style.configure("Accent.TButton", background=ACCENT, foreground="white",
                        font=(FONT, 10, "bold"))
        style.map("Accent.TButton", background=[("active", ACCENT_HOVER)])
        style.configure("Treeview", font=(FONT, 9), rowheight=24)
        style.configure("Treeview.Heading", font=(FONT, 9, "bold"),
                        background=PRIMARY, foreground="white")
        style.map("Treeview.Heading", background=[("active", PRIMARY_HOVER)])
        style.configure("TNotebook.Tab", font=(FONT, 10), padding=[12, 4])

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 界面构建
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _build_ui(self):
        # ── 顶部标题栏 ───────────────────────────────────────────────────
        header = tk.Frame(self, bg=PRIMARY, height=52)
        header.pack(fill="x")
        tk.Label(
            header, text="🐱  招聘猫  Recruitment Tracker",
            bg=PRIMARY, fg="white",
            font=(FONT, 15, "bold")
        ).pack(side="left", padx=18, pady=10)
        tk.Label(
            header, text=f"v{APP_VERSION}",
            bg=PRIMARY, fg=LIGHT_BLUE_FG,
            font=(FONT, 9)
        ).pack(side="right", padx=18, pady=10)

        # ── 主体：左右分栏 ───────────────────────────────────────────────
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=10, pady=(8, 0))

        left = ttk.Frame(body, width=280)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        self._build_left_panel(left)
        self._build_right_panel(right)

        # ── 底部状态栏 ───────────────────────────────────────────────────
        statusbar = tk.Frame(self, bg=STATUS_BG, height=28)
        statusbar.pack(fill="x", side="bottom")

        self.status_var = tk.StringVar(value="就绪")
        tk.Label(statusbar, textvariable=self.status_var,
                 bg=STATUS_BG, fg=STATUS_FG,
                 font=(FONT, 9), anchor="w").pack(side="left", padx=10)

        self.progress = ttk.Progressbar(statusbar, mode="indeterminate", length=160)
        self.progress.pack(side="right", padx=10, pady=3)

    # ── 左侧面板 ─────────────────────────────────────────────────────────
    def _build_left_panel(self, parent):
        # 网站列表标题
        title_row = ttk.Frame(parent)
        title_row.pack(fill="x", pady=(4, 2))
        ttk.Label(title_row, text="📋 监控网站列表",
                  font=(FONT, 10, "bold")).pack(side="left")

        # 操作按钮行
        btn_row = ttk.Frame(parent)
        btn_row.pack(fill="x", pady=(0, 4))
        ttk.Button(btn_row, text="导入 TXT", command=self._import_txt, width=9).pack(side="left", padx=(0, 4))
        ttk.Button(btn_row, text="添加", command=self._add_url, width=6).pack(side="left", padx=(0, 4))
        ttk.Button(btn_row, text="删除", command=self._remove_url, width=6).pack(side="left")

        # 网站 Listbox
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        self.url_listbox = tk.Listbox(
            list_frame, yscrollcommand=scrollbar.set,
            font=(FONT, 9),
            selectbackground=PRIMARY, selectforeground="white",
            activestyle="none", relief="flat", bd=1,
            highlightthickness=1, highlightcolor=PRIMARY
        )
        self.url_listbox.pack(fill="both", expand=True)
        scrollbar.config(command=self.url_listbox.yview)
        self.url_listbox.bind("<Double-Button-1>", self._open_url_browser)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=8)

        # 扫描控制
        ttk.Button(parent, text="▶  开始扫描", style="Primary.TButton",
                   command=self._start_scan).pack(fill="x", pady=2)
        ttk.Button(parent, text="⏹  停止", command=self._stop_scan).pack(fill="x", pady=2)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=8)

        # ── 定时自动扫描 ──────────────────────────────────────────────
        ttk.Label(parent, text="⏱ 定时自动扫描",
                  font=(FONT, 9, "bold")).pack(anchor="w")

        interval_row = ttk.Frame(parent)
        interval_row.pack(fill="x", pady=(3, 2))
        ttk.Label(interval_row, text="间隔：").pack(side="left")

        INTERVAL_OPTIONS = ["30 分钟", "1 小时", "2 小时", "4 小时", "8 小时", "自定义"]
        self._interval_var = tk.StringVar(value="2 小时")
        self._interval_combo = ttk.Combobox(
            interval_row, textvariable=self._interval_var,
            values=INTERVAL_OPTIONS, state="readonly", width=9
        )
        self._interval_combo.pack(side="left", padx=(2, 0))
        self._interval_combo.bind("<<ComboboxSelected>>", self._on_interval_changed)

        # 自定义分钟输入（默认隐藏）
        self._custom_frame = ttk.Frame(parent)
        self._custom_frame.pack(fill="x", pady=(0, 2))
        ttk.Label(self._custom_frame, text="自定义分钟数：").pack(side="left")
        self._custom_min_var = tk.StringVar(value="60")
        vcmd = (self.register(lambda s: s.isdigit() and 1 <= int(s) <= 9999 if s else True), "%P")
        ttk.Entry(self._custom_frame, textvariable=self._custom_min_var,
                  width=6, validate="key", validatecommand=vcmd).pack(side="left", padx=(2, 0))
        ttk.Label(self._custom_frame, text="分钟").pack(side="left", padx=(2, 0))
        self._custom_frame.pack_forget()   # 默认隐藏

        self._auto_toggle_btn = ttk.Button(
            parent, text="启用定时扫描", command=self._toggle_auto_scan
        )
        self._auto_toggle_btn.pack(fill="x", pady=2)

        self._countdown_label = ttk.Label(
            parent, text="", foreground=DIM_FG,
            font=(FONT, 8)
        )
        self._countdown_label.pack(anchor="w")

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=8)

        # 导出按钮
        ttk.Label(parent, text="导出结果：",
                  font=(FONT, 9, "bold")).pack(anchor="w")
        export_row = ttk.Frame(parent)
        export_row.pack(fill="x", pady=4)
        ttk.Button(export_row, text="导出 Excel", command=self._export_excel, width=12).pack(side="left", padx=(0, 4))
        ttk.Button(export_row, text="导出 CSV", command=self._export_csv, width=10).pack(side="left")

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=8)

        # 数据目录
        ttk.Button(parent, text="📂 打开数据目录",
                   command=self._open_data_dir).pack(fill="x", pady=2)
        ttk.Button(parent, text="🗑  清空历史数据",
                   command=self._clear_history).pack(fill="x", pady=2)

    # ── 右侧面板（Notebook） ─────────────────────────────────────────────
    def _build_right_panel(self, parent):
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill="both", expand=True)

        # Tab1：扫描结果
        tab_results = ttk.Frame(self.notebook)
        self.notebook.add(tab_results, text=" 扫描结果 ")
        self._build_results_tab(tab_results)

        # Tab2：新通知
        tab_new = ttk.Frame(self.notebook)
        self.notebook.add(tab_new, text=" 🆕 新通知 ")
        self._build_new_tab(tab_new)

        # Tab3：运行日志
        tab_log = ttk.Frame(self.notebook)
        self.notebook.add(tab_log, text=" 运行日志 ")
        self._build_log_tab(tab_log)

        # Tab4：报告摘要
        tab_summary = ttk.Frame(self.notebook)
        self.notebook.add(tab_summary, text=" 报告摘要 ")
        self._build_summary_tab(tab_summary)

    def _build_results_tab(self, parent):
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill="x", pady=(4, 2))
        ttk.Label(toolbar, text="双击行可在浏览器中打开链接").pack(side="left", padx=4)
        ttk.Button(toolbar, text="只看新通知", command=self._filter_new).pack(side="right", padx=4)
        ttk.Button(toolbar, text="显示全部", command=self._filter_all).pack(side="right", padx=4)

        cols = ("status", "website", "title", "date", "link")
        self.result_tree = ttk.Treeview(parent, columns=cols, show="headings", selectmode="browse")
        self.result_tree.heading("status", text="状态")
        self.result_tree.heading("website", text="来源网站")
        self.result_tree.heading("title", text="通知标题")
        self.result_tree.heading("date", text="日期")
        self.result_tree.heading("link", text="链接")
        self.result_tree.column("status", width=60, anchor="center")
        self.result_tree.column("website", width=150)
        self.result_tree.column("title", width=320)
        self.result_tree.column("date", width=90, anchor="center")
        self.result_tree.column("link", width=260)

        self.result_tree.tag_configure("new", background=NEW_BG, foreground=NEW_COLOR)
        self.result_tree.tag_configure("gone", background=GONE_BG, foreground=GONE_COLOR)
        self.result_tree.tag_configure("error", background=ERROR_BG, foreground=WARN_COLOR)

        vsb = ttk.Scrollbar(parent, orient="vertical", command=self.result_tree.yview)
        hsb = ttk.Scrollbar(parent, orient="horizontal", command=self.result_tree.xview)
        self.result_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.result_tree.pack(fill="both", expand=True)
        self.result_tree.bind("<Double-Button-1>", self._open_notice_link)

    def _build_new_tab(self, parent):
        info_row = ttk.Frame(parent)
        info_row.pack(fill="x", pady=(4, 2))
        self.new_count_label = ttk.Label(info_row, text="新通知：0 条",
                                         font=(FONT, 10, "bold"),
                                         foreground=NEW_COLOR)
        self.new_count_label.pack(side="left", padx=6)

        cols = ("website", "title", "date", "link")
        self.new_tree = ttk.Treeview(parent, columns=cols, show="headings", selectmode="browse")
        self.new_tree.heading("website", text="来源网站")
        self.new_tree.heading("title", text="通知标题")
        self.new_tree.heading("date", text="日期")
        self.new_tree.heading("link", text="链接")
        self.new_tree.column("website", width=170)
        self.new_tree.column("title", width=360)
        self.new_tree.column("date", width=100, anchor="center")
        self.new_tree.column("link", width=310)
        self.new_tree.tag_configure("new", background=NEW_BG, foreground=NEW_COLOR)

        vsb = ttk.Scrollbar(parent, orient="vertical", command=self.new_tree.yview)
        vsb.pack(side="right", fill="y")
        self.new_tree.pack(fill="both", expand=True)
        self.new_tree.bind("<Double-Button-1>", self._open_new_link)

    def _build_log_tab(self, parent):
        self.log_text = scrolledtext.ScrolledText(
            parent, wrap="word",
            font=("Consolas", 9),
            bg=LOG_BG, fg=LOG_FG,
            insertbackground="white",
            state="disabled"
        )
        self.log_text.pack(fill="both", expand=True)
        btn_row = ttk.Frame(parent)
        btn_row.pack(fill="x", pady=2)
        ttk.Button(btn_row, text="清空日志", command=self._clear_log).pack(side="right", padx=4)

    def _build_summary_tab(self, parent):
        self.summary_text = scrolledtext.ScrolledText(
            parent, wrap="word",
            font=(FONT, 10),
            state="disabled"
        )
        self.summary_text.pack(fill="both", expand=True)
        btn_row = ttk.Frame(parent)
        btn_row.pack(fill="x", pady=2)
        ttk.Button(btn_row, text="复制摘要", command=self._copy_summary).pack(side="right", padx=4)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 左侧面板操作
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _import_txt(self):
        path = filedialog.askopenfilename(
            title="选择网站列表 TXT 文件",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        except UnicodeDecodeError:
            with open(path, "r", encoding="gbk", errors="ignore") as f:
                lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        existing = set(self.url_listbox.get(0, "end"))
        added = 0
        for url in lines:
            if url not in existing:
                self.url_listbox.insert("end", url)
                added += 1
        self._log(f"从文件导入 {added} 个网站（跳过 {len(lines)-added} 个重复）")
        self._set_status(f"已导入 {added} 个网站")
        self._save_url_list()

    def _add_url(self):
        dialog = _InputDialog(self, title="添加网站", prompt="请输入网站地址：")
        url = dialog.result
        if url:
            url = url.strip()
            existing = set(self.url_listbox.get(0, "end"))
            if url in existing:
                messagebox.showinfo("提示", "该网站已在列表中")
                return
            self.url_listbox.insert("end", url)
            self._log(f"手动添加网站：{url}")
            self._save_url_list()

    def _remove_url(self):
        sel = self.url_listbox.curselection()
        if not sel:
            return
        url = self.url_listbox.get(sel[0])
        if messagebox.askyesno("确认", f"删除网站：\n{url}"):
            self.url_listbox.delete(sel[0])
            self._log(f"删除网站：{url}")
            self._save_url_list()

    def _open_url_browser(self, event=None):
        sel = self.url_listbox.curselection()
        if sel:
            url = self.url_listbox.get(sel[0])
            if not url.startswith("http"):
                url = "https://" + url
            webbrowser.open(url)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 定时自动扫描
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _get_interval_seconds(self) -> int:
        """根据当前选择返回间隔秒数"""
        val = self._interval_var.get()
        mapping = {
            "30 分钟": 30 * 60,
            "1 小时":  60 * 60,
            "2 小时": 120 * 60,
            "4 小时": 240 * 60,
            "8 小时": 480 * 60,
        }
        if val in mapping:
            return mapping[val]
        # 自定义
        try:
            mins = int(self._custom_min_var.get())
            return max(1, mins) * 60
        except ValueError:
            return 120 * 60

    def _on_interval_changed(self, event=None):
        if self._interval_var.get() == "自定义":
            self._custom_frame.pack(fill="x", pady=(0, 2),
                                    before=self._auto_toggle_btn)
        else:
            self._custom_frame.pack_forget()
        # 若已启用，重新排期
        if self._auto_scan_enabled:
            self._cancel_countdown()
            self._schedule_next_scan()

    def _toggle_auto_scan(self):
        if not self._auto_scan_enabled:
            if not list(self.url_listbox.get(0, "end")):
                messagebox.showwarning("提示", "请先添加或导入监控网站")
                return
            self._auto_scan_enabled = True
            self._interval_combo.config(state="disabled")
            self._auto_toggle_btn.config(text="停止定时扫描")
            self._log(f"定时扫描已启用，间隔 {self._get_interval_seconds()//60} 分钟")
            self._start_scan()   # 立即执行一次
        else:
            self._auto_scan_enabled = False
            self._cancel_countdown()
            self._interval_combo.config(state="readonly")
            self._auto_toggle_btn.config(text="启用定时扫描")
            self._countdown_label.config(text="")
            self._log("定时扫描已停止")
            self._set_status("定时扫描已停止")

    def _schedule_next_scan(self):
        """在间隔秒数后触发下一次扫描"""
        self._cancel_countdown()
        seconds = self._get_interval_seconds()
        self._auto_scan_countdown = seconds
        self._tick_countdown()
        self._auto_scan_after_id = self.after(seconds * 1000, self._auto_trigger_scan)

    def _auto_trigger_scan(self):
        if self._auto_scan_enabled:
            self._log("定时触发扫描")
            self._start_scan()

    def _tick_countdown(self):
        """每秒刷新倒计时标签"""
        if not self._auto_scan_enabled or self._auto_scan_countdown <= 0:
            return
        remaining = self._auto_scan_countdown
        h, rem = divmod(remaining, 3600)
        m, s = divmod(rem, 60)
        if h:
            text = f"下次扫描：{h}h {m:02d}m {s:02d}s"
        else:
            text = f"下次扫描：{m:02d}m {s:02d}s"
        self._countdown_label.config(text=text)
        self._auto_scan_countdown -= 1
        self._countdown_after_id = self.after(1000, self._tick_countdown)

    def _cancel_countdown(self):
        if self._auto_scan_after_id:
            self.after_cancel(self._auto_scan_after_id)
            self._auto_scan_after_id = None
        if self._countdown_after_id:
            self.after_cancel(self._countdown_after_id)
            self._countdown_after_id = None

    def _on_close(self):
        self._cancel_countdown()
        self._stop_flag.set()
        self.destroy()

    # ── 网址列表持久化 ────────────────────────────────────────────────────

    def _url_list_path(self):
        return self.storage.data_dir / "_url_list.txt"

    def _save_url_list(self):
        """将当前 Listbox 中的网址保存到数据目录"""
        urls = list(self.url_listbox.get(0, "end"))
        try:
            with open(self._url_list_path(), "w", encoding="utf-8") as f:
                for url in urls:
                    f.write(url + "\n")
        except Exception as e:
            logger.warning(f"保存网址列表失败: {e}")

    def _load_url_list(self):
        """从数据目录加载上次保存的网址列表"""
        p = self._url_list_path()
        if not p.exists():
            return
        try:
            with open(p, "r", encoding="utf-8") as f:
                urls = [l.strip() for l in f if l.strip()]
            for url in urls:
                self.url_listbox.insert("end", url)
            if urls:
                self._log(f"已恢复上次网址列表，共 {len(urls)} 个网站")
        except Exception as e:
            logger.warning(f"加载网址列表失败: {e}")

    def _open_data_dir(self):
        d = str(self.storage.data_dir)
        os.startfile(d)

    def _clear_history(self):
        if messagebox.askyesno("确认", "清空所有历史数据后，下次扫描将把全部通知视为新通知。\n确定要清空吗？"):
            self.storage.clear_all()
            self._log("历史数据已清空")
            messagebox.showinfo("完成", "历史数据已清空")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 扫描逻辑（后台线程）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _start_scan(self):
        urls = list(self.url_listbox.get(0, "end"))
        if not urls:
            messagebox.showwarning("提示", "请先添加或导入监控网站")
            return
        if self._scan_thread and self._scan_thread.is_alive():
            messagebox.showinfo("提示", "扫描正在进行中，请等待完成")
            return

        self._stop_flag.clear()
        self.scan_results.clear()
        self._clear_trees()
        self.progress.start(10)
        self._set_status("扫描中…")
        self._log(f"开始扫描 {len(urls)} 个网站")

        self._scan_thread = threading.Thread(target=self._scan_worker, args=(urls,), daemon=True)
        self._scan_thread.start()

    def _scan_worker(self, urls: List[str]):
        scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        results: List[ScanResult] = []

        for i, url in enumerate(urls):
            if self._stop_flag.is_set():
                self._ui_log(f"扫描已中止（{i}/{len(urls)}）")
                break

            self._ui_log(f"[{i+1}/{len(urls)}] 正在扫描：{url}")
            self._ui_status(f"正在扫描 [{i+1}/{len(urls)}]：{url}")

            try:
                new_notices = self.scraper.scrape(url)
                old_notices = self.storage.load(url)
                result = compare(url, old_notices, new_notices, scan_time)
                self.storage.save(url, new_notices)
                self._ui_log(
                    f"  → 共 {len(new_notices)} 条，"
                    f"新增 {len(result.new_notices)} 条，消失 {len(result.gone_notices)} 条"
                )
            except Exception as e:
                logger.exception(f"抓取失败：{url}")
                result = ScanResult(website=url, scan_time=scan_time, error=str(e))
                self._ui_log(f"  ✗ 出错：{e}")

            results.append(result)
            self.after(0, lambda r=result: self._append_result(r))

        self.scan_results = results
        self.after(0, self._scan_done)

    def _scan_done(self):
        self.progress.stop()
        total_new = sum(len(r.new_notices) for r in self.scan_results)
        errors = sum(1 for r in self.scan_results if r.error)
        msg = f"扫描完成 | 共 {len(self.scan_results)} 个网站 | 新增通知 {total_new} 条 | 出错 {errors} 个"
        self._set_status(msg)
        self._log(msg)
        self._refresh_new_tab()
        self._update_summary()
        if total_new > 0:
            self.notebook.select(1)   # 跳到新通知 Tab
            self._ui_toast(f"发现 {total_new} 条新招聘通知！")
        # 定时扫描：完成后重新排期
        if self._auto_scan_enabled:
            self._schedule_next_scan()

    def _stop_scan(self):
        self._stop_flag.set()
        self._set_status("正在停止…")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 结果展示
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _append_result(self, result: ScanResult):
        """将一个网站的结果追加到 result_tree"""
        if result.error:
            self.result_tree.insert("", "end",
                values=("错误", result.website, result.error, "", ""),
                tags=("error",))
            return

        new_hashes = {n.content_hash for n in result.new_notices}
        gone_hashes = {n.content_hash for n in result.gone_notices}

        for n in result.all_notices:
            tag = "new" if n.content_hash in new_hashes else ""
            status = "🆕 新增" if tag == "new" else "  未变"
            self.result_tree.insert("", "end",
                values=(status, result.website, n.title, n.date, n.link),
                tags=(tag,))

        for n in result.gone_notices:
            self.result_tree.insert("", "end",
                values=("🗑 消失", result.website, n.title, n.date, n.link),
                tags=("gone",))

    def _refresh_new_tab(self):
        for item in self.new_tree.get_children():
            self.new_tree.delete(item)
        total = 0
        for r in self.scan_results:
            for n in r.new_notices:
                self.new_tree.insert("", "end",
                    values=(r.website, n.title, n.date, n.link),
                    tags=("new",))
                total += 1
        self.new_count_label.config(text=f"新通知：{total} 条")

    def _update_summary(self):
        text = summarize_results(self.scan_results)
        self.summary_text.config(state="normal")
        self.summary_text.delete("1.0", "end")
        self.summary_text.insert("end", text)
        self.summary_text.config(state="disabled")

    def _clear_trees(self):
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        for item in self.new_tree.get_children():
            self.new_tree.delete(item)
        self.new_count_label.config(text="新通知：0 条")
        self.summary_text.config(state="normal")
        self.summary_text.delete("1.0", "end")
        self.summary_text.config(state="disabled")

    def _filter_new(self):
        for item in self.result_tree.get_children():
            tags = self.result_tree.item(item, "tags")
            if "new" not in tags:
                self.result_tree.detach(item)

    def _filter_all(self):
        self._clear_trees()
        for r in self.scan_results:
            self._append_result(r)

    # ── 链接跳转 ─────────────────────────────────────────────────────────
    def _open_notice_link(self, event=None):
        item = self.result_tree.focus()
        if item:
            link = self.result_tree.item(item, "values")[4]
            if link and link.startswith("http"):
                webbrowser.open(link)

    def _open_new_link(self, event=None):
        item = self.new_tree.focus()
        if item:
            link = self.new_tree.item(item, "values")[3]
            if link and link.startswith("http"):
                webbrowser.open(link)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 导出
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _export_excel(self):
        if not self.scan_results:
            messagebox.showinfo("提示", "尚无扫描结果，请先执行扫描")
            return
        default_name = f"招聘猫结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel 文件", "*.xlsx")],
            initialfile=default_name,
            title="保存 Excel 文件"
        )
        if not path:
            return
        try:
            export_to_excel(self.scan_results, path)
            messagebox.showinfo("完成", f"Excel 已保存：\n{path}")
            os.startfile(path)
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def _export_csv(self):
        if not self.scan_results:
            messagebox.showinfo("提示", "尚无扫描结果，请先执行扫描")
            return
        default_name = f"招聘猫结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv")],
            initialfile=default_name,
            title="保存 CSV 文件"
        )
        if not path:
            return
        try:
            export_to_csv(self.scan_results, path)
            messagebox.showinfo("完成", f"CSV 已保存：\n{path}")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 日志与状态
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _log(self, msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {msg}\n"
        self.log_text.config(state="normal")
        self.log_text.insert("end", line)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    def _copy_summary(self):
        text = self.summary_text.get("1.0", "end")
        self.clipboard_clear()
        self.clipboard_append(text)
        self._set_status("摘要已复制到剪贴板")

    def _set_status(self, msg: str):
        self.status_var.set(msg)

    def _ui_log(self, msg: str):
        """线程安全日志"""
        self.after(0, lambda: self._log(msg))

    def _ui_status(self, msg: str):
        self.after(0, lambda: self._set_status(msg))

    def _ui_toast(self, msg: str):
        """简单弹出提示（非阻塞）"""
        toast = tk.Toplevel(self)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(bg=NEW_COLOR)
        tk.Label(toast, text=f"  {msg}  ",
                 bg=NEW_COLOR, fg="white",
                 font=(FONT, 12, "bold"),
                 padx=16, pady=12).pack()
        # 居中显示
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 400) // 2
        y = self.winfo_y() + 80
        toast.geometry(f"400x50+{x}+{y}")
        toast.after(3000, toast.destroy)


# ══════════════════════════════════════════════════════════════════════════
# 简易输入对话框
# ══════════════════════════════════════════════════════════════════════════

class _InputDialog(tk.Toplevel):
    def __init__(self, parent, title: str, prompt: str):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.result = None

        ttk.Label(self, text=prompt, padding=(12, 8)).pack(anchor="w")
        self.entry = ttk.Entry(self, width=50)
        self.entry.pack(padx=12, pady=(0, 8))
        self.entry.focus_set()

        btn_row = ttk.Frame(self)
        btn_row.pack(pady=(0, 10))
        ttk.Button(btn_row, text="确定", command=self._ok).pack(side="left", padx=6)
        ttk.Button(btn_row, text="取消", command=self.destroy).pack(side="left", padx=6)

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())

        # 居中
        parent.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 400) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 120) // 2
        self.geometry(f"400x100+{x}+{y}")
        self.wait_window()

    def _ok(self):
        self.result = self.entry.get().strip()
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = App()
    app.mainloop()
