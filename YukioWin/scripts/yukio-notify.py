#!/usr/bin/env python3
"""Deep Code 的 notify 脚本：每轮任务结束时告诉雪绪一声。

平时不需要它——雪绪默认直接读 ~/.deepcode/projects 下的会话记录，工具级别的动作都看得到，
notify 一轮只响一次。装它的理由只有一个：Deep Code 换了会话记录的格式、雪绪读不懂了，
这条通道仍然能让她在任务结束时递交报告 / 出错时沮丧。

装法：把这个文件放到 ~/.deepcode/ 下，然后在 ~/.deepcode/settings.json 里加一行

    "notify": "C:\\\\Users\\\\你\\\\.deepcode\\\\yukio-notify.py"

Windows 上如果 .py 没关联到 python.exe，就填同目录的 yukio-notify.bat。

Deep Code 通过环境变量传进来：STATUS（completed / failed）、TITLE、DURATION、BODY、FAIL_REASON。
这个脚本不读 BODY，也不把任何对话内容写进收件箱，只写状态和标题。
"""

import json
import os
import sys
import time


def app_data_dir():
    override = os.environ.get("YUKIO_HOME")
    if override:
        return override
    if os.name == "nt":
        return os.path.join(os.environ.get("LOCALAPPDATA") or
                            os.path.join(os.path.expanduser("~"), "AppData", "Local"), "Yukio")
    return os.path.join(os.path.expanduser("~"), ".yukio")


def find_session():
    """找出当前项目最近在跑的那个会话，好让这些事件和会话记录里的对上号。"""
    base = os.environ.get("DEEPCODE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".deepcode")
    projects = os.path.join(base, "projects")
    cwd = os.path.abspath(os.getcwd())
    best = (None, None, -1.0)   # (会话 ID, 标题, 更新时间)
    try:
        names = os.listdir(projects)
    except OSError:
        return (None, None)
    for name in names:
        index = os.path.join(projects, name, "sessions-index.json")
        try:
            with open(index, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            mtime = os.path.getmtime(index)
        except (OSError, ValueError):
            continue
        original = data.get("originalPath")
        # 优先认路径对得上的项目；对不上就看谁最近写过。
        weight = mtime + (1e9 if isinstance(original, str) and
                          os.path.normcase(os.path.abspath(original)) == os.path.normcase(cwd) else 0)
        for entry in data.get("entries") or []:
            if not isinstance(entry, dict) or not entry.get("id"):
                continue
            if weight > best[2]:
                best = (entry.get("id"), entry.get("summary"), weight)
            break   # entries 已按更新时间排序，取第一条
    return (best[0], best[1])


def main():
    status = (os.environ.get("STATUS") or "completed").strip()
    title = (os.environ.get("TITLE") or "").strip()
    session, summary = find_session()
    session = session or "deepcode-notify"
    title = title or summary or ""

    events = []
    if title:
        events.append({"kind": "session_title", "session": session, "detail": title[:80]})
    if status == "failed":
        events.append({"kind": "task_failed", "session": session,
                       "detail": (os.environ.get("FAIL_REASON") or "")[:60]})
    else:
        events.append({"kind": "final_answer", "session": session})
        events.append({"kind": "task_end", "session": session})

    path = os.path.join(app_data_dir(), "inbox.jsonl")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            for event in events:
                event.setdefault("ts", time.time() * 1000.0)
                fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError:
        pass   # 通知失败绝不能影响 Deep Code
    return 0


if __name__ == "__main__":
    sys.exit(main())
