"""On-screen keyboard: layouts and controller navigation.

The layout, the selection and the modifier latches all live here rather than in
the shell plugin, so pressing a key types immediately through the uinput
keyboard omapad already owns. The plugin is only a view: it is handed the
rows, the selected cell and the latch state, and draws them.

Two layout sets ship:

`grid`, the default, is a console keyboard: the whole thing on one page, in a
fixed width budget every row shares. It used to insist on even columns, on the
grounds that a D-pad walks a uniform grid predictably - but `move_vertical`
carries the horizontal *position* rather than the column index, so a wide Tab
or Enter costs nothing in navigation and buys a keyboard that looks like the
one the fingers already know. So the keys are sized the way a real keyboard
sizes them: Tab, Caps, Shift, Enter and Space are wider than a letter, and the
budget per row is what keeps the columns lining up.

`classic` mirrors a physical desktop keyboard, staggered widths and all, for
when familiarity matters more than navigation.

Shift does two things here. On a character key it swaps the character, the way
it does on a real keyboard. On a key that carries an `alt` action it swaps the
whole key: Shift over the arrows turns left/right into up/down, which is what
lets four arrows live in two cells.

On top of those pages an app profile can lend one of its own - the commands a
terminal wants in front of it - for as long as its window is focused. That page
is built here from what the profile handed over rather than written into a
layout, so how many pages the keyboard has is a property of the model, and the
page-turn cell has to read its name back out of it.
"""

import copy

from . import keymap

# A key is a label, its shifted label, and what it does.
#   action  "KEYNAME" or "SHIFT+KEYNAME" types it, "mod:<name>" latches,
#           "layer:<name>" switches layer ("next"/"prev" turn the page),
#           "text:<string>" types the string, "close" puts the keyboard away
#   weight  share of the row's width
#   special non-character key: drawn dimmer and smaller
#   alt     what the key types instead while Shift is latched. Only a typed
#           chord - a key that changes layer or closes has to keep doing that.
def _k(label, shifted, action, weight=1.0, special=False, alt=None):
    return {
        "label": label,
        "shifted": shifted,
        "action": action,
        "w": weight,
        "s": special,
        "alt": alt,
    }


def _letter(char):
    return _k(char, char.upper(), char.upper())


def _digit(char, shifted, name):
    return _k(char, shifted, name)


def _sym(label, name):
    """A symbol reached by shifting another key."""
    return _k(label, label, "SHIFT+" + name)


# The key that puts the keyboard away, bottom-right of every layer.
def _hide():
    return _k("▼", "▼", "close", 1, True)

# ------------------------------------------------------------- classic layout

MAIN = [
    [
        _k("Esc", "Esc", "ESC", 1, True),
        _k("`", "~", "GRAVE"),
        _digit("1", "!", "1"), _digit("2", "@", "2"), _digit("3", "#", "3"),
        _digit("4", "$", "4"), _digit("5", "%", "5"), _digit("6", "^", "6"),
        _digit("7", "&", "7"), _digit("8", "*", "8"), _digit("9", "(", "9"),
        _digit("0", ")", "0"),
        _k("-", "_", "MINUS"), _k("=", "+", "EQUAL"),
        _k("Bksp", "Bksp", "BACKSPACE", 1, True),
    ],
    [
        _k("⇥", "⇥", "TAB", 1.5, True),
        _letter("q"), _letter("w"), _letter("e"), _letter("r"), _letter("t"),
        _letter("y"), _letter("u"), _letter("i"), _letter("o"), _letter("p"),
        _k("[", "{", "LEFTBRACE"), _k("]", "}", "RIGHTBRACE"),
        _k("\\", "|", "BACKSLASH", 1.5),
    ],
    [
        _k("⇪", "⇪", "CAPSLOCK", 1.75, True),
        _letter("a"), _letter("s"), _letter("d"), _letter("f"), _letter("g"),
        _letter("h"), _letter("j"), _letter("k"), _letter("l"),
        _k(";", ":", "SEMICOLON"), _k("'", '"', "APOSTROPHE"),
        _k("⏎", "⏎", "ENTER", 2.25, True),
    ],
    [
        _k("⇧", "⇧", "mod:shift", 2.25, True),
        _letter("z"), _letter("x"), _letter("c"), _letter("v"),
        _letter("b"), _letter("n"), _letter("m"),
        _k(",", "<", "COMMA"), _k(".", ">", "DOT"), _k("/", "?", "SLASH"),
        _k("↑", "↑", "UP", 1, True),
        _k("Del", "Del", "DELETE", 1.75, True),
    ],
    [
        _k("Ctrl", "Ctrl", "mod:ctrl", 1.5, True),
        _k("Alt", "Alt", "mod:alt", 1.5, True),
        _k("Super", "Super", "LEFTMETA", 1.5, True),
        _k("␣", "␣", "SPACE", 5, True),
        _k("Fn", "Fn", "layer:fn", 1.5, True),
        _k("←", "←", "LEFT", 1, True),
        _k("↓", "↓", "DOWN", 1, True),
        _k("→", "→", "RIGHT", 1, True),
        _hide(),
    ],
]

