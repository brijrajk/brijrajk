#!/usr/bin/env python3
"""
Generates a LeetCode profile SVG with hardcoded pixel layout.
Canvas: 900 x 620
Sidebar: 0-220
Main panel: 220-900

Sections (main panel):
  Row 1 (y=0..130):   Contest stats + sparkline
  Divider y=135
  Row 2 (y=145..290): Donut + Diff rows + Badges
  Divider y=295
  Row 3 (y=300..610): Heatmap
"""

import json, math, os, re, sys
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError

USERNAME = "brij_raj"
SVG_PATH = "assets/leetcode-profile.svg"
README   = "README.md"
GRAPHQL  = "https://leetcode.com/graphql"

QUERY = """
query getUserStats($username: String!) {
  matchedUser(username: $username) {
    username
    profile { ranking reputation realName }
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
    attended rating contest { title startTime }
  }
}
"""

def fetch(username):
    payload = json.dumps({"query": QUERY, "variables": {"username": username}}).encode()
    req = Request(GRAPHQL, data=payload, headers={
        "Content-Type": "application/json",
        "Referer": "https://leetcode.com",
        "User-Agent": "Mozilla/5.0",
    }, method="POST")
    try:
        with urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except URLError as e:
        print(f"ERROR: {e}"); sys.exit(1)

def arc(cx, cy, r, s, e, color, sw=11):
    if e <= s: return ""
    if e - s >= 1: e = s + 0.9999
    def pt(p):
        a = p * 2 * math.pi - math.pi/2
        return cx + r*math.cos(a), cy + r*math.sin(a)
    x1,y1 = pt(s); x2,y2 = pt(e)
    lg = 1 if e-s > 0.5 else 0
    return f'<path d="M{x1:.1f},{y1:.1f} A{r},{r} 0 {lg},1 {x2:.1f},{y2:.1f}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round"/>'

def heatmap(cal_str, x0, y0, weeks=52):
    cal = json.loads(cal_str or "{}")
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=(today.weekday()+1)%7 + (weeks-1)*7)
    cs, gap = 10, 2; step = cs+gap
    out = []; seen = set()
    for w in range(weeks):
        for d in range(7):
            day = start + timedelta(weeks=w, days=d)
            if day > today: continue
            ts = int(datetime(day.year,day.month,day.day,tzinfo=timezone.utc).timestamp())
            n  = cal.get(str(ts), 0)
            c  = "#1a2a1a" if n==0 else "#0e4429" if n<=2 else "#006d32" if n<=5 else "#26a641" if n<=9 else "#39d353"
            out.append(f'<rect x="{x0+w*step}" y="{y0+d*step}" width="{cs}" height="{cs}" rx="2" fill="{c}"/>')
            if d==0:
                m = day.strftime("%b")
                if m not in seen:
                    seen.add(m)
                    out.append(f'<text x="{x0+w*step}" y="{y0-5}" fill="#4d5e6e" font-size="10" font-family="sans-serif">{m}</text>')
    return "\n  ".join(out)

def sparkline(history, x0, y0, w, h):
    pts = [p for p in history if p.get("attended")]
    if len(pts) < 2: return ""
    ratings = [p["rating"] for p in pts]
    mn,mx = min(ratings),max(ratings); span = mx-mn or 1; n = len(ratings)
    coords = [(x0 + i*w/(n-1), y0+h-(r-mn)/span*h) for i,r in enumerate(ratings)]
    poly  = " ".join(f"{x:.1f},{y:.1f}" for x,y in coords)
    area  = f"{x0:.1f},{y0+h:.1f} {poly} {x0+w:.1f},{y0+h:.1f}"
    lx,ly = coords[-1]
    yr_s  = datetime.fromtimestamp(pts[0]["contest"]["startTime"],  tz=timezone.utc).strftime("%Y")
    yr_e  = datetime.fromtimestamp(pts[-1]["contest"]["startTime"], tz=timezone.utc).strftime("%Y")
    return (
        f'<polygon points="{area}" fill="#FFA116" fill-opacity="0.1"/>'
        f'<polyline points="{poly}" fill="none" stroke="#FFA116" stroke-width="1.5" stroke-linejoin="round"/>'
        f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3.5" fill="#FFA116"/>'
        f'<text x="{lx+6:.1f}" y="{ly+4:.1f}" fill="#FFA116" font-size="10" font-family="sans-serif" font-weight="600">{int(ratings[-1])}</text>'
        f'<text x="{x0}" y="{y0+h+14}" fill="#4d5e6e" font-size="10" font-family="sans-serif">{yr_s}</text>'
        f'<text x="{x0+w}" y="{y0+h+14}" text-anchor="end" fill="#4d5e6e" font-size="10" font-family="sans-serif">{yr_e}</text>'
    )

