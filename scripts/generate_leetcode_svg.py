#!/usr/bin/env python3
"""
Fetches LeetCode data and generates a full profile SVG card saved to assets/leetcode-profile.svg.
Also updates the <!-- LEETCODE_STATS_START --> ... <!-- LEETCODE_STATS_END --> block in README.md.
Run: python scripts/generate_leetcode_svg.py
"""

import json
import math
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError

USERNAME  = "brij_raj"
SVG_PATH  = "assets/leetcode-profile.svg"
README    = "README.md"
GRAPHQL   = "https://leetcode.com/graphql"

QUERY = """
query getUserStats($username: String!) {
  matchedUser(username: $username) {
    username
    profile { ranking reputation realName company countryName }
    submitStats: submitStatsGlobal {
      acSubmissionNum { difficulty count submissions }
    }
    userCalendar(year: 2025) { submissionCalendar totalActiveDays streak }
    badges { id displayName }
    languageProblemCount { languageName problemsSolved }
  }
  userContestRanking(username: $username) {
    attendedContestsCount rating globalRanking totalParticipants topPercentage
    badge { name }
  }
  userContestRankingHistory(username: $username) {
    attended rating ranking contest { title startTime }
  }
}
"""

def fetch(username):
    payload = json.dumps({"query": QUERY, "variables": {"username": username}}).encode()
    req = Request(GRAPHQL, data=payload, headers={
        "Content-Type": "application/json",
        "Referer": "https://leetcode.com",
        "User-Agent": "Mozilla/5.0 (GitHub Actions)",
    }, method="POST")
    try:
        with urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except URLError as e:
        print(f"ERROR: {e}"); sys.exit(1)

def arc(cx, cy, r, pct):
    if pct >= 1: pct = 0.9999
    a = pct * 2 * math.pi
    x2 = cx + r * math.sin(a)
    y2 = cy - r * math.cos(a)
    lg = 1 if a > math.pi else 0
    return f"M {cx:.1f} {cy-r:.1f} A {r} {r} 0 {lg} 1 {x2:.1f} {y2:.1f}"

def heatmap(cal_str, x0, y0, weeks=26):
    cal = json.loads(cal_str or "{}")
    today = datetime.now(timezone.utc).date()
    cells, cs = [], 12
    for w in range(weeks-1, -1, -1):
        for d in range(7):
            day = today - timedelta(weeks=w, days=(today.weekday()+1-d) % 7)
            ts  = int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp())
            n   = cal.get(str(ts), 0)
            col = ["#1e2d3d","#0e4429","#006d32","#26a641","#39d353"][
                0 if n==0 else 1 if n<=2 else 2 if n<=5 else 3 if n<=9 else 4]
            cx  = x0 + (weeks-1-w) * (cs+2)
            cy  = y0 + d * (cs+2)
            cells.append(f'<rect x="{cx}" y="{cy}" width="{cs}" height="{cs}" rx="2" fill="{col}"/>')
    return "\n  ".join(cells)

def sparkline(history, x0, y0, w=340, h=70):
    pts = [h for h in history if h.get("attended")]
    if len(pts) < 2:
        return f'<text x="{x0+w//2}" y="{y0+h//2}" text-anchor="middle" fill="#555" font-size="11">No history</text>'
    ratings = [p["rating"] for p in pts]
    mn, mx  = min(ratings), max(ratings)
    span    = mx - mn or 1
    coords  = []
    for i, r in enumerate(ratings):
        px = x0 + i * w / (len(ratings)-1)
        py = y0 + h - (r-mn)/span*h
        coords.append(f"{px:.1f},{py:.1f}")
    mi = ratings.index(mn); ma = ratings.index(mx)
    pmx = x0 + ma * w / (len(ratings)-1)
    pmy = y0 + h - (mx-mn)/span*h - 10
    last_x, last_y = coords[-1].split(",")
    return (f'<polyline points="{" ".join(coords)}" fill="none" stroke="#FFA116" stroke-width="1.5" stroke-linejoin="round"/>'
            f'<text x="{pmx:.1f}" y="{pmy:.1f}" text-anchor="middle" fill="#FFA116" font-size="10" font-weight="600">{int(mx)}</text>'
            f'<circle cx="{last_x}" cy="{last_y}" r="3" fill="#FFA116"/>')

