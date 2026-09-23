"""What the machine is doing: how loud it is, how bright, what is playing.

A source rather than a surface - the same shape `snap.py` and `handover.py`
have. There is no socket and no control verb, because nothing here is drawn:
it answers three questions the daemon then puts on a tile.

**Nothing in this module runs a command.** It returns the string to run, and
the daemon submits it to the same worker thread every other slow thing goes
through - a press must never wait on `pactl`. The parsers are pure functions
over canned output, which is what makes them testable without a sound server.

Every command is a setting, so a machine that answers these questions some
other way answers them by editing `[live]` rather than by patching this. The
shipped volume commands deliberately do not go through
`omarchy-audio-output-volume`: that helper always ends in `omarchy-osd`, so
every press from the HUD would raise Omarchy's own overlay *over the tile
showing the same number*, which is the opposite of what putting volume on a
tile is for.
"""

import json
import logging
import re

log = logging.getLogger("omapad")

# What each reading holds, in the shape `CHOSEN` describes a setting: the
# daemon and the menu both ask this rather than either knowing what a volume
# is. `kind` is what a tile may draw it as, and a number carries the arithmetic
# a slider needs.
READINGS = {
    "volume": {
        "kind": "number", "step": 0.05, "min": 0.0, "max": 1.0,
        "unit": "%", "scale": 100,
    },
    "mute": {"kind": "bool"},
    "brightness": {
        "kind": "number", "step": 0.05, "min": 0.0, "max": 1.0,
        "unit": "%", "scale": 100,
    },
    # Its own kind, because what is playing is not a number, a switch or a
    # short list: it is a title, an artist, whether it is running and which
    # way it may still be walked.
    "media": {"kind": "media"},
    # Whether the compositor may let the screen's refresh follow the game's
    # frame rate. A switch rather than Hyprland's four values: which of the
    # "on" ones is meant is the write's business, in `[live] vrr_set`.
    "vrr": {"kind": "bool"},
}

# What a reading may be asked to become. A number takes `up`, `down` or a
# fraction; a switch takes `on`, `off` or `toggle`; the transport takes one of
# its own three words, which are MPRIS's and are passed through.
TRANSPORT = ("playPause", "next", "previous")

# The first percentage `pactl get-sink-volume` prints. Two channels are
# printed and they are the same number in every case that matters.
VOLUME = re.compile(r"(\d+)\s*%")


class LiveError(ValueError):
    pass


def parse_volume(lines):
    """`pactl get-sink-volume` -> 0..1, or None where it said nothing.

    Clamped at the top: a sink may be turned past 100% and a bar cannot draw
    it, so the tile says full rather than lying about the shape of its own
    travel. None rather than zero for no answer at all - silent and unknown
    are not the same thing, and one of them must not overwrite a good value.
    """
    for line in lines:
        found = VOLUME.search(line)
        if found:
            return min(1.0, int(found.group(1)) / 100.0)
    return None


def parse_mute(lines):
    """`pactl get-sink-mute` -> True when it says yes."""
    for line in lines:
        head, separator, tail = line.partition(":")
        if separator and head.strip().lower() == "mute":
            return tail.strip().lower() in ("yes", "1", "true", "on")
    return None


def parse_brightness(lines):
    """The helper prints one number, a percentage of the panel's range."""
    for line in lines:
        text = line.strip().rstrip("%").strip()
        try:
            return max(0.0, min(1.0, float(text) / 100.0))
        except ValueError:
            continue
    return None


def parse_media(lines):
    """`omarchy-shell media status` -> the five things a tile draws.

    Mapped here rather than handed on as it arrives: an MPRIS field name is
    not a payload field name, and a rename upstream must not silently become a
    rename on the wire. Anything that is not one JSON object is None, which
    leaves whatever was read last standing.
    """
    for line in lines:
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            found = json.loads(line)
        except ValueError:
            return None
        if not isinstance(found, dict):
            return None
        return {
            "player": bool(found.get("hasMedia")),
            "playing": bool(found.get("playing")),
            "title": str(found.get("title") or ""),
            "artist": str(found.get("artist") or ""),
            "next": bool(found.get("canGoNext")),
            "previous": bool(found.get("canGoPrevious")),
        }
    return None


def parse_vrr(lines):
    """`hyprctl getoption misc:vrr` -> True for anything but off.

    The option, not the monitor's `vrr` field: that one says whether the
    rate is following a game *right now*, which on the fullscreen-only
    setting is no on the desktop the switch is drawn over - a switch that
    read off the moment it was turned on.
    """
    for line in lines:
        head, separator, tail = line.partition(":")
        if separator and head.strip() == "int":
            try:
                return int(tail.strip()) != 0
            except ValueError:
                return None
    return None


PARSERS = {
    "volume": parse_volume,
    "mute": parse_mute,
    "brightness": parse_brightness,
    "media": parse_media,
    "vrr": parse_vrr,
}


