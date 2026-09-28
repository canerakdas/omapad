#!/usr/bin/env python3
"""Write the sounds a press makes into `sounds/`.

    python3 assets/sounds.py
    python3 assets/sounds.py --measure DIR   # how loud a pack of your own is

Synthesised rather than recorded, and checked in like the badges are, for the
same three reasons. A sample somebody recorded is a licence to carry and a
file nobody can edit; these are a hundred lines of arithmetic, so changing
what a commit sounds like is changing a number here and running this again.
What they are is two bars, a marimba and a vibraphone, each modelled with
its mallet, with every cue a note or two on one of them. They cost
about 70 kB together, against a sample pack's megabyte. And a generated file
that is committed shows up in a diff when the numbers move, which
`tests/test_assets.py` is what makes binding.

They are placeholders in the sense that a drawn badge is: correct, shipped,
and replaceable by anything with the same name. Point `[sound] pack` at a
directory of your own `move.wav`, `next.wav`, `show.wav` and the rest of
`sound.VOICES` and nothing here is loaded at all.

**Why these are quiet, short and low.** They are heard over whatever is
playing rather than instead of it - a film, a game, a track - and the pad
makes one every time a thumb moves. A UI sound earns its place by being
noticed and not listened to, which means: under 200 ms, no step that clicks
the speaker, a ring that is down before the next press, and nothing whose
loudness lives below what a television's small drivers can produce.
Everything below is one of those four decisions.

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

# The cues, each as a phrase played on a bar: a note, a pair of notes or a
# chord.
#
#   ms      how long the whole thing lasts, the ring included
#   notes   (onset in ms, frequency in Hz, how hard it is struck relative
#           to the others in the cue)
#   bar     optional: "soft" or "hard" for a vibraphone bar struck with
#           that mallet (see `VIBRAPHONE`); without it, the marimba
#   swell   optional: ms the cue spends rising from silence, for the one
#           voice that arrives rather than lands
#   dull    optional: a low-pass in Hz over the whole thing
#   lufs    how loud it is, measured as a television hears it (see above). In
#           `sound.VOICES` order they rise, because that order is what each
#           costs, two apart at the least; a pair that is one gesture in two
#           directions shares its level
#
# Two instruments, and the line between them is Brewster's rule for earcons
# read at the level of families: members of one share a timbre and differ
# in pitch and contour, and two kinds of thing get two families. Walking -
# the move and the page turns - and the tick are the marimba, dry and
# short, because they happen many times a minute. What happens *to* a
# surface - it arrives, a press is taken, it is left, it will go no
# further - is the vibraphone, the marimba's metal cousin: the same bar,
# the same mallets, a longer ring. The marimba in those four was heard as
# the walk repeating itself, and the vibraphone was chosen by ear (101).
#
# The notes are D, E, F sharp and A, the D major pentatonic without its B:
# any two of them sounding over each other is consonant, so a cue that
# lands on the tail of the last one is never a wrong note. What a cue means
# is carried by where it sits and which way it goes, never by a pitch
# sliding: a glide on a struck note is the sound of a water drop, and was
# heard as one.
VOICES = {
    # A step of the selection: one high note, the shortest cue here,
    # because it happens six times in a second while somebody crosses a
    # page and faster still once a held direction has ramped. Past 45 ms it
    # would be two notes sounding at once on every step.
    "move": {"ms": 45, "notes": ((0, 659.3, 1.0),), "lufs": -50.0},
    # A page turned - the menu's bar, the guide, the keyboard's pages. The
    # neighbours of the move's note, F sharp for the next page and D for
    # the previous one, so the room hears which way the page went: what
    # Xbox's MoveNext and MovePrevious are for. Heard and never felt, like
    # the move, and for the move's reason - a shoulder held down turns page
    # after page.
    "next": {"ms": 60, "notes": ((0, 740.0, 1.0),), "lufs": -48.0},
    "prev": {"ms": 60, "notes": ((0, 587.3, 1.0),), "lufs": -48.0},
    # A surface arriving - the menu, the quick menu, the keyboard, the guide.
    # A low D and its octave on the vibraphone, soft, swelling in over
    # `swell`: the deepest thing a surface says and the slowest to arrive,
    # which is what an arrival is next to a press. A rolled D, F sharp, A
    # on the marimba was here first and was heard as a notification (101).
    "show": {
        "ms": 180, "bar": "soft", "swell": 25.0,
        "notes": ((0, 293.7, 1.0), (0, 587.3, 0.5)), "lufs": -46.0,
    },
    # A press that did something. The motor's own word: one note, a fifth
    # below the move's D, so a press reads as heavier than the walk that
    # got there.
    "tick": {"ms": 70, "notes": ((0, 440.0, 1.0),), "lufs": -42.0},
    # The end of the travel - a selection with nowhere further to go, a
    # slider against its own maximum. Two quick low strokes, the second
    # softer - the shape of *no* in every language that has a sound for it
    # - soft and muffled, so it refuses without scolding.
    #
    # Each stroke is the lowest D and its octave, the octave the stronger,
    # and that is for the television: a set's drivers barely play 147 Hz,
    # and the ear rebuilds a fundamental from what sits above it, so the set
    # plays the octave and the room still hears the low note.
    "edge": {
        "ms": 125, "bar": "soft", "dull": 1500.0,
        "notes": ((0, 146.8, 0.9), (0, 293.7, 1.0),
                  (55, 146.8, 0.7), (55, 293.7, 0.8)),
        "lufs": -39.0,
    },
    # Taken, kept, fired. D and the A above it struck together, hard, on
    # the vibraphone: an open fifth is the most settled sound two notes
    # make, and the hard mallet is the brightest stroke in the set, which
    # is the difference between a sound that happened and one that
    # concluded.
    "commit": {
        "ms": 160, "bar": "hard",
        "notes": ((0, 587.3, 0.8), (0, 880.0, 0.7)), "lufs": -36.0,
    },
    # Back a level, out of a page, off a control, out of a countdown. One
    # note, the A below the commit's D, soft and muffled: where the commit
    # rings out above D, the back sits under it and says nothing more. The
    # commit's two notes falling were here first and were heard as wrong
    # (101) - a falling figure reads as an error, and leaving is not one.
    #
    # It is the tick's note, and told from it by the instrument: the tick
    # is a hard stroke on the marimba, this a soft one on the vibraphone
    # with its brightness taken off, and two dB under it, which is where
    # `sound.VOICES` puts it - a press that took you somewhere costs more
    # than one that took you back.
    "back": {
        "ms": 110, "bar": "soft", "dull": 2500.0,
        "notes": ((0, 440.0, 1.0),), "lufs": -44.0,
    },
}

# The bar: its modes as (ratio to the note, share, ms to fall by 1/e at
# `REFERENCE_HZ`). A marimba bar is carved underneath so its overtones sit
# near two octaves and a bit over three above the note rather than where a
# plain bar would put them - that tuning is what makes it a marimba and
# not a woodblock.
BAR = ((1.0, 1.0, 55.0), (3.93, 0.35, 14.0), (9.2, 0.12, 5.0))

# The vibraphone's bar, per mallet, as (ratio, share, ms to fall by 1/e).
# Aluminium tuned to 1, 4 and 10, and ringing for most of a second, which is
# what separates it from the marimba more than anything; the cue's own
# length and `FADE_OUT_MS` are what stop it. Its mallet is given as which
# overtones it wakes rather than as a push, because a vibraphone's decays
# do not follow the pitch the way a wooden bar's do: the soft yarn head
# barely reaches the fourth harmonic and never the tenth.
VIBRAPHONE = {
    "soft": ((1.0, 1.0, 400.0), (4.0, 0.12, 50.0)),
    "hard": ((1.0, 1.0, 400.0), (4.0, 0.3, 50.0), (10.0, 0.06, 15.0)),
}

# Higher bars ring shorter, as real ones do: every decay is scaled by
# (REFERENCE_HZ / note) ** RING_SLOPE.
REFERENCE_HZ = 440.0
RING_SLOPE = 0.5

# The resonator tube under the bar: it holds the note itself and nothing
# above it, a hair sharp of the bar, (share, ms). It is driven by the bar,
# so it comes up over `TUBE_RISE_MS` rather than being struck - which is
# the bloom that separates a marimba from a xylophone.
TUBE = (0.5, 110.0)
TUBE_SHARP = 1.003
TUBE_RISE_MS = 4.0

# The mallet, as a half-sine push of `MALLET_MS` against the bar. The
# length of that push is the whole of how hard the mallet is: a pulse that
# long has little energy above roughly 1 / MALLET_MS, so a soft yarn head
# (3.5 ms) leaves the upper modes almost silent and a hard one (0.9 ms)
# rings them. Hard was chosen by ear.
# `THUMP` is how much of the push itself is heard - the wood of the
# mallet, not the bar.
MALLET_MS = 0.9
THUMP = 0.12

# Nothing is rendered above this: well past what any mode here reaches
# except the top partial of the highest note, and there it would be over
# Nyquist's comfort on a 44.1 kHz file.
TOP_HZ = 15000.0

# The ends of every cue. A sine starts at zero, but the thump does not
# quite; 0.4 ms is under what anybody hears as an attack and keeps the
# stroke sharp. The 15 ms out is so the tube, still ringing when a cue's
# length is up, is faded rather than cut, which would be a click.
FADE_IN_MS = 0.4
FADE_OUT_MS = 15.0


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


def _low_pass(samples, hz):
    """A first-order low-pass at `hz`."""
    k = math.exp(-2.0 * math.pi * hz / RATE)
    out = []
    low = 0.0
    for x in samples:
        low = (1.0 - k) * x + k * low
        out.append(low)
    return out


def _mallet(freq):
    """How much of the mallet's push reaches `freq`: the magnitude of a
    half-sine pulse's spectrum there, 1 at DC."""
    x = 2.0 * freq * MALLET_MS / 1000.0
    if abs(x - 1.0) < 1e-9:
        return math.pi / 4.0
    return abs(math.cos(math.pi * freq * MALLET_MS / 1000.0) / (1.0 - x * x))


