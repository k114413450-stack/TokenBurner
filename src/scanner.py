# -*- coding: utf-8 -*-
"""
Token scanner engine.

Every number this module returns belongs to exactly one of two classes, and the
two are never silently added together:

  VERIFIED   parsed from the tool's own per-request API usage records
             (``inputTokens`` / ``outputTokens`` / ``cached_tokens``). This is
             the real, billable number.
  ESTIMATED  derived from the size of on-disk conversation files
             (``bytes / CHARS_PER_TOKEN``) for tools that keep no usage ledger.
             Labelled as an estimate everywhere it surfaces.

Why the split exists
--------------------
The previous implementation applied the byte heuristic to every
``.db/.json/.jsonl/.log/.ldb`` file found under a tool's whole data directory.
Measured on a real WorkBuddy install (2.6 GB, 60 k files):

    logs            704.3 MB -> 210,994,136 "tokens"
    traces          290.6 MB ->  87,061,199 "tokens"
    security         42.2 MB ->  12,636,863 "tokens"
    changes-detail   34.3 MB ->  10,282,110 "tokens"
    ...
    projects         48.9 MB ->  14,656,019 "tokens"   <- the ONLY conversation data

94.8 % of the counted bytes were installed software, IDE caches, telemetry
traces and log files. Ironically the result (348.5 M) landed within 20 % of the
real 421.2 M, because the junk inflation (~21x) very nearly cancelled the
undercount of the conversation files (~29x: the transcript stores each message
once, while the API re-sends the entire context on every request - hence a 98.5 %
cache-hit rate). An error that accidentally looks correct is worse than one that
does not, so both causes are fixed here.
"""

import json
import os
import sqlite3
from datetime import date, datetime, timedelta

try:
    from app_paths import get_app_data_dir
except ImportError:
    from src.app_paths import get_app_data_dir

# Paths are resolved on every access rather than captured at import time.
# `%APPDATA%` is not guaranteed to be the same value for the whole life of the
# process (packaged builds, multiple profiles, test harnesses), and a
# module-level constant silently read and wrote the wrong user's config - which
# in practice meant a stale `web_tokens` entry leaking into an unrelated run.
def data_dir():
    return get_app_data_dir()


def config_file():
    return os.path.join(data_dir(), "config.json")


def history_file():
    return os.path.join(data_dir(), "daily_history.json")

# Average characters per token for mixed CJK/latin source text. Only used by the
# ESTIMATED path.
CHARS_PER_TOKEN = 3.5

# ---------------------------------------------------------------------------
# Data-quality tiers
# ---------------------------------------------------------------------------
TIER_VERIFIED = "verified"
TIER_ESTIMATED = "estimated"
TIER_UNAVAILABLE = "unavailable"

# Directories that never contain conversation data. Used to keep the byte
# heuristic away from installed runtimes, caches, logs and telemetry.
NON_CONVERSATION_DIRS = {
    "binaries", "node_modules", "site-packages", "dist-packages", ".git",
    ".venv", "venv", "env", "logs", "log", "traces", "trace", "plugins",
    "plugin", "cache", "caches", "code_cache", "gpucache", "security",
    "file-history", "changes-detail", "changes-index", "delta-history",
    "connectors-marketplace", "connectors", "shell-snapshots", "tmp", "temp",
    "appearance-resources", "artifact-index", "pending-telemetry",
    "service worker", "blob_storage", "dawncache", "dawn_graphitecache",
    "shadercache", "component_crx_cache", "grshadercache",
}

# Extensions the byte heuristic is allowed to look at.
CONVERSATION_EXTS = (".json", ".jsonl", ".log", ".txt", ".db", ".ldb")


def load_config():
    default_cfg = {
        "nickname": "CyberDev",
        "web_tokens": 0,
        "api_tokens": 0,
        "hourly_rate_tokens": 12000,
        # Cost model. Rates are USD per 1M tokens and are explicitly an
        # assumption, not a bill: the app has no access to provider pricing.
        # Cached input is billed at a fraction of fresh input by every major
        # provider, which matters enormously here (98.5 % of input is cached).
        "pricing": {
            "input_per_m": 2.94,
            "cached_input_per_m": 0.294,
            "output_per_m": 11.76,
        },
        # YOLO auto-clicker safety policy. See yolo_approver.py.
        # dry_run is ON by default: out of the box the engine only *detects* and
        # reports, it never moves the mouse.
        "yolo": {
            "dry_run": True,
            "whitelist_processes": [
                "claude.exe", "codex.exe", "cursor.exe", "windsurf.exe",
                "trae.exe", "code.exe", "windowsterminal.exe", "wt.exe",
                "cmd.exe", "powershell.exe", "pwsh.exe", "conhost.exe",
            ],
            "whitelist_titles": [],
            "confidence": 0.82,
            "min_seconds_between_clicks": 3.0,
            "max_clicks_per_minute": 10,
            "max_clicks_per_session": 100,
        },
    }
    if os.path.exists(config_file()):
        try:
            with open(config_file(), "r", encoding="utf-8") as f:
                data = json.load(f)
                # shallow merge, but keep nested defaults intact
                pricing = dict(default_cfg["pricing"])
                if isinstance(data.get("pricing"), dict):
                    pricing.update(data["pricing"])
                yolo = dict(default_cfg["yolo"])
                if isinstance(data.get("yolo"), dict):
                    yolo.update(data["yolo"])
                default_cfg.update(data)
                default_cfg["pricing"] = pricing
                default_cfg["yolo"] = yolo
        except Exception:
            pass
    return default_cfg


