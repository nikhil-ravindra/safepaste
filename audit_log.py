# audit_log.py — owner: Person 3
"""Privacy-preserving audit log: one JSON line per event, and never any raw text.

Contract (Person 3):
    write(event) -> None

write() is an allowlist, not a filter: every field is checked against a fixed
schema and anything unknown or malformed is dropped (and counted), so a caller
cannot leak raw text by passing the wrong key. Pass the prompt as "prompt" and
it is hashed here; only its sha256 reaches disk.

Accepted fields:
    action          str slug, e.g. "sent", "approved_and_sent", "cancelled"
    risk            "low" | "medium" | "high"
    mode            str slug, e.g. "gemini", "mock"
    types           {"CLIENT": 2, ...} or ["CLIENT", "CLIENT", ...]
    counts          {"findings": 3, "placeholders_not_found": 0, ...}
    had_screenshot  bool
    prompt          str, hashed then discarded
    prompt_sha256   64-char hex, if you hashed it yourself

Log path: $SAFEPASTE_AUDIT_LOG, default audit_log.jsonl next to this file.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

TYPES = {"CLIENT", "AMOUNT", "CODENAME", "PERSON", "CREDENTIAL", "CODE", "OTHER"}
RISKS = {"low", "medium", "high"}

_SLUG = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_lock = threading.Lock()


def log_path() -> Path:
    return Path(os.environ.get("SAFEPASTE_AUDIT_LOG") or Path(__file__).with_name("audit_log.jsonl"))


def _is_count(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _types(value):
    if isinstance(value, (list, tuple)):
        value = Counter(str(t).upper() for t in value)
    if not isinstance(value, dict):
        return None
    clean: dict[str, int] = {}
    for kind, count in value.items():
        kind = str(kind).upper()
        if not _is_count(count):
            return None
        kind = kind if kind in TYPES else "OTHER"
        clean[kind] = clean.get(kind, 0) + count
    return clean


def _counts(value):
    if not isinstance(value, dict):
        return None
    if not all(isinstance(k, str) and _SLUG.match(k) and _is_count(v) for k, v in value.items()):
        return None
    return dict(value)


_VALIDATORS = {
    "action": lambda v: v if isinstance(v, str) and _SLUG.match(v) else None,
    "risk": lambda v: v if isinstance(v, str) and v in RISKS else None,
    "mode": lambda v: v if isinstance(v, str) and _SLUG.match(v) else None,
    "types": _types,
    "counts": _counts,
    "had_screenshot": lambda v: v if isinstance(v, bool) else None,
    "prompt_sha256": lambda v: v if isinstance(v, str) and _SHA256.match(v) else None,
}


def sanitise(event: dict) -> dict:
    record: dict = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    dropped = 0

    for key, value in (event or {}).items():
        if key == "prompt":
            if isinstance(value, str):
                record["prompt_sha256"] = hashlib.sha256(value.encode("utf-8")).hexdigest()
            else:
                dropped += 1
            continue
        if key == "prompt_sha256" and isinstance(event.get("prompt"), str):
            continue  # the hash we compute from "prompt" wins
        clean = _VALIDATORS[key](value) if key in _VALIDATORS else None
        if clean is None:
            dropped += 1
        else:
            record[key] = clean

    if dropped:
        record["dropped_fields"] = dropped
    return record


def write(event: dict) -> None:
    line = json.dumps(sanitise(event), ensure_ascii=False, sort_keys=True)
    path = log_path()
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def tail(n: int = 20) -> list[dict]:
    """Most recent n entries, newest first. For the UI only."""
    path = log_path()
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines()[-n:]:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries[::-1]
