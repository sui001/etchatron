#!/usr/bin/env bash
# Put this page on plotterpi, where piplot serves it beside the curve studio:
#   http://100.68.139.69:8080/etchatron.html            tailnet, no password
#   https://plotterpi.tail405153.ts.net/etchatron.html  visitors, password to plot
#
# Copying a page is safe mid-plot: piplot reads it per request. Never restart
# piplot from here; that kills a running plot. Needs piplot 0.12.0 or later,
# which has the /etchatron.html route and the etchatron machine driver.
#
# The page loads ../lib/timeline.js (the timeline's entries, shared with
# timeline/index.html). piplot serves only named .html pages from docs/, not
# loose scripts, so the file is inlined into the copy rather than sent beside
# it, and piplot needs no change.
#
#   deploy_to_plotterpi.sh --dry-run   builds etchatron.dry-run.html here, sends nothing
set -euo pipefail
host="${PI_HOST:-plotterpi}"
here="$(cd "$(dirname "$0")" && pwd)"
lib="$here/../lib/timeline.js"
tag='<script src="../lib/timeline.js"></script>'
out="$here/etchatron.dry-run.html"
grep -qF "$tag" "$here/index.html" || { echo "index.html no longer loads $tag: update this script" >&2; exit 1; }
if grep -qi '</script' "$lib"; then echo "timeline.js contains </script, so it cannot be inlined" >&2; exit 1; fi
awk -v tag="$tag" -v lib="$lib" '
  $0 == tag { print "<script>"; while ((getline l < lib) > 0) print l; print "</script>"; next }
  { print }' "$here/index.html" > "$out"
if grep -qF "$tag" "$out" || ! grep -q 'const TIMELINE' "$out"; then echo "inlining failed, nothing sent" >&2; exit 1; fi
if [ "${1:-}" = "--dry-run" ]; then echo "built $out, nothing sent"; exit 0; fi
scp -q "$out" "$host":piplot/docs/etchatron.html
rm -f "$out"
echo "deployed: http://100.68.139.69:8080/etchatron.html"
