# Qianxia / 千夏 — desktop-pet animation concepts

最新设计网站：[千夏 · 桌宠设计集](https://qianxia-desktop-pet-gallery.abuzzokapi64.chatgpt.site)（仅本人，使用 ChatGPT 登录）。[本地网站](latest-website/index.html) · [离线网站包](qianxia-latest-website.zip)。

最新修改：[第九轮桌腿遮挡修正](selected-315331434243-round09/README.zh-CN.md) · [最新 12 张原图包](selected-315331434243-round09/qianxia-12-states-round09.zip)。

第八轮记录：[第八轮埋头休息](selected-315331434243-round08/README.zh-CN.md) · [最新原图包](selected-315331434243-round08/qianxia-12-states-round08.zip)。

第七轮记录：[第七轮完成休息与等待提示](selected-315331434243-round07/README.zh-CN.md) · [最新 12 张原图包](selected-315331434243-round07/qianxia-12-states-round07.zip)。

第六轮记录：[第六轮参考微笑对照](selected-315331434243-round06/preview.html) · [最新原图包](selected-315331434243-round06/qianxia-12-states-round06.zip)。

第五轮记录：[第五轮闭嘴微笑对照](selected-315331434243-round05/preview.html) · [最新原图包](selected-315331434243-round05/qianxia-12-states-round05.zip)。

第四轮记录：[第四轮姿势与玩具对照](selected-315331434243-round04/preview.html) · [最新 12 张透明原图包](selected-315331434243-round04/qianxia-12-states-round04.zip)。

第三轮记录：[全息文件修正与全套预览](selected-315331434243-round03/preview.html) · [最新 12 张原图包](selected-315331434243-round03/qianxia-12-states-round03.zip)。

第二轮记录：[第二轮前后对照](selected-315331434243-round02/preview.html) · [修改说明](selected-315331434243-round02/README.zh-CN.md) · [透明原图包](selected-315331434243-round02/qianxia-12-states-round02.zip)。

已选方案 `315331434243`：[12 张首轮静态图总览](selected-315331434243-round01/preview.html) · [本轮说明](selected-315331434243-round01/README.zh-CN.md)。

中文版：[千夏现代科幻风桌宠方案——每个状态 5 个设计](sci-fi-designs.zh-CN.md)。

> Latest direction: [modern sci-fi — five options for every state](sci-fi-designs.md). That document supersedes the cozy styling and three-option selection below. These earlier images remain composition explorations, not the current style target.

Design proposal, 2026-10-09. Based on the user's character sheet and the current local Yukio source tree. This is a fan skin concept; the setting and props are original design choices, not claims about game lore.

The brief contains **three alternatives for each of the 12 current agent states**, plus three alternatives for each existing interaction segment. A/B/C are alternatives to choose between, not a proposed new random-animation system.

## Accepted direction

Cute, varied actions using **Yukio's existing masked-part animation method**. Rich detail means a compact desktop-pet vignette: Qianxia, a small desk, and a few personal props surrounded by transparency. No full room, window, skyline, walls, tall shelving or floor platform.

The first room illustration was too broad for the user's clarified scope. `room-mood-concept.png` is retained as an early exploration only. **`desktop-pet-concept.png` is the relevant composition proposal.** It illustrates the stylus-writing option. Neither image is a segmented, approved or playable animation asset.

![Compact desktop-pet concept](desktop-pet-concept.png)

## Character and compact setting

Keep the reference's mint hair, cyan bow, asymmetrical clips, pink oversized sleeves, white jacket, pink tie, dark skirt and pink/white sneakers. Her calm, slightly deadpan face makes tiny reactions charming. Mouth and eyebrow expressions are drawn into each state's source illustration; they do not continuously deform during playback.

Character plus shoes should occupy roughly 85–90% of the sprite height; face and working hands remain dominant. Build at 384×416 physical pixels for the existing 192×208-point presentation. The generated concept is larger and still needs purpose-made source preparation; shrinking it alone does not produce a rig.

Four small, stationary decorative groups give the desk personality:

1. A dark rabbit plush peeking from the stool beside her.
2. Two pastel books tucked under the desk.
3. A tiny plant at the outer desk corner, below her elbow.
4. A heart sticker, cyan X sticker and small clipped note on the desk front.

Keep these in identical positions across the 12 state illustrations. Reuse one background plate rather than generating the furniture independently twelve times. The active prop occupies the central work area; optional alternative props replace it rather than accumulating as clutter. Pale prop colors and quieter outlines keep the face legible. Details such as book tabs, pot markings and stickers enrich large views without needing to be individually readable at desktop size.

## What the existing method supports

The current production route is `make_motion.py` → `approved_motion.py`. It renders a state-specific source illustration using refined masks, a repaired premultiplied RGBA base, fixed foreground occluders, and small part translations/rotations with attachment falloff. It exports lossless WebP body atlases and six-level independent eyelid patches. Gaze translates the iris/pupil/highlight within fixed eye openings.

For all twelve agent states:

- Keep head, neck, hair, bow, torso, legs, desk and decor fixed. Head orientation may be drawn differently in a source pose, but the proposed set uses a consistent frontal view for stable transitions.
- Animate one or two hand/prop groups. Keep a held object in the same moving group as the gripping hand; hide attachment boundaries at a stationary cuff or desk edge.
- Start with about 0.5–2 logical points of hand travel and 1–3 degrees of rotation. These are proposed tuning ranges, not measurements or validated limits for Qianxia. Increase only when contact and clean-plate coverage permit.
- Use different rhythms and gaze targets to distinguish actions. Keep the independent blink clock; do not restart it on every action or prescribe a blink on every hand beat.
- Keep prop markings and screens static. These concepts do not require page deformation, changing text, growing ink strokes, particles, facial morphs, cloth simulation or perspective turns.
- Preserve state IDs, router semantics, existing duration arrays and loop entry structure when authoring the first candidate. Redistribute the new small gestures within those timings.

**Same technique does not mean a drop-in asset swap.** The renderer currently hardcodes the Yukio input directory, two typing pivots, and some attachment bands. Qianxia needs new source art, masks, eye boxes/curves, clean plates, foreground masks and pose parameters. The character-specific constants must become rig data or receive a separate Qianxia configuration. This is preparation within the existing technique, not a switch to 3D, Live2D or generated video. No such implementation changes were made in this design task.

## Three options for every agent state

The first column is a proposed coherent starting set, not a claim of user approval. Each option begins with its prop already positioned in the source illustration; there is no animated prop retrieval, hand regrip or large pose change.

| Current state and purpose | A — proposed starting set | B — alternative | C — alternative |
|---|---|---|---|
| **Idle** `idle` — no active task | **Bunny companion.** A hand rests on a desk-side plush and makes one tiny pat after a long pause; gaze drifts toward the user. | **Warm cup.** Both sleeves frame a fixed cup; one hand makes a tiny relaxed adjustment beside it while she looks outward. No sipping or steam. | **Sleepy sleeves.** Cheeks rest above folded stationary sleeves; quiet gaze and independent blinks carry the pose. Head never sinks or bobs. |
| **Thinking** `thinking` — reasoning/planning | **Idea cards.** Chin rests on a stationary sleeve while her eyes alternate between two star-shaped notes propped on the desk. | **Thinking pen.** A pen is already held near, but clear of, her cheek; the entire pose stays still while gaze moves up, pauses, and returns. | **Little decision board.** She holds a fixed mini board with two simple routes; her eyes inspect left, then right, then settle centrally. |
| **Reading files** `read_file` — examining local documents/code | **Archive cards.** A finger follows one short line on a tabbed file card, pauses, and returns; the card stack stays fixed. | **Ribbon bookmark.** A hand holding a short bookmark tab makes a small pull-and-return beside an open stationary binder. Pages never turn. | **Document strip.** A paw-shaped reading pointer moves slowly along a short row on a fixed document tray. |
| **Viewing images** `view_image` — visual inspection | **Photo check.** A hand holding a photo rocks it by a very small angle; her gaze checks two corners. No front/back turn. | **Lightbox pointer.** A fixed lightbox displays a simple picture; her short pointer traces a small inspection arc above it. | **Picture loupe.** A chunky square loupe and its gripping hand move together across a small photo. A repaired photo/desk base fills the vacated area. |
| **Writing files** `write_file` — creating/editing content | **Pink pen tablet.** Hand and stylus make three short strokes, pause, and return over a stationary tablet. Screen marks are pre-drawn. | **Bunny notebook.** A chunky pencil makes quick short strokes on a fixed notebook; the opposite sleeve stays anchored. | **Edit marker.** A chisel marker makes two deliberate tracing sweeps over a pre-drawn highlighted line, then pauses. No new ink is revealed. |
| **Testing / verifying** `verify` — checking results | **Mini test console.** One sleeve-covered hand presses a large test button, pauses, and her gaze checks a row of neutral indicators. | **Sample comparison.** Two differently colored cards stay on stands; her eyes and pointing hands alternate between their matching rows. | **Inspection pointer.** A short pointer traces three pre-drawn empty checklist boxes, with a distinct pause at each. No pass stamp is added. |
| **Browsing the web** `read_web` — external information lookup | **Browser tablet.** A fixed tablet has a large globe and tab silhouettes; a hand performs two small downward strokes, pauses, then taps. | **Mouse browsing.** Her mouse hand makes a small sweep and click while her eyes examine a fixed compact browser screen. | **Link cards.** A finger moves between two link-symbol cards on a fixed tablet stand. The cards and their graphics remain unchanged. |
| **Other work** `default_work` — builds, commands and uncategorized tools | **Sleeve typing.** Two small hands alternate uneven typing bursts over a compact pink keyboard; a fixed tiny console screen identifies work. | **Control pad.** One hand taps two neighboring square buttons on a compact work pad, with a longer listening pause. | **Trackball station.** A hand makes small circular motions over a stationary trackball controller; gaze stays on the adjacent console. Ball markings do not rotate. |
| **Responding** `respond` — arranging/presenting the answer | **Ribbon report.** Both hands already grip a small result packet; one short outward nudge presents it, then the hands settle. | **Answer tablet.** She already holds a compact result tablet front-facing; a tiny lift and settle offers it for reading. | **Delivery envelope.** A hand nudges an already sealed envelope with a message icon toward the desk edge, then holds it. No folding or release. |
| **Task complete** `task_complete` — finished, waiting for acknowledgment | **Rabbit check badge.** She holds a large rabbit-shaped check paddle, gives one restrained upward emphasis, then keeps it clearly visible. | **Star award.** Both hands hold a star-shaped badge with a bold check; it settles after one tiny proud lift. | **Finished folder.** A completed folder with a large check is held toward the user; one small presentation motion precedes a steady hold. |
| **Question for user** `question_for_user` — awaiting an answer/permission | **Choice tickets.** Two tickets sit on a stand beneath a large question mark; a pointing hand alternates between them slowly, then waits. | **Question paddle.** A hand already holds a question-mark paddle and makes a restrained attention tap/lift before a quiet hold. | **Your-turn card.** A fixed question card sits on the desk; one hand makes two small taps beside it, then remains still. |
| **Failed** `failed` — tool/task error | **Stuck result.** A hand hovers over a fixed error slip, lowers slightly once, and stays there; the source face has a small disappointed pout. | **Unfinished check.** Her pen hand stops over a crossed result box, backs off a little, and holds. No scribbling away the error. | **Trouble ticket.** She holds a small warning ticket at a slight pre-drawn angle; her hands settle once and gaze lowers. No repeated distress cycle. |

## Timing and meaning

The differences should remain recognizable without labels: thinking is mostly gaze; reading is a slow trace; writing uses short repeated strokes; web reading uses scroll-pause-tap; generic work uses alternating bursts; testing uses press-wait-inspect.

Use the existing state timeline lengths as the initial scaffold: idle ~12.02 s; thinking ~7.02 s; file reading ~2.22 s; image inspection ~2.82 s; writing ~2.02 s; verification ~3.62 s; web reading and default work ~2.42 s. These are total encoded sequence lengths from the current local rigs, including the closing step, not a proposal to add new timers.

Responding, completion, waiting and failure already support an introduction followed by a quiet loop. Their current loop entries occur at 1.4 s, 5.0 s, 4.2 s and 1.4 s respectively. The actual router normally gives `respond` about three seconds before `task_complete`, so its presentation gesture must finish inside that window. The completion icon must already be legible before the introduction finishes.

Verification must never look like all tests passed while the agent is still checking. Keep its console indicators neutral and checklist boxes unfilled. Reserve the large check for actual `task_complete`. Responding presents content; completion announces that work is finished. Waiting uses a question mark and a sustained expectant pose, never a triumphant check. Keep the real question/options card separate and readable; decorative tickets do not invent answer text or imply clickable controls.

The failure introduction happens once, followed by a subdued hold. A harmless permission denial is not a failure. Completion and question animations must stay legible for long waits, with no endlessly repeated celebration or urgent flashing.

## Existing pickup and throw interactions

These are temporary interaction overrides, not additional agent states. The local tree includes pickup plus six throw-related segments; wall and landing impacts have light, medium and strong variants. Throw work is marked unreleased, with native Windows acceptance pending in the project record.

Use the **existing separate held/interaction pipeline and physics**, not the fixed-head desk-state renderer. Author character-only source layers; furniture and decorative props do not fly with her. The same masks/clean-plate principle applies, but each interaction needs its own correctly anchored Qianxia assets and geometry. Each column below is a coherent alternative reaction set.

| Existing segment | A — sleepy surprise | B — plush-like pout | C — composed little helper |
|---|---|---|---|
| `held` | Fixed surprised face; oversized sleeves and shoes dangle with the existing pendulum motion. | Fixed pout and tucked elbows; the whole held cutout swings using the current grip. | Fixed alert face and compact hands; the same drag sway, with no new waving action. |
| `interaction_airborne` | Surprised held pose carried through existing travel and rotation. | Pouting compact pose carried through the same flight. | Alert compact pose carried through the same flight. |
| `interaction_wall-impact` | Short existing recoil with a pre-drawn squint. | Small recoil with puffed cheeks already drawn in the impact source. | Small recoil with a pre-drawn tight-eye expression. |
| `interaction_landing-impact` | Existing landing compression in her chunky sneakers. | Compact landing pose with the sleeves already close to her body. | Neat braced landing pose, compressed only within existing deformation limits. |
| `interaction_dizzy-intro` | Transition to a pre-authored dazed face as the current body sway begins. | Transition to a pre-authored pout/dazed face. | Transition to a pre-authored tired face, hands still compact. |
| `interaction_dizzy-loop` | Current planted-foot sway with pink stars using existing star motion. | Same supported sway with cyan stars; no additional spinning character action. | Same supported sway with pale yellow stars and the existing eye treatment. |
| `interaction_recover` | Existing sway settles, then return to the latest actual task state. | Same settle with a fixed small pout before return. | Same settle with a fixed calm face before return. |

Impact strength changes the existing reaction amplitude/duration, not the meaning of the reaction. Keep catch/rethrow behavior and live task routing. Do not add a separate recovery chore such as fixing her bow: that would need additional hand choreography. Old running-left/right assets are present on disk but are not loaded by the current base catalog; this proposal does not count them as active agent states.

## Production handoff for the selected options

1. Choose one option per agent state and one interaction style. Prepare consistent source poses using the approved character design and a shared compact desk plate.
2. For each state, author `source.png`, final part masks, `allowed-mask.png`, repaired `composition.npz`, `rig.json`, parameters and provenance. New segmentation uses verified SAM 2.1 access followed by manual correction; do not substitute Yukio's old masks.
3. Configure Qianxia's per-state wrist pivots, foreground coverage and eye layers. For thinking options, the stationary cheek hand and gaze-only behavior already fit the current design. Hair, head/neck and decor remain fixed.
4. Render a separate candidate package using the existing compositor and atlas format. Preserve the full twelve-state manifest. The current checks contain character-specific assumptions and must use Qianxia's documented masks and intended changes; an eye-only comparison against Yukio is not an appropriate acceptance test.
5. Verify decoded atlases, frame timings, intro/loop boundaries, blink mapping, alpha, fixed regions and hand/prop contact. Review each complete loop at least three times at native size, enlarged, and on contrasting backgrounds. Confirm actions are distinguishable without labels.

No animation has been produced or passed QA in this concept task. No current app resources, source code, packages or running app were replaced.

## Evidence and files

State inventory: [macOS Events.swift](../../../YukioPlayer/Sources/YukioCore/Events.swift), [Windows events.py](../../../YukioWin/yukio/events.py). Rendering constraints: [approved_motion.py](../../../YukioPlayer/tools/motion/approved_motion.py), [approved input notes](../../../sources/approved-animation-rig/README.md). Runtime sequencing: [ActivityRouter.swift](../../../YukioPlayer/Sources/YukioCore/ActivityRouter.swift). Interaction behavior: [animation format](../../animation-format.md), [local interaction record](../../animation-review/throw-and-dizzy/README.md).

Both illustrations used the built-in image generation tool. Exact prompts are preserved in `image-prompt.txt` and `compact-image-prompt.txt`. The character reference is `character-reference.png`; file hashes and image properties are recorded in `provenance.json`. The reference remains the identity authority; generated artwork is proposed interpretation rather than an approved model sheet.
