"""Compact topmost settings, shared by right-click, the assistant and tray."""
import tkinter as tk
from tkinter import ttk, messagebox
from .l10n import tr
from .outside_click import OutsideClickDismissal


class PetSettingsWindow:
    def __init__(self, assistant):
        self.assistant, self.app = assistant, assistant.app
        self.window = tk.Toplevel(assistant.root)
        self.window.withdraw()
        self.window.geometry('420x746')
        self.window.minsize(420, 746)
        self.window.attributes('-topmost', True)
        self.window.protocol('WM_DELETE_WINDOW', self.window.withdraw)
        self.body = ttk.Frame(self.window, padding=18)
        self.body.pack(fill='both', expand=True)
        self.values = {}
        self.outside_click = OutsideClickDismissal(self.window)

    def present(self):
        self.refresh()
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()
        self.window.update_idletasks()
        w, h = self.window.winfo_width(), self.window.winfo_height()
        left, top, right, bottom = self.app.win32.work_area()
        x = max(left, min(self.app.pet.x-w-12, right-w))
        y = max(top, min(self.app.pet.y, bottom-h))
        self.window.geometry(f'+{x}+{y}')

    def refresh(self):
        self.window.title(tr('Yukio · Pet settings', 'Yukio · 桌宠设置'))
        for child in self.body.winfo_children(): child.destroy()
        head = ttk.Frame(self.body); head.pack(fill='x', pady=(0,12))
        ttk.Label(head, text='Yukio', font=('Segoe UI', 19)).pack(side='left')
        self.lower_sign_button = lower_sign_button(self.body, self.app._drop_sign)
        for key, en, zh, action in [
            ('petVisible','Show Yukio','显示雪绪',lambda v:self.app.set_hidden(not v)),
            ('follow','Follow AI activity','跟随 AI 活动',lambda v:self.app.settings.set('follow',v)),
            ('showBubble','Show task bubble','头顶显示任务',lambda v:self.app.settings.set('showBubble',v)),
            ('showCards','Show other chats','显示别的聊天',lambda v:self.app.settings.set('showCards',v)),
            ('showQuestionCard','Answer here','在这儿回答问题',lambda v:self.app.settings.set('showQuestionCard',v))]:
            value=tk.BooleanVar(value=not self.app.pet_hidden if key=='petVisible' else self.app.settings.get(key,True))
            self.values[key]=value
            ttk.Checkbutton(self.body,text=tr(en,zh),variable=value,command=lambda v=value,a=action:a(v.get())).pack(anchor='w',pady=3)
        ttk.Label(self.body,text=tr('Size (50–200%)','大小（50–200%）')).pack(anchor='w',pady=(10,0))
        ttk.Scale(self.body,from_=0.5,to=2,value=self.app.scale,command=lambda v:self.app._set_scale(float(v))).pack(fill='x')
        row=ttk.Frame(self.body);row.pack(fill='x',pady=8)
        source=ttk.Combobox(row,values=('auto','claude','deepcode','gpt'),state='readonly',width=12)
        source.set(self.app.settings.get('source'));source.pack(side='left')
        source.bind('<<ComboboxSelected>>',lambda _:self.app._set_source(source.get()))
        lang=ttk.Combobox(row,values=('English','中文'),state='readonly',width=12)
        lang.set('中文' if self.app.settings.get('language')=='zh' else 'English');lang.pack(side='right')
        def language(_):
            self.app._set_language('zh' if lang.get()=='中文' else 'en')
            self.refresh()
        lang.bind('<<ComboboxSelected>>',language)
        ttk.Separator(self.body).pack(fill='x',pady=8)
        self.startup_value=tk.BooleanVar(value=self.app.launch_at_login.status in ('enabled','requires_approval'))
        self.startup_button=ttk.Checkbutton(self.body,text=tr('Launch at login','登录时自动启动'),variable=self.startup_value,command=self.toggle_startup)
        self.startup_button.pack(anchor='w')
        status=self.app.launch_at_login.status
        labels={'enabled':tr('Enabled for this Windows user.','已为当前 Windows 用户开启。'),
                'disabled':tr('Off. Yukio does not enable this automatically.','已关闭，不会自动替你开启。'),
                'requires_approval':tr('Check permission in Windows Startup Apps.','请在 Windows 启动应用中确认允许。'),
                'different_location':tr('Registered at another path. Enable to use this copy.','启动项指向其他位置，开启可改为当前程序。'),
                'unavailable':tr('Cannot read the Windows startup setting.','无法读取 Windows 启动设置。')}
        ttk.Label(self.body,text=labels[status],wraplength=370).pack(anchor='w',pady=5)
        ttk.Button(self.body,text=tr('Windows Startup Apps…','Windows 启动应用…'),command=self.app.launch_at_login.open_settings).pack(anchor='w')
        ttk.Separator(self.body).pack(fill='x',pady=8)
        self.update_value=tk.BooleanVar(value=self.app.settings.get('automaticUpdates',True))
        ttk.Checkbutton(self.body,text=tr('Automatically check for updates','自动检查新版本'),variable=self.update_value,
                        command=lambda:self.app.settings.set('automaticUpdates',self.update_value.get())).pack(anchor='w')
        from . import __version__
        ttk.Button(self.body,text=tr('Check for updates…','检查更新…')+'  ('+__version__+')',
                   command=lambda:self.app.updater.check()).pack(anchor='w')
        bar=ttk.Frame(self.body);bar.pack(fill='x',side='bottom',pady=(10,0))
        ttk.Button(bar,text=tr('Reset position','复位位置'),command=self.app._reset_position).pack(side='left')
        ttk.Button(bar,text=tr('Play demo','播放演示'),command=self.app.start_demo).pack(side='left',padx=6)
        ttk.Button(bar,text=tr('Done','完成'),command=self.window.withdraw).pack(side='right')

    def toggle_startup(self):
        try:
            self.app.launch_at_login.set_enabled(self.startup_value.get())
        except (OSError, ImportError, ValueError) as error:
            messagebox.showerror(tr('Could not update startup','未能更改启动设置'),str(error),parent=self.window)
        self.refresh()


def lower_sign_button(parent, command):
    # Draw the same card/down-arrow icon at an ample size on every Windows font.
    icon = tk.PhotoImage(master=parent, width=48, height=48)
    for x, y, width, height in [(7, 4, 27, 3), (7, 4, 3, 29), (31, 4, 3, 17),
                                (7, 30, 14, 3), (29, 23, 3, 19)]:
        icon.put('#ffffff', to=(x, y, x+width, y+height))
    for i in range(10):
        icon.put('#ffffff', to=(20+i, 32+i, 23+i, 35+i))
        icon.put('#ffffff', to=(38-i, 32+i, 41-i, 35+i))
    button = tk.Button(parent, text=tr('Lower sign', '取消举牌'), image=icon,
                       compound='left', font=('Segoe UI', 18, 'bold'),
                       background='#2e6e8a', foreground='white',
                       activebackground='#245970', activeforeground='white',
                       relief='flat', cursor='hand2', padx=16, pady=8, command=command)
    button.icon = icon
    button.pack(fill='x', pady=(0, 12))
    return button
