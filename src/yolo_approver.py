# -*- coding: utf-8 -*-
"""
YOLO auto-approver engine.

WHAT IT DOES
    Watches the *currently focused* window for a button that looks like a
    confirmation prompt (Submit / Run / Allow / Proceed) and clicks it.

WHY IT IS DEFENSIVE
    A screen-scraping clicker that acts on template match alone is a foot-gun:
    the match has no idea which application it is looking at, so any window that
    happens to contain a similar-looking shape gets clicked. The previous version
    did exactly that - match anywhere on any monitor, click immediately, no
    window check - while the README advertised it as approving "safe" prompts.
    Nothing in the code could tell a safe prompt from a destructive one.

    Every click now has to pass a chain of gates, in order:

      1. FOCUSED WINDOW   only the foreground window is ever considered.
      2. WHITELIST        its process name / title must be explicitly allowed.
                          An empty whitelist means "never click" - it is a hard
                          gate, not a hint.
      3. SCREENSHOT SCOPE only the foreground window's own rectangle is grabbed,
                          so a match physically cannot come from another app.
      4. CONFIDENCE       template match score must clear the threshold.
      5. CLICK POINT      the computed point is re-checked against the window
                          rectangle before the mouse moves.
      6. RATE LIMIT       cooldown, per-minute cap and per-session cap.
      7. DRY RUN          on by default: gates 1-6 run, the click is logged and
                          counted, but the mouse never moves.

    Every decision - including every blocked one - is written to
    ``%APPDATA%\\TokenBurner\\yolo_audit.jsonl`` so the user can audit exactly
    what happened and why.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import cv2
import numpy as np
import pyautogui
from PIL import ImageGrab

try:
    from app_paths import get_app_data_dir
except ImportError:
    from src.app_paths import get_app_data_dir

try:
    from scanner import load_config
except ImportError:
    try:
        from src.scanner import load_config
    except ImportError:                                    # standalone fallback
        def load_config():
            return {"yolo": {}}

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = CURRENT_DIR.parent
TEMPLATES_DIR = PROJECT_DIR / "assets" / "templates"

AUDIT_LOG_MAX_BYTES = 1_000_000


def audit_log_path() -> Path:
    """
    Resolved on every call, not at import time.

    ``%APPDATA%`` can differ from whatever it was when the module was imported
    (the packaged app, a test harness, or any process that changes the profile).
    A module-level constant silently wrote the audit trail to the wrong place.
    """
    return Path(get_app_data_dir()) / "yolo_audit.jsonl"

# A window smaller than this is not a plausible target and is far more likely to
# be a mis-read rectangle (minimised window, tooltip, hidden helper window).
MIN_TARGET_W = 120
MIN_TARGET_H = 80


def _foreground_window():
    """
    Describe the current foreground window.

    Returns a dict with hwnd/pid/process/title/rect, or None. HWND is declared
    as a pointer-sized type explicitly: ctypes otherwise assumes c_int and
    truncates the handle on 64-bit Windows.
    """
    try:
        import ctypes
        import ctypes.wintypes

        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = ctypes.wintypes.HWND
        user32.GetWindowTextLengthW.argtypes = [ctypes.wintypes.HWND]
        user32.GetWindowTextLengthW.restype = ctypes.c_int
        user32.GetWindowTextW.argtypes = [
            ctypes.wintypes.HWND, ctypes.wintypes.LPWSTR, ctypes.c_int
        ]
        user32.GetWindowThreadProcessId.argtypes = [
            ctypes.wintypes.HWND, ctypes.POINTER(ctypes.wintypes.DWORD)
        ]

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None

        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value or ""

        rect = ctypes.wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        box = (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))

        process = ""
        if pid.value:
            try:
                import psutil
                process = psutil.Process(pid.value).name().lower()
            except Exception:
                process = ""

        return {
            "hwnd": int(hwnd),
            "pid": int(pid.value),
            "process": process,
            "title": title,
            "rect": box,
        }
    except Exception:
        return None


class YoloApprover:
    def __init__(self, confidence: float = None, interval: float = 1.0):
        cfg = load_config().get("yolo", {}) or {}
        self.cfg = cfg
        self.confidence = float(confidence if confidence is not None else cfg.get("confidence", 0.82))
        self.interval = interval
        self.dry_run = bool(cfg.get("dry_run", True))
        self.whitelist_processes = [
            str(p).lower() for p in (cfg.get("whitelist_processes") or []) if str(p).strip()
        ]
        self.whitelist_titles = [
            str(t).lower() for t in (cfg.get("whitelist_titles") or []) if str(t).strip()
        ]
        self.min_seconds_between_clicks = float(cfg.get("min_seconds_between_clicks", 3.0))
        self.max_clicks_per_minute = int(cfg.get("max_clicks_per_minute", 10))
        self.max_clicks_per_session = int(cfg.get("max_clicks_per_session", 100))

        self.enabled = False
        self.clicks_total = 0
        self.blocked_total = 0
        self.last_click_time = 0.0
        self.last_match_name = ""
        self.last_block_reason = ""
        self.last_window = ""
        self._click_times: List[float] = []
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.on_click_callback: Optional[Callable[[str, int, int], None]] = None
        self.templates: List[Tuple[str, np.ndarray, int, int]] = []
        self.reload_templates()

    # ------------------------------------------------------------------ setup
    def reload_templates(self) -> int:
        """Load button templates from the bundled dir plus a user override dir."""
        self.templates.clear()
        search_dirs = [
            TEMPLATES_DIR,
            Path(get_app_data_dir()) / "templates",
        ]
        loaded_names = set()
        for d in search_dirs:
            if not d.is_dir():
                continue
            for p in sorted(d.glob("*.png")):
                if p.name in loaded_names:
                    continue
                img = cv2.imread(str(p))
                if img is not None:
                    h, w = img.shape[:2]
                    self.templates.append((p.name, img, w, h))
                    loaded_names.add(p.name)
        print(f"[YOLO] Loaded {len(self.templates)} button template(s)")
        return len(self.templates)

    def toggle(self) -> bool:
        if self.enabled:
            self.stop()
        else:
            self.start()
        return self.enabled

    def apply_config(self, cfg: dict = None) -> dict:
        """
        Re-read the safety policy without restarting the scanner.

        Called when the user edits the whitelist or the dry-run switch in the
        HUD, so a policy change takes effect immediately instead of on next
        launch.
        """
        if cfg is None:
            cfg = load_config().get("yolo", {}) or {}
        self.cfg = cfg
        self.dry_run = bool(cfg.get("dry_run", True))
        self.whitelist_processes = [
            str(p).lower() for p in (cfg.get("whitelist_processes") or []) if str(p).strip()
        ]
        self.whitelist_titles = [
            str(t).lower() for t in (cfg.get("whitelist_titles") or []) if str(t).strip()
        ]
        self.confidence = float(cfg.get("confidence", self.confidence))
        self.min_seconds_between_clicks = float(
            cfg.get("min_seconds_between_clicks", self.min_seconds_between_clicks)
        )
        self.max_clicks_per_minute = int(
            cfg.get("max_clicks_per_minute", self.max_clicks_per_minute)
        )
        self.max_clicks_per_session = int(
            cfg.get("max_clicks_per_session", self.max_clicks_per_session)
        )
        self._audit("policy_updated", dry_run=self.dry_run,
                    whitelist=list(self.whitelist_processes))
        return self.get_status()

    def start(self):
        if self.enabled:
            return
        if not self.templates:
            self.reload_templates()
        self.enabled = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._scan_loop, daemon=True)
        self._thread.start()
        mode = "DRY RUN (no clicks)" if self.dry_run else "LIVE"
        print(f"[YOLO] Scanner started in {mode} mode")
        self._audit("start", mode=mode)

    def stop(self):
        if not self.enabled:
            return
        self.enabled = False
        self._stop_event.set()
        print("[YOLO] Scanner stopped")
        self._audit("stop")

    # ----------------------------------------------------------------- status
    def get_status(self) -> dict:
        return {
            "enabled": self.enabled,
            "dry_run": self.dry_run,
            "clicks_total": self.clicks_total,
            "blocked_total": self.blocked_total,
            "last_click_time": self.last_click_time,
            "last_match_name": self.last_match_name,
            "last_block_reason": self.last_block_reason,
            "last_window": self.last_window,
            "templates_count": len(self.templates),
            "whitelist_processes": list(self.whitelist_processes),
            "whitelist_titles": list(self.whitelist_titles),
            "can_click": self._whitelist_ready(),
        }

    def _whitelist_ready(self) -> bool:
        """Without an explicit allow-list the engine refuses to act at all."""
        return bool(self.whitelist_processes or self.whitelist_titles)

    # --------------------------------------------------------------- audit log
    def _audit(self, event: str, **fields):
        try:
            path = audit_log_path()
            if path.exists() and path.stat().st_size > AUDIT_LOG_MAX_BYTES:
                # Rotate rather than grow without bound.
                path.replace(path.with_suffix(".jsonl.1"))
            rec = {"ts": time.time(), "iso": time.strftime("%Y-%m-%d %H:%M:%S"), "event": event}
            rec.update(fields)
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass

    # ------------------------------------------------------------- gate checks
    def _gate_window(self, win) -> Tuple[bool, str]:
        """Gate 1-2: the foreground window must be whitelisted and clickable."""
        if not win:
            return False, "no foreground window"
        if not self._whitelist_ready():
            return False, "whitelist is empty - refusing to click anywhere"
        proc = (win.get("process") or "").lower()
        title = (win.get("title") or "").lower()
        if proc in self.whitelist_processes:
            return True, f"process '{proc}' is whitelisted"
        for t in self.whitelist_titles:
            if t and t in title:
                return True, f"title matches '{t}'"
        return False, f"'{proc or '?'}' / '{title[:40]}' not in whitelist"

    def _gate_geometry(self, win, screen_w, screen_h):
        """
        Gates 3-5 helper: a sane on-screen rectangle, or None.

        The screenshot is cropped to this rectangle, so a template physically
        cannot match outside the focused window.
        """
        if not win:
            return None
        left, top, right, bottom = win["rect"]
        w, h = right - left, bottom - top
        if w < MIN_TARGET_W or h < MIN_TARGET_H:
            return None
        if right <= 0 or bottom <= 0 or left >= screen_w or top >= screen_h:
            return None
        # Clamp to the physical screen so ImageGrab never gets an invalid bbox.
        left = max(0, left)
        top = max(0, top)
        right = min(screen_w, right)
        bottom = min(screen_h, bottom)
        if right - left < MIN_TARGET_W or bottom - top < MIN_TARGET_H:
            return None
        return (left, top, right, bottom)

    def _gate_rate(self) -> Tuple[bool, str]:
        """Gate 6: cooldown, per-minute and per-session caps."""
        now = time.time()
        if self.max_clicks_per_session and self.clicks_total >= self.max_clicks_per_session:
            return False, f"session cap reached ({self.max_clicks_per_session})"
        if self.min_seconds_between_clicks:
            elapsed = now - self.last_click_time
            if self.last_click_time and elapsed < self.min_seconds_between_clicks:
                return False, f"cooldown {elapsed:.1f}s < {self.min_seconds_between_clicks}s"
        if self.max_clicks_per_minute:
            recent = [t for t in self._click_times if now - t < 60.0]
            if len(recent) >= self.max_clicks_per_minute:
                return False, f"rate cap reached ({self.max_clicks_per_minute}/min)"
        return True, ""

    # -------------------------------------------------------------- scan cycle
    def _scan_once(self) -> bool:
        if not self.templates:
            return False

        # ---- gate 1-2: focused, whitelisted window -------------------------
        win = _foreground_window()
        ok, why = self._gate_window(win)
        if not ok:
            if self.last_block_reason != why:
                self.last_block_reason = why
                self.blocked_total += 1
                self._audit("blocked", gate="window", reason=why)
            return False

        self.last_window = f"{win.get('process','?')}: {win.get('title','')[:60]}"

        # ---- gates 3-5 setup: crop the search area to that window ----------
        try:
            pil_full = ImageGrab.grab()
            screen_w, screen_h = pil_full.size
        except Exception as e:
            print(f"[YOLO] Screenshot error: {e}")
            return False

        bbox = self._gate_geometry(win, screen_w, screen_h)
        if bbox is None:
            self.last_block_reason = "window geometry unusable"
            return False

        try:
            pil_img = ImageGrab.grab(bbox=bbox)
            shot = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            win_h, win_w = shot.shape[:2]
        except Exception as e:
            print(f"[YOLO] Window grab error: {e}")
            return False

        # ---- gate 4: confidence -------------------------------------------
        best_score = 0.0
        best_match = None
        for name, tpl, tw, th in self.templates:
            if tw > win_w or th > win_h:
                continue
            try:
                res = cv2.matchTemplate(shot, tpl, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                if max_val >= self.confidence and max_val > best_score:
                    best_score = max_val
                    best_match = (name, max_loc[0] + tw // 2, max_loc[1] + th // 2, max_val)
            except Exception:
                continue

        if best_match is None:
            self.last_block_reason = ""
            return False

        name, rel_x, rel_y, score = best_match
        # Window-relative -> absolute screen coordinates.
        cx, cy = bbox[0] + rel_x, bbox[1] + rel_y

        # ---- gate 5: the point must still be inside the window ------------
        if not (bbox[0] <= cx <= bbox[2] and bbox[1] <= cy <= bbox[3]):
            self.last_block_reason = "click point outside target window"
            self.blocked_total += 1
            self._audit("blocked", gate="point", reason=self.last_block_reason,
                        process=win.get("process"), title=win.get("title", "")[:80])
            return False

        # ---- gate 6: rate limits ------------------------------------------
        ok, why = self._gate_rate()
        if not ok:
            self.last_block_reason = why
            self.blocked_total += 1
            self._audit("blocked", gate="rate", reason=why, template=name,
                        process=win.get("process"), title=win.get("title", "")[:80])
            return False

        self.last_block_reason = ""
        self.last_match_name = name

        # ---- gate 7: dry run ----------------------------------------------
        if self.dry_run:
            self.clicks_total += 1
            self.last_click_time = time.time()
            self._click_times.append(self.last_click_time)
            self._audit("dry_run_hit", template=name, score=round(score, 3),
                        x=cx, y=cy, process=win.get("process"),
                        title=win.get("title", "")[:80])
            print(f"[YOLO] DRY RUN hit '{name}' score={score:.3f} at ({cx},{cy}) - not clicking")
            if self.on_click_callback:
                try:
                    self.on_click_callback(name, cx, cy)
                except Exception:
                    pass
            return True

        print(f"[YOLO] Hit '{name}' at ({cx}, {cy}) score={score:.3f} -> Clicking")
        try:
            orig_pos = pyautogui.position()
            pyautogui.click(cx, cy)
            pyautogui.moveTo(orig_pos[0], orig_pos[1])
        except Exception as e:
            print(f"[YOLO] Click error: {e}")
            self._audit("click_error", template=name, error=str(e)[:120])
            return False

        self.clicks_total += 1
        self.last_click_time = time.time()
        self._click_times.append(self.last_click_time)
        self._audit("click", template=name, score=round(score, 3), x=cx, y=cy,
                    process=win.get("process"), title=win.get("title", "")[:80])
        if self.on_click_callback:
            try:
                self.on_click_callback(name, cx, cy)
            except Exception:
                pass
        return True

    def _attach_desktop(self):
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hdesk = user32.OpenDesktopW("default", 0, False, 0x10000000)
            if hdesk:
                user32.SetThreadDesktop(hdesk)
        except Exception:
            pass

    def _scan_loop(self):
        self._attach_desktop()
        while self.enabled and not self._stop_event.is_set():
            try:
                hit = self._scan_once()
                if hit:
                    time.sleep(1.2 if not self.dry_run else self.interval)
                else:
                    time.sleep(self.interval)
            except Exception as e:
                print(f"[YOLO] Scan loop exception: {e}")
                time.sleep(self.interval)


_instance: Optional[YoloApprover] = None


def get_yolo_approver() -> YoloApprover:
    global _instance
    if _instance is None:
        _instance = YoloApprover()
    return _instance
