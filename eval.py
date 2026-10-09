"""Measures how well SafePaste catches sensitive items. Owner: Person 2.

For each synthetic prompt in tests/prompts.jsonl:
  1. Gemma + regex inspect it against policy.md (inspector.inspect)
  2. mask() replaces what was found
  3. An expected item counts as CAUGHT if it no longer appears in the masked text
  4. A finding that matches no expected item counts as a FALSE SWAP
  5. The mock cloud answer is restored; we check every placeholder came back

Line format: {"id": 1, "prompt": "...", "expected": [{"text": "Acme Corp", "type": "CLIENT"}]}
Run:  python eval.py            (needs Ollama running and SAFEPASTE_MODEL set)
All test data is synthetic.
"""
import json
import sys
from collections import Counter
from pathlib import Path

import cloud
import inspector
import mask

HERE = Path(__file__).parent


def overlaps(a: str, b: str) -> bool:
    a, b = a.lower(), b.lower()
    return a in b or b in a


def main(path: str = "tests/prompts.jsonl") -> None:
    policy = (HERE / "policy.md").read_text(encoding="utf-8")
    lines = [l for l in (HERE / path).read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lines:
        sys.exit(f"No test prompts in {path}")

    expected_total = caught_total = false_swaps = restore_ok = 0
    missed_by_type, total_by_type = Counter(), Counter()

    for line in lines:
        case = json.loads(line)
        text, expected = case["prompt"], case.get("expected", [])
        findings = inspector.inspect(text, policy)
        masked, mapping = mask.mask(text, findings)

        missed = []
        for item in expected:
            total_by_type[item.get("type", "OTHER")] += 1
            if item["text"].lower() in masked.lower():
                missed.append(item["text"])
                missed_by_type[item.get("type", "OTHER")] += 1
        caught = len(expected) - len(missed)
        expected_total += len(expected)
        caught_total += caught

        extra = [f["text"] for f in findings if not any(overlaps(f["text"], e["text"]) for e in expected)]
        false_swaps += len(extra)

        _, not_back = mask.restore(cloud.ask(masked, mode="mock"), mapping)
        restore_ok += not not_back

        status = "OK  " if not missed else "MISS"
        print(f"[{status}] #{case.get('id')}: caught {caught}/{len(expected)}"
              + (f" | missed {missed}" if missed else "")
              + (f" | extra {extra}" if extra else "")
              + (f" | Gemma error: {inspector.LAST_ERROR}" if inspector.LAST_ERROR else ""))

    print("\n================ SafePaste evaluation ================")
    print(f"Prompts:            {len(lines)}")
    print(f"Catch rate:         {caught_total}/{expected_total} = {100 * caught_total / max(expected_total, 1):.1f}%")
    print(f"False swaps:        {false_swaps}  (safe text masked unnecessarily)")
    print(f"Restore success:    {restore_ok}/{len(lines)} answers fully restored (mock cloud)")
    print("Catch rate by type:")
    for t, n in total_by_type.most_common():
        print(f"  {t:<11} {n - missed_by_type[t]}/{n}")


if __name__ == "__main__":
    main(*sys.argv[1:])
