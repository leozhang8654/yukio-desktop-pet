#!/usr/bin/env python3
"""Fit the supplied transparent held pose without changing its art or silhouette."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image

REPO = Path(__file__).resolve().parents[3]
SOURCE = REPO / 'sources/qianxia-held'


def build(output):
    parameters = json.loads((SOURCE / 'parameters.json').read_text())
    source = SOURCE / 'original.png'
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if source_hash != parameters['sourceSha256']:
        raise ValueError('Held source does not match the recorded input')
    image = Image.open(source).convert('RGBA')
    size, offset = parameters['resizedPixels'], parameters['offsetPixels']
    # Resample premultiplied color to prevent transparent RGB from causing fringes.
    fitted = image.convert('RGBa').resize(size, Image.Resampling.LANCZOS).convert('RGBA')
    canvas = Image.new('RGBA', parameters['canvasPixels'])
    canvas.paste(fitted, offset)
    base = output / 'base'
    base.mkdir(parents=True, exist_ok=True)
    path = base / 'held.png'
    canvas.save(path)
    assert Image.open(path).convert('RGBA').tobytes() == canvas.tobytes()
    scale = parameters['pixelScale']
    sx, sy = size[0] / image.width, size[1] / image.height
    assert sx == sy
    grip = parameters['gripInSourcePixels']
    spec = {'id': 'held', 'asset': 'held.png', 'frameWidth': canvas.width // scale,
        'frameHeight': canvas.height // scale, 'pixelScale': scale, 'frameCount': 1,
        'nativeDurationsMs': [1000], 'grip': {'x': (grip[0] * sx + offset[0]) / scale,
        'y': (grip[1] * sy + offset[1]) / scale, 'headTop': canvas.getbbox()[1] / scale}}
    (base / 'base-animations.json').write_text(json.dumps({'animations': [spec]}, indent=2) + '\n')
    record = {'source': 'sources/qianxia-held/original.png', 'sourceSha256': source_hash,
        'outputSha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'parameters': parameters,
        'drag': 'Use the supplied held pose and the existing drag/settle physics.'}
    (output / 'held-provenance.json').write_text(json.dumps(record, indent=2) + '\n')
    provenance_path = output / 'provenance.json'
    if provenance_path.exists():
        provenance = json.loads(provenance_path.read_text())
        provenance['heldFrame'] = 'Supplied held pose; see held-provenance.json.'
        provenance_path.write_text(json.dumps(provenance, indent=2) + '\n')
    print(path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=REPO / 'YukioPlayer/Resources/Assets/skins/qianxia')
    build(parser.parse_args().output)
