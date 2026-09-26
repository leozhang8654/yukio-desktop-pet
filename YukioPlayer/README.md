**English** · [简体中文](README.zh-CN.md)

# Yukio desktop player (macOS, follows Claude Code, DeepSeek or GPT)

One Yukio (雪绪) who changes what she is doing based on what your coding agent — **Claude Code**, **DeepSeek's Deep Code CLI**, or **GPT's Codex**, picked in the menu under "Assistant" — is doing right now: seven kinds of activity each get their own motion, all other work shows the computer-desk pose, an error makes her sad, she stands up the ❓ question card when she needs your decision — the question itself is written out on a card beside her and you can answer it right there — and she holds up the ✅ done card when the answer is in. The sign stays up waiting for you; click her and she jumps back to that chat. If that chat is already open in front of you, she skips the sign. With no task running, she idles.
With several chats open at once, whichever one has just finished or is waiting for your decision is shown first; the other chats that have something to say stack above the bubble as cards of the same design, and clicking one takes you to that chat. You can also pin one chat in the menu so she follows only that one. Every motion moves gently and continuously (writing, typing, moving her eyes, blinking), and the small bubble over her head shows the big task, the current task, and progress.
Native Swift / AppKit. It needs only the Xcode Command Line Tools and has no third-party dependencies.

## Build and run

```sh
cd YukioPlayer
swift test                     # 139 tests (routing, blink timing, classification, parsing, file following, assets, bubble text, motion timeline, chat matching and selection, questions and answering)
./scripts/build-app.sh         # produces build/Yukio.app (assets and icon are bundled into the app)
open build/Yukio.app
```

Once running: Yukio appears in the bottom-right corner of the screen, and her small avatar appears in the menu bar. The menu has the state line ("Yukio · \<state\>"), the chat she is following, "Play demo", "Follow assistant activity" (untick it to pause following), "Assistant" (Claude Code / DeepSeek / GPT, or Auto), "Chat to follow" (pick one), "Show task bubble", "Show other chats", "Answer here", "Language" (English / 中文; English is the default and the choice is remembered), "Size", "Back to the bottom-right corner", and "Quit Yukio". While she is holding the ✅ done card, two extra items appear at the top, "Open this chat and lower the sign" and "Lower the sign, don't open the chat"; while the ❓ question card is up there is one extra, "Open this chat to answer". Descriptions already attached to earlier events keep their language until the next event arrives. "Size" is a slider (50% to 200% in 5% steps): drag it and Yukio grows or shrinks on the spot, with her feet staying where they are.

Settings and menu entry points:

1. The menu bar avatar. On first run it sits toward the right (about 260 points from the right edge); hold ⌘ and drag to move it, and the system remembers the spot.
2. Right-click (or control-click) Yukio herself to open Settings directly.
3. Open Yukio.app again (from Finder, Spotlight, or `open build/Yukio.app`): the menu pops up next to Yukio.

When the menu bar on a notch display is full, macOS pushes the icons that don't fit under the notch or off the screen (measured on this machine: with a plain text title, which read "雪绪" at the time, it was pushed to x=0 and completely invisible). After switching to the avatar and placing it toward the right it is visible, but it pushes the leftmost of the other icons into the notch. You can turn off icons you don't need in "System Settings › Menu Bar" to free up room.

Window-less check modes (during development, run `swift run YukioPlayer <flag>`). The CLI's own diagnostic output is still in Chinese for now.

