"""The 'cloud AI' that answers — Gemma 4 on Google's Gemini API. Owner: Person 2.

SafePaste uses Gemma on both sides:
  - Small Gemma 4 (e4b) on the laptop GUARDS: finds secrets and swaps them (inspector.py).
  - Big Gemma 4 (26B) in the cloud ANSWERS: it only ever sees placeholders like ⟦CLIENT_1⟧.

Modes:
  "gemma-cloud" → Gemma 4 via the Gemini API (needs GEMINI_API_KEY in .env)
  "mock"        → canned answer, no network (backup for the demo)
The cloud model ID comes from CLOUD_GEMMA_MODEL; default is a Gemma 4 ID from Google's docs.
"""
import os
import re
import warnings

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DEFAULT_CLOUD_MODEL = "gemma-4-26b-a4b-it"  # documented at ai.google.dev/gemma/docs/core/gemma_on_gemini_api
BASE_RULES = (
    "Some values in the user's message were replaced by tokens like ⟦CLIENT_1⟧ or ⟦AMOUNT_2⟧ for privacy. "
    "Keep every such token exactly as written wherever you refer to it, and do not guess what it stands for. "
    "Answer briefly and directly: no preamble, no repeating the question."
)
CALC_RULES = (
    " You cannot see the real money amounts behind ⟦AMOUNT_n⟧ tokens, so never invent or estimate them. "
    "When the user needs arithmetic on those amounts (an average, total, difference, growth or share), write the "
    "calculation in this exact form and the user's computer will fill in the result: "
    "[[calc:rupees: (⟦AMOUNT_1⟧ + ⟦AMOUNT_2⟧) / 2]]. Use 'rupees' for money results, 'percent' for percentages "
    "(multiply by 100) and 'number' otherwise. Inside a calculation use ONLY ⟦AMOUNT_n⟧ tokens, plain numbers, "
    "+ - * / and brackets. Never put ⟦CLIENT_n⟧ or other non-number tokens inside a calculation. "
    "Numbers that are written out in the message are visible to you: calculate with those normally."
)
LAST_NOTE = None  # set when the cloud call falls back to mock, so the app can say so


def system_rules(prompt: str) -> str:
    """Only teach the [[calc]] convention when money amounts were actually hidden."""
    return BASE_RULES + (CALC_RULES if "⟦AMOUNT_" in prompt else "")


def _generate_mock_summary(prompt: str) -> str:
    """Offline stand-in that reuses the placeholders and the [[calc]] convention, so the demo works with no internet."""
    placeholders = list(dict.fromkeys(re.findall(r"⟦[^⟧]+⟧", prompt)))
    amounts = [p for p in placeholders if p.startswith("⟦AMOUNT_")]
    others = [p for p in placeholders if p not in amounts]
    wants_maths = re.search(r"\b(average|avg|mean|total|sum|growth|compare|difference)\b", prompt, re.I)
    lines = []
    if others:
        lines.append("Key items in this update: " + ", ".join(others) + ".")
    if amounts and wants_maths and len(amounts) >= 2:
        terms = " + ".join(amounts)
        lines.append(f"Total across the {len(amounts)} figures: [[calc:rupees: {terms}]].")
        lines.append(f"Average per item: [[calc:rupees: ({terms}) / {len(amounts)}]].")
        lines.append(f"{amounts[0]} compared with {amounts[1]}: [[calc:percent: ({amounts[0]} - {amounts[1]}) / {amounts[1]} * 100]] difference.")
    elif amounts:
        lines.append("Figures mentioned: " + ", ".join(amounts) + ".")
    if not lines:
        lines.append("Operations remain on track. No specific items needed follow-up.")
    return "Summary (mock answer): " + " ".join(lines)


def _fallback(reason: str, prompt: str) -> str:
    global LAST_NOTE
    LAST_NOTE = reason
    warnings.warn(reason)
    return _generate_mock_summary(prompt)


_CLIENT = None
_THINKING_OFF_OK = True  # flips to False if this model rejects a thinking setting


def _client(api_key: str):
    """One client for the whole session: no new connection setup on every message."""
    global _CLIENT
    if _CLIENT is None:
        from google import genai
        _CLIENT = genai.Client(api_key=api_key)
    return _CLIENT


def _config(prompt: str, thinking_off: bool):
    """prompt here is all text the model will see, so the maths rules turn on if any turn has amounts."""
    from google.genai import types
    extra = {}
    if thinking_off:
        extra["thinking_config"] = types.ThinkingConfig(thinking_budget=0)  # answer directly, no long hidden reasoning
    return types.GenerateContentConfig(
        system_instruction=system_rules(prompt),
        max_output_tokens=int(os.getenv("CLOUD_MAX_TOKENS", "500")),  # short answers come back faster
        temperature=0.3,
        **extra,
    )


def _contents(prompt: str, history):
    """Earlier masked turns first, then this message. Placeholders only, never real values."""
    from google.genai import types
    out = []
    for user, model in history or []:
        out.append(types.Content(role="user", parts=[types.Part(text=user)]))
        out.append(types.Content(role="model", parts=[types.Part(text=model)]))
    out.append(types.Content(role="user", parts=[types.Part(text=prompt)]))
    return out


def _ask_gemma_cloud(prompt: str, history=None) -> str:
    global _THINKING_OFF_OK
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return _fallback("GEMINI_API_KEY is not set in .env.", prompt)
    model = os.getenv("CLOUD_GEMMA_MODEL", DEFAULT_CLOUD_MODEL)
    seen = prompt + "".join(u + m for u, m in (history or []))
    try:
        client = _client(api_key)
        try:
            response = client.models.generate_content(model=model, contents=_contents(prompt, history),
                                                      config=_config(seen, _THINKING_OFF_OK))
        except Exception as e:
            if not (_THINKING_OFF_OK and "think" in str(e).lower()):
                raise
            _THINKING_OFF_OK = False  # this model doesn't take the setting: retry once without it, remember
            response = client.models.generate_content(model=model, contents=_contents(prompt, history),
                                                      config=_config(seen, False))
        if response.text:
            return response.text
        return _fallback("Cloud Gemma returned an empty answer.", prompt)
    except Exception as e:  # no internet, bad key, timeout → demo keeps working
        return _fallback(f"Cloud Gemma call failed ({type(e).__name__}: {e}).", prompt)


def ask(prompt: str, mode: str = "gemma-cloud", history=None) -> str:
    """Send the MASKED prompt to the cloud model and return its answer."""
    global LAST_NOTE
    LAST_NOTE = None
    if mode.lower() == "mock":
        return _generate_mock_summary(prompt)
    return _ask_gemma_cloud(prompt, history)


if __name__ == "__main__":
    sample = "Summarize: ⟦CLIENT_1⟧ paid ⟦AMOUNT_1⟧ for ⟦CODENAME_1⟧."
    print("mock:  ", ask(sample, mode="mock"))
    print("cloud: ", ask(sample, mode="gemma-cloud"))
