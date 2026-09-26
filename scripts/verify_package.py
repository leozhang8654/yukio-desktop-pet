#!/usr/bin/env python3
"""Verify the delivered handoff package using Python's standard library."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]


def read_json(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def referenced_file(folder, relative):
    candidate = (ROOT / folder / relative).resolve()
    if not candidate.is_relative_to(ROOT) or not candidate.is_file():
        raise ValueError(f"Missing or unsafe resource: {folder}/{relative}")
    return candidate


def main():
    checksums = read_json("docs/history/SHA256SUMS.json")
    for relative, expected in checksums.items():
        file = referenced_file("", relative)
        actual = hashlib.sha256(file.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Checksum mismatch: {relative}")

    activities = read_json("assets/activities/activities.json")
    expected_ids = {
        "thinking", "read_file", "view_image", "write_file", "verify",
        "read_web", "respond", "default_work", "question_for_user", "task_complete",
    }
    # 单帧底图的状态：动作由 YukioPlayer/tools/motion 生成，这里只校验底图本身。
    single_frame_ids = {"default_work", "question_for_user", "task_complete"}
    states = activities["states"]
    if len(states) != len(expected_ids) or {s["id"] for s in states} != expected_ids:
        raise ValueError("Activity states do not match the user's selection")
    if activities["defaultState"] != "default_work":
        raise ValueError("Unknown work must fall back to the computer desk")
    for state in states:
        referenced_file("assets/activities", state["asset"])
        if state["frameWidth"] != 192 or state["frameHeight"] != 208:
            raise ValueError(f"Incorrect cell size: {state['id']}")
        sequence, durations = state["sequence"], state["durationsMs"]
        frame_count = 1 if state["id"] in single_frame_ids else 4
        if not sequence or len(sequence) != len(durations):
            raise ValueError(f"Invalid sequence: {state['id']}")
        if any(not isinstance(i, int) or not 0 <= i < frame_count for i in sequence):
            raise ValueError(f"Out-of-range frame: {state['id']}")
        if any(duration <= 0 for duration in durations):
            raise ValueError(f"Invalid duration: {state['id']}")
    report = next(s for s in states if s["id"] == "respond")
    if report["loop"] or not report["holdLastFrame"]:
        raise ValueError("Report must play once and hold its last frame")

    base = read_json("assets/base/base-animations.json")
    referenced_file("assets/base", base["neutral"])
    for animation in base["animations"]:
        referenced_file("assets/base", animation["asset"])
    if len(base["lookAnglesDegrees"]) != 16:
        raise ValueError("Expected 16 look directions")

    native = read_json("docs/history/native-current/pet.json")
    if native["id"] != "yukio-codex-maid" or native["spriteVersionNumber"] != 2:
        raise ValueError("Unexpected current native pet")
    referenced_file("docs/history/native-current", native["spritesheetPath"])
    print(f"PASS: {len(checksums)} files verified; {len(states)} activity assets, "
          f"{len(base['animations'])} base strips, and one native pet snapshot.")
    print("This verifies the asset handoff, not a completed desktop application.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