def save_config(cfg):
    try:
        with open(config_file(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
    except Exception:
        pass


# ===========================================================================
# Shared helpers for the ESTIMATED path
# ===========================================================================

def _is_non_conversation(file_path, base_dir):
    """True when any path component (relative to base_dir) is a known junk dir."""
    try:
        rel = os.path.relpath(file_path, base_dir)
    except Exception:
        return False
    parts = [p.lower() for p in rel.split(os.sep)]
    for p in parts[:-1]:
        if p in NON_CONVERSATION_DIRS:
            return True
    return False


def _estimate_bytes(base_dirs, exts=CONVERSATION_EXTS):
    """
    Size of conversation-like files under ``base_dirs``, skipping junk dirs.

    Returns (bytes, file_count). This is a *fallback* for tools that keep no
    usage ledger; prefer get_usage_ledger().
    """
    total_bytes = 0
    count = 0
    for base in base_dirs:
        if not base or not os.path.isdir(base):
            continue
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d.lower() not in NON_CONVERSATION_DIRS]
            for f in files:
                if not f.lower().endswith(exts):
                    continue
                fp = os.path.join(root, f)
                if _is_non_conversation(fp, base):
                    continue
                try:
                    total_bytes += os.path.getsize(fp)
                    count += 1
                except Exception:
                    continue
    return total_bytes, count


def _estimate_tokens(base_dirs, exts=CONVERSATION_EXTS):
    b, n = _estimate_bytes(base_dirs, exts)
    return int(b / CHARS_PER_TOKEN), n


# ===========================================================================
# VERIFIED path - real usage ledger
# ===========================================================================
#
# A ledger source is a directory tree of newline-delimited JSON where each line
# may carry an API usage record. Parsing is incremental: files are append-only,
# so only the bytes after the last consumed offset are read, and the aggregate
# is carried forward. That keeps a full re-scan cheap even though the HUD polls
# continuously.

LEDGER_TTL_SECONDS = 60
_ledger_cache = {"ts": 0.0, "data": None, "files": {}, "aggs": {}}


def _day_from_timestamp(ts):
    """Epoch seconds/milliseconds or ISO-8601 string -> 'YYYY-MM-DD'."""
    if ts is None:
        return None
    try:
        if isinstance(ts, (int, float)):
            v = float(ts)
            if v > 1e11:          # milliseconds
                v /= 1000.0
            if v <= 0:
                return None
            return datetime.fromtimestamp(v).strftime("%Y-%m-%d")
        s = str(ts).strip()
        if not s:
            return None
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(s).strftime("%Y-%m-%d")
        except ValueError:
            return s[:10]
    except Exception:
        return None


def _norm_usage(u):
    """
    Normalise a usage record from any provider into
    (total, input, output, cached, reasoning). Returns None when unusable.

    Handles both camelCase (WorkBuddy / OpenAI-style) and snake_case
    (Claude Code) field names.
    """
    if not isinstance(u, dict):
        return None

    def pick(*names):
        for n in names:
            v = u.get(n)
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)):
                return int(v)
        return 0

    inp = pick("inputTokens", "input_tokens", "prompt_tokens", "promptTokens")
    out = pick("outputTokens", "output_tokens", "completion_tokens", "completionTokens")
    total = pick("totalTokens", "total_tokens")
    cached = pick("cached_tokens", "cachedTokens", "cache_read_input_tokens")

    # Some providers nest the cache figure in a details array.
    for key in ("inputTokensDetails", "input_tokens_details", "prompt_tokens_details"):
        det = u.get(key)
        if isinstance(det, list) and det and isinstance(det[0], dict):
            cached += int(det[0].get("cached_tokens") or det[0].get("cachedTokens") or 0)
        elif isinstance(det, dict):
            cached += int(det.get("cached_tokens") or det.get("cachedTokens") or 0)

    reason = pick("reasoning_tokens", "reasoningTokens")
    for key in ("outputTokensDetails", "output_tokens_details", "completion_tokens_details"):
        det = u.get(key)
        if isinstance(det, list) and det and isinstance(det[0], dict):
            reason += int(det[0].get("reasoning_tokens") or det[0].get("reasoningTokens") or 0)
        elif isinstance(det, dict):
            reason += int(det.get("reasoning_tokens") or det.get("reasoningTokens") or 0)

    if total <= 0:
        total = inp + out
    if total <= 0:
        return None
    if cached > inp:
        cached = inp
    return total, inp, out, cached, reason