| Flag | What it does |
| --- | --- |
| `--check` | Loads and crops every asset and confirms no frame goes out of bounds |
| `--snapshot out.png` | Draws the animations actually in use on a checkerboard (strips with many frames are sampled evenly down to 10) to check cropping and transparent edges |
| `--bubble out.png` | Draws a few sample head bubbles at 2x resolution to check layout, truncation, and position |
| `--cards out.png` | Draws the card stack over her head at 2x resolution (bubble plus other chats, one panel collapsed and one expanded) to check layout, truncation, and state colors |
| `--replay session.jsonl` | Replays a session log on a virtual clock and prints the sequence of states Yukio would show; the format (Claude / Deep Code / Codex) is detected from the file, and `--with-bubble` also prints the bubble text (title and file names included) |
| `--watch seconds` | Follows the session logs live and prints events, write latency, and state switches (never the conversation content) |
| `--source auto\|claude\|deepseek\|gpt` | Which family `--watch` and `--chats` follow; without it they use the same setting as the menu |
| `--menu` | Prints the menu text, submenus included, without opening a window (add `-source gpt` or `-language zh` to see another setting's wording) |
| `--chat-link session-id` | Looks up without opening: prints the chat this transcript session maps to and the link a click would open |
| `--chats seconds` | Lists recent chats (the same list as the "Chat to follow" menu), with `→` marking the one she would follow right now; watches for 3 seconds by default |
| `--demo` | Plays the demo right after launch |

## Activity mapping

| State | Motion | Claude Code source |
| --- | --- | --- |
| `thinking` | A: thinking, chin on hand | A task is running and no tool is executing (the model is generating); TodoWrite, Task*, plan mode, ToolSearch |
| `read_file` | B: reading a book at the desk | Read (non-image), Glob, Grep; read-only shell commands (cat, sed -n, rg, ls, git status/diff, ...) |
| `view_image` | B: inspecting with a magnifying glass | Read on an image file; MCP screenshot-type tools |
| `write_file` | B: writing on paper | Write, Edit, MultiEdit, NotebookEdit; writing commands (redirecting to a file, sed -i, cp, mv, mkdir, git commit, ...) |
| `verify` | B: checking two documents against each other | Test / check commands (swift test, pytest, npm test, cargo test, `*verify*`/`*test*` scripts, ...) |
| `read_web` | B: browsing on a tablet | WebFetch, WebSearch; browser-type MCP tools; curl/wget |
| `respond` | B: handing over the report | The final answer (`end_turn` text); hands it over once and holds still, then switches to the ✅ done card after 3 seconds |
| `task_complete` | C: showing the ✅ done card | Follows the report hand-over and **stays up**: click her to jump back to that chat and lower the sign; if you don't, it steps aside on its own when you send the next message in that chat |
| `question_for_user` | C: standing up the ❓ question card | `AskUserQuestion`: the task is still running but waiting for your decision; the question is copied onto a card beside her so you can answer without leaving your seat (see "Answering from here"), and the card stays until you answer |
| `default_work` | Steady computer desk | Everything else (builds, installing dependencies, Agent, Skill, unknown MCP tools, ...) |
| `failed` | Sad (base sprite strip `failed`; lowers her eyes once and holds) | A tool error (non-zero exit, edit text not found, missing file, ...): the next tool to start takes over, otherwise back to thinking after at most 4 seconds; an API error that aborts the turn: stays 8 seconds, then back to idle. Denied permissions and interruptions don't count as failures |
| `idle` | Base idle | No task in progress; the fallback after she loses contact |

While being dragged she shows no activity; instead she is "picked up by an invisible hand" (see the next section), and once released and settled she returns to the current activity. The classification rules are in `Sources/YukioCore/ClaudeToolClassifier.swift`; they are finite and each one has a test. When a call can't be classified she falls back to the computer desk, and arbitrary commands are never treated as tests.

## Dragging: picked up by an invisible hand

Press and drag her and Yukio no longer runs; she gets picked up like a kitten: shoulders hunched up to her ears, arms and legs dangling loosely, feet off the ground.
The hand holding her is invisible; the grip point is an empty spot a short way above the top of her head. The whole image swings around that point, and the angle and sag are computed by `Sources/YukioCore/HangSwing.swift`:

- Flick the hand to the right and she lags behind from inertia (feet drifting left); when the hand stops she swings past vertical to the other side and settles after a few swings.
- When dragged at a steady speed only air drag is left, and her body leans back slightly and steadily; as soon as you stop she straightens up.
- Vertically there is a separate "stretchy cloth": yank the hand upward and she first sags below (by at most 16% of the pendulum length, about 15 points) and then springs back.
  Pure sideways dragging never sags. **Most of the sense of weight comes from this sag**, together with the slow 0.9-second swing.
- After release the damping increases, she swings to a stop on her own (about 1 second) and then switches back to the current activity; grab her again while she is still swinging and she carries on from the current angle instead of resetting to zero.
- When Yukio is scaled up her center of mass is farther from the grip point, so the same flick swings her less (about half at 2x size).

| Parameter (`HangSwing.Tuning`) | Default | Notes |
| --- | --- | --- |
| `periodSec` | 0.9 | Seconds for one back-and-forth of a small swing. Heavy things swing slowly; this setting affects the sense of weight the most |
| `damping` / `releaseDamping` | 0.13 / 0.4 | Damping ratio while held and after release |
| `airDrag` | 0.43 | How far she leans back when moving at a steady speed (about 3° at 600 points/second) |
| `handCoupling` | 0.11 | How much of the hand's acceleration is really thrown into her. Taken literally as "one point equals one millimeter", a casual drag would already hit the limit, so it is discounted: a gentle nudge gives 3°, a normal drag 10°, and only a hard flick reaches the cap |
| `maxAngleDeg` | 20 | Maximum tilt angle; hitting it feels like hitting a stop |
| `velocitySmoothingSec` | 0.07 | Hand speed is low-pass filtered before acceleration is derived (mouse events arrive in jumps); it also makes her start half a beat late |
| `sagPeriodSec` / `sagDamping` | 0.42 / 0.32 | Period and damping of one stretch-and-return of the vertical cloth |
| `verticalCoupling` | 0.25 | How much of the hand's vertical speed becomes sag: a gentle lift gives 4 to 6 points, a hard yank 11 |
| `maxSagRatio` | 0.16 | Maximum sag as a fraction of the pendulum length (about 15 points, scaling up with her) |

The asset is `Resources/Assets/base/held.png` (192×240, taller than a regular frame because both legs hang down below).
`tools/hang/make_held.py` crops it out of `sources/held-source.png` (a transparent full-body illustration generated by GPT):

- GPT drew the "pinched collar" as a sharp dark-blue triangle above her head, which the user didn't want; the script flood-selects the whole patch by its dark blue, starting from inside the tip, and removes it, cleaning up the anti-aliased edge along with it (only the part above the hair outline is cleared; the hair outline and the little tuft on top are left alone);
- scaling is by **head width** rather than overall height, so the head stays the same size and she doesn't seem to jump in size when the image switches;
- her center of mass is aligned to the frame's center line (so she hangs straight), and the top of her hair is aligned to the same row as the standing image (y=16), so her head doesn't move at the instant she is picked up.

The grip point (the empty spot 6 points above the top of her head) and the head-top line are written in the `grip` entry of `base-animations.json`;
the pendulum length (grip point to center of mass) is measured by the player itself when it loads the image, so changing the image needs no number changes.

The instant she is picked up the window temporarily grows to 340×309 (at 1x; the bottom 15 points are reserved for the sag) so she isn't clipped by the window when she swings to either side; the extra area is transparent.
When she is put down the window returns to normal, and edge snapping, position memory, and the head bubble are all computed from the usual 192×208 block. Hit testing first rotates the point back to the upright frame, so clicks land correctly even while she is tilted.

The swing **direction** was once drawn backwards (the rotation was written as `-angle`, so on screen her feet flew out toward the direction of movement, the opposite of a real pendulum).
The convention is: a positive angle means feet to the right; layer coordinates have y pointing up, so moving the feet to the right takes a **positive** rotation
(on a clock face, a hand pointing at 6 moves toward 7, 8, 9 when turned clockwise, which is to the left; going right is counterclockwise).
`--hang` self-checks this every time: it draws the image at ±20° and measures the horizontal position of the feet, then separately computes the matrix `PetView` uses;
both must satisfy "positive angle equals feet to the right", otherwise it prints "反了" ("reversed") and exits with a non-zero code.

This machine has no screen-recording permission, so two command-line checks stand in for eyeballing it:

```
swift run YukioPlayer --hang out.png       # five tilt angles side by side, with the window frame, the usual block's frame, and the grip point drawn in; also self-checks the swing direction
swift run YukioPlayer --hang-gif out.gif   # plays "drag a bit, release, lift, flick back" with the real swing logic, at 30 fps
```

## Motions

Each state uses the reviewed 384×416 artwork and final SAM component masks in [`sources/approved-animation-rig`](../sources/approved-animation-rig/README.md). The head and neck remain fixed, without nodding. Hands and attached props retain the approved motion: reading gaze follows the text, the pen moves with the writing hand, and the magnifier follows its hand. Cuffs, furniture and foreground occlusion retain the approved pixels.

`tools/motion/make_motion.py` now calls `approved_motion.py`, preserving the 50 fps timeline, intro/loop boundaries and v4 independent six-level eyelids. Run it with `--out build/neck-stability-sam/after`, then use `check_motion.py` with `--before`, `--after`, `--out` and optional `--gif` to verify every state and produce a comparison. Install validated assets separately. No super-resolution pass is needed. Historical generators require an explicit `--legacy` flag and are not the production workflow.

### Leg length of the standing pose (2026-09-18)

The original standing poses (idle, sad) have chibi proportions: the same size head on very short legs, only 50 px from hem to sole. `base/held.png`, used when the big hand picks her up, is a different set: the same head, but a longer body and legs. Switching between the two, the difference in leg length is obvious.

`tools/proportion/restretch_idle.py` brings the standing pose to the same proportions as the held image, **without redrawing**: it only stretches the strip of white sock between the hem and the boot tops vertically (20 → 34 px); head, torso, skirt, straps, sock tops, and boots stay pixel-for-pixel the same, and the whole figure moves up to the top of the frame (top of head from y16 to y2). **The soles still land on the original row (y195)**, so where she stands doesn't change. The idle and sad sets are both changed (the same-named files under `base/` and `motion/` alike), and the originals are backed up in `sources/pre-restretch/`.

```sh
python3 tools/proportion/restretch_idle.py --preview out.png     # preview only
python3 tools/proportion/restretch_idle.py --apply               # write back to the assets
python3 tools/proportion/restretch_idle.py --apply --targets idle,failed
```

The standing pose is still a little shorter than the held image (the frame is only 208 tall; the held one is 240); the difference is in torso length and boot size. The leg-to-body ratio went from 22% to 33% (the held image is 38%). Matching it exactly would mean giving the standing pose a 240-tall frame too, which means changing the window height and the ground line, and that is a separate job.

Because the head-top line of the standing pose (y2) and the seated pose (y22) differ by a stretch, the head bubble and the card stack beside her now attach to **each segment's own** head-top line (`SpriteLibrary.headTopInset(for:)`) and re-attach whenever the motion changes.

## The head bubble

The small bubble over Yukio's head is at most 180 points wide and two lines tall; it fades in when there is a task and fades out when there isn't. "Show task bubble" in the menu turns it off.

| Position | Content | Source |
| --- | --- | --- |
| Top line (title) | The big task | Claude's session title (the session name in the desktop app, or the CLI's automatic title); with no title, the first line of this turn's request |
| Bottom line | The current task | The "in progress" item in Claude's task list (TaskCreate / TaskUpdate or TodoWrite) |
| Bottom line (no task list) | The current activity | The tool call in progress: `Editing main.swift`, `$ swift test`, `Browsing developer.apple.com`, `Your turn · click to open`, ... |
| Number on the right and thin bar at the bottom | Task progress | Done / total in the task list; when a whole batch is done and new tasks are created, the count starts over |

