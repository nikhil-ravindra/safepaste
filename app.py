"""SafePaste: inspect and mask on this machine, send only the masked text, restore the answer locally.

Run:  streamlit run app.py
"""

from __future__ import annotations

import html
import importlib
import re
from pathlib import Path

import streamlit as st

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import audit_log
import calc
import db
import mask
import memory
import json
import os
import time
import urllib.request
import warnings

import ui

HERE = Path(__file__).parent
DEFAULT_POLICY = (
    "Treat as sensitive: client and company names, money amounts, internal codenames, "
    "people's names and emails, credentials and secrets, and proprietary source code."
)
RISK_STYLE = {
    "low": ("#4F7A4A", "Low risk"),
    "medium": ("#B98A2E", "Medium risk"),
    "high": ("#B5603F", "High risk"),
}
TYPE_COLOR = {  # soft, paper-friendly highlights
    "CLIENT": "#DCE8D3",
    "AMOUNT": "#EFE0C8",
    "CODENAME": "#E8DCEB",
    "PERSON": "#F3DCD0",
    "CREDENTIAL": "#F1CFC3",
    "CODE": "#E4E0D7",
    "OTHER": "#EFE7D2",
}


def load_module(name: str):
    """Return (module, is_stub): the teammate's real module if it exists, else stubs/<name>.py."""
    try:
        return importlib.import_module(name), False
    except ModuleNotFoundError as exc:
        if exc.name != name:
            raise  # the real module exists but one of its own imports is missing
        return importlib.import_module(f"stubs.{name}"), True


MODULES = {name: load_module(name) for name in ("vision", "inspector", "risk", "cloud")}
vision, inspector, risk, cloud = (MODULES[name][0] for name in ("vision", "inspector", "risk", "cloud"))


def file_policy() -> str:
    path = HERE / "policy.md"
    return path.read_text(encoding="utf-8") if path.exists() else DEFAULT_POLICY


def load_policy() -> str:
    """The policy Gemma reads: the sidebar editor's version if changed, else policy.md."""
    return st.session_state.get("policy_text") or file_policy()


HIDE_CHOICES = {
    "Client names": "CLIENT",
    "Money amounts": "AMOUNT",
    "Codenames": "CODENAME",
    "People": "PERSON",
    "Keys": "CREDENTIAL",
    "Code": "CODE",
    "Other": "OTHER",
}

EXAMPLES = {
    "Sales update": ("Summarize Q3 for my boss in 3 bullets: Acme Corp renewed at ₹4.2 Cr, Zenith Retail churned, "
                       "and the Project Falcon launch slips to December. Ping ravi@acme.in for the deck."),
    "API key in code": ("Why does this fail?\n\nimport requests\nAPI_KEY = \"sk-live9f8a7b6c5d4e3f2a1b0c\"\n"
                         "resp = requests.get('https://api.internal.example/v1/deals', headers={'Authorization': API_KEY})\n"
                         "print(resp.json()['Acme Corp'])"),
    "New codename": "Write a short teaser announcing Project Phoenix to our sales team, launching next month.",
    "Average deal size": ("What's our average deal size this quarter, and how much bigger is the Acme Corp deal than "
                          "Zenith Retail? Acme Corp: ₹4.2 Cr, Zenith Retail: ₹2.1 Cr, Orbit Foods: ₹95,00,000."),
    "Nothing secret": "Write a polite two-line email asking my team to submit their timesheets by Friday.",
}


def pdf_text(data: bytes) -> str:
    """Text of a PDF, read on this laptop. Needs pypdf (pip install pypdf)."""
    from io import BytesIO
    from pypdf import PdfReader
    return "\n".join((page.extract_text() or "") for page in PdfReader(BytesIO(data)).pages).strip()


def load_policy_file() -> None:
    """on_change for the policy uploader: put the file's text into the policy box."""
    upload = st.session_state.get("policy_file")
    if upload is None:
        return
    try:
        data = upload.getvalue()
        if upload.name.lower().endswith(".pdf"):
            text = pdf_text(data)
        else:
            text = data.decode("utf-8", errors="replace").strip()
    except ImportError:
        st.session_state["policy_msg"] = "Reading PDFs needs pypdf. Run: pip install pypdf"
        return
    except Exception as exc:
        st.session_state["policy_msg"] = f"Couldn't read {upload.name}: {exc}"
        return
    if not text:
        st.session_state["policy_msg"] = f"No text found in {upload.name}. A scanned PDF needs a text version."
        return
    st.session_state["policy_text"] = text
    st.session_state["policy_msg"] = f"Loaded the policy from {upload.name}. Gemma uses it from the next check."


