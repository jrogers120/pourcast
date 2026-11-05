"""Daily "Tonight in Nashville" Instagram graphic + caption.

Called from build.py. Writes into public/social/:
  <YYYY-MM-DD>.png   1080x1350 portrait image (Instagram feed size)
  <YYYY-MM-DD>.txt   caption
  latest.json        {"date", "image", "caption"} for the posting bot
"""
import json
import os
import re

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = lambda name, size: ImageFont.truetype(os.path.join(HERE, "fonts", name), size)
BOLD = "DejaVuSansCondensed-Bold.ttf"
REG = "DejaVuSansCondensed.ttf"
WIDE = "DejaVuSans-Bold.ttf"

BLUE, NAVY, RED, GOLD, AMBER, WHITE, INK, GREY, PAPER = (
    "#0B3D91", "#072A66", "#D7263D", "#FFC53D", "#F5B12E", "#FFFFFF", "#14213D", "#5B6475", "#F4F6FB")
W, H = 1080, 1350
DOW = ["SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"]
MON = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def _fit(draw, text, font_name, size, max_w):
    while size > 18:
        f = FONT(font_name, size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 2
    return FONT(font_name, size)


def _clip(draw, text, font, max_w):
    if draw.textlength(text, font=font) <= max_w:
        return text
    while text and draw.textlength(text + "…", font=font) > max_w:
        text = text[:-1]
    return text.rstrip() + "…"


def _logo(d, cx, cy, r):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WHITE)
    d.ellipse([cx - r * .9, cy - r * .9, cx + r * .9, cy + r * .9], fill=BLUE)
    s = r / 100
    d.ellipse([cx + 32 * s - 30 * s, cy - 30 * s - 30 * s, cx + 32 * s + 30 * s, cy - 30 * s + 30 * s], fill=GOLD)
    d.rounded_rectangle([cx - 44 * s, cy - 18 * s, cx + 26 * s, cy + 64 * s], radius=8 * s, fill=AMBER)
    d.arc([cx + 10 * s, cy - 2 * s, cx + 56 * s, cy + 44 * s], -90, 90, fill=WHITE, width=max(3, int(10 * s)))
    d.ellipse([cx - 52 * s, cy - 36 * s, cx - 8 * s, cy - 4 * s], fill=WHITE)
    d.ellipse([cx - 22 * s, cy - 44 * s, cx + 22 * s, cy - 6 * s], fill=WHITE)
    d.ellipse([cx + 4 * s, cy - 34 * s, cx + 40 * s, cy - 4 * s], fill=WHITE)


def _matchup(title):
    """'Ravens vs. Jaguars' and 'Jaguars at Ravens' are the same game."""
    parts = re.split(r"\s+(?:vs\.?|at|@)\s+", title.strip(), maxsplit=1, flags=re.I)
    return tuple(sorted(p.strip().lower() for p in parts))


def pick(today_events, bar_label):
    """Group today's events into the sections shown on the graphic."""
    games, seen = [], set()
    for x in sorted([x for x in today_events if x.get("type") in ("college", "game")],
                    key=lambda x: (0 if x["type"] == "college" else 1, x.get("time") or "99")):
        key = _matchup(x["title"])
        if key in seen:
            continue
        seen.add(key)
        bars = [bar_label(y["barId"]) for y in today_events
                if y.get("type") in ("college", "game") and _matchup(y.get("title", "")) == key]
        games.append((x, bars))
    happy = sorted([x for x in today_events if x.get("type") == "happy"], key=lambda x: x.get("time") or "99")
    nights = sorted([x for x in today_events if x.get("type") in ("trivia", "karaoke", "music", "special")],
                    key=lambda x: x.get("time") or "99")
    return games, happy, nights


