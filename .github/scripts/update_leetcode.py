#!/usr/bin/env python3
"""
Fetches LeetCode stats for brij_raj and updates the LeetCode section in README.md.
Uses LeetCode's public GraphQL API — no auth required.
"""

import json
import re
import sys
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError

USERNAME = "brij_raj"
README_PATH = "README.md"
GRAPHQL_URL = "https://leetcode.com/graphql"

QUERY = """
query getUserStats($username: String!) {
  matchedUser(username: $username) {
    username
    profile {
      ranking
      reputation
      starRating
    }
    submitStats: submitStatsGlobal {
      acSubmissionNum {
        difficulty
        count
        submissions
      }
    }
    badges {
      id
      displayName
    }
  }
  userContestRanking(username: $username) {
    attendedContestsCount
    rating
    globalRanking
    totalParticipants
    topPercentage
    badge {
      name
    }
  }
}
"""


def fetch_leetcode_stats(username: str) -> dict:
    payload = json.dumps({"query": QUERY, "variables": {"username": username}}).encode()
    req = Request(
        GRAPHQL_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Referer": "https://leetcode.com",
            "User-Agent": "Mozilla/5.0 (GitHub Actions)",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except URLError as e:
        print(f"❌ Failed to fetch LeetCode stats: {e}")
        sys.exit(1)


def medal_for_rating(rating: float) -> str:
    if rating >= 2400:
        return "🔴 Guardian"
    elif rating >= 2100:
        return "🟠 Knight"
    elif rating >= 1900:
        return "🟣 Expert"
    elif rating >= 1600:
        return "🔵 Specialist"
    else:
        return "⚪ Pupil"


def build_leetcode_section(data: dict) -> str:
    user = data["data"]["matchedUser"]
    contest = data["data"]["userContestRanking"]

    # Solved stats
    stats = {s["difficulty"]: s["count"] for s in user["submitStats"]["acSubmissionNum"]}
    total = stats.get("All", 0)
    easy = stats.get("Easy", 0)
    medium = stats.get("Medium", 0)
    hard = stats.get("Hard", 0)

    # Profile
    ranking = user["profile"]["ranking"]

    # Contest
    if contest:
        contest_rating = round(contest["rating"])
        contest_rank = contest["globalRanking"]
        total_participants = contest["totalParticipants"]
        top_pct = round(contest["topPercentage"], 1)
        contests_attended = contest["attendedContestsCount"]
        badge_name = contest["badge"]["name"] if contest.get("badge") else None
        medal = medal_for_rating(contest["rating"])
    else:
        contest_rating = "N/A"
        contest_rank = "N/A"
        total_participants = "N/A"
        top_pct = "N/A"
        contests_attended = 0
        badge_name = None
        medal = ""

    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Build badge URLs (shields.io)
    def badge(label, message, color, logo=""):
        logo_part = f"&logo={logo}&logoColor=black" if logo else ""
        label_enc = label.replace(" ", "%20").replace("#", "%23")
        message_enc = str(message).replace(" ", "%20").replace("#", "%23")
        return f"https://img.shields.io/badge/{label_enc}-{message_enc}-{color}?style=for-the-badge{logo_part}"

    card_base = f"https://leetcard.jacoblin.cool/{username}?theme=dark&font=Fira%20Code&border=0&radius=10&bg_color=0d1117&title_color=58a6ff&text_color=c9d1d9&ring_color=58a6ff"

    lines = [
        "## 🧩 LeetCode Stats",
        "",
        "<!-- LEETCODE_STATS_START -->",
        '<p align="center">',
        f'  <img src="{badge("Total Solved", total, "FFA116", "leetcode")}"/>',
        "  &nbsp;",
        f'  <img src="{badge("Global Rank", f"%23{ranking}", "1a2332")}"/>',
        "  &nbsp;",
        f'  <img src="{badge("Easy", easy, "00b8a3")}"/>',
        "  &nbsp;",
        f'  <img src="{badge("Medium", medium, "ffc01e")}"/>',
        "  &nbsp;",
        f'  <img src="{badge("Hard", hard, "ef4743")}"/>',
        "</p>",
        "",
        '<p align="center">',
        f'  <img src="{badge("Contest Rating", contest_rating, "58a6ff")}"/>',
        "  &nbsp;",
        f'  <img src="{badge("Contest Rank", f"%23{contest_rank}", "1a2332")}"/>',
        "  &nbsp;",
        f'  <img src="{badge("Top", f"{top_pct}%25", "6e40c9")}"/>',
        "  &nbsp;",
        f'  <img src="{badge("Contests", contests_attended, "0d1117")}"/>',
    ]

    if badge_name:
        lines += [
            "  &nbsp;",
            f'  <img src="{badge("Badge", badge_name, "ffd700")}"/>',
        ]

    lines += [
        "</p>",
        "",
        '<p align="center">',
        f'  <img src="{card_base}&ext=heatmap" width="49%"/>',
        f'  <img src="{card_base}&ext=contest" width="49%"/>',
        "</p>",
        "",
        '<p align="center">',
        f'  <a href="https://leetcode.com/u/{username}/">',
        f'    <img src="{badge("View Profile on LeetCode", "", "FFA116", "leetcode")}"/>',
        "  </a>",
        "</p>",
        "",
        f'<p align="center"><sub>🔄 Auto-updated: {updated} · {medal}</sub></p>',
        "",
        "<!-- LEETCODE_STATS_END -->",
    ]

    return "\n".join(lines)


def update_readme(section: str, readme_path: str):
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = r"<!-- LEETCODE_STATS_START -->.*?<!-- LEETCODE_STATS_END -->"
    new_content = re.sub(pattern, section.split("\n", 2)[2].rsplit("\n", 1)[0], content, flags=re.DOTALL)

    # If markers don't exist yet, replace the whole section header
    if new_content == content:
        print("⚠️  Markers not found — inserting full section.")
        pattern2 = r"## 🧩 LeetCode Stats\n.*?(?=\n---|\Z)"
        new_content = re.sub(pattern2, section, content, flags=re.DOTALL)

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"✅ README updated at {readme_path}")


if __name__ == "__main__":
    print(f"📡 Fetching LeetCode stats for @{USERNAME}...")
    data = fetch_leetcode_stats(USERNAME)
    section = build_leetcode_section(data)
    print("📝 Generated section:\n")
    print(section)
    update_readme(section, README_PATH)
