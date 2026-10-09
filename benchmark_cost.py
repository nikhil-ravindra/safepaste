"""Token and cost benchmark: what each prompt in tests/prompts.jsonl costs to run through SafePaste.

Every prompt makes two model calls:
  1. GUARD  — local Gemma 4 (inspector.py via Ollama) reads policy + prompt and returns findings JSON.
             Runs on the laptop, so it costs tokens and time but no API dollars.
  2. ANSWER — cloud Gemma 4 26B (cloud.py) reads the MASKED prompt and writes the answer. This is
             the only call that is billed.

Input tokens are counted exactly with the Gemma 3/4 SentencePiece tokenizer (262k vocab) on the
same strings the app builds. Output tokens are estimates: the guard's from the findings JSON a
perfect guard would return, the answer's from a per-task budget (ANSWER_BUDGET below).
Masking uses mask.mask() with the expected items, i.e. it assumes the guard caught everything.

Run:  pip install sentencepiece
      python benchmark_cost.py                     # table on stdout
      python benchmark_cost.py --out COST_REPORT.md
No Ollama or API key needed. The tokenizer (~4.7 MB) is downloaded once to ~/.cache/safepaste/.
"""
from __future__ import annotations

import argparse
import json
import math
import urllib.request
from pathlib import Path

import cloud
import inspector
import mask

HERE = Path(__file__).parent
TOKENIZER_URL = ("https://raw.githubusercontent.com/google/gemma_pytorch/main/"
                 "tokenizer/gemma3_cleaned_262144_v2.spiece.model")
TOKENIZER_PATH = Path.home() / ".cache" / "safepaste" / "gemma3_262k.spiece.model"

# USD per 1M tokens (input, output) for the ANSWER call. Checked 2026-10-09; edit as prices move.
PRICES = {
    "Gemma 4 26B · Gemini API free tier": (0.00, 0.00),   # free tier only, rate-limited, data may train Google models
    "Gemma 4 26B · Vertex AI": (0.15, 0.60),               # paid, Google Cloud billing
    "Gemini 2.5 Flash-Lite": (0.10, 0.40),
    "Gemini 3 Flash": (0.50, 3.00),
    "Gemini 3 Pro": (2.00, 12.00),
}
BILLED = "Gemma 4 26B · Vertex AI"  # the paid price the summary leads with

# Estimated answer length in tokens per task. "x1.2" means 1.2 x the masked prompt's tokens.
ANSWER_BUDGET = {"qa": 150, "summarize": 180, "email": 250, "analysis": 350, "code_review": 400,
                 "rewrite": "x1.2", "translate": "x1.6"}

# Ollama's Gemma chat template folds the system prompt into the first user turn.
TEMPLATE = "<bos><start_of_turn>user\n{system}\n\n{prompt}<end_of_turn>\n<start_of_turn>model\n"


class Tokenizer:
    def __init__(self):
        self.exact = False
        try:
            import sentencepiece as spm
            if not TOKENIZER_PATH.exists():
                TOKENIZER_PATH.parent.mkdir(parents=True, exist_ok=True)
                urllib.request.urlretrieve(TOKENIZER_URL, TOKENIZER_PATH)
            self.sp = spm.SentencePieceProcessor(model_file=str(TOKENIZER_PATH))
            self.exact = True
        except Exception as e:  # no sentencepiece or no network: fall back to a rough estimate
            print(f"warning: Gemma tokenizer unavailable ({type(e).__name__}: {e}); "
                  "using ~3.5 chars/token, numbers are approximate\n")

    def count(self, text: str) -> int:
        if self.exact:
            return len(self.sp.encode(text))
        return math.ceil(len(text) / 3.5)


def guard_output(expected: list[dict]) -> str:
    """The findings JSON a perfect local guard would return for this prompt."""
    return json.dumps({"findings": [
        {"text": e["text"], "type": e["type"], "reason": f"Policy forbids sending {e['type'].lower()} items."}
        for e in expected]}, ensure_ascii=False)


def answer_tokens(task: str, masked_tokens: int) -> int:
    budget = ANSWER_BUDGET.get(task, 250)
    if isinstance(budget, str):
        return max(60, round(float(budget[1:]) * masked_tokens))
    return budget