def use_example(name: str) -> None:
    st.session_state["prompt"] = EXAMPLES[name]
    st.session_state.pop("run", None)


@st.cache_data(ttl=10, show_spinner=False)
def local_gemma_status(model: str) -> tuple[bool, str]:
    """Is Ollama running locally, and is the chosen Gemma model installed?"""
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434") + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=1.5) as r:
            names = [m.get("name", "") for m in json.loads(r.read()).get("models", [])]
    except Exception:
        return False, "Ollama is not running. Open the Ollama app."
    if not model:
        return False, "SAFEPASTE_MODEL not set"
    if model not in names and f"{model}:latest" not in names:
        return False, f"{model} not installed (ollama pull {model})"
    return True, f"{model} ready"


def type_of(placeholder: str) -> str:
    return placeholder.strip("⟦⟧").rsplit("_", 1)[0]


def loose(text) -> str:
    """Case- and spacing-insensitive key, matching how mask() falls back."""
    return " ".join(str(text).split()).lower()


def highlighted(text: str, spans: dict) -> str:
    """Escaped HTML of text with secrets (terracotta) or placeholders (sage) marked. Two tones only."""
    parts, last = [], 0
    if spans:
        pattern = re.compile("|".join(re.escape(s) for s in sorted(spans, key=len, reverse=True)))
        for match in pattern.finditer(text):
            kind, value = spans[match.group(0)], match.group(0)
            tone = "ph" if value.startswith("⟦") else "secret"
            parts.append(html.escape(text[last : match.start()]))
            parts.append(f'<mark class="sp-mark {tone}" title="{kind}">{html.escape(value)}</mark>')
            last = match.end()
    parts.append(html.escape(text[last:]))
    return '<div class="sp-doc">' + "".join(parts) + "</div>"


