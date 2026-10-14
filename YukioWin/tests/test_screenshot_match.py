import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from PIL import Image

spec = importlib.util.spec_from_file_location('screenshot_check', Path(__file__).resolve().parents[1] / 'scripts/check_screenshot.py')
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

class ScreenshotMatchTests(unittest.TestCase):
    def test_opening_still_pixels_that_move_later_are_not_static(self):
        frames = [Image.new('RGBA', (20, 20), (220, 30, 80, 255)) for _ in range(13)]
        frames[-1].putpixel((3, 4), (30, 210, 150, 255))
        library = SimpleNamespace(frame_count=lambda _: len(frames), frame=lambda _, i: SimpleNamespace(image=frames[i]))
        pixels = check.static_pixels(library, 'test')
        self.assertEqual(len(pixels), 399)
        self.assertFalse(any((x, y) == (3, 4) for x, y, _ in pixels))

    def test_near_opaque_moving_frame_matches_without_relaxing_ratio(self):
        frames = [Image.new('RGBA', (20, 20), (220, 30, 80, 253)), Image.new('RGBA', (20, 20), (30, 210, 150, 254))]
        library = SimpleNamespace(frame_count=lambda _: 2, frame=lambda _, i: SimpleNamespace(image=frames[i]))
        screen = Image.alpha_composite(Image.new('RGBA', (20, 20), (17, 100, 200, 255)), frames[1]).convert('RGB')
        ratio, count, index = check.best_frame_match(screen, library, 'test', (0, 0, 20, 20))
        self.assertEqual((ratio, count, index), (1.0, 400, 1))
        wrong = Image.new('RGB', (20, 20), 'white')
        self.assertLess(check.best_frame_match(wrong, library, 'test', (0, 0, 20, 20))[0], check.REQUIRED_RATIO)
        self.assertIsNone(check.best_frame_match(screen, library, 'test', (-1, 0, 20, 20))[2])
        frames[:] = [Image.new('RGBA', (20, 20), (255, 255, 255, 20))] * 2
        self.assertIsNone(check.best_frame_match(wrong, library, 'test', (0, 0, 20, 20))[2])
