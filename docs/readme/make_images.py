#!/usr/bin/env python3
"""重新生成 README.md / README.zh-CN.md 用到的图（写到 docs/readme/）。

来源：
  YukioPlayer/Resources/Assets/motion/   应用实际播放的动作图条 → states-*.png、desk.gif
  macOS 播放器的离屏渲染 --bubble / --cards（英文与中文界面各一份）/ --hang-gif → bubble*.png、cards*.png、drag.gif
    不传 --renders 时用 YukioPlayer/.build/release/YukioPlayer 现场渲染（先 swift build -c release）。
需要 Pillow 与 numpy。
"""
import argparse, json, os, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "readme"
MOTION = ROOT / "YukioPlayer" / "Resources" / "Assets" / "motion"
BG, EDGE, TXT = (237, 242, 250, 255), (214, 224, 238, 255), (59, 74, 99, 255)

ORDER = ["thinking", "read_file", "view_image", "write_file", "verify", "read_web", "respond", "task_complete",
         "question_for_user", "default_work", "failed", "idle"]
LABELS = {
    "en": {"thinking": "Thinking", "read_file": "Reading files", "view_image": "Viewing an image", "write_file": "Writing files",
           "verify": "Running tests", "read_web": "Browsing the web", "respond": "Handing in the answer",
           "task_complete": "Done, waiting for you", "question_for_user": "Needs your decision", "default_work": "Other work",
           "failed": "Something failed", "idle": "Idle"},
    "zh": {"thinking": "思考", "read_file": "读文件", "view_image": "看图片", "write_file": "写文件", "verify": "跑测试",
           "read_web": "看网页", "respond": "递交回答", "task_complete": "答完了，等你点", "question_for_user": "等你拿主意",
           "default_work": "其他工作", "failed": "出错了", "idle": "空闲"},
}
# 「桌前的一天」：状态与每段的时长（毫秒）
DAY = [("thinking", 2200), ("read_file", 2600), ("view_image", 2600), ("write_file", 3000), ("verify", 2200),
       ("failed", 2400), ("write_file", 1800), ("verify", 2000), ("respond", 3400), ("task_complete", 3000)]

motion = json.loads((MOTION / "motion.json").read_text(encoding="utf-8"))
states = {s["id"]: s for s in motion["states"]}
_strips = {}


