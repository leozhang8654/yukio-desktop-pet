# Approval cards and paste repair — development validation

This is development work for 0.4.4, not a claim that every provider UI is compatible. Public 0.4.3 downloads do not contain this work.

## What was checked

- macOS: 209 Swift tests passed, including exact request/turn/session matching, changed operation rejection, permission scope limited to one turn, unavailable decisions, file details, duplicate rejection, Claude allow/deny receipts, and native field-editor paste/select/replace.
- Windows shared code: 270 Python tests passed on macOS, with the Windows-only pipe test skipped there.
- Windows native packaged build: [run 38328727887](https://github.com/leozhang8654/yukio-desktop-pet/actions/runs/38328727887), source `6cd7227`, passed all 270 tests, packaging, upgrade, real named-pipe background replies, windowed-executable Claude PermissionRequest allow/deny receipts with Chinese input/output, settings and pet rendering at 100% and 150%.
- Deep Code adapter: five Node tests passed. Covered question receipts, approval allow/deny, changed batches, free-text rejection and absence of persistent grants. No model account or live model execution was used.
- Actual macOS debug app: the real answer panel accepted Chinese, English, emoji and multiple pasted lines without opening the assistant window first. Subsequent keyboard tests were deferred when the user continued interacting with the computer.

## Problems found and repaired

The answer panel relied on an Edit menu installed only by another window. It now handles standard editing shortcuts through its own field editor. Caps Lock no longer prevents those shortcuts.

The Windows hook could read an empty heartbeat during a concurrent refresh and incorrectly treat the pet as disconnected. Heartbeat replacement is now atomic; the round-trip test caught this before packaging.

The reported screenshot came from a GPT extension conversation that was not owned by the desktop background connection. A macOS fallback now requires the official selected-chat header (or exact conversation URL), full matching question and a dedicated submission control. Existing drafts and ambiguous matches stop the send. Losing the receipt after dispatch never triggers an automatic second send.

## Still unverified / release limits

- A real GPT extension approval was inspected with the user. The visible page contained an intention to request permission but no decision buttons; the local conversation record was interrupted/not loaded. No live approval was submitted, no test file was created and this is not a passed end-to-end test.
- Real GPT/Claude/DeepSeek website and extension approval round trips remain unverified. UI detection is experimental and can only operate when the target exposes a supported request and controls. Generated artifacts and public share pages are excluded.
- Ordinary Claude desktop chat is not covered merely by installing Claude Code hooks. Deep Code requires the isolated adapter launcher.
- Windows native tests confirm the packaged local helper and UI on a runner, not logged-in GPT/Claude/DeepSeek products, a physical Windows multi-monitor setup, or all scaling configurations.
- Desktop installation and public release must be verified separately. A feature branch or successful build alone is not a completed update.