def _extract_usage_records(obj):
    """
    Return (usage_dict, timestamp) for ONE decoded JSONL line, or None.

    Exactly one record per line is returned, and that matters: WorkBuddy writes
    the same API usage twice on the same line - once as ``providerData.usage``
    (camelCase, with cached/reasoning detail) and once as ``message.usage``
    (snake_case, same values). Verified on the reference machine: of 2637 lines
    carrying both, all 2637 carried identical figures. Reading both doubled the
    reported total from 421.2 M to 843.7 M.

    Only these known locations are inspected on purpose. Transcripts also embed
    full session snapshots, and walking the whole object recursively would count
    the same request many times over.
    """
    for container_key in ("providerData", "message"):
        container = obj.get(container_key)
        if isinstance(container, dict):
            u = container.get("usage")
            if isinstance(u, dict):
                return u, obj.get("timestamp")
    # OpenAI Responses / Codex style explicit token_count events.
    if obj.get("type") == "token_count" and isinstance(obj.get("payload"), dict):
        info = obj["payload"].get("info")
        if isinstance(info, dict):
            u = info.get("total_token_usage") or info.get("last_token_usage")
            if isinstance(u, dict):
                return u, obj.get("timestamp")
    return None


def _new_agg():
    return {
        "total": 0, "input": 0, "output": 0, "cached": 0, "reasoning": 0,
        "messages": 0, "days": {}, "day_output": {},
    }


def _consume_file(path, start_offset, agg):
    """
    Parse the bytes of ``path`` appended since ``start_offset`` into ``agg``.
    Returns the new offset. Only complete lines are consumed, so a file that is
    being appended to right now never yields a half-parsed record.
    """
    try:
        size = os.path.getsize(path)
    except Exception:
        return start_offset
    if size < start_offset:
        start_offset = 0          # file was truncated or rewritten
    if size == start_offset:
        return start_offset

    try:
        with open(path, "rb") as f:
            f.seek(start_offset)
            chunk = f.read(size - start_offset)
    except Exception:
        return start_offset

    last_nl = chunk.rfind(b"\n")
    if last_nl == -1:
        return start_offset
    consumed = chunk[: last_nl + 1]
    new_offset = start_offset + last_nl + 1

    for raw in consumed.split(b"\n"):
        if not raw.strip():
            continue
        # Cheap pre-filter: the overwhelming majority of transcript lines carry
        # no usage block, and json.loads is by far the most expensive step here.
        if b"usage" not in raw and b"token_count" not in raw:
            continue
        try:
            obj = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        hit = _extract_usage_records(obj)
        if hit is None:
            continue
        u, ts = hit
        n = _norm_usage(u)
        if n is None:
            continue
        total, inp, out, cached, reason = n
        agg["total"] += total
        agg["input"] += inp
        agg["output"] += out
        agg["cached"] += cached
        agg["reasoning"] += reason
        agg["messages"] += 1
        day = _day_from_timestamp(ts)
        if day:
            agg["days"][day] = agg["days"].get(day, 0) + total
            agg["day_output"][day] = agg["day_output"].get(day, 0) + out
    return new_offset


# Ledger sources: name -> (base dirs, filename filter)
def _ledger_source_dirs():
    home = os.environ.get("USERPROFILE", "") or os.path.expanduser("~")
    appdata = os.environ.get("APPDATA", "")
    localappdata = os.environ.get("LOCALAPPDATA", "")
    return {
        "workbuddy": [
            os.path.join(home, ".workbuddy", "projects"),
            os.path.join(appdata, "WorkBuddy", "projects"),
            os.path.join(localappdata, "WorkBuddy", "projects"),
        ],
        "claude": [os.path.join(home, ".claude", "projects")],
        "codex": [
            os.path.join(home, ".codex", "sessions"),
            os.path.join(home, ".codex", "archived_sessions"),
        ],
    }