def generate_svg(data):
    u  = data["data"]["matchedUser"]
    co = data["data"]["userContestRanking"]
    hi = data["data"].get("userContestRankingHistory", [])

    st   = {s["difficulty"]: s for s in u["submitStats"]["acSubmissionNum"]}
    tot  = st.get("All",    {}).get("count", 0)
    easy = st.get("Easy",   {}).get("count", 0)
    med  = st.get("Medium", {}).get("count", 0)
    hard = st.get("Hard",   {}).get("count", 0)
    e_t  = st.get("Easy",   {}).get("submissions", 949)
    m_t  = st.get("Medium", {}).get("submissions", 2066)
    h_t  = st.get("Hard",   {}).get("submissions", 942)

    cal      = u.get("userCalendar") or {}
    cal_str  = cal.get("submissionCalendar", "{}")
    act_days = cal.get("totalActiveDays", 0)
    streak   = cal.get("streak", 0)
    ranking  = u["profile"]["ranking"]
    rep      = u["profile"].get("reputation", 0)
    name     = (u["profile"].get("realName") or USERNAME)[:18]

    langs    = sorted(u.get("languageProblemCount") or [], key=lambda x: x["problemsSolved"], reverse=True)[:4]
    badges   = (u.get("badges") or [])[:3]

    cr      = round(co["rating"])           if co else 0
    c_rank  = co["globalRanking"]           if co else 0
    c_tot   = co["totalParticipants"]       if co else 0
    c_pct   = round(co["topPercentage"], 1) if co else 0
    c_att   = co["attendedContestsCount"]   if co else 0
    c_badge = co["badge"]["name"]           if co and co.get("badge") else ""
    hi_rat  = int(max([h["rating"] for h in hi if h.get("attended")] or [0]))

    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    W, H, C1, P = 860, 560, 200, 16

    cx, cy, R = C1+P+52, 220, 42
    ep = easy / max(e_t, 1); mp = med / max(m_t, 1); hp = hard / max(h_t, 1)
    ms = ep*360; hs = (ep+mp)*360

    b_n = len(badges)
    b_rows = math.ceil(b_n/2)
    lang_y0 = 318 + b_rows*24

    badge_svgs = "".join([
        f'<rect x="{16+(i%2)*82}" y="{292+(i//2)*24}" width="76" height="18" rx="4" fill="#1e2d3d"/>'
        f'<text x="{54+(i%2)*82}" y="{304+(i//2)*24}" text-anchor="middle" fill="#FFA116" font-size="9" font-family="monospace">{b["displayName"][:10]}</text>'
        for i, b in enumerate(badges)
    ])

    lang_svgs = "".join([
        f'<text x="16" y="{lang_y0+i*20}" fill="#9ca3af" font-size="10" font-family="monospace">{l["languageName"][:12]}</text>'
        f'<rect x="16" y="{lang_y0+3+i*20}" width="120" height="5" rx="2" fill="#1e2d3d"/>'
        f'<rect x="16" y="{lang_y0+3+i*20}" width="{int(l["problemsSolved"]/max(langs[0]["problemsSolved"],1)*120)}" height="5" rx="2" fill="#FFA116"/>'
        f'<text x="{C1-16}" y="{lang_y0+i*20}" text-anchor="end" fill="#6b7280" font-size="10" font-family="monospace">{l["problemsSolved"]}</text>'
        for i, l in enumerate(langs)
    ])

    div_y = 300 + b_rows*24 + 4

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img">
<title>LeetCode Profile — {name}</title>
<rect width="{W}" height="{H}" rx="12" fill="#0d1117"/>
<rect width="{C1}" height="{H}" rx="12" fill="#0f1923"/>
<rect x="{C1-1}" width="1" height="{H}" fill="#1e2d3d"/>

