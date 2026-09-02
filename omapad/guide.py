"""The bindings guide: what every button does, badged like the button itself.

Read-only, and deliberately so - seeing the map is most of what item 11 wanted,
and `[osk.keys]` already lets one key of it be changed without touching Python.
Same split as the other two surfaces: the pages and the position live here, the
shell plugin is handed columns of rows and only draws them.

Descriptions are derived from the action rather than kept in a second table
that would drift out of date: `click:left` is a left click whichever button
carries it. Where the derivation is thin - a Lua dispatcher, a script name -
the binding says what it means outright, next to itself:

    L = { tap = "hypr:hl.dsp.focus({ workspace = 'r-1' })",
          desc = "Previous workspace" }

Rows are grouped by the region of the pad a thumb finds them in, not by layer
order, because that is how you look for a button you are holding.
"""

import os
import re

# Region, then the buttons in it. A pad's own printed labels, so this reads the
# same in NS and XInput mode.
REGIONS = (
    ("Face buttons", ("A", "B", "X", "Y")),
    ("D-pad", ("DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT")),
    ("Shoulders", ("L", "R", "ZL", "ZR")),
    ("Sticks", ("LSTICK", "RSTICK")),
    ("System", ("MINUS", "PLUS", "HOME", "CAPTURE")),
)

# The badge is a shape plus a short text, and the shape is what makes it read
# as a controller button: a round face button, a pill for a shoulder, an arrow
# for the D-pad. The plugin draws the shape; this only says which one.
KINDS = {
    "A": "face", "B": "face", "X": "face", "Y": "face",
    "DPAD_UP": "dpad", "DPAD_DOWN": "dpad",
    "DPAD_LEFT": "dpad", "DPAD_RIGHT": "dpad",
    "L": "bumper", "R": "bumper",
    "ZL": "trigger", "ZR": "trigger",
    "LSTICK": "stick", "RSTICK": "stick",
    "MINUS": "system", "PLUS": "system",
    "HOME": "system", "CAPTURE": "system",
}

# What the badge prints, per console. The logical names are the Switch's,
# because that is what the kernel reports for a Pro Controller and what a
# binding is written against; every other pad prints something else on the
# same button, and printing a name the thing in your hands does not carry is
# the one job a guide must not get wrong.
#
# The face buttons are positions, not letters: `A` is whichever button sits
# where Nintendo puts A, so an Xbox pad's A is the same entry and a
# PlayStation pad's is the circle. That also says which way this can be wrong
# - a layout naming a pad you are not holding puts the symbols in the wrong
# corners - which is why `auto` follows the connected profile.
#
# A stick click is L3/R3 wherever you go, and the D-pad has no letters on any
# of them.
_SHARED = {
    "DPAD_UP": "▲", "DPAD_DOWN": "▼",
    "DPAD_LEFT": "◀", "DPAD_RIGHT": "▶",
    "LSTICK": "L3", "RSTICK": "R3",
}


def _layout(names):
    table = dict(_SHARED)
    table.update(names)
    return table


LAYOUTS = {
    "nintendo": _layout({
        "A": "A", "B": "B", "X": "X", "Y": "Y",
        "L": "L", "R": "R", "ZL": "ZL", "ZR": "ZR",
        "MINUS": "−", "PLUS": "+",
        "HOME": "Home", "CAPTURE": "Capture",
    }),
    "xbox": _layout({
        "A": "A", "B": "B", "X": "X", "Y": "Y",
        "L": "LB", "R": "RB", "ZL": "LT", "ZR": "RT",
        "MINUS": "View", "PLUS": "Menu",
        "HOME": "Guide", "CAPTURE": "Share",
    }),
    "playstation": _layout({
        "A": "✕", "B": "○", "X": "□", "Y": "△",
        "L": "L1", "R": "R1", "ZL": "L2", "ZR": "R2",
        "MINUS": "Create", "PLUS": "Options",
        "HOME": "PS", "CAPTURE": "Mute",
    }),
}

# The names are the Switch's, so its own printing is what a badge falls back
# to when nobody has said which pad this is.
DEFAULT_LAYOUT = "nintendo"


def badge_of(button, layout=DEFAULT_LAYOUT):
    """What the pad `layout` names prints on `button`."""
    names = LAYOUTS.get(layout) or LAYOUTS[DEFAULT_LAYOUT]
    return names.get(button, button)