def get_usage_ledger(force=False):
    """
    Real per-request token usage, aggregated per source.

    Returns {'sources': {name: agg}, 'files': {path: offset}} where each agg has
    total/input/output/cached/reasoning/messages and per-day dicts.

    The aggregation is carried forward in ``_ledger_cache['aggs']`` and only the
    bytes appended since the previous call are parsed, so a poll costs one
    os.stat per transcript rather than a re-read of the whole history.

    Any change that a pure "append the new bytes" model cannot express - a file
    that shrank, or one that disappeared - invalidates the cache and forces a
    clean rebuild. Getting this wrong is how you silently double count or lose
    history, so the cheap path is only taken when it is provably safe.
    """
    import time as _time

    now = _time.time()
    if (
        not force
        and _ledger_cache["data"] is not None
        and (now - _ledger_cache["ts"]) < LEDGER_TTL_SECONDS
    ):
        return _ledger_cache["data"]

    offsets = _ledger_cache["files"]
    aggs = _ledger_cache["aggs"]

    def rebuild():
        offsets.clear()
        aggs.clear()

    # ---- 1. a tracked file that shrank or vanished invalidates everything ----
    for fp, off in list(offsets.items()):
        try:
            if os.path.getsize(fp) < off:
                rebuild()
                break
        except OSError:
            rebuild()
            break

    # Consistency guard: an accumulated total with no offsets to justify it is a
    # contradictory state (it would be re-added to a full re-parse). Only the
    # empty-offsets + non-empty-aggs combination is reset, so a normal cold start
    # is unaffected.
    if not offsets and aggs:
        aggs.clear()

    # ---- 2. enumerate the current transcript files (cheap: stat only) -------
    sources = {}
    seen = set()
    for name, bases in _ledger_source_dirs().items():
        paths = []
        for base in bases:
            if not base or not os.path.isdir(base):
                continue
            for root, subdirs, files in os.walk(base):
                subdirs[:] = [d for d in subdirs if d.lower() not in NON_CONVERSATION_DIRS]
                for f in files:
                    if f.lower().endswith((".jsonl", ".json")):
                        paths.append(os.path.join(root, f))
        if paths:
            sources[name] = paths
            seen.update(paths)

    # A previously seen file is gone -> its contribution can only be undone by
    # rebuilding, since the aggregate is a plain running sum.
    if any(fp not in seen for fp in offsets):
        rebuild()

    # ---- 3. consume only the appended bytes --------------------------------
    for name, paths in sources.items():
        agg = aggs.setdefault(name, _new_agg())
        for fp in paths:
            offsets[fp] = _consume_file(fp, offsets.get(fp, 0), agg)

    data = {"sources": aggs, "files": offsets}
    _ledger_cache["ts"] = now
    _ledger_cache["data"] = data
    return data


def _ledger_agg(source_name):
    led = get_usage_ledger()
    return led["sources"].get(source_name)


# ===========================================================================
# Per-tool scanners. Each returns (tokens, status, tier).
# ===========================================================================

def scan_workbuddy():
    agg = _ledger_agg("workbuddy")
    if agg and agg["total"] > 0:
        pct = agg["cached"] / agg["input"] * 100.0 if agg["input"] else 0.0
        return (
            agg["total"],
            f"{agg['messages']} requests from usage log (cache {pct:.0f}%)",
            TIER_VERIFIED,
        )
    # No usage ledger available -> fall back to conversation files only.
    home = os.environ.get("USERPROFILE", "")
    appdata = os.environ.get("APPDATA", "")
    localappdata = os.environ.get("LOCALAPPDATA", "")
    dirs = [
        os.path.join(home, ".workbuddy", "projects"),
        os.path.join(appdata, "WorkBuddy", "projects"),
        os.path.join(localappdata, "WorkBuddy", "projects"),
    ]
    tok, n = _estimate_tokens(dirs, exts=(".jsonl", ".json"))
    if n:
        return tok, f"{n} transcript file(s), estimated from size", TIER_ESTIMATED
    return 0, "Not found", TIER_UNAVAILABLE


def scan_claude_code():
    agg = _ledger_agg("claude")
    if agg and agg["total"] > 0:
        return (
            agg["total"],
            f"{agg['messages']} requests from usage log",
            TIER_VERIFIED,
        )
    home = os.environ.get("USERPROFILE", "")
    claude_dir = os.path.join(home, ".claude")
    if not os.path.isdir(claude_dir):
        return 0, "Not found", TIER_UNAVAILABLE
    tok, n = _estimate_tokens([claude_dir], exts=(".jsonl", ".json"))
    if n:
        return tok, f"{n} file(s), estimated from size", TIER_ESTIMATED
    return 0, "Not found", TIER_UNAVAILABLE


def scan_codex_cli():
    agg = _ledger_agg("codex")
    if agg and agg["total"] > 0:
        return agg["total"], f"{agg['messages']} token_count events", TIER_VERIFIED
    home = os.environ.get("USERPROFILE", "")
    base = os.path.join(home, ".codex")
    if not os.path.isdir(base):
        return 0, "Not found", TIER_UNAVAILABLE
    tok, n = _estimate_tokens([base], exts=(".jsonl", ".json"))
    if n:
        return tok, f"{n} file(s), estimated from size", TIER_ESTIMATED
    return 0, "Not found", TIER_UNAVAILABLE


def scan_antigravity():
    home = os.environ.get("USERPROFILE", "")
    brain_dir = os.path.join(home, ".gemini", "antigravity", "brain")
    if not os.path.isdir(brain_dir):
        return 0, "Not found", TIER_UNAVAILABLE
    # transcripts live at <brain>/<id>/.system_generated/logs/transcript.jsonl
    total_bytes = 0
    count = 0
    try:
        for folder in os.listdir(brain_dir):
            t_file = os.path.join(
                brain_dir, folder, ".system_generated", "logs", "transcript.jsonl"
            )
            if os.path.exists(t_file):
                total_bytes += os.path.getsize(t_file)
                count += 1
    except Exception as e:
        return 0, str(e)[:80], TIER_UNAVAILABLE
    if not count:
        return 0, "Not found", TIER_UNAVAILABLE
    return int(total_bytes / CHARS_PER_TOKEN), f"{count} conversations (est. from size)", TIER_ESTIMATED


