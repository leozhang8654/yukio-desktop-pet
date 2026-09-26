"""举牌时立在她身边的那张问题卡：把 AskUserQuestion 的问题原样抄下来，
选项一行一个可以直接点，下面留一个输入框自己写一句。

外观沿用头顶气泡那套（`bubble.py` 里的圆角、描边、墨色），只是宽一些——
气泡 180 点只够放一行状态，问题要读得下去，所以这张 280 点、正文会折行。
用 Pillow 画成一张 RGBA 图交给分层窗口显示；真正收键盘输入的是一个系统输入框
（见 `win32.TextInput`），摆在这里画出来的那个框上。

移植自 YukioPlayer/Sources/YukioPlayer/QuestionCard.swift，尺寸与排版一致。
"""

from __future__ import annotations

from typing import List, NamedTuple, Optional, Sequence, Tuple

from PIL import Image, ImageDraw

from .bubble import (ACCENT, INK, MUTED, PAPER, RADIUS, _line_height, _single_line,
                     _text_width, load_font)
from .events import PetQuestion, QuestionOption
from .l10n import tr

WIDTH = 280.0
#: 问题正文最多显示几行，再长就截断（完整的那份在聊天里）。
MAX_QUESTION_LINES = 6
#: 最多列几个选项，多出来的折进那行提示。
MAX_OPTIONS = 6

PAD_X = 10.0
PAD_Y = 7.0
GAP = 6.0
OPTION_GAP = 3.0
OPTION_PAD_X = 6.0
OPTION_PAD_Y = 4.0
NUMBER_WIDTH = 16.0
INPUT_HEIGHT = 24.0
SEND_WIDTH = 30.0
CLOSE_BOX = 15.0
OPEN_CHAT_WIDTH = 78.0

HEADER_SIZE = 10.0
QUESTION_SIZE = 12.5
OPTION_SIZE = 11.5
DETAIL_SIZE = 10.0
HINT_SIZE = 10.0


class Hit(NamedTuple):
    """点在了这张卡的什么地方。"""

    #: "option" 直接答这个选项、"input" 写自己的话、"send" 送出、"open_chat" 跳回聊天、"close" 收起。
    kind: str
    #: 第几个选项（其余是 -1）。
    index: int = -1


def _on_paper(rgb, k: float):
    """半透明的填充色会在卡片上打个洞——Pillow 是直接写像素、不做合成的，
    所以先把颜色按比例和纸色混好，再用不透明的那份画。
    """
    base = PAPER[:3]
    return tuple(int(round(b + (c - b) * k)) for b, c in zip(base, rgb)) + (PAPER[3],)


def _wrap(draw, text: str, font, max_px: float, max_lines: int) -> List[str]:
    """折行：西文按词断，中文逐字断；超过 max_lines 行就截断，末尾补省略号。"""
    text = _single_line(text)
    if max_px <= 0 or not text:
        return []
    lines: List[str] = []
    line = ""
    # 断点：空格之后，或中日韩字之间。
    for ch in text:
        candidate = line + ch
        if _text_width(draw, candidate, font) <= max_px or not line:
            line = candidate
            continue
        # 这一行满了：西文尽量在最后一个空格处断，别把单词劈开。
        cut = line.rfind(" ")
        if cut > 0 and ch != " " and line[cut + 1:].isascii():
            lines.append(line[:cut])
            line = line[cut + 1:] + ch
        else:
            lines.append(line)
            line = ch
        if len(lines) == max_lines:
            break
    if len(lines) < max_lines and line:
        lines.append(line)
    if not lines:
        return []
    # 还有没放下的内容：最后一行补省略号。
    used = sum(len(l) for l in lines)
    if used < len(text.replace(" ", "")) and len(lines) == max_lines:
        last = lines[-1]
        while last and _text_width(draw, last + "…", font) > max_px:
            last = last[:-1]
        lines[-1] = last + "…"
    return [l.strip() for l in lines]


def _fit_one(draw, text: str, font, max_px: float) -> str:
    """一行以内：放不下就截断加省略号。"""
    text = _single_line(text)
    if max_px <= 0 or not text:
        return ""
    if _text_width(draw, text, font) <= max_px:
        return text
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _text_width(draw, text[:mid] + "…", font) <= max_px:
            lo = mid
        else:
            hi = mid - 1
    return (text[:lo] + "…") if lo else "…"