# ---------------------------------------------------------------- grid layout
#
# Fourteen units of width per row, spent the way a real keyboard spends them: a
# letter is one, Tab and Caps and the shifts and Enter are wider. Only the
# budget has to match across rows - that is what lines the columns up - and
# vertical navigation carries the position, not the index, so the wide keys
# cost nothing to walk past.
#
# Every page carries a full keyboard - Tab, Caps, Shift, Enter and Backspace
# included - because they are keys you reach for in the middle of a word, and a
# page turn to get at them is worse than a narrower key.

# The same bottom row on every page, so the keys you use without looking do not
# move when the page turns. Only the first cell changes: it names the page it
# goes to, and the pages cycle in the order L/R walk them.
#
# That name is filled in at view time rather than written into the layout,
# because how many pages a keyboard has is no longer fixed: an app profile can
# add one for as long as its window is in front, and then the page after `Fn`
# is that one rather than `abc`. So the cell says "turn the page" and the model,
# which is the only thing that knows the running order, prints where that goes.
def _bottom():
    return [
        _k("", "", "layer:next", 1.5, True),
        _k("Ctrl", "Ctrl", "mod:ctrl", 1.5, True),
        _k("Alt", "Alt", "mod:alt", 1.5, True),
        _k("Space", "Space", "SPACE", 5, True),
        # Shift swaps the whole key, so four arrows cost two cells.
        _k("←", "↑", "LEFT", 1, True, alt="UP"),
        _k("→", "↓", "RIGHT", 1, True, alt="DOWN"),
        # Right nearly everywhere and wrong in a terminal, which wants
        # Ctrl+Shift+V. Per-application profiles are what fixes that.
        _k("Paste", "Paste", "CTRL+V", 1.5, True),
        _hide(),
    ]


GRID_MAIN = [
    [
        # The key to the left of the 1, where every keyboard puts it.
        _k("`", "~", "GRAVE"),
        _digit("1", "!", "1"), _digit("2", "@", "2"), _digit("3", "#", "3"),
        _digit("4", "$", "4"), _digit("5", "%", "5"), _digit("6", "^", "6"),
        _digit("7", "&", "7"), _digit("8", "*", "8"), _digit("9", "(", "9"),
        _digit("0", ")", "0"),
        _k("-", "_", "MINUS"), _k("=", "+", "EQUAL"),
        # Named rather than drawn: ⌫ and ⌦ are one pixel apart at this size
        # and the wrong one eats a word. Shortened to what the cell holds -
        # relabel them from [osk.keys] if the room is there.
        _k("Bksp", "Bksp", "BACKSPACE", 1, True),
    ],
    [
        _k("Tab", "Tab", "TAB", 1.5, True),
        _letter("q"), _letter("w"), _letter("e"), _letter("r"), _letter("t"),
        _letter("y"), _letter("u"), _letter("i"), _letter("o"), _letter("p"),
        _k("'", '"', "APOSTROPHE"),
        _k("Del", "Del", "DELETE", 1.5, True),
    ],
    [
        _k("Caps", "Caps", "CAPSLOCK", 1.75, True),
        _letter("a"), _letter("s"), _letter("d"), _letter("f"), _letter("g"),
        _letter("h"), _letter("j"), _letter("k"), _letter("l"),
        _k(";", ":", "SEMICOLON"),
        _k("Enter", "Enter", "ENTER", 2.25, True),
    ],
    [
        _k("Shift", "Shift", "mod:shift", 2.25, True),
        _letter("z"), _letter("x"), _letter("c"), _letter("v"),
        _letter("b"), _letter("n"), _letter("m"),
        _k(",", "<", "COMMA"), _k(".", ">", "DOT"), _k("/", "?", "SLASH"),
        # A second Shift, as on a real keyboard: from the right-hand side of
        # the grid it halves the travel to reach one.
        _k("Shift", "Shift", "mod:shift", 1.75, True),
    ],
    _bottom(),
]

