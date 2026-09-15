#!/usr/bin/env python3
"""生成雪绪的小幅动作图条（Resources/Assets/motion/ 与 motion.json）。

用法（在 YukioPlayer 目录）：
  python3 tools/motion/make_motion.py                  生成全部动作
  python3 tools/motion/make_motion.py --eyes out.png   只画眨眼检测图（检查眼睛框）
  python3 tools/motion/make_motion.py --sheet 目录      每个动作画一张放大对照图（检查动的部位与幅度）
  python3 tools/motion/make_motion.py --html out.html  新旧动作并排播放的预览页

需要 numpy、opencv-python、Pillow。每个动作只用一张已确认的底图：桌椅与身体逐像素不动，
手、笔、头、眼按时间曲线做 2 像素以内的平滑变形；眨眼盖在变形之前，眼皮跟着头动。
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from motionlib import (H, W, Frame, Rotate, Shift, assemble, detect_eye, ease, load_frame,  # noqa: E402
                       max_step, paint_blink, render, save_strip, scalar, to_image, vec)

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'Resources' / 'Assets'
OUT = ASSETS / 'motion'

BLINK = [(0.55, 50), (1.0, 70), (0.45, 80)]          # (闭合程度, 毫秒)：快速闭上、稍停、睁开
SLOW_BLINK = [(0.5, 70), (1.0, 110), (0.5, 110)]     # 思考、沮丧：慢一点


@dataclass
class State:
    id: str
    plate: tuple                   # (相对 Assets 的路径, 帧号)
    eyes: list                     # 两只眼的搜索框 (x0, y0, x1, y1)，1 倍坐标
    period: float                  # 动作一轮的秒数（period × fps 须为整数）
    cycles: int                    # 时间轴重复几轮；各轮相同的帧只存一份
    fps: int
    blinks: list                   # 眨眼时刻（动作时间，秒）
    handles: object                # eyes -> 位移把手列表
    blink: list = field(default_factory=lambda: BLINK)
    intro: list = field(default_factory=list)   # [(路径, 帧号, 毫秒)]：先播一次，之后循环


def irises(eyes, motion, sigma=(2.2, 2.0)):
    """眼珠（连同睫毛）小幅移动：看向别处。"""
    return [Shift(e.center, sigma, motion, e.box, feather=1.5) for e in eyes]


def scaled(motion, kx=1.0, ky=1.0):
    return lambda t: (motion(t)[0] * kx, motion(t)[1] * ky)


# ---------- 各动作 ----------

def thinking(eyes):
    # 托腮：头绕托着下巴的手慢慢歪一点又回来，眼睛偶尔往上看。幅度都很小。
    tilt = scalar([(0, 0), (1.2, 0), (2.6, 1.1), (4.4, 1.1), (5.8, 0)], 7.0)
    gaze = vec([(0, 0, 0), (1.6, 0, 0), (2.2, -0.55, -0.35), (3.8, -0.55, -0.35), (4.4, 0, 0)], 7.0)
    return [Rotate((96, 88), (88, 50), (26, 24), tilt, region=(50, 14, 134, 86), feather=5),
            *irises(eyes, gaze)]


def read_file(eyes):
    # 读书：视线和指头沿一行从左到右，读完快速回到行首；头跟着微微转。
    line = vec([(0, -0.7, 0), (2.0, 0.7, 0.15)], 2.5)
    return [Shift((92, 50), (24, 22), scaled(line, 0.35, 0), region=(54, 14, 130, 84), feather=5),
            *irises(eyes, scaled(line, 0.55, 0.3)),
            Shift((71, 110), (7, 5), line, region=(59, 101, 84, 119), feather=2.5)]


def view_image(eyes):
    # 放大镜：拿镜子的手沿小椭圆慢慢移动，视线跟着镜片。
    loop = lambda t: (1.1 * math.cos(2 * math.pi * t / 3.0), 0.7 * math.sin(2 * math.pi * t / 3.0))
    return [Shift((74, 97), (12, 10), loop, region=(50, 83, 97, 110), feather=4),
            *irises(eyes, scaled(loop, 0.35, 0.3))]


def write_file(eyes):
    # 写字：握笔的手带着笔尖一边小幅上下抖一边往右写，写完一行快速回到左边。
    P, END = 2.4, 2.0

    def hand(t):
        t %= P
        if t < END:
            u = t / END
            return (1.6 * u, 0.35 * math.sin(math.pi * u) * math.sin(2 * math.pi * 3.0 * t))
        return (1.6 * (1 - ease((t - END) / (P - END))), 0.0)

    def tip(t):
        t %= P
        if t >= END:
            return (0.0, 0.0)
        u = t / END
        return (0.0, 0.25 * math.sin(math.pi * u) * math.sin(2 * math.pi * 3.0 * t + 0.8))

    return [Shift((70, 108), (10, 11), hand, region=(55, 88, 92, 120), feather=3),
            Shift((80, 118), (3.5, 3.5), tip, region=(73, 111, 87, 123), feather=1.5),
            Shift((92, 50), (24, 22), scaled(hand, 0.2, 0.25), region=(54, 14, 130, 84), feather=5),
            *irises(eyes, scaled(hand, 0.35, 0.2))]


def verify(eyes):
    # 对照检查：头在左右两份文件之间转来转去（五官比轮廓多移一点，看起来像转头），手按着正在看的那份。
    look = vec([(0, -1.0, 0), (1.3, -1.0, 0), (1.9, 1.0, 0), (3.0, 1.0, 0)], 3.6)
    return [Shift((88, 50), (26, 24), look, region=(50, 14, 130, 86), feather=5),
            Shift((90, 73), (14, 7), scaled(look, 0.5, 0), region=(70, 63, 110, 84), feather=3),
            *irises(eyes, scaled(look, 0.5, 0)),
            Shift((68, 111), (6, 5), lambda t: (0, 0.45 * max(0.0, -look(t)[0])), region=(58, 103, 80, 118), feather=2),
            Shift((111, 111), (6, 5), lambda t: (0, 0.45 * max(0.0, look(t)[0])), region=(100, 103, 122, 118), feather=2)]


def read_web(eyes):
    # 平板：点着屏幕的手指往上划两下，停一会儿（浏览翻页）；眼睛跟着往下扫。
    swipe = vec([(0, 0, 0), (0.5, 0, 0), (0.78, -0.4, -1.1), (1.25, 0, 0), (1.45, 0, 0),
                 (1.73, -0.4, -1.1), (2.2, 0, 0)], 2.6)
    return [Shift((87, 107), (8, 6), swipe, region=(73, 99, 99, 116), feather=2.5),
            *irises(eyes, scaled(swipe, 0.2, -0.2))]


def default_work(eyes):
    # 敲键盘：左右手交替、节奏不齐地轻敲，停一小会儿再敲；眼睛在屏幕上左右扫。
    P = 2.4

    def tapper(times, depth=0.8):
        def f(t):
            t %= P
            d = 0.0
            for s in times:
                u = t - s
                if 0 <= u < 0.04:
                    d = max(d, ease(u / 0.04))
                elif 0.04 <= u < 0.15:
                    d = max(d, 1 - ease((u - 0.04) / 0.11))
            return (0.0, depth * d)
        return f

    scan = vec([(0, -0.3, 0), (1.2, 0.3, 0)], P)
    return [Shift((85, 108), (6, 5), tapper([0.00, 0.27, 0.80, 1.07, 1.60]), region=(75, 100, 95, 117), feather=2),
            Shift((112, 108), (6, 5), tapper([0.13, 0.53, 0.93, 1.33, 1.47]), region=(102, 100, 122, 117), feather=2),
            *irises(eyes, scan)]


def idle(eyes):
    # 空闲：偶尔向左、向右看一看（轮廓、五官、眼珠依次多移一点，像是转头），头跟着微微歪。
    look = vec([(0, 0, 0), (2.6, 0, 0), (3.3, -1.0, 0), (5.0, -1.0, 0), (5.7, 0, 0),
                (8.4, 0, 0), (9.1, 1.0, 0), (10.6, 1.0, 0), (11.3, 0, 0)], 12.0)
    return [Rotate((93, 80), (93, 44), (26, 24), lambda t: 0.8 * look(t)[0], region=(54, 8, 134, 80), feather=5),
            Shift((93, 44), (26, 24), look, region=(54, 8, 134, 80), feather=5),
            Shift((93, 60), (14, 8), scaled(look, 0.5, 0), region=(72, 49, 114, 73), feather=3),
            *irises(eyes, scaled(look, 0.6, 0))]


def failed(eyes):
    # 沮丧：垂眼停住后，慢慢叹一口气（头往下沉半个像素再回来），慢慢眨眼。
    sigh = vec([(0, 0, 0), (1.5, 0, 0), (2.7, 0, 0.55), (4.4, 0, 0)], 5.5)
    return [Shift((93, 46), (26, 24), sigh, region=(54, 8, 134, 80), feather=5)]


def static(eyes):
    return []


STATES = [
    State('thinking', ('activities/thinking.webp', 0), [(76, 63, 88, 77), (95, 63, 107, 77)],
          7.0, 1, 8, [0.9, 4.9], thinking, blink=SLOW_BLINK),
    State('read_file', ('activities/read_file.webp', 0), [(77, 64, 89, 78), (97, 64, 109, 78)],
          2.5, 2, 12, [4.55], read_file),
    State('view_image', ('activities/view_image.webp', 0), [(77, 64, 89, 78), (97, 64, 109, 78)],
          3.0, 2, 12, [1.9, 5.2], view_image),
    State('write_file', ('activities/write_file.webp', 0), [(76, 64, 88, 78), (97, 64, 109, 78)],
          2.4, 2, 20, [4.45], write_file),
    State('verify', ('activities/verify.webp', 0), [(74, 66, 87, 79), (93, 68, 108, 79)],
          3.6, 1, 15, [1.6], verify),
    State('read_web', ('activities/read_web.webp', 0), [(78, 66, 90, 77), (99, 66, 111, 77)],
          2.6, 2, 15, [3.9], read_web),
    State('respond', ('activities/respond.webp', 3), [(77, 65, 89, 79), (97, 65, 109, 79)],
          4.0, 1, 15, [1.6], static,
          intro=[('activities/respond.webp', 0, 1200), ('activities/respond.webp', 1, 220),
                 ('activities/respond.webp', 2, 220)]),
    State('default_work', ('activities/computer-desk.png', 0), [(92, 62, 102, 75), (110, 57, 122, 72)],
          2.4, 2, 15, [4.15], default_work),
    State('idle', ('base/idle.webp', 0), [(78, 54, 90, 68), (97, 50, 109, 64)],
          12.0, 1, 12, [1.3, 5.2, 7.3, 10.9], idle),
    State('failed', ('base/failed.webp', 3), [(78, 56, 91, 68), (98, 52, 110, 64)],
          5.5, 1, 10, [0.9], failed, blink=SLOW_BLINK,
          intro=[('base/failed.webp', 0, 240), ('base/failed.webp', 2, 180)]),
]


# ---------- 生成 ----------

def plate_and_eyes(st: State):
    plate = load_frame(str(ASSETS / st.plate[0]), st.plate[1])
    return plate, [detect_eye(plate, b) for b in st.eyes]


def build(st: State):
    plate, eyes = plate_and_eyes(st)
    handles = st.handles(eyes)
    per = int(round(st.period * st.fps))
    assert abs(per - st.period * st.fps) < 1e-6, f'{st.id}: period × fps 须为整数'
    cache = {}

    def src(a):
        k = round(a, 3)
        if k not in cache:
            cache[k] = paint_blink(plate, eyes, a)
        return cache[k]

    intro = [Frame(load_frame(str(ASSETS / p), i), ms) for p, i, ms in st.intro]
    loop, pending, worst = [], sorted(st.blinks), 0.0
    for k in range(per * st.cycles):
        phase = (k % per) / st.fps
        m = k / st.fps
        while pending and pending[0] <= m + 1e-9:
            pending.pop(0)
            for a, ms in st.blink:
                loop.append(Frame(render(src(a), handles, phase), ms))
        loop.append(Frame(render(src(0), handles, phase), 1000 / st.fps))
        worst = max(worst, max_step(handles, phase, ((k + 1) % per) / st.fps))
    return plate, eyes, handles, intro, loop, worst


def combine(intro, loop):
    """先播一次的帧和循环帧放进同一条图条；返回 (帧, 序列, 时长, 循环起点)。"""
    iu, iseq, idur = assemble(intro) if intro else ([], [], [])
    lu, lseq, ldur = assemble(loop)
    return iu + lu, iseq + [i + len(iu) for i in lseq], idur + ldur, len(iseq)


def generate():
    OUT.mkdir(exist_ok=True)
    entries = []
    for st in STATES:
        plate, eyes, handles, intro, loop, worst = build(st)
        uniques, seq, dur, loop_start = combine(intro, loop)
        save_strip(uniques, str(OUT / f'{st.id}.webp'))
        # 桌腿、椅子一带（y ≥ 126）必须与底图逐像素相同：不许抽搐。
        base = np.round(plate * 255)
        moved = max(int((np.abs(np.round(f.image * 255) - base)[126:].max(axis=2) > 0).sum()) for f in loop)
        entries.append({'id': st.id, 'asset': f'{st.id}.webp', 'frameWidth': W, 'frameHeight': H,
                        'sequence': seq, 'durationsMs': dur, 'loop': True, 'loopStart': loop_start})
        cycle = sum(dur[loop_start:])
        print(f'{st.id:13s} 不重复帧 {len(uniques):3d}  步数 {len(seq):3d}  一轮 {cycle / 1000:5.2f}s  '
              f'相邻帧最大位移 {worst:.2f}px  桌腿区变化像素 {moved}')
        if moved:
            raise SystemExit(f'{st.id}: 桌腿区被改动了')
    (OUT / 'motion.json').write_text(json.dumps({
        'version': 1,
        'generator': 'tools/motion/make_motion.py',
        'note': '每个动作只用一张底图，局部平滑变形生成；桌椅与身体逐像素不动。',
        'states': entries,
    }, ensure_ascii=False, indent=1) + '\n')
    print('写入', OUT / 'motion.json')


# ---------- 检查图 ----------

def eyes_sheet(path):
    """每个底图的两只眼：检测结果（红=睫毛线顶，绿=眼睛下缘）、半闭、全闭，放大 8 倍。"""
    tiles = []
    for st in STATES:
        plate, eyes = plate_and_eyes(st)
        x0 = min(b[0] for b in st.eyes) - 3
        y0 = min(b[1] for b in st.eyes) - 4
        x1 = max(b[2] for b in st.eyes) + 3
        y1 = max(b[3] for b in st.eyes) + 3
        row = []
        for a in (0.0, 0.5, 1.0):
            im = Image.new('RGBA', (W, H), (255, 255, 255, 255))
            im.alpha_composite(to_image(paint_blink(plate, eyes, a)))
            im = im.crop((x0, y0, x1, y1)).resize(((x1 - x0) * 8, (y1 - y0) * 8), Image.NEAREST)
            if a == 0:
                d = ImageDraw.Draw(im)
                for e in eyes:
                    bx0, by0, bx1, by1 = e.box
                    d.rectangle([(bx0 - x0) * 8, (by0 - y0) * 8, (bx1 - x0) * 8 - 1, (by1 - y0) * 8 - 1], outline=(0, 120, 255))
                    for x, (top, lash, bottom) in e.columns.items():
                        d.rectangle([(x - x0) * 8 + 3, (top - y0) * 8 + 3, (x - x0) * 8 + 5, (top - y0) * 8 + 5], fill=(255, 0, 0))
                        d.rectangle([(x - x0) * 8 + 3, (bottom - 1 - y0) * 8 + 3, (x - x0) * 8 + 5, (bottom - 1 - y0) * 8 + 5], fill=(0, 200, 0))
            row.append(im)
        tiles.append((st.id, row))
    tw = max(sum(i.width for i in r) + 20 for _, r in tiles)
    th = sum(r[0].height + 18 for _, r in tiles)
    sheet = Image.new('RGBA', (tw, th), (230, 230, 230, 255))
    d = ImageDraw.Draw(sheet)
    y = 0
    for name, row in tiles:
        d.text((4, y + 2), name, fill=(0, 0, 0))
        x = 0
        for im in row:
            sheet.alpha_composite(im, (x, y + 16))
            x += im.width + 10
        y += row[0].height + 18
    sheet.save(path)


def motion_sheets(folder):
    """每个动作：六个相位的放大局部（上）与相对底图的差异（下，红色越深变化越大）。"""
    Path(folder).mkdir(parents=True, exist_ok=True)
    for st in STATES:
        plate, eyes = plate_and_eyes(st)
        handles = st.handles(eyes)
        if not handles:
            continue
        wsum = sum(h.w for h in handles)
        ys, xs = np.nonzero(wsum > 0)
        x0, x1 = max(xs.min() - 4, 0), min(xs.max() + 5, W)
        y0, y1 = max(ys.min() - 4, 0), min(ys.max() + 5, H)
        z = 4
        tiles = []
        for j in range(6):
            t = st.period * j / 6
            f = render(plate, handles, t)
            im = Image.new('RGBA', (W, H), (255, 255, 255, 255))
            im.alpha_composite(to_image(f))
            crop = im.crop((x0, y0, x1, y1)).resize(((x1 - x0) * z, (y1 - y0) * z), Image.NEAREST)
            diff = np.abs(f - plate).max(axis=2)[y0:y1, x0:x1]
            heat = np.full((y1 - y0, x1 - x0, 3), 255, np.uint8)
            k = np.clip(diff * 4, 0, 1)
            heat[..., 1] = (255 * (1 - k)).astype(np.uint8)
            heat[..., 2] = (255 * (1 - k)).astype(np.uint8)
            heat = Image.fromarray(heat).resize(((x1 - x0) * z, (y1 - y0) * z), Image.NEAREST).convert('RGBA')
            tiles.append((f't={t:.2f}s', crop, heat))
        cw, ch = tiles[0][1].size
        sheet = Image.new('RGBA', (len(tiles) * (cw + 8), 2 * ch + 30), (230, 230, 230, 255))
        d = ImageDraw.Draw(sheet)
        for i, (label, crop, heat) in enumerate(tiles):
            d.text((i * (cw + 8) + 2, 1), f'{st.id} {label}', fill=(0, 0, 0))
            sheet.alpha_composite(crop, (i * (cw + 8), 14))
            sheet.alpha_composite(heat, (i * (cw + 8), 16 + ch))
        sheet.save(Path(folder) / f'{st.id}.png')


def html_preview(path):
    """新旧动作并排播放（按图条的序列与时长，放大 2 倍，线性插值，和桌面上一样）。"""
    def data_uri(p):
        return 'data:image/webp;base64,' + base64.b64encode(Path(p).read_bytes()).decode()

    acts = {s['id']: s for s in json.loads((ASSETS / 'activities/activities.json').read_text())['states']}
    base = {a['id']: a for a in json.loads((ASSETS / 'base/base-animations.json').read_text())['animations']}
    motion = {s['id']: s for s in json.loads((OUT / 'motion.json').read_text())['states']}
    items = []
    for st in STATES:
        if st.id in acts:
            a = acts[st.id]
            old = dict(src=data_uri(ASSETS / 'activities' / a['asset']), seq=a['sequence'], dur=a['durationsMs'],
                       loop=a['loop'], loopStart=0)
        elif st.id == 'idle':
            b = base['idle']
            old = dict(src=data_uri(ASSETS / 'base' / b['asset']), seq=list(range(b['frameCount'])),
                       dur=b['nativeDurationsMs'], loop=True, loopStart=0)
        else:
            old = dict(src=data_uri(ASSETS / 'base/failed.webp'), seq=[0, 2, 3], dur=[240, 180, 1000],
                       loop=False, loopStart=0)
        m = motion[st.id]
        new = dict(src=data_uri(OUT / m['asset']), seq=m['sequence'], dur=m['durationsMs'], loop=True,
                   loopStart=m['loopStart'])
        items.append(dict(id=st.id, old=old, new=new))
    page = HTML_TEMPLATE.replace('__ITEMS__', json.dumps(items))
    Path(path).write_text(page)


HTML_TEMPLATE = """<!doctype html><meta charset="utf-8"><title>雪绪动作预览</title>
<style>
body{margin:0;padding:16px;font:14px -apple-system,system-ui,sans-serif;background:#eef1f5;color:#1f2a44}
h1{font-size:18px;margin:0 0 4px} p{margin:0 0 14px;color:#56627a}
.grid{display:flex;flex-wrap:wrap;gap:14px}
.card{background:#fff;border-radius:10px;padding:10px 12px;box-shadow:0 1px 2px rgba(0,0,0,.08)}
.card h2{font-size:13px;margin:0 0 6px}
.pair{display:flex;gap:8px}.pair div{text-align:center;font-size:11px;color:#6b7690}
canvas{width:192px;height:208px;background:repeating-conic-gradient(#f4f4f4 0 25%,#fff 0 50%) 0 0/16px 16px;border-radius:6px}
</style>
<h1>雪绪 · 新旧动作对照</h1><p>左：现在的动作；右：新的小幅动作。按图条的真实时长播放，放大显示和桌面一致。</p>
<div class="grid" id="g"></div>
<script>
const items = __ITEMS__;
const players = [];
for (const it of items) {
  const card = document.createElement('div'); card.className = 'card';
  card.innerHTML = `<h2>${it.id}</h2><div class="pair"><div><canvas width="384" height="416"></canvas><br>现在</div><div><canvas width="384" height="416"></canvas><br>新</div></div>`;
  document.getElementById('g').appendChild(card);
  const cs = card.querySelectorAll('canvas');
  for (const [k, spec] of [[0, it.old], [1, it.new]]) {
    const img = new Image(); img.src = spec.src;
    players.push({ctx: cs[k].getContext('2d'), img, spec, step: 0, at: performance.now(), done: false});
  }
}
function frame(now) {
  for (const p of players) {
    const s = p.spec;
    while (!p.done && now - p.at >= s.dur[p.step]) {
      p.at += s.dur[p.step];
      if (p.step + 1 < s.seq.length) p.step++;
      else if (s.loop) p.step = s.loopStart;
      else p.done = true;
    }
    if (!p.img.complete) continue;
    p.ctx.imageSmoothingEnabled = true;
    p.ctx.clearRect(0, 0, 384, 416);
    p.ctx.drawImage(p.img, s.seq[p.step] * 192, 0, 192, 208, 0, 0, 384, 416);
  }
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
</script>
"""


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--eyes')
    ap.add_argument('--sheet')
    ap.add_argument('--html')
    args = ap.parse_args()
    if args.eyes:
        eyes_sheet(args.eyes)
    elif args.sheet:
        motion_sheets(args.sheet)
    elif args.html:
        html_preview(args.html)
    else:
        generate()