# A column's worth of rows, counting each group's own title line. Two columns
# make a page; a layer with more than that is split rather than clipped. Wide
# enough that the shipped layers each fit on one page - a second page holding
# three rows is worse than a slightly taller card.
COLUMN_ROWS = 14

CLICKS = {
    "left": "Left click", "right": "Right click", "middle": "Middle click",
    "back": "Back click", "forward": "Forward click",
}

KEY_NAMES = {
    "ENTER": "Enter", "RETURN": "Enter", "ESC": "Esc", "SPACE": "Space",
    "TAB": "Tab", "BACKSPACE": "Backspace", "DELETE": "Delete",
    "UP": "Up", "DOWN": "Down", "LEFT": "Left", "RIGHT": "Right",
    "HOME": "Home", "END": "End", "PAGEUP": "Page up", "PAGEDOWN": "Page down",
    "CAPSLOCK": "Caps Lock", "SUPER": "Super", "CTRL": "Ctrl", "ALT": "Alt",
    "SHIFT": "Shift", "LEFTSHIFT": "Left Shift", "RIGHTSHIFT": "Right Shift",
}

OSK_TEXT = {
    "toggle": "On-screen keyboard", "open": "Open the keyboard",
    "close": "Close the keyboard", "press": "Press the key",
    "up": "Move up", "down": "Move down",
    "left": "Move left", "right": "Move right",
    "shift": "Shift, for one key", "ctrl": "Ctrl, for one key",
    "alt": "Alt, for one key", "caps": "Caps Lock",
    "submit": "Enter, then close", "hold:shift": "Shift, while held",
    "hold:ctrl": "Ctrl, while held", "hold:alt": "Alt, while held",
}

MENU_TEXT = {
    "toggle": "Controller menu", "open": "Open the menu",
    "close": "Close the menu", "press": "Pick", "back": "Back",
    "up": "Move up", "down": "Move down",
    "left": "Back", "right": "Pick",
}

GUIDE_TEXT = {
    "toggle": "This view", "open": "Open this view", "close": "Close",
    "next": "Next page", "prev": "Previous page",
}

MAP_TEXT = {
    "toggle": "Controller mapping", "open": "Map the controller",
    "close": "Close", "cancel": "Close", "skip": "Skip this button",
    "back": "Previous button", "restart": "Start over", "save": "Save",
}

SURFACE_TEXT = {
    "close": "Close this", "close_all": "Close everything",
    "back": "Back, then close",
}

# The settings the pad can change about itself (`pad:`), in words. Here rather
# than beside the settings themselves for the same reason every other table on
# this page is here: what an action is *called* is the guide's question, and
# config.py answering it too would be two names for one row.
PAD_NAMES = {
    "profile": "Controller profile",
    "layout": "Button labels",
    "rumble": "Vibration",
    "rumble_strength": "Vibration strength",
    "scroll_speed": "Scroll speed",
    "pointer_speed": "Pointer speed",
    "badge_style": "Button style",
}

PAD_VALUES = {
    "auto": "follow the pad", "toggle": "on or off",
    "next": "the next one", "prev": "the previous one",
    "up": "one step up", "down": "one step down",
    "nintendo_pro": "Nintendo Pro", "nintendo": "Nintendo",
    "xbox": "Xbox", "playstation": "PlayStation",
    "filled": "filled in", "stencil": "punched through",
}

MODE_TEXT = {
    "toggle": "Desktop / game mode",
    "desktop": "Take the pad back", "game": "Hand the pad to games",
}

FOCUS_TEXT = {
    "next": "Next control", "prev": "Previous control",
    "up": "Focus up", "down": "Focus down",
    "left": "Focus left", "right": "Focus right",
    "activate": "Press what is focused", "back": "Back out",
}

SNAP_TEXT = {
    "left": "Window to the left", "right": "Window to the right",
    "up": "Window above", "down": "Window below",
    "centre": "Centre of this window", "center": "Centre of this window",
}

STICK_ROLES = {
    "cursor": "Move the pointer", "scroll": "Scroll",
    "resize": "Resize the window", "move": "Move the window",
    "snap": "Flick to the next window",
    "focus": "Walk the focus",
}

