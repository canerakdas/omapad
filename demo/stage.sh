#!/usr/bin/env bash
# Dress the set: an empty workspace with two tiled windows, the terminal
# focused so the on-screen keyboard has somewhere to type into. Safe to re-run
# - a window already there is left alone.
#
# Every dispatch is written in Lua. This Hyprland routes them through it, and
# the old `hyprctl dispatch workspace 9` form is a syntax error rather than a
# no-op.
set -euo pipefail

WORKSPACE="${1:-${DEMO_WORKSPACE:-9}}"
TERMINAL="${DEMO_TERMINAL:-foot}"
FILES="${DEMO_FILES:-nautilus}"
# Somewhere with enough in it to scroll, and nothing in it worth opening
# by accident: the take clicks and scrolls in this window.
FILES_AT="${DEMO_FILES_AT:-/usr/share}"

# `setsid`, so the staged windows are not descendants of the recorder.
# `handover.py` asks whether the focused window's process tree has the pad
# open, and a window launched from here would have the demo's own daemon as a
# cousin - which reads as "the app in front wants the pad" and drops the grab
# in the middle of the take.
launch() {
  setsid "$@" >/dev/null 2>&1 &
}

# On this workspace, not anywhere: the machine a take is recorded on already
# has terminals open, and a set dressed on someone else's workspace is no set.
count_here() {
  hyprctl clients -j | python3 -c '
import json, sys
workspace, want = sys.argv[1], sys.argv[2]
print(sum(1 for client in json.load(sys.stdin)
          if str(client["workspace"]["name"]) == workspace
          and want in client["class"]))' "$WORKSPACE" "$1"
}

# The screensaver is an ordinary window and would sit in front of the take.
hyprctl dispatch \
  "hl.dsp.window.close({ window = 'class:org.omarchy.screensaver' })" \
  >/dev/null 2>&1 || true
sleep 0.4

# The bar carries the pad widget, and game mode's whole trick is taking it away
# for a bigger one - so the take needs it up. The argument names the `bar-off`
# flag rather than the bar: `off` is what brings the bar back.
omarchy toggle bar off >/dev/null 2>&1 || true

hyprctl dispatch "hl.dsp.focus({ workspace = $WORKSPACE })" >/dev/null
sleep 1.0

if [ "$(count_here Nautilus)" = "0" ]; then
  launch "$FILES" --new-window "$FILES_AT"
  sleep 3.5
fi
if [ "$(count_here "$TERMINAL")" = "0" ]; then
  launch "$TERMINAL" -D "$HOME"
  sleep 2.0
fi

# By address, not by class: there are terminals of the same class on other
# workspaces, and a class selector focuses one of those - taking the view with
# it.
ADDRESS="$(hyprctl clients -j | python3 -c '
import json, sys
workspace, want = sys.argv[1], sys.argv[2]
for client in json.load(sys.stdin):
    if str(client["workspace"]["name"]) == workspace and want in client["class"]:
        print(client["address"])
        break' "$WORKSPACE" "$TERMINAL")"
if [ -n "$ADDRESS" ]; then
  hyprctl dispatch "hl.dsp.focus({ window = 'address:$ADDRESS' })" >/dev/null
fi
sleep 0.6
