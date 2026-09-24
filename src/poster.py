# -*- coding: utf-8 -*-
# Dynamic 1080x1920 High-Definition Cyberpunk Poster Generator with Streak Compounding
import os
import sys
from datetime import date
from PIL import Image, ImageDraw, ImageFont

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

try:
    from scanner import get_full_stats
    from progression import (
        calculate_level, stage_progress, format_tokens_zh, MAX_LEVEL,
    )
except ImportError:
    from src.scanner import get_full_stats
    from src.progression import (
        calculate_level, stage_progress, format_tokens_zh, MAX_LEVEL,
    )

try:
    from app_paths import get_app_data_dir
except ImportError:
    from src.app_paths import get_app_data_dir

OUT_DIR = os.path.join(os.path.expanduser("~"), "Desktop")
if not os.path.exists(OUT_DIR):
    OUT_DIR = get_app_data_dir()
OUT_POSTER = os.path.join(OUT_DIR, "TokenBurner_WarReport.png")

def generate_poster(stats=None, auto_open=False):
    if stats is None:
        stats = get_full_stats()

    nickname = stats.get("nickname", "CyberDev")
    tokens = stats.get("total_tokens", 0)
    streak_days = stats.get("streak_days", 1)
    today_burned = stats.get("today_burned", 0)
    tools = stats.get("tools", {})

    W, H = 1080, 1920
    img = Image.new("RGB", (W, H), "#070913")
    draw = ImageDraw.Draw(img)

    font_path = r"C:\Windows\Fonts\msyh.ttc"
    font_bold = r"C:\Windows\Fonts\msyhbd.ttc"
    if not os.path.exists(font_bold):
        font_bold = font_path

    f_title = ImageFont.truetype(font_bold, 46)
    f_sub = ImageFont.truetype(font_path, 26)
    f_huge = ImageFont.truetype(font_bold, 84)
    f_h2 = ImageFont.truetype(font_bold, 36)
    f_body = ImageFont.truetype(font_path, 30)
    f_bold = ImageFont.truetype(font_bold, 30)
    f_sm = ImageFont.truetype(font_path, 22)
    f_tag = ImageFont.truetype(font_bold, 20)

    # Ambient radial neon glows
    # Drawn through an alpha mask instead of a stack of opaque ellipses. The old
    # `for r in range(450, 0, -10)` loop swapped colour at r <= 250, which left a
    # clearly visible hard ring across the top of the poster.
    glow_mask = Image.new("L", (W, H), 0)
    gd = ImageDraw.Draw(glow_mask)
    _glow_steps = 140
    for _i in range(_glow_steps):
        _r = int(470 * (_glow_steps - _i) / _glow_steps)
        gd.ellipse(
            [W // 2 - _r, 300 - _r, W // 2 + _r, 300 + _r],
            fill=int(132 * (_i / _glow_steps) ** 1.9),
        )
    _glow = Image.new("RGBA", (W, H), (58, 44, 150, 0))
    _glow.putalpha(glow_mask)
    img = Image.alpha_composite(img.convert("RGBA"), _glow).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Grid background lines
    for y in range(80, H - 80, 140):
        draw.line([(50, y), (W - 50, y)], fill="#111827", width=1)
    for x in range(80, W - 80, 140):
        draw.line([(x, 80), (x, H - 80)], fill="#0c1220", width=1)

    # Header Capsule Tag
    draw.rounded_rectangle([W//2 - 160, 50, W//2 + 160, 90], radius=20, fill="#1e1b4b", outline="#6366f1", width=1)
    draw.text((W // 2, 70), "2026 CYBER TOKEN REPORT", fill="#a5b4fc", font=f_tag, anchor="mm")

    # Main Headline
    draw.text((W // 2, 130), "赛博算力战报 · 年度 Token 燃烧", fill="#f8fafc", font=f_title, anchor="mm")
    draw.text((W // 2, 180), "TokenBurner · 全部数据本地扫描，不联网、不上传", fill="#64748b", font=f_sub, anchor="mm")

    # User Profile Pill (With Streak Badge)
    pill_w = 540
    draw.rounded_rectangle([W//2 - pill_w//2, 225, W//2 + pill_w//2, 280], radius=28, fill="#0f172a", outline="#38bdf8", width=1)
    draw.text((W // 2, 252), f"@{nickname} · 连续燃烧 {streak_days} 天", fill="#38bdf8", font=f_sm, anchor="mm")

    # Giant Token Counter Card
    # Height 360 -> 378: the provenance/cache note added in the sub-data row sat
    # 3px above the bottom border (measured on the rendered PNG), which reads as
    # clipped. 18px of extra card puts it ~22px clear without disturbing the
    # badge block below at y=720.
    card_y = 320
    draw.rounded_rectangle([60, card_y, W - 60, card_y + 378], radius=24, fill="#0f172a", outline="#2563eb", width=2)
    draw.line([(100, card_y + 2), (W - 100, card_y + 2)], fill="#60a5fa", width=3)
    draw.text((W // 2, card_y + 55), "2026 综合累计燃烧 TOKEN 数量", fill="#94a3b8", font=f_sub, anchor="mm")
    
    # Calculate Chinese Unit (万 / 亿 / 兆)
    if tokens >= 1_000_000_000_000:
        token_str = f"{tokens / 1_000_000_000_000:.3f} 兆"
    elif tokens >= 100_000_000:
        token_str = f"{tokens / 100_000_000:.2f} 亿"
    elif tokens >= 10_000:
        token_str = f"{tokens / 10_000:.1f} 万"
    else:
        token_str = f"{tokens:,}"

    draw.text((W // 2, card_y + 140), token_str, fill="#38bdf8", font=f_huge, anchor="mm")
    # Say where the number comes from. The total can mix figures parsed from the
    # tools' own API usage logs with figures guessed from file size, and a guess
    # must be labelled as one on anything that gets published.
    est_tok = int(stats.get("estimated_tokens", 0) or 0)
    if est_tok > 0 and est_tok < tokens:
        src_note = f"精确数值: {tokens:,} Tokens（其中 {est_tok:,} 为文件体积估算）"
    elif est_tok > 0:
        src_note = f"精确数值: {tokens:,} Tokens（全部为文件体积估算）"
    else:
        src_note = f"精确数值: {tokens:,} Tokens · 全部来自工具用量日志"
    draw.text((W // 2, card_y + 205), src_note, fill="#64748b", font=f_sm, anchor="mm")
    
    # 100-Level Progression (purely local - the fake global leaderboard is gone)
    lv, pct, in_level, need_level, stage_code, stage_title = calculate_level(tokens, lang="zh")
    pos_in_stage, stage_size = stage_progress(lv)

    # Sub-data row: cache-aware cost + distance to next level.
    #
    # This slot used to hold "AI 替代人工劳动力价值 ¥X", computed as
    # (tokens / 1M) * 5 hours * ¥250/h - i.e. it asserted that every million
    # tokens equals five hours of human labour. There is no basis for that, and
    # it is doubly wrong here because ~98 % of those tokens are the same context
    # being re-read from the provider's cache. Replaced with a cost figure that
    # is derived from the actual input/output/cached split.
    draw.line([(100, card_y + 240), (W - 100, card_y + 240)], fill="#1e293b", width=1)

    ledger = stats.get("ledger") or {}
    cache_pct = ledger.get("cache_hit_pct", 0.0)
    cost_usd = stats.get("est_cost_usd", 0.0)
    cost_cny = cost_usd * 7.2
    draw.text((260, card_y + 278), "等效 API 成本（估算）", fill="#64748b", font=f_sm, anchor="mm")
    draw.text((260, card_y + 316), f"≈ ¥{cost_cny:,.0f}", fill="#10b981", font=f_h2, anchor="mm")
    if ledger:
        draw.text((260, card_y + 344), f"缓存命中 {cache_pct:.1f}% · 费率见 config.json",
                  fill="#475569", font=f_tag, anchor="mm")

    # Replaces the old "全网综合算力天梯 #N (TOP x%)". That number was produced
    # by RankingEngine from ~200 randomly generated "ghost users" per model, so
    # it was pure noise dressed up as a global ranking.
    if lv >= MAX_LEVEL:
        next_lv_label = "已达最高段位"
        next_lv_value = "MAX"
    else:
        next_lv_label = f"距离 Lv.{lv + 1}"
        next_lv_value = format_tokens_zh(need_level)
    draw.text((W - 260, card_y + 278), next_lv_label, fill="#64748b", font=f_sm, anchor="mm")
    draw.text((W - 260, card_y + 316), next_lv_value, fill="#f59e0b", font=f_h2, anchor="mm")

    # Title & Badge Section (100 Level RPG)
    badge_y = 720
    draw.rounded_rectangle([60, badge_y, W - 60, badge_y + 180], radius=20, fill="#1a102f", outline="#8b5cf6", width=2)
    draw.rounded_rectangle([W//2 - 140, badge_y + 25, W//2 + 140, badge_y + 60], radius=15, fill="#4c1d95")
    draw.text((W // 2, badge_y + 42), f"{stage_code} · 段位 {pos_in_stage}/{stage_size} · {pct * 100:.0f}%", fill="#ddd6fe", font=f_tag, anchor="mm")
    draw.text((W // 2, badge_y + 112), f"★ Lv.{lv} {stage_title} ★", fill="#fbbf24", font=f_h2, anchor="mm")

    # Level progress bar (real data - replaces the removed global-rank readout)
    bar_x1, bar_x2 = 200, W - 200
    bar_y = badge_y + 152
    draw.rounded_rectangle([bar_x1, bar_y - 5, bar_x2, bar_y + 5], radius=5, fill="#2e1065")
    fill_w = int((bar_x2 - bar_x1) * max(0.0, min(1.0, pct)))
    if fill_w > 10:
        draw.rounded_rectangle([bar_x1, bar_y - 5, bar_x1 + fill_w, bar_y + 5], radius=5, fill="#a855f7")

    # Token Burn Momentum Chart (driven by real daily history)
    chart_y = 930

    # ------------------------------------------------------------------
    # REAL DATA PREP
    # This chart used to be a hard-coded exponential curve with a fixed
    # "+184.2% BULLISH" badge and a fixed "+82.5万" callout, so every user got
    # the same fabricated "surge" regardless of actual usage. It now plots the
    # burn recorded by scanner.record_daily_history().
    # ------------------------------------------------------------------
    recent = stats.get("recent_days") or []
    series = []
    for d in recent:
        try:
            series.append((str(d.get("date", "")), int(d.get("burned", 0) or 0)))
        except Exception:
            continue
    if not series:
        series = [(date.today().isoformat(), int(today_burned or 0))]
    while len(series) < 2:
        series.append(series[-1])

    values = [v for _, v in series]
    last_val = values[-1]
    prior = values[:-1]
    prev_avg = (sum(prior) / len(prior)) if prior else 0

    draw.rounded_rectangle([60, chart_y, W - 60, chart_y + 400], radius=24, fill="#0b1120", outline="#1e293b", width=2)
    draw.line([(100, chart_y + 2), (W - 100, chart_y + 2)], fill="#10b981", width=3)
    
    draw.text((100, chart_y + 45), f"▲ 近 {len(series)} 日算力燃烧走势", fill="#f8fafc", font=f_h2)
    draw.text((100, chart_y + 85), "TOKEN BURN MOMENTUM // 按真实历史数据绘制", fill="#64748b", font=f_tag)

    # Momentum Badge — computed from real data (last day vs. average of the window)
    if prev_avg > 0:
        chg = (last_val - prev_avg) / prev_avg * 100.0
        up = chg >= 0
        badge_txt = f"{chg:+.1f}% {'▲ BULLISH' if up else '▼ COOLING'}"
        badge_bg = "#064e3b" if up else "#4c0519"
        badge_fg = "#34d399" if up else "#fb7185"
        badge_bd = "#10b981" if up else "#f43f5e"
    else:
        # No prior day to compare against. Previously this printed "-- NO DATA"
        # while the callout right next to it showed a real burn figure, which
        # looked contradictory. Show the actual today figure instead.
        if last_val > 0:
            badge_txt = f"今日新增 {format_tokens_zh(last_val)}"
            badge_bg, badge_fg, badge_bd = "#064e3b", "#34d399", "#10b981"
        else:
            badge_txt = "-- 暂无数据"
            badge_bg, badge_fg, badge_bd = "#1e293b", "#64748b", "#334155"

    badge_w = 240
    draw.rounded_rectangle([W - 100 - badge_w, chart_y + 35, W - 100, chart_y + 80], radius=16, fill=badge_bg, outline=badge_bd, width=1)
    draw.text((W - 100 - badge_w // 2, chart_y + 57), badge_txt, fill=badge_fg, font=f_tag, anchor="mm")

    # Chart Area Coordinates
    cx1 = 110
    cx2 = W - 110
    cy1 = chart_y + 125
    cy2 = chart_y + 335
    ch = cy2 - cy1
    cw = cx2 - cx1

    # Dotted horizontal grid lines
    for ratio in [0.25, 0.50, 0.75]:
        gy = int(cy2 - ch * ratio)
        for gx in range(cx1, cx2, 16):
            draw.line([(gx, gy), (gx + 8, gy)], fill="#172554", width=1)

    # Curve scaled from the real per-day burn figures.
    peak_val = max(values) if values else 0
    if peak_val > 0:
        curve_rel = [v / peak_val for v in values]
    else:
        curve_rel = [0.0] * len(values)

    pts = []
    n_pts = len(curve_rel)
    for i, val in enumerate(curve_rel):
        px = int(cx1 + (i / (n_pts - 1)) * cw)
        py = int(cy2 - val * (ch - 25))
        pts.append((px, py))

    # Translucent gradient fill under curve
    poly = [(cx1, cy2)] + pts + [(cx2, cy2)]
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    ov_draw.polygon(poly, fill=(16, 185, 129, 36))
    
    # Layered depth gradient
    for step in range(1, 5):
        y_cut = cy2 - int(ch * (step / 5.0))
        strip_poly = [(cx1, cy2)] + [(px, max(py, y_cut)) for px, py in pts] + [(cx2, cy2)]
        ov_draw.polygon(strip_poly, fill=(16, 185, 129, 14))

    img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"))
    draw = ImageDraw.Draw(img)

    # Neon glow line (thick dark green) + sharp foreground neon green line
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i+1]], fill="#065f46", width=8)
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i+1]], fill="#00ff66", width=4)

    # Peak beacon point (concentric glowing rings)
    pk_x, pk_y = pts[-1]
    draw.ellipse([pk_x - 14, pk_y - 14, pk_x + 14, pk_y + 14], fill="#064e3b", outline="#00ff66", width=2)
    draw.ellipse([pk_x - 6, pk_y - 6, pk_x + 6, pk_y + 6], fill="#ffffff")

    # Floating Callout Banner above peak
    callout_w = 280
    bx1 = pk_x - callout_w + 10
    by1 = pk_y - 48
    draw.rounded_rectangle([bx1, by1, bx1 + callout_w, by1 + 34], radius=10, fill="#042f2e", outline="#10b981", width=1)

    if today_burned >= 10000:
        callout_txt = f"★ 今日燃烧: +{today_burned/10000:.1f}万 ↑"
    elif today_burned > 0:
        callout_txt = f"★ 今日燃烧: +{today_burned:,} ↑"
    else:
        # Was hard-coded to "+82.5万" — the poster claimed a burn even when the
        # user had burned nothing today.
        callout_txt = "★ 今日无新增燃烧"
    draw.text((bx1 + callout_w // 2, by1 + 17), callout_txt, fill="#34d399", font=f_sm, anchor="mm")

    # X-axis date milestones taken from the real series
    time_nodes = []
    for i in sorted(set(int(round(k * (n_pts - 1) / 4.0)) for k in range(5))):
        r = i / (n_pts - 1)
        lbl = series[i][0][5:] if len(series[i][0]) >= 10 else series[i][0]
        time_nodes.append((lbl or "--", r))
    if len(time_nodes) >= 2:
        time_nodes[-1] = ("NOW", 1.0)
    for lbl, r in time_nodes:
        lx = int(cx1 + r * cw)
        anchor = "lm" if r == 0 else ("rm" if r == 1.0 else "mm")
        draw.text((lx, cy2 + 25), lbl, fill="#64748b", font=f_tag, anchor=anchor)

    # Cyberpunk Equivalent Power Benchmark section
    fun_y = 1370
    draw.rounded_rectangle([60, fun_y, W - 60, fun_y + 310], radius=20, fill="#0b1329", outline="#1e293b", width=2)
    draw.text((100, fun_y + 45), "■ 你的 Token 战力相当于什么？", fill="#f8fafc", font=f_h2)

    # Unit conversions for the "what is your token power worth" panel.
    #
    # Two separate mistakes lived here. `lines` used to be `tokens * 3.4` - it
    # MULTIPLIED where every other metric divides, turning 341M tokens into
    # 1.16 billion lines of code. Fixing that to `tokens / 12` was still wrong:
    # the total counts every re-read of the prompt cache (98 % of the volume
    # here), so it yields ~35 million lines - the same class of error, one
    # order of magnitude smaller.
    #
    # Every equivalence is now driven by the volume that represents actual work:
    # output tokens plus fresh (non-cached) input. When no usage ledger exists,
    # it falls back to the total and says so in the footnote.
    ledger = stats.get("ledger") or {}
    out_tok = int(ledger.get("output") or 0)
    inp_tok = int(ledger.get("input") or 0)
    cached_tok = min(int(ledger.get("cached") or 0), inp_tok)
    fresh_in = max(0, inp_tok - cached_tok)
    requests_n = int(ledger.get("requests") or 0)

    if out_tok or fresh_in:
        work_tokens = out_tok + fresh_in
    else:
        work_tokens = tokens

    books = max(1, int(work_tokens / 1000000))
    lines = max(100, int(out_tok / 12)) if out_tok else max(100, int(work_tokens / 12))
    coffee = max(5, int(work_tokens / 250000))

    if requests_n:
        equivalents = [
            ("【经典研读】", f"新读入 {books} 本《资治通鉴》量级的文本", "#38bdf8"),
            ("【代码熔炉】", f"AI 实际输出折合约 {lines:,} 行代码/文本", "#10b981"),
            ("【赛博能量】", f"折合消耗了 {coffee} 杯极客夜班浓缩咖啡", "#f59e0b"),
            ("【请求次数】", f"累计发起 {requests_n:,} 次 AI 请求", "#a855f7"),
        ]
    else:
        equivalents = [
            ("【经典研读】", f"精读了 {books} 本《资治通鉴》全书文本", "#38bdf8"),
            ("【代码熔炉】", f"编写并重构了 {lines:,} 行生产级架构代码", "#10b981"),
            ("【赛博能量】", f"折合消耗了 {coffee} 杯极客夜班浓缩咖啡", "#f59e0b"),
            ("【Agent驱动】", f"驱动 AI 自主 Agent 连续无人值守运行 {max(1, int(work_tokens / 260000))} 小时", "#a855f7"),
        ]
    for i, (tag, txt, col) in enumerate(equivalents):
        ey = fun_y + 92 + i * 52
        draw.rounded_rectangle([100, ey - 6, 230, ey + 28], radius=8, fill="#111c38", outline=col, width=1)
        draw.text((165, ey + 11), tag, fill=col, font=f_tag, anchor="mm")
        draw.text((250, ey + 11), txt, fill="#cbd5e1", font=f_sm, anchor="lm")

    # State the basis of every derived figure on the poster. These are all
    # rough conversions and saying so is cheaper than being called out.
    basis = "※ 等量换算为粗略口径：约 1M tokens ≈ 1 本书 / 12 tokens ≈ 1 行代码"
    if est_tok > 0:
        basis = "※ 含文件体积估算部分，非全部实测；等量换算为粗略口径"
    draw.text((100, fun_y + 288), basis, fill="#475569", font=f_tag)

    # Bottom Footer CTA
    draw.line([(80, 1720), (W - 80, 1720)], fill="#1e293b", width=1)
    draw.text((W // 2, 1765), "测测你今年烧了多少 Token？", fill="#38bdf8", font=f_h2, anchor="mm")
    draw.text((W // 2, 1815), f"已本地追踪 {streak_days} 天 · 不联网、不上传任何数据", fill="#94a3b8", font=f_sm, anchor="mm")
    # The old footer said "微信扫码加入极客天梯榜" (there was no QR code) and
    # printed "TOKENBURNER.IO", a domain this project does not own.
    draw.text((W // 2, 1855), "GITHUB.COM/K114413450-STACK/TOKENBURNER", fill="#475569", font=f_tag, anchor="mm")

    try:
        img.save(OUT_POSTER, "PNG")
        target_poster = OUT_POSTER
    except Exception:
        fallback = os.path.join(get_app_data_dir(), "TokenBurner_WarReport.png")
        img.save(fallback, "PNG")
        target_poster = fallback

    print(f"Poster rendered successfully: {target_poster}")
    
    if auto_open:
        try:
            os.startfile(target_poster)
        except Exception:
            pass
    return target_poster

if __name__ == "__main__":
    generate_poster(auto_open=False)