The text follows the motion Yukio is currently showing (debounced) and never runs ahead of it; when details change too fast within one motion (reading several files in a row), each piece of text stays for at least 1.2 seconds. On an error it shows "Error: \<that call\>", and after an answer it shows "Answered". The bubble shows only file names, the first few words of a command, and the domain of a URL, never file contents. When there is no other chat to pick from, clicks pass through to the window behind as before; when there are other chats, clicking it fans out the stack (see the next section).

## Clicking the sign: jump back to that chat

When it's your turn she holds up a sign: the ✅ done card when a turn's answer is in, and the ❓ question card when `AskUserQuestion` is waiting for your decision. Both signs are clickable, and clicking jumps to the chat that sign belongs to.

When a turn's answer is in, Yukio hands over the report, raises the ✅ done card 3 seconds later, and then **keeps holding it**. It never comes down on its own; however long you are away from the computer, it's still up when you get back.

There is only one case where she doesn't hold it up: **that chat is already open in front of you**, meaning the Claude desktop app is frontmost and the chat it has selected is this very one.
You're already looking at the finished answer, and a sign would just be in the way. The same goes for a sign already up: switch over to that chat yourself and
the sign comes down on the spot, no click needed (that turn counts as seen, and switching away won't bring it back up).

How she knows which chat is open: the desktop app records each session in `~/Library/Application Support/Claude/claude-code-sessions/…/local_*.json`,
where `lastFocusedAt` is updated when you switch to a chat, so the one with the largest value is the currently selected chat.
`./.build/release/YukioPlayer --open-chat` checks this on the spot. This is the desktop app's internal record, not a public interface;
when it can't be read she **falls back to holding up the sign as usual**. Better one sign too many than a reminder swallowed.

- **Click her** (a single left click, no holding): opens the Claude chat that turn belongs to, lowers the sign, and returns to idle. "Open this chat and lower the sign" in the menu does the same thing; use it when the mouse is hard to aim.
- **Not clicking is fine too**: send the next request in that chat and the sign steps aside for the new motion on its own. It also comes down when the turn is interrupted or that session's record is deleted.
- **Leaving it up doesn't get in the way**: if 15 minutes pass without a click, she goes to follow the chats still working, sign still in hand; when that chat stops, the sign comes back up on its own.
- **Click her while the ❓ question card is up**: opens that chat so you can answer. Unlike the done card, this card doesn't go away; the question is still waiting for you, and the card clears itself once you answer in the chat. The matching menu item is "Open this chat to answer".
- In any other state clicking her does nothing; dragging, right-click-to-open-Settings, and click-through all work as before (moving more than 3 points counts as a drag, not a click).
- Restarting the player drops any sign she is holding: a sign is raised only when a task has just finished (within `completeArmMs`), so startup doesn't hold up a stale record from hours ago.

The jump uses the deep link the Claude desktop app registers itself, `claude://code/continue?session=local_…`. The session ID in the transcript and the desktop app's session ID are not the same; the mapping is read from `cliSessionId` in
`~/Library/Application Support/Claude/claude-code-sessions/<account>/<organization>/local_<id>.json` (read only, never written).
This is the desktop app's internal record, not a public interface, and may change between versions; when nothing matches (for example Claude Code running in a terminal) she only brings Claude to the front and never jumps into someone else's chat.
`--chat-link <session ID>` lets you check beforehand which chat was recognized.

## Answering from here

While the ❓ question card is up, the question itself is stood up beside her: the header, the question wrapped over up to six lines,
and the options one per row. Long questions are cut with an ellipsis (the full one is in the chat); at most six options are listed and the rest
are noted as "N more in the chat". The card sits on whichever side of her has room and never covers her or the bubble over her head.

- **Click an option** and that option's text is the answer. Number keys 1–9 do the same.
- **A multi-select question** keeps the options you click ticked; press ⏎ to send them all, joined by "、" (", " in English).
- **Type your own** in the box at the bottom and press ⏎ (or click the ⏎ button). It is a real text field, so input methods work as usual.
- **✕** puts the card away for this question only; she keeps the ❓ card up and the next question brings the card back.
- **"Open the chat ›"** jumps to the chat instead, exactly like clicking her.

How the answer gets there: Yukio copies it to the clipboard, opens that chat through the deep link (which brings Claude or Codex to the front),
waits until that app really is frontmost, and then presses ⌘V and ⏎ for you. **It needs the system's Accessibility permission**
(macOS asks the first time, in System Settings › Privacy & Security › Accessibility). Without the permission — or if the app doesn't come to the front,
or you switch away while it is happening — she does not press any key at all: the answer is simply on the clipboard, the chat is open, and the card says so
("Copied · press ⌘V in the chat"). She never types into an app other than the one the answer belongs to. The clipboard is put back afterwards
unless you copied something else in the meantime.

For a chat with no window to jump to (Deep Code runs in a terminal) the answer is only copied. In the demo nothing is sent anywhere.

Settings › **Answer here** turns the whole card off; then the ❓ card behaves as it used to — click her to go and answer in the chat.
`./.build/release/YukioPlayer --question out.png` draws the card offscreen (single-select, multi-select, no options, already answered)
and prints its click regions, which is how its layout is checked without a screen recording.

## Several chats running at once: which one to follow

One Yukio follows only one chat at a time (otherwise the motions would get mixed up). The default is **Auto**, in this order:

1. **Whatever is waiting on you comes first**, even if other chats are busy at full tilt. When several are waiting they are ranked by tier: **waiting for your decision (❓ question card) → the whole turn stopped on an error → answered and holding the ✅ done card**; within a tier the most recent one is shown. Deal with one and the next surfaces on its own. (This tier order is copied from the ChatGPT desktop app's pet: `waiting → failed → review → running`.)
   A finished turn's sign is always raised and kept, even if she happened to be following another chat at that moment; a completion reminder is never dropped just because its chat wasn't up.
2. When nothing is waiting on you, she follows the chat that is **still working**: she doesn't switch while it keeps going; only when it stops, is interrupted, or goes quiet does she switch to the other chat with the most recent activity.
3. **A sign held for 15 minutes without a click steps aside** (`signYieldMs`): the sign doesn't come down, it just stops occupying her, and she goes to show the chat that is still working; once that one stops too, the sign comes back up on its own, and clicking it still jumps back to the original chat. Come back after half an hour away and you see "what the working chat is doing" rather than a sign that has been up for half an hour; in the chat list that entry reads "Holding the sign for you (stepped aside)". The ❓ question card has no such 15 minutes: the whole chat is stuck there waiting for you, and it steps aside naturally once it counts as gone quiet after `staleOpenToolMs` (30 minutes).

The head bubble is handy here: it shows **that chat's** title, so you can tell at a glance which one finished. Click the raised sign and you jump back to that chat; if you'd rather not go now, the menu has "Lower the sign, don't open the chat", and once it's down she goes straight back to the chat that is still working.

To keep her on one particular chat, pin it in the **Chat to follow** submenu:

- The first item is "Auto (done and questions first)", the default described above; a checkmark means it's the one in use. The submenu title also reports a count: how many chats are waiting for you (or, when none are, how many are running), as in "Chat to follow (2 waiting for you)" or "(3 running)".
- Below it are the chats from the last half hour, at most 10, ranked by the tiers above: the ones waiting for you first, then the running ones, then by how long they have been quiet. Each shows the chat name (Claude's session title, or the first line of the request if there is none) and what it is doing right now ("Editing a file", "Holding the sign, click her", "Stopped on an error", "12 min ago").
- Click one to pin it: she switches immediately without waiting for the debounce, and **no other chat can take her away, however busy it gets or however often it finishes**. When the pinned chat stops she idles and waits, and doesn't wander off to follow another chat.
- A pin lasts only for this run; quit and relaunch and she is back on Auto. Like a raised sign, it's a "choice for right now". To go back to Auto, click "Auto" again.
- While a chat is pinned, other chats still raise and keep their signs; she just doesn't show them. Back on Auto they surface in tier order.

### The card stack over her head: other chats

She can only act out one chat at a time, but when other chats have something to say nobody should be left in the dark. **The bubble over her head is the bottom card** (the chat she is following); every other chat gets a card of its own, stacked upward with the same corner radius, outline, font size, and two-line layout (`CardLook`), the most urgent one right next to the bubble:

| On the card | Content |
| --- | --- |
| Color band on the left | State: Waiting (orange), Error (red), Ready (green), Running (blue) |
| Top line (same as the bubble's top line) | Chat name |
| Bottom line (same as the bubble's bottom line) | What it is doing, what it is waiting for, or the error that stopped it |
| Bottom right | Short state label |
| ✕ at top right | Collapses just this card without opening the chat |

**Normally there is only one** (the bubble over her head, about the chat she is following). When other chats have something to say, a thin "N more" pill appears above the bubble.

- **Click the card over her head (or that pill)**: the stack fans out, one card per other chat, the most urgent one next to the bubble.
- **Click one of the fanned-out cards**: **switches her to that chat** (replacing the previous one, the same as pinning it under "Chat to follow" in the menu), then the stack collapses on its own.
- **Click ✕**: collapses just that one reminder without switching chats. The dismissal is remembered per turn: the card reappears when that chat has activity in its next turn.
- **Right-click a card**: "Open this chat" / "Stop reminding about this chat" (for this run).
- Once a chat is pinned, an extra "Auto" appears at the top of the fanned-out stack; click it to go back to Auto (follow whoever is most urgent).
- A fanned-out stack collapses by itself after 12 seconds without a click; clicking the bubble again also collapses it. At most 8 cards are fanned out; when there isn't room above, fewer are shown, and they never cover the bubble.
- **This doesn't conflict with clicking her**: clicking **her** = jump to that chat and lower the raised sign; clicking **the card over her head** = fan out and pick a chat. The two are independent.
- "Show other chats" in the menu turns the whole stack off; it is also hidden while following is paused or the demo is playing. When the bubble is turned off, the stack starts from the head-top line.
- Clicks in the gaps between cards still pass through; only the cards themselves take clicks.

The ordering uses the same tiers as her own choice of whom to follow, so **the card right next to the bubble is "the one she will show next"**.

This design follows the notification tray of the ChatGPT desktop app's pet: it too **normally shows only the top card** (the pet's motion takes its state from that card, `Fo(y[0]).mascotState` in the code), keeps the rest tucked behind with a count badge, and expands only on click (`isNotificationStackCollapsed` / `canExpandActivityStack`, accessibility label `Expand activity stack, {count} items`); the ordering is the same set of tiers too (`ld()`: waiting 0 → failed 1 → review 2 → running 3). The difference is that **picking a card after expanding means "make this the chat she follows"** rather than opening the chat window; opening the window is left to the right-click menu and to clicking her herself.

On the command line, `--chats` shows this list without opening a window:

```
→ 924655c8-…  多个聊天同时运行时的选择功能 · Working
  fd060c60-…  问题牌子点击跳转聊天 · Thinking
  8fcc36d9-…  大小调整滑条 · 4 min ago
```

## App icon

`Resources/AppIcon.icns` is the cover shown in Finder, Spotlight, and "Open With"; `tools/icon/make_icon.py` generates it (needs numpy, Pillow, and the system's own iconutil). The packaging script copies it into the app and writes `CFBundleIconFile` in Info.plist.

The picture is the top-left cell of `sources/read_web-corrected-source-2x2.png` (627×627, the highest-resolution Yukio in the repo): the magenta background is keyed out by difference and the foreground color solved for, leaving no purple fringe; it is cropped to head and shoulders, with the desk edge resting on the bottom of the icon. The frame is a continuous rounded square of 824 on a 1024 canvas (superellipse exponent 5, matching measurements of this machine's system icons), with a light ice-blue gradient behind it, a soft glow behind her head, a cool light from the tablet, and a faint drop shadow underneath. All ten sizes from 16 to 1024 are scaled down from the same 1024 image, and the sizes ≤64 get a little extra sharpening.

- The default is the light version; `--style night` produces a dark blue one; `--png out.png` exports only the 1024 image; `--preview p.png` writes a side-by-side of every size, for eyeballing whether the small icons are still recognizable.
- The app is an LSUIElement (it doesn't go in the Dock), so this cover mainly shows up in Finder and Spotlight; the menu bar avatar is still taken from the motion sprite strips (`SpriteLibrary.avatarImage()`).

## Structure

```
Sources/YukioCore/            UI-independent, fully testable
  Events.swift                Event protocol (task_start/end/abort/failed, activity_start/end/failed, thinking, final_answer, source_lost, session_title, todo_list/update)
  ActivityRouter.swift        Session isolation, focus selection (done and questions first, one chat can be pinned), debounce, minimum hold, merge window, lost-contact fallback, bubble content and chat list
  ClaudeToolClassifier.swift  Claude tool → activity and short description
  ClaudeParsers.swift         Transcript line → events; hooks JSON → events; task list; JSON stream splitting
  LiveSources.swift           Read-only following of ~/.claude/projects; optional hooks inbox
  ClaudeSessionLinks.swift    Transcript session → the matching chat in the Claude desktop app (read only, for click-to-jump)
  HangSwing.swift             The swing while held by the big hand (pendulum + damping + air drag, pure numbers)
  ActivityCards.swift         The card stack over her head: one card per chat, ordering / collapsing / muting
  Catalog.swift / SpriteTimeline.swift / HeldValue.swift / DemoScript.swift
Sources/YukioPlayer/          macOS window, head bubble, dragging, menu bar, command-line modes
Resources/Assets/            Final assets copied from the handoff package (seven activity sets, computer desk, base motions)
Resources/Assets/motion/     Generated small-motion sprite strips and motion.json (override same-named animations)
Resources/AppIcon.icns       App icon (the cover shown in Finder)
tools/motion/                Motion generator (Python: base image + local smooth warp + blinking)
tools/proportion/            Standing-pose leg length (stretches idle / sad to the same proportions as "held")
tools/hang/                  Cropping script for the held frame (Python: align by head width, measure the grip point)
tools/icon/                  Icon generator (Python: keying + rounded square + ten sizes)
integrations/claude-hooks/   Official hooks integration (enabled on this machine, see below)
```

## Scheduling parameters (`RouterConfig`, all starting points for tuning)

| Parameter | Default | Notes |
| --- | --- | --- |
| `debounceMs` | 400 | The candidate state must stay stable this long before she switches |
| `minHoldMs` | 1500 | Each displayed state is held at least this long |
| `toolGraceMs` | 3500 | A finished tool still counts as its activity for this long, merging consecutive calls of the same kind (in real transcripts calls are mostly 2 to 4 seconds apart) |
| `respondHoldMs` | 3000 | After a task ends, "handing over the report" is shown this long, enough to play the paper-tidying beat, then the ✅ done card takes over |
| `completeArmMs` | 8000 | Only decides "how recently a task must have finished to raise the sign": once raised the sign doesn't come down by itself, but old records replayed at player startup won't raise an expired sign |
| `signYieldMs` | 15 min | A sign held this long without a click steps aside for the chats still working (the sign isn't lowered; it comes back up once that chat stops) |
| `failedHoldMs` | 4000 | How long at most the sad pose shows after a tool failure (the next tool to start takes over), then back to thinking |
| `failedLingerMs` | 8000 | How long the sad pose lingers after the turn is aborted by an API error, then back to idle |
| `staleNoToolMs` / `staleOpenToolMs` | 10 min / 30 min | How long without events counts as lost contact, then back to idle |

With several chats running at once she follows only one; the rules are in "Several chats running at once: which one to follow" above.

## Event sources

### Which assistant she follows

The menu item **Assistant** picks the family, and the choice is stored in `UserDefaults` under `source` (the same key name the Windows build uses):

| Menu | Reads | Notes |
| --- | --- | --- |
| Auto (whoever is working) — default | all three below | Chats from every family compete under the same rules (see "Several chats running at once") |
| Claude Code | `~/.claude/projects/<project>/<session>.jsonl` (honors `CLAUDE_CONFIG_DIR`), plus the optional hooks inbox | Session titles, task lists, ❓ `AskUserQuestion` |
| DeepSeek (Deep Code) | `~/.deepcode/projects/<code>/<session>.jsonl` and that folder's `sessions-index.json` (honors `DEEPCODE_CONFIG_DIR`) | The index is the only place "waiting for your approval" is written |
| GPT (Codex) | `~/.codex/sessions/<year>/<month>/<day>/rollout-*.jsonl` (honors `CODEX_HOME`) | One file per chat; both the Codex desktop app and the CLI write it |

Switching families clears everything first (the pinned chat and any raised sign belong to the old family) and replays the new family's logs from scratch.

### Default: session logs (read only, zero configuration)

Read only; nothing any of these tools owns is ever modified. At startup the tail of the sessions active in the last 15 minutes is replayed to recover "what is happening right now".

Note: these are the session records each tool writes locally, **not a public API**, and the formats may change between versions; a parse failure only means fewer events, never a crash, and she returns to idle under the lost-contact rules. Subagent (sidechain) activity does not drive the main character.

Codex writes two streams into the same file and both are used: `response_item` (what goes to the model) carries a tool call the moment it starts, so the motion keeps up, while `event_msg` (`item_completed`, `task_complete`, `turn_aborted`) arrives after the fact and fills in success or failure and the end of a turn. The desktop app runs almost everything through one `exec` tool whose argument is a piece of JavaScript, so what she is actually doing is read out of that text: `tools.exec_command({cmd:…})` goes through the same shell classifier as Claude's `Bash`, `tools.apply_patch` is editing a file, `tools.view_image` is looking at an image, and `tools.write_stdin` keeps the previous motion.

### Claude Code official hooks (enabled on this machine)

The second source goes through Claude Code's official interface. It was enabled on this machine on 2026-09-16 with the user's consent: the script is installed at `~/Library/Application Support/YukioPlayer/yukio-hook.sh`, and five events are registered in `~/.claude/settings.json`: `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`, and `SessionEnd`. The settings from before the change are backed up at `~/.claude/settings.json.bak-20260916-225949`.

To enable it on another machine:

1. `mkdir -p ~/Library/Application\ Support/YukioPlayer && cp integrations/claude-hooks/yukio-hook.sh ~/Library/Application\ Support/YukioPlayer/ && chmod +x ~/Library/Application\ Support/YukioPlayer/yukio-hook.sh`
2. Merge the `hooks` from `integrations/claude-hooks/settings-snippet.json` into `~/.claude/settings.json` (if hooks already exist, merge entry by entry rather than overwriting).

To turn it off: just delete those hook entries from `settings.json`; the transcript source keeps working as usual.

The script only appends the hook input to the inbox `~/Library/Application Support/YukioPlayer/claude-hooks.jsonl` (cleared automatically past 5 MB), prints nothing, and always exits 0; measured at about 0 ms per call, so it never blocks Claude. With both sources on, events are deduplicated by `tool_use_id`. Hooks carry no session title, so with hooks alone the bubble title uses the first line of the request.

Claude Code has only nine event names: `PreToolUse`, `PostToolUse`, `Notification`, `UserPromptSubmit`, `Stop`, `SubagentStop`, `SessionStart`, `SessionEnd`, and `PreCompact`. The `PostToolUseFailure` and `StopFailure` written in an earlier snapshot don't exist and have been removed. `PostToolUse` fires only after a tool succeeds, so tool failures and whole-turn API errors are still filled in from the session transcripts, which is also why both sources are kept.

## Known limitations

- The standing poses (idle, sad) now match the held image's proportions but are still a little shorter overall: the frame is 208 tall versus 240 for the held one, with the difference in the torso and boots. The seated-at-the-desk sets were drawn as a separate batch, with heads about 10% bigger than the standing pose.
- Current motion sheets use 384×416 pixels (2x); the held image is 384×480. Sizes above 200% can appear softer.
- The base images for `question_for_user` and `task_complete` were not drawn in the same batch as the other seated states, and the desk legs are off by two or three pixels; this gap is within the range the existing states already differ by among themselves (`read_web` and `write_file` differ by 1208 pixels; these two are at 1303 and 1936), so switching is no more noticeable than it is now.
- The motions are small warps of a base image and only suit movements within 2 pixels; big motions like turning a page or changing pose need new drawings.
- While held there is only one frame and no blinking: the `tools/motion` pipeline is hard-coded to 192×208, and the held frame is 192×240, so blinking would first need that size limit lifted.
- The swing is computed at the main loop's 30 Hz, 18 frames per back-and-forth; on a fast flick you can see the individual frames.
- The held pose was not drawn in the same batch as the seated poses (newly generated by GPT); after aligning by head width the heads match, but the limbs are proportionally a little longer.
- Thinking blocks are only written to the transcript after the message completes, so "Thinking" is inferred (a task is running and no tool is executing); the final answer also appears only once fully written, so Thinking is shown while it streams.
- The bubble's task list is rebuilt from the transcript: at startup only the last 1 MB of each session is replayed, so in very long sessions tasks created earlier may be missed and progress undercounted until Claude updates the list again.
- Session titles are generated by Claude, and when a session moves on to a new request the title doesn't necessarily follow.
- Click-to-jump recognizes Claude desktop app sessions and Codex chats (`codex://threads/<session id>`, the id being the one in the rollout file name; the Codex app's own log calls it `threadId`). An agent running in a terminal has no matching chat window, so a click only brings the desktop app to the front. Deep Code has no window to open, so there the click item is hidden and the sign simply comes down. The Codex link has not been clicked through end to end yet — needs an eyeball.
- Codex session logs carry no chat title, so in the chat list and the bubble those chats are named by the first line of the request (or the session id when even that is outside the replayed tail).
- A raised sign occupies her for the first 15 minutes: another chat starting work can't take her away (this is deliberate, so you don't miss the one that finished). If you don't want to go now, click it, or use "Lower the sign, don't open the chat" in the menu; you can also pin another chat. After 15 minutes she goes to show the working chat first, sign still up, and comes back once that one stops.
- Once a chat is pinned she no longer switches automatically; when it stops she idles and waits. If you forget you pinned one, the menu's second line "Following: … (pinned)" reminds you.
- The main loop runs at 30 Hz over the 50 fps animation timeline. Release builds load lossless pages with a 32 MiB page-cache cap; total process memory also includes frames, windows and other resources.
- The app is ad-hoc signed on this machine; distributing it to others needs a proper signature and notarization.
