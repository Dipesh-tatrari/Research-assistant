"""
memory.py
---------
Phase 5 — Memory & Intelligence layer.

Gives the Research Assistant the ability to:
  1. Detect duplicate topics and return the cached report instantly
  2. Detect stale reports (older than STALE_DAYS) and suggest a refresh
  3. Find related past research so the writer can build on prior work
  4. Track topic similarity using simple keyword overlap (no ML needed)

All data lives in history.json — no new dependencies required.
"""

import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Settings  — tweak here
# ---------------------------------------------------------------------------
STALE_DAYS       = 7    # reports older than this are considered stale
SIMILARITY_FLOOR = 0.35  # 0–1; topics above this score count as "related"

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> set[str]:
    """Lowercase words, strip punctuation, drop common stop-words."""
    STOP = {
        "a","an","the","in","on","of","for","to","and","or","is","are",
        "was","were","it","its","this","that","with","as","at","by","be",
        "from","about","into","than","then","so","but","not","what","how",
        "when","where","which","who","will","can","do","does","has","have",
    }
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return {t for t in tokens if t not in STOP and len(t) > 1}


def _similarity(a: str, b: str) -> float:
    """Jaccard similarity between two topic strings."""
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _days_old(iso_timestamp: str) -> float:
    """Return how many days ago an ISO-8601 UTC timestamp was."""
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 86400
    except Exception:
        return 999.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class Memory:
    """
    Persistent memory layer backed by history.json.

    Usage:
        mem = Memory(history_file_path)

        check = mem.check_topic("AI agents in healthcare")
        if check["status"] == "exact":
            print("Already researched! Report at:", check["path"])
        elif check["status"] == "stale":
            print("Found old report, refreshing...")
        elif check["status"] == "related":
            print("Related past research:", check["related"])
        else:
            print("New topic — running full research")
    """

    def __init__(self, history_file: str) -> None:
        self.history_file = history_file

    def _load(self) -> list[dict]:
        if not os.path.exists(self.history_file):
            return []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Only consider successful runs with existing report files
                return [
                    r for r in (data if isinstance(data, list) else [])
                    if r.get("status") == "success"
                    and r.get("output_path")
                    and os.path.exists(r["output_path"])
                ]
        except (json.JSONDecodeError, OSError):
            return []

    def check_topic(self, topic: str) -> dict:
        """
        Check memory before running a new research job.

        Returns a dict with one of four statuses:

        • "exact"   — identical topic researched recently, report is fresh
                      keys: status, path, timestamp, days_old, output
        • "stale"   — identical topic found but report is older than STALE_DAYS
                      keys: status, path, timestamp, days_old, output
        • "related" — similar (not identical) topics found
                      keys: status, related (list of dicts)
        • "new"     — no relevant history, proceed with full research
                      keys: status
        """
        records = self._load()
        if not records:
            return {"status": "new"}

        exact_match   = None
        related_matches = []

        for r in records:
            sim = _similarity(topic, r["topic"])

            if sim >= 0.85:                       # effectively identical
                age = _days_old(r["timestamp"])
                if exact_match is None or age < _days_old(exact_match["timestamp"]):
                    exact_match = r             # keep the most recent match

            elif sim >= SIMILARITY_FLOOR:         # related but not same
                related_matches.append({
                    "topic":     r["topic"],
                    "path":      r["output_path"],
                    "timestamp": r["timestamp"],
                    "days_old":  round(_days_old(r["timestamp"]), 1),
                    "similarity": round(sim, 2),
                })

        # -- Exact match found --------------------------------------------
        if exact_match:
            age  = _days_old(exact_match["timestamp"])
            # Read the cached report text
            try:
                with open(exact_match["output_path"], "r", encoding="utf-8") as f:
                    cached_output = f.read()
            except OSError:
                cached_output = ""

            return {
                "status":    "stale" if age > STALE_DAYS else "exact",
                "path":      exact_match["output_path"],
                "timestamp": exact_match["timestamp"],
                "days_old":  round(age, 1),
                "output":    cached_output,
            }

        # -- Related matches found -----------------------------------------
        if related_matches:
            related_matches.sort(key=lambda x: x["similarity"], reverse=True)
            return {
                "status":  "related",
                "related": related_matches[:3],   # top 3 most similar
            }

        return {"status": "new"}

    def get_context_for_topic(self, topic: str) -> str:
        """
        Build a context string from related past reports to inject into
        the researcher's task description, so it builds on prior work.

        Returns an empty string if no related history exists.
        """
        check = self.check_topic(topic)

        if check["status"] in ("exact", "stale") and check.get("output"):
            return (
                f"\n\n--- PRIOR RESEARCH CONTEXT ---\n"
                f"You previously researched a similar topic "
                f"({check['days_old']} days ago). "
                f"Build on this — focus on new developments and avoid repeating "
                f"what is already covered:\n\n"
                f"{check['output'][:2000]}...\n"
                f"--- END PRIOR CONTEXT ---\n"
            )

        if check["status"] == "related":
            snippets = []
            for r in check["related"]:
                try:
                    with open(r["path"], "r", encoding="utf-8") as f:
                        content = f.read(800)
                    snippets.append(
                        f"Topic: {r['topic']} ({r['days_old']}d ago)\n{content}..."
                    )
                except OSError:
                    pass
            if snippets:
                return (
                    f"\n\n--- RELATED RESEARCH CONTEXT ---\n"
                    f"You have researched related topics before. "
                    f"Use these as background and focus on what's new:\n\n"
                    + "\n\n".join(snippets)
                    + "\n--- END RELATED CONTEXT ---\n"
                )

        return ""

    def get_all_topics(self) -> list[str]:
        """Return all successfully researched topics (newest first)."""
        records = self._load()
        seen, topics = set(), []
        for r in reversed(records):
            t = r.get("topic", "")
            if t and t not in seen:
                seen.add(t)
                topics.append(t)
        return list(reversed(topics))

    def get_stats(self) -> dict:
        """Return summary stats for the Streamlit sidebar."""
        records = self._load()
        if not records:
            return {"total": 0, "unique_topics": 0, "oldest_days": 0, "newest_days": 0}
        ages        = [_days_old(r["timestamp"]) for r in records]
        all_records = self._load.__func__(self) if False else []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                all_records = json.load(f)
        except Exception:
            all_records = records
        unique = len({r.get("topic","") for r in records})
        return {
            "total":        len(all_records),
            "unique_topics": unique,
            "oldest_days":  round(max(ages), 1) if ages else 0,
            "newest_days":  round(min(ages), 1) if ages else 0,
        }
