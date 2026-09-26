"""Reminder persistence, catch-up and failure recovery, without a GUI or real clock."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from yukio.reminders import ReminderStore, APPLE_EPOCH
from yukio.settings import Settings

NOW = 1800000000


class ReminderTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "reminders.json"
        self.store = ReminderStore(self.path)

    def test_invalid_input_never_changes_disk(self):
        for title, due in [("  ", NOW+60), ("drink", NOW), ("drink", float("nan"))]:
            self.assertFalse(self.store.save(title, due, now=NOW))
        self.assertEqual(self.store.items, [])
        self.assertFalse(self.path.exists())

    def test_sleep_catchup_and_restart_preserve_ringing(self):
        self.assertTrue(self.store.save(" water ", NOW+60, now=NOW))
        self.assertTrue(self.store.save("walk", NOW+120, now=NOW))
        self.assertEqual(self.store.tick(NOW), [])
        restarted = ReminderStore(self.path)
        self.assertEqual(len(restarted.tick(NOW+3600)), 2)
        self.assertEqual(restarted.tick(NOW+3601), [])
        self.assertEqual(len(ReminderStore(self.path).list("ringing")), 2)
        self.assertEqual(restarted.items[0]["title"], "water")

    def test_edit_snooze_complete_and_delete(self):
        self.store.save("old", NOW+60, now=NOW)
        rid = self.store.items[0]["id"]
        self.store.save("new", NOW+120, rid, now=NOW)
        self.assertEqual(self.store.tick(NOW+60), [])
        self.assertEqual(self.store.tick(NOW+120), [rid])
        self.assertTrue(self.store.snooze(rid, NOW+130))
        self.assertEqual(self.store.tick(NOW+429), [])
        self.assertEqual(self.store.tick(NOW+430), [rid])
        self.store.complete(rid)
        self.store.snooze(rid, NOW+500)
        self.assertEqual(self.store.items[0]["status"], "completed")
        self.assertEqual(self.store.tick(NOW+1000), [])
        self.store.remove(rid)
        self.assertEqual(ReminderStore(self.path).items, [])

    def test_failed_write_keeps_previous_state_and_allows_retry(self):
        self.store.save("saved", NOW+60, now=NOW)
        original = self.path.read_bytes()
        with patch("yukio.reminders.os.replace", side_effect=OSError("disk full")):
            self.assertEqual(self.store.tick(NOW+60), [])
            self.assertFalse(self.store.save("lost", NOW+120, now=NOW))
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(len(self.store.list("scheduled")), 1)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])
        self.assertEqual(len(self.store.tick(NOW+60)), 1)

    def test_corrupt_or_future_version_file_never_overwritten(self):
        for content in ['not json', '{"version":2,"items":[]}', '{"version":1,"items":[{}]}']:
            self.path.write_text(content)
            store = ReminderStore(self.path)
            self.assertFalse(store.available)
            self.assertFalse(store.save("new", NOW+60, now=NOW))
            self.assertEqual(store.tick(NOW+60), [])
            self.assertEqual(self.path.read_text(), content)

    def test_reads_macOS_v1_date_and_writes_same_contract(self):
        fixture = {"version": 1, "items": [{"id": "E388B2A7-61BB-409F-92E2-F3F8D7A1D020", "title": "喝水", "dueAt": NOW+60-APPLE_EPOCH, "status": "scheduled"}]}
        self.path.write_text(json.dumps(fixture))
        store = ReminderStore(self.path)
        self.assertEqual(store.due_at(store.items[0]), NOW+60)
        self.assertEqual(len(store.tick(NOW+60)), 1)
        self.assertEqual(json.loads(self.path.read_text())["items"][0]["dueAt"], NOW+60-APPLE_EPOCH)

    def test_preferences_and_existing_card_switches_survive_restart(self):
        path = str(self.path.parent / "settings.json")
        values = {"assistantName": "雪绪", "assistantUserName": "Leo", "assistantReminderSound": False,
                  "petVisible": False, "showCards": False, "showQuestionCard": False}
        settings = Settings(path)
        for k,v in values.items(): settings.set(k,v)
        restored = Settings(path)
        for k,v in values.items(): self.assertEqual(restored.get(k),v)
