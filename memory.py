"""Chat memory for one SafePaste session. Lives in RAM only and is never written to disk.

What it remembers:
    turns    the conversation so far, MASKED (placeholders only), so the cloud model can
             answer follow-ups like "make it shorter" or "now compare it with last year".
    mapping  placeholder -> real value for the whole chat, so Acme Corp is ⟦CLIENT_1⟧ in
             every message of this chat and answers about earlier messages restore correctly.

Closing the tab, "New chat" or restarting the app wipes it. Nothing here touches the disk.
"""
from __future__ import annotations

import re
import uuid

PLACEHOLDER = re.compile(r"⟦([A-Z]+)_(\d+)⟧")
MAX_TURNS = 6  # how many earlier exchanges are sent back to the cloud as context


class SessionMemory:
    def __init__(self) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.mapping: dict[str, str] = {}   # ⟦CLIENT_1⟧ -> "Acme Corp", for the whole chat
        self.turns: list[tuple[str, str]] = []  # (masked user message, masked cloud answer)

    def merge(self, masked: str, turn_mapping: dict) -> tuple[str, dict]:
        """Renumber this message's placeholders so they agree with the rest of the chat.

        A value seen earlier keeps its old placeholder; a new value gets the next free number.
        Returns (masked text with chat-wide placeholders, this message's mapping in those terms).
        """
        known = {original: ph for ph, original in self.mapping.items()}
        next_n: dict[str, int] = {}
        for ph in self.mapping:
            kind, n = PLACEHOLDER.fullmatch(ph).groups()
            next_n[kind] = max(next_n.get(kind, 0), int(n))

        rename, turn = {}, {}
        for ph, original in turn_mapping.items():
            if original in known:
                new_ph = known[original]
            else:
                kind = PLACEHOLDER.fullmatch(ph).group(1)
                next_n[kind] = next_n.get(kind, 0) + 1
                new_ph = f"⟦{kind}_{next_n[kind]}⟧"
                known[original] = new_ph
                self.mapping[new_ph] = original
            rename[ph] = new_ph
            turn[new_ph] = original

        if rename:  # one pass, so ⟦CLIENT_1⟧ -> ⟦CLIENT_3⟧ and ⟦CLIENT_2⟧ -> ⟦CLIENT_1⟧ never collide
            pattern = re.compile("|".join(re.escape(p) for p in rename))
            masked = pattern.sub(lambda m: rename[m.group(0)], masked)
        return masked, turn

    def history(self) -> list[tuple[str, str]]:
        return self.turns[-MAX_TURNS:]

    def add_turn(self, masked_user: str, masked_answer: str) -> None:
        self.turns.append((masked_user, masked_answer))
