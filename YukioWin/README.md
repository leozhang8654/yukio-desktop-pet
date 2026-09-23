**English** · [简体中文](README.zh-CN.md)

# Yukio desktop pet (Windows edition: DeepSeek, Claude or GPT)

Yukio (雪绪), a white-haired, blue-eyed girl in a butler's uniform, sits in the bottom-right corner of your Windows desktop and switches poses to match whatever your coding agent — **DeepSeek's Deep Code CLI**, **Claude Code**, or **GPT's Codex**, picked from the tray menu under "Assistant", all three by default — is doing right now: thinking, reading a file, viewing an image, writing a file, running tests, browsing the web, handing in the answer. For any other work she sits at the computer and types. She slumps when something goes wrong, puts up the ❓ question card when a decision is yours to make, and holds up the ✅ done card once the answer is in, waiting for you. While she is holding up the sign, click her and she lowers it (if the chat she is following belongs to the Claude desktop app, she also jumps back to that chat). If that chat is already open in front of you, she doesn't hold up the sign at all. With no task she idles. When several chats are open at once, whichever has just finished or is waiting for your decision is shown first; the rest hang as a stack of small cards piled upward from the bubble, and clicking one takes you to that chat. You can also pin one chat from the menu so she follows only that one. Every pose keeps moving in small, continuous ways (writing, typing, turning her head, blinking), and the small bubble over her head shows the current task and its progress.

The artwork, the activity mapping, the debounce and hold times, the focus rules, the sign and the card stack, and the swing parameters for when she is picked up are all identical to the macOS edition (`../YukioPlayer`, Swift). Only the two ends are swapped: **whose session logs she reads** (all three families) and **what draws the window** (a Windows layered window instead of AppKit). The only differences left are the size control (fixed steps here, a slider there) and how far click-to-jump has been tested on a real machine; both are listed under "Known limitations" at the end.

The only dependency is Pillow. The window, the tray and the menus call the Windows API directly through ctypes; there is no other UI framework.

## Download (no Python needed)

