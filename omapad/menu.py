"""The controller menu: the entry tree, its geometry, and the view payload.

A grid of tiles under a bar of groups, rather than one column of rows. A list
says every row is worth the same; a grid says what is worth looking at, which
is the whole difference between a menu and the panel a console opens over a
game. The top level is the bar - a row there is a place, not a verb - and the
selected group's tiles fill the card under it.

Same split as the keyboard: the tree, the selection, the drill-down stack and
**where every tile sits** live here, and the shell plugin is handed tiles with
their cells and only draws them. Entries come from `[[menu.items]]` in the
config and use the same action grammar as a button binding, so the menu can
reach anything a button can.

Nothing here knows what a setting holds, how loud the machine is or what a
badge looks like. It holds state and geometry; everything else arrives through
a callback the daemon supplies.

A row may also **list** its submenu instead of holding one: `from` is a command
whose output is one row per line. Which audio outputs exist is not something a
config file can know - the answer changes when a television is plugged in - and
a menu that can only name what was written down cannot ask.
"""

import re
import shlex
import time

from . import actions
from . import snap
from .viewsock import drawable

ROOT_TITLE = "Go"

# What a listed row's submenu says when its command finds nothing. A page with
# no rows on it is a press in the dark: the menu opened, and the screen has
# nothing to say about why.
NOTHING_LISTED = "Nothing found"

# The states a row may ask to exist in (`when`). Short on purpose: each one
# has to be something the daemon already knows without asking anything slow,
# and something the person holding the pad can see for themselves - a row that
# comes and goes for a reason nobody can point at is worse than a row that is
# always there and sometimes does nothing.
WHEN = ("game", "handed_over", "locked", "kept")

# The values a listed line carries, in the order the row's action takes them.
# Numbered rather than one `%s` because the command a row runs often wants two
# of them - a node id and a device name - and unnumbered fields could not say
# which was which. A bare `%` is left alone, so `5%-` still steps a brightness.
FIELD = re.compile(r"%([1-9])")

# How many cells across a page is. The default rather than a constant: it
# decides how much fits on one screen and how big a tile reads from across a
# room, and a laptop panel and a television do not want the same answer.
COLUMNS = 6

# What a tile off to the side costs against one straight ahead, the same
# question `[snap] bias` answers about windows and deliberately its own
# number: windows are large and sparse, tiles are small and touching, and a
# 1x1 beside a 2x2 is a press the window default was never measured on.
BIAS = 2.0

# What a tile may declare itself to be. A closed list on purpose: a name here
# owes generated art where it needs art, a QML delegate, a documented payload,
# validation that fails `omapad check`, and a test. A control that can be
# added by touching one file is one that can ship half-drawn.
CONTROLS = ("toggle", "choice", "slider", "gauge", "media", "readout",
            "row_break")

# Which control a setting may be drawn as, by the kind of thing it holds. A
# switch pointed at a number is a tile that could never draw itself, and the
# parser is a better place to find that out than the sofa.
CONTROL_KINDS = {
    "toggle": ("bool",),
    "choice": ("choice",),
    "slider": ("number",),
    "gauge": ("number",),
    "media": ("media",),
    # The one tile that is not a control: it prints what something is and has
    # no press at all. What the machine is doing is published rather than set
    # - a temperature is not a setting - so the tile that shows it commits to
    # nothing, and A on it does nothing.
    "readout": ("reading",),
}

# Which stick a gauge draws the position of. Two, because a pad has two, and a
# name rather than an index so a config says which thumb it means.
STICKS = ("left", "right")

# The controls that are entered before they are changed. A switch has two
# states and a choice is a short list, so A acting is the whole of it; a
# control with a range has to be taken first, because a grid spends both axes
# on getting about and cannot lend one to a tile it is only passing over.
TAKEABLE = ("slider", "gauge")

# Where a control reads its value. `pad:` is omapad's own settings, `live:` is
# what the desktop is doing - how loud it is, how bright, what is playing -
# and `sys:` is what the machine underneath is doing, which is published
# rather than set. Three sources, three tables, one grammar.
READERS = ("pad", "live", "sys")

# The cells a control asks for, and the default a row overrides with `span`.
# The size is the control's own shape rather than a preference: a bar shorter
# than three cells cannot be aimed at with a thumb, and a switch is a switch at
# any width.
SPANS = {
    "": (1, 1),
    # A switch is a switch at any width.
    "toggle": (1, 1),
    # Wide enough to hold its longest value between two chevrons.
    "choice": (2, 1),
    # A bar shorter than three cells cannot be aimed at: the whole of what a
    # slider says is where along its travel it is, and at one cell that is a
    # dozen pixels of difference between a setting and the one either side.
    "slider": (3, 1),
    # Two lines of somebody else's words, which are as long as they are. A
    # title elided at one cell says nothing at all.
    "media": (3, 2),
    # Square, because it is round: a dial in a wide box is a dial with air
    # either side of it, and the thumb inside has to move the same distance
    # both ways or the reading is a lie about where the stick is.
    "gauge": (2, 2),
    # A name and a number on one line. One cell holds one of them, and a
    # reading whose name is cut in half is a number nobody can place.
    "readout": (2, 1),
}

# What a page may spend on a job of its own. A and B are not on it and are not
# going to be: the face-button contract is that A commits and B leaves, in
# every layer, every surface and every application, and a page that could take
# either would be the one place on the pad where that stopped being true.
# X is this thing's own verb and Y is the reach, which is exactly the pair the
# contract leaves free.
PAGE_KEYS = ("X", "Y")

# What X means everywhere else in this surface, and what a page taking it has
# to keep on the hold. `bindings.md` rule 2: an override may have the app's
# most-pressed control, and MUST keep the meaning it displaced within reach.
KEEPS_ON_HOLD = {"X": "menu:close"}

# A tile that ends the row instead of filling it. Not a one-cell spacer: a
# spacer holds a hole open at one column count and shifts everything under it
# at another, and the same layout has to read on a laptop panel and on a
# television. A break is the one gap that means the same thing at any width.
ROW_BREAK = "row_break"

# What a row is called in the file a person's own arrangement is written to.
# Derived from the label so nothing has to be written down to be moveable, and
# overridable because a label is allowed to change without orphaning a layout.
SLUG = re.compile(r"[^a-z0-9]+")


class MenuError(ValueError):
    pass


def slug(label):
    """A row's default id, from its label."""
    out = SLUG.sub("-", label.lower()).strip("-")
    return out or "row"


