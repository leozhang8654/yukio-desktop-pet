<div align="center">

**English** · [简体中文](README.zh-CN.md)

<h1>Yukio · the desktop pet that works alongside your coding agent</h1>

<img src="docs/readme/states-en.png" width="900" alt="Twelve things Yukio does at her desk: thinking, reading files, viewing an image, writing files, running tests, browsing the web, handing in the answer, holding up the done card, holding up the question card, other work, something failed, idle">

<p>
<a href="https://github.com/leozhang8654/yukio-desktop-pet/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/leozhang8654/yukio-desktop-pet?label=download&color=2f6feb"></a>
<a href="https://github.com/leozhang8654/yukio-desktop-pet/releases"><img alt="Total downloads" src="https://img.shields.io/github/downloads/leozhang8654/yukio-desktop-pet/total?color=2f6feb"></a>
<img alt="macOS 13 or newer" src="https://img.shields.io/badge/macOS-13%2B-000000?logo=apple&logoColor=white">
<img alt="Windows 10 and 11" src="https://img.shields.io/badge/Windows-10%20%2F%2011-0078D4">
<img alt="Swift and AppKit, no third-party dependencies" src="https://img.shields.io/badge/Swift%20%2B%20AppKit-zero%20dependencies-F05138?logo=swift&logoColor=white">
<img alt="Python and ctypes, Pillow is the only dependency" src="https://img.shields.io/badge/Python%20%2B%20ctypes-Pillow%20only-3776AB?logo=python&logoColor=white">
</p>

</div>

**Yukio (雪绪)** is a white-haired, blue-eyed girl in a navy butler's uniform who sits in the corner of your screen and acts out what your AI coding agent is doing, as it happens. Claude Code reads a file, she opens a book. It edits, she picks up the pen. Tests run, she checks two sheets against each other. It finishes, and she holds up a ✅ card until you click her. That click drops you straight back into the chat that just finished.

