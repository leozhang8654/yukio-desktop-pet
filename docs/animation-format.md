# Independent eyelids (motion catalog v4)

macOS and Windows use the same `YukioPlayer/Resources/Assets/motion` files.
Each action keeps its body atlas, sequence, per-step durations and optional
one-time intro (`loopStart`). The 192×208 logical frame has `pixelScale: 2`.

An optional `blink` object adds a lossless eye-patch atlas:

- `asset`: filename relative to `motion/`.
- `x`, `y`, `width`, `height`: replacement rectangle in physical atlas pixels,
  with the origin at the top left, **not** logical display points.
- `levels`: six closing/opening levels; level zero uses the unmodified body.
- `frames[bodyAtlasIndex][level - 1]`: row-major patch index in the eye atlas.
- `seed`: per-state deterministic seed for future blink events.

Copy the selected eye patch into the body image. Do not alpha-composite it over
the original iris; replacement must include transparent pixels. The patch is
already drawn for that body's head pose. Do not transform it separately.

Keep one blink clock per pet across action changes. A state change selects the
new seed for future scheduling; it must not cancel an active blink, a pending
event or the second blink of a double. The clock uses milliseconds and the
32-bit LCG `state = (1664525 * state + 1013904223) mod 2^32`.
The authoritative implementation and cross-language fixtures are in
`BlinkClock.swift` and `BlinkClockTests.swift`.

The `held` drag state has no eye overlay and is unchanged. Keep decoding/cache
work bounded and avoid re-decoding an entire WebP atlas on each frame.

For cross-platform pixel checks, the macOS executable's `--blink-snapshots DIR`
exports body frames 0 and `maxFrameIndex / 2` at all seven eyelid levels. Use
`YUKIO_ASSETS` to point diagnostics at an isolated candidate directory.

## Optional lossless pages

Both runtimes can read `motion/windows-pages/manifest.json` (the historical
directory name is shared across platforms). The v1 manifest records the SHA-256
of the authoritative `motion.json`; a mismatch is rejected, never silently used.
Each state's `body` contains `count`, `perPage`, and relative `pages`. Body pages
are one row of 13 full-size frames. `eyes` additionally contains `columns` (16),
with 64 patches per page. The Windows preparation script verifies every exported
page's decoded RGBA against its source. No resampling or lossy compression occurs.

macOS uses a 32 MiB page cache plus at most 16 cropped frames of the current
action. Without a page manifest it remains compatible with the original atlases.
The held/drag state uses neither pages nor eyelid overlays. The diagnostic
`--motion-benchmark` traverses every encoded step twice and reports first-frame,
warm p95 and warm maximum rendering times separately.
