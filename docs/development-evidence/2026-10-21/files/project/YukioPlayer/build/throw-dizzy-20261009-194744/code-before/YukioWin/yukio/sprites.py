"""帧库：横向图条 → 一帧一张的 RGBA 位图，用 Pillow 解码。

源码图条在要显示时才解码并受内存预算约束；打包版优先读取构建期生成的
无损小页，只缓存当前几页。round_12 的 2x 图集展开后接近 1 GB，不能在启动时全读。
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from typing import Dict, List, Optional, Tuple

from PIL import Image

from .catalog import AnimationCatalog, AnimationSpec, HELD_ID
from .events import PetState

#: 同时留在内存里的动画段数。新版 2x 图集每段可达 140 MB，另加总预算避免四段全是大图时爆内存。
KEEP_DECODED = 4
KEEP_DECODED_BYTES = 128 * 1024 * 1024
KEEP_PAGE_BYTES = 64 * 1024 * 1024
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
        self._decoded: Dict[str, Image.Image] = {}
        self._eye_sheets: Dict[str, Image.Image] = {}
        self._decoded_bytes: Dict[str, int] = {}
        self._eye_bytes: Dict[str, int] = {}
        self._body_estimates: Dict[str, int] = {}
        self._eye_estimates: Dict[str, int] = {}
        self._recent: List[str] = []
        self._page_cache: Dict[str, Image.Image] = {}
        self._page_bytes: Dict[str, int] = {}
        self._page_recent: List[str] = []
        self._head_tops: Dict[str, float] = {}
        self._head_top_inset: Optional[float] = None
        self._hang_length: Optional[float] = None
        self._paged_states = self._load_page_manifest()
        # 启动时只读图集头与尺寸，不把 12 套 2x WebP 全部解码成 RGBA。
        # 真正显示某一段时才解码；否则新版素材启动峰值会超过 1 GB。
        for spec in catalog.specs.values():
            paged = self._paged_states.get(spec.id)
            if paged is not None:
                self._validate_paged(spec, paged)
                self._paths[spec.id] = ""
                self._counts[spec.id] = int(paged["body"]["count"])
                continue
            path = os.path.join(assets_root, *spec.asset_path.split("/"))
            width, height = self._inspect_sheet(path, spec)
            self._paths[spec.id] = path
            self._counts[spec.id] = _frame_count_size((width, height), spec)
            self._body_estimates[spec.id] = width * height * 4
            if spec.blink is not None:
                eye_path = os.path.join(assets_root, "motion", spec.blink.asset)
                eye_width, eye_height = self._inspect_eye_sheet(eye_path, spec)
                self._eye_estimates[spec.id] = eye_width * eye_height * 4

    def _load_page_manifest(self) -> dict:
        path = os.path.join(self.assets_root, "motion", "windows-pages", "manifest.json")
        if not os.path.isfile(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8-sig") as fh:
                manifest = json.load(fh)
            motion_path = os.path.join(self.assets_root, "motion", "motion.json")
            with open(motion_path, "rb") as fh:
                digest = hashlib.sha256(fh.read()).hexdigest()
            if manifest.get("version") != 1 or manifest.get("motionSha256") != digest:
                raise SpriteError("Windows 分页素材与 motion.json 版本不一致")
            return manifest.get("states") or {}
        except (OSError, ValueError, TypeError) as exc:
            raise SpriteError("Windows 分页素材清单无效（%s）" % exc)

    def _validate_paged(self, spec: AnimationSpec, paged: dict) -> None:
        try:
            body = paged["body"]
            if int(body["count"]) <= spec.max_frame_index or int(body["perPage"]) <= 0:
                raise ValueError("body count")
            for name in body["pages"]:
                width, height = image_size(os.path.join(self.assets_root, "motion", "windows-pages", name))
                if height != spec.frame_height * max(spec.pixel_scale, 1) or width <= 0:
                    raise ValueError("body page geometry")
            if spec.blink is not None:
                eyes = paged["eyes"]
                max_patch = max(index for row in spec.blink.frames for index in row)
                if int(eyes["count"]) <= max_patch or int(eyes["perPage"]) <= 0 or int(eyes["columns"]) <= 0:
                    raise ValueError("eye count")
                for name in eyes["pages"]:
                    width, height = image_size(os.path.join(self.assets_root, "motion", "windows-pages", name))
                    if width % spec.blink.width or height % spec.blink.height:
                        raise ValueError("eye page geometry")
        except (KeyError, TypeError, ValueError, OSError) as exc:
            raise SpriteError("Windows 分页素材 %s 无效（%s）" % (spec.id, exc))

    def logical_asset_size(self, relative_path: str) -> Optional[Tuple[int, int]]:
        """Original atlas geometry represented by packaged Windows pages."""
        for spec_id, paged in self._paged_states.items():
            spec = self.catalog.specs.get(spec_id)
            if spec is None:
                continue
            if relative_path == spec.asset_path:
                body = paged["body"]
                return int(body["atlasWidth"]), int(body["atlasHeight"])
            if spec.blink is not None and relative_path == "motion/" + spec.blink.asset:
                eyes = paged["eyes"]
                return int(eyes["atlasWidth"]), int(eyes["atlasHeight"])
        return None

    @property
    def head_top_inset(self) -> float:
        """Fallback head line, populated lazily without decoding every atlas at startup."""
        if self._head_top_inset is None:
            self._head_top_inset = self.head_top_inset_for("idle")
        return self._head_top_inset

    @property
    def hang_length(self) -> float:
        """Grip-to-centroid distance, measured lazily from the single-frame held image."""
        if self._hang_length is None:
            spec = self.catalog.specs.get(HELD_ID)
            if spec is None or spec.hang is None:
                self._hang_length = 1.0
            else:
                frame = self.frame(HELD_ID, 0)
                k = float(max(spec.pixel_scale, 1))
                cx, cy = _centroid(frame.image, frame.width, frame.height)
                self._hang_length = max(math.hypot(cx / k - spec.hang.grip_x,
                                                   cy / k - spec.hang.grip_y), 1.0)
        return self._hang_length

    def head_top_inset_for(self, spec_id: str) -> float:
        """这一段自己的头顶线（气泡与卡叠贴着它放）。

        站着的待机比坐着高一截，气泡要贴各自的头，不能共用一条线。
        """
        if spec_id not in self._head_tops and spec_id != HELD_ID:
            spec = self.catalog.specs.get(spec_id)
            if spec is not None:
                frame = self.frame(spec_id, 0)
                k = float(max(spec.pixel_scale, 1))
                self._head_tops[spec_id] = _first_opaque_row(frame.image) / k
                frame.image.close()
        if spec_id in self._head_tops:
            return self._head_tops[spec_id]
        if self._head_top_inset is not None:
            return self._head_top_inset
        return 0.0

    @staticmethod
    def _inspect_sheet(path: str, spec: AnimationSpec) -> Tuple[int, int]:
        """Validate atlas geometry from the image header without expanding it to RGBA."""
        try:
            width, height = image_size(path)
        except (OSError, ValueError) as exc:
            raise SpriteError("无法读取图片：%s（%s）" % (spec.asset_path, exc))
        cw, ch = _cell(spec)
        count = (width // cw) * (height // ch)
        if height % ch or width % cw or spec.max_frame_index >= count:
            raise SpriteError("图格越界：%s %d×%d" % (spec.id, width, height))
        return width, height

    @staticmethod
    def _decode_sheet(path: str, spec: AnimationSpec) -> Image.Image:
        try:
            sheet = Image.open(path)
            sheet.load()
            if sheet.mode != "RGBA":
                converted = sheet.convert("RGBA")
                sheet.close()
                sheet = converted
        except (OSError, ValueError) as exc:
            raise SpriteError("无法读取图片：%s（%s）" % (spec.asset_path, exc))
        width, height = sheet.size
        cw, ch = _cell(spec)
        count = (width // cw) * (height // ch)
        if height % ch or width % cw or spec.max_frame_index >= count:
            raise SpriteError("图格越界：%s %d×%d" % (spec.id, width, height))
        return sheet

    def frame_count(self, spec_id: str) -> int:
        return self._counts.get(spec_id, 0)

    @staticmethod
    def _decode_eye_sheet(path: str, spec: AnimationSpec) -> Image.Image:
        blink = spec.blink
        try:
            sheet = Image.open(path).convert("RGBA")
        except (OSError, ValueError) as exc:
            raise SpriteError("无法读取眨眼图集：%s（%s）" % (blink.asset, exc))
        width, height = sheet.size
        if width % blink.width or height % blink.height:
            sheet.close()
            raise SpriteError("眨眼图格尺寸错误：%s %d×%d" % (spec.id, width, height))
        count = (width // blink.width) * (height // blink.height)
        max_patch = max((patch for row in blink.frames for patch in row), default=-1)
        if max_patch >= count:
            sheet.close()
            raise SpriteError("眨眼图格越界：%s %d/%d" % (spec.id, max_patch, count))
        return sheet

    @staticmethod
    def _inspect_eye_sheet(path: str, spec: AnimationSpec) -> Tuple[int, int]:
        blink = spec.blink
        try:
            width, height = image_size(path)
        except (OSError, ValueError) as exc:
            raise SpriteError("无法读取眨眼图集：%s（%s）" % (blink.asset, exc))
        if width % blink.width or height % blink.height:
            raise SpriteError("眨眼图格尺寸错误：%s %d×%d" % (spec.id, width, height))
        count = (width // blink.width) * (height // blink.height)
        max_patch = max((patch for row in blink.frames for patch in row), default=-1)
        if max_patch >= count:
            raise SpriteError("眨眼图格越界：%s %d/%d" % (spec.id, max_patch, count))
        return width, height

    def _drop_cached(self, id: str) -> None:
        sheet = self._decoded.pop(id, None)
        if sheet is not None:
            sheet.close()
        eye_sheet = self._eye_sheets.pop(id, None)
        if eye_sheet is not None:
            eye_sheet.close()
        self._decoded_bytes.pop(id, None)
        self._eye_bytes.pop(id, None)
        self._recent = [item for item in self._recent if item != id]

    def _cache_bytes(self) -> int:
        return sum(self._decoded_bytes.values()) + sum(self._eye_bytes.values())

    def _make_room(self, incoming: int, keep: Optional[str] = None) -> None:
        while self._recent and (len(self._recent) >= KEEP_DECODED or
                                self._cache_bytes() + incoming > KEEP_DECODED_BYTES):
            victim = next((item for item in self._recent if item != keep), None)
            if victim is None:
                break
            self._drop_cached(victim)

    def _load_page(self, relative_path: str) -> Image.Image:
        page = self._page_cache.get(relative_path)
        if page is None:
            path = os.path.join(self.assets_root, "motion", "windows-pages", relative_path)
            try:
                page = Image.open(path)
                page.load()
                if page.mode != "RGBA":
                    converted = page.convert("RGBA")
                    page.close()
                    page = converted
            except (OSError, ValueError) as exc:
                raise SpriteError("Windows 分页图片无法读取：%s（%s）" % (relative_path, exc))
            incoming = page.size[0] * page.size[1] * 4
            while self._page_recent and sum(self._page_bytes.values()) + incoming > KEEP_PAGE_BYTES:
                victim = self._page_recent.pop(0)
                old = self._page_cache.pop(victim, None)
                if old is not None:
                    old.close()
                self._page_bytes.pop(victim, None)
            self._page_cache[relative_path] = page
            self._page_bytes[relative_path] = incoming
        self._page_recent = [item for item in self._page_recent if item != relative_path]
        self._page_recent.append(relative_path)
        return page

    def _paged_body_frame(self, id: str, frame_index: int, spec: AnimationSpec) -> Frame:
        body = self._paged_states[id]["body"]
        per_page = int(body["perPage"])
        page_index, local = divmod(frame_index, per_page)
        page = self._load_page(body["pages"][page_index])
        cw, ch = _cell(spec)
        left = local * cw
        return Frame(page.crop((left, 0, left + cw, ch)))

    def _paged_eye_patch(self, id: str, patch_index: int, spec: AnimationSpec) -> Image.Image:
        eyes = self._paged_states[id]["eyes"]
        per_page = int(eyes["perPage"])
        columns = int(eyes["columns"])
        page_index, local = divmod(patch_index, per_page)
        page = self._load_page(eyes["pages"][page_index])
        left = (local % columns) * spec.blink.width
        top = (local // columns) * spec.blink.height
        return page.crop((left, top, left + spec.blink.width, top + spec.blink.height))

    def frame(self, spec_id: str, index: int, blink_level: int = 0) -> Frame:
        id = spec_id if spec_id in self._paths else PetState.default_work.value
        spec = self.catalog.specs.get(id)
        frame_count = self._counts.get(id, 1)
        frame_index = min(max(index, 0), frame_count - 1)
        if id in self._paged_states:
            base = self._paged_body_frame(id, frame_index, spec)
        else:
            sheet = self._decoded.get(id)
            if sheet is None:
                self._make_room(self._body_estimates.get(id, 0), keep=id)
                path = self._paths.get(id)
                try:
                    sheet = self._decode_sheet(path, spec) if path and spec else None
                except SpriteError:
                    sheet = None
                if sheet is None:
                    return _blank_frame(spec)
                self._decoded[id] = sheet
                self._decoded_bytes[id] = sheet.size[0] * sheet.size[1] * 4
            if not self._recent or self._recent[-1] != id:
                self._recent = [x for x in self._recent if x != id]
                self._recent.append(id)
                self._make_room(0, keep=id)
            cw, ch = _cell(spec)
            per_row = sheet.size[0] // cw
            left = (frame_index % per_row) * cw
            top = (frame_index // per_row) * ch
            base = Frame(sheet.crop((left, top, left + cw, top + ch)))
        blink = spec.blink if spec is not None else None
        if blink_level <= 0 or blink is None or frame_index >= len(blink.frames):
            return base
        patch_index = blink.frames[frame_index][min(int(blink_level), blink.levels) - 1]
        if id in self._paged_states:
            eye = self._paged_eye_patch(id, patch_index, spec)
        else:
            sheet = self._eye_sheets.get(id)
            if sheet is None:
                self._make_room(self._eye_estimates.get(id, 0), keep=id)
                eye_path = os.path.join(self.assets_root, "motion", blink.asset)
                try:
                    sheet = self._decode_eye_sheet(eye_path, spec)
                except SpriteError:
                    return base
                self._eye_sheets[id] = sheet
                self._eye_bytes[id] = sheet.size[0] * sheet.size[1] * 4
            columns = sheet.size[0] // blink.width
            eye_left = (patch_index % columns) * blink.width
            eye_top = (patch_index // columns) * blink.height
            eye = sheet.crop((eye_left, eye_top, eye_left + blink.width, eye_top + blink.height))
        image = base.image.copy()
        base.image.close()
        # No mask: copy RGBA bytes into the ROI so transparent pixels erase the
        # old iris exactly like CoreGraphics' .copy blend mode on macOS.
        image.paste(eye, (blink.x, blink.y))
        eye.close()
        return Frame(image)

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


def _cell(spec: AnimationSpec) -> Tuple[int, int]:
    """图条里一格的像素尺寸：帧的点尺寸 × pixel_scale。"""
    k = max(spec.pixel_scale, 1)
    return (spec.frame_width * k, spec.frame_height * k)


def _frame_count_size(size: Tuple[int, int], spec: AnimationSpec) -> int:
    """Header-only variant of _frame_count used during lazy startup."""
    cw, ch = _cell(spec)
    per_row, rows = size[0] // cw, size[1] // ch
    return min(per_row * rows, spec.max_frame_index + 1) if rows > 1 else per_row * rows


def image_size(path: str) -> Tuple[int, int]:
    """Read PNG/GIF/WebP dimensions without asking Pillow to decode a huge atlas.

    Pillow's WebP plugin expands the whole image even when callers only inspect
    ``.size``. The round_12 atlases total nearly 1 GB as RGBA, so startup and
    ``--check`` use these container headers instead.
    """
    with open(path, "rb") as fh:
        data = fh.read(32)
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 10:
        return int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little")
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP" and len(data) >= 30:
        chunk = data[12:16]
        if chunk == b"VP8X":
            return (1 + int.from_bytes(data[24:27], "little"),
                    1 + int.from_bytes(data[27:30], "little"))
        if chunk == b"VP8 " and data[23:26] == b"\x9d\x01\x2a":
            return (int.from_bytes(data[26:28], "little") & 0x3FFF,
                    int.from_bytes(data[28:30], "little") & 0x3FFF)
        if chunk == b"VP8L" and data[20] == 0x2F:
            bits = int.from_bytes(data[21:25], "little")
            return (1 + (bits & 0x3FFF), 1 + ((bits >> 14) & 0x3FFF))
    # Small legacy formats are rare here; retain a safe generic fallback.
    with Image.open(path) as image:
        return image.size


def _centroid(image: Image.Image, frame_width: int, frame_height: Optional[int] = None,
              threshold: int = OPAQUE_THRESHOLD) -> Tuple[float, float]:
    """图条第一帧里不透明像素的重心（帧内像素，左上原点）。"""
    frame = image.crop((0, 0, min(frame_width, image.size[0]), min(frame_height or image.size[1], image.size[1])))
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


def _first_opaque_row(image: Image.Image, frame_height: Optional[int] = None,
                      threshold: int = OPAQUE_THRESHOLD) -> int:
    """各帧最高点的最小值（帧内像素行号）。图条排成几行时逐行带算，取最小。"""
    alpha = image.getchannel("A").point(lambda v: 255 if v > threshold else 0)
    fh = max(frame_height or image.size[1], 1)
    best = fh
    for band in range(0, image.size[1], fh):
        bbox = alpha.crop((0, band, image.size[0], min(band + fh, image.size[1]))).getbbox()
        if bbox:
            best = min(best, bbox[1])
    return best


def _blank_frame(spec: Optional[AnimationSpec]) -> Frame:
    w = spec.frame_width if spec else 192
    h = spec.frame_height if spec else 208
    return Frame(Image.new("RGBA", (w, h), (0, 0, 0, 0)))


def load_library(assets_root: str) -> Tuple[AnimationCatalog, SpriteLibrary]:
    catalog = AnimationCatalog.load(assets_root)
    return catalog, SpriteLibrary(catalog, assets_root)
