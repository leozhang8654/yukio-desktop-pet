"""被一只看不见的大手拎着时的晃动，以及那张图与窗口的摆放。

手往右一甩，身体因为惯性落在后面（往左偏）；手停住，身体越过竖直方向荡到另一边，再来回几次收住。
匀速拖着走时只剩空气阻力，身体略微后仰；一停就回正。
竖直方向另有一根「会伸缩的布」：手猛地往上提，身体先坠在下面再弹回来——沉甸甸的感觉主要来自这里。

纯逻辑、不碰窗口，时间用毫秒（与播放器其余部分一致），可以用虚拟时钟测试。

移植自 YukioPlayer/Sources/YukioCore/HangSwing.swift 与 main.swift 里的 HangGeometry，
数值与行为保持一致。
"""

from __future__ import annotations

import math
from typing import NamedTuple, Optional, Tuple


class Tuning:
    """摆动的参数。数值与 macOS 版一致，改之前先看 HANDOFF 里当天的记录。"""

    def __init__(self):
        #: 小幅摆动一个来回的秒数。沉的东西摆得慢：0.9 秒比 0.6 秒明显更有分量。
        #: 固定周期是为了手感稳定：放大雪绪时摆得一样慢，只是摆幅小些。
        self.period_sec = 0.9
        #: 阻尼比。0 一直晃，1 不过冲。沉的东西惯性大，晃两下才停。
        self.damping = 0.13
        #: 松手后的阻尼比：快一些停稳，好接回原来的动作。
        self.release_damping = 0.4
        #: 空气阻力（1/秒）：匀速移动时身体略微落在后面（600 点/秒约 3°），停下即回正。
        self.air_drag = 0.43
        #: 手的加速度有多少真的甩到她身上。严格按「一个点当一毫米」算，随便一拖就甩到顶格；
        #: 打折之后：轻轻挪 3°、正常拖 11°、大步拖 18°、用力甩才碰上限。
        self.hand_coupling = 0.11
        #: 手速的低通时间常数（秒）。鼠标事件一跳一跳地来，先抹平再求加速度，免得抖成毛刺；
        #: 调大一点也让她起步慢半拍，像拖着个有分量的东西。
        self.velocity_smoothing_sec = 0.07
        #: 最大倾角（度）。撞到这个角度就像碰到挡块，不再往外走。
        self.max_angle_deg = 20.0
        #: 积分子步长（秒）。一帧切成若干步，快速甩动也不会发散。
        self.step_sec = 1.0 / 240
        #: 竖直方向那根布的伸缩：一个来回的秒数与阻尼比。比左右摆快，弹一下就收住。
        self.sag_period_sec = 0.42
        self.sag_damping = 0.32
        #: 手上下动的速度有多少变成「坠」。0.25 时轻轻提坠 4–6 点，猛地提坠 11 点（还没到上限）。
        self.vertical_coupling = 0.25
        #: 最多坠多少，按摆长的比例（放大时跟着放大）。
        self.max_sag_ratio = 0.16
        #: 判定“停稳了”的角度（度）、角速度（度/秒）与坠的距离（点）。
        self.settle_angle_deg = 0.7
        self.settle_rate_deg_per_sec = 9.0
        self.settle_sag_points = 0.6


#: 播放器最多再等这么久就把她放下：万一参数改得收敛很慢，也不会一直挂着。
SETTLE_LIMIT_MS = 2400.0


