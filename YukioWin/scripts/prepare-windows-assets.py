#!/usr/bin/env python3
"""Build small lossless WebP pages for the Windows runtime.

The macOS assets use very wide 2x atlases. Pillow/libwebp expands an entire
atlas to read one frame, and the round_12 set approaches 1 GB as RGBA. The
packaged Windows app therefore carries equivalent 13-frame body pages and
64-patch eyelid pages. Source artwork and motion.json stay authoritative.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))

from yukio.catalog import AnimationCatalog  # noqa: E402

BODY_PER_PAGE = 13
EYE_COLUMNS = 16
EYES_PER_PAGE = 64


def default_source() -> Path:
    candidates = [ROOT / "Assets", REPO / "YukioPlayer" / "Resources" / "Assets", REPO / "assets"]
    for candidate in candidates:
        if (candidate / "activities" / "activities.json").is_file():
            return candidate
    raise SystemExit("No Assets directory found")


def copy_non_motion_atlases(source: Path, output: Path) -> None:
    def ignore(directory: str, names):
        if Path(directory).resolve() == (source / "motion").resolve():
            return [name for name in names if name.lower().endswith(".webp")]
        return []

    shutil.copytree(source, output, ignore=ignore)


def save_exact_webp(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Method 3 keeps CI preparation bounded (method 6 took several minutes for
    # only four states) while remaining pixel-exact; only compressed size changes.
    image.save(path, "WEBP", lossless=True, quality=100, method=3, exact=True)
    with Image.open(path) as check:
        check = check.convert("RGBA")
        if check.size != image.size or check.tobytes() != image.tobytes():
            raise RuntimeError("lossless page changed pixels: %s" % path)


def body_pages(source: Path, output: Path, spec) -> dict:
    path = source / spec.asset_path
    with Image.open(path) as opened:
        sheet = opened.convert("RGBA")
    cell_w = spec.frame_width * max(spec.pixel_scale, 1)
    cell_h = spec.frame_height * max(spec.pixel_scale, 1)
    source_columns = sheet.width // cell_w
    count = spec.max_frame_index + 1
    pages = []
    for page_index, start in enumerate(range(0, count, BODY_PER_PAGE)):
        take = min(BODY_PER_PAGE, count - start)
        page = Image.new("RGBA", (cell_w * take, cell_h), (0, 0, 0, 0))
        for local in range(take):
            frame_index = start + local
            left = (frame_index % source_columns) * cell_w
            top = (frame_index // source_columns) * cell_h
            frame = sheet.crop((left, top, left + cell_w, top + cell_h))
            page.paste(frame, (local * cell_w, 0))
            frame.close()
        name = "body/%s-%03d.webp" % (spec.id, page_index)
        save_exact_webp(page, output / "motion" / "windows-pages" / name)
        page.close()
        pages.append(name)
    sheet.close()
    return {"count": count, "perPage": BODY_PER_PAGE, "pages": pages,
            "atlasWidth": source_columns * cell_w,
            "atlasHeight": ((count + source_columns - 1) // source_columns) * cell_h}


def eye_pages(source: Path, output: Path, spec) -> dict:
    blink = spec.blink
    path = source / "motion" / blink.asset
    with Image.open(path) as opened:
        sheet = opened.convert("RGBA")
    source_columns = sheet.width // blink.width
    count = max(index for row in blink.frames for index in row) + 1
    pages = []
    for page_index, start in enumerate(range(0, count, EYES_PER_PAGE)):
        take = min(EYES_PER_PAGE, count - start)
        rows = (take + EYE_COLUMNS - 1) // EYE_COLUMNS
        page = Image.new("RGBA", (blink.width * min(EYE_COLUMNS, take), blink.height * rows),
                         (0, 0, 0, 0))
        for local in range(take):
            patch_index = start + local
            left = (patch_index % source_columns) * blink.width
            top = (patch_index // source_columns) * blink.height
            patch = sheet.crop((left, top, left + blink.width, top + blink.height))
            page.paste(patch, ((local % EYE_COLUMNS) * blink.width,
                               (local // EYE_COLUMNS) * blink.height))
            patch.close()
        name = "eyes/%s-%03d.webp" % (spec.id, page_index)
        save_exact_webp(page, output / "motion" / "windows-pages" / name)
        page.close()
        pages.append(name)
    sheet.close()
    return {"count": count, "perPage": EYES_PER_PAGE, "columns": EYE_COLUMNS, "pages": pages,
            "atlasWidth": source_columns * blink.width,
            "atlasHeight": ((count + source_columns - 1) // source_columns) * blink.height}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=ROOT / "build" / "windows-assets" / "Assets")
    args = parser.parse_args()
    source = (args.source or default_source()).resolve()
    output = args.output.resolve()
    if output.exists():
        shutil.rmtree(output)
    copy_non_motion_atlases(source, output)
    catalog = AnimationCatalog.load(str(source))
    states = {}
    for spec in sorted(catalog.specs.values(), key=lambda item: item.id):
        if not spec.asset_path.startswith("motion/"):
            continue
        entry = {"body": body_pages(source, output, spec)}
        if spec.blink is not None:
            entry["eyes"] = eye_pages(source, output, spec)
        states[spec.id] = entry
        print("paged", spec.id, len(entry["body"]["pages"]), "body pages")
    motion_bytes = (source / "motion" / "motion.json").read_bytes()
    manifest = {"version": 1, "motionSha256": hashlib.sha256(motion_bytes).hexdigest(), "states": states}
    manifest_path = output / "motion" / "windows-pages" / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("OK:", manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