Grab `Yukio-0.1.0-Windows.exe` (about 21 MB) from [Releases](https://github.com/leozhang8654/yukio-desktop-pet/releases/latest), put it anywhere, and double-click it. Python, Pillow and the artwork are all packed inside. It needs 64-bit Windows 10 or newer.

The first time you open it, Windows may show the blue "Windows protected your PC" screen. The app has no code-signing certificate; click "More info", then "Run anyway", and it won't ask again.

## Run from source

You need Windows 10 or newer and Python 3.9 or newer (tick "Add python.exe to PATH" during installation).

```bat
git clone https://github.com/leozhang8654/yukio-desktop-pet
cd yukio-desktop-pet\YukioWin
pip install pillow
python run.py
```

Yukio appears in the bottom-right corner of the screen, and a small avatar of her appears in the taskbar tray. To get a `Yukio.exe` that anyone can double-click without installing Python:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build-exe.ps1
```

The result is `dist\Yukio.exe` (about 25 MB, artwork included). Without a Windows dev environment, you can also run the "Build Windows Yukio" workflow under GitHub Actions and download the exe it produces.

## How to use

| What you want to do | How |
| --- | --- |
| Move her | Press on her and drag. While dragged she looks picked up by an invisible hand by the back of her collar and swings like a pendulum: drag right and her feet trail behind to the left, stop and she swings past vertical before settling, yank her upward and she first drops, then bounces back. Once you let go and the swing dies down she returns to her current pose, and the position is remembered |
| Click her | While she is holding up the ✅ done card: the sign goes down (that turn is over). While the ❓ question card is up: the card stays, the question is still waiting for you. If the chat she is following belongs to the Claude desktop app, either click also jumps back to that chat (see "Click to jump back to the chat" below) |
| Open the menu | Right-click her (or double-click), or left-click her small avatar in the tray |
| Change size | Menu › Size: seven fixed steps, 50% / 75% / 100% / 125% / 150% / 175% / 200%, plus "Bigger (+5%)" and "Smaller (−5%)", so she can stop at any multiple of 5% between 50% and 200%. On high-DPI screens the display scaling is applied on top automatically, so she stays sharp |
| Change language | Menu › Language: English / 中文. English is the default; the choice is remembered in settings.json as "language". Descriptions already attached to earlier events keep their language until the next event |
| Pause following | Menu › Follow AI activity. With it off she stays idle but still receives events, so she catches up the moment you turn it back on |
| Hide the bubble | Menu › Show task bubble |
| Hide other chats | Menu › Show other chats. With it off only the bubble remains and no cards are stacked |
| Change which assistant she follows | Menu › Assistant: Auto (whoever is working) / Claude Code / DeepSeek (Deep Code) / GPT (Codex) |
| Pick a chat to follow | Menu › Chat to follow. The default is "Auto (done and questions first)": whichever chat has just finished or is waiting for your decision is shown first, and when there is none she follows the one most recently at work. Click a chat to pin it; no other chat can take her away, however busy it gets. A pin lasts only for this run |
| See it in action | Menu › Play demo: walks through every state in 60 seconds; it is not real activity (it plays once by itself the first time you open her if neither tool is installed) |
| Quit | Menu › Quit Yukio |

Double-clicking `Yukio.exe` again doesn't open a second Yukio; it makes the one already running pop up her menu.

Settings live in `%LOCALAPPDATA%\Yukio\settings.json` (position, size, the follow toggle, whether the bubble and the cards are shown).

> On the macOS edition, "Size" is a 50%–200% slider that resizes her live as you drag. The Win32 tray menu is a native system popup menu and a slider won't fit in it, so this edition uses seven fixed steps plus the two ±5% items instead. The range and the step are the same; it just takes a few more clicks.

## How she knows what DeepSeek is doing

### Default: Deep Code's local session logs (read-only, zero config)

[Deep Code](https://api-docs.deepseek.com/quick_start/agent_integrations/deepcode/) is the terminal coding assistant listed in DeepSeek's docs (`npm i -g @vegamo/deepcode-cli`, command `deepcode`). It keeps each project's sessions in:

```
%USERPROFILE%\.deepcode\projects\<project code>\
    sessions-index.json     session list: title and status (processing / ask_permission / failed …)
    <session ID>.jsonl      message log, one entry per line
```

Yukio reads only these two. From the `.jsonl` she takes the role, the time, the tool name and arguments, whether the tool reported an error, and the task list from `UpdatePlan`. From `sessions-index.json` she takes the title, plus the states that are only written to the index: "waiting for your approval / interrupted / this turn failed". **She never writes to or modifies any Deep Code file, and none of its settings need to change.** Conversation content is never saved or uploaded; the bubble only ever shows file names, the first few words of a command, and the domain of a URL.

These are session logs Deep Code writes locally, not a public API, and the fields may change between versions. When something can't be parsed she just misses events rather than crashing, and drops back to idle under the gone-quiet rule.

### GPT (Codex) sessions work too

Codex — the desktop app and the CLI both — writes one file per chat under `%USERPROFILE%\.codex\sessions\<year>\<month>\<day>\rollout-*.jsonl` (`CODEX_HOME` is honored). She reads the tool calls out of it the same way; for the desktop app's one all-purpose `exec` tool, what is actually happening is read out of the JavaScript argument (`tools.exec_command({cmd:…})` goes through the same shell classifier as Claude's `Bash`, `tools.apply_patch` is editing a file, `tools.view_image` is looking at an image). Same rules as the macOS edition (`yukio/parsers_codex.py` is a port of `CodexParsers.swift`), and `tests/test_parsers_codex.py` asserts the same things.

### Claude Code transcripts work too

Point Claude Code at DeepSeek's Anthropic-compatible endpoint (`ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic`) and it runs a DeepSeek model but still writes transcripts in Claude Code's format (`%USERPROFILE%\.claude\projects`). She follows that route just the same, and the menu lets you restrict her to either one.

### Generic inbox: other tools can drive her too

Append JSON to `%LOCALAPPDATA%\Yukio\inbox.jsonl` (one object per line) and Yukio acts on it:

```json
{"kind": "task_start", "session": "build", "detail": "Refactor the login page"}
{"kind": "activity_start", "id": "t1", "tool": "edit", "input": {"file_path": "a.py"}}
{"kind": "activity_end", "id": "t1"}
{"kind": "final_answer"}
{"kind": "task_end"}
```

The fields are documented at the top of `yukio/bridge.py`. `scripts\yukio-notify.py` is a ready-made script for Deep Code's `notify` hook (put `"notify": "C:\\Users\\you\\.deepcode\\yukio-notify.py"` in `~/.deepcode/settings.json`). You normally won't need it: it fires only once per turn, far less detail than reading the session log directly. It is kept so that if Deep Code ever changes its log format, at least "task finished / error" still get through.

## Activity mapping

| State | Pose | Deep Code source | Claude Code source |
| --- | --- | --- | --- |
| `thinking` | A: thinking, chin in hand | A task is in progress with no tool running; `reasoning_content`; `UpdatePlan` | Same as left; TodoWrite, Task*, plan mode |
| `read_file` | B: reading a book at the desk | `read`; read-only shell commands (cat, rg, ls, git status…) | Read, Glob, Grep |
| `view_image` | B: inspecting with the magnifier | `ReadImage`, `UnderstandImage`; screenshot-type MCP tools | Read on an image file |
| `write_file` | B: writing on paper | `write`, `edit`; writing commands (redirects, sed -i, cp, git commit…) | Write, Edit, MultiEdit |
| `verify` | B: checking two sheets against each other | test / check commands (pytest, npm test, cargo test…) | Same as left |
| `read_web` | B: browsing on the tablet | `WebSearch`; curl / wget; browser-type MCP tools | WebFetch, WebSearch |
| `respond` | B: handing in the report | An assistant message with body text and no tool calls | `end_turn` text |
| `task_complete` | C: showing the ✅ done card | Follows handing in the report | Same as left |
| `question_for_user` | C: putting up the ❓ question card | `AskUserQuestion`; index status `ask_permission` (waiting for your approval), `waiting_for_user` | AskUserQuestion |
| `default_work` | The steady computer-desk pose | Everything else (builds, installing dependencies, `skill`, unknown MCP tools…) | Same as left |
| `failed` | Dejected | Tool result `"ok": false`; index status `failed`. Interruptions and denied permissions don't count as failures | Tool errors; API errors |
| `idle` | Base idle | No task in progress; gone-quiet fallback | Same as left |

The classification rules are in `yukio/classify.py`, each with its own test. When unsure she falls back to the computer-desk pose instead of treating an arbitrary command as a test.

## Several chats at once: which one she follows

One Yukio **shows** only one chat at a time (otherwise the poses would get tangled). The other chats with something to say hang as small cards above the bubble.

The default is **Auto**. Chats are ranked in tiers, and the higher the tier the sooner a chat is shown (the same ordering the ChatGPT desktop app's pet uses):

1. Chats **waiting for your answer** (the ❓ question card)
2. Chats **stopped on an error** for the whole turn
3. Chats that have **finished and are holding up the ✅ done card**
4. When there is none of the above, the chat **still at work**: she doesn't switch while it keeps going; only once it stops, is interrupted or goes quiet does she move to the other chat with the most recent activity

Within a tier the most recent chat comes first; deal with one and the next surfaces by itself. The head bubble shows **that chat's** title, so you can tell at a glance which one has finished.

**Once a chat finishes, the sign stays up**: instead of lowering itself after 8 seconds, it stays up until you click her (or that chat starts a new turn, is interrupted, or its log is deleted). If a raised sign goes unclicked for a full 15 minutes, she steps aside for a chat that is still at work. The sign is not lowered; it comes back up once that chat stops too, and the list shows that chat as "Holding the sign for you (stepped aside)". Even if she is following another chat at the moment one finishes, that sign is raised and kept, so the completion notice for that turn is never lost.

**The card stack over her head**: the chat she is currently showing gets no card (the bubble already covers it); every other chat gets one, stacked upward from the bubble with the most urgent card right next to it. A card shows the chat name, what it is doing right now, a short label on the right (Waiting / Error / Ready / Running), and a bar on the left in the same color. At most 3 cards are stacked; the rest fold into "N more", which you click to expand. Clicking the card body = go to that chat and dismiss the card; clicking ✕ = just dismiss it (it comes back when that chat has activity in its next turn); right-clicking a card = no more cards for that chat during this run. Menu › **Show other chats** turns the whole thing off.

Menu › **Chat to follow** lets you pick one yourself. The first item is "Auto (done and questions first)"; below it are the chats from the last half hour, up to 10, ranked by the same tiers (waiting for your answer → error → done → running → by how long they have been quiet). Each shows the chat name (the session title from the log, or the first line of the request if there is none) and what it is doing right now; the submenu title also carries a count (how many are waiting for you / how many are running). Click a chat to pin it: she switches to it at once and no other chat can take her away, however busy it gets; when the pinned chat stops, she idles and waits. A pin lasts only for this run; restart and she is back to Auto. The `--chats` command-line flag shows this list ahead of time.

## Click to jump back to the chat

While she is holding up the ✅ done card or the ❓ question card, clicking her (or one of the cards in the stack over her head) opens that chat through **the deep link the Claude desktop app registers itself**:

```
claude://code/continue?session=local_…
```

The session ID in the transcript (the file name of `~/.claude/projects/*/<session>.jsonl`) is not the same as the desktop app's session ID. The mapping lives in the desktop app's own records, which she **reads and never writes**:

```
%APPDATA%\Claude\claude-code-sessions\<account>\<org>\local_<id>.json   the cliSessionId inside
```

`python run.py --chat-link <session ID>` checks ahead of time whether a session can be matched. These are the desktop app's internal records, not a public interface, and may change between versions; **when there is no match she only lowers the sign and never jumps to the wrong chat**.

Claude Code running in a terminal, and **Deep Code (DeepSeek) sessions, have no such link in the first place**: those chats live in a terminal, so a click just lowers the sign. The jump has been tested for real on the macOS edition; on Windows the paths and the protocol follow the desktop app's same scheme, but have not been verified on a real Windows machine.

## Self-check (runs outside Windows too)

```sh
python run.py --selftest                     # 141 tests: routing, debounce, classification, parsing, following, chat selection, card stack, swing, player logic
python run.py --check                        # load and crop all artwork, confirm no frame runs out of bounds
python run.py --snapshot out.png             # draw the animations actually in use on a checkerboard
python run.py --bubble out.png               # draw several head bubbles to check layout, truncation and position
python run.py --cards out.png                # draw "bubble + the stack of other chats above it", one panel collapsed and one expanded
python run.py --hang out.png                 # the five tilt angles while picked up, side by side, plus a self-check of the swing direction (non-zero exit if it is reversed)
python run.py --replay samples/deepcode-session.jsonl --with-bubble
python run.py --watch 60                     # follow live, printing events and state changes (never conversation content)
python run.py --chats 3                      # list recent chats; → marks the one she would follow right now
python run.py --chat-link <session ID>       # look up which Claude desktop app chat this session maps to (where a click on the sign would go)
```

`--replay` works out by itself whether a log is in Deep Code, Claude Code, Codex or inbox format; `--watch` and `--chats` take `--source auto|claude|deepcode|gpt`. The `samples/deepcode-session.jsonl` in the repo is a made-up sample (it contains no real conversation) that you can use to watch one complete state sequence. The CLI's own diagnostic output is still in Chinese for now.

## Structure

```
yukio/events.py            event protocol (task start / end / failure, activity start / end / failure, thinking, answer, task list)
yukio/router.py            session isolation, focus selection (waiting for your answer / error / done and holding the sign first; one chat can be pinned), raised signs,
                           debounce, minimum hold, merge window, gone-quiet fallback, bubble content, chat list and the card stack
yukio/cards.py             one notification card's content and tier (waiting for your answer → error → done → running)
yukio/cardstack.py         layout and drawing of the card stack (Pillow, shares its look with the bubble)
yukio/hang.py              the pendulum swing while picked up by the invisible hand, and that image's window geometry (pure logic, testable with a fake clock)
yukio/chatlinks.py         transcript session → the matching chat in the Claude desktop app (reads its records only, produces the claude:// deep link)
yukio/classify.py          tool → activity and short description (both the Deep Code and the Claude Code tool names + shell tokenizing)
yukio/parsers_deepcode.py  Deep Code messages and session index → events
yukio/parsers_claude.py    Claude Code transcripts → events
yukio/parsers_codex.py     GPT (Codex) rollout logs → events
yukio/bridge.py            event format of the generic inbox
yukio/sources.py           read-only following of the session directories and the inbox
yukio/tailer.py            tails files by byte offset and cuts out complete JSON (a half line waits for the next read)
yukio/catalog.py           animation index and frame timeline (reads the macOS edition's own activities.json / motion.json)
yukio/sprites.py           sprite strip → per-frame bitmaps, decoded only when used, the 4 most recent strips kept in memory
yukio/bubble.py            layout and drawing of the head bubble (Pillow)
yukio/win32.py             layered window, tray, menus, message loop (ctypes)
yukio/app.py               main loop, dragging, menu actions, settings
tests/                     141 tests; tests/fake_win32.py swaps the window layer for a stand-in so the logic can be tested on any platform
scripts/                   packaging (PyInstaller), the notify script for Deep Code
Resources/Yukio.ico        the exe's icon (cropped from the macOS edition's cover image)
```

The artwork is not stored twice: by default she uses `../YukioPlayer/Resources/Assets` from the repo (seven activity sprite strips, the computer desk, the base motion, the generated small motions). Packaging copies it into the exe. To use artwork from somewhere else, set the `YUKIO_ASSETS` environment variable.

## Known limitations

- **Checked against the real Deep Code once**: on 2026-09-17, `@vegamo/deepcode-cli` 0.4.0 was installed on this machine and driven through one real "read a file → answer" turn by a local fake model (speaking the OpenAI streaming protocol, never contacting DeepSeek's servers, no key needed). Yukio was then pointed at the session log it wrote: `--replay` parsed it without errors, and `--watch` followed it live through Thinking → Reading hello.txt → handing in the report → the ✅ done card → idle, with 30–80 ms between an event being written and being picked up. The fields matched what is written here exactly (`messageParams.tool_calls` / `reasoning_content`, `tool_call_id`, `ok` in the result JSON). The tool names it actually sends the model are bash, read, write, edit, WebSearch, UpdatePlan, skill, UnderstandImage / ReadImage, and the classification rules recognize all of them.
- **"No sign when the chat is already open in front of you" has not been tested on Windows**: the check has two halves. One reads the desktop app's session records to find which chat is selected right now (this half has been tested on macOS, `--open-chat` checks it on the spot, and both platforms use the same records and the same `lastFocusedAt` field). The other decides whether the Claude desktop app is really in the foreground (`win32.foreground_process_name()`, which only runs on Windows, compared against `Claude.exe`). That second half, like the `chat_url` deep link, follows the desktop app's same scheme and has not been verified on Windows. If any step comes up empty she falls back to **holding up the sign as usual**, so no reminder is lost.
- **How far it has been verified on a real machine**: every build actually runs the packaged exe on a GitHub Windows runner (Windows Server 2025). It enumerates the four windows (Yukio, the bubble, the card stack, the host), checks their sizes and `WS_EX_LAYERED` (with only one chat the card stack is a hidden 1×1 window), confirms that she shows "Writing · Editing login.py" for a staged Deep Code session, then takes a screenshot and compares the on-screen pixels against the sprite strip point by point (at 100% and 150% scaling; the last run scored 98.6% and 99.9%, threshold 90%). What it doesn't cover is the part only a human can try: what the tray menu looks like when opened, how dragging feels, multiple monitors, an Explorer restart, system scaling that isn't a multiple of 100%. If any of that goes wrong, run `python run.py` from source first; the full error shows in the terminal (when the exe is double-clicked, errors go to `%LOCALAPPDATA%\Yukio\error.log`).
- The window class is registered per process, so `FindWindow("YukioPet")` can't find her from another process (use `EnumWindows` + `GetClassName` instead, which is what `scripts/smoke-test.ps1` does).
- Deep Code holds the results of a batch of tool calls until the whole batch has finished before writing them to the session log, so for several very short calls in one batch you may only see the last one's end time. The start of each individual tool is real-time.
- The session log is not a public API, and its fields may change after a Deep Code upgrade. If they do, `--replay` on a fresh log shows whether parsing is still accurate.
- The artwork is 192×208 at 1x (the picked-up image is 192×240); at 150% / 200% it is upscaled by interpolation and looks slightly soft.
- **While picked up she is a single frame and doesn't blink**: `held.png` is a one-frame image. The swing is a live rotation around the grip point, but the character herself doesn't move.
- **Click to jump back to the chat has only been tested for real on macOS**: on Windows, the location of the Claude desktop app's records and the `claude://` protocol registration follow the same scheme, but have not been verified on a real Windows machine. When there is no match she only lowers the sign and never jumps to the wrong chat.
- **Size is seven fixed steps + ±5%, not a slider**: the macOS edition fits a 50%–200% slider in its menu; a native Win32 popup menu can't hold one, and matching it exactly would take a separate settings window. The range and the 5% step are the same on both.
- The app is not digitally signed, so Windows SmartScreen may block it the first time ("More info" → "Run anyway").
- The macOS edition lives in `../YukioPlayer` (Swift, follows Claude Code); the two don't affect each other.
