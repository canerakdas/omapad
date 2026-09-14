"""What the machine itself is doing: how busy, how full, how hot, how loud.

A source rather than a surface - the same shape `live.py` and `snap.py` have.
There is no socket and no control verb, because nothing here is drawn: it
answers a handful of questions the daemon then puts on a tile, and `hud.py`
decides where that tile goes.

`live.py` is the other half of this and deliberately not the same thing: that
one is what the *desktop* is doing - how loud it is, how bright, what is
playing - and every one of its answers is a helper's. These are what the
*kernel* is publishing about the machine underneath, so almost all of them are
a file read rather than a command, and a file read is not something to spawn a
shell for twice a second.

**Where each reading comes from is a setting**, in one grammar - `<how>:<where>`
- because there is no answer here that is true of every machine. Which chip
publishes a temperature, whether the graphics card publishes a load at all,
whether anything on this desktop knows a game's frame rate: all three differ
between two laptops of the same year. A reading whose source is empty is one
this machine does not have, nothing asks for it, and the tile is not drawn.

The parsers are pure functions over canned text, which is what makes them
testable without the machine they describe.
"""

import glob
import os
import re

# What each reading is, in the shape `live.READINGS` and `config.CHOSEN`
# describe a thing that can be read. `kind` is what a tile may draw it as -
# one kind, `reading`, because none of these can be set and a tile that can
# only print is the one control that is not a control.
#
# `full` is the top of the scale where there is one, and it is what lets a
# tile draw a bar as well as a number: a percentage is somewhere along a
# known travel, and a temperature is not. `divide` is the kernel's own unit
# against the one a person reads.
READINGS = {
    # A share of the time since the last read, so 0.37 is 37% of one interval
    # across every core the machine has.
    "cpu": {"kind": "reading", "unit": "%", "scale": 100, "full": 1.0},
    "memory": {"kind": "reading", "unit": "%", "scale": 100, "full": 1.0},
    "disk": {"kind": "reading", "unit": "%", "scale": 100, "full": 1.0},
    # hwmon publishes a temperature in thousandths of a degree and a fan in
    # whole revolutions. Both are the kernel's ABI rather than a preference,
    # which is why they are here and not in the config.
    "temperature": {"kind": "reading", "unit": "°C", "divide": 1000.0},
    "fan": {"kind": "reading", "unit": "rpm"},
    # The two with no general answer. What they count in is a setting,
    # because what a person points them at decides it.
    "gpu": {"kind": "reading", "unit": "%"},
    "fps": {"kind": "reading", "unit": "fps"},
}

# How a reading is fetched. The word before the colon in a source.
#
#   proc:<file>           one of the two /proc files this module can read
#   mount:<path>          a filesystem, named by any path on it
#   hwmon:<chip>/<file>   /sys/class/hwmon, by the chip's own name
#   file:<path>           one number, from one file
#   cmd:<command>         a helper that prints one number
#
# `file:` and `cmd:` are the two that can reach anything, and they are why
# this list does not need to grow every time a driver publishes something new.
HOWS = ("proc", "mount", "hwmon", "file", "cmd")

# The /proc files with a parser here. Anything else under /proc is a `file:`
# source: those two are parsed because neither is one number.
PROC_FILES = ("stat", "meminfo")

# Where the kernel publishes its sensors. Not a setting: it is where the hwmon
# class is mounted, which is the same on every Linux, and a machine that moved
# it has bigger questions than this file.
HWMON = "/sys/class/hwmon"

# The first number in a line, however the rest of the line is punctuated. A
# helper prints `74`, `74.0` or `74 fps` and all three mean the same thing.
NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


class SysinfoError(ValueError):
    pass


def source(spec, where="sysinfo"):
    """Parse one `<how>:<where>` source, or None where it is empty.

    Checked when the config is read rather than at the poll, for the reason
    every other action is: `omapad check` should name a source that cannot
    work, instead of a HUD with a tile that never fills and never says why.
    """
    text = str(spec or "").strip()
    if not text:
        return None
    how, separator, rest = text.partition(":")
    how, rest = how.strip(), rest.strip()
    if not separator or how not in HOWS:
        raise SysinfoError(
            "%s is <how>:<where>, one of %s - not %r"
            % (where, ", ".join(HOWS), spec)
        )
    if not rest:
        raise SysinfoError("%s says %s: and then nothing" % (where, how))
    if how == "proc" and rest not in PROC_FILES:
        raise SysinfoError(
            "%s: proc: reads %s, not %r"
            % (where, " or ".join(PROC_FILES), rest)
        )
    if how == "hwmon" and "/" not in rest:
        raise SysinfoError(
            "%s: a hwmon source is <chip>/<file>, not %r" % (where, rest)
        )
    if how in ("mount", "file") and not rest.startswith("/"):
        raise SysinfoError(
            "%s: %s: takes a path, and %r is not one" % (where, how, rest)
        )
    return (how, rest)


