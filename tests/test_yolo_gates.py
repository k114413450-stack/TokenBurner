# -*- coding: utf-8 -*-
"""
Regression tests for the YOLO auto-approver's safety gates.

Run with:  python -m unittest discover -s tests -v

The vision layer is exercised for real (``cv2.matchTemplate`` against a
synthetic screen); only ``pyautogui`` is stubbed, so running the suite never
moves the physical mouse.

These tests exist because the gates are the whole point of this module. A
clicker that matches a button shape and clicks it is one line of code; the value
is entirely in refusing to act in every case it should not, and that is what is
asserted here.
"""

import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

try:
    import cv2
    import numpy as np
except ImportError:                                     # pragma: no cover
    cv2 = None
    np = None

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

# Stub pyautogui before the engine imports it: the suite must never move the
# user's mouse, and a real click would be both disruptive and untestable.
CLICKS = []
if "pyautogui" not in sys.modules:
    _pagu = types.ModuleType("pyautogui")
    _pagu.FAILSAFE = True
    _pagu.PAUSE = 0.05
    _pagu.position = lambda: (10, 10)
    _pagu.moveTo = lambda x, y, *a, **k: None

    def _click(x=None, y=None, *a, **k):
        if x is not None:
            CLICKS.append((x, y))

    _pagu.click = _click
    sys.modules["pyautogui"] = _pagu

if cv2 is not None:
    import yolo_approver as Y
else:                                                   # pragma: no cover
    Y = None


