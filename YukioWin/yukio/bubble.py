"""头顶小气泡：上行大任务（标题），下行当前任务或活动；有清单时右侧显示进度，底部一条细进度条。

用 Pillow 画成一张 RGBA 图，交给分层窗口显示（Windows）或直接存成 PNG（快照检查）。
排版尺寸与 macOS 版一致（点为单位），按 scale 放大成实际像素，所以高分屏上是清晰的。
"""

from __future__ import annotations

import os
import sys
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from .router import Progress, StatusLine

MAX_WIDTH = 180.0
MIN_WIDTH = 64.0
PAD_X = 8.0
PAD_Y = 5.0
LINE_GAP = 1.0
BAR_HEIGHT = 2.5
BAR_GAP = 4.0
PROGRESS_GAP = 6.0
RADIUS = 7.0

TITLE_SIZE = 10.0
CURRENT_SIZE = 11.5
PROGRESS_SIZE = 10.0

#: 制服的深蓝与眼睛的蓝。
INK = (31, 41, 69)
MUTED = (97, 112, 143)
ACCENT = (61, 148, 230)
PAPER = (255, 255, 255, 240)

#: 按顺序找一个带中文字形的字体；找不到就退回 Pillow 自带位图字体（只有西文）。
FONT_CANDIDATES = {
    "nt": [
        ("C:/Windows/Fonts/msyh.ttc", 0), ("C:/Windows/Fonts/msyh.ttf", 0),
        ("C:/Windows/Fonts/msyhl.ttc", 0), ("C:/Windows/Fonts/simhei.ttf", 0),
        ("C:/Windows/Fonts/simsun.ttc", 0), ("C:/Windows/Fonts/Deng.ttf", 0),
        ("C:/Windows/Fonts/segoeui.ttf", 0),
    ],
    "posix": [
        ("/System/Library/Fonts/PingFang.ttc", 1), ("/System/Library/Fonts/PingFang.ttc", 0),
        ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0),
        ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 0),
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 0),
    ],
}

_font_cache = {}


def font_file() -> Optional[Tuple[str, int]]:
    override = os.environ.get("YUKIO_FONT")
    if override and os.path.exists(override):
        return (override, 0)
    for path, index in FONT_CANDIDATES.get("nt" if os.name == "nt" else "posix", []):
        if os.path.exists(path):
            return (path, index)
    return None


def load_font(size_px: float):
    key = int(round(size_px * 4))
    cached = _font_cache.get(key)
    if cached is not None:
        return cached
    chosen = font_file()
    font = None
    if chosen:
        try:
            font = ImageFont.truetype(chosen[0], int(round(size_px)), index=chosen[1])
        except OSError:
            font = None
    if font is None:
        font = ImageFont.load_default()
    _font_cache[key] = font
    return font


def _text_width(draw: ImageDraw.ImageDraw, text: str, font) -> float:
    if not text:
        return 0.0
    try:
        return float(draw.textlength(text, font=font))
    except AttributeError:  # 极老的 Pillow
        return float(font.getsize(text)[0])


def _line_height(font) -> float:
    """用含中文的样本量行高：中文字形比西文的上下伸部高。"""
    try:
        box = font.getbbox("雪绪Ag")
        return float(box[3] - box[1]) + 2.0
    except Exception:
        return float(getattr(font, "size", 12)) * 1.4


def _fit(draw, text: str, font, max_px: float) -> str:
    """放不下时截断并加省略号。"""
    if max_px <= 0 or not text:
        return ""
    if _text_width(draw, text, font) <= max_px:
        return text
    ellipsis = "…"
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _text_width(draw, text[:mid] + ellipsis, font) <= max_px:
            lo = mid
        else:
            hi = mid - 1
    return (text[:lo] + ellipsis) if lo else ellipsis


def _single_line(text: str) -> str:
    return " ".join(text.splitlines())


