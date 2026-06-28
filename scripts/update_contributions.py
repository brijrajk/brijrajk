#!/usr/bin/env python3
"""
Fetches live PR statuses from GitHub API and rewrites the
<!-- CONTRIBUTIONS_START --> ... <!-- CONTRIBUTIONS_END --> block in README.md.

Status logic:
  merged_at is set        → ✅ Merged
  state==closed, no merge → ❌ Closed
  state==open             → 🔄 Open

Run: python scripts/update_contributions.py
Requires: GITHUB_TOKEN env var (automatically set in GitHub Actions)
"""

import json, os, re, sys
from urllib.request import urlopen, Request
from urllib.error import URLError

README = "README.md"
TOKEN  = os.environ.get("GITHUB_TOKEN", "")

# (owner, repo, pr_number, description)
TRACKED = [
    ("pytorch",        "pytorch",                    185694, "[library] Improve infer_schema error message when future annotations cause NameError"),
    ("pytorch",        "pytorch",                    185756, "[clamp] Fix float16 scalar overflow check inconsistency between CPU and GPU"),
    ("pytorch",        "pytorch",                    185751, "[nn] Raise ValueError early for invalid (ndim, pad_size) in non-constant F.pad modes"),
    ("pytorch",        "pytorch",                    187861, "[nn] Raise ValueError for norm_type=0 in lp_pool{1,2,3}d and LPPoolNd"),
    ("pytorch",        "pytorch",                    187908, "[fix] torch.where silently overflows fp16 scalars (issue #187429)"),
    ("pytorch",        "pytorch",                    188167, "[c10][cuda] Restore current device via RAII on the throwing path in CUDAGuardImpl"),
    ("vllm-project",   "vllm",                       44349,  "[Tests] Gate Step3VL under Transformers v5"),
    ("apache",         "gluten",                     12151,  "[GLUTEN-12013][VL] Fix bloom-filter bytes corruption on whole-stage AQE fallback"),
    ("apache",         "gluten",                     12158,  "[GLUTEN-12157][VL] Fix silently-skipped math/scalar test suites; add Velox native tests for sin, tan, tanh, radians, ln"),
    ("apache",         "gluten",                     12199,  "[MINOR][VL] Re-enable stale ignored atan2 test in MathFunctionsValidateSuite"),
    ("apache",         "gluten",                     12332,  "[GLUTEN-12260][VL] Fix CheckOverflowTransformer passing wrong child dataType"),
    ("apache",         "gluten",                     12333,  "[GLUTEN-11539][VL] Improve error message for unsupported spark.io.compression.codec in native shuffle"),
    ("apache",         "gluten",                     12335,  "[GLUTEN-10992][VL] Fix MatchError for KeyGroupedPartitioning in native shuffle"),
    ("apache",         "gluten",                     12360,  "[GLUTEN-11539][VL] Improve error message when spark.io.compression.codec=none"),
    ("apache",         "gluten",                     12374,  "[UT][VL] Refresh TPC-H q19 plan stability golden file"),
    ("facebookincubator","velox",                    17668,  "perf(tpcds): Eliminate redundant map allocations in toTableName and fromTableName"),
    ("facebookincubator","velox",                    17669,  "feat: Register Spark transform_values function"),
    ("facebookincubator","velox",                    17675,  "docs(geospatial): Expand convex_hull_agg and geometry_union_agg docs"),
    ("facebookincubator","velox",                    17676,  "docs: Fix duplicate object description warnings in Sphinx doc build"),
    ("facebookincubator","velox",                    17677,  "test(parquet): Verify WriterOptions::encoding is forwarded to Arrow writer"),
    ("apache",         "spark",                      56154,  "[SPARK-49798][DOCS] Fix inaccurate documentation of RuntimeConfig.get"),
    ("apache",         "spark",                      56174,  "[SPARK-43847][PYTHON] Throw structured error when reading Protobuf descriptor file fails"),
    ("apache",         "spark",                      56178,  "[SPARK-40437][SS][PYTHON] Support string representation of durationMs in GroupState.setTimeoutDuration"),
    ("apache",         "spark",                      56248,  "[SPARK-34679][DOCS] Add inferTimestamp option to JSON data source options table"),
    ("apache",         "spark",                      56250,  "[SPARK-56561][PYTHON][DOCS] Document order preservation for array_distinct, array_intersect, array_union, array_except"),
    ("apache",         "spark",                      56469,  "[SPARK-57418][DOCS] Add singleVariantColumn option to CSV, JSON, and XML data source options tables"),
    ("apache",         "spark",                      56473,  "[SPARK-56367][SS][PYTHON][DOCS] Fix latestOffset docstring, update tutorial signature, and add Trigger.AvailableNow documentation"),
    ("apache",         "spark",                      56673,  "[SPARK-43322][SQL] Document null/empty behavior in explode_outer and posexplode_outer"),
    ("apache",         "spark",                      56675,  "[SPARK-47013][SS] Document spark.sql.streaming.minBatchesToRetain config"),
    ("aws-samples",    "aws-etl-orchestrator",        9,     "Migrate to Python3.12"),
    ("duckdb",         "duckdb",                     23104,  "Fix *COLUMNS() false rejection when operators appear in lambda bodies"),
    ("duckdb",         "duckdb",                     23363,  "Fix *COLUMNS() false rejection when operators appear in lambda bodies"),
    ("duckdb",         "duckdb",                     23366,  "Fix *COLUMNS() false rejection when operator wraps function result"),
    ("google",         "it-cert-automation-practice", 2336,  "Closes: #1"),
]

