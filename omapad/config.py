"""Configuration loading: shipped defaults deep-merged with the user's file."""

import os
import tomllib

from . import actions as actions_module
from . import gamebar as gamebar_module
from . import guide as guide_module
from . import snap as snap_module
from . import keymap
from . import osk as osk_module

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
# whichever is up. See daemon.surface_top().
SURFACES = ("map", "guide", "menu", "osk")
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
    "profile": {
        "attr": "profile_name", "table": "device", "key": "profile",
        "kind": "choice", "choices": ("auto",) + tuple(sorted(PROFILES)),
    },
    "layout": {
        "attr": "layout_name", "table": "device", "key": "layout",
        "kind": "choice",
        "choices": ("auto",) + tuple(sorted(guide_module.LAYOUTS)),
    },
    # How the badges are drawn, which is the other half of what they print:
    # the answer depends on how far away the screen is, so it is asked from
    # where you are sitting rather than at a keyboard.
    "badge_style": {
        "attr": "ui_badge_style", "table": "ui", "key": "badge_style",
        "kind": "choice", "choices": BADGE_STYLES,
    },
    "rumble": {
        "attr": "rumble_enabled", "table": "rumble", "key": "enabled",
        "kind": "bool",
    },
    "rumble_strength": {
        "attr": "rumble_strong", "table": "rumble", "key": "strong",
        # A twentieth of the motor's range per step: fine enough to stop on
        # the level you meant, coarse enough that reaching it is a few
        # presses rather than a job.
        "kind": "number", "step": 0.05, "min": 0.0, "max": 1.0,
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
    amount = float(value) * spec.get("scale", 1)
    unit = spec.get("unit", "")
    if unit == "%":
        return "%g%%" % round(amount)
    return ("%g %s" % (round(amount, 2), unit)).strip()


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
            text = '"%s"' % str(value).replace('"', "")
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
    "cursor", "scroll", "resize", "move", "snap", "focus", "none",
)


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

        mode = data.get("mode", {})
        self.start_mode = mode.get("start", "desktop")
        if self.start_mode not in ("desktop", "game"):
            raise ConfigError("mode.start must be 'desktop' or 'game'")
        self.grab = bool(mode.get("grab", True))
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
        self.cursor_theme = pointer_cursor.get("theme", "omapad-ring")
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

        rumble = data.get("rumble", {})
        self.rumble_enabled = bool(rumble.get("enabled", True))
        self.rumble_strong = float(rumble.get("strong", 0.20))
        self.rumble_weak = float(rumble.get("weak", 0.0))
        self.rumble_duration = int(rumble.get("duration_ms", 60))

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
        self.ui_game_scale = float(ui.get("game_scale", 1.25))
        for name, value in (("scale", self.ui_scale),
                            ("game_scale", self.ui_game_scale)):
            if value <= 0:
                raise ConfigError("ui.%s must be greater than zero" % name)
        # The shell cannot read this file, so which of the two a surface draws
        # travels in its payload beside the scale.
        self.ui_badge_style = str(ui.get("badge_style", "filled"))
        if self.ui_badge_style not in BADGE_STYLES:
            raise ConfigError(
                "ui.badge_style must be one of %s" % ", ".join(BADGE_STYLES)
            )

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
        self.osk_repeat_delay = float(osk.get("repeat_delay_ms", 350)) / 1000.0
        self.osk_repeat_rate = float(osk.get("repeat_rate_ms", 70)) / 1000.0

        menu = data.get("menu", {})
        self.menu_socket = menu.get("socket") or None
        self.menu_title = menu.get("title", "Go")
        # A list, so the deep merge replaces it wholesale rather than merging
        # entry by entry - which is what you want: a user menu is their menu,
        # not the shipped one with rows spliced in at matching indexes.
        self.menu_items = menu.get("items", [])
        # The day and the time, at the head of the menu. strftime; empty for
        # none. It lives here rather than on the bar because the bar's left end
        # is the menu's own place and two things there read as clutter.
        self.menu_clock = menu.get("clock", "%A %H:%M")
        self.menu_repeat_delay = float(menu.get("repeat_delay_ms", 400)) / 1000.0
        self.menu_repeat_rate = float(menu.get("repeat_rate_ms", 110)) / 1000.0
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

        guide = data.get("guide", {})
        self.guide_socket = guide.get("socket") or None

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


def load(path=None, mapping=None, settings=None):
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
    return Config(data, chosen)


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
