#!/usr/bin/env bash
# Put this page on plotterpi, where piplot serves it beside the curve studio:
#   http://100.68.139.69:8080/etchatron.html            tailnet, no password
#   https://plotterpi.tail405153.ts.net/etchatron.html  visitors, password to plot
#
# Copying a page is safe mid-plot: piplot reads it per request. Never restart
# piplot from here; that kills a running plot. Needs piplot 0.12.0 or later,
# which has the /etchatron.html route and the etchatron machine driver.
set -euo pipefail
host="${PI_HOST:-plotterpi}"
here="$(cd "$(dirname "$0")" && pwd)"
scp -q "$here/index.html" "$host":piplot/docs/etchatron.html
echo "deployed: http://100.68.139.69:8080/etchatron.html"
