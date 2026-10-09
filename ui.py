"""SafePaste visual layer. Owner: Person 3.

Design rules we follow on purpose: warm paper tones (no pure white), two accent tones only
(sage = safe/local, terracotta = secret/warning) plus brown for labels, no gradients, no shadows,
no emojis or icon packs, no card grids, no hover effects, serif headings with a plain sans body.
Pure HTML/CSS, no JavaScript and no extra packages.
"""
import html
from pathlib import Path

import streamlit as st

BG, SURFACE, INK, MUTED, LINE = "#F5EEDC", "#EEE5CF", "#2F2C22", "#6C6553", "#D9CDB1"
OLIVE, OLIVE_DARK, OLIVE_SOFT = "#66733A", "#535E2E", "#DFE3C5"
SAGE, SAGE_SOFT = OLIVE, OLIVE_SOFT            # "safe / on laptop" tone
CLAY, CLAY_SOFT = "#A0583C", "#E9D2C4"          # warnings only
BROWN, BROWN_SOFT = "#8A6A47", "#E6D3BA"        # labels + secret highlights
OCHRE = "#A7782A"
PREVIEW = Path(__file__).parent / "demo_assets" / "product_preview.png"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,500;6..72,600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
html, body, .stApp, .stMarkdown, p, label, li, button, textarea, input {{ font-family:'IBM Plex Sans',sans-serif !important; }}
.stApp {{ background:{BG}; color:{INK}; }}
.block-container {{ padding-top:3rem; max-width:1140px; }}
h1, h2, h3 {{ font-family:'Newsreader',Georgia,serif !important; font-weight:600 !important; color:{INK}; letter-spacing:-.005em; }}
[data-testid="stSidebar"] {{ background:#ECE2CA; border-right:1px solid {LINE}; }}
header[data-testid="stHeader"] {{ background:{BG}; }}
[data-testid="stButtonGroup"], [data-testid="stButtonGroup"] > div {{ flex-wrap:wrap !important; overflow:visible !important; }}
[data-testid="stAlert"] > div, div[role="alert"] {{ background:{BROWN_SOFT} !important; color:{INK} !important; border:1px solid {LINE}; border-radius:6px; }}
[data-testid="stButtonGroup"] button[aria-checked="true"], [data-testid="stButtonGroup"] button[kind="pillsActive"], [data-testid="stMultiSelect"] span[data-baseweb="tag"] {{ background:{OLIVE_SOFT} !important; color:{OLIVE_DARK} !important; }}
[data-baseweb="select"] > div {{ background:{SURFACE} !important; border-color:{LINE} !important; }}
textarea {{ background:{SURFACE} !important; border:1px solid {LINE} !important; border-radius:6px !important; box-shadow:none !important; }}
[data-testid="stForm"] {{ border:1px solid {LINE}; border-radius:8px; background:{SURFACE}; }}
div.stButton > button, div.stFormSubmitButton > button {{ border-radius:6px; border:1px solid {LINE}; background:{SURFACE};
  color:{INK}; font-weight:500; box-shadow:none; transition:none; }}
button[kind="primary"], button[kind="primaryFormSubmit"],
button[data-testid="stBaseButton-primary"], button[data-testid="stBaseButton-primaryFormSubmit"] {{
  background:{OLIVE} !important; border:1px solid {OLIVE} !important; color:{BG} !important; font-weight:600 !important; }}
button[kind="primary"] p, button[kind="primaryFormSubmit"] p, button[data-testid="stBaseButton-primaryFormSubmit"] p, button[data-testid="stBaseButton-primary"] p {{ color:{BG} !important; font-weight:600 !important; }}
button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover, button[data-testid="stBaseButton-primaryFormSubmit"]:hover {{ background:{OLIVE_DARK} !important; border-color:{OLIVE_DARK} !important; }}
[data-testid="stExpander"] details {{ border:1px solid {LINE}; border-radius:6px; background:{SURFACE}; }}

/* hide Streamlit's own chrome so it reads as a product */
[data-testid="stAppDeployButton"], [data-testid="stMainMenu"], .stDeployButton, [data-testid="stHeaderActionElements"],
[data-testid="stDecoration"] {{ display:none !important; }}
[data-testid="stWidgetLabel"] p {{ font-weight:600 !important; font-size:.9rem !important; color:{INK} !important; }}
[data-testid="stTabs"] button[aria-selected="true"] p {{ color:{OLIVE_DARK} !important; font-weight:600 !important; }}
[data-testid="stTabs"] [data-baseweb="tab-highlight"] {{ background:{OLIVE_DARK} !important; }}
div.stButton > button[kind="secondary"]:hover {{ border-color:{OLIVE} !important; color:{OLIVE_DARK} !important; background:{OLIVE_SOFT} !important; }}

/* header: wordmark left, back button right, context chips underneath */
.sp-head {{ padding-top:2px; }}
.sp-kicker {{ font-family:'IBM Plex Mono',monospace; font-size:.72rem; letter-spacing:.14em; text-transform:uppercase; color:{OLIVE}; margin-bottom:8px; }}
.sp-title {{ font-family:'Newsreader',serif; font-size:2.5rem; font-weight:600; line-height:1; color:{INK}; }}
.sp-sub {{ color:{MUTED}; font-size:.95rem; margin-top:10px; }}
.st-key-back div.stButton > button {{ background:{OLIVE_DARK} !important; border:1px solid {OLIVE_DARK} !important; color:{BG} !important;
  font-weight:600 !important; border-radius:6px !important; padding:.55rem 1rem !important; }}
.st-key-back button p {{ color:{BG} !important; font-weight:600 !important; }}
.st-key-back div.stButton > button:hover {{ background:#434C24 !important; border-color:#434C24 !important; }}
.sp-strip {{ display:flex; flex-wrap:wrap; gap:8px; padding:14px 0 18px; margin-bottom:26px; border-bottom:1px solid {LINE}; }}
.sp-chip {{ display:inline-flex; align-items:center; gap:8px; font-size:.8rem; padding:5px 11px; border-radius:999px;
  border:1px solid {LINE}; background:{SURFACE}; color:{MUTED}; }}
.sp-chip b {{ color:{INK}; font-weight:600; }}
.sp-chip.ok {{ background:{OLIVE_SOFT}; border-color:#C9CFA6; color:{OLIVE_DARK}; }}
.sp-chip.ok b {{ color:{OLIVE_DARK}; }}
.sp-chip.warn {{ background:{CLAY_SOFT}; border-color:#DDBCA9; color:{CLAY}; }}
.sp-chip .dot {{ width:7px; height:7px; border-radius:50%; background:currentColor; }}

/* section headings: numbered, serif, clearly bigger than the help text */
.sp-sec {{ display:flex; align-items:baseline; gap:12px; margin:4px 0 2px; }}
.sp-num {{ font-family:'IBM Plex Mono',monospace; font-size:.8rem; font-weight:500; color:{BG}; background:{OLIVE};
  border-radius:4px; padding:1px 6px; position:relative; top:-3px; }}
.sp-h {{ font-family:'Newsreader',serif; font-size:1.55rem; font-weight:600; line-height:1.2; color:{INK}; }}
.sp-note {{ font-size:.84rem; color:{MUTED}; margin:4px 0 14px; line-height:1.55; max-width:60ch; }}
.sp-mini {{ font-size:.72rem; font-weight:600; letter-spacing:.12em; text-transform:uppercase; color:{BROWN}; margin:0 0 8px; }}
.sp-label {{ font-size:.72rem; font-weight:600; letter-spacing:.1em; text-transform:uppercase; color:{BROWN}; margin:2px 0 6px; }}
.sp-gap {{ height:22px; }}
/* memory circle (top right) and its panel */
.st-key-memdot button {{ width:44px !important; height:44px !important; min-height:44px !important; border-radius:50% !important;
  padding:0 !important; background:{OLIVE_SOFT} !important; border:1.5px solid {OLIVE} !important; display:flex; justify-content:center; }}
.st-key-memdot button p {{ font-family:'IBM Plex Mono',monospace !important; font-weight:600 !important; color:{OLIVE_DARK} !important; font-size:.95rem !important; }}
.st-key-memdot button [data-testid="stIconMaterial"], .st-key-memdot button svg {{ display:none !important; }}
[data-testid="stPopoverBody"] {{ min-width:460px; max-width:560px; background:{BG} !important; border:1px solid {LINE} !important; }}
.mem-turn {{ display:flex; gap:12px; padding:10px 0; border-top:1px solid {LINE}; font-size:.85rem; line-height:1.5; }}
.mem-no {{ font-family:'IBM Plex Mono',monospace; color:{OLIVE}; font-size:.75rem; padding-top:2px; }}
.mem-you {{ color:{INK}; font-weight:500; }}
.mem-ai {{ color:{MUTED}; margin-top:4px; }}
.mem-map {{ width:100%; border-collapse:collapse; font-size:.82rem; margin-bottom:6px; }}
.mem-map td {{ padding:5px 6px; border-top:1px solid {LINE}; }}
.mem-ph {{ font-family:'IBM Plex Mono',monospace; color:{OLIVE_DARK}; background:{OLIVE_SOFT}; width:40%; }}
.sp-foot {{ margin-top:48px; padding-top:14px; border-top:1px solid {LINE}; font-size:.78rem; color:{MUTED};
  display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px; }}
.sp-status {{ font-size:.86rem; padding:8px 0 10px; border-bottom:1px solid {LINE}; margin-bottom:10px; }}
.sp-status .dot {{ display:inline-block; width:7px; height:7px; border-radius:50%; margin-right:8px; vertical-align:middle; }}

/* pipeline: a plain numbered row */
.sp-pipe {{ display:flex; align-items:stretch; margin:6px 0 14px; border:1px solid {LINE}; border-radius:8px; background:{SURFACE}; overflow-x:auto; }}
.sp-step {{ flex:1 1 0; min-width:108px; padding:11px 13px; border-right:1px solid {LINE}; opacity:0; animation: sp-in .35s ease-out forwards; }}
.sp-step:last-child {{ border-right:0; }}
.sp-step .no {{ font-family:'IBM Plex Mono',monospace; font-size:.7rem; color:{MUTED}; }}
.sp-step .nm {{ font-family:'Newsreader',serif; font-weight:600; font-size:1.02rem; margin-top:1px; }}
.sp-step .dt {{ font-size:.76rem; color:{MUTED}; margin-top:1px; }}
.sp-step .wh {{ font-size:.68rem; margin-top:6px; color:{SAGE}; }}
.sp-step.cloud .wh {{ color:{BROWN}; }}
.sp-step.wait {{ background:#F4E9CF; }} .sp-step.wait .dt {{ color:{OCHRE}; font-weight:500; }}
.sp-step.skip {{ opacity:.45 !important; }}
.sp-wall {{ flex:0 0 22px; border-right:1px solid {LINE}; background: repeating-linear-gradient(180deg, {CLAY} 0 5px, transparent 5px 10px) center/1.5px 100% no-repeat; position:relative; }}
.sp-wall span {{ position:absolute; top:50%; left:50%; transform:translate(-50%,-50%) rotate(-90deg); font-size:.55rem; letter-spacing:.12em;
  color:{CLAY}; background:{SURFACE}; padding:0 4px; white-space:nowrap; font-weight:600; }}

/* one-line summary instead of stat tiles */
.sp-summary {{ font-size:.95rem; margin:0 0 18px; color:{INK}; }}
.sp-summary b {{ font-family:'Newsreader',serif; font-size:1.25rem; font-weight:600; }}
.sp-summary .sep {{ color:{LINE}; margin:0 10px; }}
.r-low {{ color:{SAGE}; }} .r-medium {{ color:{OCHRE}; }} .r-high {{ color:{CLAY}; }}

/* message panels read like a document */
.sp-doc {{ white-space:pre-wrap; overflow-wrap:anywhere; font-size:.95rem; line-height:1.75; padding:14px 16px; min-height:8rem;
  border:1px solid {LINE}; border-radius:8px; background:{SURFACE}; }}
mark.sp-mark {{ padding:0 3px; border-radius:3px; color:inherit; }}
mark.sp-mark.secret {{ background:{BROWN_SOFT}; }}
mark.sp-mark.ph {{ background:{SAGE_SOFT}; font-family:'IBM Plex Mono',monospace; font-size:.86em; animation: sp-in .5s ease-out both; }}
.sp-legend {{ font-size:.8rem; color:{MUTED}; margin:8px 0 4px; }}
.sp-banner {{ margin:14px 0 6px; padding:11px 14px; border-radius:6px; font-size:.9rem; background:{OLIVE_SOFT}; color:{OLIVE_DARK}; }}

/* local calculations */
.cb {{ border:1px solid {LINE}; border-radius:8px; background:{SURFACE}; padding:12px 16px; margin:14px 0 6px; }}
.cb-row {{ padding:7px 0; border-top:1px solid {LINE}; font-size:.92rem; }}
.cb-f {{ font-family:'IBM Plex Mono',monospace; font-size:.82rem; color:{MUTED}; }}
.cb-eq {{ margin:0 10px; color:{MUTED}; }}
.cb-row b {{ font-family:'Newsreader',serif; font-size:1.1rem; color:{SAGE}; }}

/* skeleton loader */
.sk {{ border:1px solid {LINE}; border-radius:8px; background:{SURFACE}; padding:14px 16px; margin:6px 0 14px; }}
.sk .bar {{ height:10px; border-radius:4px; margin:9px 0; background: linear-gradient(90deg, #E2D7BE 0%, #EEE6D2 50%, #E2D7BE 100%);
  background-size:200% 100%; animation: sk-move 1.3s linear infinite; }}
.sk .cap {{ font-size:.78rem; color:{MUTED}; }}
@media (max-width:760px) {{ .sp-meta {{ display:none; }} }}

/* hourglass flip loader (pure CSS) */
.hg {{ position:relative; width:34px; height:52px; animation: hg-flip 2.4s cubic-bezier(.7,0,.3,1) infinite; }}
.hg::before, .hg::after {{ content:""; position:absolute; left:0; width:34px; height:3px; background:{BROWN}; border-radius:2px; }}
.hg::before {{ top:0; }} .hg::after {{ bottom:0; }}
.hg .glass {{ position:absolute; inset:3px 2px; clip-path: polygon(0 0,100% 0,56% 50%,100% 100%,0 100%,44% 50%);
  background:{SURFACE}; border:0; overflow:hidden; }}
.hg .top, .hg .bot {{ position:absolute; left:0; right:0; background:{OLIVE}; }}
.hg .top {{ top:0; height:50%; transform-origin:bottom; animation: hg-top 2.4s linear infinite; }}
.hg .bot {{ bottom:0; height:50%; transform-origin:bottom; animation: hg-bot 2.4s linear infinite; }}
.hg .stream {{ position:absolute; left:50%; top:46%; width:2px; height:28%; margin-left:-1px; background:{OLIVE}; animation: hg-stream 2.4s linear infinite; }}
.hg.sm {{ width:18px; height:28px; }} .hg.sm::before, .hg.sm::after {{ width:18px; height:2px; }}
@keyframes hg-flip {{ 0%,78% {{ transform:rotate(0); }} 100% {{ transform:rotate(180deg); }} }}
@keyframes hg-top {{ 0% {{ transform:scaleY(1); }} 75%,100% {{ transform:scaleY(0); }} }}
@keyframes hg-bot {{ 0% {{ transform:scaleY(0); }} 75%,100% {{ transform:scaleY(1); }} }}
@keyframes hg-stream {{ 0%,74% {{ opacity:1; }} 76%,100% {{ opacity:0; }} }}
.ld {{ position:fixed; inset:0; z-index:999999; background:{BG}; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:26px; text-align:center; }}
.ld-t {{ font-family:'Newsreader',serif; font-size:1.7rem; font-weight:600; color:{INK}; }}
.ld-lines {{ position:relative; height:1.4em; width:420px; max-width:90vw; color:{MUTED}; font-size:.95rem; }}
.ld-lines span {{ position:absolute; left:0; right:0; opacity:0; animation: ld-cycle 4.5s infinite; }}
.ld-lines span:nth-child(2) {{ animation-delay:1.5s; }} .ld-lines span:nth-child(3) {{ animation-delay:3s; }}
@keyframes ld-cycle {{ 0% {{ opacity:0; transform:translateY(4px); }} 8%,30% {{ opacity:1; transform:none; }} 38%,100% {{ opacity:0; }} }}
.sk-head {{ display:flex; align-items:center; gap:12px; }}

@keyframes sp-in {{ from {{ opacity:0; }} to {{ opacity:1; }} }}
@keyframes sk-move {{ from {{ background-position:200% 0; }} to {{ background-position:0 0; }} }}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def hero() -> None:
    st.html("""
<div class="sp-head">
  <div class="sp-kicker">Privacy layer for cloud AI</div>
  <div class="sp-title">SafePaste</div>
  <div class="sp-sub">Gemma 4 checks your message on this laptop before any of it reaches the cloud.</div>
</div>""")


def context_strip(model: str, local_ok: bool, cloud_mode: str, has_key: bool) -> None:
    """One row of plain chips: what runs where, so nobody has to open the sidebar to know."""
    local_cls = "ok" if local_ok else "warn"
    local_txt = f"Local check <b>{html.escape(model or 'not set')}</b>" + ("" if local_ok else " · not reachable")
    if cloud_mode == "mock":
        cloud_cls, cloud_txt = "", "Cloud <b>mock answers</b> · offline"
    elif has_key:
        cloud_cls, cloud_txt = "ok", "Cloud <b>Gemma 4 on the Gemini API</b> · placeholders only"
    else:
        cloud_cls, cloud_txt = "warn", "Cloud <b>no API key</b> · mock answers will be used"
    st.html(f"""<div class="sp-strip">
<span class="sp-chip {local_cls}"><span class="dot"></span>{local_txt}</span>
<span class="sp-chip {cloud_cls}"><span class="dot"></span>{cloud_txt}</span>
<span class="sp-chip">Audit log <b>counts and a hash</b> · never raw text</span>
</div>""")


def label(text: str, note: str = "", step: str = "") -> None:
    num = f'<span class="sp-num">{html.escape(step)}</span>' if step else ""
    st.html(f'<div class="sp-sec">{num}<span class="sp-h">{html.escape(text)}</span></div>'
            + (f'<div class="sp-note">{html.escape(note)}</div>' if note else ""))


def mini(text: str) -> None:
    st.html(f'<div class="sp-mini">{html.escape(text)}</div>')


def gap() -> None:
    st.html('<div class="sp-gap"></div>')


def footer() -> None:
    st.html('<div class="sp-foot"><span>SafePaste · open source, Apache-2.0</span>'
            '<span>Secrets stay on this laptop. The cloud sees placeholders only.</span></div>')


def status_line(ok: bool, text: str) -> None:
    color = SAGE if ok else CLAY
    st.html(f'<div class="sp-status"><span class="dot" style="background:{color}"></span>{html.escape(text)}</div>')


HOURGLASS = '<div class="hg"><div class="glass"><div class="top"></div><div class="stream"></div><div class="bot"></div></div></div>'


def loader_page(title: str, lines: list) -> None:
    """Full-page transition: hourglass flip plus three status lines that take turns."""
    st.markdown("<style>[data-testid='stSidebar'],[data-testid='stSidebarCollapsedControl']{display:none !important;}</style>",
                unsafe_allow_html=True)
    spans = "".join(f"<span>{html.escape(l)}</span>" for l in lines[:3])
    st.html(f'<div class="ld">{HOURGLASS}<div class="ld-t">{html.escape(title)}</div><div class="ld-lines">{spans}</div></div>')


def skeleton() -> None:
    st.html('<div class="sk"><div class="sk-head">' + HOURGLASS.replace('class="hg"', 'class="hg sm"') +
            '<div class="cap">Gemma 4 is reading your message on this laptop</div></div>'
            '<div class="bar" style="width:92%"></div><div class="bar" style="width:78%"></div>'
            '<div class="bar" style="width:85%"></div><div class="bar" style="width:40%"></div></div>')


def _ms(seconds) -> str:
    return f", {seconds:.1f}s" if isinstance(seconds, (int, float)) else ""


def pipeline(run: dict) -> None:
    t = run.get("timings", {})
    n = len(run.get("mapping", {}))
    status = run.get("status")
    approve = "skip" if not run.get("needs_approval") else ("wait" if status == "pending" else "done")
    sent = status == "sent"
    steps = [
        ("Read", ("screenshot and text" if run.get("image") else "text") + _ms(t.get("vision")), "local", "done"),
        ("Inspect", f'{len(run.get("findings", []))} found' + _ms(t.get("inspect")), "local", "done"),
        ("Swap", f"{n} placeholder{'s' if n != 1 else ''}", "local", "done"),
        ("Approve", {"skip": "not needed", "wait": "waiting for you",
                     "done": "cancelled" if status == "cancelled" else "approved"}[approve], "local", approve),
        None,
        ("Answer", ("cloud Gemma" + _ms(t.get("cloud"))) if sent else "not sent yet", "cloud", "done" if sent else "skip"),
        ("Restore", f"{n - len(run.get('missing', []))} of {n} put back" if sent else "not yet", "local", "done" if sent else "skip"),
    ]
    parts, no = [], 0
    for s in steps:
        if s is None:
            parts.append('<div class="sp-wall"><span>LAPTOP EDGE</span></div>')
            continue
        no += 1
        name, detail, where, state = s
        tag = "on this laptop" if where == "local" else "in the cloud"
        parts.append(f'<div class="sp-step {where} {state}" style="animation-delay:{no * .08:.2f}s">'
                     f'<div class="no">{no:02d}</div><div class="nm">{name}</div>'
                     f'<div class="dt">{html.escape(detail)}</div><div class="wh">{tag}</div></div>')
    st.html('<div class="sp-pipe">' + "".join(parts) + "</div>")


def summary(run: dict) -> None:
    n = len(run.get("mapping", {}))
    level = run.get("risk", "low")
    sent_secrets = "0" if not run.get("unmatched") else "check right panel"
    t = run.get("timings", {})
    local = sum(t.get(k, 0) for k in ("vision", "inspect") if isinstance(t.get(k), (int, float)))
    sep = '<span class="sep">/</span>'
    st.html(f'<div class="sp-summary"><b>{n}</b> item{"s" if n != 1 else ""} swapped{sep}'
            f'<b class="r-{level}">{level.capitalize()}</b> risk{sep}'
            f'<b class="r-low">{sent_secrets}</b> secrets sent to the cloud{sep}<b>{local:.1f}s</b> local check by Gemma on this laptop</div>')


def calc_box(steps: list) -> str:
    steps = [st_ for st_ in steps if st_.get("ok")]
    if not steps:
        return ""
    rows = "".join(
        f'<div class="cb-row"><span class="cb-f">{html.escape(st_["formula"])}</span>'
        f'<span class="cb-eq">=</span><b>{html.escape(st_["result"])}</b></div>' for st_ in steps)
    return ('<div class="cb"><div class="sp-label">Calculated on this laptop</div>'
            '<div class="sp-note">The cloud model wrote these formulas with placeholders. The real numbers were '
            'plugged in here, so the cloud never saw them.</div>' + rows + "</div>")


def banner(text: str) -> None:
    st.html(f'<div class="sp-banner">{html.escape(text)}</div>')


# ---------------------------------------------------------------- start page
LANDING_CSS = f"""
<style>
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], header[data-testid="stHeader"] {{ display:none !important; }}
.block-container {{ padding-top:3.6rem !important; max-width:980px; }}
.lp-kicker {{ font-size:.74rem; font-weight:600; letter-spacing:.14em; text-transform:uppercase; color:{BROWN}; }}
.lp-h1 {{ font-family:'Newsreader',Georgia,serif; font-size:clamp(2.4rem,5vw,3.8rem); font-weight:600; line-height:1.05;
  margin:14px 0 14px; max-width:760px; }}
.lp-h1 em {{ color:{SAGE}; }}
.lp-sub {{ max-width:620px; font-size:1.06rem; color:{MUTED}; line-height:1.6; margin-bottom:22px; }}
.lp-sentence {{ margin:36px 0 10px; padding:16px 0; border-top:1px solid {LINE}; border-bottom:1px solid {LINE}; font-size:1.12rem; line-height:1.9; }}
.lp-sentence .cap {{ display:block; font-size:.72rem; font-weight:600; letter-spacing:.12em; color:{BROWN}; margin-bottom:2px; }}
.flip {{ display:inline-grid; vertical-align:bottom; }}
.flip > b {{ grid-area:1/1; font-weight:500; padding:0 4px; border-radius:3px; }}
.flip .real {{ background:{BROWN_SOFT}; animation: lp-out 6s infinite; }}
.flip .ph {{ background:{SAGE_SOFT}; font-family:'IBM Plex Mono',monospace; font-size:.88em; opacity:0; animation: lp-in 6s infinite; }}
.flip.a > b {{ animation-delay:.3s; }} .flip.k > b {{ animation-delay:.6s; }}
.lp-steps {{ margin:30px 0 8px; }}
.lp-steps h3 {{ font-size:1.5rem; margin:0 0 10px; }}
.lp-row {{ display:flex; gap:18px; padding:14px 0; border-top:1px solid {LINE}; }}
.lp-row .n {{ font-family:'IBM Plex Mono',monospace; font-size:.8rem; color:{BROWN}; min-width:28px; padding-top:3px; }}
.lp-row .t {{ font-weight:600; }} .lp-row .s {{ color:{MUTED}; font-size:.93rem; line-height:1.55; margin-top:2px; max-width:700px; }}
.lp-cap {{ font-size:.82rem; color:{MUTED}; margin:8px 0 0; }}
.lp-foot {{ margin:30px 0 6px; font-size:.78rem; color:{MUTED}; }}
@keyframes lp-out {{ 0%,35% {{ opacity:1; }} 45%,90% {{ opacity:0; }} 100% {{ opacity:1; }} }}
@keyframes lp-in  {{ 0%,35% {{ opacity:0; }} 45%,90% {{ opacity:1; }} 100% {{ opacity:0; }} }}
</style>
"""

LANDING_TOP = """
<div class="lp-kicker">SafePaste, private AI use at work</div>
<div class="lp-h1">Use AI at work.<br><em>Keep the secrets at home.</em></div>
<div class="lp-sub">A small Gemma 4 model on your laptop reads what you are about to send, swaps client names,
  deal values and codenames for placeholders, and puts them back in the answer. The cloud model only ever sees the placeholders.</div>"""

LANDING_SENTENCE = """
<div class="lp-sentence"><span class="cap">What you type, and what the cloud receives</span>
  Summarize Q3: <span class="flip"><b class="real">Acme Corp</b><b class="ph">⟦CLIENT_1⟧</b></span> renewed at
  <span class="flip a"><b class="real">₹4.2 Cr</b><b class="ph">⟦AMOUNT_1⟧</b></span>, and
  <span class="flip k"><b class="real">Project Falcon</b><b class="ph">⟦CODENAME_1⟧</b></span> slips to December.</div>"""

LANDING_STEPS = """
<div class="lp-steps"><h3>How it works</h3>
  <div class="lp-row"><div class="n">01</div><div><div class="t">You write the policy in plain English.</div>
    <div class="s">"Never send client names, deal values or the Project Falcon codename." Gemma reads this memo, so it catches company-specific secrets that fixed patterns would miss.</div></div></div>
  <div class="lp-row"><div class="n">02</div><div><div class="t">Gemma checks your message on the laptop.</div>
    <div class="s">Text and screenshots are read locally. Keys, emails and phone numbers are caught by simple rules as a backup.</div></div></div>
  <div class="lp-row"><div class="n">03</div><div><div class="t">Secrets become placeholders, and risky sends wait for you.</div>
    <div class="s">Credentials, code or several secrets at once need your approval. You see exactly what will leave before it does.</div></div></div>
  <div class="lp-row"><div class="n">04</div><div><div class="t">The answer comes back with the real names restored.</div>
    <div class="s">The security team gets a log of what was caught, stored as types, counts and a hash. The raw text is never written down.</div></div></div>
</div>"""


def landing_top() -> None:
    st.markdown(LANDING_CSS, unsafe_allow_html=True)
    st.html(LANDING_TOP)


def landing_rest() -> None:
    st.html(LANDING_SENTENCE)
    if PREVIEW.exists():
        st.image(str(PREVIEW), use_container_width=True)
        st.html('<div class="lp-cap">The actual app after a check. All names and numbers are synthetic.</div>')
    st.html(LANDING_STEPS)
