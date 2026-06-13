"""
streamlit_app.py - Phase 7: Custom Agent Personas UI
"""

import json
import os
import requests
from datetime import datetime
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="Research Assistant",
    page_icon="Research",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Password Gate ─────────────────────────────────────────────────────────────
def _check_password() -> bool:
    """
    Returns True if the user has entered the correct password.
    Password is read from st.secrets["APP_PASSWORD"] (Streamlit Cloud)
    or the APP_PASSWORD environment variable (local / other hosts).
    """
    # Safely read from secrets (won't crash if secrets.toml doesn't exist)
    correct_pw = os.environ.get("APP_PASSWORD", "research2025")
    try:
        correct_pw = st.secrets.get("APP_PASSWORD", correct_pw)
    except Exception:
        pass  # no secrets.toml — fall back to env var or default

    if st.session_state.get("_authenticated"):
        return True

    # ── Login screen ──────────────────────────────────────────────────────────
    st.markdown("""
    <style>
    .login-wrap{display:flex;align-items:center;justify-content:center;
                min-height:80vh;}
    .login-box{background:#161b27;border:1px solid #1e2535;border-radius:12px;
               padding:2.5rem 2rem;width:100%;max-width:380px;text-align:center;}
    .login-title{font-family:'IBM Plex Mono',monospace;font-size:1.3rem;
                 font-weight:600;color:#e2e8f0;margin-bottom:.4rem;}
    .login-sub{font-size:.82rem;color:#64748b;margin-bottom:1.8rem;}
    </style>
    """, unsafe_allow_html=True)

    col_l, col_c, col_r = st.columns([1, 1.4, 1])
    with col_c:
        st.markdown("<div class='login-box'>", unsafe_allow_html=True)
        st.markdown("<div class='login-title'>Research Assistant</div>", unsafe_allow_html=True)
        st.markdown("<div class='login-sub'>Enter password to continue</div>", unsafe_allow_html=True)

        pw_input = st.text_input(
            "Password",
            type="password",
            placeholder="Enter password...",
            label_visibility="collapsed",
        )
        login_btn = st.button("Unlock", use_container_width=True)

        if login_btn or pw_input:
            if pw_input == correct_pw:
                st.session_state["_authenticated"] = True
                st.rerun()
            elif pw_input:
                st.markdown(
                    "<div style='color:#ef4444;font-size:.82rem;margin-top:.5rem;'>"
                    "Incorrect password. Try again.</div>",
                    unsafe_allow_html=True
                )
        st.markdown("</div>", unsafe_allow_html=True)
    return False

if not _check_password():
    st.stop()
