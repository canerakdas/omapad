#!/usr/bin/env bash
# One command from a live desktop to demo.mp4. Safe to re-run.
#
# The order is the whole trick: the pad has to exist before the daemon looks
# for one, the set has to be dressed before the recorder's first frame, and the
# captions are burnt in afterwards from the cue log the storyboard wrote.
#
# Every knob is an environment variable with its default in place:
#   DEMO_MONITOR    which output to record          (first one Hyprland lists)
#   DEMO_WORKSPACE  which workspace to record on    (9)
#   DEMO_FPS        frame rate                      (60)
#   DEMO_OUT        the finished file               (demo/demo.mp4)
#   DEMO_FONT       caption font                    (Noto Sans)
#   DEMO_SERVICE    the everyday unit to stand down (gamepadd.service)
#   DEMO_FILES_AT   what the file manager shows         (/usr/share)
# Arguments name scenes to record, for a re-shoot of one chapter:
#   ./record.sh keyboard menu
set -euo pipefail

DEMO="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
cd "$DEMO"

DEMO_MONITOR="${DEMO_MONITOR:-$(hyprctl monitors -j |
  python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["name"])')}"
DEMO_WORKSPACE="${DEMO_WORKSPACE:-9}"
DEMO_FPS="${DEMO_FPS:-60}"
DEMO_OUT="${DEMO_OUT:-$DEMO/demo.mp4}"
RAW="$DEMO/raw.mp4"
GO="$DEMO/go"

SERVICE="${DEMO_SERVICE:-gamepadd.service}"
REC=""
DRIVER=""
RESTORE_SERVICE=""

cleanup() {
  rm -f "$GO"
  # Whatever went wrong: no recorder left holding the screen, no half-driven
  # pad, the everyday daemon back, and a desktop that idles normally again.
  [ -n "$REC" ] && kill -INT "$REC" 2>/dev/null || true
  [ -n "$DRIVER" ] && kill "$DRIVER" 2>/dev/null || true
  [ -n "$RESTORE_SERVICE" ] && systemctl --user start "$SERVICE" || true
  omarchy-toggle-idle allow-idle >/dev/null 2>&1 || true
}
trap cleanup EXIT

# The everyday daemon has to stand down for the take. Two daemons are not a
# race the demo can win: they share one control socket, and the one that did
# not get it has its surfaces closed again by the other's next heartbeat - so
# the take records a desktop where nothing the pad does appears to work.
if systemctl --user --quiet is-active "$SERVICE" 2>/dev/null; then
  echo "stopping $SERVICE for the take"
  systemctl --user stop "$SERVICE"
  RESTORE_SERVICE=1
  sleep 1
fi

# A daemon left over from an interrupted take holds the same socket.
pkill -f "omapad -c $DEMO/config[.]toml" 2>/dev/null || true
sleep 0.5

rm -f "$RAW" "$RAW.ts" cues.jsonl "$GO"

# The screensaver would otherwise land in the middle of a take.
omarchy-toggle-idle stay-awake >/dev/null

# The pad and the daemon, up and settled before anything is recorded.
python3 story.py --go "$GO" "$@" > driver.log 2>&1 &
DRIVER=$!
for _ in $(seq 300); do
  grep -q READY driver.log 2>/dev/null && break
  sleep 0.1
done
grep -q READY driver.log 2>/dev/null || { cat driver.log; exit 1; }

"$DEMO/stage.sh" "$DEMO_WORKSPACE"

gpu-screen-recorder -w "$DEMO_MONITOR" -f "$DEMO_FPS" -k h264 -q very_high \
  -cursor yes -write-first-frame-ts yes -o "$RAW" > recorder.log 2>&1 &
REC=$!
sleep 3
touch "$GO"

wait "$DRIVER"
DRIVER=""
sleep 1.5
kill -INT "$REC"
wait "$REC" 2>/dev/null || true
REC=""

read -r DEMO_WIDTH DEMO_HEIGHT <<<"$(hyprctl monitors -j | python3 -c '
import json, sys
name = sys.argv[1]
for monitor in json.load(sys.stdin):
    if monitor["name"] == name:
        print(monitor["width"], monitor["height"])
        break' "$DEMO_MONITOR")"
export DEMO_WIDTH DEMO_HEIGHT

python3 captions.py "$RAW" "$DEMO_OUT"
