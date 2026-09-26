#!/usr/bin/env python3
"""Write the sounds a press makes into `sounds/`.

    python3 assets/sounds.py
    python3 assets/sounds.py --measure DIR   # how loud a pack of your own is

Synthesised rather than recorded, and checked in like the badges are, for the
same three reasons. A sample somebody recorded is a licence to carry and a
file nobody can edit; these are eighty lines of arithmetic, so changing what a
commit sounds like is changing a number here and running this again. They cost
about 14 kB together, against a sample pack's megabyte. And a generated file
that is committed shows up in a diff when the numbers move, which
`tests/test_assets.py` is what makes binding.

They are placeholders in the sense that a drawn badge is: correct, shipped,
and replaceable by anything with the same name. Point `[sound] pack` at a
directory of your own `move.wav`, `next.wav`, `show.wav` and the rest of
`sound.VOICES` and nothing here is loaded at all.

**Why these are quiet, short and low.** They are heard over whatever is
playing rather than instead of it - a film, a game, a track - and the pad
makes one every time a thumb moves. A UI sound earns its place by being
noticed and not listened to, which means: under 100 ms, no attack that clicks
the speaker, a decay that is over before the next press, and a pitch low
enough that a television's small drivers can actually produce it. Everything
below is one of those four decisions.

**How loud each one is, is measured rather than guessed.** Each voice names a
loudness in LUFS (ITU-R BS.1770, the meter every broadcaster's loudness rule
is written against) and is scaled until it measures that - *as a television
hears it*, through `TV_CORNER` below. A share of a peak level was what set
them before, and a peak is not what an ear hears: a 175 Hz bump and a 1.2 kHz
tick at the same peak are two different loudnesses on paper, and further apart
again on a set with three-inch drivers. Measured that way, the edge had come
out as quiet as the tick it is meant to stand over, and the back louder than
the tick `sound.VOICES` says it costs less than.

The meter is written out here rather than taken from a library, because this
tree takes none (python.md 1.2). What it leaves out is the rest of BS.1770 -
channel weights and the gating - and that is the whole of it for a mono file
shorter than one block: one block has nothing to gate, and one channel
nothing to weight.
"""

import math
import os
import struct
import sys
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

# The loudest a sample may be, before `[sound] volume` touches it. Well under
# full scale on purpose: these are mixed over whatever is already playing, and
# a UI sound that has to be turned down by the person who wanted it is a
# sound that was mastered wrong. It is a ceiling now rather than the level -
# each voice's `lufs` is the level - and `tests/test_sound.py` holds every
# file under it.
PEAK = 0.22

# The window a cue is measured over: BS.1770's momentary block, 400 ms. Every
# one of these is shorter, so each is measured as its energy spread over the
# same block - which is what makes a 16 ms tick and a 90 ms commit comparable
# at all, and roughly what an ear does with a sound that short.
BLOCK = 0.4

# K-weighting, BS.1770's own two stages: a shelf for the head and a high-pass
# for how little the ear makes of the bottom octave. Given as the analog
# design rather than the standard's table of coefficients, because the table
# is for 48 kHz and these files are not; at 48 kHz this reproduces the table
# to the last printed digit, which the tests check.
SHELF_HZ = 1681.974450955533
SHELF_GAIN_DB = 3.999843853973347
SHELF_Q = 0.7071752369554196
SHELF_BAND = 0.4996667741545416
LOWCUT_HZ = 38.13547087602444
LOWCUT_Q = 0.5003270373238773

# The television. A set's own drivers are a few centimetres across and give
# up somewhere around 150-250 Hz, steeply; a cue that is loud enough on a
# desk's speakers can be half gone on the set it was made for. Modelled as a
# fourth-order Butterworth high-pass at 200 Hz - the middle of that range and
# the slope of a small sealed driver - and every `lufs` below is measured
# through it. Headphones and a soundbar hear the same files a little louder at
# the bottom, which only ever costs the edge, and in its favour.
TV_CORNER = 200.0
TV_ORDER = 4

