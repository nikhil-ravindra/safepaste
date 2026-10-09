# SafePaste

Use cloud AI at work without handing it your secrets.

SafePaste runs a small Gemma 4 model on the employee's laptop. Before a message goes to a cloud AI, it finds client names, deal values, codenames, people and keys, swaps each for a placeholder like `⟦CLIENT_1⟧`, and sends only the masked text. When the answer comes back, the real values are put back on the laptop.

Built for Hacktoberfest Hack Day Bengaluru 2026 (MLH x IEEE CIS). Tracks: PS02 Gemma 4, and Best Open-Source AI Project.

## The problem

People paste company data into AI chats every day. Once they press enter, it has left the company. In 2023 Samsung banned generative AI tools after engineers pasted internal source code into ChatGPT. Bans do not stop the habit; people move to personal phones, where the company sees nothing.

## How it works

```
On the laptop                                   | Cloud            | Back on the laptop
01 Read     text, or a screenshot read by Gemma |                  |
02 Inspect  regex + Gemma 4 e4b vs the policy   | 05 Answer        | 06 Restore real values,
03 Swap     secrets -> ⟦TYPE_N⟧ placeholders     |    Gemma 4 26B   |    do maths on hidden
04 Approve  high risk waits for a person        |    sees masked   |    amounts, log counts
                                                |    text only     |    and a hash only
```

What you type:

> Summarize Q3: Acme Corp renewed at ₹4.2 Cr, Zenith Retail churned, Project Falcon slips to December. Ping ravi@acme.in.

What the cloud receives:

> Summarize Q3: ⟦CLIENT_1⟧ renewed at ⟦AMOUNT_1⟧, ⟦CLIENT_2⟧ churned, ⟦CODENAME_1⟧ slips to December. Ping ⟦PERSON_1⟧.

## Features

- **Plain-English policy.** Security writes rules as sentences ("never send client names..."). Gemma reads them before every check. Edit the policy in the app or upload it as a PDF, and the next check uses it.
- **Two layers of detection.** Regex for fixed shapes (API keys, AWS and GitHub tokens, passwords, emails, Indian mobile numbers, ₹ amounts) and Gemma 4 for things that need understanding (clients, codenames, names).
- **Screenshots.** Upload an image of a dashboard or sheet. Local Gemma turns it into text on the laptop; the image never goes to the cloud.
- **Human approval.** Keys, code, or more than five secrets in one message mean high risk, and nothing is sent until a person approves.
- **Choose what to hide.** Untick a kind (for example money amounts) when the AI needs to see it.
- **Maths on hidden numbers.** The cloud writes formulas with placeholders, for example `[[calc:rupees: (⟦AMOUNT_1⟧ + ⟦AMOUNT_2⟧) / 2]]`. The laptop plugs in the real values and evaluates them with a whitelist calculator (numbers, + - * / and brackets only).
- **Chat memory.** Follow-up questions work. The same value keeps the same placeholder for the whole chat. Memory lives in RAM only, as placeholders; "New chat" forgets it. The circle at the top right shows what the chat remembers.
- **Private-by-schema log.** A local SQLite file records sessions and events: time, action, risk, counts by type and a sha256 of the masked text. There is no column where text could go.

## Safety rules in the code

1. If inspection crashes, nothing is sent. If local Gemma is down, the regex rules still run and the screen says so.
2. Every finding must appear word for word in the message, so the model cannot invent secrets.
3. Risk levels come from fixed rules; anything unexpected counts as high risk.
4. The placeholder map is never written to disk.
5. The audit log and database store counts and hashes, never raw text.
6. Demos and tests use synthetic data only. The API key lives in `.env`, which git ignores.

## Results

25 synthetic prompts in `tests/prompts.jsonl`: 15 contain 32 planted secrets, 10 contain nothing secret. Run with `python eval.py`.

| Metric | Regex only | With Gemma 4 e4b |
|---|---|---|
| Catch rate | 15 / 32 (46.9%) | 32 / 32 (100%) |
| False swaps | 0 | 1 (the word "invoice") |
| Restore success (mock cloud) | 25 / 25 | 25 / 25 |
| Clients / codenames | 0 / 10, 0 / 4 | 10 / 10, 4 / 4 |
| People / amounts / keys | 3 / 6, 8 / 8, 4 / 4 | 6 / 6, 8 / 8, 4 / 4 |

This is a small set we wrote ourselves. In live use Gemma has missed a client name once, which is why the policy is editable and high-risk messages need approval.

Speed on our 32 GB Windows laptop: Gemma 4 e4b about 90 tokens/s (12B about 21 tokens/s, so we use e4b). The local check takes about 3 to 4 seconds per message. Most of the remaining wait is the cloud model.

## Run it

Requirements: Python 3.11+, [Ollama](https://ollama.com), a Gemini API key (optional; without it the app uses a mock cloud answer and says so).

```bash
ollama pull gemma4:e4b
pip install -r requirements.txt
cp .env.example .env          # then add GEMINI_API_KEY
python -m streamlit run app.py
```

`.env` settings:

| Variable | Default | Meaning |
|---|---|---|
| `GEMINI_API_KEY` | none | Key for Gemma 4 on the Gemini API |
| `SAFEPASTE_MODEL` | `gemma4:e4b` | Local Ollama model |
| `CLOUD_GEMMA_MODEL` | `gemma-4-26b-a4b-it` | Cloud model |
| `CLOUD_MAX_TOKENS` | `500` | Cap on answer length |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama address |

Other commands:

```bash
python eval.py     # detection benchmark
python db.py       # totals from the local database (counts only)
```

## Project layout

| File | Job |
|---|---|
| `app.py` | Streamlit app: pipeline, approval, answer |
| `ui.py` | Styling, landing page, loader, pipeline view |
| `ollama_client.py` | Calls local Gemma via Ollama (stdlib only) |
| `inspector.py` | Regex + Gemma detection, validated findings |
| `vision.py` | Screenshot to text with local Gemma |
| `risk.py` | Fixed risk rules |
| `mask.py` | Swap secrets for placeholders and back |
| `cloud.py` | Gemma 4 on the Gemini API, with mock fallback |
| `calc.py` | Safe local maths on hidden amounts |
| `memory.py` | Chat memory in RAM, placeholders only |
| `db.py` | SQLite sessions and events, no text columns |
| `audit_log.py` | JSONL audit log, allowlisted fields, hashed prompt |
| `policy.md` | Default company policy in plain English |
| `eval.py`, `tests/prompts.jsonl` | Benchmark and synthetic test set |

## Limits

- A small local model can miss things; regex and human approval are the backstops.
- Context can still hint ("the Pune client that renewed" says something even with the name hidden).
- Restoring needs the cloud to keep placeholders intact; missing ones are flagged.
- Today SafePaste is its own chat window, not a plug-in for ChatGPT or Copilot.

## Next

1. Copy-out mode: copy the safe prompt into any AI tool, paste the answer back to restore it.
2. A local endpoint that speaks the OpenAI API, so existing tools can point at SafePaste.
3. A browser extension that checks a paste before it lands.

## Team

- Nikhil: interface, local Gemma pipeline, integration
- [Name]: masking, restore and the audit log
- [Name]: test set, evaluation and the pitch

## License

Apache-2.0. All demo data is synthetic.
