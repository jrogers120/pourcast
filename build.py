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
_af = os.path.join(ROOT, "data", "awards.json")
AWARDS = json.load(open(_af)) if os.path.exists(_af) else {}
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
NAV = [("/", "Forecast"), ("/map/", "Map"), ("/tonight/college-football/", "College football"), ("/tonight/nfl/", "NFL"),
       ("/tonight/trivia/", "Trivia"), ("/tonight/happy-hour/", "Happy hour"), ("/christmas/", "Christmas pop-ups"), ("/bars/", "Bars"), ("/vote/", "Vote"), ("/shop/", "Merch"), ("/submit/", "Post an event")]
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
]


TYPE_CHIPS = [("", "All"), ("game", "Games"), ("happy", "Happy hour"), ("trivia", "Trivia"), ("karaoke", "Karaoke"), ("music", "Live music"), ("special", "Specials")]

FILTER_JS = r"""
var NAMES=['sun','mon','tue','wed','thu','fri','sat'];
var sel=document.getElementById('areaSel'),cnt=document.getElementById('areaCount');
var cards=[].slice.call(document.querySelectorAll('article.card.ev')),secs=[].slice.call(document.querySelectorAll('section.dayblock'));
var st={area:'',type:'',day:''},showEarlier=false;
function chi(){var p=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Chicago',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date()),o={};p.forEach(function(x){o[x.type]=x.value;});
 return {date:o.year+'-'+o.month+'-'+o.day,min:(+o.hour)*60+(+o.minute),hour:+o.hour};}
function fmt(m){m=Math.max(1,Math.round(m));return m<60?m+' min':(Math.floor(m/60)+' hr'+(m%60?' '+m%60+' min':''));}
function timing(){var n=chi();cards.forEach(function(c){var l=c.querySelector('.live');c.classList.remove('is-live','is-ended','is-soon');if(l)l.textContent='';
  if(c.getAttribute('data-date')!==n.date||n.hour<4)return;var s=+c.getAttribute('data-s'),e=+c.getAttribute('data-e');
  if(n.min>=e)c.classList.add('is-ended');
  else if(n.min>=s){c.classList.add('is-live');if(l)l.textContent=e>=1560?'On now':'On now · ends in '+fmt(e-n.min);}
  else if(s-n.min<=90){c.classList.add('is-soon');if(l)l.textContent='Starts in '+fmt(s-n.min);}});}
function areaOk(c){var v=st.area;if(!v)return true;var as=(c.getAttribute('data-area')||'').split('|');
 return as.some(function(a){return v.slice(0,2)=='a:'?a==v.slice(2):R[a]==v.slice(2);});}
function typeOk(c){var t=c.getAttribute('data-type'),v=st.type;return !v||t==v||(v=='game'&&t=='college');}
function apply(){timing();var shown=0;
 secs.forEach(function(s){var ok=st.day===''||(st.day==='now'?s.getAttribute('data-day')==='0':s.getAttribute('data-day')===st.day);s.hidden=!ok;});
 cards.forEach(function(c){var ok=areaOk(c)&&typeOk(c);
  if(ok&&st.day==='now'&&!c.classList.contains('is-live'))ok=false;
  if(ok&&c.classList.contains('is-ended')&&!showEarlier)ok=false;
  c.hidden=!ok;var sec=c.closest('section.dayblock');if(ok&&!(sec&&sec.hidden))shown++;});
 document.querySelectorAll('.grid').forEach(function(g){if(!g.querySelector('article.card.ev'))return;var any=g.querySelector('article.card.ev:not([hidden])'),n=g.nextElementSibling;
  if(!n||!n.classList.contains('areaempty')){n=document.createElement('div');n.className='empty areaempty';g.after(n);}
  n.textContent=st.day==='now'?'Nothing on right now with these filters. Try All week.':'Nothing posted that matches. Try another area or type.';n.hidden=!!any;});
 var eb=document.getElementById('earlier');if(!eb&&secs.length){var h=secs[0].querySelector('h2,.day');if(h){eb=document.createElement('button');eb.id='earlier';eb.type='button';eb.className='earlier';h.after(eb);
  eb.addEventListener('click',function(){showEarlier=!showEarlier;apply();});}}
 if(eb){var n2=cards.filter(function(c){return c.classList.contains('is-ended')&&areaOk(c)&&typeOk(c);}).length;
  eb.hidden=!n2||st.day==='now';eb.textContent=showEarlier?'Hide earlier events':'Show '+n2+' earlier event'+(n2>1?'s':'')+' from today';}
 cnt.textContent=(st.area||st.type||st.day)?shown+' events':'';}
function press(rowId,attr,v){var row=document.getElementById(rowId);if(!row)return;row.querySelectorAll('button').forEach(function(b){var on=b.getAttribute(attr)===v;b.setAttribute('aria-pressed',on?'true':'false');
 if(on&&v!=='')row.scrollLeft=b.offsetLeft-row.offsetLeft-12;});}
function url(){var u=new URL(location.href);['area','type','day'].forEach(function(k){var v=st[k];if(k==='day'&&v!==''&&v!=='now'){var b=document.querySelector('#dayPick button[data-d="'+v+'"]');v=b?NAMES[b.getAttribute('data-dow')]:'';}
 if(v)u.searchParams.set(k,v);else u.searchParams.delete(k);});history.replaceState(null,'',u);}
var q=new URLSearchParams(location.search);
var a=q.get('area');if(a===null){try{a=localStorage.getItem('pourcastArea')||'';}catch(e){a='';}}
if(a&&![].some.call(sel.options,function(o){return o.value==a}))a='';sel.value=a;st.area=a;
var t=q.get('type')||'';if(!document.querySelector('#typePick button[data-t="'+t+'"]'))t='';st.type=t;
var d=q.get('day');if(d==='now'&&document.getElementById('dayPick'))st.day='now';else if(d){var k=NAMES.indexOf(d.slice(0,3).toLowerCase());document.querySelectorAll('#dayPick button').forEach(function(b){if(b.getAttribute('data-d')===d||(k>=0&&b.getAttribute('data-dow')==k))st.day=b.getAttribute('data-d');});}
press('dayPick','data-d',st.day);press('typePick','data-t',st.type);apply();
sel.addEventListener('change',function(){st.area=sel.value;try{localStorage.setItem('pourcastArea',sel.value);}catch(e){}apply();url();});
document.querySelectorAll('#dayPick button').forEach(function(b){b.addEventListener('click',function(){st.day=b.getAttribute('data-d');press('dayPick','data-d',st.day);apply();url();});});
document.querySelectorAll('#typePick button').forEach(function(b){b.addEventListener('click',function(){st.type=b.getAttribute('data-t');press('typePick','data-t',st.type);apply();url();});});
setInterval(apply,60000);
"""


