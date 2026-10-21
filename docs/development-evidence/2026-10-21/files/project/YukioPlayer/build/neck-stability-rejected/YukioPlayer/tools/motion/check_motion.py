#!/usr/bin/env python3
"""检查头颈固定、开场和循环接缝，并用实际发布图集制作修复前后预览。

先备份 Resources/Assets/motion，再运行两步生成脚本，最后：
  python tools/motion/check_motion.py --before build/neck-stability/before --out build/neck-stability
"""
from __future__ import annotations
import argparse
import json
import shutil
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw
import make_motion as m


def read_assets(folder):
    specs = json.loads((folder / 'motion.json').read_text())['states']
    result = {}
    for spec in specs:
        path = folder / spec['asset']
        im = Image.open(path).convert('RGBA')
        scale = spec.get('pixelScale', 1)
        w, h = spec['frameWidth'] * scale, spec['frameHeight'] * scale
        cols = im.width // w
        assert im.width % w == 0 and im.height % h == 0
        frames = [np.asarray(im.crop((i % cols * w, i // cols * h, (i % cols + 1) * w,
                                     (i // cols + 1) * h))).copy() for i in range(max(spec['sequence']) + 1)]
        for frame in frames:
            frame[frame[..., 3] == 0] = 0  # WebP 不保证透明像素的不可见 RGB。
        assert len(spec['sequence']) == len(spec['durationsMs'])
        assert all(d > 0 for d in spec['durationsMs'])
        result[spec['id']] = (spec, frames, path)
    return result


def overview(before, after, folder):
    """八秒动图速览；完整时长与其余状态在 HTML 中查看。"""
    names = ('read_file', 'write_file', 'view_image')
    eyes = {}
    for side, collection in enumerate((before, after)):
        for name in names:
            spec, _, path = collection[name]
            if spec.get('blink'):
                eyes[side, name] = Image.open(path.parent / spec['blink']['asset']).convert('RGBA')
    images = []
    for ms in range(0, 8000, 50):
        canvas = Image.new('RGB', (1152, 252), '#eef1f5')
        draw = ImageDraw.Draw(canvas)
        for col, name in enumerate(names):
            draw.text((col * 384 + 8, 6), name, fill='#223047')
            for side, collection in enumerate((before, after)):
                spec, frames, _ = collection[name]
                duration = spec['durationsMs']
                intro = sum(duration[:spec['loopStart']])
                total = sum(duration)
                t = ms if ms < total else intro + (ms - intro) % (total - intro)
                k = 0
                while k < len(duration) - 1 and t >= duration[k]:
                    t -= duration[k]
                    k += 1
                scale = spec.get('pixelScale', 1)
                im = Image.fromarray(frames[spec['sequence'][k]])
                if spec.get('blink'):
                    b = spec['blink']
                    level = blink_level(b, ms)
                    if level:
                        sheet = eyes[side, name]
                        patch = b['frames'][spec['sequence'][k]][level - 1]
                        cols = sheet.width // b['width']
                        x, y = patch % cols * b['width'], patch // cols * b['height']
                        im.paste(sheet.crop((x, y, x + b['width'], y + b['height'])), (b['x'], b['y']))
                im = im.crop((48 * scale, 14 * scale, 144 * scale, 118 * scale)).resize((192, 208), Image.Resampling.LANCZOS)
                x = col * 384 + side * 192
                draw.text((x + 8, 24), 'BEFORE' if side == 0 else 'AFTER', fill='#223047')
                canvas.paste(im, (x, 44), im)
        images.append(canvas)
    # 共用调色板，避免逐帧重新量化造成固定区域闪色。
    samples = Image.new('RGB', (1152, 252 * 8))
    for i in range(8):
        samples.paste(images[i * 20], (0, i * 252))
    palette = samples.quantize(colors=256)
    frames = [im.quantize(palette=palette, dither=Image.Dither.NONE) for im in images]
    frames[0].save(folder / 'comparison.gif', save_all=True, append_images=frames[1:],
                   duration=50, loop=0, optimize=False, disposal=1)


def blink_level(b, now):
    """复现 BlinkClock.swift，从同一个种子开始的独立眼皮。"""
    rng = b['seed']

    def random(low, high):
        nonlocal rng
        rng = (1664525 * rng + 1013904223) % 2**32
        return low + (high - low) * rng / 2**32

    end = 0
    while True:
        start = end + random(2800, 7000)
        duration = random(180, 260)
        events = [(start, duration)]
        if random(0, 1) < 0.125:
            events.append((start + duration + random(100, 180), random(180, 260)))
        for start, duration in events:
            if now < start:
                return 0
            if now < start + duration:
                u = (now - start) / duration
                amount = m.ease(u / .36) if u < .36 else 1 if u < .52 else 1 - m.ease((u - .52) / .48)
                return int(amount * b['levels'] + .5)
        end = events[-1][0] + events[-1][1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--before', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--after', type=Path, default=m.ASSETS / 'motion')
    ap.add_argument('--gif', action='store_true', help='同时输出读书、写字、看图的八秒对比动图')
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    before, after = read_assets(args.before), read_assets(args.after)
    rows, items = [], []
    for st in m.STATES:
        scene, intro, loop, worst = m.build(st)
        frames, seq, dur, start = m.combine(intro, loop)
        spec, actual, path = after[st.id]
        assert (seq, dur, start) == (spec['sequence'], spec['durationsMs'], spec['loopStart']), st.id
        small = [np.asarray(m.to_image(f)) for f in frames]
        # 固定头颈（站姿更靠上）。眼睛和扫过脸前的道具是允许变化的部分。
        mask = np.zeros((m.H, m.W), np.uint8)
        top = 76 if st.id in ('idle', 'failed') else 96
        mask[:top] = 1
        eye_mask = np.zeros_like(mask)
        for e in scene.eyes:
            x0, y0, x1, y1 = e.box
            eye_mask[max(0,y0-3):y1+3, max(0,x0-3):x1+3] = 1
        mask[eye_mask > 0] = 0
        # 道具既包括被挖走的原位置，也包括整个时间轴中实际覆盖的位置。
        prop = scene.hole.copy()
        times = [-st.intro + k / st.intro_fps for k in range(round(st.intro * st.intro_fps))]
        times += [k / st.fps for k in range(round(st.period * st.fps))]
        for t in times:
            for p in scene.rig.parts + scene.rig.behind:
                prop = np.maximum(prop, p.layer(scene.plate, t)[..., 3])
        prop = cv2.dilate((prop > 0).astype(np.uint8), np.ones((3, 3), np.uint8))
        mask[prop > 0] = 0
        ref = small[seq[start]]
        changed = max(int(np.any(f != ref, axis=2)[mask > 0].sum()) for f in small)
        assert changed == 0, (st.id, '头颈变形', changed)
        # 连续时间曲线在循环边界以及开场→循环处必须没有不连续。
        epsilon = 1e-6
        seam = scene.step(st.period - epsilon, 0)
        intro_seam = scene.step(-epsilon, 0) if st.intro else 0
        assert seam < 1e-3 and intro_seam < 1e-3, (st.id, seam, intro_seam)
        loop_step = scene.step(st.period - 1 / st.fps, 0)
        assert loop_step <= worst + 1e-6
        assert np.array_equal(scene.frame(0), scene.frame(st.period)), st.id
        # 2 倍模型在动作边缘有抗锯齿过渡；检查离眼睛和道具至少 3 点的固定区域。
        fixed = cv2.erode(mask, np.ones((7, 7), np.uint8))
        scale = spec.get('pixelScale', 1)
        fixed = np.repeat(np.repeat(fixed, scale, 0), scale, 1) > 0
        def visible(frame):
            p = frame.astype(np.float32)
            p[..., :3] *= p[..., 3:4] / 255
            return p
        anchor = visible(actual[seq[start]])
        # 在实际合成的预乘色彩上检查；极低 alpha 处的不可见 RGB 舍入不算位移。
        changed_big = max(int((np.abs(visible(f) - anchor).max(axis=2)[fixed] > 0.5).sum()) for f in actual)
        rows.append(dict(state=st.id, head_neck_changed_pixels_1x=changed,
                         head_neck_changed_pixels_2x=changed_big,
                         max_step_px=round(worst, 4), loop_step_px=round(loop_step, 4),
                         loop_discontinuity_px=round(seam, 8), intro_discontinuity_px=round(intro_seam, 8)))
        pair = dict(id=st.id)
        for key, data in [('before', before[st.id]), ('after', after[st.id])]:
            s, _, p = data
            directory = args.out / key
            directory.mkdir(exist_ok=True)
            if p.resolve() != (directory / p.name).resolve():
                shutil.copy2(p, directory / p.name)
            pair[key] = dict(s, src=f'{key}/{p.name}')
            if s.get('blink'):
                eye = p.parent / s['blink']['asset']
                if eye.resolve() != (directory / eye.name).resolve():
                    shutil.copy2(eye, directory / eye.name)
                pair[key]['blinkSrc'] = f'{key}/{eye.name}'
        items.append(pair)
    (args.out / 'checks.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    template = Path(__file__).with_name('compare_motion.html').read_text()
    (args.out / 'comparison.html').write_text(template.replace('__ITEMS__', json.dumps(items)))
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    assert all(r['head_neck_changed_pixels_2x'] == 0 for r in rows), '超分后固定区域仍有变化，见 checks.json'
    if args.gif:
        overview(before, after, args.out)


if __name__ == '__main__':
    main()