def generate_svg(data):
    u  = data["data"]["matchedUser"]
    co = data["data"]["userContestRanking"]
    hi = data["data"].get("userContestRankingHistory", [])

    st     = {s["difficulty"]:s for s in u["submitStats"]["acSubmissionNum"]}
    total  = st.get("All",    {}).get("count", 0)
    easy   = st.get("Easy",   {}).get("count", 0)
    med    = st.get("Medium", {}).get("count", 0)
    hard   = st.get("Hard",   {}).get("count", 0)
    # "submissions" = total problems available on LeetCode per difficulty
    # These are the denominators shown in LeetCode UI (e.g. 133/949)
    easy_t = st.get("Easy",   {}).get("submissions", 949)
    med_t  = st.get("Medium", {}).get("submissions", 2066)
    hard_t = st.get("Hard",   {}).get("submissions", 942)
    # Clamp to known minimums in case API returns lower counts
    easy_t = max(easy_t, easy)
    med_t  = max(med_t,  med)
    hard_t = max(hard_t, hard)
    sum_t  = easy_t + med_t + hard_t

    cal      = u.get("userCalendar") or {}
    cal_str  = cal.get("submissionCalendar", "{}")
    act_days = cal.get("totalActiveDays", 0)
    streak   = cal.get("streak", 0)
    ranking  = u["profile"]["ranking"]
    rep      = u["profile"].get("reputation", 0)
    name     = u["profile"].get("realName") or USERNAME

    langs  = sorted(u.get("languageProblemCount") or [], key=lambda x: x["problemsSolved"], reverse=True)[:4]
    badges = (u.get("badges") or [])[:2]

    cr     = round(co["rating"])           if co else 0
    c_rank = co["globalRanking"]           if co else 0
    c_tot  = co["totalParticipants"]       if co else 0
    c_pct  = round(co["topPercentage"], 1) if co else 0
    c_att  = co["attendedContestsCount"]   if co else 0
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Donut arcs — stacked by proportion of total problems
    e_end = easy / max(sum_t, 1)
    m_end = e_end + med / max(sum_t, 1)
    h_end = m_end + hard / max(sum_t, 1)

    # Sidebar language bars
    max_lang = langs[0]["problemsSolved"] if langs else 1
    lang_rows = ""
    for i, l in enumerate(langs):
        ly = 390 + i*30
        bw = int(l["problemsSolved"] / max_lang * 180)
        lang_rows += (
            f'<text x="16" y="{ly}" fill="#8b9cb0" font-size="11" font-family="sans-serif">{l["languageName"]}</text>'
            f'<text x="204" y="{ly}" text-anchor="end" fill="#c9d1d9" font-size="11" font-family="sans-serif">{l["problemsSolved"]}</text>'
            f'<rect x="16" y="{ly+4}" width="188" height="5" rx="2.5" fill="#2d3748"/>'
            f'<rect x="16" y="{ly+4}" width="{bw}" height="5" rx="2.5" fill="#FFA116"/>'
        )

    # Badge name word-wrap helper
    def badge_label(name, max_w=10):
        words = name.split(); l1 = ""; l2 = ""
        for w in words:
            if len(l1) + len(w) + (1 if l1 else 0) <= max_w: l1 = (l1+" "+w).strip()
            else: l2 = (l2+" "+w).strip()
        return l1, l2

    # Sidebar badge boxes
    sb_badges = ""
    for i, b in enumerate(badges):
        bx = 16 + i*96
        l1, l2 = badge_label(b["displayName"], 11)
        sb_badges += (
            f'<rect x="{bx}" y="296" width="84" height="64" rx="6" fill="#0f2d1a" stroke="#1a4a2a" stroke-width="1"/>'
            f'<text x="{bx+42}" y="318" text-anchor="middle" font-size="18">🏅</text>'
            f'<text x="{bx+42}" y="332" text-anchor="middle" fill="#6b7280" font-size="7.5" font-family="sans-serif">{l1}</text>'
            f'<text x="{bx+42}" y="342" text-anchor="middle" fill="#6b7280" font-size="7.5" font-family="sans-serif">{l2}</text>'
        )

    # Main panel badge boxes (right of diff rows, x=680)
    main_badges = ""
    for i, b in enumerate(badges):
        bx = 680 + i*76
        l1, l2 = badge_label(b["displayName"], 9)
        main_badges += (
            f'<rect x="{bx}" y="162" width="70" height="74" rx="8" fill="#0f2940" stroke="#1a3a5a" stroke-width="1"/>'
            f'<text x="{bx+35}" y="193" text-anchor="middle" font-size="22">🏅</text>'
            f'<text x="{bx+35}" y="208" text-anchor="middle" fill="#4d5e6e" font-size="7.5" font-family="sans-serif">{l1}</text>'
            f'<text x="{bx+35}" y="218" text-anchor="middle" fill="#4d5e6e" font-size="7.5" font-family="sans-serif">{l2}</text>'
        )

    # Difficulty rows — x=430, bars 200px wide
    def diff_row(label, solved, ttl, color, ry):
        bw = int(solved / max(ttl,1) * 200)
        return (
            f'<rect x="430" y="{ry-9}" width="7" height="7" rx="1.5" fill="{color}"/>'
            f'<text x="442" y="{ry}" fill="#c9d1d9" font-size="12" font-family="sans-serif">{label}</text>'
            f'<text x="498" y="{ry}" fill="#e2e8f0" font-size="12" font-weight="600" font-family="sans-serif">{solved}</text>'
            f'<text x="532" y="{ry}" fill="#4d5e6e" font-size="11" font-family="sans-serif">/ {ttl}</text>'
            f'<rect x="442" y="{ry+4}" width="200" height="4" rx="2" fill="#2d3748"/>'
            f'<rect x="442" y="{ry+4}" width="{bw}" height="4" rx="2" fill="{color}"/>'
        )

    hm  = heatmap(cal_str, 236, 330, weeks=52)
    sp  = sparkline(hi,     560, 55,  320, 70)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="620" viewBox="0 0 900 620">
