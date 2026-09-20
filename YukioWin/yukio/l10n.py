"""界面语言：默认英文，托盘菜单「Language」可切中文，选择存在 settings.json 的 language 里。

已经写进事件里的说明文字（如 "Reading main.py"）不回溯翻译，下一条事件起换语言。
环境变量 YUKIO_LANG=zh 可以让命令行模式与测试按中文跑。
"""

from __future__ import annotations

import os

ENGLISH, CHINESE = "en", "zh"


def _normalise(code) -> str:
    return CHINESE if str(code or "").lower().startswith("zh") else ENGLISH


_current = _normalise(os.environ.get("YUKIO_LANG"))


def language() -> str:
    return _current


def set_language(code) -> None:
    global _current
    _current = _normalise(code)


def tr(en: str, zh: str) -> str:
    """英文在前、中文在后，按当前界面语言取一个。"""
    return zh if _current == CHINESE else en