def _scan_vscode_state_db(db_paths, key_like, label):
    """Shared reader for the Cursor / Windsurf / Trae VSCode-style state.vscdb."""
    for db_path in db_paths:
        if not os.path.exists(db_path):
            continue
        total_chars = 0
        blocks = 0
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            try:
                c = conn.cursor()
                c.execute(
                    "SELECT key, value FROM ItemTable WHERE " + " OR ".join(
                        [f"key LIKE '{k}'" for k in key_like]
                    )
                )
                for _, val in c.fetchall():
                    if isinstance(val, (str, bytes)):
                        total_chars += len(val)
                        blocks += 1
            finally:
                conn.close()
        except Exception:
            # Fall back to a plain connection for older sqlite builds.
            try:
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                c.execute(
                    "SELECT key, value FROM ItemTable WHERE " + " OR ".join(
                        [f"key LIKE '{k}'" for k in key_like]
                    )
                )
                for _, val in c.fetchall():
                    if isinstance(val, (str, bytes)):
                        total_chars += len(val)
                        blocks += 1
                conn.close()
            except Exception as e:
                return 0, str(e)[:80], TIER_UNAVAILABLE
        if blocks:
            return int(total_chars / CHARS_PER_TOKEN), f"{blocks} {label} blocks (est.)", TIER_ESTIMATED
    return 0, "Not found", TIER_UNAVAILABLE


def scan_cursor():
    appdata = os.environ.get("APPDATA", "")
    return _scan_vscode_state_db(
        [os.path.join(appdata, "Cursor", "User", "globalStorage", "state.vscdb")],
        ["%chatdata%", "%composerChatViewPane%", "%aiCodeTracking%"],
        "chat",
    )


def scan_windsurf():
    appdata = os.environ.get("APPDATA", "")
    return _scan_vscode_state_db(
        [
            os.path.join(appdata, "Windsurf", "User", "globalStorage", "state.vscdb"),
            os.path.join(appdata, "Code - Windsurf", "User", "globalStorage", "state.vscdb"),
        ],
        ["%chat%", "%cascade%", "%ai%"],
        "cascade",
    )


def scan_trae():
    appdata = os.environ.get("APPDATA", "")
    return _scan_vscode_state_db(
        [
            os.path.join(appdata, "Trae", "User", "globalStorage", "state.vscdb"),
            os.path.join(appdata, "trae", "User", "globalStorage", "state.vscdb"),
        ],
        ["%chat%", "%ai%", "%trae%"],
        "chat",
    )


def scan_vscode_cline():
    appdata = os.environ.get("APPDATA", "")
    code_dir = os.path.join(appdata, "Code", "User", "globalStorage")
    if not os.path.isdir(code_dir):
        return 0, "Not found", TIER_UNAVAILABLE
    targets = []
    try:
        for item in os.listdir(code_dir):
            low = item.lower()
            if "cline" in low or "roo" in low or "continue" in low:
                targets.append(os.path.join(code_dir, item))
    except Exception as e:
        return 0, str(e)[:80], TIER_UNAVAILABLE
    tok, n = _estimate_tokens(targets, exts=(".json", ".jsonl", ".txt"))
    if n:
        return tok, f"{n} extension file(s) (est. from size)", TIER_ESTIMATED
    return 0, "Not found", TIER_UNAVAILABLE


def scan_github_copilot():
    home = os.environ.get("USERPROFILE", "")
    copilot_dir = os.path.join(home, ".copilot")
    session_state = os.path.join(copilot_dir, "session-state")
    if not os.path.isdir(session_state):
        return 0, "Not found", TIER_UNAVAILABLE
    total_bytes = 0
    count = 0
    try:
        for folder in os.listdir(session_state):
            ev_file = os.path.join(session_state, folder, "events.jsonl")
            if os.path.exists(ev_file):
                total_bytes += os.path.getsize(ev_file)
                count += 1
    except Exception as e:
        return 0, str(e)[:80], TIER_UNAVAILABLE
    if not count:
        return 0, "Not found", TIER_UNAVAILABLE
    return int(total_bytes / CHARS_PER_TOKEN), f"{count} sessions (est. from size)", TIER_ESTIMATED


def scan_doubaowork():
    localappdata = os.environ.get("LOCALAPPDATA", "")
    user_data = os.path.join(localappdata, "DoubaoWork", "User Data")
    if not os.path.isdir(user_data):
        return 0, "Not found", TIER_UNAVAILABLE
    total_bytes = 0
    file_count = 0
    try:
        for root, dirs, files in os.walk(user_data):
            low = root.lower()
            if "doubaowork-chat" in low or ("doubaowork" in low and "indexeddb" in low):
                for f in files:
                    if f.endswith((".ldb", ".log", ".blob")):
                        total_bytes += os.path.getsize(os.path.join(root, f))
                        file_count += 1
    except Exception as e:
        return 0, str(e)[:80], TIER_UNAVAILABLE
    if not file_count:
        return 0, "Not found", TIER_UNAVAILABLE
    return int(total_bytes / CHARS_PER_TOKEN), f"{file_count} db files (est. from size)", TIER_ESTIMATED


