"""雪绪的「骨骼分层」动作引擎：一张底图拆成几层，层挂在骨骼上转动、平移，像 Live2D 那样连着动。

和 motionlib（只抠一只手套平移）的区别：
- 会动的是**整条手臂**——袖子从肩膀起、到袖口、手套、再到手里的笔／放大镜，抠成一层；
  骨骼的权重沿手臂从肩膀（0）平滑升到袖口（1），肩膀不动、袖口和手整体跟着走，袖子中段像布一样顺着弯，
  手腕不再脱离袖子漂浮。腕骨是肘骨的子骨，握着的道具跟手一起转。
- 底图挖掉这一层之后的洞，用「最近的完好像素」补（平色区域干净、不糊），再按需打补丁（横向克隆、平涂）；
- 头、眼仍用高斯权重的骨骼直接在底图上变形（幅度 1–2 点）；眨眼画在底图上，眼皮跟着头动。
- 全部在 2 倍图（384×416）上做，帧直接就是应用要播的 2 倍图条，不再经过超分。

坐标一律是 2 倍图里的像素（x 向右、y 向下）；角度正值为屏幕上的顺时针。
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Callable, Optional

import cv2
import numpy as np
from PIL import Image

W, H = 384, 416
_YY, _XX = np.mgrid[0:H, 0:W].astype(np.float32)


def set_size(w: int, h: int):
    global W, H, _YY, _XX
    W, H = w, h
    _YY, _XX = np.mgrid[0:H, 0:W].astype(np.float32)


# ---------- 图像读写（内部一律预乘 alpha 的 float32） ----------

def load_rgba(path: str) -> np.ndarray:
    a = np.asarray(Image.open(path).convert('RGBA'), dtype=np.float32) / 255.0
    if a.shape[:2] != (H, W):
        raise ValueError(f'{path}: 应是 {W}×{H}，实际 {a.shape[1]}×{a.shape[0]}')
    a = a.copy()
    a[..., :3] *= a[..., 3:4]
    return a


def to_image(p: np.ndarray) -> Image.Image:
    p = np.clip(p, 0.0, 1.0)
    out = np.zeros_like(p)
    al = p[..., 3:4]
    np.divide(p[..., :3], np.maximum(al, 1e-6), out=out[..., :3])
    out[..., :3] = np.where(al > 1e-4, out[..., :3], 0)
    out[..., 3:4] = al
    return Image.fromarray(np.round(np.clip(out, 0, 1) * 255).astype(np.uint8), 'RGBA')


def to_uint8(p: np.ndarray) -> np.ndarray:
    return np.asarray(to_image(p)).copy()


def unpremul_rgb(p: np.ndarray) -> np.ndarray:
    al = p[..., 3:4]
    return np.where(al > 1e-4, p[..., :3] / np.maximum(al, 1e-6), 0)


def on_white(p: np.ndarray) -> Image.Image:
    im = Image.new('RGBA', (W, H), (255, 255, 255, 255))
    im.alpha_composite(to_image(p))
    return im


# ---------- 形状与蒙版 ----------

def polygon(points: list, S: int = 4) -> np.ndarray:
    """多边形蒙版，4 倍超采样画再缩回，边缘抗锯齿。"""
    m = np.zeros((H * S, W * S), np.uint8)
    pts = np.round(np.array(points, np.float32) * S).astype(np.int32)
    cv2.fillPoly(m, [pts], 255, lineType=cv2.LINE_AA)
    return cv2.resize(m.astype(np.float32) / 255, (W, H), interpolation=cv2.INTER_AREA)


def disk(center: tuple, radius: float, S: int = 4) -> np.ndarray:
    m = np.zeros((H * S, W * S), np.uint8)
    cv2.circle(m, (int(round(center[0] * S)), int(round(center[1] * S))), int(round(radius * S)), 255, -1,
               lineType=cv2.LINE_AA)
    return cv2.resize(m.astype(np.float32) / 255, (W, H), interpolation=cv2.INTER_AREA)


def union(*masks: np.ndarray) -> np.ndarray:
    out = np.zeros((H, W), np.float32)
    for m in masks:
        out = np.maximum(out, m)
    return out


def minus(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.clip(a - b, 0, 1)


def grow(mask: np.ndarray, px: int) -> np.ndarray:
    if px <= 0:
        return mask
    k = 2 * px + 1
    return cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))


def feather(mask: np.ndarray, sigma: float) -> np.ndarray:
    return np.clip(cv2.GaussianBlur(mask, (0, 0), sigma), 0, 1).astype(np.float32) if sigma > 0 else mask


def opaque_within(plate: np.ndarray, mask: np.ndarray, grow_px: int = 3) -> np.ndarray:
    """蒙版再和「底图上不透明的像素（外扩 grow_px 把抗锯齿边整个带上）」相交：多边形可以放心画到人物轮廓外面。
    外扩得够宽，轮廓外那圈半透明的描线残影才会一起进洞——否则补洞时它们是离洞最近的像素，会被拉进来成一道灰边。"""
    a = (plate[..., 3] > 0.02).astype(np.float32)
    return np.minimum(mask, grow(a, grow_px))


# ---------- 骨骼权重 ----------

def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def ramp(a: tuple, b: tuple) -> np.ndarray:
    """沿 a→b 方向的线性权重：投影在 a 之前为 0、b 之后为 1，中间平滑过渡。用于手臂：a 在肩膀、b 在袖口。"""
    ax, ay = a
    bx, by = b
    vx, vy = bx - ax, by - ay
    L2 = max(vx * vx + vy * vy, 1e-6)
    s = ((_XX - ax) * vx + (_YY - ay) * vy) / L2
    return smoothstep(s).astype(np.float32)


def gauss(center: tuple, sigma: tuple, region: Optional[tuple] = None, fea: float = 3.0) -> np.ndarray:
    """高斯衰减权重；region=(x0,y0,x1,y1) 时再乘一个软边矩形。尾巴截断为 0，远处逐像素不变。"""
    cx, cy = center
    sx, sy = sigma
    w = np.exp(-(((_XX - cx) / sx) ** 2 + ((_YY - cy) / sy) ** 2) / 2)
    if region is not None:
        x0, y0, x1, y1 = region
        wx = np.clip(np.minimum(_XX - x0, x1 - _XX) / fea + 1, 0, 1)
        wy = np.clip(np.minimum(_YY - y0, y1 - _YY) / fea + 1, 0, 1)
        w = w * wx * wy
    return np.clip((w - 0.03) / 0.97, 0, 1).astype(np.float32)


def full() -> np.ndarray:
    return np.ones((H, W), np.float32)


# ---------- 骨骼 ----------

Motion2 = Callable[[float], tuple]
Angle = Callable[[float], float]


def _zero2(t):
    return (0.0, 0.0)


def _zero(t):
    return 0.0


@dataclass
class Bone:
    """一根骨：绕 pivot 转 angle(t) 度（顺时针为正），再平移 shift(t)；有父骨时叠在父骨的运动上。
    weight 是它在画面上的影响范围（0–1），子骨的权重应不大于父骨的。"""
    name: str
    pivot: tuple
    weight: np.ndarray
    parent: Optional['Bone'] = None
    angle: Angle = _zero
    shift: Motion2 = _zero2

    def local(self, t: float) -> np.ndarray:
        th = math.radians(self.angle(t))
        c, s = math.cos(th), math.sin(th)
        px, py = self.pivot
        dx, dy = self.shift(t)
        # 先绕 pivot 转，再平移：M·p = R(p − pivot) + pivot + shift
        return np.array([[c, -s, px - c * px + s * py + dx],
                         [s, c, py - s * px - c * py + dy],
                         [0, 0, 1]], np.float64)

    def world(self, t: float) -> np.ndarray:
        M = self.local(t)
        return self.parent.world(t) @ M if self.parent is not None else M

    def is_still(self, t: float) -> bool:
        return abs(self.angle(t)) < 1e-9 and abs(self.shift(t)[0]) < 1e-9 and abs(self.shift(t)[1]) < 1e-9 and \
            (self.parent is None or self.parent.is_still(t))


def rigid_displacement(bone: Bone, t: float):
    """整幅画面按 bone 整条链的运动刚性位移。"""
    if bone.is_still(t):
        return np.zeros((H, W), np.float32), np.zeros((H, W), np.float32)
    M = bone.world(t)
    px = (M[0, 0] * _XX + M[0, 1] * _YY + M[0, 2] - _XX).astype(np.float32)
    py = (M[1, 0] * _XX + M[1, 1] * _YY + M[1, 2] - _YY).astype(np.float32)
    return px, py


def displacement(bones: list, t: float, rigid: bool = False):
    """这组骨在时刻 t 给画面每个像素的位移 (dx, dy)：线性混合蒙皮——每根骨的权重减去它子骨的权重，乘上它整条链的运动。
    rigid=True 时不看权重，整幅按最后一根骨的链刚性移动。"""
    dx = np.zeros((H, W), np.float32)
    dy = np.zeros((H, W), np.float32)
    if rigid:
        return rigid_displacement(bones[-1], t)
    ids = {id(b) for b in bones}
    for b in bones:
        if b.is_still(t):
            continue
        w = b.weight.copy()
        for c in bones:
            if c.parent is b and id(c) in ids:
                w -= c.weight
        w = np.clip(w, 0, 1)
        M = b.world(t)
        px = M[0, 0] * _XX + M[0, 1] * _YY + M[0, 2] - _XX
        py = M[1, 0] * _XX + M[1, 1] * _YY + M[1, 2] - _YY
        dx += w * px
        dy += w * py
    return dx, dy


def warp(src: np.ndarray, dx: np.ndarray, dy: np.ndarray) -> np.ndarray:
    """按位移场变形：输出像素 p 取源图 q，q + d(q) = p。先 q≈p−d(p)，再代回一次修正（大位移、转动也准）。"""
    if float(np.abs(dx).max()) < 1e-6 and float(np.abs(dy).max()) < 1e-6:
        return src
    mx, my = _XX - dx, _YY - dy
    dx1 = cv2.remap(dx, mx, my, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    dy1 = cv2.remap(dy, mx, my, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    out = cv2.remap(src, _XX - dx1, _YY - dy1, interpolation=cv2.INTER_CUBIC,
                    borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    still = (np.abs(dx) < 1e-5) & (np.abs(dy) < 1e-5)
    out[still] = src[still]
    out = np.clip(out, 0, 1)
    out[..., :3] = np.minimum(out[..., :3], out[..., 3:4])
    return out


def max_step(bones: list, t0: float, t1: float) -> float:
    a = displacement(bones, t0)
    b = displacement(bones, t1)
    return float(np.max(np.hypot(b[0] - a[0], b[1] - a[1])))


# ---------- 时间曲线 ----------

def ease(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def keys(points: list, period: float) -> Callable[[float], tuple]:
    """循环关键帧：points=[(时间, 值…), …]，相邻关键帧之间缓入缓出。末尾自动接回第一个关键帧。"""
    pts = sorted(points)
    first = pts[0]
    pts = pts + [(first[0] + period,) + tuple(first[1:])]

    def f(t: float):
        t = t % period
        if t < pts[0][0]:
            t += period
        for (ta, *va), (tb, *vb) in zip(pts, pts[1:]):
            if ta <= t <= tb:
                k = ease((t - ta) / (tb - ta)) if tb > ta else 1.0
                return tuple(a + (b - a) * k for a, b in zip(va, vb))
        return tuple(first[1:])
    return f


def vec(points: list, period: float) -> Motion2:
    f = keys(points, period)
    return lambda t: f(t)[:2]


def scalar(points: list, period: float) -> Callable[[float], float]:
    f = keys(points, period)
    return lambda t: f(t)[0]


def once(points: list, hold: float):
    """只播一次的关键帧：超出最后一个关键帧后保持其值（hold 秒之后仍保持）。"""
    pts = sorted(points)
    last = pts[-1]

    def f(t: float):
        if t <= pts[0][0]:
            return tuple(pts[0][1:])
        for (ta, *va), (tb, *vb) in zip(pts, pts[1:]):
            if ta <= t <= tb:
                k = ease((t - ta) / (tb - ta)) if tb > ta else 1.0
                return tuple(a + (b - a) * k for a, b in zip(va, vb))
        return tuple(last[1:])
    return f


# ---------- 补洞 ----------

def nearest_fill(plate: np.ndarray, hole: np.ndarray) -> np.ndarray:
    """洞里每个像素取洞外离它最近的像素（预乘 RGBA 连同透明度一起拷）。平色区域补得干净，不像 Telea 那样糊成一团。"""
    h = hole > 0.04
    if not h.any():
        return plate.copy()
    dist, labels = cv2.distanceTransformWithLabels(h.astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    known = np.flatnonzero(~h)          # 标签按洞外像素的扫描顺序从 1 起编号
    flat = plate.reshape(-1, 4)
    src = known[np.clip(labels.astype(np.int64) - 1, 0, len(known) - 1)]
    out = plate.copy()
    out[h] = flat[src.reshape(H, W)[h]]
    return out


def clone(base: np.ndarray, plate: np.ndarray, area: np.ndarray, dx: float, dy: float) -> np.ndarray:
    """补丁：area 里的像素改成底图上平移 (dx, dy) 处的像素（桌面、屏幕这种横向均匀的背景，横着克隆最像）。"""
    M = np.array([[1, 0, -dx], [0, 1, -dy]], np.float32)
    moved = cv2.warpAffine(plate, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    a = area[..., None]
    return moved * a + base * (1 - a)


def flat(base: np.ndarray, plate: np.ndarray, area: np.ndarray, at: tuple) -> np.ndarray:
    """补丁：area 平涂成底图 at 点的颜色。"""
    x, y = at
    c = plate[int(y), int(x)]
    a = area[..., None]
    return c[None, None, :] * a + base * (1 - a)


def paint(base: np.ndarray, area: np.ndarray, rgba: tuple) -> np.ndarray:
    """补丁：area 平涂成给定颜色（0–1，未预乘，含 alpha）。"""
    c = np.array([rgba[0] * rgba[3], rgba[1] * rgba[3], rgba[2] * rgba[3], rgba[3]], np.float32)
    a = area[..., None]
    return c[None, None, :] * a + base * (1 - a)


def extend_rows(base: np.ndarray, plate: np.ndarray, area: np.ndarray, hole: np.ndarray) -> np.ndarray:
    """补丁：area 里的洞按同一行左右两侧最近的完好像素线性补齐。纸、桌面这种横向均匀的东西，横着接最像。"""
    out = base.copy()
    h = hole > 0.04
    sel = (area > 0.5) & h
    for y in np.nonzero(sel.any(axis=1))[0]:
        keep = np.nonzero(~h[y])[0]
        if len(keep) == 0:
            continue
        for x in np.nonzero(sel[y])[0]:
            left = keep[keep < x]
            right = keep[keep > x]
            if len(left) and len(right):
                a, b = int(left[-1]), int(right[0])
                k = (x - a) / (b - a)
                out[y, x] = plate[y, a] * (1 - k) + plate[y, b] * k
            else:
                out[y, x] = plate[y, int(left[-1]) if len(left) else int(right[0])]
    return out


def sheet_image(rect: tuple, fill, ink, lines: int = 5, S: int = 4) -> np.ndarray:
    """画一张纸（米白底、灰边、几行字），预乘 RGBA。用来做整理文件时叠在后面、没对齐的纸。"""
    x0, y0, x1, y1 = rect
    img = np.zeros((H * S, W * S, 4), np.float32)
    p0 = (int(round(x0 * S)), int(round(y0 * S)))
    p1 = (int(round(x1 * S)), int(round(y1 * S)))
    cv2.rectangle(img, p0, p1, tuple(float(v) for v in fill), -1, lineType=cv2.LINE_AA)
    cv2.rectangle(img, p0, p1, tuple(float(v) for v in ink), max(1, S // 2), lineType=cv2.LINE_AA)
    faint = tuple(float(v) * 0.35 + float(f) * 0.65 for v, f in zip(ink, fill))
    for i in range(lines):
        yy = int(round((y0 + 8 + i * (y1 - y0 - 16) / max(lines - 1, 1)) * S))
        cv2.line(img, (p0[0] + 6 * S, yy), (p1[0] - 6 * S - (i % 2) * 6 * S, yy), faint, max(1, S // 2),
                 lineType=cv2.LINE_AA)
    return cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA)


def stroke(points: list, width: float, S: int = 4) -> np.ndarray:
    """折线蒙版（画描线用），抗锯齿。"""
    m = np.zeros((H * S, W * S), np.uint8)
    pts = np.round(np.array(points, np.float32) * S).astype(np.int32)
    cv2.polylines(m, [pts], False, 255, max(1, int(round(width * S))), lineType=cv2.LINE_AA)
    return cv2.resize(m.astype(np.float32) / 255, (W, H), interpolation=cv2.INTER_AREA)


def lama_fill(plate: np.ndarray, hole: np.ndarray, model) -> np.ndarray:
    """用 LaMa 补 RGB（透明度仍按最近像素补）。model 是 simple_lama_inpainting.SimpleLama()；没装就别调。"""
    near = nearest_fill(plate, hole)
    h = hole > 0.04
    rgb = np.clip(unpremul_rgb(near), 0, 1)
    al = near[..., 3]
    rgb8 = np.round(rgb * 255).astype(np.uint8)
    m8 = (grow(h.astype(np.float32), 1) > 0).astype(np.uint8) * 255
    res = np.asarray(model(Image.fromarray(rgb8), Image.fromarray(m8)).convert('RGB'), np.float32)[:H, :W] / 255
    out = near.copy()
    out[h, :3] = res[h] * al[h, None]
    return out


# ---------- 眨眼（从 motionlib 移植，坐标换成 2 倍） ----------

@dataclass
class Eye:
    box: tuple
    columns: dict
    center: tuple


def detect_eye(plate: np.ndarray, box: tuple) -> Eye:
    x0, y0, x1, y1 = box
    rgb = unpremul_rgb(plate[y0:y1, x0:x1])
    al = plate[y0:y1, x0:x1, 3]
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    dark = (lum < 0.42) & (al > 0.7)
    iris = (b - r > 0.16) & (b > 0.45) & (al > 0.7)
    columns = {}
    for c in range(x1 - x0):
        d = np.nonzero(dark[:, c])[0]
        if len(d) == 0:
            continue
        top = int(d[0])
        lash = 1
        while top + lash < dark.shape[0] and dark[top + lash, c] and lash < 6:
            lash += 1
        e = np.nonzero(dark[:, c] | iris[:, c])[0]
        columns[x0 + c] = (y0 + top, lash, y0 + int(e[-1]) + 1)
    ys, xs = np.nonzero(iris)
    center = (x0 + float(xs.mean()), y0 + float(ys.mean())) if len(xs) else ((x0 + x1) / 2, (y0 + y1) / 2)
    return Eye(box, columns, center)


def eye_outline(eye: Eye) -> dict:
    cols = sorted(eye.columns.items())
    xa, xb = cols[0][0], cols[-1][0] + 1
    xm, hw = (xa + xb) / 2, max((xb - xa) / 2, 1.0)
    depth = max(bottom - top for _, (top, lash, bottom) in cols)
    out = {}
    for x, (top, lash, bottom) in cols:
        u = (x + 0.5 - xm) / hw
        almond = top + lash + (depth - lash) * math.sqrt(max(0.0, 1 - u * u))
        out[x] = (top, lash, max(float(bottom), almond))
    return out


def _median_color(pixels: list, fallback: np.ndarray) -> np.ndarray:
    return np.median(np.array(pixels), axis=0).astype(np.float32) if pixels else fallback


def paint_blink(plate: np.ndarray, eyes: list, amount: float, S: int = 2) -> np.ndarray:
    """闭合程度 amount（0–1）的眼睛。半闭：眼皮（脸颊肤色）从上往下盖住一部分；全闭：盖上肤色并画一条闭眼线。"""
    if amount <= 0:
        return plate
    out = plate.copy()
    for eye in eyes:
        if not eye.columns:
            continue
        geo = eye_outline(eye)
        xs = sorted(geo)
        xs0, xs1 = xs[0], xs[-1] + 1
        ys0 = max(min(g[0] for g in geo.values()) - 4, 0)
        ys1 = min(int(math.ceil(max(g[2] for g in geo.values()))) + 8, H)
        region = plate[ys0:ys1, xs0:xs1]
        rgb = unpremul_rgb(region)
        lum = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
        skin_px, lash_px = [], []
        for x in xs[4:-4] or xs:
            top, lash, bottom = geo[x]
            c = x - xs0
            for yy in range(int(math.ceil(bottom)) + 2, int(math.ceil(bottom)) + 6):
                if 0 <= yy - ys0 < region.shape[0] and region[yy - ys0, c, 3] > 0.95 and lum[yy - ys0, c] > 0.72:
                    skin_px.append(region[yy - ys0, c])
            for yy in range(top, top + lash):
                lash_px.append(region[yy - ys0, c])
        skin = _median_color(skin_px, np.array([0.99, 0.93, 0.89, 1.0], np.float32))
        if lash_px:
            lash_px = sorted(lash_px, key=lambda p: float(p[:3] @ np.array([0.299, 0.587, 0.114], np.float32)))
            lash_px = lash_px[:max(1, len(lash_px) * 2 // 5)]
        ink = _median_color(lash_px, np.array([0.10, 0.10, 0.20, 1.0], np.float32))

        up = np.clip(cv2.resize(region, ((xs1 - xs0) * S, (ys1 - ys0) * S), interpolation=cv2.INTER_CUBIC), 0, 1)
        new = up.copy()
        rows = np.arange(new.shape[0], dtype=np.float32)[:, None]
        # 睫毛线顶部逐列平滑一下（眼角上挑的那几列不再各自为政），眼皮和闭眼线都沿这条平滑的弧走；
        # 盖肤色时仍从每列真正的睫毛顶起，眼角挑起来的那一撮也一起盖住。
        smooth = {}
        for x in xs:
            near = [geo[k][0] for k in xs if abs(k - x) <= 2]
            smooth[x] = sum(near) / len(near)
        for x in xs:
            top, lash, bottom = geo[x]
            t, l, bt = (top - ys0) * S, lash * S, (bottom - ys0) * S
            ts = int(round((smooth[x] - ys0) * S))
            for sub in range(S):
                cx = (x - xs0) * S + sub
                if amount < 1:
                    lid = int(round(ts + amount * max(0.0, bt - l - ts)))
                    lashpix = up[t:t + l, cx].copy()
                    new[min(t, ts):lid, cx] = skin
                    n = min(l, new.shape[0] - lid)
                    if n > 0:
                        new[lid:lid + n, cx] = lashpix[:n]
                else:
                    new[min(t, ts):min(int(round(bt + 2 * S)), new.shape[0]), cx] = skin
        if amount >= 1:
            xm, hw = (xs0 + xs1) / 2, max((xs1 - xs0) / 2, 1.0)
            for x in xs:
                top, lash, bottom = geo[x]
                for sub in range(S):
                    fx = x + (sub + 0.5) / S
                    u = min(abs(fx - xm) / hw, 1.0)
                    yc = (smooth[x] + 0.62 * (bottom - smooth[x]) - ys0) * S
                    half = (1.5 - 0.8 * u * u) * S       # 中间约 3 像素粗（2 倍图），两端约 1.4
                    cov = np.clip(half - np.abs(rows[:, 0] + 0.5 - yc) + 0.5, 0, 1)[:, None]
                    cx = (x - xs0) * S + sub
                    new[:, cx] = ink * cov + new[:, cx] * (1 - cov)
        down = cv2.resize(new, (xs1 - xs0, ys1 - ys0), interpolation=cv2.INTER_AREA)
        changed = cv2.resize((np.abs(new - up).max(axis=2) > 1e-4).astype(np.float32),
                             (xs1 - xs0, ys1 - ys0), interpolation=cv2.INTER_AREA) > 0
        target = out[ys0:ys1, xs0:xs1]
        target[changed] = down[changed]
    out = np.clip(out, 0, 1)
    out[..., :3] = np.minimum(out[..., :3], out[..., 3:4])
    return out


# ---------- 层与场景 ----------

@dataclass
class Layer:
    """一层：image 是整幅画布大小的预乘 RGBA；mask 是从底图上抠它的蒙版（合成层为 None，不在底图上挖洞）；
    bones 是让它动的骨（含父骨）；z 越大越靠上（底图是 0 之下）。"""
    name: str
    image: np.ndarray
    bones: list
    mask: Optional[np.ndarray] = None
    z: int = 1
    rigid: bool = False      # 整层刚性地跟着 bones 里最后那根骨（连同它的父骨）走，不看权重：手里的笔、放大镜
    fix: Optional[Callable] = None   # 抠出来之后对这一层的像素做的修整（例如把放大镜的镜片涂成不透明）


def cut(plate: np.ndarray, mask: np.ndarray) -> np.ndarray:
    return plate * mask[..., None]


def compose(base: np.ndarray, layers: list) -> np.ndarray:
    out = base
    for L in layers:
        L = np.clip(L, 0, 1)
        L[..., :3] = np.minimum(L[..., :3], L[..., 3:4])
        out = L + out * (1 - L[..., 3:4])
    out = np.clip(out, 0, 1)
    out[..., :3] = np.minimum(out[..., :3], out[..., 3:4])
    return out


@dataclass
class Rig:
    layers: list = field(default_factory=list)
    base_bones: list = field(default_factory=list)     # 直接作用在补好的底图上（头、眼）
    patches: list = field(default_factory=list)        # (底图, 原图, 洞) -> 底图，补洞之后依次应用
    base_image: Optional[np.ndarray] = None            # 指定底图（不从原图挖洞补出来）


class Scene:
    """一个动作：底图、补好的背景、各层与骨骼；按时间和眨眼程度出帧。"""

    def __init__(self, plate: np.ndarray, eyes: list, rig: Rig, filler=nearest_fill):
        self.plate, self.eyes, self.rig = plate, eyes, rig
        self.hole = union(*[L.mask for L in rig.layers if L.mask is not None]) if rig.layers else np.zeros((H, W), np.float32)
        if rig.base_image is not None:
            self.base = rig.base_image
        else:
            self.base = filler(plate, self.hole) if float(self.hole.max()) > 0 else plate
            for p in rig.patches:
                self.base = p(self.base, plate, self.hole)
        self._blink: dict = {}

    def frame(self, t: float, blink: float = 0.0) -> np.ndarray:
        k = round(blink, 3)
        if k not in self._blink:
            self._blink[k] = paint_blink(self.base, self.eyes, blink)
        base = warp(self._blink[k], *displacement(self.rig.base_bones, t)) if self.rig.base_bones else self._blink[k]
        stack = []
        for L in sorted(self.rig.layers, key=lambda L: L.z):
            stack.append(warp(L.image, *displacement(L.bones, t, L.rigid)) if L.bones else L.image)
        return compose(base, stack) if stack else base

    def all_bones(self) -> list:
        seen, out = set(), []
        for b in self.rig.base_bones + [b for L in self.rig.layers for b in L.bones]:
            if id(b) not in seen:
                seen.add(id(b))
                out.append(b)
        return out

    def step(self, t0: float, t1: float) -> float:
        """两帧之间最大的位移变化（像素，2 倍图）：底图看整幅，各层只看它自己有像素的地方（骨骼权重在层外也是 1）。"""
        worst = max_step(self.rig.base_bones, t0, t1) if self.rig.base_bones else 0.0
        for L in self.rig.layers:
            if not L.bones:
                continue
            a = displacement(L.bones, t0, L.rigid)
            b = displacement(L.bones, t1, L.rigid)
            sup = L.image[..., 3] > 0.05
            if sup.any():
                worst = max(worst, float(np.max(np.hypot(b[0] - a[0], b[1] - a[1])[sup])))
        return worst


# ---------- 时间轴与图条 ----------

@dataclass
class Frame:
    image: np.ndarray
    duration_ms: float


def frame_key(p: np.ndarray) -> str:
    return hashlib.sha1(np.round(np.clip(p, 0, 1) * 255).astype(np.uint8).tobytes()).hexdigest()


def assemble(frames: list):
    """相邻相同的帧合并时长；全局相同的帧只存一份。返回 (不重复的帧, 序列, 时长)。"""
    uniques, index, sequence, durations = [], {}, [], []
    for f in frames:
        k = frame_key(f.image)
        if k not in index:
            index[k] = len(uniques)
            uniques.append(f.image)
        i = index[k]
        if sequence and sequence[-1] == i:
            durations[-1] += f.duration_ms
        else:
            sequence.append(i)
            durations.append(f.duration_ms)
    return uniques, sequence, [round(d) for d in durations]


MAX_WEBP = 16383


def pack(frames: list) -> Image.Image:
    """按行优先排进网格：一行放不下 WebP 宽度上限时折行。frames 是 uint8 RGBA。"""
    fh, fw = frames[0].shape[:2]
    per_row = max(1, min(len(frames), MAX_WEBP // fw))
    rows = math.ceil(len(frames) / per_row)
    sheet = Image.new('RGBA', (fw * per_row, fh * rows), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        sheet.paste(Image.fromarray(f), ((i % per_row) * fw, (i // per_row) * fh))
    return sheet


def save_webp(im: Image.Image, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, 'WEBP', lossless=True, quality=100, method=6)


# ---------- 轮廓描边（与 upscale_motion.py 同一套） ----------

OUTLINE_RGB = (14, 14, 40)


def ring_coverage(alpha: np.ndarray, radius: float, K: int = 4) -> np.ndarray:
    h, w = alpha.shape
    up = cv2.resize(alpha, (w * K, h * K), interpolation=cv2.INTER_LINEAR)
    inside = (up > 0.5).astype(np.uint8)
    d = cv2.distanceTransform(1 - inside, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    ring = np.clip(radius * K + 1 - d, 0, 1)
    ring[inside == 1] = 1
    return cv2.resize(ring, (w, h), interpolation=cv2.INTER_AREA)


def add_outline(rgba8: np.ndarray, radius: float) -> np.ndarray:
    """轮廓外垫一圈深色描边：人物叠在描边上面，不透明的像素一个不改。"""
    if radius <= 0:
        return rgba8
    f = rgba8.astype(np.float32) / 255
    a, rgb = f[..., 3], f[..., :3]
    ring = ring_coverage(a, radius)
    color = np.array(OUTLINE_RGB, np.float32) / 255
    out_a = a + ring * (1 - a)
    out_rgb = (rgb * a[..., None] + color * (ring * (1 - a))[..., None]) / np.maximum(out_a[..., None], 1e-6)
    out = np.concatenate([out_rgb, out_a[..., None]], axis=2)
    out[out_a < 1e-4] = 0
    return np.round(np.clip(out, 0, 1) * 255).astype(np.uint8)
