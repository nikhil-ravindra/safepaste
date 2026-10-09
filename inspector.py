"""Finds sensitive items in text using the company policy. Owner: Person 1.

Two layers:
  1. Regex for things with a fixed shape (API keys, emails, phones, ₹ amounts).
  2. Gemma 4 for things that need understanding (client names, codenames, deal values),
     guided by the plain-English policy.
Gemma's answers are validated: every item must appear word-for-word in the input,
so the model can't invent secrets that aren't there.
"""
import json
import re

import ollama_client

TYPES = ["CLIENT", "AMOUNT", "CODENAME", "PERSON", "CREDENTIAL", "CODE", "OTHER"]
LAST_ERROR = None  # set when Gemma fails, so the app can show a warning

REGEX_RULES = [
    ("CREDENTIAL", r"\bsk-[A-Za-z0-9_\-]{16,}"),            # OpenAI-style keys
    ("CREDENTIAL", r"\bAKIA[0-9A-Z]{16}\b"),                 # AWS access keys
    ("CREDENTIAL", r"\bAIza[0-9A-Za-z_\-]{35}\b"),           # Google API keys
    ("CREDENTIAL", r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),       # GitHub tokens
    ("CREDENTIAL", r"(?i)\b(?:password|passwd|api[_-]?key|secret|token)\s*[:=]\s*\S+"),
    ("PERSON", r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),              # emails
    ("PERSON", r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{9}(?!\d)"),    # Indian mobile numbers
    ("AMOUNT", r"(?:₹|Rs\.?|INR)\s?[\d,]+(?:\.\d+)?(?:\s?(?:Cr|crore|lakh|L|K|Mn|M))?"),
]

SCHEMA = {
    "type": "object",
    "properties": {"findings": {"type": "array", "items": {
        "type": "object",
        "properties": {"text": {"type": "string"}, "type": {"type": "string", "enum": TYPES},
                       "reason": {"type": "string"}},
        "required": ["text", "type", "reason"]}}},
    "required": ["findings"],
}

SYSTEM = """You are a data-loss-prevention checker running locally inside a company.
Find every piece of text that the COMPANY POLICY says must not be sent to an external AI.
Rules:
- Copy each item EXACTLY as it appears in the text (same spelling, case and symbols).
- Use the shortest exact span (e.g. "Acme Corp", not the whole sentence).
- type must be one of: CLIENT, AMOUNT, CODENAME, PERSON, CREDENTIAL, CODE, OTHER.
- Give a short reason referring to the policy.
- If nothing is sensitive, return an empty list.
Return only JSON."""


def _regex_findings(text: str) -> list[dict]:
    out = []
    for ftype, pattern in REGEX_RULES:
        for m in re.finditer(pattern, text):
            out.append({"text": m.group(0).strip(), "type": ftype, "reason": "matched a fixed pattern"})
    return out


def _gemma_findings(text: str, policy: str) -> list[dict]:
    prompt = f"COMPANY POLICY:\n{policy}\n\nTEXT TO CHECK:\n<<<\n{text}\n>>>"
    last = None
    for _ in range(2):  # one retry if the JSON is bad
        raw = ollama_client.chat(prompt, json_schema=SCHEMA, system=SYSTEM)
        try:
            items = json.loads(raw).get("findings", [])
            return [i for i in items if isinstance(i, dict) and i.get("text") and i.get("type") in TYPES]
        except (json.JSONDecodeError, AttributeError) as e:
            last = e
    raise ollama_client.OllamaError(f"Gemma returned unusable JSON twice ({last})")


def inspect(text: str, policy: str) -> list[dict]:
    """Return sensitive items: [{"text", "type", "reason"}]. Never raises."""
    global LAST_ERROR
    LAST_ERROR = None
    findings = _regex_findings(text)
    try:
        findings += _gemma_findings(text, policy)
    except ollama_client.OllamaError as e:
        LAST_ERROR = str(e)  # regex results still protect the obvious things

    clean, seen = [], set()
    for f in findings:
        t = f["text"].strip()
        if not t or t not in text or t.lower() in seen:  # drop invented or duplicate items
            continue
        seen.add(t.lower())
        clean.append({"text": t, "type": f["type"], "reason": f.get("reason", "")})
    return clean