def _scan_domestic_home_dirs(candidates, label):
    total_bytes = 0
    scanned = 0
    for c_dir in candidates:
        if not os.path.isdir(c_dir):
            continue
        for root, dirs, files in os.walk(c_dir):
            dirs[:] = [d for d in dirs if d.lower() not in NON_CONVERSATION_DIRS]
            for f in files:
                if f.lower().endswith((".db", ".json", ".jsonl", ".txt")):
                    try:
                        total_bytes += os.path.getsize(os.path.join(root, f))
                        scanned += 1
                    except Exception:
                        continue
    if scanned:
        return int(total_bytes / CHARS_PER_TOKEN), f"{scanned} file(s) ({label}, est.)", TIER_ESTIMATED
    return 0, "Not found", TIER_UNAVAILABLE


def scan_alibaba_qoder():
    home = os.environ.get("USERPROFILE", "")
    appdata = os.environ.get("APPDATA", "")
    return _scan_domestic_home_dirs(
        [
            os.path.join(home, ".qoder"),
            os.path.join(home, ".quadar"),
            os.path.join(home, ".lingma"),
            os.path.join(appdata, "Qoder"),
            os.path.join(appdata, "quadar"),
            os.path.join(appdata, "Code", "User", "globalStorage", "aliyun.tongyi-lingma"),
        ],
        "Qoder",
    )


def scan_baidu_comate():
    home = os.environ.get("USERPROFILE", "")
    appdata = os.environ.get("APPDATA", "")
    return _scan_domestic_home_dirs(
        [
            os.path.join(home, ".comate"),
            os.path.join(appdata, "comate"),
            os.path.join(appdata, "Code", "User", "globalStorage", "baidu.comate"),
        ],
        "Comate",
    )


def scan_codegeex():
    home = os.environ.get("USERPROFILE", "")
    appdata = os.environ.get("APPDATA", "")
    return _scan_domestic_home_dirs(
        [
            os.path.join(home, ".codegeex"),
            os.path.join(appdata, "CodeGeeX"),
            os.path.join(appdata, "Code", "User", "globalStorage", "aminer.codegeex"),
        ],
        "CodeGeeX",
    )


# (display name, status key, ledger source name, scanner)
SCANNER_TABLE = [
    ("WorkBuddy", "workbuddy", "workbuddy", scan_workbuddy),
    ("ClaudeCode", "claude", "claude", scan_claude_code),
    ("CodexCLI", "codex", "codex", scan_codex_cli),
    ("Antigravity", "antigravity", None, scan_antigravity),
    ("Cursor", "cursor", None, scan_cursor),
    ("Windsurf", "windsurf", None, scan_windsurf),
    ("Trae", "trae", None, scan_trae),
    ("Copilot", "copilot", None, scan_github_copilot),
    ("Qoder", "qoder", None, scan_alibaba_qoder),
    ("Comate", "comate", None, scan_baidu_comate),
    ("CodeGeeX", "codegeex", None, scan_codegeex),
    ("DoubaoWork", "doubaowork", None, scan_doubaowork),
    ("VSCode", "vscode", None, scan_vscode_cline),
]

# Kept so existing callers/tests that iterated the old names still resolve.
scan_workbuddy.__name__ = "scan_workbuddy"


# ===========================================================================
# Daily history
# ===========================================================================

def _migrate_days(raw_days):
    """Accept both the legacy {start_tokens, today_burned} and the new shape."""
    days = {}
    for d_str, info in (raw_days or {}).items():
        if not isinstance(info, dict):
            continue
        tok = info.get("tokens")
        if tok is None:
            tok = info.get("today_burned", 0)
        try:
            days[d_str] = {
                "tokens": int(tok or 0),
                "output": int(info.get("output") or 0),
                "verified": bool(info.get("verified", False)),
            }
        except Exception:
            continue
    return days