<title>LeetCode Profile — {name}</title>

<!-- BG -->
<rect width="900" height="620" rx="12" fill="#1a1a2e"/>

<!-- Sidebar BG -->
<rect x="0" y="0" width="220" height="620" rx="12" fill="#16213e"/>
<rect x="219" y="0" width="1" height="620" fill="#2d3748"/>

<!-- Avatar -->
<circle cx="110" cy="50" r="34" fill="#0f3460"/>
<text x="110" y="59" text-anchor="middle" fill="#FFA116" font-size="22" font-weight="700" font-family="sans-serif">BK</text>

<!-- Name -->
<text x="110" y="103" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="600" font-family="sans-serif">{name}</text>
<text x="110" y="119" text-anchor="middle" fill="#8b9cb0" font-size="11" font-family="sans-serif">{USERNAME}</text>
<text x="110" y="138" text-anchor="middle" fill="#8b9cb0" font-size="11" font-family="sans-serif">Rank</text>
<text x="110" y="156" text-anchor="middle" fill="#FFA116" font-size="15" font-weight="700" font-family="sans-serif">#{ranking:,}</text>

<line x1="12" y1="166" x2="208" y2="166" stroke="#2d3748" stroke-width="1"/>

<!-- Community stats -->
<text x="16" y="184" fill="#4d5e6e" font-size="10" font-family="sans-serif" letter-spacing="1">COMMUNITY STATS</text>
<text x="16" y="202" fill="#8b9cb0" font-size="11" font-family="sans-serif">Reputation</text>
<text x="204" y="202" text-anchor="end" fill="#c9d1d9" font-size="11" font-family="sans-serif">{rep}</text>
<text x="16" y="220" fill="#8b9cb0" font-size="11" font-family="sans-serif">Active Days</text>
<text x="204" y="220" text-anchor="end" fill="#c9d1d9" font-size="11" font-family="sans-serif">{act_days}</text>
<text x="16" y="238" fill="#8b9cb0" font-size="11" font-family="sans-serif">Max Streak</text>
<text x="204" y="238" text-anchor="end" fill="#c9d1d9" font-size="11" font-family="sans-serif">{streak}</text>

<line x1="12" y1="250" x2="208" y2="250" stroke="#2d3748" stroke-width="1"/>

<!-- Sidebar badges -->
<text x="16" y="268" fill="#4d5e6e" font-size="10" font-family="sans-serif" letter-spacing="1">BADGES ({len(badges)})</text>
{sb_badges}

<line x1="12" y1="366" x2="208" y2="366" stroke="#2d3748" stroke-width="1"/>

<!-- Languages -->
<text x="16" y="384" fill="#4d5e6e" font-size="10" font-family="sans-serif" letter-spacing="1">LANGUAGES</text>
{lang_rows}

<!-- Updated -->
<text x="110" y="612" text-anchor="middle" fill="#2d3748" font-size="9" font-family="sans-serif">Updated {updated}</text>

<!-- ═══ MAIN PANEL ═══ -->

<!-- Row 1: Contest stats  y=0..130 -->
<!-- Contest Rating -->
<text x="236" y="18" fill="#8b9cb0" font-size="11" font-family="sans-serif">Contest Rating</text>
<text x="236" y="48" fill="#e2e8f0" font-size="28" font-weight="700" font-family="sans-serif">{cr}</text>

<!-- Global Ranking -->
<text x="350" y="18" fill="#8b9cb0" font-size="11" font-family="sans-serif">Global Ranking</text>
<text x="350" y="48" fill="#e2e8f0" font-size="15" font-family="sans-serif">{c_rank:,}/{c_tot:,}</text>

