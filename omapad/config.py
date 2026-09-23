"""Configuration loading: shipped defaults deep-merged with the user's file."""

import logging
import math
import os
import shutil
import tomllib

from . import actions as actions_module
from . import gamebar as gamebar_module
from . import guide as guide_module
from . import live as live_module
from . import menu as menu_module
from . import snap as snap_module
from . import sysinfo as sysinfo_module
from . import keymap
from . import osk as osk_module

log = logging.getLogger("omapad")

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(PACKAGE_DIR), "config", "config.toml"
)


def user_config_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "omapad", "config.toml")


def mapping_path():
    """Where the mapping screen writes what it measured.

    A file of its own, next to config.toml rather than inside it: that one is
    hand-written and full of comments a program would trample, and a mapping
    is undone by deleting a file rather than by finding the block again.
    """
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "omapad", "mapping.toml")


def layout_path():
    """Where an arrangement made from the pad is written down.

    A third program-written file, and separate from settings.toml on purpose:
    that one is scalars and this one is structure, so a layout that will not
    parse must not be able to take the settings down with it. Never a
    `ConfigError` either - a file the daemon wrote itself must not be how the
    daemon stops starting.
    """
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "omapad", "layout.toml")


def settings_path():
    """Where a setting changed from the pad is written down.

    A file of its own, for the same reason mapping.toml is one: config.toml is
    hand-written and full of comments a program has no business rewriting. It
    is merged last, so what was just changed from the menu wins over what the
    config file says - that is what changing it meant - and deleting the file
    hands every setting in it back to the config.
    """
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "omapad", "settings.toml")


# Logical button names per controller family, keyed by evdev button code.
# Names follow what is printed on the pad, not the kernel's BTN_* label.
#
# Pads like the Beitong KP20/KP40 expose a different identity per hardware
# mode: in NS mode the kernel's hid-nintendo driver reports it as a Switch Pro
# Controller with digital ZL/ZR, while in XInput mode ZL/ZR arrive as analog
# axes instead. Profiles therefore also declare which axes act as buttons.
PROFILES = {
    "nintendo_pro": {
        "buttons": {
            0x130: "B", 0x131: "A", 0x133: "X", 0x134: "Y",
            0x135: "CAPTURE", 0x136: "L", 0x137: "R",
            0x138: "ZL", 0x139: "ZR",
            0x13A: "MINUS", 0x13B: "PLUS", 0x13C: "HOME",
            0x13D: "LSTICK", 0x13E: "RSTICK",
        },
        "triggers": {},
    },
    "xbox": {
        "buttons": {
            0x130: "A", 0x131: "B", 0x133: "X", 0x134: "Y",
            0x136: "L", 0x137: "R",
            0x13A: "MINUS", 0x13B: "PLUS", 0x13C: "HOME",
            0x13D: "LSTICK", 0x13E: "RSTICK",
        },
        # ABS_Z and ABS_RZ: analog triggers reported as ZL / ZR.
        "triggers": {0x02: "ZL", 0x05: "ZR"},
    },
}

# What `[device] layout = "auto"` resolves to. Only two profiles can be
# detected, and a PlayStation pad is not one of them - it reports as XInput -
# so that layout is a thing someone chooses, never a thing found.
PROFILE_LAYOUTS = {
    "nintendo_pro": "nintendo",
    "xbox": "xbox",
}

# The surfaces the daemon draws, in the order they outrank one another: the
# mapping screen reads the pad raw, and each of the others closes the ones
# below it when it opens. `base` is not one - it is the table that applies
# whichever is up. See daemon.surface_top(). The quick menu and the menu close
# each other, so which of the two is higher only decides the tie that cannot
# happen; it is above because it is the one opened from the other over a game.
SURFACES = ("map", "guide", "quick", "menu", "osk")
KEYBOARD_SURFACES = ("base",) + SURFACES

DPAD_NAMES = {
    ("x", -1): "DPAD_LEFT", ("x", 1): "DPAD_RIGHT",
    ("y", -1): "DPAD_UP", ("y", 1): "DPAD_DOWN",
}


def detect_profile(name, vid_pid):
    """Pick a profile from the device's own identity."""
    if vid_pid.upper().startswith("057E") or " NS" in name.upper():
        return "nintendo_pro"
    return "xbox"


# The two ways a badge is drawn. `filled` washes the shape in the surface's
# own colour and sets the label on top of it; `stencil` fills the shape with
# the accent and punches the label through it. Named here because the config,
# the menu row and the payload all have to agree on the words.
BADGE_STYLES = ("filled", "stencil")


# One rung of the ladder every size on these surfaces climbs - the type, the
# gaps, the radii off them. **It is sqrt(2), which is the silver ratio less
# one**, and the distinction is worth keeping: `metrics.silver` (1 + sqrt(2))
# is the ratio itself, and it has a job of its own a rung along.
#
# A corner is a size like any of them, so a step here multiplies rather than
# adds: 23 pixels against 25 is not a difference anybody sees from a sofa, and
# 23 against 32 is.
RUNG = math.sqrt(2.0)

# The stops a corner may be rounded to, against whatever the compositor
# rounds a window by. Derived rather than typed, so the ladder cannot drift
# from the rung above it - and zero is not on it: no amount of dividing
# reaches square, so it is the stop *under* the bottom rather than a rung.
#
# **It stops one rung above the desktop's own answer**, and that is the whole
# range on purpose. This multiplier says how far off *the desktop* these
# surfaces stand, and two rungs past it a 128-pixel tile is a circle - which
# is not a rounder corner, it is a different shape. Somebody who wants
# fundamentally bigger corners is asking about the base rather than about the
# distance from it, and the base is `[menu] tile_corner`.
RADIUS_STOPS = (0.0,) + tuple(
    round(0.5 * RUNG ** n, 3) for n in range(4)
)


# ---------------------------------------------------------------------------
# The settings the pad itself can change.
#
# Everything else in this file is decided at a keyboard, which is the right
# place for most of it. These four are not: which profile a pad takes and what
# its badges print are exactly the questions someone has while holding the
# thing and getting the wrong answer, how those badges are drawn is a question
# you have while looking at them from a sofa, and the motor is a preference you
# change in the room you are sitting in. So they can be reached from `pad:` - a menu
# row, or a button - and what the pad chose is written to settings.toml.
#
# `attr` is where the value lives on Config once loaded, `table`/`key` where it
# is written; a setting that can be stepped says how far one step goes. What
# each is *called* is guide.PAD_NAMES, with every other action's words.
# ---------------------------------------------------------------------------

CHOSEN = {
    # `words` is what each value is called where somebody reads it - a tile
    # that walks a choice in place, and the line a notification prints. Beside
    # the choices rather than in a table of its own: a second place to say
    # what `xbox` is called is a second place for it to be wrong. A value with
    # no word here prints itself, which is right for the ones that are already
    # words.
    "profile": {
        "attr": "profile_name", "table": "device", "key": "profile",
        "kind": "choice", "choices": ("auto",) + tuple(sorted(PROFILES)),
        "words": {"auto": "Detect it", "nintendo_pro": "Nintendo Pro",
                  "xbox": "Xbox"},
    },
    "layout": {
        "attr": "layout_name", "table": "device", "key": "layout",
        "kind": "choice",
        "choices": ("auto",) + tuple(sorted(guide_module.LAYOUTS)),
        "words": {"auto": "Follow the pad", "nintendo": "Nintendo",
                  "playstation": "PlayStation", "xbox": "Xbox"},
    },
    # How the badges are drawn, which is the other half of what they print:
    # the answer depends on how far away the screen is, so it is asked from
    # where you are sitting rather than at a keyboard.
    "badge_style": {
        "attr": "ui_badge_style", "table": "ui", "key": "badge_style",
        "kind": "choice", "choices": BADGE_STYLES,
        "words": {"filled": "Filled", "stencil": "Stencil"},
    },
    # How solid a tile's ground is drawn. On the pad for `radius`'s reason and
    # more so: the page the slider is on is the page it opens up, so the tiles
    # go glassy under the thumb that is moving it - and how much of a desktop
    # you want showing through a menu is a judgement about the room you are
    # sitting in rather than one a config file can make for you.
    "tile_fill": {
        "attr": "menu_tile_fill", "table": "menu", "key": "tile_fill",
        # A tenth per step, which is `sound_volume`'s answer and for the same
        # reason: ten places end to end, and a difference smaller than that
        # between two tiles is not one anybody sees from a sofa. A `stops`
        # ladder would be wrong here - this is an amount you cross rather than
        # a handful of places to stand, which is what separates it from
        # `radius`.
        "kind": "number", "step": 0.1, "min": 0.0, "max": 1.0,
        "unit": "%", "scale": 100,
    },
    "rumble": {
        "attr": "rumble_enabled", "table": "rumble", "key": "enabled",
        "kind": "bool",
    },
    # The other half of what a press says back. Beside the motor rather than
    # under a menu of its own: they are two answers to one question, and
    # whoever is turning one off is deciding between them.
    "sound": {
        "attr": "sound_enabled", "table": "sound", "key": "enabled",
        "kind": "bool",
    },
    "sound_volume": {
        "attr": "sound_volume", "table": "sound", "key": "volume",
        # A tenth per step, which is coarser than the motor's twentieth: a
        # cue is 90 ms long at the most, and a difference you cannot hear
        # between two presses is not a step worth stopping on.
        "kind": "number", "step": 0.1, "min": 0.0, "max": 1.0,
        "unit": "%", "scale": 100,
    },
    # How hard a corner is rounded, against what the compositor rounds a
    # window by. On the pad because it is the one setting here you can only
    # judge by looking at the thing it sets - and the thing it sets is the
    # surface the slider is on, so the tiles round under the thumb that is
    # moving it.
    #
    # `stops` rather than `step`: a corner is a size, every size on these
    # surfaces climbs by one rung of the same ladder, and a step of a tenth
    # would be six presses to cross a difference nobody can see. See `RUNG`.
    "radius": {
        "attr": "ui_radius", "table": "ui", "key": "radius",
        "kind": "number", "stops": RADIUS_STOPS,
        "min": RADIUS_STOPS[0], "max": RADIUS_STOPS[-1],
        # **A word per stop, and no percentage.** A ladder has somewhere to
        # *be* rather than an amount to be at, and "141%" is a number you have
        # to divide before it says anything - against what? The bar under it
        # is drawn in the stops themselves, so how far along is already said
        # in the one place that can say it without arithmetic, and what is
        # left for the line to say is which corner this is. The middle four
        # are the hardest to name and the easiest to see, which is the whole
        # argument for the segments.
        "words": {
            0.0: "Square", 0.5: "Barely", 0.707: "Slight",
            1.0: "The desktop's", 1.414: "Round",
        },
    },
    # How long the surfaces take to move. On the pad rather than only in the
    # file because it is a thing you find out by watching a screen move, and
    # the person who cannot read a moving screen is the one who should not
    # have to go and find a text editor to stop it.
    "motion": {
        "attr": "ui_motion", "table": "ui", "key": "motion",
        # A quarter of the drawn speed per stop: four presses from off to
        # normal, and each one is a change you can actually see. Anything
        # finer is a slider nobody can tell they have moved - which is what
        # makes this five places to be rather than a range to cover, and the
        # tile draws it in five segments.
        #
        # Worded, and `Off` is why: this setting exists for somebody who
        # cannot read a moving screen, and the stop that answers them should
        # say so rather than print `0%`. The rest are named for how much of
        # the movement is left, which is the thing being chosen.
        "kind": "number",
        "stops": (0.0, 0.25, 0.5, 0.75, 1.0),
        "words": {0.0: "Off", 0.25: "Little", 0.5: "Half", 0.75: "Most",
                  1.0: "Full"},
        "min": 0.0, "max": 1.0,
        "unit": "%", "scale": 100,
    },
    # Whether the readings are on screen. A setting rather than a surface
    # verb, because it is a thing you decide once and leave: chosen from the
    # sofa, written down, and still on the next time the daemon starts.
    "hud": {
        "attr": "hud_show", "table": "hud", "key": "show", "kind": "bool",
    },
    "rumble_strength": {
        "attr": "rumble_strong", "table": "rumble", "key": "strong",
        # A twentieth of the motor's range per step: fine enough to stop on
        # the level you meant, coarse enough that reaching it is a few
        # presses rather than a job.
        "kind": "number", "step": 0.05, "min": 0.0, "max": 1.0,
        "unit": "%", "scale": 100,
    },
    # How long every hold on the pad takes, against the lengths the bindings
    # were written at. On the pad because it is the one setting here that is
    # about the hand rather than the thing in it: whether two seconds of
    # keeping a shoulder down is a gesture you can make is not a question
    # anybody can answer for somebody else, and the person who cannot make it
    # is the last person who should have to find a text editor to say so.
    "hold_scale": {
        "attr": "confirm_scale", "table": "confirm", "key": "scale",
        # A quarter of the written length per stop, over a range of one
        # doubling: six presses from half to double, each of them a wait you
        # can feel change. The ends are `[confirm] scale`'s own - under a half
        # a tap and a hold stop being different gestures - and seven places to
        # be is what the tile draws in seven segments.
        #
        # **No words, unlike the two ladders that have them.** This is an
        # amount rather than a place: a hold at 150% is half again as long as
        # the one the binding was written at, and `Slower` would be a word
        # standing where a quantity already reads.
        "kind": "number",
        "stops": (0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0),
        "min": 0.5, "max": 2.0,
        "unit": "%", "scale": 100,
    },
    # How fast the two thumbs are, which is the setting nobody agrees on: it
    # depends on the pad, the screen and how far away the sofa is. Both are
    # felt rather than read, so they are steps from the menu with the pointer
    # still live under it, not a number typed at a keyboard.
    "scroll_speed": {
        "attr": "scroll_speed", "table": "scroll", "key": "speed",
        "kind": "number", "step": 1.0, "min": 1.0, "max": 40.0,
        "unit": "notches a second",
    },
    "pointer_speed": {
        "attr": "pointer_speed", "table": "pointer", "key": "speed",
        # A tenth of the shipped speed per step: enough to feel in one press,
        # small enough to land on the one that suits you.
        "kind": "number", "step": 100.0, "min": 200.0, "max": 4000.0,
        "unit": "pixels a second",
    },
    # And how much of each stick does nothing, which is the same question
    # asked of the other end of the travel: a pad whose sticks rest crooked
    # walks the pointer off on its own until the zone is wide enough to
    # swallow it, and a pad with tight sticks loses aim to a zone somebody
    # else needed. One number per stick rather than per role, because the
    # slop is in the hardware: the right stick has the same wear scrolling
    # the desktop as it has walking a game's controls. Which of the two you
    # are holding is answered by watching the pointer under the open menu,
    # not by a number typed at a keyboard.
    "left_deadzone": {
        "attr": "left_deadzone", "table": "pointer", "key": "left_deadzone",
        # A hundredth of the travel per step: the drift a pad shows is a
        # couple of percent wide, so a coarser step walks past the setting
        # that cures it. Half the travel is the ceiling - past that there is
        # not enough stick left on the far side to aim with.
        "kind": "number", "step": 0.01, "min": 0.0, "max": 0.50,
        "unit": "%", "scale": 100,
    },
    "right_deadzone": {
        "attr": "right_deadzone", "table": "pointer", "key": "right_deadzone",
        "kind": "number", "step": 0.01, "min": 0.0, "max": 0.50,
        "unit": "%", "scale": 100,
    },
    # Whether a press puts the pointer away. It is on the pad because it is
    # only ever wrong from the couch: a ring left over the thing a press just
    # opened is a complaint you have while looking at it, and one that
    # vanishes under a resting thumb is the same complaint from the other
    # side. Neither is answerable at a keyboard.
    "hide_pointer": {
        "attr": "hide_pointer", "table": "pointer", "key": "hide_on_press",
        "kind": "bool",
    },
    # Where dictation puts what was said. On the pad because the answer is
    # about the window in front of you rather than about this machine: the
    # same sentence wants typing where there is a text field to type into, and
    # copying where there is not - a game, a terminal running something, a
    # window that is not yours at all. That is a question you have while
    # looking at the window, which is the other side of a room from the file
    # the tool keeps the answer in.
    "dictate_clipboard": {
        "attr": "osk_dictate_clipboard", "table": "osk",
        "key": "dictate_clipboard", "kind": "bool",
    },
    # Which mode the *next* start comes up in - the one setting here that
    # changes nothing about the daemon it was set from. It is on the pad
    # because of what it decides: a machine that is used from a sofa has to be
    # told to come up ready for one, and the only place to tell it was a
    # config file, which is the keyboard this project exists to do without.
    # The shipped value is "desktop", so nothing comes up from the couch
    # until it has been asked for from the couch.
    "start_mode": {
        "attr": "start_mode", "table": "mode", "key": "start",
        "kind": "choice", "choices": ("desktop", "game"),
        "words": {"desktop": "Desktop", "game": "Game mode"},
    },
    # And the one entry here that is not a preference at all: whether the menu
    # still owes somebody a first start. It is in this table because
    # settings.toml is where the pad writes things down, and a mark it cannot
    # write is a first start that happens again every morning. Nothing reads
    # it but the `Start here` tile's `when`, and deleting its line from that
    # file is how the tile comes back.
    "first_run": {
        "attr": "menu_first_run", "table": "menu", "key": "first_run",
        "kind": "bool",
    },
}

