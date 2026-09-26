"""Local reminders, independent of windows and the desktop pet.

JSON version 1 matches macOS ReminderBook (dueAt is seconds since 2001-01-01).
All mutations write atomically before becoming visible to the app.
"""
from __future__ import annotations

from copy import deepcopy
import json
import math
import os
from pathlib import Path
import tempfile
import time
import uuid

from .l10n import tr

APPLE_EPOCH = 978307200


class ReminderStore:
    def __init__(self, path):
        self.path = Path(path)
        self.items = []
        self.available = True
        self.error = None
        self.revision = 0
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or data.get("version") != 1:
                    raise ValueError(tr("Unsupported reminder file version", "不支持的提醒文件版本"))
                items = data["items"]
                if not isinstance(items, list):
                    raise ValueError("Invalid reminder list")
                seen = set()
                for item in items:
                    uuid.UUID(item["id"])
                    if item["id"] in seen or not isinstance(item["title"], str):
                        raise ValueError("Invalid reminder")
                    seen.add(item["id"])
                    if item["status"] not in ("scheduled", "ringing", "completed"):
                        raise ValueError("Invalid reminder status")
                    if isinstance(item["dueAt"], bool) or not math.isfinite(item["dueAt"]):
                        raise ValueError("Invalid reminder date")
                self.items = items
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            self.available = False
            self.error = tr("Cannot read reminders; original file preserved: %s", "无法读取提醒，原文件已保留：%s") % exc

    def list(self, status):
        return sorted((deepcopy(i) for i in self.items if i["status"] == status),
                      key=lambda i: i["dueAt"], reverse=status == "completed")

    @staticmethod
    def due_at(item):
        return item["dueAt"] + APPLE_EPOCH

    def _write(self, items):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                             prefix=self.path.name + ".", suffix=".tmp", delete=False) as output:
                temporary = output.name
                json.dump({"version": 1, "items": items}, output, ensure_ascii=False, indent=2, allow_nan=False)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    def _commit(self, change):
        if not self.available:
            return False
        try:
            items = deepcopy(self.items)
            change(items)
            if items != self.items:
                self._write(items)
                self.items = items
                self.revision += 1
            self.error = None
            return True
        except (OSError, ValueError) as exc:
            self.error = tr("Reminder not saved: %s", "提醒未保存：%s") % exc
            return False

    def save(self, title, due_at, reminder_id=None, now=None):
        now = time.time() if now is None else now
        def change(items):
            clean = title.strip()
            if not clean:
                raise ValueError(tr("Give this reminder a name.", "给这条提醒起个名字吧。"))
            if not math.isfinite(due_at) or due_at <= now:
                raise ValueError(tr("Choose a future time.", "请选择一个还没到的时间。"))
            item = next((i for i in items if i["id"] == reminder_id), None)
            if item is None:
                item = {"id": str(uuid.uuid4())}
                items.append(item)
            item.update(title=clean, dueAt=due_at - APPLE_EPOCH, status="scheduled")
        return self._commit(change)

    def tick(self, now=None):
        now = time.time() if now is None else now
        due = [i["id"] for i in self.items if i["status"] == "scheduled" and self.due_at(i) <= now]
        if not due or not self.available:
            return []
        def change(items):
            for item in items:
                if item["id"] in due:
                    item["status"] = "ringing"
        return due if self._commit(change) else []

    def complete(self, reminder_id):
        def change(items):
            for item in items:
                if item["id"] == reminder_id:
                    item["status"] = "completed"
        return self._commit(change)

    def snooze(self, reminder_id, now=None):
        now = time.time() if now is None else now
        def change(items):
            for item in items:
                if item["id"] == reminder_id and item["status"] == "ringing":
                    item.update(dueAt=now + 300 - APPLE_EPOCH, status="scheduled")
        return self._commit(change)

    def remove(self, reminder_id):
        return self._commit(lambda items: items.__setitem__(slice(None), [i for i in items if i["id"] != reminder_id]))
