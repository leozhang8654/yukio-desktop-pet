"""头顶那摞卡片里“别的聊天”那几张：一条聊天一张，压着气泡往上叠，点一张就去那条聊天。

外观就是头顶气泡那张卡（`bubble.py` 里的那套圆角、描边、字号和两行排版），
只多了一条状态色和一个 ✕。用 Pillow 画成一张 RGBA 图交给分层窗口显示；
命中测试按卡片矩形算，卡与卡之间的缝隙不接收点击。

移植自 YukioPlayer/Sources/YukioPlayer/CardStack.swift，尺寸与排版一致。
"""

from __future__ import annotations

from typing import List, NamedTuple, Optional, Tuple

from PIL import Image, ImageDraw

from .bubble import (ACCENT, INK, MUTED, PAD_X, PAD_Y, PAPER, LINE_GAP, MAX_WIDTH, RADIUS,
                     CURRENT_SIZE, TITLE_SIZE, PROGRESS_SIZE, _fit, _line_height, _single_line,
                     _text_width, load_font)
from .cards import ActivityCard, CardStatus
from .l10n import tr

#: 和气泡同宽，叠起来是一摞齐的。
WIDTH = MAX_WIDTH
#: 叠起来时两张卡之间的缝。
STACK_GAP = 4.0
#: 收起时最多显示几张，其余折进“还有 N 条”。
COLLAPSED_COUNT = 3
STRIPE = 3.0
STRIPE_GAP = 5.0
CLOSE_BOX = 15.0
MORE_HEIGHT = 18.0

#: 左边那条状态色：橙＝等你回答，红＝出错，绿＝答完了，蓝＝在跑。
STATUS_COLOR = {
    CardStatus.waiting: (237, 158, 41),
    CardStatus.failed: (214, 79, 74),
    CardStatus.ready: (56, 173, 112),
    CardStatus.running: ACCENT,
}


def _darker(rgb, k: float = 0.75):
    return tuple(int(v * k) for v in rgb)


class Hit(NamedTuple):
    """点在了这摞卡的什么地方。"""

    #: "card" 打开那条聊天、"dismiss" 只收起这张、"expand" 展开／收起。
    kind: str
    #: 第几张卡（expand 时是 -1）。
    index: int