<circle cx="100" cy="56" r="32" fill="#1e2d3d"/>
<text x="100" y="63" text-anchor="middle" fill="#FFA116" font-size="22" font-weight="700" font-family="monospace">BK</text>
<text x="100" y="105" text-anchor="middle" fill="#e5e7eb" font-size="13" font-weight="600" font-family="monospace">{name}</text>
<text x="100" y="120" text-anchor="middle" fill="#9ca3af" font-size="11" font-family="monospace">{USERNAME}</text>

<line x1="12" y1="132" x2="{C1-12}" y2="132" stroke="#1e2d3d" stroke-width="1"/>
<text x="100" y="152" text-anchor="middle" fill="#9ca3af" font-size="11" font-family="monospace">Rank</text>
<text x="100" y="168" text-anchor="middle" fill="#FFA116" font-size="14" font-weight="700" font-family="monospace">#{ranking:,}</text>

<line x1="12" y1="178" x2="{C1-12}" y2="178" stroke="#1e2d3d" stroke-width="1"/>
<text x="16" y="198" fill="#6b7280" font-size="10" font-family="monospace" letter-spacing="0.5">COMMUNITY STATS</text>
<text x="16" y="216" fill="#9ca3af" font-size="11" font-family="monospace">Reputation</text>
<text x="{C1-16}" y="216" text-anchor="end" fill="#e5e7eb" font-size="11" font-family="monospace">{rep}</text>
<text x="16" y="234" fill="#9ca3af" font-size="11" font-family="monospace">Active Days</text>
<text x="{C1-16}" y="234" text-anchor="end" fill="#e5e7eb" font-size="11" font-family="monospace">{act_days}</text>
<text x="16" y="252" fill="#9ca3af" font-size="11" font-family="monospace">Max Streak</text>
<text x="{C1-16}" y="252" text-anchor="end" fill="#e5e7eb" font-size="11" font-family="monospace">{streak}</text>

<line x1="12" y1="262" x2="{C1-12}" y2="262" stroke="#1e2d3d" stroke-width="1"/>
<text x="16" y="280" fill="#6b7280" font-size="10" font-family="monospace" letter-spacing="0.5">BADGES ({b_n})</text>
{badge_svgs}

<line x1="12" y1="{div_y}" x2="{C1-12}" y2="{div_y}" stroke="#1e2d3d" stroke-width="1"/>
<text x="16" y="{div_y+18}" fill="#6b7280" font-size="10" font-family="monospace" letter-spacing="0.5">LANGUAGES</text>
{lang_svgs}

<text x="100" y="{H-8}" text-anchor="middle" fill="#374151" font-size="9" font-family="monospace">Updated {updated}</text>

<!-- MAIN PANEL -->
<text x="{C1+P}" y="30" fill="#9ca3af" font-size="11" font-family="monospace">PROBLEMS SOLVED</text>
<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="#1e2d3d" stroke-width="10"/>
<path d="{arc(cx,cy,R,ep)}" fill="none" stroke="#00b8a3" stroke-width="10" stroke-linecap="round"/>
<path d="{arc(cx,cy,R,mp)}" fill="none" stroke="#FFC01E" stroke-width="10" stroke-linecap="round" transform="rotate({ms:.1f} {cx} {cy})"/>
<path d="{arc(cx,cy,R,hp)}" fill="none" stroke="#EF4743" stroke-width="10" stroke-linecap="round" transform="rotate({hs:.1f} {cx} {cy})"/>
<text x="{cx}" y="{cy+5}" text-anchor="middle" fill="#e5e7eb" font-size="16" font-weight="700" font-family="monospace">{tot}</text>
<text x="{cx}" y="{cy+18}" text-anchor="middle" fill="#6b7280" font-size="9" font-family="monospace">Solved</text>