# What a setting used to be called. settings.toml is written by the menu
# rather than by hand, so a file from an older build is not a typo to reject:
# the dead zones moved from the role a stick was in to the stick itself, and a
# value chosen from the sofa yesterday stays chosen. The next thing written
# puts it back under the new name.
SETTING_ALIASES = {
    "pointer_deadzone": "left_deadzone",
    "scroll_deadzone": "right_deadzone",
}

TRUE_WORDS = ("on", "true", "yes", "1")
FALSE_WORDS = ("off", "false", "no", "0")


class SettingError(ValueError):
    pass


def setting_request(name, raw):
    """Validate `pad:<name>=<value>`, into what `Config.set_setting` takes.

    Parsed when the binding is read rather than when it is pressed, so a typo
    is something `omapad check` names instead of a row that does nothing.
    """
    spec = CHOSEN.get(name)
    if spec is None:
        raise SettingError("unknown setting %r (one of %s)"
                           % (name, ", ".join(sorted(CHOSEN))))
    word = str(raw).strip().lower()
    if not word:
        raise SettingError("%s needs a value" % name)
    # Words every kind understands: one step along whatever it holds, so a
    # single button can walk a setting the menu offers as a list of rows.
    if word in ("next", "up", "more"):
        return ("step", 1)
    if word in ("prev", "previous", "down", "less"):
        return ("step", -1)
    kind = spec["kind"]
    if kind == "bool":
        if word == "toggle":
            return ("toggle", None)
        if word in TRUE_WORDS:
            return ("set", True)
        if word in FALSE_WORDS:
            return ("set", False)
        raise SettingError("%s takes on, off or toggle, not %r" % (name, raw))
    if kind == "choice":
        if word == "toggle":
            return ("step", 1)
        if word not in spec["choices"]:
            raise SettingError("%s takes one of %s, not %r"
                               % (name, ", ".join(spec["choices"]), raw))
        return ("set", word)
    try:
        value = float(word)
    except ValueError:
        raise SettingError("%s takes a number, not %r" % (name, raw)) from None
    return ("set", _clamp_setting(spec, value))


def _clamp_setting(spec, value):
    return round(min(max(value, spec["min"]), spec["max"]), 3)


def _nearest_stop(stops, value):
    return min(range(len(stops)), key=lambda i: abs(stops[i] - float(value)))


# The same answer under the name the daemon asks it by: which stop a value is
# on, for a bar that is drawn in stops rather than as a length.
nearest_stop_index = _nearest_stop


def _stepped(spec, current, argument):
    """The value `argument` stops along a ladder from `current`.

    For the settings whose steps are a *proportion* rather than an amount -
    see `RADIUS_STOPS`. A value somebody wrote by hand that is not on the
    ladder is not moved onto it and then stepped: it steps from the stop
    nearest it, so one press from 1.2 is the next stop up rather than a number
    1.2 has quietly been rounded to.
    """
    stops = spec["stops"]
    at = _nearest_stop(stops, current) + argument
    return stops[max(0, min(len(stops) - 1, at))]


def setting_share(spec, value):
    """Where a number sits along its own travel, 0..1, for a bar to draw.

    A ladder is walked by its stops rather than measured along them: they are
    a proportion apart, so a bar that spaced them by their arithmetic would
    bunch the bottom half of a ladder into its first third and say it was
    uneven when it is the most even thing on the surface.
    """
    stops = spec.get("stops")
    if stops:
        return _nearest_stop(stops, value) / float(len(stops) - 1)
    span = float(spec["max"]) - float(spec["min"])
    if span <= 0:
        return 0.0
    return (float(value) - float(spec["min"])) / span


def setting_text(name, value):
    """What a setting is on right now, for a menu row to print.

    Only numbers answer: a choice or a switch is already ticked in the row
    that holds it, but a row that steps a number is a press in the dark -
    nothing else on screen says what the number is or that it has stopped at
    an end. Empty for everything else.
    """
    spec = CHOSEN.get(name)
    if spec is None or spec["kind"] != "number" or value is None:
        return ""
    stops = spec.get("stops")
    if stops:
        # A ladder says which stop it is on rather than how far along: the
        # bar under it is drawn in the stops themselves, so how far along is
        # already said without arithmetic. A stop with no word of its own
        # falls back to the number, which is what a hand-written value in
        # between two of them is.
        words = spec.get("words") or {}
        word = words.get(stops[_nearest_stop(stops, value)])
        if word and abs(float(value) - stops[_nearest_stop(stops, value)]) < 1e-9:
            return word
    amount = float(value) * spec.get("scale", 1)
    unit = spec.get("unit", "")
    if unit == "%":
        return "%g%%" % round(amount)
    return ("%g %s" % (round(amount, 2), unit)).strip()


def toml_string(text):
    """`text` as a TOML basic string, quotes included.

    Everything this project writes it reads again at the next start, so a
    string going into one of those files has to survive the round trip. One of
    them is a pad's own name for itself, which is an ioctl away from a USB
    descriptor - bytes chosen outside this machine, and the only rule on them
    is that they are not NUL. Dropping the quote characters was not enough: a
    name carrying a newline ends the line and leaves what follows it standing
    as TOML, and a name ending in a backslash escapes the closing quote.
    Either one makes the file unparseable, and an unparseable `mapping.toml`
    is a daemon that will not start until someone deletes it by hand.
    """
    out = []
    for char in str(text):
        if char in ('"', "\\"):
            out.append("\\" + char)
        elif char >= " " and char != "\x7f":
            out.append(char)
        # A control character has no escape worth writing here: TOML forbids it
        # raw, and a name with one in it is not a name anybody reads.
    return '"%s"' % "".join(out)


def read_layout(path):
    """Everything in layout.toml that still makes sense, and nothing else.

    Syntax corruption and semantic corruption are not the same failure, and
    the difference is the whole of this function:

    | Broken | Answer |
    |---|---|
    | the file will not parse as TOML | ignore the whole layout, one warning |
    | an unknown id | ignore that id |
    | an invalid span | ignore that one override, keep the rest |
    | a duplicate id | keep the first, drop the rest |
    | a reference to no page | ignore that one; `menu.adoptions` resolves it |

    What it cannot do is raise. Nothing here is the user's typing - it is a
    file omapad wrote - so a mistake in it is omapad's to survive.
    """
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        log.warning("%s: %s - the shipped arrangement is used instead",
                    path, exc)
        return {}
    pages = data.get("layout")
    if not isinstance(pages, dict):
        return {}
    out = {}
    for page, plan in pages.items():
        if not isinstance(plan, dict):
            continue
        removed = plan.get("removed")
        if removed is None:
            # What the list was called while a tile taken off a page had
            # nowhere to go but the page it came off. Read under the old
            # name and written under the new one, so a file from before the
            # strip keeps every tile somebody put away.
            removed = plan.get("hidden")
        out[str(page)] = {
            "order": _layout_ids(plan.get("order")),
            "removed": _layout_ids(removed),
            "span": _layout_spans(plan.get("span")),
            "at": _layout_cells(plan.get("at")),
            # The tiles this page was given, each named `page/id` because an
            # id is unique on the page that wrote it and nowhere else.
            # Whether the page it names still exists is `menu.adoptions`'
            # question, not this one: the same rule as an id in `order` that
            # no longer resolves, one level along.
            "adopted": _layout_refs(plan.get("adopted")),
        }
    return out


def _layout_ids(value):
    """A list of ids, de-duplicated, first one winning."""
    if not isinstance(value, list):
        return []
    out = []
    for entry in value:
        if not isinstance(entry, str):
            continue
        name = entry.strip()
        if name and name not in out:
            out.append(name)
    return out


def _layout_refs(value):
    """The `page/id` references that are shaped like one, first one winning.

    Only the shape is checked here. Whether the page still has the tile is
    the tree's answer and is asked where the tree is - a reference that
    resolves to nothing is dropped there, the way an unknown id in `order`
    is dropped in `arrange`.
    """
    out = []
    for name in _layout_ids(value):
        page, _, tile = name.partition(menu_module.REF)
        if page and tile and menu_module.REF not in tile:
            out.append(name)
    return out


def _layout_spans(value):
    """The size overrides that are sizes. One bad one costs only itself."""
    if not isinstance(value, dict):
        return {}
    out = {}
    for name, span in value.items():
        if not isinstance(span, list) or len(span) != 2:
            continue
        try:
            width, height = int(span[0]), int(span[1])
        except (TypeError, ValueError):
            continue
        if width < 1 or height < 1:
            continue
        out[str(name)] = (width, height)
    return out


def _layout_cells(value):
    """The cells that are cells. One bad one costs only itself.

    `0` is a cell and `-1` is not, which is the one way this differs from a
    span: a tile in the top left corner is at [0, 0], and a tile off the page
    is not anywhere. How far *right* a cell may be is not checked here, since
    that depends on the column count the page is drawn at - `menu.place`
    clamps it, so a pin made on a wide screen comes back onto a narrow one.
    """
    if not isinstance(value, dict):
        return {}
    out = {}
    for name, cell in value.items():
        if not isinstance(cell, list) or len(cell) != 2:
            continue
        try:
            x, y = int(cell[0]), int(cell[1])
        except (TypeError, ValueError):
            continue
        if x < 0 or y < 0:
            continue
        out[str(name)] = (x, y)
    return out