def measure(case: dict, policy: str, tok: Tokenizer) -> dict:
    text, expected = case["prompt"], case.get("expected", [])
    masked, _ = mask.mask(text, expected)

    guard_prompt = f"COMPANY POLICY:\n{policy}\n\nTEXT TO CHECK:\n<<<\n{text}\n>>>"  # as in inspector.py
    guard_in = tok.count(TEMPLATE.format(system=inspector.SYSTEM, prompt=guard_prompt))
    guard_out = tok.count(guard_output(expected))

    masked_tokens = tok.count(masked)
    cloud_in = tok.count(cloud.KEEP_PLACEHOLDERS) + masked_tokens  # system_instruction + contents
    cloud_out = answer_tokens(case.get("task", ""), masked_tokens)

    return {"id": case.get("id"), "category": case.get("category", ""), "task": case.get("task", ""),
            "items": len(expected), "raw": tok.count(text), "masked": masked_tokens,
            "guard_in": guard_in, "guard_out": guard_out, "cloud_in": cloud_in, "cloud_out": cloud_out}


def cost(row: dict, price: tuple[float, float]) -> float:
    return (row["cloud_in"] * price[0] + row["cloud_out"] * price[1]) / 1e6


def usd(x: float) -> str:
    return f"${x:,.2f}" if x >= 0.01 or x == 0 else f"${x:.6f}"


