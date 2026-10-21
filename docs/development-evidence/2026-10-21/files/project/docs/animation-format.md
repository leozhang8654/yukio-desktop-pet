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

macOS uses a 48 MiB page cache plus at most 16 cropped frames of a daily action
or 48 of an interaction action. Without a page manifest it remains compatible with the original atlases.
The held/drag state uses neither pages nor eyelid overlays. The diagnostic
`--motion-benchmark` traverses every encoded step twice and reports first-frame,
warm p95 and warm maximum rendering times separately.

## Throw interaction (unreleased)

`interaction/interaction.json` uses the same atlas/sequence/duration/blink
schema as `motion.json`. IDs start with `interaction_`; they do not enter
ActivityRouter. Six segments are airborne, wall-impact, landing-impact,
dizzy-intro, dizzy-loop and recover. Wall and landing impacts additionally have
`_light` and `_medium` variants; the unsuffixed assets are the strong variant.
The runtime maps pre-impact strength to variant and playback duration. Physics
and gaze/star animation clocks remain separate.

Interaction cells are 216×264 points at pixelScale 2, with 12-point transparent
padding. Top-level `contentOrigin`, `center`, `foot`, and `collider` document
content anchoring. `hitRuns[uniqueFrame]` is a list of `[y, xStart, xEndExclusive]`
in source pixels for the character only. Stars remain visible but do not catch
mouse clicks or collide. The source physics hull is relative to the center,
y-up. Presentation corrects the body silhouette at the room boundary and keeps
the planted foot fixed through the baked sway.

Blink paths resolve relative to each spec's folder. Airborne has its own six
held-eye overlays; special impact/dizzy expressions take precedence. The global
blink clock keeps advancing. Original held and the twelve motion atlases remain
unchanged. All transforms use premultiplied alpha; WebP stores straight RGBA.

`interaction/physics.json` is the shared tuning source: 120 Hz stepping,
12-step catch-up budget, pause-gap handling, release gain/cap, gravity,
restitution, friction, contact settling, strength thresholds and reaction times.
The selected full monitor is one room (`NSScreen.frame` / `rcMonitor`); pixels,
monitor DPI, artwork pixelScale and user scale are distinct. Render timers target
60 Hz without increasing business polling. See the [implementation and QA
record](animation-review/throw-and-dizzy/README.md) for measured limits.

Pages containing interaction IDs also record `interactionSha256`; stale hashes
are rejected. Run `YukioWin/scripts/prepare-windows-assets.py` against complete
assets to generate matching lossless body and eyelid pages for both platforms.
The macOS `--interaction-check DIR` exports deterministic native compositor
frames with debug geometry and timings. Windows `--interaction-check DIR`
requires a Windows desktop and drives its actual layered window. Neither is a
substitute for manual pointer/capture, mixed-DPI and system UI occlusion tests.
