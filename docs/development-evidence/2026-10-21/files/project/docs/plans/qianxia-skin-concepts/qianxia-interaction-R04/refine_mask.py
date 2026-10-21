"""Apply independently identified background-only component exclusions.

No automatic small-object policy: exclusions below refer only to frozen R03.
Preserves every channel of the main character and all original edge coverage.
"""
from pathlib import Path
import hashlib, json
import cv2
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / 'qianxia-interaction-R03'
raw = SOURCE / 'held-generated.png'
frozen = json.loads((SOURCE / 'frozen-hashes.json').read_text())
assert hashlib.sha256(raw.read_bytes()).hexdigest() == frozen[raw.name]
original = np.array(Image.open(raw).convert('RGBA'))
count, labels, stats, centers = cv2.connectedComponentsWithStats((original[..., 3] > 0).astype('uint8'), connectivity=8)
assert count == 90
# Independent R03 review identifies IDs 2–89 as background alpha residue;
# NONE are body parts, hanging tags, hair tips, or intended decorations.
excluded_ids = list(range(2, 90))
excluded = np.isin(labels, excluded_ids)
assert int(excluded.sum()) == 166
assert int(original[..., 3][excluded].max()) == 2
candidate = original.copy()
candidate[excluded] = 0
assert np.array_equal(candidate[~excluded], original[~excluded])
Image.fromarray(candidate).save(HERE / 'held.png')
support = (candidate[..., 3] > 0).astype('uint8') * 255
Image.fromarray(support).save(HERE / 'body-support-mask.png')
Image.fromarray(excluded.astype('uint8') * 255).save(HERE / 'removed-background-mask.png')
report = {
    'source_sha256': hashlib.sha256(raw.read_bytes()).hexdigest(),
    'source_size': list(Image.open(raw).size),
    'operation': 'Remove independently reviewed background residual components only; no dilation, erosion, blur, body repaint or interior alpha normalization.',
    'excluded_component_ids': excluded_ids,
    'excluded_pixels': int(excluded.sum()),
    'excluded_alpha_max': int(original[..., 3][excluded].max()),
    'unchanged_pixels_outside_exclusion': bool(np.array_equal(candidate[~excluded], original[~excluded])),
    'main_character_rgba_byte_equal': bool(np.array_equal(candidate[labels == 1], original[labels == 1])),
    'user_gate': 'Static cutout approval required before animation; no installation.',
}
(HERE / 'refinement.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
