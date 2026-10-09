"""Local SQLite store for SafePaste sessions and events. Standard library only.

Privacy by schema: there is no column for raw text, real values or the placeholder map.
The most a row can hold is counts, types, risk, the action taken and a sha256 of the
masked text. So even a stolen safepaste.db reveals no secrets.

Tables:
    sessions(id, started, ended, messages)
    events(id, ts, session_id, action, risk, mode, types, masked, had_screenshot, masked_sha256)

File: $SAFEPASTE_DB, default safepaste.db next to this file (keep it in .gitignore).
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

_lock = threading.Lock()
RISKS = {"low", "medium", "high"}
TYPES = {"CLIENT", "AMOUNT", "CODENAME", "PERSON", "CREDENTIAL", "CODE", "OTHER"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id        TEXT PRIMARY KEY,
    started   TEXT NOT NULL,
    ended     TEXT,
    messages  INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             TEXT NOT NULL,
    session_id     TEXT NOT NULL REFERENCES sessions(id),
    action         TEXT NOT NULL,
    risk           TEXT NOT NULL,
    mode           TEXT NOT NULL,
    types          TEXT NOT NULL,      -- JSON like {"CLIENT": 2}, never the values
    masked         INTEGER NOT NULL,   -- how many items were swapped
    had_screenshot INTEGER NOT NULL,
    masked_sha256  TEXT NOT NULL       -- hash of the MASKED text only
);
CREATE INDEX IF NOT EXISTS events_session ON events(session_id);
"""


def _path() -> Path:
    return Path(os.environ.get("SAFEPASTE_DB") or Path(__file__).with_name("safepaste.db"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(_path())
    con.executescript(SCHEMA)
    return con


def start_session(session_id: str) -> None:
    with _lock, _connect() as con:
        con.execute("INSERT OR IGNORE INTO sessions(id, started) VALUES (?, ?)", (session_id, _now()))


def end_session(session_id: str) -> None:
    with _lock, _connect() as con:
        con.execute("UPDATE sessions SET ended = ? WHERE id = ? AND ended IS NULL", (_now(), session_id))


def record_event(session_id: str, action: str, risk: str, mode: str, types: list[str],
                 had_screenshot: bool, masked_text: str) -> None:
    """Only whitelisted, non-secret fields get in. masked_text is hashed here and dropped."""
    counts: dict[str, int] = {}
    for t in types:
        t = str(t).upper() if str(t).upper() in TYPES else "OTHER"
        counts[t] = counts.get(t, 0) + 1
    row = (
        _now(), session_id, str(action)[:40], risk if risk in RISKS else "high", str(mode)[:20],
        json.dumps(counts, sort_keys=True), sum(counts.values()), int(bool(had_screenshot)),
        hashlib.sha256(masked_text.encode("utf-8")).hexdigest(),
    )
    with _lock, _connect() as con:
        con.execute("INSERT OR IGNORE INTO sessions(id, started) VALUES (?, ?)", (session_id, _now()))
        con.execute("INSERT INTO events(ts, session_id, action, risk, mode, types, masked, had_screenshot,"
                    " masked_sha256) VALUES (?,?,?,?,?,?,?,?,?)", row)
        if action in ("sent", "approved_and_sent"):
            con.execute("UPDATE sessions SET messages = messages + 1 WHERE id = ?", (session_id,))


def stats() -> dict:
    """Totals for a dashboard or a judge: counts only."""
    with _lock, _connect() as con:
        sessions = con.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        events = con.execute("SELECT COUNT(*), COALESCE(SUM(masked), 0) FROM events").fetchone()
        by_risk = dict(con.execute("SELECT risk, COUNT(*) FROM events GROUP BY risk").fetchall())
    return {"sessions": sessions, "events": events[0], "items_masked": events[1], "by_risk": by_risk}


if __name__ == "__main__":
    print(json.dumps(stats(), indent=2))
