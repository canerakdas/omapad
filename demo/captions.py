"""Burn the cue log into the recording.

The cues carry monotonic timestamps and gpu-screen-recorder writes the
monotonic timestamp of its first frame beside the video, so the two line up
exactly - no guessing at how long the recorder took to spin up, and no drift
over a two-minute take.

ASS rather than a drawn overlay, because an overlay window would be recorded
along with everything else: a caption that says what is being pressed must not
be a thing on the screen the pad could have pressed.
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

WIDTH = int(os.environ.get("DEMO_WIDTH", "1920"))
HEIGHT = int(os.environ.get("DEMO_HEIGHT", "1200"))

# Captions sit at the top: every surface omapad draws owns either the bottom
# of the screen (the keyboard, the bar) or the middle of it (the menu, the
# guide, the mapping screen).
KEYS_Y = 74
DESC_Y = 134

# A caption shorter than this is a cue that was overtaken by the next beat -
# a flash nobody can read, so it is dropped instead.
MINIMUM = 0.5
TAIL = 1.4

FADE = "{\\fad(160,160)}"

# BorderStyle 3 paints the box with OutlineColour, not BackColour, and ASS
# alpha runs the other way round from every other format: 00 is opaque. A
# caption has to stay legible over whatever theme the desktop is wearing, so
# both are set nearly opaque above rather than left to contrast with the
# wallpaper of the day.

STYLES = """[Script Info]
ScriptType: v4.00+
PlayResX: %d
PlayResY: %d
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, \
OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, \
ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, \
MarginR, MarginV, Encoding
Style: Keys,%s,46,&H00FFFFFF,&H00FFFFFF,&H0A120E0A,&H0A120E0A,-1,0,0,0,\
100,100,2,0,3,15,0,8,60,60,40,1
Style: Desc,%s,31,&H00F0F0F0,&H00F0F0F0,&H26120E0A,&H26120E0A,0,0,0,0,\
100,100,0,0,3,11,0,8,60,60,40,1
Style: Title,%s,54,&H00FFFFFF,&H00FFFFFF,&H30120E0A,&H30120E0A,-1,0,0,0,\
100,100,3,0,3,22,0,5,140,140,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, \
Text
"""


def timestamp(seconds):
    seconds = max(0.0, seconds)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return "%d:%02d:%05.2f" % (hours, minutes, seconds)


def escape(text):
    """ASS reads braces as override blocks and backslashes as tags."""
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def wrap(text, width=64):
    """libass wraps where it likes; the breaks are put in here instead."""
    lines, line = [], ""
    for word in text.split():
        candidate = (line + " " + word).strip()
        if len(candidate) > width and line:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return "\\N".join(lines)


def spans(cues, first_frame):
    """Each cue runs until the next one, the last one for `TAIL`."""
    out = []
    for index, cue in enumerate(cues):
        if cue.get("keys") is None and cue.get("text") is None:
            continue
        start = cue["t"] - first_frame
        if index + 1 < len(cues):
            end = cues[index + 1]["t"] - first_frame
        else:
            end = start + TAIL
        if end - start >= MINIMUM:
            out.append((cue, start, end - 0.05))
    return out


def events(cues, first_frame):
    lines = []
    for cue, start, end in spans(cues, first_frame):
        head = "Dialogue: 0,%s,%s," % (timestamp(start), timestamp(end))
        if cue.get("chapter") in ("intro", "outro"):
            lines.append("%sTitle,,0,0,0,,%s%s"
                         % (head, FADE, wrap(escape(cue["text"]), 46)))
            continue
        if cue.get("keys"):
            lines.append("%sKeys,,0,0,0,,%s{\\pos(%d,%d)}%s"
                         % (head, FADE, WIDTH // 2, KEYS_Y,
                            escape(cue["keys"])))
        if cue.get("text"):
            y = DESC_Y if cue.get("keys") else KEYS_Y
            lines.append("%sDesc,,0,0,0,,%s{\\pos(%d,%d)}%s"
                         % (head, FADE, WIDTH // 2, y,
                            wrap(escape(cue["text"]))))
    return lines


def first_frame_monotonic(video):
    """The sidecar `-write-first-frame-ts yes` leaves, in seconds."""
    with open(video + ".ts") as handle:
        rows = [line for line in handle if line.strip()]
    return int(rows[-1].split()[0]) / 1e6


def main():
    video = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "raw.mp4")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "demo.mp4")
    font = os.environ.get("DEMO_FONT", "Noto Sans")
    with open(os.path.join(HERE, "cues.jsonl")) as handle:
        cues = [json.loads(line) for line in handle if line.strip()]
    path = os.path.join(HERE, "captions.ass")
    with open(path, "w") as handle:
        handle.write(STYLES % (WIDTH, HEIGHT, font, font, font))
        handle.write("\n".join(events(cues, first_frame_monotonic(video))))
        handle.write("\n")
    print("captions: %s (%d cues)" % (path, len(cues)))
    subprocess.check_call([
        "ffmpeg", "-y", "-loglevel", "warning", "-i", video,
        "-vf", "subtitles=%s" % path,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", out,
    ])
    print("wrote %s" % out)


if __name__ == "__main__":
    main()