def readable(answer_html: str) -> str:
    """Light markdown for the answer box: **bold** becomes bold, '* ' lines become bullets, extra blank lines go."""
    out = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", answer_html)
    out = re.sub(r"(?m)^[ \t]*[*-][ \t]+", "• ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out


def legend(kinds) -> str:
    return '<div class="sp-legend">Types found: ' + ", ".join(k.lower() for k in sorted(kinds)) + "</div>"


def prepare(text: str, image):
    """Everything that happens before anything leaves the machine. None if there is no text at all."""
    parts = [text.strip()] if text.strip() else []
    timings = {}
    if image is not None:
        with st.spinner("Gemma 4 is reading the screenshot on this laptop…"):
            t0 = time.perf_counter()
            transcript = vision.transcribe(image.getvalue())
            timings["vision"] = time.perf_counter() - t0
        if transcript and transcript.strip():
            parts.append(transcript.strip())
    original = "\n\n".join(parts)
    if not original:
        return None
    loading = st.empty()
    with loading.container():
        ui.skeleton()

    with st.spinner("Gemma 4 is checking it against your company policy, on this laptop…"):
        t0 = time.perf_counter()
        all_findings = inspector.inspect(original, load_policy())
        hide = set(st.session_state.get("hide_types") or HIDE_CHOICES.values())
        findings = [f for f in all_findings if f.get("type") in hide]
        kept_visible = len(all_findings) - len(findings)
        timings["inspect"] = time.perf_counter() - t0
    notes = []
    if getattr(vision, "LAST_ERROR", None) and image is not None:
        notes.append(f"Screenshot couldn't be read by local Gemma: {vision.LAST_ERROR}")
    if getattr(inspector, "LAST_ERROR", None):
        notes.append("Local Gemma didn't answer, so only the fixed pattern rules ran (keys, emails, phones, ₹). "
                     f"Details: {inspector.LAST_ERROR}")
    level = str(risk.assess(findings, original)).strip().lower()
    if level not in RISK_STYLE:
        level = "high"  # an unexpected answer from the risk module fails closed
    masked, mapping = mask.mask(original, findings)
    # Same value, same placeholder for the whole chat (memory lives in RAM only).
    masked, mapping = st.session_state.memory.merge(masked, mapping)
    missed = mask.unmatched(original, findings)
    loading.empty()

    return {
        "original": original,
        "findings": findings,
        "risk": level,
        "masked": masked,
        "mapping": mapping,
        "unmatched": missed,
        # Approval is required for high risk, and also when the inspector flagged something
        # that mask() could not find, since that text may be going out unmasked.
        "needs_approval": level == "high" or bool(missed),
        "image": image.getvalue() if image is not None else None,
        "status": "pending",
        "timings": timings,
        "kept_visible": kept_visible,
        "notes": notes,
    }


def log_event(run: dict, action: str, mode: str) -> None:
    try:
        audit_log.write(
            {
                "action": action,
                "risk": run["risk"],
                "mode": mode,
                "types": [type_of(p) for p in run["mapping"]],
                "counts": {
                    "findings": len(run["findings"]),
                    "masked": len(run["mapping"]),
                    "placeholders_not_found": len(run.get("missing", [])),
                },
                "had_screenshot": run["image"] is not None,
                "prompt": run["masked"],  # hashed inside audit_log; only the sha256 is stored
            }
        )
    except OSError as exc:
        st.error(f"Could not write the audit log: {exc}")
    try:
        db.record_event(st.session_state.memory.id, action, run["risk"], mode,
                        [type_of(p) for p in run["mapping"]], run["image"] is not None, run["masked"])
    except Exception:
        pass  # the database is a log, never a reason to block the user


def send(run: dict, mode: str, approved: bool) -> None:
    try:
        with st.spinner("Cloud Gemma is answering. It only sees placeholders…"):
            t0 = time.perf_counter()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")  # library deprecation noise is not a failure
                answer = cloud.ask(run["masked"], mode=mode, history=st.session_state.memory.history())
            if mode != "mock" and getattr(cloud, "LAST_NOTE", None):
                run["cloud_note"] = f"Cloud Gemma unavailable, so a mock answer was used. {cloud.LAST_NOTE}"
            run.setdefault("timings", {})["cloud"] = time.perf_counter() - t0
    except Exception as exc:  # report it; never fall back to sending anything else
        run.update(status="error", error=str(exc))
        log_event(run, "cloud_error", mode)
        return
    chat_mapping = st.session_state.memory.mapping  # answers may mention values from earlier messages
    answer_calc, calc_steps = calc.resolve(answer, chat_mapping)
    restored, missing = mask.restore(answer_calc, chat_mapping)
    used_in_calc = {ph for step in calc_steps for ph in calc.PLACEHOLDER.findall(step["formula"])}
    # only this message's placeholders count as "missing"; used in a formula counts as handled
    missing = [ph for ph in missing if ph in run["mapping"] and ph not in used_in_calc]
    st.session_state.memory.add_turn(run["masked"], answer)
    run["chat_originals"] = {orig: type_of(ph) for ph, orig in chat_mapping.items()}
    run["calc_steps"] = calc_steps
    run.update(status="sent", answer_masked=answer, answer=restored, missing=missing)
    log_event(run, "approved_and_sent" if approved else "sent", mode)


def render(run: dict, mode: str) -> None:
    color, label = RISK_STYLE[run["risk"]]
    count = len(run["mapping"])
    ui.pipeline(run)
    ui.summary(run)
    for note in run.get("notes", []):
        st.warning(note)

    originals = {orig: type_of(ph) for ph, orig in run["mapping"].items()}
    placeholders = {ph: type_of(ph) for ph in run["mapping"]}

    left, right = st.columns(2, gap="large")
    with left:
        ui.label("What you typed")
        st.html(highlighted(run["original"], originals))
        if run["image"]:
            with st.expander("Screenshot (read on this machine)"):
                st.image(run["image"])
    with right:
        if run["status"] == "pending":
            ui.label("What the cloud will receive")
            st.html(highlighted(run["masked"], placeholders))
        elif run["status"] == "cancelled":
            ui.label("What the cloud received")
            st.info("Nothing. You cancelled before sending.")
        else:
            ui.label("What the cloud received")
            st.html(highlighted(run["masked"], placeholders))

    if count:
        st.html(legend(set(placeholders.values())))
        reasons = {loose(f.get("text")): f.get("reason", "") for f in run["findings"]}
        rows = [
            {"placeholder": ph, "type": type_of(ph), "original": orig, "why": reasons.get(loose(orig), "")}
            for ph, orig in run["mapping"].items()
        ]
        with st.expander(f"Why these were masked ({count})"):
            st.dataframe(rows, hide_index=True)
    else:
        st.caption("Nothing sensitive found, so the text goes out unchanged.")

    if run["status"] == "pending":
        if run["risk"] == "high":
            st.error("High risk. Only the text on the right will leave this machine. Check it before you approve.")
        if run["unmatched"]:
            st.warning(
                "The inspector flagged text it could not point to in your prompt, so it was not masked. "
                "Check the right-hand side for it: "
                + ", ".join(f"{f.get('text')} ({f.get('type', 'OTHER')})" for f in run["unmatched"])
            )
        approve, cancel, _ = st.columns([1, 1, 4])
        if approve.button("Approve and send", type="primary"):
            send(run, mode, approved=True)
            st.rerun()
        if cancel.button("Cancel"):
            run["status"] = "cancelled"
            log_event(run, "cancelled", mode)
            st.rerun()
        return

    if run["status"] == "error":
        st.error(f"The cloud call failed: {run['error']}")
    elif run["status"] == "sent":
        if run.get("cloud_note"):
            st.info(run["cloud_note"])
        if run.get("calc_steps"):
            st.html(ui.calc_box(run["calc_steps"]))
        ui.banner(f"The cloud model only saw {count} placeholder{'s' if count != 1 else ''}. The real values were put back here, on this laptop.")
        ui.label("Answer", "Real values were put back on this laptop.")
        if run["missing"]:
            st.warning(
                "The cloud answer left out these placeholders, so their originals are missing from it: "
                + ", ".join(run["missing"])
            )
        st.html(readable(highlighted(run["answer"].strip(), run.get("chat_originals", originals))))


st.set_page_config(page_title="SafePaste", page_icon="🛡️", layout="wide")
ui.inject_css()

def warm_up_local_gemma(model: str) -> None:
    """Load the local model into memory now, so the first real check is fast (Ollama preload: empty prompt)."""
    if not model:
        return
    body = json.dumps({"model": model, "prompt": "", "keep_alive": "30m"}).encode("utf-8")
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434") + "/api/generate"
    try:
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=60).read()
    except Exception:
        pass  # the sidebar status light will show the problem


