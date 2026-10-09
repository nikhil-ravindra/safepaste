"""Turns a screenshot into text, locally, with Gemma 4 vision. Owner: Person 1.

Design: the image never leaves the laptop. We transcribe it here, then the text
goes through the same redaction as typed text — only redacted text is sent out.
"""
import ollama_client

PROMPT = """Transcribe ALL text visible in this image exactly as written.
Keep numbers, currency symbols and names exactly. For tables, write one row per line
with cells separated by " | ". Do not summarise or add anything. Output only the text."""

LAST_ERROR = None


def transcribe(image_bytes: bytes) -> str:
    """Return the text in the screenshot, or "" if Gemma can't read it."""
    global LAST_ERROR
    LAST_ERROR = None
    try:
        return ollama_client.chat(PROMPT, image_bytes=image_bytes, timeout=180).strip()
    except ollama_client.OllamaError as e:
        LAST_ERROR = f"Couldn't read the screenshot: {e}"
        return ""