GRID_SYM = [
    [
        _sym("!", "1"), _sym("@", "2"), _sym("#", "3"), _sym("$", "4"),
        _sym("%", "5"), _sym("^", "6"), _sym("&", "7"), _sym("*", "8"),
        _sym("(", "9"), _sym(")", "0"),
        _sym("_", "MINUS"), _sym("+", "EQUAL"),
        _k("Bksp", "Bksp", "BACKSPACE", 2, True),
    ],
    [
        _k("[", "{", "LEFTBRACE"), _k("]", "}", "RIGHTBRACE"),
        _sym("{", "LEFTBRACE"), _sym("}", "RIGHTBRACE"),
        _k("\\", "|", "BACKSLASH"), _sym("|", "BACKSLASH"),
        _sym("<", "COMMA"), _sym(">", "DOT"), _sym("?", "SLASH"),
        _sym(":", "SEMICOLON"), _sym('"', "APOSTROPHE"),
        _sym("~", "GRAVE"),
        _k("Del", "Del", "DELETE", 2, True),
    ],
    [
        _k("Esc", "Esc", "ESC", 1, True),
        _k("Tab", "Tab", "TAB", 1, True),
        _k("Ins", "Ins", "INSERT", 1, True),
        _k("Home", "Home", "HOME", 1, True),
        _k("End", "End", "END", 1, True),
        _k("PgUp", "PgUp", "PAGEUP", 1, True),
        _k("PgDn", "PgDn", "PAGEDOWN", 1, True),
        _k("PrtSc", "PrtSc", "SYSRQ", 1, True),
        _k("←", "←", "LEFT", 1, True),
        _k("↑", "↑", "UP", 1, True),
        _k("↓", "↓", "DOWN", 1, True),
        _k("→", "→", "RIGHT", 1, True),
        _k("Enter", "Enter", "ENTER", 2, True),
    ],
    _bottom(),
]

FN = [
    [
        _k("Esc", "Esc", "ESC", 1, True),
        _k("F1", "F1", "F1", 1, True), _k("F2", "F2", "F2", 1, True),
        _k("F3", "F3", "F3", 1, True), _k("F4", "F4", "F4", 1, True),
        _k("F5", "F5", "F5", 1, True), _k("F6", "F6", "F6", 1, True),
        _k("F7", "F7", "F7", 1, True), _k("F8", "F8", "F8", 1, True),
        _k("F9", "F9", "F9", 1, True), _k("F10", "F10", "F10", 1, True),
        _k("F11", "F11", "F11", 1, True), _k("F12", "F12", "F12", 1, True),
        _k("Bksp", "Bksp", "BACKSPACE", 1, True),
    ],
    [
        _k("PrtSc", "PrtSc", "SYSRQ", 1, True),
        _k("Menu", "Menu", "COMPOSE", 1, True),
        _k("Super", "Super", "LEFTMETA", 1, True),
        _k("Caps", "Caps", "CAPSLOCK", 1, True),
        _k("Tab", "Tab", "TAB", 1, True),
        _k("Ins", "Ins", "INSERT", 1, True),
        _k("Del", "Del", "DELETE", 1, True),
        _k("Home", "Home", "HOME", 1, True),
        _k("End", "End", "END", 1, True),
        _k("PgUp", "PgUp", "PAGEUP", 1, True),
        _k("PgDn", "PgDn", "PAGEDOWN", 1, True),
        _k("↑", "↑", "UP", 1, True),
        _k("↓", "↓", "DOWN", 1, True),
        _k("Enter", "Enter", "ENTER", 1, True),
    ],
    [
        # Eight keys over the same fourteen units: a media row is read, not
        # touch-typed, so the labels get the room instead.
        _k("Vol−", "Vol−", "VOLUMEDOWN", 1.75, True),
        _k("Vol+", "Vol+", "VOLUMEUP", 1.75, True),
        _k("Mute", "Mute", "MUTE", 1.75, True),
        _k("Prev", "Prev", "PREVIOUSSONG", 1.75, True),
        _k("Play", "Play", "PLAYPAUSE", 1.75, True),
        _k("Next", "Next", "NEXTSONG", 1.75, True),
        _k("☀−", "☀−", "BRIGHTNESSDOWN", 1.75, True),
        _k("☀+", "☀+", "BRIGHTNESSUP", 1.75, True),
    ],
    _bottom(),
]

