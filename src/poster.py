# -*- coding: utf-8 -*-
# Dynamic 1080x1920 High-Definition Cyberpunk Poster Generator with Streak Compounding
import os
import sys
from PIL import Image, ImageDraw, ImageFont

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

try:
    from scanner import get_full_stats
    from ranking_engine import RankingEngine, calculate_level
    from model_detector import ModelDetector
except ImportError:
    from src.scanner import get_full_stats
    from src.ranking_engine import RankingEngine, calculate_level
    from src.model_detector import ModelDetector

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
    cost_usd = stats.get("est_cost_usd", 0.0)
    rank_percent = stats.get("rank_percent", 90.0)
    title_badge = stats.get("title_badge", "Lv.6 高阶炼丹师")
    streak_days = stats.get("streak_days", 1)
    today_burned = stats.get("today_burned", 0)
    models = stats.get("models", [])
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
    for r in range(450, 0, -10):
        color = (13, 22, 48) if r > 250 else (22, 16, 50)
        draw.ellipse([W//2 - r, 300 - r, W//2 + r, 300 + r], fill=color)

    # Grid background lines
    for y in range(80, H - 80, 140):
        draw.line([(50, y), (W - 50, y)], fill="#111827", width=1)
    for x in range(80, W - 80, 140):
        draw.line([(x, 80), (x, H - 80)], fill="#0c1220", width=1)

    # Header Capsule Tag
    draw.rounded_rectangle([W//2 - 160, 50, W//2 + 160, 90], radius=20, fill="#1e1b4b", outline="#6366f1", width=1)
    draw.text((W // 2, 70), "2026 CYBER TOKEN REPORT", fill="#a5b4fc", font=f_tag, anchor="mm")

    # Main Headline
    draw.text((W // 2, 130), "赛博炼丹师 · 年度 Token 战报", fill="#f8fafc", font=f_title, anchor="mm")
    draw.text((W // 2, 180), "TokenBurner · 全球 AI 极客算力排位认证", fill="#64748b", font=f_sub, anchor="mm")

    # User Profile Pill (With Streak Badge)
    pill_w = 540
    draw.rounded_rectangle([W//2 - pill_w//2, 225, W//2 + pill_w//2, 280], radius=28, fill="#0f172a", outline="#38bdf8", width=1)
    draw.text((W // 2, 252), f"炼丹师: @{nickname} [连续打卡 {streak_days} 天]", fill="#38bdf8", font=f_sm, anchor="mm")

    # Giant Token Counter Card
    card_y = 320
    draw.rounded_rectangle([60, card_y, W - 60, card_y + 360], radius=24, fill="#0f172a", outline="#2563eb", width=2)
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
    draw.text((W // 2, card_y + 205), f"精确数值: {tokens:,} Tokens", fill="#64748b", font=f_sm, anchor="mm")
    
    # 100-Level RPG Progression and Model Leaderboard
    lv, pct, in_level, need_level, era_name, title_name = calculate_level(tokens, lang="zh")
    
    detector = ModelDetector()
    active_model = stats.get("active_model", detector.active_model_name)
    ranking = RankingEngine()
    lb = ranking.get_model_leaderboard(active_model, tokens, nickname)
    model_rank = lb.get("my_rank", 1)
    model_beat = lb.get("beat_percentage", 99.0)

    # Sub-data row (Cost & Percentile)
    draw.line([(100, card_y + 240), (W - 100, card_y + 240)], fill="#1e293b", width=1)
    
    # Calculate intelligent labor saving (250 CNY/hr)
    saved_hours = int((tokens / 1_000_000) * 5)
    saved_cny = saved_hours * 250
    draw.text((260, card_y + 285), "AI 替代人工劳动力价值", fill="#64748b", font=f_sm, anchor="mm")
    draw.text((260, card_y + 325), f"¥{saved_cny:,} 人民币", fill="#10b981", font=f_h2, anchor="mm")

    draw.text((W - 260, card_y + 285), "全网综合算力天梯", fill="#64748b", font=f_sm, anchor="mm")
    draw.text((W - 260, card_y + 325), f"#{model_rank} (TOP {100 - model_beat:.1f}%)", fill="#f59e0b", font=f_h2, anchor="mm")

    # Title & Badge Section (100 Level RPG)
    badge_y = 720
    draw.rounded_rectangle([60, badge_y, W - 60, badge_y + 180], radius=20, fill="#1a102f", outline="#8b5cf6", width=2)
    draw.rounded_rectangle([W//2 - 140, badge_y + 25, W//2 + 140, badge_y + 60], radius=15, fill="#4c1d95")
    draw.text((W // 2, badge_y + 42), f"{era_name} · 官方认证段位", fill="#ddd6fe", font=f_tag, anchor="mm")
    draw.text((W // 2, badge_y + 115), f"★ Lv.{lv} {title_name} ★", fill="#fbbf24", font=f_h2, anchor="mm")

    # 24H Token Surge Momentum Stock-style Chart
    chart_y = 930
    draw.rounded_rectangle([60, chart_y, W - 60, chart_y + 400], radius=24, fill="#0b1120", outline="#1e293b", width=2)
    draw.line([(100, chart_y + 2), (W - 100, chart_y + 2)], fill="#10b981", width=3)
    
    draw.text((100, chart_y + 45), "▲ 24H 算力激增动能走势", fill="#f8fafc", font=f_h2)
    draw.text((100, chart_y + 85), "24H SURGE MOMENTUM // 极速放量拉升突破", fill="#64748b", font=f_tag)

    # Bullish Rally Badge
    badge_w = 230
    draw.rounded_rectangle([W - 100 - badge_w, chart_y + 35, W - 100, chart_y + 80], radius=16, fill="#064e3b", outline="#10b981", width=1)
    draw.text((W - 100 - badge_w // 2, chart_y + 57), "+184.2% ▲ BULLISH", fill="#34d399", font=f_tag, anchor="mm")

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

    # Parabolic surge curve data points (simulating exponential 24H token burn)
    curve_rel = [
        0.04, 0.05, 0.04, 0.06, 0.08, 0.11, 0.14, 0.18,
        0.23, 0.28, 0.33, 0.38, 0.45, 0.52, 0.59, 0.66,
        0.73, 0.81, 0.88, 0.94, 0.98, 1.00
    ]
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
    callout_w = 260
    bx1 = pk_x - callout_w + 10
    by1 = pk_y - 48
    draw.rounded_rectangle([bx1, by1, bx1 + callout_w, by1 + 34], radius=10, fill="#042f2e", outline="#10b981", width=1)
    
    if today_burned >= 10000:
        td_str = f"+{today_burned/10000:.1f}万"
    elif today_burned > 0:
        td_str = f"+{today_burned:,}"
    else:
        td_str = "+82.5万"
    draw.text((bx1 + callout_w // 2, by1 + 17), f"★ 今日狂暴: {td_str} ↑", fill="#34d399", font=f_sm, anchor="mm")

    # X-axis time milestones
    time_nodes = [("00:00", 0.0), ("06:00", 0.25), ("12:00", 0.50), ("18:00", 0.75), ("NOW 24H", 1.0)]
    for lbl, r in time_nodes:
        lx = int(cx1 + r * cw)
        anchor = "lm" if r == 0 else ("rm" if r == 1.0 else "mm")
        draw.text((lx, cy2 + 25), lbl, fill="#64748b", font=f_tag, anchor=anchor)

    # Cyberpunk Equivalent Power Benchmark section
    fun_y = 1370
    draw.rounded_rectangle([60, fun_y, W - 60, fun_y + 310], radius=20, fill="#0b1329", outline="#1e293b", width=2)
    draw.text((100, fun_y + 45), "■ 你的 Token 战力相当于什么？", fill="#f8fafc", font=f_h2)

    books = max(1, int(tokens / 1000000))
    lines = max(100, int(tokens * 3.4))
    coffee = max(5, int(tokens / 230000))
    hours = max(1, int(tokens / 260000))

    equivalents = [
        ("【经典研读】", f"精读了 {books} 本《资治通鉴》全书文本", "#38bdf8"),
        ("【代码熔炉】", f"编写并重构了 {lines:,} 行生产级架构代码", "#10b981"),
        ("【赛博能量】", f"折合消耗了 {coffee} 杯极客夜班浓缩咖啡", "#f59e0b"),
        ("【Agent驱动】", f"驱动 AI 自主 Agent 连续无人值守运行 {hours} 小时", "#a855f7")
    ]
    for i, (tag, txt, col) in enumerate(equivalents):
        ey = fun_y + 92 + i * 52
        draw.rounded_rectangle([100, ey - 6, 230, ey + 28], radius=8, fill="#111c38", outline=col, width=1)
        draw.text((165, ey + 11), tag, fill=col, font=f_tag, anchor="mm")
        draw.text((250, ey + 11), txt, fill="#cbd5e1", font=f_sm, anchor="lm")

    # Bottom Footer CTA (Streak Lock-in)
    draw.line([(80, 1720), (W - 80, 1720)], fill="#1e293b", width=1)
    draw.text((W // 2, 1765), "测测你今年烧了多少 Token？", fill="#38bdf8", font=f_h2, anchor="mm")
    draw.text((W // 2, 1815), f"已持续追踪 {streak_days} 天 · 微信扫码加入极客天梯榜", fill="#94a3b8", font=f_sm, anchor="mm")
    draw.text((W // 2, 1855), "TOKENBURNER.IO · 2026 CYBER ALCHEMIST LEAGUE", fill="#475569", font=f_tag, anchor="mm")

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
