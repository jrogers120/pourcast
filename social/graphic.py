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


SEC = ["alabama", "arkansas", "auburn", "florida", "georgia", "kentucky", "lsu", "mississippi state", "missouri",
       "oklahoma", "ole miss", "south carolina", "tennessee", "texas", "texas a&m", "vanderbilt"]
LOCAL = ["tennessee", "vanderbilt", "titans"]
BIG_TV = ["abc", "cbs", "nbc", "fox", "espn"]


def _score(game, bars):
    """Rough 'how much will Nashville care' score, used when no editor pick exists."""
    teams = [t.strip() for t in _matchup(game["title"])]
    sc = 0
    sc += 6 * sum(1 for t in teams if any(t == l or t.endswith(" " + l) or t == l + "s" for l in LOCAL))
    sc += 3 * sum(1 for t in teams if t in SEC)
    sc += min(len(bars), 6)
    tv = (game.get("tv") or "").lower()
    sc += 3 if any(tv.startswith(n) for n in BIG_TV) else 0
    sc += 2 if (game.get("time") or "") >= "18:00" else 0
    return sc


def headliners(games, picks_for_day):
    """(good, bad) as (event, bars, blurb), or None. Editor picks in data/picks.json win."""
    if not games:
        return None, None
    by_key = {_matchup(g["title"]): (g, b) for g, b in games}
    good = bad = None
    p = picks_for_day or {}
    if p.get("good") and _matchup(p["good"]) in by_key:
        good = by_key[_matchup(p["good"])] + (p.get("goodWhy") or "",)
    if p.get("bad") and _matchup(p["bad"]) in by_key:
        bad = by_key[_matchup(p["bad"])] + (p.get("badWhy") or "",)
    # Without today's betting lines we can't call a game close or a blowout, so:
    # fall back to the game Nashville cares most about, and skip the bad game.
    if not good:
        good = sorted(games, key=lambda gb: _score(*gb), reverse=True)[0] + ("",)
    if bad and _matchup(bad[0]["title"]) == _matchup(good[0]["title"]):
        bad = None
    return good, bad


GOOD_TAGS = ["CLEAR SKIES", "HIGH PRESSURE SYSTEM", "HEAT WAVE ALERT", "SUNNY & SIZZLING", "PERFECT CONDITIONS"]
BAD_TAGS = ["BLOWOUT WARNING", "FLOOD WATCH", "COLD FRONT", "FOG ADVISORY", "HIGH WIND WARNING"]
GOOD_PUNS = [
    "Two fronts colliding. Expect thunder in every bar.",
    "Pressure's building all night. Bring a rain jacket for the spills.",
    "Forecast: 100% chance of nail-biting with scattered high-fives.",
    "Conditions are perfect for a late-night lightning strike.",
    "Barometer says this one goes down to the final drop.",
    "Warm, humid and tight. The kind of air you can cut with a knife.",
]
BAD_PUNS = [
    "Flood warning: one side's getting washed out early.",
    "Severe yawn advisory. Happy hour is the better forecast.",
    "Gusts up to 30 points. Secure your remote.",
    "Fog rolling in by halftime. Visibility on the outcome: zero.",
    "Cold front moving in. Expect a mass exodus to the patio.",
    "Expect a one-sided downpour. Umbrellas for the underdog.",
]


def _pun(options, today, salt=0):
    return options[(today.toordinal() + salt) % len(options)]


def _sun(d, cx, cy, r):
    import math
    for i in range(12):
        a = math.radians(i * 30)
        d.line([cx + math.cos(a) * r * 1.25, cy + math.sin(a) * r * 1.25, cx + math.cos(a) * r * 1.65, cy + math.sin(a) * r * 1.65],
               fill=GOLD, width=max(4, int(r * .16)))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GOLD, outline=AMBER, width=4)


def _storm(d, cx, cy, r):
    cloud = "#5B6475"
    for dx, dy, rr in [(-.55, .1, .55), (0, -.25, .7), (.6, .1, .5)]:
        d.ellipse([cx + dx * r - rr * r, cy + dy * r - rr * r, cx + dx * r + rr * r, cy + dy * r + rr * r], fill=cloud)
    d.rounded_rectangle([cx - 1.05 * r, cy - .05 * r, cx + 1.05 * r, cy + .62 * r], radius=int(.3 * r), fill=cloud)
    d.polygon([(cx + .05 * r, cy + .45 * r), (cx - .35 * r, cy + 1.15 * r), (cx - .02 * r, cy + 1.1 * r),
               (cx - .2 * r, cy + 1.65 * r), (cx + .38 * r, cy + .85 * r), (cx + .05 * r, cy + .88 * r), (cx + .28 * r, cy + .45 * r)], fill=GOLD)
    for x in (-.75, .7):
        d.line([cx + x * r, cy + .8 * r, cx + (x - .15) * r, cy + 1.2 * r], fill="#6FA8FF", width=6)