def report(rows: list[dict], tok: Tokenizer, overhead: int, users: int, per_day: int, days: int) -> str:
    n = len(rows)
    total = {k: sum(r[k] for r in rows) for k in ("raw", "masked", "guard_in", "guard_out", "cloud_in", "cloud_out")}
    monthly = users * per_day * days
    lines = [
        "# SafePaste token and cost benchmark", "",
        f"{n} synthetic prompts from `tests/prompts.jsonl`, {sum(r['items'] for r in rows)} labelled sensitive items. "
        f"Tokenizer: {'Gemma 3/4 SentencePiece, 262k vocab (exact)' if tok.exact else 'estimate, ~3.5 chars/token'}. "
        "Generated by `python benchmark_cost.py --out COST_REPORT.md`.", "",
        "Only the cloud answer call is billed. The local guard runs on the laptop: it costs time and power, not API dollars.", "",
        "## Per prompt", "",
        f"Cost is for the billed cloud call at {BILLED} prices "
        f"(${PRICES[BILLED][0]:.2f} in / ${PRICES[BILLED][1]:.2f} out per 1M tokens). "
        "Guard and answer output tokens are estimates; everything else is counted.", "",
        "| # | category | task | items | prompt tok | masked tok | guard in | guard out | cloud in | cloud out | cost / prompt | cost / 1k prompts |",
        "|--:|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for r in rows:
        c = cost(r, PRICES[BILLED])
        lines.append(f"| {r['id']} | {r['category']} | {r['task']} | {r['items']} | {r['raw']} | {r['masked']} | "
                     f"{r['guard_in']} | {r['guard_out']} | {r['cloud_in']} | {r['cloud_out']} | {usd(c)} | {usd(c * 1000)} |")
    lines.append(f"| **all** | | | {sum(r['items'] for r in rows)} | {total['raw']} | {total['masked']} | "
                 f"{total['guard_in']} | {total['guard_out']} | {total['cloud_in']} | {total['cloud_out']} | "
                 f"{usd(sum(cost(r, PRICES[BILLED]) for r in rows))} | |")

    lines += ["", "## Average prompt", "",
              "| stage | where | input tokens | output tokens |", "|---|---|--:|--:|",
              f"| guard (inspector.py) | local Ollama | {total['guard_in'] / n:.0f} | {total['guard_out'] / n:.0f} |",
              f"| answer (cloud.py) | cloud | {total['cloud_in'] / n:.0f} | {total['cloud_out'] / n:.0f} |",
              "", f"{overhead} of the guard's input tokens are fixed: the chat template, `inspector.SYSTEM` and policy.md "
              "go out with every prompt, so the local guard reads about "
              f"{total['guard_in'] / total['cloud_in']:.1f}x as many tokens as the cloud model does.",
              "", f"Masking changes the prompt from {total['raw']} to {total['masked']} tokens across the benchmark "
              f"({100 * (total['masked'] - total['raw']) / total['raw']:+.1f}%). A placeholder such as ⟦CLIENT_1⟧ is "
              f"{tok.count('⟦CLIENT_1⟧')} tokens: longer than a short name, much shorter than an API key, "
              "so masking is roughly token-neutral.",
              "", "## Cloud model comparison", "",
              f"Monthly volume assumed: {users} users x {per_day} prompts/day x {days} days = {monthly:,} prompts, "
              "each the average benchmark prompt.", "",
              "| answer model | $ in / out per 1M | per prompt | per 1k prompts | whole benchmark | per month |",
              "|---|---|--:|--:|--:|--:|"]
    for name, price in PRICES.items():
        avg = sum(cost(r, price) for r in rows) / n
        lines.append(f"| {name} | ${price[0]:.2f} / ${price[1]:.2f} | {usd(avg)} | {usd(avg * 1000)} | "
                     f"{usd(avg * n)} | {usd(avg * monthly)} |")

    by_cat: dict[str, list[dict]] = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r)
    lines += ["", "## By category", "",
              f"| category | prompts | avg cloud in | avg cloud out | avg cost / 1k prompts ({BILLED}) |",
              "|---|--:|--:|--:|--:|"]
    for cat, rs in by_cat.items():
        k = len(rs)
        lines.append(f"| {cat} | {k} | {sum(r['cloud_in'] for r in rs) / k:.0f} | {sum(r['cloud_out'] for r in rs) / k:.0f} | "
                     f"{usd(1000 * sum(cost(r, PRICES[BILLED]) for r in rs) / k)} |")

    lines += ["", "## Assumptions", "",
              "- Prices are USD per 1M tokens, checked 2026-10-09; edit `PRICES` in `benchmark_cost.py` when they change. "
              "On the Gemini API, Gemma 4 is free tier only (rate-limited, and free-tier prompts may be used to improve "
              "Google products); the paid route for the same model is Vertex AI.",
              "- Guard input = Gemma chat template + `inspector.SYSTEM` + policy.md + the prompt, as `inspector.py` builds it. "
              "The JSON schema is enforced by Ollama's constrained decoding and is not counted as prompt text. "
              "A bad-JSON retry would double the guard's tokens.",
              "- Guard output = the findings JSON for the expected items, with a one-line reason each.",
              "- Cloud input = `cloud.KEEP_PLACEHOLDERS` system instruction + the masked prompt (mask.mask with the expected items).",
              "- Cloud output budgets per task: " + ", ".join(
                  f"{t} {b if isinstance(b, int) else b + ' prompt'}" for t, b in ANSWER_BUDGET.items()) + ". "
              "Output dominates cost on every paid model, so these budgets matter most.",
              "- Screenshots: `vision.py` transcribes locally (Gemma vision, roughly 256-1,100 image tokens per screenshot "
              "depending on resolution), then the transcript goes through the same two calls. No extra billed tokens.",
              "- The Gemma 4 tokenizer is assumed to match Gemma 3's 262k SentencePiece vocabulary."]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--prompts", default="tests/prompts.jsonl")
    ap.add_argument("--out", help="also write the markdown report to this file")
    ap.add_argument("--users", type=int, default=50)
    ap.add_argument("--prompts-per-day", type=int, default=20)
    ap.add_argument("--days", type=int, default=22)
    args = ap.parse_args()

    policy = (HERE / "policy.md").read_text(encoding="utf-8")
    cases = [json.loads(l) for l in (HERE / args.prompts).read_text(encoding="utf-8").splitlines() if l.strip()]
    tok = Tokenizer()
    overhead = measure({"prompt": ""}, policy, tok)["guard_in"]
    md = report([measure(c, policy, tok) for c in cases], tok, overhead, args.users, args.prompts_per_day, args.days)
    print(md)
    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")


if __name__ == "__main__":
    main()
