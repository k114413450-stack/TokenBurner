# -*- coding: utf-8 -*-
# TokenBurner 3D Vision Core Runner (WebView2 + Three.js)
import os
import sys
import webview

import json
import time
from datetime import datetime

try:
    from app_paths import get_app_data_dir
except ImportError:
    from src.app_paths import get_app_data_dir

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
    from progression import calculate_level, stage_progress, stage_for_level, MAX_LEVEL
except ImportError:
    from src.scanner import get_full_stats, load_config, save_config
    from src.poster import generate_poster
    from src.model_detector import ModelDetector
    from src.progression import calculate_level, stage_progress, stage_for_level, MAX_LEVEL

# Where "report an untracked tool" sends people. There is no backend on purpose -
# the poster and README both promise 100% local, so the honest implementation is
# to open a prefilled GitHub issue in the user's own browser.
GITHUB_REPO = "k114413450-stack/TokenBurner"

# FIX: the optional YOLO auto-approver pulls in opencv/pyautogui. It used to be
# imported together with the core modules, so a missing opencv crashed the whole
# HUD on startup with no visible error. It is now optional.
_YOLO_UNAVAILABLE_REASON = None
get_yolo_approver = None
try:
    try:
        from yolo_approver import get_yolo_approver
    except ImportError:
        from src.yolo_approver import get_yolo_approver
except Exception as _yolo_err:
    # The inner fallback masks the real cause (the outer error becomes
    # "No module named 'src'" even when the true problem is a missing cv2),
    # so probe the optional dependencies directly to report something useful.
    for _dep in ("cv2", "pyautogui", "numpy", "PIL"):
        try:
            __import__(_dep)
        except Exception as _dep_err:
            _YOLO_UNAVAILABLE_REASON = (
                f"missing optional dependency '{_dep}' ({_dep_err}) - "
                f"run: pip install -r requirements.txt"
            )
            break
    if _YOLO_UNAVAILABLE_REASON is None:
        _YOLO_UNAVAILABLE_REASON = f"{type(_yolo_err).__name__}: {_yolo_err}"

_EMPTY_YOLO_STATUS = {
    "enabled": False,
    "dry_run": True,
    "clicks_total": 0,
    "blocked_total": 0,
    "last_click_time": 0,
    "last_match_name": "",
    "last_block_reason": "",
    "last_window": "",
    "templates_count": 0,
    "whitelist_processes": [],
    "whitelist_titles": [],
    "can_click": False,
    "unavailable": True,
    "reason": _YOLO_UNAVAILABLE_REASON or "",
}

_active_window = None