DRINK_TAGS = ["100% CHANCE OF SIPS", "SCATTERED SHAKERS", "LIGHT DRIZZLE OF BITTERS", "TROPICAL FRONT",
              "COCKTAIL ADVISORY", "CHILL IN THE AIR"]


def drink_for(today, picks_for_day, drinks, bar_ok):
    """Editor/scheduled pick from picks.json wins; otherwise rotate the saved list by date."""
    p = (picks_for_day or {}).get("drink")
    if p and p.get("name") and bar_ok(p.get("barId")):
        return p
    pool = [x for x in (drinks or []) if bar_ok(x.get("barId"))]
    if not pool:
        return None
    import random
    order = list(range(len(pool)))
    random.Random(len(pool)).shuffle(order)  # fixed shuffle so it doesn't go bar-by-bar
    return pool[order[today.toordinal() % len(pool)]]


def _glass(d, cx, cy, r):
    d.polygon([(cx - r, cy - r * .8), (cx + r, cy - r * .8), (cx, cy + r * .35)], fill="#F8D7E3", outline=WHITE)
    d.polygon([(cx - r * .78, cy - r * .62), (cx + r * .78, cy - r * .62), (cx, cy + r * .2)], fill=RED)
    d.line([cx, cy + r * .35, cx, cy + r * 1.05], fill=WHITE, width=max(4, int(r * .12)))
    d.ellipse([cx - r * .55, cy + r * .98, cx + r * .55, cy + r * 1.18], fill=WHITE)
    d.line([cx + r * .15, cy - r * 1.15, cx - r * .25, cy - r * .2], fill="#8B5A2B", width=4)
    d.ellipse([cx - r * .02, cy - r * 1.02, cx + r * .32, cy - r * .7], fill="#7BB661", outline="#4E7F3A", width=2)


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