class HangSwing:
    """把雪绪当成吊在抓手下面的单摆。"""

    def __init__(self, now: float, length: float = 96.0, tuning: Optional[Tuning] = None):
        self.tuning = tuning or Tuning()
        #: 抓手到身体重心的距离（点）。只用来把手的加速度换算成角加速度：
        #: 同样的甩动，雪绪放大时（重心更远）摆幅更小，和真东西一样。
        self.length = max(float(length), 1.0)
        #: 身体偏离竖直方向的角度（弧度），正数表示脚偏向右边。
        self.angle = 0.0
        #: 角速度（弧度／秒）。
        self.rate = 0.0
        #: 身体比抓手点低多少（点，正数＝坠下去）。渲染时整张图往下挪这么多。
        self.sag = 0.0
        self._sag_rate = 0.0
        #: 平滑后的手的横向、纵向速度（点／秒；纵向以屏幕坐标为准，向上为正）。
        self._hand_vx = 0.0
        self._hand_vy = 0.0
        self._last_x: Optional[float] = None
        self._last_y: Optional[float] = None
        self._last_ms = float(now)
        self._released = False

    @property
    def angle_degrees(self) -> float:
        return self.angle * 180.0 / math.pi

    @property
    def settled(self) -> bool:
        """松手后已经停稳，可以切回原来的动作。"""
        t = self.tuning
        return (self._released
                and abs(self.angle_degrees) < t.settle_angle_deg
                and abs(self.rate * 180.0 / math.pi) < t.settle_rate_deg_per_sec
                and abs(self.sag) < t.settle_sag_points)

    def release(self) -> None:
        """松手：大手把她放下，之后只剩自己荡回来，阻尼加大。"""
        self._released = True

    def grab(self) -> None:
        """还在晃的时候又被抓住：接着当前的角度和角速度继续，不要归零。"""
        self._released = False

    def advance(self, now: float, hand_x: float, hand_y: float) -> None:
        """推进到 now。hand_x、hand_y 是抓手当前在屏幕上的位置（点，y 向上为正）。"""
        t = self.tuning
        dt = (now - self._last_ms) / 1000.0
        self._last_ms = now
        if dt <= 0:
            return
        # 休眠、被遮挡后可能隔了很久才回来，不要一次补积分半秒。
        dt = min(dt, 0.1)
        smooth = 1.0 - math.exp(-dt / max(t.velocity_smoothing_sec, 1e-4))

        raw_x = (hand_x - (self._last_x if self._last_x is not None else hand_x)) / dt
        self._last_x = hand_x
        previous_x = self._hand_vx
        self._hand_vx += (raw_x - self._hand_vx) * smooth
        # 抓手横向加速给的惯性冲量，等于把 -a/L·cosθ 在这一帧上积分一次。
        self.rate -= t.hand_coupling * (self._hand_vx - previous_x) * math.cos(self.angle) / self.length

        # 竖直方向同理：手往上提得越猛，身体越是先坠在下面。
        raw_y = (hand_y - (self._last_y if self._last_y is not None else hand_y)) / dt
        self._last_y = hand_y
        previous_y = self._hand_vy
        self._hand_vy += (raw_y - self._hand_vy) * smooth
        self._sag_rate += t.vertical_coupling * (self._hand_vy - previous_y)

        w0 = 2 * math.pi / max(t.period_sec, 1e-3)
        ws = 2 * math.pi / max(t.sag_period_sec, 1e-3)
        zeta = t.release_damping if self._released else t.damping
        limit = t.max_angle_deg * math.pi / 180.0
        sag_limit = t.max_sag_ratio * self.length
        remaining = dt
        while remaining > 0:
            h = min(t.step_sec, remaining)
            remaining -= h
            gravity = -w0 * w0 * math.sin(self.angle)
            friction = -2 * zeta * w0 * self.rate
            air = -t.air_drag * self._hand_vx * math.cos(self.angle) / self.length
            self.rate += (gravity + friction + air) * h
            self.angle += self.rate * h
            if self.angle > limit:
                self.angle = limit
                self.rate = min(self.rate, 0.0)
            elif self.angle < -limit:
                self.angle = -limit
                self.rate = max(self.rate, 0.0)

            self._sag_rate += (-ws * ws * self.sag - 2 * t.sag_damping * ws * self._sag_rate) * h
            self.sag += self._sag_rate * h
            if self.sag > sag_limit:
                self.sag = sag_limit
                self._sag_rate = min(self._sag_rate, 0.0)
            elif self.sag < -sag_limit:
                self.sag = -sag_limit
                self._sag_rate = max(self._sag_rate, 0.0)