class HudApi:
    def __init__(self):
        self.detector = ModelDetector()
        self.active_model = self.detector.active_model_name
        self.active_tool = self.detector.active_tool
        self.lang = "zh"  # default to Chinese per user request
        self.skin = load_config().get("skin", "eva")
        self.yolo = get_yolo_approver() if get_yolo_approver else None
        self.start_model_detector_thread()

    def _yolo_status(self):
        if self.yolo is None:
            return dict(_EMPTY_YOLO_STATUS)
        return self.yolo.get_status()

    def start_model_detector_thread(self):
        import threading
        import time
        import ctypes
        import psutil

        def _loop():
            import ctypes.wintypes
            user32 = ctypes.windll.user32
            # FIX: on 64-bit Windows HWND is pointer-sized. Without explicit
            # restype/argtypes ctypes assumes c_int and truncates the handle,
            # which silently breaks the detection on some window handles.
            user32.GetForegroundWindow.restype = ctypes.wintypes.HWND
            user32.GetWindowTextLengthW.argtypes = [ctypes.wintypes.HWND]
            user32.GetWindowTextLengthW.restype = ctypes.c_int
            user32.GetWindowTextW.argtypes = [
                ctypes.wintypes.HWND, ctypes.wintypes.LPWSTR, ctypes.c_int
            ]
            user32.GetWindowThreadProcessId.argtypes = [
                ctypes.wintypes.HWND, ctypes.POINTER(ctypes.wintypes.DWORD)
            ]

            pid_val = ctypes.wintypes.DWORD()
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

                        # FIX: the self-exclusion only tested the literal string
                        # "token_burner", but the actual window title is
                        # "TokenBurner 3D Hologram" (no underscore), so the guard
                        # never fired. Also the HUD runs under python.exe, so the
                        # process-name check can never match it either.
                        title_l = title.lower()
                        is_self = ("tokenburner" in title_l) or ("token_burner" in title_l)
                        if proc_name and not is_self:
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
        lv, pct, in_level, need_level, stage_code, stage_title = calculate_level(total, lang=self.lang)
        pos_in_stage, stage_size = stage_progress(lv)
        stage_info = stage_for_level(lv)

        stats["lang"] = self.lang
        stats["skin"] = self.skin
        stats["active_model"] = self.active_model
        stats["active_tool"] = self.active_tool
        stats["level"] = lv
        stats["max_level"] = MAX_LEVEL
        stats["level_title"] = stage_title
        stats["level_pct"] = round(pct * 100.0, 1)
        stats["level_need"] = need_level
        stats["level_into"] = in_level
        stats["stage"] = stage_code
        stats["stage_desc"] = stage_info.get("desc", "")
        stats["stage_index"] = (lv - 1) // 10 + 1
        stats["stage_pos"] = pos_in_stage
        stats["stage_size"] = stage_size

        # Data provenance. The headline number is a mix of figures read from the
        # tools' own API usage logs (verified) and figures inferred from file
        # size (estimated); the UI has to be able to say which is which, because
        # a size-based guess must never be presented as a measured fact.
        quality = stats.get("data_quality") or {}
        stats["quality"] = quality
        stats["verified_tokens"] = stats.get("verified_tokens", 0)
        stats["estimated_tokens"] = stats.get("estimated_tokens", 0)
        stats["manual_tokens"] = stats.get("manual_tokens", 0)

        stats["yolo"] = self._yolo_status()
        return stats

    def get_yolo_policy(self):
        cfg = load_config().get("yolo", {}) or {}
        return {
            "dry_run": bool(cfg.get("dry_run", True)),
            "whitelist_processes": list(cfg.get("whitelist_processes") or []),
            "whitelist_titles": list(cfg.get("whitelist_titles") or []),
            "confidence": cfg.get("confidence", 0.82),
            "min_seconds_between_clicks": cfg.get("min_seconds_between_clicks", 3.0),
            "max_clicks_per_minute": cfg.get("max_clicks_per_minute", 10),
            "max_clicks_per_session": cfg.get("max_clicks_per_session", 100),
            "status": self._yolo_status(),
        }

    def set_yolo_policy(self, dry_run=None, whitelist=None):
        """Persist a YOLO policy change and apply it to the running scanner."""
        cfg = load_config()
        ycfg = dict(cfg.get("yolo") or {})
        if dry_run is not None:
            ycfg["dry_run"] = bool(dry_run)
        if whitelist is not None:
            items = [
                s.strip().lower()
                for s in str(whitelist).replace("\n", ",").replace(";", ",").split(",")
                if s.strip()
            ]
            ycfg["whitelist_processes"] = items
        cfg["yolo"] = ycfg
        save_config(cfg)
        if self.yolo is not None:
            self.yolo.apply_config(ycfg)
        return self.get_yolo_policy()

    def get_yolo_audit_tail(self, limit=20):
        """Last N audit entries, so the user can see exactly what was clicked."""
        try:
            import collections
            path = os.path.join(get_app_data_dir(), "yolo_audit.jsonl")
            if not os.path.exists(path):
                return []
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                tail = collections.deque(f, maxlen=max(1, int(limit)))
            out = []
            for line in tail:
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
            return out
        except Exception:
            return []

    def toggle_yolo(self):
        if self.yolo is None:
            return dict(_EMPTY_YOLO_STATUS)
        self.yolo.toggle()
        return self.yolo.get_status()

    def get_yolo_status(self):
        return self._yolo_status()

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

    def export_poster(self):
        stats = get_full_stats()
        poster_path = generate_poster(stats=stats, auto_open=True)
        return poster_path

    def submit_tool_report(self, tool_name, notes=""):
        """
        "Report an untracked tool" used to write a local JSON file while the UI
        claimed "上报成功，作者后续将适配" - nothing ever left the machine, so the
        request was silently dropped. It now opens a prefilled GitHub issue in
        the user's own browser, which is the only honest way to reach the
        maintainer from a 100%-offline app.
        """
        tool_name = str(tool_name or "").strip()
        if not tool_name:
            return False

        notes = str(notes or "").strip()
        title = f"[Tool Request] 适配 {tool_name}"
        body_lines = [
            "### 无法统计的工具 / 网页",
            tool_name,
            "",
        ]
        if notes:
            body_lines += ["### 补充说明", notes, ""]
        body_lines += [
            "### 环境",
            f"- TokenBurner: v1.0.0",
            f"- Platform: Windows",
            "",
            "<!-- 由 TokenBurner HUD 自动生成，请在提交前确认没有隐私信息 -->",
        ]

        from urllib.parse import quote
        url = (
            f"https://github.com/{GITHUB_REPO}/issues/new"
            f"?title={quote(title)}&body={quote(chr(10).join(body_lines))}&labels=tool-request"
        )

        # Always leave a local breadcrumb so the request is not lost offline.
        try:
            data_dir = get_app_data_dir()
            reports_file = os.path.join(data_dir, "tool_reports.json")
            reports = []
            if os.path.exists(reports_file):
                try:
                    with open(reports_file, "r", encoding="utf-8") as f:
                        reports = json.load(f)
                except Exception:
                    reports = []
            reports.append({
                "timestamp": datetime.now().isoformat(),
                "tool_name": tool_name,
                "notes": notes,
            })
            with open(reports_file, "w", encoding="utf-8") as f:
                json.dump(reports, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

        try:
            import webbrowser
            return bool(webbrowser.open(url))
        except Exception:
            return False

    def report_url(self, tool_name="", notes=""):
        """Exposed so the UI can show/copy the target URL without opening it."""
        from urllib.parse import quote
        title = f"[Tool Request] 适配 {str(tool_name or '').strip()}"
        return (
            f"https://github.com/{GITHUB_REPO}/issues/new"
            f"?title={quote(title)}&labels=tool-request"
        )

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
        import ctypes
        import ctypes.wintypes

        user32 = ctypes.windll.user32
        user32.FindWindowW.restype = ctypes.wintypes.HWND
        user32.FindWindowW.argtypes = [ctypes.wintypes.LPCWSTR, ctypes.wintypes.LPCWSTR]
        user32.SetWindowRgn.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.HANDLE, ctypes.wintypes.BOOL]
        gdi32 = ctypes.windll.gdi32
        gdi32.CreateRoundRectRgn.restype = ctypes.wintypes.HANDLE
        gdi32.CreateRoundRectRgn.argtypes = [ctypes.c_int] * 6
        dwmapi = ctypes.windll.dwmapi
        dwmapi.DwmSetWindowAttribute.argtypes = [
            ctypes.wintypes.HWND, ctypes.wintypes.DWORD, ctypes.c_void_p, ctypes.wintypes.DWORD
        ]

        hwnd = 0
        if hasattr(window, 'native') and window.native and hasattr(window.native, 'Handle'):
            hwnd = int(window.native.Handle.ToInt64())
        if not hwnd:
            hwnd = user32.FindWindowW(None, "TokenBurner 3D Hologram")
        if not hwnd:
            return

        # 1. Windows 11 DWM Corner Preference: DWMWCP_ROUND = 2
        try:
            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            DWMWCP_ROUND = 2
            val = ctypes.c_int(DWMWCP_ROUND)
            dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(val), ctypes.sizeof(val)
            )
        except Exception:
            pass

        # 2. GDI CreateRoundRectRgn: Physically clips window boundary on Windows 10/11
        try:
            rgn = gdi32.CreateRoundRectRgn(0, 0, width + 1, height + 1, radius * 2, radius * 2)
            if not user32.SetWindowRgn(hwnd, rgn, True):
                # SetWindowRgn takes ownership on success; delete on failure.
                gdi32.DeleteObject(rgn)
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
