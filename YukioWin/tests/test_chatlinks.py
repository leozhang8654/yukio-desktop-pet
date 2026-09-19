"""转录会话 → 桌面版 Claude 的那条聊天。移植自 YukioPlayer/Tests/YukioCoreTests/SessionLinkTests.swift。"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yukio.chatlinks import (ChatLinks, chat_url_for_desktop_session, is_desktop_session_id,
                             is_transcript_session_id, value_of)


def record(desktop: str, cli: str, filler: int = 0) -> str:
    """真实记录的开头：桌面版会话 ID 在最前，紧跟着转录的会话 ID。"""
    return ('{"sessionId":"%s","cliSessionId":"%s","cwd":"C:\\\\Users\\\\me\\\\proj",'
            '"isArchived":false,"title":"某个任务","toolSurfaceSnapshot":"%s"}'
            % (desktop, cli, "x" * filler))


class ChatLinkTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="yukio-session-links-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def make_records(self, records) -> str:
        # 桌面版把记录放在 <账号>/<组织>/ 下面，这里照着摆一层子目录。
        folder = os.path.join(self.root, "账号", "组织")
        os.makedirs(folder, exist_ok=True)
        for name, text in records:
            with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
                fh.write(text)
        return self.root

    def test_finds_the_chat_that_belongs_to_a_transcript_session(self):
        a = "11111111-2222-3333-4444-555555555555"
        b = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        root = self.make_records([
            ("local_1e6b0a2c-0000-4000-8000-000000000001.json",
             record("local_1e6b0a2c-0000-4000-8000-000000000001", a, filler=4096)),
            ("local_1e6b0a2c-0000-4000-8000-000000000002.json",
             record("local_1e6b0a2c-0000-4000-8000-000000000002", b)),
        ])
        links = ChatLinks(root)
        self.assertEqual(links.desktop_session_id(b), "local_1e6b0a2c-0000-4000-8000-000000000002")
        self.assertEqual(links.chat_url(a),
                         "claude://code/continue?session=local_1e6b0a2c-0000-4000-8000-000000000001")

    def test_unknown_session_gives_no_link_instead_of_a_wrong_one(self):
        root = self.make_records([
            ("local_1e6b0a2c-0000-4000-8000-000000000001.json",
             record("local_1e6b0a2c-0000-4000-8000-000000000001",
                    "11111111-2222-3333-4444-555555555555")),
        ])
        links = ChatLinks(root)
        # 终端里跑的会话（桌面版没有这条记录）：宁可没有链接，也不要跳到别人的聊天。
        self.assertIsNone(links.desktop_session_id("99999999-8888-7777-6666-555555555555"))
        # 目录不存在时也只是没有链接。
        self.assertIsNone(ChatLinks(os.path.join(root, "没有这个目录"))
                          .chat_url("11111111-2222-3333-4444-555555555555"))

    def test_only_id_shaped_values_become_links(self):
        # 会话 ID 直接拼进查找与链接，先限定字符。
        self.assertTrue(is_transcript_session_id("c0a80650-cd5e-4e6a-a048-462a287f8ddc"))
        self.assertFalse(is_transcript_session_id('" or 1=1'))
        self.assertFalse(is_transcript_session_id("短"))
        self.assertTrue(is_desktop_session_id("local_3987aafa-f03f-4d83-8995-1f6a2ebba08a"))
        self.assertIsNotNone(chat_url_for_desktop_session("local_3987aafa-f03f-4d83-8995-1f6a2ebba08a"))
        self.assertIsNone(chat_url_for_desktop_session("3987aafa-f03f-4d83-8995-1f6a2ebba08a"))
        self.assertIsNone(chat_url_for_desktop_session("local_a b"))

    def test_reads_the_value_even_with_spaces_around_the_colon(self):
        data = b'{ "sessionId" : "local_x-1" , "cliSessionId":"abc" }'
        self.assertEqual(value_of("sessionId", data), "local_x-1")
        self.assertEqual(value_of("cliSessionId", data), "abc")
        self.assertIsNone(value_of("没有这个键", data))


if __name__ == "__main__":
    unittest.main()
