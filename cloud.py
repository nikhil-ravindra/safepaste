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
KEEP_PLACEHOLDERS = ("Some words are replaced by tokens like ⟦CLIENT_1⟧ or ⟦AMOUNT_2⟧. "
                     "Keep every such token exactly as written, unchanged, wherever you refer to it. "
                     "Do not guess what the tokens stand for.")


def _generate_mock_summary(prompt: str) -> str:
    """Offline stand-in that reuses the placeholders, so restore still works with no internet."""
    placeholders = list(dict.fromkeys(re.findall(r"⟦[^⟧]+⟧", prompt)))
    if placeholders:
        return ("Summary: the key items in this update are " + ", ".join(placeholders) +
                ". Overall performance is on track; follow up on these items with the relevant owners.")
    return "Summary: operations remain on track. No specific items needed follow-up."


def _ask_gemma_cloud(prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        warnings.warn("GEMINI_API_KEY not set. Falling back to mock mode.")
        return _generate_mock_summary(prompt)
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=os.getenv("CLOUD_GEMMA_MODEL", DEFAULT_CLOUD_MODEL),
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=KEEP_PLACEHOLDERS),
        )
        if response.text:
            return response.text
        warnings.warn("Cloud Gemma returned an empty answer. Falling back to mock mode.")
    except Exception as e:  # no internet, bad key, timeout → demo keeps working
        warnings.warn(f"Cloud Gemma call failed ({type(e).__name__}: {e}). Falling back to mock mode.")
    return _generate_mock_summary(prompt)


def ask(prompt: str, mode: str = "gemma-cloud") -> str:
    """Send the MASKED prompt to the cloud model and return its answer."""
    if mode.lower() == "mock":
        return _generate_mock_summary(prompt)
    return _ask_gemma_cloud(prompt)


if __name__ == "__main__":
    sample = "Summarize: ⟦CLIENT_1⟧ paid ⟦AMOUNT_1⟧ for ⟦CODENAME_1⟧."
    print("mock:  ", ask(sample, mode="mock"))
    print("cloud: ", ask(sample, mode="gemma-cloud"))
