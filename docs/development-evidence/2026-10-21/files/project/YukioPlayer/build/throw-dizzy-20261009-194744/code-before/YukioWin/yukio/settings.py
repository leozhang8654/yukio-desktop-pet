"""本机设置：位置、大小、是否跟随、跟随谁。存成一个 JSON，坏了就用默认值。"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from .sources import app_data_dir

DEFAULTS: Dict[str, Any] = {
    "follow": True,
    "petVisible": True,
    "showCards": True,
    "showQuestionCard": True,
    "assistantName": "Yukio",
    "assistantUserName": "",
    "assistantReminderSound": True,
    "showBubble": True,
    "scale": 1.0,
    "source": "auto",      # auto / claude / deepcode（DeepSeek）/ gpt（Codex）
    "language": "en",      # en / zh：界面语言，默认英文
    "originX": None,
    "originY": None,
}


class Settings:
    def __init__(self, path: str = None):
        self.path = path or os.path.join(app_data_dir(), "settings.json")
        self._values = dict(DEFAULTS)
        try:
            with open(self.path, "r", encoding="utf-8-sig") as fh:
                stored = json.load(fh)
            if isinstance(stored, dict):
                for key in DEFAULTS:
                    if key in stored:
                        self._values[key] = stored[key]
        except (OSError, ValueError):
            pass

    def get(self, key: str, fallback: Any = None) -> Any:
        return self._values.get(key, DEFAULTS.get(key, fallback))

    def set(self, key: str, value: Any) -> None:
        if self._values.get(key) == value:
            return
        self._values[key] = value
        self.save()

    def save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self._values, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except OSError:
            pass
