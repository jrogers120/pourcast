#!/usr/bin/env python3
"""Build the Pourcast static site from data/*.json into public/.

Usage: python3 build.py [--today YYYY-MM-DD]
No third-party packages needed.
"""
import json, os, re, shutil, sys, html
from urllib.parse import quote_plus
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "public")
CFG = json.load(open(os.path.join(ROOT, "config.json")))
TZ = ZoneInfo(CFG["timezone"])
BARS = {b["id"]: b for b in json.load(open(os.path.join(ROOT, "data", "bars.json")))}
EVENTS = json.load(open(os.path.join(ROOT, "data", "events.json")))
BASE = CFG["base_url"].rstrip("/")
CITY = CFG["city"]
DOW = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
TYPES = {
    "college": ("College football", "college-football", "College football watch parties"),
    "game": ("NFL & other games", "nfl", "NFL watch parties"),
    "trivia": ("Trivia", "trivia", "Trivia nights"),
    "karaoke": ("Karaoke", "karaoke", "Karaoke nights"),
    "music": ("Live music", "live-music", "Live music"),
    "happy": ("Happy hour", "happy-hour", "Happy hours"),
    "special": ("Special event", "special-events", "Drag shows, bingo and special events"),
}
NFL = {"Arizona Cardinals","Atlanta Falcons","Baltimore Ravens","Buffalo Bills","Carolina Panthers","Chicago Bears","Cincinnati Bengals","Cleveland Browns","Dallas Cowboys","Denver Broncos","Detroit Lions","Green Bay Packers","Houston Texans","Indianapolis Colts","Jacksonville Jaguars","Kansas City Chiefs","Las Vegas Raiders","Los Angeles Chargers","Los Angeles Rams","Miami Dolphins","Minnesota Vikings","New England Patriots","New Orleans Saints","New York Giants","New York Jets","Philadelphia Eagles","Pittsburgh Steelers","San Francisco 49ers","Seattle Seahawks","Tampa Bay Buccaneers","Tennessee Titans","Washington Commanders"}

e = lambda s: html.escape(str(s or ""), quote=True)
slug = lambda s: re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def today_central():
    for i, a in enumerate(sys.argv):
        if a == "--today":
            return date.fromisoformat(sys.argv[i + 1])
    return datetime.now(TZ).date()


TODAY = today_central()
WEEK = [TODAY + timedelta(days=i) for i in range(7)]
pydow = lambda d: (d.weekday() + 1) % 7  # Sunday = 0, matching the app


def time12(hm):
    if not hm:
        return ""
    h, m = map(int, hm.split(":"))
    return f"{h % 12 or 12}:{m:02d} {'PM' if h >= 12 else 'AM'}"


def when(ev):
    return ev.get("timeLabel") or (time12(ev["time"]) if ev.get("time") else "At game time")


def occurs(ev, d):
    return pydow(d) in ev.get("days", []) if ev.get("weekly") else ev.get("date") == d.isoformat()


def bar_label(bid):
    b = BARS.get(bid)
    if not b:
        return "A Nashville bar"
    return b["name"] + (f" ({b['area']})" if b.get("area") else "")


def bar_url(bid):
    return f"/bars/{bid}/"


def team_url(t):
    return f"/watch/{slug(t)}/"


def day_name(d):
    if d == TODAY:
        return "Today"
    if d == TODAY + timedelta(days=1):
        return "Tomorrow"
    return DOW[pydow(d)]


def fmt_date(d):
    return d.strftime("%b ") + str(d.day)


def sort_key(ev):
    return (ev.get("time") or "99")


# ---------- page shell ----------
NAV = [("/", "Forecast"), ("/tonight/college-football/", "College football"), ("/tonight/nfl/", "NFL"),
       ("/tonight/trivia/", "Trivia"), ("/tonight/happy-hour/", "Happy hour"), ("/bars/", "Bars"), ("/submit/", "Post an event")]