# What the *bar* prints instead, where one word is not the first word of the
# phrase. The guide is read; the bar is glanced at over the top of a game,
# three slots wide, so it says the verb and stops - "Keyboard", not "On-screen
# keyboard".
#
# Keyed by action rather than by the sentence the guide builds, so this cannot
# drift the way a table of long strings would: rewrite OSK_TEXT above and the
# short form still answers. Only the entries `_shorten` gets wrong are here -
# "Clear the screen" is already Clear, and a row for it would be a second
# place to change one word.
BRIEF = {
    "click": {"left": "Click", "right": "Context"},
    "osk": {
        "toggle": "Keyboard", "open": "Keyboard", "submit": "Done",
        "up": "Up", "down": "Down", "left": "Left", "right": "Right",
    },
    "menu": {"toggle": "Menu", "open": "Menu", "up": "Up", "down": "Down"},
    "guide": {"toggle": "Guide", "open": "Guide"},
    "map": {"toggle": "Mapping", "restart": "Restart"},
    "mode": {"toggle": "Mode", "desktop": "Desktop", "game": "Game"},
    "focus": {"up": "Up", "down": "Down", "left": "Left", "right": "Right"},
    "snap": {"up": "Up", "down": "Down", "left": "Left", "right": "Right"},
}


def _shorten(text):
    """The first word of a phrase, which is nearly always the verb in it.

    "Mute the microphone" is Mute and "Clear the screen" is Clear. Where the
    first word is not the meaning - "New tab" is a tab, not a new - the
    binding says `short` itself; guessing better than this would mean parsing
    English, and a bar that guessed wrong would disagree with the guide.
    """
    words = text.split()
    if not words:
        return ""
    return words[0].strip(",;:-/") or text


def brief_of(spec):
    """One word for what an action does, for the bar. See BRIEF."""
    text = str(spec or "").strip()
    kind, _, argument = text.partition(":")
    word = BRIEF.get(kind.strip(), {}).get(argument.strip())
    if word:
        return word
    return _shorten(describe(spec))


# hl.dsp.window.close() - the dispatcher path, and the quoted arguments that
# say what it acts on.
_DISPATCH = re.compile(r"hl\.dsp\.([A-Za-z0-9_.]+)\s*\(")
_ARGUMENT = re.compile(r"(?:([A-Za-z_][A-Za-z0-9_]*)\s*=\s*)?'([^']*)'")


def _sentence(text):
    text = " ".join(text.split())
    return text[:1].upper() + text[1:]


def _describe_key(chord):
    parts = [part.strip() for part in chord.split("+") if part.strip()]
    return "+".join(
        KEY_NAMES.get(part.upper(), part.capitalize()) for part in parts
    )


def _describe_hypr(expression):
    """A Lua dispatcher, read back as words.

    Thin by nature - `direction = 'u'` is not a sentence - which is what the
    binding's own `desc` is for. This is the fallback, not the answer.
    """
    match = _DISPATCH.search(expression)
    if match is None:
        return expression
    words = match.group(1).replace(".", " ").replace("_", " ").split()
    for name, value in _ARGUMENT.findall(expression):
        value = value.replace("_", " ")
        # `mode = 'fullscreen'` on hl.dsp.window.fullscreen says nothing twice,
        # and the name of an argument whose value is already there says even
        # less - so the whole pair goes.
        if not value or value in words:
            continue
        name = (name or "").replace("_", " ")
        if name and name not in words:
            words.append(name)
        words.append(value)
    return _sentence(" ".join(words))


def _describe_exec(command):
    words = command.split()
    if not words:
        return ""
    head = os.path.basename(words[0])
    # Everything on this desktop is called omarchy-something; the prefix is
    # noise in a list where every other row has it too.
    if head.startswith("omarchy-"):
        head = head[len("omarchy-"):]
    return _sentence(" ".join([head.replace("-", " ")] + words[1:]))


def _describe_pad(argument):
    """`pad:layout=xbox`, read back as the setting and what it is set to."""
    name, _, value = argument.partition("=")
    name = name.strip()
    label = PAD_NAMES.get(name, name.replace("_", " "))
    value = value.strip()
    if not value:
        return _sentence(label)
    return "%s: %s" % (_sentence(label), PAD_VALUES.get(value, value))


