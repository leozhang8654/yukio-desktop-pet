"""Render the reviewed SAM rigs with a stationary head and independent eyelids.

Inputs are versioned in sources/approved-animation-rig. No segmentation,
redrawing, background removal or super-resolution is performed here.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import cv2
import numpy as np
from PIL import Image
from motionlib import detect_eye
from blink_curves import paint_curve_blink
from gaze_layers import GazeRig

ROOT = Path(__file__).resolve().parents[3]
INPUTS = ROOT / 'sources/approved-animation-rig'
STATES = ['default_work','write_file','verify','view_image','read_file','read_web',
          'thinking','respond','question_for_user','task_complete','idle','failed']
W, H, LEVELS = 384, 416, 6


def rgba8(p):
    a = np.clip(p[..., 3:4], 0, 1)
    out = np.concatenate([p[..., :3] / np.maximum(a, 1e-8), a], axis=2)
    out[a[..., 0] == 0] = 0
    return np.round(np.clip(out, 0, 1) * 255).astype(np.uint8)


def over(base, top):
    return top + base * (1 - top[..., 3:4])


class Rig:
    def __init__(self, state):
        self.state = state
        folder = INPUTS / state
        self.data = json.loads((folder / 'rig.json').read_text())
        self.src = np.array(Image.open(folder / 'source.png').convert('RGBA'))
        self.ms = {p.name[:-9]: np.array(Image.open(p)) > 0
                   for p in folder.glob('*-mask.png') if p.name != 'allowed-mask.png'}
        self.allowed = np.array(Image.open(folder / 'allowed-mask.png')) > 0
        composition = np.load(folder / 'composition.npz')
        self.base = composition['base'].copy()
        self.fg = composition['foreground']
        self.prem = self.src.astype('float32') / 255
        self.prem[..., :3] *= self.prem[..., 3:4]
        self.head = self.ms['head']
        # Replace the old moving-head seam donors with the exact stationary
        # source pixels, including source alpha. Never composite the face over
        # those donors: doing so thickens semi-transparent outline pixels.
        self.base[self.head] = self.prem[self.head]
        self.eyes = [detect_eye(self.prem, tuple(b)) for b in self.data['eyes']]
        self.gaze = GazeRig(self.prem, self.eyes, self.data['poses'])
        self.layers = {name: self.prem * mask[..., None] for name, mask in self.ms.items()}
        self.yy, self.xx = np.mgrid[:H, :W].astype('float32')
        self.face_cache = {}
        self.part_cache = {}

    def moving_parts(self, index):
        pose = self.data['poses'][index]
        for name in self.ms:
            if name == 'head' or (self.state == 'thinking' and name == 'cheek_hand'):
                continue
            dx, dy, angle = pose['transforms'].get(name, (0., 0., 0.))
            key = (name, dx, dy, angle)
            if key not in self.part_cache:
                dx *= 2
                dy *= 2
                pp = ({'left': (185, 209), 'right': (255, 217)}[name]
                      if self.state == 'default_work' else tuple(self.data['parts'][name]['pivot']))
                mat = cv2.getRotationMatrix2D(pp, -angle, 1)
                moved = cv2.warpAffine(self.layers[name], mat, (W, H), flags=cv2.INTER_LINEAR)
                if self.state == 'default_work':
                    weight = np.clip((self.yy - 207) / 14, 0, 1)
                elif self.state in {'respond', 'task_complete'}:
                    weight = np.clip(np.minimum(self.xx - 143, 243 - self.xx) / 18, 0, 1)
                else:
                    weight = np.clip(np.hypot(self.xx - pp[0], self.yy - pp[1]) / 18, 0, 1)
                weight = weight * weight * (3 - 2 * weight)
                moved = cv2.remap(moved, self.xx - dx * weight, self.yy - dy * weight, cv2.INTER_LINEAR)
                if len(self.part_cache) >= 12:
                    self.part_cache.pop(next(iter(self.part_cache)))
                self.part_cache[key] = moved
            yield self.part_cache[key]

    def render(self, index, level=0):
        gx, gy = [round(v * 8) / 8 for v in self.data['poses'][index]['gaze']]
        key = (gx, gy, level)
        if key not in self.face_cache:
            face = paint_curve_blink(self.gaze.render(gx, gy), self.eyes,
                                     level / LEVELS, self.data['curves'],
                                     cover_margin=1.3, warm_skin_only=True,
                                     eye_apertures=self.gaze.eyes).copy()
            face[..., 3] = self.prem[..., 3]
            face[..., :3] = np.minimum(face[..., :3], face[..., 3:4])
            if len(self.face_cache) >= 24:
                self.face_cache.pop(next(iter(self.face_cache)))
            self.face_cache[key] = face
        f = self.base.copy()
        # Head/neck translation, rotation and scaling are deliberately absent.
        # Gaze and eyelids stay in the fixed aperture of the approved source.
        f[self.head] = self.face_cache[key][self.head]
        for moved in self.moving_parts(index):
            f = over(f, moved)
        out = rgba8(f)
        out[~self.allowed] = self.src[~self.allowed]
        out[self.fg] = self.src[self.fg]
        out[out[..., 3] == 0] = 0
        return out


def atlas(frames, path):
    h, w = frames[0].shape[:2]
    cols = min(14, len(frames))
    sheet = Image.new('RGBA', (cols * w, math.ceil(len(frames) / cols) * h))
    assert max(sheet.size) < 16384
    for i, frame in enumerate(frames):
        sheet.paste(Image.fromarray(frame), (i % cols * w, i // cols * h))
    sheet.save(path, lossless=True, exact=True, method=3)
    with Image.open(path) as encoded:
        for i, frame in enumerate(frames):
            assert np.array_equal(np.array(encoded.crop((i % cols * w, i // cols * h,
                                   (i % cols + 1) * w, (i // cols + 1) * h))), frame)


def export(state, out, preserve_motion_from=None):
    rig = Rig(state)
    data = rig.data
    baseline_spec, baseline_sheet = None, None
    if preserve_motion_from is not None:
        catalog = json.loads((preserve_motion_from / 'motion.json').read_text())
        baseline_spec = next(s for s in catalog['states'] if s['id'] == state)
        assert baseline_spec['durationsMs'] == data['durationsMs']
        assert baseline_spec['loopStart'] == data['loopStart']
        assert baseline_spec['pixelScale'] == 2
        baseline_sheet = Image.open(preserve_motion_from / baseline_spec['asset']).convert('RGBA')
    frames, seen, sequence, indices = [], {}, [], []
    for i in range(len(data['poses'])):
        frame = rig.render(i)
        if baseline_sheet is not None:
            # An eye-only repair must not resample released hands/props. OpenCV
            # versions can otherwise introduce small unrelated pixel changes.
            index = baseline_spec['sequence'][i]
            cols = baseline_sheet.width // W
            x, y = index % cols * W, index // cols * H
            original = np.array(baseline_sheet.crop((x, y, x + W, y + H)))
            for eye in rig.eyes:
                x0, y0, x1, y1 = eye.box
                original[y0:y1, x0:x1, :3] = frame[y0:y1, x0:x1, :3]
            frame = original
        key = hashlib.sha256(frame.tobytes()).digest()
        if key not in seen:
            seen[key] = len(frames)
            frames.append(frame)
            indices.append(i)
        sequence.append(seen[key])
    assert sequence[-1] == sequence[data['loopStart']], state + ' loop seam'
    atlas(frames, out / f'{state}.webp')
    patches, seen, mapping = [], {}, []
    x0, y0, x1, y1 = data['roi']
    for f, i in zip(frames, indices):
        row = []
        open_frame = rig.render(i)
        for level in range(1, LEVELS + 1):
            rendered = rig.render(i, level)
            blink = f.copy()
            changed = np.any(rendered != open_frame, axis=2)
            blink[..., :3][changed] = rendered[..., :3][changed]
            patch = blink[y0:y1, x0:x1].copy()
            assert np.array_equal(blink[..., 3], f[..., 3]), state + ' blink alpha'
            blink[y0:y1, x0:x1] = f[y0:y1, x0:x1]
            assert np.array_equal(blink, f), state + ' blink ROI'
            key = hashlib.sha256(patch.tobytes()).digest()
            if key not in seen:
                seen[key] = len(patches)
                patches.append(patch)
            row.append(seen[key])
        mapping.append(row)
    atlas(patches, out / f'{state}-eyes.webp')
    print(f'{state}: {len(sequence)} steps, {len(frames)} body frames, {len(patches)} eye patches', flush=True)
    return dict(id=state, asset=f'{state}.webp', frameWidth=192, frameHeight=208,
                pixelScale=2, sequence=sequence, durationsMs=data['durationsMs'], loop=True,
                loopStart=data['loopStart'], blink=dict(asset=f'{state}-eyes.webp', x=x0, y=y0,
                width=x1-x0, height=y1-y0, levels=LEVELS, frames=mapping, seed=data['seed']))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, default=ROOT / 'YukioPlayer/build/neck-stability-sam/after')
    ap.add_argument('--only', action='append', choices=STATES)
    ap.add_argument('--preserve-motion-from', type=Path,
                    help='Released motion folder; replace only the eyes and retain all other pixels')
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    states = [export(s, args.out, args.preserve_motion_from) for s in STATES if not args.only or s in args.only]
    (args.out / 'motion.json').write_text(json.dumps(dict(version=4, states=states), indent=2) + '\n')


if __name__ == '__main__':
    main()
