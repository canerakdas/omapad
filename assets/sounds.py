#!/usr/bin/env python3
"""Write the five sounds a press makes into `sounds/`.

    python3 assets/sounds.py

Synthesised rather than recorded, and checked in like the badges are, for the
same three reasons. A sample somebody recorded is a licence to carry and a
file nobody can edit; these are eighty lines of arithmetic, so changing what a
commit sounds like is changing a number here and running this again. They cost
about 14 kB together, against a sample pack's megabyte. And a generated file
that is committed shows up in a diff when the numbers move, which
`tests/test_assets.py` is what makes binding.

They are placeholders in the sense that a drawn badge is: correct, shipped,
and replaceable by anything with the same name. Point `[sound] pack` at a
directory of your own `move.wav`, `tick.wav`, `edge.wav`, `commit.wav`,
`back.wav` and nothing here is loaded at all.

**Why these are quiet, short and low.** They are heard over whatever is
playing rather than instead of it - a film, a game, a track - and the pad
makes one every time a thumb moves. A UI sound earns its place by being
noticed and not listened to, which means: under 100 ms, no attack that clicks
the speaker, a decay that is over before the next press, and a pitch low
enough that a television's small drivers can actually produce it. Everything
below is one of those four decisions.
"""

import math
import os
import struct
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
SOUNDS = os.path.join(HERE, "sounds")

# CD rate rather than 48 kHz. Nothing here goes near 20 kHz, every sound
# server on this desktop resamples anyway, and it is a tenth smaller on disk.
RATE = 44100
# One channel: a cue that came from the left would be saying something about
# where it happened, and none of these happened anywhere.
CHANNELS = 1
WIDTH = 2

# How loud the file itself is, before `[sound] volume` touches it. Well under
# full scale on purpose: these are mixed over whatever is already playing, and
# a UI sound that has to be turned down by the person who wanted it is a
# sound that was mastered wrong.
PEAK = 0.22

# The cues, each as a stack of partials and an envelope.
#
#   ms      how long the whole thing lasts, decay included
#   partials  (frequency in Hz, how much of the peak it gets)
#   bend    where the fundamental ends up, as a ratio, swept over the sound
#   decay   how many time constants fit in `ms` - higher is more percussive
#   level   the cue's own share of PEAK, which is what makes a move quieter
#           than a commit without either being remastered
#
# The frequencies are four notes and a thud rather than round numbers: the
# three that a press produces in a row - move, move, commit - are a fifth
# apart, so a hand walking a menu and pressing something sounds like one
# instrument rather than three unrelated beeps.
VOICES = {
    # A step of the selection. The quietest and shortest thing here by a wide
    # margin, because it is the one that happens six times in a second while
    # somebody crosses a page, and anything with a tail turns that into a
    # chord.
    "move": {
        "ms": 16, "partials": ((1174.7, 1.0), (2349.3, 0.18)),
        "bend": 1.0, "decay": 5.0, "level": 0.45,
    },
    # A press that did something. The motor's own word, and the sound sits
    # just under it: a fifth below the move, so a press reads as heavier than
    # the walk that got there.
    "tick": {
        "ms": 28, "partials": ((783.99, 1.0), (1568.0, 0.22)),
        "bend": 1.0, "decay": 4.5, "level": 0.7,
    },
    # The end of the travel - a selection with nowhere further to go, a
    # slider against its own maximum. Low, dull and with no upper partial at
    # all, so it reads as something stopping rather than as a note.
    "edge": {
        "ms": 55, "partials": ((174.61, 1.0), (261.63, 0.12)),
        "bend": 0.94, "decay": 3.2, "level": 0.8,
    },
    # Taken, kept, fired. The only one allowed a shape rather than a pitch:
    # it bends up a fourth over its own length, which is the difference
    # between a sound that happened and a sound that concluded.
    "commit": {
        "ms": 90, "partials": ((587.33, 1.0), (1174.7, 0.3), (1760.0, 0.1)),
        "bend": 1.335, "decay": 3.0, "level": 1.0,
    },
    # Back a level, out of a page, off a control, out of a countdown. The
    # commit's own note and the commit's own interval, **falling**: it starts
    # where that one starts and bends down the fourth that one bends up. A
    # cancel is not a different instrument from a confirm - it is the same
    # gesture going the other way, and a pair that share a note and mirror an
    # interval is how a room hears which of the two happened without anybody
    # being taught the difference.
    #
    # Softer and shorter than the commit as well, because leaving is the
    # smaller event: nothing was decided, and a sound that made as much of
    # itself as the decision would be the surface arguing with you about it.
    "back": {
        "ms": 70, "partials": ((587.33, 1.0), (1174.7, 0.18)),
        "bend": 0.749, "decay": 3.4, "level": 0.6,
    },
}

# How much of the front of a sound is spent coming up from silence, as a
# share of its length. A waveform that starts at full amplitude steps the
# speaker cone and that step is the click a cheap set makes audible; 3 ms is
# under what anybody hears as an attack and over what any driver complains
# about. A share rather than a fixed 3 ms because the move is 16 ms long and
# a fifth of it is the right fade there too.
ATTACK = 0.12


def render(spec):
    """One cue, as floats in -1..1."""
    count = max(1, int(RATE * spec["ms"] / 1000.0))
    attack = max(1, int(count * ATTACK))
    weight = sum(share for _, share in spec["partials"])
    out = []
    # The phase of each partial is integrated rather than computed from
    # `t * frequency`, because the fundamental is being bent: multiplying a
    # moving frequency by an absolute time sweeps the phase at the wrong rate
    # and the sound arrives a semitone out of where the numbers say.
    phases = [0.0] * len(spec["partials"])
    for n in range(count):
        where = n / float(count)
        bend = 1.0 + (spec["bend"] - 1.0) * where
        # Exponential, so it is still decaying at the end rather than being
        # cut off there - a sound that stops is a click at the other end.
        envelope = math.exp(-spec["decay"] * where)
        if n < attack:
            envelope *= n / float(attack)
        sample = 0.0
        for index, (freq, share) in enumerate(spec["partials"]):
            phases[index] += 2.0 * math.pi * freq * bend / RATE
            sample += math.sin(phases[index]) * share
        out.append(sample / weight * envelope * PEAK * spec["level"])
    return out


def write(path, samples):
    """One WAV, 16-bit mono. Rounded rather than truncated: truncation is a
    DC offset towards zero, and a file of those is a quiet thump on a set
    that has to move its cone back afterwards."""
    frames = b"".join(
        struct.pack("<h", max(-32768, min(32767, int(round(s * 32767)))))
        for s in samples
    )
    with wave.open(path, "wb") as out:
        out.setnchannels(CHANNELS)
        out.setsampwidth(WIDTH)
        out.setframerate(RATE)
        out.writeframes(frames)


def main():
    if not os.path.isdir(SOUNDS):
        os.makedirs(SOUNDS)
    for name in sorted(VOICES):
        path = os.path.join(SOUNDS, "%s.wav" % name)
        write(path, render(VOICES[name]))
        print("%s  %d ms" % (os.path.relpath(path, HERE), VOICES[name]["ms"]))


if __name__ == "__main__":
    main()