def render_layout(layout):
    """Serialise an arrangement, one table per page."""
    lines = [
        "# omapad layout - written by the controller menu.",
        "#",
        "# One table per page, naming the tiles in the order they are shown.",
        "# Anything the config has that is not named here is added at the",
        "# end, and a name here the config no longer has is ignored - so",
        "# editing config.toml can never break this file, and this file can",
        "# never hide a tile that did not exist when it was written.",
        "#",
        "# A tile under `removed` is off its page and stands in the strip",
        "# along the foot of the card, where it can be put back or put on",
        "# another page. A page's `adopted` names the tiles it was given",
        "# that way, as `page/id`; the page they came from says nothing, so",
        "# there is one place saying where a tile is.",
        "#",
        "# A tile under `at` was put in that cell and stays in it; everything",
        "# else flows around those, in the order above. A cell off the edge of",
        "# a narrower screen is pulled back onto it rather than lost.",
        "#",
        "# Delete a page's table to hand that page back to the config, or the",
        "# file to hand back every page.",
        "",
    ]
    for page in sorted(layout):
        plan = layout[page]
        if not plan.get("order") and not plan.get("removed") \
                and not plan.get("span") and not plan.get("at") \
                and not plan.get("adopted"):
            continue
        lines.append("[layout.%s]" % page)
        if plan.get("order"):
            lines.append("order = [%s]" % ", ".join(
                toml_string(name) for name in plan["order"]))
        if plan.get("removed"):
            lines.append("removed = [%s]" % ", ".join(
                toml_string(name) for name in plan["removed"]))
        if plan.get("adopted"):
            lines.append("adopted = [%s]" % ", ".join(
                toml_string(name) for name in plan["adopted"]))
        if plan.get("span"):
            lines.append("")
            lines.append("[layout.%s.span]" % page)
            for name in sorted(plan["span"]):
                width, height = plan["span"][name]
                lines.append("%s = [%d, %d]"
                             % (toml_string(name), width, height))
        if plan.get("at"):
            lines.append("")
            lines.append("[layout.%s.at]" % page)
            for name in sorted(plan["at"]):
                x, y = plan["at"][name]
                lines.append("%s = [%d, %d]" % (toml_string(name), x, y))
        lines.append("")
    return "\n".join(lines)


def render_settings(chosen):
    """Serialise what the pad has changed, one line per setting."""
    lines = [
        "# omapad settings - written by the controller menu.",
        "#",
        "# Only what was changed from the pad is here, and it is merged over",
        "# config.toml rather than into it. Delete a line to hand that setting",
        "# back to the config file, or the file to hand back all of them.",
        "",
    ]
    for name in sorted(chosen):
        value = chosen[name]
        if isinstance(value, bool):
            text = "true" if value else "false"
        elif isinstance(value, (int, float)):
            text = repr(round(float(value), 3))
        else:
            text = toml_string(value)
        lines.append("%s = %s" % (name, text))
    lines.append("")
    return "\n".join(lines)


# What each traversal step sends by default. Space rather than Enter for
# `activate`: Space is what presses the focused button or ticks the focused
# checkbox in GTK, Qt and every browser, where Enter fires a form's default
# action, which is not always the thing under the focus ring.
# Which focus step each way of a "focus" stick means, by default: the Tab
# order across, the arrows up and down.
TRAVERSE_STICK_DEFAULTS = (
    ("left", "prev"),
    ("right", "next"),
    ("up", "up"),
    ("down", "down"),
)

TRAVERSE_DEFAULTS = (
    ("next", "TAB"),
    ("prev", "SHIFT+TAB"),
    ("up", "UP"),
    ("down", "DOWN"),
    ("left", "LEFT"),
    ("right", "RIGHT"),
    ("activate", "SPACE"),
    ("back", "ESC"),
)


class ConfigError(RuntimeError):
    pass


def _deep_merge(base, override):
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_toml(path):
    with open(path, "rb") as handle:
        return tomllib.load(handle)


# How long the output of an app page's command is reused before it is asked
# for again. A page is opened in bursts - turn to it, type, turn away - and
# spawning a shell per page turn to re-read a history file nobody has written
# to is the wrong side of that trade.
APP_PAGE_TTL = 10.0
APP_PAGE_LIMIT = 8

# What a [profile.<name>] table may hold besides a held layer's own bindings.
# A closed list, so a key that is neither this nor a [layers.*] name is a typo
# rather than a setting nobody has implemented yet.
PROFILE_KEYS = frozenset(
    ("match", "bindings", "osk", "left_stick", "right_stick", "handover")
)


def _page_entry(profile, entry):
    """One entry of an app page: what it prints, and what it does.

    Two things it can do, and exactly one of them: `text` types a whole string,
    `action` sends a chord. The chord is what a key that is wrong in this one
    app needs - a terminal's paste is Ctrl+Shift+V - written the same way
    [osk.keys] writes one, and parsed here so `omapad check` names the
    profile rather than the daemon failing when the page is drawn.
    """
    if isinstance(entry, str):
        entry = {"text": entry}
    if not isinstance(entry, dict):
        raise ConfigError(
            "profile %r osk entry must be a string or a table" % profile
        )
    text = entry.get("text")
    action = entry.get("action")
    if text and action:
        raise ConfigError(
            "profile %r osk entry has both 'text' and 'action'" % profile
        )
    if action is not None:
        if not isinstance(action, str) or not action.strip():
            raise ConfigError(
                "profile %r osk entry action must be a key chord" % profile
            )
        try:
            keymap.parse_chord(action)
        except keymap.KeyParseError as exc:
            raise ConfigError("profile %r osk entry: %s" % (profile, exc)) from exc
    elif not isinstance(text, str) or not text.strip():
        raise ConfigError(
            "profile %r osk entry needs a 'text' or an 'action'" % profile
        )
    label = entry.get("label") or text or action
    if not isinstance(label, str):
        raise ConfigError("profile %r osk entry label must be a string" % profile)
    return {"label": label.strip(), "text": text, "action": action}


def parse_app_page(profile, spec):
    """The keyboard page a profile lends the app it matches, or None.

    Entries come from two places and both are optional: `keys`, written down
    here, and `from`, a shell command whose output is one entry per line. The
    command is what puts "the commands you last ran" on the keyboard without
    omapad having to know anything about anybody's shell - which history file
    it is, and whether it is bash or atuin answering, stays in the config.
    """
    if spec is None:
        return None
    if not isinstance(spec, dict):
        raise ConfigError("profile %r osk must be a table" % profile)
    label = spec.get("label") or profile
    if not isinstance(label, str) or not label.strip():
        raise ConfigError("profile %r osk label must be a string" % profile)
    source = spec.get("from")
    if source is not None and not isinstance(source, str):
        raise ConfigError("profile %r osk 'from' must be a command string" % profile)
    keys = spec.get("keys") or []
    if not isinstance(keys, list):
        raise ConfigError("profile %r osk keys must be a list" % profile)
    return {
        "label": label.strip(),
        "keys": [_page_entry(profile, entry) for entry in keys],
        "from": source,
        "ttl": float(spec.get("ttl", APP_PAGE_TTL)),
        "limit": int(spec.get("limit", APP_PAGE_LIMIT)),
    }


def _match_patterns(spec):
    """`[device] match` as the patterns to try, in the order written.

    "auto" - the default - and an empty list mean every pad qualifies. Kept a
    list even for the one-pattern case so the caller has a single shape.
    """
    if isinstance(spec, str):
        spec = [] if spec.strip().lower() in ("", "auto") else [spec]
    if not isinstance(spec, list):
        raise ConfigError("device.match must be a string or a list of strings")
    patterns = []
    for entry in spec:
        if not isinstance(entry, str) or not entry.strip():
            raise ConfigError(
                "device.match entries must be non-empty strings, got %r" % (entry,)
            )
        patterns.append(entry.strip())
    return patterns


# What a stick may be told to do. "none" is a role like any other here - a
# stick a layer turns off - which is why this is a wider list than daemon.py's
# STICK_ROLES, the ones that actually integrate something every tick.
STICK_ROLES = (
    "cursor", "scroll", "resize", "move", "snap", "focus", "swap", "menu",
    "none",
)


def _repeat_ramp(table, where, default_ramp=2.5, default_ms=1000):
    """How much faster a held direction walks, and how long it takes to.

    One reader for the three tables that have the pair - `[menu]`, `[osk]`,
    `[traverse]` - because the question is the same in all three and three
    copies of the same two lines is three places for the validation to be
    missed in one.

    Returns the factor and the time in seconds, the way every other duration
    on `Config` is kept.
    """
    ramp = float(table.get("repeat_ramp", default_ramp))
    if ramp < 1.0:
        raise ConfigError("%s.repeat_ramp must be 1.0 or more; 1.0 is a walk"
                          " that does not accelerate" % where)
    ramp_ms = float(table.get("repeat_ramp_ms", default_ms))
    if ramp_ms < 0:
        raise ConfigError("%s.repeat_ramp_ms must be 0 or more" % where)
    return ramp, ramp_ms / 1000.0


def _stick_role(where, value, allow_empty=False):
    """One stick role, checked here so `omapad check` names a typo.

    A misspelt role used to be silently the same as "none": the stick simply
    stopped working, with nothing anywhere saying why.
    """
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ConfigError("%s must be a string, got %r" % (where, value))
    role = value.strip()
    if not role and allow_empty:
        return ""
    if role not in STICK_ROLES:
        raise ConfigError(
            "%s: unknown stick role %r (one of %s)"
            % (where, value, ", ".join(STICK_ROLES))
        )
    return role