def build(entries, where="menu.items", columns=COLUMNS, settings=None,
          readings=None, machine=None):
    """Normalise config entries into a tree, resolving every action.

    Actions are parsed here rather than when an entry is picked, so a typo
    surfaces in `omapad check` instead of doing nothing at the moment you
    press it. A row that lists its submenu (`from`) is checked the same way,
    against the template each of its lines will run.

    A tile's `id` and `span` are settled here for the same reason: the id is
    what a saved layout names a tile by, and a span wider than the page has
    is a row that could never be drawn.

    `settings` is `config.CHOSEN` - what a `pad:` reader may name, with
    `readings` and `machine` the same for `live:` and `sys:`. Passed in rather
    than imported so this module stays the thing that holds state and geometry
    and nothing else; every caller has all three, so a reader is checked in
    practice wherever one is written.
    """
    items = []
    seen = {}
    for index, entry in enumerate(entries or []):
        path = "%s[%d]" % (where, index)
        if not isinstance(entry, dict):
            raise MenuError("%s must be a table" % path)
        control = _control(entry.get("control"), path)
        if control == ROW_BREAK:
            # Nothing a row is required to have applies: a break is never
            # drawn, never selected and never named by a layout.
            items.append(_break_row())
            continue
        label = str(entry.get("label", "")).strip()
        if not label:
            raise MenuError("%s needs a label" % path)
        children = entry.get("items")
        spec = entry.get("action")
        source = entry.get("from")
        if children is not None and spec is not None:
            raise MenuError("%s has both an action and items" % path)
        if source is not None:
            if children is not None:
                raise MenuError("%s both lists its rows and holds them" % path)
            if spec is None:
                raise MenuError("%s lists rows without saying what one runs" % path)
            if not str(source).strip():
                raise MenuError("%s: 'from' is empty" % path)
        item = {
            "label": label,
            "icon": str(entry.get("icon", "")),
            "detail": str(entry.get("detail", "")),
            "items": None,
            "action": None,
            # A row you nudge rather than pick: the menu stays put and the
            # button keeps firing while it is held. Volume is the case that
            # asks for it - reopening the menu per step is absurd.
            "repeat": bool(entry.get("repeat", False)),
            # A row that does not send the menu away when it is picked. What a
            # setting row needs: choosing a badge layout and being thrown back
            # to the desktop to see what it did is how you end up opening the
            # menu four times to try two of them. A repeating row already
            # stays, by the same argument.
            "stay": bool(entry.get("stay", False) or entry.get("repeat", False)),
            # The command whose output becomes this row's submenu, and the
            # action each of its lines runs. Held as written rather than
            # parsed: the values are not known until the command has answered.
            "from": None,
            "template": None,
            # What that submenu says when the command finds nothing.
            "empty": str(entry.get("empty", "")).strip() or NOTHING_LISTED,
            # The states this row is offered in, any of them being enough.
            # Empty - which is almost every row - means always.
            "when": _when(entry.get("when"), path),
            # What this tile is. Empty is a plain tile - a name, an icon, and
            # something that happens when it is pressed.
            "control": control,
            # What a saved layout calls it, and what it measures.
            "id": str(entry.get("id", "")).strip() or slug(label),
        }
        item["span"] = _span(entry, item["control"], path, columns)
        item["shows"] = _shows(entry, item, path)
        # Where a control tile gets its value, as (source, name).
        item["reads"] = _reads(entry, item, path, settings, readings, machine)
        # What this page spends X and Y on while it is the page in front. Only
        # a page can: a tile that acts has nothing to be the page of.
        item["keys"] = _keys(entry, item, path)
        # A tile the menu opens on while its condition holds. It exists for
        # the row the bar has no room for: the workspace lock used to sit at
        # the top level because a row you have to go and find is a row that is
        # not there, and the bar holds places rather than verbs. Opening on it
        # is nearer than the top level ever was - but only a row that is
        # sometimes offered has anything to be nearer *about*.
        item["open_on"] = bool(entry.get("open_on", False))
        if item["open_on"] and not item["when"]:
            raise MenuError("%s: 'open_on' needs a 'when'" % path)
        if item["id"] in seen:
            raise MenuError(
                "%s: two tiles here are called %r - give one an 'id'"
                % (path, item["id"])
            )
        seen[item["id"]] = True
        if source is not None or children is not None:
            # Neither kind of submenu row is picked, so neither can nudge or
            # stay: both are answers to what happens when a row *runs*.
            if item["repeat"]:
                raise MenuError("%s: only an action row can repeat" % path)
            if item["stay"]:
                raise MenuError("%s: only an action row can stay open" % path)
        if source is not None:
            # Parsed here and thrown away, for the reason every other action is
            # parsed here: `omapad check` should name a row whose template is
            # nonsense rather than a page of rows that do nothing.
            try:
                actions.parse(spec)
            except actions.ActionError as exc:
                raise MenuError("%s: %s" % (path, exc)) from exc
            item["from"] = str(source).strip()
            item["template"] = spec
            # Not None, so the row reads as a submenu before it has been
            # entered: what it holds is read at the press, and until then the
            # only honest answer is that it drills in.
            item["items"] = []
        elif children is not None:
            # Carrying both down, which is the whole of what a nested page
            # needs to be checked the same way this one is: without them a
            # control below the top level is never matched against the
            # setting it reads, and the shipped tree keeps every one of them
            # a level down.
            item["items"] = build(children, path + ".items", columns,
                                  settings, readings, machine)
            if not item["items"]:
                raise MenuError("%s opens an empty submenu" % path)
        elif spec is not None:
            try:
                item["action"] = actions.parse(spec)
            except actions.ActionError as exc:
                raise MenuError("%s: %s" % (path, exc)) from exc
        elif item["control"] in CONTROL_KINDS:
            # A control acts on what it reads. The press is the whole of it,
            # so there is nothing to repeat and nowhere to be thrown out to.
            if item["repeat"]:
                raise MenuError("%s: a control does not repeat" % path)
            item["stay"] = True
        else:
            raise MenuError("%s needs an action or items" % path)
        items.append(item)
    return items


def _break_row():
    """A gap that ends the row it is in. Never drawn, never selected."""
    return {
        "label": "", "icon": "", "detail": "", "items": None, "action": None,
        "repeat": False, "stay": False, "from": None, "template": None,
        "empty": "", "when": (), "control": ROW_BREAK, "id": "",
        "span": (1, 1), "open_on": False, "keys": {}, "reads": (),
        "shows": "",
    }


def _keys(entry, item, path):
    """What a page spends X and Y on, as raw specs the daemon resolves.

    Held as written rather than built, because the thing that turns a spec into
    a binding needs how long an announced hold counts for, and that is a
    setting this module has no business reading. Parsed here all the same, so
    a nonsense one fails `omapad check` rather than a press.
    """
    table = entry.get("keys")
    if table is None:
        return {}
    if not isinstance(table, dict):
        raise MenuError("%s: 'keys' is a table of buttons" % path)
    if item["items"] is None and not entry.get("items") \
            and not entry.get("from"):
        raise MenuError(
            "%s: only a page can spend a key - this tile acts" % path
        )
    out = {}
    for button, spec in table.items():
        button = str(button).strip()
        if button not in PAGE_KEYS:
            raise MenuError(
                "%s: a page may spend %s, not %r"
                % (path, " or ".join(PAGE_KEYS), button)
            )
        try:
            actions.Binding(spec)
        except actions.ActionError as exc:
            raise MenuError("%s: %s: %s" % (path, button, exc)) from exc
        kept = KEEPS_ON_HOLD.get(button)
        if kept and not _holds(spec, kept):
            raise MenuError(
                "%s: %s here has to keep %r on the hold"
                % (path, button, kept)
            )
        out[button] = spec
    return out