# The cues, each as a stack of partials and an envelope.
#
#   ms      how long the whole thing lasts, decay included
#   partials  (frequency in Hz, how much of the peak it gets)
#   bend    where the fundamental ends up, as a ratio, swept over the sound
#   decay   how many time constants fit in `ms` - higher is more percussive
#   attack  optional: the share of `ms` spent coming up from silence, where
#           the voice wants other than `ATTACK`
#   lufs    how loud it is, measured as a television hears it (see above). In
#           `sound.VOICES` order they rise, because that order is what each
#           costs, two apart at the least; a pair that is one gesture in two
#           directions shares its level
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
        "bend": 1.0, "decay": 5.0, "lufs": -50.0,
    },
    # A page turned - the menu's bar, the guide, the keyboard's pages. The
    # move's own note, a little longer, bent a whole tone up for the next
    # page and down for the previous one, so the room hears which way the
    # page went: what Xbox's MoveNext and MovePrevious are for. Heard and
    # never felt, like the move, and for the move's reason - a shoulder held
    # down turns page after page.
    "next": {
        "ms": 34, "partials": ((1174.7, 1.0), (2349.3, 0.15)),
        "bend": 1.1225, "decay": 4.5, "lufs": -48.0,
    },
    "prev": {
        "ms": 34, "partials": ((1174.7, 1.0), (2349.3, 0.15)),
        "bend": 0.8909, "decay": 4.5, "lufs": -48.0,
    },
    # A surface arriving - the menu, the quick menu, the keyboard, the guide.
    # The back upside down: it rises the fourth the back falls, from A to the
    # D every sound inside the surface starts on, so opening a thing and
    # putting it away are one gesture read in two directions, the way a
    # commit and a back are. And it swells rather than strikes: a long
    # attack is what tells it from the commit's rising fourth, because a
    # surface arriving is not a press landing.
    "show": {
        "ms": 85, "partials": ((440.0, 1.0), (880.0, 0.2)),
        "bend": 1.3348, "decay": 2.6, "attack": 0.35, "lufs": -46.0,
    },
    # A press that did something. The motor's own word, and the sound sits
    # just under it: a fifth below the move, so a press reads as heavier than
    # the walk that got there.
    "tick": {
        "ms": 28, "partials": ((783.99, 1.0), (1568.0, 0.22)),
        "bend": 1.0, "decay": 4.5, "lufs": -42.0,
    },
    # The end of the travel - a selection with nowhere further to go, a
    # slider against its own maximum. Low, dull and with nothing bright
    # above it, so it reads as something stopping rather than as a note.
    #
    # Its own octave and fifth are strong, and that is for the television:
    # a set's drivers barely play 175 Hz, and with only the fundamental the
    # edge had to be pushed until it was the loudest thing on a desk before
    # a set heard it at all. The ear rebuilds a fundamental from the
    # harmonics above it, so the set plays the octave and the room still
    # hears the low note - and nothing above 350 Hz keeps it dull.
    "edge": {
        "ms": 55,
        "partials": ((174.61, 1.0), (261.63, 0.2), (349.23, 0.45)),
        "bend": 0.94, "decay": 3.2, "lufs": -39.0,
    },
    # Taken, kept, fired. The only one allowed a shape rather than a pitch:
    # it bends up a fourth over its own length, which is the difference
    # between a sound that happened and a sound that concluded.
    "commit": {
        "ms": 90, "partials": ((587.33, 1.0), (1174.7, 0.3), (1760.0, 0.1)),
        "bend": 1.335, "decay": 3.0, "lufs": -36.0,
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
    # Under the tick too, which is where `sound.VOICES` puts it: a press
    # that took you somewhere costs more than one that took you back.
    "back": {
        "ms": 70, "partials": ((587.33, 1.0), (1174.7, 0.18)),
        "bend": 0.749, "decay": 3.4, "lufs": -44.0,
    },
}

# How much of the front of a sound is spent coming up from silence, as a
# share of its length. A waveform that starts at full amplitude steps the
# speaker cone and that step is the click a cheap set makes audible; 3 ms is
# under what anybody hears as an attack and over what any driver complains
# about. A share rather than a fixed 3 ms because the move is 16 ms long and
# a fifth of it is the right fade there too.
ATTACK = 0.12


def _biquad(samples, b, a):
    """One second-order section, direct form I. `a[0]` is taken as 1."""
    b0, b1, b2 = b
    a1, a2 = a[1], a[2]
    x1 = x2 = y1 = y2 = 0.0
    out = []
    for x in samples:
        y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, x, y1, y
        out.append(y)
    return out


def k_weighting(rate):
    """BS.1770's two stages at `rate`, as ((b, a), (b, a))."""
    k = math.tan(math.pi * SHELF_HZ / rate)
    high = 10.0 ** (SHELF_GAIN_DB / 20.0)
    band = high ** SHELF_BAND
    a0 = 1.0 + k / SHELF_Q + k * k
    shelf = (
        ((high + band * k / SHELF_Q + k * k) / a0,
         2.0 * (k * k - high) / a0,
         (high - band * k / SHELF_Q + k * k) / a0),
        (1.0, 2.0 * (k * k - 1.0) / a0, (1.0 - k / SHELF_Q + k * k) / a0),
    )
    k = math.tan(math.pi * LOWCUT_HZ / rate)
    a0 = 1.0 + k / LOWCUT_Q + k * k
    lowcut = (
        (1.0, -2.0, 1.0),
        (1.0, 2.0 * (k * k - 1.0) / a0, (1.0 - k / LOWCUT_Q + k * k) / a0),
    )
    return (shelf, lowcut)


