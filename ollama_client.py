"""Talks to Gemma 4 running locally via Ollama. Owner: Person 1.

Design: standard library only (no installs), localhost only, model name from
the SAFEPASTE_MODEL env var (never guessed), thinking off for speed.
"""
import base64
import json
import os
import urllib.error
import urllib.request

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")


class OllamaError(Exception):
    """Raised when Gemma can't be reached or returns something unusable."""


def _model() -> str:
    model = os.environ.get("SAFEPASTE_MODEL")
    if not model:
        raise OllamaError("Set SAFEPASTE_MODEL, e.g. gemma4:e4b (check with: ollama list)")
    return model


def chat(prompt: str, image_bytes: bytes | None = None, json_schema: dict | None = None,
         system: str | None = None, timeout: int = 120) -> str:
    """Send one message to Gemma and return its reply text.

    json_schema: if given, Ollama forces the reply to match this JSON schema.
    image_bytes: optional screenshot, sent as base64 (never leaves the laptop).
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    user = {"role": "user", "content": prompt}
    if image_bytes:
        user["images"] = [base64.b64encode(image_bytes).decode("ascii")]
    messages.append(user)

    body = {"model": _model(), "messages": messages, "stream": False, "think": False,
            "options": {"temperature": 0}}
    if json_schema:
        body["format"] = json_schema

    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise OllamaError(f"Can't reach Ollama at {OLLAMA_URL} — is it running? ({e})") from e
    except TimeoutError as e:
        raise OllamaError(f"Gemma took longer than {timeout}s") from e
    except json.JSONDecodeError as e:
        raise OllamaError("Ollama returned invalid JSON") from e

    if "error" in data:
        raise OllamaError(f"Ollama error: {data['error']}")
    return data.get("message", {}).get("content", "")