def strike(freq, count):
    """One note on the marimba, `count` samples long, at an arbitrary
    level."""
    scale = (REFERENCE_HZ / freq) ** RING_SLOPE
    out = [0.0] * count
    for ratio, share, decay in BAR:
        mode = freq * ratio
        if mode > TOP_HZ:
            continue
        weight = share * _mallet(mode) / _mallet(freq)
        tau = decay * scale / 1000.0 * RATE
        step = 2.0 * math.pi * mode / RATE
        for n in range(count):
            out[n] += weight * math.exp(-n / tau) * math.sin(step * n)
    share, decay = TUBE
    tau = decay * scale / 1000.0 * RATE
    rise = TUBE_RISE_MS / 1000.0 * RATE
    step = 2.0 * math.pi * freq * TUBE_SHARP / RATE
    for n in range(count):
        out[n] += (share * (1.0 - math.exp(-n / rise))
                   * math.exp(-n / tau) * math.sin(step * n))
    width = max(2, int(RATE * MALLET_MS / 1000.0))
    for n in range(min(width, count)):
        out[n] += THUMP * math.sin(math.pi * n / width)
    return out


def ring(freq, count, mallet):
    """One note on the vibraphone, struck with the `mallet` of
    `VIBRAPHONE`, at an arbitrary level. No tube and no thump: the tubes
    under a vibraphone are what its motor turns, and without the motor they
    add only what the long decay already is."""
    out = [0.0] * count
    for ratio, share, decay in VIBRAPHONE[mallet]:
        mode = freq * ratio
        if mode > TOP_HZ:
            continue
        tau = decay / 1000.0 * RATE
        step = 2.0 * math.pi * mode / RATE
        for n in range(count):
            out[n] += share * math.exp(-n / tau) * math.sin(step * n)
    return out


def shape(spec):
    """One cue at an arbitrary level, as floats: its notes laid over each
    other, before anything decides how loud it is."""
    count = max(1, int(RATE * spec["ms"] / 1000.0))
    out = [0.0] * count
    bar = spec.get("bar")
    for onset, freq, share in spec["notes"]:
        start = int(RATE * onset / 1000.0)
        if bar:
            note = ring(freq, count - start, bar)
        else:
            note = strike(freq, count - start)
        for n, sample in enumerate(note):
            out[start + n] += share * sample
    if "swell" in spec:
        rise = RATE * spec["swell"] / 1000.0
        out = [sample * min(1.0, n / rise) for n, sample in enumerate(out)]
    if "dull" in spec:
        # Twice, for a second-order slope: one pole leaves a stroke's top
        # bright enough to click.
        out = _low_pass(_low_pass(out, spec["dull"]), spec["dull"])
    fade_in = max(1, int(RATE * FADE_IN_MS / 1000.0))
    fade_out = max(1, int(RATE * FADE_OUT_MS / 1000.0))
    for n in range(min(fade_in, count)):
        out[n] *= n / float(fade_in)
    for n in range(min(fade_out, count)):
        out[count - 1 - n] *= n / float(fade_out)
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