def make(out_dir, today, today_events, bar_label, when, base_url, pydow, picks=None, drinks=None, bar_ok=None):
    games, happy, nights = pick(today_events, bar_label)
    good, bad = headliners(games, (picks or {}).get(today.isoformat()))
    drink = drink_for(today, (picks or {}).get(today.isoformat()), drinks, bar_ok or (lambda b: bool(b)))
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)

    # masthead
    d.rectangle([0, 0, W, 190], fill=BLUE)
    _logo(d, 105, 95, 68)
    d.text((195, 38), "POURCAST", font=FONT(WIDE, 74), fill=WHITE)
    d.text((199, 124), "NASHVILLE, TN  ·  WHAT'S POURING TONIGHT", font=FONT(BOLD, 30), fill=GOLD)
    # red date bar
    d.rectangle([0, 190, W, 262], fill=RED)
    date_txt = f"TONIGHT'S FORECAST  ·  {DOW[pydow(today)]}, {MON[today.month - 1]} {today.day}"
    d.text((48, 205), date_txt, font=_fit(d, date_txt, BOLD, 40, W - 96), fill=WHITE)

    y = 292
    L, R = 48, W - 48

    def hero(item, kind):
        nonlocal y
        g, bars, why = item
        good_kind = kind == "good"
        h = 196
        d.rounded_rectangle([L, y, R, y + h], radius=14, fill=WHITE if good_kind else "#E9ECF3",
                            outline=GOLD if good_kind else "#9AA3B5", width=5)
        (_sun if good_kind else _storm)(d, L + 92, y + h // 2 - (0 if good_kind else 22), 46 if good_kind else 50)
        tx = L + 190
        tag = ("GAME OF THE DAY  ·  " + _pun(GOOD_TAGS, today)) if good_kind else ("BAD GAME OF THE DAY  ·  " + _pun(BAD_TAGS, today))
        d.text((tx, y + 18), tag, font=FONT(BOLD, 30), fill=RED if good_kind else GREY)
        d.text((tx, y + 56), _clip(d, g["title"], FONT(BOLD, 46), R - tx - 20), font=_fit(d, g["title"], BOLD, 46, R - tx - 20), fill=INK)
        line = when(g) + (f"  ·  {g['tv']}" if g.get("tv") else "") + f"  ·  {bars[0]}" + (f" + {len(bars) - 1} more" if len(bars) > 1 else "")
        d.text((tx, y + 114), _clip(d, line, FONT(REG, 28), R - tx - 20), font=FONT(REG, 28), fill=GREY)
        blurb = why or (_pun(GOOD_PUNS, today) if good_kind else _pun(BAD_PUNS, today, 3))
        d.text((tx, y + 150), _clip(d, blurb, FONT(BOLD, 27), R - tx - 20), font=_fit(d, blurb, BOLD, 27, R - tx - 20), fill=INK if good_kind else GREY)
        y += h + 16

    if good:
        hero(good, "good")
    if bad:
        hero(bad, "bad")
    if good or bad:
        y += 8
    featured = {_matchup(i[0]["title"]) for i in (good, bad) if i}
    games = [gb for gb in games if _matchup(gb[0]["title"]) not in featured]

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

    DRINK_H = 124
    budget = H - 150 - (DRINK_H + 14 if drink else 0)  # keep room for drink strip + footer

    if games:
        section("MORE GAMES" if featured else "GAME DAY", f"{len(games)} GAMES")
        for x, bars in games:
            if y > budget - (150 if (nights or happy) else 110):
                break
            more = f" + {len(bars) - 2} more" if len(bars) > 2 else ""
            row(when(x), x["title"] + (f"  ·  {x['tv']}" if x.get("tv") else ""), "Home bars: " + ", ".join(bars[:2]) + more)
        y += 6

    if nights and y < budget - 200:
        section("TRIVIA TONIGHT", f"{len(nights)}")
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

    # drink of the day strip
    if drink:
        top = H - 110 - 14 - DRINK_H
        d.rounded_rectangle([L, top, R, top + DRINK_H], radius=14, fill=NAVY, outline=GOLD, width=4)
        _glass(d, L + 70, top + 52, 36)
        tx = L + 140
        tag = "DRINK OF THE DAY  ·  " + _pun(DRINK_TAGS, today, 1)
        d.text((tx, top + 12), tag, font=_fit(d, tag, BOLD, 27, R - tx - 20), fill=GOLD)
        head = f"{drink['name']} at {bar_label(drink['barId'])}"
        d.text((tx, top + 44), _clip(d, head, FONT(BOLD, 36), R - tx - 20), font=_fit(d, head, BOLD, 36, R - tx - 20), fill=WHITE)
        d.text((tx, top + 86), _clip(d, drink.get("desc") or "", FONT(REG, 26), R - tx - 20), font=FONT(REG, 26), fill="#C9D6F2")

    # footer
    d.rectangle([0, H - 110, W, H], fill=NAVY)
    ft = "Full list + every happy hour: " + base_url.replace("https://", "")
    d.text((48, H - 82), ft, font=_fit(d, ft, BOLD, 38, W - 96), fill=WHITE)

    os.makedirs(out_dir, exist_ok=True)
    name = today.isoformat()
    img.save(os.path.join(out_dir, f"{name}.png"), optimize=True)

    # caption
    dayname = DOW[pydow(today)].title()
    lines = [f"🍺 Tonight's Pourcast for Nashville: {dayname}, {MON[today.month - 1].title()} {today.day}", "📍 Nashville, TN", ""]
    for item, icon, label in ((good, "☀️", "GAME OF THE DAY"), (bad, "⛈️", "BAD GAME OF THE DAY")):
        if item:
            g, bars, why = item
            why = why or (_pun(GOOD_PUNS, today) if icon == "☀️" else _pun(BAD_PUNS, today, 3))
            lines.append(f"{icon} {label}: {g['title']}, {when(g)}" + (f" on {g['tv']}" if g.get("tv") else "") + f", at {bars[0]}" + (f" + {len(bars) - 1} more" if len(bars) > 1 else ""))
            if why:
                lines.append(f"   {why}")
    if good or bad:
        lines.append("")
    if drink:
        lines.append(f"🍸 DRINK OF THE DAY: {drink['name']} at {bar_label(drink['barId'])}")
        if drink.get("desc"):
            lines.append(f"   {drink['desc']}. Menus rotate, so ask your bartender.")
        lines.append("")
    if games:
        lines.append("🏈 MORE GAMES" if featured else "🏈 GAME DAY")
        for x, bars in games[:8]:
            lines.append(f"• {when(x)}: {x['title']}" + (f" ({x['tv']})" if x.get("tv") else "") + f", at {bars[0]}" + (f" + {len(bars) - 1} more" if len(bars) > 1 else ""))
        lines.append("")
    if nights:
        lines.append("🧠 TRIVIA TONIGHT")
        for x in nights[:8]:
            lines.append(f"• {when(x)}: {x['title']} at {bar_label(x['barId'])}")
        lines.append("")
    if happy:
        lines.append(f"🍻 Happy hour radar: {len(happy)} deals across town, including:")
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
