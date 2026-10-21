#!/usr/bin/env python3
"""把 GPT 生成的「被无形大手拎住」原图裁成播放器用的一帧底图。

用法（在 YukioPlayer 目录）：
  python3 tools/hang/make_held.py                    生成 Resources/Assets/base/held.png
  python3 tools/hang/make_held.py --check out.png    生成对照图（与站立图并排、标出抓手点）

源图是透明背景的 1024×1536 立绘，比例与现有图条不一致，所以不按整体高度缩放，
而是按「头宽」对齐（头是最显眼的部位，头一样大，换图时才不会觉得人物忽大忽小）。
成品帧比常规的 192×208 高：两条腿垂下来，一共 192×240。
摆放约定：这一帧的上边缘与常规帧的上边缘对齐，因此头发顶端要落在与站立图相同的行（y=16）。

GPT 把「被捏起来的领口」画成了头顶一个尖锐的深蓝三角，用户不要，这里抠掉：
那个尖整块在头发后面、露在头发轮廓之上，从尖内部按深蓝色漫延选出来，连同抗锯齿边缘一起删干净。
抓手点因此不再对着图上的某个东西，而是她头顶上方一小段的空点——那只大手本来就是看不见的。
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT.parent / 'sources' / 'held-source.png'
REFERENCE = ROOT.parent / 'assets' / 'base' / 'neutral.png'
OUT = ROOT / 'Resources' / 'Assets' / 'base' / 'held.png'
SHARED = ROOT.parent / 'assets' / 'base' / 'held.png'

W, H = 192, 240
HAIR_TOP = 16          # 头发顶端所在行，与 neutral.png 相同
GRIP_ABOVE_HAIR = 6    # 抓手点在头发顶端上方几行（空处：大手看不见）
ALPHA = 24
PEAK_MARGIN = 12       # 清尖顶残留时，只清尖的包围盒外扩这么多像素（源图像素）以内


def mask(image: Image.Image) -> np.ndarray:
    return np.array(image.split()[3]) > ALPHA


def head_width(image: Image.Image) -> int:
    """头部最宽处的像素宽度。取人物上 42% 里每行宽度的最大值。"""
    m = mask(image)
    ys, _ = np.where(m)
    top, bottom = ys.min(), ys.max()
    zone = range(top, top + int((bottom - top + 1) * 0.42))
    widths = []
    for y in zone:
        row = np.where(m[y])[0]
        widths.append(0 if len(row) == 0 else row.max() - row.min() + 1)
    return max(widths)


def hair_top(image: Image.Image, threshold: float = 0.55) -> int:
    """头发顶端的行号：从上往下第一行宽度超过头宽 threshold 的行。

    抠掉领口尖之前，再往上是那个又窄又高的尖，不能当成头顶。
    """
    m = mask(image)
    ys, _ = np.where(m)
    hw = head_width(image)
    for y in range(ys.min(), ys.max() + 1):
        row = np.where(m[y])[0]
        if len(row) and row.max() - row.min() + 1 >= hw * threshold:
            return y
    return ys.min()


def _dilate(m: np.ndarray, times: int) -> np.ndarray:
    out = m.copy()
    for _ in range(times):
        grown = out.copy()
        grown[1:] |= out[:-1]
        grown[:-1] |= out[1:]
        grown[:, 1:] |= out[:, :-1]
        grown[:, :-1] |= out[:, 1:]
        out = grown
    return out


def drop_collar_peak(image: Image.Image) -> Image.Image:
    """删掉头顶那个尖锐的深蓝三角（GPT 画的「被捏起的领口」）。

    从尖内部按深蓝色漫延选出一整块（蝴蝶结隔着白头发，不会连上），再删掉它的抗锯齿边缘；
    边缘只删「头发轮廓以上」的部分，头发自己的描边和呆毛不动。
    """
    a = np.array(image).astype(int)
    red, green, blue, alpha = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    lum = (red + green + blue) / 3
    navy = (alpha > 40) & (blue - red > 8) & (lum < 185)
    m = mask(image)
    ys, _ = np.where(m)
    top = ys.min()
    row = np.where(m[top + 24])[0]      # 尖顶有一小块高光，种子往下挪一点
    seed = (top + 24, int((row.min() + row.max()) // 2))
    if not navy[seed]:
        return image                     # 换了新图、没有这个尖就原样返回

    peak = np.zeros(navy.shape, bool)
    peak[seed] = True
    stack = [seed]
    while stack:
        y, x = stack.pop()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                ny, nx = y + dy, x + dx
                if 0 <= ny < navy.shape[0] and 0 <= nx < navy.shape[1] and navy[ny, nx] and not peak[ny, nx]:
                    peak[ny, nx] = True
                    stack.append((ny, nx))

    hair = (alpha > 200) & (lum >= 228) & (~peak)      # 白头发（不含尖）
    above = np.zeros_like(peak)
    for x in range(peak.shape[1]):
        rows = np.where(hair[:, x])[0]
        above[:rows[0] if len(rows) else peak.shape[0], x] = True
    a[..., 3] = np.where(peak | ((_dilate(peak, 3) & ~peak) & above), 0, alpha)

    # 尖顶的高光会剩一小撮：头发轮廓以上剩下的零星像素一并清掉。只在尖附近清：`above` 是按列算的
    # 「这一列第一个白头发像素以上」，整张图都这么清的话，蝴蝶结（压在白头发上面）会被整个删掉。
    py, px = np.where(peak)
    near = np.zeros_like(peak)
    near[max(py.min() - PEAK_MARGIN, 0):py.max() + PEAK_MARGIN + 1,
         max(px.min() - PEAK_MARGIN, 0):px.max() + PEAK_MARGIN + 1] = True
    left = (a[..., 3] > ALPHA) & above & near
    a[..., 3] = np.where(left, 0, a[..., 3])
    return Image.fromarray(a.astype(np.uint8))


def grip(image: Image.Image) -> tuple[float, float]:
    """抓手那一点：横向取人物重心（这样她自然垂直吊着），纵向在头发顶端上方一小段的空处。"""
    m = mask(image)
    _, xs = np.where(m)
    return float(xs.mean()), hair_top(image) - GRIP_ABOVE_HAIR * (image.height / H)


def build() -> tuple[Image.Image, dict]:
    src = drop_collar_peak(Image.open(SOURCE).convert('RGBA'))
    ref = Image.open(REFERENCE).convert('RGBA')

    scale = head_width(ref) / head_width(src)
    size = (max(1, round(src.width * scale)), max(1, round(src.height * scale)))
    small = src.resize(size, Image.LANCZOS)

    gx, gy = grip(small)
    top = hair_top(small)
    m = mask(small)
    ys, xs = np.where(m)

    # 重心对到帧的横向中线（吊起来才是正的）；头发顶端对到 HAIR_TOP。
    dx = round(W / 2 - gx)
    dy = HAIR_TOP - top
    canvas = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    canvas.alpha_composite(small, (dx, dy))

    info = {
        'scale': round(scale, 4),
        'headWidth': int(head_width(ref)),
        'gripX': round(gx + dx, 1),
        'gripY': round(gy + dy, 1),
        'hairTop': int(top + dy),
        'bottom': int(ys.max() + dy),
        'left': int(xs.min() + dx),
        'right': int(xs.max() + dx),
    }
    return canvas, info


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', help='另存一张对照图：站立、拎起并排，标出抓手点')
    args = ap.parse_args()

    canvas, info = build()
    for path in (OUT, SHARED):
        path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(path)
    print(f'{OUT.relative_to(ROOT)}  {W}×{H}  ' + '  '.join(f'{k}={v}' for k, v in info.items()))
    if info['bottom'] >= H or info['left'] < 0 or info['right'] >= W:
        raise SystemExit('人物超出帧边界，调整 W/H 或 HAIR_TOP')

    if args.check:
        ref = Image.open(REFERENCE).convert('RGBA')
        sheet = Image.new('RGBA', (W * 2, H), (255, 255, 255, 255))
        sheet.alpha_composite(ref, (0, 0))
        sheet.alpha_composite(canvas, (W, 0))
        px = sheet.load()
        for x in range(W, W * 2):                      # 头发顶端那条线
            px[x, HAIR_TOP] = (255, 0, 0, 255)
            px[x - W, HAIR_TOP] = (255, 0, 0, 255)
        cx, cy = int(info['gripX']) + W, int(round(info['gripY']))
        for d in range(-6, 7):                          # 抓手点十字
            px[cx + d, cy] = (0, 160, 255, 255)
            px[cx, max(0, cy + d)] = (0, 160, 255, 255)
        sheet.convert('RGB').resize((W * 4, H * 2), Image.NEAREST).save(args.check)
        print('对照图：', args.check)


if __name__ == '__main__':
    main()
