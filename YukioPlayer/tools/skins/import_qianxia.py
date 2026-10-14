#!/usr/bin/env python3
"""Import only the R07 runtime assets from the supplied archive, unchanged."""
import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path
from PIL import Image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archive', type=Path)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[2] / 'Resources/Assets/skins/qianxia')
    args = parser.parse_args()
    out = args.output
    prefix = 'qianxia-motion-results-2026-10-13/qianxia-motion-R07/motion/'
    with zipfile.ZipFile(args.archive) as archive:
        manifest_bytes = archive.read(prefix + 'motion.json')
        manifest = json.loads(manifest_bytes)
        names = {'motion.json'}
        for state in manifest['states']:
            names.add(state['asset'])
            if state.get('blink'):
                names.add(state['blink']['asset'])
        hashes = {}
        for name in sorted(names):
            if Path(name).name != name:
                raise ValueError('Asset must be a filename')
            data = archive.read(prefix + name)
            target = out / 'motion' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            hashes['motion/' + name] = hashlib.sha256(data).hexdigest()
        # The catalog's compatibility held frame is Qianxia's exact idle frame.
        # Runtime dragging keeps the active pose; no Yukio artwork is inherited.
        idle = next(s for s in manifest['states'] if s['id'] == 'idle')
        scale = idle.get('pixelScale', 1)
        with Image.open(io.BytesIO(archive.read(prefix + idle['asset']))) as sheet:
            image = sheet.convert('RGBA').crop((0, 0, idle['frameWidth'] * scale, idle['frameHeight'] * scale))
            (out / 'base').mkdir(parents=True, exist_ok=True)
            image.save(out / 'base/held.png')
    (out / 'activities').mkdir(parents=True, exist_ok=True)
    (out / 'activities/activities.json').write_text('{"states": []}\n')
    base = {'animations': [{'id': 'held', 'asset': 'held.png', 'frameWidth': 192, 'frameHeight': 208,
        'pixelScale': 2, 'frameCount': 1, 'nativeDurationsMs': [1000],
        'grip': {'x': 96, 'y': 45, 'headTop': 0}}]}
    (out / 'base/base-animations.json').write_text(json.dumps(base, indent=2) + '\n')
    provenance = {'skin': 'qianxia', 'revision': 'R07', 'archive': args.archive.name,
        'archiveSha256': hashlib.sha256(args.archive.read_bytes()).hexdigest(),
        'archivePrefix': prefix, 'unchangedRuntimeFiles': hashes,
        'heldFrame': 'Exact first idle frame; compatibility only. Dragging keeps the active pose.'}
    (out / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    print('Imported', len(names), 'unchanged files to', out)


if __name__ == '__main__':
    main()
