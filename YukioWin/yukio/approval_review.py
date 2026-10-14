"""Scrollable complete request; no Enter binding and no preselected grant."""
import tkinter as tk
from tkinter import ttk
from .l10n import tr

def present(root, question, send):
    window = tk.Toplevel(root)
    window.title(question.header or tr('Approval request', '申请确认'))
    window.geometry('600x420'); window.minsize(420, 300)
    window.attributes('-topmost', True)
    ttk.Label(window, text=tr('Review the complete request. This choice applies once.', '请查看完整申请。你的选择只针对这一次申请。'), padding=12).pack(fill='x')
    body = ttk.Frame(window); body.pack(fill='both', expand=True, padx=12)
    text = tk.Text(body, wrap='word', height=12)
    scrollbar = ttk.Scrollbar(body, orient='vertical', command=text.yview)
    text.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side='right', fill='y'); text.pack(fill='both', expand=True)
    text.insert('1.0', question.text); text.configure(state='disabled')
    buttons = ttk.Frame(window, padding=12); buttons.pack(fill='x')
    def choose(label):
        window.destroy(); send(label)
    ttk.Button(buttons, text=tr('Later', '稍后处理'), command=window.destroy).pack(side='left')
    for option in question.options:
        ttk.Button(buttons, text=option.label, command=lambda label=option.label: choose(label)).pack(side='right', padx=4)
    window.bind('<Escape>', lambda _: window.destroy())
    return window