She follows three families of agent, and you pick which one in her menu under **Assistant**: **Claude Code**, **DeepSeek's [Deep Code CLI](https://api-docs.deepseek.com/quick_start/agent_integrations/deepcode/)**, and **GPT's [Codex](https://developers.openai.com/codex/)** (the desktop app and the CLI both write the same session logs). The default, **Auto**, follows all three at once and shows whichever chat has something to say. Both builds are native, small, and never touch the network.

## Download

Grab the file for your system from the [latest release](https://github.com/leozhang8654/yukio-desktop-pet/releases/latest). Nothing to compile, nothing else to install.

| You use | Download | Then |
| --- | --- | --- |
| macOS 13 or newer (Apple silicon and Intel) | `Yukio-0.1.0-macOS.zip`, about 6 MB | Unzip, drag `Yukio.app` into Applications, allow it once (below) |
| Windows 10 / 11, 64-bit | `Yukio-0.1.0-Windows.exe`, about 21 MB | Double-click. Python and the artwork are packed inside |

<details>
<summary><b>macOS says "Apple could not verify Yukio…"</b></summary>

The app carries only an ad-hoc signature and is not notarized (that needs a paid developer account), so Gatekeeper stops it once. It is not because the app did anything.

1. Double-click `Yukio.app` and click **Done** on the warning.
2. Open **System Settings › Privacy & Security**, scroll to **Security**, click **Open Anyway** next to the Yukio line, confirm, and enter your password.

Since macOS 15 the old right-click › Open trick no longer bypasses Gatekeeper. From Terminal it is one line instead:

```sh
xattr -dr com.apple.quarantine /Applications/Yukio.app
```

Builds you compile yourself are not quarantined and never show this.

</details>

<details>
<summary><b>Windows says "Windows protected your PC"</b></summary>

The exe is not code-signed. Click **More info**, then **Run anyway**. Windows asks only once.

</details>

The SHA-256 of every file is on the release page if you want to check a download.

Once running, Yukio appears in the bottom-right corner of the screen and a small avatar of her appears in the macOS menu bar or the Windows tray. On macOS, right-clicking Yukio opens Settings directly; click the menu-bar avatar or launch the app a second time for the full menu. Want a tour first? Pick **Play demo** from Settings or the menu and she walks through every state in 60 seconds. English is the default, 中文 is one click away in Settings, and the choice is remembered.

## What she does

- **Twelve states, one character.** Thinking, reading files, viewing an image, writing files, running tests, browsing the web, handing in the answer, the ✅ done card, the ❓ question card, other work, something failed, idle. The mapping from each agent's tools to a state is explicit and covered by tests (one set of rules for all three: shell commands are classified the same way whether they arrive as Claude's `Bash`, Deep Code's `bash`, or Codex's `exec`). Unknown work falls back to typing at the computer instead of guessing.
- **Micro-motions, not slideshows.** Every state is one approved base image that a generator brings to life in small, continuous moves: the pen travels along the line, the magnifier sweeps the photo, a finger scrolls the tablet, two hands take turns on the keyboard, eyes blink in the right skin tone. The desk and chair never shift by a pixel, and the generator checks that. 20 to 30 frames per second.
- **She tells you when it is your turn.** After the final answer she holds up the ✅ card and keeps holding it until you click. `AskUserQuestion` raises the ❓ card instead. Click her and the Claude desktop app opens that exact chat through its own `claude://` link. If that chat is already in front of you, she skips the card altogether.
- **A bubble over her head.** The session title on top, the current step below, taken from the task list when there is one and otherwise from the tool: "Edit main.swift", "$ swift test", "developer.apple.com". A progress count and a thin bar sit beside it. Only file names, the first words of a command, and domains ever appear.
- **Several chats at once.** She can only act out one chat, so she picks the one that needs you: waiting for your answer, then stopped on an error, then done and holding a card, then whatever is still running. Every other chat becomes a small card stacked on top of the bubble. Click the bubble to fan them out, click a card to switch to that chat, or pin one chat from the menu.
- **Pick her up.** Drag her and she dangles from an invisible hand like a kitten held by the scruff: a damped pendulum with inertia, air drag, and a little sag when you yank upward. Let go and she settles in about a second.
- **Private by design.** She only reads the session logs the agents already write to disk, read-only. No network, no changes to any tool's settings, no conversation content stored or shown.
- **Light.** About 1% CPU and 45 MB of memory on the macOS build. The download is 6 MB and there are no third-party dependencies.

## A day at the desk

<table>
<tr>
<td><img src="docs/readme/desk.gif" width="192" alt="Yukio thinking, reading, checking a screenshot with the magnifier, writing, running tests, failing, fixing, passing, tidying the report and holding up the done card"></td>
<td>

Thinking → reading the code → checking a screenshot → editing → tests fail → fixing → tests pass → tidying the report → ✅.

These are the actual motion strips the app plays, exported at a slightly lower frame rate to keep the file small. Right after the answer she straightens the stack of papers, taps it twice on the desk, and only then raises the card.

</td>
</tr>
</table>

## The bubble and the card stack

<img src="docs/readme/bubble.png" width="900" alt="Six bubble samples above Yukio: a step with 3 of 7 done, a long title cut short, thinking, an error on swift test, the question card with 'Your turn · click to open', and the done card with 'Done · click to open'">

<img src="docs/readme/cards.png" width="470" alt="Left: the bubble with a '5 more' hint above it. Right: fanned out, five other chats stacked over the bubble, each with a colour bar for its state: waiting, failed, ready, running">

Left: normally there is just the bubble and a thin "5 more" hint. Right: fanned out, with the most urgent chat closest to the bubble. Orange is waiting for you, red stopped on an error, green finished, blue still running. The ✕ dismisses one card until that chat does something new. Cards fold back after 12 seconds on their own.

## Picking her up

<img src="docs/readme/drag.gif" width="236" alt="Yukio dangling from an invisible hand: swinging while dragged, settling after release, sagging and bouncing back when lifted sharply">

Straight out of the app's own swing model, with the camera following her so you see the tilt rather than the travel. Dragged sideways she lags behind the hand and swings past centre when it stops. Let go and she settles in about a second. A sharp lift makes her sag and spring back. The hand is invisible: the grip is a point just above her head, and the pendulum length is measured from the artwork itself, so a larger Yukio swings less.

## How she knows

**Where she reads from.** Claude Code writes a transcript for every session under `~/.claude/projects`; Codex writes one per chat under `~/.codex/sessions/<year>/<month>/<day>/rollout-*.jsonl`; Deep Code keeps its sessions under `~/.deepcode/projects`. Yukio tails whichever of those you picked, read-only, and turns tool calls into states. A tool call shows up about 0.2 seconds after it starts, then a 0.4 second debounce keeps her from twitching between quick calls. Claude Code's official hooks can be wired in as a second source; the script and settings snippet are in `YukioPlayer/integrations/claude-hooks/`, and enabling them is your call.

**Windows.** The same three families, at `%USERPROFILE%\.deepcode\projects`, `%USERPROFILE%\.claude\projects`, and `%USERPROFILE%\.codex\sessions`; for Deep Code she also reads the session index, which is the only place "waiting for your approval" is written. Point Claude Code at DeepSeek's Anthropic-compatible endpoint and its transcripts are followed the same way. Any other tool can drive her by appending JSON lines to `%LOCALAPPDATA%\Yukio\inbox.jsonl`.

These logs are internal to those tools, not public APIs. If a format changes she shows fewer events and drifts back to idle instead of crashing.

## Build from source

**macOS** needs only the Xcode Command Line Tools.

```sh
git clone https://github.com/leozhang8654/yukio-desktop-pet
cd yukio-desktop-pet/YukioPlayer
swift test                      # 101 tests: routing, debounce, classification, parsers, bubble text, timelines, chat picking
./scripts/build-app.sh          # build/Yukio.app
open build/Yukio.app
./scripts/package-release.sh    # universal binary zip in dist/
```

**Windows** needs Python 3.9 or newer.

```bat
cd yukio-desktop-pet\YukioWin
pip install pillow
python run.py
python run.py --selftest                                          # 141 tests, runs on any OS
powershell -ExecutionPolicy Bypass -File scripts\build-exe.ps1    # dist\Yukio.exe, artwork included
```

No Windows machine? The GitHub Actions workflow builds the exe on a real Windows runner and smoke-tests it there: it launches the exe, finds her windows, checks the pose against a staged Deep Code session, and compares screenshots pixel by pixel at 100% and 150% scaling.

Both players have window-less modes for poking around: `--demo`, `--replay session.jsonl`, `--watch 60`, `--chats`, `--snapshot`, `--bubble`, `--cards`, `--hang`. See the two player READMEs for the full list.

## Repository map

| Path | What is in it |
| --- | --- |
| `YukioPlayer/` | macOS player: Swift sources and tests, bundled artwork and app icon, the motion, icon, and drag-pose generators under `tools/`, build and release scripts. [README](YukioPlayer/README.md) |
| `YukioWin/` | Windows player: Python and ctypes layered window, tests, PyInstaller spec, the smoke test CI runs. [README](YukioWin/README.md) |
| `assets/` | Final transparent artwork: the seven activity strips, the desk, the two cards, the base poses |
| `sources/` | High-resolution generation sources, magenta-keyed |
| `references/` | Contact sheet, generation prompts, image inventory |
| `docs/readme/` | The images on this page, and `make_images.py` to regenerate them |
| `HANDOFF.md` | Design log: requirements, feedback, and what changed when (Chinese) |
| `START_HERE.md`, `PLAYER_REQUIREMENTS.md`, `CONTINUE_PROMPT.txt`, `native-current/`, `preview.html` | The original hand-off bundle, kept for history |

## Good to know

- English by default. Right-click Yukio to open Settings, where Language can be switched to 中文; the choice is remembered. Descriptions already attached to earlier events keep their language until the next event arrives. The command-line check modes still print their diagnostics in Chinese.
- The art is drawn and animated at 192×208, then shipped as 2x sheets (384×416; the picked-up frame 384×480) upscaled with an anime super-resolution model. The old thick, blurry dark fringe from keying is gone; a thin half-point outline is drawn around her instead. She stays crisp on Retina and HiDPI screens; above 200% she starts to soften again.
- Click-to-jump needs a desktop app: the Claude app for Claude Code chats, the Codex app for Codex chats (`codex://threads/<id>`). An agent run in a terminal has no chat window to open, so a click only brings that app to the front. Deep Code chats live in the terminal, so there a click simply lowers the card. Verified on macOS; the Windows path is written the same way but has not been tried on a real machine yet.
- Size is a 50 to 200% slider on macOS and seven steps plus ±5% nudges on Windows, because a native Win32 menu cannot hold a slider.
- The binaries are unsigned and not notarized. Building from source avoids the first-launch prompts.

## How the art is made

The character was drawn by ChatGPT's image model from a fixed reference sheet, then keyed, cropped, and animated by the Python tools in `YukioPlayer/tools/`. The animation is deliberately not generated frame by frame. Each state has a single confirmed base image. Parts that need to move visibly, such as a hand, the pen, the magnifier, or the papers, are lifted onto their own layer and moved by two to five pixels with the hole filled in behind them. Head and eyes use small local warps. Every output frame is checked so the desk legs stay exactly where they were. The finished frames are then upscaled to 2x with Real-ESRGAN's anime model and given a thin dark outline, and anything that stays still at 1x is kept pixel-identical across frames at 2x too.

If Yukio makes your day at the keyboard a little nicer, a ⭐ helps other people find her.
