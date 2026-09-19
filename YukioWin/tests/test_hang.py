"""被大手拎着时的摆动与窗口几何。移植自 YukioPlayer/Tests/YukioCoreTests/HangTests.swift。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yukio.hang import HangGeometry, HangSwing, Tuning, feet_offset_at


class Hand:
    """按 30 Hz 推进摆动，手的位置由一段轨迹给出。"""

    def __init__(self, length=100.0, tuning=None, x=500.0, y=400.0):
        self.swing = HangSwing(0, length=length, tuning=tuning)
        self.now = 0.0
        self.x = x
        self.y = y

    def move(self, v, ms, up=0.0, step=1000.0 / 30):
        """横向 v、纵向 up（向上为正，点／秒）走 ms 毫秒。v 为 0 就是停在原地。"""
        left = ms
        while left > 0:
            h = min(step, left)
            left -= h
            self.now += h
            self.x += v * h / 1000.0
            self.y += up * h / 1000.0
            self.swing.advance(self.now, self.x, self.y)

    @property
    def degrees(self):
        return self.swing.angle_degrees


class HangSwingTests(unittest.TestCase):
    def test_hangs_straight_when_nobody_moves(self):
        hand = Hand()
        hand.move(0, 2000)
        self.assertLess(abs(hand.degrees), 0.001)

    def test_body_lags_behind_the_hand(self):
        # 往右加速：身体落在后面，也就是脚偏向左（负角）。
        right = Hand()
        right.move(900, 200)
        self.assertLess(right.degrees, -3)

        left = Hand()
        left.move(-900, 200)
        self.assertGreater(left.degrees, 3)

    def test_swings_past_vertical_after_stopping(self):
        hand = Hand()
        hand.move(900, 250)
        self.assertLess(hand.degrees, -3)
        # 手停住，身体越过竖直方向荡到前面去。
        overshoot = 0.0
        for _ in range(12):
            hand.move(0, 1000.0 / 30)
            overshoot = max(overshoot, hand.degrees)
        self.assertGreater(overshoot, 2)

    def test_swing_dies_down(self):
        hand = Hand()
        hand.move(1200, 200)
        hand.move(0, 200)
        first = later = 0.0
        for _ in range(30):
            hand.move(0, 1000.0 / 30)
            first = max(first, abs(hand.degrees))
        for _ in range(30):
            hand.move(0, 1000.0 / 30)
            later = max(later, abs(hand.degrees))
        self.assertLess(later, first * 0.7)

    def test_leans_back_while_carried_at_constant_speed(self):
        # 匀速拖着走：只剩空气阻力，身体稳定地略微落在后面，不会越摆越大。
        hand = Hand()
        hand.move(600, 3000)
        self.assertTrue(-12 < hand.degrees < -1)
        # 停下就回正。
        hand.move(0, 2500)
        self.assertLess(abs(hand.degrees), 1.5)

    def test_never_folds_over_even_when_flung_around(self):
        hand = Hand()
        worst = 0.0
        for i in range(20):
            hand.move(6000 if i % 2 == 0 else -6000, 120)
            worst = max(worst, abs(hand.degrees))
        self.assertLessEqual(worst, Tuning().max_angle_deg + 0.001)

    def test_bigger_pet_swings_less(self):
        # 重心更远（放大后的雪绪）：同样的甩动，摆幅更小。
        small = Hand(length=100)
        big = Hand(length=160)
        small.move(900, 200)
        big.move(900, 200)
        self.assertLess(abs(big.degrees), abs(small.degrees))

    def test_settles_soon_after_release(self):
        hand = Hand()
        hand.move(1500, 200, up=600)
        hand.swing.release()
        self.assertFalse(hand.swing.settled)
        waited = 0.0
        while not hand.swing.settled and waited < 4000:
            hand.move(0, 1000.0 / 30)
            waited += 1000.0 / 30
        self.assertTrue(hand.swing.settled)
        self.assertLess(waited, 2400)          # 播放器最多等 2400 ms 就放下

    # MARK: 重量感：竖直方向那根会伸缩的布

    def test_body_sinks_when_lifted_quickly(self):
        hand = Hand()
        hand.move(0, 200, up=900)
        self.assertGreater(hand.swing.sag, 4)      # 手往上提，身体先坠在下面
        # 手停住后弹回来，越过原位一点再收住。
        lowest = hand.swing.sag
        for _ in range(30):
            hand.move(0, 1000.0 / 30)
            lowest = min(lowest, hand.swing.sag)
        self.assertLess(lowest, 0)
        hand.move(0, 1500)
        self.assertLess(abs(hand.swing.sag), 0.6)

    def test_pure_sideways_drag_does_not_sink(self):
        hand = Hand()
        hand.move(1200, 400)
        self.assertLess(abs(hand.swing.sag), 0.001)

    def test_sinking_has_a_limit(self):
        hand = Hand(length=100)
        for _ in range(10):
            hand.move(0, 100, up=9000)
            hand.move(0, 100, up=-9000)
        self.assertLessEqual(abs(hand.swing.sag), 0.16 * 100 + 0.001)

    def test_grabbing_again_keeps_the_current_swing(self):
        hand = Hand()
        hand.move(1200, 200)
        hand.swing.release()
        hand.move(0, 100)
        angle = hand.degrees
        hand.swing.grab()
        self.assertEqual(hand.swing.angle_degrees, angle)
        self.assertFalse(hand.swing.settled)

    def test_survives_sleep_and_frame_drops(self):
        # 窗口被遮住、机器休眠后隔很久才回来：不补积分，也不会炸成 NaN。
        hand = Hand()
        hand.move(900, 200)
        hand.now += 600000
        hand.swing.advance(hand.now, hand.x + 4000, hand.y - 3000)
        self.assertEqual(hand.degrees, hand.degrees)      # 不是 NaN
        self.assertLessEqual(abs(hand.degrees), Tuning().max_angle_deg + 0.001)


class HangGeometryTests(unittest.TestCase):
    def test_positive_angle_puts_the_feet_to_the_right(self):
        """正角＝脚偏右。

        macOS 版曾经把符号写反，屏幕上成了「脚朝着移动方向甩出去」，与真实的钟摆相反；
        这条盯着旋转方向，改渲染时别再弄反。
        """
        self.assertGreater(feet_offset_at(20), 0)
        self.assertLess(feet_offset_at(-20), 0)

    def test_the_window_grows_enough_for_the_swing_and_the_sag(self):
        # 抓手点在头顶上方 9.7 px、横向居中；192×240 的图挂在 192×208 那块窗口上。
        geo = HangGeometry.make((192, 208), (192, 240), (96.0, 9.7), scale=1.0, sag_room=15.2)
        w, h = geo.panel_size
        self.assertGreater(w, 192)
        self.assertGreater(h, 240)
        # 上边缘与平时那块对齐：图顶在窗口里就是抓手点上方那一点点。
        self.assertAlmostEqual(geo.sprite_rect[1] + 9.7, geo.pivot[1], places=3)
        # 抓手点横向仍在平时那块的中线上。
        self.assertAlmostEqual(geo.pivot[0] + geo.offset[0], 96.0, delta=1.0)
        # 窗口往左上让出的那截，正好容得下最大倾角扫过去的部分。
        self.assertLess(geo.offset[0], 0)
        self.assertLess(geo.offset[1], 0)

    def test_scaling_up_scales_the_window_and_the_grip(self):
        one = HangGeometry.make((192, 208), (192, 240), (96.0, 9.7), scale=1.0)
        two = HangGeometry.make((384, 416), (192, 240), (96.0, 9.7), scale=2.0)
        self.assertGreater(two.panel_size[0], one.panel_size[0] * 1.8)
        self.assertAlmostEqual(two.pivot[1] - two.sprite_rect[1], 2 * 9.7, places=3)


if __name__ == "__main__":
    unittest.main()
