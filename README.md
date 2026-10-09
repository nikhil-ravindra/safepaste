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
- `python bench_latency.py --model gemma4:e4b` times the local guard on every benchmark prompt with real Ollama and reports median/p95 time, tokens/s and catch rate. Run it again with `gemma4:e2b` to compare.

## Speed

The guard is quick because Gemma writes very little. Regex hits are masked before Gemma reads the text, and Gemma returns only `text` + `type`, with no reasons, which cuts its output by about 60%. The app also loads Gemma in the background at start-up and keeps it loaded for 30 minutes (`SAFEPASTE_KEEP_ALIVE`). The context size is fixed (`SAFEPASTE_NUM_CTX`, default 8192), so Ollama never reloads the model between requests.

Ollama side:

- `ollama ps` while the app runs: PROCESSOR should read `100% GPU`. A CPU/GPU split is the most common reason it's slow. Fix it with a smaller model or a smaller `SAFEPASTE_NUM_CTX`.
- Start Ollama with `OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 ollama serve` (less memory for the KV cache, faster on long prompts).
- On a laptop without a GPU, use `gemma4:e2b`. Check its catch rate with `bench_latency.py` first.
- Laptops throttle on battery. Plug in for the demo.