def _holds(spec, wanted):
    """Whether a binding keeps `wanted` within reach on its hold."""
    if not isinstance(spec, dict):
        return False
    hold = spec.get("hold")
    if not isinstance(hold, str):
        return False
    return hold.strip() == wanted


def _reads(entry, item, path, settings, readings=None, machine=None):
    """Where a control tile takes its value from, as (source, name).

    Empty for a tile that is not a control - and a `reads` on one of those is
    a tile that would read something and then draw none of it, so it is said
    rather than ignored.

    The three tables are passed in rather than imported, so this module stays
    the thing that holds state and geometry: `settings` is what omapad holds,
    `readings` is what the desktop is doing and `machine` is what the hardware
    is publishing, and none of the three is this module's to know about.
    """
    spec = entry.get("reads")
    control = item["control"]
    wants = control in CONTROL_KINDS
    if spec is None:
        if wants:
            raise MenuError(
                "%s: a %s has to say what it reads" % (path, control)
            )
        return ()
    if not wants:
        raise MenuError("%s: only a control reads something" % path)
    source, _, name = str(spec).partition(":")
    source, name = source.strip(), name.strip()
    if source not in READERS or not name:
        raise MenuError(
            "%s: 'reads' is %s:<name>, not %r"
            % (path, "|".join(READERS), spec)
        )
    table = {"pad": settings, "live": readings, "sys": machine}.get(source)
    if table is not None:
        found = table.get(name)
        if found is None:
            raise MenuError(
                "%s: nothing called %r to read (one of %s)"
                % (path, name, ", ".join(sorted(table)))
            )
        if found["kind"] not in CONTROL_KINDS[control]:
            raise MenuError(
                "%s: %r holds a %s, which a %s cannot draw"
                % (path, name, found["kind"], control)
            )
    return (source, name)


def _shows(entry, item, path):
    """Which stick a gauge draws, or empty for every other tile.

    A gauge is the one control that draws two things at once: the setting it
    reads, as a shaded zone, and where a thumb is right now, which is not a
    setting at all and belongs to no config file.
    """
    spec = entry.get("shows")
    wants = item["control"] == "gauge"
    if spec is None:
        if wants:
            raise MenuError(
                "%s: a gauge has to say which stick it shows" % path
            )
        return ""
    if not wants:
        raise MenuError("%s: only a gauge shows a stick" % path)
    name = str(spec).strip().lower()
    if name not in STICKS:
        raise MenuError(
            "%s: no such stick %r (one of %s)"
            % (path, spec, ", ".join(STICKS))
        )
    return name


def _control(spec, path):
    """What a tile declares itself to be, or empty for a plain one.

    The word is `control` rather than `kind` because `kind` already means a
    badge shape everywhere else in this tree, and a third meaning for it is
    the drift the naming convention exists to stop.
    """
    if spec is None:
        return ""
    name = str(spec).strip()
    if not name:
        return ""
    if name not in CONTROLS:
        raise MenuError(
            "%s: no such control %r (try %s)"
            % (path, name, ", ".join(CONTROLS))
        )
    return name


def _span(entry, control, path, columns):
    """How many cells a tile takes, as (width, height)."""
    spec = entry.get("span")
    if spec is None:
        return SPANS.get(control, SPANS[""])
    if not isinstance(spec, (list, tuple)) or len(spec) != 2:
        raise MenuError("%s: 'span' is [width, height] in cells" % path)
    try:
        width, height = int(spec[0]), int(spec[1])
    except (TypeError, ValueError):
        raise MenuError("%s: 'span' is [width, height] in cells" % path)
    if width < 1 or height < 1:
        raise MenuError("%s: a span is at least one cell each way" % path)
    if width > columns:
        raise MenuError(
            "%s: a span of %d is wider than the %d columns there are"
            % (path, width, columns)
        )
    return (width, height)


def _when(spec, path):
    """The states a row asks to exist in, as a tuple. Empty means always.

    A name that is not one of `WHEN` is a typo, and `omapad check` should say
    which row carries it rather than leaving a row that never appears.
    """
    if spec is None:
        return ()
    names = [spec] if isinstance(spec, str) else spec
    if not isinstance(names, list):
        raise MenuError("%s: 'when' is a state or a list of them" % path)
    out = []
    for name in names:
        name = str(name).strip()
        if name not in WHEN:
            raise MenuError(
                "%s: no such state %r (try %s)"
                % (path, name, ", ".join(WHEN))
            )
        out.append(name)
    return tuple(out)


def listed(item, lines, limit):
    """The rows a listing command just printed, as `item`'s submenu.

    One row per line, tab-separated: the label, then the values the row's
    template takes as `%1` to `%9`. A label that begins with `*` is the one in
    force and is ticked - the mark `pactl` and `wpctl` already put beside the
    current device - and the mark itself is not drawn.

    **Every value is quoted as it goes in.** A device names itself from its own
    USB descriptor, which is to say from somewhere outside this machine, and
    the action it lands in is usually a shell command: unquoted, a speaker
    called `x; rm -rf ~` would be one.

    A line whose action will not parse is dropped rather than raised on: the
    rest of the list is still worth drawing, and a page that opens empty says
    so in its own words.
    """
    rows = []
    for line in lines:
        fields = line.split("\t")
        label = fields[0].strip()
        on = label.startswith("*")
        if on:
            label = label[1:].strip()
        # The label is drawn and nothing else; the values keep their own text,
        # which the template quotes on the way into the action.
        label = drawable(label)
        if not label:
            continue
        values = [field.strip() for field in fields[1:]]
        try:
            action = actions.parse(_filled(item["template"], values))
        except actions.ActionError:
            continue
        rows.append(_listed_row(item, label, action, on))
        if len(rows) >= limit:
            break
    if not rows:
        # The command's answer rather than a choice: no action, so picking it
        # does nothing and the menu stays where it is.
        rows.append(_listed_row(item, item["empty"], None, None))
    return rows