class Config:
    def __init__(self, data, chosen=None):
        self.data = data
        # What was changed from the pad rather than written in a file, by
        # setting name. Kept apart from `data` so settings.toml can be written
        # back out holding only that, and not a copy of everybody's defaults.
        self.chosen = dict(chosen or {})
        # The arrangement made from the pad, page by page. Filled by `load`
        # from layout.toml; empty means the tiles are the config's own order,
        # which is what a machine that has never been rearranged has.
        self.layout = {}
        device = data.get("device", {})
        # Which pad to drive. Empty is any pad: what makes something a pad is
        # what it advertises, not what it is called, so a pad nobody has heard
        # of works with nothing written here. Patterns only narrow that down.
        self.device_match = _match_patterns(device.get("match", "auto"))
        self.profile_name = device.get("profile", "auto")
        if self.profile_name != "auto" and self.profile_name not in PROFILES:
            raise ConfigError("unknown device profile: %r" % self.profile_name)
        # Which console's printing the badges carry - see guide.LAYOUTS. The
        # profile decides what a button *is*; this decides what it is *called*,
        # and they are not the same question: a PlayStation pad reports itself
        # as an XInput one, so it takes the xbox profile and prints shapes.
        self.layout_name = device.get("layout", "auto")
        if self.layout_name != "auto" and self.layout_name not in guide_module.LAYOUTS:
            raise ConfigError("unknown device layout: %r (one of %s, or auto)"
                              % (self.layout_name,
                                 ", ".join(sorted(guide_module.LAYOUTS))))
        # [device.buttons] lets a user rename or add codes: 0x130 = "B"
        self.button_overrides = {
            int(str(code), 0): name
            for code, name in device.get("buttons", {}).items()
        }
        # And [device.triggers] the same, for the pads that report ZL/ZR as
        # axes: 0x02 = "ZL".
        self.trigger_overrides = {
            int(str(code), 0): name
            for code, name in device.get("triggers", {}).items()
        }
        # [pad."VVVV:PPPP"] blocks, written by the mapping screen. Keyed by
        # device identity because a pad with a hardware mode switch has more
        # than one, and its codes change with it.
        self.pad_mappings = {}
        for identity, spec in (data.get("pad") or {}).items():
            if not isinstance(spec, dict):
                raise ConfigError("pad %r must be a table" % identity)
            entry = {"name": spec.get("name", "")}
            for table in ("buttons", "triggers"):
                entry[table] = {
                    int(str(code), 0): name
                    for code, name in (spec.get(table) or {}).items()
                }
            self.pad_mappings[identity.strip().upper()] = entry
        self.trigger_threshold = float(device.get("trigger_threshold", 0.45))
        self.trigger_release = float(device.get("trigger_release", 0.30))
        self.trigger_rest = float(device.get("trigger_rest", 0.25))
        if not 0.0 <= self.trigger_rest < 1.0:
            raise ConfigError("device.trigger_rest is between 0 and 1")
        # Below the release point, or a trigger could be held as a button and
        # read as not pulled at the same time - the sweep would stop dead
        # halfway in while the layer it opened stayed open.
        if self.trigger_rest >= self.trigger_release:
            raise ConfigError(
                "device.trigger_rest must be below device.trigger_release")

        mode = data.get("mode", {})
        self.start_mode = mode.get("start", "desktop")
        if self.start_mode not in ("desktop", "game"):
            raise ConfigError("mode.start must be 'desktop' or 'game'")
        self.grab = bool(mode.get("grab", True))
        # A grab taken while a button is down never lets the app that had the
        # pad see that button's release - evdev feeds the grabber alone - so a
        # grab waits for the hand to come off the pad first. This is how long
        # it waits before taking it anyway; the bound is for the button that is
        # never let go. 0 takes the pad the moment it is wanted.
        self.grab_settle = float(mode.get("grab_settle", 2.0))
        if self.grab_settle < 0:
            raise ConfigError("mode.grab_settle must be 0 or more")
        self.notify = bool(mode.get("notify", True))
        # The switch is the one press whose result you may not be looking
        # at, so it is felt as well as seen. `[rumble] enabled` still wins:
        # this asks for a tick, it does not turn the motor on.
        self.mode_rumble = bool(mode.get("rumble", True))
        # How often to ask whether the focused app has opened the pad. Focus
        # changes trigger the question anyway; this catches the app that opens
        # it a moment after it comes up, which is most of them.
        self.handover_poll = float(mode.get("handover_poll", 2.0))
        # How far around the focused window's process the question is asked.
        # Steam -> reaper -> wrapper -> game is three, which is why three; a
        # session leader is eight up, and reaching it would hand the pad over
        # for every window on the desktop.
        self.handover_depth = int(mode.get("handover_depth", 3))
        if self.handover_depth < 1:
            raise ConfigError("mode.handover_depth must be 1 or more")
        # Whether a process beside the focused one - same cgroup, not its
        # ancestor or its child - counts as the app. Under Proton the pad is
        # opened by `winedevice.exe`, a sibling of the game, so without this a
        # game keeps the desktop's pointer over it.
        self.handover_siblings = bool(mode.get("handover_siblings", True))
        # Omarchy's own bar is a desktop object: every widget on it opens a
        # popup you click. In game mode the pad is the game's, so none of it
        # can be reached - and a full-screen game is better off with the
        # screen. `omarchy toggle bar` parks it off-screen without restarting
        # the shell, and it is put back on the way out and at shutdown. On by
        # default with `gamebar.enabled`: the bar that replaces it is only
        # worth drawing where the desktop one has gone.
        self.hide_bar_in_game = bool(mode.get("hide_bar_in_game", True))
        # In game mode nobody is looking at the desktop straight-on, so the
        # screensaver firing while a cloud game pauses or a menu idles reads as
        # a black screen over the game. `omarchy toggle idle stay-awake` is the
        # same best-effort flag flip as the bar one, and it is undone on the way
        # out and at shutdown like the bar is. On by default with game mode, for
        # the same reason as `hide_bar_in_game`: game mode is the couch, and an
        # idle-fallen desktop at the foot of the bed is game mode talking over
        # the one audience it exists for.
        self.stay_awake_in_game = bool(mode.get("stay_awake_in_game", True))
        # What the sticks do in game mode, where an empty string means "the
        # same as on the desktop". It lives in [mode] rather than a
        # [layers.game] because game mode is not held by a button, and a layer
        # without one would make the missing-button check meaningless.
        self.game_left_stick = _stick_role(
            "mode.left_stick", mode.get("left_stick", ""), allow_empty=True
        )
        self.game_right_stick = _stick_role(
            "mode.right_stick", mode.get("right_stick", ""), allow_empty=True
        )

        pointer = data.get("pointer", {})
        self.pointer_speed = float(pointer.get("speed", 1100.0))
        self.pointer_accel = float(pointer.get("accel", 2.2))
        # The dead zone belongs to the stick, not to what the stick is doing:
        # the slop is in the hardware, and the right stick has the same wear
        # walking a game's controls as it has scrolling the desktop. The right
        # one ships wider because it ships in the `scroll` role, where a page
        # sliding away under a thumb that never asked costs more than a notch
        # that arrives late; give it the aiming role and it is worth bringing
        # down to the left one's. A config that still names the zones the way
        # the roles did is renamed on the way in - see `_renamed`.
        self.left_deadzone = float(pointer.get("left_deadzone", 0.10))
        self.right_deadzone = float(pointer.get("right_deadzone", 0.18))
        # A whole stick of dead zone leaves nothing to aim with, and
        # `apply_curve` divides by what is left of the travel, so 1.0 is a
        # division by zero rather than a stick that does nothing.
        for side in ("left", "right"):
            if not 0.0 <= getattr(self, "%s_deadzone" % side) < 1.0:
                raise ConfigError(
                    "pointer.%s_deadzone must be 0 or more and under 1" % side
                )
        self.precision_button = pointer.get("precision_button", "ZL") or None
        self.precision_factor = float(pointer.get("precision_factor", 0.28))
        self.poll_hz = max(30, int(pointer.get("poll_hz", 125)))
        # Whether a press that is not the pointer's own takes the pointer off
        # screen until something points again. What does the hiding is the
        # compositor's own `cursor:hide_on_key_press`, so this is which
        # presses ask for it, not whether it can happen - see
        # `Daemon.pointer_away`.
        self.hide_pointer = bool(pointer.get("hide_on_press", True))
        self.left_stick = _stick_role(
            "pointer.left_stick", pointer.get("left_stick", "cursor")
        )
        self.right_stick = _stick_role(
            "pointer.right_stick", pointer.get("right_stick", "scroll")
        )
        # Some pads (notably Beitong KP-series in NS mode) neither report their
        # analog sticks exactly at the device's advertised centre, nor emit a
        # fresh event to announce a return to rest. The daemon then keeps the
        # last value it saw - typically a small offset past the deadzone - and
        # the cursor drifts off to a corner as if the still stick were pressed.
        # recenter re-bases the "neutral" of each axis to what the stick
        # actually rests at around connect, so an idle stick really reads 0.
        self.recenter = bool(pointer.get("recenter", True))
        # A resting value further than this fraction of the range from the
        # device centre is assumed to be a stick the user is holding at connect
        # rather than the pad's true rest, and is left alone. The far side of
        # the same number is how much travel calibrating would leave: the
        # nearer end is `1 - limit` of the advertised half-range away, so 0.60
        # is also "never calibrate onto a rest that leaves under 40% of the
        # range to reach full deflection with".
        self.recenter_limit = float(pointer.get("recenter_limit", 0.60))
        if not 0.0 < self.recenter_limit <= 1.0:
            raise ConfigError(
                "pointer.recenter_limit must be above 0 and at most 1"
            )

        # A hold that announces itself before acting (see `confirm_ms` on a
        # binding) is backed out of with this button, wherever it is bound.
        # The pointer game mode draws instead of the desktop's arrow, and the
        # theme to put back on the way out. An empty restore theme is read off
        # the desktop at the moment of the swap rather than guessed here, so a
        # user who changes their cursor while omapad runs still gets theirs
        # back.
        pointer_cursor = data.get("cursor", {})
        self.cursor_enabled = bool(pointer_cursor.get("enabled", True))
        # A directory name, not a path: `cursor.install` writes into
        # ~/.local/share/icons/<theme> and unlinks the shapes it no longer
        # carries from inside it, so a name with a `/` or a `..` in it would
        # be some other theme's directory being written to and pruned. Named
        # here, where `omapad check` can say so, rather than at the press.
        self.cursor_theme = str(pointer_cursor.get("theme", "omapad-ring")).strip()
        if (not self.cursor_theme or "/" in self.cursor_theme
                or self.cursor_theme in (".", "..")):
            raise ConfigError(
                "cursor.theme must be a directory name, not a path: %r"
                % (pointer_cursor.get("theme"),))
        self.cursor_size = max(16, int(pointer_cursor.get("size", 48)))
        # `auto` is the desktop theme's own foreground and background; any
        # other name is a key read out of the same file, so "accent" is a
        # pointer in the theme's accent. See cursor.resolve.
        self.cursor_color = pointer_cursor.get("color", "auto")
        self.cursor_outline = pointer_cursor.get("outline", "auto")
        self.cursor_restore_theme = pointer_cursor.get("restore_theme", "") or ""
        self.cursor_restore_size = int(pointer_cursor.get("restore_size", 0))
        # The ring's own proportions, as fractions of the size so it looks like
        # itself at any of them. A dot or a halo at zero is left off.
        self.cursor_thickness = float(pointer_cursor.get("thickness", 0.085))
        self.cursor_dot = float(pointer_cursor.get("dot", 0.05))
        self.cursor_halo = float(pointer_cursor.get("halo", 0.045))
        # The band alone, not the dot: the dot is where the click lands and
        # stays solid whatever this says.
        self.cursor_ring_opacity = min(1.0, max(0.0, float(
            pointer_cursor.get("ring_opacity", 0.75))))
        # all = every cursor shape is the ring; pointer = only the arrow, and
        # the rest are left to the desktop's theme.
        self.cursor_shapes = pointer_cursor.get("shapes", "all")
        # game = only from the couch; always = whenever the daemon is running.
        self.cursor_apply = pointer_cursor.get("apply", "game")
        if self.cursor_apply not in ("game", "always"):
            raise ConfigError("cursor.apply must be 'game' or 'always'")

        # The burst a click leaves behind. The pointer is the one thing on
        # screen that cannot answer a press by itself - see ripple.py.
        ripple = data.get("ripple", {})
        self.ripple_enabled = bool(ripple.get("enabled", True))
        # 0 means twice the pointer's own size, so the burst reads as
        # something leaving the ring rather than as a second thing that
        # happened near it. Written out, it is a diameter in logical pixels.
        ripple_size = int(ripple.get("size", 0))
        if ripple_size < 0:
            raise ConfigError("ripple.size cannot be negative")
        self.ripple_size = ripple_size or self.cursor_size * 2
        self.ripple_duration = int(ripple.get("duration_ms", 260))
        if self.ripple_duration <= 0:
            raise ConfigError("ripple.duration_ms must be above zero")
        # The ring's band, as a fraction of the size the way the cursor's own
        # proportions are, so the burst looks like itself at any of them.
        self.ripple_thickness = float(ripple.get("thickness", 0.09))
        if not 0.0 < self.ripple_thickness <= 0.5:
            raise ConfigError("ripple.thickness must be between 0 and 0.5")
        self.ripple_socket = ripple.get("socket") or None

        # The noise a press makes. Off by default because it is the one
        # answer this program gives to the room rather than to the hands -
        # see sound.py.
        sound = data.get("sound", {})
        self.sound_enabled = bool(sound.get("enabled", False))
        self.sound_volume = float(sound.get("volume", 0.6))
        if not 0.0 <= self.sound_volume <= 1.0:
            raise ConfigError("sound.volume must be between 0 and 1")
        # A directory, and it is not checked for the four files: a pack that
        # holds only `commit.wav` keeps the other three from the shipped set,
        # which is what makes replacing one sound worth doing. Expanded here
        # so `~/sounds` is a path the shell can open - the plugin is handed
        # this and has no shell of its own to expand it with.
        pack = str(sound.get("pack", "") or "").strip()
        self.sound_pack = os.path.expanduser(pack) if pack else ""
        if self.sound_pack and not os.path.isdir(self.sound_pack):
            raise ConfigError("sound.pack is not a directory: %s"
                              % self.sound_pack)
        self.sound_socket = sound.get("socket") or None

        # Walking the focus with the app's own keys (item: tab traversal).
        # Which key each step sends is config rather than code because the
        # answer is not the same everywhere - a list wants the arrows, a form
        # wants Tab - and an app that disagrees can be given its own.
        traverse = data.get("traverse", {})
        self.traverse_keys = {}
        for step, default in TRAVERSE_DEFAULTS:
            chord = str(traverse.get(step, default) or "").strip()
            if not chord:
                continue  # a step deliberately turned off
            try:
                self.traverse_keys[step] = keymap.parse_chord(chord)
            except keymap.KeyParseError as exc:
                raise ConfigError("traverse.%s: %s" % (step, exc)) from exc
        self.traverse_repeat_delay = float(
            traverse.get("repeat_delay_ms", 350)
        ) / 1000.0
        self.traverse_repeat_rate = float(
            traverse.get("repeat_rate_ms", 90)
        ) / 1000.0
        # Every stick walk on the pad takes its rate from here, the menu's
        # grid included, so this ramp is the one that reaches all of them.
        (self.traverse_repeat_ramp,
         self.traverse_repeat_ramp_time) = _repeat_ramp(traverse, "traverse")
        # A stick with the "focus" role. Lower than a snap flick: this one
        # repeats while it is held, so it is a direction rather than a shove.
        self.traverse_flick = float(traverse.get("flick", 0.65))
        self.traverse_release = float(traverse.get("release", 0.35))
        # Which step each way of the stick means. Tab order across and arrows
        # up and down is what most apps want, but a vertical list walked with
        # Tab is just as common - so it is named rather than assumed.
        self.traverse_stick = {}
        stick = traverse.get("stick") or {}
        for way, default in TRAVERSE_STICK_DEFAULTS:
            step = str(stick.get(way, default) or "").strip().lower()
            if not step:
                continue  # a direction deliberately turned off
            if step not in dict(TRAVERSE_DEFAULTS):
                raise ConfigError(
                    "traverse.stick.%s: %r is not a focus step" % (way, step)
                )
            self.traverse_stick[way] = step

        snap = data.get("snap", {})
        self.snap_focus = bool(snap.get("focus", True))
        self.snap_same_monitor = bool(snap.get("same_monitor", True))
        # A stick with the "snap" role fires once per push. It has to cross
        # `flick` to fire and fall back under `release` before it can fire
        # again, which is the same hysteresis the analog triggers use and for
        # the same reason: a stick held over is one press, not a stream.
        self.snap_flick = float(snap.get("flick", 0.75))
        self.snap_release = float(snap.get("release", 0.45))
        self.snap_bias = float(
            snap.get("bias", snap_module.PERPENDICULAR_WEIGHT)
        )
        # A binding can already ask for a tick with `rumble = true`; a stick
        # cannot, because a role is not a binding. This is that switch for the
        # snap stick - and a snap is the case the motor is for, since the
        # pointer arrives somewhere you were not looking.
        self.snap_rumble = bool(snap.get("rumble", False))

        swap = data.get("swap", {})
        # A stick with the "swap" role, and the tiled half of "move". The same
        # hysteresis as a snap - cross `flick` to fire, fall back under
        # `release` before it fires again - on its own numbers, because this
        # one rearranges the screen: a window swapped one place too far is a
        # worse mistake than a pointer that landed on the wrong window, so it
        # asks for a firmer push than [snap] does.
        self.swap_flick = float(swap.get("flick", 0.85))
        self.swap_release = float(swap.get("release", 0.45))
        if not 0.0 <= self.swap_release < self.swap_flick <= 1.0:
            raise ConfigError(
                "swap.release must be 0 or more and below swap.flick, which"
                " must be at most 1.0"
            )

        idle = data.get("idle", {})
        # How long the pad keeps the screen awake after it was last touched.
        # Kept in seconds like every other duration here; 0 is the hold that
        # never lets go, which is what every surface did before this existed.
        self.idle_awake = float(idle.get("awake_ms", 300000)) / 1000.0
        if self.idle_awake < 0:
            raise ConfigError("idle.awake_ms must be 0 or more")

        confirm = data.get("confirm", {})
        self.confirm_cancel = confirm.get("cancel_button", "B")
        # The two halves of an announced hold, for every binding that says
        # `confirm = true` rather than naming its own: how long it waits
        # before it ticks and says what is coming, and how long the countdown
        # after that lasts. One setting rather than a number repeated on every
        # binding that has to reach past an app holding the pad.
        self.confirm_hold_ms = int(confirm.get(
            "hold_ms", actions_module.ANNOUNCED_MS[0]))
        self.confirm_ms = int(confirm.get(
            "confirm_ms", actions_module.ANNOUNCED_MS[1]))
        if self.confirm_hold_ms <= 0 or self.confirm_ms <= 0:
            raise ConfigError("confirm.hold_ms and confirm.confirm_ms must be"
                              " positive")
        # And what holding costs the hand doing it, which is the same
        # question asked of every hold at once rather than of one binding.
        # Bounded both ways for the same reason: under a half a tap and a
        # hold are no longer different gestures, and over a double a hold is
        # long enough that nobody reaches the end of it.
        self.confirm_scale = float(confirm.get("scale", 1.0))
        if not 0.5 <= self.confirm_scale <= 2.0:
            raise ConfigError("confirm.scale must be between 0.5 and 2.0")
        # How long a finger may come off a hold that has already announced
        # itself. Zero is the shipped promise that letting go backs out.
        self.confirm_slack_ms = int(confirm.get("slack_ms", 0))
        if self.confirm_slack_ms < 0:
            raise ConfigError("confirm.slack_ms must be 0 or more")

        rumble = data.get("rumble", {})
        self.rumble_enabled = bool(rumble.get("enabled", True))
        self.rumble_strong = float(rumble.get("strong", 0.20))
        self.rumble_weak = float(rumble.get("weak", 0.0))
        self.rumble_duration = int(rumble.get("duration_ms", 60))
        self.rumble_edge_strength = float(rumble.get("edge_strength", 0.35))
        self.rumble_edge_duration = int(rumble.get("edge_duration_ms", 70))
        self.rumble_commit_strength = float(
            rumble.get("commit_strength", 0.28))
        self.rumble_commit_duration = int(
            rumble.get("commit_duration_ms", 90))
        # On, where it shipped off. What it says is no longer a flat hum
        # under a moving thumb - the thing decision 17's rule is about - but
        # how far a value has been taken from where it stood, which is
        # silence until something has actually been changed.
        self.rumble_texture = bool(rumble.get("texture", True))
        # Re-derived when the texture stopped being a scale: a level that
        # only ever rose to this from a floor could afford to be low, and a
        # flat one that has to be felt through a thumb in motion cannot.
        self.rumble_texture_strength = float(
            rumble.get("texture_strength", 0.25))
        self.rumble_floor = int(rumble.get("floor_ms", 50))
        for key, value in (("strong", self.rumble_strong),
                           ("weak", self.rumble_weak),
                           ("edge_strength", self.rumble_edge_strength),
                           ("commit_strength", self.rumble_commit_strength),
                           ("texture_strength",
                            self.rumble_texture_strength)):
            if not 0.0 <= value <= 1.0:
                raise ConfigError("rumble.%s must be between 0 and 1" % key)
        for key, value in (("duration_ms", self.rumble_duration),
                           ("edge_duration_ms", self.rumble_edge_duration),
                           ("commit_duration_ms",
                            self.rumble_commit_duration)):
            if value <= 0:
                raise ConfigError("rumble.%s must be positive" % key)
        if self.rumble_floor < 0:
            raise ConfigError("rumble.floor_ms cannot be negative")

        scroll = data.get("scroll", {})
        self.scroll_speed = float(scroll.get("speed", 8.0))
        self.scroll_accel = float(scroll.get("accel", 2.0))
        self.scroll_natural = bool(scroll.get("natural", False))
        # Two different things are called acceleration, and this file has both.
        # `accel` above is the response curve: how far the stick is over, into
        # how fast it goes. `ramp` is the one a long page asks for: a stick
        # held over keeps getting faster, up to this many times the speed,
        # reached after ramp_ms of holding. 1.0 is off, and is what a mouse
        # wheel does.
        self.scroll_ramp = float(scroll.get("ramp", 3.0))
        if self.scroll_ramp < 1.0:
            raise ConfigError(
                "scroll.ramp is how many times faster a held stick gets, so it "
                "cannot be below 1.0 (got %r)" % self.scroll_ramp
            )
        self.scroll_ramp_ms = max(0.0, float(scroll.get("ramp_ms", 900.0)))

        # -- how big the surfaces draw ------------------------------------
        #
        # A multiplier over the shell's own scale, not a replacement for it: a
        # theme that already runs roomy keeps its proportions here. Game mode
        # gets its own because the same screen is read from a sofa there, and
        # the size that works at a desk is not the size that works across a
        # room.
        ui = data.get("ui", {})
        self.ui_scale = float(ui.get("scale", 1.0))
        self.ui_game_scale = float(ui.get("game_scale", 1.0))
        for name, value in (("scale", self.ui_scale),
                            ("game_scale", self.ui_game_scale)):
            if value <= 0:
                raise ConfigError("ui.%s must be greater than zero" % name)
        # How long every animation on every surface runs, as a multiplier.
        # It rides the same payload the scale does and for the same reason:
        # the plugin cannot read this file, and a surface has to be redrawn
        # at the new number the moment it changes rather than at the next
        # restart. 0 is motion off - every animation lands on its last frame
        # at once. 1 is the top of the range rather than the middle of it:
        # this asks for *less* motion, and a surface slower than it was drawn
        # to be is the lag every duration on it was kept short to avoid.
        self.ui_motion = float(ui.get("motion", 1.0))
        if not 0.0 <= self.ui_motion <= 1.0:
            raise ConfigError("ui.motion must be between 0 and 1")
        # Whether the compositor's own answer about animations is allowed to
        # veto the number above. A veto rather than a scale - see the comment
        # in config.toml, and `daemon.view_motion`.
        self.ui_motion_follows_desktop = bool(
            ui.get("motion_follows_desktop", True)
        )
        # What a television takes off its own edges. A share of each side
        # rather than a number of pixels: it is a property of the set, which
        # crops a proportion, and the surfaces are drawn at every resolution
        # somebody plugs one in at. A fifth of the screen is the most this
        # can mean before it is throwing the screen away rather than keeping
        # its edge clear.
        # 0 rather than broadcast's 5%: game mode is the couch environment
        # and not proof of a television, and every edge of a monitor shows
        # what it is sent. See the comment on the setting.
        self.ui_safe_area = float(ui.get("safe_area", 0.0))
        if not 0.0 <= self.ui_safe_area <= 0.2:
            raise ConfigError("ui.safe_area must be between 0 and 0.2")
        # The family the surfaces set their words in, and the empty string
        # means the desktop's own. It rides the payload beside the scale for
        # the scale's reason - the plugin cannot read this file - and it is a
        # *name* rather than a list: Qt takes one family in `font.family`, so
        # a comma here would be a font nobody has installed.
        #
        # It does not reach the badges, and cannot: a button's label is
        # punched out of its silhouette by `assets/generate.py` in the face
        # shipped beside it, so a typed label in another family would stand
        # next to a drawn one that did not match.
        #
        # Not on the pad, and that is the rule rather than an omission: what
        # this takes is the name of a face somebody has installed, and a
        # thumb cannot type one - every setting the menu carries is a switch,
        # a list of words or a ladder of numbers.
        self.ui_font = str(ui.get("font", "")).strip()
        if "," in self.ui_font:
            raise ConfigError(
                "ui.font names one family, not a list - Qt takes a single "
                "name and falls back on its own"
            )
        # How hard a corner is rounded, against what the compositor rounds a
        # window by. The ceiling is the ladder's own top stop: past it a tile
        # is not a rounded rectangle any more, it is a lozenge.
        self.ui_radius = float(ui.get("radius", 1.0))
        if not 0.0 <= self.ui_radius <= RADIUS_STOPS[-1]:
            raise ConfigError("ui.radius must be between 0 and %g"
                              % RADIUS_STOPS[-1])
        # The shell cannot read this file, so which of the two a surface draws
        # travels in its payload beside the scale.
        self.ui_badge_style = str(ui.get("badge_style", "filled"))
        if self.ui_badge_style not in BADGE_STYLES:
            raise ConfigError(
                "ui.badge_style must be one of %s" % ", ".join(BADGE_STYLES)
            )
        # Whether omapad asks the compositor to blur behind its own surfaces.
        # A request, not a promise: Hyprland only blurs where blur is on at
        # all, so this does nothing on a desktop that has turned it off, and
        # `[menu] dim` is what has to carry the contrast there.
        self.ui_blur = bool(ui.get("blur", True))
        self.ui_blur_rule = str(ui.get("blur_rule", "")).strip() or (
            'hl.layer_rule({ match = { namespace = "omapad-.*" },'
            ' blur = true, ignore_alpha = %s })'
        )
        self.ui_blur_alpha = float(ui.get("blur_alpha", 0.15))
        if not 0.0 <= self.ui_blur_alpha <= 1.0:
            raise ConfigError("ui.blur_alpha must be between 0 and 1")

        osk = data.get("osk", {})
        self.osk_socket = osk.get("socket") or None
        self.osk_layout = osk.get("layout", "grid")
        self.osk_labels_follow_layout = bool(
            osk.get("labels_follow_layout", True)
        )
        # Print the pad button that reaches a key beside it, where one does.
        self.osk_badges = bool(osk.get("badges", True))
        # And where on the key it goes - see osk.BADGE_ALIGNS.
        self.osk_badge_align = osk.get("badge_align",
                                       osk_module.DEFAULT_BADGE_ALIGN)
        if self.osk_badge_align not in osk_module.BADGE_ALIGNS:
            raise ConfigError("osk.badge_align must be one of %s, not %r"
                              % (", ".join(osk_module.BADGE_ALIGNS),
                                 self.osk_badge_align))
        self.control_socket = data.get("control", {}).get("socket") or None
        # Per-key label and action overrides, keyed by a key's default action.
        # Values are tables: { label = "…", action = "…" }, either half
        # optional. A bare string is taken as the label, which is what most of
        # these are.
        self.osk_key_overrides = {}
        for action, spec in (osk.get("keys") or {}).items():
            if isinstance(spec, str):
                spec = {"label": spec}
            if isinstance(spec, dict):
                self.osk_key_overrides[action] = spec
        # What the keyboard's microphone key runs. Empty is a keyboard with no
        # such key at all, and so is a command whose program this machine has
        # not got: a key that cannot work is one you press from across a room
        # while the screen does not change. Only the first word is looked for,
        # so a command that needs an environment in front of it wants a script
        # of its own to be the first word instead.
        self.osk_dictate = str(
            osk.get("dictate", "voxtype record toggle")
        ).strip()
        first = self.osk_dictate.split()
        if first and not shutil.which(first[0]):
            self.osk_dictate = ""
        # And the two halves of the same thing, for the button that holds the
        # microphone open rather than switching it on. Not derived from the
        # one above: a command is a command, and guessing that `toggle` can be
        # turned into `start` is guessing about somebody else's program.
        self.osk_talk_start = str(
            osk.get("talk_start", "voxtype record start")
        ).strip()
        self.osk_talk_stop = str(
            osk.get("talk_stop", "voxtype record stop")
        ).strip()
        for attr in ("osk_talk_start", "osk_talk_stop"):
            first = getattr(self, attr).split()
            if first and not shutil.which(first[0]):
                setattr(self, attr, "")
        # Where whatever that command started says what it is doing, so the key
        # can be lit while the microphone is open. A file rather than a
        # command, because the answer is wanted several times a second.
        self.osk_dictate_state = os.path.expanduser(os.path.expandvars(
            str(osk.get("dictate_state", "$XDG_RUNTIME_DIR/voxtype/state"))
        )).strip()
        # Where dictation puts what was said, and what says so to the tool
        # that puts it there. omapad never sees the words - voxtype types them
        # itself and leaves no transcript behind - so this setting is a switch
        # thrown at somebody else's program rather than a thing the daemon
        # does, and the two commands are how it is thrown.
        self.osk_dictate_clipboard = bool(osk.get("dictate_clipboard", False))
        self.osk_dictate_clipboard_on = str(
            osk.get("dictate_clipboard_on", "")
        ).strip()
        self.osk_dictate_clipboard_off = str(
            osk.get("dictate_clipboard_off", "")
        ).strip()
        if bool(self.osk_dictate_clipboard_on) != bool(
                self.osk_dictate_clipboard_off):
            # A switch that can only go one way leaves whoever flipped it back
            # worse off than never having offered it: the words are on the
            # clipboard for good and nothing on the pad says why.
            raise ConfigError(
                "osk.dictate_clipboard_on and osk.dictate_clipboard_off are "
                "both needed, or neither"
            )
        self.osk_repeat_delay = float(osk.get("repeat_delay_ms", 350)) / 1000.0
        self.osk_repeat_rate = float(osk.get("repeat_rate_ms", 70)) / 1000.0
        (self.osk_repeat_ramp,
         self.osk_repeat_ramp_time) = _repeat_ramp(osk, "osk")

        menu = data.get("menu", {})
        self.menu_socket = menu.get("socket") or None
        self.menu_title = menu.get("title", "Go")
        # Whether the menu still owes somebody a first start. The daemon
        # writes it false the first time the menu is opened, which is what
        # makes the `Start here` tile a thing that happens once.
        self.menu_first_run = bool(menu.get("first_run", True))
        # A list, so the deep merge replaces it wholesale rather than merging
        # entry by entry - which is what you want: a user menu is their menu,
        # not the shipped one with rows spliced in at matching indexes.
        self.menu_items = menu.get("items", [])
        # The read-only grid above the bar, by the same argument: a head
        # somebody wrote is theirs, not the shipped one with cells spliced in.
        self.menu_head = menu.get("head", [])
        # How many cells across a page is. It decides how much fits on one
        # screen and how big a tile reads from across a room, so a laptop
        # panel and a television do not want the same answer. Below three
        # there is nowhere to put a bar, and far above it a tile is a row
        # again.
        self.menu_columns = int(menu.get("columns", 6))
        if self.menu_columns < 3:
            raise ConfigError("menu.columns must be 3 or more")
        # How tall one cell is, unscaled. The width is whatever `columns`
        # leaves, so this is the rest of a tile's shape, and the shell cannot
        # read this file - it travels in the payload like every other geometry
        # setting. A floor rather than any positive number: a cell shorter
        # than a line of text is a page of tiles with nothing legible on them.
        # One module, square: a cell is this wide and this tall, and what
        # does not fit the screen scrolls. Not divided out of the card's width
        # any more - that made the shape of a tile a property of the monitor
        # it landed on.
        self.menu_cell = int(menu.get("cell", 128))
        if self.menu_cell < 16:
            raise ConfigError("menu.cell must be 16 or more")
        # What a tile off to the side costs against one straight ahead, both
        # measured edge to edge - the same question `snap.bias` answers about
        # windows, and its own number because tiles are small and touching
        # where windows are large and sparse. Below 1 the nearest tile wins
        # whatever direction was pressed, which makes the press meaningless.
        self.menu_bias = float(menu.get("bias", 2.0))
        if self.menu_bias < 0:
            raise ConfigError("menu.bias cannot be negative")
        # The day and the time, at the head of the menu. strftime; empty for
        # none. It lives here rather than on the bar because the bar's left end
        # is the menu's own place and two things there read as clutter.
        self.menu_clock = menu.get("clock", "%A %H:%M")
        self.menu_repeat_delay = float(menu.get("repeat_delay_ms", 400)) / 1000.0
        self.menu_repeat_rate = float(menu.get("repeat_rate_ms", 110)) / 1000.0
        (self.menu_repeat_ramp,
         self.menu_repeat_ramp_time) = _repeat_ramp(menu, "menu")
        # How long the worker waits on a row that lists its submenu before
        # calling the listing empty. The press does not wait on it - the page
        # opens and the rows land when they land - so this is how late an
        # answer may be and still be worth drawing, not the pad's own pause.
        self.menu_list_timeout = float(menu.get("list_timeout_ms", 1000)) / 1000.0
        if self.menu_list_timeout <= 0:
            raise ConfigError("menu.list_timeout_ms must be more than 0")
        # And how many of its lines reach the page. A listing is a command's
        # output, so a broken one can print a log file; the menu is walked one
        # row at a time with a thumb and has nowhere to put a hundred of them.
        self.menu_list_limit = int(menu.get("list_limit", 24))
        if self.menu_list_limit < 1:
            raise ConfigError("menu.list_limit must be 1 or more")
        # How long a flick across the bar waits before a group that lists its
        # tiles asks. Walking five chips in a second should spawn one command,
        # not five, and the chip you stop on is the only one worth asking
        # about.
        self.menu_group_settle = float(
            menu.get("group_settle_ms", 180)) / 1000.0
        if self.menu_group_settle < 0:
            raise ConfigError("menu.group_settle_ms cannot be negative")
        # Whether the card prints what its face buttons do along the foot. In
        # game mode omapad's own bar is already along an edge saying the same
        # thing, and somebody running that may not want it said twice - but
        # the two are not the same answer in general: the bar is the screen's
        # and this is the page's, and only this one can show a key the page in
        # front has spent on a job of its own.
        self.menu_keys = bool(menu.get("keys", True))
        # How much bigger one push of a held direction gets on a control with
        # a range, and how long it takes to get there. A slider walked one
        # step per repeat is thirty-eight presses end to end on the shipped
        # pointer speed; this is what a held wheel does about the same
        # problem, with the same reversal reset.
        self.menu_ramp = float(menu.get("ramp", 4.0))
        if self.menu_ramp < 1.0:
            raise ConfigError("menu.ramp is 1.0 or more (1.0 is off)")
        self.menu_ramp_ms = int(menu.get("ramp_ms", 900))
        if self.menu_ramp_ms < 0:
            raise ConfigError("menu.ramp_ms cannot be negative")
        # How long a fully pulled trigger takes to cross a control's whole
        # range. Half pulled takes twice as long, so the number is the fastest
        # the control ever moves rather than the only speed it has.
        self.menu_sweep_ms = int(menu.get("sweep_ms", 1500))
        if self.menu_sweep_ms <= 0:
            raise ConfigError("menu.sweep_ms must be positive")
        # How far a thumb has to carry a knob round to cross its whole range,
        # and how far over the stick has to be before an angle is worth
        # reading at all. The first is the gearing of the one gesture on this
        # pad that is a turn; the second is what stops a thumb resting near
        # the middle - where a degree is noise - from moving anything.
        # Which gesture a ring answers to. `aim` puts the value where the
        # thumb points, because a drawn knob has a pointer and the stick is
        # one; `carry` moves it by how far the thumb has travelled, which
        # cannot jump on the frame a hand lands. The two gearing numbers
        # below are `carry`'s alone - an aimed dial has no gearing to have.
        self.menu_turn = str(menu.get("turn", "aim"))
        if self.menu_turn not in ("aim", "carry"):
            raise ConfigError("menu.turn must be 'aim' or 'carry'")
        self.menu_turn_degrees = float(menu.get("turn_degrees", 270.0))
        if self.menu_turn_degrees <= 0:
            raise ConfigError("menu.turn_degrees must be positive")
        # And the floor under one step of it, because the gearing above is of
        # the *range* and a thumb aims at a step: the same 270 degrees is a
        # quarter turn per step on a pair of words and seven degrees on the
        # pointer's speed. This is the angle a thumb can stop inside, and the
        # slower of the two always wins.
        self.menu_turn_step_degrees = float(
            menu.get("turn_step_degrees", 30.0))
        if self.menu_turn_step_degrees <= 0:
            raise ConfigError("menu.turn_step_degrees must be positive")
        # `carry`'s, and `aim` has its own below: one integrates travel and
        # the other reads a bearing, so they do not need the same radius.
        self.menu_turn_grip = float(menu.get("turn_grip", 0.5))
        if not 0.0 < self.menu_turn_grip < 1.0:
            raise ConfigError("menu.turn_grip is between 0 and 1")
        # And `aim`'s, which is lower because it keeps nothing: a wobble is an
        # error that corrects itself rather than one that accumulates. Half
        # the travel was a wall - a thumb turning a dial the way a hand turns
        # one reaches about 0.45 of it and stops there.
        self.menu_aim_grip = float(menu.get("aim_grip", 0.25))
        if not 0.0 < self.menu_aim_grip < 1.0:
            raise ConfigError("menu.aim_grip is between 0 and 1")
        # How fast the stick has to be falling inward before it is a stick
        # coming home rather than a thumb still turning. A rate, in stick
        # travel a second: aiming moves about a thousandth of the travel a
        # frame, a spring a quarter of it, so this sits between two numbers
        # two orders of magnitude apart.
        self.menu_turn_return = float(menu.get("turn_return", 4.0))
        if self.menu_turn_return <= 0:
            raise ConfigError("menu.turn_return must be positive")
        # What the sticks do while the menu is up. The implicit surface layers
        # keep the base roles everywhere else, so this is a documented new
        # case rather than a general mechanism: the left one walks the tiles
        # and the right one keeps the pointer, which is what `[menu]` promises
        # about the pointer staying live under the open card.
        self.menu_left_stick = _stick_role(
            "menu.left_stick", menu.get("left_stick", "menu"))
        self.menu_right_stick = _stick_role(
            "menu.right_stick", menu.get("right_stick", "cursor"))
        # How often a gauge is told where the thumb is. A scheduler parameter
        # rather than a second clock: the loop already runs at `poll_hz` while
        # anything needs a tick, and this only decides how many of those turns
        # carry a push.
        # Whether the card fills the screen. A card reads as a menu and a
        # whole screen reads as a page, which is the difference between "I am
        # picking a thing" and "I am in the panel" - and on a television
        # across a room the second one is what a HUD is for.
        self.menu_fullscreen = bool(menu.get("fullscreen", True))
        # How dark the screen behind the card goes, over whatever the theme's
        # own scrim already does. A fullscreen HUD draws no panel, so this is
        # the only thing standing between a tile's label and a window full of
        # text - and with the compositor blurring as well, it is the tint over
        # the blur rather than the whole of the contrast.
        self.menu_dim = float(menu.get("dim", 0.6))
        if not 0.0 <= self.menu_dim <= 1.0:
            raise ConfigError("menu.dim must be between 0 and 1")
        # What a corner is rounded by where the compositor rounds nothing.
        # The shell cannot read this file, so it travels; it asks
        # `decoration:rounding` first and falls back to this, because that is
        # 0 on plenty of setups and at 0 every state of a tile is the same
        # square.
        self.menu_tile_corner = int(menu.get("tile_corner", 23))
        if self.menu_tile_corner < 0:
            raise ConfigError("menu.tile_corner must be 0 or more")
        # How long a tile stays lit after a press lands on it. The shell
        # cannot read this file either, so it travels with the flash it times.
        # How solid a plain tile's ground is drawn, before the tile has said
        # anything about itself. Travels for `tile_corner`'s reason, and is
        # the fill rather than the tile: the ink on it is drawn at full
        # strength whatever this is.
        self.menu_tile_fill = float(menu.get("tile_fill", 1.0))
        if not 0.0 <= self.menu_tile_fill <= 1.0:
            raise ConfigError("menu.tile_fill must be between 0 and 1")
        self.menu_press_ms = int(menu.get("press_ms", 160))
        if self.menu_press_ms < 0:
            raise ConfigError("menu.press_ms must be 0 or more")
        # How long a row that says `countdown = true` counts for. Whole
        # seconds, because the row prints the number: a count that went `9.5`
        # would be a clock rather than a decision somebody is being given time
        # to take back.
        self.menu_countdown = int(menu.get("countdown", 10))
        if self.menu_countdown <= 0:
            raise ConfigError("menu.countdown must be at least one second")
        self.menu_live_hz = int(menu.get("live_hz", 60))
        if self.menu_live_hz <= 0:
            raise ConfigError("menu.live_hz must be positive")
        if self.menu_live_hz > self.poll_hz:
            # A push per turn the loop cannot make. Said rather than silently
            # served at whatever the loop manages, because the number would be
            # a promise the daemon was never keeping.
            raise ConfigError(
                "menu.live_hz is %d, which is more turns than pointer.poll_hz"
                " (%d) gives it" % (self.menu_live_hz, self.poll_hz))

        # What the machine is doing, and the commands that ask and answer.
        # Every one is a setting: a machine that reads its volume some other
        # way is a config change rather than a patch. An empty string is a
        # reading this machine does not have, and nothing asks for it.
        live = data.get("live", {})
        self.live_reads = {}
        self.live_writes = {}
        for name in sorted(live_module.READINGS):
            self.live_reads[name] = str(live.get("%s_read" % name, "")).strip()
            self.live_writes[name] = str(live.get("%s_set" % name, "")).strip()
            template = self.live_writes[name]
            if template and "%1" not in template:
                raise ConfigError(
                    "live.%s_set has to say where the value goes, as %%1"
                    % name
                )
        self.live_timeout = float(live.get("timeout_ms", 1000)) / 1000.0
        self.live_poll = float(live.get("poll_ms", 2000)) / 1000.0
        self.live_settle = float(live.get("settle_ms", 250)) / 1000.0
        # How often a number somebody is still moving is actually sent. A
        # level supersedes the one before it, so the ones in between are work
        # for a value nobody stopped on - and the loop can ask far faster than
        # a helper can answer.
        self.live_write = float(live.get("write_ms", 60)) / 1000.0
        for key, value in (("timeout_ms", self.live_timeout),
                           ("poll_ms", self.live_poll),
                           ("settle_ms", self.live_settle),
                           ("write_ms", self.live_write)):
            if value <= 0:
                raise ConfigError("live.%s must be positive" % key)

        # What the machine underneath is doing, and where each answer is
        # published. Every source is a setting because none of these is true
        # of every machine: which chip holds a temperature, whether the
        # graphics card publishes a load at all, whether anything here knows a
        # game's frame rate. An empty source is a reading this machine does
        # not have - nothing asks for it, and no tile is drawn.
        sysinfo = data.get("sysinfo", {})
        self.sysinfo_sources = {}
        for name in sorted(sysinfo_module.READINGS):
            try:
                self.sysinfo_sources[name] = sysinfo_module.source(
                    sysinfo.get(name, ""), "sysinfo.%s" % name
                )
            except sysinfo_module.SysinfoError as exc:
                raise ConfigError(str(exc)) from exc
        # What the two free-form readings count in. Only they have the
        # question: everything else is a kernel ABI with one answer, and a
        # unit on those would be a way to make a tile lie.
        self.sysinfo_units = {}
        self.sysinfo_divisors = {}
        for name in ("gpu", "fps"):
            unit = sysinfo.get("%s_unit" % name)
            if unit is not None:
                self.sysinfo_units[name] = str(unit)
            scale = sysinfo.get("%s_scale" % name)
            if scale is not None:
                self.sysinfo_divisors[name] = float(scale)
                if self.sysinfo_divisors[name] <= 0:
                    raise ConfigError(
                        "sysinfo.%s_scale must be positive" % name
                    )
        self.sysinfo_poll = float(sysinfo.get("poll_ms", 2000)) / 1000.0
        self.sysinfo_timeout = float(sysinfo.get("timeout_ms", 1000)) / 1000.0
        for key, value in (("poll_ms", self.sysinfo_poll),
                           ("timeout_ms", self.sysinfo_timeout)):
            if value <= 0:
                raise ConfigError("sysinfo.%s must be positive" % key)

        # The readings, left on screen. The page is a menu group like any
        # other - which is what puts its tiles where somebody arranged them,
        # here and over a game alike - so almost nothing is settable here: the
        # grid is the menu's and the tiles are the page's.
        hud = data.get("hud", {})
        self.hud_socket = hud.get("socket") or None
        self.hud_show = bool(hud.get("show", False))
        # Which group holds it, by the id of a top-level [[menu.items]] entry.
        # A name rather than a position: a page that moved along the bar is
        # still the same page.
        self.hud_page = str(hud.get("page", "hud")).strip()
        if not self.hud_page:
            raise ConfigError("hud.page names a menu group, and cannot be empty")
        # How solid the readings are over what is behind them. A HUD is read
        # while something else is being watched, so the thing it is over has
        # to stay watchable.
        self.hud_opacity = float(hud.get("opacity", 0.9))
        if not 0.0 < self.hud_opacity <= 1.0:
            raise ConfigError("hud.opacity must be above 0 and at most 1")
        # How many rows the screen is divided into. **This is the whole of why
        # the HUD has a fixed grid and the menu does not**: a menu page is as
        # many rows as its tiles came to and scrolls, so there is no last row
        # to put anything on. A screen has a bottom edge, so the grid has to
        # have one too, or "bottom right" is a cell that is simply not
        # anywhere.
        #
        # It decides how tall a tile is as well as where one can go, because a
        # cell is a share of the screen rather than a number of pixels: raise
        # it for thinner tiles and finer placement, lower it for fewer, bigger
        # ones. There is no arrangement in which those two are separate.
        self.hud_rows = int(hud.get("rows", 12))
        if self.hud_rows < 1:
            raise ConfigError("hud.rows must be 1 or more")
        # How far off the edge of the screen the grid starts, unscaled. Not
        # the menu's own margin, which exists because a card on a television
        # must not sit in the part of the screen that is not there - this one
        # is a corner somebody deliberately put something in, so it defaults
        # to a hair off the edge and goes to 0 for the corner itself.
        self.hud_margin = int(hud.get("margin", 16))
        if self.hud_margin < 0:
            raise ConfigError("hud.margin must be 0 or more")

        guide = data.get("guide", {})
        self.guide_socket = guide.get("socket") or None

        # The quick menu (quick.py). Its tiles are built and checked where the
        # menu's are - by the daemon, which comes up with an empty row rather
        # than not at all, and by `omapad check`, which names the tile - so
        # only what is read here is checked here.
        quick = data.get("quick", {})
        if not isinstance(quick, dict):
            raise ConfigError("quick must be a table")
        self.quick_socket = quick.get("socket") or None
        self.quick_items = quick.get("items", [])

        chrono = data.get("chrono", {})
        # The minute mark: a running stopwatch ticks the pad each time its
        # sweep hand comes round. The only decision the instrument has - the
        # cycle and the pusher are what a monopusher chronograph is - and the
        # turn itself is the dial's geometry rather than a number to set, so
        # there is nothing here to get wrong and nothing to validate.
        self.chrono_rumble = bool(chrono.get("rumble", True))

        self.mapping_socket = data.get("mapping", {}).get("socket") or None
        self.status_socket = data.get("status", {}).get("socket") or None

        gamebar = data.get("gamebar", {})
        # The other half of `mode.hide_bar_in_game`, and on for the same
        # reason: game mode takes the desktop bar away, and a couch with
        # nothing on screen has no way to read where it is or how to get back.
        self.gamebar_enabled = bool(gamebar.get("enabled", True))
        self.gamebar_socket = gamebar.get("socket") or None
        # "auto" follows Omarchy's own `bar.position`, which the plugin
        # already watches for transparency; "top"/"bottom" pin it.
        self.gamebar_position = gamebar.get("position", "auto")
        # How tall the bar is, before the shell's spacing scale. The badges it
        # draws are about 20 of these units, so anything under that crops what
        # the bar exists to show; the plugin floors it at what the row needs.
        self.gamebar_height = int(gamebar.get("height", 32))
        if self.gamebar_height < 1:
            raise ConfigError("gamebar.height must be 1 or more")
        # How far a badge leans at the tick, in the same units as the height.
        # Only the reach is a setting: the lean is one flick and then it
        # stays, and how much longer is left is the sweep's to say. Nothing at
        # all with 0, or big enough to catch the corner of your eye across a
        # room.
        self.gamebar_lean = int(gamebar.get("confirm_lean", 2))
        if self.gamebar_lean < 0:
            raise ConfigError("gamebar.confirm_lean must be 0 or more")
        # How long a badge sits dimmed before it starts filling. A hold that
        # begins to fill on contact flickers under a shoulder tapped to walk
        # browser tabs, which is the commonest press these buttons take; a
        # short wait swallows the flick without making the hold look late.
        # The fill still lands full exactly at the tick - the plugin takes the
        # delay out of the ramp, not off the end.
        self.gamebar_fill_delay_ms = int(gamebar.get("confirm_fill_delay_ms", 60))
        if self.gamebar_fill_delay_ms < 0:
            raise ConfigError("gamebar.confirm_fill_delay_ms must be 0 or more")
        # Actions the bar never prints, because they mean the same wherever you
        # are. By action rather than by button, so rebinding carries the
        # omission with it.
        self.gamebar_omit = tuple(gamebar.get("omit", list(gamebar_module.COMMON)))
        # Which regions of the pad the row of hints prints for - the face
        # buttons by default, because they are the half of the pad that
        # changes under you. See gamebar.HINTED for why the shoulders are not
        # in it. Named by kind rather than by button so a widened list picks
        # up every button in the region without naming any of them.
        bar_kinds = gamebar.get("kinds", list(gamebar_module.HINTED))
        if not isinstance(bar_kinds, (list, tuple)):
            raise ConfigError("gamebar.kinds must be a list of button kinds")
        if not bar_kinds:
            raise ConfigError(
                "gamebar.kinds must name at least one kind of button - the "
                "bar has nowhere else to say what the pad does right now"
            )
        known = sorted(set(guide_module.KINDS.values()))
        for kind in bar_kinds:
            if kind not in known:
                raise ConfigError(
                    "gamebar.kinds: unknown kind %r (one of: %s)"
                    % (kind, ", ".join(known))
                )
        self.gamebar_kinds = tuple(bar_kinds)
        # Whether the hints are one word or the phrase the guide prints. The
        # bar is glanced at over the top of a game and has three slots to say
        # where you are in; the guide is the page you read. Turn it off for
        # the long form in both places - a bar across a room, or a scheme
        # whose bindings are hard to name in a word.
        self.gamebar_brief = bool(gamebar.get("brief", True))
        # Whether a pointer may fire what a badge names. The bar was drawn for
        # a thumb, but game mode is the couch environment and not a hand-off:
        # the desktop is still there, and so is whatever pointer is on it. Off
        # gives back a strip that swallows no clicks at all.
        self.gamebar_click = bool(gamebar.get("click", True))

        window = data.get("window", {})
        self.window_step = float(window.get("step", 900.0))
        self.window_hz = float(window.get("update_hz", 30.0))

        # What `term:interrupt` does with its two answers. Parsed here rather
        # than when the button is pressed, so a typo is something `omapad
        # check` names instead of a window that will not close.
        terminal = data.get("terminal", {})
        self.terminal_interrupt = self._terminal_action(
            terminal, "interrupt", "key:CTRL+C"
        )
        self.terminal_idle = self._terminal_action(
            terminal, "idle", "hypr:hl.dsp.window.close()"
        )
        # How far below the focused window's process to look for a shell. The
        # emulators measured here start it as a direct child; the rest is for a
        # wrapper script or a login shell in between.
        self.terminal_depth = int(terminal.get("depth", 4))
        if self.terminal_depth < 1:
            raise ConfigError("terminal.depth must be 1 or more")

        self.layers = []
        for name, spec in (data.get("layers") or {}).items():
            if not isinstance(spec, dict) or "button" not in spec:
                raise ConfigError("layer %r needs a 'button' key" % name)
            self.layers.append(
                Layer(
                    name=name,
                    button=spec["button"],
                    left_stick=_stick_role(
                        "layer %r left_stick" % name, spec.get("left_stick", "none")
                    ),
                    right_stick=_stick_role(
                        "layer %r right_stick" % name, spec.get("right_stick", "none")
                    ),
                    fallthrough=bool(spec.get("fallthrough", False)),
                    reaches_past=bool(spec.get("reaches_past", False)),
                )
            )

        self.bindings = data.get("bindings", {})
        for layer in self.layers:
            self.bindings.setdefault(layer.name, {})
        self.bindings.setdefault("base", {})
        # The keyboard, menu and guide layers are implicit: they activate when
        # their surface is up rather than while a button is held, so none of
        # them has a [layers.*] entry.
        self.bindings.setdefault("osk", {})
        self.bindings.setdefault("menu", {})
        self.bindings.setdefault("quick", {})
        self.bindings.setdefault("guide", {})
        # So is game mode, which activates with the mode rather than with a
        # surface. Empty by default: the pad belongs to the game there, and
        # every button this names is one the game stops seeing.
        self.bindings.setdefault("game", {})

        # Chords are deliberately global rather than per-layer: the one they
        # exist for is the way out of game mode, which has to work from
        # wherever you are.
        self.chords = []
        for combo, spec in (data.get("chords") or {}).items():
            buttons = frozenset(
                part.strip() for part in combo.split("+") if part.strip()
            )
            if len(buttons) < 2:
                raise ConfigError("chord %r needs at least two buttons" % combo)
            if not isinstance(spec, str):
                raise ConfigError("chord %r must be a plain action" % combo)
            self.chords.append((buttons, spec))
        # Longest first, so a three-button chord is not shadowed by a two-button
        # one it contains.
        self.chords.sort(key=lambda entry: -len(entry[0]))

        # The keyboard on the desk, while a surface of ours is on screen.
        # Its tables are named after the surfaces exactly the way the pad's
        # are - [keyboard.bindings.base] is the fallback, [keyboard.bindings.
        # menu] the one that outranks it while the menu is up - because that
        # is the shape someone editing this file has already learned.
        keyboard = data.get("keyboard") or {}
        if not isinstance(keyboard, dict):
            raise ConfigError("keyboard must be a table")
        self.keyboard_enabled = bool(keyboard.get("enabled", True))
        self.keyboard_match = str(keyboard.get("match", "auto"))
        self.keyboard_grab = bool(keyboard.get("grab", False))
        ignore = keyboard.get("ignore", [])
        if isinstance(ignore, str):
            ignore = [ignore]
        if not isinstance(ignore, list) or not all(
            isinstance(token, str) for token in ignore
        ):
            raise ConfigError("keyboard.ignore must be a list of names")
        self.keyboard_ignore = tuple(ignore)
        # code -> action, per surface. Resolved to keycodes here rather than at
        # the press: a key name nobody has is a mistake `omapad check` should
        # name, and the loop should not be looking names up while typing.
        self.keyboard_bindings = {}
        tables = keyboard.get("bindings") or {}
        if not isinstance(tables, dict):
            raise ConfigError("keyboard.bindings must be a table")
        for surface, binds in tables.items():
            if surface not in KEYBOARD_SURFACES:
                raise ConfigError(
                    "keyboard.bindings.%s: no such surface (try %s)"
                    % (surface, ", ".join(sorted(KEYBOARD_SURFACES)))
                )
            if not isinstance(binds, dict):
                raise ConfigError(
                    "keyboard.bindings.%s must be a table" % surface
                )
            table = {}
            for key, spec in binds.items():
                try:
                    code = keymap.resolve(key)
                except keymap.KeyParseError as exc:
                    raise ConfigError(
                        "keyboard.bindings.%s: %s" % (surface, exc)
                    ) from exc
                if not isinstance(spec, str):
                    # No tap/hold tables here: a keyboard already repeats, and
                    # holding a key to mean something else is not what one is.
                    raise ConfigError(
                        "keyboard.bindings.%s.%s must be a plain action"
                        % (surface, key)
                    )
                table[code] = spec
            self.keyboard_bindings[surface] = table

        # Per-application profiles (item 09): a [profile.<name>] table matches a
        # focused window by class and layers its own [bindings] over the shipped
        # ones. The resolution order becomes profile -> layer -> base, so an app
        # changes only the buttons it names and everything else keeps working.
        #
        # Its bindings are the app's scheme *at rest* and stop where a modifier
        # starts (item 38): ZL + B closes the window in every app, whatever B
        # is worth in the one in front. An app that wants a held layer's button
        # too names the layer - [profile.<name>.window] - and that table is read
        # in [bindings.window]'s place for as long as the app has focus.
        self.profiles = []
        for name, spec in (data.get("profile") or {}).items():
            if not isinstance(spec, dict):
                raise ConfigError("profile %r must be a table" % name)
            matches = spec.get("match")
            if isinstance(matches, str):
                matches = [matches]
            if not isinstance(matches, list) or not matches or not all(
                isinstance(m, str) and m.strip() for m in matches
            ):
                raise ConfigError(
                    "profile %r needs a 'match' string (or list of strings)" % name
                )
            bindings = spec.get("bindings") or {}
            if not isinstance(bindings, dict):
                raise ConfigError("profile %r bindings must be a table" % name)
            # Whether this application may be handed the pad at all. The
            # question is normally answered by /proc - has the focused app
            # opened the pad - and that answer is right for anything that
            # opens one in order to be played with. It is wrong for an
            # application that opens the pad for some other reason: Discord
            # polls the Gamepad API for its own keybinds, and taking it at
            # its word costs the pointer for as long as it is focused. The
            # class is already named here, so this is where the exception
            # belongs.
            handed = spec.get("handover", True)
            if not isinstance(handed, bool):
                raise ConfigError(
                    "profile %r handover must be true or false" % name
                )
            # Every other key is a held layer the app disagrees with. Unknown
            # ones raise rather than being ignored, because the failure is
            # otherwise silent: [profile.shell.windows] would simply never
            # fire, and nothing on screen would say why.
            layers = {}
            for key, table in spec.items():
                if key in PROFILE_KEYS:
                    continue
                if self.layer(key) is None:
                    raise ConfigError(
                        "profile %r: %r is neither a profile key (%s) nor a "
                        "layer in [layers.*]"
                        % (name, key, ", ".join(sorted(PROFILE_KEYS)))
                    )
                if not isinstance(table, dict):
                    raise ConfigError(
                        "profile %r layer %r must be a table" % (name, key)
                    )
                layers[key] = table
            self.profiles.append(
                {
                    "name": name,
                    "match": [m.strip().lower() for m in matches],
                    "bindings": bindings,
                    "layers": layers,
                    "handover": handed,
                    "osk": parse_app_page(name, spec.get("osk")),
                    # An app may also disagree about what a stick is for. Empty
                    # means "whatever the layer says", so a profile that only
                    # rebinds buttons leaves both thumbs alone.
                    "left_stick": _stick_role(
                        "profile %r left_stick" % name,
                        spec.get("left_stick", ""),
                        allow_empty=True,
                    ),
                    "right_stick": _stick_role(
                        "profile %r right_stick" % name,
                        spec.get("right_stick", ""),
                        allow_empty=True,
                    ),
                }
            )

        # Buttons that act purely as modifiers never fire their own binding.
        self.modifier_buttons = {layer.button for layer in self.layers}
        if self.precision_button:
            self.modifier_buttons.add(self.precision_button)

    def _terminal_action(self, table, key, default):
        """One half of `term:interrupt`, parsed and named where it is wrong."""
        spec = table.get(key, default)
        try:
            return actions_module.parse(spec)
        except actions_module.ActionError as exc:
            raise ConfigError("terminal.%s: %s" % (key, exc)) from exc

    def profile_matching(self, window_class):
        """The active profile for a window class, or None.

        Matches are case-insensitive substrings of the class (Hyprland reports
        `foot`, `Alacritty`, `org.wezfurlong.wezterm`). The first declared
        profile whose match hits wins, so declare the more specific one first.
        An empty or unknown class has no profile: the pad falls back to its
        ordinary layers.
        """
        cls = (window_class or "").lower()
        if not cls:
            return None
        for profile in self.profiles:
            if any(match in cls for match in profile["match"]):
                return profile
        return None

    def binding_with_profile(self, profile, layer_name, button):
        """The binding a button has when a profile is active.

        `[bindings]` is the app's scheme at rest, so it overrides the base
        layer and game mode, which is the same desktop with a bar on it. It
        stops at a held layer (item 38): the modifier is the desktop's, not the
        app's, so `ZL` + `B` closes the window whatever `B` is worth in the app
        in front - which is also the only reading under which the guide's
        window page, which knows nothing about profiles, tells the truth.
        An app that wants a window op of its own says so by name, and
        `[profile.<name>.window]` is read in `[bindings.window]`'s place.

        It never reaches the implicit surfaces (osk, menu, guide) at all: a
        surface drawn on screen still outranks the app underneath, and neither
        a table nor a layer name can ask for one.
        A button no profile table names falls through to the ordinary
        layer -> base resolution.
        """
        if profile is None:
            return self.binding_for(layer_name, button)
        if layer_name not in ("base", "game"):
            held = (profile.get("layers") or {}).get(layer_name, {})
            binding = held.get(button)
            if binding is not None:
                return binding
            binding = self.bindings.get(layer_name, {}).get(button)
            layer = self.layer(layer_name)
            if binding is not None or layer is None or not layer.fallthrough:
                return binding
            # A layer that falls through means "this button does what it does
            # anywhere else", and under an app that is the app's own binding.
            layer_name = "base"
        binding = profile["bindings"].get(button)
        if binding is not None:
            return binding
        return self.binding_for(layer_name, button)

    def binding_for(self, layer_name, button):
        binding = self.bindings.get(layer_name, {}).get(button)
        if binding is None and layer_name != "base":
            # The couch layer always falls through: game mode is the desktop
            # with a bar on it, not a shorter desktop, so a button nobody has
            # overridden does exactly what it does anywhere else.
            layer = self.layer(layer_name)
            if layer_name == "game" or (layer is not None and layer.fallthrough):
                binding = self.bindings.get("base", {}).get(button)
        return binding

    def keyboard_binding_for(self, surface, code):
        """What a physical key means while `surface` is on screen.

        The surface's own table first, then the base one, so Escape can mean
        "go up a level" in the menu and "send this away" everywhere else
        without repeating itself.
        """
        binding = self.keyboard_bindings.get(surface, {}).get(code)
        if binding is None:
            binding = self.keyboard_bindings.get("base", {}).get(code)
        return binding

    def stick_deadzone(self, stick):
        """How much of one stick's travel does nothing.

        Asked of the stick rather than of the role it is in, so a right stick
        that scrolls the desktop and walks a game's controls in game mode
        carries the same slop into both - which is where the slop is.
        """
        if stick == "right":
            return self.right_deadzone
        return self.left_deadzone

    def stick_roles(self, layer_name, profile=None):
        """What a layer's sticks do, under the app in front of you.

        cursor | scroll | resize | move | snap | focus | none. The implicit
        layers keep the base roles - the pointer still works while the keyboard
        is up - except game mode, which may name its own in [mode]: it is the
        desktop from the couch, and a thumb is worth different things there.

        A profile then has the last word, over the same layers its bindings
        reach - base and game mode, never a held one: what a stick is worth is
        an app's question as much as a button's, but while `ZL` is down both
        sticks belong to the window (item 38), so a browser's wheel does not
        follow the modifier in and take resize / move with it. Game mode's
        `focus` stick is the case that forced this - it walks the focused app's
        own controls, and a browser scrolls whatever holds the focus rather
        than what the pointer is over, so the wheel is the better answer there
        and nowhere else.
        """
        layer = self.layer(layer_name)
        if layer is not None:
            roles = (layer.left_stick, layer.right_stick)
        elif layer_name == "menu":
            # The one implicit surface layer that does not keep the base
            # roles, because it is the one with something for a thumb to do:
            # a grid of tiles, and a gauge that answers where the stick is.
            return (self.menu_left_stick, self.menu_right_stick)
        elif layer_name == "quick":
            # Nothing for a thumb to steer on a row the D-pad walks, and a
            # pointer drifting over the game behind it is worse than a stick
            # that does nothing while it is up.
            return ("none", "none")
        elif layer_name == "game":
            roles = (
                self.game_left_stick or self.left_stick,
                self.game_right_stick or self.right_stick,
            )
        else:
            roles = (self.left_stick, self.right_stick)
        if profile is not None and layer_name in ("base", "game"):
            roles = (
                profile.get("left_stick") or roles[0],
                profile.get("right_stick") or roles[1],
            )
        return roles

    def layer(self, name):
        for layer in self.layers:
            if layer.name == name:
                return layer
        return None

    def profile_for(self, name, vid_pid):
        """Resolve (buttons, triggers) for a freshly connected device."""
        profile_name = self.profile_name
        if profile_name == "auto":
            profile_name = detect_profile(name, vid_pid)
        profile = PROFILES[profile_name]
        buttons = dict(profile["buttons"])
        triggers = dict(profile["triggers"])
        # Measured beats assumed, and hand-written beats both: a mapping is
        # what this pad was seen to do, and [device.*] is what someone said it
        # does. A pad that has been measured also replaces the profile's
        # trigger axes outright rather than adding to them - a pad found to
        # have none has none, and leaving the profile's in would have ZL
        # arriving twice.
        mapping = self.pad_mappings.get((vid_pid or "").strip().upper())
        if mapping is not None:
            buttons.update(mapping["buttons"])
            triggers = dict(mapping["triggers"])
        buttons.update(self.button_overrides)
        triggers.update(self.trigger_overrides)
        return profile_name, buttons, triggers

    @property
    def announced_hold(self):
        """The two numbers an announced hold runs on, for `actions.Binding`."""
        return (self.confirm_hold_ms, self.confirm_ms)

    @property
    def announced_scaled(self):
        """The same pair with `[confirm] scale` already in it.

        `Binding` scales its own, because a binding may name numbers of its
        own and those are scaled too. A menu row names none and takes the pair
        as it stands, so it asks for it ready - one place, so the same gesture
        cannot end up two lengths depending on which surface asked.
        """
        hold, count = self.announced_hold
        return (max(1, int(round(hold * self.confirm_scale))),
                max(1, int(round(count * self.confirm_scale))))

    # -- the settings the pad can change -----------------------------------

    def setting(self, name):
        """What a `pad:` setting currently holds."""
        return getattr(self, CHOSEN[name]["attr"])

    def set_setting(self, name, request):
        """Apply one request from `setting_request`. Returns the new value.

        The value lands in three places: the attribute the daemon reads, the
        loaded data (so nothing that re-reads it sees the old answer), and
        `chosen`, which is what gets written to settings.toml.
        """
        spec = CHOSEN[name]
        kind, argument = request
        current = self.setting(name)
        if kind == "set":
            value = argument
        elif kind == "toggle":
            value = not current
        elif spec["kind"] == "bool":
            value = not current
        elif spec["kind"] == "choice":
            choices = spec["choices"]
            try:
                index = choices.index(current)
            except ValueError:
                index = 0
            value = choices[(index + argument) % len(choices)]
        elif spec.get("stops"):
            # A ladder, not an amount: the stops are a proportion apart.
            value = _stepped(spec, current, argument)
        else:
            value = _clamp_setting(spec, float(current) + spec["step"] * argument)
        setattr(self, spec["attr"], value)
        self.data.setdefault(spec["table"], {})[spec["key"]] = value
        self.chosen[name] = value
        return value

    def badge_layout(self, profile_name):
        """Which console's printing to badge with, for a connected profile.

        `None` is "no pad yet": the logical names are the Switch's, so that is
        what a badge says until something is plugged in and says otherwise.
        """
        if self.layout_name != "auto":
            return self.layout_name
        return PROFILE_LAYOUTS.get(profile_name, guide_module.DEFAULT_LAYOUT)

    def layer_for_button(self, button):
        for layer in self.layers:
            if layer.button == button:
                return layer
        return None


