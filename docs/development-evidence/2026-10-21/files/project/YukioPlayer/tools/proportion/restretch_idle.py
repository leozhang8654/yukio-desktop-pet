#!/usr/bin/env python3
"""把待机（idle）的人物比例改得跟被拎起来那张（held）一样：腿拉长、整体上移。

原来的待机图是原生那套 Q 版：头大、腿短（膝下那截只有 20 px）。被拎起来时用的是
`base/held.png`，同样大的头配更长的身子和腿，两张一换腿长差一截，很显眼。

这里不重画，只做一件事：把**袜子那段**（裙摆下、靴口上的那截白袜）纵向拉长，
其余（头、上身、裙、吊带、袜口花边、靴子）逐像素不动，只整体平移。
脚底线仍落在原来那一行，站的位置不变；头顶顶到画面上沿，多出来的高度全给腿。

用法：
    python3 tools/proportion/restretch_idle.py --preview out.png   # 只看效果
    python3 tools/proportion/restretch_idle.py --apply             # 写回素材（先备份 .orig）
"""

import argparse
import os
import shutil
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))   # 仓库根（tools/proportion 上面三层）
ASSETS = os.path.join(os.path.dirname(HERE), "..", "Resources", "Assets")
ASSETS = os.path.normpath(ASSETS)

#: 待机图里的分界线（192×208 帧内的 y）。都是照着图量的，改之前先用 --preview 看。
SOCK_TOP = 150      # 袜口花边下沿：这行以上一律不拉
BOOT_TOP = 170      # 靴口上沿：这行以下一律不拉
SOLE = 195          # 鞋底：拉完仍要落在这一行
HEAD_TOP = 16       # 原图头顶
OUT_HEAD_TOP = 2    # 拉完后的头顶（顶到画面上沿，留 2 px 余量）


def restretch(im, sock_top=SOCK_TOP, boot_top=BOOT_TOP, sole=SOLE,
              head_top=HEAD_TOP, out_head_top=OUT_HEAD_TOP):
    """三段：头到袜口原样上移；袜子那段拉长；靴子原样接在下面，鞋底回到原来那行。"""
    w, h = im.size
    dy = out_head_top - head_top                       # 负数：整体上移
    sock_h = boot_top - sock_top
    # 靴子段里鞋底的位置不变，反推袜子该有多高
    new_sock_h = sole - (boot_top + dy) - (sole - boot_top) - dy + (boot_top + dy) - (sock_top + dy)
    # 上面那行绕了，直接解方程：(sock_top+dy) + new_sock_h + (sole-boot_top) == sole
    new_sock_h = sole - (sole - boot_top) - (sock_top + dy)
    if new_sock_h <= 0:
        raise SystemExit("袜子段算出来是负的，检查分界线")

    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    head = im.crop((0, 0, w, sock_top))
    sock = im.crop((0, sock_top, w, boot_top))
    boot = im.crop((0, boot_top, w, h))
    out.alpha_composite(head, (0, max(0, sock_top + dy - head.size[1])) if dy < 0 else (0, dy))
    # 上面那句对负 dy 也要简单些：直接按偏移贴，越界部分自动裁掉
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    paste_shifted(out, head, dy)
    sock_big = sock.resize((w, new_sock_h), Image.LANCZOS)
    paste_shifted(out, sock_big, sock_top + dy, from_top=True)
    paste_shifted(out, boot, sock_top + dy + new_sock_h, from_top=True)
    return out, new_sock_h, sock_h


def paste_shifted(canvas, piece, y, from_top=False):
    """把一段贴到 y 处（from_top=False 时 y 是相对原位置的偏移）。越界自动裁。"""
    w, h = canvas.size
    top = y if from_top else y
    if top >= h or top + piece.size[1] <= 0:
        return
    src_top = max(0, -top)
    src_bot = min(piece.size[1], h - top)
    part = piece.crop((0, src_top, piece.size[0], src_bot))
    canvas.alpha_composite(part, (0, max(0, top)))


def strip(path, frame_w, frame_h):
    im = Image.open(path).convert("RGBA")
    n = im.size[0] // frame_w
    return im, n


def process(path, frame_w, frame_h, **kw):
    im, n = strip(path, frame_w, frame_h)
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    info = None
    for i in range(n):
        f = im.crop((i * frame_w, 0, (i + 1) * frame_w, frame_h))
        g, new_h, old_h = restretch(f, **kw)
        info = (old_h, new_h)
        out.alpha_composite(g, (i * frame_w, 0))
    return out, n, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", metavar="OUT.png")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--sock-top", type=int, default=SOCK_TOP)
    ap.add_argument("--boot-top", type=int, default=BOOT_TOP)
    ap.add_argument("--sole", type=int, default=SOLE)
    ap.add_argument("--head-top", type=int, default=HEAD_TOP)
    ap.add_argument("--out-head-top", type=int, default=OUT_HEAD_TOP)
    ap.add_argument("--targets", default="idle,failed",
                    help="要改的站姿动作，逗号分隔（base/ 与 motion/ 下同名的都会改）")
    a = ap.parse_args()
    kw = dict(sock_top=a.sock_top, boot_top=a.boot_top, sole=a.sole,
              head_top=a.head_top, out_head_top=a.out_head_top)

    # 站着的两套（待机、沮丧）都要改：不然一出错她的腿又变回短的。
    names = [n.strip() for n in a.targets.split(",") if n.strip()]
    targets = [(os.path.join(ASSETS, d, n + ".webp"), 192, 208)
               for n in names for d in ("base", "motion")
               if os.path.exists(os.path.join(ASSETS, d, n + ".webp"))]

    if a.preview:
        base = Image.open(targets[0][0]).convert("RGBA").crop((0, 0, 192, 208))
        after, _, info = process(targets[0][0], 192, 208, **kw)
        held = Image.open(os.path.join(ASSETS, "base", "held.png")).convert("RGBA")
        z = 2
        canvas = Image.new("RGBA", ((192 * 3 + 40) * z, 245 * z), (252, 252, 252, 255))
        for k, im in enumerate([base, after.crop((0, 0, 192, 208)), held]):
            big = im.resize((im.size[0] * z, im.size[1] * z), Image.LANCZOS)
            canvas.alpha_composite(big, (k * (192 + 20) * z, (245 - im.size[1]) * z))
        canvas.save(a.preview)
        print(f"袜子段 {info[0]} → {info[1]} px；预览写到 {a.preview}")
        return

    if not a.apply:
        print(__doc__)
        return

    for path, fw, fh in targets:
        out, n, info = process(path, fw, fh, **kw)
        # 原图备份放在仓库的 sources/ 里，不要留在 Resources 下（那一整个目录会打进应用）。
        stem = os.path.splitext(os.path.basename(path))[0]
        where = "base" if os.sep + "base" + os.sep in path else "motion"
        backup = os.path.join(ROOT, "sources", "pre-restretch", f"{stem}-{where}.webp")
        os.makedirs(os.path.dirname(backup), exist_ok=True)
        if not os.path.exists(backup):
            shutil.copy2(path, backup)
        out.save(path, lossless=True) if path.endswith(".webp") else out.save(path)
        print(f"{os.path.relpath(path, ROOT)}：{n} 帧，袜子段 {info[0]} → {info[1]} px（原图备份在 {os.path.relpath(backup, ROOT)}）")


if __name__ == "__main__":
    main()
