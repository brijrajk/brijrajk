import json, subprocess, re

# Add any PR here — (repo, number, description)
PRS = [
    # PyTorch
    ("pytorch/pytorch", 185694, "Fix `infer_schema` error message when `from __future__ import annotations` causes `NameError`"),
    ("pytorch/pytorch", 185751, "Fix `F.pad` raising `NotImplementedError` instead of `ValueError` for invalid `(ndim, pad_size)` in non-constant modes"),
    ("pytorch/pytorch", 185756, "Fix `torch.clamp` float16 scalar overflow check inconsistency between CPU and GPU"),
    # Gluten
    ("apache/gluten", 12158, "Fix silently-skipped math/scalar test suites; add Velox native tests for `sin`, `tan`, `tanh`, `radians`, `ln`"),
    ("apache/gluten", 12151, "Fix bloom-filter bytes corruption on whole-stage AQE fallback"),
    # Velox
    ("facebookincubator/velox", 17677, "test(parquet): Verify `WriterOptions::encoding` is forwarded to Arrow writer"),
    ("facebookincubator/velox", 17676, "docs: Fix duplicate object description warnings in Sphinx doc build"),
    ("facebookincubator/velox", 17675, "docs(geospatial): Expand `convex_hull_agg` and `geometry_union_agg` docs"),
    ("facebookincubator/velox", 17669, "feat(sparksql): Register `transform_values` in sparksql map functions registry"),
    # Spark
    ("apache/spark", 56178, "[PYTHON] Support string representation of `durationMs` in `GroupState.setTimeoutDuration`"),
    ("apache/spark", 56174, "[PYTHON] Throw structured error when reading Protobuf descriptor file fails"),
    ("apache/spark", 56154, "[DOCS] Fix inaccurate documentation of `RuntimeConfig.get`"),
]

REPO_DISPLAY = {
    "pytorch/pytorch":          ("🤖", "PyTorch"),
    "apache/gluten":            ("🚀", "Apache Gluten"),
    "facebookincubator/velox":  ("🧠", "Velox"),
    "apache/spark":             ("🔥", "Apache Spark"),
}


REPO_DISPLAY = {
    "pytorch/pytorch": "PyTorch",
    "apache/spark": "Apache Spark",
    "facebookincubator/velox": "Velox",
    # add display names for any repo you contribute to
}

def get_pr_status(repo, number):
    out = subprocess.check_output(
        ["gh", "api", f"repos/{repo}/pulls/{number}",
         "--jq", "{state: .state, merged_at: .merged_at}"]
    )
    data = json.loads(out)
    if data["merged_at"]:
        return "✅ Merged"
    if data["state"] == "closed":
        for branch in ["main", "master"]:
            result = subprocess.run(
                ["gh", "api", f"repos/{repo}/commits?sha={branch}&per_page=100",
                 "--jq", f'[.[].commit.message] | any(contains("#{number}"))'],
                capture_output=True, text=True
            )
            if result.stdout.strip() == "true":
                return "✅ Merged"
        return "❌ Closed"
    return "🔄 Open"

# Group PRs by repo
from collections import defaultdict
by_repo = defaultdict(list)
for repo, number, description in PRS:
    status = get_pr_status(repo, number)
    url = f"https://github.com/{repo}/pull/{number}"
    by_repo[repo].append(f"| [#{number}]({url}) | {description} | {status} |")

# Build the full section
lines = []
for repo, rows in by_repo.items():
    name = REPO_DISPLAY.get(repo, repo)
    lines.append(f"### {name} ({repo})")
    lines.append("| PR | Description | Status |")
    lines.append("|----|-------------|--------|")
    lines.extend(rows)
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
print("Done.")
