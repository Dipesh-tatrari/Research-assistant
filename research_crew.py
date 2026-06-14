"""
research_crew.py
----------------
Research Assistant - Phase 7: Custom Agent Personas
CrewAI 1.14.7 + Groq (llama-3.3-70b-versatile)

New in Phase 7:
  - 6 specialist personas: General, Medical, Financial, Legal, Technical, Policy
  - Each persona has unique role, backstory, search strategy, report format, tone
  - ResearchCrew(topic, persona="medical") — one argument to switch everything
  - Persona shown in history.json and Streamlit sidebar
  - All Phase 5 (memory) and Phase 6 (export) features retained

Run:
    set GROQ_API_KEY=gsk_...
    python research_crew.py "CRISPR gene therapy 2025" --persona medical
    python research_crew.py "AI chip market 2025"      --persona financial
    python research_crew.py "EU AI Act compliance"     --persona legal
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

os.environ["LITELLM_DROP_PARAMS"] = "true"
os.environ["LITELLM_CACHE"]       = "false"

# ── Permanent cache_breakpoint fix ───────────────────────────────────────────
# CrewAI 1.14.7 injects cache_breakpoint into messages which Groq rejects.
# We patch mark_cache_breakpoint to a no-op BEFORE crewai loads any agents.
def _patch_crewai_cache():
    try:
        import crewai.llms.cache as _cache_mod
        def _noop(message, *args, **kwargs):
            return message
        _cache_mod.mark_cache_breakpoint = _noop
        # Also patch it in all modules that already imported it
        import crewai.agents.crew_agent_executor as _exec_mod
        _exec_mod.mark_cache_breakpoint = _noop
        try:
            import crewai.experimental.agent_executor as _exp_mod
            _exp_mod.mark_cache_breakpoint = _noop
        except Exception:
            pass
    except Exception as e:
        print(f"Cache patch warning: {e}")

_patch_crewai_cache()
# ── End fix ──────────────────────────────────────────────────────────────────

from crewai import LLM, Agent, Crew, Process, Task
from crewai.tools import BaseTool
from duckduckgo_search import DDGS

from memory   import Memory
from exporter import export_all
from personas import get_persona, list_personas

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
OUTPUTS_DIR  = os.path.join(BASE_DIR, "outputs")
LOGS_DIR     = os.path.join(BASE_DIR, "logs")
HISTORY_FILE = os.path.join(LOGS_DIR, "history.json")

MODEL_CONFIG = {
    "model":       "groq/llama-3.3-70b-versatile",
    "temperature": 0.3,
    "max_iter":    5,
}

# ---------------------------------------------------------------------------
# DuckDuckGo tool
# ---------------------------------------------------------------------------
class DuckDuckGoSearchTool(BaseTool):
    name: str        = "DuckDuckGo Search"
    description: str = "Search the web for current information. Input: a concise search query string."

    def _run(self, query: str) -> str:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=6))
            if not results:
                return "No results found. Try a different query."
            return "\n\n".join(
                f"Title: {r['title']}\nURL: {r['href']}\nSummary: {r['body']}"
                for r in results
            )
        except Exception as exc:
            return f"Search failed ({type(exc).__name__}): {exc}"

# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------
def _ensure_dirs():
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)

def _load_history() -> list:
    """Local fallback only — primary storage is cloud_storage (Supabase)."""
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []

def record_run(topic, output_path, status="success", error_message=None,
               source="new", exports=None, persona="general", output_text=""):
    """
    Persist a run record. Writes to Supabase via cloud_storage if configured,
    AND to local history.json as a backup (useful for local dev / memory.py).
    """
    entry = {
        "timestamp":   datetime.now(timezone.utc).isoformat(),
        "topic":       topic,
        "output_path": output_path,
        "status":      status,
        "source":      source,
        "persona":     persona,
    }
    if error_message: entry["error"]   = error_message
    if exports:       entry["exports"] = exports

    # Always write locally too (memory.py reads this for cache/related checks)
    _ensure_dirs()
    records = _load_history()
    records.append(entry)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    # Also write to Supabase if configured (survives restarts on Streamlit Cloud)
    try:
        from cloud_storage import record_run as cloud_record_run
        cloud_record_run(
            topic=topic,
            output_path=output_path,
            output_text=output_text,
            status=status,
            error_message=error_message,
            source=source,
            exports=exports,
            persona=persona,
        )
    except Exception as e:
        log.warning(f"Cloud history write skipped: {e}")

    return entry

def print_history():
    records = list(reversed(_load_history()))
    if not records:
        print("No history found.")
        return
    print(f"\n{'─'*65}")
    print(f"  Research History  ({len(records)} runs)")
    print(f"{'─'*65}")
    for r in records:
        icon    = "✓" if r["status"] == "success" else "✗"
        source  = r.get("source", "new")
        badge   = {"cached":"[CACHE]","refreshed":"[REFRESH]","new":"[NEW]"}.get(source,"")
        persona = r.get("persona","general").upper()
        exports = r.get("exports", {})
        fmt     = " ".join(k.upper() for k in exports if not k.endswith("_error") and k != "md")
        print(f"  {icon} [{r['timestamp'][:19]}] {badge} [{persona}] {r['topic']}")
        if fmt: print(f"       Exports: {fmt}")
        if "error" in r: print(f"       Error: {r['error']}")
    print(f"{'─'*65}\n")

# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------
def build_llm() -> LLM:
    api_key = os.environ.get("GROQ_API_KEY", "").strip().strip('"').strip("'")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY is not set.\n  Windows: set GROQ_API_KEY=gsk_...")
    os.environ["GROQ_API_KEY"] = api_key
    return LLM(
        model=MODEL_CONFIG["model"],
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
        temperature=MODEL_CONFIG["temperature"],
    )

# ---------------------------------------------------------------------------
# Task builder — persona-aware
# ---------------------------------------------------------------------------
def _build_research_description(topic: str, persona_cfg: dict,
                                 memory_context: str = "") -> str:
    return (
        f"Conduct rigorous research on the following topic using web search.\n\n"
        f"TOPIC: {topic}\n\n"
        f"{memory_context}"
        f"YOUR SPECIALIST FOCUS:\n{persona_cfg['search_focus']}\n\n"
        f"You MUST gather and document:\n"
        f"1. Background & context — definition, scope, history\n"
        f"2. Key findings (minimum 6, each with source URL)\n"
        f"3. Recent developments (last 12 months, with dates)\n"
        f"4. Major players & stakeholders\n"
        f"5. Challenges, controversies, or risks\n"
        f"6. Future outlook with forecasts from credible sources\n\n"
        f"Run multiple DuckDuckGo searches to cover all areas. "
        f"Record every source URL — the writer cannot cite what you don't find."
    )

def _build_writing_description(topic: str, persona_cfg: dict) -> str:
    return (
        f"Using the research brief, write a full professional research report "
        f"on: {topic}\n\n"
        f"REPORT STRUCTURE — follow exactly:\n\n"
        f"# [Descriptive Title]\n\n"
        f"**Topic:** {topic}  \n"
        f"**Date:** {datetime.now().strftime('%B %d, %Y')}  \n"
        f"**Analyst Type:** {persona_cfg['researcher']['role']}  \n\n"
        f"---\n\n"
        f"{persona_cfg['report_format']}\n"
        f"---\n\n"
        f"*Report generated by Research Assistant - {MODEL_CONFIG['model']}*\n\n"
        f"QUALITY RULES:\n"
        f"- Tone: {persona_cfg['tone']}\n"
        f"- Every claim must have a citation from the research brief\n"
        f"- Minimum 1200 words in body sections\n"
        f"- Do not invent data — only use what the researcher found\n"
        f"- Use precise language — no vague filler words"
    )

# ---------------------------------------------------------------------------
# ResearchCrew — Phase 7
# ---------------------------------------------------------------------------
class ResearchCrew:
    """
    Phase 7: Persona-aware memory + export pipeline.

    Args:
        topic:   Research subject.
        persona: One of: general, medical, financial, legal, technical, policy
        force:   Skip memory cache and run fresh.

    result = ResearchCrew("CRISPR 2025", persona="medical").run()
    result keys: status, topic, output, path, exports,
                 memory_status, memory_info, persona
    """

    def __init__(self, topic: str, persona: str = "general",
                 force: bool = False) -> None:
        self.topic       = topic.strip()
        self.persona_key = persona
        self.persona_cfg = get_persona(persona)
        self.force       = force
        self.memory      = Memory(HISTORY_FILE)
        self._llm        = build_llm()
        self._search     = DuckDuckGoSearchTool()

    def _timestamped_path(self) -> str:
        _ensure_dirs()
        ts   = datetime.now().strftime("%Y%m%d_%H%M")
        slug = "".join(c if c.isalnum() else "_" for c in self.topic.lower())[:35]
        return os.path.join(
            OUTPUTS_DIR,
            f"report_{ts}_{self.persona_key}_{slug}.md"
        )

    def _researcher(self) -> Agent:
        cfg = self.persona_cfg["researcher"]
        return Agent(
            role=cfg["role"],
            goal=cfg["goal"],
            backstory=cfg["backstory"],
            tools=[self._search],
            llm=self._llm,
            verbose=True,
            allow_delegation=False,
            max_iter=MODEL_CONFIG["max_iter"],
            max_retry_limit=2,
        )

    def _writer(self) -> Agent:
        cfg = self.persona_cfg["writer"]
        return Agent(
            role=cfg["role"],
            goal=cfg["goal"],
            backstory=cfg["backstory"],
            tools=[],
            llm=self._llm,
            verbose=True,
            allow_delegation=False,
            max_retry_limit=2,
        )

    def _research_task(self, researcher: Agent,
                       memory_context: str = "") -> Task:
        return Task(
            description=_build_research_description(
                self.topic, self.persona_cfg, memory_context
            ),
            expected_output=(
                "A comprehensive research brief with all 6 areas covered, "
                "minimum 8 source URLs, quantitative data, and expert references."
            ),
            agent=researcher,
        )

    def _writing_task(self, writer: Agent, research_task: Task,
                      output_path: str) -> Task:
        return Task(
            description=_build_writing_description(self.topic, self.persona_cfg),
            expected_output=(
                "A complete, publication-ready research report with all sections, "
                "minimum 1200 words, fully cited."
            ),
            agent=writer,
            context=[research_task],
            output_file=output_path,
        )

    def _run_crew(self, memory_context: str = "") -> tuple[str, str]:
        output_path   = self._timestamped_path()
        researcher    = self._researcher()
        writer        = self._writer()
        research_task = self._research_task(researcher, memory_context)
        writing_task  = self._writing_task(writer, research_task, output_path)

        crew = Crew(
            agents=[researcher, writer],
            tasks=[research_task, writing_task],
            process=Process.sequential,
            verbose=True,
        )
        result      = crew.kickoff()
        output_text = str(result)

        if not os.path.exists(output_path):
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(output_text)
        return output_text, output_path

    def _do_exports(self, output_text: str, output_path: str) -> dict:
        try:
            return export_all(
                markdown_text=output_text,
                topic=self.topic,
                base_path=output_path,
                model=MODEL_CONFIG["model"],
            )
        except Exception as exc:
            log.warning("Export error: %s", exc)
            return {"export_error": str(exc)}

    def run(self) -> dict:
        log.info("Research: '%s' | persona: %s | force: %s",
                 self.topic, self.persona_key, self.force)

        mem_check = (
            self.memory.check_topic(self.topic)
            if not self.force
            else {"status": "new"}
        )
        log.info("Memory: %s", mem_check["status"])

        def _success(output_text, output_path, mem_status, source):
            exports = self._do_exports(output_text, output_path)
            record_run(self.topic, output_path, "success",
                       source=source, exports=exports,
                       persona=self.persona_key, output_text=output_text)
            return {
                "status":        "success",
                "topic":         self.topic,
                "output":        output_text,
                "path":          output_path,
                "exports":       exports,
                "memory_status": mem_status,
                "memory_info":   mem_check,
                "persona":       self.persona_key,
                "persona_label": self.persona_cfg["label"],
            }

        try:
            if mem_check["status"] == "exact":
                log.info("Cache hit")
                return _success(mem_check["output"], mem_check["path"],
                                "cached", "cached")

            if mem_check["status"] == "stale":
                log.info("Stale — refreshing")
                ctx = self.memory.get_context_for_topic(self.topic)
                out, path = self._run_crew(memory_context=ctx)
                return _success(out, path, "stale", "refreshed")

            if mem_check["status"] == "related":
                log.info("Related — injecting context")
                ctx = self.memory.get_context_for_topic(self.topic)
                out, path = self._run_crew(memory_context=ctx)
                return _success(out, path, "related", "new")

            # New topic
            out, path = self._run_crew()
            return _success(out, path, "new", "new")

        except EnvironmentError as exc:
            msg = f"Config error: {exc}"
            log.error(msg)
            record_run(self.topic, "", "failed", msg, persona=self.persona_key)
            return {"status":"failed","topic":self.topic,"output":msg,
                    "path":None,"exports":{},"memory_status":"failed",
                    "memory_info":{},"persona":self.persona_key,
                    "persona_label":self.persona_cfg["label"]}

        except Exception as exc:
            exc_str = str(exc).lower()
            if "rate_limit" in exc_str or "429" in exc_str:
                msg = "Groq rate limit. Wait 60s and retry."
            elif "connectionerror" in type(exc).__name__.lower():
                msg = "Network error. Check connection."
            elif "401" in exc_str:
                msg = "Invalid GROQ_API_KEY."
            else:
                msg = f"Error ({type(exc).__name__}): {exc}"
            log.error(msg)
            record_run(self.topic, "", "failed", msg, persona=self.persona_key)
            return {"status":"failed","topic":self.topic,"output":msg,
                    "path":None,"exports":{},"memory_status":"failed",
                    "memory_info":{},"persona":self.persona_key,
                    "persona_label":self.persona_cfg["label"]}

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def run_crew(topic: str, persona: str = "general",
             force: bool = False) -> dict:
    return ResearchCrew(topic, persona=persona, force=force).run()

if __name__ == "__main__":
    force   = "--force" in sys.argv
    args    = [a for a in sys.argv[1:] if not a.startswith("--")]
    persona = "general"

    # --persona medical  or  --persona=medical
    for arg in sys.argv[1:]:
        if arg.startswith("--persona"):
            persona = arg.split("=")[-1] if "=" in arg else (
                sys.argv[sys.argv.index(arg)+1]
                if sys.argv.index(arg)+1 < len(sys.argv) else "general"
            )
            if persona.startswith("--"):
                persona = "general"

    topic_args = [a for a in args if a not in list_personas()]
    if topic_args:
        topic = " ".join(topic_args)
    else:
        raw   = os.environ.get("RESEARCH_TOPIC",
                               "The current state of open-source LLMs")
        topic = raw.strip().strip('"').strip("'")

    persona_info = get_persona(persona)

    print(f"\n{'='*65}")
    print(f"  Research Assistant - Phase 7: Custom Personas")
    print(f"  Topic   : {topic}")
    print(f"  Persona : {persona_info['label']}")
    print(f"  Force   : {force}")
    print(f"{'='*65}\n")

    result = run_crew(topic, persona=persona, force=force)

    print(f"\n{'='*65}")
    if result["status"] == "success":
        badges = {
            "cached":  "CACHE HIT",
            "stale":   "REFRESHED",
            "related": "NEW + CONTEXT",
            "new":     "NEW RESEARCH",
        }
        print(f"  {badges.get(result['memory_status'],'COMPLETE')}")
        print(f"  Persona : {result['persona_label']}")
        print(f"  MD      : {result['path']}")
        ex = result.get("exports", {})
        if "pdf"  in ex: print(f"  PDF     : {ex['pdf']}")
        if "docx" in ex: print(f"  DOCX    : {ex['docx']}")
        print(f"{'='*65}\n")
        print(result["output"])
    else:
        print(f"  FAILED: {result['output']}")
        print(f"{'='*65}\n")

    print_history()
