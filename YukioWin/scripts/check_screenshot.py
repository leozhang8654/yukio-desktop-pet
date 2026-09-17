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

#: 允许的单通道色差（截屏和色彩管理可能差一两个数）。
TOLERANCE = 6
#: 至少要有这么多比例的静止像素对得上。
REQUIRED_RATIO = 0.90


def static_pixels(library: SpriteLibrary, spec_id: str, limit: int = 12):
    """各帧都不透明且颜色一致的像素：[(x, y, (r, g, b)), …]。"""
    count = min(library.frame_count(spec_id), limit)
    frames = [library.frame(spec_id, i).image for i in range(count)]
    if not frames:
        return []
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
    catalog = AnimationCatalog.load(root)
    library = SpriteLibrary(catalog, root)
    spec = catalog.specs.get(spec_id)
    if spec is None:
        print("没有这个动作：%s" % spec_id)
        return 1

    screen = Image.open(path).convert("RGB")
    pixels = static_pixels(library, spec_id)
    if not pixels:
        print("这个动作没有可比对的静止像素")
        return 1
    scale_x = width / spec.frame_width
    scale_y = height / spec.frame_height

    hit = miss = outside = 0
    for x, y, (r, g, b) in pixels:
        sx = int(left + (x + 0.5) * scale_x)
        sy = int(top + (y + 0.5) * scale_y)
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