class Layer:
    __slots__ = ("name", "button", "left_stick", "right_stick", "fallthrough",
                 "reaches_past")

    def __init__(self, name, button, left_stick, right_stick, fallthrough,
                 reaches_past=False):
        self.name = name
        self.button = button
        self.left_stick = left_stick
        self.right_stick = right_stick
        self.fallthrough = fallthrough
        # The default every binding in the layer takes unless it says
        # otherwise. A held trigger is already a deliberate gesture - it is
        # why the layer is on a trigger - so a layer reached that way is the
        # natural unit for "this still works while the app has the pad".
        self.reaches_past = reaches_past


def load(path=None, mapping=None, settings=None, layout=None):
    """Shipped defaults, the user's config, what was measured, what was chosen.

    In that order, so each layer answers for what the one before it could not:
    the config file is written by hand, mapping.toml is what the pad was seen
    to do, and settings.toml is what was changed from the pad a moment ago.
    """
    data = _load_toml(DEFAULT_CONFIG_PATH)
    for source in (path or user_config_path(), mapping or mapping_path()):
        if not os.path.exists(source):
            continue
        try:
            data = _deep_merge(data, _renamed(_load_toml(source)))
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError("%s: %s" % (source, exc)) from exc
    source = settings or settings_path()
    chosen = {}
    if os.path.exists(source):
        try:
            chosen = _load_toml(source)
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError("%s: %s" % (source, exc)) from exc
        chosen = _migrate_settings(chosen)
        data = _deep_merge(data, _settings_data(chosen, source))
    config = Config(data, chosen)
    # Not merged into `data`: this one is structure rather than scalars, and
    # it is read with its own rules - see `read_layout`.
    config.layout = read_layout(
        layout_path() if layout is None else layout)
    return config


