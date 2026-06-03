import json, subprocess, re
from collections import defaultdict

AUTHOR = "brijrajk"

# Repos to skip (forks, personal experiments, etc.)
SKIP_REPOS = {
    "brijrajk/pytorch",
    "brijrajk/spark",
    "brijrajk/facebook-velox",
    "brijrajk/incubator-gluten",
    "brijrajk/vllm",
}

# Display config — emoji + friendly name
REPO_DISPLAY = {
    "pytorch/pytorch":          ("🤖", "PyTorch"),
    "vllm-project/vllm":        ("⚡", "vLLM"),
    "apache/gluten":            ("🚀", "Apache Gluten"),
    "facebookincubator/velox":  ("🧠", "Velox"),
    "apache/spark":             ("🔥", "Apache Spark"),
}

# Fixed display order — PyTorch always first, vLLM second
# New repos not listed here get auto-appended at the bottom
REPO_ORDER = [
    "pytorch/pytorch",
    "vllm-project/vllm",
    "apache/gluten",
    "facebookincubator/velox",
    "apache/spark",
]

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

def build_repo_table(repo, prs):
    """Build markdown table lines for a single repo."""
    emoji, name = REPO_DISPLAY.get(repo, ("📦", repo))
    lines = []
    lines.append(f"### {emoji} {name}")
    lines.append("| PR | Description | Status |")
    lines.append("|----|-------------|--------|")
    for number, url, title, status in prs:
        lines.append(f"| [#{number}]({url}) | {title} | {status} |")
    lines.append("")
    return lines

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
# Sort each repo's PRs — Merged first, then Open, then Closed, newest first within each
STATUS_PRIORITY = {
    "✅ Merged": 0,
    "🔄 Open":   1,
    "❌ Closed": 2,
}

for repo in by_repo:
    by_repo[repo].sort(key=lambda x: (STATUS_PRIORITY.get(x[3], 9), -x[0]))

# Build tables — fixed order first, then auto-detected new repos
lines = []

# 1. Render in fixed order
for repo in REPO_ORDER:
    if repo not in by_repo:
        continue
    lines.extend(build_repo_table(repo, by_repo[repo]))

# 2. Auto-append any new repos not in REPO_ORDER
for repo in sorted(by_repo.keys()):
    if repo in REPO_ORDER:
        continue
    lines.extend(build_repo_table(repo, by_repo[repo]))

# Inject into README between markers
new_section = "<!-- CONTRIBUTIONS_START -->\n" + "\n".join(lines) + "\n<!-- CONTRIBUTIONS_END -->"
readme = open("README.md").read()
updated = re.sub(
    r"<!-- CONTRIBUTIONS_START -->.*?<!-- CONTRIBUTIONS_END -->",
    new_section,
    readme,
    flags=re.DOTALL
)
open("README.md", "w").write(updated)
print(f"Updated README with {len(all_prs)} PRs across {len(by_repo)} repos.")