LOGO_SVG = ('<svg width="48" height="48" viewBox="0 0 200 200" aria-hidden="true"><circle cx="100" cy="100" r="96" fill="#fff"/><circle cx="100" cy="100" r="86" fill="#0B3D91"/>'
            '<circle cx="132" cy="70" r="30" fill="#FFC53D"/><path d="M132 26 L132 14 M166 36 L175 27 M176 70 L188 70" stroke="#FFC53D" stroke-width="7" stroke-linecap="round"/>'
            '<rect x="56" y="82" width="70" height="82" rx="8" fill="#F5B12E"/><path d="M126 98 h14 a16 16 0 0 1 16 16 v14 a16 16 0 0 1 -16 16 h-14" fill="none" stroke="#fff" stroke-width="10"/>'
            '<path d="M50 88 q0 -22 22 -20 q6 -16 24 -12 q14 -12 28 4 q20 0 18 22 z" fill="#fff"/></svg>')


def ad_slot():
    if not CFG.get("adsense_client"):
        return ""
    return (f'<div class="ad"><div><div class="ad-label">Advertisement</div><ins class="adsbygoogle" style="display:block" '
            f'data-ad-client="{e(CFG["adsense_client"])}" data-ad-slot="{e(CFG.get("adsense_slot",""))}" data-ad-format="auto" data-full-width-responsive="true"></ins>'
            '<script>(adsbygoogle=window.adsbygoogle||[]).push({});</script></div></div>')


def ticker_text():
    evs = sorted([x for x in EVENTS if occurs(x, TODAY)], key=sort_key)
    if not evs:
        return "Clear skies tonight. Check the 7-day forecast below."
    return "   •   ".join(f"{when(x)}  {x['title']} at {bar_label(x['barId'])}" for x in evs)


REGIONS = [
    ("Downtown & Broadway", ["Broadway", "Downtown", "Printers Alley", "Rutledge Hill", "The Gulch"]),
    ("Midtown & Music Row", ["Midtown", "Demonbreun", "Music Row", "West End", "Hillsboro Village", "Edgehill"]),
    ("East Nashville", ["East Nashville"]),
    ("Germantown & West", ["Germantown", "North Nashville", "Capitol View", "The Nations", "Sylvan Park", "Bellevue"]),
    ("South Nashville", ["12 South", "8th Ave", "Melrose", "Wedgewood-Houston", "Berry Hill", "Green Hills", "South Nashville"]),
    ("Donelson, Hermitage & north", ["Donelson", "Music Valley", "Hermitage", "Old Hickory", "Goodlettsville", "Hendersonville"]),
    ("Franklin", ["Franklin"]),
    ("Spring Hill", ["Spring Hill"]),
]


def area_filter():
    used = {b.get("area") for b in BARS.values() if b.get("area")}
    known = {a for _, al in REGIONS for a in al}
    regions = REGIONS + ([("Other areas", sorted(used - known))] if used - known else [])
    opts = ['<option value="">All areas</option>']
    for r, al in regions:
        al = [a for a in al if a in used]
        if not al:
            continue
        opts.append(f'<option value="r:{e(r)}">{e(r)}{" (all)" if len(al) > 1 else ""}</option>')
        if len(al) > 1:
            opts.append(f'<optgroup label="{e(r)}">' + "".join(f'<option value="a:{e(a)}">{e(a)}</option>' for a in al) + "</optgroup>")
    rmap = {a: r for r, al in regions for a in al}
    return ('<div class="areafilter"><label for="areaSel">Area</label><select id="areaSel">' + "".join(opts) + "</select>"
            '<span class="areacount" id="areaCount"></span></div>'
            "<script>(function(){var R=" + json.dumps(rmap) + r""";
var sel=document.getElementById('areaSel'),cnt=document.getElementById('areaCount');
function apply(v){var cards=document.querySelectorAll('article.card.ev'),shown=0;
 cards.forEach(function(c){var a=c.getAttribute('data-area')||'',ok=!v||(v.slice(0,2)=='a:'?a==v.slice(2):R[a]==v.slice(2));c.hidden=!ok;if(ok)shown++;});
 document.querySelectorAll('.grid').forEach(function(g){if(!g.querySelector('article.card.ev'))return;var any=g.querySelector('article.card.ev:not([hidden])'),n=g.nextElementSibling;
  if(!n||!n.classList.contains('areaempty')){n=document.createElement('div');n.className='empty areaempty';n.textContent='Nothing posted in this area. Try another area or All areas.';g.after(n);}
  n.hidden=!!any;});
 cnt.textContent=v?shown+' events':'';}
var v=new URLSearchParams(location.search).get('area');if(v===null){try{v=localStorage.getItem('pourcastArea')||'';}catch(e){v='';}}
if(v&&![].some.call(sel.options,function(o){return o.value==v}))v='';sel.value=v;apply(v);
sel.addEventListener('change',function(){apply(sel.value);try{localStorage.setItem('pourcastArea',sel.value);}catch(e){}});
})();</script>""")