def _renamed(data):
    """Read a user's file that still names a setting the way an older one did.

    Only the user's own sources go through this: the shipped defaults always
    carry the current names, and they are merged *under* the user's, so a
    fallback inside `Config` would never see the old key at all.

    The dead zones are the case: they were one number per role - `deadzone`
    under [pointer] for whatever was aiming, under [scroll] for whatever was
    scrolling - and are now one per stick. Each old key answers for the stick
    that ships in its role, and an explicit new one wins over it.
    """
    pointer = dict(data.get("pointer", {}))
    legacy = (
        ("left_deadzone", pointer.pop("deadzone", None)),
        ("right_deadzone", data.get("scroll", {}).get("deadzone")),
    )
    if not any(value is not None for _, value in legacy):
        return data
    for key, value in legacy:
        if value is not None:
            pointer.setdefault(key, value)
    data = dict(data)
    data["pointer"] = pointer
    if "scroll" in data:
        scroll = dict(data["scroll"])
        scroll.pop("deadzone", None)
        data["scroll"] = scroll
    return data


def _migrate_settings(chosen):
    """Rename what a settings.toml from an older build calls a setting.

    A name that is still current wins over the one it replaced, so a file
    holding both is not decided by which was read first.
    """
    for old, new in SETTING_ALIASES.items():
        if old in chosen:
            value = chosen.pop(old)
            chosen.setdefault(new, value)
    return chosen


def _settings_data(chosen, source):
    """settings.toml is flat, in setting names; the config is neither."""
    data = {}
    for name, value in chosen.items():
        spec = CHOSEN.get(name)
        if spec is None:
            raise ConfigError("%s: unknown setting %r (one of %s)"
                              % (source, name, ", ".join(sorted(CHOSEN))))
        data.setdefault(spec["table"], {})[spec["key"]] = value
    return data