LAYOUTS = {
    "grid": {"main": GRID_MAIN, "sym": GRID_SYM, "fn": FN},
    "classic": {"main": MAIN, "fn": FN},
}
DEFAULT_LAYOUT = "grid"

# Where the badge that names a key's button sits on it. `right` puts it hard
# against the key's own right edge, so the badges line up down a column and
# read as one list of what the pad reaches; `label` keeps it beside the
# character, as one centred pair, which reads as belonging to that key at the
# cost of sitting wherever the word ends. The daemon only forwards this - the
# placing itself is the plugin's, since it is the only side that knows how
# wide the key came out.
BADGE_ALIGNS = ("right", "label")
DEFAULT_BADGE_ALIGN = "right"

# What the page-turn cell prints for each page. Not the layer's own name: the
# cell is read as a label ("&123"), not as an identifier.
LAYER_LABELS = {"main": "abc", "sym": "&123", "fn": "Fn"}

# The page an app profile lends the keyboard. One name, because a keyboard has
# exactly one app in front of it.
APP_LAYER = "app"


def chord_for(action):
    """The chord a key types, or None for a key that does something else."""
    if action.startswith(("mod:", "layer:", "text:")) or action == "close":
        return None
    return keymap.parse_chord(action)


# Resolving each key's chord once keeps press() and the label lookup cheap.
for _layout in LAYOUTS.values():
    for _layer in _layout.values():
        for _row in _layer:
            for _key in _row:
                # The action a key had before any override: its stable name,
                # and how the caps key is still recognised once the user has
                # pointed it somewhere else.
                _key["id"] = _key["action"]
                _key["chord"] = chord_for(_key["action"])
                _key["alt_chord"] = (
                    keymap.parse_chord(_key["alt"]) if _key["alt"] else None
                )


class OverrideError(ValueError):
    pass


def apply_overrides(layers, overrides):
    """A copy of the layer set with the user's own labels and actions in it.

    Keyed by a key's default action, which is the one stable name it has: the
    label is the thing being changed, and nobody wrote down a row and column.
    A key that appears on more than one page - Tab, Enter - is overridden on
    all of them, which is the only answer that does not surprise.
    """
    layers = copy.deepcopy(layers)
    for rows in layers.values():
        for row in rows:
            for key in row:
                spec = overrides.get(key["action"])
                if not spec:
                    continue
                label = spec.get("label")
                if label:
                    key["label"] = label
                    key["shifted"] = spec.get("shifted", label)
                    # The user's own label is not up for revision by the XKB
                    # lookup, which would otherwise print the layout's
                    # character over it.
                    key["fixed"] = True
                action = spec.get("action")
                if action:
                    try:
                        key["chord"] = chord_for(action)
                    except keymap.KeyParseError as exc:
                        raise OverrideError(
                            "osk.keys.%s: %s" % (key["action"], exc)
                        ) from exc
                    key["action"] = action
    return layers


# ------------------------------------------------------------------ app pages
#
# A profile lends the keyboard a page of its own for as long as its window is
# in front: the commands a terminal wants, and the keys that are wrong
# everywhere but there. Its entries are mostly text rather than keys, so the
# page is laid out the way text is read rather than the way a grid is walked -
# a long entry takes the row alone, two short ones share it - and it stops at
# PAGE_ROWS so the keyboard keeps the height it has on every other page.
PAGE_ROWS = 4
PAGE_PAIR_CHARS = 22


def _entry_key(entry, weight):
    """One entry of an app page: a label that types a string, or sends a chord.

    The chord is how a key that is wrong in one app is right there - a
    terminal's paste - and it goes through the ordinary typed-key path, latched
    modifiers and all, because that is what it is.
    """
    action = entry.get("action")
    if action:
        key = _k(entry["label"], entry["label"], action, weight, True)
        key["chord"] = keymap.parse_chord(action)
    else:
        key = _k(
            entry["label"], entry["label"], "text:" + entry["text"], weight, True
        )
        key["chord"] = None
    key["id"] = key["action"]
    key["alt_chord"] = None
    return key


