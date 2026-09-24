# -*- coding: utf-8 -*-
"""
Regression tests for the real usage ledger in ``src/scanner.py``.

Run with:  python -m unittest discover -s tests -v

These cover the parts that are easy to get silently wrong. Every case here is
one that actually broke during development:

  * a line carrying the same usage twice (camelCase ``providerData.usage`` and
    snake_case ``message.usage``) must count once - counting both doubled the
    reported total from 421 M to 844 M;
  * a half-written line (no trailing newline yet) must not be consumed, or the
    record is lost forever once the rest arrives;
  * ``force=True`` must bypass the ledger's own TTL as well as the scan cache,
    otherwise "refresh" quietly returns data up to a minute old;
  * a truncated or rewritten transcript must not leave its old total behind.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))


def ms(days_ago=0, hour=12):
    """
    Epoch milliseconds for a recent day.

    Must be relative to the real clock: the daily series deliberately keeps only
    the last 30 days, so a hard-coded timestamp silently ages out of the window
    and the test starts lying.
    """
    d = datetime.now().replace(hour=hour, minute=0, second=0, microsecond=0)
    d -= timedelta(days=days_ago)
    return int(d.timestamp() * 1000)


def _usage_line(rec_id, total, inp=None, out=None, cached=0, ts=None):
    inp = total if inp is None else inp
    out = 0 if out is None else out
    return json.dumps({
        "id": rec_id,
        "timestamp": ms() if ts is None else ts,
        "type": "function_call",
        "providerData": {"usage": {
            "requests": 1,
            "inputTokens": inp,
            "outputTokens": out,
            "totalTokens": total,
            "inputTokensDetails": [{"cached_tokens": cached}],
        }},
    })


def _snake_usage_line(rec_id, total, ts=None):
    return json.dumps({
        "id": rec_id,
        "timestamp": ms() if ts is None else ts,
        "type": "function_call",
        "message": {"usage": {
            "input_tokens": total,
            "output_tokens": 0,
            "total_tokens": total,
            "cache_read_input_tokens": 0,
        }},
    })


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="tb-ledger-")
        self.home = Path(self.tmp) / "home"
        self.appdata = Path(self.tmp) / "appdata"
        (self.home / ".workbuddy" / "projects" / "s1").mkdir(parents=True)
        (self.appdata / "TokenBurner").mkdir(parents=True)

        self._saved = {k: os.environ.get(k) for k in ("USERPROFILE", "APPDATA", "LOCALAPPDATA")}
        os.environ["USERPROFILE"] = str(self.home)
        os.environ["APPDATA"] = str(self.appdata)
        os.environ["LOCALAPPDATA"] = str(self.appdata)

        import scanner
        self.scanner = scanner
        self.reset()

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- helpers ---------------------------------------------------------
    @property
    def transcript(self):
        return self.home / ".workbuddy" / "projects" / "s1" / "a.jsonl"

    def reset(self):
        """Full cold start: offsets, accumulated aggregates and scan cache."""
        self.scanner._ledger_cache["files"].clear()
        self.scanner._ledger_cache["aggs"].clear()
        self.scanner._ledger_cache["data"] = None
        self.scanner._scan_cache["data"] = None

    def write(self, *lines, path=None):
        p = Path(path) if path else self.transcript
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            for ln in lines:
                f.write(ln + "\n")

    def append(self, text):
        with open(self.transcript, "a", encoding="utf-8") as f:
            f.write(text)

    def total(self):
        return self.scanner.get_full_stats(force=True)["total_tokens"]

    # -- tests -----------------------------------------------------------
    def test_simple_sum(self):
        """camelCase and snake_case records both parse."""
        self.write(_usage_line("1", 1100), _snake_usage_line("2", 2200))
        self.assertEqual(self.total(), 3300)

    def test_duplicate_encoding_counts_once(self):
        """One request written in both encodings must not be counted twice."""
        both = json.dumps({
            "id": "1", "timestamp": 1758000000000, "type": "function_call",
            "providerData": {"usage": {"inputTokens": 300, "outputTokens": 30,
                                       "totalTokens": 330}},
            "message": {"usage": {"input_tokens": 300, "output_tokens": 30,
                                  "total_tokens": 330}},
        })
        self.write(both)
        self.assertEqual(self.total(), 330)

    def test_partial_line_not_consumed(self):
        """A record still being written must be deferred, not dropped."""
        self.write(_usage_line("1", 1100))
        self.append(_usage_line("2", 550))           # no trailing newline
        self.assertEqual(self.total(), 1100)

        self.append("\n")
        self.assertEqual(self.total(), 1650)

    def test_incremental_equals_cold_start(self):
        """Appending must accumulate; a cold re-parse must agree."""
        self.write(_usage_line("1", 1000))
        first = self.total()
        self.append(_usage_line("2", 2000) + "\n")
        incremental = self.total()
        self.assertEqual(incremental, 3000)
        self.assertNotEqual(incremental, first)

        self.reset()
        self.assertEqual(self.total(), 3000)

    def test_repeated_scan_is_stable(self):
        """No double counting when nothing changed."""
        self.write(_usage_line("1", 1000))
        self.assertEqual(self.total(), 1000)
        self.assertEqual(self.total(), 1000)
        self.assertEqual(self.total(), 1000)

    def test_multiple_files(self):
        self.write(_usage_line("1", 1000))
        self.write(_usage_line("2", 250), path=self.transcript.parent / "b.jsonl")
        self.assertEqual(self.total(), 1250)

    def test_truncated_file_leaves_no_residue(self):
        """A rewritten transcript must not keep contributing its old value."""
        self.write(_usage_line("1", 1000))
        self.assertEqual(self.total(), 1000)
        self.write(_usage_line("2", 11))
        self.assertEqual(self.total(), 11)

    def test_removed_file_is_dropped(self):
        b = self.transcript.parent / "b.jsonl"
        self.write(_usage_line("1", 1000))
        self.write(_usage_line("2", 500), path=b)
        self.assertEqual(self.total(), 1500)
        b.unlink()
        self.assertEqual(self.total(), 1000)

    def test_force_bypasses_ledger_ttl(self):
        """force=True must refresh the ledger, not just the scan cache."""
        self.write(_usage_line("1", 1000))
        self.assertEqual(self.total(), 1000)
        self.append(_usage_line("2", 700) + "\n")
        # Both caches are still warm; force must ignore both.
        self.assertEqual(self.total(), 1700)

    def test_cached_and_output_split(self):
        self.write(_usage_line("1", 1000, inp=900, out=100, cached=850))
        stats = self.scanner.get_full_stats(force=True)
        led = stats["ledger"]
        self.assertEqual(led["input"], 900)
        self.assertEqual(led["output"], 100)
        self.assertEqual(led["cached"], 850)
        self.assertEqual(led["requests"], 1)
        self.assertAlmostEqual(led["cache_hit_pct"], 850 / 900 * 100, places=1)

    def test_daily_history_uses_record_timestamps(self):
        """Days come from the records themselves, not from sampling totals."""
        self.write(
            _usage_line("1", 1000, ts=ms(days_ago=2)),
            _usage_line("2", 2000, ts=ms(days_ago=1)),
            _usage_line("3", 4000, ts=ms(days_ago=0)),
        )
        stats = self.scanner.get_full_stats(force=True)
        self.assertEqual(stats["data_quality"]["series_source"], "usage-ledger")

        days = {d["date"]: d for d in (stats.get("recent_days") or [])}
        self.assertEqual(len(days), 3, "each record timestamp should make a day")
        self.assertTrue(all(d["verified"] for d in days.values()))

        def key(days_ago):
            return (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")

        self.assertEqual(days[key(2)]["burned"], 1000)
        self.assertEqual(days[key(1)]["burned"], 2000)
        self.assertEqual(days[key(0)]["burned"], 4000)
        self.assertEqual(stats["today_burned"], 4000)

    def test_streak_counts_consecutive_days(self):
        self.write(
            _usage_line("1", 1000, ts=ms(days_ago=2)),
            _usage_line("2", 2000, ts=ms(days_ago=1)),
            _usage_line("3", 500, ts=ms(days_ago=0)),
        )
        stats = self.scanner.get_full_stats(force=True)
        self.assertEqual(stats["streak_days"], 3)

    def test_streak_breaks_on_a_gap(self):
        """A day with no burn in the middle must reset the count."""
        self.write(
            _usage_line("1", 1000, ts=ms(days_ago=3)),
            _usage_line("2", 500, ts=ms(days_ago=0)),      # days -1 and -2 empty
        )
        stats = self.scanner.get_full_stats(force=True)
        self.assertEqual(stats["streak_days"], 1)

    def test_recorded_days_survive_a_rewritten_transcript(self):
        """
        History is append-only by design: a transcript that gets rewritten or
        trimmed must not retroactively erase days already recorded, because the
        tokens really were burned.
        """
        self.write(
            _usage_line("1", 1000, ts=ms(days_ago=1)),
            _usage_line("2", 500, ts=ms(days_ago=0)),
        )
        self.assertEqual(self.scanner.get_full_stats(force=True)["streak_days"], 2)

        self.write(_usage_line("3", 500, ts=ms(days_ago=0)))   # day -1 dropped
        stats = self.scanner.get_full_stats(force=True)
        days = {d["date"] for d in stats["recent_days"]}
        self.assertIn((datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"), days)
        self.assertEqual(stats["streak_days"], 2)

    def test_provenance_is_labelled(self):
        self.write(_usage_line("1", 1000))
        stats = self.scanner.get_full_stats(force=True)
        self.assertEqual(stats["verified_tokens"], 1000)
        self.assertEqual(stats["estimated_tokens"], 0)
        self.assertEqual(stats["data_quality"]["tiers"]["WorkBuddy"], "verified")

    def test_no_data_at_all_is_not_an_error(self):
        stats = self.scanner.get_full_stats(force=True)
        self.assertEqual(stats["total_tokens"], 0)
        # Nothing to report must be reported as unavailable, never as a guess.
        self.assertEqual(stats["data_quality"]["tiers"]["WorkBuddy"], "unavailable")

    def test_cost_is_cache_aware(self):
        """98 % cached input must not be billed at the fresh-input rate."""
        self.write(_usage_line("1", 1000, inp=1000, out=0, cached=1000))
        stats = self.scanner.get_full_stats(force=True)
        pricing = stats["pricing"]
        expected = 1000 * float(pricing["cached_input_per_m"]) / 1_000_000
        self.assertAlmostEqual(stats["est_cost_usd"], round(expected, 2), places=2)

    def test_malformed_lines_are_skipped(self):
        self.write(
            "{not json at all",
            _usage_line("1", 1000),
            json.dumps({"id": "x", "providerData": {}}),
            '{"id":"y","providerData":{"usage":{"inputTokens":0,"outputTokens":0,"totalTokens":0}}}',
            _usage_line("3", 250),
        )
        self.assertEqual(self.total(), 1250)


if __name__ == "__main__":
    unittest.main(verbosity=2)