def filters(body):
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
    types_here = set(re.findall(r'data-type="([a-z]+)"', body))
    tchips = ""
    if len(types_here) > 1:
        tchips = '<div class="chiprow types" id="typePick" role="group" aria-label="Pick a type">' + "".join(
            f'<button type="button" data-t="{v}" aria-pressed="{"true" if not v else "false"}">{e(l)}</button>'
            for v, l in TYPE_CHIPS if not v or v in types_here or (v == "game" and "college" in types_here)) + "</div>"
    days = ""
    if 'class="dayblock"' in body:
        chips = ['<button type="button" data-d="" aria-pressed="true">All week</button>',
                 '<button type="button" data-d="now" class="now" aria-pressed="false">Right now</button>']
        for i, d in enumerate(WEEK):
            lbl = "Today" if i == 0 else ("Tomorrow" if i == 1 else DOW[pydow(d)][:3] + " " + fmt_date(d))
            chips.append(f'<button type="button" data-d="{i}" data-dow="{pydow(d)}" aria-pressed="false">{e(lbl)}</button>')
        days = '<div class="chiprow" id="dayPick" role="group" aria-label="Pick a day">' + "".join(chips) + "</div>"
    return ('<div class="filters"><div class="areafilter"><label for="areaSel">Area</label><select id="areaSel">' + "".join(opts) + "</select>"
            '<span class="areacount" id="areaCount"></span></div>' + days + tchips + "</div>"
            "<script>document.addEventListener('DOMContentLoaded',function(){var R=" + json.dumps(rmap) + ";" + FILTER_JS + "});</script>")


TICKER = ticker_text()
# constant, slow reading speed (~40 px/sec) no matter how long the ticker is
TICKER_SECS = max(45, round((len(TICKER) * 8.5 + 1200) / 55))


def page(path, title, desc, body, current="", jsonld=None):
    canon = BASE + path
    ads_head = (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={e(CFG["adsense_client"])}" crossorigin="anonymous"></script>'
                if CFG.get("adsense_client") else "")
    nav = "".join(f'<a href="{h}"{" aria-current=\"page\"" if h == current else ""}>{e(t)}</a>' for h, t in NAV)
    ld = f'<script type="application/ld+json">{json.dumps(jsonld)}</script>' if jsonld else ""
    filt = filters(body) if ('class="card ev' in body and not path.startswith(("/bars/", "/areas/"))) else ""
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
<header class="masthead"><div class="wrap"><a class="logo" href="/">{LOGO_SVG}<b>Pour<span>cast</span><sup class="tm">™</sup></b></a><div class="strap"><b>{e(CITY)}</b><i>7-Day Bar Forecast</i></div></div></header>
<div class="ticker" aria-label="Today's highlights"><span class="lbl">Today</span><span class="track"><span class="run" style="animation-duration:{TICKER_SECS}s">{e(TICKER)}</span></span></div>
<nav class="secnav" aria-label="Sections"><div class="wrap">{nav}</div></nav>
<main><div class="wrap">
{filt}{body}
</div></main>
<footer><div class="wrap">
<div><b>{e(CFG["site_name"])}</b>: game watches, trivia, karaoke and happy hours at {e(CITY)}-area bars. Updated {fmt_date(TODAY)}, {TODAY.year}.</div>
<div>Instagram: <a href="https://www.instagram.com/{e(CFG["instagram"])}/">@{e(CFG["instagram"])}</a> · Email: {e(CFG["contact_email"])}</div>
<div><a href="/about/">About</a> · <a href="/submit/">Post an event</a> · <a href="/privacy/">Privacy policy</a> · Deals and times change, so check with the bar before you go. Please drink responsibly; 21+.</div>
<div>Pourcast™ © {TODAY.year} Pourcast. All rights reserved.</div>
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


DUR = {"college": 210, "game": 210, "trivia": 120, "karaoke": 240, "music": 180, "happy": 180, "special": 180}
_WIN = re.compile(r"(\d{1,2})(?::(\d\d))?\s*(AM|PM)?\s*[–-]\s*(?:(\d{1,2})(?::(\d\d))?\s*(AM|PM)|(close|midnight))", re.I)


def span(ev):
    """(start, end) in minutes after midnight; end can pass 1440 (after midnight)."""
    t = ev.get("time") or ""
    lab = (ev.get("timeLabel") or "").lower()
    if not t or "all day" in lab:
        st = int(t[:2]) * 60 + int(t[3:]) if t else 11 * 60
        return st, 26 * 60
    st = int(t[:2]) * 60 + int(t[3:])
    m = _WIN.search(ev.get("title", "") + " " + lab)
    if m:
        if m.group(7):
            en = 24 * 60 if m.group(7).lower() == "midnight" else 26 * 60
        else:
            h = int(m.group(4)) % 12 + (12 if m.group(6).upper() == "PM" else 0)
            en = h * 60 + int(m.group(5) or 0)
        while en <= st:
            en += 24 * 60
        return st, en
    return st, st + DUR.get(ev.get("type"), 180)


def merge(evs):
    """Collapse the same deal at several locations of one chain into one card."""
    out, seen = [], {}
    for x in evs:
        b = BARS.get(x["barId"]) or {}
        k = (b.get("name"), x.get("type"), x.get("title"), x.get("deals"), x.get("time"), x.get("timeLabel"), x.get("team"))
        if b.get("name") and k in seen:
            seen[k].setdefault("_bars", [seen[k]["barId"]]).append(x["barId"])
            continue
        y = dict(x)
        seen[k] = y
        out.append(y)
    return out


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
    bids = ev.get("_bars") or [ev["barId"]]
    areas = [(BARS.get(b) or {}).get("area") or "" for b in bids]
    if len(bids) > 1:
        where = (f'{e(BARS[bids[0]]["name"])} · {len(bids)} locations: '
                 + ", ".join(f'<a href="{bar_url(b)}">{e(a or "Nashville")}</a>' for b, a in zip(bids, areas)))
    else:
        where = f'<a href="{bar_url(bids[0])}">{e(bar_label(bids[0]))}</a>'
    timeattr = ""
    if d is not None:
        st, en = span(ev)
        timeattr = f' data-date="{d.isoformat()}" data-s="{st}" data-e="{en}"'
    return (f'<article class="card ev {e(t)}" data-type="{e(t)}" data-area="{e("|".join(areas))}"{timeattr}><div class="meta"><span class="badge">{e(label)}</span><span class="when">{e(sched)}{e(when(ev))}</span><span class="live"></span></div>'
            f'<div class="title">{e(ev["title"])}</div><div class="where">{where}{host}</div>'
            f'{"<div class=chips>" + "".join(chips) + "</div>" if chips else ""}</article>')


