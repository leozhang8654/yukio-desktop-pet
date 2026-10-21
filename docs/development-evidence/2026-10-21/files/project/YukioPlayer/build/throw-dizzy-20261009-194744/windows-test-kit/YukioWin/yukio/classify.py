"""工具 → 雪绪活动，以及气泡里那句简短说明。

规则有限且可测试：内置工具按名称映射；shell 按命令首词和少量子命令判断；
MCP 工具按名称关键字判断。无法确定时一律回默认电脑桌，不猜测为测试。

同时认识两套工具名：
  * Deep Code（DeepSeek 终端版）：read / write / edit / bash / WebSearch / ReadImage /
    UnderstandImage / UpdatePlan / AskUserQuestion / skill；
  * Claude Code：Read / Write / Edit / Bash / Grep / Glob / WebFetch / TodoWrite / Task… 。
两边的 mcp__<服务>__<工具> 命名一致。
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from .events import PetQuestion, PetState
from .l10n import tr

#: classify() 返回 CONTINUE_PREVIOUS 表示“延续该会话上一个工具的活动”（轮询后台命令等）。
CONTINUE_PREVIOUS = "continue_previous"

IMAGE_EXTENSIONS = {
    "png", "jpg", "jpeg", "gif", "webp", "bmp", "tif", "tiff", "heic", "heif", "svg", "ico",
}


def _base_name(path: str) -> str:
    """取路径最后一段。Windows 与 POSIX 分隔符都认。"""
    return path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1] or path


def _ext(path: str) -> str:
    name = _base_name(path)
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def _text(input: Dict[str, Any], key: str) -> Optional[str]:
    v = input.get(key)
    if not isinstance(v, str):
        return None
    t = v.strip()
    return t or None


def _name(input: Dict[str, Any], key: str) -> Optional[str]:
    v = input.get(key)
    if not isinstance(v, str) or not v:
        return None
    return _base_name(v)


def _host(url: str) -> str:
    try:
        h = urlparse(url if "//" in url else "//" + url).hostname
    except ValueError:
        h = None
    if not h:
        return url
    return h[4:] if h.startswith("www.") else h


# MARK: 分类

_READ_TOOLS = {"glob", "grep", "ls", "notebookread", "listdir", "list_dir", "search", "codebase_search"}
_WRITE_TOOLS = {"write", "edit", "multiedit", "notebookedit", "str_replace_editor", "apply_patch"}
_WEB_TOOLS = {"webfetch", "websearch", "web_search", "web_fetch", "fetch"}
_IMAGE_TOOLS = {"readimage", "understandimage", "view_image", "read_image"}
_SHELL_TOOLS = {"bash", "powershell", "shell", "run_command", "terminal"}
_CONTINUE_TOOLS = {"bashoutput", "killshell", "killbash", "taskoutput", "taskstop", "readbashoutput"}
#: 问话类工具：各家写法不同，都是「停下来等你拿主意」。
_ASK_TOOLS = {"askuserquestion", "ask_user_question", "ask_user",
              "request_user_input", "request_user_input_async"}
_PLAN_TOOLS = {
    "todowrite", "taskcreate", "taskupdate", "tasklist", "taskget",
    "updateplan", "enterplanmode", "exitplanmode", "toolsearch", "exit_plan_mode",
}


def classify(tool: str, input: Optional[Dict[str, Any]] = None):
    """返回 PetState，或 CONTINUE_PREVIOUS。"""
    input = input or {}
    key = tool.lower()

    if key == "read":
        path = input.get("file_path") or input.get("path") or ""
        path = path if isinstance(path, str) else ""
        return PetState.view_image if _ext(path) in IMAGE_EXTENSIONS else PetState.read_file
    if key in _IMAGE_TOOLS:
        return PetState.view_image
    if key in _READ_TOOLS:
        return PetState.read_file
    if key in _WRITE_TOOLS:
        return PetState.write_file
    if key in _WEB_TOOLS:
        return PetState.read_web
    if key in _SHELL_TOOLS:
        command = input.get("command")
        return classify_shell(command if isinstance(command, str) else "")
    if key in _CONTINUE_TOOLS:
        return CONTINUE_PREVIOUS
    if key in _PLAN_TOOLS:
        return PetState.thinking
    if key in _ASK_TOOLS:
        # 等待用户回答：不是在工作。
        return PetState.question_for_user
    if tool.startswith("mcp__"):
        return classify_mcp(tool, input)
    return PetState.default_work


def question(tool: str, input: Optional[Dict[str, Any]] = None) -> Optional[PetQuestion]:
    """这次调用是不是在问你话；是就把问题抄下来（举牌时显示在她身边）。

    只认问话类工具：别的工具参数里叫 question 的字段与这件事无关。
    """
    if tool.lower() not in _ASK_TOOLS:
        return None
    return PetQuestion.parse(input or {})


def classify_mcp(tool: str, input: Dict[str, Any]) -> PetState:
    name = tool.lower()
    action = input.get("action")
    action = action.lower() if isinstance(action, str) else None
    if ("screenshot" in name or "view_image" in name or "read_image" in name
            or action in ("screenshot", "zoom")):
        return PetState.view_image
    web_hints = ["browser", "chrome", "navigate", "webfetch", "web_fetch", "fetch_url", "get_page", "read_page"]
    if any(h in name for h in web_hints):
        return PetState.read_web
    return PetState.default_work


# MARK: shell

#: 组合命令取最强类别：验证 > 写入 > 网页 > 其他 > 读取。
NEUTRAL, READ, OTHER, WEB, WRITE, VERIFY = range(6)

NEUTRAL_COMMANDS = {
    "cd", "pushd", "popd", "export", "set", "unset", "source", ".", "echo", "printf", "true", "false",
    "sleep", "clear", "wait", "trap", "exit", "pwd", "date", "whoami",
}
READ_COMMANDS = {
    "cat", "head", "tail", "less", "more", "nl", "wc", "rg", "grep", "egrep", "fgrep", "ag", "ls", "find",
    "fd", "tree", "stat", "file", "du", "df", "which", "type", "jq", "yq", "diff", "cmp", "strings", "xxd",
    "hexdump", "od", "shasum", "md5", "sha256sum", "md5sum", "realpath", "readlink", "basename", "dirname",
    "awk", "sort", "uniq", "cut", "column", "mdls", "plutil", "sips", "otool", "lsof", "ps", "pgrep",
    # Windows（cmd / PowerShell 里常见的只读命令）
    "dir", "findstr", "where", "get-content", "get-childitem", "select-string", "gci", "ls.exe",
}
WRITE_COMMANDS = {
    "tee", "touch", "mkdir", "cp", "mv", "rm", "rmdir", "ln", "chmod", "chown", "install", "patch",
    "unzip", "rsync", "apply_patch", "ditto", "trash",
    # Windows
    "copy", "xcopy", "robocopy", "del", "erase", "move", "ren", "rename", "md", "rd",
    "new-item", "set-content", "remove-item", "copy-item", "move-item",
}
WEB_COMMANDS = {"curl", "wget", "http", "https", "xh", "lynx", "w3m", "invoke-webrequest", "iwr"}
VERIFY_COMMANDS = {
    "pytest", "jest", "vitest", "mocha", "ava", "tox", "nox", "rspec", "phpunit", "ctest", "bats",
    "shellcheck", "eslint", "mypy", "pyright", "flake8", "pylint", "swiftlint", "golangci-lint", "playwright",
}
WRAPPERS = {"sudo", "time", "env", "command", "exec", "nohup", "xargs", "caffeinate", "winpty"}
TEST_WORDS = {"test", "tests", "spec", "verify", "check", "lint", "typecheck"}


def _mentions_test_word(s: str) -> bool:
    word = ""
    for ch in s.lower():
        if ch.isalpha():
            word += ch
        else:
            if word in TEST_WORDS:
                return True
            word = ""
    return word in TEST_WORDS


def classify_shell(command: str) -> PetState:
    segments, writes_via_redirect = tokenize(command)
    kinds = [kind_of(words) for words in segments]
    if writes_via_redirect:
        kinds.append(WRITE)
    strongest = max(kinds) if kinds else NEUTRAL
    if strongest == VERIFY:
        return PetState.verify
    if strongest == WRITE:
        return PetState.write_file
    if strongest == WEB:
        return PetState.read_web
    if strongest == READ:
        return PetState.read_file
    return PetState.default_work


def _strip_prefix(raw_words: List[str]) -> List[str]:
    """去掉前置环境变量与包装命令（sudo、time、timeout 30 …）。"""
    words = list(raw_words)
    while words:
        w = words[0]
        if "=" in w and not w.startswith("-") and (w[0].isalpha() or w[0] == "_"):
            words.pop(0)
        elif w in WRAPPERS:
            words.pop(0)
        elif w in ("timeout", "gtimeout"):
            words.pop(0)
            if words:
                head = words[0].rstrip("smhd")
                try:
                    float(head)
                except ValueError:
                    pass
                else:
                    words.pop(0)
        else:
            break
    return words


def kind_of(raw_words: List[str]) -> int:
    words = _strip_prefix(raw_words)
    if not words:
        return NEUTRAL
    first = words[0]
    cmd = _base_name(first).lower()
    if cmd.endswith(".exe"):
        cmd = cmd[:-4]
    args = words[1:]
    sub = next((a for a in args if not a.startswith("-")), "")

    if cmd in NEUTRAL_COMMANDS:
        return NEUTRAL
    if cmd in VERIFY_COMMANDS:
        return VERIFY
    if cmd in WEB_COMMANDS:
        return WEB

    if cmd in ("bash", "sh", "zsh"):
        for i, a in enumerate(args):
            if a in ("-c", "-lc") and i + 1 < len(args):
                inner = classify_shell(args[i + 1])
                return {PetState.verify: VERIFY, PetState.write_file: WRITE,
                        PetState.read_web: WEB, PetState.read_file: READ}.get(inner, OTHER)
        script = next((a for a in args if not a.startswith("-")), None)
        if script is not None:
            return VERIFY if _mentions_test_word(_base_name(script)) else OTHER
        return OTHER
    if cmd in ("python", "python3", "py", "node", "ruby", "deno", "bun", "php"):
        if "-m" in args:
            i = args.index("-m")
            if i + 1 < len(args):
                return VERIFY if args[i + 1] in ("pytest", "unittest", "mypy", "pyflakes", "ruff") else OTHER
        if "--test" in args or (cmd == "deno" and sub == "test") or (cmd == "bun" and sub == "test"):
            return VERIFY
        if args[:1] in (["-c"], ["-e"]):
            return OTHER
        script = next((a for a in args if not a.startswith("-")), None)
        if script is not None:
            return VERIFY if _mentions_test_word(_base_name(script)) else OTHER
        return OTHER
    if cmd in ("npm", "pnpm", "yarn"):
        if sub in ("test", "t"):
            return VERIFY
        if sub == "run" or cmd == "yarn":
            if sub == "run":
                rest = args[args.index("run") + 1:] if "run" in args else []
                script = rest[0] if rest else ""
            else:
                script = sub
            return VERIFY if _mentions_test_word(script) else OTHER
        return OTHER
    if cmd in ("npx", "bunx"):
        if sub in VERIFY_COMMANDS or (sub == "tsc" and "--noEmit" in args):
            return VERIFY
        if sub == "prettier" and "--check" in args:
            return VERIFY
        return OTHER
    if cmd == "tsc":
        return VERIFY if "--noEmit" in args else OTHER
    if cmd == "ruff":
        return VERIFY if sub == "check" else OTHER
    if cmd in ("make", "just", "gmake"):
        return VERIFY if _mentions_test_word(sub) else OTHER
    if cmd == "swift":
        return VERIFY if sub == "test" else OTHER
    if cmd == "xcodebuild":
        return VERIFY if ("test" in args or "test-without-building" in args) else OTHER
    if cmd == "cargo":
        return VERIFY if sub in ("test", "check", "clippy", "nextest") else OTHER
    if cmd == "go":
        return VERIFY if sub in ("test", "vet") else OTHER
    if cmd in ("dotnet", "mvn", "gradle", "gradlew", "./gradlew"):
        return VERIFY if sub in ("test", "verify", "check") else OTHER
    if cmd == "git":
        read_subs = {"status", "log", "show", "diff", "blame", "branch", "ls-files",
                     "rev-parse", "grep", "remote", "describe", "shortlog", "reflog"}
        write_subs = {"add", "commit", "checkout", "switch", "restore", "stash", "merge",
                      "rebase", "reset", "apply", "mv", "rm", "cherry-pick", "pull", "revert", "tag"}
        if sub in read_subs:
            return READ
        if sub in write_subs:
            return WRITE
        return OTHER
    if cmd == "sed":
        return WRITE if any(a == "-i" or a.startswith("-i") or a == "--in-place" for a in args) else READ
    if cmd == "perl":
        return WRITE if any((a.startswith("-") and "i" in a and "p" in a) or a == "-i" for a in args) else OTHER
    if cmd == "tar":
        return WRITE if any(("x" in a[1:] if a.startswith("-") else a.startswith("x")) for a in args) else OTHER
    if cmd == "open":
        return WEB if any(a.startswith("http://") or a.startswith("https://") for a in args) else OTHER

    if cmd in READ_COMMANDS:
        return READ
    if cmd in WRITE_COMMANDS:
        return WRITE
    if _mentions_test_word(cmd) and (first.startswith("./") or "/" in first or "\\" in first):
        return VERIFY
    return OTHER


def tokenize(command: str) -> Tuple[List[List[str]], bool]:
    """极简 shell 分词：按 && || ; | 换行 分段，处理引号与反斜杠；识别写入文件的重定向。

    不求完整 POSIX，只为分类服务。
    """
    segments: List[List[str]] = []
    words: List[str] = []
    word = ""
    has_word = False
    quote: Optional[str] = None
    escape = False
    expect_redirect_target = False
    writes = False
    chars = command
    i = 0
    n = len(chars)

    def end_word():
        nonlocal word, has_word, expect_redirect_target, writes
        if not has_word:
            return
        if expect_redirect_target:
            if word not in ("/dev/null", "/dev/stderr", "/dev/stdout", "nul", "NUL") and not word.startswith("&"):
                writes = True
            expect_redirect_target = False
        else:
            words.append(word)
        word = ""
        has_word = False

    def end_segment():
        nonlocal words
        end_word()
        if words:
            segments.append(words)
        words = []

    while i < n:
        c = chars[i]
        if escape:
            word += c
            has_word = True
            escape = False
            i += 1
            continue
        if quote is not None:
            if c == quote:
                quote = None
            elif c == "\\" and quote == '"':
                escape = True
            else:
                word += c
            i += 1
            continue
        if c == "\\":
            escape = True
        elif c in "'\"":
            quote = c
            has_word = True
        elif c in " \t":
            end_word()
        elif c in "\n;":
            end_segment()
        elif c == "&":
            if i + 1 < n and chars[i + 1] == "&":
                end_segment()
                i += 1
            elif i + 1 < n and chars[i + 1] == ">":
                end_word()
                i += 1
                if i + 1 < n and chars[i + 1] == ">":
                    i += 1
                expect_redirect_target = True
            elif has_word and word.endswith(">"):
                word += c
            else:
                end_segment()  # 后台运行 &
        elif c == "|":
            if i + 1 < n and chars[i + 1] == "|":
                i += 1
            end_segment()
        elif c == ">":
            # 2>&1、>&2 之类只是转移流，不写文件。
            fd_prefix = has_word and word.isdigit()
            if has_word and not fd_prefix:
                end_word()
            if fd_prefix:
                word = ""
                has_word = False
            if i + 1 < n and chars[i + 1] == ">":
                i += 1
            if i + 1 < n and chars[i + 1] == "&":
                i += 1
                while i + 1 < n and (chars[i + 1].isdigit() or chars[i + 1] == "-"):
                    i += 1
            else:
                expect_redirect_target = True
        elif c == "<":
            # 输入重定向与 heredoc：跳过标记本身。
            end_word()
            while i + 1 < n and chars[i + 1] in "<-":
                i += 1
            expect_redirect_target = False
        elif c in "(){}":
            if c == "(" and word.endswith("$"):
                word = word[:-1]
            end_segment()
        else:
            word += c
            has_word = True
        i += 1

    if expect_redirect_target and has_word:
        end_word()
    end_segment()
    return segments, writes


def shell_summary(command: str) -> Optional[str]:
    """命令摘要：取决定分类的那一段（跳过 cd、export 等），最多前三个词，命令名只留文件名。"""
    text = command.split("<<", 1)[0] if "<<" in command else command
    segments = [w for w in (_strip_prefix(s) for s in tokenize(text)[0]) if w]
    if not segments:
        return None
    kinds = [kind_of(s) for s in segments]
    best = 0
    for i, k in enumerate(kinds):
        if k > kinds[best]:
            best = i
    words = list(segments[best])
    if words[0] in ("bash", "sh", "zsh"):
        for i, w in enumerate(words):
            if w in ("-c", "-lc") and i + 1 < len(words):
                return shell_summary(words[i + 1])
    words[0] = _base_name(words[0])
    return " ".join(words[:3])


# MARK: 给人看的说明

def describe(tool: str, input: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """气泡里“当前活动”的简短说明。只取文件名、命令前几个词、网址域名，不含文件内容。"""
    input = input or {}
    key = tool.lower()

    if key == "read":
        f = _name(input, "file_path") or _name(input, "path")
        if not f:
            return None
        return tr("Viewing %s", "查看 %s") % f if _ext(f) in IMAGE_EXTENSIONS else tr("Reading %s", "阅读 %s") % f
    if key in ("readimage", "understandimage"):
        f = _name(input, "file_path") or _name(input, "image_path")
        return tr("Viewing %s", "查看 %s") % f if f else tr("Viewing an image", "查看图片")
    if key == "notebookread":
        f = _name(input, "notebook_path")
        return tr("Reading %s", "阅读 %s") % f if f else None
    if key == "write":
        f = _name(input, "file_path")
        return tr("Writing %s", "写入 %s") % f if f else None
    if key in ("edit", "multiedit", "str_replace_editor"):
        f = _name(input, "file_path")
        return tr("Editing %s", "编辑 %s") % f if f else tr("Editing a file", "编辑文件")
    if key == "notebookedit":
        f = _name(input, "notebook_path")
        return tr("Editing %s", "编辑 %s") % f if f else None
    if key == "grep":
        p = _text(input, "pattern")
        return tr("Searching %s", "搜索 %s") % p if p else None
    if key == "glob":
        p = _text(input, "pattern")
        return tr("Finding %s", "查找 %s") % p if p else None
    if key == "ls":
        f = _name(input, "path")
        return tr("Viewing %s", "查看 %s") % f if f else None
    if key == "webfetch":
        u = _text(input, "url")
        return tr("Browsing %s", "浏览 %s") % _host(u) if u else None
    if key in ("websearch", "web_search"):
        q = _text(input, "query")
        return tr("Searching the web: %s", "搜索网页 %s") % q if q else None
    if key in _SHELL_TOOLS:
        command = _text(input, "command") or ""
        # heredoc 脚本（python3 - <<EOF …）从命令本身看不出在做什么，优先用调用时附带的说明。
        if "<<" in command:
            d = _text(input, "description")
            if d:
                return d
        s = shell_summary(command)
        return "$ %s" % s if s else _text(input, "description")
    if key in _CONTINUE_TOOLS:
        return None
    if key in ("todowrite", "taskcreate", "taskupdate", "tasklist", "taskget", "updateplan"):
        return tr("Updating the task list", "整理任务清单")
    if key in ("enterplanmode", "exitplanmode", "exit_plan_mode"):
        return tr("Planning", "制定计划")
    if key == "toolsearch":
        return tr("Finding tools", "查找工具")
    if key in _ASK_TOOLS:
        q = PetQuestion.parse(input)
        return q.short_label if q else tr("Needs your answer", "等你回答")
    if key in ("agent", "task"):
        d = _text(input, "description")
        return tr("Delegating: %s", "委派：%s") % d if d else tr("Delegating to a helper", "委派助手")
    if key == "skill":
        s = _text(input, "skill") or _text(input, "name")
        return tr("Skill %s", "技能 %s") % s if s else tr("Loading a skill", "加载技能")
    if tool.startswith("mcp__"):
        short = tool.split("__")[-1]
        state = classify_mcp(tool, input)
        if state is PetState.view_image:
            return tr("Screenshot", "截图")
        if state is PetState.read_web:
            u = _text(input, "url")
            return tr("Browsing %s", "浏览 %s") % _host(u) if u else tr("Browser %s", "浏览器 %s") % short
        return short
    return tool
