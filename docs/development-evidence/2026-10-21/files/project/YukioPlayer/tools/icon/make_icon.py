#!/usr/bin/env python3
"""生成应用封面图标 Resources/AppIcon.icns（访达、预览、Dock 里看到的那张）。

用法（在 YukioPlayer 目录）：
  python3 tools/icon/make_icon.py                  生成 Resources/AppIcon.icns
  python3 tools/icon/make_icon.py --style night    深蓝版（默认 ice 浅色）
  python3 tools/icon/make_icon.py --png out.png    只导出 1024 的大图
  python3 tools/icon/make_icon.py --preview p.png  各尺寸对照图，用来目测小图标还认不认得出

只需要 numpy、Pillow 和系统自带的 iconutil。

底图取 `sources/read_web-corrected-source-2x2.png` 左上格（627×627，仓库里雪绪分辨率最高的一张，
洋红底）。先按差值抠像解出前景色，边缘不留紫；再裁成头肩半身，桌沿压在图标下边。
外框按 macOS 的图标网格：1024 画布里 824 的连续圆角方块（超椭圆指数 5，实测与系统图标一致），
下面带一层淡投影。小尺寸单独锐化一点，16/32 像素时轮廓才不糊。
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

PLAYER = Path(__file__).resolve().parents[2]
REPO = PLAYER.parent
SOURCE = REPO / 'sources' / 'read_web-corrected-source-2x2.png'
OUT_ICNS = PLAYER / 'Resources' / 'AppIcon.icns'

S = 1024                     # 画布
BOX = 824                    # 圆角方块边长（苹果网格：1024 里的 824）
N = 5.0                      # 超椭圆指数，接近系统图标的连续圆角
CELL = 627                   # 源图左上格
CROP = (152, 2, 478, 328)    # 从源图裁的半身范围：留一点头顶，下边停在桌面上

# 各尺寸的 iconset 文件名
SIZES = [('icon_16x16.png', 16), ('icon_16x16@2x.png', 32),
         ('icon_32x32.png', 32), ('icon_32x32@2x.png', 64),
         ('icon_128x128.png', 128), ('icon_128x128@2x.png', 256),
         ('icon_256x256.png', 256), ('icon_256x256@2x.png', 512),
         ('icon_512x512.png', 512), ('icon_512x512@2x.png', 1024)]

STYLES = {
    # 顶色, 底色, 头后柔光(颜色, 强度), 平板屏幕的冷光强度, 暗角
    'night': ((40, 58, 100), (12, 19, 44), ((200, 226, 255), 0.22), 0.30, 0.28),
    'ice': ((236, 244, 255), (166, 194, 230), ((255, 255, 255), 0.45), 0.22, 0.16),
}


# ---------- 抠像 ----------

def key_cell(cell: np.ndarray) -> Image.Image:
    """洋红底差值抠像 + 反混合：观察值 = a×前景 + (1-a)×底色，解出前景色，边缘不留紫边。"""
    c = cell.astype(np.float64)
    corners = np.concatenate([c[:12, :12].reshape(-1, 3), c[:12, -12:].reshape(-1, 3),
                              c[-12:, :12].reshape(-1, 3), c[-12:, -12:].reshape(-1, 3)])
    bg = np.median(corners, axis=0)
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    span = min(bg[0], bg[2]) - bg[1]
    k = np.clip((np.minimum(r, b) - g) / span, 0, 1)          # 1 是纯背景，0 是纯前景
    a = np.clip((1 - k) / 0.94, 0, 1)                          # 稍微收一点，吃掉最外圈半透明
    a = np.where(a < 0.02, 0, a)
    a3 = a[..., None]
    fg = np.clip(np.where(a3 > 0.004, (c - (1 - a3) * bg) / np.maximum(a3, 1e-6), 0), 0, 255)
    over = np.maximum(np.minimum(fg[..., 0], fg[..., 2]) - fg[..., 1], 0)   # 残余紫：红蓝同时高于绿
    fg[..., 0] -= np.where(fg[..., 0] > fg[..., 1], over, 0)
    fg[..., 2] -= np.where(fg[..., 2] > fg[..., 1], over, 0)
    return Image.fromarray(np.dstack([fg, a * 255]).astype(np.uint8))


# ---------- 背景与外框 ----------

def squircle(size: int, box: int, ss: int = 4) -> Image.Image:
    """连续圆角方块的蒙版；先按 4 倍算再缩回来，边缘是抗锯齿的。"""
    n = box * ss
    y, x = np.mgrid[0:n, 0:n]
    u, v = (x + 0.5) / n * 2 - 1, (y + 0.5) / n * 2 - 1
    inside = (np.abs(u) ** N + np.abs(v) ** N) <= 1
    m = Image.fromarray((inside * 255).astype(np.uint8)).resize((box, box), Image.LANCZOS)
    full = Image.new('L', (size, size), 0)
    full.paste(m, ((size - box) // 2, (size - box) // 2))
    return full


def vgrad(size: int, top, bottom) -> Image.Image:
    t = np.linspace(0, 1, size)[:, None, None] ** 1.1
    arr = np.array(top)[None, None, :] * (1 - t) + np.array(bottom)[None, None, :] * t
    return Image.fromarray(np.repeat(arr, size, axis=1).astype(np.uint8)).convert('RGBA')


def radial(size: int, cx, cy, rx, ry, color, peak, power=2.0) -> Image.Image:
    y, x = np.mgrid[0:size, 0:size]
    d = np.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2)
    a = np.clip(1 - d, 0, 1) ** power * peak
    rgba = np.dstack([np.full((size, size, 3), color), a * 255]).astype(np.uint8)
    return Image.fromarray(rgba).convert('RGBA')


def cell_to_icon(x: float, y: float) -> tuple:
    """源图坐标 → 图标画布坐标。"""
    x0, y0, x1, _ = CROP
    k = BOX / (x1 - x0)
    return (S - BOX) / 2 + (x - x0) * k, (S - BOX) / 2 + (y - y0) * k


def character() -> Image.Image:
    src = Image.open(SOURCE).convert('RGB')
    im = key_cell(np.asarray(src.crop((0, 0, CELL, CELL))))
    pad = Image.new('RGBA', (im.width + 80, im.height + 80), (0, 0, 0, 0))
    pad.paste(im, (40, 40))                                   # 裁剪框可以越过原图边界
    c = pad.crop(tuple(v + 40 for v in CROP))
    c = c.resize((BOX, round(c.height * BOX / c.width)), Image.LANCZOS)
    r, g, b, a = c.split()
    rgb = Image.merge('RGB', (r, g, b)).filter(ImageFilter.UnsharpMask(radius=3, percent=65, threshold=2))
    rgb.putalpha(a)
    return rgb


def master(style: str) -> Image.Image:
    top, bottom, (halo_color, halo_peak), screen, vignette = STYLES[style]
    mask = squircle(S, BOX)
    face = vgrad(S, top, bottom)
    hx, hy = cell_to_icon(315, 150)                           # 头后柔光
    face = Image.alpha_composite(face, radial(S, hx, hy, BOX * 0.52, BOX * 0.50, halo_color, halo_peak))
    tx, ty = cell_to_icon(330, 300)                           # 平板屏幕透出来的冷光
    face = Image.alpha_composite(face, radial(S, tx, ty, BOX * 0.44, BOX * 0.28, (150, 200, 255), screen, 1.6))

    art = character()
    layer = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    layer.paste(art, ((S - BOX) // 2, (S - BOX) // 2), art)
    face = Image.alpha_composite(face, layer)

    inner = np.asarray(radial(S, S // 2, S // 2, S * 0.80, S * 0.80, (0, 0, 0), 1.0, 1.0))[..., 3] / 255
    dark = ((1 - inner) * vignette * 255).astype(np.uint8)     # 暗角，让人物更靠前
    face = Image.alpha_composite(face, Image.fromarray(np.dstack([np.zeros((S, S, 3), np.uint8), dark])).convert('RGBA'))
    face.putalpha(mask)

    shadow = Image.new('RGBA', (S, S), (10, 14, 28, 255))
    shadow.putalpha(mask.point(lambda v: int(v * 0.32)))
    shadow = shadow.transform(shadow.size, Image.AFFINE, (1, 0, 0, 0, 1, -12)).filter(ImageFilter.GaussianBlur(14))
    return Image.alpha_composite(shadow, face)


def resized(im: Image.Image, size: int) -> Image.Image:
    out = im.resize((size, size), Image.LANCZOS)
    if size <= 64:                                             # 小图标缩完发糊，补一点锐度
        r, g, b, a = out.split()
        rgb = Image.merge('RGB', (r, g, b)).filter(ImageFilter.UnsharpMask(radius=1, percent=70, threshold=0))
        rgb.putalpha(a)
        out = rgb
    return out


def write_icns(im: Image.Image, dest: Path) -> None:
    if not shutil.which('iconutil'):
        sys.exit('找不到 iconutil：需要 Xcode Command Line Tools')
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / 'AppIcon.iconset'
        iconset.mkdir()
        for name, size in SIZES:
            resized(im, size).save(iconset / name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['iconutil', '-c', 'icns', str(iconset), '-o', str(dest)], check=True)


def preview(im: Image.Image, dest: Path) -> None:
    shots = [512, 256, 128, 64, 32, 16]
    pad = 16
    w = sum(s + pad for s in shots) + pad
    sheet = Image.new('RGBA', (w, 512 + 2 * pad), (244, 244, 247, 255))
    x = pad
    for s in shots:
        sheet.alpha_composite(resized(im, s), (x, pad + 512 - s))
        x += s + pad
    sheet.convert('RGB').save(dest)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--style', choices=sorted(STYLES), default='ice')
    ap.add_argument('--png', help='导出 1024 大图')
    ap.add_argument('--preview', help='各尺寸对照图')
    ap.add_argument('--icns', default=str(OUT_ICNS))
    args = ap.parse_args()

    im = master(args.style)
    if args.png:
        im.save(args.png)
    if args.preview:
        preview(im, Path(args.preview))
    if not args.png and not args.preview:
        write_icns(im, Path(args.icns))
        print(args.icns)


if __name__ == '__main__':
    main()