def upcoming(evs):
    """Events in the next 7 days, one-time ones first by date, weekly ones by day."""
    out = []
    for d in WEEK:
        for x in merge(sorted([x for x in evs if occurs(x, d)], key=sort_key)):
            out.append((d, x))
    return out


# ---------- pages ----------
DAY_ICON = {"college": ("🏈", "Game-day storm"), "game": ("🏈", "Game-day storm"), "happy": ("🍻", "Happy-hour front"),
            "trivia": ("🧠", "Trivia showers"), "karaoke": ("🎤", "Karaoke winds"), "music": ("🎸", "Live-music breeze"),
            "special": ("✨", "Special conditions")}


def conditions_panel():
    pf = os.path.join(ROOT, "data", "picks.json")
    picks = (json.load(open(pf)) if os.path.exists(pf) else {}).get(TODAY.isoformat(), {})
    strip = []
    for i, d in enumerate(WEEK):
        evs = [x for x in EVENTS if occurs(x, d)]
        games = sum(1 for x in evs if x.get("type") in ("college", "game"))
        cnt = {}
        for x in evs:
            cnt[x.get("type")] = cnt.get(x.get("type"), 0) + 1
        top = "college" if games >= 5 else (max(cnt, key=cnt.get) if cnt else None)
        icon = DAY_ICON.get(top, ("☀️", ""))[0] if top else "☀️"
        lbl = "Today" if i == 0 else DOW[pydow(d)][:3]
        strip.append(f'<a class="fday" href="/?day={["sun","mon","tue","wed","thu","fri","sat"][pydow(d)]}"><b>{e(lbl)}</b><span class="ficon">{icon}</span><small>{len(evs)} events</small></a>')
    tev = [x for x in EVENTS if occurs(x, WEEK[0])]
    g = sum(1 for x in tev if x.get("type") in ("college", "game"))
    h = sum(1 for x in tev if x.get("type") == "happy")
    tk = sum(1 for x in tev if x.get("type") in ("trivia", "karaoke"))
    if g >= 5:
        headline = f"⛈️ Game-day storm: {g} watch parties rolling through"
    elif h >= 20:
        headline = f"🍻 Happy-hour front moving in: {h} deals across town"
    else:
        headline = f"🌤️ Mostly pleasant: {len(tev)} things on tonight"
    pl = lambda n, a, b: f"{n} {a if n == 1 else b}"
    lines = [pl(h, "happy hour", "happy hours"), pl(g, "game watch", "game watches") if g else "", pl(tk, "trivia or karaoke night", "trivia & karaoke nights") if tk else ""]
    pick = ""
    if picks.get("good"):
        pick += f'<div class="fpick"><b>Game of the Day</b> {e(picks["good"])}<small>{e(picks.get("goodWhy", ""))}</small></div>'
    if picks.get("drink"):
        dr = picks["drink"]
        pick += f'<div class="fpick"><b>Drink of the Day</b> {e(dr.get("name", ""))} at {e(BARS.get(dr.get("barId"), {}).get("name", ""))}<small>{e(dr.get("desc", ""))}</small></div>'
    return ('<section class="conditions"><div class="ctop"><span class="clabel">Tonight\'s conditions</span>'
            f'<h2 class="chead">{e(headline)}</h2><p class="cline">{e(" · ".join(l for l in lines if l))}</p>{pick}'
            '<div class="cbtns"><a class="mapbtn" href="/?day=now">Right now</a><a class="mapbtn ghost" href="/map/">Map</a>'
            '<a class="mapbtn ghost" href="/tonight/happy-hour/">Happy hour</a></div></div>'
            f'<div class="fstrip">{"".join(strip)}</div></section>')


SWEAT_SVG = ('<svg viewBox="0 0 240 220" class="merchsvg" role="img" aria-label="{label}"><path d="M78 22 L102 12 Q120 30 138 12 L162 22 L200 60 L224 180 L198 188 L172 100 L172 205 L68 205 L68 100 L42 188 L16 180 L40 60 Z" fill="{fill}" stroke="rgba(0,0,0,.35)" stroke-width="2"/>'
             '<path d="M102 12 Q120 34 138 12" fill="none" stroke="rgba(0,0,0,.35)" stroke-width="2"/><rect x="68" y="194" width="104" height="11" fill="rgba(0,0,0,.08)"/>'
             '<path d="M16 180 L42 188 L44 178 L19 170 Z M224 180 L198 188 L196 178 L221 170 Z" fill="rgba(0,0,0,.08)"/>'
             '<text x="148" y="66" text-anchor="middle" font-family="Barlow,Arial" font-style="italic" font-weight="900" font-size="11" fill="{ink}">Pourcast</text>'
             '<text x="148" y="76" text-anchor="middle" font-family="Barlow Condensed,Arial" font-weight="700" font-size="5.5" letter-spacing="1" fill="{ink}">NASHVILLE · EST. 2026</text></svg>')
BACK_SVG = ('<svg viewBox="0 0 240 220" class="merchsvg" role="img" aria-label="{label}, back"><path d="M78 22 L102 16 Q120 22 138 16 L162 22 L200 60 L224 180 L198 188 L172 100 L172 205 L68 205 L68 100 L42 188 L16 180 L40 60 Z" fill="{fill}" stroke="rgba(0,0,0,.35)" stroke-width="2"/>'
            '<defs><path id="arc{key}" d="M74 116 Q120 58 166 116"/></defs><text font-family="Barlow Condensed,Arial" font-weight="800" font-size="7.5" letter-spacing=".5" fill="{ink}"><textPath href="#arc{key}" startOffset="50%" text-anchor="middle">7-DAY BAR FORECAST</textPath></text>'
            '<circle cx="120" cy="124" r="13" fill="none" stroke="{ink}" stroke-width="2"/><path d="M114 120 h9 v10 h-9 z M123 122 h3 a2 2 0 0 1 2 2 v3 a2 2 0 0 1 -2 2 h-3" fill="none" stroke="{ink}" stroke-width="1.8"/>'
            '<text x="120" y="156" text-anchor="middle" font-family="Barlow,Arial" font-style="italic" font-weight="900" font-size="15" fill="{ink}">POURCAST</text>'
            '<text x="120" y="167" text-anchor="middle" font-family="Barlow Condensed,Arial" font-weight="700" font-size="5.6" letter-spacing=".6" fill="{ink}">100% CHANCE OF A GOOD NIGHT</text></svg>')
