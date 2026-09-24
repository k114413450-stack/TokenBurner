"""
YOLO Auto-Approver Engine for TokenBurner.
Continuously scans the screen for confirmation/approval buttons (e.g. Submit, Run, Allow, Proceed)
and triggers automated clicks to prevent interruption in AI coding workflows.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import cv2
import numpy as np
import pyautogui
from PIL import ImageGrab

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = CURRENT_DIR.parent
TEMPLATES_DIR = PROJECT_DIR / "assets" / "templates"


class YoloApprover:
    def __init__(self, confidence: float = 0.82, interval: float = 1.0):
        self.confidence = confidence
        self.interval = interval
        self.enabled = False
        self.clicks_total = 0
        self.last_click_time = 0.0
        self.last_match_name = ""
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.on_click_callback: Optional[Callable[[str, int, int], None]] = None
        self.templates: List[Tuple[str, np.ndarray, int, int]] = []
        self.reload_templates()

    def reload_templates(self) -> int:
        self.templates.clear()
        search_dirs = [
            TEMPLATES_DIR,
            Path("D:/scan_click/assets"),
        ]
        loaded_names = set()
        for d in search_dirs:
            if not d.is_dir():
                continue
            for p in d.glob("*.png"):
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

    def start(self):
        if self.enabled:
            return
        self.enabled = True
        self._stop_event.clear()
        if not self.templates:
            self.reload_templates()
        self._thread = threading.Thread(target=self._scan_loop, daemon=True)
        self._thread.start()
        print("[YOLO] Auto-approver scanner started")

    def stop(self):
        if not self.enabled:
            return
        self.enabled = False
        self._stop_event.set()
        print("[YOLO] Auto-approver scanner stopped")

    def get_status(self) -> dict:
        return {
            "enabled": self.enabled,
            "clicks_total": self.clicks_total,
            "last_click_time": self.last_click_time,
            "last_match_name": self.last_match_name,
            "templates_count": len(self.templates),
        }

    def _scan_once(self) -> bool:
        if not self.templates:
            return False

        try:
            pil_img = ImageGrab.grab()
            screenshot = np.array(pil_img)
            screen_bgr = cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR)
            screen_h, screen_w = screen_bgr.shape[:2]
        except Exception as e:
            print(f"[YOLO] Screenshot error: {e}")
            return False

        best_score = 0.0
        best_match = None

        for name, tpl, tw, th in self.templates:
            if tw > screen_w or th > screen_h:
                continue
            try:
                res = cv2.matchTemplate(screen_bgr, tpl, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                if max_val > best_score:
                    best_score = max_val
                    if max_val >= self.confidence:
                        best_match = (name, max_loc[0] + tw // 2, max_loc[1] + th // 2, max_val)
                        break
            except Exception:
                continue

        if best_match is not None:
            name, cx, cy, score = best_match
            print(f"[YOLO] Hit '{name}' at ({cx}, {cy}) score={score:.3f} -> Clicking")
            try:
                # Save current mouse position
                orig_pos = pyautogui.position()
                pyautogui.click(cx, cy)
                # Restore mouse position smoothly so user flow is not disturbed
                pyautogui.moveTo(orig_pos[0], orig_pos[1])
                self.clicks_total += 1
                self.last_click_time = time.time()
                self.last_match_name = name
                if self.on_click_callback:
                    try:
                        self.on_click_callback(name, cx, cy)
                    except Exception:
                        pass
                return True
            except Exception as e:
                print(f"[YOLO] Click error: {e}")
                return False

        return False

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
                    # Sleep longer after click to give UI time to dismiss modal
                    time.sleep(1.2)
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