class QuestionCardLayout:
    """这张卡的排版与绘制，与窗口无关（--question 快照也用它）。

    scale：一个点等于多少像素（雪绪的缩放 × 屏幕缩放）。
    矩形都是左上原点的像素坐标，和分层窗口一致。
    """

    def __init__(self, question: PetQuestion, picked: Optional[Sequence[int]] = None,
                 can_open_chat: bool = True, sent_notice: Optional[str] = None,
                 typed: str = "", scale: float = 1.0):
        self.scale = max(0.5, float(scale))
        self.question = question
        self.picked = set(picked or ())
        self.can_open_chat = bool(can_open_chat)
        self.sent_notice = sent_notice
        #: 输入框里已经写下的字（真正的输入框盖在上面时不用画，快照要）。
        self.typed = typed
        s = self.scale

        self._header_font = load_font(HEADER_SIZE * s)
        self._question_font = load_font(QUESTION_SIZE * s)
        self._option_font = load_font(OPTION_SIZE * s)
        self._detail_font = load_font(DETAIL_SIZE * s)
        self._hint_font = load_font(HINT_SIZE * s)
        probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))

        width = WIDTH * s
        inner_w = width - 2 * PAD_X * s
        self.header = _single_line(question.header) if question.header else None
        # 没有小标题时问题正文从最上面一行开始，右上角的 ✕ 压在那儿：正文整体让出这一格宽。
        self._question_w = inner_w - ((CLOSE_BOX + 4) * s if self.header is None else 0)
        self._question_lines = _wrap(probe, question.text, self._question_font,
                                     self._question_w, MAX_QUESTION_LINES)
        self.options: List[QuestionOption] = list(question.options[:MAX_OPTIONS])
        self.hidden_options = len(question.options) - len(self.options)

        y = PAD_Y * s
        if self.header is not None:
            self._header_rect = (PAD_X * s, y, inner_w - CLOSE_BOX * s, _line_height(self._header_font))
            y += _line_height(self._header_font) + 1 * s
        else:
            self._header_rect = None
        question_h = len(self._question_lines) * _line_height(self._question_font)
        self._question_rect = (PAD_X * s, y, self._question_w, question_h)
        y += question_h + GAP * s

        label_w = inner_w - NUMBER_WIDTH * s - 2 * OPTION_PAD_X * s
        self._option_rects: List[Tuple[float, float, float, float]] = []
        self._option_lines: List[Tuple[str, Optional[str]]] = []
        for option in self.options:
            label = _fit_one(probe, option.label, self._option_font, label_w)
            detail = _fit_one(probe, option.detail, self._detail_font, label_w) if option.detail else None
            h = 2 * OPTION_PAD_Y * s + _line_height(self._option_font)
            if detail:
                h += _line_height(self._detail_font) - 1 * s
            self._option_rects.append((PAD_X * s, y, inner_w, h))
            self._option_lines.append((label, detail))
            y += h + OPTION_GAP * s
        if self.options:
            y += GAP * s - OPTION_GAP * s

        if sent_notice is None:
            self._input_rect = (PAD_X * s, y, inner_w - SEND_WIDTH * s - 4 * s, INPUT_HEIGHT * s)
            self._send_rect = (width - PAD_X * s - SEND_WIDTH * s, y, SEND_WIDTH * s, INPUT_HEIGHT * s)
            self._notice_rect = None
            y += INPUT_HEIGHT * s + GAP * s
        else:
            self._input_rect = None
            self._send_rect = None
            self._notice_rect = (PAD_X * s, y, inner_w, _line_height(self._option_font))
            y += _line_height(self._option_font) + GAP * s

        hint_h = _line_height(self._hint_font)
        self._hint_rect = (PAD_X * s, y, inner_w, hint_h)
        self._open_chat_rect = ((width - PAD_X * s - OPEN_CHAT_WIDTH * s, y, OPEN_CHAT_WIDTH * s, hint_h)
                                if self.can_open_chat else None)
        y += hint_h + PAD_Y * s

        self.size_px = (int(round(width)), int(round(y)))
        self.size_pt = (self.size_px[0] / s, self.size_px[1] / s)
        self._close_rect = (width - (CLOSE_BOX + 2) * s, 2 * s, CLOSE_BOX * s, CLOSE_BOX * s)

    # MARK: 命中

    @staticmethod
    def _inside(rect, x: float, y: float) -> bool:
        if rect is None:
            return False
        rx, ry, rw, rh = rect
        return rx <= x <= rx + rw and ry <= y <= ry + rh

    def hit(self, x: float, y: float) -> Optional[Hit]:
        """窗口内坐标（左上原点，像素）上有没有可点的东西。"""
        if not (0 <= x <= self.size_px[0] and 0 <= y <= self.size_px[1]):
            return None
        if self._inside(self._close_rect, x, y):
            return Hit("close")
        for i, rect in enumerate(self._option_rects):
            if self._inside(rect, x, y):
                return Hit("option", i)
        if self._inside(self._input_rect, x, y):
            return Hit("input")
        if self._inside(self._send_rect, x, y):
            return Hit("send")
        if self._inside(self._open_chat_rect, x, y):
            return Hit("open_chat")
        return None

    @property
    def input_rect(self) -> Optional[Tuple[int, int, int, int]]:
        """输入框在卡片里的位置（像素，左上原点）：真正的系统输入框摆到这儿。"""
        if self._input_rect is None:
            return None
        x, y, w, h = self._input_rect
        return (int(round(x + 2)), int(round(y + 2)), int(round(w - 4)), int(round(h - 4)))

    # MARK: 绘制

    def render(self) -> Image.Image:
        s = self.scale
        w, h = self.size_px
        image = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        line_w = max(1, int(round(s)))
        draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=(RADIUS + 1) * s, fill=PAPER,
                               outline=INK + (41,), width=line_w)

        if self.header is not None and self._header_rect:
            x, y, rw, _ = self._header_rect
            draw.text((x, y), _fit_one(draw, self.header, self._header_font, rw),
                      font=self._header_font, fill=MUTED + (255,))
        self._draw_close(draw)

        x, y, _, _ = self._question_rect
        lh = _line_height(self._question_font)
        for i, line in enumerate(self._question_lines):
            draw.text((x, y + i * lh), line, font=self._question_font, fill=INK + (255,))

        for i, rect in enumerate(self._option_rects):
            self._draw_option(draw, i, rect)

        if self._notice_rect is not None:
            nx, ny, nw, _ = self._notice_rect
            draw.text((nx, ny), _fit_one(draw, self.sent_notice or "", self._option_font, nw),
                      font=self._option_font, fill=ACCENT + (255,))
        else:
            self._draw_input(draw)
            self._draw_send(draw)

        if self.sent_notice is not None:
            hint = tr("Check the chat", "请到聊天中确认")
        elif self.hidden_options > 0:
            hint = tr("%d more in the chat", "还有 %d 个选项在聊天里") % self.hidden_options
        elif self.question.multi_select:
            hint = tr("Pick any, press Enter", "可多选，按回车送出")
        else:
            hint = tr("Click an option, or type", "点选项，或自己写一句")
        hx, hy, hw, _ = self._hint_rect
        if self._open_chat_rect:
            hw -= OPEN_CHAT_WIDTH * s
        draw.text((hx, hy), _fit_one(draw, hint, self._hint_font, hw),
                  font=self._hint_font, fill=MUTED + (255,))
        if self._open_chat_rect:
            ox, oy, _, _ = self._open_chat_rect
            draw.text((ox, oy), tr("Open the chat >", "打开聊天 >"), font=self._hint_font,
                      fill=ACCENT + (255,))
        return image

    def _draw_option(self, draw, i: int, rect) -> None:
        s = self.scale
        x, y, w, h = rect
        on = i in self.picked
        draw.rounded_rectangle((x, y, x + w - 1, y + h - 1), radius=5 * s,
                               fill=_on_paper(ACCENT, 0.14) if on else _on_paper(INK, 0.05),
                               outline=_on_paper(ACCENT, 0.55) if on else _on_paper(INK, 0.12),
                               width=max(1, int(round(s))))
        label, detail = self._option_lines[i]
        lh = _line_height(self._option_font)
        top = y + OPTION_PAD_Y * s
        # 记号用「√」不用「✓」：Windows 的中文字体里前者一定有，后者会变成豆腐块。
        number = "√" if on else str(i + 1)
        nh = _line_height(self._hint_font)
        draw.text((x + OPTION_PAD_X * s, top + (lh - nh) / 2), number, font=self._hint_font,
                  fill=(ACCENT if on else MUTED) + (255,))
        tx = x + OPTION_PAD_X * s + NUMBER_WIDTH * s
        draw.text((tx, top), label, font=self._option_font, fill=INK + (255,))
        if detail:
            draw.text((tx, top + lh - 1 * s), detail, font=self._detail_font, fill=MUTED + (255,))

    def _draw_input(self, draw) -> None:
        s = self.scale
        x, y, w, h = self._input_rect
        draw.rounded_rectangle((x, y, x + w - 1, y + h - 1), radius=5 * s,
                               fill=(255, 255, 255, PAPER[3]), outline=_on_paper(INK, 0.20),
                               width=max(1, int(round(s))))
        if self.typed:
            text = _fit_one(draw, self.typed, self._option_font, w - 10 * s)
            lh = _line_height(self._option_font)
            draw.text((x + 5 * s, y + (h - lh) / 2), text, font=self._option_font, fill=INK + (255,))

    def _draw_send(self, draw) -> None:
        s = self.scale
        x, y, w, h = self._send_rect
        draw.rounded_rectangle((x, y, x + w - 1, y + h - 1), radius=5 * s, fill=ACCENT + (255,))
        # 箭头而不是 ⏎：中文字体里有箭头，回车符号多半没有。
        glyph = "→"
        lh = _line_height(self._hint_font)
        gw = _text_width(draw, glyph, self._hint_font)
        draw.text((x + (w - gw) / 2, y + (h - lh) / 2), glyph, font=self._hint_font,
                  fill=(255, 255, 255, 255))

    def _draw_close(self, draw) -> None:
        s = self.scale
        x, y, w, h = self._close_rect
        inset = 5 * s
        color = _on_paper(MUTED, 0.75)
        width = max(1, int(round(1.2 * s)))
        draw.line((x + inset, y + inset, x + w - inset, y + h - inset), fill=color, width=width)
        draw.line((x + inset, y + h - inset, x + w - inset, y + inset), fill=color, width=width)

    # MARK: 摆在哪儿

    @staticmethod
    def origin(size_pt: Tuple[float, float], pet_rect: Tuple[float, float, float, float],
               work_area_pt: Tuple[float, float, float, float]) -> Tuple[float, float]:
        """卡片左上角（屏幕坐标，点，y 向下）：立在她身旁，右边放不下就换到左边。

        pet_rect：(x, y, 宽, 高)；work_area_pt：(左, 上, 右, 下)。
        """
        px, py, pw, ph = pet_rect
        left, top, right, bottom = work_area_pt
        gap = 8.0
        cw, ch = size_pt
        x = px + pw + gap
        if x + cw > right - 4:
            x = px - gap - cw
        x = min(max(x, left + 4), max(left + 4, right - cw - 4))
        # 上边大致与她的肩同高：卡片不高时贴着上半身，很高时往上挪，别顶出屏幕。
        y = py + ph * 0.25 - ch * 0.25
        y = min(max(y, top + 4), max(top + 4, bottom - ch - 4))
        return (round(x), round(y))


def probe_points(layout: QuestionCardLayout) -> List[Tuple[str, Tuple[float, float]]]:
    """自查用：几个代表点（每个选项、输入框、送出、打开聊天、✕、空白处）。"""
    out: List[Tuple[str, Tuple[float, float]]] = []

    def center(rect):
        x, y, w, h = rect
        return (x + w / 2, y + h / 2)

    for i, rect in enumerate(layout._option_rects):
        out.append(("选项%d" % (i + 1), center(rect)))
    if layout._input_rect:
        out.append(("输入框", center(layout._input_rect)))
    if layout._send_rect:
        out.append(("送出", center(layout._send_rect)))
    if layout._open_chat_rect:
        out.append(("打开聊天", center(layout._open_chat_rect)))
    out.append(("✕", center(layout._close_rect)))
    out.append(("问题正文（不可点）", center(layout._question_rect)))
    return out