PANTS_SVG = ('<svg viewBox="0 0 240 220" class="merchsvg" role="img" aria-label="{label}"><path d="M75 15 L165 15 L180 200 L130 200 L120 80 L110 200 L60 200 Z" fill="{fill}" stroke="rgba(0,0,0,.35)" stroke-width="2"/>'
             '<rect x="75" y="15" width="90" height="14" fill="rgba(0,0,0,.1)"/><path d="M112 29 L110 44 M128 29 L130 44" stroke="{ink}" stroke-width="1.5"/>'
             '<rect x="62" y="188" width="48" height="12" fill="rgba(0,0,0,.1)"/><rect x="130" y="188" width="48" height="12" fill="rgba(0,0,0,.1)"/>'
             '<text x="100" y="62" text-anchor="middle" font-family="Barlow,Arial" font-style="italic" font-weight="900" font-size="8" fill="{ink}">Pourcast</text></svg>')


def build_shop():
    items = [("The Forecast Crew", "Washed Navy", "Garment-dyed heavyweight crewneck. Small chest hit up front, arched 7-Day Bar Forecast print on the back.", "#3A4660", "#EFE6D2", True),
             ("Last Call Crew", "Bone", "Oversized cream crewneck with tonal navy print. The one you'll steal back from your friends.", "#EFE6D2", "#2F3B55", True),
             ("Front Porch Crew", "Sage", "Boxy heavyweight crewneck in muted sage, cream print front and back.", "#9DAA92", "#F6F0E1", True),
             ("Sunday Scaries Sweats", "Washed Navy", "Relaxed fleece joggers, small Pourcast hit on the thigh. Built for brunch and game day.", "#3A4660", "#EFE6D2", False),
             ("Recovery Sweats", "Heather Oat", "Oat fleece sweatpants with a tonal embroidered logo.", "#D8CDB8", "#5A4A3A", False)]
    mail = f'mailto:{CFG["contact_email"]}?subject=' + quote_plus("Pourcast merch: put me on the list")
    cards = ""
    for i, (n, col, d, f, ink, top) in enumerate(items):
        art = SWEAT_SVG.format(label=e(n), fill=f, ink=ink)
        if top:
            art = f'<div class="merchpair">{art}{BACK_SVG.format(label=e(n), fill=f, ink=ink, key=i)}</div>'
        else:
            art = PANTS_SVG.format(label=e(n), fill=f, ink=ink)
        cards += f'<article class="card merch">{art}<h3>{e(n)}</h3><p class="mcol">{e(col)}</p><p class="muted">{e(d)}</p><span class="chip">Coming soon</span></article>'
    body = (f'<h1>Pourcast merch</h1><p class="dek">Heavyweight, garment-dyed sweats in washed colors with a small Pourcast hit up front and the forecast on the back. First drop is coming soon; these are design previews.</p>'
            f'<div class="grid merchgrid">{cards}</div>'
            f'<div class="alert"><b>First dibs</b><span>Want in on the first drop? <a href="{mail}">Email us</a> or DM <a href="https://www.instagram.com/{e(CFG["instagram"])}/">@{e(CFG["instagram"])}</a> and we\'ll let you know when it\'s live.</span></div>')
    page("/shop/", f"Pourcast Merch: Sweatshirts & Sweatpants | {CITY} Bar Forecast",
         "Pourcast sweatshirts, hoodies and sweatpants. First drop coming soon.", body, "/shop/")


def build_home():
    parts = [f'<h1>{e(CITY)} 7-day bar forecast</h1><p class="dek">Where to watch the game, find trivia and karaoke, and catch happy hour across {e(CITY)}, {fmt_date(WEEK[0])}–{fmt_date(WEEK[-1])}.</p>', conditions_panel()]
    cfb_sat = [x for x in EVENTS if x.get("type") == "college" and not x.get("weekly") and x.get("date") in {d.isoformat() for d in WEEK}]
    if cfb_sat:
        parts.append(f'<div class="alert"><b>Weather alert</b><span>100% chance of college football: {len(cfb_sat)} watch parties at {e(CITY)} home bars this week. <a href="/tonight/college-football/">See where every fan base watches</a>.</span></div>')
    parts.append(vote_alert())
    for i, d in enumerate(WEEK):
        evs = merge(sorted([x for x in EVENTS if occurs(x, d)], key=lambda x: (0 if x.get("type") == "college" else 1, sort_key(x))))
        parts.append(f'<section class="dayblock" data-day="{i}"><h2>{e(day_name(d))} · {e(DOW[pydow(d)][:3])} {fmt_date(d)}</h2>')
        parts.append(('<div class="grid">' + "".join(card(x, d) for x in evs) + '</div>' if evs else '<div class="empty">Nothing posted yet. <a href="/submit/">Add an event</a>.</div>') + '</section>')
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
                    blk = f'<section class="dayblock" data-day="{WEEK.index(d)}"><div class="day">{e(day_name(d))} · {fmt_date(d)}</div><div class="grid">'
                    parts.append(blk if cur is None else '</div></section>' + blk)
                    cur = d
                parts.append(card(x, d))
            parts.append("</div></section>")
        else:
            parts.append('<div class="empty">Nothing posted for the next 7 days. <a href="/submit/">Add one</a>.</div>')
        parts.append(ad_slot())
        if t in ("college", "game"):
            teams = sorted({tm for b in BARS.values() for tm in b["teams"] if (tm in NFL) == (t == "game")})
            if teams:
                parts.append(f'<h2>Find your team\'s home bar</h2><ul class="list">' + "".join(f'<li><a href="{team_url(tm)}">{e(tm)}</a></li>' for tm in teams) + "</ul>")
        page(f"/tonight/{s}/", f"{heading} in {CITY} This Week | Pourcast",
             f"{heading} at {CITY}-area bars this week, with times, deals and where to go.", "".join(parts), f"/tonight/{s}/")


