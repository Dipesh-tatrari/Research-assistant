"""
cloud_storage.py
----------------
Replaces local file-based history.json and outputs/ folder with
Supabase (PostgreSQL + Storage) so data persists across deployments.

Set these environment variables / Streamlit secrets:
    SUPABASE_URL = https://xxx.supabase.co
    SUPABASE_KEY = your-anon-key

Falls back to local file storage if Supabase is not configured,
so local development still works without any changes.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Detect environment
# ---------------------------------------------------------------------------

def _get_supabase_creds() -> tuple[Optional[str], Optional[str]]:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    # Also try Streamlit secrets
    if not url or not key:
        try:
            import streamlit as st
            url = url or st.secrets.get("SUPABASE_URL")
            key = key or st.secrets.get("SUPABASE_KEY")
        except Exception:
            pass

    return url, key


def _supabase_client():
    url, key = _get_supabase_creds()
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# History — write
# ---------------------------------------------------------------------------

def record_run(
    topic: str,
    output_path: str,
    output_text: str = "",
    status: str = "success",
    error_message: Optional[str] = None,
    source: str = "new",
    exports: Optional[dict] = None,
    persona: str = "general",
) -> dict:
    """
    Save a research run record.
    Uses Supabase if configured, otherwise falls back to local history.json.
    """
    entry = {
        "timestamp":   datetime.now(timezone.utc).isoformat(),
        "topic":       topic,
        "output_path": output_path,
        "output_text": output_text,
        "status":      status,
        "source":      source,
        "persona":     persona,
        "exports":     exports or {},
    }
    if error_message:
        entry["error"] = error_message

    client = _supabase_client()
    if client:
        try:
            client.table("research_history").insert({
                "timestamp":   entry["timestamp"],
                "topic":       topic,
                "status":      status,
                "source":      source,
                "persona":     persona,
                "output_text": output_text[:50000],  # Supabase text limit safety
                "output_path": output_path,
                "exports":     json.dumps(exports or {}),
                "error":       error_message,
            }).execute()
        except Exception as exc:
            print(f"Supabase write error: {exc}")
            _local_record(entry)
    else:
        _local_record(entry)

    return entry


def _local_record(entry: dict):
    """Fallback: write to local history.json"""
    logs_dir = Path(__file__).parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    hist_file = logs_dir / "history.json"
    try:
        records = json.loads(hist_file.read_text(encoding="utf-8")) if hist_file.exists() else []
    except Exception:
        records = []
    records.append(entry)
    hist_file.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# History — read
# ---------------------------------------------------------------------------

def get_history(limit: int = 50) -> list[dict]:
    """
    Fetch recent run history.
    Uses Supabase if configured, otherwise reads local history.json.
    """
    client = _supabase_client()
    if client:
        try:
            resp = (
                client.table("research_history")
                .select("id,timestamp,topic,status,source,persona,output_path,exports,error")
                .order("timestamp", desc=True)
                .limit(limit)
                .execute()
            )
            records = []
            for r in resp.data:
                try:
                    r["exports"] = json.loads(r["exports"]) if r.get("exports") else {}
                except Exception:
                    r["exports"] = {}
                records.append(r)
            return records
        except Exception as exc:
            print(f"Supabase read error: {exc}")

    # Fallback to local
    hist_file = Path(__file__).parent / "logs" / "history.json"
    if not hist_file.exists():
        return []
    try:
        data = json.loads(hist_file.read_text(encoding="utf-8"))
        return list(reversed(data))[:limit]
    except Exception:
        return []


def get_report_text(topic: str) -> Optional[str]:
    """
    Fetch the output text of the most recent successful run for a topic.
    Used by the memory system.
    """
    client = _supabase_client()
    if client:
        try:
            resp = (
                client.table("research_history")
                .select("output_text,timestamp")
                .eq("topic", topic)
                .eq("status", "success")
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )
            if resp.data:
                return resp.data[0]["output_text"]
        except Exception as exc:
            print(f"Supabase fetch error: {exc}")
    return None


def get_stats() -> dict:
    """Return summary stats for the sidebar."""
    client = _supabase_client()
    if client:
        try:
            resp = client.table("research_history").select("topic,timestamp,status").execute()
            data = resp.data or []
            successful = [r for r in data if r.get("status") == "success"]
            unique = len({r["topic"] for r in successful})
            return {
                "total":         len(data),
                "unique_topics": unique,
                "using_cloud":   True,
            }
        except Exception:
            pass

    # Fallback to local
    hist_file = Path(__file__).parent / "logs" / "history.json"
    if not hist_file.exists():
        return {"total": 0, "unique_topics": 0, "using_cloud": False}
    try:
        data = json.loads(hist_file.read_text(encoding="utf-8"))
        unique = len({r.get("topic","") for r in data if r.get("status") == "success"})
        return {"total": len(data), "unique_topics": unique, "using_cloud": False}
    except Exception:
        return {"total": 0, "unique_topics": 0, "using_cloud": False}


# ---------------------------------------------------------------------------
# File storage — upload report files to Supabase Storage
# ---------------------------------------------------------------------------

def upload_report(file_path: str, topic: str) -> Optional[str]:
    """
    Upload a report file to Supabase Storage.
    Returns the public URL or None if upload failed / not configured.
    """
    client = _supabase_client()
    if not client or not os.path.exists(file_path):
        return None

    try:
        filename  = os.path.basename(file_path)
        ext       = filename.split(".")[-1]
        mime_map  = {"pdf": "application/pdf", "md": "text/markdown",
                     "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
        mime_type = mime_map.get(ext, "application/octet-stream")

        with open(file_path, "rb") as f:
            data = f.read()

        client.storage.from_("research-reports").upload(
            path=filename,
            file=data,
            file_options={"content-type": mime_type, "upsert": "true"},
        )

        url_resp = client.storage.from_("research-reports").get_public_url(filename)
        return url_resp
    except Exception as exc:
        print(f"Upload error: {exc}")
        return None


def is_cloud_configured() -> bool:
    """Return True if Supabase credentials are available."""
    url, key = _get_supabase_creds()
    return bool(url and key)


def debug_status() -> dict:
    """
    Returns diagnostic info — call this to debug why Supabase isn't working.
    Usage:
        from cloud_storage import debug_status
        print(debug_status())
    """
    url, key = _get_supabase_creds()
    result = {
        "url_set":     bool(url),
        "key_set":     bool(key),
        "url_preview": (url[:30] + "...") if url else None,
        "client_created": False,
        "table_reachable": False,
        "error": None,
    }
    if not url or not key:
        result["error"] = "SUPABASE_URL or SUPABASE_KEY not set in env/secrets"
        return result

    try:
        from supabase import create_client
        client = create_client(url, key)
        result["client_created"] = True
    except Exception as exc:
        result["error"] = f"create_client failed: {exc}"
        return result

    try:
        resp = client.table("research_history").select("id").limit(1).execute()
        result["table_reachable"] = True
        result["row_count_sample"] = len(resp.data)
    except Exception as exc:
        result["error"] = f"table query failed: {exc}"

    return result
