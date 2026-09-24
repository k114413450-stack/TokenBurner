# -*- coding: utf-8 -*-
# TokenBurner 3D Vision Core Runner (WebView2 + Three.js)
import os
import sys
import webview
import random

import json
import time
from datetime import datetime

try:
    from app_paths import get_app_data_dir
except ImportError:
    from src.app_paths import get_app_data_dir

try:
    import winsound
except ImportError:
    winsound = None

def get_bundle_dir():
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

BUNDLE_DIR = get_bundle_dir()
CURRENT_DIR = BUNDLE_DIR
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

try:
    from scanner import get_full_stats, load_config, save_config
    from poster import generate_poster
    from model_detector import ModelDetector
    from ranking_engine import RankingEngine, calculate_level
    from yolo_approver import get_yolo_approver
except ImportError:
    from src.scanner import get_full_stats, load_config, save_config
    from src.poster import generate_poster
    from src.model_detector import ModelDetector
    from src.ranking_engine import RankingEngine, calculate_level
    from src.yolo_approver import get_yolo_approver

_active_window = None

class HudApi:
    def __init__(self):
        self.detector = ModelDetector()
        self.ranking = RankingEngine()
        self.active_model = self.detector.active_model_name
        self.active_tool = self.detector.active_tool
        self.lang = "zh"  # default to Chinese per user request
        self.skin = load_config().get("skin", "eva")
        self.yolo = get_yolo_approver()
        self.start_model_detector_thread()

    def start_model_detector_thread(self):
        import threading
        import time
        import ctypes
        import psutil

        def _loop():
            user32 = ctypes.windll.user32
            pid_val = ctypes.c_ulong()
            while True:
                try:
                    hwnd = user32.GetForegroundWindow()
                    if hwnd:
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_val))
                        proc_name = ""
                        if pid_val.value:
                            try:
                                proc_name = psutil.Process(pid_val.value).name().lower()
                            except Exception:
                                proc_name = ""
                        
                        length = user32.GetWindowTextLengthW(hwnd)
                        title = ""
                        if length > 0:
                            buf = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buf, length + 1)
                            title = buf.value

                        if proc_name and "tokenburner" not in proc_name and "token_burner" not in title.lower():
                            plat, model = self.detector.detect_from_window(title, process_name=proc_name)
                            if model:
                                self.active_model = model
                                self.active_tool = self.detector.active_tool
                except Exception:
                    pass
                time.sleep(1.5)

        threading.Thread(target=_loop, daemon=True).start()

    def get_stats(self):
        stats = get_full_stats()
        total = stats.get("total_tokens", 0)
        lv, pct, in_level, need_level, era_name, title_name = calculate_level(total, lang=self.lang)
        
        my_name = load_config().get("nickname", "CyberDev")
        lb = self.ranking.get_model_leaderboard(self.active_model, total, my_name, lang=self.lang)

        stats["lang"] = self.lang
        stats["skin"] = self.skin
        stats["active_model"] = self.active_model
        stats["active_tool"] = self.active_tool
        stats["level"] = lv
        stats["level_title"] = title_name
        stats["level_pct"] = round(pct * 100.0, 1)
        stats["level_need"] = need_level
        stats["era"] = era_name
        stats["model_rank"] = lb.get("my_rank", 1)
        stats["model_beat"] = lb.get("beat_percentage", 99.0)
        stats["model_leaderboard"] = lb.get("top_entries", [])[:10]
        stats["yolo"] = self.yolo.get_status()
        return stats

    def toggle_yolo(self):
        self.yolo.toggle()
        return self.yolo.get_status()

    def get_yolo_status(self):
        return self.yolo.get_status()

    def set_skin(self, skin_name):
        self.skin = "eva" if skin_name == "eva" else "cyan"
        cfg = load_config()
        cfg["skin"] = self.skin
        save_config(cfg)
        return self.skin

    def set_language(self, lang):
        self.lang = "zh" if lang == "zh" else "en"
        return self.lang

    def resize_window(self, is_expanded):
        global _active_window
        if _active_window:
            try:
                new_w = 465
                new_h = 490 if is_expanded else 295
                _active_window.resize(new_w, new_h)
                apply_rounded_corners(_active_window, new_w, new_h, radius=20)
            except Exception:
                pass
        return is_expanded

    def simulate_pulse(self):
        if winsound:
            try:
                winsound.Beep(1580, 55)
            except Exception:
                pass
        sim_delta = random.randint(1280, 2650)
        cfg = load_config()
        cfg["web_tokens"] = cfg.get("web_tokens", 0) + sim_delta
        save_config(cfg)
        return sim_delta

    def prompt_add_tokens(self):
        # Quick add 1M tokens or custom
        cfg = load_config()
        cfg["web_tokens"] = cfg.get("web_tokens", 0) + 1000000
        save_config(cfg)
        return cfg["web_tokens"]

    def export_poster(self):
        stats = get_full_stats()
        poster_path = generate_poster(stats=stats, auto_open=True)
        return poster_path

    def submit_tool_report(self, tool_name, notes=""):
        if not tool_name or not str(tool_name).strip():
            return False
        data_dir = get_app_data_dir()
        reports_file = os.path.join(data_dir, "tool_reports.json")
        reports = []
        if os.path.exists(reports_file):
            try:
                with open(reports_file, "r", encoding="utf-8") as f:
                    reports = json.load(f)
            except Exception:
                reports = []
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "tool_name": str(tool_name).strip(),
            "notes": str(notes or "").strip()
        }
        reports.append(entry)
        try:
            with open(reports_file, "w", encoding="utf-8") as f:
                json.dump(reports, f, indent=4, ensure_ascii=False)
            return True
        except Exception:
            return False

    def close_window(self):
        global _active_window
        if _active_window:
            _active_window.destroy()