def _listed_row(item, label, action, on):
    return {
        "label": label,
        # No icon: what a device is called is the whole of the row, and a glyph
        # repeated down a list of them says nothing about any of it.
        "icon": "",
        "detail": "",
        "items": None,
        "action": action,
        "repeat": False,
        # Picking one and being thrown out to the desktop would mean reopening
        # the menu to hear whether it was the right one.
        "stay": True,
        "from": None,
        "template": None,
        "empty": item["empty"],
        # A listing answers what is plugged in, which is not a state a row can
        # be written to wait for.
        "when": (),
        "control": "",
        # Named by what it is called, because that is the only stable thing a
        # listing carries - and a device is not something a saved layout can
        # be arranging anyway.
        "id": slug(label),
        "span": SPANS[""],
        "open_on": False,
        # A listed tile is a device, not a page: it has nothing to spend, and
        # nothing a setting could answer for.
        "keys": {},
        "reads": (),
        # Which one the listing marked, and what the tick follows once a row
        # here has been picked. A listed row is the one kind that knows its own
        # answer: the daemon cannot ask a device anything.
        "on": on,
        "listed": True,
    }


def _filled(template, values):
    """`%1` to `%9` replaced by the values a listing line carried, quoted."""
    def value(match):
        index = int(match.group(1)) - 1
        # A value the line did not carry leaves nothing behind rather than an
        # empty argument: a line one field short is a listing that has gone
        # wrong, and the row it makes is dropped for failing to parse.
        if index >= len(values) or not values[index]:
            return ""
        return shlex.quote(values[index])
    return FIELD.sub(value, template)


def build_head(entries, where="menu.head", columns=COLUMNS):
    """Normalise `[[menu.head]]` into the read-only grid above the bar.

    A cell either prints a time - `format` in strftime - or the last thing a
    command printed. `ttl` is how long that answer stays fresh, which is not
    the same clock as the heartbeat: the surface is redrawn every couple of
    seconds, and the weather is asked for every fifteen minutes.

    A `format` cell may carry `under`, a second format set small beneath the
    first: the time over the day is one thing read at two sizes, and two cells
    could not say that - the head is packed first fit, so nothing here can
    promise that the cell holding the day lands under the cell holding the
    time rather than beside it.

    Nothing here runs anything, and nothing here knows what weather is. The
    command is a string from the config; somebody else owns the network, the
    location and what to say when it cannot be reached.
    """
    items = []
    seen = {}
    for index, entry in enumerate(entries or []):
        path = "%s[%d]" % (where, index)
        if not isinstance(entry, dict):
            raise MenuError("%s must be a table" % path)
        fmt = str(entry.get("format", "")).strip()
        source = str(entry.get("from", "")).strip()
        under = str(entry.get("under", "")).strip()
        if bool(fmt) == bool(source):
            raise MenuError(
                "%s prints either a 'format' or a 'from', not both or neither"
                % path
            )
        # A second line under a command's answer would be a second command,
        # with its own `ttl` and its own failure to word - so it is refused
        # here rather than half-supported.
        if under and not fmt:
            raise MenuError(
                "%s: 'under' is a second line under a 'format', not a 'from'"
                % path
            )
        for spec in (fmt, under):
            if not spec:
                continue
            try:
                time.strftime(spec)
            except ValueError as exc:
                raise MenuError("%s: %s" % (path, exc)) from exc
        item = {
            "control": "",
            "id": str(entry.get("id", "")).strip() or slug(fmt or source),
            "format": fmt,
            # The line under it, in strftime as well. Empty is a cell of one
            # line, which is nearly all of them.
            "under": under,
            "from": source,
            # How long an answer stays fresh, in seconds. Zero asks once.
            "ttl": _ttl(entry.get("ttl"), path),
            # What the cell says before the first answer, and after a command
            # that had nothing to say. A blank cell in a grid reads as a
            # drawing fault rather than as a command that failed.
            "empty": str(entry.get("empty", "")).strip(),
        }
        item["span"] = _span(entry, "", path, columns)
        if item["id"] in seen:
            raise MenuError(
                "%s: two cells here are called %r - give one an 'id'"
                % (path, item["id"])
            )
        seen[item["id"]] = True
        items.append(item)
    return items


def _ttl(spec, path):
    if spec is None:
        return 0.0
    try:
        seconds = float(spec)
    except (TypeError, ValueError):
        raise MenuError("%s: 'ttl' is a number of seconds" % path)
    if seconds < 0:
        raise MenuError("%s: a 'ttl' cannot be negative" % path)
    return seconds


def effective_span(item, plan):
    """How many cells a tile takes, with the saved arrangement having the say.

    **One function, one authority.** The config's `span` is the tile's
    intrinsic size and the layout file's is the person's override; nothing
    else in the daemon or the panel may ask "which span applies?".
    """
    override = (plan or {}).get("span", {}).get(item["id"])
    if override:
        return (int(override[0]), int(override[1]))
    return item["span"]


def pinned_cell(item, plan):
    """The cell somebody put this tile in, or None where nobody has.

    The companion of `effective_span`, and the same rule: **one function, one
    authority**. A pin is the only thing that takes a tile out of the flow, so
    nothing else in the daemon or the panel may ask "was this one placed?".
    """
    found = (plan or {}).get("at", {}).get(item["id"])
    if found is None:
        return None
    return (int(found[0]), int(found[1]))


def arrange(items, plan, editing=False):
    """One page's tiles, in the order and at the sizes somebody chose.

    Three rules, and they are deterministic on purpose - this is where a saved
    arrangement and a changed config meet, and that must not be something
    anybody has to interpret:

    1. `hidden` suppresses **only ids the config still has**. It has no effect
       on an unknown id, so it can never hide something that did not exist
       when it was written.
    2. Every tile the config has that is in neither list is **appended**, in
       config order. So a newly shipped tile always appears.
    3. An id in `order` that no longer resolves is **dropped**. So editing
       config.toml can never break a saved layout.

    A `row_break` is authored rather than arranged, and keeps the slot it was
    written in: it is the author's paragraph mark, and a tile moved past it
    crosses into the next paragraph, which is what moving past one should do.

    While `editing`, a hidden tile is drawn rather than dropped - dimmed, and
    in its place - so putting one back is the same gesture as taking it away
    and there is nowhere for it to go and be lost.
    """
    if not plan:
        return items
    breaks = [(number, item) for number, item in enumerate(items)
              if item["control"] == ROW_BREAK]
    tiles = [item for item in items if item["control"] != ROW_BREAK]
    by_id = {}
    for item in tiles:
        by_id.setdefault(item["id"], item)
    hidden = set(plan.get("hidden", ()))
    out = []
    for name in plan.get("order", ()):
        item = by_id.pop(name, None)
        if item is not None:
            out.append(item)
    for item in tiles:
        if item["id"] in by_id:
            by_id.pop(item["id"])
            out.append(item)
    if not editing:
        out = [item for item in out if item["id"] not in hidden]
    for number, item in breaks:
        out.insert(min(number, len(out)), item)
    return out