def describe(spec):
    """A short phrase for what an action does. Empty when it does nothing."""
    if spec is None:
        return ""
    spec = str(spec).strip()
    if not spec or spec == "nop":
        return ""
    kind, _, argument = spec.partition(":")
    kind, argument = kind.strip(), argument.strip()
    if kind == "click":
        return CLICKS.get(argument, _sentence(argument + " click"))
    if kind == "key":
        return _describe_key(argument)
    if kind == "scroll":
        return _sentence("scroll " + argument)
    if kind == "osk":
        if argument.startswith("layer:"):
            page = argument[len("layer:"):]
            if page in ("next", "prev"):
                return "%s keyboard page" % ("Next" if page == "next" else "Previous")
            return "Keyboard page: %s" % page
        return OSK_TEXT.get(argument, _sentence(argument))
    if kind == "menu":
        return MENU_TEXT.get(argument, _sentence(argument))
    if kind == "guide":
        return GUIDE_TEXT.get(argument, _sentence(argument))
    if kind == "map":
        return MAP_TEXT.get(argument, _sentence(argument))
    if kind == "surface":
        return SURFACE_TEXT.get(argument, _sentence(argument))
    if kind == "pad":
        return _describe_pad(argument)
    if kind == "mode":
        return MODE_TEXT.get(argument, _sentence(argument))
    if kind == "snap":
        return SNAP_TEXT.get(argument, _sentence("snap " + argument))
    if kind == "focus":
        return FOCUS_TEXT.get(argument, _sentence("focus " + argument))
    if kind == "hypr":
        return _describe_hypr(argument)
    if kind == "exec":
        return _describe_exec(argument)
    return spec


def button_row(button, spec, layout=DEFAULT_LAYOUT, brief=False):
    """One printed row, or None when the binding says to do nothing.

    `brief` is the bar's reading of the same binding: one word rather than a
    phrase. It is the same binding read shorter and never a different meaning
    - a bar that disagreed with the guide would be worse than a bar with no
    words on it - so it takes the binding's own `short` where there is one,
    the first word of its `desc` where there is not, and the action's own
    short form only when the binding says nothing at all.
    """
    if isinstance(spec, dict):
        text = str(spec.get("desc", "")).strip()
        hold = str(spec.get("hold_desc", "")).strip()
        if brief:
            text = str(spec.get("short", "")).strip() or _shorten(text)
            hold = str(spec.get("hold_short", "")).strip() or _shorten(hold)
        say = brief_of if brief else describe
        text = text or say(spec.get("tap"))
        hold = hold or say(spec.get("hold"))
    elif brief:
        text, hold = brief_of(spec), ""
    else:
        text, hold = describe(spec), ""
    if not text and not hold:
        return None
    return {
        "b": badge_of(button, layout),
        "k": KINDS.get(button, "system"),
        "d": text,
        "h": hold,
    }


def _stick_rows(config, layer_name):
    """The two sticks, which carry a role rather than a binding."""
    left, right = config.stick_roles(layer_name)
    rows = []
    for badge, role in (("L", left), ("R", right)):
        text = STICK_ROLES.get(role, "")
        if text:
            rows.append({"b": badge, "k": "stick", "d": text, "h": ""})
    return rows


def _groups_for(config, layer_name, available, layout=DEFAULT_LAYOUT):
    """Rows of one layer, grouped by the region of the pad they sit in.

    Empty for a layer that binds nothing, so it gets no page: the sticks
    always carry a role, and a page holding only that would say a layer exists
    when nothing about it does.
    """
    bindings = config.bindings.get(layer_name, {})
    layer = config.layer(layer_name)
    placed = set()
    groups = []
    bound = 0
    for title, buttons in REGIONS:
        rows = []
        if title == "Sticks":
            rows.extend(_stick_rows(config, layer_name))
        for button in buttons:
            placed.add(button)
            if available is not None and button not in available:
                continue  # not on the pad in front of you: printing it lies
            if layer is not None and button == layer.button:
                # The button holding the layer open cannot also act inside it.
                rows.append({
                    "b": badge_of(button, layout),
                    "k": KINDS.get(button, "system"),
                    "d": "Hold for this layer",
                    "h": "",
                })
                continue
            row = button_row(button, bindings.get(button), layout)
            if row is not None:
                rows.append(row)
                bound += 1
        if rows:
            groups.append({"t": title, "rows": rows})
    # A pad renamed through [device.buttons] still has to show up somewhere.
    extra = []
    for button in sorted(bindings):
        if button in placed:
            continue
        if available is not None and button not in available:
            continue
        row = button_row(button, bindings.get(button), layout)
        if row is not None:
            extra.append(row)
            bound += 1
    if extra:
        groups.append({"t": "Other", "rows": extra})
    if not bound and layer_name != "base":
        return []
    return groups


