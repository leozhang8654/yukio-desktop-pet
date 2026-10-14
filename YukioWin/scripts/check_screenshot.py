#!/usr/bin/env python3
"""对着截屏检查：那一块屏幕上的像素，是不是真的就是雪绪。

    python scripts/check_screenshot.py 截屏.png 动作名 左 上 宽 高

把该动作图条里“各帧都不透明、而且颜色完全一样”的那些像素（桌子、椅子、身体这些不动的部分）
挑出来，逐个和截屏上同一位置的颜色比。分层窗口是逐像素 alpha 合成的，完全不透明的像素
在屏幕上应当一模一样，所以匹配率低就说明她没画出来、画歪了或者画糊了。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image

from yukio.catalog import AnimationCatalog, assets_root
from yukio.console import force_utf8_console
from yukio.sprites import SpriteLibrary
from yukio.skins import skin_root

#: 允许的单通道色差（截屏和色彩管理可能差一两个数）。
TOLERANCE = 6
#: 至少要有这么多比例的静止像素对得上。
REQUIRED_RATIO = 0.90


def static_pixels(library: SpriteLibrary, spec_id: str, size=None, limit: int = 12):
    """各帧都不透明且颜色一致的像素：[(x, y, (r, g, b)), …]。

    size：屏幕上她实际占的像素尺寸。放大显示时先按播放器同样的办法（双线性）缩到这个尺寸
    再比，否则插值出来的颜色对不上。
    """
    count = min(library.frame_count(spec_id), limit)
    frames = [library.frame(spec_id, i).image for i in range(count)]
    if not frames:
        return []
    if size and tuple(size) != frames[0].size:
        frames = [f.resize(tuple(size), Image.BILINEAR) for f in frames]
    width, height = frames[0].size
    data = [f.tobytes() for f in frames]   # RGBA，每像素 4 字节
    base = data[0]
    out = []
    for i in range(width * height):
        j = i * 4
        if base[j + 3] != 255:
            continue
        pixel = base[j:j + 4]
        if any(d[j:j + 4] != pixel for d in data[1:]):
            continue
        out.append((i % width, i // width, (pixel[0], pixel[1], pixel[2])))
    return out


def best_frame_match(screen, library, spec_id, rect):
    """For moving/near-opaque skins, compare against every decoded frame.

    Alpha 253/254 has no exactly opaque static pixels. Bound the unknown
    desktop background contribution mathematically; retain the same 90% ratio
    and per-channel tolerance, requiring at least 100 high-alpha samples.
    """
    left, top, width, height = rect
    if left < 0 or top < 0 or left + width > screen.width or top + height > screen.height:
        return 0.0, 0, None
    actual = list(screen.crop((left, top, left + width, top + height)).convert('RGB').getdata())
    best = (0.0, 0, None)
    for index in range(library.frame_count(spec_id)):
        frame = library.frame(spec_id, index).image.resize((width, height), Image.BILINEAR).convert('RGBA')
        hit = count = 0
        for pixel, observed in zip(frame.getdata(), actual):
            alpha = pixel[3]
            if alpha < 253:
                continue
            count += 1
            # Any desktop background is in [0,255]. Quantization adds <=1.
            if all((pixel[c] * alpha // 255 - TOLERANCE - 1) <= observed[c] <=
                   ((pixel[c] * alpha + 255 * (255 - alpha)) // 255 + TOLERANCE + 1)
                   for c in range(3)):
                hit += 1
        if count >= 100 and hit / count > best[0]:
            best = (hit / count, count, index)
    return best


def main() -> int:
    force_utf8_console()
    if len(sys.argv) < 7:
        print(__doc__)
        return 2
    path, spec_id = sys.argv[1], sys.argv[2]
    left, top, width, height = (int(v) for v in sys.argv[3:7])

    root = assets_root()
    if not root:
        print("找不到素材目录")
        return 1
    root = skin_root(root, sys.argv[7] if len(sys.argv) > 7 else "yukio")
    catalog = AnimationCatalog.load(root)
    library = SpriteLibrary(catalog, root)
    spec = catalog.specs.get(spec_id)
    if spec is None:
        print("没有这个动作：%s" % spec_id)
        return 1

    screen = Image.open(path).convert("RGB")
    pixels = static_pixels(library, spec_id, (width, height))
    if not pixels:
        ratio, count, index = best_frame_match(screen, library, spec_id, (left, top, width, height))
        print("动态帧比对：最佳帧 %s，%d 个高不透明像素，匹配率 %.1f%%" % (index, count, ratio * 100))
        return 0 if index is not None and ratio >= REQUIRED_RATIO else 1

    hit = miss = outside = 0
    for x, y, (r, g, b) in pixels:
        sx = left + x
        sy = top + y
        if not (0 <= sx < screen.size[0] and 0 <= sy < screen.size[1]):
            outside += 1
            continue
        sr, sg, sb = screen.getpixel((sx, sy))
        if abs(sr - r) <= TOLERANCE and abs(sg - g) <= TOLERANCE and abs(sb - b) <= TOLERANCE:
            hit += 1
        else:
            miss += 1
    compared = hit + miss
    ratio = hit / compared if compared else 0.0
    print("比对 %d 个静止像素：对上 %d，对不上 %d，落在屏幕外 %d，匹配率 %.1f%%"
          % (len(pixels), hit, miss, outside, ratio * 100))
    if compared == 0:
        print("窗口整个不在屏幕里")
        return 1
    if ratio < REQUIRED_RATIO:
        print("匹配率低于 %.0f%%：屏幕上那一块不是雪绪，或者画得不对" % (REQUIRED_RATIO * 100))
        return 1
    print("屏幕上确实是她（%s · %s）" % (spec_id, spec.label))
    return 0


if __name__ == "__main__":
    sys.exit(main())
