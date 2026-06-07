name: 🧩 Update LeetCode Profile SVG

on:
  schedule:
    - cron: "0 0 * * *"      # daily at midnight UTC
  workflow_dispatch:          # manual trigger from Actions tab
  push:
    branches: [main]
    paths: ["scripts/generate_leetcode_svg.py"]

jobs:
  update-leetcode:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Generate SVG
        run: python scripts/generate_leetcode_svg.py

      - name: Commit & push
        run: |
          git config --global user.name  "github-actions[bot]"
          git config --global user.email "github-actions[bot]@users.noreply.github.com"
          git add assets/leetcode-profile.svg README.md
          git diff --cached --quiet || git commit -m "chore: 🧩 auto-update LeetCode SVG [skip ci]"
          git push
