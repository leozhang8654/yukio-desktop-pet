#!/bin/sh
# 可选：Claude Code hook → 雪绪收件箱。
# 把 hook 的 stdin JSON 原样追加到收件箱文件，由雪绪读取。
# 永远不阻塞 Claude：不输出任何内容，始终以 0 退出。
INBOX="${YUKIO_INBOX:-$HOME/Library/Application Support/YukioPlayer/claude-hooks.jsonl}"
mkdir -p "$(dirname "$INBOX")" 2>/dev/null
{ cat; printf '\n'; } >> "$INBOX" 2>/dev/null
exit 0
