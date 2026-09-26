"""Light desktop assistant UI; Tk is bundled in the Windows executable.

The Win32 pet owns the reminder store and clock. Closing this window only hides it.
Tk events are pumped from the existing guarded application tick, on the same thread.
"""
from __future__ import annotations

from datetime import datetime
import time
import tkinter as tk
from tkinter import ttk

from .l10n import tr

INK, GREEN, PALE, MUTED = "#23312b", "#326451", "#f0f6f1", "#65756c"
NOTE = ("Reminders continue with this window closed. Keep Yukio running; missed reminders appear after wake or relaunch.",
        "关闭主窗口后仍会提醒。请保持 Yukio 运行；休眠或退出期间错过的提醒，会在唤醒或下次启动后补上。")


class AssistantWindow:
    def __init__(self, app):
        self.app, self.store = app, app.reminders
        self.root = tk.Tk()
        self.root.withdraw()
        icon = app._tray_icon_path()
        if icon:
            try:
                self.root.iconbitmap(default=icon)
            except tk.TclError:
                pass
        self.root.title(tr("Yukio · Personal assistant", "Yukio · 个人助手"))
        self.root.geometry("980x680+20+20")
        self.root.minsize(820, 580)
        self.root.configure(bg="white")
        self.root.protocol("WM_DELETE_WINDOW", self.root.withdraw)
        self.root.bind("<Control-w>", lambda _: self.root.withdraw())
        self.root.report_callback_exception = self._callback_error
        self.closed = False
        self.page = "home"
        self.completed = False
        self.editor = None
        self.delivery = None
        self._revision = -1
        self._error = None
        self._ring_signature = None
        self._pumping = False
        self.entries = {}
        self.nav_buttons = {}
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background="white")
        style.configure("TLabel", background="white", foreground=INK, font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 8))
        style.configure("Accent.TButton", background=GREEN, foreground="white")
        style.map("Accent.TButton", background=[("active", "#417b65"), ("disabled", "#c0ccc4")])
        style.configure("TCheckbutton", background="white", foreground=INK, padding=5)
        side = tk.Frame(self.root, bg=PALE, width=210, padx=20, pady=25)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        self.label(side, "Yukio", 25, bg=PALE)
        self.label(side, tr("A little company, a little help", "一点陪伴，一点帮助"), 9, MUTED, PALE)
        tk.Frame(side, bg=PALE, height=35).pack()
        for key, en, zh in [("home", "Home", "首页"), ("reminders", "Reminders", "提醒"),
                            ("personal", "Personalization", "个性化"), ("extensions", "Extensions", "扩展")]:
            button = ttk.Button(side, text=tr(en, zh), command=lambda k=key: self.navigate(k))
            button.pack(fill="x", pady=4)
            self.nav_buttons[key] = button
        ttk.Button(side, text=tr("Pet settings", "桌宠设置"), command=lambda: self.navigate("settings")).pack(side="bottom", fill="x", pady=12)
        self.label(side, tr("Start with one small thing.", "从一件小事开始。"), 10, MUTED, PALE).pack_configure(side="bottom")
        shell = ttk.Frame(self.root)
        shell.pack(side="left", expand=True, fill="both")
        self.canvas = tk.Canvas(shell, bg="white", highlightthickness=0)
        scroll = ttk.Scrollbar(shell, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.canvas.pack(fill="both", expand=True)
        self.body = ttk.Frame(self.canvas, padding=30)
        self.body_window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>", lambda _: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.body_window, width=e.width))
        self.canvas.bind_all("<MouseWheel>", self._wheel)
        self.refresh(force=True)

    def label(self, parent, text, size=11, color=INK, bg="white", wrap=620):
        widget = tk.Label(parent, text=text, font=("Segoe UI", size), fg=color, bg=bg,
                          anchor="w", justify="left", wraplength=wrap)
        widget.pack(anchor="w", fill="x", pady=(0, 10))
        return widget

    def button(self, parent, text, command, accent=False):
        button = ttk.Button(parent, text=text, command=command, style="Accent.TButton" if accent else "TButton")
        button.pack(side="left", padx=(0, 8), pady=4)
        return button

    def _wheel(self, event):
        if event.widget.winfo_toplevel() == self.root:
            self.canvas.yview_scroll(-int(event.delta / 120), "units")

    def _callback_error(self, exception, value, trace):
        import traceback
        traceback.print_exception(exception, value, trace)
        self.store.error = tr("Could not complete this action: %s", "操作未完成：%s") % value
        self.refresh(force=True)

    def present(self):
        self.refresh(force=True)
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def navigate(self, page):
        self.page = page
        self.refresh(force=True)
        self.canvas.yview_moveto(0)

    def refresh(self, force=False):
        changed = self._revision != self.store.revision or self._error != self.store.error
        if force or changed:
            self.root.title(tr("Yukio · Personal assistant", "Yukio · 个人助手"))
            for key, en, zh in [("home", "Home", "首页"), ("reminders", "Reminders", "提醒"), ("personal", "Personalization", "个性化"), ("extensions", "Extensions", "扩展")]:
                self.nav_buttons[key].configure(text=tr(en, zh))
            self._revision, self._error = self.store.revision, self.store.error
            if force or self.page in ("home", "reminders"):
                for child in self.body.winfo_children():
                    child.destroy()
                if self.store.error:
                    self.label(self.body, self.store.error, 10, "#a33535")
                getattr(self, "_" + self.page)()
        ringing = self.store.list("ringing")
        signature = (tuple((i["id"], i["title"], i["dueAt"]) for i in ringing), self.store.error)
        if signature != self._ring_signature:
            self._ring_signature = signature
            self._delivery(ringing)

    def pump(self):
        if self.closed or self._pumping:
            return
        self._pumping = True
        try:
            self.refresh()
            self.root.update()
        finally:
            self._pumping = False

    def destroy(self):
        if not self.closed:
            self.closed = True
            self.root.destroy()

    def _home(self):
        self.label(self.body, datetime.now().strftime("%Y-%m-%d · %A"), 10, MUTED)
        user = self.app.settings.get("assistantUserName", "").strip()
        name = self.app.settings.get("assistantName") or "Yukio"
        self.label(self.body, (user + tr(", take it easy today.", "，今天慢慢来。")) if user else tr("Take it easy today.", "今天，慢慢来。"), 25)
        self.label(self.body, tr("I'm %s. Let's start with the little things.", "我是%s。从记住你的小事开始。") % name, 12, MUTED)
        card = tk.Frame(self.body, bg=PALE, padx=22, pady=22)
        card.pack(fill="x", pady=16)
        self.label(card, tr("Something you'd like me to remember?", "有件事，想让我提醒你吗？"), 18, bg=PALE)
        self.label(card, tr("A glass of water, an appointment, or a short walk.", "喝杯水、出门赴约，或者起来走一走。"), 11, MUTED, PALE)
        row = tk.Frame(card, bg=PALE); row.pack(fill="x")
        self.new_button = self.button(row, tr("Create reminder", "创建提醒"), self.edit, True)
        if not self.store.available:
            self.new_button.state(["disabled"])
        self.label(self.body, tr("Scheduled: %d    Due: %d    Completed: %d", "待提醒：%d    待确认：%d    已完成：%d") % tuple(len(self.store.list(s)) for s in ("scheduled", "ringing", "completed")), 12)
        self.label(self.body, tr("Coming up", "接下来"), 16)
        self._rows((self.store.list("ringing") + self.store.list("scheduled"))[:3])
        self.label(self.body, tr(*NOTE), 10, MUTED)

    def _reminders(self):
        self.label(self.body, tr("Keep the little things here.", "把小事记在这里。"), 24)
        bar = ttk.Frame(self.body); bar.pack(fill="x", pady=12)
        self.new_button = self.button(bar, tr("New reminder", "新建提醒"), self.edit, True)
        if not self.store.available:
            self.new_button.state(["disabled"])
        self.button(bar, tr("Pending", "待提醒"), lambda: self._filter(False))
        self.button(bar, tr("Completed", "已完成"), lambda: self._filter(True))
        self._rows(self.store.list("completed") if self.completed else self.store.list("ringing") + self.store.list("scheduled"))
        self.label(self.body, tr(*NOTE), 10, MUTED)

    def _filter(self, completed):
        self.completed = completed
        self.refresh(force=True)

    def _rows(self, items, parent=None):
        parent = parent or self.body
        if not items:
            self.label(parent, tr("Nothing here yet. Add a reminder when you need one.", "还没有安排。等有件事想记住时，再来这里。"), 12, MUTED)
        for item in items:
            frame = tk.Frame(parent, bg="white", highlightbackground="#dce5de", highlightthickness=1, padx=16, pady=12)
            frame.pack(fill="x", pady=(0, 12))
            self.label(frame, item["title"], 13)
            stamp = datetime.fromtimestamp(self.store.due_at(item)).strftime("%Y-%m-%d %H:%M")
            self.label(frame, stamp + (tr(" · It's time", " · 到时间了") if item["status"] == "ringing" else ""), 10, MUTED)
            actions = ttk.Frame(frame); actions.pack(fill="x")
            rid = item["id"]
            if item["status"] == "ringing":
                self.button(actions, tr("Snooze 5 minutes", "稍后 5 分钟"), lambda i=rid: self.act("snooze", i))
                self.button(actions, tr("Got it", "知道了"), lambda i=rid: self.act("complete", i), True)
            elif item["status"] == "scheduled":
                self.button(actions, tr("Edit", "编辑"), lambda i=item: self.edit(i))
            self.button(actions, tr("Delete", "删除"), lambda i=rid: self.act("remove", i))

    def act(self, action, reminder_id):
        getattr(self.store, action)(reminder_id)
        self.refresh(force=True)

    def _personal(self):
        self.label(self.body, tr("Make this space yours.", "让这里，更像你的。"), 24)
        self.label(self.body, tr("Names and reminder preferences save automatically on this PC.", "名字和提醒习惯会自动保存在这台电脑上。"), 11, MUTED)
        for key, en, zh in [("assistantName", "Assistant name", "助手的名字"), ("assistantUserName", "Your name (optional)", "怎么称呼你（可选）")]:
            self.label(self.body, tr(en, zh), 11)
            value = tk.StringVar(value=self.app.settings.get(key, ""))
            entry = ttk.Entry(self.body, textvariable=value, width=36)
            entry.pack(anchor="w", pady=(0, 20))
            value.trace_add("write", lambda *_, k=key, v=value: self.app.settings.set(k, v.get()))
            self.entries[key] = value
        self._check(self.body, "assistantReminderSound", tr("Play a reminder sound", "提醒时播放提示音"))
        self.label(self.body, tr("Speaking style, memory and new appearances are planned.", "说话风格、偏好记忆和更多角色外观仍在规划中。"), 11, MUTED)

    def _extensions(self):
        self.label(self.body, tr("Room for new abilities.", "慢慢长出新本领。"), 24)
        for en, zh, detail in [
            ("AI conversation", "AI 对话", tr("Connect a model and draft reminders from a sentence.", "连接模型，用一句话创建提醒草稿。")),
            ("Desktop widgets", "桌面小组件", tr("See the next reminder at a glance.", "一眼看到下一条提醒和今天的安排。")),
            ("Calendar connections", "日历与更多连接", tr("Bring your existing schedule into one place.", "把已有的日程带进来。")),
            ("Context and preferences", "情境感知与个性化", tr("Editable schedules, activity records and preferences; screen observation and briefings are not implemented.", "可修改的行程、活动记录和偏好；屏幕观察与新闻简报尚未实现。"))]:
            self.label(self.body, tr(en, zh) + tr(" · Planned", " · 规划中"), 15)
            self.label(self.body, detail, 11, MUTED)
        self.label(self.body, tr("No model calls or screen monitoring are enabled in this version.", "本版没有调用模型，也没有启用屏幕监测。"), 11, MUTED)

    def _check(self, parent, key, label, action=None):
        value = tk.BooleanVar(value=self.app.settings.get(key, True))
        ttk.Checkbutton(parent, text=label, variable=value,
                        command=lambda: (action(value.get()) if action else self.app.settings.set(key, value.get()))).pack(anchor="w", pady=6)
        # Keep Tcl variables alive for the lifetime of the controls.
        self.entries[key] = value

    def _settings(self):
        self.label(self.body, tr("Pet settings", "桌宠设置"), 24)
        self._check(self.body, "petVisible", tr("Show Yukio", "显示雪绪"), lambda v: self.app.set_hidden(not v))
        for key, en, zh in [("follow", "Follow AI activity", "跟随 AI 活动"), ("showBubble", "Show task bubble", "头顶显示任务"),
                            ("showCards", "Show other chats", "头顶显示别的聊天"), ("showQuestionCard", "Answer here", "在这儿回答问题")]:
            self._check(self.body, key, tr(en, zh))
        self.label(self.body, tr("Size (50–200%)", "大小（50–200%）"), 11)
        slider = ttk.Scale(self.body, from_=0.5, to=2, value=self.app.settings.get("scale"),
                           command=lambda v: self.app._set_scale(float(v)))
        slider.pack(fill="x", pady=(0, 20))
        self.label(self.body, tr("Follow assistant", "跟随的助手"), 11)
        source = ttk.Combobox(self.body, values=("auto", "claude", "deepcode", "gpt"), state="readonly")
        source.set(self.app.settings.get("source")); source.pack(anchor="w", pady=(0, 20))
        source.bind("<<ComboboxSelected>>", lambda _: self.app._set_source(source.get()))
        self.label(self.body, "Language / 语言", 11)
        lang = ttk.Combobox(self.body, values=("English", "中文"), state="readonly")
        lang.set("中文" if self.app.settings.get("language") == "zh" else "English")
        lang.pack(anchor="w", pady=(0, 20))
        def language_changed(_):
            self.app._set_language("zh" if lang.get() == "中文" else "en")
            self.refresh(force=True)
        lang.bind("<<ComboboxSelected>>", language_changed)
        bar = ttk.Frame(self.body); bar.pack(fill="x")
        self.button(bar, tr("Play demo", "播放模拟演示"), self.app.start_demo)
        self.button(bar, tr("Reset position", "回到右下角"), self.app._reset_position)
        self.button(bar, tr("More pet controls", "更多桌宠操作"), self.app.show_menu)

    def edit(self, item=None):
        if self.editor is not None and self.editor.winfo_exists():
            self.editor.lift(); return
        self.editor = tk.Toplevel(self.root)
        self.editor.title(tr("Edit reminder", "编辑提醒") if item else tr("New reminder", "新建提醒"))
        self.editor.transient(self.root)
        self.editor.configure(bg="white")
        box = ttk.Frame(self.editor, padding=25); box.pack(fill="both", expand=True)
        self.label(box, tr("What should I remind you about?", "提醒你做什么？"), 17, wrap=460)
        self.edit_title = tk.StringVar(value=item["title"] if item else "")
        title = ttk.Entry(box, textvariable=self.edit_title, width=48); title.pack(fill="x", pady=12)
        due = self.store.due_at(item) if item else time.time() + 25 * 60
        self.edit_due = tk.StringVar(value=datetime.fromtimestamp(due).strftime("%Y-%m-%d %H:%M"))
        self.label(box, tr("Local date and time (YYYY-MM-DD HH:MM)", "本地日期和时间（YYYY-MM-DD HH:MM）"), 10)
        ttk.Entry(box, textvariable=self.edit_due).pack(fill="x", pady=(0, 15))
        shortcuts = ttk.Frame(box); shortcuts.pack(fill="x")
        for minutes in (1, 5, 25, 60):
            self.button(shortcuts, tr("%d min", "%d 分钟后") % minutes,
                        lambda m=minutes: self.edit_due.set(datetime.fromtimestamp(time.time()+m*60).strftime("%Y-%m-%d %H:%M")))
        self.edit_error = self.label(box, "", 10, "#a33535", wrap=460)
        self._edit_id = item["id"] if item else None
        actions = ttk.Frame(box); actions.pack(fill="x", pady=15)
        self.button(actions, tr("Cancel", "取消"), self.editor.destroy)
        self.save_button = self.button(actions, tr("Save reminder", "保存提醒"), self.save_editor, True)
        if not self.store.available:
            self.save_button.state(["disabled"])
        self.editor.bind("<Return>", lambda _: self.save_editor())
        self.editor.bind("<Escape>", lambda _: self.editor.destroy())
        title.focus_set()

    def save_editor(self):
        try:
            due = datetime.strptime(self.edit_due.get().strip(), "%Y-%m-%d %H:%M").timestamp()
        except (ValueError, OverflowError, OSError):
            self.edit_error.configure(text=tr("Enter a valid local date and time: YYYY-MM-DD HH:MM", "请输入有效的本地日期和时间：YYYY-MM-DD HH:MM"))
            return False
        if not self.store.save(self.edit_title.get(), due, self._edit_id):
            self.edit_error.configure(text=self.store.error)
            return False
        self.editor.destroy()
        self.refresh(force=True)
        return True

    def _delivery(self, items):
        if not items:
            if self.delivery is not None:
                self.delivery.destroy(); self.delivery = None
            return
        if self.delivery is None:
            self.delivery = tk.Toplevel(self.root)
            self.delivery.title(tr("Yukio · It's time", "Yukio · 到时间了"))
            self.delivery.attributes("-topmost", True)
            self.delivery.protocol("WM_DELETE_WINDOW", self.present)
            self.delivery.geometry("460x420+%d+40" % max(0, self.root.winfo_screenwidth()-485))
            self.delivery.configure(bg="white")
            self.delivery_canvas = tk.Canvas(self.delivery, bg="white", highlightthickness=0)
            scroll = ttk.Scrollbar(self.delivery, command=self.delivery_canvas.yview)
            self.delivery_canvas.configure(yscrollcommand=scroll.set)
            scroll.pack(side="right", fill="y"); self.delivery_canvas.pack(fill="both", expand=True)
            self.delivery_body = ttk.Frame(self.delivery_canvas, padding=18)
            window = self.delivery_canvas.create_window((0, 0), window=self.delivery_body, anchor="nw")
            self.delivery_body.bind("<Configure>", lambda _: self.delivery_canvas.configure(scrollregion=self.delivery_canvas.bbox("all")))
            self.delivery_canvas.bind("<Configure>", lambda e: self.delivery_canvas.itemconfigure(window, width=e.width))
        for child in self.delivery_body.winfo_children():
            child.destroy()
        self.label(self.delivery_body, tr("%s has a reminder for you", "%s来提醒你") % (self.app.settings.get("assistantName") or "Yukio"), 15, wrap=400)
        self._rows(items, self.delivery_body)
        if self.store.error:
            self.label(self.delivery_body, self.store.error, 10, "#a33535", wrap=400)
        self.delivery.deiconify()
