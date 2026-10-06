import unittest

from yukio.bubble import BubbleLayout
from yukio.cardstack import CardStackLayout
from yukio.events import Kind, PetEvent
from yukio.router import ActivityRouter


class BubbleColorTests(unittest.TestCase):
    def test_mixed_agents_keep_their_colors_when_focus_switches(self):
        router = ActivityRouter(now=0)
        colors = {"codex": (80, 85, 94, 255),
                  "claude-transcript": (217, 119, 70, 255),
                  "claude-hook": (217, 119, 70, 255),
                  "deepcode": (77, 128, 228, 255)}
        for source in colors:
            router.ingest(PetEvent(0, source, source, Kind.task_start), now=0)
        for source, color in colors.items():
            router.pin_session(source, now=1000)
            router.tick(1000)
            for scale in (1, 1.5, 2):
                image = BubbleLayout(router.status_line(1000), scale=scale).render()
                self.assertEqual(image.getpixel((image.width // 2, int(3 * scale))), color)
                self.assertEqual(image.getpixel((image.width // 2, int(4 * scale))), (255, 255, 255, 240))
                card = next(c for c in router.cards(1000, include_focused=True) if c.session == source)
                image = CardStackLayout([card], scale=scale).render()
                self.assertEqual(image.getpixel((image.width // 2, int(3 * scale))), color)
                self.assertEqual(image.getpixel((image.width // 2, int(4 * scale))), (255, 255, 255, 240))