def build_popups():
    pf = os.path.join(ROOT, "data", "popups.json")
    pops = json.load(open(pf)) if os.path.exists(pf) else []
    t = TODAY.isoformat()
    live = [p for p in pops if not p.get("end") or p["end"] >= t]
    live.sort(key=lambda p: p["start"])
    md = lambda iso: fmt_date(date.fromisoformat(iso))
    parts = [f'<h1>Christmas pop-up bars in {e(CITY)}</h1><p class="dek">Holiday pop-ups for {TODAY.year}, with dates, age rules and whether you need a reservation. These stay off the daily forecast. Check each bar before you go; dates can shift.</p>']
    def block(title, items):
        if not items:
            return
        parts.append(f'<h2>{e(title)}</h2><div class="grid">')
        for p in items:
            end = p.get("endLabel") or (md(p["end"]) if p.get("end") else "the holidays")
            status = "Open now" if p["start"] <= t else f"Opens {md(p['start'])}"
            chips = f'<span class="chip">{e(p["notes"])}</span>' if p.get("notes") else ""
            parts.append(f'<article class="card"><div class="when">{e(status)}</div><h3>{e(p["name"])}</h3>'
                         f'<p class="muted">{e(p["host"])}{" · " + e(p["area"]) if p.get("area") else ""}</p>'
                         f'<p>{md(p["start"])} through {e(end)}</p><div class="chips">{chips}</div>'
                         f'<p class="small"><a href="{e(p["source"])}" target="_blank" rel="noopener">Details</a></p></article>')
        parts.append('</div>')
    block("Open now", [p for p in live if p["start"] <= t])
    block("Coming soon", [p for p in live if p["start"] > t])
    if not live:
        parts.append('<div class="empty">No holiday pop-ups posted right now.</div>')
    page("/christmas/", f"Christmas Pop-Up Bars in {CITY} {TODAY.year} | Pourcast",
         f"Every holiday and Christmas pop-up bar in {CITY} this season, with dates and reservation info.", "".join(parts), "/christmas/")


LEAFLET = ('<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" crossorigin="">'
           '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" crossorigin=""></script>')
MAP_COLORS = {"college": "#C8202A", "game": "#0B3D91", "happy": "#E0A100", "trivia": "#5B2A86",
              "karaoke": "#1E7A46", "music": "#1E7A46", "special": "#B5338A"}


def map_data():
    out = []
    for b in BARS.values():
        if not b.get("lat"):
            continue
        evs = []
        for i, d in enumerate(WEEK):
            for x in sorted([x for x in EVENTS if x["barId"] == b["id"] and occurs(x, d)], key=sort_key):
                st, en = span(x)
                evs.append({"d": i, "date": d.isoformat(), "t": x.get("type", "special"), "title": x["title"],
                            "when": when(x), "deals": x.get("deals", ""), "s": st, "e": en})
        maps = "https://www.google.com/maps/search/?api=1&query=" + quote_plus(b["name"] + ", " + (b.get("address") or ""))
        out.append({"id": b["id"], "name": b["name"], "area": b.get("area", ""), "addr": b.get("address", ""),
                    "lat": b["lat"], "lng": b["lng"], "url": bar_url(b["id"]), "dir": maps, "ev": evs})
    return out


MAP_JS = r"""
var COL=__COLORS__,LBL={college:'College football',game:'NFL / game',happy:'Happy hour',trivia:'Trivia',karaoke:'Karaoke',music:'Live music',special:'Special'};
function esc(s){return String(s||'').replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function chi(){var p=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Chicago',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date()),o={};p.forEach(function(x){o[x.type]=x.value;});return{date:o.year+'-'+o.month+'-'+o.day,min:(+o.hour)*60+(+o.minute)};}
function km(a,b,c,d){var R=6371,x=(c-a)*Math.PI/180,y=(d-b)*Math.PI/180,h=Math.sin(x/2)*Math.sin(x/2)+Math.cos(a*Math.PI/180)*Math.cos(c*Math.PI/180)*Math.sin(y/2)*Math.sin(y/2);return 2*R*Math.asin(Math.sqrt(h));}
function miles(k){var m=k*0.621371;return m<0.1?'right here':(m<10?m.toFixed(1):Math.round(m))+' mi away';}
"""

MAP_PAGE_JS = r"""
var map=L.map('bigmap',{zoomControl:true}).setView([36.158,-86.785],13);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; OpenStreetMap contributors'}).addTo(map);
var st={day:'0',type:''},me=null,meMark=null,marks=[];
function evsFor(b){var n=chi();return b.ev.filter(function(e){
  if(st.day==='now'){if(e.date!==n.date)return false;if(!(n.min>=e.s&&n.min<e.e))return false;}
  else if(String(e.d)!==st.day)return false;
  if(st.type&&!(e.t===st.type||(st.type==='game'&&e.t==='college')))return false;
  if(st.day!=='now'&&e.date===n.date&&n.min>=e.e)return false;
  return true;});}
function popup(b,evs){var h='<div class="mp"><b>'+esc(b.name)+'</b><div class="mpa">'+esc(b.area)+(b.addr?' · '+esc(b.addr):'')+'</div>';
  if(me)h+='<div class="mpd">📍 '+miles(km(me[0],me[1],b.lat,b.lng))+'</div>';
  if(evs.length){h+='<ul>'+evs.slice(0,5).map(function(e){return '<li><span class="dot" style="background:'+COL[e.t]+'"></span><b>'+esc(e.when)+'</b> '+esc(e.title)+(e.deals?'<br><small>'+esc(e.deals)+'</small>':'')+'</li>';}).join('')+'</ul>';if(evs.length>5)h+='<small>+'+(evs.length-5)+' more</small>';}
  else h+='<div class="mpa">Nothing posted for this pick.</div>';
  return h+'<div class="mpl"><a href="'+b.url+'">Bar page</a> · <a href="'+b.dir+'" target="_blank" rel="noopener">Directions</a></div></div>';}
function draw(){marks.forEach(function(m){map.removeLayer(m);});marks=[];var shown=0,list=[];
  BARS.forEach(function(b){var evs=evsFor(b),on=evs.length>0;if(!on&&(st.type||st.day==='now'))return;
    var m=L.circleMarker([b.lat,b.lng],{radius:on?9:5,color:'#fff',weight:2,fillColor:on?COL[evs[0].t]:'#8A96A8',fillOpacity:on?.95:.7}).addTo(map);
    m.bindPopup(function(){return popup(b,evsFor(b));},{maxWidth:280});marks.push(m);if(on){shown++;list.push([b,evs]);}});
  document.getElementById('mapCount').textContent=shown+' bars with something on';
  var near=document.getElementById('nearList');
  if(me){list.sort(function(a,c){return km(me[0],me[1],a[0].lat,a[0].lng)-km(me[0],me[1],c[0].lat,c[0].lng);});
    near.innerHTML=!list.length?'<p class="muted">Nothing on near you for this pick. Try another day or type.</p>':'<h2>Closest to you</h2><ol class="near">'+list.slice(0,8).map(function(x){var b=x[0];return '<li><a href="'+b.url+'">'+esc(b.name)+'</a> <span class="muted">'+miles(km(me[0],me[1],b.lat,b.lng))+'</span><br><small>'+esc(x[1][0].when)+' · '+esc(x[1][0].title)+'</small></li>';}).join('')+'</ol>';}
}
function press(sel,attr,v){document.querySelectorAll(sel+' button').forEach(function(b){b.setAttribute('aria-pressed',b.getAttribute(attr)===v?'true':'false');});}
document.querySelectorAll('#mapDay button').forEach(function(b){b.addEventListener('click',function(){st.day=b.getAttribute('data-d');press('#mapDay','data-d',st.day);draw();});});
document.querySelectorAll('#mapType button').forEach(function(b){b.addEventListener('click',function(){st.type=b.getAttribute('data-t');press('#mapType','data-t',st.type);draw();});});
document.getElementById('locBtn').addEventListener('click',function(){var btn=this;if(!navigator.geolocation){btn.textContent='Location not available';return;}
  btn.textContent='Finding you…';navigator.geolocation.getCurrentPosition(function(p){me=[p.coords.latitude,p.coords.longitude];
    if(meMark)map.removeLayer(meMark);meMark=L.circleMarker(me,{radius:9,color:'#fff',weight:3,fillColor:'#1A73E8',fillOpacity:1}).addTo(map).bindPopup('You are here');
    map.setView(me,15);btn.textContent='📍 Showing where you are';draw();},
  function(){btn.textContent='Couldn\'t get your location. Check location permission.';},{enableHighAccuracy:true,timeout:10000});});
var q=new URLSearchParams(location.search);if(q.get('day')==='now'){st.day='now';press('#mapDay','data-d','now');}
var fb=q.get('bar');draw();
if(fb){BARS.forEach(function(b,i){if(b.id===fb){map.setView([b.lat,b.lng],16);marks.forEach(function(m){var ll=m.getLatLng();if(ll.lat===b.lat&&ll.lng===b.lng)m.openPopup();});}});}
"""

