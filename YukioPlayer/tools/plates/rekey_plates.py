#!/usr/bin/env python3
"""重新抠出雪绪的底图，边缘不再发黑发紫。

用法（在 YukioPlayer 目录）：
  python3 tools/plates/rekey_plates.py                 重抠 7 套活动图条，清理 computer-desk.png、base/idle.webp、base/failed.webp
  python3 tools/plates/rekey_plates.py --out 目录      写到别处（对比用），不动 Resources/Assets
  python3 tools/plates/rekey_plates.py --sheet 对照.png  每张底图新旧并排（放大 3 倍、白底）
  python3 tools/plates/rekey_plates.py --fit           重新把源图配准到现有底图，打印 (缩放, x 偏移, y 偏移) 表

需要 numpy、opencv-python、Pillow。

为什么：仓库 sources/ 里的源图是洋红底（约 313 像素高），早先抠图时混了洋红的边缘像素没有按 alpha
把颜色反算回来，整圈轮廓比画里的描线又黑又厚，头发、白丝袜、桌沿外面都多了一道黑边。这里按
「像素 = 前景色 × α + 洋红 × (1 − α)」反算：α 取洋红味相对内部的比例，颜色在「最近的亮色／暗色内部像素」
两个候选里挑残差小的那个（描线是暗的，头发是白的，各归各），最后再压掉残余的洋红味。
抠好的源图按当初的缩放与偏移（REGISTRATION，用 --fit 得到）缩到 192×208，几何与旧底图逐像素对得上，
tools/motion 里手工标的坐标不用改。

没有洋红源图的三张（电脑桌、待机、沮丧）只清理边缘：按已有 alpha 与洋红味把混色像素反算、去溢色。
问号卡、勾选卡两张（sources/*-hold-2x.png 缩下来的）边缘本来就是干净的描线，不动。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]          # YukioPlayer/
REPO = ROOT.parent
ASSETS = ROOT / 'Resources' / 'Assets'
SOURCES = REPO / 'sources'

W, H = 192, 208
MAGENTA = np.array([249.0, 4.0, 249.0], np.float32)   # 源图底色（按每张图边框取中位数，这是默认值）

# 活动图条：源图文件、网格（列, 行）、每帧的配准 (缩放, x 偏移, y 偏移)——源图坐标 × 缩放 + 偏移 = 底图坐标。
# 用 --fit 对着 2026-09-13 的旧底图算出来的（alpha 平均差 0.007 上下）；各帧略有出入，所以逐帧记。
ACTIVITIES = {
    'thinking':   ('thinking-source.png', (4, 1)),
    'read_file':  ('read_file-source.png', (4, 1)),
    'view_image': ('view_image-source.png', (4, 1)),
    'write_file': ('write_file-source.png', (4, 1)),
    'verify':     ('verify-source.png', (4, 1)),
    'respond':    ('respond-source.png', (4, 1)),
    'read_web':   ('read_web-corrected-source-2x2.png', (2, 2)),
}
REGISTRATION = {
    'thinking':   [(0.6162, -0.81, 11.76), (0.6160, -0.80, 11.76), (0.6162, -0.81, 11.76), (0.6162, -0.93, 11.76)],
    'read_file':  [(0.6121, 0.39, 12.54), (0.6121, 0.39, 12.54), (0.6087, 1.06, 13.59), (0.6131, -0.27, 12.53)],
    'view_image': [(0.6121, 0.39, 12.43), (0.6121, 0.39, 12.43), (0.6097, 1.01, 13.46), (0.6132, -0.27, 12.42)],
    'write_file': [(0.6122, 0.39, 12.43), (0.6122, 0.39, 12.43), (0.6102, 0.88, 13.46), (0.6132, -0.27, 12.42)],
    'verify':     [(0.5322, 0.13, 11.39), (0.5303, 0.71, 11.92), (0.5303, 0.71, 11.92), (0.5312, 0.69, 11.91)],
    'respond':    [(0.5170, 2.51, 16.83), (0.5171, 2.49, 16.83), (0.5171, 2.49, 16.83), (0.5160, 3.07, 16.84)],
    'read_web':   [(0.3189, -4.22, 13.85), (0.3189, -4.22, 13.85), (0.3189, -4.22, 13.85), (0.3189, -4.22, 13.85)],
}
# 只清理边缘的底图（相对 Assets）。
CLEAN_ONLY = ['activities/computer-desk.png', 'base/idle.webp', 'base/failed.webp']


# ---------- 基本工具 ----------

def magentaness(p: np.ndarray) -> np.ndarray:
    """(R+B)/2 − G：洋红有多重。白、肤色、藏青都接近 0，纯洋红约 245。"""
    return (p[..., 0] + p[..., 2]) / 2 - p[..., 1]


def bleed(val: np.ndarray, known: np.ndarray, iters: int = 12) -> tuple[np.ndarray, np.ndarray]:
    """把 known 处的值一圈圈往外扩（3×3 邻域平均），返回 (扩完的值, 哪些位置有值)。"""
    val = np.asarray(val, np.float32)
    vec = val.ndim == 3
    kn = known.astype(np.float32)
    col = val * (kn[..., None] if vec else kn)
    w = kn.copy()
    k = np.ones((3, 3), np.float32)
    for _ in range(iters):
        cs = cv2.filter2D(col, -1, k, borderType=cv2.BORDER_REPLICATE)
        ws = cv2.filter2D(w, -1, k, borderType=cv2.BORDER_REPLICATE)
        wsx, wx = (ws[..., None], w[..., None]) if vec else (ws, w)
        col = np.where((wx == 0) & (wsx > 0), cs / np.maximum(wsx, 1e-6), col)
        w = np.where((w == 0) & (ws > 0), 1, w)
    return col, w


def unmix(P: np.ndarray, a: np.ndarray, bg: np.ndarray, core: np.ndarray, dist: np.ndarray,
          mref: np.ndarray, mb: float, lum: np.ndarray):
    """已知每个像素的 α，反算前景色。

    颜色在两个候选里挑：最近的亮色内部像素、最近的暗色内部像素（描线），取按 α 混回去后与观测残差小的那个；
    两个都解释不了（三色混合）就直接按公式反算。α 接近 1 时逐渐过渡到直接反算。最后压掉边缘残余的洋红味。
    """
    light = core & (lum >= 90)
    dark = core & (lum < 90)
    FL, wL = bleed(P, light)
    FD, wD = bleed(P, dark)

    def resid(Fh):
        return np.linalg.norm(P - (bg + a[..., None] * (Fh - bg)), axis=2)

    rL = np.where(wL > 0, resid(FL), 1e9)
    rD = np.where(wD > 0, resid(FD), 1e9)
    use_dark = rD < rL
    Fh = np.where(use_dark[..., None], FD, FL)
    direct = np.clip((P - (1 - a[..., None]) * bg) / np.maximum(a[..., None], 1e-3), 0, 255)
    F = np.where((np.minimum(rL, rD) > 30)[..., None], direct, Fh)
    wmix = np.clip((a - 0.9) / 0.1, 0, 1)[..., None]
    F = F * (1 - wmix) + direct * wmix
    F[core] = P[core]
    # 去溢色：离边缘 8 像素内，洋红味超过内部自身的部分从 R、B 里减掉。
    excess = np.clip(magentaness(F) - mref - 4, 0, None) * (dist < 8)
    F[..., 0] -= excess
    F[..., 2] -= excess
    return np.clip(F, 0, 255)


def key_source(rgb8: np.ndarray, bg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """洋红底源图的一帧 → (前景色 0–255, α 0–1)。"""
    P = rgb8.astype(np.float32)
    mb = float(magentaness(bg))
    m = magentaness(P)
    lum = P.mean(axis=2)
    bgmask = m > 0.75 * mb
    dist = cv2.distanceTransform((~bgmask).astype(np.uint8), cv2.DIST_L2, 5)
    # 内部自身的洋红味（藏青约 20）：从离边缘远、颜色干净的像素往外扩，作为每个像素的参照。
    deep = (dist > 4) & (m < 0.15 * mb)
    mref, _ = bleed(m, deep, iters=40)
    mref = np.clip(mref, 0, 0.2 * mb)
    a = 1 - np.clip((m - mref) / np.maximum(mb - mref, 1), 0, 1)
    core = ((dist > 2.5) | ((m - mref) < 0.12 * mb)) & ~bgmask
    F = unmix(P, a, bg, core, dist, mref, mb, lum)
    a[core] = 1
    a[m > 0.92 * mb] = 0
    return F, a


def clean_edges(rgba8: np.ndarray, bg: np.ndarray = MAGENTA) -> np.ndarray:
    """已经带 alpha 的底图：边缘 3 像素内，按洋红味重算 α（取与已有 α 的较小者），颜色反算、去溢色。"""
    P = rgba8[..., :3].astype(np.float32)
    a0 = rgba8[..., 3].astype(np.float32) / 255
    mb = float(magentaness(bg))
    m = magentaness(P)
    lum = P.mean(axis=2)
    bgmask = a0 < 0.02
    dist = cv2.distanceTransform((~bgmask).astype(np.uint8), cv2.DIST_L2, 5)
    deep = (dist > 3) & (a0 > 0.98) & (m < 0.15 * mb)
    mref, _ = bleed(m, deep, iters=40)
    mref = np.clip(mref, 0, 0.2 * mb)
    a_est = 1 - np.clip((m - mref) / np.maximum(mb - mref, 1), 0, 1)
    core = ((dist > 3) | ((m - mref) < 0.12 * mb)) & ~bgmask
    a_est[core] = 1
    F = unmix(P, a_est, bg, core, dist, mref, mb, lum)
    a = np.minimum(a0, a_est)
    a[bgmask] = 0
    out = np.concatenate([F, a[..., None] * 255], axis=2)
    return np.round(np.clip(out, 0, 255)).astype(np.uint8)


def source_frames(state: str):
    """源图按等分网格切格；返回 [(RGB 帧, 底色)]。"""
    name, (cols, rows) = ACTIVITIES[state]
    src = np.array(Image.open(SOURCES / name).convert('RGB'))
    Hs, Ws = src.shape[:2]
    fw, fh = Ws / cols, Hs / rows
    out = []
    for i in range(cols * rows):
        r, c = divmod(i, cols)
        x0, y0 = int(round(c * fw)), int(round(r * fh))
        x1, y1 = int(round((c + 1) * fw)), int(round((r + 1) * fh))
        fr = src[y0:y1, x0:x1]
        border = np.concatenate([fr[0], fr[-1], fr[:, 0], fr[:, -1]]).astype(np.float32)
        out.append((fr, np.median(border, axis=0)))
    return out


def resample(prem: np.ndarray, s: float, tx: float, ty: float) -> np.ndarray:
    """预乘 RGBA 按 (s, tx, ty) 缩到 192×208：先 4 倍超采样（三次插值），再面积平均缩回，亚像素偏移也准。"""
    K = 4
    M = np.array([[s * K, 0, tx * K], [0, s * K, ty * K]], np.float32)
    big = cv2.warpAffine(prem, M, (W * K, H * K), flags=cv2.INTER_CUBIC,
                         borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    return np.clip(cv2.resize(big, (W, H), interpolation=cv2.INTER_AREA), 0, 255)


def to_straight(prem: np.ndarray) -> np.ndarray:
    al = prem[..., 3:4]
    rgb = np.where(al > 0.5, prem[..., :3] / np.maximum(al / 255, 1e-3), 0)
    return np.round(np.concatenate([np.clip(rgb, 0, 255), al], axis=2)).astype(np.uint8)


def rekey_activity(state: str) -> list[np.ndarray]:
    frames = []
    for i, (fr, bg) in enumerate(source_frames(state)):
        F, a = key_source(fr, bg)
        prem = np.concatenate([F * a[..., None], a[..., None] * 255], axis=2)
        s, tx, ty = REGISTRATION[state][i]
        frames.append(to_straight(resample(prem, s, tx, ty)))
    return frames


# ---------- 配准 ----------

def fit(state: str) -> list[tuple[float, float, float]]:
    """把源图每帧的 alpha 配到现有底图上：先按包围盒估缩放与偏移，再在附近细搜。"""
    sheet = Image.open(ASSETS / 'activities' / f'{state}.webp').convert('RGBA')
    result = []
    for i, (fr, bg) in enumerate(source_frames(state)):
        _, fa = key_source(fr, bg)
        pa = np.asarray(sheet.crop((i * W, 0, (i + 1) * W, H)), np.float32)[..., 3] / 255

        def bbox(a):
            ys, xs = np.nonzero(a > 0.5)
            return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
        sb, pb = bbox(fa), bbox(pa)
        s0 = ((pb[2] - pb[0]) / (sb[2] - sb[0]) + (pb[3] - pb[1]) / (sb[3] - sb[1])) / 2
        best = None
        for s in np.linspace(s0 - 0.01, s0 + 0.01, 21):
            for dx in np.linspace(-1.5, 1.5, 7):
                for dy in np.linspace(-1.5, 1.5, 7):
                    tx, ty = pb[0] - sb[0] * s + dx, pb[1] - sb[1] * s + dy
                    M = np.array([[s, 0, tx], [0, s, ty]], np.float32)
                    err = np.abs(cv2.warpAffine(fa, M, (W, H), flags=cv2.INTER_AREA) - pa).mean()
                    if best is None or err < best[0]:
                        best = (err, s, tx, ty)
        err, s, tx, ty = best
        print(f'{state:12s} 帧 {i}: 缩放 {s:.4f}  偏移 ({tx:.2f}, {ty:.2f})  alpha 平均差 {err:.4f}')
        result.append((round(float(s), 4), round(float(tx), 2), round(float(ty), 2)))
    return result


# ---------- 输出 ----------

def save_sheet(frames: list[np.ndarray], path: Path):
    strip = Image.new('RGBA', (W * len(frames), H), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        strip.paste(Image.fromarray(f), (i * W, 0))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == '.png':
        strip.save(path, 'PNG', optimize=True)
    else:
        strip.save(path, 'WEBP', lossless=True, quality=100, method=6)


def load_frames(path: Path) -> list[np.ndarray]:
    im = Image.open(path).convert('RGBA')
    return [np.asarray(im.crop((i * W, 0, (i + 1) * W, H))).copy() for i in range(im.width // W)]


def build_all() -> dict[str, list[np.ndarray]]:
    out = {}
    for state in ACTIVITIES:
        out[f'activities/{state}.webp'] = rekey_activity(state)
        print('重抠', state)
    for rel in CLEAN_ONLY:
        out[rel] = [clean_edges(f) for f in load_frames(ASSETS / rel)]
        print('清边', rel)
    return out


def comparison_sheet(results: dict[str, list[np.ndarray]], path: Path, zoom: int = 3):
    """每张底图第一帧：旧（左）新（右），放大、白底，看轮廓与颜色。"""
    from PIL import ImageDraw
    tiles = []
    for rel, frames in results.items():
        old = load_frames(ASSETS / rel)[0]
        row = Image.new('RGB', (W * zoom * 2 + 12, H * zoom + 16), (200, 200, 200))
        for k, arr in enumerate((old, frames[0])):
            im = Image.fromarray(arr).resize((W * zoom, H * zoom), Image.NEAREST)
            bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
            bg.alpha_composite(im)
            row.paste(bg.convert('RGB'), (k * (W * zoom + 12), 16))
        ImageDraw.Draw(row).text((4, 2), f'{rel}  旧 | 新', fill=(0, 0, 0))
        tiles.append(row)
    cols = 2
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * tiles[0].width, rows * tiles[0].height), (200, 200, 200))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * t.width, (i // cols) * t.height))
    sheet.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', help='输出目录（默认直接写回 Resources/Assets）')
    ap.add_argument('--sheet', help='新旧对照图路径')
    ap.add_argument('--fit', action='store_true', help='重新配准并打印表，不写文件')
    args = ap.parse_args()
    if args.fit:
        for state in ACTIVITIES:
            fit(state)
        return
    results = build_all()
    if args.sheet:
        comparison_sheet(results, Path(args.sheet))
    base = Path(args.out) if args.out else ASSETS
    for rel, frames in results.items():
        save_sheet(frames, base / rel)
        print('写入', base / rel)


if __name__ == '__main__':
    main()
