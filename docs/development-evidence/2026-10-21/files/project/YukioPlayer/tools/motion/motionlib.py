"""雪绪小幅动作：一张已确认的底图 + 局部平滑变形，生成丝滑、小幅度、不抽搐的逐帧图条。

为什么这样做：现有每套动作的 4 帧是分别生成的画，整幅线条（连桌腿、椅子）都有 1 像素级漂移，
直接轮播就会“呼吸抽搐”。这里只取其中一帧当底图，画面其余部分逐像素不动；要动的部分（手、笔、头、眼）
用高斯衰减的位移场做亚像素平移或小角度旋转，位移都在 2 像素以内，不会产生空洞或双重轮廓。
眨眼在变形之前画到底图上，所以眼皮会跟着头一起动。
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Callable, Optional

import cv2
import numpy as np
from PIL import Image

W, H = 192, 208
_YY, _XX = np.mgrid[0:H, 0:W].astype(np.float32)

Vec = tuple[float, float]
Motion = Callable[[float], Vec]


# ---------- 图像读写（内部一律用预乘 alpha 的 float32，插值时透明边缘不会发黑发白） ----------

def load_frame(path: str, index: int = 0) -> np.ndarray:
    im = Image.open(path).convert('RGBA')
    a = np.asarray(im.crop((index * W, 0, (index + 1) * W, H)), dtype=np.float32) / 255.0
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


def unpremul_rgb(p: np.ndarray) -> np.ndarray:
    al = p[..., 3:4]
    return np.where(al > 1e-4, p[..., :3] / np.maximum(al, 1e-6), 0)


# ---------- 位移把手 ----------

def soft_weight(center: Vec, sigma: Vec, region: Optional[tuple] = None, feather: float = 3.0) -> np.ndarray:
    """高斯衰减权重；region=(x0,y0,x1,y1) 时再乘一个软边矩形，限制影响范围。尾巴截断为 0，远处逐像素不变。"""
    cx, cy = center
    sx, sy = sigma
    w = np.exp(-(((_XX - cx) / sx) ** 2 + ((_YY - cy) / sy) ** 2) / 2)
    if region is not None:
        x0, y0, x1, y1 = region
        wx = np.clip(np.minimum(_XX - x0, x1 - _XX) / feather + 1, 0, 1)
        wy = np.clip(np.minimum(_YY - y0, y1 - _YY) / feather + 1, 0, 1)
        w = w * wx * wy
    return np.clip((w - 0.03) / 0.97, 0, 1).astype(np.float32)


@dataclass
class Shift:
    """在 center 附近按权重平移像素。motion(t) 返回 (dx, dy) 像素。"""
    center: Vec
    sigma: Vec
    motion: Motion
    region: Optional[tuple] = None
    feather: float = 3.0

    def __post_init__(self):
        self.w = soft_weight(self.center, self.sigma, self.region, self.feather)

    def field(self, t: float):
        dx, dy = self.motion(t)
        return self.w * dx, self.w * dy


@dataclass
class Rotate:
    """绕 pivot 小角度旋转（度，正值顺时针），权重同上。用于转头、歪头。"""
    pivot: Vec
    center: Vec
    sigma: Vec
    angle: Callable[[float], float]
    region: Optional[tuple] = None
    feather: float = 3.0

    def __post_init__(self):
        self.w = soft_weight(self.center, self.sigma, self.region, self.feather)

    def field(self, t: float):
        th = math.radians(self.angle(t))
        px, py = self.pivot
        rx, ry = _XX - px, _YY - py
        dx = rx * math.cos(th) - ry * math.sin(th) - rx
        dy = rx * math.sin(th) + ry * math.cos(th) - ry
        return self.w * dx, self.w * dy


def render(src: np.ndarray, handles: list, t: float) -> np.ndarray:
    dx = np.zeros((H, W), np.float32)
    dy = np.zeros((H, W), np.float32)
    for h in handles:
        fx, fy = h.field(t)
        dx += fx
        dy += fy
    # 反向映射：输出像素 p 取源图 p - d(p)。位移小且平滑，一阶近似足够。
    out = cv2.remap(src, _XX - dx, _YY - dy, interpolation=cv2.INTER_CUBIC,
                    borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    still = (np.abs(dx) < 1e-5) & (np.abs(dy) < 1e-5)
    out[still] = src[still]
    out = np.clip(out, 0, 1)
    out[..., :3] = np.minimum(out[..., :3], out[..., 3:4])
    return out


def max_step(handles: list, t0: float, t1: float) -> float:
    """两帧之间任一像素位移的最大变化（像素），用来确认动作足够细碎、看起来连续。"""
    if not handles:
        return 0.0
    a = [h.field(t0) for h in handles]
    b = [h.field(t1) for h in handles]
    ddx = sum(f[0] for f in b) - sum(f[0] for f in a)
    ddy = sum(f[1] for f in b) - sum(f[1] for f in a)
    return float(np.max(np.hypot(ddx, ddy)))


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


def vec(points: list, period: float) -> Motion:
    f = keys(points, period)
    return lambda t: f(t)[:2]


def scalar(points: list, period: float) -> Callable[[float], float]:
    f = keys(points, period)
    return lambda t: f(t)[0]


# ---------- 时间轴与图条 ----------

@dataclass
class Frame:
    image: np.ndarray
    duration_ms: float


def frame_key(p: np.ndarray) -> str:
    return hashlib.sha1(np.round(np.clip(p, 0, 1) * 255).astype(np.uint8).tobytes()).hexdigest()


def assemble(frames: list[Frame]):
    """相邻相同的帧合并时长；全局相同的帧只存一份。返回 (不重复的帧列表, 序列, 时长)。"""
    uniques: list[np.ndarray] = []
    index: dict[str, int] = {}
    sequence: list[int] = []
    durations: list[float] = []
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


def save_strip(uniques: list[np.ndarray], path: str):
    if len(uniques) * W > 16383:
        raise ValueError(f'{path}: {len(uniques)} 帧超过 WebP 宽度上限')
    strip = Image.new('RGBA', (W * len(uniques), H), (0, 0, 0, 0))
    for i, p in enumerate(uniques):
        strip.paste(to_image(p), (i * W, 0))
    strip.save(path, 'WEBP', lossless=True, quality=100, method=6)


# ---------- 眨眼 ----------

@dataclass
class Eye:
    """一只眼：每列 (上睫毛线顶部, 睫毛线厚度, 眼睛下缘)（1 倍坐标，下缘不含），以及虹膜中心。"""
    box: tuple
    columns: dict
    center: Vec


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
        while top + lash < dark.shape[0] and dark[top + lash, c] and lash < 3:
            lash += 1
        e = np.nonzero(dark[:, c] | iris[:, c])[0]
        columns[x0 + c] = (y0 + top, lash, y0 + int(e[-1]) + 1)
    ys, xs = np.nonzero(iris)
    center = (x0 + float(xs.mean()), y0 + float(ys.mean())) if len(xs) else ((x0 + x1) / 2, (y0 + y1) / 2)
    return Eye(box, columns, center)


def eye_outline(eye: Eye) -> dict:
    """每列 (睫毛线顶, 厚度, 下缘)。眼角那几列没有虹膜，下缘按杏仁形（半椭圆）补齐，眼角的眼白也会被盖住。"""
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


def paint_blink(plate: np.ndarray, eyes: list, amount: float, S: int = 4) -> np.ndarray:
    """闭合程度 amount（0–1）的眼睛，在 S 倍分辨率下画再缩回，边缘自然抗锯齿。只改眼睛本身的像素。

    半闭：眼皮（取眼睛下方脸颊的肤色）从上往下盖住一部分，原来的上睫毛线跟着移到眼皮边缘；
    全闭：整只眼盖上肤色，在眼睛高度约 62% 处画一条中间粗、两端细的闭眼线（颜色取原睫毛线）。
    """
    if amount <= 0:
        return plate
    out = plate.copy()
    for eye in eyes:
        if not eye.columns:
            continue
        geo = eye_outline(eye)
        xs = sorted(geo)
        xs0, xs1 = xs[0], xs[-1] + 1
        ys0 = max(min(g[0] for g in geo.values()) - 2, 0)
        ys1 = min(int(math.ceil(max(g[2] for g in geo.values()))) + 4, H)
        region = plate[ys0:ys1, xs0:xs1]
        rgb = unpremul_rgb(region)
        lum = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
        # 肤色：眼睛下缘往下 1–3 像素、亮而不透明的像素的中位数；睫毛色：睫毛线像素的中位数。
        skin_px, lash_px = [], []
        for x in xs[2:-2] or xs:
            top, lash, bottom = geo[x]
            c = x - xs0
            for yy in range(int(math.ceil(bottom)) + 1, int(math.ceil(bottom)) + 3):
                if 0 <= yy - ys0 < region.shape[0] and region[yy - ys0, c, 3] > 0.95 and lum[yy - ys0, c] > 0.72:
                    skin_px.append(region[yy - ys0, c])
            for yy in range(top, top + lash):
                lash_px.append(region[yy - ys0, c])
        skin = _median_color(skin_px, np.array([0.99, 0.93, 0.89, 1.0], np.float32))
        # 睫毛线边缘有抗锯齿的浅色像素，只取最深的四成，闭眼线才不会发灰。
        if lash_px:
            lash_px = sorted(lash_px, key=lambda p: float(p[:3] @ np.array([0.299, 0.587, 0.114], np.float32)))
            lash_px = lash_px[:max(1, len(lash_px) * 2 // 5)]
        ink = _median_color(lash_px, np.array([0.10, 0.10, 0.20, 1.0], np.float32))

        up = np.clip(cv2.resize(region, ((xs1 - xs0) * S, (ys1 - ys0) * S), interpolation=cv2.INTER_CUBIC), 0, 1)
        new = up.copy()
        rows = np.arange(new.shape[0], dtype=np.float32)[:, None]
        for x in xs:
            top, lash, bottom = geo[x]
            t, l, bt = (top - ys0) * S, lash * S, (bottom - ys0) * S
            for sub in range(S):
                cx = (x - xs0) * S + sub
                if amount < 1:
                    lid = int(round(t + amount * max(0.0, bt - l - t)))
                    lashpix = up[t:t + l, cx].copy()
                    new[t:lid, cx] = skin
                    n = min(l, new.shape[0] - lid)
                    if n > 0:
                        new[lid:lid + n, cx] = lashpix[:n]
                else:
                    # 多盖 1 像素：虹膜下缘抗锯齿的浅蓝色不会在闭眼线下露出一圈。
                    new[t:min(int(round(bt + S)), new.shape[0]), cx] = skin
        if amount >= 1:
            xm, hw = (xs0 + xs1) / 2, max((xs1 - xs0) / 2, 1.0)
            for x in xs:
                top, lash, bottom = geo[x]
                for sub in range(S):
                    fx = x + (sub + 0.5) / S
                    u = min(abs(fx - xm) / hw, 1.0)
                    yc = (top + 0.62 * (bottom - top) - ys0) * S
                    half = (0.75 - 0.4 * u * u) * S       # 中间约 1.5 像素粗，两端约 0.7
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


# ---------- 整块移动的部件：从底图抠出来，背后补齐，按时间平移、旋转 ----------
# 变形只适合 1–2 像素；手、笔、放大镜、纸要动几像素时，把它们当成一层单独移动，
# 原位置用四周像素补齐（移开时露出来的就是补出来的背景），这样不会拉扯周围的画面。

def polygon_mask(points: list, S: int = 4) -> np.ndarray:
    """多边形蒙版（1 倍坐标），4 倍超采样画再缩回，边缘抗锯齿。"""
    m = np.zeros((H * S, W * S), np.uint8)
    pts = np.round(np.array(points, np.float32) * S).astype(np.int32)
    cv2.fillPoly(m, [pts], 255, lineType=cv2.LINE_AA)
    return cv2.resize(m.astype(np.float32) / 255, (W, H), interpolation=cv2.INTER_AREA)


def disk_mask(center: Vec, radius: float, S: int = 4) -> np.ndarray:
    m = np.zeros((H * S, W * S), np.uint8)
    cv2.circle(m, (int(round(center[0] * S)), int(round(center[1] * S))), int(round(radius * S)), 255, -1,
               lineType=cv2.LINE_AA)
    return cv2.resize(m.astype(np.float32) / 255, (W, H), interpolation=cv2.INTER_AREA)


def pick_pixels(plate: np.ndarray, rule) -> np.ndarray:
    """按颜色选像素：rule(r, g, b, alpha, 亮度) → 布尔图（颜色为未预乘值）。"""
    rgb = unpremul_rgb(plate)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    return rule(r, g, b, plate[..., 3], lum).astype(np.float32)


def part_mask(plate: np.ndarray, region: list, rule=None, grow: int = 1, add=(), feather: float = 0.5) -> np.ndarray:
    """部件蒙版：region 多边形内按颜色 rule 选出部件，再向外长 grow 像素把描边带上；add 为整块加入的形状。"""
    area = polygon_mask(region)
    if rule is None:
        m = area
    else:
        sel = pick_pixels(plate, rule)
        if grow > 0:
            k = 2 * grow + 1
            sel = cv2.dilate(sel, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
        m = np.minimum(sel, area)
    for shape in add:
        m = np.maximum(m, shape)
    if feather > 0:
        m = cv2.GaussianBlur(m, (0, 0), feather)
    return np.clip(m, 0, 1).astype(np.float32)


def flood_mask(plate: np.ndarray, seeds: list, tol: float = 0.2, region: Optional[list] = None,
               grow: int = 1, add=(), feather: float = 0.5, min_lum: float = 0.6) -> np.ndarray:
    """从部件内部的种子点出发，选出与种子颜色相差不超过 tol 的相连像素（固定范围：抗锯齿的描边是一级级渐变，
    按相邻像素比较会顺着渐变一路漫到袖子上；和种子比就挡得住），得到整块手套或纸；
    再向外长 grow 像素把描边带上。region 限定范围；比 min_lum 暗的种子（多半点到了描边或背景上）跳过。"""
    rgb = np.clip(unpremul_rgb(plate), 0, 1)
    rgb8 = np.round(rgb * 255).astype(np.uint8)
    lum = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    d = int(round(tol * 255))
    total = np.zeros((H + 2, W + 2), np.uint8)
    for x, y in seeds:
        if lum[int(y), int(x)] < min_lum:
            print(f'  跳过种子 ({x}, {y})：亮度 {lum[int(y), int(x)]:.2f}')
            continue
        m = np.zeros((H + 2, W + 2), np.uint8)
        cv2.floodFill(rgb8.copy(), m, (int(x), int(y)), (0, 0, 0), (d, d, d), (d, d, d),
                      flags=4 | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE | (255 << 8))
        total = np.maximum(total, m)
    sel = total[1:-1, 1:-1].astype(np.float32) / 255
    if grow > 0:
        k = 2 * grow + 1
        sel = cv2.dilate(sel, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    if region is not None:
        sel = np.minimum(sel, polygon_mask(region))
    for shape in add:
        sel = np.maximum(sel, shape)
    if feather > 0:
        sel = cv2.GaussianBlur(sel, (0, 0), feather)
    return np.clip(sel, 0, 1).astype(np.float32)


def clean_plate(plate: np.ndarray, hole: np.ndarray, radius: float = 3) -> np.ndarray:
    """把部件挖掉，用四周像素补齐（OpenCV inpaint，Telea）。部件移开时露出来的就是这里。"""
    h = hole > 0.04
    m8 = h.astype(np.uint8) * 255
    rgb8 = np.round(np.clip(unpremul_rgb(plate), 0, 1) * 255).astype(np.uint8)
    a8 = np.round(np.clip(plate[..., 3], 0, 1) * 255).astype(np.uint8)
    rgb = cv2.inpaint(rgb8, m8, radius, cv2.INPAINT_TELEA).astype(np.float32) / 255
    al = cv2.inpaint(a8, m8, radius, cv2.INPAINT_TELEA).astype(np.float32)[..., None] / 255
    fill = np.concatenate([rgb * al, al], axis=2)
    out = plate.copy()
    out[h] = fill[h]
    return out


def extend_rows(plate: np.ndarray, base: np.ndarray, hole: np.ndarray, y0: int, y1: int) -> np.ndarray:
    """把 y0..y1 之间挖掉的像素，按同一行左右两侧最近的完好像素线性补齐。
    桌沿、桌面这种横向均匀的背景，这样比 inpaint 的糊团更接近原来的样子（部件抬起时露出的就是这条带）。"""
    out = base.copy()
    solid = hole <= 0.04
    for y in range(max(y0, 0), min(y1, H)):
        keep = np.nonzero(solid[y])[0]
        if len(keep) == 0:
            continue
        for x in np.nonzero(~solid[y])[0]:
            left = keep[keep < x]
            right = keep[keep > x]
            if len(left) and len(right):
                a, b = int(left[-1]), int(right[0])
                k = (x - a) / (b - a)
                out[y, x] = plate[y, a] * (1 - k) + plate[y, b] * k
            else:
                out[y, x] = plate[y, int(left[-1]) if len(left) else int(right[0])]
    return out


@dataclass
class Part:
    """整块移动的一层：按 mask 从 src 抠出，绕 pivot 顺时针转 angle 度，再平移 (dx, dy)。motion(t) → (dx, dy, angle)。"""
    mask: np.ndarray
    pivot: Vec
    motion: Callable[[float], tuple]
    image: Optional[np.ndarray] = None   # 不从底图抠、而是另外画好的一层（例如整理文件时后面那几张纸）

    def layer(self, src: np.ndarray, t: float) -> np.ndarray:
        dx, dy, angle = self.motion(t)
        piece = (self.image if self.image is not None else src) * self.mask[..., None]
        M = cv2.getRotationMatrix2D(self.pivot, -angle, 1.0)
        M[0, 2] += dx
        M[1, 2] += dy
        return cv2.warpAffine(piece, M, (W, H), flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))


def compose(base: np.ndarray, layers: list) -> np.ndarray:
    out = base
    for L in layers:
        L = np.clip(L, 0, 1)
        L[..., :3] = np.minimum(L[..., :3], L[..., 3:4])
        out = L + out * (1 - L[..., 3:4])
    out = np.clip(out, 0, 1)
    out[..., :3] = np.minimum(out[..., :3], out[..., 3:4])
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
        yy = int(round((y0 + 4 + i * (y1 - y0 - 8) / max(lines - 1, 1)) * S))
        cv2.line(img, (p0[0] + 3 * S, yy), (p1[0] - 3 * S - (i % 2) * 3 * S, yy), faint, max(1, S // 2),
                 lineType=cv2.LINE_AA)
    return cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA)