class BubbleLayout:
    """一条气泡的排版与绘制。scale：一个点等于多少像素（雪绪的缩放 × 屏幕缩放）。"""

    def __init__(self, line: StatusLine, scale: float = 1.0):
        self.scale = max(0.5, float(scale))
        self.title = _single_line(line.title) if line.title else None
        self.current = _single_line(line.current)
        self.progress: Optional[Progress] = line.progress

        s = self.scale
        self._title_font = load_font(TITLE_SIZE * s)
        self._current_font = load_font(CURRENT_SIZE * s)
        self._progress_font = load_font(PROGRESS_SIZE * s)
        probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))

        self._progress_text = "%d/%d" % (self.progress.done, self.progress.total) if self.progress else ""
        self._progress_w = _text_width(probe, self._progress_text, self._progress_font) if self.progress else 0.0
        title_w = (_text_width(probe, self.title, self._title_font) + 1) if self.title else 0.0
        current_w = _text_width(probe, self.current, self._current_font) + 1
        if self.progress:
            current_w += PROGRESS_GAP * s + self._progress_w
        width = min(MAX_WIDTH * s, max(MIN_WIDTH * s, max(title_w, current_w) + 2 * PAD_X * s))
        height = 2 * PAD_Y * s + _line_height(self._current_font)
        if self.title:
            height += _line_height(self._title_font) + LINE_GAP * s
        if self.progress:
            height += (BAR_GAP + BAR_HEIGHT) * s
        #: 像素尺寸（实际画多大）与点尺寸（摆位置用）。
        self.size_px = (int(round(width)), int(round(height)))
        self.size_pt = (self.size_px[0] / s, self.size_px[1] / s)

    def render(self) -> Image.Image:
        s = self.scale
        w, h = self.size_px
        image = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        radius = RADIUS * s
        draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=PAPER,
                               outline=INK + (41,), width=max(1, int(round(s))))

        x = PAD_X * s
        inner_w = w - 2 * PAD_X * s
        top = PAD_Y * s
        if self.title:
            lh = _line_height(self._title_font)
            draw.text((x, top), _fit(draw, self.title, self._title_font, inner_w),
                      font=self._title_font, fill=MUTED + (255,))
            top += lh + LINE_GAP * s
        lh = _line_height(self._current_font)
        text_w = inner_w
        if self.progress:
            ph = _line_height(self._progress_font)
            draw.text((w - PAD_X * s - self._progress_w, top + (lh - ph) / 2), self._progress_text,
                      font=self._progress_font, fill=MUTED + (255,))
            text_w -= self._progress_w + PROGRESS_GAP * s
        draw.text((x, top), _fit(draw, self.current, self._current_font, text_w),
                  font=self._current_font, fill=INK + (255,))
        if self.progress and self.progress.total > 0:
            top += lh + BAR_GAP * s
            bar_h = max(2.0, BAR_HEIGHT * s)
            r = bar_h / 2
            draw.rounded_rectangle((x, top, x + inner_w, top + bar_h), radius=r, fill=INK + (26,))
            done = inner_w * min(self.progress.done, self.progress.total) / self.progress.total
            if done > 0:
                draw.rounded_rectangle((x, top, x + max(done, bar_h), top + bar_h), radius=r, fill=ACCENT + (255,))
        return image

    @staticmethod
    def origin(size_pt: Tuple[float, float], pet_rect: Tuple[float, float, float, float],
               head_top: float) -> Tuple[float, float]:
        """气泡左上角（屏幕坐标，y 向下）：水平居中于雪绪，底边贴在头顶线上方。

        pet_rect：(x, y, 宽, 高)，头顶线 head_top 是人物最高点距窗口顶的点数（已乘缩放）。
        """
        x, y, w, h = pet_rect
        bx = round(x + w / 2 - size_pt[0] / 2)
        by = round(y + head_top - size_pt[1] - 3)
        return (bx, by)
