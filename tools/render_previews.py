"""
Regenerate the two README preview images from the real code and real local data.

    python tools/render_previews.py            # both images
    python tools/render_previews.py --hud      # HUD screenshot only
    python tools/render_previews.py --poster   # poster only
    python tools/render_previews.py --manual 92765
                                               # preview the "manual" provenance
                                               # branch without editing config

Why this exists
---------------
The README shipped two preview images that were captured from an older build:
the poster still advertised a fabricated global leaderboard and a ¥34,500
"human labour value", and the HUD still showed the pre-fix counter. A screenshot
that contradicts the text is worse than no screenshot, so the images are now
generated from the same code path the app uses, on demand.

The HUD is a pywebview page: it reads everything from
`window.pywebview.api.get_stats()`. This script stubs that bridge with the REAL
stats produced by `scanner.get_full_stats()` and screenshots the page in
headless Chromium. Nothing is mocked up - the numbers are the ones the app
would show on this machine.

Requirements: `pip install playwright && playwright install chromium`
(the app itself does not need Playwright).
"""
import argparse
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.scanner import get_full_stats                      # noqa: E402
from src.progression import (                               # noqa: E402
    calculate_level, stage_progress, stage_for_level, MAX_LEVEL,
)

ASSETS = ROOT / "assets"
# The window the app actually creates; see apply_rounded_corners() in hud_3d.py.
HUD_WIDTH, HUD_HEIGHT = 460, 295
SCALE = 2                       # 2x so the PNG stays crisp on HiDPI displays


def build_stats(lang="zh", manual_override=None):
    """The same dict hud_3d.HudApi.get_stats() hands to the page."""
    stats = dict(get_full_stats(force=True))
    if manual_override is not None:
        # Preview-only: show what a hand-typed config entry looks like without
        # touching the user's real config.json.
        stats["manual_tokens"] = int(manual_override)
        stats["total_tokens"] = (int(stats.get("verified_tokens", 0))
                                 + int(stats.get("estimated_tokens", 0))
                                 + int(manual_override))
        quality = dict(stats.get("data_quality") or {})
        quality["manual_tokens"] = int(manual_override)
        stats["data_quality"] = quality

    total = stats.get("total_tokens", 0)
    lv, pct, in_level, need_level, stage_code, stage_title = calculate_level(total, lang=lang)
    pos_in_stage, stage_size = stage_progress(lv)
    stage_info = stage_for_level(lv)
    stats.update({
        "lang": lang,
        "skin": stats.get("skin") or "eva",
        "active_model": stats.get("active_model") or "WorkBuddy",
        "active_tool": stats.get("active_tool") or "WorkBuddy",
        "level": lv,
        "max_level": MAX_LEVEL,
        "level_title": stage_title,
        "level_pct": round(pct * 100.0, 1),
        "level_need": need_level,
        "level_into": in_level,
        "stage": stage_code,
        "stage_desc": stage_info.get("desc", ""),
        "stage_index": (lv - 1) // 10 + 1,
        "stage_pos": pos_in_stage,
        "stage_size": stage_size,
        "quality": stats.get("data_quality") or {},
        "verified_tokens": stats.get("verified_tokens", 0),
        "estimated_tokens": stats.get("estimated_tokens", 0),
        "manual_tokens": stats.get("manual_tokens", 0),
        "yolo": {
            "enabled": False, "dry_run": True, "clicks_total": 0, "blocked_total": 0,
            "last_click_time": 0, "last_match_name": "", "last_block_reason": "",
            "last_window": "", "templates_count": 1, "whitelist_processes": [],
            "whitelist_titles": [], "can_click": False, "unavailable": False, "reason": "",
        },
    })
    return stats


def render_hud(stats, out_path):
    from playwright.sync_api import sync_playwright

    stats_json = json.dumps(stats, ensure_ascii=False)
    stub = """
    window.pywebview = { api: {
      get_stats: async () => (%s),
      get_yolo_policy: async () => ({dry_run: true, whitelist_processes: [], whitelist_titles: []}),
      get_yolo_audit_tail: async () => [],
      get_yolo_status: async () => (%s).yolo,
      set_yolo_policy: async () => ({}),
      toggle_yolo: async () => ({}),
      set_skin: async () => ({}),
      set_language: async () => ({}),
      resize_window: async () => ({}),
      export_poster: async () => ({}),
      report_url: async () => "https://github.com/k114413450-stack/TokenBurner/issues/new",
      submit_tool_report: async () => false,
      close_window: async () => ({}),
    }};
    window.addEventListener('load', () => window.dispatchEvent(new Event('pywebviewready')));
    """ % (stats_json, stats_json)

    with sync_playwright() as p:
        browser = p.chromium.launch(args=[
            "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
        ])
        page = browser.new_page(
            viewport={"width": HUD_WIDTH, "height": HUD_HEIGHT},
            device_scale_factor=SCALE,
        )
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.add_init_script(stub)
        page.goto((ROOT / "src" / "hud_3d.html").as_uri())
        page.wait_for_timeout(3500)      # 3D core warm-up + the 850 ms counter tween

        shown = page.evaluate("""() => ({
            total: document.getElementById('lbl-total')?.innerText,
            level: document.getElementById('lbl-level')?.innerText,
            provenance: document.getElementById('lbl-provenance')?.innerText,
        })""")
        page.screenshot(path=str(out_path))
        browser.close()

    if errors:
        raise RuntimeError("HUD page raised: %s" % errors[:3])
    return shown


def render_poster(stats, out_path):
    from src.poster import generate_poster, OUT_POSTER
    generate_poster(stats, auto_open=False)
    shutil.copyfile(OUT_POSTER, out_path)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hud", action="store_true", help="render the HUD screenshot only")
    ap.add_argument("--poster", action="store_true", help="render the poster only")
    ap.add_argument("--manual", type=int, default=None, metavar="N",
                    help="preview the 'manual' provenance branch with N manual tokens")
    args = ap.parse_args()

    do_hud = args.hud or not args.poster
    do_poster = args.poster or not args.hud

    stats = build_stats(manual_override=args.manual)
    print("total     : %s" % f"{stats['total_tokens']:,}")
    print("verified  : %s" % f"{stats['verified_tokens']:,}")
    print("estimated : %s" % f"{stats['estimated_tokens']:,}")
    print("manual    : %s" % f"{stats['manual_tokens']:,}")

    if do_hud:
        out = ASSETS / "hud_preview.png"
        shown = render_hud(stats, out)
        print("hud       : %s  ->  %s" % (shown, out))
    if do_poster:
        out = ASSETS / "war_report_preview.png"
        render_poster(stats, out)
        print("poster    : -> %s" % out)


if __name__ == "__main__":
    main()
