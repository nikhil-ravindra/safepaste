# SafePaste
# SafePaste Demo Assets

This directory contains visual and synthetic data assets required for testing and presenting the SafePaste hackathon project.

## Included Files

- **`dashboard_q3.png`**: A mock screenshot simulating an internal corporate Google Sheet dashboard containing fake Indian financial transactions, GST values, client names, and project codenames. Used to demonstrate `vision.py` screenshot inspection and masking.

## Disclaimer & Privacy Notice

> **Note**: All records, company names, monetary amounts (₹), project codenames, API keys, and transaction IDs contained in this directory and associated screenshot files are 100% synthetically generated for demonstration purposes only. None of the entries represent real individuals, corporate entities, or live credentials.

## Benchmark

`tests/prompts.jsonl` holds 23 synthetic prompts with their sensitive items labelled.

- `python eval.py` measures the catch rate (needs Ollama and `SAFEPASTE_MODEL`; without them it reports regex-only results).
- `python benchmark_cost.py --out COST_REPORT.md` counts tokens per prompt for each model call and prices them (needs `pip install sentencepiece`, no API key). Results: [COST_REPORT.md](COST_REPORT.md).
