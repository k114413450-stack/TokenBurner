# -*- coding: utf-8 -*-
# Multi-Tool Token Scanner Engine with Antigravity, Cursor, and Daily History
import os
import json
import sqlite3
from datetime import datetime, date, timedelta

try:
    from app_paths import get_app_data_dir
except ImportError:
    from src.app_paths import get_app_data_dir

DATA_DIR = get_app_data_dir()
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
HISTORY_FILE = os.path.join(DATA_DIR, "daily_history.json")

def load_config():
    default_cfg = {
        "nickname": "CyberDev",
        "web_tokens": 0,
        "api_tokens": 0,
        "hourly_rate_tokens": 12000
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_cfg.update(data)
        except Exception:
            pass
    return default_cfg

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
    except Exception:
        pass

def scan_antigravity():
    home = os.environ.get("USERPROFILE", "")
    brain_dir = os.path.join(home, ".gemini", "antigravity", "brain")
    if not os.path.exists(brain_dir):
        return 0, "Not found"
    
    total_bytes = 0
    count = 0
    try:
        for folder in os.listdir(brain_dir):
            t_file = os.path.join(brain_dir, folder, ".system_generated", "logs", "transcript.jsonl")
            if os.path.exists(t_file):
                total_bytes += os.path.getsize(t_file)
                count += 1
        est_tokens = int(total_bytes / 3.5)
        return est_tokens, f"{count} conversations"
    except Exception as e:
        return 0, str(e)

def scan_cursor():
    appdata = os.environ.get("APPDATA", "")
    db_path = os.path.join(appdata, "Cursor", "User", "globalStorage", "state.vscdb")
    if not os.path.exists(db_path):
        return 0, "Not found"
    
    total_chars = 0
    blocks = 0
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT key, value FROM ItemTable WHERE key LIKE '%chatdata%' OR key LIKE '%composerChatViewPane%' OR key LIKE '%aiCodeTracking%';")
        rows = c.fetchall()
        for _, val in rows:
            if isinstance(val, (str, bytes)):
                total_chars += len(val)
                blocks += 1
        conn.close()
        est_tokens = int(total_chars / 3.5)
        return est_tokens, f"{blocks} blocks scanned"
    except Exception as e:
        return 0, str(e)

def scan_claude_code():
    home = os.environ.get("USERPROFILE", "")
    claude_dir = os.path.join(home, ".claude")
    if not os.path.exists(claude_dir):
        return 0, "Not found"
    
    total_chars = 0
    try:
        for root, _, files in os.walk(claude_dir):
            for file in files:
                if file.endswith((".json", ".log", ".txt")):
                    fp = os.path.join(root, file)
                    total_chars += os.path.getsize(fp)
        return int(total_chars / 3.5), "Scanned ~/.claude"
    except Exception as e:
        return 0, str(e)

def scan_vscode_cline():
    appdata = os.environ.get("APPDATA", "")
    code_dir = os.path.join(appdata, "Code", "User", "globalStorage")
    if not os.path.exists(code_dir):
        return 0, "Not found"
    
    total_chars = 0
    try:
        for item in os.listdir(code_dir):
            if "cline" in item.lower() or "roo" in item.lower() or "continue" in item.lower():
                target_dir = os.path.join(code_dir, item)
                for root, _, files in os.walk(target_dir):
                    for file in files:
                        if file.endswith((".json", ".db", ".log")):
                            fp = os.path.join(root, file)
                            total_chars += os.path.getsize(fp)
        return int(total_chars / 3.5), "Scanned Code extensions"
    except Exception as e:
        return 0, str(e)

def scan_github_copilot():
    home = os.environ.get("USERPROFILE", "")
    copilot_dir = os.path.join(home, ".copilot")
    if not os.path.exists(copilot_dir):
        return 0, "Not found"
    
    total_bytes = 0
    count = 0
    try:
        session_state_dir = os.path.join(copilot_dir, "session-state")
        if os.path.exists(session_state_dir):
            for folder in os.listdir(session_state_dir):
                s_dir = os.path.join(session_state_dir, folder)
                if os.path.isdir(s_dir):
                    ev_file = os.path.join(s_dir, "events.jsonl")
                    if os.path.exists(ev_file):
                        total_bytes += os.path.getsize(ev_file)
                        count += 1
        est_tokens = int(total_bytes / 3.5)
        return est_tokens, f"{count} sessions"
    except Exception as e:
        return 0, str(e)

def scan_windsurf():
    appdata = os.environ.get("APPDATA", "")
    candidates = [
        os.path.join(appdata, "Windsurf", "User", "globalStorage", "state.vscdb"),
        os.path.join(appdata, "Code - Windsurf", "User", "globalStorage", "state.vscdb")
    ]
    for db_path in candidates:
        if os.path.exists(db_path):
            total_chars = 0
            blocks = 0
            try:
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                c.execute("SELECT key, value FROM ItemTable WHERE key LIKE '%chat%' OR key LIKE '%cascade%' OR key LIKE '%ai%';")
                rows = c.fetchall()
                for _, val in rows:
                    if isinstance(val, (str, bytes)):
                        total_chars += len(val)
                        blocks += 1
                conn.close()
                est_tokens = int(total_chars / 3.5)
                return est_tokens, f"{blocks} blocks scanned"
            except Exception as e:
                return 0, str(e)
    return 0, "Not found"

def scan_trae():
    appdata = os.environ.get("APPDATA", "")
    candidates = [
        os.path.join(appdata, "Trae", "User", "globalStorage", "state.vscdb"),
        os.path.join(appdata, "trae", "User", "globalStorage", "state.vscdb")
    ]
    for db_path in candidates:
        if os.path.exists(db_path):
            total_chars = 0
            blocks = 0
            try:
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                c.execute("SELECT key, value FROM ItemTable WHERE key LIKE '%chat%' OR key LIKE '%ai%' OR key LIKE '%trae%';")
                rows = c.fetchall()
                for _, val in rows:
                    if isinstance(val, (str, bytes)):
                        total_chars += len(val)
                        blocks += 1
                conn.close()
                est_tokens = int(total_chars / 3.5)
                return est_tokens, f"{blocks} blocks scanned"
            except Exception as e:
                return 0, str(e)
    return 0, "Not found"

def scan_doubaowork():
    localappdata = os.environ.get("LOCALAPPDATA", "")
    user_data = os.path.join(localappdata, "DoubaoWork", "User Data")
    if not os.path.exists(user_data):
        return 0, "Not found"
    total_bytes = 0
    file_count = 0
    try:
        for root, dirs, files in os.walk(user_data):
            if "doubaowork-chat" in root or ("doubaowork" in root and "IndexedDB" in root):
                for f in files:
                    if f.endswith((".ldb", ".log", ".blob")):
                        fp = os.path.join(root, f)
                        total_bytes += os.path.getsize(fp)
                        file_count += 1
        est_tokens = int(total_bytes / 3.5)
        return est_tokens, f"{file_count} db files scanned"
    except Exception as e:
        return 0, str(e)

def scan_workbuddy():
    appdata = os.environ.get("APPDATA", "")
    localappdata = os.environ.get("LOCALAPPDATA", "")
    home = os.environ.get("USERPROFILE", "")
    candidates = [
        os.path.join(appdata, "WorkBuddy"),
        os.path.join(localappdata, "WorkBuddy"),
        os.path.join(home, ".workbuddy")
    ]
    total_bytes = 0
    scanned = 0
    try:
        for c_dir in candidates:
            if os.path.exists(c_dir):
                for root, dirs, files in os.walk(c_dir):
                    for f in files:
                        if f.endswith((".db", ".json", ".jsonl", ".log", ".ldb")):
                            fp = os.path.join(root, f)
                            total_bytes += os.path.getsize(fp)
                            scanned += 1
        if scanned > 0:
            return int(total_bytes / 3.5), f"{scanned} files scanned"
        return 0, "Not found"
    except Exception as e:
        return 0, str(e)

def scan_alibaba_qoder():
    home = os.environ.get("USERPROFILE", "")
    appdata = os.environ.get("APPDATA", "")
    candidates = [
        os.path.join(home, ".qoder"),
        os.path.join(home, ".quadar"),
        os.path.join(home, ".lingma"),
        os.path.join(appdata, "Qoder"),
        os.path.join(appdata, "quadar"),
        os.path.join(appdata, "Code", "User", "globalStorage", "aliyun.tongyi-lingma")
    ]
    total_bytes = 0
    scanned = 0
    try:
        for c_dir in candidates:
            if os.path.exists(c_dir):
                for root, dirs, files in os.walk(c_dir):
                    for f in files:
                        if f.endswith((".db", ".json", ".jsonl", ".log", ".ldb")):
                            fp = os.path.join(root, f)
                            total_bytes += os.path.getsize(fp)
                            scanned += 1
        if scanned > 0:
            return int(total_bytes / 3.5), f"{scanned} files scanned"
        return 0, "Not found"
    except Exception as e:
        return 0, str(e)

def scan_baidu_comate():
    home = os.environ.get("USERPROFILE", "")
    appdata = os.environ.get("APPDATA", "")
    candidates = [
        os.path.join(home, ".comate"),
        os.path.join(appdata, "comate"),
        os.path.join(appdata, "Code", "User", "globalStorage", "baidu.comate")
    ]
    total_bytes = 0
    scanned = 0
    try:
        for c_dir in candidates:
            if os.path.exists(c_dir):
                for root, dirs, files in os.walk(c_dir):
                    for f in files:
                        if f.endswith((".db", ".json", ".jsonl", ".log")):
                            fp = os.path.join(root, f)
                            total_bytes += os.path.getsize(fp)
                            scanned += 1
        if scanned > 0:
            return int(total_bytes / 3.5), f"{scanned} files scanned"
        return 0, "Not found"
    except Exception as e:
        return 0, str(e)

def scan_codegeex():
    home = os.environ.get("USERPROFILE", "")
    appdata = os.environ.get("APPDATA", "")
    candidates = [
        os.path.join(home, ".codegeex"),
        os.path.join(appdata, "CodeGeeX"),
        os.path.join(appdata, "Code", "User", "globalStorage", "aminer.codegeex")
    ]
    total_bytes = 0
    scanned = 0
    try:
        for c_dir in candidates:
            if os.path.exists(c_dir):
                for root, dirs, files in os.walk(c_dir):
                    for f in files:
                        if f.endswith((".db", ".json", ".jsonl", ".log")):
                            fp = os.path.join(root, f)
                            total_bytes += os.path.getsize(fp)
                            scanned += 1
        if scanned > 0:
            return int(total_bytes / 3.5), f"{scanned} files scanned"
        return 0, "Not found"
    except Exception as e:
        return 0, str(e)

def record_daily_history(current_total):
    today_str = date.today().isoformat()
    hist_data = {
        "days": {},
        "current_streak": 1,
        "last_active_date": today_str
    }
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                hist_data = json.load(f)
        except Exception:
            pass

    days = hist_data.get("days", {})
    last_date_str = hist_data.get("last_active_date", today_str)
    streak = hist_data.get("current_streak", 1)

    if today_str not in days:
        if last_date_str:
            try:
                last_d = date.fromisoformat(last_date_str)
                today_d = date.today()
                if today_d - last_d == timedelta(days=1):
                    streak += 1
                elif today_d - last_d > timedelta(days=1):
                    streak = 1
            except Exception:
                streak = 1
        else:
            streak = 1
        days[today_str] = {
            "start_tokens": current_total,
            "latest_tokens": current_total,
            "today_burned": 0
        }
    else:
        start_tok = days[today_str].get("start_tokens", current_total)
        burned = max(0, current_total - start_tok)
        days[today_str]["latest_tokens"] = current_total
        days[today_str]["today_burned"] = burned

    hist_data["days"] = days
    hist_data["current_streak"] = streak
    hist_data["last_active_date"] = today_str

    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(hist_data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    today_burned = days[today_str].get("today_burned", 0)
    
    # Calculate period totals
    today_d = date.today()
    week_burned = 0
    month_burned = 0
    for d_str, d_info in days.items():
        try:
            d_obj = date.fromisoformat(d_str)
            b = d_info.get("today_burned", 0)
            if 0 <= (today_d - d_obj).days < 7:
                week_burned += b
            if d_obj.year == today_d.year and d_obj.month == today_d.month:
                month_burned += b
        except Exception:
            pass

    week_burned = max(week_burned, today_burned)
    month_burned = max(month_burned, today_burned)

    periods = {
        "day": today_burned,
        "week": week_burned,
        "month": month_burned,
        "total": current_total
    }

    return streak, today_burned, periods

def calculate_rank_and_title(total_tokens):
    if total_tokens >= 50000000:
        return 99.8, "Lv.9 灭霸级·算力湮灭者", [("Claude 3.5 Sonnet", 65, "#f97316"), ("DeepSeek-V3", 25, "#06b6d4"), ("GPT-4o", 10, "#10b981")]
    elif total_tokens >= 30000000:
        return 99.4, "Lv.8 算力吞金兽 / 人肉代码焚化炉", [("Claude 3.5 Sonnet", 64, "#f97316"), ("DeepSeek-V3", 24, "#06b6d4"), ("GPT-4o", 12, "#10b981")]
    elif total_tokens >= 15000000:
        return 98.2, "Lv.7 赛博狂魔·架构推演大师", [("Claude 3.5 Sonnet", 55, "#f97316"), ("DeepSeek-V3", 30, "#06b6d4"), ("GPT-4o", 15, "#10b981")]
    elif total_tokens >= 5000000:
        return 94.5, "Lv.6 高阶炼丹师 / 提示词架构师", [("Claude 3.5 Sonnet", 50, "#f97316"), ("DeepSeek-V3", 35, "#06b6d4"), ("GPT-4o", 15, "#10b981")]
    elif total_tokens >= 1000000:
        return 88.0, "Lv.5 赛博学徒 / AI重度探索家", [("Claude 3.5 Sonnet", 40, "#f97316"), ("DeepSeek-V3", 40, "#06b6d4"), ("GPT-4o", 20, "#10b981")]
    else:
        return 60.0, "Lv.3 赛博初生 / 算力点火者", [("GPT-4o", 50, "#10b981"), ("DeepSeek-V3", 30, "#06b6d4"), ("Claude 3.5", 20, "#f97316")]

def get_full_stats():
    cfg = load_config()
    agy_tok, agy_status = scan_antigravity()
    cursor_tok, cursor_status = scan_cursor()
    copilot_tok, copilot_status = scan_github_copilot()
    doubao_tok, doubao_status = scan_doubaowork()
    qoder_tok, qoder_status = scan_alibaba_qoder()
    wb_tok, wb_status = scan_workbuddy()
    comate_tok, comate_status = scan_baidu_comate()
    geex_tok, geex_status = scan_codegeex()
    windsurf_tok, windsurf_status = scan_windsurf()
    trae_tok, trae_status = scan_trae()
    claude_tok, claude_status = scan_claude_code()
    vscode_tok, vscode_status = scan_vscode_cline()
    
    web_tok = cfg.get("web_tokens", 0)
    api_tok = cfg.get("api_tokens", 0)
    
    total_tokens = (
        agy_tok + cursor_tok + copilot_tok + doubao_tok + qoder_tok +
        wb_tok + comate_tok + geex_tok + windsurf_tok + trae_tok +
        claude_tok + vscode_tok + web_tok + api_tok
    )
    est_cost_usd = round(total_tokens * 0.00000294, 2)
    rank_pct, title_badge, models = calculate_rank_and_title(total_tokens)
    
    streak, today_burned, periods = record_daily_history(total_tokens)

    return {
        "nickname": cfg.get("nickname", "CyberDev"),
        "total_tokens": total_tokens,
        "est_cost_usd": est_cost_usd,
        "rank_percent": rank_pct,
        "title_badge": title_badge,
        "models": models,
        "streak_days": streak,
        "today_burned": today_burned,
        "periods": periods,
        "tools": {
            "Antigravity": agy_tok,
            "Copilot": copilot_tok,
            "DoubaoWork": doubao_tok,
            "Cursor": cursor_tok,
            "Qoder": qoder_tok,
            "WorkBuddy": wb_tok,
            "Comate": comate_tok,
            "CodeGeeX": geex_tok,
            "Windsurf": windsurf_tok,
            "Trae": trae_tok,
            "ClaudeCode": claude_tok,
            "VSCode": vscode_tok,
            "Web": web_tok,
            "API": api_tok
        },
        "statuses": {
            "antigravity": agy_status,
            "copilot": copilot_status,
            "doubaowork": doubao_status,
            "cursor": cursor_status,
            "qoder": qoder_status,
            "workbuddy": wb_status,
            "comate": comate_status,
            "codegeex": geex_status,
            "windsurf": windsurf_status,
            "trae": trae_status,
            "claude": claude_status,
            "vscode": vscode_status
        }
    }

if __name__ == "__main__":
    stats = get_full_stats()
    print("Full Token Scanner Result with Domestic AI IDEs:")
    print(f"Total: {stats['total_tokens']:,}, AGY: {stats['tools']['Antigravity']:,}, Copilot: {stats['tools']['Copilot']:,}, DoubaoWork: {stats['tools']['DoubaoWork']:,}, Cursor: {stats['tools']['Cursor']:,}")
