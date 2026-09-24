# -*- coding: utf-8 -*-
"""
TokenBurner - Local Level Progression Engine
============================================
Replaces the old `ranking_engine.py`.

WHAT CHANGED
------------
The previous module shipped a fake global leaderboard: it generated ~200
"ghost users" per model from a log-normal distribution and mixed them with the
real user so the UI could print `#N (TOP x%)`. None of it was real, and the
README advertised a "global ranking", so anyone comparing numbers could tell.

A real cross-user leaderboard needs a backend, which contradicts this
project's headline promise ("100% Local, zero telemetry"). So the ranking has
been removed entirely rather than faked. Levels are now the only progression
signal, and they are computed purely from local token counts.

Notes for contributors: if you want a real leaderboard, add it as an opt-in
module with a real backend and an explicit consent screen. Keep this file
offline-only.

LEVEL CURVE
-----------
Old curve: 1,000,000 x 1.22^(n-1) accumulated.
  -> Lv.100 needed 1.97e15 tokens (~5.7 billion USD at $2.94/M). Anything past
     Lv.35 was unreachable for a human, i.e. ~70% of the ladder was decoration.

New curve: 100,000 x 1.07^(n-1) accumulated.
  -> Lv.100 lands at ~1.16e9 tokens (~11.6 亿), which a genuine heavy user can
     reach over time. Early levels are deliberately cheap so a new install
     levels up within the first few thousand tokens.

Strictly English identifiers per the project's code convention; the user-facing
strings are bilingual.
"""

import math
from typing import Tuple, List, Dict

MAX_LEVEL = 100
LEVELS_PER_STAGE = 10

# Base XP for the step from Lv.1 -> Lv.2, and the per-level multiplier.
BASE_XP = 100_000
XP_RATIO = 1.07

# ---------------------------------------------------------------------------
# 10 stages x 10 levels.
# The progression follows what this app is actually named after: combustion.
# Fuse -> Ember -> Forge -> Furnace -> Reactor -> Fusion -> Star -> Supernova
# -> Nebula -> Singularity. Each stage name is the title shown for every level
# inside it (the XP bar carries the per-level granularity), so we never need
# 100 hand-written names that inevitably drift into "silly".
# `en` is used as the stage code on the poster, `zh` as the level title.
# ---------------------------------------------------------------------------
STAGES: List[Dict[str, str]] = [
    {"zh": "引信",   "en": "FUSE",        "desc": "零星试水，刚开始用 AI 干活"},
    {"zh": "火种",   "en": "EMBER",       "desc": "稳定上手，火没灭过"},
    {"zh": "炉火",   "en": "FORGE",       "desc": "每天都在烧，已成习惯"},
    {"zh": "熔炉",   "en": "FURNACE",     "desc": "吞吐上来了，开始批量产出"},
    {"zh": "反应堆", "en": "REACTOR",     "desc": "多任务并行，长期高负载"},
    {"zh": "聚变",   "en": "FUSION",      "desc": "投入产出比开始指数级放大"},
    {"zh": "恒星",   "en": "STAR",        "desc": "自成体系，单点稳定供能"},
    {"zh": "超新星", "en": "SUPERNOVA",   "desc": "爆发式增长，罕见量级"},
    {"zh": "星云",   "en": "NEBULA",      "desc": "已远超个人使用规模"},
    {"zh": "奇点",   "en": "SINGULARITY", "desc": "长期目标，几乎无人能及"},
]

# Precomputed cumulative thresholds.
# LEVEL_THRESHOLDS[n] == total tokens required to REACH level n.
# LEVEL_THRESHOLDS[1] == 0, so a brand-new install starts at Lv.1 with 0 budget.
LEVEL_THRESHOLDS: List[int] = [0] * (MAX_LEVEL + 1)
_accum = 0
for _lv in range(1, MAX_LEVEL + 1):
    LEVEL_THRESHOLDS[_lv] = _accum
    _accum += int(BASE_XP * math.pow(XP_RATIO, _lv - 1))

# Highest level's lower bound; anything at or above this is maxed out.
MAX_THRESHOLD = LEVEL_THRESHOLDS[MAX_LEVEL]
# Tokens needed to go from MAX_LEVEL to MAX_LEVEL + 1 (kept for display only).
_NEXT_AFTER_MAX_STEP = int(BASE_XP * math.pow(XP_RATIO, MAX_LEVEL - 1))


