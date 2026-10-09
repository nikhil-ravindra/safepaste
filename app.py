# app.py — own"""SafePaste: inspect and mask on this machine, send only the masked text, restore the answer locally.

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
import mask

HERE = Path(__file__).parent
DEFAULT_POLICY = (
    "Treat as sensitive: client and company names, money amounts, internal codenames, "
    "people's names and emails, credentials and secrets, and proprietary source code."
)
RISK_STYLE = {
    "low": ("#15803d", "Low risk"),
    "medium": ("#b45309", "Medium risk"),
    "high": ("#b91c1c", "High risk"),
}
TYPE_COLOR = {
    "CLIENT": "rgba(59,130,246,.28)",
    "AMOUNT": "rgba(34,197,94,.28)",
    "CODENAME": "rgba(168,85,247,.28)",
    "PERSON": "rgba(249,115,22,.30)",
    "CREDENTIAL": "rgba(239,68,68,.32)",
    "CODE": "rgba(100,116,139,.32)",
    "OTHER": "rgba(234,179,8,.32)",
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


def load_policy() -> str:
    path = HERE / "policy.md"
    return path.read_text(encoding="utf-8") if path.exists() else DEFAULT_POLICY


def type_of(placeholder: str) -> str:
    return placeholder.strip("⟦⟧").rsplit("_", 1)[0]


def loose(text) -> str:
    """Case- and spacing-insensitive key, matching how mask() falls back."""
    return " ".join(str(text).split()).lower()


def highlighted(text: str, spans: dict) -> str:
    """Escaped HTML of text with every key of spans marked in the colour of its type."""
    parts, last = [], 0
    if spans:
        pattern = re.compile("|".join(re.escape(s) for s in sorted(spans, key=len, reverse=True)))
        for match in pattern.finditer(text):
            kind = spans[match.group(0)]
            parts.append(html.escape(text[last : match.start()]))
            parts.append(
                f'<mark title="{kind}" style="background:{TYPE_COLOR.get(kind, TYPE_COLOR["OTHER"])};'
                f'color:inherit;padding:0 2px;border-radius:3px">{html.escape(match.group(0))}</mark>'
            )
            last = match.end()
    parts.append(html.escape(text[last:]))
    return (
        '<div style="white-space:pre-wrap;overflow-wrap:anywhere;font-family:ui-monospace,Menlo,monospace;'
        "font-size:.88rem;line-height:1.6;padding:.85rem 1rem;border:1px solid rgba(128,128,128,.35);"
        'border-radius:.5rem;min-height:8rem">' + "".join(parts) + "</div>"
    )


def legend(kinds) -> str:
    chips = "".join(
        f'<span style="background:{TYPE_COLOR.get(k, TYPE_COLOR["OTHER"])};padding:1px 7px;'
        f'border-radius:3px;margin-right:6px;font-size:.75rem;font-family:ui-monospace,Menlo,monospace">{k}</span>'
        for k in sorted(kinds)
    )
    return f"<div>{chips}</div>"


def prepare(text: str, image):
    """Everything that happens before anything leaves the machine. None if there is no text at all."""
    parts = [text.strip()] if text.strip() else []
    if image is not None:
        with st.spinner("Reading the screenshot on this machine…"):
            transcript = vision.transcribe(image.getvalue())
        if transcript and transcript.strip():
            parts.append(transcript.strip())
    original = "\n\n".join(parts)
    if not original:
        return None

    with st.spinner("Inspecting on this machine…"):
        findings = inspector.inspect(original, load_policy())
    level = str(risk.assess(findings, original)).strip().lower()
    if level not in RISK_STYLE:
        level = "high"  # an unexpected answer from the risk module fails closed
    masked, mapping = mask.mask(original, findings)
    missed = mask.unmatched(original, findings)

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


def send(run: dict, mode: str, approved: bool) -> None:
    try:
        with st.spinner("Asking the cloud with the masked text…"):
            answer = cloud.ask(run["masked"], mode=mode)
    except Exception as exc:  # report it; never fall back to sending anything else
        run.update(status="error", error=str(exc))
        log_event(run, "cloud_error", mode)
        return
    restored, missing = mask.restore(answer, run["mapping"])
    run.update(status="sent", answer_masked=answer, answer=restored, missing=missing)
    log_event(run, "approved_and_sent" if approved else "sent", mode)


def render(run: dict, mode: str) -> None:
    color, label = RISK_STYLE[run["risk"]]
    count = len(run["mapping"])
    st.html(
        f'<span style="background:{color};color:#fff;padding:3px 11px;border-radius:999px;'
        f'font-weight:600;font-size:.85rem">{label}</span>'
        f'<span style="margin-left:10px;opacity:.75">{count} item{"" if count == 1 else "s"} masked</span>'
    )

    originals = {orig: type_of(ph) for ph, orig in run["mapping"].items()}
    placeholders = {ph: type_of(ph) for ph in run["mapping"]}

    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("What you typed")
        st.html(highlighted(run["original"], originals))
        if run["image"]:
            with st.expander("Screenshot (read on this machine)"):
                st.image(run["image"])
    with right:
        if run["status"] == "pending":
            st.subheader("What the cloud will receive")
            st.html(highlighted(run["masked"], placeholders))
        elif run["status"] == "cancelled":
            st.subheader("What the cloud received")
            st.info("Nothing. You cancelled before sending.")
        else:
            st.subheader("What the cloud received")
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
        st.subheader("Answer")
        if run["missing"]:
            st.warning(
                "The cloud answer left out these placeholders, so their originals are missing from it: "
                + ", ".join(run["missing"])
            )
        restored_tab, formatted_tab, raw_tab = st.tabs(["Restored", "Formatted", "Raw from cloud"])
        with restored_tab:
            st.html(highlighted(run["answer"], originals))
        with formatted_tab:
            st.markdown(run["answer"].replace("$", r"\$"))
        with raw_tab:
            st.html(highlighted(run["answer_masked"], placeholders))

    latest = audit_log.tail(1)
    if latest:
        with st.expander("What was logged for this request"):
            st.caption("The sha256 is of the masked text. No raw text is ever written.")
            st.json(latest[0])


st.set_page_config(page_title="SafePaste", page_icon="🛡️", layout="wide")

with st.sidebar:
    st.header("Settings")
    mode = st.radio("Cloud mode", ["mock", "gemini"], help="mock never calls the network.")
    st.subheader("Modules")
    for name, (_, is_stub) in MODULES.items():
        st.markdown(f"`{name}.py` · {'stub' if is_stub else 'live'}")

st.title("SafePaste")
st.caption(
    "Sensitive details are found and masked on this machine. Only the masked version goes to the cloud, "
    "and the answer is restored here."
)

with st.form("compose"):
    text = st.text_area(
        "Your prompt",
        height=160,
        placeholder="e.g. Rewrite this for the board: Acme Corp grew 20% to $4.2M in Q3…",
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
    render(st.session_state.run, mode)

with st.sidebar:
    st.subheader("Audit log")
    st.caption("Types, counts, risk, action and a sha256. Never raw text.")
    entries = audit_log.tail(10)
    if entries:
        for entry in entries:
            masked_total = sum(entry.get("types", {}).values())
            st.caption(
                f"{entry.get('ts', '')[11:19]} · {entry.get('action', '?')} · "
                f"{entry.get('risk', '?')} · {masked_total} masked"
            )
        with st.expander("Raw entries"):
            st.json(entries)
    else:
        st.caption("No entries yet.")
er: Person 3
