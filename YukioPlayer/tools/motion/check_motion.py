#!/usr/bin/env python3
"""检查头颈固定、开场和循环接缝，并用实际发布图集制作修复前后预览。

先备份 Resources/Assets/motion，再运行 make_motion.py，最后：
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
import motionlib as m
from approved_motion import Rig, STATES, ROOT


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


def load_one(folder, name):
    specs = json.loads((folder / 'motion.json').read_text())
    assert specs['version'] == 4
    spec = next(s for s in specs['states'] if s['id'] == name)
    path = folder / spec['asset']
    sheet = Image.open(path).convert('RGBA')
    w, h = spec['frameWidth'] * spec['pixelScale'], spec['frameHeight'] * spec['pixelScale']
    cols = sheet.width // w
    frames = [np.array(sheet.crop((i % cols*w, i//cols*h, (i%cols+1)*w, (i//cols+1)*h)))
              for i in range(max(spec['sequence'])+1)]
    return spec, frames, path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--before', type=Path, required=True)
    ap.add_argument('--after', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--gif', action='store_true')
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    rows, items, before_gif, after_gif = [], [], {}, {}
    contacts = Image.new('RGB', (384*4, 446*len(STATES)), '#eef1f5')
    draw = ImageDraw.Draw(contacts)
    for row, state in enumerate(STATES):
        old, before, oldpath = load_one(args.before, state)
        spec, frames, path = load_one(args.after, state)
        rig = Rig(state)
        for key in ('durationsMs', 'loopStart', 'loop', 'frameWidth', 'frameHeight', 'pixelScale'):
            assert old[key] == spec[key], (state, key)
        assert old['blink']['seed'] == spec['blink']['seed']
        assert old['blink']['levels'] == spec['blink']['levels'] == 6
        swept = np.zeros(rig.head.shape, bool)
        for i in range(len(rig.data['poses'])):
            for layer in rig.moving_parts(i):
                swept |= layer[..., 3] > 0
        for name, mask in rig.ms.items():
            if name != 'head':
                swept |= mask
        # Include a 1px filtering border, and allow eyelids inside their ROI.
        swept = cv2.dilate(swept.astype('uint8'), np.ones((3, 3), np.uint8)) > 0
        fixed = rig.head & ~swept
        x0, y0, x1, y1 = rig.data['roi']
        fixed[y0:y1, x0:x1] = False
        assert fixed.sum() > 5000, (state, 'empty head test')
        # This region includes shoulders/neck immediately outside the head,
        # while excluding moving hands/props and eye apertures.
        neck = cv2.dilate(rig.head.astype('uint8'), np.ones((25, 25), np.uint8)) > 0
        neck &= ~swept
        neck[y0:y1, x0:x1] = False
        head_changed = max(int(np.any(f[fixed] != rig.src[fixed], axis=1).sum()) for f in frames)
        neck_changed = max(int(np.any(f[neck] != frames[0][neck], axis=1).sum()) for f in frames)
        assert head_changed == neck_changed == 0, (state, 'head/neck moved', head_changed, neck_changed)
        outside_head = cv2.dilate(rig.head.astype('uint8'), np.ones((25, 25), np.uint8)) == 0
        unrelated = 0
        for k, i in enumerate(spec['sequence']):
            unrelated = max(unrelated, int(np.any(frames[i][outside_head] != before[old['sequence'][k]][outside_head], axis=1).sum()))
        assert unrelated == 0, (state, 'unrelated artwork changed', unrelated)
        assert np.array_equal(frames[spec['sequence'][-1]], frames[spec['sequence'][spec['loopStart']]]), state+' seam'
        # Read the ENCODED eye atlas and check every body/eyelid combination.
        blink = spec['blink']
        eyes = Image.open(args.after / blink['asset']).convert('RGBA')
        cols = eyes.width // blink['width']
        for frame, patches in zip(frames, blink['frames']):
            for patch_id in patches:
                px, py = patch_id % cols * blink['width'], patch_id // cols * blink['height']
                patch = np.array(eyes.crop((px, py, px+blink['width'], py+blink['height'])))
                assert np.array_equal(patch[..., 3], frame[y0:y1, x0:x1, 3]), state+' eye alpha'
        diffs = [float(np.abs(frames[b].astype('float32') - frames[a]).mean())
                 for a, b in zip(spec['sequence'], spec['sequence'][1:])]
        loopstart = spec['loopStart']
        intro_step = diffs[loopstart-1] if loopstart else 0
        rows.append(dict(state=state, timelineSteps=len(spec['sequence']), bodyFrames=len(frames),
                         fixedHeadPixels=int(fixed.sum()), fixedHeadChangedPixels=head_changed,
                         fixedNeckChangedPixels=neck_changed, outsideHeadChangedPixels=unrelated,
                         loopSeamChangedPixels=0, introBoundaryMeanChannelDelta=intro_step,
                         maxAdjacentMeanChannelDelta=max(diffs), independentBlinkLevels=6))
        # Keep actual image files beside the portable HTML, no baked screenshots.
        item = dict(id=state)
        for label, original, sourcepath in [('before',old,oldpath),('after',spec,path)]:
            target = args.out / label
            target.mkdir(exist_ok=True)
            for asset in [original['asset'], original['blink']['asset']]:
                dest = target / asset
                if dest.resolve() != (sourcepath.parent / asset).resolve():
                    shutil.copy2(sourcepath.parent / asset, dest)
            item[label] = dict(original, src=f'{label}/{original["asset"]}', blinkSrc=f'{label}/{original["blink"]["asset"]}')
        items.append(item)
        draw.text((8, row*446+8), state+' | AFTER: start / action / full blink / loop end', fill='#223047')
        mid = len(spec['sequence'])//2
        chosen = [frames[spec['sequence'][0]], frames[spec['sequence'][mid]], rig.render(mid,6), frames[spec['sequence'][-1]]]
        for col, f in enumerate(chosen):
            im = Image.fromarray(f)
            contacts.paste(im, (col*384, row*446+30), im)
        if state in ('read_file','write_file','view_image'):
            before_gif[state] = old, before, oldpath
            after_gif[state] = spec, frames, path
        print(state, 'PASS', flush=True)
    contacts.save(args.out / 'all-states.png')
    (args.out / 'validation.json').write_text(json.dumps(dict(version=4, states=rows), indent=2)+'\n')
    template = Path(__file__).with_name('compare_motion.html').read_text()
    (args.out / 'comparison.html').write_text(template.replace('__ITEMS__', json.dumps(items)))
    if args.gif:
        overview(before_gif, after_gif, args.out)


if __name__ == '__main__':
    main()