def app_page_rows(entries, bottom):
    """A profile's entries as a page, over the bottom row every page shares.

    The budget comes from that row rather than from a constant: it is what the
    other pages spend, and a page whose columns do not line up with theirs
    would move the keys under the thumb when the page turns.
    """
    budget = sum(key["w"] for key in bottom) or 1.0
    queue = [
        entry for entry in entries
        if entry.get("text") or entry.get("action")
    ]
    rows = []
    while queue and len(rows) < PAGE_ROWS:
        entry = queue.pop(0)
        pairs = (
            len(entry["label"]) <= PAGE_PAIR_CHARS
            and queue
            and len(queue[0]["label"]) <= PAGE_PAIR_CHARS
        )
        if pairs:
            rows.append([
                _entry_key(entry, budget / 2.0),
                _entry_key(queue.pop(0), budget / 2.0),
            ])
        else:
            rows.append([_entry_key(entry, budget)])
    rows.append(bottom)
    return rows


MODIFIER_KEYS = {
    "shift": "LEFTSHIFT",
    "ctrl": "LEFTCTRL",
    "alt": "LEFTALT",
}
SHIFT_CODE = keymap.resolve("LEFTSHIFT")


# ------------------------------------------------------ typing a whole string
#
# An app page types text, and a character is not a keycode: which key produces
# 'ş' is the compositor's layout's business, not ours. So the same XKB table
# the labels are read out of is inverted into character -> chord, and the
# built-in labels stand in when there is no compositor to ask.
def char_chords(labels):
    """character -> ([modifier codes], keycode), from an XKB label table."""
    chords = {}
    # Lowest keycode first, so a character that two keys can produce is typed
    # from the one a keyboard puts first.
    for code in sorted(labels):
        plain, shifted = labels[code]
        if plain:
            chords.setdefault(plain, ([], code))
        if shifted:
            chords.setdefault(shifted, ([SHIFT_CODE], code))
    return chords


def _builtin_chords():
    """The same table read off the built-in labels, US as they are.

    Derived from the layout rather than written out again, so it cannot drift
    from what the keys say. Special keys are skipped - a page of text has no
    business typing Tab or Enter - which leaves the space bar to name.
    """
    chords = {}
    for rows in LAYOUTS["grid"].values():
        for row in rows:
            for key in row:
                if key["s"] or not key["chord"]:
                    continue
                mods, code = key["chord"]
                if len(key["label"]) == 1:
                    chords.setdefault(key["label"], (list(mods), code))
                if len(key["shifted"]) == 1:
                    chords.setdefault(key["shifted"], ([SHIFT_CODE], code))
    chords.setdefault(" ", ([], keymap.resolve("SPACE")))
    return chords


BUILTIN_CHORDS = _builtin_chords()


# ------------------------------------------------ which button reaches a key

# The keyboard's own layer binds buttons to things the keyboard can also be
# asked for by hand: X types Backspace, ZL holds Shift, R turns the page. A key
# that one of them reaches prints it, small, in the corner - so the keyboard
# teaches the pad instead of the pad having to be learned from the guide.
#
# Matched on what a binding *does* rather than on which button carries it: move
# Backspace onto Y and the badge moves with it, and a scheme nobody here has
# seen badges itself. What types is matched by the chord, so `key:CTRL+V` finds
# the Paste key without either side naming the other; what drives the keyboard
# (the modifiers, Caps, the page turn, the key that puts it away) is matched by
# the key's own identity, because those keys type nothing to compare.
#
# A button that reaches no single key gets no badge - moving the selection,
# pressing it - because there is nothing to print it beside. `osk:submit` is
# the exception worth making: it sends Enter and then puts the keyboard away,
# and the Enter key is the half of that you can point at. Printing it there is
# how the trigger you actually finish a line with says so, instead of the key
# carrying whichever quieter button also types Enter.

def _chord_id(chord):
    """A chord as one hashable name. Modifier order is not part of it."""
    mods, code = chord
    return ("chord", tuple(sorted(mods)), code)


