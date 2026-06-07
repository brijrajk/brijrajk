#!/usr/bin/env python3
"""
Generates a LeetCode profile SVG matching the real LeetCode UI.
Layout:
  LEFT SIDEBAR  (0 to 220px):     avatar, rank, community stats, badges, languages
  TOP RIGHT     (220 to 900px):   contest rating + sparkline
  MID RIGHT:                      donut (left) + difficulty rows (center) + badges (right)
  BOTTOM:                         52-week heatmap
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

def donut_arc(cx, cy, r, start_pct, end_pct, color, sw=12):
    if end_pct <= start_pct: return ""
    if end_pct - start_pct >= 1: end_pct = start_pct + 0.9999
    def pt(pct):
        a = pct * 2 * math.pi - math.pi / 2
        return cx + r * math.cos(a), cy + r * math.sin(a)
    x1, y1 = pt(start_pct)
    x2, y2 = pt(end_pct)
    large = 1 if (end_pct - start_pct) > 0.5 else 0
    return f'<path d="M {x1:.2f} {y1:.2f} A {r} {r} 0 {large} 1 {x2:.2f} {y2:.2f}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round"/>'

def heatmap_svg(cal_str, x0, y0, weeks=52):
    cal = json.loads(cal_str or "{}")
    today = datetime.now(timezone.utc).date()
    days_since_sun = (today.weekday() + 1) % 7
    start = today - timedelta(days=days_since_sun + (weeks - 1) * 7)
    cs, gap = 10, 2
    step = cs + gap
    cells, month_labels, seen_months = [], [], set()
    for w in range(weeks):
        for d in range(7):
            day = start + timedelta(weeks=w, days=d)
            if day > today: continue
            ts  = int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp())
            n   = cal.get(str(ts), 0)
            col = "#1a2a1a" if n==0 else "#0e4429" if n<=2 else "#006d32" if n<=5 else "#26a641" if n<=9 else "#39d353"
            cells.append(f'<rect x="{x0+w*step}" y="{y0+d*step}" width="{cs}" height="{cs}" rx="2" fill="{col}"/>')
            if d == 0:
                m = day.strftime("%b")
                if m not in seen_months:
                    seen_months.add(m)
                    month_labels.append(f'<text x="{x0+w*step}" y="{y0-5}" fill="#4d5e6e" font-size="10" font-family="sans-serif">{m}</text>')
    return "\n  ".join(cells + month_labels)

def sparkline_svg(history, x0, y0, w, h):
    pts = [p for p in history if p.get("attended")]
    if len(pts) < 2: return ""
    ratings = [p["rating"] for p in pts]
    mn, mx  = min(ratings), max(ratings)
    span    = mx - mn or 1
    n       = len(ratings)
    coords  = []
    for i, r in enumerate(ratings):
        px = x0 + i * w / (n - 1)
        py = y0 + h - (r - mn) / span * h
        coords.append((px, py))
    poly   = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    area   = f"{x0:.1f},{y0+h:.1f} {poly} {x0+w:.1f},{y0+h:.1f}"
    lx, ly = coords[-1]
    yr_s   = datetime.fromtimestamp(pts[0]["contest"]["startTime"],  tz=timezone.utc).strftime("%Y")
    yr_e   = datetime.fromtimestamp(pts[-1]["contest"]["startTime"], tz=timezone.utc).strftime("%Y")
    return (
        f'<polygon points="{area}" fill="#FFA116" fill-opacity="0.1"/>'
        f'<polyline points="{poly}" fill="none" stroke="#FFA116" stroke-width="1.5" stroke-linejoin="round"/>'
        f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="4" fill="#FFA116"/>'
        f'<text x="{lx+6:.1f}" y="{ly+4:.1f}" fill="#FFA116" font-size="11" font-family="sans-serif" font-weight="600">{int(ratings[-1])}</text>'
        f'<text x="{x0}" y="{y0+h+14}" fill="#4d5e6e" font-size="10" font-family="sans-serif">{yr_s}</text>'
        f'<text x="{x0+w}" y="{y0+h+14}" text-anchor="end" fill="#4d5e6e" font-size="10" font-family="sans-serif">{yr_e}</text>'
    )

def generate_svg(data):
    u  = data["data"]["matchedUser"]
    co = data["data"]["userContestRanking"]
    hi = data["data"].get("userContestRankingHistory", [])

    st      = {s["difficulty"]: s for s in u["submitStats"]["acSubmissionNum"]}
    total   = st.get("All",    {}).get("count", 0)
    easy    = st.get("Easy",   {}).get("count", 0)
    med     = st.get("Medium", {}).get("count", 0)
    hard    = st.get("Hard",   {}).get("count", 0)
    easy_t  = st.get("Easy",   {}).get("submissions", 949)
    med_t   = st.get("Medium", {}).get("submissions", 2066)
    hard_t  = st.get("Hard",   {}).get("submissions", 942)
    sum_t   = easy_t + med_t + hard_t

    cal      = u.get("userCalendar") or {}
    cal_str  = cal.get("submissionCalendar", "{}")
    act_days = cal.get("totalActiveDays", 0)
    streak   = cal.get("streak", 0)
    ranking  = u["profile"]["ranking"]
    rep      = u["profile"].get("reputation", 0)
    name     = (u["profile"].get("realName") or USERNAME)

    langs    = sorted(u.get("languageProblemCount") or [], key=lambda x: x["problemsSolved"], reverse=True)[:4]
    badges   = (u.get("badges") or [])[:2]

    cr      = round(co["rating"])           if co else 0
    c_rank  = co["globalRanking"]           if co else 0
    c_tot   = co["totalParticipants"]       if co else 0
    c_pct   = round(co["topPercentage"], 1) if co else 0
    c_att   = co["attendedContestsCount"]   if co else 0
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ── Canvas ──────────────────────────────────────────────────────────────
    W, H   = 900, 640
    SB     = 220          # sidebar right edge
    PAD    = 16

    # ── Zones ───────────────────────────────────────────────────────────────
    # TOP BAR   y=0..140   contest rating + sparkline
    # MID       y=150..300 donut | diff rows | badges
    # BOTTOM    y=310..640 heatmap

    TOP_H  = 140
    MID_Y  = TOP_H + 10
    MID_H  = 150
    HM_Y   = MID_Y + MID_H + 20

    # ── Donut ───────────────────────────────────────────────────────────────
    dcx = SB + PAD + 55
    dcy = MID_Y + MID_H // 2
    dr  = 50
    e_pct = easy / max(sum_t, 1)
    m_pct = med  / max(sum_t, 1)
    h_pct = hard / max(sum_t, 1)

    # ── Diff rows (right of donut) ──────────────────────────────────────────
    DR_X   = dcx + dr + 20
    DR_BAR = 180   # bar max width

    def diff_row(label, solved, ttl, color, ry):
        bw = int(solved / max(ttl, 1) * DR_BAR)
        return (
            f'<rect x="{DR_X}" y="{ry-9}" width="7" height="7" rx="1.5" fill="{color}"/>'
            f'<text x="{DR_X+12}" y="{ry}" fill="#c9d1d9" font-size="12" font-family="sans-serif">{label}</text>'
            f'<text x="{DR_X+68}" y="{ry}" fill="#e2e8f0" font-size="12" font-weight="600" font-family="sans-serif">{solved}</text>'
            f'<text x="{DR_X+100}" y="{ry}" fill="#4d5e6e" font-size="11" font-family="sans-serif">/ {ttl}</text>'
            f'<rect x="{DR_X+12}" y="{ry+4}" width="{DR_BAR}" height="4" rx="2" fill="#2d3748"/>'
            f'<rect x="{DR_X+12}" y="{ry+4}" width="{bw}" height="4" rx="2" fill="{color}"/>'
        )

    # ── Badges (right of diff rows) ──────────────────────────────────────────
    BG_X = DR_X + DR_BAR + 40

    # ── Lang bars (sidebar) ──────────────────────────────────────────────────
    max_lang = langs[0]["problemsSolved"] if langs else 1
    lang_svg = ""
    for i, l in enumerate(langs):
        ly  = 382 + i * 30
        bw  = int(l["problemsSolved"] / max_lang * (SB - 32))
        lang_svg += (
            f'<text x="16" y="{ly}" fill="#8b9cb0" font-size="11" font-family="sans-serif">{l["languageName"]}</text>'
            f'<text x="{SB-16}" y="{ly}" text-anchor="end" fill="#c9d1d9" font-size="11" font-family="sans-serif">{l["problemsSolved"]}</text>'
            f'<rect x="16" y="{ly+4}" width="{SB-32}" height="5" rx="2.5" fill="#2d3748"/>'
            f'<rect x="16" y="{ly+4}" width="{bw}" height="5" rx="2.5" fill="#FFA116"/>'
        )

    # ── Badge boxes (sidebar) ────────────────────────────────────────────────
    sb_badge_svg = ""
    for i, b in enumerate(badges):
        bx = 16 + i * 96
        sb_badge_svg += (
            f'<rect x="{bx}" y="296" width="84" height="58" rx="6" fill="#0f2d1a" stroke="#1a4a2a" stroke-width="1"/>'
            f'<text x="{bx+42}" y="322" text-anchor="middle" font-size="20">🏅</text>'
            f'<text x="{bx+42}" y="346" text-anchor="middle" fill="#6b7280" font-size="8" font-family="sans-serif">{b["displayName"][:11]}</text>'
        )

    # ── Main badge boxes ─────────────────────────────────────────────────────
    main_badge_svg = ""
    for i, b in enumerate(badges):
        bx = BG_X + i * 72
        main_badge_svg += (
            f'<rect x="{bx}" y="{MID_Y+30}" width="64" height="64" rx="8" fill="#0f2940" stroke="#1a3a5a" stroke-width="1"/>'
            f'<text x="{bx+32}" y="{MID_Y+68}" text-anchor="middle" font-size="26">🏅</text>'
            f'<text x="{bx+32}" y="{MID_Y+86}" text-anchor="middle" fill="#4d5e6e" font-size="8" font-family="sans-serif">{b["displayName"][:9]}</text>'
        )

    # ── Heatmap ──────────────────────────────────────────────────────────────
    HM_X   = SB + PAD
    HM_W   = W - SB - PAD * 2
    hm     = heatmap_svg(cal_str, HM_X, HM_Y + 16, weeks=52)

    # ── Sparkline ────────────────────────────────────────────────────────────
    SP_X  = SB + PAD + 310
    SP_Y  = 20
    SP_W  = W - SP_X - PAD
    SP_H  = TOP_H - 30
    spark = sparkline_svg(hi, SP_X, SP_Y, SP_W, SP_H)

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<title>LeetCode Profile — {name}</title>

<!-- Background -->
<rect width="{W}" height="{H}" rx="12" fill="#1a1a2e"/>

<!-- Sidebar -->
<rect width="{SB}" height="{H}" rx="12" fill="#16213e"/>
<rect x="{SB-1}" y="0" width="1" height="{H}" fill="#2d3748"/>

<!-- Avatar -->
<circle cx="{SB//2}" cy="50" r="34" fill="#0f3460"/>
<text x="{SB//2}" y="58" text-anchor="middle" fill="#FFA116" font-size="22" font-weight="700" font-family="sans-serif">BK</text>

<!-- Name / username -->
<text x="{SB//2}" y="104" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="600" font-family="sans-serif">{name}</text>
<text x="{SB//2}" y="120" text-anchor="middle" fill="#8b9cb0" font-size="11" font-family="sans-serif">{USERNAME}</text>

<!-- Rank -->
<text x="{SB//2}" y="142" text-anchor="middle" fill="#8b9cb0" font-size="11" font-family="sans-serif">Rank</text>
<text x="{SB//2}" y="160" text-anchor="middle" fill="#FFA116" font-size="15" font-weight="700" font-family="sans-serif">#{ranking:,}</text>

<line x1="12" y1="170" x2="{SB-12}" y2="170" stroke="#2d3748" stroke-width="1"/>

<!-- Community stats -->
<text x="16" y="188" fill="#4d5e6e" font-size="10" font-family="sans-serif" letter-spacing="1">COMMUNITY STATS</text>
<text x="16" y="207" fill="#8b9cb0" font-size="11" font-family="sans-serif">Reputation</text>
<text x="{SB-16}" y="207" text-anchor="end" fill="#c9d1d9" font-size="11" font-family="sans-serif">{rep}</text>
<text x="16" y="225" fill="#8b9cb0" font-size="11" font-family="sans-serif">Active Days</text>
<text x="{SB-16}" y="225" text-anchor="end" fill="#c9d1d9" font-size="11" font-family="sans-serif">{act_days}</text>
<text x="16" y="243" fill="#8b9cb0" font-size="11" font-family="sans-serif">Max Streak</text>
<text x="{SB-16}" y="243" text-anchor="end" fill="#c9d1d9" font-size="11" font-family="sans-serif">{streak}</text>

<line x1="12" y1="256" x2="{SB-12}" y2="256" stroke="#2d3748" stroke-width="1"/>

<!-- Sidebar badges -->
<text x="16" y="274" fill="#4d5e6e" font-size="10" font-family="sans-serif" letter-spacing="1">BADGES ({len(badges)})</text>
{sb_badge_svg}

<line x1="12" y1="364" x2="{SB-12}" y2="364" stroke="#2d3748" stroke-width="1"/>

<!-- Languages -->
<text x="16" y="380" fill="#4d5e6e" font-size="10" font-family="sans-serif" letter-spacing="1">LANGUAGES</text>
{lang_svg}

<!-- Updated -->
<text x="{SB//2}" y="{H-8}" text-anchor="middle" fill="#2d3748" font-size="9" font-family="sans-serif">Updated {updated}</text>

<!-- ═══════════ MAIN PANEL ═══════════ -->

<!-- TOP: Contest rating row -->
<text x="{SB+PAD}" y="22" fill="#8b9cb0" font-size="11" font-family="sans-serif">Contest Rating</text>
<text x="{SB+PAD}" y="50" fill="#e2e8f0" font-size="28" font-weight="700" font-family="sans-serif">{cr}</text>

<text x="{SB+PAD+110}" y="22" fill="#8b9cb0" font-size="11" font-family="sans-serif">Global Ranking</text>
<text x="{SB+PAD+110}" y="50" fill="#e2e8f0" font-size="16" font-family="sans-serif">{c_rank:,}/{c_tot:,}</text>

<text x="{SB+PAD+260}" y="22" fill="#8b9cb0" font-size="11" font-family="sans-serif">Attended</text>
<text x="{SB+PAD+260}" y="50" fill="#e2e8f0" font-size="16" font-family="sans-serif">{c_att}</text>

<text x="{W-PAD}" y="22" text-anchor="end" fill="#8b9cb0" font-size="11" font-family="sans-serif">Top</text>
<text x="{W-PAD}" y="52" text-anchor="end" fill="#e2e8f0" font-size="26" font-weight="700" font-family="sans-serif">{c_pct}%</text>

<!-- Sparkline -->
{spark}

<!-- Divider under top bar -->
<line x1="{SB+PAD}" y1="{TOP_H}" x2="{W-PAD}" y2="{TOP_H}" stroke="#2d3748" stroke-width="1"/>

<!-- MID: Donut -->
<circle cx="{dcx}" cy="{dcy}" r="{dr}" fill="none" stroke="#2d3748" stroke-width="12"/>
{donut_arc(dcx, dcy, dr, 0,               e_pct,           "#00b8a3")}
{donut_arc(dcx, dcy, dr, e_pct,           e_pct + m_pct,   "#ffc01e")}
{donut_arc(dcx, dcy, dr, e_pct + m_pct,   e_pct+m_pct+h_pct, "#ef4743")}
<text x="{dcx}" y="{dcy-10}" text-anchor="middle" fill="#e2e8f0" font-size="20" font-weight="700" font-family="sans-serif">{total}</text>
<text x="{dcx}" y="{dcy+8}" text-anchor="middle" fill="#4d5e6e" font-size="10" font-family="sans-serif">/ {easy_t+med_t+hard_t}</text>
<text x="{dcx}" y="{dcy+24}" text-anchor="middle" fill="#00b8a3" font-size="10" font-family="sans-serif">✓ Solved</text>

<!-- MID: Difficulty rows -->
{diff_row("Easy", easy, easy_t, "#00b8a3", MID_Y + 40)}
{diff_row("Med.",  med,  med_t,  "#ffc01e", MID_Y + 80)}
{diff_row("Hard", hard, hard_t, "#ef4743", MID_Y + 120)}

<!-- MID: Badges right panel -->
<text x="{BG_X}" y="{MID_Y+18}" fill="#8b9cb0" font-size="12" font-family="sans-serif" font-weight="600">Badges</text>
<text x="{BG_X+30}" y="{MID_Y+18}" fill="#e2e8f0" font-size="16" font-weight="700" font-family="sans-serif">{len(badges)}</text>
<text x="{W-PAD}" y="{MID_Y+18}" text-anchor="end" fill="#4d5e6e" font-size="12" font-family="sans-serif">→</text>
{main_badge_svg}
<text x="{W-PAD}" y="{MID_Y+110}" text-anchor="end" fill="#6b7280" font-size="10" font-family="sans-serif">Most Recent: {badges[0]["displayName"] if badges else ""}</text>

<!-- Divider above heatmap -->
<line x1="{SB+PAD}" y1="{HM_Y}" x2="{W-PAD}" y2="{HM_Y}" stroke="#2d3748" stroke-width="1"/>

<!-- BOTTOM: Heatmap -->
<text x="{HM_X}" y="{HM_Y+14}" fill="#c9d1d9" font-size="12" font-weight="600" font-family="sans-serif">submissions in the past one year</text>
<text x="{W-PAD}" y="{HM_Y+14}" text-anchor="end" fill="#4d5e6e" font-size="10" font-family="sans-serif">Total active days: {act_days}  ·  Max streak: {streak}</text>

{hm}

<!-- Heatmap legend -->
<text x="{HM_X}" y="{H-10}" fill="#4d5e6e" font-size="10" font-family="sans-serif">Less</text>
{''.join([f'<rect x="{HM_X+32+i*14}" y="{H-22}" width="11" height="11" rx="2" fill="{c}"/>' for i,c in enumerate(["#1a2a1a","#0e4429","#006d32","#26a641","#39d353"])])}
<text x="{HM_X+32+5*14+4}" y="{H-10}" fill="#4d5e6e" font-size="10" font-family="sans-serif">More</text>

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