def make(out_dir, today, today_events, bar_label, when, base_url, pydow):
    games, happy, nights = pick(today_events, bar_label)
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)

    # masthead
    d.rectangle([0, 0, W, 190], fill=BLUE)
    _logo(d, 105, 95, 68)
    d.text((195, 38), "POURCAST", font=FONT(WIDE, 74), fill=WHITE)
    d.text((199, 124), "NASHVILLE  ·  WHAT'S POURING TONIGHT", font=FONT(BOLD, 30), fill=GOLD)
    # red date bar
    d.rectangle([0, 190, W, 262], fill=RED)
    date_txt = f"TONIGHT'S FORECAST  ·  {DOW[pydow(today)]}, {MON[today.month - 1]} {today.day}"
    d.text((48, 205), date_txt, font=_fit(d, date_txt, BOLD, 40, W - 96), fill=WHITE)

    y = 292
    L, R = 48, W - 48

    def section(title, count=None):
        nonlocal y
        d.rectangle([L, y, L + 10, y + 40], fill=RED)
        d.text((L + 26, y - 2), title, font=FONT(BOLD, 38), fill=INK)
        if count:
            f = FONT(BOLD, 28)
            tw = d.textlength(count, font=f)
            d.rounded_rectangle([R - tw - 28, y + 2, R, y + 40], radius=18, fill=BLUE)
            d.text((R - tw - 14, y + 5), count, font=f, fill=WHITE)
        y += 58

    def row(left, main, sub=None):
        nonlocal y
        f_t, f_m, f_s = FONT(BOLD, 30), FONT(BOLD, 34), FONT(REG, 27)
        d.text((L, y + 3), left, font=f_t, fill=RED)
        d.text((L + 190, y), _clip(d, main, f_m, R - L - 190), font=f_m, fill=INK)
        y += 44
        if sub:
            d.text((L + 190, y), _clip(d, sub, f_s, R - L - 190), font=f_s, fill=GREY)
            y += 38
        y += 10

    budget = H - 150  # keep room for footer

    if games:
        section("GAME DAY", f"{len(games)} GAMES")
        for x, bars in games:
            if y > budget - 230:
                break
            more = f" + {len(bars) - 2} more" if len(bars) > 2 else ""
            row(when(x), x["title"] + (f"  ·  {x['tv']}" if x.get("tv") else ""), "Home bars: " + ", ".join(bars[:2]) + more)
        y += 6

    if nights and y < budget - 200:
        section("ON TAP TONIGHT", f"{len(nights)}")
        for x in nights:
            if y > budget - 200:
                break
            row(when(x), x["title"], bar_label(x["barId"]))
        y += 6

    if happy and y < budget - 140:
        section("HAPPY HOUR", f"{len(happy)} DEALS")
        for x in happy:
            if y > budget - 60:
                break
            row(when(x), bar_label(x["barId"]), x.get("deals"))

    if not (games or nights or happy):
        d.text((L, y), "Clear skies tonight. Check back tomorrow.", font=FONT(BOLD, 40), fill=INK)

    # footer
    d.rectangle([0, H - 110, W, H], fill=NAVY)
    ft = "Full list + every happy hour: " + base_url.replace("https://", "")
    d.text((48, H - 82), ft, font=_fit(d, ft, BOLD, 38, W - 96), fill=WHITE)

    os.makedirs(out_dir, exist_ok=True)
    name = today.isoformat()
    img.save(os.path.join(out_dir, f"{name}.png"), optimize=True)

    # caption
    dayname = DOW[pydow(today)].title()
    lines = [f"🍺 Tonight in Nashville: {dayname}, {MON[today.month - 1].title()} {today.day}", ""]
    if games:
        lines.append("🏈 GAME DAY")
        for x, bars in games[:8]:
            lines.append(f"• {when(x)}: {x['title']}" + (f" ({x['tv']})" if x.get("tv") else "") + f", at {bars[0]}" + (f" + {len(bars) - 1} more" if len(bars) > 1 else ""))
        lines.append("")
    if nights:
        lines.append("🎤 ON TAP TONIGHT")
        for x in nights[:8]:
            lines.append(f"• {when(x)}: {x['title']} at {bar_label(x['barId'])}")
        lines.append("")
    if happy:
        lines.append(f"🍻 {len(happy)} happy hours today, including:")
        for x in happy[:6]:
            lines.append(f"• {bar_label(x['barId'])}: {x.get('deals') or x['title']}")
        lines.append("")
    lines += ["Every bar, every deal, every game: link in bio 👉 " + base_url.replace("https://", ""),
              "Hosting something? Post it free on the site.", "",
              "#Nashville #NashvilleBars #NashvilleHappyHour #MusicCity #NashvilleNightlife #SECFootball #Pourcast"]
    caption = "\n".join(lines)[:2150]
    open(os.path.join(out_dir, f"{name}.txt"), "w").write(caption)
    json.dump({"date": name, "image": f"{base_url}/social/{name}.png", "caption": caption},
              open(os.path.join(out_dir, "latest.json"), "w"), ensure_ascii=False)
    return name