<!-- Attended -->
<text x="490" y="18" fill="#8b9cb0" font-size="11" font-family="sans-serif">Attended</text>
<text x="490" y="48" fill="#e2e8f0" font-size="15" font-family="sans-serif">{c_att}</text>

<!-- Top -->
<text x="884" y="18" text-anchor="end" fill="#8b9cb0" font-size="11" font-family="sans-serif">Top</text>
<text x="884" y="52" text-anchor="end" fill="#e2e8f0" font-size="26" font-weight="700" font-family="sans-serif">{c_pct}%</text>

<!-- Sparkline: x=560..880, y=55..125 (below contest numbers) -->
{sp}

<!-- Divider row1/row2 -->
<line x1="228" y1="135" x2="892" y2="135" stroke="#2d3748" stroke-width="1"/>

<!-- Row 2: Donut + Diff rows + Badges  y=145..290 -->

<!-- Donut: center (330, 215), r=52 -->
<circle cx="330" cy="215" r="52" fill="none" stroke="#2d3748" stroke-width="11"/>
{arc(330, 215, 52, 0,     e_end, "#00b8a3")}
{arc(330, 215, 52, e_end, m_end, "#ffc01e")}
{arc(330, 215, 52, m_end, h_end, "#ef4743")}
<text x="330" y="209" text-anchor="middle" fill="#e2e8f0" font-size="22" font-weight="700" font-family="sans-serif">{total}</text>
<text x="330" y="225" text-anchor="middle" fill="#4d5e6e" font-size="10" font-family="sans-serif">/ {sum_t}</text>
<text x="330" y="241" text-anchor="middle" fill="#00b8a3" font-size="10" font-family="sans-serif">✓ Solved</text>

<!-- Diff rows: x=430, y=180/215/250 -->
{diff_row("Easy", easy, easy_t, "#00b8a3", 185)}
{diff_row("Med.",  med,  med_t,  "#ffc01e", 220)}
{diff_row("Hard", hard, hard_t, "#ef4743", 255)}

<!-- Badges panel: x=680 -->
<text x="680" y="158" fill="#8b9cb0" font-size="12" font-weight="600" font-family="sans-serif">Badges  <tspan fill="#e2e8f0" font-size="16" font-weight="700">{len(badges)}</tspan></text>
<text x="880" y="158" text-anchor="end" fill="#4d5e6e" font-size="13" font-family="sans-serif">→</text>
{main_badges}
<text x="880" y="245" text-anchor="end" fill="#6b7280" font-size="10" font-family="sans-serif">Most Recent: {badges[0]["displayName"] if badges else ""}</text>

<!-- Divider row2/row3 -->
<line x1="228" y1="295" x2="892" y2="295" stroke="#2d3748" stroke-width="1"/>

<!-- Row 3: Heatmap  y=300..610 -->
<text x="236" y="314" fill="#c9d1d9" font-size="12" font-weight="600" font-family="sans-serif">Submissions — past year</text>
<text x="884" y="314" text-anchor="end" fill="#4d5e6e" font-size="10" font-family="sans-serif">Active days: {act_days}  ·  Streak: {streak}</text>

<!-- Heatmap cells: x=236, y=330 (month labels at y=325) -->
{hm}

<!-- Legend -->
<text x="236" y="610" fill="#4d5e6e" font-size="10" font-family="sans-serif">Less</text>
{''.join([f'<rect x="{272+i*14}" y="598" width="11" height="11" rx="2" fill="{c}"/>' for i,c in enumerate(["#1a2a1a","#0e4429","#006d32","#26a641","#39d353"])])}
<text x="{272+5*14+4}" y="610" fill="#4d5e6e" font-size="10" font-family="sans-serif">More</text>

</svg>'''

def update_readme(readme):
    with open(readme) as f: c = f.read()
    img = '<p align="center">\n  <img src="assets/leetcode-profile.svg" alt="LeetCode Profile" width="100%"/>\n</p>'
    new = re.sub(r'<!-- LEETCODE_STATS_START -->.*?<!-- LEETCODE_STATS_END -->',
                 f'<!-- LEETCODE_STATS_START -->\n{img}\n<!-- LEETCODE_STATS_END -->', c, flags=re.DOTALL)
    if new == c: print("WARNING: markers not found"); return
    with open(readme, "w") as f: f.write(new)
    print("README updated")

if __name__ == "__main__":
    print(f"Fetching @{USERNAME}...")
    data = fetch(USERNAME)
    svg  = generate_svg(data)
    os.makedirs(os.path.dirname(SVG_PATH), exist_ok=True)
    with open(SVG_PATH, "w") as f: f.write(svg)
    print(f"SVG → {SVG_PATH}")
    update_readme(README)