# ── End Password Gate ─────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');
html,body,[class*="css"]{font-family:'IBM Plex Sans',sans-serif;}
.stApp{background-color:#0f1117;}
section[data-testid="stSidebar"]{background-color:#161b27;border-right:1px solid #1e2535;}
.ra-header{padding:1.5rem 0 1.2rem;border-bottom:1px solid #1e2535;margin-bottom:1.5rem;}
.ra-title{font-family:'IBM Plex Mono',monospace;font-size:1.5rem;font-weight:600;color:#e2e8f0;}
.ra-subtitle{font-size:0.82rem;color:#64748b;font-family:'IBM Plex Mono',monospace;margin-top:0.2rem;}
.stTextInput input{background-color:#161b27!important;border:1px solid #1e2535!important;color:#e2e8f0!important;border-radius:6px!important;font-size:0.95rem!important;padding:0.75rem 1rem!important;}
.stTextInput input:focus{border-color:#3b82f6!important;box-shadow:0 0 0 2px rgba(59,130,246,0.15)!important;}
.stButton>button{background:linear-gradient(135deg,#3b82f6,#2563eb)!important;color:white!important;border:none!important;border-radius:6px!important;font-weight:500!important;padding:0.6rem 1.2rem!important;width:100%!important;}
.stButton>button:hover{opacity:.88!important;}
.stDownloadButton>button{background:#1e2535!important;color:#e2e8f0!important;border:1px solid #334155!important;border-radius:6px!important;font-size:0.85rem!important;width:100%!important;}
.card{background:#161b27;border:1px solid #1e2535;border-radius:8px;padding:1.25rem 1.5rem;margin-bottom:1rem;}
.card-success{border-left:3px solid #22c55e;}
.card-error{border-left:3px solid #ef4444;}
.card-info{border-left:3px solid #3b82f6;}
.card-cache{border-left:3px solid #a855f7;}
.card-warning{border-left:3px solid #f59e0b;}

/* Persona cards */
.persona-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:0.6rem;margin-bottom:1.2rem;}
.persona-card{background:#161b27;border:1px solid #1e2535;border-radius:8px;padding:0.9rem 1rem;cursor:pointer;transition:all 0.15s;position:relative;}
.persona-card:hover{border-color:#334155;background:#1a2032;}
.persona-card.selected{border-color:var(--pc);background:#1a2032;box-shadow:0 0 0 1px var(--pc);}
.persona-icon{font-size:1.4rem;margin-bottom:0.4rem;}
.persona-name{font-size:0.82rem;font-weight:600;color:#e2e8f0;margin-bottom:0.2rem;}
.persona-desc{font-size:0.72rem;color:#64748b;line-height:1.4;}
.persona-badge{display:inline-block;padding:0.15rem 0.5rem;border-radius:3px;font-size:0.7rem;font-family:'IBM Plex Mono',monospace;font-weight:600;margin-right:0.3rem;}

.mem-badge{display:inline-block;padding:.2rem .6rem;border-radius:4px;font-size:.75rem;font-family:'IBM Plex Mono',monospace;font-weight:600;margin-right:.4rem;}
.badge-new{background:#1e3a5f;color:#60a5fa;}
.badge-cached{background:#2d1b69;color:#a78bfa;}
.badge-stale{background:#3d2100;color:#fbbf24;}
.badge-related{background:#1a3320;color:#4ade80;}
.chip{display:inline-block;background:#1e2535;color:#94a3b8;border-radius:4px;padding:.2rem .6rem;font-size:.75rem;font-family:'IBM Plex Mono',monospace;margin-right:.4rem;}
.export-box{background:#0f1117;border:1px solid #1e2535;border-radius:8px;padding:1rem 1.25rem;margin-top:.75rem;}
.export-title{color:#94a3b8;font-size:.75rem;font-family:'IBM Plex Mono',monospace;font-weight:600;margin-bottom:.75rem;letter-spacing:.05em;}
.hist-item{background:#161b27;border:1px solid #1e2535;border-radius:6px;padding:.75rem 1rem;margin-bottom:.5rem;font-size:.82rem;}
.hist-success{border-left:2px solid #22c55e;}
.hist-failed{border-left:2px solid #ef4444;}
.hist-topic{color:#e2e8f0;font-weight:500;margin-bottom:.2rem;}
.hist-meta{color:#64748b;font-family:'IBM Plex Mono',monospace;font-size:.72rem;}
.report-container{background:#161b27;border:1px solid #1e2535;border-radius:8px;padding:2.5rem;margin-top:1rem;line-height:1.8;}
.report-container h1{color:#e2e8f0;font-size:1.6rem;border-bottom:2px solid #2563eb;padding-bottom:.5rem;margin-bottom:1.2rem;}
.report-container h2{color:#93c5fd;font-size:1.2rem;margin-top:2rem;margin-bottom:.6rem;}
.report-container h3{color:#cbd5e1;font-size:1rem;margin-top:1.2rem;}
.report-container p{color:#94a3b8;line-height:1.8;margin-bottom:.8rem;}
.report-container li{color:#94a3b8;line-height:1.9;}
.report-container a{color:#3b82f6;}
.report-container hr{border-color:#1e2535;margin:1.5rem 0;}
.report-container strong{color:#cbd5e1;}
.report-container code{background:#1e2535;color:#7dd3fc;padding:.1rem .3rem;border-radius:3px;font-size:.85em;}
/* Chat section */
.chat-header{font-family:'IBM Plex Mono',monospace;font-size:.8rem;font-weight:600;
             color:#94a3b8;letter-spacing:.06em;margin:2rem 0 1rem;}
.chat-msg-user{background:#1e3a5f;border:1px solid #2563eb33;border-radius:8px 8px 2px 8px;
               padding:.75rem 1rem;margin-bottom:.6rem;color:#e2e8f0;font-size:.9rem;
               max-width:80%;margin-left:auto;}
.chat-msg-ai{background:#161b27;border:1px solid #1e2535;border-radius:8px 8px 8px 2px;
             padding:.75rem 1rem;margin-bottom:.6rem;color:#94a3b8;font-size:.9rem;
             max-width:88%;}
.chat-msg-ai strong{color:#cbd5e1;}
.chat-msg-ai a{color:#3b82f6;}
.chat-wrap{max-height:420px;overflow-y:auto;padding:.5rem 0;margin-bottom:.75rem;}
.chat-input-area{background:#161b27;border:1px solid #1e2535;border-radius:8px;padding:.75rem;}
</style>
""", unsafe_allow_html=True)

BASE_DIR     = Path(__file__).parent
HISTORY_FILE = BASE_DIR / "logs" / "history.json"

def load_history() -> list:
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, encoding="utf-8") as f:
            data = json.load(f)
            return list(reversed(data)) if isinstance(data, list) else []
    except Exception:
        return []

def validate_api_key() -> bool:
    return bool(os.environ.get("GROQ_API_KEY","").strip().strip('"').strip("'"))

def word_count(text: str) -> int:
    return len(text.split())

MEM_LABELS = {
    "new":     ("New research",       "badge-new"),
    "cached":  ("Served from cache",  "badge-cached"),
    "stale":   ("Refreshed (stale)",  "badge-stale"),
    "related": ("Used related context","badge-related"),
}

PERSONA_ICONS = {
    "general":   "Search",
    "medical":   "Medical",
    "financial": "Financial",
    "legal":     "Legal",
    "technical": "Technical",
    "policy":    "Policy",
}

PERSONA_COLORS = {
    "general":   "#3b82f6",
    "medical":   "#22c55e",
    "financial": "#f59e0b",
    "legal":     "#8b5cf6",
    "technical": "#06b6d4",
    "policy":    "#ef4444",
}

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("<div style='padding:1rem 0 .5rem;font-family:IBM Plex Mono,monospace;font-size:.9rem;color:#e2e8f0;font-weight:600;'>Configuration</div>", unsafe_allow_html=True)

    if validate_api_key():
        st.markdown("<div class='card card-success'><span style='color:#22c55e;font-size:.8rem;'>GROQ_API_KEY detected</span></div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='card card-error'><span style='color:#ef4444;font-size:.8rem;'>GROQ_API_KEY not set</span></div>", unsafe_allow_html=True)

    try:
        from memory import Memory
        mem_obj = Memory(str(HISTORY_FILE))
        stats   = mem_obj.get_stats()
        st.markdown("---")
        st.markdown("<div style='color:#64748b;font-size:.75rem;font-family:IBM Plex Mono,monospace;margin-bottom:.75rem;'>MEMORY STATS</div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1: st.metric("Total Runs", stats["total"])
        with c2: st.metric("Topics",     stats["unique_topics"])
    except Exception:
        pass

    st.markdown("---")
    st.markdown("<div style='color:#64748b;font-size:.75rem;font-family:IBM Plex Mono,monospace;margin-bottom:.75rem;'>RECENT RUNS</div>", unsafe_allow_html=True)

    history = load_history()
    if not history:
        st.markdown("<div style='color:#475569;font-size:.8rem;'>No runs yet.</div>", unsafe_allow_html=True)
    else:
        for run in history[:8]:
            status  = run.get("status","failed")
            src     = run.get("source","new")
            persona = run.get("persona","general")
            color   = PERSONA_COLORS.get(persona,"#3b82f6")
            exports = run.get("exports",{})
            fmt     = " ".join(k.upper() for k in exports if not k.endswith("_error") and k!="md")
            ts      = run.get("timestamp","")[:16].replace("T"," ")
            topic   = run.get("topic","")[:30]
            left_border = "#22c55e" if status == "success" else "#ef4444"
            src_color, src_text = {"cached":("#a78bfa","cached"),"refreshed":("#fbbf24","refreshed")}.get(src,("#94a3b8","new"))
            st.markdown(
                "<div style='background:#161b27;border:1px solid #1e2535;"
                "border-left:2px solid " + left_border + ";"
                "border-radius:6px;padding:.65rem .9rem;margin-bottom:.4rem;'>"
                "<div style='margin-bottom:.2rem;'>"
                "<span style='color:" + color + ";font-size:.68rem;font-weight:700;'>" + persona.upper() + "</span>"
                " <span style='font-size:.65rem;color:" + src_color + ";background:" + src_color + "18;"
                "border-radius:3px;padding:.05rem .35rem;'>" + src_text + "</span>"
                "</div>"
                "<div style='color:#e2e8f0;font-size:.8rem;font-weight:500;"
                "white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'>" + topic + "</div>"
                "<div style='color:#64748b;font-size:.7rem;font-family:IBM Plex Mono,monospace;margin-top:.15rem;'>"
                + ts + (" &nbsp;·&nbsp; " + fmt if fmt else "") + "</div>"
                "</div>",
                unsafe_allow_html=True
            )

# ── Main ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class='ra-header'>
    <div class='ra-title'>Research Assistant</div>
    <div class='ra-subtitle'>Phase 7 · Custom Personas · PDF · DOCX · Groq · LLaMA 3.3 70B</div>
</div>
""", unsafe_allow_html=True)

# ── Persona selector ──────────────────────────────────────────────────────────
st.markdown("<div style='color:#94a3b8;font-size:0.8rem;font-family:IBM Plex Mono,monospace;font-weight:600;margin-bottom:0.6rem;letter-spacing:0.05em;'>SELECT ANALYST PERSONA</div>", unsafe_allow_html=True)

try:
    from personas import list_personas
    all_personas = list_personas()
except Exception:
    all_personas = [{"key":"general","label":"General Researcher","description":"Balanced research.","color":"#3b82f6","icon":"Search"}]

if "selected_persona" not in st.session_state:
    st.session_state.selected_persona = "general"

# ── Persona grid — pure HTML so all cards are identical size ─────────────────
selected_now = st.session_state.selected_persona

# Build each card as a plain string — no f-string nesting issues
def _card(p, is_selected):
    bc  = p["color"] if is_selected else "#1e2535"
    bg  = "#1e2840"  if is_selected else "#161b27"
    shd = ("0 0 0 1.5px " + p["color"]) if is_selected else "none"
    dsc = p["description"][:52] + ("..." if len(p["description"]) > 52 else "")
    return (
        "<div style='background:" + bg + ";border:1.5px solid " + bc + ";"
        "border-radius:10px;padding:1rem;text-align:center;"
        "box-shadow:" + shd + ";display:flex;flex-direction:column;"
        "justify-content:flex-start;height:100%;'>"
        "<div style='font-size:0.75rem;font-weight:700;color:" + p["color"] + ";"
        "letter-spacing:0.06em;margin-bottom:0.4rem;text-transform:uppercase;'>"
        + p["icon"] + "</div>"
        "<div style='font-size:0.82rem;font-weight:600;color:#e2e8f0;margin-bottom:0.35rem;'>"
        + p["label"] + "</div>"
        "<div style='font-size:0.7rem;color:#64748b;line-height:1.45;flex:1;'>"
        + dsc + "</div>"
        "</div>"
    )

cards_html = "".join(_card(p, selected_now == p["key"]) for p in all_personas)
n = len(all_personas)
grid_html = (
    "<div style='display:grid;grid-template-columns:repeat(" + str(n) + ",1fr);"
    "gap:0.65rem;margin-bottom:0.5rem;align-items:stretch;'>"
    + cards_html +
    "</div>"
)
st.markdown(grid_html, unsafe_allow_html=True)

# One Select button per persona — rendered below the grid in matching columns
btn_cols = st.columns(len(all_personas))
for col, p in zip(btn_cols, all_personas):
    with col:
        if st.button("Select", key=f"persona_{p['key']}", use_container_width=True):
            st.session_state.selected_persona = p["key"]
            st.rerun()

selected_persona = st.session_state.selected_persona
persona_info     = next((p for p in all_personas if p["key"] == selected_persona), all_personas[0])

# Active persona banner
st.markdown(f"""
<div style='background:#161b27;border:1px solid {persona_info["color"]}33;
            border-left:3px solid {persona_info["color"]};border-radius:6px;
            padding:0.7rem 1rem;margin-bottom:1.2rem;'>
    <span style='color:{persona_info["color"]};font-weight:600;font-size:0.85rem;'>
        {persona_info["icon"]} {persona_info["label"]}
    </span>
    <span style='color:#64748b;font-size:0.82rem;margin-left:0.5rem;'>
        — {persona_info["description"]}
    </span>
</div>""", unsafe_allow_html=True)

# ── Topic input + buttons ─────────────────────────────────────────────────────
col1, col2, col3 = st.columns([3, 0.8, 0.8])
with col1:
    topic = st.text_input("topic", placeholder="e.g. CRISPR gene therapy clinical trials 2025",
                          label_visibility="collapsed")
with col2:
    run_btn   = st.button("Run",   disabled=not validate_api_key())
with col3:
    force_btn = st.button("Force", disabled=not validate_api_key(),
                          help="Bypass cache — run fresh research")

# Memory preview
if topic.strip():
    try:
        from memory import Memory
        _mem = Memory(str(HISTORY_FILE))
        chk  = _mem.check_topic(topic.strip())
        if chk["status"] == "exact":
            st.markdown(f"<div class='card card-cache'><span class='mem-badge badge-cached'>CACHED</span><span style='color:#c4b5fd;font-size:.85rem;'>Researched <strong>{chk['days_old']} days ago</strong>. Instant return. Use Force to refresh.</span></div>", unsafe_allow_html=True)
        elif chk["status"] == "stale":
            st.markdown(f"<div class='card card-warning'><span class='mem-badge badge-stale'>STALE</span><span style='color:#fcd34d;font-size:.85rem;'>Report is <strong>{chk['days_old']} days old</strong> — will refresh with prior context.</span></div>", unsafe_allow_html=True)
        elif chk["status"] == "related":
            rel = ", ".join(f"<em>{r['topic']}</em>" for r in chk["related"][:2])
            st.markdown(f"<div class='card card-info'><span class='mem-badge badge-related'>RELATED</span><span style='color:#93c5fd;font-size:.85rem;'>Related research: {rel}.</span></div>", unsafe_allow_html=True)
    except Exception:
        pass

# ── Execute ───────────────────────────────────────────────────────────────────
force = force_btn and not run_btn

# Persist last result in session state so chat survives reruns
if "last_result" not in st.session_state:
    st.session_state.last_result = None

if (run_btn or force_btn) and topic.strip():
    try:
        from research_crew import ResearchCrew
    except ImportError as e:
        st.error(f"Cannot import research_crew.py: {e}")
        st.stop()

    start = datetime.now()
    with st.spinner(f"[{persona_info['label']}] Researching '{topic}'... (2-4 min)"):
        result = ResearchCrew(topic.strip(), persona=selected_persona, force=force).run()

    elapsed    = (datetime.now() - start).seconds
    mem_status = result.get("memory_status","new")
    p_color    = PERSONA_COLORS.get(selected_persona,"#3b82f6")

    if result["status"] == "success":
        label, badge_cls = MEM_LABELS.get(mem_status,("Complete","badge-new"))
        wc = word_count(result["output"])

        st.markdown(f"""
        <div class='card card-success'>
            <span style='color:#22c55e;font-weight:600;'>Research complete</span>
            <span class='mem-badge {badge_cls}' style='margin-left:.5rem;'>{label}</span>
            <span style='background:{p_color}22;color:{p_color};' class='mem-badge'>
                {result.get("persona_label","General")}
            </span>
            <span style='float:right;'>
                <span class='chip'>{elapsed}s</span>
                <span class='chip'>{wc} words</span>
            </span>
        </div>""", unsafe_allow_html=True)

        # Downloads
        exports = result.get("exports",{})
        st.markdown("<div class='export-box'><div class='export-title'>DOWNLOAD REPORT</div>", unsafe_allow_html=True)
        dl1, dl2, dl3 = st.columns(3)
        with dl1:
            md_path = result.get("path")
            if md_path and os.path.exists(md_path):
                with open(md_path,"rb") as f:
                    st.download_button("Markdown", f,
                        file_name=os.path.basename(md_path), mime="text/markdown")
        with dl2:
            pdf_path = exports.get("pdf")
            if pdf_path and os.path.exists(pdf_path):
                with open(pdf_path,"rb") as f:
                    st.download_button("PDF", f,
                        file_name=os.path.basename(pdf_path), mime="application/pdf")
            elif "pdf_error" in exports:
                st.caption(f"PDF error: {exports['pdf_error'][:50]}")
        with dl3:
            docx_path = exports.get("docx")
            if docx_path and os.path.exists(docx_path):
                with open(docx_path,"rb") as f:
                    st.download_button("Word", f,
                        file_name=os.path.basename(docx_path),
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            elif "docx_error" in exports:
                st.caption(f"DOCX error: {exports['docx_error'][:50]}")
        st.markdown("</div>", unsafe_allow_html=True)

        # Related context expander
        mem_info = result.get("memory_info",{})
        if mem_status == "related" and mem_info.get("related"):
            with st.expander("Related research used as context"):
                for r in mem_info["related"]:
                    st.markdown(f"**{r['topic']}** — {r['days_old']}d ago · {int(r['similarity']*100)}% similar")

        # ── Report display ─────────────────────────────────────────────
        st.markdown("<div class='report-container'>", unsafe_allow_html=True)
        st.markdown(result["output"])
        st.markdown("</div>", unsafe_allow_html=True)

        # Save result to session state so chat persists across reruns
        st.session_state.last_result = result

    else:
        st.markdown(
            "<div class='card card-error'>"
            "<span style='color:#ef4444;font-weight:600;'>Research failed</span><br>"
            "<span style='color:#94a3b8;font-size:.85rem;'>" + result['output'] + "</span>"
            "</div>",
            unsafe_allow_html=True
        )

elif (run_btn or force_btn) and not topic.strip():
    st.markdown("<div class='card card-info'><span style='color:#3b82f6;'>Enter a research topic above.</span></div>", unsafe_allow_html=True)

else:
    if not st.session_state.get("last_result"):
        persona_list = " · ".join(
            "<span style='color:" + p['color'] + ";'>" + p['label'] + "</span>"
            for p in all_personas
        )
        st.markdown(
            "<div style='text-align:center;padding:3rem 2rem;'>"
            "<div style='font-size:2.5rem;margin-bottom:1rem;'>Research</div>"
            "<div style='color:#475569;font-size:.95rem;line-height:2.2;'>"
            "Select a persona, enter a topic, and click <strong style='color:#94a3b8;'>Run</strong>.<br>"
            + persona_list +
            "<br>Exports as <strong style='color:#94a3b8;'>Markdown · PDF · Word</strong> automatically."
            "</div></div>",
            unsafe_allow_html=True
        )

# ── Persistent Chat Section ────────────────────────────────────────────────────
# Shown whenever a result exists in session state, regardless of button state
if st.session_state.get("last_result") and st.session_state.last_result.get("status") == "success":
    _res        = st.session_state.last_result
    _report     = _res.get("output","")
    _chat_key   = "chat_" + _res.get("topic","").replace(" ","_")[:40]
    _api_key    = os.environ.get("GROQ_API_KEY","").strip().strip('"').strip("'")

    if _chat_key not in st.session_state:
        st.session_state[_chat_key] = []

    st.markdown("---")
    st.markdown(
        "<div style='font-family:IBM Plex Mono,monospace;font-size:.8rem;font-weight:600;"
        "color:#94a3b8;letter-spacing:.06em;margin-bottom:.5rem;'>CHAT WITH YOUR REPORT</div>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<div style='color:#64748b;font-size:.78rem;margin-bottom:1rem;'>"
        "Ask follow-up questions based on the research report above.</div>",
        unsafe_allow_html=True
    )

    # Render chat history using st.chat_message for reliability
    for _msg in st.session_state[_chat_key]:
        with st.chat_message(_msg["role"]):
            st.markdown(_msg["content"])

    # Suggestion chips
    _suggestions = [
        "Summarise the key findings",
        "What are the main risks?",
        "What should I do next?",
        "Explain this to a beginner",
    ]
    _clicked_sug = None
    _sug_cols = st.columns(len(_suggestions))
    for _sc, _sug in zip(_sug_cols, _suggestions):
        with _sc:
            if st.button(_sug, key="sug_" + _sug[:20] + _chat_key, use_container_width=True):
                _clicked_sug = _sug

    # Chat input using st.chat_input — persists correctly across reruns
    _user_input = st.chat_input("Ask anything about this report...")

    _question = _clicked_sug or (_user_input.strip() if _user_input else None)

    if _question:
        if not _api_key:
            st.error("GROQ_API_KEY not set.")
        else:
            # Show user message immediately
            with st.chat_message("user"):
                st.markdown(_question)

            # Build context-aware messages
            _system = (
                "You are a research assistant. The user has read the following research report. "
                "Answer their questions based on this report. "
                "If the answer is not in the report, say so and offer relevant general knowledge.\n\n"
                "=== RESEARCH REPORT ===\n"
                + _report[:6000]
                + "\n=== END OF REPORT ==="
            )
            _messages = [{"role": "system", "content": _system}]
            for _m in st.session_state[_chat_key][-12:]:
                _messages.append({"role": _m["role"], "content": _m["content"]})
            _messages.append({"role": "user", "content": _question})

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        _resp = requests.post(
                            "https://api.groq.com/openai/v1/chat/completions",
                            headers={
                                "Authorization": "Bearer " + _api_key,
                                "Content-Type": "application/json",
                            },
                            json={
                                "model": "llama-3.3-70b-versatile",
                                "messages": _messages,
                                "temperature": 0.4,
                                "max_tokens": 1024,
                            },
                            timeout=30,
                        )
                        _resp.raise_for_status()
                        _answer = _resp.json()["choices"][0]["message"]["content"]
                    except Exception as _exc:
                        _answer = "Sorry, I could not get a response: " + str(_exc)
                st.markdown(_answer)

            st.session_state[_chat_key].append({"role": "user",      "content": _question})
            st.session_state[_chat_key].append({"role": "assistant",  "content": _answer})

    # Clear chat
    if st.session_state.get(_chat_key):
        if st.button("Clear chat", key="clear_" + _chat_key):
            st.session_state[_chat_key] = []
            st.rerun()
