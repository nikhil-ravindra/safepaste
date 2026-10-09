# mask.py — owner: Person 3
"""Swap sensitive spans for placeholders before text leaves the machine, and swap them back after.

Contract (Person 3):
    mask(text, findings)    -> (masked_text, {"⟦CLIENT_1⟧": "Acme Corp", ...})
    restore(text, mapping)  -> (restored_text, [placeholders_not_found])

Rules:
    - Placeholders look like ⟦TYPE_N⟧, numbered per type in order of first appearance.
    - The same original text always maps to the same placeholder.
    - Longest matches are replaced first, so "Acme Corp" wins over "Acme".
    - Replacement is a single pass, so a placeholder is never re-masked or re-restored.
    - A finding that is not in the text verbatim is matched ignoring case and spacing,
      because an LLM inspector often returns "acme corp" for "Acme  Corp".
"""

from __future__ import annotations

import re

TYPES = {"CLIENT", "AMOUNT", "CODENAME", "PERSON", "CREDENTIAL", "CODE", "OTHER"}


def _normalise_type(raw) -> str:
    t = str(raw or "OTHER").strip().upper()
    return t if t in TYPES else "OTHER"


def _alternation(strings) -> re.Pattern:
    # Longest first; ties broken alphabetically so output is deterministic.
    ordered = sorted(strings, key=lambda s: (-len(s), s))
    return re.compile("|".join(re.escape(s) for s in ordered))


def _spellings(text: str, wanted: str) -> list[str]:
    """How wanted actually appears in text: verbatim if it does, else ignoring case and spacing."""
    if wanted in text:
        return [wanted]
    loose = re.compile(r"\s+".join(re.escape(word) for word in wanted.split()), re.IGNORECASE)
    return list(dict.fromkeys(m.group(0) for m in loose.finditer(text)))


def unmatched(text: str, findings: list[dict]) -> list[dict]:
    """Findings that appear nowhere in text, even ignoring case and spacing, so mask() cannot hide them."""
    return [
        f
        for f in findings or []
        if str(f.get("text") or "").strip() and not _spellings(text, str(f["text"]).strip())
    ]


def mask(text: str, findings: list[dict]) -> tuple[str, dict]:
    # First finding wins if the same text is reported twice with different types.
    type_of: dict[str, str] = {}
    for finding in findings or []:
        wanted = str(finding.get("text") or "").strip()  # LLM JSON may hand back numbers
        if not wanted:
            continue
        for original in _spellings(text, wanted):
            type_of.setdefault(original, _normalise_type(finding.get("type")))

    if not type_of:
        return text, {}

    placeholder_of: dict[str, str] = {}
    counters: dict[str, int] = {}

    def swap(match: re.Match) -> str:
        original = match.group(0)
        if original not in placeholder_of:
            kind = type_of[original]
            counters[kind] = counters.get(kind, 0) + 1
            placeholder_of[original] = f"⟦{kind}_{counters[kind]}⟧"
        return placeholder_of[original]

    masked = _alternation(type_of).sub(swap, text)
    # Only spans that were actually replaced end up in the mapping.
    mapping = {placeholder: original for original, placeholder in placeholder_of.items()}
    return masked, mapping


def restore(text: str, mapping: dict) -> tuple[str, list[str]]:
    if not mapping:
        return text, []

    found: set[str] = set()

    def swap(match: re.Match) -> str:
        placeholder = match.group(0)
        found.add(placeholder)
        return mapping[placeholder]

    restored = _alternation(mapping).sub(swap, text)
    not_found = [placeholder for placeholder in mapping if placeholder not in found]
    return restored, not_found
