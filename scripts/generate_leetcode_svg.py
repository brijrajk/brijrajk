#!/usr/bin/env python3
"""
Generates a LeetCode profile SVG that closely matches the real LeetCode UI.
Saves to assets/leetcode-profile.svg and updates README.md markers.
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
    profile { ranking reputation realName company }
    submitStats: submitStatsGlobal {
      acSubmissionNum { difficulty count submissions }
    }
    userCalendar(year: 2025) { submissionCalendar totalActiveDays streak }
    badges { id displayName icon }
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
        "User-Agent": "Mozilla/5.0",
    }, method="POST")
    try:
        with urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except URLError as e:
        print(f"ERROR: {e}"); sys.exit(1)

def donut_arc(cx, cy, r, start_pct, end_pct, color, sw=14):
    """Draw a donut arc segment from start_pct to end_pct of full circle."""
    if end_pct - start_pct <= 0:
        return ""
    if end_pct - start_pct >= 1:
        end_pct = start_pct + 0.9999
    
    def pt(pct):
        a = pct * 2 * math.pi - math.pi/2
        return cx + r * math.cos(a), cy + r * math.sin(a)
    
    x1, y1 = pt(start_pct)
    x2, y2 = pt(end_pct)
    large = 1 if (end_pct - start_pct) > 0.5 else 0
    return f'<path d="M {x1:.2f} {y1:.2f} A {r} {r} 0 {large} 1 {x2:.2f} {y2:.2f}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round"/>'

def heatmap_cells(cal_str, x0, y0, weeks=52):
    cal = json.loads(cal_str or "{}")
    today = datetime.now(timezone.utc).date()
    # align to Sunday
    days_since_sunday = (today.weekday() + 1) % 7
    start = today - timedelta(days=days_since_sunday + (weeks-1)*7)
    
    cells = []
    cs, gap = 10, 2
    step = cs + gap
    
    for w in range(weeks):
        for d in range(7):
            day = start + timedelta(weeks=w, days=d)
            if day > today:
                continue
            ts = int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp())
            n  = cal.get(str(ts), 0)
            col = "#1e2a1e" if n == 0 else "#0e4429" if n <= 2 else "#006d32" if n <= 5 else "#26a641" if n <= 9 else "#39d353"
            cx = x0 + w * step
            cy = y0 + d * step
            cells.append(f'<rect x="{cx}" y="{cy}" width="{cs}" height="{cs}" rx="2" fill="{col}"/>')
    
    # Month labels
    months = []
    for w in range(0, weeks, 4):
        day = start + timedelta(weeks=w)
        label = day.strftime("%b")
        mx = x0 + w * step
        months.append(f'<text x="{mx}" y="{y0 - 4}" fill="#4d5e6e" font-size="10" font-family="sans-serif">{label}</text>')
    
    return "\n  ".join(cells + months)

def sparkline(history, x0, y0, w, h):
    pts = [p for p in history if p.get("attended")]
    if len(pts) < 2:
        return ""
    ratings = [p["rating"] for p in pts]
    mn, mx  = min(ratings), max(ratings)
    span    = mx - mn or 1
    n       = len(ratings)
    
    coords = []
    for i, r in enumerate(ratings):
        px = x0 + i * w / (n - 1)
        py = y0 + h - (r - mn) / span * h
        coords.append(f"{px:.1f},{py:.1f}")
    
    # Filled area under line
    area_pts = f"{x0:.1f},{y0+h:.1f} " + " ".join(coords) + f" {x0 + w:.1f},{y0+h:.1f}"
    
    last_x, last_y = coords[-1].split(",")
    hi_i = ratings.index(mx)
    hi_x = x0 + hi_i * w / (n - 1)
    hi_y = y0 + h - (mx - mn) / span * h

    year_start = pts[0]["contest"]["startTime"] if pts else 0
    year_end   = pts[-1]["contest"]["startTime"] if pts else 0
    def yr(ts): return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y")

    return (
        f'<polygon points="{area_pts}" fill="#FFA116" fill-opacity="0.08"/>'
        f'<polyline points="{" ".join(coords)}" fill="none" stroke="#FFA116" stroke-width="1.5" stroke-linejoin="round"/>'
        f'<circle cx="{last_x}" cy="{last_y}" r="4" fill="#FFA116"/>'
        f'<text x="{float(last_x)+6}" y="{float(last_y)+4}" fill="#FFA116" font-size="11" font-family="sans-serif" font-weight="600">{int(ratings[-1])}</text>'
        f'<circle cx="{hi_x:.1f}" cy="{hi_y:.1f}" r="3" fill="white" fill-opacity="0.8"/>'
        f'<text x="{x0}" y="{y0+h+14}" fill="#4d5e6e" font-size="10" font-family="sans-serif">{yr(year_start)}</text>'
        f'<text x="{x0+w}" y="{y0+h+14}" fill="#4d5e6e" font-size="10" font-family="sans-serif" text-anchor="end">{yr(year_end)}</text>'
    )

def generate_svg(data):
    u  = data["data"]["matchedUser"]
    co = data["data"]["userContestRanking"]
    hi = data["data"].get("userContestRankingHistory", [])

    st     = {s["difficulty"]: s for s in u["submitStats"]["acSubmissionNum"]}
    total  = st.get("All",    {}).get("count", 0)
    easy   = st.get("Easy",   {}).get("count", 0)
    med    = st.get("Medium", {}).get("count", 0)
    hard   = st.get("Hard",   {}).get("count", 0)
    easy_t = st.get("Easy",   {}).get("submissions", 949)
    med_t  = st.get("Medium", {}).get("submissions", 2066)
    hard_t = st.get("Hard",   {}).get("submissions", 942)
    total_t = easy_t + med_t + hard_t

    cal       = u.get("userCalendar") or {}
    cal_str   = cal.get("submissionCalendar", "{}")
    act_days  = cal.get("totalActiveDays", 0)
    streak    = cal.get("streak", 0)
    ranking   = u["profile"]["ranking"]
    rep       = u["profile"].get("reputation", 0)
    name      = (u["profile"].get("realName") or USERNAME)

    langs  = sorted(u.get("languageProblemCount") or [], key=lambda x: x["problemsSolved"], reverse=True)[:4]
    badges = (u.get("badges") or [])[:2]

    cr     = round(co["rating"])           if co else 0
    c_rank = co["globalRanking"]           if co else 0
    c_tot  = co["totalParticipants"]       if co else 0
    c_pct  = round(co["topPercentage"], 1) if co else 0
    c_att  = co["attendedContestsCount"]   if co else 0
    hi_rat = int(max([h["rating"] for h in hi if h.get("attended")] or [0]))
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    W, H = 900, 620
    # Layout zones
    SB_W  = 210   # sidebar width
    PAD   = 18

    # --- Donut ---
    dcx, dcy, dr = SB_W + PAD + 80, PAD + 100, 58
    ep = easy / max(easy_t, 1)
    mp = med  / max(med_t,  1)
    hp = hard / max(hard_t, 1)
    # stack arcs: easy starts at 0, med follows, hard follows
    easy_end = easy / max(total_t, 1)
    med_end  = easy_end + med / max(total_t, 1)
    hard_end = med_end + hard / max(total_t, 1)

    donut_bg   = f'<circle cx="{dcx}" cy="{dcy}" r="{dr}" fill="none" stroke="#2d3748" stroke-width="14"/>'
    arc_easy   = donut_arc(dcx, dcy, dr, 0,        easy_end, "#00b8a3")
    arc_med    = donut_arc(dcx, dcy, dr, easy_end, med_end,  "#ffc01e")
    arc_hard   = donut_arc(dcx, dcy, dr, med_end,  hard_end, "#ef4743")

    # --- Sidebar lang bars ---
    max_lang = langs[0]["problemsSolved"] if langs else 1
    lang_svg = ""
    for i, l in enumerate(langs):
        ly = 360 + i * 30
        bw = int(l["problemsSolved"] / max_lang * (SB_W - 32))
        lang_svg += (
            f'<text x="16" y="{ly}" fill="#8b9cb0" font-size="11" font-family="sans-serif">{l["languageName"]}</text>'
            f'<text x="{SB_W-16}" y="{ly}" text-anchor="end" fill="#c9d1d9" font-size="11" font-family="sans-serif">{l["problemsSolved"]}</text>'
            f'<rect x="16" y="{ly+4}" width="{SB_W-32}" height="5" rx="2.5" fill="#1e2d3d"/>'
            f'<rect x="16" y="{ly+4}" width="{bw}" height="5" rx="2.5" fill="#FFA116"/>'
        )

    # --- Badge boxes ---
    badge_svg = ""
    badge_colors = ["#1a3a2a", "#1a2a3a"]
    for i, b in enumerate(badges):
        bx = 16 + i * (SB_W//2 - 4)
        badge_svg += (
            f'<rect x="{bx}" y="280" width="{SB_W//2 - 12}" height="50" rx="6" fill="{badge_colors[i % 2]}" stroke="#2d4a3a" stroke-width="1"/>'
            f'<text x="{bx + (SB_W//2-12)//2}" y="300" text-anchor="middle" fill="#FFA116" font-size="16">🏅</text>'
            f'<text x="{bx + (SB_W//2-12)//2}" y="322" text-anchor="middle" fill="#8b9cb0" font-size="8" font-family="sans-serif">{b["displayName"][:12]}</text>'
        )

    # --- Contest sparkline ---
    spark = sparkline(hi, SB_W + PAD + 240, PAD + 40, W - SB_W - PAD*2 - 240, 90)

    # --- Heatmap (52 weeks) ---
    hm_y = 440
    hm   = heatmap_cells(cal_str, SB_W + PAD, hm_y, weeks=52)
    hm_w = 52 * 12

    # --- Difficulty stat rows ---
    def diff_row(label, solved, total, color, y):
        bar_full = 220
        bar_fill = int(solved / max(total, 1) * bar_full)
        return (
            f'<rect x="{dcx+dr+20}" y="{y-10}" width="8" height="8" rx="2" fill="{color}"/>'
            f'<text x="{dcx+dr+34}" y="{y}" fill="#c9d1d9" font-size="12" font-family="sans-serif">{label}</text>'
            f'<text x="{dcx+dr+34+55}" y="{y}" fill="#c9d1d9" font-size="12" font-family="sans-serif" font-weight="600">{solved}</text>'
            f'<text x="{dcx+dr+34+80}" y="{y}" fill="#4d5e6e" font-size="11" font-family="sans-serif">/ {total}</text>'
            f'<rect x="{dcx+dr+34}" y="{y+4}" width="{bar_full}" height="4" rx="2" fill="#1e2d3d"/>'
            f'<rect x="{dcx+dr+34}" y="{y+4}" width="{bar_fill}" height="4" rx="2" fill="{color}"/>'
        )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<title>LeetCode Profile — {name}</title>

<!-- Background -->
<rect width="{W}" height="{H}" rx="12" fill="#1a1a2e"/>

<!-- Sidebar bg -->
<rect width="{SB_W}" height="{H}" rx="12" fill="#16213e"/>
<rect x="{SB_W-1}" width="1" height="{H}" fill="#2d3748"/>

<!-- Avatar -->
<circle cx="{SB_W//2}" cy="52" r="36" fill="#0f3460"/>
<text x="{SB_W//2}" y="60" text-anchor="middle" fill="#FFA116" font-size="24" font-weight="700" font-family="sans-serif">BK</text>

<!-- Name -->
<text x="{SB_W//2}" y="108" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="600" font-family="sans-serif">{name}</text>
<text x="{SB_W//2}" y="124" text-anchor="middle" fill="#8b9cb0" font-size="11" font-family="sans-serif">{USERNAME}</text>

<!-- Rank -->
<text x="{SB_W//2}" y="148" text-anchor="middle" fill="#8b9cb0" font-size="11" font-family="sans-serif">Rank</text>
<text x="{SB_W//2}" y="166" text-anchor="middle" fill="#FFA116" font-size="15" font-weight="700" font-family="sans-serif">#{ranking:,}</text>

<line x1="12" y1="176" x2="{SB_W-12}" y2="176" stroke="#2d3748" stroke-width="1"/>

<!-- Community Stats -->
<text x="16" y="196" fill="#4d5e6e" font-size="10" font-family="sans-serif" letter-spacing="1">COMMUNITY STATS</text>
<text x="16" y="214" fill="#8b9cb0" font-size="11" font-family="sans-serif">Reputation</text>
<text x="{SB_W-16}" y="214" text-anchor="end" fill="#c9d1d9" font-size="11" font-family="sans-serif">{rep}</text>
<text x="16" y="232" fill="#8b9cb0" font-size="11" font-family="sans-serif">Active Days</text>
<text x="{SB_W-16}" y="232" text-anchor="end" fill="#c9d1d9" font-size="11" font-family="sans-serif">{act_days}</text>
<text x="16" y="250" fill="#8b9cb0" font-size="11" font-family="sans-serif">Max Streak</text>
<text x="{SB_W-16}" y="250" text-anchor="end" fill="#c9d1d9" font-size="11" font-family="sans-serif">{streak}</text>

<line x1="12" y1="262" x2="{SB_W-12}" y2="262" stroke="#2d3748" stroke-width="1"/>

<!-- Badges -->
<text x="16" y="278" fill="#4d5e6e" font-size="10" font-family="sans-serif" letter-spacing="1">BADGES ({len(badges)})</text>
{badge_svg}

<line x1="12" y1="342" x2="{SB_W-12}" y2="342" stroke="#2d3748" stroke-width="1"/>

<!-- Languages -->
<text x="16" y="358" fill="#4d5e6e" font-size="10" font-family="sans-serif" letter-spacing="1">LANGUAGES</text>
{lang_svg}

<!-- Updated timestamp -->
<text x="{SB_W//2}" y="{H-8}" text-anchor="middle" fill="#2d3748" font-size="9" font-family="sans-serif">Updated {updated}</text>

<!-- ===== MAIN PANEL ===== -->

<!-- Contest rating section top-right -->
<text x="{SB_W+PAD}" y="{PAD+18}" fill="#8b9cb0" font-size="11" font-family="sans-serif">Contest Rating</text>
<text x="{SB_W+PAD}" y="{PAD+40}" fill="#e2e8f0" font-size="26" font-weight="700" font-family="sans-serif">{cr}</text>

<text x="{SB_W+PAD+100}" y="{PAD+18}" fill="#8b9cb0" font-size="11" font-family="sans-serif">Global Ranking</text>
<text x="{SB_W+PAD+100}" y="{PAD+40}" fill="#e2e8f0" font-size="15" font-family="sans-serif">{c_rank:,}/{c_tot:,}</text>

<text x="{SB_W+PAD+240}" y="{PAD+18}" fill="#8b9cb0" font-size="11" font-family="sans-serif">Attended</text>
<text x="{SB_W+PAD+240}" y="{PAD+40}" fill="#e2e8f0" font-size="15" font-family="sans-serif">{c_att}</text>

<text x="{W-PAD}" y="{PAD+18}" text-anchor="end" fill="#8b9cb0" font-size="11" font-family="sans-serif">Top</text>
<text x="{W-PAD}" y="{PAD+40}" text-anchor="end" fill="#e2e8f0" font-size="22" font-weight="700" font-family="sans-serif">{c_pct}%</text>

<!-- Sparkline -->
{spark}

<!-- Divider -->
<line x1="{SB_W+PAD}" y1="160" x2="{W-PAD}" y2="160" stroke="#2d3748" stroke-width="1"/>

<!-- Donut chart -->
{donut_bg}
{arc_easy}
{arc_med}
{arc_hard}
<text x="{dcx}" y="{dcy-8}" text-anchor="middle" fill="#e2e8f0" font-size="22" font-weight="700" font-family="sans-serif">{total}</text>
<text x="{dcx}" y="{dcy+10}" text-anchor="middle" fill="#4d5e6e" font-size="11" font-family="sans-serif">/ {total_t}</text>
<text x="{dcx}" y="{dcy+26}" text-anchor="middle" fill="#00b8a3" font-size="10" font-family="sans-serif">✓ Solved</text>

<!-- Difficulty rows -->
{diff_row("Easy",   easy, easy_t, "#00b8a3", dcy - 40)}
{diff_row("Med.",   med,  med_t,  "#ffc01e", dcy)}
{diff_row("Hard",   hard, hard_t, "#ef4743", dcy + 40)}

<!-- Badges section right of donut -->
<text x="{W - 200}" y="178" fill="#8b9cb0" font-size="12" font-family="sans-serif" font-weight="600">Badges</text>
<text x="{W - 200}" y="196" fill="#e2e8f0" font-size="22" font-weight="700" font-family="sans-serif">{len(badges)}</text>
<text x="{W - 50}" y="178" text-anchor="end" fill="#4d5e6e" font-size="11" font-family="sans-serif">→</text>
{''.join([f'<rect x="{W-200+i*66}" y="205" width="60" height="60" rx="8" fill="#0f3460" stroke="#2d3748" stroke-width="1"/><text x="{W-200+i*66+30}" y="242" text-anchor="middle" fill="#FFA116" font-size="24">🏅</text><text x="{W-200+i*66+30}" y="258" text-anchor="middle" fill="#4d5e6e" font-size="8" font-family="sans-serif">{b["displayName"][:10]}</text>' for i,b in enumerate(badges)])}
<text x="{W-PAD}" y="280" text-anchor="end" fill="#8b9cb0" font-size="10" font-family="sans-serif">Most Recent: {badges[0]["displayName"] if badges else ""}</text>

<!-- Divider -->
<line x1="{SB_W+PAD}" y1="295" x2="{W-PAD}" y2="295" stroke="#2d3748" stroke-width="1"/>

<!-- Heatmap section -->
<text x="{SB_W+PAD}" y="315" fill="#8b9cb0" font-size="12" font-family="sans-serif" font-weight="600">{act_days * 7 + streak} submissions in the past one year</text>
<text x="{W-PAD}" y="315" text-anchor="end" fill="#4d5e6e" font-size="10" font-family="sans-serif">Total active days: {act_days}  ·  Max streak: {streak}</text>

{hm}

<!-- Heatmap legend -->
<text x="{SB_W+PAD}" y="{hm_y + 7*12 + 18}" fill="#4d5e6e" font-size="10" font-family="sans-serif">Less</text>
{''.join([f'<rect x="{SB_W+PAD+32+i*14}" y="{hm_y + 7*12 + 6}" width="11" height="11" rx="2" fill="{c}"/>' for i,c in enumerate(["#1e2a1e","#0e4429","#006d32","#26a641","#39d353"])])}
<text x="{SB_W+PAD+32+5*14+4}" y="{hm_y + 7*12 + 18}" fill="#4d5e6e" font-size="10" font-family="sans-serif">More</text>

</svg>'''

    return svg

def update_readme(readme):
    with open(readme) as f: content = f.read()
    img = '<p align="center">\n  <img src="assets/leetcode-profile.svg" alt="LeetCode Profile" width="100%"/>\n</p>'
    new = re.sub(r'<!-- LEETCODE_STATS_START -->.*?<!-- LEETCODE_STATS_END -->',
                 f'<!-- LEETCODE_STATS_START -->\n{img}\n<!-- LEETCODE_STATS_END -->', content, flags=re.DOTALL)
    if new == content:
        print("WARNING: markers not found"); return
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
