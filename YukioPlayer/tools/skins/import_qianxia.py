#!/usr/bin/env python3
"""Import only the R07 runtime assets from the supplied archive, unchanged."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from build_qianxia_held import build as build_held


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
    (out / 'activities').mkdir(parents=True, exist_ok=True)
    (out / 'activities/activities.json').write_text('{"states": []}\n')
    provenance = {'skin': 'qianxia', 'revision': 'R07', 'archive': args.archive.name,
        'archiveSha256': hashlib.sha256(args.archive.read_bytes()).hexdigest(),
        'archivePrefix': prefix, 'unchangedRuntimeFiles': hashes}
    (out / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    build_held(out)
    print('Imported', len(names), 'unchanged files to', out)


if __name__ == '__main__':
    main()
