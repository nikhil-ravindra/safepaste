"""Talks to Gemma 4 running locally via Ollama. Owner: Person 1.

Design: standard library only (no installs), localhost only, model name from
the SAFEPASTE_MODEL env var (never guessed), thinking off for speed.

Speed: the model stays loaded between requests (keep_alive), the context size is fixed so
Ollama never reloads the model to resize it, and warm_up() loads it before the first prompt.
LAST_STATS holds Ollama's timings for the latest call, for the UI and bench_latency.py.
"""
import base64
import json
import os
import urllib.error
import urllib.request

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
KEEP_ALIVE = os.environ.get("SAFEPASTE_KEEP_ALIVE", "30m")  # Ollama's default unloads after 5 idle minutes
NUM_CTX = int(os.environ.get("SAFEPASTE_NUM_CTX", "8192"))  # same on every call, or Ollama reloads the model
LAST_STATS: dict = {}


class OllamaError(Exception):
    """Raised when Gemma can't be reached or returns something unusable."""


def _model() -> str:
    model = os.environ.get("SAFEPASTE_MODEL")
    if not model:
        raise OllamaError("Set SAFEPASTE_MODEL, e.g. gemma4:e4b (check with: ollama list)")
    return model


def _post(body: dict, timeout: int) -> dict:
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
    return data


def warm_up(timeout: int = 300) -> None:
    """Load the model into memory now, so the first real prompt doesn't pay the load time."""
    _post({"model": _model(), "messages": [], "keep_alive": KEEP_ALIVE,
           "options": {"num_ctx": NUM_CTX}}, timeout)


def _stats(data: dict) -> dict:
    """Ollama reports durations in nanoseconds; keep seconds and token counts."""
    s = lambda key: data.get(key, 0) / 1e9
    gen = data.get("eval_count", 0)
    return {"total_s": s("total_duration"), "load_s": s("load_duration"),
            "prompt_tokens": data.get("prompt_eval_count", 0), "prompt_s": s("prompt_eval_duration"),
            "output_tokens": gen, "output_s": s("eval_duration"),
            "tokens_per_s": gen / s("eval_duration") if data.get("eval_duration") else 0.0}


def chat(prompt: str, image_bytes: bytes | None = None, json_schema: dict | None = None,
         system: str | None = None, timeout: int = 120, max_tokens: int | None = None) -> str:
    """Send one message to Gemma and return its reply text.

    json_schema: if given, Ollama forces the reply to match this JSON schema.
    image_bytes: optional screenshot, sent as base64 (never leaves the laptop).
    max_tokens: stop generating after this many tokens, so a looping model can't stall the app.
    """
    global LAST_STATS
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    user = {"role": "user", "content": prompt}
    if image_bytes:
        user["images"] = [base64.b64encode(image_bytes).decode("ascii")]
    messages.append(user)

    options = {"temperature": 0, "num_ctx": NUM_CTX}
    if max_tokens:
        options["num_predict"] = max_tokens
    body = {"model": _model(), "messages": messages, "stream": False, "think": False,
            "keep_alive": KEEP_ALIVE, "options": options}
    if json_schema:
        body["format"] = json_schema

    LAST_STATS = {}
    data = _post(body, timeout)
    LAST_STATS = _stats(data)
    return data.get("message", {}).get("content", "")