class HangGeometry(NamedTuple):
    """拎起来时那张图与窗口的摆放（屏幕坐标，y 向下，与 Windows 的分层窗口一致）。

    图比常规帧高：领口被捏起的尖在头顶上方，两条腿垂到下面；上边缘与平时那块 192×208 对齐，
    所以抓起来的一瞬间头不会跳。窗口按最大倾角扫过的范围放大，晃到两边也不会被切掉
    （多出来的部分是透明的，看不见）。
    """

    #: 拎起来时窗口的大小（像素）。
    panel_size: Tuple[int, int]
    #: 放大后的窗口左上角相对平时窗口左上角的位移（通常是负数）。
    offset: Tuple[int, int]
    #: 图在窗口里占的矩形 (x, y, 宽, 高)，以及绕着转的那一点（都是窗口内坐标）。
    sprite_rect: Tuple[float, float, float, float]
    pivot: Tuple[float, float]

    @staticmethod
    def make(pet_size: Tuple[int, int], frame_size: Tuple[int, int],
             grip: Tuple[float, float], scale: float = 1.0, sag_room: float = 0.0,
             max_angle_deg: Optional[float] = None) -> "HangGeometry":
        """pet_size：平时那块窗口的像素大小；frame_size、grip：帧的原始尺寸与抓手点（帧内像素）。

        sag_room：身体最多能往下坠多少像素，窗口底下要留出这段。
        """
        if max_angle_deg is None:
            max_angle_deg = Tuning().max_angle_deg
        pw, ph = pet_size
        fw, fh = frame_size
        sprite = (
            (pw - fw * scale) / 2.0,        # 左：与平时那块横向居中
            0.0,                            # 上：与平时那块上边缘对齐（头不跳）
            fw * scale,
            fh * scale,
        )
        pivot = (sprite[0] + grip[0] * scale, sprite[1] + grip[1] * scale)

        limit = max_angle_deg * math.pi / 180.0
        box = _rect_bounds(sprite)
        for i in range(-12, 13):
            box = _union(box, _rotated_bounds(sprite, pivot, limit * i / 12.0))
        box = (box[0] - 1, box[1] - 1, box[2] + 1, box[3] + 1)
        box = (box[0], box[1], box[2], box[3] + sag_room)

        width = int(math.ceil(box[2] - box[0]))
        height = int(math.ceil(box[3] - box[1]))
        return HangGeometry(
            panel_size=(max(1, width), max(1, height)),
            offset=(int(math.floor(box[0])), int(math.floor(box[1]))),
            sprite_rect=(sprite[0] - box[0], sprite[1] - box[1], sprite[2], sprite[3]),
            pivot=(pivot[0] - box[0], pivot[1] - box[1]))


def rotate_point(dx: float, dy: float, angle_deg: float) -> Tuple[float, float]:
    """绕原点转一个偏移量，坐标系 y 向下（位图与 Pillow 都是这样）。

    **正角＝脚偏向右边**，和 macOS 版一致。y 向下时这是「视觉上的逆时针」：
    钟面指向 6 点的指针顺时针是往左走的，所以脚要往右就得逆时针——
    正好是 Pillow `Image.rotate(正数)` 的方向，渲染时直接传角度即可。
    macOS 版曾经在这里把符号写反，屏幕上成了「脚朝着移动方向甩出去」，
    所以这份实现有 `feet_offset_at` 与配套测试盯着。
    """
    rad = angle_deg * math.pi / 180.0
    c, s = math.cos(rad), math.sin(rad)
    return (dx * c + dy * s, -dx * s + dy * c)


def feet_offset_at(angle_deg: float, length: float = 100.0) -> float:
    """抓手点下方 length 点处（脚）转过之后偏离中线多少，正数＝偏右。"""
    return rotate_point(0.0, length, angle_deg)[0]


def _rect_bounds(rect: Tuple[float, float, float, float]):
    x, y, w, h = rect
    return (x, y, x + w, y + h)


def _union(a, b):
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _rotated_bounds(rect, pivot, angle_rad):
    """矩形绕一点旋转后的外接矩形。"""
    x, y, w, h = rect
    px, py = pivot
    deg = angle_rad * 180.0 / math.pi
    xs, ys = [], []
    for cx, cy in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)):
        ox, oy = rotate_point(cx - px, cy - py, deg)
        xs.append(px + ox)
        ys.append(py + oy)
    return (min(xs), min(ys), max(xs), max(ys))