<rect x="{C1+P+110}" y="185" width="4" height="4" rx="1" fill="#00b8a3"/>
<text x="{C1+P+118}" y="190" fill="#9ca3af" font-size="11" font-family="monospace">Easy</text>
<text x="{C1+P+200}" y="190" fill="#e5e7eb" font-size="11" font-family="monospace">{easy} / {e_t}</text>
<rect x="{C1+P+110}" y="207" width="4" height="4" rx="1" fill="#FFC01E"/>
<text x="{C1+P+118}" y="212" fill="#9ca3af" font-size="11" font-family="monospace">Medium</text>
<text x="{C1+P+200}" y="212" fill="#e5e7eb" font-size="11" font-family="monospace">{med} / {m_t}</text>
<rect x="{C1+P+110}" y="229" width="4" height="4" rx="1" fill="#EF4743"/>
<text x="{C1+P+118}" y="234" fill="#9ca3af" font-size="11" font-family="monospace">Hard</text>
<text x="{C1+P+200}" y="234" fill="#e5e7eb" font-size="11" font-family="monospace">{hard} / {h_t}</text>

<line x1="{C1+P+232}" y1="155" x2="{C1+P+232}" y2="260" stroke="#1e2d3d" stroke-width="1"/>

<text x="{C1+P+245}" y="158" fill="#FFA116" font-size="22" font-weight="700" font-family="monospace">{cr}</text>
<text x="{C1+P+245}" y="172" fill="#9ca3af" font-size="10" font-family="monospace">CONTEST RATING</text>
<text x="{C1+P+390}" y="158" fill="#e5e7eb" font-size="18" font-weight="600" font-family="monospace">{hi_rat}</text>
<text x="{C1+P+390}" y="172" fill="#9ca3af" font-size="10" font-family="monospace">HIGHEST</text>
<text x="{C1+P+510}" y="158" fill="#e5e7eb" font-size="18" font-weight="600" font-family="monospace">{c_pct}%</text>
<text x="{C1+P+510}" y="172" fill="#9ca3af" font-size="10" font-family="monospace">TOP</text>

{sparkline(hi, C1+P+245, 180, w=360, h=70)}

<text x="{C1+P+245}" y="264" fill="#6b7280" font-size="10" font-family="monospace">Global: #{c_rank:,} / {c_tot:,}  ·  Contests: {c_att}{"  ·  " + c_badge if c_badge else ""}</text>

<line x1="{C1+P}" y1="274" x2="{W-P}" y2="274" stroke="#1e2d3d" stroke-width="1"/>
<text x="{C1+P}" y="294" fill="#9ca3af" font-size="11" font-family="monospace">ACTIVITY · Last 26 Weeks</text>
<text x="{W-P}" y="294" text-anchor="end" fill="#6b7280" font-size="10" font-family="monospace">Active: {act_days} days  ·  Streak: {streak}</text>

{heatmap(cal_str, C1+P, 302, weeks=26)}

<text x="{C1+P}" y="{H-10}" fill="#374151" font-size="9" font-family="monospace">Less</text>
{"".join([f'<rect x="{C1+P+28+i*16}" y="{H-20}" width="12" height="12" rx="2" fill="{c}"/>' for i,c in enumerate(["#1e2d3d","#0e4429","#006d32","#26a641","#39d353"])])}
<text x="{C1+P+28+5*16+4}" y="{H-10}" fill="#374151" font-size="9" font-family="monospace">More</text>
</svg>'''

def update_readme(readme):
    with open(readme) as f: content = f.read()
    img = '<p align="center">\n  <img src="assets/leetcode-profile.svg" alt="LeetCode Profile" width="100%"/>\n</p>'
    new = re.sub(r'<!-- LEETCODE_STATS_START -->.*?<!-- LEETCODE_STATS_END -->',
                 f'<!-- LEETCODE_STATS_START -->\n{img}\n<!-- LEETCODE_STATS_END -->', content, flags=re.DOTALL)
    if new == content:
        print("WARNING: markers not found in README"); return
    with open(readme, "w") as f: f.write(new)
    print("README updated")

if __name__ == "__main__":
    print(f"Fetching @{USERNAME}...")
    data = fetch(USERNAME)
    svg  = generate_svg(data)
    os.makedirs(os.path.dirname(SVG_PATH), exist_ok=True)
    with open(SVG_PATH, "w") as f: f.write(svg)
    print(f"SVG saved → {SVG_PATH}")
    update_readme(README)
