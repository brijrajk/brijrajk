name: 🧩 Update LeetCode Stats

on:
  schedule:
    - cron: "0 0 * * *"   # Every day at midnight UTC
  workflow_dispatch:        # Allow manual trigger from GitHub Actions tab
  push:
    branches: [main]
    paths:
      - "scripts/update_leetcode.py"

jobs:
  update-leetcode:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - name: 📥 Checkout repository
        uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: 🐍 Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: 🔄 Run LeetCode stats updater
        run: python scripts/update_leetcode.py

      - name: 📤 Commit and push changes
        run: |
          git config --global user.name "github-actions[bot]"
          git config --global user.email "github-actions[bot]@users.noreply.github.com"
          git add README.md
          git diff --cached --quiet || git commit -m "chore: 🧩 auto-update LeetCode stats [skip ci]"
          git push