TICKER = ticker_text()
# constant, slow reading speed (~40 px/sec) no matter how long the ticker is
TICKER_SECS = max(45, round((len(TICKER) * 8.5 + 1200) / 55))


def page(path, title, desc, body, current="", jsonld=None):
    canon = BASE + path
    ads_head = (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={e(CFG["adsense_client"])}" crossorigin="anonymous"></script>'
                if CFG.get("adsense_client") else "")
    nav = "".join(f'<a href="{h}"{" aria-current=\"page\"" if h == current else ""}>{e(t)}</a>' for h, t in NAV)
    ld = f'<script type="application/ld+json">{json.dumps(jsonld)}</script>' if jsonld else ""
    filt = area_filter() if ('class="card ev' in body and not path.startswith(("/bars/", "/areas/"))) else ""
    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(canon)}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(canon)}">
<meta property="og:type" content="website">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow:ital,wght@0,500;0,600;0,700;0,800;1,800;1,900&family=Barlow+Condensed:wght@700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/site.css">
{ads_head}{ld}
</head>
<body>
<header class="masthead"><div class="wrap"><a class="logo" href="/">{LOGO_SVG}<b>Pour<span>cast</span></b></a><div class="strap"><b>{e(CITY)}</b><i>7-Day Bar Forecast</i></div></div></header>
<div class="ticker" aria-label="Today's highlights"><span class="lbl">Today</span><span class="track"><span class="run" style="animation-duration:{TICKER_SECS}s">{e(TICKER)}</span></span></div>
<nav class="secnav" aria-label="Sections"><div class="wrap">{nav}</div></nav>
<main><div class="wrap">
{filt}{body}
</div></main>
<footer><div class="wrap">
<div><b>{e(CFG["site_name"])}</b>: game watches, trivia, karaoke and happy hours at {e(CITY)}-area bars. Updated {fmt_date(TODAY)}, {TODAY.year}.</div>
<div>Instagram: <a href="https://www.instagram.com/{e(CFG["instagram"])}/">@{e(CFG["instagram"])}</a> · Email: {e(CFG["contact_email"])}</div>
<div><a href="/about/">About</a> · <a href="/submit/">Post an event</a> · <a href="/privacy/">Privacy policy</a> · Deals and times change, so check with the bar before you go. Please drink responsibly; 21+.</div>
</div></footer>
</body>
</html>
"""
    bp = CFG.get("base_path", "").rstrip("/")
    if bp:  # site served from a subfolder (e.g. username.github.io/pourcast)
        doc = doc.replace('href="/', f'href="{bp}/').replace('src="/', f'src="{bp}/')
    dest = os.path.join(OUT, path.strip("/"), "index.html") if path.endswith("/") else os.path.join(OUT, path.strip("/"))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    open(dest, "w").write(doc)
    PAGES.append(path)


PAGES = []


def card(ev, d=None, show_day=False):
    t = ev.get("type", "special")
    label = TYPES.get(t, ("Event",))[0]
    chips = []
    if ev.get("team"):
        chips.append(f'<a class="chip" href="{team_url(ev["team"])}">{e(ev["team"])}</a>')
    if ev.get("tv"):
        chips.append(f'<span class="chip">TV: {e(ev["tv"])}</span>')
    if ev.get("deals"):
        chips.append(f'<span class="chip">{e(ev["deals"])}</span>')
    if ev.get("cover"):
        chips.append(f'<span class="chip">{e(ev["cover"])}</span>')
    sched = ""
    if show_day:
        sched = ("Every " + ", ".join(DOW[x] for x in sorted(ev["days"])) if ev.get("weekly")
                 else f"{DOW[pydow(date.fromisoformat(ev['date']))]}, {fmt_date(date.fromisoformat(ev['date']))}") + " · "
    host = f' · Hosted by {e(ev["host"])}' if ev.get("host") else ""
    area = (BARS.get(ev["barId"]) or {}).get("area") or ""
    return (f'<article class="card ev {e(t)}" data-area="{e(area)}"><div class="meta"><span class="badge">{e(label)}</span><span class="when">{e(sched)}{e(when(ev))}</span></div>'
            f'<div class="title">{e(ev["title"])}</div><div class="where"><a href="{bar_url(ev["barId"])}">{e(bar_label(ev["barId"]))}</a>{host}</div>'
            f'{"<div class=chips>" + "".join(chips) + "</div>" if chips else ""}</article>')


def upcoming(evs):
    """Events in the next 7 days, one-time ones first by date, weekly ones by day."""
    out = []
    for d in WEEK:
        for x in sorted([x for x in evs if occurs(x, d)], key=sort_key):
            out.append((d, x))
    return out


# ---------- pages ----------
def build_home():
    parts = [f'<h1>{e(CITY)} 7-day bar forecast</h1><p class="dek">Where to watch the game, find trivia and karaoke, and catch happy hour across {e(CITY)}, Franklin and Spring Hill, {fmt_date(WEEK[0])}–{fmt_date(WEEK[-1])}.</p>']
    cfb_sat = [x for x in EVENTS if x.get("type") == "college" and not x.get("weekly") and x.get("date") in {d.isoformat() for d in WEEK}]
    if cfb_sat:
        parts.append(f'<div class="alert"><b>Weather alert</b><span>100% chance of college football: {len(cfb_sat)} watch parties at {e(CITY)} home bars this week. <a href="/tonight/college-football/">See where every fan base watches</a>.</span></div>')
    for i, d in enumerate(WEEK):
        evs = sorted([x for x in EVENTS if occurs(x, d)], key=lambda x: (0 if x.get("type") == "college" else 1, sort_key(x)))
        parts.append(f'<h2>{e(day_name(d))} · {e(DOW[pydow(d)][:3])} {fmt_date(d)}</h2>')
        parts.append('<div class="grid">' + "".join(card(x, d) for x in evs) + '</div>' if evs else '<div class="empty">Nothing posted yet. <a href="/submit/">Add an event</a>.</div>')
        if i in (0, 2, 4):
            parts.append(ad_slot())
    ld = {"@context": "https://schema.org", "@type": "WebSite", "name": CFG["site_name"], "url": BASE + "/"}
    page("/", f"{CITY} Bar Forecast: Game Watches, Trivia & Happy Hours | Pourcast",
         f"This week's {CITY} bar forecast: where to watch college football and NFL games, trivia and karaoke nights, and the best happy hours.", "".join(parts), "/", ld)


def build_types():
    for t, (label, s, heading) in TYPES.items():
        evs = [x for x in EVENTS if x.get("type") == t]
        parts = [f'<h1>{e(heading)} in {e(CITY)}</h1><p class="dek">Every {e(label.lower())} listing on Pourcast for the next 7 days, plus the weekly regulars.</p>']
        up = upcoming(evs)
        cur = None
        if up:
            for d, x in up:
                if d != cur:
                    parts.append(f'<div class="day">{e(day_name(d))} · {fmt_date(d)}</div><div class="grid">' if cur is None else f'</div><div class="day">{e(day_name(d))} · {fmt_date(d)}</div><div class="grid">')
                    cur = d
                parts.append(card(x, d))
            parts.append("</div>")
        else:
            parts.append('<div class="empty">Nothing posted for the next 7 days. <a href="/submit/">Add one</a>.</div>')
        parts.append(ad_slot())
        if t in ("college", "game"):
            teams = sorted({tm for b in BARS.values() for tm in b["teams"] if (tm in NFL) == (t == "game")})
            if teams:
                parts.append(f'<h2>Find your team\'s home bar</h2><ul class="list">' + "".join(f'<li><a href="{team_url(tm)}">{e(tm)}</a></li>' for tm in teams) + "</ul>")
        page(f"/tonight/{s}/", f"{heading} in {CITY} This Week | Pourcast",
             f"{heading} at {CITY}-area bars this week, with times, deals and where to go.", "".join(parts), f"/tonight/{s}/")


def build_bars():
    by_area = {}
    for b in BARS.values():
        by_area.setdefault(b.get("area") or "Other Nashville bars", []).append(b)
    parts = [f'<h1>{e(CITY)} bars on Pourcast</h1><p class="dek">{len(BARS)} bars across {e(CITY)}, Franklin and Spring Hill, by neighborhood.</p>']
    for a in sorted(by_area, key=lambda a: (a == "Other Nashville bars", a)):
        aslug = slug(a)
        parts.append(f'<h2><a href="/areas/{aslug}/" style="color:inherit;text-decoration:none">{e(a)}</a></h2><ul class="list">' +
                     "".join(f'<li><a href="{bar_url(b["id"])}">{e(b["name"])}</a></li>' for b in sorted(by_area[a], key=lambda b: b["name"])) + "</ul>")
        # area page
        aevs = [x for x in EVENTS if x["barId"] in {b["id"] for b in by_area[a]}]
        ap = [f'<h1>Bars in {e(a)}</h1><p class="dek">What\'s on this week at {e(a)} bars, and every bar we list there.</p>']
        up = upcoming(aevs)
        ap.append('<h2>This week</h2>' + ('<div class="grid">' + "".join(card(x, d, show_day=False) .replace('<span class="when">', f'<span class="when">{e(day_name(d))} · ', 1) for d, x in up) + '</div>' if up else '<div class="empty">Nothing posted this week.</div>'))
        ap.append(ad_slot())
        ap.append('<h2>Bars</h2><ul class="list">' + "".join(f'<li><a href="{bar_url(b["id"])}">{e(b["name"])}</a></li>' for b in sorted(by_area[a], key=lambda b: b["name"])) + "</ul>")
        page(f"/areas/{aslug}/", f"Bars in {a}: This Week's Events & Happy Hours | Pourcast",
             f"Game watches, trivia, karaoke and happy hours at bars in {a} this week.", "".join(ap))
    page("/bars/", f"{CITY} Bars by Neighborhood | Pourcast", f"Browse {len(BARS)} {CITY}-area bars by neighborhood, with weekly events and happy hours.", "".join(parts), "/bars/")

    for b in BARS.values():
        evs = [x for x in EVENTS if x["barId"] == b["id"]]
        weekly = sorted([x for x in evs if x.get("weekly")], key=lambda x: (min(x["days"]), sort_key(x)))
        once = sorted([x for x in evs if not x.get("weekly") and x.get("date", "") >= TODAY.isoformat()], key=lambda x: (x["date"], sort_key(x)))
        loc = b.get("area") or CITY
        p = [f'<h1>{e(b["name"])}</h1><p class="dek">{e(loc)} · Events, game watches and happy hours this week.</p>']
        if b.get("address"):
            maps = "https://www.google.com/maps/search/?api=1&query=" + quote_plus(b["name"] + ", " + b["address"])
            p.append(f'<p class="addr"><span>📍 {e(b["address"])}</span> <a class="dir" href="{maps}" target="_blank" rel="noopener">Directions</a></p>')
        if b["teams"]:
            p.append('<div class="alert"><b>Home bar for</b><span>' + ", ".join(f'<a href="{team_url(t)}">{e(t)}</a>' for t in b["teams"]) + " fans</span></div>")
        p.append('<h2>Coming up</h2>' + ('<div class="grid">' + "".join(card(x, show_day=True) for x in once) + '</div>' if once else '<div class="empty">No one-time events posted yet.</div>'))
        p.append('<h2>Every week</h2>' + ('<div class="grid">' + "".join(card(x, show_day=True) for x in weekly) + '</div>' if weekly else '<div class="empty">No weekly specials posted yet. Work here? <a href="/submit/">Add yours free</a>.</div>'))
        p.append(ad_slot())
        srcs = sorted({x["source"] for x in evs if x.get("source")})
        if srcs:
            p.append('<p class="src">Listing sources: ' + " · ".join(f'<a href="{e(s)}" rel="nofollow">{e(re.sub(r"^https?://(www\\.)?", "", s).split("/")[0])}</a>' for s in srcs) + '</p>')
        ld = {"@context": "https://schema.org", "@type": "BarOrPub", "name": b["name"], "url": BASE + bar_url(b["id"]),
              "address": {"@type": "PostalAddress", "addressLocality": "Franklin" if loc == "Franklin" else "Spring Hill" if loc == "Spring Hill" else CITY, "addressRegion": "TN"}}
        page(bar_url(b["id"]), f"{b['name']} {CITY}: Events, Game Watches & Happy Hour | Pourcast",
             f"What's on at {b['name']} in {loc} this week: " + (f"home bar for {', '.join(b['teams'])} fans, " if b["teams"] else "") + "events and specials.",
             "".join(p), jsonld=ld)


def build_teams():
    teams = sorted({t for b in BARS.values() for t in b["teams"]})
    for t in teams:
        hb = [b for b in BARS.values() if t in b["teams"]]
        games = sorted([x for x in EVENTS if x.get("team") == t and not x.get("weekly") and x.get("date", "") >= TODAY.isoformat()], key=lambda x: (x["date"], sort_key(x)))
        p = [f'<h1>Where to watch {e(t)} in {e(CITY)}</h1><p class="dek">The {e(CITY)} bar' + ("s" if len(hb) > 1 else "") + f' where {e(t)} fans watch every game, and this week\'s kickoff.</p>']
        p.append('<h2>Home bar' + ("s" if len(hb) > 1 else "") + '</h2><div class="cols">' +
                 "".join(f'<div class="card"><div class="title"><a href="{bar_url(b["id"])}">{e(b["name"])}</a></div><div class="src">{e(b.get("area") or CITY)}</div></div>' for b in hb) + '</div>')
        p.append('<h2>Next game</h2>' + ('<div class="grid">' + "".join(card(x, show_day=True) for x in games) + '</div>' if games else '<div class="empty">No game this week (bye week or not posted yet). Check back after Monday.</div>'))
        p.append(ad_slot())
        page(team_url(t), f"Where to Watch {t} in {CITY}: Fan Bar & Game Times | Pourcast",
             f"Find the {CITY} bar where {t} fans watch every game, plus this week's kickoff time and TV channel.", "".join(p))
    p = [f'<h1>Where to watch your team in {e(CITY)}</h1><p class="dek">Every college and NFL team with a {e(CITY)} home bar.</p><h2>College</h2><ul class="list">' +
         "".join(f'<li><a href="{team_url(t)}">{e(t)}</a></li>' for t in teams if t not in NFL) + '</ul><h2>NFL</h2><ul class="list">' +
         "".join(f'<li><a href="{team_url(t)}">{e(t)}</a></li>' for t in teams if t in NFL) + "</ul>"]
    page("/watch/", f"Where to Watch Your Team in {CITY} | Pourcast", f"College and NFL fan bars in {CITY}: find your team's home bar.", "".join(p))


def build_static():
    mail = e(CFG["contact_email"])
    page("/about/", "About Pourcast", f"Pourcast is {CITY}'s 7-day bar forecast.",
         f'<h1>About Pourcast</h1><p class="dek">Pourcast is {e(CITY)}\'s 7-day bar forecast: where to watch the game, find trivia and karaoke, and catch happy hour.</p>'
         f'<p>We track team home bars, weekly events and happy hour deals across {e(CITY)}, Franklin and Spring Hill, and update game listings every week of the season. Listings come from bars, organizers and public sources; deals and times change, so check with the bar before you go.</p>'
         f'<p>Contact: {mail} · Instagram <a href="https://www.instagram.com/{e(CFG["instagram"])}/">@{e(CFG["instagram"])}</a></p>')
    page("/submit/", "Post an Event on Pourcast", "Bars, social clubs and organizers can post events on Pourcast for free.",
         f'<h1>Post your event, free</h1><p class="dek">Run a trivia night, karaoke, watch party, happy hour or social club meetup at a {e(CITY)}-area bar? Send it to us.</p>'
         f'<div class="card"><p style="margin:0">Email <b>{mail}</b> with:</p><ul><li>Bar name and neighborhood</li><li>Event name and type</li><li>Day and start time (one time, or every week)</li><li>Specials or cover, and who\'s hosting</li></ul><p style="margin:0">We\'ll add it to the forecast, and the best ones go in our weekly email and on Instagram.</p></div>', "/submit/")
    page("/privacy/", "Privacy Policy | Pourcast", "How Pourcast handles data, cookies and advertising.",
         f'<h1>Privacy policy</h1><p class="dek">Last updated {fmt_date(TODAY)}, {TODAY.year}.</p>'
         '<h2>What we collect</h2><p>This site does not require an account. If you email us, we keep your message to reply and to list your event.</p>'
         '<h2>Cookies and advertising</h2><p>We use third-party advertising, including Google AdSense. Google and its partners use cookies to serve ads based on your prior visits to this and other websites. '
         'Google\'s use of advertising cookies lets it and its partners serve ads based on your visits to this site and/or other sites on the internet. You can opt out of personalized advertising at '
         '<a href="https://www.google.com/settings/ads">Google Ads Settings</a> or <a href="https://www.aboutads.info/choices/">www.aboutads.info</a>.</p>'
         '<h2>Analytics</h2><p>We may use privacy-friendly analytics to count page views. We do not sell personal information.</p>'
         f'<h2>Alcohol</h2><p>Pourcast is intended for adults 21 and older. Please drink responsibly.</p><h2>Contact</h2><p>{mail}</p>')
    # 404
    page("/404.html", "Page not found | Pourcast", "Page not found.", '<h1>Off the radar</h1><p class="dek">That page doesn\'t exist. <a href="/">Back to the forecast</a>.</p>')


def build_meta():
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p in PAGES:
        if p.endswith("404.html"):
            continue
        sm.append(f"<url><loc>{e(BASE + p)}</loc><lastmod>{TODAY.isoformat()}</lastmod></url>")
    sm.append("</urlset>")
    open(os.path.join(OUT, "sitemap.xml"), "w").write("\n".join(sm))
    open(os.path.join(OUT, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")
    if CFG.get("adsense_client"):
        pub = CFG["adsense_client"].replace("ca-", "")
        open(os.path.join(OUT, "ads.txt"), "w").write(f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n")
    open(os.path.join(OUT, ".nojekyll"), "w").write("")
    if CFG.get("custom_domain"):
        open(os.path.join(OUT, "CNAME"), "w").write(CFG["custom_domain"] + "\n")


if __name__ == "__main__":
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    shutil.copytree(os.path.join(ROOT, "assets"), os.path.join(OUT, "assets"))
    build_home(); build_types(); build_bars(); build_teams(); build_static(); build_meta()
    try:
        sys.path.insert(0, os.path.join(ROOT, "social"))
        import graphic
        pf = os.path.join(ROOT, "data", "picks.json")
        picks = json.load(open(pf)) if os.path.exists(pf) else {}
        df = os.path.join(ROOT, "data", "drinks.json")
        drinks = json.load(open(df)) if os.path.exists(df) else []
        graphic.make(os.path.join(OUT, "social"), TODAY, [x for x in EVENTS if occurs(x, TODAY)],
                     bar_label, when, BASE, pydow, picks, drinks, lambda b: b in BARS)
        print("Made Instagram graphic for", TODAY)
    except ImportError as err:
        print("Skipped Instagram graphic (Pillow not installed):", err)
    print(f"Built {len(PAGES)} pages for {TODAY} into {OUT}")