def binding_target(action):
    """The identity of the key one binding reaches, or None."""
    if not isinstance(action, str):
        return None
    action = action.strip()
    if action.startswith("key:"):
        try:
            return _chord_id(keymap.parse_chord(action[4:]))
        except Exception:
            # An unparseable chord is what `omapad check` is for; here it
            # only means one badge does not get drawn.
            return None
    if not action.startswith("osk:"):
        return None
    command = action[4:]
    # Held or latched, a modifier reaches the same key.
    if command.startswith("hold:"):
        command = command[5:]
    if command in ("shift", "ctrl", "alt"):
        return "mod:" + command
    if command == "caps":
        # By identity, not by chord: Omarchy's layout turns Caps Lock into
        # Compose, so the caps key ships pointed at both shifts instead.
        return "CAPSLOCK"
    if command == "close":
        return "close"
    if command == "submit":
        # Enter and away. Badged on Enter rather than nowhere: what it presses
        # is that key, and what it does after is the guide's to say.
        return _chord_id(keymap.parse_chord("ENTER"))
    if command.startswith("layer:"):
        return command
    return None


def badge_index(bindings, available=None):
    """{key identity: button name} for one layer of bindings.

    The first binding to reach a key keeps it: the shipped scheme closes the
    keyboard from four buttons and the key can only print one, so the order
    the config lists them in is the order they are offered in.
    """
    index = {}
    for button, spec in bindings.items():
        if available is not None and button not in available:
            continue
        if isinstance(spec, dict):
            actions = (spec.get("tap"), spec.get("hold"))
        else:
            actions = (spec,)
        for action in actions:
            target = binding_target(action)
            if target is not None:
                index.setdefault(target, button)
    return index


def row_centers(row):
    """Normalised horizontal centre of every key in a row, in 0..1."""
    total = sum(key["w"] for key in row) or 1.0
    centers = []
    offset = 0.0
    for key in row:
        centers.append((offset + key["w"] / 2.0) / total)
        offset += key["w"]
    return centers


