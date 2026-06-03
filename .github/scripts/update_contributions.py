import json, subprocess, re
from collections import defaultdict

AUTHOR = "brijrajk"

# Repos to skip (forks noise, personal experiments, etc.)
SKIP_REPOS = {
    "brijrajk/pytorch",
    "brijrajk/spark",
    "brijrajk/facebook-velox",
    "brijrajk/incubator-gluten",
}

REPO_DISPLAY = {
    "pytorch/pytorch":          ("🤖", "PyTorch"),
    "apache/gluten":            ("🚀", "Apache Gluten"),
    "facebookincubator/velox":  ("🧠", "Velox"),
    "apache/spark":             ("🔥", "Apache Spark"),
}

def search_prs():
    """Fetch all PRs opened by AUTHOR across all of GitHub."""
    prs = []
    page = 1
    while True:
        out = subprocess.check_output([
            "gh", "api",
            f"search/issues?q=author:{AUTHOR}+type:pr&per_page=100&page={page}",
            "--jq", ".items[] | {repo: (.repository_url | split(\"/\") | .[-2:] | join(\"/\")), number: .number, title: .title, state: .state}"
        ])
        items = [json.loads(line) for line in out.decode().strip().splitlines() if line]
        if not items:
            break
        prs.extend(items)
        page += 1
        if len(items) < 100:
            break
    return [p for p in prs if p["repo"] not in SKIP_REPOS]

def get_pr_status(repo, number, state):
    if state == "open":
        return "🔄 Open"
    
    # closed — check if actually merged via merged_at
    out = subprocess.check_output([
        "gh", "api", f"repos/{repo}/pulls/{number}",
        "--jq", ".merged_at"
    ]).decode().strip()
    
    if out and out != "null":
        return "✅ Merged"
    
    # fallback: check merge_commit_sha
    out2 = subprocess.check_output([
        "gh", "api", f"repos/{repo}/pulls/{number}",
        "--jq", ".merge_commit_sha"
    ]).decode().strip()
    
    if out2 and out2 != "null":
        return "✅ Merged"
    
    return "❌ Closed"


# Discover all PRs automatically
all_prs = search_prs()

# Group by repo
by_repo = defaultdict(list)
for pr in all_prs:
    repo = pr["repo"]
    status = get_pr_status(repo, pr["number"], pr["state"])
    url = f"https://github.com/{repo}/pull/{pr['number']}"
    by_repo[repo].append((pr["number"], url, pr["title"], status))

# Sort each repo's PRs newest first
for repo in by_repo:
    by_repo[repo].sort(key=lambda x: x[0], reverse=True)

# Build the table section
lines = []
for repo, prs in sorted(by_repo.items()):
    emoji, name = REPO_DISPLAY.get(repo, ("📦", repo))
    lines.append(f"### {emoji} {name} ({repo})")
    lines.append("| PR | Description | Status |")
    lines.append("|----|-------------|--------|")
    for number, url, title, status in prs:
        lines.append(f"| [#{number}]({url}) | {title} | {status} |")
    lines.append("")

new_section = "<!-- CONTRIBUTIONS_START -->\n" + "\n".join(lines) + "<!-- CONTRIBUTIONS_END -->"

readme = open("README.md").read()
updated = re.sub(
    r"<!-- CONTRIBUTIONS_START -->.*?<!-- CONTRIBUTIONS_END -->",
    new_section,
    readme,
    flags=re.DOTALL
)
open("README.md", "w").write(updated)
print(f"Updated README with {len(all_prs)} PRs across {len(by_repo)} repos.")