class CardStackLayout:
    """这摞卡的排版与绘制，与窗口无关（--cards 快照也用它）。

    scale：一个点等于多少像素（雪绪的缩放 × 屏幕缩放）。
    """

    def __init__(self, cards: List[ActivityCard], expanded: bool = False, scale: float = 1.0):
        self.scale = max(0.5, float(scale))
        self.expanded = bool(expanded)
        limit = len(cards) if expanded else min(COLLAPSED_COUNT, len(cards))
        #: 这摞里显示出来的卡（收起时是前几张）。
        self.shown: List[ActivityCard] = list(cards[:limit])
        #: 折进“还有 N 条”的张数。
        self.hidden = len(cards) - len(self.shown)

        s = self.scale
        self._title_font = load_font(TITLE_SIZE * s)
        self._current_font = load_font(CURRENT_SIZE * s)
        self._small_font = load_font(PROGRESS_SIZE * s)
        card_h = (2 * PAD_Y * s + _line_height(self._title_font) + LINE_GAP * s
                  + _line_height(self._current_font))

        #: 每张卡的矩形（左上原点，第 0 张在最下面、离气泡最近）。
        width = WIDTH * s
        rects: List[Tuple[float, float, float, float]] = []
        total = len(self.shown) * card_h + max(0, len(self.shown) - 1) * STACK_GAP * s
        if self.hidden > 0 or self.expanded:
            total += MORE_HEIGHT * s + STACK_GAP * s
        # 最要紧的那张挨着气泡（也就是最下面一张），所以从下往上排。
        y = total
        for _ in self.shown:
            y -= card_h
            rects.append((0.0, y, width, card_h))
            y -= STACK_GAP * s
        self._card_rects = rects
        self._more_rect = (0.0, 0.0, width, MORE_HEIGHT * s) if (self.hidden > 0 or self.expanded) else None

        self.size_px = (int(round(width)), int(round(max(0.0, total))))
        self.size_pt = (self.size_px[0] / s, self.size_px[1] / s)

    # MARK: 摆位与命中

    @staticmethod
    def origin(size_pt: Tuple[float, float], pet_rect: Tuple[float, float, float, float],
               bubble_top: float) -> Tuple[float, float]:
        """这摞卡的左上角（屏幕坐标，y 向下）：和气泡同一竖线上居中，压在气泡上面往上长。

        bubble_top 是气泡的上边（没有气泡时传头顶线），留一条缝接着叠。
        """
        x, y, w, h = pet_rect
        bx = round(x + w / 2 - size_pt[0] / 2)
        by = round(bubble_top - STACK_GAP - size_pt[1])
        return (bx, by)

    def hit(self, x: float, y: float) -> Optional[Hit]:
        """窗口内坐标（左上原点）上有没有可点的东西。"""
        for i, (rx, ry, rw, rh) in enumerate(self._card_rects):
            if rx <= x < rx + rw and ry <= y < ry + rh:
                cx0, cy0, cx1, cy1 = self._close_rect((rx, ry, rw, rh))
                if cx0 <= x < cx1 and cy0 <= y < cy1:
                    return Hit("dismiss", i)
                return Hit("card", i)
        if self._more_rect:
            rx, ry, rw, rh = self._more_rect
            if rx <= x < rx + rw and ry <= y < ry + rh:
                return Hit("expand", -1)
        return None

    def _close_rect(self, card):
        rx, ry, rw, rh = card
        s = self.scale
        box = CLOSE_BOX * s
        return (rx + rw - box - s, ry + s, rx + rw - s, ry + box + s)

    # MARK: 绘制

    def render(self) -> Image.Image:
        s = self.scale
        image = Image.new("RGBA", self.size_px, (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        for card, rect in zip(self.shown, self._card_rects):
            self._draw_card(draw, card, rect)
        if self._more_rect:
            rx, ry, rw, rh = self._more_rect
            pill = (rx + 30 * s, ry + s, rx + rw - 30 * s, ry + rh - s)
            draw.rounded_rectangle(pill, radius=(pill[3] - pill[1]) / 2, fill=PAPER,
                                   outline=INK + (41,), width=max(1, int(round(s))))
            text = tr("Collapse", "收起") if self.expanded else tr("%d more", "还有 %d 条") % self.hidden
            tw = _text_width(draw, text, self._title_font)
            th = _line_height(self._title_font)
            draw.text(((pill[0] + pill[2]) / 2 - tw / 2, (pill[1] + pill[3]) / 2 - th / 2),
                      text, font=self._title_font, fill=MUTED + (255,))
        return image

    def _draw_card(self, draw, card: ActivityCard, rect) -> None:
        s = self.scale
        rx, ry, rw, rh = rect
        draw.rounded_rectangle((rx, ry, rx + rw - 1, ry + rh - 1), radius=RADIUS * s, fill=PAPER,
                               outline=INK + (41,), width=max(1, int(round(s))))
        color = STATUS_COLOR.get(card.status, ACCENT)
        bar = (rx + 4 * s, ry + 5 * s, rx + 4 * s + STRIPE * s, ry + rh - 5 * s)
        draw.rounded_rectangle(bar, radius=STRIPE * s / 2, fill=color + (255,))

        x = rx + (4 + STRIPE + STRIPE_GAP) * s
        right = rx + rw - PAD_X * s
        top = ry + PAD_Y * s

        # 上行：聊天名（和气泡上行一样的淡色小字），右边让出 ✕。
        th = _line_height(self._title_font)
        draw.text((x, top), _fit(draw, _single_line(card.title), self._title_font,
                                 max(10.0, right - x - CLOSE_BOX * s)),
                  font=self._title_font, fill=MUTED + (255,))
        self._draw_close(draw, self._close_rect(rect))
        top += th + LINE_GAP * s

        # 下行：在做什么（和气泡下行一样的深色粗字），右边一个短状态标签。
        ch = _line_height(self._current_font)
        label = card.status_label
        label_w = _text_width(draw, label, self._small_font) + 1
        lh = _line_height(self._small_font)
        draw.text((right - label_w, top + (ch - lh) / 2), label,
                  font=self._small_font, fill=_darker(color) + (255,))
        draw.text((x, top), _fit(draw, _single_line(card.subtitle), self._current_font,
                                 max(10.0, right - x - label_w - 6 * s)),
                  font=self._current_font, fill=INK + (255,))

    def _draw_close(self, draw, box) -> None:
        x0, y0, x1, y1 = box
        inset = 5 * self.scale
        width = max(1, int(round(1.2 * self.scale)))
        color = MUTED + (178,)
        draw.line((x0 + inset, y0 + inset, x1 - inset, y1 - inset), fill=color, width=width)
        draw.line((x0 + inset, y1 - inset, x1 - inset, y0 + inset), fill=color, width=width)