def stage_for_level(level: int) -> Dict[str, str]:
    """Return the STAGES entry that owns the given level."""
    idx = min(len(STAGES) - 1, max(0, (level - 1) // LEVELS_PER_STAGE))
    return STAGES[idx]


def stage_progress(level: int) -> Tuple[int, int]:
    """Return (position_in_stage, stage_size), both 1-based sizes."""
    idx = min(len(STAGES) - 1, max(0, (level - 1) // LEVELS_PER_STAGE))
    stage_start = idx * LEVELS_PER_STAGE + 1
    return level - stage_start + 1, LEVELS_PER_STAGE


def level_bounds(level: int) -> Tuple[int, int]:
    """Return (tokens_to_reach_level, tokens_to_reach_next_level)."""
    level = max(1, min(MAX_LEVEL, int(level)))
    if level >= MAX_LEVEL:
        return LEVEL_THRESHOLDS[MAX_LEVEL], LEVEL_THRESHOLDS[MAX_LEVEL] + _NEXT_AFTER_MAX_STEP
    return LEVEL_THRESHOLDS[level], LEVEL_THRESHOLDS[level + 1]


def calculate_level(tokens: int, lang: str = "zh") -> Tuple[int, float, int, int, str, str]:
    """
    Map a cumulative token count onto the 100-level ladder.

    Returns
    -------
    (level, progress_ratio, tokens_into_level, tokens_left_in_level, stage_code, stage_title)

    * progress_ratio  : 0.0 - 1.0 progress inside the current level
    * stage_code      : English stage name (e.g. "FURNACE")
    * stage_title     : localized stage name (e.g. "熔炉")
    """
    is_zh = (lang == "zh")
    try:
        tokens = int(tokens or 0)
    except (TypeError, ValueError):
        tokens = 0
    if tokens < 0:
        tokens = 0

    # Max level: everything above MAX_THRESHOLD stays pinned at MAX_LEVEL.
    if tokens >= MAX_THRESHOLD:
        stage = STAGES[-1]
        return (
            MAX_LEVEL,
            1.0,
            tokens - MAX_THRESHOLD,
            0,
            stage["en"],
            stage["zh"] if is_zh else stage["en"],
        )

    # Linear scan is fine (100 items) and immune to the off-by-one bugs the
    # previous reversed-range implementation had.
    level = 1
    for lv in range(MAX_LEVEL, 0, -1):
        if tokens >= LEVEL_THRESHOLDS[lv]:
            level = lv
            break

    floor_tok = LEVEL_THRESHOLDS[level]
    ceil_tok = LEVEL_THRESHOLDS[level + 1] if level < MAX_LEVEL else MAX_THRESHOLD
    span = max(1, ceil_tok - floor_tok)
    into = tokens - floor_tok
    pct = max(0.0, min(1.0, into / span))

    stage = stage_for_level(level)
    return (
        level,
        pct,
        into,
        max(0, ceil_tok - tokens),
        stage["en"],
        stage["zh"] if is_zh else stage["en"],
    )


def format_tokens_zh(n: int) -> str:
    """Compact Chinese number formatting used by the HUD and the poster."""
    try:
        n = int(n or 0)
    except (TypeError, ValueError):
        return "0"
    if n >= 1_000_000_000_000:
        return f"{n / 1_000_000_000_000:.2f} 兆"
    if n >= 100_000_000:
        return f"{n / 100_000_000:.2f} 亿"
    if n >= 10_000:
        return f"{n / 10_000:.1f} 万"
    return f"{n:,}"


if __name__ == "__main__":
    print(f"{'Lv':>4} {'threshold':>20} {'stage':<14} {'stage_zh':<8} {'step':>14}")
    prev = 0
    for lv in [1, 2, 5, 10, 11, 20, 21, 30, 40, 50, 60, 70, 80, 90, 99, 100]:
        stage = stage_for_level(lv)
        print(
            f"{lv:>4} {LEVEL_THRESHOLDS[lv]:>20,} {stage['en']:<14} {stage['zh']:<8} "
            f"{LEVEL_THRESHOLDS[lv] - prev:>14,}"
        )
        prev = LEVEL_THRESHOLDS[lv]
    print()
    print("Lv.100 total:", f"{MAX_THRESHOLD:,}", f"({format_tokens_zh(MAX_THRESHOLD)})")
