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
