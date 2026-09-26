#!/usr/bin/env python3
"""Verify fixed eye corners, conjugate gaze, and the encoded animation assets."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from approved_motion import Rig, STATES
from check_motion import load_one


def iris_centres(plate, eyes):
    centres = []
    for eye in eyes:
        x0, y0, x1, y1 = eye.box
        rgb = plate[y0:y1, x0:x1, :3]
        weight = np.maximum(rgb[..., 2] - rgb[..., 0] - .12, 0) * eye.aperture
        yy, xx = np.mgrid[y0:y1, x0:x1]
        assert weight.sum() > 1, 'Lost iris'
        centres.append([np.sum(xx * weight) / weight.sum(), np.sum(yy * weight) / weight.sum()])
    return np.array(centres)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--before', type=Path, required=True)
    ap.add_argument('--after', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    report = []
    contact = Image.new('RGB', (1440, 180 * len(STATES)), '#e7ebef')
    labels = ImageDraw.Draw(contact)
    for row, state in enumerate(STATES):
        rig = Rig(state)
        fixed = np.ones(rig.src.shape[:2], bool)
        outside_boxes = fixed.copy()
        for eye in rig.gaze.eyes:
            x0, y0, x1, y1 = eye.box
            fixed[y0:y1, x0:x1] &= ~eye.aperture
            outside_boxes[y0:y1, x0:x1] = False
            rgb = rig.prem[y0:y1, x0:x1, :3]
            warm_dark = (rgb[..., 0] - rgb[..., 2] > .04) & (rgb.mean(2) < .4)
            assert not (warm_dark & eye.iris).any(), (state, 'Eye-corner ink in iris cutout')
        assert np.array_equal(rig.gaze.render(0, 0), rig.prem), (state, 'Neutral artwork changed')
        baseline = iris_centres(rig.prem, rig.gaze.eyes)
        positions = {}
        maximum_disparity = np.zeros(2)
        trajectory = [tuple(round(v * 8) / 8 for v in p['gaze']) for p in rig.data['poses']]
        for gaze in set(trajectory):
            plate = rig.gaze.render(*gaze)
            assert np.array_equal(plate[fixed], rig.prem[fixed]), (state, gaze, 'Corner/lash/face moved')
            assert np.array_equal(plate[..., 3], rig.prem[..., 3]), (state, 'Alpha changed')
            positions[gaze] = iris_centres(plate, rig.gaze.eyes)
            movement = positions[gaze] - baseline
            maximum_disparity = np.maximum(maximum_disparity, np.abs(movement[0] - movement[1]))
            assert movement[0, 0] * movement[1, 0] >= -.01, (state, gaze, 'Opposing horizontal gaze')
        # At the source's 2x resolution, 0.55 px is under 0.28 desktop points.
        # Small differences come from the distinct fixed eyelid apertures.
        assert maximum_disparity.max() < .55, (state, maximum_disparity, 'Binocular drift')
        max_step = max(float(np.abs(positions[b] - positions[a]).max())
                       for a, b in zip(trajectory, trajectory[1:]))
        assert max_step < .4, (state, max_step, 'Gaze jump')

        old, old_frames, _ = load_one(args.before, state)
        new, new_frames, _ = load_one(args.after, state)
        for key in ('durationsMs', 'loopStart', 'loop', 'frameWidth', 'frameHeight', 'pixelScale'):
            assert old[key] == new[key], (state, 'Timing changed', key)
        assert old['blink']['seed'] == new['blink']['seed']
        assert len(old['sequence']) == len(new['sequence']) == len(trajectory)
        # Compare actual decoded release frames, not just generator output.
        for old_index, new_index in set(zip(old['sequence'], new['sequence'])):
            assert np.array_equal(old_frames[old_index][outside_boxes], new_frames[new_index][outside_boxes]), (
                state, 'Non-eye motion/artwork changed')
        for i in set([0, len(trajectory) - 1, new['loopStart']]):
            assert np.array_equal(new_frames[new['sequence'][i]][~outside_boxes], rig.render(i)[~outside_boxes]), (
                state, 'Encoded eye frame mismatch')
        blink = new['blink']
        with Image.open(args.after / blink['asset']) as sheet:
            columns = sheet.width // blink['width']
            for closed_id in {patches[-1] for patches in blink['frames']}:
                px = closed_id % columns * blink['width']
                py = closed_id // columns * blink['height']
                patch = np.array(sheet.crop((px, py, px + blink['width'], py + blink['height']))).astype(int)
                for eye in rig.gaze.eyes:
                    x0, y0, x1, y1 = eye.box
                    eye_rgb = patch[y0-blink['y']:y1-blink['y'], x0-blink['x']:x1-blink['x'], :3]
                    blue = (eye_rgb[..., 2] - eye_rgb[..., 0] > 40) & (eye_rgb[..., 2] > 100)
                    assert not (blue & eye.aperture).any(), (state, closed_id, 'Iris sliver in full blink')

        extreme = max(range(len(trajectory)), key=lambda i: np.linalg.norm(trajectory[i]))
        boxes = rig.data['eyes']
        crop = (min(b[0] for b in boxes) - 4, min(b[1] for b in boxes) - 4,
                max(b[2] for b in boxes) + 4, max(b[3] for b in boxes) + 4)
        views = [('SOURCE', rig.src), ('GAZE', rig.render(extreme)),
                 ('HALF BLINK', rig.render(extreme, 3)), ('CLOSED', rig.render(extreme, 6))]
        for col, (label, pixels) in enumerate(views):
            im = Image.fromarray(pixels).crop(crop)
            im = im.resize((im.width * 4, im.height * 4), Image.Resampling.NEAREST)
            contact.paste(im, (col * 360, row * 180 + 20), im)
            labels.text((col * 360 + 4, row * 180 + 3), state + ' ' + label, fill='#223047')
        item = dict(state=state, timelineSteps=len(trajectory), distinctGazes=len(positions),
                    sharedXYGain=rig.gaze.gain.tolist(), maxBinocularDriftSourcePixels=maximum_disparity.tolist(),
                    maxAdjacentIrisStepSourcePixels=max_step, changedPixelsOutsideEyeBoxes=0,
                    changedCornerPixels=0, independentBlinkLevels=6, fullBlinkIrisLeaks=0)
        report.append(item)
        print(state, 'PASS', flush=True)
    contact.save(args.out / 'eyes-and-blinks.png')
    (args.out / 'gaze-validation.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