def _paginate(title, groups, note=""):
    """Pack groups into columns, and columns into pages of two."""
    chunks = []
    for group in groups:
        rows = group["rows"]
        # A group taller than a column is split rather than clipped, and the
        # title repeats so the second half still says what it is.
        while len(rows) + 1 > COLUMN_ROWS:
            chunks.append({"t": group["t"], "rows": rows[:COLUMN_ROWS - 1]})
            rows = rows[COLUMN_ROWS - 1:]
        chunks.append({"t": group["t"], "rows": rows})

    costs = [len(chunk["rows"]) + 1 for chunk in chunks]
    if sum(costs) <= COLUMN_ROWS * 2:
        # It all fits on one page, so the question is not where it overflows
        # but where it looks even: filling the first column to the brim leaves
        # the second one half empty next to it.
        columns = _balance(chunks, costs)
    else:
        columns = []
        current = []
        used = 0
        for chunk, cost in zip(chunks, costs):
            if current and used + cost > COLUMN_ROWS:
                columns.append(current)
                current, used = [], 0
            current.append(chunk)
            used += cost
        if current:
            columns.append(current)

    pages = [
        {"title": title, "note": note, "cols": columns[index:index + 2]}
        for index in range(0, len(columns), 2)
    ]
    if len(pages) > 1:
        for number, page in enumerate(pages, 1):
            page["title"] = "%s %d/%d" % (title, number, len(pages))
    return pages


def _balance(chunks, costs):
    """Cut one page's groups into two columns of about the same height.

    Only where both halves still fit a column: evenness is worth having, but
    not at the price of a card taller than the cap it was given.
    """
    if len(chunks) < 2:
        return [chunks]
    total = sum(costs)
    cuts = [
        index
        for index in range(1, len(chunks))
        if sum(costs[:index]) <= COLUMN_ROWS
        and total - sum(costs[:index]) <= COLUMN_ROWS
    ]
    if not cuts:
        return [chunks]
    cut = min(cuts, key=lambda index: abs(total - 2 * sum(costs[:index])))
    return [chunks[:cut], chunks[cut:]]


def _layer_titles(config, layout=DEFAULT_LAYOUT):
    """Every layer worth a page, in the order you meet it.

    The guide's own layer is left out: those bindings are how you are reading
    the page, not something the page has to tell you about.
    """
    titles = [("base", "Base", "")]
    for layer in config.layers:
        titles.append((
            layer.name,
            "%s layer" % layer.name.capitalize(),
            "Hold %s. %s" % (
                badge_of(layer.button, layout),
                "Unbound buttons fall back to Base."
                if layer.fallthrough
                else "Unbound buttons do nothing here.",
            ),
        ))
    titles.append(("osk", "Keyboard", "While the on-screen keyboard is up."))
    titles.append(("menu", "Menu", "While the controller menu is up."))
    # Empty unless [bindings.game] names something, and then it is the page
    # worth having: the short list of what still answers while a game has the
    # pad, which is exactly what you cannot work out by pressing buttons.
    titles.append((
        "game",
        "Game mode",
        "While the pad belongs to the game. Every other button goes to it.",
    ))
    return titles


def build_pages(config, available=None, layout=DEFAULT_LAYOUT):
    """Every page the guide can show, for the pad that is actually connected.

    `available` is the set of logical names the connected pad has; None means
    no pad is attached and everything the config binds is worth showing.
    """
    pages = []
    for name, title, note in _layer_titles(config, layout):
        groups = _groups_for(config, name, available, layout)
        if groups:
            pages.extend(_paginate(title, groups, note))
    return pages


class GuideModel:
    """Which page is showing, and what is on it."""

    def __init__(self, config):
        self.config = config
        # Which console's printing the badges carry. The daemon sets it when a
        # pad connects, because `auto` cannot be answered before then.
        self.layout = config.badge_layout(None)
        self.pages = []
        self.index = 0
        self.rebuild()

    def rebuild(self, available=None):
        """Rebuild against the pad in front of you.

        Called when the guide opens rather than once at startup, because which
        buttons exist depends on the profile of whatever is plugged in now.
        """
        self.pages = build_pages(self.config, available, self.layout)
        if self.index >= len(self.pages):
            self.index = 0

    def reset(self):
        self.index = 0

    def move(self, step):
        if not self.pages:
            return
        self.index = (self.index + step) % len(self.pages)

    @property
    def title(self):
        if not self.pages:
            return ""
        return self.pages[self.index]["title"]

    def view_state(self, opened):
        """The payload the shell plugin draws."""
        page = self.pages[self.index] if self.pages else {
            "title": "", "note": "", "cols": [],
        }
        return {
            "open": opened,
            "page": self.index,
            "count": len(self.pages),
            "title": page["title"],
            "note": page["note"],
            "cols": page["cols"],
        }
