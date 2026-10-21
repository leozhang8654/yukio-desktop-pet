# Qianxia — modern sci-fi desktop-pet concepts

Latest design direction; supersedes the cozy desk styling in the earlier brief. **Five alternatives for each of the 12 agent states: 60 designs.** Five matching style alternatives for each of the seven pickup/throw segments are included separately. These are choices, not a request to build a random variation system.

## Visual direction

Keep Qianxia's supplied character design and outfit. Give her a tiny rounded white-and-charcoal workstation with mint/cyan edge lights and small pink accents. Technology should look tactile and cute: chunky keys, stubby styluses, rabbit-shaped devices and sleeve-sized controllers. The desk and character form a compact transparent silhouette; no room, walls, scenery, large platform or broad cloud of floating UI.

Keep the character roughly 85–90% of frame height. Limit supporting detail to three or four clusters: a docked bunny-shaped device; two cartridge-like storage blocks beneath the desk; a small charging puck or folded headset; tiny stickers, vents and one cable integrated into the furniture. Select one central active tool per state. Projected-looking interfaces fit directly above a small physical desk base and stay below the face; they never occupy the status bubble or real question-card area. Draw large simple icons rather than tiny readable text.

The earlier images illustrate character identity and compactness only; they do not show this revised sci-fi styling. No new illustration or animation was generated in this revision.

## Animation boundary

All twelve agent-state ideas are designed for the existing masked-part compositor: static head/neck/body/furniture, one or two small hand/prop groups, fixed wrist attachments, repaired hidden pixels, shared gaze limits and independent six-level blinking. A held item moves with its gripping hand. Props begin already held, docked or placed. No grabbing, changing grip, insertion, unplugging or releasing is animated.

A holographic appearance is painted translucent artwork with a fixed glow. Key grids, screen contents, icons, beams and display highlights do not animate or cast moving light. No perspective-turning panels, spinning 3D objects, growing ink, page flips, simulated cables, floating particle systems or animated robot companions are required. Small in-plane prop shifts and rotations use the same existing transforms. Device dials move only a few degrees with their hand group; each anchor/contact still needs rig validation.

Use 384×416 source art displayed at 192×208 points. Existing timing arrays, loop-entry structure and router semantics remain the initial scaffold. Start around 0.5–2 logical points and 1–3 degrees of motion; these are suggested authoring ranges, not proven limits. Qianxia still needs her own sources, masks, clean plates, eye definitions and per-state parameters. The existing Yukio-specific hardcoded anchors/input paths need configuration; technique compatibility is not a claim that these designs already render unchanged.

## Five designs per agent state

### Idle — `idle`

Purpose: No active task.

1. **Bunny-bot companion.** Her hand gives a tiny docked bunny robot one slow pat, followed by a long relaxed pause.
2. **Charging lounge.** She rests beside a miniature charging puck; one fingertip traces a short arc along its rim.
3. **Magnetic fidget.** A hand holding a small magnetic puck rocks it a few degrees beside her sleeve, then rests.
4. **Headphone break.** Headphones are already worn; her hand makes a tiny earcup adjustment while her gaze drifts toward you.
5. **Smart-cup pause.** Both sleeves frame a temperature-display cup; one hand gently settles against it, then remains still.

### Thinking — `thinking`

Purpose: Reasoning and planning.

1. **Node-map puzzle.** Chin on a fixed sleeve, her eyes alternate between two branches on a small translucent node-map display.
2. **Paused light pen.** She holds a luminous-tip pen near her cheek and looks upward, pauses, then returns to the console.
3. **Logic tile.** Her hand nudges an already-held circuit tile slightly beside a matching slot, hesitates, and eases back without releasing it.
4. **Orbit diagram.** Her eyes slowly inspect three marked points on a fixed circular planning display; her hands stay folded.
5. **Decision chips.** Two cyan-and-pink decision chips sit in a tray; a finger makes one small indecisive tap before she looks between them.

### Reading files — `read_file`

Purpose: Examining local documents or code.

1. **Data-cartridge reader.** A cartridge is already docked; her finger traces a short line on its compact document display.
2. **E-ink dossier.** She holds a thin e-ink slate while a reading finger travels slowly down a fixed column of text bars.
3. **Transparent archive card.** Her hand rocks a translucent data card slightly as her gaze checks its header and lower rows.
4. **Code-strip viewer.** A short pointer follows a line on a narrow desk-mounted code display, pauses, then returns.
5. **Layered file tabs.** Three translucent file panels sit in a fixed fan; her pointing hand and gaze inspect their numbered tabs in sequence.

### Viewing images — `view_image`

Purpose: Inspecting visual content.

1. **Scanner loupe.** A hand and square illuminated loupe sweep together over a fixed thumbnail on a small inspection pad.
2. **Holo-photo tile.** She holds a luminous framed image tile, giving it a tiny in-plane tilt while her eyes inspect opposite corners.
3. **Light-table inspection.** A stylus makes a small inspection arc over an image on a flat light table, then pauses over one feature.
4. **Twin-image viewer.** Two picture thumbnails sit on a compact dual display; her eyes compare them while one finger indicates a corner.
5. **Crop-frame check.** She holds a small luminous rectangular frame just above a fixed picture and shifts it slightly to inspect the composition.

