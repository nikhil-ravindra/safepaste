"""Decides how risky a send is. Owner: Person 1.

Design: plain rules, not AI, so the decision is predictable and explainable.
  high   → credentials, code, or lots of secrets → employee must approve
  medium → some items swapped → send the safe version automatically
  low    → nothing sensitive found
"""
import re

CODE_HINTS = re.compile(r"(def |class |import |function |=>|#include|public static|SELECT .* FROM|\{\s*$)", re.M)


def looks_like_code(text: str) -> bool:
    lines = [l for l in text.splitlines() if l.strip()]
    return len(lines) >= 5 and len(CODE_HINTS.findall(text)) >= 2


def assess(findings: list[dict], text: str) -> str:
    types = {f["type"] for f in findings}
    if types & {"CREDENTIAL", "CODE"} or looks_like_code(text) or len(findings) > 5:
        return "high"
    return "medium" if findings else "low"