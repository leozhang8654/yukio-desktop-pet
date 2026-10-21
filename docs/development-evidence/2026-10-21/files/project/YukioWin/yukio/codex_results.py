"""Metadata-only Codex result evidence, separate from pet animation policy.

No output text is interpreted as a status. UI item IDs are not assumed to be
outer call IDs. This is an in-memory correlation window, not a history store.
"""
from collections import OrderedDict
from dataclasses import asdict, dataclass
import json
import math
from typing import Optional


def identifier(value):
    return value if isinstance(value, str) and value.strip() else None


def structured(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            obj = json.loads(value)
            return obj if isinstance(obj, dict) else {}
        except ValueError:
            pass
    return {}


def outcome(obj):
    """Only recognized machine fields; cancellation takes precedence over exit 130."""
    status = obj.get('status')
    status = status.lower() if isinstance(status, str) else ''
    metadata = obj.get('metadata')
    code = obj.get('exit_code', metadata.get('exit_code') if isinstance(metadata, dict) else None)
    code = (int(code) if type(code) in (int, float) and -(2**63) <= code < 2**63
            and math.isfinite(code) and int(code) == code else None)
    if status in ('cancelled', 'canceled', 'interrupted', 'aborted'):
        return 'cancelled', code
    result = obj.get('result')
    result = result if isinstance(result, dict) else {}
    failed = (status in ('failed', 'error') or obj.get('success') is False
              or obj.get('isError') is True or result.get('isError') is True
              or (code is not None and code != 0))
    if failed:
        return 'failed', code
    # `completed` can mean only transport completion, including a tool error.
    if (status in ('succeeded', 'success') or obj.get('success') is True or code == 0
            or obj.get('isError') is False or result.get('isError') is False):
        return 'succeeded', code
    return 'unknown', code


@dataclass(frozen=True)
class CodexToolResult:
    session_id: str
    turn_id: Optional[str]
    call_id: Optional[str]
    item_id: Optional[str]
    source_kind: str
    timestamp_ms: float
    outcome: str
    call_outcome: str
    association: str
    exit_code: Optional[int]
    projection_eligible: bool
    conflicting_results: bool
    turn_association: str
    item_type: Optional[str] = None
    reported_status: Optional[str] = None
    schema_version: int = 1

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v is not None}


class CodexResultTracker:
    def __init__(self, capacity=4096):
        self.capacity = capacity
        self.turn_id = None
        self.closed = False
        self.calls = OrderedDict()
        self.retired = OrderedDict()

    def reset(self):
        self.calls.clear()
        self.retired.clear()
        self.turn_id = None
        self.closed = False

    def begin_turn(self, value):
        turn = identifier(value)
        if turn and (turn != self.turn_id or self.closed):
            self._retire()
            self.closed = False
            self.turn_id = turn

    def close_turn(self):
        self._retire()
        self.closed = True

    def _retire(self):
        for call in self.calls:
            self.retired[call] = None
            if len(self.retired) > self.capacity:
                self.retired.popitem(last=False)
        self.calls.clear()

    def is_current(self, value):
        turn = identifier(value)
        return not self.closed and (turn is None or turn == self.turn_id)

    def matches_turn(self, value):
        turn = identifier(value)
        return turn is None or self.turn_id is None or turn == self.turn_id

    def start(self, call):
        if self.closed:  # legacy records may omit task_started/turn_context
            self.turn_id = None
            self.closed = False
        call = identifier(call)
        if call:
            self._remember(call)

    def _remember(self, call):
        if call not in self.calls:
            self.calls[call] = set()
            if len(self.calls) > self.capacity:
                self.calls.popitem(last=False)

    def record(self, *, session, payload, item, source_kind, timestamp):
        is_item = item is not None
        obj = item if is_item else structured(payload.get('output'))
        item_id = identifier(item.get('id')) if is_item else None
        explicit_turn = identifier(payload.get('turn_id'))
        turn = explicit_turn or self.turn_id
        turn_association = 'explicit_turn_id' if explicit_turn else ('current_context' if turn else 'unavailable')
        call = identifier((item if is_item else payload).get('call_id'))
        if is_item and call is None:
            call = identifier(payload.get('call_id'))
        association = 'explicit_call_id' if call else 'unlinked'
        current = self.is_current(turn)
        if call is None and is_item and current and item_id in self.calls:
            call, association = item_id, 'matching_item_id'
        # Legacy output `id` is a candidate only when a matching start was seen.
        if call is None and not is_item and current:
            candidate = identifier(payload.get('id'))
            if candidate in self.calls:
                call, association = candidate, 'matching_item_id'
        if call in self.retired and explicit_turn is None:
            # A reused call ID plus no turn ID cannot distinguish a late old result.
            turn, turn_association, current = None, 'ambiguous_reused_call', False
        observed, code = outcome(obj)
        resolved, conflict = 'unknown', False
        if call and current:
            self._remember(call)
            if observed != 'unknown':
                self.calls[call].add(observed)
            signals = self.calls[call]
            conflict = len(signals) > 1
            resolved = next(iter(signals)) if len(signals) == 1 else 'unknown'
        return CodexToolResult(session, turn, call, item_id, source_kind, timestamp,
                               observed, resolved, association, code,
                               bool(call and current), conflict, turn_association,
                               identifier(item.get('type')) if is_item else None,
                               identifier(obj.get('status')))
