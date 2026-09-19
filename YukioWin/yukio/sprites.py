"""帧库：横向图条 → 一帧一张的 RGBA 位图，用 Pillow 解码。

图条在要显示时才解码，最近用过的 4 段留在内存里，其余只记帧数和位置：
动作图条帧数多（写字那条 63 帧、12096×208），全部预先解码要一两百 MB。
"""

from __future__ import annotations

import math
import os
from typing import Dict, List, Optional, Tuple

from PIL import Image

from .catalog import AnimationCatalog, AnimationSpec, HELD_ID
from .events import PetState

#: 同时留在内存里的动画段数。
KEEP_DECODED = 4
#: alpha 高于这个值才算不透明（用于量头顶线和命中测试）。
OPAQUE_THRESHOLD = 24


class SpriteError(Exception):
    pass


class Frame:
    __slots__ = ("image", "width", "height")

    def __init__(self, image: Image.Image):
        self.image = image
        self.width, self.height = image.size

    def is_opaque(self, x: int, y: int, threshold: int = OPAQUE_THRESHOLD) -> bool:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        return self.image.getpixel((x, y))[3] > threshold


class SpriteLibrary:
    def __init__(self, catalog: AnimationCatalog, assets_root: str):
        self.catalog = catalog
        self.assets_root = assets_root
        self._paths: Dict[str, str] = {}
        self._counts: Dict[str, int] = {}
        self._decoded: Dict[str, List[Frame]] = {}
        self._recent: List[str] = []
        head_top = None
        self._head_tops: Dict[str, float] = {}
        hang_length = 0.0
        # 启动时逐段解码一次：检查尺寸与帧索引、量出头顶线与重心，然后丢掉，只记帧数和位置。
        for spec in catalog.specs.values():
            path = os.path.join(assets_root, *spec.asset_path.split("/"))
            sheet = self._decode_sheet(path, spec)
            self._paths[spec.id] = path
            self._counts[spec.id] = sheet.size[0] // spec.frame_width
            if spec.id == HELD_ID and spec.hang is not None:
                # 重心按不透明像素取平均：图换了（重画、改姿势）摆长自己跟着变，不用手填数字。
                cx, cy = _centroid(sheet, spec.frame_width)
                hang_length = max(math.hypot(cx - spec.hang.grip_x, cy - spec.hang.grip_y), 1.0)
            else:
                top = _first_opaque_row(sheet)
                self._head_tops[spec.id] = float(top)
                head_top = top if head_top is None else min(head_top, top)
            sheet.close()
        #: 各状态动作里人物最高点距帧顶的像素数（取最小）。没量到那一段时退回它。
        #: 不含「被拎起来」：那一帧领口的尖比头还高，算进来会把平时的气泡整体顶上去。
        self.head_top_inset = float(head_top or 0)
        #: 「被拎起来」那一帧里，抓手点到人物重心的距离（像素）。摆动就是绕抓手点吊着这段长度。
        self.hang_length = hang_length

    def head_top_inset_for(self, spec_id: str) -> float:
        """这一段自己的头顶线（气泡与卡叠贴着它放）。

        站着的待机比坐着高一截，气泡要贴各自的头，不能共用一条线。
        """
        return self._head_tops.get(spec_id, self.head_top_inset)

    @staticmethod
    def _decode_sheet(path: str, spec: AnimationSpec) -> Image.Image:
        try:
            sheet = Image.open(path)
            sheet = sheet.convert("RGBA")
        except (OSError, ValueError) as exc:
            raise SpriteError("无法读取图片：%s（%s）" % (spec.asset_path, exc))
        width, height = sheet.size
        count = width // spec.frame_width
        if height != spec.frame_height or spec.max_frame_index >= count:
            raise SpriteError("图格越界：%s %d×%d" % (spec.id, width, height))
        return sheet

    def frame_count(self, spec_id: str) -> int:
        return self._counts.get(spec_id, 0)

    def frame(self, spec_id: str, index: int) -> Frame:
        id = spec_id if spec_id in self._paths else PetState.default_work.value
        frames = self._decoded.get(id)
        if frames is None:
            frames = self._decode_frames(id)
            if not frames:
                frames = [_blank_frame(self.catalog.specs.get(id))]
            self._decoded[id] = frames
        if not self._recent or self._recent[-1] != id:
            self._recent = [x for x in self._recent if x != id]
            self._recent.append(id)
            while len(self._recent) > KEEP_DECODED:
                self._decoded.pop(self._recent.pop(0), None)
        return frames[min(max(index, 0), len(frames) - 1)]

    def _decode_frames(self, id: str) -> List[Frame]:
        spec = self.catalog.specs.get(id)
        path = self._paths.get(id)
        if not spec or not path:
            return []
        try:
            sheet = self._decode_sheet(path, spec)
        except SpriteError:
            return []
        out = []
        for i in range(sheet.size[0] // spec.frame_width):
            box = (i * spec.frame_width, 0, (i + 1) * spec.frame_width, spec.frame_height)
            out.append(Frame(sheet.crop(box)))
        sheet.close()
        return out

    def avatar_image(self, size: int = 32) -> Optional[Image.Image]:
        """托盘小头像：取待机第一帧不透明区域顶部的正方形（头部）。"""
        f = self.frame("idle", 0)
        alpha = f.image.getchannel("A")
        bbox = alpha.point(lambda v: 255 if v > OPAQUE_THRESHOLD else 0).getbbox()
        if not bbox:
            return None
        min_x, min_y, max_x, _ = bbox
        side = int((max_x - min_x) * 0.75)
        if side <= 0:
            return None
        x = max(0, min(f.width - side, (min_x + max_x) // 2 - side // 2))
        head = f.image.crop((x, min_y, x + side, min(min_y + side, f.height)))
        return head.resize((size, size), Image.LANCZOS)


def _centroid(image: Image.Image, frame_width: int,
              threshold: int = OPAQUE_THRESHOLD) -> Tuple[float, float]:
    """图条第一帧里不透明像素的重心（帧内像素，左上原点）。"""
    frame = image.crop((0, 0, min(frame_width, image.size[0]), image.size[1]))
    alpha = frame.getchannel("A").point(lambda v: 255 if v > threshold else 0)
    w, h = alpha.size
    data = alpha.tobytes()
    sum_x = sum_y = count = 0
    for y in range(h):
        row = data[y * w:(y + 1) * w]
        for x in range(w):
            if row[x]:
                sum_x += x
                sum_y += y
                count += 1
    if not count:
        return (frame_width / 2.0, image.size[1] / 2.0)
    return (sum_x / count, sum_y / count)


def _first_opaque_row(image: Image.Image, threshold: int = OPAQUE_THRESHOLD) -> int:
    """整条图条里第一行有不透明像素的行号（= 各帧最高点的最小值）。"""
    alpha = image.getchannel("A")
    bbox = alpha.point(lambda v: 255 if v > threshold else 0).getbbox()
    return bbox[1] if bbox else image.size[1]


def _blank_frame(spec: Optional[AnimationSpec]) -> Frame:
    w = spec.frame_width if spec else 192
    h = spec.frame_height if spec else 208
    return Frame(Image.new("RGBA", (w, h), (0, 0, 0, 0)))


def load_library(assets_root: str) -> Tuple[AnimationCatalog, SpriteLibrary]:
    catalog = AnimationCatalog.load(assets_root)
    return catalog, SpriteLibrary(catalog, assets_root)