def request(name, raw):
    """Turn `up` or `0.4` or `toggle` into (kind, argument), or raise.

    The same grammar `config.setting_request` gives a `pad:` setting, so a
    button reads the same whichever of the two it is pointed at. Checked here
    so a typo fails `omapad check` rather than a press.
    """
    spec = READINGS.get(name)
    if spec is None:
        raise LiveError(
            "nothing called %r to read (one of %s)"
            % (name, ", ".join(sorted(READINGS)))
        )
    word = str(raw).strip()
    if spec["kind"] == "media":
        if word not in TRANSPORT:
            raise LiveError(
                "media takes %s, not %r" % (" or ".join(TRANSPORT), word)
            )
        return ("do", word)
    if spec["kind"] == "bool":
        if word in ("on", "off"):
            return ("set", word == "on")
        if word == "toggle":
            return ("toggle", None)
        raise LiveError("%s takes on, off or toggle, not %r" % (name, word))
    if word in ("up", "next"):
        return ("step", 1)
    if word in ("down", "prev", "previous"):
        return ("step", -1)
    try:
        value = float(word)
    except ValueError:
        raise LiveError("%s takes a number, not %r" % (name, raw)) from None
    return ("set", clamp(spec, value))


def clamp(spec, value):
    return round(min(max(value, spec["min"]), spec["max"]), 3)


def text(name, value):
    """What a reading is on right now, in the words a tile prints."""
    spec = READINGS.get(name)
    if spec is None or value is None:
        return ""
    if spec["kind"] == "bool":
        return "on" if value else "off"
    if spec["kind"] == "media":
        # Nothing: a tile that runs one of the transport's words is a verb,
        # and replacing its name with the track title would make three tiles
        # say the same thing.
        return ""
    amount = float(value) * spec.get("scale", 1)
    unit = spec.get("unit", "")
    if unit == "%":
        return "%g%%" % round(amount)
    return ("%g %s" % (round(amount, 2), unit)).strip()


class Live:
    """The last answer to each question, and the command that asks it again.

    The generation counter is the whole of the stale-read race: a read started
    before a write can land after it and rewind the bar for a tenth of a
    second, which looks like a flicker nobody can reproduce. A write bumps the
    counter; an answer older than the last write is thrown away.
    """

    def __init__(self, config):
        self.values = {}
        self.generation = 0
        self.configure(config)

    def configure(self, config):
        self.reads = dict(config.live_reads)
        self.writes = dict(config.live_writes)

    def value(self, name):
        """The last thing read, or None where nothing has answered yet."""
        return self.values.get(name)

    def ask(self, name):
        """(command, generation) for one reading, or (None, 0) where it is off.

        A command set to the empty string is a reading this machine does not
        have. Nothing asks, and the tile draws whatever it drew before -
        which, having never been read, is nothing.
        """
        command = self.reads.get(name) or ""
        if not command:
            return (None, 0)
        return (command, self.generation)

    def took(self, name, lines, generation):
        """Record an answer. False where it was overtaken, or said nothing.

        A reading that times out keeps its last value rather than blanking the
        tile: a tile that empties because a helper was slow is worse than one
        that is a second stale, and a helper that hangs must never be able to
        empty the HUD.
        """
        if generation < self.generation:
            return False
        parse = PARSERS.get(name)
        if parse is None:
            return False
        value = parse(lines)
        if value is None:
            return False
        changed = self.values.get(name) != value
        self.values[name] = value
        return changed

    def apply(self, name, asked):
        """(command, value) for one write, or (None, None) where it cannot.

        The value is set here as well as sent, so the tile moves under the
        thumb rather than a helper's round trip later. `generation` is bumped
        with it, which is what makes a read already in flight harmless.
        """
        template = self.writes.get(name) or ""
        spec = READINGS.get(name)
        if not template or spec is None:
            return (None, None)
        kind, argument = asked
        if kind == "do":
            found = self.values.get(name) or {}
            if found and not found.get(argument, True):
                # The player says that way is closed. Said rather than done
                # quietly: `false` here is a value, so the caller can tell it
                # apart from a machine that has no such command at all.
                return (None, False)
            word = argument
            value = None
        else:
            current = self.values.get(name)
            if kind == "set":
                value = argument
            elif kind == "toggle":
                value = not bool(current)
            elif spec["kind"] == "bool":
                value = not bool(current)
            else:
                if current is None:
                    # Nothing has answered yet, so there is no number to step
                    # from. Stepping from a guess would jump the volume to
                    # somewhere nobody asked for.
                    return (None, None)
                value = clamp(spec, float(current) + spec["step"] * argument)
            if value == current and kind != "do":
                # Already there: the end of the travel, or a switch told to be
                # what it is. Nothing to send, and the caller says so.
                return (None, value)
            word = _word(spec, value)
        self.generation += 1
        if value is not None:
            self.values[name] = value
        return (template.replace("%1", word), value)


def _word(spec, value):
    """How a value is written into a command.

    A percentage rather than a fraction, because every helper these templates
    reach is a command-line one and those all count in whole percent.
    """
    if spec["kind"] == "bool":
        return "1" if value else "0"
    return "%d" % round(float(value) * spec.get("scale", 1))
