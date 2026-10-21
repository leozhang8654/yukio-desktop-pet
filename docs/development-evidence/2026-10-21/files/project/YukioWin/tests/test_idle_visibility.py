"""Visibility lifecycle with fake windows; native Win32 acceptance is separate."""
import os
import tempfile
import unittest

from test_app_logic import make_app, advance, now
from yukio.events import PetEvent, Kind, PetState
from yukio.settings import Settings


class IdleVisibilityTests(unittest.TestCase):
    def make(self):
        app = make_app(hide_when_idle=True)
        self.addCleanup(app.shutdown)
        return app

    def event(self, app, kind, activity=None):
        app.router.ingest(PetEvent(now(), "test", "visibility", kind,
                                  event_id=activity.value if activity else None, activity=activity), now())
        advance(app, 55)

    def test_default_and_round_trip_setting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "settings.json")
            settings = Settings(path)
            self.assertTrue(settings.get("hideWhenIdle"))
            settings.set("hideWhenIdle", False)
            self.assertFalse(Settings(path).get("hideWhenIdle"))

    def test_idle_work_idle_preserves_position_and_hides_all_windows(self):
        a = self.make()
        self.assertTrue(a.pet_hidden)
        self.assertFalse(a.pet.visible)
        origin = a.pet.x, a.pet.y
        self.event(a, Kind.task_start)
        self.assertTrue(a.pet.visible)
        self.assertTrue(a.bubble.visible)
        self.assertEqual((a.pet.x, a.pet.y), origin)
        self.event(a, Kind.task_abort)
        self.assertEqual(a.shown_state, PetState.idle)
        self.assertTrue(all(not w.visible for w in (a.pet, a.bubble, a.cards, a.question)))

    def test_switch_and_explicit_show_restore_the_same_idle_frame(self):
        a = self.make()
        a.set_hide_when_idle(False)
        self.assertTrue(a.pet.visible)
        a.set_hide_when_idle(True)
        self.assertFalse(a.pet.visible)
        a.set_hidden(False)
        advance(a, 5)
        self.assertTrue(a.pet.visible)
        self.event(a, Kind.task_start)
        self.event(a, Kind.task_abort)
        self.assertFalse(a.pet.visible)

    def test_manual_hide_has_priority_over_work_and_setting(self):
        a = self.make()
        a.set_hidden(True)
        self.event(a, Kind.task_start)
        a.set_hide_when_idle(False)
        self.assertFalse(a.pet.visible)
        self.assertFalse(a.bubble.visible)
        a.set_hidden(False)
        self.assertTrue(a.pet.visible)
        self.assertTrue(a.bubble.visible)

    def test_question_completion_and_failure_remain_visible(self):
        a = self.make()
        self.event(a, Kind.task_start)
        self.event(a, Kind.activity_start, PetState.question_for_user)
        self.assertEqual(a.shown_state, PetState.question_for_user)
        self.assertTrue(a.pet.visible)
        self.event(a, Kind.activity_end, PetState.question_for_user)
        self.event(a, Kind.final_answer)
        self.event(a, Kind.task_end)
        advance(a, 180)
        self.assertEqual(a.shown_state, PetState.task_complete)
        self.assertTrue(a.pet.visible)
        a._drop_sign()
        advance(a, 55)
        self.assertFalse(a.pet.visible)
        self.event(a, Kind.task_start)
        self.event(a, Kind.task_failed)
        self.assertEqual(a.shown_state, PetState.failed)
        self.assertTrue(a.pet.visible)

    def test_drag_and_demo_keep_idle_visible_until_they_end(self):
        a = self.make()
        self.event(a, Kind.task_start)
        a._drag_pending = True
        self.event(a, Kind.task_abort)
        self.assertTrue(a.pet.visible)
        a._drag_pending = False
        advance(a, 1)
        self.assertFalse(a.pet.visible)
        a.start_demo()
        advance(a, 1)
        self.assertTrue(a.pet.visible)
        a.stop_demo()
        advance(a, 1)
        self.assertFalse(a.pet.visible)