def place(items, columns, plan=None, rows=None):
    """Where every tile on one page sits, in grid cells.

    **Two passes, because a page has two kinds of tile on it.** A tile
    somebody put somewhere is at that cell; everything else first fits around
    it, in the order the page holds them. The order is authorial - a row is
    placed by how often a thumb reaches for it - so the flow keeps it, and a
    small tile is allowed to backfill the hole a big one left rather than the
    order being rewritten to avoid holes.

    The pins go first, and they have to: a flowed tile would otherwise take
    the cell one was put in, and where a tile ended up would depend on what
    else happened to be on the page.

    A pin is **clamped, never refused**. This is the cost of a cell over a
    name, and it is what keeps the cost small: a pin made on six columns is
    off the edge on four, and a tile that vanished on a smaller screen would
    be the arrangement breaking rather than adapting. Two pins over one cell -
    which only a hand-edited file, or two of those clamps, can make - leave
    the first where it is and hand the second to the flow, so the page is
    still a packing rather than a pile.

    `rows` is the same clamp downwards, for a page with a **last row**. A menu
    page has none - it is as many rows as its tiles came to, and it scrolls -
    so it passes None and a pin may be as far down as somebody carried it. A
    page drawn over the whole screen has one, because a screen has a bottom
    edge: there, a pin below it is pulled onto it rather than drawn off the
    end of the thing it is a page of.

    Returns (tiles, rows). A tile is `{"item", "at", "size"}` - `at` and
    `size` named for what `snap.rect` reads, so the same function that walks
    between windows walks between these.
    """
    taken = set()
    where = {}
    used = 0

    def claim(item, x, y, width, height):
        for down in range(height):
            for across in range(width):
                taken.add((x + across, y + down))
        where[item["id"]] = ((x, y), (width, height))

    def clear(x, y, width, height):
        return all((x + across, y + down) not in taken
                   for down in range(height)
                   for across in range(width))

    for item in items:
        if item["control"] == ROW_BREAK:
            continue
        cell = pinned_cell(item, plan)
        if cell is None:
            continue
        width, height = effective_span(item, plan)
        width = min(width, columns)
        x = max(0, min(cell[0], columns - width))
        y = max(0, cell[1])
        if rows is not None:
            height = min(height, rows)
            y = max(0, min(y, rows - height))
        if not clear(x, y, width, height):
            continue
        claim(item, x, y, width, height)
        used = max(used, y + height)

    # The flow, and the floor a row break raises. A pinned tile is out of the
    # flow entirely - it was put somewhere on purpose - so it neither moves a
    # paragraph mark nor is moved by one, and `floor` counts only what has
    # flowed.
    floor = 0
    flowed = 0
    for item in items:
        if item["control"] == ROW_BREAK:
            # Everything after it starts below everything before it.
            floor = flowed
            continue
        if item["id"] in where:
            continue
        width, height = effective_span(item, plan)
        width = min(width, columns)
        x, y = _first_fit(taken, columns, width, height, floor)
        claim(item, x, y, width, height)
        flowed = max(flowed, y + height)
        used = max(used, y + height)

    tiles = []
    for item in items:
        if item["control"] == ROW_BREAK:
            continue
        at, size = where[item["id"]]
        tiles.append({"item": item, "at": at, "size": size})
    return tiles, used


def _first_fit(taken, columns, width, height, floor):
    """The topmost, then leftmost, free box of that size at or below `floor`.

    Terminates because a width is clamped to the column count, so an empty
    row always holds one.
    """
    y = floor
    while True:
        for x in range(columns - width + 1):
            if all((x + across, y + down) not in taken
                   for down in range(height)
                   for across in range(width)):
                return (x, y)
        y += 1


