#!/usr/bin/env python3
"""给冒烟测试造一份 Deep Code 会话：一条用户请求 + 一次正在进行的 edit 调用。

雪绪读到它应该显示“纸上书写”，气泡写“编辑 login.py”。时间戳按当前时刻生成，
所以每次跑都是“刚刚发生的事”，不会被当成过期会话。

    python scripts/seed_smoke_session.py [目标 projects 目录]

默认写到 ~/.deepcode/projects/ci-smoke（Windows 上是 %USERPROFILE%\\.deepcode\\...）。
只写自己造的这个 ci-smoke 目录，不碰别的会话。
"""

import datetime as dt
import json
import os
import sys

SESSION = "11111111-2222-4333-8444-555555555555"


def stamp(seconds_ago: float) -> str:
    try:
        now = dt.datetime.now(dt.timezone.utc)
    except AttributeError:  # 很老的 Python
        now = dt.datetime.utcnow()
    when = now - dt.timedelta(seconds=seconds_ago)
    return when.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (when.microsecond // 1000)


def message(id, role, seconds_ago, **kw):
    out = {"id": id, "sessionId": SESSION, "role": role, "content": "", "contentParams": None,
           "messageParams": None, "compacted": False, "visible": True,
           "createTime": stamp(seconds_ago), "updateTime": stamp(seconds_ago)}
    out.update(kw)
    return out


def write(projects_dir: str) -> str:
    project = os.path.join(projects_dir, "ci-smoke")
    os.makedirs(project, exist_ok=True)

    index = {"entries": [{"id": SESSION, "summary": "冒烟测试：改一改登录页",
                          "assistantReply": None, "assistantThinking": None, "toolCalls": None,
                          "status": "processing", "failReason": None, "usage": None,
                          "activeTokens": 0, "createTime": stamp(40), "updateTime": stamp(2),
                          "processes": None, "planMode": False}],
             "originalPath": os.path.join("C:\\", "ci", "proj")}
    with open(os.path.join(project, "sessions-index.json"), "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=2)

    tool_call = {"id": "c1", "type": "function",
                 "function": {"name": "edit",
                              "arguments": json.dumps({"file_path": "C:/ci/proj/login.py",
                                                       "snippet_id": "s1",
                                                       "old_string": "a", "new_string": "b"})}}
    lines = [
        message("m1", "user", 20, content="改一改登录页的表单校验",
                meta={"userPrompt": {"text": "改一改登录页的表单校验"}}),
        message("m2", "assistant", 3, content="",
                messageParams={"tool_calls": [tool_call]}, visible=False,
                meta={"asThinking": True}),
    ]
    path = os.path.join(project, SESSION + ".jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
    return project


def main() -> int:
    if len(sys.argv) > 1:
        projects = sys.argv[1]
    else:
        base = os.environ.get("DEEPCODE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".deepcode")
        projects = os.path.join(base, "projects")
    print(write(projects))
    return 0


if __name__ == "__main__":
    sys.exit(main())
