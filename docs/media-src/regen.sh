#!/usr/bin/env bash
# Rebuilds every image and clip in docs/ and agensi/media/ from real runs against live Nasdaq prices.
# Needs: Python 3.10+ with Pillow and pytest, Node with Playwright (set PW_ROOT to a folder whose node_modules
# has it if it is not installed next to this file), and ffmpeg. Takes about a minute.
# The numbers move with the market, so after a rebuild refresh the README table and examples/sample-* too.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/../.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

# the demo runs the shipped script from an empty folder, which is also what a buyer's agent does
demo=/tmp/dsa-demo
rm -rf "$demo" && mkdir "$demo"
cp "$root/agensi/daily-us-stock-analysis/scripts/stock_analysis.py" "$demo/"

python3 "$here/record.py" "$here/demo.spec.json" "$work/demo.cast.json"
node "$here/termcast.mjs" "$work/demo.cast.json" "$root/docs/demo.gif" "$root/docs/demo.mp4"
python3 "$here/record.py" "$here/still.spec.json" "$work/still.cast.json"
node "$here/termcast.mjs" "$work/still.cast.json" "$work/no-plan.png" --still

python3 "$here/make_charts.py" "$work/pages"
cp "$root/agensi/media/logo.png" "$work/pages/"
node "$here/render.mjs" html "$work/pages/anatomy.html" "$work/score-anatomy.png" 2
node "$here/render.mjs" html "$work/pages/plan.html" "$work/aapl-plan.png" 2
node "$here/render.mjs" html "$work/pages/social.html" "$work/social-preview.png" 1
node "$here/render.mjs" md "$work/pages/answer.md" "$work/answer.png" \
  "Your agent's answer to: \"Check AAPL, MSFT, NVDA and TSLA. I have \$25,000 and risk 1% a trade.\""

python3 "$here/shrink.py" 128 "$work/score-anatomy.png" "$work/aapl-plan.png" "$work/no-plan.png" "$work/answer.png"
cp "$work/score-anatomy.png" "$work/aapl-plan.png" "$work/no-plan.png" "$work/social-preview.png" "$root/docs/"
cp "$work/score-anatomy.png" "$root/agensi/media/screenshot-1.png"
cp "$work/aapl-plan.png" "$root/agensi/media/screenshot-2.png"
cp "$work/answer.png" "$root/agensi/media/screenshot-3.png"
ls -l "$root/docs" "$root/agensi/media"