loader_slot = None
if st.session_state.get("opening"):
    loader_slot = st.empty()
    with loader_slot.container():
        ui.loader_page("Starting SafePaste", [
            "Waking up Gemma 4 on this laptop",
            "Loading your company policy",
            "Nothing has left this laptop yet",
        ])
    started = time.perf_counter()
    warm_up_local_gemma(os.environ.get("SAFEPASTE_MODEL", ""))
    time.sleep(max(0.0, 1.8 - (time.perf_counter() - started)))  # keep the transition readable, never shorter
    st.session_state.opening = False
    st.session_state.entered = True
    # No st.rerun() here: the main page renders under the loader in this same run and replaces the
    # landing page, so the old landing content never flashes on screen.

if not st.session_state.get("entered"):
    ui.landing_top()
    left, _ = st.columns([1, 3])
    left.button("Open SafePaste", type="primary", use_container_width=True,
                on_click=lambda: st.session_state.update(opening=True))
    ui.landing_rest()
    st.html('<div class="lp-foot">Hacktoberfest Hack Day Bengaluru \'26 · open source (Apache-2.0) · all demo data is synthetic</div>')
    st.stop()

with st.sidebar:
    st.header("Settings")
    mode = st.radio("Cloud AI", ["gemma-cloud", "mock"],
                    help="gemma-cloud = Gemma 4 on the Gemini API (sees only placeholders). mock never calls the network.")
    ui.gap()
    ui.label("What to hide", "Untick a kind to let it through, for example money amounts when you need sums.")
    chosen = st.pills("Hide", list(HIDE_CHOICES), selection_mode="multi", default=list(HIDE_CHOICES),
                      label_visibility="collapsed") or []
    st.session_state["hide_types"] = [HIDE_CHOICES[c] for c in chosen]

head_left, head_mem, head_right = st.columns([5, 0.42, 1.25], vertical_alignment="top")
with head_left:
    ui.hero()
with head_mem:
    memory_slot = st.empty()  # the memory circle is drawn at the end of the run, so its count is current
with head_right:
    with st.container(key="back"):
        st.button("← Back to start", use_container_width=True,
                  on_click=lambda: st.session_state.update(entered=False))
st.html('<div style="border-bottom:1px solid #D9CDB1;margin:18px 0 28px"></div>')

if "memory" not in st.session_state:
    st.session_state.memory = memory.SessionMemory()
    try:
        db.start_session(st.session_state.memory.id)
    except Exception:
        pass  # the database is a log, never a reason to block the user


def new_chat() -> None:
    """Forget this chat completely: masked history and the placeholder map go, the log keeps counts only."""
    old = st.session_state.get("memory")
    if old is not None:
        try:
            db.end_session(old.id)
        except Exception:
            pass
    st.session_state.memory = memory.SessionMemory()
    try:
        db.start_session(st.session_state.memory.id)
    except Exception:
        pass
    st.session_state.pop("run", None)
    st.session_state["prompt"] = ""


if "policy_text" not in st.session_state:
    st.session_state["policy_text"] = file_policy()

policy_col, compose_col = st.columns([1, 1.55], gap="large")

