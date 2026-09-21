#!/usr/bin/env python3
"""把 1 倍的动作图条超分成 2 倍，写进应用实际播放的 Resources/Assets/motion/。

用法（在 YukioPlayer 目录；要在装了 torch 的环境里跑，见下）：
  python tools/motion/upscale_motion.py                  全部动作 + 被拎起来那一帧（base/held@2x.png）
  python tools/motion/upscale_motion.py --only respond   只重做某一段（motion.json 里只换这一条），可写多次
  python tools/motion/upscale_motion.py --no-held        不重做被拎起来那一帧
  python tools/motion/upscale_motion.py --scale 1        不超分，把 1 倍图条原样搬过去（回退用，不需要 torch）

流程：先用 tools/motion/make_motion.py 在 build/motion-1x/ 生成 1 倍图条（手工标坐标的动作生成都在 1 倍下做，
不用改）；这里逐帧过一遍 Real-ESRGAN 的动画模型（放大 4 倍，再面积平均缩到 2 倍），透明通道单独超分后合回去，
线条和眼睛在视网膜屏上放大也是清楚的，而且不改人物。超过 WebP 宽度上限（16383）的长条折成几行；
motion.json 里 pixelScale=2 告诉播放器一格是 384×416 像素、仍按 192×208 点摆放。

环境：系统 Python 没有 torch，单独建一个就行（Apple 芯片走 MPS，一帧约 0.3 秒，全部约 3 分钟）：
  python3.13 -m venv ~/.cache/yukio-sr
  ~/.cache/yukio-sr/bin/pip install torch numpy pillow opencv-python-headless
  ~/.cache/yukio-sr/bin/python tools/motion/upscale_motion.py
模型 RealESRGAN_x4plus_anime_6B.pth（17.9 MB，Real-ESRGAN 官方 GitHub 发布页）第一次运行自动下载到
tools/motion/models/（已加入 .gitignore），下载后核对 SHA-256；也可以自己放进去。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'Resources' / 'Assets'
STAGING = ROOT / 'build' / 'motion-1x'
OUT = ASSETS / 'motion'
MODELS = Path(__file__).resolve().parent / 'models'
MODEL_NAME = 'RealESRGAN_x4plus_anime_6B.pth'
MODEL_URL = 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/' + MODEL_NAME
MODEL_SHA256 = 'f872d837d3c90ed2e05227bed711af5671a6fd1c9f7d7e91c911a61f155e99da'
MAX_WEBP = 16383
HELD = ('base/held.png', 'base/held@2x.png')


# ---------- 模型（RRDBNet，与 Real-ESRGAN 同构，只做推理） ----------

def build_net():
    import torch
    import torch.nn as nn
    import torch.nn.functional as Fn

    class RDB(nn.Module):
        def __init__(self, nf=64, gc=32):
            super().__init__()
            self.conv1 = nn.Conv2d(nf, gc, 3, 1, 1)
            self.conv2 = nn.Conv2d(nf + gc, gc, 3, 1, 1)
            self.conv3 = nn.Conv2d(nf + 2 * gc, gc, 3, 1, 1)
            self.conv4 = nn.Conv2d(nf + 3 * gc, gc, 3, 1, 1)
            self.conv5 = nn.Conv2d(nf + 4 * gc, nf, 3, 1, 1)
            self.lrelu = nn.LeakyReLU(0.2, True)

        def forward(self, x):
            x1 = self.lrelu(self.conv1(x))
            x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
            x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
            x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
            x5 = self.conv5(torch.cat((x, x1, x2, x3, x4), 1))
            return x5 * 0.2 + x

    class RRDB(nn.Module):
        def __init__(self, nf, gc=32):
            super().__init__()
            self.rdb1, self.rdb2, self.rdb3 = RDB(nf, gc), RDB(nf, gc), RDB(nf, gc)

        def forward(self, x):
            return self.rdb3(self.rdb2(self.rdb1(x))) * 0.2 + x

    class RRDBNet(nn.Module):
        def __init__(self, num_in_ch=3, num_out_ch=3, num_feat=64, num_block=6, num_grow_ch=32):
            super().__init__()
            self.conv_first = nn.Conv2d(num_in_ch, num_feat, 3, 1, 1)
            self.body = nn.Sequential(*[RRDB(num_feat, num_grow_ch) for _ in range(num_block)])
            self.conv_body = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
            self.conv_up1 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
            self.conv_up2 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
            self.conv_hr = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
            self.conv_last = nn.Conv2d(num_feat, num_out_ch, 3, 1, 1)
            self.lrelu = nn.LeakyReLU(0.2, True)

        def forward(self, x):
            feat = self.conv_first(x)
            feat = feat + self.conv_body(self.body(feat))
            feat = self.lrelu(self.conv_up1(Fn.interpolate(feat, scale_factor=2, mode='nearest')))
            feat = self.lrelu(self.conv_up2(Fn.interpolate(feat, scale_factor=2, mode='nearest')))
            return self.conv_last(self.lrelu(self.conv_hr(feat)))

    return RRDBNet()


def model_path() -> Path:
    MODELS.mkdir(parents=True, exist_ok=True)
    path = MODELS / MODEL_NAME
    if not path.exists():
        print('下载模型', MODEL_URL)
        tmp = path.with_suffix('.part')
        urllib.request.urlretrieve(MODEL_URL, tmp)
        tmp.rename(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != MODEL_SHA256:
        raise SystemExit(f'{path} 的 SHA-256 不对：{digest}，删掉重新下载')
    return path


class Upscaler:
    def __init__(self):
        import torch
        self.torch = torch
        self.device = 'mps' if torch.backends.mps.is_available() else ('cuda' if torch.cuda.is_available() else 'cpu')
        sd = torch.load(model_path(), map_location='cpu', weights_only=True)
        sd = sd.get('params_ema', sd.get('params', sd))
        self.net = build_net()
        self.net.load_state_dict(sd, strict=True)
        self.net.eval().to(self.device)
        print('超分设备', self.device)

    def run(self, images: list[np.ndarray]) -> list[np.ndarray]:
        """若干张 H×W×3（0–1）→ 4 倍大的同样张数。"""
        torch = self.torch
        with torch.no_grad():
            t = torch.from_numpy(np.stack([im.transpose(2, 0, 1) for im in images])).float().to(self.device)
            out = self.net(t).clamp(0, 1).cpu().numpy()
        return [o.transpose(1, 2, 0) for o in out]


def bleed(rgb: np.ndarray, known: np.ndarray, iters: int = 16) -> np.ndarray:
    """透明处填成最近的不透明颜色（3×3 邻域平均一圈圈往外扩），网络看到的边缘就是连续的，不会把黑边当线条。"""
    col = rgb * known[..., None]
    w = known.astype(np.float32).copy()
    k = np.ones((3, 3), np.float32)
    for _ in range(iters):
        cs = cv2.filter2D(col, -1, k, borderType=cv2.BORDER_REPLICATE)
        ws = cv2.filter2D(w, -1, k, borderType=cv2.BORDER_REPLICATE)
        col = np.where((w[..., None] == 0) & (ws[..., None] > 0), cs / np.maximum(ws[..., None], 1e-6), col)
        w = np.where((w == 0) & (ws > 0), 1, w)
    return col


def upscale_rgba(up: Upscaler, rgba8: np.ndarray, scale: int) -> np.ndarray:
    """一帧 RGBA（8 位）→ scale 倍的 RGBA。颜色与透明度各自过一遍网络（透明度当灰度图），再合起来。"""
    a = rgba8[..., 3].astype(np.float32) / 255
    rgb = bleed(rgba8[..., :3].astype(np.float32) / 255, a > 0.02)
    hr_rgb, hr_a3 = up.run([rgb, np.repeat(a[..., None], 3, axis=2)])
    hr_a = hr_a3.mean(axis=2)
    if scale != 4:
        f = scale / 4
        hr_rgb = cv2.resize(hr_rgb, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
        hr_a = cv2.resize(hr_a, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    out = np.concatenate([np.clip(hr_rgb, 0, 1), np.clip(hr_a, 0, 1)[..., None]], axis=2)
    return np.round(out * 255).astype(np.uint8)


def plain_rgba(rgba8: np.ndarray, scale: int) -> np.ndarray:
    if scale == 1:
        return rgba8
    return np.asarray(Image.fromarray(rgba8).resize((rgba8.shape[1] * scale, rgba8.shape[0] * scale), Image.LANCZOS))


# ---------- 图条读写 ----------

def read_strip(path: Path, fw: int, fh: int) -> list[np.ndarray]:
    im = Image.open(path).convert('RGBA')
    if im.height != fh or im.width % fw:
        raise SystemExit(f'{path}: 1 倍图条应是 {fw}×{fh} 的一行，实际 {im.width}×{im.height}')
    return [np.asarray(im.crop((i * fw, 0, (i + 1) * fw, fh))).copy() for i in range(im.width // fw)]


def pack(frames: list[np.ndarray]) -> Image.Image:
    """按行优先排进网格：一行放不下 WebP 宽度上限时折行。"""
    fh, fw = frames[0].shape[:2]
    per_row = max(1, min(len(frames), MAX_WEBP // fw))
    rows = math.ceil(len(frames) / per_row)
    sheet = Image.new('RGBA', (fw * per_row, fh * rows), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        sheet.paste(Image.fromarray(f), ((i % per_row) * fw, (i // per_row) * fh))
    return sheet


def save_webp(im: Image.Image, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, 'WEBP', lossless=True, quality=100, method=6)


def convert(frames: list[np.ndarray], scale: int, up) -> list[np.ndarray]:
    return [upscale_rgba(up, f, scale) if up else plain_rgba(f, scale) for f in frames]


# ---------- 主流程 ----------

def process_states(entries: list[dict], scale: int, up) -> list[dict]:
    done = []
    for e in entries:
        t0 = time.time()
        frames = read_strip(STAGING / e['asset'], e['frameWidth'], e['frameHeight'])
        big = convert(frames, scale, up)
        sheet = pack(big)
        save_webp(sheet, OUT / e['asset'])
        new = dict(e)
        new['pixelScale'] = scale
        done.append(new)
        print(f"{e['id']:18s} {len(frames):3d} 帧 → {sheet.width}×{sheet.height}  {time.time() - t0:5.1f}s")
    return done


def process_held(scale: int, up):
    src, dst = (ASSETS / HELD[0]), (ASSETS / HELD[1])
    frame = np.asarray(Image.open(src).convert('RGBA')).copy()
    big = convert([frame], scale, up)[0]
    dst.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(big).save(dst, 'PNG', optimize=True)
    path = ASSETS / 'base' / 'base-animations.json'
    text = path.read_text(encoding='utf-8')
    data = json.loads(text)
    for a in data['animations']:
        if a['id'] == 'held':
            a['asset'] = Path(HELD[1]).name if scale != 1 else Path(HELD[0]).name
            if scale != 1:
                a['pixelScale'] = scale
            else:
                a.pop('pixelScale', None)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + ('\n' if text.endswith('\n') else ''),
                    encoding='utf-8')
    print(f"held → {big.shape[1]}×{big.shape[0]}，base-animations.json 已指向 {HELD[1] if scale != 1 else HELD[0]}")


def write_motion_json(entries: list[dict], scale: int, merge: bool):
    path = OUT / 'motion.json'
    src = json.loads((STAGING / 'motion.json').read_text(encoding='utf-8'))
    if merge and path.exists():
        current = json.loads(path.read_text(encoding='utf-8'))
        by_id = {s['id']: s for s in current['states']}
        for e in entries:
            by_id[e['id']] = e
        states = list(by_id.values())
    else:
        states = entries
    note = src.get('note', '')
    if scale != 1:
        note += f' 图条是 {scale} 倍分辨率（pixelScale={scale}，tools/motion/upscale_motion.py 用 Real-ESRGAN 动画模型超分），太长的折成几行。'
    path.write_text(json.dumps({
        'version': 3,
        'generator': 'tools/motion/make_motion.py → tools/motion/upscale_motion.py',
        'note': note,
        'states': states,
    }, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('写入', path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', action='append', help='只处理这些动作 id')
    ap.add_argument('--no-held', action='store_true', help='不重做被拎起来那一帧')
    ap.add_argument('--scale', type=int, default=2, choices=[1, 2, 4], help='输出倍率（默认 2）')
    args = ap.parse_args()
    if not (STAGING / 'motion.json').exists():
        raise SystemExit(f'先运行 tools/motion/make_motion.py 生成 1 倍图条（{STAGING}）')
    src = json.loads((STAGING / 'motion.json').read_text(encoding='utf-8'))
    entries = src['states']
    if args.only:
        missing = set(args.only) - {e['id'] for e in entries}
        if missing:
            raise SystemExit(f'没有这些动作：{sorted(missing)}')
        entries = [e for e in entries if e['id'] in set(args.only)]
    up = Upscaler() if args.scale != 1 else None
    t0 = time.time()
    done = process_states(entries, args.scale, up)
    write_motion_json(done, args.scale, merge=bool(args.only))
    if not args.no_held:
        process_held(args.scale, up)
    print(f'完成，共 {time.time() - t0:.0f}s')


if __name__ == '__main__':
    main()
