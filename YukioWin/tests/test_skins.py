"""Skin behavior through the actual player with fake Win32 windows."""
import os
import unittest
from unittest.mock import patch
from test_app_logic import make_app, app_module
from yukio.catalog import CatalogError, SpriteTimeline
from yukio.events import PetState
from yukio.settings import Settings
from yukio.skins import skin_root, normalize_skin


class SkinTests(unittest.TestCase):
    def test_switch_round_trip_preserves_activity_position_and_preferences(self):
        app = make_app()
        self.addCleanup(app.shutdown)
        app.shown_state = PetState.write_file
        app.timeline = SpriteTimeline(app.catalog.spec(app.shown_state), 0)
        before = app.library.frame('write_file', 0).image.tobytes()
        origin, scale = (app.pet.x, app.pet.y), app.scale
        app.set_skin('qianxia')
        self.assertEqual(app.shown_state, PetState.write_file)
        self.assertEqual(app.timeline.spec.id, 'write_file')
        self.assertEqual(app.timeline.spec.blink.levels, 12)
        self.assertEqual((app.pet.x, app.pet.y), origin)
        self.assertEqual(app.scale, scale)
        self.assertEqual(Settings(app.settings.path).get('skin'), 'qianxia')
        self.assertNotEqual(before, app.library.frame('write_file', 0).image.tobytes())
        app._drag_began()
        self.assertIsNone(app.swing)
        app.pet.move(app.pet.x + 10, app.pet.y)
        app._drag_ended()
        self.assertEqual(app.settings.get('originX'), app.pet.x)
        app.set_skin('yukio')
        self.assertEqual(before, app.library.frame('write_file', 0).image.tobytes())
        app._drag_began()
        self.assertIsNotNone(app.swing)
        app.set_skin('qianxia')
        self.assertIsNone(app.swing)
        self.assertIsNone(app.held_timeline)

    def test_failed_switch_keeps_old_skin_and_saved_choice(self):
        app = make_app()
        self.addCleanup(app.shutdown)
        catalog, library = app.catalog, app.library
        with patch('yukio.app.AnimationCatalog.load', side_effect=CatalogError('missing')):
            with self.assertRaises(CatalogError):
                app.set_skin('qianxia')
        self.assertIs(app.catalog, catalog)
        self.assertIs(app.library, library)
        self.assertEqual(app.skin, 'yukio')
        self.assertEqual(Settings(app.settings.path).get('skin'), 'yukio')

    def test_restart_restores_selection_and_missing_skin_recovers(self):
        original = make_app()
        self.addCleanup(original.shutdown)
        original.set_skin('qianxia')
        path = original.settings.path
        with patch.object(app_module, 'Settings', side_effect=lambda: Settings(path)), \
             patch.object(app_module, 'default_sources', return_value=[]):
            restored = app_module.PetApp([])
            self.addCleanup(restored.shutdown)
            self.assertEqual(restored.skin, 'qianxia')
            self.assertEqual(restored.timeline.spec.blink.levels, 12)
            real_load = app_module.AnimationCatalog.load
            def fail_skin(root):
                if root.endswith(os.path.join('skins', 'qianxia')):
                    raise CatalogError('broken skin')
                return real_load(root)
            with patch.object(app_module.AnimationCatalog, 'load', side_effect=fail_skin):
                fallback = app_module.PetApp([])
                self.addCleanup(fallback.shutdown)
                self.assertEqual(fallback.skin, 'yukio')
                self.assertEqual(Settings(path).get('skin'), 'yukio')

    def test_invalid_skin_cannot_escape_assets(self):
        self.assertEqual(normalize_skin('../outside'), 'yukio')
        with self.assertRaises(ValueError):
            skin_root('/assets', '../outside')
