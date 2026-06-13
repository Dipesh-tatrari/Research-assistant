"""
streamlit_app.py — Phase 6: Professional Export + Research Report UI
"""

from dotenv import load_dotenv
load_dotenv()

import json
import os
from datetime import datetime
from pathlib import Path

import streamlit as st

from cloud_storage import get_history, get_stats, is_cloud_configured

st.set_page_config(
    page_title="Research Assistant",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.stApp { background-color: #0f1117; }
section[data-testid="stSidebar"] { background-color: #161b27; border-right: 1px solid #1e2535; }
.ra-header { padding: 2rem 0 1.5rem 0; border-bottom: 1px solid #1e2535; margin-bottom: 2rem; }
.ra-title { font-family: 'IBM Plex Mono', monospace; font-size: 1.6rem; font-weight: 600; color: #e2e8f0; }
.ra-subtitle { font-size: 0.85rem; color: #64748b; font-family: 'IBM Plex Mono', monospace; }
.stTextInput input { background-color: #161b27 !important; border: 1px solid #1e2535 !important; color: #e2e8f0 !important; border-radius: 6px !important; font-size: 0.95rem !important; padding: 0.75rem 1rem !important; }
.stTextInput input:focus { border-color: #3b82f6 !important; box-shadow: 0 0 0 2px rgba(59,130,246,0.15) !important; }
.stButton > button { background: linear-gradient(135deg,#3b82f6,#2563eb) !important; color: white !important; border: none !important; border-radius: 6px !important; font-weight: 500 !important; padding: 0.6rem 1.2rem !important; width: 100% !important; transition: opacity .2s !important; }
.stButton > button:hover { opacity: .88 !important; }
.stDownloadButton > button { background: #1e2535 !important; color: #e2e8f0 !important; border: 1px solid #334155 !important; border-radius: 6px !important; font-size: 0.85rem !important; width: 100% !important; }
.stDownloadButton > button:hover { background: #263045 !important; }
.card  { background:#161b27; border:1px solid #1e2535; border-radius:8px; padding:1.25rem 1.5rem; margin-bottom:1rem; }
.card-success { border-left:3px solid #22c55e; }
.card-warning { border-left:3px solid #f59e0b; }
.card-error   { border-left:3px solid #ef4444; }
.card-info    { border-left:3px solid #3b82f6; }
.card-cache   { border-left:3px solid #a855f7; }
.mem-badge { display:inline-block; padding:.2rem .6rem; border-radius:4px; font-size:.75rem; font-family:'IBM Plex Mono',monospace; font-weight:600; margin-right:.4rem; }
.badge-new     { background:#1e3a5f; color:#60a5fa; }
.badge-cached  { background:#2d1b69; color:#a78bfa; }
.badge-stale   { background:#3d2100; color:#fbbf24; }
.badge-related { background:#1a3320; color:#4ade80; }
.chip { display:inline-block; background:#1e2535; color:#94a3b8; border-radius:4px; padding:.2rem .6rem; font-size:.75rem; font-family:'IBM Plex Mono',monospace; margin-right:.4rem; }
.export-box { background:#0f1117; border:1px solid #1e2535; border-radius:8px; padding:1rem 1.25rem; margin-top:.75rem; }
.export-title { color:#94a3b8; font-size:.75rem; font-family:'IBM Plex Mono',monospace; font-weight:600; margin-bottom:.75rem; letter-spacing:.05em; }
.hist-item { background:#161b27; border:1px solid #1e2535; border-radius:6px; padding:.75rem 1rem; margin-bottom:.5rem; font-size:.82rem; }
.hist-success { border-left:2px solid #22c55e; }
.hist-failed  { border-left:2px solid #ef4444; }
.hist-topic { color:#e2e8f0; font-weight:500; margin-bottom:.2rem; }
.hist-meta  { color:#64748b; font-family:'IBM Plex Mono',monospace; font-size:.75rem; }
.report-container { background:#161b27; border:1px solid #1e2535; border-radius:8px; padding:2.5rem; margin-top:1rem; line-height:1.8; }
.report-container h1 { color:#e2e8f0; font-size:1.6rem; border-bottom:2px solid #2563eb; padding-bottom:.5rem; margin-bottom:1.2rem; }
.report-container h2 { color:#93c5fd; font-size:1.2rem; margin-top:2rem; margin-bottom:.6rem; }
.report-container h3 { color:#cbd5e1; font-size:1rem; margin-top:1.2rem; }
.report-container p  { color:#94a3b8; line-height:1.8; margin-bottom:.8rem; }
.report-container li { color:#94a3b8; line-height:1.9; }
.report-container a  { color:#3b82f6; }
.report-container hr { border-color:#1e2535; margin:1.5rem 0; }
.report-container strong { color:#cbd5e1; }
.report-container code { background:#1e2535; color:#7dd3fc; padding:.1rem .3rem; border-radius:3px; font-size:.85em; }
.report-container blockquote { border-left:3px solid #2563eb; padding-left:1rem; color:#64748b; }
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
    "new":     ("🆕 New research",        "badge-new"),
    "cached":  ("⚡ Served from cache",   "badge-cached"),
    "stale":   ("♻ Refreshed (stale)",    "badge-stale"),
    "related": ("🔗 Used related context", "badge-related"),
}

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("<div style='padding:1rem 0 .5rem;font-family:IBM Plex Mono,monospace;font-size:.9rem;color:#e2e8f0;font-weight:600;'>⚙ Configuration</div>", unsafe_allow_html=True)
    if validate_api_key():
        st.markdown("<div class='card card-success'><span style='color:#22c55e;font-size:.8rem;'>● GROQ_API_KEY detected</span></div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='card card-error'><span style='color:#ef4444;font-size:.8rem;'>✗ GROQ_API_KEY not set</span></div>", unsafe_allow_html=True)

    # Memory stats
    try:
        from memory import Memory
        mem_obj = Memory(str(HISTORY_FILE))
        stats   = get_stats()
        st.markdown("---")
        st.markdown("<div style='color:#64748b;font-size:.75rem;font-family:IBM Plex Mono,monospace;margin-bottom:.75rem;'>MEMORY STATS</div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1: st.metric("Total Runs", stats["total"])
        with c2: st.metric("Topics",     stats["unique_topics"])
    except Exception:
        pass

    st.markdown("---")
    st.markdown("<div style='color:#64748b;font-size:.75rem;font-family:IBM Plex Mono,monospace;margin-bottom:.75rem;'>RECENT RUNS</div>", unsafe_allow_html=True)
    history = get_history(limit = 8)
    if not history:
        st.markdown("<div style='color:#475569;font-size:.8rem;'>No runs yet.</div>", unsafe_allow_html=True)
    else:
        for run in history[:8]:
            sc     = "hist-success" if run.get("status") == "success" else "hist-failed"
            icon   = "✓" if run.get("status") == "success" else "✗"
            src    = run.get("source","new")
            src_ic = {"cached":"⚡","refreshed":"♻","new":"🆕"}.get(src,"")
            exports= run.get("exports",{})
            fmt    = " ".join(k.upper() for k in exports if not k.endswith("_error") and k != "md")
            ts     = run.get("timestamp","")[:16].replace("T"," ")
            topic  = run.get("topic","")[:30]
            st.markdown(f"""
            <div class='hist-item {sc}'>
                <div class='hist-topic'>{icon} {src_ic} {topic}</div>
                <div class='hist-meta'>{ts}{' · '+fmt if fmt else ''}</div>
            </div>""", unsafe_allow_html=True)

# ── Main ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class='ra-header'>
    <div class='ra-title'>🔬 Research Assistant</div>
    <div class='ra-subtitle'>Phase 6 · Professional Export · PDF · DOCX · Groq · LLaMA 3.3 70B</div>
</div>
""", unsafe_allow_html=True)

# Memory preview
try:
    from memory import Memory
    _mem = Memory(str(HISTORY_FILE))
    _all_topics = _mem.get_all_topics()
except Exception:
    _all_topics = []

col1, col2, col3 = st.columns([3, 0.8, 0.8])
with col1:
    topic = st.text_input("Research topic", placeholder="e.g. AI agents in healthcare 2025", label_visibility="collapsed")
with col2:
    run_btn   = st.button("▶ Run",   disabled=not validate_api_key())
with col3:
    force_btn = st.button("↺ Force", disabled=not validate_api_key(), help="Bypass cache — run fresh research")

# Live memory preview
if topic.strip() and _all_topics:
    try:
        chk = _mem.check_topic(topic.strip())
        if chk["status"] == "exact":
            st.markdown(f"<div class='card card-cache'><span class='mem-badge badge-cached'>⚡ CACHED</span><span style='color:#c4b5fd;font-size:.85rem;'>Researched <strong>{chk['days_old']} days ago</strong>. Run returns cached report instantly. Use ↺ Force to refresh.</span></div>", unsafe_allow_html=True)
        elif chk["status"] == "stale":
            st.markdown(f"<div class='card card-warning'><span class='mem-badge badge-stale'>♻ STALE</span><span style='color:#fcd34d;font-size:.85rem;'>Report is <strong>{chk['days_old']} days old</strong> — will refresh with prior context injected.</span></div>", unsafe_allow_html=True)
        elif chk["status"] == "related":
            rel = ", ".join(f"<em>{r['topic']}</em>" for r in chk["related"][:2])
            st.markdown(f"<div class='card card-info'><span class='mem-badge badge-related'>🔗 RELATED</span><span style='color:#93c5fd;font-size:.85rem;'>Related research found: {rel}. Prior context will be injected.</span></div>", unsafe_allow_html=True)
    except Exception:
        pass

# ── Run ───────────────────────────────────────────────────────────────────────
force = force_btn and not run_btn

if (run_btn or force_btn) and topic.strip():
    try:
        from research_crew import ResearchCrew
    except ImportError as e:
        st.error(f"Cannot import research_crew.py: {e}")
        st.stop()

    start = datetime.now()
    with st.spinner(f"Researching **{topic}** and generating PDF + DOCX — takes 2–4 minutes..."):
        result = ResearchCrew(topic.strip(), force=force).run()
    elapsed    = (datetime.now() - start).seconds
    mem_status = result.get("memory_status", "new")

    if result["status"] == "success":
        label, badge_cls = MEM_LABELS.get(mem_status, ("Complete","badge-new"))
        wc = word_count(result["output"])

        # Success banner
        st.markdown(f"""
        <div class='card card-success'>
            <span style='color:#22c55e;font-weight:600;'>✓ Research complete</span>
            &nbsp;<span class='mem-badge {badge_cls}'>{label}</span>
            <span style='float:right;'>
                <span class='chip'>{elapsed}s</span>
                <span class='chip'>{wc} words</span>
            </span>
        </div>""", unsafe_allow_html=True)

        # ── Download buttons ─────────────────────────────────────────────
        exports = result.get("exports", {})
        st.markdown("<div class='export-box'><div class='export-title'>📥 DOWNLOAD REPORT</div>", unsafe_allow_html=True)
        dl1, dl2, dl3 = st.columns(3)

        with dl1:
            md_path = result.get("path")
            if md_path and os.path.exists(md_path):
                with open(md_path, "rb") as f:
                    st.download_button("📄 Markdown", f,
                        file_name=os.path.basename(md_path),
                        mime="text/markdown")

        with dl2:
            pdf_path = exports.get("pdf")
            if pdf_path and os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    st.download_button("📕 PDF", f,
                        file_name=os.path.basename(pdf_path),
                        mime="application/pdf")
            elif "pdf_error" in exports:
                st.caption(f"PDF error: {exports['pdf_error'][:60]}")

        with dl3:
            docx_path = exports.get("docx")
            if docx_path and os.path.exists(docx_path):
                with open(docx_path, "rb") as f:
                    st.download_button("📘 Word", f,
                        file_name=os.path.basename(docx_path),
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            elif "docx_error" in exports:
                st.caption(f"DOCX error: {exports['docx_error'][:60]}")

        st.markdown("</div>", unsafe_allow_html=True)

        # Related context used
        mem_info = result.get("memory_info", {})
        if mem_status == "related" and mem_info.get("related"):
            with st.expander("🔗 Related research used as context"):
                for r in mem_info["related"]:
                    st.markdown(f"**{r['topic']}** — {r['days_old']}d ago · {int(r['similarity']*100)}% similar")

        # ── Report display ───────────────────────────────────────────────
        st.markdown("<div class='report-container'>", unsafe_allow_html=True)
        st.markdown(result["output"])
        st.markdown("</div>", unsafe_allow_html=True)

    else:
        st.markdown(f"""
        <div class='card card-error'>
            <span style='color:#ef4444;font-weight:600;'>✗ Research failed</span><br>
            <span style='color:#94a3b8;font-size:.85rem;'>{result['output']}</span>
        </div>""", unsafe_allow_html=True)

elif (run_btn or force_btn) and not topic.strip():
    st.markdown("<div class='card card-info'><span style='color:#3b82f6;'>Please enter a research topic above.</span></div>", unsafe_allow_html=True)

else:
    st.markdown("""
    <div style='text-align:center;padding:4rem 2rem;'>
        <div style='font-size:3rem;margin-bottom:1rem;'>🔬</div>
        <div style='color:#475569;font-size:.95rem;line-height:2.2;'>
            Enter a topic and click <strong style='color:#94a3b8;'>▶ Run</strong>.<br>
            The agent will produce a full academic research report<br>
            and export it as <strong style='color:#94a3b8;'>Markdown · PDF · Word</strong> simultaneously.
        </div>
    </div>""", unsafe_allow_html=True)