class MenuModel:
    """Which group is showing, where every tile sits, and how to get back."""

    def __init__(self, items=None, title=ROOT_TITLE, clock_format="%A %H:%M",
                 columns=COLUMNS, bias=BIAS, head=None, layout=None,
                 page_rows=None):
        self.root = items or []
        self.root_title = title
        # strftime, or empty for none. The menu carries a clock because game
        # mode takes Omarchy's bar away and the pad can reach no other one.
        # The head grid is where it belongs now; this is the title line's,
        # kept because a config that set it is still allowed to mean it.
        self.clock_format = clock_format
        self.columns = columns
        self.bias = bias
        # Which pages have a **last row**, by id. A menu page does not: it is
        # as many rows as its tiles came to and it scrolls, so a tile can be
        # carried as far down as somebody wants. A page that is also drawn
        # somewhere with a bottom edge - the HUD is the whole screen - does,
        # and the menu has to know, because the menu is where the page is
        # arranged. Without it a tile can be carried to a row the page it
        # belongs to has no room for, and what it does there is worse than
        # nothing: it is clamped onto the last row, and if something is
        # already pinned there it loses the cell and falls back into the flow.
        self.page_rows = dict(page_rows or {})
        # The read-only grid above the bar: a clock, a day, whatever a command
        # prints. Nothing on it is selectable, because a cursor that can wander
        # into the clock is a cursor that has to come back out.
        self.head = head or []
        # One entry per level above the current one: its tiles, the tile that
        # was selected, and its title. Going back restores where you left,
        # which is what makes drilling in and out feel like one place.
        self.stack = []
        # Which of `WHEN` are true, set by the daemon when the menu opens -
        # once, not per draw: a tile that appeared or vanished under the
        # selection would move every tile after it while a thumb was aiming at
        # one.
        self.conditions = frozenset()
        self.groups = []
        self.group = 0
        # Whose page is in front: the group at depth 0, and the tile that was
        # drilled into below that. What a page spends its keys on hangs off
        # it, so the daemon has one thing to ask rather than a depth to reason
        # about.
        self.page_item = None
        self.source = []
        self.items = []
        self.tiles = []
        self.rows = 0
        self.title = title
        # The model's own identity, and the reason it is a name rather than a
        # number: a tile changing size re-packs the page under it, so an index
        # is stale the moment it is used.
        self.selected = None
        # Rearranging: whether the page in front is being edited, and which
        # tile is being carried. `taken` and `picked` are never both set -
        # entering edit lets go of a control, and a control cannot be taken
        # while editing.
        self.edit = False
        self.picked = None
        # The arrangement, page by page, as it came off layout.toml.
        self.layout = dict(layout or {})
        # The tile being adjusted, as an id, or None. A control with a range
        # has to be held before both axes belong to it - see TAKEABLE. Never
        # set at the same time as a page change: taking is a thing done to the
        # tile in front, and there is no way to leave it still holding one.
        self.taken = None
        self.reset()

    def visible(self, items):
        """The tiles of one page that are offered right now.

        The same list object where nothing on the page asks anything, which is
        every page but one: a listed submenu is filled in place after the page
        has been entered, and a copy here would be a page nobody is looking at.
        """
        if not any(item["when"] for item in items):
            return items
        return [item for item in items
                if not item["when"]
                or self.conditions.intersection(item["when"])]

    @property
    def depth(self):
        return len(self.stack)

    @property
    def current(self):
        for tile in self.tiles:
            if tile["item"]["id"] == self.selected:
                return tile["item"]
        return None

    @property
    def index(self):
        """Where the selection sits among the drawn tiles.

        A drawing convenience, and the pointer's way of naming one. Nothing
        here decides anything from it - see `selected`.
        """
        for number, tile in enumerate(self.tiles):
            if tile["item"]["id"] == self.selected:
                return number
        return 0

    # -- the bar ------------------------------------------------------------

    def group_page(self, item):
        """The tiles a chip shows.

        A top-level row that acts rather than opening a place is a page of
        one. The bar holds places, and the shipped tree puts no verb there -
        but a config that does still has somewhere to draw it.
        """
        if item["items"] is None:
            return [item]
        return self.visible(item["items"])

    def build_groups(self):
        """The chips, which is the top level filtered twice.

        A group whose own `when` is unmet is not offered, and neither is one
        whose every tile is unmet: a chip that opens an empty page says the
        menu has somewhere to go and then does not.
        """
        self.groups = [item for item in self.visible(self.root)
                       if self.group_page(item)]

    def group_move(self, step):
        """Walk the bar. Wraps: it is a short strip, not a page of tiles."""
        if len(self.groups) < 2:
            return False
        self.enter_group((self.group + step) % len(self.groups))
        return True

    def enter_group(self, index):
        if not self.groups:
            self.group = 0
            self.stack = []
            self.page_item = None
            self._show([], self.root_title)
            return
        self.group = max(0, min(int(index), len(self.groups) - 1))
        self.stack = []
        self.page_item = self.groups[self.group]
        # The title line stays the root's word: the bar is already saying
        # which group this is, and printing it twice says it once.
        self._show(self.group_page(self.groups[self.group]), self.root_title)

    def open_at(self):
        """(group, tile id) the menu should open on.

        A tile carrying `open_on` beside its `when` asks to be what the menu
        opens on while that condition holds. Earliest wins, and the answer is
        (0, None) when nothing claims it.
        """
        for number, group in enumerate(self.groups):
            for item in self.group_page(group):
                if item["open_on"]:
                    return (number, item["id"])
        return (0, None)

    # -- the grid -----------------------------------------------------------

    def page(self):
        """What the page in front is called in the file arrangements live in.

        A group's own id, or the id of the tile that opened the page. Empty
        where a page has no owner, which nothing arrangeable has.
        """
        return (self.page_item or {}).get("id", "")

    def plan(self):
        """The saved arrangement for the page in front, or None."""
        return self.layout.get(self.page())

    def rows_limit(self):
        """The last row the page in front has, or None where it has none.

        Applied when the page is placed as well as when a tile is carried, so
        what the menu draws while somebody is arranging is what the surface
        that has the bottom edge will draw - one answer rather than two that
        can disagree about where a tile ended up.
        """
        return self.page_rows.get(self.page())

    def _show(self, items, title, select=None):
        """Draw a page: place its tiles and settle the selection on one.

        `source` is the page as the config holds it and `items` is that page
        arranged. The tree is never mutated: an arrangement lives in
        `self.layout` and is applied here, so a page reads the same whether it
        was just rearranged or just walked back into.
        """
        self.taken = None
        self.picked = None
        self.source = items
        self.title = title
        plan = self.plan()
        self.items = arrange(items, plan, self.edit)
        self.tiles, self.rows = place(self.items, self.columns, plan,
                                      self.rows_limit())
        names = [tile["item"]["id"] for tile in self.tiles]
        if select in names:
            self.selected = select
        else:
            self.selected = names[0] if names else None

    def repack(self):
        """Place the page again, keeping the selection on the same tile.

        What a listing landing, or a tile changing size, leaves to be done.
        """
        held = self.taken
        picked = self.picked
        self._show(self.source, self.title, self.selected)
        if picked is not None and self.select_id(picked):
            self.picked = picked
        # The same page, so whatever was being held still is: a slider being
        # scrubbed while a listing lands beside it must not be let go of by
        # the redraw.
        if held is not None and self.select_id(held):
            self.taken = held

    def _rect(self, tile):
        return {"at": tile["at"], "size": tile["size"],
                "id": tile["item"]["id"]}

    def step(self, direction):
        """Move the selection to the tile that way, or leave it alone.

        `snap.choose` is what decides, unchanged. It already answers "which
        rectangle is that way from here?" for the windows a flick lands on,
        and a tile is a rectangle in cells - so the pad walks a page the way
        it walks a desktop, by one rule rather than two that can disagree.

        Nothing at the edge means the selection stays. A grid that wrapped
        would put the cursor at the far side of a page a thumb was pushing
        away from, which in two dimensions is simply losing it.
        """
        here = None
        for tile in self.tiles:
            if tile["item"]["id"] == self.selected:
                here = tile
                break
        if here is None:
            return False
        boxes = [self._rect(tile) for tile in self.tiles]
        x = here["at"][0] + here["size"][0] / 2.0
        y = here["at"][1] + here["size"][1] / 2.0
        landed = snap.choose(boxes, x, y, direction, self.bias)
        if landed is None:
            return False
        self.selected = landed["id"]
        self.taken = None
        return True

    def select(self, index):
        """Jump the selection to one tile, the way a pointer names it.

        Out of range clamps to the nearest rather than wrapping: a pointer is
        aiming somewhere, and a selection that wrapped would read as a
        mistake.
        """
        if not self.tiles:
            return
        index = max(0, min(int(index), len(self.tiles) - 1))
        if self.tiles[index]["item"]["id"] != self.selected:
            self.taken = None
        self.selected = self.tiles[index]["item"]["id"]

    def select_id(self, name):
        """Jump the selection to a named tile. False when it is not here."""
        for tile in self.tiles:
            if tile["item"]["id"] == name:
                if name != self.selected:
                    self.taken = None
                self.selected = name
                return True
        return False

    # -- holding a control --------------------------------------------------

    def takeable(self):
        """The tile in front, if it is one that has to be held to be moved."""
        item = self.current
        if item is not None and item["control"] in TAKEABLE:
            return item
        return None

    # -- rearranging --------------------------------------------------------

    def _plan(self):
        """The page's arrangement, made if it had none. Never None."""
        page = self.page()
        plan = self.layout.get(page)
        if plan is None:
            plan = {"order": [], "hidden": [], "span": {}, "at": {}}
            self.layout[page] = plan
        # A plan read off an older file, or built by hand, has no cells in it.
        plan.setdefault("at", {})
        # The order is written whole the first time anything is moved, so the
        # file records the page as it was seen rather than as a diff against a
        # config that may since have changed.
        if not plan["order"]:
            plan["order"] = [item["id"] for item in self.source
                             if item["control"] != ROW_BREAK]
        return plan

    def set_edit(self, on):
        """Turn rearranging on or off. False where nothing changed."""
        on = bool(on)
        if on == self.edit:
            return False
        self.edit = on
        # Both are a finger's: a control being adjusted and a tile being
        # carried are things you are in the middle of, and this is the moment
        # you are in the middle of neither.
        self.taken = None
        self.picked = None
        # Hidden tiles come back while editing and go away again after, so the
        # page has to be arranged again either way.
        self.repack()
        return True

    def pick(self):
        """Pick the tile in front up, or put down the one being carried."""
        if not self.edit:
            return False
        if self.picked is not None:
            self.picked = None
            return True
        if self.current is None:
            return False
        self.picked = self.selected
        return True

    STEPS = {"left": (-1, 0), "right": (1, 0),
             "up": (0, -1), "down": (0, 1)}

    def carry(self, direction):
        """Move the carried tile one cell, and leave it in that cell.

        **A cell, and this used to be a place in the order.** Reordering was
        the right answer while a page was a list that packed itself: first fit
        always produces a valid packing, so a tile could only land somewhere
        real. What it cannot express is an empty cell - with nothing else on a
        page there is no order to be third in, so there was no way to put one
        tile at the middle of the screen and nothing around it. On a page of
        readings drawn over a game that is the whole job, so the cell wins and
        `place` carries the cost: a pin is clamped onto a narrower screen
        rather than lost.

        A pin does not reorder anything. Everything unpinned flows around it,
        which is how this still does what the old gesture did: carrying a tile
        left into the middle of a row pins it there and the rest of the row
        closes up behind it.

        The three refusals are the three edges, and each says so rather than
        moving nothing quietly - the motor answers an edge with an edge.
        """
        if self.picked is None:
            return False
        step = self.STEPS.get(direction)
        if step is None:
            return False
        here = None
        for tile in self.tiles:
            if tile["item"]["id"] == self.picked:
                here = tile
                break
        if here is None:
            return False
        width, height = here["size"]
        x = here["at"][0] + step[0]
        y = here["at"][1] + step[1]
        if x < 0 or x + width > self.columns or y < 0:
            return False
        limit = self.rows_limit()
        if limit is not None:
            # The page has a bottom edge somewhere, so this is it. Carrying a
            # tile past it does not move it anywhere useful - `place` pulls it
            # back onto the last row, and onto whatever is already there - so
            # it is refused, and the motor answers the bottom of a page the
            # same way it answers the side of one.
            if y + height > limit:
                return False
        elif y > self.rows:
            # No bottom edge: down is allowed one row past the last and no
            # further. That is what grows a page a row at a time - the only
            # way to reach an empty cell below everything - without a held
            # direction flinging a tile somewhere a thumb then has to walk all
            # the way back from.
            return False
        if not self._room(x, y, width, height):
            return False
        plan = self._plan()
        plan["at"][self.picked] = (x, y)
        self.repack()
        return True

    def _room(self, x, y, width, height):
        """Is that box clear of every *other* tile somebody has placed?

        Only of the pinned ones: an unpinned tile is in the flow and flows out
        of the way, which is the whole of how a tile is moved into the middle
        of a row. A pinned one does not move, so walking onto it would hand
        the carried tile back to the flow and teleport it - a press that goes
        somewhere nobody pointed at.
        """
        plan = self.plan()
        for tile in self.tiles:
            if tile["item"]["id"] == self.picked:
                continue
            if pinned_cell(tile["item"], plan) is None:
                continue
            left, top = tile["at"]
            across, down = tile["size"]
            if (x < left + across and left < x + width
                    and y < top + down and top < y + height):
                return False
        return True

    def hide(self):
        """Take the tile in front off the page, or put it back on it.

        One gesture rather than two, because while editing a hidden tile is
        still drawn where it sits: there is no page it has gone to and nothing
        to go and find, so removing and restoring are the same press.
        """
        if not self.edit or self.current is None:
            return False
        plan = self._plan()
        name = self.selected
        if name in plan["hidden"]:
            plan["hidden"].remove(name)
        else:
            plan["hidden"].append(name)
            self.picked = None
        self.repack()
        return True

    def hidden(self, name):
        """Is that tile one edit mode is showing only so it can be put back?"""
        plan = self.plan()
        return bool(plan) and name in plan.get("hidden", ())

    def resize(self, wider, taller):
        """Make the carried tile bigger or smaller, in whole cells.

        Clamped to the page rather than refused: a tile pushed past the edge
        of a six-column grid stops at six, which is what pushing it further
        could have meant.
        """
        if self.picked is None:
            return False
        item = None
        for tile in self.tiles:
            if tile["item"]["id"] == self.picked:
                item = tile["item"]
                break
        if item is None:
            return False
        plan = self._plan()
        width, height = effective_span(item, plan)
        width = max(1, min(self.columns, width + wider))
        height = max(1, height + taller)
        if (width, height) == effective_span(item, plan):
            return False
        plan["span"][self.picked] = (width, height)
        self.repack()
        return True

    def restore(self):
        """Give the page back to the config. False where it had it already."""
        page = self.page()
        if page not in self.layout:
            return False
        del self.layout[page]
        self.repack()
        return True

    def watching(self):
        """The stick the tile in front is drawing, or empty for none.

        What decides whether the surface streams: the *tile's* kind, not the
        surface's. A menu open on a page of buttons costs nothing at all.
        """
        item = self.current
        if item is None:
            return ""
        return item["shows"]

    def take(self):
        """Hold the tile in front. False where there is nothing to hold."""
        item = self.takeable()
        if item is None:
            return False
        self.taken = item["id"]
        return True

    def release(self):
        """Let go. False where nothing was held, so B can mean back."""
        if self.taken is None:
            return False
        self.taken = None
        return True

    @property
    def held(self):
        """The tile being adjusted, or None."""
        if self.taken is None:
            return None
        return self.current

    # -- drilling in and back out -------------------------------------------

    def where(self):
        """The chip and the tile to come back to, as ids. None for nowhere.

        Ids rather than indices, because a chip can come and go with a `when`.
        The tile at the *bottom* of the stack rather than the one in front:
        coming back inside a submenu you had drilled into would be coming back
        somewhere you did not leave from.
        """
        if not self.groups:
            return None
        return (self.groups[self.group]["id"],
                self.stack[0][1] if self.stack else self.selected)

    def go(self, where):
        """Open on a named chip and tile. False where it is not there now."""
        if not where:
            return False
        group, tile = where
        for number, item in enumerate(self.groups):
            if item["id"] != group:
                continue
            self.enter_group(number)
            if tile is not None:
                self.select_id(tile)
            return True
        return False

    def reset(self, where=None):
        """The way the menu looks when it opens.

        `where` is where it was when it was last closed. Coming back to it is
        most of what a HUD is for: you turn the volume down, you go back to
        the game, and you come back to turn it down again - and a menu that
        started at the top every time would make you walk there every time.

        With nowhere to come back to, a tile carrying `open_on` gets to say
        where it starts, and otherwise it is the first tile of the first chip.
        """
        self.build_groups()
        if self.go(where):
            return
        group, tile = self.open_at()
        self.enter_group(group)
        if tile is not None:
            self.select_id(tile)

    def press(self):
        """Act on the selected tile.

        Returns ("enter", item) for a submenu, ("run", item) for a leaf, or
        ("none", None) when the page is empty.
        """
        item = self.current
        if item is None:
            return ("none", None)
        if item["items"] is not None:
            self.stack.append(
                (self.items, self.selected, self.title, self.page_item)
            )
            self.page_item = item
            self._show(self.visible(item["items"]), item["label"])
            return ("enter", item)
        return ("run", item)

    def choose(self, item):
        """Move the tick to the tile just picked, on the page it sits on.

        A listed tile's tick came from the listing, and the command it runs is
        let go of rather than waited for - so re-reading the listing here would
        race the thing this press has only just started. The press is the
        answer until the page is entered again and the command asked afresh.
        """
        for other in self.items:
            if other.get("listed") and other["action"] is not None:
                other["on"] = other is item

    def back(self):
        """Leave the current submenu. False when there is nothing above it.

        False at depth 0 as well, where the group's own page is the top: the
        bar is not a level to climb to, so the daemon closes the menu there.
        """
        if not self.stack:
            return False
        items, selected, title, self.page_item = self.stack.pop()
        self._show(items, title, selected)
        return True

    def page_keys(self):
        """What the page in front spends X and Y on. Empty for most of them."""
        if self.page_item is None:
            return {}
        return self.page_item.get("keys") or {}

    def page_name(self):
        """Which page that is, for anything that caches per page."""
        if self.page_item is None:
            return ""
        return "%d/%d/%s" % (self.group, self.depth, self.page_item["id"])

    def clock(self):
        if not self.clock_format:
            return ""
        try:
            return time.strftime(self.clock_format)
        except ValueError:
            return ""

    # -- the payload --------------------------------------------------------

    def head_state(self, texts=None):
        """The read-only grid above the bar.

        A cell either prints a time this model can render itself, or the last
        thing a command said - which the daemon supplies, because running one
        is not this module's business.
        """
        tiles, rows = place(self.head, self.columns)
        out = []
        for tile in tiles:
            item = tile["item"]
            under = ""
            if item["format"]:
                text = self._strftime(item["format"])
                under = self._strftime(item["under"])
            else:
                text = (texts or {}).get(item["id"]) or item["empty"]
            cell = {
                "t": drawable(text),
                "x": tile["at"][0], "y": tile["at"][1],
                "w": tile["size"][0], "h": tile["size"][1],
            }
            # Left out where there is none, so a one-line cell costs the wire
            # nothing and the panel's `u !== undefined` is the whole test.
            if under:
                cell["u"] = drawable(under)
            out.append(cell)
        return out, rows

    @staticmethod
    def _strftime(spec):
        """A format rendered, or nothing if the platform refuses it.

        `build_head` already rendered every format once, so reaching the
        except here means a directive that works in January and not in June -
        and a head cell is redrawn twice a second, which is no place to raise.
        """
        if not spec:
            return ""
        try:
            return time.strftime(spec)
        except ValueError:
            return ""

    def live_state(self, opened, live):
        """The short push: where a thumb is, and nothing else.

        **No `items` key, deliberately.** The panel's `applyState` gets past
        its own "same line as last time" guard, finds no items, and never
        reaches `fresh()` - so the model is not reassigned and no delegate is
        rebuilt. About a tenth of what the whole surface costs, sixty times a
        second, and one binding re-runs instead of twenty tiles being built.

        `sel` rides along on purpose rather than being inferred from the last
        full push: the stream has to be meaningful on its own, so the panel
        never has to correlate two of them to know which gauge these floats
        belong to.
        """
        return {
            "open": opened,
            "sel": self.selected or "",
            "g": self.group,
            "live": live,
        }

    def view_state(self, opened, state=None, value=None, head=None,
                   keys=None, control=None):
        """The payload the shell plugin draws.

        `state` answers "is this already the case?" for one action - the
        daemon's own question, since a tile cannot ask a setting anything. A
        tile it answers about is ticked, which is the whole difference between
        a list of choices and a list of guesses.

        `value` answers the other half of that question for a tile that steps
        a number: what the number is now. It replaces the tile's own detail,
        which is a sentence written once and cannot know. Ticking cannot say
        it - every step of a number is equally "not the case".

        `head` is what each head command last said, keyed by cell id, and
        `keys` is what each face button does on this page, already worded.
        The daemon resolves both: one runs commands and the other holds
        bindings, and this module does neither.

        `control` answers for a tile that holds a value - what it is on, and
        in what words. Same reason again: what a setting holds is the
        config's, and this module has no config.
        """
        items = []
        for tile in self.tiles:
            item = tile["item"]
            row = {
                "id": item["id"],
                "l": item["label"],
                "i": item["icon"],
                "d": item["detail"],
                "sub": item["items"] is not None,
                "x": tile["at"][0], "y": tile["at"][1],
                "w": tile["size"][0], "h": tile["size"][1],
            }
            if self.edit and self.hidden(item["id"]):
                # Drawn only so it can be put back, and drawn as what it is.
                row["off"] = True
            if item["id"] == self.picked:
                row["p"] = True
            if item["control"]:
                row["k"] = item["control"]
                if item["shows"]:
                    row["s"] = item["shows"]
                if item["id"] == self.taken:
                    # Held, so both axes belong to it rather than to getting
                    # about. Drawn differently because that is the one state
                    # of this surface a press means something else in.
                    row["hd"] = True
                if control is not None:
                    # What it is on now. Merged rather than returned as the
                    # row, so a control tile keeps its label, its icon and its
                    # cells like any other.
                    row.update(control(item) or {})
            if item.get("on") is not None:
                # A listed tile knows its own answer: the daemon can ask a
                # setting what it holds, but not a device whether it is the
                # one the sound is going to.
                row["on"] = bool(item["on"])
            elif item["action"] is not None:
                if state is not None:
                    answer = state(item["action"])
                    if answer is not None:
                        row["on"] = bool(answer)
                if value is not None:
                    text = value(item["action"])
                    if text:
                        row["d"] = text
            items.append(row)
        head_tiles, head_rows = self.head_state(head)
        return {
            "open": opened,
            "title": self.title,
            "clock": self.clock(),
            "depth": self.depth,
            "sel": self.selected or "",
            "hd": self.taken or "",
            "edit": self.edit,
            "pick": self.picked or "",
            "g": self.group,
            "groups": [{"l": item["label"], "i": item["icon"],
                        "id": item["id"]}
                       for item in self.groups],
            "head": head_tiles,
            "headrows": head_rows,
            "keys": keys or [],
            "cols": self.columns,
            "rows": self.rows,
            "items": items,
        }