with policy_col:
    ui.label("Company policy", "Written in plain English. Gemma reads it on this laptop before anything is sent. "
             "Edit it here, for example add a new codename, and the next check uses it.", step="01")
    st.file_uploader("Or upload the policy as a PDF", type=["pdf", "txt", "md"], key="policy_file",
                     on_change=load_policy_file)
    if st.session_state.get("policy_msg"):
        st.caption(st.session_state["policy_msg"])
    st.text_area("Company policy", key="policy_text", height=330, label_visibility="collapsed")
    st.button("Reset to policy.md", use_container_width=True,
              on_click=lambda: st.session_state.update(policy_text=file_policy()))

with compose_col:
  ui.label("Your message", "Write what you'd paste into an AI tool, or start from an example.", step="02")
  ui.mini("Try an example")
  names = list(EXAMPLES)
  row1, row2 = st.columns(3), st.columns(3)
  for col, name in zip(list(row1) + list(row2), names):
      col.button(name, on_click=use_example, args=(name,), use_container_width=True)
  row2[2].button("New chat", use_container_width=True, on_click=new_chat)
  memory_note = st.empty()  # filled at the end of the run, so the count includes the message just sent

  with st.form("compose"):
      text = st.text_area(
          "Your prompt",
          key="prompt",
          height=160,
          placeholder="e.g. Rewrite this for the board: Acme Corp grew 20% to ₹4.2 Cr in Q3…",
      )
      image = st.file_uploader("Screenshot (optional)", type=["png", "jpg", "jpeg", "webp"])
      submitted = st.form_submit_button("Check and send", type="primary")

if submitted:
    if not text.strip() and image is None:
        st.warning("Type a prompt or attach a screenshot first.")
    else:
        try:
            new_run = prepare(text, image)
        except Exception as exc:  # inspection failed: fail closed, send nothing
            st.session_state.pop("run", None)
            st.error(f"Local inspection failed, so nothing was sent. {exc}")
        else:
            if new_run is None:
                st.session_state.pop("run", None)
                st.warning("No text found in the screenshot, so nothing was sent.")
            else:
                st.session_state.run = new_run
                if not new_run["needs_approval"]:
                    send(new_run, mode, approved=False)

if st.session_state.get("run"):
    st.html('<div style="height:28px;border-bottom:1px solid #D9CDB1;margin-bottom:22px"></div>')
    render(st.session_state.run, mode)

turns = len(st.session_state.memory.turns)
if turns:
    memory_note.html(f'<div class="sp-note">This chat remembers {turns} earlier message{"s" if turns != 1 else ""}, '
                     'kept as placeholders in memory only. New chat forgets it.</div>')

def memory_panel() -> None:
    """The circle at the top right: what this chat remembers (RAM only) and what the database holds (counts only)."""
    mem = st.session_state.memory
    with memory_slot.container(key="memdot"):
        with st.popover(str(len(mem.turns)), help="Memory: what this chat remembers"):
            st.html('<div class="sp-h" style="font-size:1.3rem">Memory</div>'
                    '<div class="sp-note">Kept in this laptop\'s memory only, as placeholders. Real values are '
                    'shown here because you are on the laptop. New chat forgets all of it.</div>')
            if not mem.turns:
                st.caption("Nothing yet. Send a message and it shows up here.")
            for i, (user, answer) in enumerate(mem.turns, 1):
                you, _ = mask.restore(user, mem.mapping)
                reply, _ = mask.restore(answer, mem.mapping)
                short = lambda t: html.escape(t if len(t) <= 220 else t[:220] + "…")
                st.html(f'<div class="mem-turn"><div class="mem-no">{i:02d}</div><div><div class="mem-you">{short(you)}</div>'
                        f'<div class="mem-ai">{short(reply)}</div></div></div>')
            if mem.mapping:
                ui.mini("Hidden values in this chat")
                rows = "".join(f'<tr><td class="mem-ph">{html.escape(ph)}</td><td>{html.escape(orig)}</td></tr>'
                               for ph, orig in mem.mapping.items())
                st.html(f'<table class="mem-map">{rows}</table>')
            try:
                totals = db.stats()
                ui.mini("Saved on this laptop (database)")
                st.caption(f"{totals['sessions']} chats · {totals['events']} messages logged · "
                           f"{totals['items_masked']} items hidden. Counts only, never text.")
            except Exception:
                pass
            st.button("New chat (forget this)", on_click=new_chat, use_container_width=True, key="mem_new")


memory_panel()
ui.footer()

if loader_slot is not None:
    loader_slot.empty()  # the main page is fully drawn underneath, so lift the loader now

