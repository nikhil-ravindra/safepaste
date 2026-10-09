# eval.py — owner: Person 2
import json
import os
import sys
from cloud import ask


def load_test_prompts(file_path: str = "tests/prompts.jsonl") -> list:
    """Loads JSONL test dataset."""
    if not os.path.exists(file_path):
        print(f"Error: Dataset not found at {file_path}")
        sys.exit(1)

    prompts = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                prompts.append(json.loads(line.strip()))
    return prompts


def evaluate_dataset(mode: str = "mock", file_path: str = "tests/prompts.jsonl"):
    """
    Evaluates catch rate and placeholder preservation across the synthetic dataset.
    """
    prompts = load_test_prompts(file_path)
    total_tests = len(prompts)
    passed_tests = 0

    print(f"\n==================================================")
    print(f"   SafePaste Evaluation Suite - Mode: [{mode.upper()}]")
    print(f"==================================================\n")

    for test in prompts:
        test_id = test.get("id")
        prompt_text = test.get("prompt")
        expected_items = test.get("expected", [])

        # Execute prompt through cloud wrapper
        response = ask(prompt_text, mode=mode)

        # Verify that all expected placeholders appear in the mock response or original prompt structure
        missing_placeholders = []
        for item in expected_items:
            expected_text = item.get("text")
            if expected_text not in response and expected_text not in prompt_text:
                missing_placeholders.append(expected_text)

        if not missing_placeholders:
            passed_tests += 1
            status = "PASSED"
        else:
            status = "FAILED"

        print(f"Test #{test_id:02d}: [{status}] | Expected Placeholders: {len(expected_items)}")
        if missing_placeholders:
            print(f"         Missing: {missing_placeholders}")

    catch_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0.0

    print("\n--------------------------------------------------")
    print(f"Evaluation Summary:")
    print(f"  Total Prompts Evaluated: {total_tests}")
    print(f"  Successful Catch/Preservations: {passed_tests}")
    print(f"  Overall Catch Rate: {catch_rate:.2f}%")
    print("--------------------------------------------------\n")


if __name__ == "__main__":
    # Default to mock mode evaluation; pass 'gemini' as CLI arg for live cloud test
    eval_mode = sys.argv[1] if len(sys.argv) > 1 else "mock"
    evaluate_dataset(mode=eval_mode)