BAR_MAP_JS = r"""
var B=window.BARPT,m=L.map('barmap',{scrollWheelZoom:false}).setView([B.lat,B.lng],16);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; OpenStreetMap contributors'}).addTo(m);
L.circleMarker([B.lat,B.lng],{radius:10,color:'#fff',weight:3,fillColor:'#C8202A',fillOpacity:1}).addTo(m).bindPopup(esc(B.name)).openPopup();
document.getElementById('barLoc').addEventListener('click',function(){var btn=this;if(!navigator.geolocation){btn.textContent='Location not available';return;}
  btn.textContent='Finding you…';navigator.geolocation.getCurrentPosition(function(p){var me=[p.coords.latitude,p.coords.longitude];
    L.circleMarker(me,{radius:9,color:'#fff',weight:3,fillColor:'#1A73E8',fillOpacity:1}).addTo(m).bindPopup('You are here');
    L.polyline([me,[B.lat,B.lng]],{color:'#1A73E8',weight:3,dashArray:'6 6'}).addTo(m);
    m.fitBounds([me,[B.lat,B.lng]],{padding:[40,40],maxZoom:16});btn.textContent='📍 You are '+miles(km(me[0],me[1],B.lat,B.lng));},
  function(){btn.textContent='Couldn\'t get your location. Check location permission.';},{enableHighAccuracy:true,timeout:10000});});
"""


def bar_map_block(b):
    if not b.get("lat"):
        return ""
    pt = json.dumps({"lat": b["lat"], "lng": b["lng"], "name": b["name"]})
    return (f'<div class="barmapwrap"><div id="barmap" class="barmap" role="img" aria-label="Map showing {e(b["name"])}"></div>'
            f'<div class="btns"><button type="button" class="mapbtn" id="barLoc">📍 Show where I am</button>'
            f'<a class="mapbtn ghost" href="/map/?bar={e(b["id"])}">Open the big map</a></div></div>'
            + LEAFLET + "<script>window.BARPT=" + pt + ";document.addEventListener('DOMContentLoaded',function(){"
            + MAP_JS.replace("__COLORS__", json.dumps(MAP_COLORS)) + BAR_MAP_JS + "});</script>")


def build_map():
    data = map_data()
    days = ['<button type="button" data-d="now" class="now" aria-pressed="false">Right now</button>']
    for i, d in enumerate(WEEK):
        lbl = "Today" if i == 0 else ("Tomorrow" if i == 1 else DOW[pydow(d)][:3] + " " + fmt_date(d))
        days.append(f'<button type="button" data-d="{i}" aria-pressed="{"true" if i == 0 else "false"}">{e(lbl)}</button>')
    types = "".join(f'<button type="button" data-t="{v}" aria-pressed="{"true" if not v else "false"}">{e(l)}</button>' for v, l in TYPE_CHIPS)
    legend = "".join(f'<span><i style="background:{c}"></i>{e(l)}</span>' for l, c in
                     [("College", MAP_COLORS["college"]), ("NFL", MAP_COLORS["game"]), ("Happy hour", MAP_COLORS["happy"]),
                      ("Trivia", MAP_COLORS["trivia"]), ("Karaoke / music", MAP_COLORS["music"]), ("Special", MAP_COLORS["special"])])
    body = (f'<h1>{e(CITY)} bar map</h1><p class="dek">Every bar on Pourcast, colored by what\'s on. Tap a pin for tonight\'s lineup and directions.</p>'
            '<div class="btns"><button type="button" class="mapbtn" id="locBtn">📍 Show where I am</button><span class="muted" id="mapCount"></span></div>'
            f'<div class="chiprow" id="mapDay">{"".join(days)}</div><div class="chiprow types" id="mapType">{types}</div>'
            '<div id="bigmap" class="bigmap" role="application" aria-label="Map of Nashville bars"></div>'
            f'<div class="legend">{legend}<span><i style="background:#8A96A8"></i>Nothing posted</span></div><div id="nearList"></div>'
            + LEAFLET + "<script>var BARS=" + json.dumps(data, ensure_ascii=False) + ";document.addEventListener('DOMContentLoaded',function(){"
            + MAP_JS.replace("__COLORS__", json.dumps(MAP_COLORS)) + MAP_PAGE_JS + "});</script>")
    page("/map/", f"{CITY} Bar Map: Happy Hours, Watch Parties & Trivia | Pourcast",
         f"Map of {CITY} bars with tonight's happy hours, game watch parties, trivia and karaoke. See what's closest to you.", body, "/map/")


