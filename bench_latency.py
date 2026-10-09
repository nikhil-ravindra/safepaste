"""Times the local guard on every prompt in tests/prompts.jsonl, with real Ollama.

Run:  SAFEPASTE_MODEL=gemma4:e4b python bench_latency.py
      python bench_latency.py --model gemma4:e2b       # compare a smaller model
Prints per-prompt wall time and Ollama's own timings, then medians, tokens/s and catch rate,
so you can pick the model and settings that are fast enough without missing secrets.
"""
import argparse
import json
import os
import statistics
import time
from pathlib import Path

HERE = Path(__file__).parent


def pct(values: list[float], p: float) -> float:
    values = sorted(values)
    return values[min(len(values) - 1, round(p * (len(values) - 1)))]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", help="overrides SAFEPASTE_MODEL")
    ap.add_argument("--prompts", default="tests/prompts.jsonl")
    args = ap.parse_args()
    if args.model:
        os.environ["SAFEPASTE_MODEL"] = args.model

    import inspector  # after setting the model
    import mask
    import ollama_client

    policy = (HERE / "policy.md").read_text(encoding="utf-8")
    cases = [json.loads(l) for l in (HERE / args.prompts).read_text(encoding="utf-8").splitlines() if l.strip()]

    started = time.perf_counter()
    inspector.warm_up(policy)
    print(f"model {os.environ.get('SAFEPASTE_MODEL')}: loaded and warmed up in {time.perf_counter() - started:.1f} s\n")

    walls, rates, caught, expected_total = [], [], 0, 0
    print(f"{'#':>3} {'items':>5} {'caught':>6} {'wall s':>7} {'read tok':>8} {'read s':>7} "
          f"{'wrote tok':>9} {'write s':>7} {'tok/s':>6}")
    for case in cases:
        t0 = time.perf_counter()
        findings = inspector.inspect(case["prompt"], policy)
        wall = time.perf_counter() - t0
        if inspector.LAST_ERROR:
            print(f"{case['id']:>3} Gemma error: {inspector.LAST_ERROR}")
            continue
        masked, _ = mask.mask(case["prompt"], findings)
        expected = case.get("expected", [])
        hit = sum(e["text"].lower() not in masked.lower() for e in expected)
        s = ollama_client.LAST_STATS
        walls.append(wall)
        rates.append(s["tokens_per_s"])
        caught += hit
        expected_total += len(expected)
        print(f"{case['id']:>3} {len(expected):>5} {hit:>6} {wall:>7.2f} {s['prompt_tokens']:>8} {s['prompt_s']:>7.2f} "
              f"{s['output_tokens']:>9} {s['output_s']:>7.2f} {s['tokens_per_s']:>6.1f}")

    if not walls:
        raise SystemExit("No successful Gemma calls. Is Ollama running and the model pulled?")
    print(f"\nwall time per prompt: median {statistics.median(walls):.2f} s, p95 {pct(walls, 0.95):.2f} s, "
          f"max {max(walls):.2f} s")
    print(f"generation speed:     median {statistics.median(rates):.1f} tokens/s")
    print(f"catch rate:           {caught}/{expected_total} = {100 * caught / max(expected_total, 1):.1f}%")


if __name__ == "__main__":
    main()