### Writing files — `write_file`

Purpose: Creating or editing content.

1. **Light-pen editor.** Her stylus makes three quick short strokes on a dark glass tablet, pauses, then returns to the starting position.
2. **Projected keyboard.** Both hands alternate tiny typing bursts over a fixed cyan key grid projected from a small desk bar.
3. **Split-key console.** Her hands type asymmetrically on two compact key clusters, with a deliberate pause after each burst.
4. **Patch stylus.** A chunky editor pen traces two short sections of a highlighted code block on a fixed upright slate.
5. **Glyph-pad input.** One finger taps three neighboring square keys on a compact symbol pad, rests, then repeats with uneven timing.

### Testing / verifying — `verify`

Purpose: Checking results without claiming success.

1. **Diagnostic probe.** Her hand lowers a probe toward a test contact, pauses to read a gauge, and lifts slightly before repeating.
2. **Waveform comparison.** Her gaze and pointing hands alternate between two fixed waveform strips, stopping at their alignment marks.
3. **Scan-wand pass.** A handheld scan wand makes one slow short pass over a test module, pauses, then returns.
4. **Test-button console.** She presses one large test button, holds still while looking at neutral indicators, then releases the small hand motion.
5. **Checksum reader.** A short pointer visits three cells on a checksum panel, with a measured pause at each empty result box.

### Browsing the web — `read_web`

Purpose: Looking up external information.

1. **Globe terminal.** Her hand makes two short scroll strokes on a globe-marked browser slate, pauses, then taps a tab.
2. **Network map.** A fixed miniature network display shows linked nodes; her pointer visits two nearby nodes while her eyes follow.
3. **Search touchpad.** Her hand makes a small touchpad sweep and click while she studies a fixed magnifier-marked search display.
4. **Link-panel fan.** Three browser panels form a stationary fan above a tiny projector; her finger alternates between their link icons.
5. **Feed dial.** Her hand nudges a small physical browsing dial a few degrees, pauses over a fixed feed display, then eases back.

### Other work — `default_work`

Purpose: Builds, commands and uncategorized tools.

1. **Mini command station.** She alternates brisk key taps with a short mouse-hand adjustment at a compact terminal.
2. **Control deck.** Two sleeve-framed hands tap separate console buttons at different rhythms, followed by a longer monitoring pause.
3. **Trackball operator.** Her hand makes restrained circular movements over a trackball while her eyes stay on the work display.
4. **Build-module station.** She presses a physical execution key beside a docked compute module, then watches its fixed neutral status strips.
5. **Touch-bar operator.** One finger makes a short horizontal sweep over a control strip, pauses, and taps its end button.

### Responding — `respond`

Purpose: Presenting the answer.

1. **Result slate.** Both hands already hold a result slate facing the user; a tiny outward nudge presents it before a steady hold.
2. **Message capsule.** Her hand nudges an already-held, message-marked data capsule toward the desk edge, then keeps it there.
3. **Holo-report frame.** She gives a held translucent report panel one small lift, with its summary graphic already visible.
4. **Digital postcard.** A hand presents a compact luminous message card with a tiny wrist motion, then settles.
5. **Output-screen presentation.** A result display already faces the user; her hand makes one small pointing gesture beside its message icon, then rests.

### Task complete — `task_complete`

Purpose: Finished and awaiting acknowledgment.

1. **Bunny check beacon.** She holds a rabbit-shaped illuminated check paddle, gives it one small proud lift, then holds it visibly.
2. **Mission-clear console.** A large check is already shown on the desk console; her finger taps beside it once and settles.
3. **Star-core award.** She presents a small star-shaped luminous core carrying a bold check, with one gentle upward emphasis.
4. **Completion keycard.** A hand already holds a finished-task keycard; it tilts slightly toward the user and stays readable.
5. **Tiny victory fists.** Beside a fixed large check display, both small fists make one restrained celebratory lift, then rest.

### Question for user — `question_for_user`

Purpose: Awaiting an answer or permission.

1. **Choice console.** A question mark sits above two large choice tiles; her finger alternates between them slowly, then waits.
2. **Question slate.** She holds a translucent question-mark slate and gives it one small attention lift before settling.
3. **Access request.** An already-held access card displays a question mark and lock icon; she nudges it toward the user and waits.
4. **Call button.** Her hand taps twice beside a desk communication button under a fixed question symbol, then remains still.
5. **Listening headset.** She rests a hand beside her already-worn headset and looks toward the user; a small question panel stays visible.

### Failed — `failed`

Purpose: A tool or task encountered an error.

1. **Disconnected connector.** A cable connector is already visibly unplugged; her holding hand lowers slightly once and her gaze drops.
2. **Error console.** Her finger stops above a console with a clear error symbol, retreats a little, then holds still.
3. **Fault keycard.** She holds an error-marked data card at a slight angle; her hands settle as she gives a subdued, pre-drawn pout.
4. **Stopped diagnostic.** A test wand already rests in her hand; she lowers it slightly beside a warning-marked module and pauses.
5. **Blocked upload.** A fixed display shows an interrupted transfer symbol; her mouse hand stops, draws back slightly, and stays there.