GROUPS = [
    ("pytorch",          "pytorch",                    "🤖 PyTorch"),
    ("vllm-project",     "vllm",                       "⚡ vLLM"),
    ("apache",           "gluten",                     "🚀 Apache Gluten"),
    ("facebookincubator","velox",                      "🧠 Velox"),
    ("apache",           "spark",                      "🔥 Apache Spark"),
    ("aws-samples",      "aws-etl-orchestrator",       "📦 aws-samples/aws-etl-orchestrator"),
    ("duckdb",           "duckdb",                     "📦 duckdb/duckdb"),
    ("google",           "it-cert-automation-practice","📦 google/it-cert-automation-practice"),
]

def gh(path):
    url = f"https://api.github.com{path}"
    hdrs = {"Accept": "application/vnd.github+json", "User-Agent": "brijrajk-readme"}
    if TOKEN: hdrs["Authorization"] = f"Bearer {TOKEN}"
    try:
        with urlopen(Request(url, headers=hdrs), timeout=15) as r:
            return json.loads(r.read())
    except URLError as e:
        print(f"  warn: {e}"); return None

# Phrases in PR comments that indicate a maintainer merged the code
MERGE_PHRASES = [
    "merging to", "merged to", "merged into", "merged in",
    "cherry-pick", "cherry pick", "landed in", "committed to",
    "closing in favor", "squashed and merged",
]

def is_merged_by_comment(owner, repo, num):
    """Check PR comments for merge-confirmation language (e.g. Spark maintainers)."""
    import re
    comments = gh(f"/repos/{owner}/{repo}/issues/{num}/comments")
    if not comments:
        return False
    for c in comments:
        body = c.get("body", "").lower()
        if any(re.search(p, body) for p in MERGE_PHRASES):
            return True
    return False

def status(owner, repo, num):
    # 1. Pull endpoint — native GitHub merge sets merged_at
    d = gh(f"/repos/{owner}/{repo}/pulls/{num}")
    if d:
        if d.get("merged_at"):
            return "✅ Merged"
        if d.get("state") == "closed":
            # 2. Label check — Meta/Velox bot adds "Merged" label on bot-sync
            labels = [l["name"].lower() for l in d.get("labels", [])]
            if "merged" in labels:
                return "✅ Merged"
            # 3. Comment check — Spark/Apache maintainers say "merging to master"
            if is_merged_by_comment(owner, repo, num):
                return "✅ Merged"
            return "❌ Closed"
        return "🔄 Open"

    # Fallback: issues endpoint (closed PRs 404 on pulls endpoint)
    d = gh(f"/repos/{owner}/{repo}/issues/{num}")
    if d:
        pr     = d.get("pull_request", {})
        labels = [l["name"].lower() for l in d.get("labels", [])]
        if pr.get("merged_at"):
            return "✅ Merged"
        if "merged" in labels:
            return "✅ Merged"
        if d.get("state") == "closed":
            if is_merged_by_comment(owner, repo, num):
                return "✅ Merged"
            return "❌ Closed"
        return "🔄 Open"
    return "❓ Unknown"

AUTHOR = "brijrajk"
SEARCH = "https://github.com/search?type=pullrequests&q=is%3Apr+author%3A" + AUTHOR

# Headline engines for the "Merged into ..." marquee.
# (owner, repo, display_name, shields_logo_slug or None)
BRANDS = [
    ("pytorch",           "pytorch", "PyTorch",       "pytorch"),
    ("vllm-project",      "vllm",    "vLLM",          None),
    ("apache",            "spark",   "Apache Spark",  "apachespark"),
    ("facebookincubator", "velox",   "Velox",         "meta"),
    ("apache",            "gluten",  "Apache Gluten", "apache"),
]