def build_bars():
    by_area = {}
    for b in BARS.values():
        by_area.setdefault(b.get("area") or "Other Nashville bars", []).append(b)
    parts = [f'<h1>{e(CITY)} bars on Pourcast</h1><p class="dek">{len(BARS)} bars across {e(CITY)}, by neighborhood.</p>']
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
            p.append(bar_map_block(b))
        p.append(award_badges(b["id"]))
        if b["teams"]:
            p.append('<div class="alert"><b>Home bar for</b><span>' + ", ".join(f'<a href="{team_url(t)}">{e(t)}</a>' for t in b["teams"]) + " fans</span></div>")
        p.append('<h2>Coming up</h2>' + ('<div class="grid">' + "".join(card(x, show_day=True) for x in once) + '</div>' if once else '<div class="empty">No one-time events posted yet.</div>'))
        p.append('<h2>Every week</h2>' + ('<div class="grid">' + "".join(card(x, show_day=True) for x in weekly) + '</div>' if weekly else '<div class="empty">No weekly specials posted yet. Work here? <a href="/submit/">Add yours free</a>.</div>'))
        p.append(ad_slot())
        srcs = sorted({x["source"] for x in evs if x.get("source")})
        own = [s for s in srcs if s.startswith("http") and not re.search(r"nashvilleguru|nashvillego|eventbrite|williamsonscene|franklinis|citylifestyle|baselocal", s)]
        ver = sorted(x["verified"] for x in evs if x.get("verified"))
        line = "Listings checked by Pourcast" + (f" (last confirmed {fmt_date(date.fromisoformat(ver[-1]))})" if ver else "") + ". Deals and times change, so confirm with the bar."
        if own:
            line += ' From the bar: ' + " · ".join(f'<a href="{e(s)}" rel="nofollow">{e(re.sub(r"^https?://(www\\.)?", "", s).split("/")[0])}</a>' for s in own)
        p.append(f'<p class="src">{line}</p>')
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
         f'<p>We track team home bars, weekly events and happy hour deals across {e(CITY)}, and update game listings every week of the season. Listings come from bars, organizers and public sources; deals and times change, so check with the bar before you go.</p>'
         f'<p>Contact: {mail} · Instagram <a href="https://www.instagram.com/{e(CFG["instagram"])}/">@{e(CFG["instagram"])}</a></p>')
    page("/submit/", "Post an Event on Pourcast", "Bars, social clubs and organizers can post events on Pourcast for free.",
         f'<h1>Post your event, free</h1><p class="dek">Run a trivia night, karaoke, watch party, happy hour or social club meetup at a {e(CITY)}-area bar? Send it to us.</p>'
         f'<div class="card"><p style="margin:0">Email <b>{mail}</b> with:</p><ul><li>Bar name and neighborhood</li><li>Event name and type</li><li>Day and start time (one time, or every week)</li><li>Specials or cover, and who\'s hosting</li></ul><p style="margin:0">We\'ll add it to the forecast, and the best ones go in our weekly email and on Instagram.</p></div>', "/submit/")
    page("/privacy/", "Privacy Policy | Pourcast", "How Pourcast handles data, cookies and advertising.",
         f'<h1>Privacy policy</h1><p class="dek">Last updated {fmt_date(TODAY)}, {TODAY.year}.</p>'
         '<h2>What we collect</h2><p>This site does not require an account. If you email us, we keep your message to reply and to list your event. If you vote for Bar of the Month or Bartender of the Week, we use your email only to count one vote per person and never share it.</p>'
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


# ---------- Bar of the Month / Bartender of the Week ----------
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def vote_periods():
    wk_start = TODAY - timedelta(days=TODAY.weekday())  # Monday
    if TODAY.weekday() >= 4:  # Fri-Sun: votes count toward next week so every week gets a full run
        wk_start += timedelta(days=7)
    wk_end = wk_start + timedelta(days=6)
    nxt = wk_end + timedelta(days=1)
    m1 = (TODAY.replace(day=28) + timedelta(days=4)).replace(day=1)
    return {"week": wk_start.isoformat(), "week_label": f"{fmt_date(wk_start)}–{fmt_date(wk_end)}", "week_announce": f"Monday, {fmt_date(nxt)}",
            "month": TODAY.strftime("%Y-%m"), "month_label": MONTHS[TODAY.month - 1], "month_close": fmt_date(m1 - timedelta(days=1)),
            "month_announce": f"{DOW[pydow(m1)]}, {fmt_date(m1)}"}


def vote_alert():
    v = vote_periods()
    return (f'<div class="alert"><b>🏆 Vote now</b><span>Who pours the best in {e(CITY)}? Write in your <a href="/vote/">Bartender of the Week</a> '
            f'(winner {e(v["week_announce"])}) and <a href="/vote/">{e(v["month_label"])} Bar of the Month</a> (winner {e(v["month_announce"])}).</span></div>')


def award_badges(bid):
    out = []
    for w in AWARDS.get("bar_of_month", []):
        if w.get("barId") == bid:
            y, m = w["month"].split("-")
            out.append(f'🏆 {MONTHS[int(m) - 1]} {y} Bar of the Month')
    for w in AWARDS.get("bartender_of_week", []):
        if w.get("barId") == bid:
            out.append(f'🍸 Bartender of the Week: {e(w["name"])} (week of {fmt_date(date.fromisoformat(w["week"]))})')
    return f'<div class="alert"><b>Voted by {e(CITY)}</b><span>{"<br>".join(out)}</span></div>' if out else ""


def build_vote():
    v = vote_periods()
    opts = "".join(f'<option value="{e(b["name"])} ({e(b.get("area") or CITY)})"></option>' for b in sorted(BARS.values(), key=lambda b: b["name"].lower()))
    action = CFG.get("vote_form_action", "")
    mail = CFG["contact_email"]
    winners = []
    for w in sorted(AWARDS.get("bartender_of_week", []), key=lambda w: w["week"], reverse=True)[:8]:
        winners.append(f'<li><b>{e(w["name"])}</b> at <a href="{bar_url(w["barId"])}">{e(bar_label(w["barId"]))}</a> · week of {fmt_date(date.fromisoformat(w["week"]))}' + (f'<br><small>{e(w["why"])}</small>' if w.get("why") else "") + "</li>")
    mwin = []
    for w in sorted(AWARDS.get("bar_of_month", []), key=lambda w: w["month"], reverse=True)[:12]:
        y, m = w["month"].split("-")
        mwin.append(f'<li><a href="{bar_url(w["barId"])}"><b>{e(bar_label(w["barId"]))}</b></a> · {MONTHS[int(m) - 1]} {y}' + (f'<br><small>{e(w["why"])}</small>' if w.get("why") else "") + "</li>")
    fld = 'style="width:100%;font:inherit;padding:10px 12px;border:1px solid var(--line);border-radius:6px;background:var(--surface);color:var(--ink);box-sizing:border-box"'
    body = (f'<h1>Vote: Bar of the Month &amp; Bartender of the Week</h1>'
            f'<p class="dek">Forecast calls for a flood of nominations. Write in the {e(CITY)} bar and bartender who made your week, and we\'ll crown the winners on Instagram and on their Pourcast page.</p>'
            f'<div class="grid">'
            f'<div class="card" style="border-top:4px solid var(--turf)"><span class="badge" style="justify-self:start">Bartender of the Week</span><p style="margin:6px 0 0">Voting for <b>{e(v["week_label"])}</b>. Winner announced <b>{e(v["week_announce"])}</b>.</p></div>'
            f'<div class="card" style="border-top:4px solid var(--red)"><span class="badge" style="justify-self:start">Bar of the Month</span><p style="margin:6px 0 0">Voting for <b>{e(v["month_label"])}</b> closes {e(v["month_close"])}. Winner announced <b>{e(v["month_announce"])}</b>.</p></div>'
            f'</div>'
            f'<h2>Cast your vote</h2>'
            f'<form id="voteForm" class="card" style="gap:14px"{f" action={chr(34)}{e(action)}{chr(34)} method={chr(34)}post{chr(34)}" if action else ""}>'
            f'<fieldset style="border:0;padding:0;margin:0;display:flex;gap:18px;flex-wrap:wrap"><legend style="font-weight:800;margin-bottom:6px">I\'m voting for</legend>'
            f'<label><input type="radio" name="category" value="Bartender of the Week" checked> Bartender of the Week</label>'
            f'<label><input type="radio" name="category" value="Bar of the Month"> Bar of the Month</label></fieldset>'
            f'<label id="bartenderRow">Bartender\'s first name<br><input name="bartender" maxlength="40" autocomplete="off" {fld} placeholder="e.g. Sam"></label>'
            f'<label>Bar<br><input name="bar" list="barList" required maxlength="80" autocomplete="off" {fld} placeholder="Start typing, or write in any {e(CITY)} bar"></label>'
            f'<datalist id="barList">{opts}</datalist>'
            f'<label>Why? <span class="muted">(optional, we may quote you)</span><br><textarea name="why" maxlength="280" rows="3" {fld}></textarea></label>'
            f'<label>Your email <span class="muted">(one vote per person each period; never shared)</span><br><input type="email" name="email" required maxlength="120" {fld}></label>'
            f'<input type="hidden" name="period" value="">'
            f'<div class="btns"><button type="submit" class="mapbtn">Submit my vote</button></div>'
            f'<p id="voteMsg" class="muted" role="status" style="margin:0"></p></form>'
            f'<p class="src">One vote per person per category each week or month; duplicate and bulk votes are removed. Bars and staff can share the page, but please don\'t vote for yourself. 21+.</p>'
            f'<h2>Bartenders of the Week</h2>' + (f'<ul class="list">{"".join(winners)}</ul>' if winners else f'<div class="empty">First winner announced {e(v["week_announce"])}. Your vote could make the forecast.</div>') +
            f'<h2>Bars of the Month</h2>' + (f'<ul class="list">{"".join(mwin)}</ul>' if mwin else f'<div class="empty">The first Bar of the Month is crowned {e(v["month_announce"])}.</div>') +
            '<script>(function(){var f=document.getElementById("voteForm"),msg=document.getElementById("voteMsg"),row=document.getElementById("bartenderRow");'
            f'var P={{"Bartender of the Week":"{v["week"]}","Bar of the Month":"{v["month"]}"}},MAIL={json.dumps(mail)},ACT={json.dumps(action)};'
            'function cat(){return f.querySelector("input[name=category]:checked").value;}'
            'function sync(){var b=cat()==="Bartender of the Week";row.style.display=b?"":"none";f.bartender.required=b;}'
            'f.querySelectorAll("input[name=category]").forEach(function(r){r.addEventListener("change",sync);});sync();'
            'function key(){return "pc-vote-"+cat()+"-"+P[cat()];}'
            'f.addEventListener("submit",function(ev){ev.preventDefault();var c=cat();f.period.value=P[c];'
            'try{if(localStorage.getItem(key())){msg.textContent="You already voted for "+c+" this period. Thanks!";return;}}catch(x){}'
            'var done=function(){try{localStorage.setItem(key(),"1");}catch(x){}msg.textContent="Vote received. Thanks for keeping the forecast honest!";f.reset();sync();};'
            'if(ACT){fetch(ACT,{method:"POST",body:new FormData(f),headers:{"Accept":"application/json"}}).then(function(r){if(r.ok)done();else msg.textContent="Something went wrong. Please try again.";}).catch(function(){msg.textContent="Something went wrong. Please try again.";});return;}'
            'var lines=["Category: "+c,"Period: "+P[c],(c==="Bartender of the Week"?"Bartender: "+f.bartender.value+"\\n":"")+"Bar: "+f.bar.value,"Why: "+f.why.value,"Voter email: "+f.email.value];'
            'location.href="mailto:"+MAIL+"?subject="+encodeURIComponent("Pourcast vote: "+c)+"&body="+encodeURIComponent(lines.join("\\n"));'
            'msg.textContent="Your email app should open with your vote filled in. Hit send to make it count.";try{localStorage.setItem(key(),"1");}catch(x){}});})();</script>')
    ld = {"@context": "https://schema.org", "@type": "WebPage", "name": f"Vote: {CITY} Bar of the Month & Bartender of the Week", "url": BASE + "/vote/"}
    page("/vote/", f"Vote: {CITY} Bar of the Month & Bartender of the Week | Pourcast",
         f"Write in your favorite {CITY} bar and bartender. Pourcast crowns a Bartender of the Week every Monday and a Bar of the Month on the 1st.", body, "/vote/", ld)


if __name__ == "__main__":
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    shutil.copytree(os.path.join(ROOT, "assets"), os.path.join(OUT, "assets"))
    build_home(); build_types(); build_popups(); build_map(); build_shop(); build_bars(); build_teams(); build_static(); build_vote(); build_meta()
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