def apply_rounded_corners(window, width=460, height=295, radius=20):
    """
    Applies OS-level rounded corners to the Win32 window.
    1. Sets DWM window corner preference (DWMWCP_ROUND on Windows 11).
    2. Uses GDI CreateRoundRectRgn and SetWindowRgn to physically clip away rectangular corners.
    """
    try:
        hwnd = 0
        if hasattr(window, 'native') and window.native and hasattr(window.native, 'Handle'):
            hwnd = int(window.native.Handle.ToInt64())
        if not hwnd:
            import ctypes
            hwnd = ctypes.windll.user32.FindWindowW(None, "TokenBurner 3D Hologram")
        if not hwnd:
            return

        import ctypes
        # 1. Windows 11 DWM Corner Preference: DWMWCP_ROUND = 2
        try:
            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            DWMWCP_ROUND = 2
            val = ctypes.c_int(DWMWCP_ROUND)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(val), ctypes.sizeof(val)
            )
        except Exception:
            pass

        # 2. GDI CreateRoundRectRgn: Physically clips window boundary on Windows 10/11
        try:
            rgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, width + 1, height + 1, radius * 2, radius * 2)
            ctypes.windll.user32.SetWindowRgn(hwnd, rgn, True)
        except Exception:
            pass
    except Exception:
        pass

def main():
    api = HudApi()
    html_file = os.path.join(CURRENT_DIR, "hud_3d.html")

    # Get primary screen dimensions
    screen_w = 1920
    try:
        screens = webview.screens
        if screens:
            screen_w = screens[0].width
    except Exception:
        pass

    win_w = 460
    win_h = 295
    start_x = max(100, screen_w - win_w - 25)
    start_y = 35

    window = webview.create_window(
        title="TokenBurner 3D Hologram",
        url=html_file,
        js_api=api,
        width=win_w,
        height=win_h,
        x=start_x,
        y=start_y,
        frameless=True,
        transparent=True,
        background_color="#0c0414",
        on_top=True,
        easy_drag=True
    )
    global _active_window
    _active_window = window

    def on_window_ready(win):
        import time
        for delay in [0.2, 0.5, 1.0, 1.8]:
            time.sleep(delay)
            apply_rounded_corners(win, win_w, win_h, radius=20)

    webview.start(on_window_ready, window)

if __name__ == "__main__":
    main()