## Semantic and timing requirements

- Idle has long rests; thinking uses long visual pauses. Reading traces slowly, writing uses short bursts, web browsing uses scroll/pause/tap, and verification uses check/wait/inspect. Avoid using typing for every active state.
- Verification shows neutral indicators and empty result boxes. It does not manufacture pass/fail outcomes. Completion alone gets the large success check.
- Responding presents content and completes its introductory gesture within the existing roughly three-second response window. Completion performs its gesture once, then keeps the success cue visible while awaiting acknowledgment.
- Waiting keeps a question cue visible and a quiet expectant hold. Props never invent actual answer options or replace the existing interactive question card. Permission denial alone must not trigger the failure design.
- Failure performs a small one-time settle and maintains the error cue. No repeated panic, endless warning flashes, or animated repair implying the error was solved.
- Use fixed per-state mouth/eyebrow drawings. During a state, expression changes come from existing gaze and eyelid behavior; mouth animation is not assumed.

## Five alternatives per existing interaction segment

These are separate physical interaction overrides, not agent states. Reuse the existing held/throw physics and interaction renderer, with Qianxia-specific source layers, grip, geometry and contact anchors. The desk, displays, cable, robot accessory and decor disappear for pickup; they never fly along. This separate renderer already supports whole-character travel/recoil/sway; it does not change the fixed-head constraint for the twelve desk states.

The five columns are coherent style sets. Icon substitutions use the existing star trajectories, timing and occlusion instead of introducing a new particle engine; their actual masks, clean plates and appearance require review. Wall/landing light, medium and strong variants retain the current impact-strength rules. The local throw implementation remains marked unreleased with Windows native acceptance pending.

| Segment | 1 — operator | 2 — technician | 3 — pilot | 4 — navigator | 5 — mascot |
|---|---|---|---|---|---|
| `held` | Surprised operator: tucked hands and wide pre-drawn eyes. | Sleepy technician: half-lidded fixed expression. | Pouting pilot: small pre-drawn pout and compact elbows. | Alert navigator: focused face and symmetrical hands. | Bunny mascot: soft fixed smile and inward-facing shoes. |
| `interaction_airborne` | The surprised pose follows existing travel and rotation. | The sleepy pose follows existing travel and rotation. | The compact pouting pose follows existing travel and rotation. | The alert pose follows existing travel and rotation. | The mascot pose follows existing travel and rotation. |
| `interaction_wall-impact` | Short recoil with a pre-drawn squint. | Short recoil with a startled pre-drawn face. | Short recoil with pre-drawn puffed cheeks. | Short recoil with tightly drawn eyelids. | Short recoil with a small pre-drawn comic frown. |
| `interaction_landing-impact` | Braced sneakers and existing landing compression. | Close-set sneakers and existing landing compression. | Tucked-sleeve landing pose and existing compression. | Neat symmetrical landing pose and existing compression. | Soft compact landing pose and existing compression. |
| `interaction_dizzy-intro` | Switch to a pre-authored dazed expression as sway begins. | Switch to a sleepy/dazed source expression. | Switch to a dazed pout source expression. | Switch to a confused source expression. | Switch to a comic dazed source expression. |
| `interaction_dizzy-loop` | Existing star paths carry cyan pixel-cross icons. | Existing star paths carry pink battery-outline icons. | Existing star paths carry small cyan broken-ring icons. | Existing star paths carry tiny violet warning diamonds. | Existing star paths carry pink bunny-face icons. |
| `interaction_recover` | Existing sway settles; return to the actual task state. | Existing sway settles; return with a calm source face. | Existing sway settles; briefly retain the fixed pout. | Existing sway settles; return with the focused source face. | Existing sway settles; return with the soft source face. |

## Suggested cohesive selection

Bunny-bot companion → Node-map puzzle → Data-cartridge reader → Scanner loupe → Light-pen editor → Diagnostic probe → Globe terminal → Mini command station → Holo-report frame → Bunny check beacon → Choice console → Disconnected connector.

This set uses visibly different tools and rhythms while sharing one small desk and the supplied character design. A prop selected for one state replaces that state's central work tool; it is not added permanently to the scene.

## Status and source references

Design-only revision. No animation source, production assets, app code or installed app changed; no animation QA pass is claimed. Detailed source/mask/alpha/loop/native-playback acceptance requirements remain in the [earlier technical brief](README.md#production-handoff-for-the-selected-options). Its cozy visual styling and three-option count are superseded by this document.

Current states: [macOS Events.swift](../../../YukioPlayer/Sources/YukioCore/Events.swift), [Windows events.py](../../../YukioWin/yukio/events.py). Animation method: [approved_motion.py](../../../YukioPlayer/tools/motion/approved_motion.py), [approved source format](../../../sources/approved-animation-rig/README.md). Interactions: [animation format](../../animation-format.md). All sci-fi props and personality beats here are original design proposals based on the user's supplied character reference, not claims about game canon.
