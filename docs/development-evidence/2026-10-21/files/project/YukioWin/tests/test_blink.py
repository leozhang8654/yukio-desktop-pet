"""Independent blink timing and exact eyelid ROI composition."""

import os
import hashlib
import json
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yukio.blink import BlinkClock
from yukio.catalog import AnimationSpec, BlinkOverlay
from yukio.sprites import SpriteLibrary


class BlinkClockTests(unittest.TestCase):
    def test_matches_swift_scheduler_fixture(self):
        clock = BlinkClock(173, 0)
        self.assertAlmostEqual(clock.next_start, 4073.081079497934, places=6)
        self.assertAlmostEqual(clock.duration, 257.62546254321933, places=6)
        clock.level(clock.next_start + clock.duration + 0.01)
        self.assertAlmostEqual(clock.next_start, 7431.838982841001, places=6)

    def test_switching_keeps_pending_or_active_blink(self):
        clock = BlinkClock(173, 1000)
        due, duration = clock.next_start, clock.duration
        clock.select_seed(941)
        self.assertEqual((clock.next_start, clock.duration), (due, duration))
        closed = clock.level(due + duration * 0.44)
        clock.select_seed(3251)
        self.assertEqual(closed, 6)
        self.assertEqual(clock.level(due + duration * 0.44), closed)
        self.assertEqual(clock.next_start, due)

    def test_double_blink_and_regular_gaps_stay_in_range(self):
        clock = BlinkClock(4567, 0)
        for _ in range(100):
            start, duration = clock.next_start, clock.duration
            self.assertGreaterEqual(duration, 180)
            self.assertLessEqual(duration, 260)
            self.assertEqual(clock.level(start + duration * 0.44), 6)
            clock.level(start + duration + 0.001)
            gap = clock.next_start - start - duration
            self.assertTrue(100 <= gap <= 180 or 2800 <= gap <= 7000)


class BlinkCompositionTests(unittest.TestCase):
    def test_patch_replaces_rgba_instead_of_blending_old_iris(self):
        root = tempfile.mkdtemp(prefix="yukio-blink-")
        os.makedirs(os.path.join(root, "motion"))
        base = Image.new("RGBA", (4, 4), (220, 0, 0, 255))
        base.save(os.path.join(root, "motion", "body.png"))
        # The transparent top-left patch pixel must erase the red base pixel.
        eye = Image.new("RGBA", (2, 2), (0, 220, 0, 255))
        eye.putpixel((0, 0), (0, 0, 0, 0))
        eye.save(os.path.join(root, "motion", "eyes.png"))
        blink = BlinkOverlay("eyes.png", 1, 1, 2, 2, 1, [[0]], 173)
        spec = AnimationSpec("idle", "idle", "motion/body.png", 4, 4,
                             [0], [100.0], True, False, blink=blink)

        class Catalog:
            specs = {"idle": spec, "default_work": spec}

        library = SpriteLibrary(Catalog(), root)
        open_eye = library.frame("idle", 0, 0).image
        closed_eye = library.frame("idle", 0, 1).image
        self.assertEqual(open_eye.getpixel((1, 1)), (220, 0, 0, 255))
        self.assertEqual(closed_eye.getpixel((1, 1)), (0, 0, 0, 0))
        self.assertEqual(closed_eye.getpixel((2, 2)), (0, 220, 0, 255))

    def test_packaged_page_mode_needs_no_giant_source_atlas(self):
        root = tempfile.mkdtemp(prefix="yukio-pages-")
        pages = os.path.join(root, "motion", "windows-pages")
        os.makedirs(os.path.join(pages, "body"))
        os.makedirs(os.path.join(pages, "eyes"))
        motion = b'{"version":4,"states":[]}'
        with open(os.path.join(root, "motion", "motion.json"), "wb") as fh:
            fh.write(motion)
        body = Image.new("RGBA", (4, 4), (20, 40, 60, 255))
        body.save(os.path.join(pages, "body", "idle-000.png"))
        eye = Image.new("RGBA", (2, 2), (0, 0, 0, 0))
        eye.save(os.path.join(pages, "eyes", "idle-000.png"))
        manifest = {
            "version": 1,
            "motionSha256": hashlib.sha256(motion).hexdigest(),
            "states": {"idle": {
                "body": {"count": 1, "perPage": 13, "pages": ["body/idle-000.png"],
                         "atlasWidth": 4, "atlasHeight": 4},
                "eyes": {"count": 1, "perPage": 64, "columns": 16,
                         "pages": ["eyes/idle-000.png"], "atlasWidth": 2, "atlasHeight": 2},
            }},
        }
        with open(os.path.join(pages, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump(manifest, fh)
        blink = BlinkOverlay("missing-source-eyes.webp", 1, 1, 2, 2, 1, [[0]], 173)
        spec = AnimationSpec("idle", "idle", "motion/missing-source-body.webp", 4, 4,
                             [0], [100.0], True, False, blink=blink)

        class Catalog:
            specs = {"idle": spec}

        library = SpriteLibrary(Catalog(), root)
        frame = library.frame("idle", 0, 1).image
        self.assertEqual(frame.getpixel((0, 0)), (20, 40, 60, 255))
        self.assertEqual(frame.getpixel((1, 1)), (0, 0, 0, 0))
        self.assertEqual(library.logical_asset_size(spec.asset_path), (4, 4))


if __name__ == "__main__":
    unittest.main()