def fetch_statuses():
    statuses = {}
    for owner, repo, num, _ in TRACKED:
        print(f"  {owner}/{repo}#{num} ...", end=" ", flush=True)
        s = status(owner, repo, num)
        statuses[(owner, repo, num)] = s
        print(s)
    return statuses

def build_scoreboard(statuses):
    merged = sum(1 for s in statuses.values() if s == "✅ Merged")
    openc  = sum(1 for s in statuses.values() if s == "🔄 Open")
    repos  = len({(o, r) for (o, r, n, _) in TRACKED})
    return "\n".join([
        "<!-- SCOREBOARD_START -->",
        "<p align=\"center\">",
        f"  <a href=\"{SEARCH}+is%3Amerged\"><img src=\"https://img.shields.io/badge/PRs%20Merged-{merged}-2ea043?style=for-the-badge&logo=github&logoColor=white&labelColor=0d1117\"/></a>",
        f"  <a href=\"{SEARCH}+is%3Aopen\"><img src=\"https://img.shields.io/badge/PRs%20Open-{openc}-1f6feb?style=for-the-badge&logo=github&logoColor=white&labelColor=0d1117\"/></a>",
        f"  <a href=\"{SEARCH}\"><img src=\"https://img.shields.io/badge/Upstream%20Repos-{repos}-8957e5?style=for-the-badge&logo=github&logoColor=white&labelColor=0d1117\"/></a>",
        "</p>",
        "<!-- SCOREBOARD_END -->",
    ])

def build_mergedlogos(statuses):
    lines = ["<!-- MERGEDLOGOS_START -->", "<p align=\"center\">"]
    for owner, repo, name, logo in BRANDS:
        ss = [s for (o, r, n), s in statuses.items() if o == owner and r == repo]
        if "✅ Merged" in ss:
            state, color = "✓", "2ea043"
        elif "🔄 Open" in ss:
            state, color = "active", "1f6feb"
        else:
            continue
        label = name.replace(" ", "%20")
        logo_q = f"&logo={logo}&logoColor=white" if logo else ""
        href = f"https://github.com/{owner}/{repo}/pulls?q=is%3Apr+author%3A{AUTHOR}"
        lines.append(
            f"  <a href=\"{href}\"><img src=\"https://img.shields.io/badge/{label}-{state}-{color}"
            f"?style=flat-square{logo_q}&labelColor=222\"/></a>"
        )
    lines += ["</p>", "<!-- MERGEDLOGOS_END -->"]
    return "\n".join(lines)

def build_contributions(statuses):
    STATUS_ORDER = {"✅ Merged": 0, "🔄 Open": 1, "❌ Closed": 2, "❓ Unknown": 3}
    lines = ["<!-- CONTRIBUTIONS_START -->"]
    for owner, repo, heading in GROUPS:
        prs = [(n, d) for (o, r, n, d) in TRACKED if o==owner and r==repo]
        if not prs: continue
        prs.sort(key=lambda nd: STATUS_ORDER.get(statuses.get((owner, repo, nd[0]), "❓ Unknown"), 3))
        lines += [f"### {heading}", "| PR | Description | Status |", "|----|-------------|--------|"]
        for num, desc in prs:
            s   = statuses.get((owner, repo, num), "❓ Unknown")
            url = f"https://github.com/{owner}/{repo}/pull/{num}"
            lines.append(f"| [#{num}]({url}) | {desc} | {s} |")
        lines.append("")
    lines.append("<!-- CONTRIBUTIONS_END -->")
    return "\n".join(lines)

def update(fragments):
    """fragments: {marker_name: rendered_block}. Each block is wrapped in its
    own START/END markers; only present markers are replaced."""
    with open(README) as f: c = f.read()
    orig = c
    for marker, block in fragments.items():
        pattern = rf'<!-- {marker}_START -->.*?<!-- {marker}_END -->'
        c, n = re.subn(pattern, lambda _: block, c, flags=re.DOTALL)
        if n == 0:
            print(f"  WARNING: {marker} markers not found")
        else:
            print(f"  {marker} updated")
    if c == orig:
        print("WARNING: nothing changed")
        return
    with open(README, "w") as f: f.write(c)

if __name__ == "__main__":
    print("Fetching PR statuses...")
    statuses = fetch_statuses()
    update({
        "SCOREBOARD":    build_scoreboard(statuses),
        "MERGEDLOGOS":   build_mergedlogos(statuses),
        "CONTRIBUTIONS": build_contributions(statuses),
    })
    print("Done")