def television(rate):
    """`TV_CORNER`'s high-pass as second-order sections, Butterworth: the
    poles of one filter of `TV_ORDER`, split into pairs."""
    w = 2.0 * math.pi * TV_CORNER / rate
    sections = []
    for pair in range(TV_ORDER // 2):
        q = 1.0 / (2.0 * math.cos(math.pi * (2 * pair + 1) / (2 * TV_ORDER)))
        alpha = math.sin(w) / (2.0 * q)
        c = math.cos(w)
        a0 = 1.0 + alpha
        sections.append((
            ((1.0 + c) / 2.0 / a0, -(1.0 + c) / a0, (1.0 + c) / 2.0 / a0),
            (1.0, -2.0 * c / a0, (1.0 - alpha) / a0),
        ))
    return tuple(sections)


def loudness(samples, rate=RATE, heard=True):
    """LUFS of a cue over one `BLOCK`, K-weighted - and through the
    television first unless `heard` is False, which is plain BS.1770."""
    count = max(len(samples), int(round(rate * BLOCK)))
    signal = list(samples) + [0.0] * (count - len(samples))
    stages = k_weighting(rate)
    if heard:
        stages = television(rate) + stages
    for b, a in stages:
        signal = _biquad(signal, b, a)
    power = sum(x * x for x in signal) / count
    if power <= 0.0:
        return float("-inf")
    return -0.691 + 10.0 * math.log10(power)


def shape(spec):
    """One cue at an arbitrary level, as floats: the partials, the bend and
    the envelope, before anything decides how loud it is."""
    count = max(1, int(RATE * spec["ms"] / 1000.0))
    attack = max(1, int(count * spec.get("attack", ATTACK)))
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
        out.append(sample / weight * envelope)
    return out


def render(spec):
    """One cue, as floats in -1..1, scaled to measure its own `lufs`."""
    out = shape(spec)
    gain = 10.0 ** ((spec["lufs"] - loudness(out)) / 20.0)
    return [sample * gain for sample in out]


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


def read(path):
    """A 16-bit WAV as floats, and its rate. Several channels are averaged:
    the panel plays whatever it is given, but a pack is measured the way the
    shipped set is made, as one channel."""
    with wave.open(path) as handle:
        rate = handle.getframerate()
        channels = handle.getnchannels()
        if handle.getsampwidth() != WIDTH:
            raise ValueError("%s is not 16-bit" % path)
        frames = handle.readframes(handle.getnframes())
    values = struct.unpack("<%dh" % (len(frames) // WIDTH), frames)
    samples = [
        sum(values[n:n + channels]) / float(channels) / 32768.0
        for n in range(0, len(values), channels)
    ]
    return samples, rate


def measure(directory):
    """Print how far each file of a pack is from the voice it stands in for,
    as the gain that would put it there. A file that is not there is the
    shipped one, so it is skipped rather than reported."""
    for name in sorted(VOICES, key=lambda name: VOICES[name]["lufs"]):
        path = os.path.join(directory, "%s.wav" % name)
        if not os.path.isfile(path):
            print("%-6s  not in the pack, the shipped one plays" % name)
            continue
        samples, rate = read(path)
        heard = loudness(samples, rate)
        peak = max(abs(sample) for sample in samples) if samples else 0.0
        print("%-6s  %6.1f LUFS, wants %6.1f: %+5.1f dB, %4d ms, peak %.2f"
              % (name, heard, VOICES[name]["lufs"],
                 VOICES[name]["lufs"] - heard,
                 len(samples) * 1000.0 / rate, peak))


def main(argv):
    if len(argv) == 2 and argv[0] == "--measure":
        measure(os.path.expanduser(argv[1]))
        return
    if not os.path.isdir(SOUNDS):
        os.makedirs(SOUNDS)
    for name in sorted(VOICES):
        path = os.path.join(SOUNDS, "%s.wav" % name)
        write(path, render(VOICES[name]))
        print("%s  %d ms  %.1f LUFS"
              % (os.path.relpath(path, HERE), VOICES[name]["ms"],
                 VOICES[name]["lufs"]))


if __name__ == "__main__":
    main(sys.argv[1:])