def parse_stat(lines, before):
    """`/proc/stat` -> (busy share since `before`, the sample to keep).

    A share of an interval rather than an instant: /proc/stat counts ticks
    since boot, so one read says what the machine has averaged since it was
    switched on, which is not a reading anybody wants. The first read of all
    therefore answers None - there is no interval yet, and a number invented
    for the first two seconds is a number nobody can trust afterwards.
    """
    for line in lines:
        fields = line.split()
        if not fields or fields[0] != "cpu":
            continue
        try:
            times = [int(field) for field in fields[1:]]
        except ValueError:
            return (None, before)
        if len(times) < 4:
            return (None, before)
        total = sum(times)
        # Idle and iowait: the kernel counts waiting on a disk separately, and
        # a machine stalled on one is not a machine doing work.
        idle = times[3] + (times[4] if len(times) > 4 else 0)
        sample = (total, idle)
        if before is None:
            return (None, sample)
        spent = total - before[0]
        rested = idle - before[1]
        if spent <= 0:
            # The counters did not move, which is a read that arrived twice in
            # the same tick. Keeping the old sample means the next one still
            # measures a real interval.
            return (None, before)
        return (max(0.0, min(1.0, (spent - rested) / float(spent))), sample)
    return (None, before)


def parse_meminfo(lines):
    """`/proc/meminfo` -> the share of memory in use, or None.

    Against `MemAvailable` rather than `MemFree`: the cache is memory the
    machine will hand to the next program that asks, and counting it as used
    prints a laptop at 95% for the whole of an evening in which nothing was
    ever short of it.
    """
    total = available = None
    for line in lines:
        head, separator, tail = line.partition(":")
        if not separator:
            continue
        found = NUMBER.search(tail)
        if not found:
            continue
        if head.strip() == "MemTotal":
            total = float(found.group(0))
        elif head.strip() == "MemAvailable":
            available = float(found.group(0))
        if total is not None and available is not None:
            break
    if not total or available is None:
        return None
    return max(0.0, min(1.0, (total - available) / total))


def parse_number(lines):
    """The first number anything printed, or None where there was none.

    What every `file:` and `cmd:` source comes back as: a sysfs file holds one
    number and a helper is asked to print one, so the first one in the answer
    is the answer. Anything else - a warning on stderr that landed in the same
    pipe, a unit after the digits - is not allowed to matter.
    """
    for line in lines:
        found = NUMBER.search(line)
        if found:
            try:
                return float(found.group(0))
            except ValueError:
                continue
    return None


def hwmon_path(spec, root=HWMON):
    """`<chip>/<file>` -> the path that file is at today, or None.

    A hwmon number is not stable: the chips are numbered in the order the
    drivers happened to probe, so `hwmon4` is a battery on one boot and a
    network card on the next. What is stable is the name each one publishes,
    so that is what a source names - and `*` means whichever chip has a file
    of that name, which is what a person who does not care which sensor it is
    writes.
    """
    chip, _, filename = str(spec).partition("/")
    chip, filename = chip.strip(), filename.strip()
    if not filename:
        return None
    for directory in sorted(glob.glob(os.path.join(root, "hwmon*"))):
        if chip != "*":
            try:
                with open(os.path.join(directory, "name")) as handle:
                    if handle.read().strip() != chip:
                        continue
            except OSError:
                continue
        path = os.path.join(directory, filename)
        if os.path.exists(path):
            return path
    return None


def text(value, unit, scale=1):
    """What a reading is, in the words a tile prints."""
    if value is None:
        return ""
    amount = float(value) * scale
    if unit == "%":
        return "%g%%" % round(amount)
    if unit in ("°C", "°F"):
        # No space before a degree, which is how every thermometer on a
        # desktop prints it.
        return "%g%s" % (round(amount), unit)
    return ("%g %s" % (round(amount, 1), unit)).strip()