@unittest.skipIf(Y is None, "opencv is not installed")
class YoloGateTest(unittest.TestCase):
    SCREEN_W, SCREEN_H = 1920, 1080
    TEMPLATE_ABS = (900, 400)            # button top-left on the virtual screen
    TEMPLATE_SIZE = (140, 40)
    WINDOW_RECT = (800, 300, 1400, 700)  # left, top, right, bottom

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="tb-yolo-")
        os.environ["APPDATA"] = self.tmp
        os.environ["USERPROFILE"] = self.tmp
        CLICKS.clear()

        # A distinctive button: enough structure for a unique match peak.
        self.tpl = np.full((40, 140, 3), 200, np.uint8)
        cv2.rectangle(self.tpl, (0, 0), (139, 39), (60, 60, 60), 2)
        cv2.rectangle(self.tpl, (14, 12), (95, 20), (30, 30, 30), -1)
        cv2.rectangle(self.tpl, (14, 24), (70, 30), (30, 30, 30), -1)

        self.screen = np.full((self.SCREEN_H, self.SCREEN_W, 3), 255, np.uint8)
        x, y = self.TEMPLATE_ABS
        self.screen[y:y + 40, x:x + 140] = self.tpl

        screen = self.screen

        class FakePil:
            def __init__(self, arr):
                self.arr = arr

            @property
            def size(self):
                return (self.arr.shape[1], self.arr.shape[0])

            def __array__(self, dtype=None, copy=None):
                return self.arr if dtype is None else self.arr.astype(dtype)

        class FakeGrab:
            @staticmethod
            def grab(bbox=None):
                if bbox is None:
                    return FakePil(screen)
                l, t, r, b = bbox
                return FakePil(screen[t:b, l:r])

        self._real_grab = Y.ImageGrab
        Y.ImageGrab = FakeGrab

        self._cur = {"w": None}
        self._real_fg = Y._foreground_window
        Y._foreground_window = lambda: self._cur["w"]

    def tearDown(self):
        Y.ImageGrab = self._real_grab
        Y._foreground_window = self._real_fg
        Y._instance = None

    # -- helpers ---------------------------------------------------------
    def set_window(self, process="claude.exe", title="claude - bash", rect=None):
        self._cur["w"] = {
            "hwnd": 1, "pid": 2, "process": process, "title": title,
            "rect": rect or self.WINDOW_RECT,
        }

    def engine(self, **over):
        cfg = {
            "dry_run": True,
            "whitelist_processes": ["claude.exe", "windowsterminal.exe"],
            "whitelist_titles": [],
            "confidence": 0.82,
            "min_seconds_between_clicks": 0.0,
            "max_clicks_per_minute": 10,
            "max_clicks_per_session": 100,
        }
        cfg.update(over)
        Y.load_config = lambda: {"yolo": cfg}
        Y._instance = None
        eng = Y.YoloApprover()
        eng.templates = [("submit_button.png", self.tpl, 140, 40)]
        eng.confidence = cfg["confidence"]
        return eng

    # -- whitelist gate ---------------------------------------------------
    def test_empty_whitelist_refuses_to_click(self):
        eng = self.engine(whitelist_processes=[])
        self.set_window()
        self.assertFalse(eng._scan_once())
        self.assertIn("whitelist is empty", eng.last_block_reason)
        self.assertEqual(eng.clicks_total, 0)
        self.assertFalse(eng.get_status()["can_click"])

    def test_non_whitelisted_process_is_blocked(self):
        eng = self.engine()
        self.set_window(process="notepad.exe", title="untitled - notepad")
        self.assertFalse(eng._scan_once())
        self.assertIn("notepad.exe", eng.last_block_reason)
        self.assertEqual(eng.clicks_total, 0)

    def test_title_whitelist_is_honoured(self):
        eng = self.engine(whitelist_processes=[], whitelist_titles=["claude"])
        self.set_window(process="whatever.exe", title="claude code session")
        self.assertTrue(eng._scan_once())

    # -- geometry gate ----------------------------------------------------
    def test_tiny_window_is_rejected(self):
        eng = self.engine()
        self.set_window(rect=(100, 100, 150, 120))       # 50x20
        self.assertFalse(eng._scan_once())
        self.assertEqual(eng.last_block_reason, "window geometry unusable")

    def test_offscreen_window_is_rejected(self):
        eng = self.engine()
        self.set_window(rect=(-5000, -5000, -4900, -4900))
        self.assertFalse(eng._scan_once())
        self.assertEqual(eng.clicks_total, 0)

    # -- confidence gate --------------------------------------------------
    def test_template_absent_from_screen_does_not_match(self):
        eng = self.engine()
        self.set_window()
        other = np.full((40, 140, 3), 30, np.uint8)
        cv2.circle(other, (70, 20), 12, (255, 255, 255), -1)
        eng.templates = [("unrelated.png", other, 140, 40)]
        self.assertFalse(eng._scan_once())
        self.assertEqual(eng.last_block_reason, "")     # a miss, not a refusal
        self.assertEqual(eng.clicks_total, 0)

    def test_confidence_threshold_is_two_sided(self):
        """The same image must hit below the threshold and miss above it."""
        blurry = cv2.GaussianBlur(self.tpl, (9, 9), 0)
        l, t, r, b = self.WINDOW_RECT
        res = cv2.matchTemplate(self.screen[t:b, l:r], blurry, cv2.TM_CCOEFF_NORMED)
        _, score, _, _ = cv2.minMaxLoc(res)

        strict = self.engine(confidence=min(0.999, score + 0.05))
        self.set_window()
        strict.templates = [("submit_blur.png", blurry, 140, 40)]
        self.assertFalse(strict._scan_once())

        loose = self.engine(confidence=max(0.5, score - 0.05))
        self.set_window()
        loose.templates = [("submit_blur.png", blurry, 140, 40)]
        self.assertTrue(loose._scan_once())

    # -- dry run ----------------------------------------------------------
    def test_dry_run_counts_but_does_not_click(self):
        eng = self.engine()                             # dry_run defaults True
        self.set_window()
        self.assertTrue(eng._scan_once())
        self.assertEqual(len(CLICKS), 0, "dry run must not move the mouse")
        self.assertEqual(eng.clicks_total, 1)
        self.assertEqual(eng.last_match_name, "submit_button.png")

    def test_audit_log_records_the_decision(self):
        eng = self.engine()
        self.set_window()
        eng._scan_once()
        log = Path(self.tmp) / "TokenBurner" / "yolo_audit.jsonl"
        self.assertTrue(log.exists())
        recs = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
        hits = [r for r in recs if r["event"] == "dry_run_hit"]
        self.assertTrue(hits)
        # Window-relative match must be translated to absolute screen coords.
        tx, ty = self.TEMPLATE_ABS
        self.assertEqual((hits[-1]["x"], hits[-1]["y"]), (tx + 70, ty + 20))

    def test_blocks_are_audited_too(self):
        eng = self.engine()
        self.set_window(process="notepad.exe")
        eng._scan_once()
        log = Path(self.tmp) / "TokenBurner" / "yolo_audit.jsonl"
        recs = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertTrue([r for r in recs if r["event"] == "blocked"])

    # -- live mode --------------------------------------------------------
    def test_live_click_uses_absolute_coordinates(self):
        eng = self.engine(dry_run=False)
        self.set_window()
        self.assertTrue(eng._scan_once())
        tx, ty = self.TEMPLATE_ABS
        self.assertEqual(CLICKS, [(tx + 70, ty + 20)])

    # -- rate limits ------------------------------------------------------
    def test_cooldown_blocks_repeat_clicks(self):
        eng = self.engine(dry_run=False, min_seconds_between_clicks=30.0)
        self.set_window()
        self.assertTrue(eng._scan_once())
        self.assertFalse(eng._scan_once())
        self.assertTrue(eng.last_block_reason.startswith("cooldown"))

    def test_session_cap_blocks(self):
        eng = self.engine(dry_run=False, max_clicks_per_session=2)
        self.set_window()
        eng._scan_once()
        eng._scan_once()
        self.assertFalse(eng._scan_once())
        self.assertTrue(eng.last_block_reason.startswith("session cap"))

    def test_per_minute_cap_blocks(self):
        eng = self.engine(dry_run=False, max_clicks_per_minute=2,
                          min_seconds_between_clicks=0.0)
        self.set_window()
        eng._scan_once()
        eng._scan_once()
        self.assertFalse(eng._scan_once())
        self.assertTrue(eng.last_block_reason.startswith("rate cap"))

    # -- capture isolation ------------------------------------------------
    def test_match_outside_focused_window_is_impossible(self):
        """The screenshot is cropped to the window, so a match cannot leak in."""
        eng = self.engine()
        self.set_window(rect=(100, 100, 700, 500))      # nowhere near the button
        self.assertFalse(eng._scan_once())
        self.assertEqual(eng.clicks_total, 0)

    # -- status contract --------------------------------------------------
    def test_status_exposes_policy_to_the_ui(self):
        eng = self.engine(dry_run=False)
        st = eng.get_status()
        for key in ("enabled", "dry_run", "clicks_total", "blocked_total",
                    "last_block_reason", "last_window", "whitelist_processes",
                    "can_click"):
            self.assertIn(key, st)
        self.assertFalse(st["dry_run"])
        self.assertTrue(st["can_click"])

    def test_apply_config_switches_policy_live(self):
        eng = self.engine()
        eng.apply_config({"dry_run": False, "whitelist_processes": ["pwsh.exe"]})
        self.assertFalse(eng.dry_run)
        self.assertEqual(eng.whitelist_processes, ["pwsh.exe"])
        self.assertTrue(eng.get_status()["can_click"])

        eng.apply_config({"dry_run": True, "whitelist_processes": []})
        self.assertTrue(eng.dry_run)
        self.assertFalse(eng.get_status()["can_click"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