def frame(sid, idx):
    """取一帧，缩到 1 倍（192×208）：图条可能是 2 倍分辨率（pixelScale）、折成几行。"""
    s = states[sid]
    if sid not in _strips:
        _strips[sid] = Image.open(MOTION / s["asset"]).convert("RGBA")
    k = int(s.get("pixelScale") or 1)
    fw, fh = s["frameWidth"] * k, s["frameHeight"] * k
    per_row = max(1, _strips[sid].width // fw)
    im = _strips[sid].crop(((idx % per_row) * fw, (idx // per_row) * fh, (idx % per_row + 1) * fw, (idx // per_row + 1) * fh))
    return im.resize((s["frameWidth"], s["frameHeight"]), Image.LANCZOS) if k != 1 else im


def font(lang, size):
    candidates = [("/System/Library/Fonts/Hiragino Sans GB.ttc", 1), ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0)] if lang == "zh" else []
    candidates += [("/System/Library/Fonts/HelveticaNeue.ttc", 0), ("/System/Library/Fonts/Helvetica.ttc", 0),
                   ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 0)]
    for path, index in candidates:
        try:
            return ImageFont.truetype(path, size, index=index)
        except OSError:
            continue
    return ImageFont.load_default()


def pose_index(sid):
    s = states[sid]
    seq = s["sequence"]
    if sid == "failed":            # 垂眼之后停住的那一帧
        return seq[s.get("loopStart", 0)]
    if sid == "task_complete":     # 把卡抬起来的那一下
        return seq[len(seq) // 2]
    return seq[0]


def grid(lang, path):
    cols, rows, cw, ch, gap = 4, 3, 216, 252, 12
    im = Image.new("RGBA", (cols * cw + (cols - 1) * gap, rows * ch + (rows - 1) * gap), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = font(lang, 15)
    for i, sid in enumerate(ORDER):
        r, c = divmod(i, cols)
        x0, y0 = c * (cw + gap), r * (ch + gap)
        d.rounded_rectangle((x0, y0, x0 + cw - 1, y0 + ch - 1), radius=18, fill=BG, outline=EDGE, width=1)
        im.alpha_composite(frame(sid, pose_index(sid)), (x0 + (cw - 192) // 2, y0 + 8))
        label = LABELS[lang][sid]
        bb = d.textbbox((0, 0), label, font=f)
        d.text((x0 + (cw - (bb[2] - bb[0])) // 2 - bb[0], y0 + 8 + 208 + 6), label, font=f, fill=TXT)
    im.save(path, optimize=True)


def save_gif(frames, durations, path):
    """全局调色板 + 逐帧只写变化区域（Pillow 自带），比逐帧调色板小得多、颜色也不闪。"""
    samples = frames[:: max(1, len(frames) // 24)]
    mosaic = Image.new("RGB", (frames[0].width * len(samples), frames[0].height))
    for j, s in enumerate(samples):
        mosaic.paste(s, (frames[0].width * j, 0))
    palette = mosaic.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    pf = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
    pf[0].save(path, save_all=True, append_images=pf[1:], duration=durations, loop=0, optimize=False, disposal=0)


def desk_gif(path, min_frame_ms=60):
    raw = []
    for sid, budget in DAY:
        seq, dur = states[sid]["sequence"], states[sid]["durationsMs"]
        remaining, i = budget, 0
        while remaining > 0:
            fi, dm = seq[i % len(seq)], dur[i % len(dur)]
            if sid == "thinking" and i == 0:
                dm = min(dm, 700)          # 开头别干等一秒
            d = min(dm, remaining)
            raw.append((sid, fi, d))
            remaining -= d
            i += 1
    merged = []                            # 30 fps 的段落合并到 ≥ min_frame_ms，文件小一半
    for sid, fi, d in raw:
        if merged and merged[-1][0] == sid and merged[-1][2] < min_frame_ms:
            merged[-1] = (sid, merged[-1][1], merged[-1][2] + d)
        else:
            merged.append((sid, fi, d))
    frames = []
    for sid, fi, _ in merged:
        bg = Image.new("RGBA", (192, 208), BG)
        bg.alpha_composite(frame(sid, fi))
        frames.append(bg.convert("RGB"))
    save_gif(frames, [d for _, _, d in merged], path)


def key_checker(path):
    """播放器的检查图画在 16 px 的 235/204 棋盘格上：把棋盘格抠透明，边缘上残留的灰色锯齿换成面板色。"""
    a = np.array(Image.open(path).convert("RGBA")).astype(np.int16)
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    checker = np.where(((xx // 16) + (yy // 16)) % 2 == 0, 235, 204)
    rgb = a[..., :3]
    bgmask = np.all(rgb == checker[..., None], axis=-1)
    near = bgmask.copy()
    for dy in (-2, -1, 0, 1, 2):
        for dx in (-2, -1, 0, 1, 2):
            near |= np.roll(np.roll(bgmask, dy, 0), dx, 1)
    light_grey = (rgb.min(-1) > 150) & ((rgb.max(-1) - rgb.min(-1)) < 40)
    band = near & ~bgmask & light_grey
    fixed = np.clip(np.array(BG[:3], dtype=np.int16) + (rgb - checker[..., None]), 0, 255)
    rgb = np.where(band[..., None], fixed, rgb)
    flat_white = (rgb.min(-1) >= 250) & ~bgmask        # 0.94 透明度的白底透出的 254/252 棋盘纹，压平
    rgb = np.where(flat_white[..., None], 254, rgb)
    alpha = np.where(bgmask, 0, a[..., 3])
    return Image.fromarray(np.dstack([rgb, alpha]).astype(np.uint8))


def panel(im, pad=28, radius=22):
    im = im.crop(im.getbbox())
    out = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(out).rounded_rectangle((0, 0, out.width - 1, out.height - 1), radius=radius, fill=BG, outline=EDGE, width=2)
    out.alpha_composite(im, (pad, pad))
    return out


def drag_gif(src, path, win_w=236):
    """--hang-gif 的画布很宽（她要被拖过整段路）：镜头横向跟着她，只留倾斜与下坠，背景换成面板色。"""
    g = Image.open(src)
    frames, durs = [], []
    for i in range(g.n_frames):
        g.seek(i)
        frames.append(np.array(g.convert("RGB")))
        durs.append(g.info.get("duration", 30))
    h, w = frames[0].shape[:2]
    colours, counts = np.unique(frames[0].reshape(-1, 3), axis=0, return_counts=True)
    bg = colours[counts.argmax()]
    boxes = []
    for a in frames:
        m = np.any(a != bg, axis=-1)
        m[m.mean(1) > 0.5, :] = False      # 整行都不是背景的是画出来的地线，不算她
        ys, xs = np.where(m)
        boxes.append((xs.min(), ys.min(), xs.max(), ys.max()))
    start = next((i for i, b in enumerate(boxes) if b[0] > 1 and b[2] < w - 2), 0)   # 开头几帧她还在画布外
    frames, durs, boxes = frames[start:], durs[start:], boxes[start:]
    top = max(0, min(b[1] for b in boxes) - 14)
    bot = min(h, max(b[3] for b in boxes) + 10)
    xc = np.array([(b[0] + b[2]) / 2 for b in boxes], dtype=float)
    xc = np.convolve(np.pad(xc, 2, mode="edge"), np.ones(5) / 5, mode="valid")
    out = []
    for a, cx in zip(frames, xc):
        x0 = int(max(0, min(w - win_w, round(cx - win_w / 2))))
        crop = a[top:bot, x0:x0 + win_w].copy()
        crop[np.all(crop == bg, axis=-1)] = BG[:3]
        out.append(Image.fromarray(crop))
    save_gif(out, durs, path)


def render(dst, lang):
    """用发行版二进制现场渲染 --bubble / --cards（按 lang 的界面语言）和 --hang-gif（无文字，只渲染一次）。"""
    exe = ROOT / "YukioPlayer" / ".build" / "release" / "YukioPlayer"
    if not exe.exists():
        sys.exit("没有 YukioPlayer/.build/release/YukioPlayer：先 swift build -c release，或用 --renders 指向已有的渲染图目录")
    env = dict(os.environ, YUKIO_ASSETS=str(ROOT / "YukioPlayer" / "Resources" / "Assets"), YUKIO_LANG=lang)
    jobs = [("--bubble", f"bubble-{lang}.png"), ("--cards", f"cards-{lang}.png")]
    if lang == "en":
        jobs.append(("--hang-gif", "hang.gif"))
    for flag, name in jobs:
        subprocess.run([str(exe), flag, str(dst / name)], check=True, env=env, stdout=subprocess.DEVNULL)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--renders", type=Path,
                    help="已有的 bubble-en.png / cards-en.png / bubble-zh.png / cards-zh.png / hang.gif 所在目录（默认现场渲染）")
    args = ap.parse_args()
    DOCS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        renders = args.renders or Path(tmp)
        if not args.renders:
            render(renders, "en")
            render(renders, "zh")
        grid("en", DOCS / "states-en.png")
        grid("zh", DOCS / "states-zh.png")
        desk_gif(DOCS / "desk.gif")
        # 英文界面的渲染是默认那份（README.md 用），中文界面的带 -zh 后缀（README.zh-CN.md 用）。
        panel(key_checker(renders / "bubble-en.png")).save(DOCS / "bubble.png", optimize=True)
        panel(key_checker(renders / "cards-en.png")).save(DOCS / "cards.png", optimize=True)
        panel(key_checker(renders / "bubble-zh.png")).save(DOCS / "bubble-zh.png", optimize=True)
        panel(key_checker(renders / "cards-zh.png")).save(DOCS / "cards-zh.png", optimize=True)
        drag_gif(renders / "hang.gif", DOCS / "drag.gif")
    for p in sorted(DOCS.iterdir()):
        if p.suffix in (".png", ".gif"):
            im = Image.open(p)
            print(f"{p.name:16s} {im.size[0]}×{im.size[1]}  {p.stat().st_size / 1024:7.0f} KB  {getattr(im, 'n_frames', 1)} 帧")


if __name__ == "__main__":
    main()