def _read_history():
    data = {"days": {}}
    if os.path.exists(history_file()):
        try:
            with open(history_file(), "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {"days": {}}
    days = _migrate_days(data.get("days"))
    observed = data.get("observed") if isinstance(data.get("observed"), dict) else {}
    return days, observed, data


def _compute_streak(days, today):
    """
    Consecutive days with real burn, counting backwards.

    A day with zero burn only breaks the streak once it is over - otherwise the
    streak would appear to reset every midnight before the first request of the
    day.
    """
    d = today
    if days.get(d.isoformat(), {}).get("tokens", 0) <= 0:
        d = d - timedelta(days=1)
    n = 0
    for _ in range(3650):
        if days.get(d.isoformat(), {}).get("tokens", 0) > 0:
            n += 1
            d = d - timedelta(days=1)
        else:
            break
    return n


def record_daily_history(observed_total, force=False):
    """
    Merge the real usage ledger into daily_history.json and return
    (streak, today_burned, periods, recent_days, source).

    Both data paths are kept:
      * ledger days (timestamped real usage) are authoritative;
      * for days the ledger does not cover, the observed delta between two
        scans of a running HUD is used so a machine without a usage log still
        gets a daily figure.
    """
    today = date.today()
    today_str = today.isoformat()
    days, observed, raw = _read_history()

    # ---- 1. merge the real ledger -----------------------------------------
    led = get_usage_ledger(force=force)
    ledger_total = 0
    ledger_days = {}
    verified_sources = 0
    for name, agg in led["sources"].items():
        if agg["total"] <= 0:
            continue
        verified_sources += 1
        ledger_total += agg["total"]
        for d_str, tok in agg["days"].items():
            entry = ledger_days.setdefault(d_str, {"tokens": 0, "output": 0})
            entry["tokens"] += tok
            entry["output"] += agg["day_output"].get(d_str, 0)

    for d_str, info in ledger_days.items():
        cur = days.setdefault(d_str, {"tokens": 0, "output": 0, "verified": False})
        # max() rather than assignment: an incremental parse must never reduce a
        # figure that an earlier full parse already recorded.
        cur["tokens"] = max(cur["tokens"], int(info["tokens"]))
        cur["output"] = max(cur["output"], int(info["output"]))
        cur["verified"] = True

    # ---- 2. observed-delta fallback for uncovered days --------------------
    use_fallback = ledger_total <= 0
    prev_total = raw.get("last_total")
    if not isinstance(prev_total, int):
        prev_total = observed_total
    if use_fallback:
        cur = days.setdefault(today_str, {"tokens": 0, "output": 0, "verified": False})
        if not cur["verified"]:
            start = raw.get("today_start_total", prev_total)
            cur["tokens"] = max(cur["tokens"], max(0, observed_total - start))

    # ---- 3. periods -------------------------------------------------------
    today_burned = days.get(today_str, {}).get("tokens", 0)
    week_burned = 0
    month_burned = 0
    for d_str, info in days.items():
        try:
            d_obj = date.fromisoformat(d_str)
        except Exception:
            continue
        burn = int(info.get("tokens") or 0)
        if 0 <= (today - d_obj).days < 7:
            week_burned += burn
        if d_obj.year == today.year and d_obj.month == today.month:
            month_burned += burn

    total_tokens = ledger_total if ledger_total > 0 else observed_total
    periods = {
        "day": today_burned,
        "week": week_burned,
        "month": month_burned,
        "total": total_tokens,
    }

    # ---- 4. recent series for the poster ----------------------------------
    recent_days = []
    for d_str in sorted(days.keys())[-31:]:
        try:
            d_obj = date.fromisoformat(d_str)
        except Exception:
            continue
        if not (0 <= (today - d_obj).days <= 30):
            continue
        recent_days.append({
            "date": d_str,
            "burned": int(days[d_str].get("tokens") or 0),
            "output": int(days[d_str].get("output") or 0),
            "verified": bool(days[d_str].get("verified", False)),
        })

    # ---- 5. persist -------------------------------------------------------
    out = {
        "days": days,
        "current_streak": _compute_streak(days, today),
        "last_active_date": today_str,
        "last_total": observed_total,
        "schema": 2,
    }
    if use_fallback:
        out["today_start_total"] = raw.get("today_start_total", prev_total)
        out["last_total"] = observed_total
    else:
        out.pop("today_start_total", None)
    try:
        with open(history_file(), "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    source = "usage-ledger" if ledger_total > 0 else "observed-delta"
    return out["current_streak"], today_burned, periods, recent_days, source


# ---------------------------------------------------------------------------
# Cost model. Cache-aware, because a flat per-token rate is meaningless when
# 98.5 % of input is served from the provider's prompt cache.
# ---------------------------------------------------------------------------
def estimate_cost(ledger_totals, pricing):
    """USD estimate from the ledger's own input/output/cached split."""
    inp = int(ledger_totals.get("input") or 0)
    out = int(ledger_totals.get("output") or 0)
    cached = min(int(ledger_totals.get("cached") or 0), inp)
    fresh = max(0, inp - cached)
    p_in = float(pricing.get("input_per_m", 2.94))
    p_cache = float(pricing.get("cached_input_per_m", 0.294))
    p_out = float(pricing.get("output_per_m", 11.76))
    usd = (fresh * p_in + cached * p_cache + out * p_out) / 1_000_000.0
    return round(usd, 2)


# ---------------------------------------------------------------------------
# Scan cache.
# `get_full_stats()` walks a dozen directories on the real filesystem, including
# large IDE caches (measured ~1-3 s per call on a developer machine). The HUD
# polls it every 1.2 s, which caused continuous, pointless disk churn.
# Results are cached for SCAN_TTL_SECONDS; pass force=True to bypass.
# ---------------------------------------------------------------------------
SCAN_TTL_SECONDS = 15
_scan_cache = {"ts": 0.0, "data": None}


def get_full_stats(force=False):
    import time as _time
    now = _time.time()
    if (
        not force
        and _scan_cache["data"] is not None
        and (now - _scan_cache["ts"]) < SCAN_TTL_SECONDS
    ):
        return _scan_cache["data"]

    stats = _scan_all(force=force)
    _scan_cache["ts"] = now
    _scan_cache["data"] = stats
    return stats


def _scan_all(force=False):
    cfg = load_config()
    # `force` MUST be threaded through: the ledger has its own (longer) TTL, and
    # without this a forced refresh returned a fresh scan wrapped around a stale
    # ledger, so "refresh" silently showed up-to-60-second-old numbers.
    ledger = get_usage_ledger(force=force)

    tools = {}
    statuses = {}
    tiers = {}
    verified_total = 0
    estimated_total = 0

    for display, status_key, ledger_src, fn in SCANNER_TABLE:
        try:
            tok, status, tier = fn()
        except Exception as e:                       # never let one tool break all
            tok, status, tier = 0, f"{type(e).__name__}: {e}"[:80], TIER_UNAVAILABLE
        tok = int(tok or 0)
        tools[display] = tok
        statuses[status_key] = status
        tiers[display] = tier
        if tier == TIER_VERIFIED:
            verified_total += tok
        elif tier == TIER_ESTIMATED:
            estimated_total += tok

    # Manual entries (used to be "一键伪造" buttons; now config-only).
    web_tok = int(cfg.get("web_tokens", 0) or 0)
    api_tok = int(cfg.get("api_tokens", 0) or 0)
    if web_tok:
        tools["Web"] = web_tok
        tiers["Web"] = TIER_ESTIMATED
        statuses["web"] = "manual entry in config.json"
        estimated_total += web_tok
    if api_tok:
        tools["API"] = api_tok
        tiers["API"] = TIER_ESTIMATED
        statuses["api"] = "manual entry in config.json"
        estimated_total += api_tok

    total_tokens = verified_total + estimated_total

    # Ledger-wide totals (not just the tools in SCANNER_TABLE) for the cost model.
    agg_all = {"input": 0, "output": 0, "cached": 0, "reasoning": 0, "messages": 0, "total": 0}
    for agg in ledger["sources"].values():
        for k in agg_all:
            agg_all[k] += int(agg.get(k) or 0)
    if agg_all["total"] <= 0:
        agg_all["total"] = verified_total

    est_cost_usd = estimate_cost(agg_all, cfg.get("pricing", {}))
    cache_pct = (agg_all["cached"] / agg_all["input"] * 100.0) if agg_all["input"] else 0.0

    streak, today_burned, periods, recent_days, series_source = record_daily_history(
        total_tokens, force=force
    )

    # Period totals must be built from the real daily series when we have one.
    if series_source == "usage-ledger":
        periods = dict(periods)
        periods["total"] = total_tokens

    return {
        "nickname": cfg.get("nickname", "CyberDev"),
        "total_tokens": total_tokens,
        "verified_tokens": verified_total,
        "estimated_tokens": estimated_total,
        "est_cost_usd": est_cost_usd,
        "pricing": cfg.get("pricing", {}),
        "ledger": {
            "input": agg_all["input"],
            "output": agg_all["output"],
            "cached": agg_all["cached"],
            "reasoning": agg_all["reasoning"],
            "requests": agg_all["messages"],
            "cache_hit_pct": round(cache_pct, 1),
        },
        "data_quality": {
            "verified_tokens": verified_total,
            "estimated_tokens": estimated_total,
            "verified_pct": round(verified_total / total_tokens * 100.0, 1) if total_tokens else 0.0,
            "tiers": tiers,
            "series_source": series_source,
            "has_any_data": total_tokens > 0,
        },
        "streak_days": streak,
        "today_burned": today_burned,
        "periods": periods,
        "recent_days": recent_days,
        "tools": tools,
        "statuses": statuses,
    }


if __name__ == "__main__":
    stats = get_full_stats(force=True)
    print("Token scanner (verified / estimated split)")
    print("  total     : %15s" % f"{stats['total_tokens']:,}")
    print("  verified  : %15s" % f"{stats['verified_tokens']:,}")
    print("  estimated : %15s" % f"{stats['estimated_tokens']:,}")
    print("  requests  : %15s" % f"{stats['ledger']['requests']:,}")
    print("  cache hit : %15s%%" % stats["ledger"]["cache_hit_pct"])
    print("  est cost  : $%.2f" % stats["est_cost_usd"])
    print("  series    : %s" % stats["data_quality"]["series_source"])
    print()
    print("  %-14s %16s  %-11s %s" % ("tool", "tokens", "tier", "status"))
    for name, tok in sorted(stats["tools"].items(), key=lambda kv: -kv[1]):
        print("  %-14s %16s  %-11s %s" % (
            name, f"{tok:,}", stats["data_quality"]["tiers"].get(name, "?"),
            stats["statuses"].get(name.lower(), ""),
        ))