class Sysinfo:
    """The last answer to each question, and how to ask it again.

    Two kinds of question, kept apart by `command()`: the ones this side can
    answer itself, which are a file read and are done on the loop, and the
    ones that need a helper, which go through the same worker thread every
    other slow thing does. A press must never wait on either, and only one of
    them could ever make it.
    """

    def __init__(self, config):
        self.values = {}
        # The last /proc/stat sample, which is the whole of what makes a busy
        # share measurable: one read says nothing on its own.
        self.sample = None
        self.configure(config)

    def configure(self, config):
        self.sources = dict(config.sysinfo_sources)
        self.units = dict(config.sysinfo_units)
        self.divisors = dict(config.sysinfo_divisors)

    def named(self):
        """The readings this machine has a source for."""
        return [name for name in READINGS if self.sources.get(name)]

    def has(self, name):
        return bool(self.sources.get(name))

    def unit(self, name):
        return self.units.get(name, READINGS.get(name, {}).get("unit", ""))

    def value(self, name):
        """The last thing read, or None where nothing has answered yet."""
        return self.values.get(name)

    def words(self, name):
        """What that value says on a tile."""
        spec = READINGS.get(name)
        if spec is None:
            return ""
        return text(self.values.get(name), self.unit(name),
                    spec.get("scale", 1))

    def fraction(self, name):
        """Where along its travel a reading is, or None where it has none.

        A percentage has a bar to draw and a temperature does not: there is no
        top of the scale for a thermometer that is not made up, and a bar
        drawn against a made-up maximum says a different thing on every
        machine it is read on.
        """
        spec = READINGS.get(name)
        value = self.values.get(name)
        if spec is None or value is None or not spec.get("full"):
            return None
        return max(0.0, min(1.0, float(value) / spec["full"]))

    def command(self, name):
        """The helper to run for one reading, or None where there is none.

        None covers both cases the loop has to tell apart from each other by
        calling `read()` instead: a reading with no source at all, and one
        this side answers itself.
        """
        found = self.sources.get(name)
        if not found or found[0] != "cmd":
            return None
        return found[1]

    def read(self, name):
        """Ask one reading this side can answer. True where it changed.

        Every path here is a file read of a few hundred bytes out of a virtual
        filesystem the kernel fills in as it is asked - microseconds, no
        device touched, nothing to block on. That is why this runs on the loop
        while `cmd:` does not: the rule is about waiting on another process,
        and this waits on nobody.
        """
        found = self.sources.get(name)
        if not found or found[0] == "cmd":
            return False
        how, where = found
        if how == "proc" and where == "stat":
            lines = _lines("/proc/stat")
            value, self.sample = parse_stat(lines, self.sample)
        elif how == "proc":
            value = parse_meminfo(_lines("/proc/meminfo"))
        elif how == "mount":
            value = _disk(where)
        else:
            path = hwmon_path(where) if how == "hwmon" else where
            value = parse_number(_lines(path)) if path else None
            if value is not None:
                value /= self._divisor(name)
        return self.took(name, value)

    def took(self, name, value):
        """Record an answer. False where there was none, or nothing moved.

        A reading that answers nothing **keeps its last value** rather than
        blanking the tile: a sensor that is briefly busy, or a helper that is
        a second late, must not be able to empty the HUD. A source that has
        never answered at all has no value, and that is how a tile knows not
        to draw itself.
        """
        if value is None:
            return False
        changed = self.values.get(name) != value
        self.values[name] = value
        return changed

    def answered(self, name, lines):
        """What a `cmd:` helper printed, through the same door as the rest."""
        value = parse_number(lines)
        if value is None:
            return False
        return self.took(name, value / self._divisor(name))

    def _divisor(self, name):
        found = self.divisors.get(name)
        if found:
            return float(found)
        return float(READINGS.get(name, {}).get("divide", 1) or 1)


def _lines(path):
    """A file as lines, or nothing at all.

    Everything here is optional hardware: a sensor that has been unbound, a
    fan a laptop publishes a file for and no number behind it (`ENODEV` is
    exactly that), a card that went away with its driver. None of it may
    raise into the loop.
    """
    try:
        with open(path) as handle:
            return handle.read().split("\n")
    except OSError:
        return []


def _disk(path):
    """How full a filesystem is, by any path on it."""
    try:
        stat = os.statvfs(path)
    except OSError:
        return None
    total = stat.f_blocks
    if not total:
        return None
    # Against the blocks a normal user may have, which is what the machine
    # will actually let something fill: the reserve root keeps is not space
    # anybody is going to see.
    used = total - stat.f_bfree
    free = stat.f_bavail
    return max(0.0, min(1.0, used / float(used + free))) if used + free else None
