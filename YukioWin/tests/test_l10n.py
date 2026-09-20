"""界面语言：默认英文、可切中文，两种语言的文案都取得到。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yukio import l10n
from yukio.cards import CardStatus
from yukio.classify import describe
from yukio.events import PetState
from yukio.router import ago_text, display_name, held_name, state_name, state_text
from yukio.settings import DEFAULTS


class L10nTests(unittest.TestCase):
    def setUp(self):
        self._old = l10n.language()

    def tearDown(self):
        l10n.set_language(self._old)

    def test_codes(self):
        for code, want in [(None, "en"), ("", "en"), ("en", "en"), ("fr", "en"),
                           ("zh", "zh"), ("zh-CN", "zh"), ("ZH_Hans", "zh")]:
            l10n.set_language(code)
            self.assertEqual(l10n.language(), want, code)

    def test_default_setting_is_english(self):
        self.assertEqual(DEFAULTS["language"], "en")

    def test_english(self):
        l10n.set_language("en")
        self.assertEqual(l10n.tr("Idle", "空闲"), "Idle")
        self.assertEqual(state_text(PetState.thinking), "Thinking")
        self.assertEqual(state_text(PetState.task_complete), "Done · click to open")
        self.assertEqual(state_name(PetState.idle), "Idle")
        self.assertEqual(held_name(), "Picked up")
        self.assertEqual(ago_text(5 * 60 * 1000), "5 min ago")
        self.assertEqual(display_name(None, "5c534545abcd"), "Session 5c534545…")
        self.assertEqual(CardStatus.label(CardStatus.waiting), "Waiting")
        self.assertEqual(describe("edit", {"file_path": "C:\\src\\login.py"}), "Editing login.py")
        self.assertEqual(describe("WebSearch", {"query": "form validation"}), "Searching the web: form validation")

    def test_chinese(self):
        l10n.set_language("zh")
        self.assertEqual(state_text(PetState.thinking), "思考中")
        self.assertEqual(state_name(PetState.idle), "空闲")
        self.assertEqual(CardStatus.label(CardStatus.ready), "答完了")
        self.assertEqual(describe("edit", {"file_path": "C:\\src\\login.py"}), "编辑 login.py")


if __name__ == "__main__":
    unittest.main()