class OskModel:
    """Layout state: which layer is up, what is selected, which mods latch."""

    def __init__(self, layout=DEFAULT_LAYOUT, layer="main", overrides=None,
                 badge_align=DEFAULT_BADGE_ALIGN):
        if layout not in LAYOUTS:
            layout = DEFAULT_LAYOUT
        self.layout = layout
        self.badge_align = (
            badge_align if badge_align in BADGE_ALIGNS else DEFAULT_BADGE_ALIGN
        )
        self.layers = LAYOUTS[layout]
        if overrides:
            self.layers = apply_overrides(self.layers, overrides)
        # The pages actually on the keyboard, and the order L/R walk them. Not
        # `layers`: an app profile can lend a page for as long as its window is
        # in front, and that page belongs to the model rather than the layout.
        self.pages = dict(self.layers)
        self.order = list(self.pages)
        self.app_label = ""
        self.layer = layer if layer in self.pages else "main"
        self.row = 1
        self.col = 0
        self.mods = {"shift": False, "ctrl": False, "alt": False}
        # Caps Lock is not a modifier omapad sends: it is a state the
        # compositor holds, per keyboard device. omapad owns the device the
        # keys are typed from and is the only thing that ever toggles its caps,
        # so following its own presses is not an approximation - it is the
        # state that applies to what this keyboard types. It outlives the
        # keyboard being closed, the way a real Caps Lock does.
        self.caps = False
        # Modifiers a button is holding down, as opposed to the one-shot
        # latches: a held Shift outlives the key it applies to.
        self.holds = set()
        # evdev keycode -> (plain, shifted) for the compositor's own layout,
        # and the same table inverted for typing a whole string.
        self.labels = {}
        self._chords = BUILTIN_CHORDS
        # {key identity: badge} for the buttons that reach a key by themselves.
        # Handed in rather than worked out here: which buttons exist and what
        # they print is the connected pad's answer, and this model outlives
        # any one pad.
        self.badges = {}

    def set_badges(self, badges):
        """Which pad button reaches each key, keyed as `badge_index` keys it."""
        self.badges = badges or {}

    def badge_for(self, key):
        """The badge to print on one key, or None.

        Identity first, so a key pointed somewhere else by `[osk.keys]` keeps
        the badge of the thing it still is - the caps key ships typing both
        shifts and is still what `osk:caps` reaches.
        """
        badge = self.badges.get(key["id"])
        if badge is None and key["chord"]:
            badge = self.badges.get(_chord_id(key["chord"]))
        return badge

    def set_labels(self, labels):
        self.labels = labels or {}
        self._chords = char_chords(self.labels) if self.labels else BUILTIN_CHORDS

    def set_app_page(self, label, entries):
        """Lend the keyboard the focused app's page, or take it away.

        Called on every focus change, so it has to be cheap and it has to be
        idempotent. No entries means no page: a profile whose command printed
        nothing is not worth a page turn.
        """
        rows = app_page_rows(entries, self.layers["fn"][-1]) if entries else None
        if rows is None or not label:
            self.clear_app_page()
            return
        self.app_label = label
        self.pages[APP_LAYER] = rows
        if APP_LAYER not in self.order:
            # Last, so the pages that are always there keep the order the
            # fingers learned.
            self.order.append(APP_LAYER)
        self.clamp()

    def clear_app_page(self):
        self.app_label = ""
        if APP_LAYER not in self.pages:
            return
        del self.pages[APP_LAYER]
        self.order.remove(APP_LAYER)
        if self.layer == APP_LAYER:
            # The page went away underneath the selection - the window it
            # belonged to is gone, or the keyboard is closing.
            self.layer = "main"
        self.clamp()

    def layer_label(self, name):
        return self.app_label if name == APP_LAYER else LAYER_LABELS.get(name, name)

    def next_layer(self, step=1):
        order = self.order
        return order[(order.index(self.layer) + step) % len(order)]

    @property
    def rows(self):
        return self.pages[self.layer]

    @property
    def current_key(self):
        return self.rows[self.row][self.col]

    def clamp(self):
        self.row = max(0, min(self.row, len(self.rows) - 1))
        self.col = max(0, min(self.col, len(self.rows[self.row]) - 1))

    def move_horizontal(self, step):
        row = self.rows[self.row]
        self.col = (self.col + step) % len(row)

    def move_vertical(self, step):
        """Change row, keeping the key nearest the current horizontal centre.

        Rows can hold different numbers of keys, so carrying the index across
        would drift; carrying the position keeps the selection under the thumb.
        """
        target = row_centers(self.rows[self.row])[self.col]
        self.row = (self.row + step) % len(self.rows)
        centers = row_centers(self.rows[self.row])
        self.col = min(
            range(len(centers)), key=lambda i: abs(centers[i] - target)
        )

    def set_layer(self, name):
        if name not in self.pages:
            return
        self.layer = name
        self.clamp()

    def cycle_layer(self, step):
        self.set_layer(self.next_layer(step))

    def latch(self, name):
        if name in self.mods:
            self.mods[name] = not self.mods[name]

    def hold(self, name, down):
        """A modifier held down on the pad rather than latched on the grid.

        The pad's Shift has to behave the way a real one does - down for as
        long as the finger is - so it survives the key it applies to, which the
        one-shot latch deliberately does not.
        """
        if name not in self.mods:
            return
        if down:
            self.holds.add(name)
        else:
            self.holds.discard(name)
        self.mods[name] = down

    def clear_latches(self):
        # What a finger is holding is not a latch and must not be cleared.
        for name in self.mods:
            self.mods[name] = name in self.holds

    def reset_mods(self):
        """Everything off - the keyboard is going away."""
        self.holds.clear()
        self.clear_latches()

    def caps_key(self):
        """The key that toggles Caps Lock, wherever the user pointed it."""
        for row in self.rows:
            for key in row:
                if key["id"] == "CAPSLOCK":
                    return key
        return None

    def toggle_caps(self):
        """Flip Caps Lock and return the chord that tells the compositor."""
        key = self.caps_key()
        if key is None or not key["chord"]:
            return None
        self.caps = not self.caps
        return key["chord"]

    def modifier_codes(self, skip=None):
        """Keycodes for the modifiers currently latched or held."""
        return [
            keymap.resolve(MODIFIER_KEYS[name])
            for name, active in self.mods.items()
            if active and name != skip
        ]

    def text_chords(self, text):
        """The chords that type a string, skipping what the layout cannot make.

        A character the active layout has no key for is dropped rather than
        typed wrong: half a command in the prompt is easier to see and fix than
        a command with the wrong character in the middle of it.
        """
        out = []
        for char in text:
            chord = self._chords.get(char)
            if chord is None:
                continue
            mods, code = chord
            if self.caps and char.isalpha():
                # Caps Lock is on in the compositor, so every letter arrives
                # with the shift this table asked for already applied - and the
                # one it did not ask for applied too.
                mods = (
                    [mod for mod in mods if mod != SHIFT_CODE]
                    if SHIFT_CODE in mods else list(mods) + [SHIFT_CODE]
                )
            out.append((mods, code))
        return out

    def press(self):
        """Resolve the selected key.

        Returns ("type", mod_codes, keycode) for a key that should be typed,
        ("text", string) for a key that types a whole string, ("layer", name),
        ("mod", name) or ("close", None) otherwise.
        """
        key = self.current_key
        action = key["action"]
        if action.startswith("mod:"):
            name = action[4:]
            self.latch(name)
            return ("mod", name)
        if action.startswith("layer:"):
            name = action[6:]
            if name in ("next", "prev"):
                name = self.next_layer(1 if name == "next" else -1)
            self.set_layer(name)
            return ("layer", name)
        if action.startswith("text:"):
            # A latch means nothing to a string - Ctrl over a command is not
            # something anybody asked for - and leaving it on would apply it to
            # the next key instead.
            self.clear_latches()
            return ("text", action[5:])
        if action == "close":
            return ("close", None)

        # Shift over a key with an alternative swaps the key itself rather than
        # the character: the arrows become the other two arrows, and the shift
        # is spent doing that instead of being sent along.
        shift_alt = self.mods["shift"] and key["alt_chord"]
        own_mods, code = key["alt_chord"] if shift_alt else key["chord"]
        latched = self.modifier_codes("shift" if shift_alt else None)
        # A symbol key carries its own shift; the latch adds to it rather than
        # replacing it, and duplicates would be pressed twice.
        mods = list(dict.fromkeys(list(own_mods) + latched))
        # Latches are one-shot, the way a sticky-keys shift behaves: they apply
        # to the next key and then let go.
        self.clear_latches()
        if key["id"] == "CAPSLOCK":
            self.caps = not self.caps
        return ("type", mods, code)

    def label_for(self, key, shifted=None):
        """What to print on a key, following the compositor's layout.

        omapad types keycodes, so the character a key produces is whatever the
        active XKB layout maps it to. Special keys keep their own glyphs; only
        character keys follow the layout.
        """
        if shifted is None:
            shifted = self.mods["shift"]
        # The page-turn cell names where it goes, and where it goes depends on
        # which pages are up: the app page joins the cycle and leaves it again
        # with the window it belongs to. A label the user wrote stands.
        if key["id"] == "layer:next" and not key.get("fixed"):
            return self.layer_label(self.next_layer(1))
        # Caps Lock reaches the letters and nothing else, and Shift over Caps
        # goes back down, the way it does on a real keyboard.
        upper = shifted != (self.caps and key["label"].isalpha())
        fallback = key["shifted"] if upper else key["label"]
        if key["s"] or key.get("fixed") or not self.labels or not key["chord"]:
            return fallback
        pair = self.labels.get(key["chord"][1])
        if not pair:
            return fallback
        plain, shifted_char = pair
        upper = shifted != (self.caps and plain.isalpha())
        text = shifted_char if (SHIFT_CODE in key["chord"][0] or upper) else plain
        return text if text else fallback

    def view_key(self, key):
        label = self.label_for(key)
        # What the key becomes on the other side of Shift, printed small in the
        # corner the way a console keyboard shows it. Empty when Shift changes
        # nothing here, and empty on the letters too: printing 'Q' over every
        # 'q' is twenty-six hints for the one thing every keyboard already
        # teaches, and it drowns out the ones worth reading.
        other = self.label_for(key, not self.mods["shift"])
        if other.lower() == label.lower():
            other = ""
        badge = self.badge_for(key)
        state = {
            "l": label,
            "x": other,
            "w": key["w"],
            "s": key["s"],
            # A one-character symbol like ⏎ or ▼ has to be drawn at character
            # size to stay readable; only word labels ("Ctrl", "Home") take the
            # smaller, quieter treatment.
            "g": len(label) == 1 and not label.isalnum(),
            "m": (
                key["action"][4:] if key["action"].startswith("mod:")
                # Caps lights up like a latch because that is what it is: a
                # state that stays on until it is pressed again.
                else "caps" if key["id"] == "CAPSLOCK" else None
            ),
        }
        # Only where there is one: an absent field is a key no button reaches,
        # and the plugin draws nothing for it.
        if badge is not None:
            state["b"] = badge["b"]
            state["k"] = badge["k"]
        return state

    def view_state(self, opened):
        """The payload the shell plugin draws."""
        rows = [
            [
                self.view_key(key)
                for key in row
            ]
            for row in self.rows
        ]
        return {
            "open": opened,
            "layout": self.layout,
            "layer": self.layer,
            "balign": self.badge_align,
            "rows": rows,
            "sel": [self.row, self.col],
            "mods": dict(self.mods, caps=self.caps),
        }
