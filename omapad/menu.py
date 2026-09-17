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
#
# `first_run` is the one that is true once and never again, which is exactly
# what the rule above warns about - and it is admitted because a row nobody
# can point at twice is what a first start *is*. It is spent on the one page
# that says what the buttons do, so the opening it appears in is the opening
# that explains it.
WHEN = ("game", "handed_over", "locked", "kept", "first_run")

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
CONTROLS = ("toggle", "choice", "slider", "knob", "gauge", "media",
            "readout", "clock", "chrono", "rows", "row_break")

# Which control a setting may be drawn as, by the kind of thing it holds. A
# switch pointed at a number is a tile that could never draw itself, and the
# parser is a better place to find that out than the sofa.
CONTROL_KINDS = {
    "toggle": ("bool",),
    "choice": ("choice",),
    "slider": ("number",),
    # **The one control that reads two kinds**, and the two are what a knob
    # has always been: a quantity turned, and a selector with a stop per
    # position. Nothing else on this surface can take both - a slider pointed
    # at a list would have to draw a length between two words, and a `choice`
    # tile pointed at a number would print it with no scale behind it. A ring
    # has a place for each, which is the whole of why this is one control and
    # not two.
    "knob": ("number", "choice"),
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

# The same value, turned rather than pushed. A slider is a length and a knob
# is an angle, and this pad has one of each: a D-pad pushes a direction, and a
# stick *is* an angle - so it is the one control on this surface whose shape a
# thumb can copy rather than translate. Everything else about it is the
# slider's: the same `reads`, the same steps, the same words, the same
# `TAKEABLE` press. A second drawing of one control, not a second control.
#
# It is not offered as the better one either. A length is read faster than an
# angle and a card is a rectangle, so the slider stays what a row of numbers
# is drawn as; what the ring buys is the gesture, and the two live side by
# side because which of them a page wants is the page's to say.
KNOB = "knob"

# The tile that holds a page rather than opening one: its `items` are drawn as
# rows inside it, and A goes in before up and down walk them. A verb has no
# value to show, so a cell spent on one says a single word - and
# four of them side by side say four words in the room one sentence needs,
# which is how a page of `Lock`, `Suspend`, `Logout` and `Reboot` ends up
# reading as a scatter and how `Screensaver` ends up drawn as `Screensa\u2026`.
#
# It is not a submenu with the drilling taken out. A submenu is a page you go
# to and come back from, and its rows get a whole card each; these are rows
# that are already in front of you, and what buys them their length is that
# they are stacked rather than laid side by side.
ROWS = "rows"

# The time, drawn as a face rather than printed as a figure. It is the second
# tile with nothing to press - `readout` is the first - and the only one that
# reads nothing at all: what a clock is on is not a setting, not something the
# desktop is doing and not something the kernel publishes, so it takes no
# `reads` and the model renders the time itself.
#
# A face rather than a second `%H:%M` because of where this is looked at. The
# head's clock is read by somebody who has just opened the menu and is already
# reading words; a tile is glanced at from across a room, over a game, and
# what a glance gets off two hands is *roughly when it is*, which is the whole
# question anybody asks a clock from a sofa.
CLOCK = "clock"

# The same face with a stopwatch in it, which is what a chronograph is. It is
# the clock plus the one thing a clock cannot do - measure - and that is
# exactly where the two part company: the time of day is rendered at the draw
# and cannot be wrong, and a measurement is state somebody started. So this
# one *is* asked of the daemon, where `chrono.py` holds it.
#
# **And it is the one tile with nothing to press that gained a press**, which
# is why it is not simply an option on the clock: a clock may be drawn over a
# game because there is nothing on it to reach for, and a chronograph may not
# (see `hud.py`). One name each, and the two are told apart by what a payload
# carries rather than by a flag somebody has to look up.
CHRONO = "chrono"

# How long a row that counts down counts for, where it does not say. Seconds,
# and a whole number of them because the row prints it: a count that went
# `9.5` would be a clock rather than a decision you are being given time to
# take back. The daemon passes `[menu] countdown` in; this is the fallback for
# a caller that has no config, which is every test.
COUNTDOWN = 10

# The controls that are entered before they are changed. A switch has two
# states and a choice is a short list, so A acting is the whole of it; a
# control with a range has to be taken first, because a grid spends both axes
# on getting about and cannot lend one to a tile it is only passing over.
#
# **A card of rows is on it for exactly that reason**, and it was not at
# first: walking its rows with the page's own up and down looked like the
# cheaper answer until you stood on one with a card underneath it. Down then
# meant the next row rather than the next card, which is a page where a
# direction means two things depending on what it is pointing at - and no
# thumb can be asked to know which. So A goes in, and up and down belong to
# the page until it does.
TAKEABLE = ("slider", KNOB, "gauge", ROWS)

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
    # Square, and the dial's own square: it is the same circle, and a page
    # that held a knob, a gauge and a clock drawn to three sizes would read as
    # a fault rather than as three tiles. Where the slider's three cells buy
    # length, these four buy a diameter - and a ring smaller than this is one
    # whose stops are a few pixels apart, which is a scale nobody can count
    # from a sofa.
    KNOB: (2, 2),
    # Two lines of somebody else's words, which are as long as they are. A
    # title elided at one cell says nothing at all.
    "media": (3, 2),
    # Square, because it is round: a dial in a wide box is a dial with air
    # either side of it, and the thumb inside has to move the same distance
    # both ways or the reading is a lie about where the stick is.
    "gauge": (2, 2),
    # Square for the same reason, and the same square: a page that holds both
    # holds two circles, and two circles drawn at two sizes read as a fault
    # rather than as two tiles. Smaller than this is a face whose hands are a
    # few pixels apart at ten past two, which is a clock that can only be
    # read by somebody who already knows the time.
    "clock": (2, 2),
    # The same square again, and it has more in it: a sweep hand, a counter
    # dial and the figures the counter cannot say. Bigger is the obvious
    # answer and the wrong one - a page where the stopwatch is the largest
    # thing on it is a page about the stopwatch.
    "chrono": (2, 2),
    # Tall, because it is a stack: a heading, the rows under it and the line
    # along the foot. Two wide rather than one because the whole reason a verb
    # is a row here is that a cell could not hold its name.
    "rows": (2, 3),
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


def minute_of_day(now=None):
    """Where both hands of a clock stand, as minutes since midnight.

    **One number rather than an hour and a minute.** An hour hand stands
    between two hours by exactly how far round the minute hand has got, so a
    payload carrying the two separately is one that can be sent disagreeing
    with itself - and the panel would have to know that to draw it, which is
    geometry this side does not owe it.

    Local time, because a clock in a room is the room's, and rendered here
    rather than asked of the daemon for the head clock's reason: what costs
    nothing to work out at the draw is wrong between draws if anything else
    has to be waited for.
    """
    stamp = time.localtime() if now is None else time.localtime(now)
    return stamp.tm_hour * 60 + stamp.tm_min


def second_of_minute(now=None):
    """Where a running-seconds hand stands, as seconds into the minute.

    The chronograph's own face carries one and the clock does not, which is
    the whole difference between a tile left over a game and a tile you open
    the menu to look at. It rides beside `mn` rather than inside it: minutes
    are what the two big hands are drawn from and are whole, and this is a
    fraction that the panel counts on from between payloads.
    """
    stamp = time.localtime() if now is None else time.localtime(now)
    # The fractional part is the machine's, not the calendar's: `localtime`
    # throws it away and a hand that only ever stood on whole seconds would
    # tick like a quartz watch rather than sweep like the thing this draws.
    whole = time.time() if now is None else now
    return stamp.tm_sec + (whole - int(whole))


def slug(label):
    """A row's default id, from its label."""
    out = SLUG.sub("-", label.lower()).strip("-")
    return out or "row"


def build(entries, where="menu.items", columns=COLUMNS, settings=None,
          readings=None, machine=None, countdown=COUNTDOWN):
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
        if control == ROWS and children is None and source is None:
            raise MenuError(
                "%s: a %s tile is drawn from its items, and has none"
                % (path, ROWS)
            )
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
            # **Which font the icon is set in, where it is not the surface's
            # own.** A glyph is only in the font that drew it: Omarchy's own
            # mark lives at U+E900 in `omarchy.ttf` and is nowhere in a Nerd
            # Font, so a row that prints it has to say where it came from.
            # The Omarchy menu has the same field for the same reason
            # (`iconFont` in its JSONC), which is what this is named after.
            # Empty - which is every other row - means the surface's own.
            "icon_font": str(entry.get("icon_font", "")).strip(),
            "detail": str(entry.get("detail", "")),
            # What a group says under its name on the bar, in the two or
            # three words a nav card has room for: what is playing, which
            # output, how many windows. Left unset, a group falls back to how
            # many tiles its page holds, which is true of every group and
            # needs nobody to maintain it.
            #
            # **A tile takes one too, and it is the line a tile cannot
            # write.** A `detail` is a sentence set down in a config file, so
            # it can say what a row does and never what the machine is
            # doing - and `Windows > Close window` is the row where that is
            # not enough: what the page has to name is the window in front,
            # which is not something anybody can write down. So a tile's
            # `meta` replaces the line it is *about* itself with: the heading
            # on a card of rows, the detail line on any other tile.
            "meta": _group_meta(entry.get("meta"), path),
            "items": None,
            "action": None,
            # A row you nudge rather than pick: the menu stays put and the
            # button keeps firing while it is held. Volume is the case that
            # asks for it - reopening the menu per step is absurd. It is the
            # opposite of `confirm` below, and the two cannot both be true:
            # one says a held A means this again, the other that it means
            # this at last.
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
            # The rows a `rows` tile draws inside itself. Kept apart from
            # `items` on purpose: `items` is what a tile *opens*, and this is
            # what a tile *is*, so a card of rows reads as a leaf everywhere
            # that asks - the payload's `sub`, the title line, `press`.
            "rows": None,
            # A row that is not picked but **held**: A starts an announced
            # hold on it - the same gesture, the same two waits and the same
            # cancel button a binding's `confirm = true` gets - and only when
            # that has counted down does the row run. For the handful of rows
            # that cannot be taken back: a machine that shuts down under a
            # thumb resting on A is the one press this surface must not make
            # cheap.
            "confirm": bool(entry.get("confirm", False)),
            # The other way of being sure, and the one a hand does not have to
            # keep doing: A starts a **countdown** the row prints, and B stops
            # it. Seconds, or 0 for a row that simply runs.
            #
            # It is a second answer rather than a replacement, because the two
            # are for different presses. A hold is right where the gesture is
            # already in the hand - a shoulder held across a workspace, a tile
            # you are looking at - and it is over in a second. A countdown is
            # right where the thing is about to take the screen away: logging
            # out is not a press you want to be *sure* about for 900 ms, it is
            # one you want ten seconds to change your mind about, and holding
            # A for ten seconds is not a gesture anybody makes.
            "countdown": 0,
            # What a saved layout calls it, and what it measures.
            "id": str(entry.get("id", "")).strip() or slug(label),
        }
        item["countdown"] = _countdown(entry, item, path, countdown)
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
        if item["control"] == ROWS and item["icon"]:
            # Said rather than dropped quietly. An icon everywhere else on
            # this surface is the big mark in a card's top corner - what says
            # which tile this is from across a room - and a card of rows has
            # no corner to spare: the heading is a caption, and a glyph set at
            # a caption's size in front of tracked capitals reads as a bullet
            # rather than as a mark. The marks on a card of rows are on its
            # rows.
            raise MenuError(
                "%s: a %s tile has no mark of its own - its rows carry theirs"
                % (path, ROWS)
            )
        if item["control"] == ROWS and item["keys"]:
            # `_keys` allows one because the entry has `items`; this tile has
            # them and is still not a page. A key is spent while a page is *in
            # front*, and nothing is ever in front of a card of rows.
            raise MenuError(
                "%s: only a page can spend a key - this tile is drawn in place"
                % path
            )
        item["open_on"] = bool(entry.get("open_on", False))
        if item["open_on"] and not item["when"]:
            raise MenuError("%s: 'open_on' needs a 'when'" % path)
        if item["id"] in seen:
            raise MenuError(
                "%s: two tiles here are called %r - give one an 'id'"
                % (path, item["id"])
            )
        seen[item["id"]] = True
        # Named after the tile, so the daemon has somewhere to file what the
        # command said without the config having to name a second thing.
        item["meta"] = dict(item["meta"], id=item["id"])
        if source is not None or children is not None:
            # Neither kind of submenu row is picked, so neither can nudge or
            # stay: both are answers to what happens when a row *runs*.
            if item["repeat"]:
                raise MenuError("%s: only an action row can repeat" % path)
            if item["stay"]:
                raise MenuError("%s: only an action row can stay open" % path)
            if item["confirm"]:
                # Opening a page is not a thing to be sure about, and a page
                # you have to hold A to reach is a page nobody finds.
                raise MenuError(
                    "%s: only an action row can ask to be confirmed" % path)
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
            if item["control"] == ROWS:
                # A **card** that lists, which is read when the page it sits on
                # settles rather than at a press: nobody enters a card, it is
                # already open. Seeded with its own `empty` words rather than
                # with nothing, because a card drawn on a page you are looking
                # at is blank for as long as the command takes - and a blank
                # card reads as a drawing fault rather than as a question that
                # has not been answered yet.
                item["rows"] = [_listed_row(item, item["empty"], None, None)]
            else:
                # Not None, so the row reads as a submenu before it has been
                # entered: what it holds is read at the press, and until then
                # the only honest answer is that it drills in.
                item["items"] = []
        elif children is not None:
            # Carrying both down, which is the whole of what a nested page
            # needs to be checked the same way this one is: without them a
            # control below the top level is never matched against the
            # setting it reads, and the shipped tree keeps every one of them
            # a level down.
            page = build(children, path + ".items", columns,
                         settings, readings, machine, countdown)
            if not page:
                raise MenuError("%s opens an empty submenu" % path)
            if item["control"] == ROWS:
                item["rows"] = _rows(page, path)
            else:
                item["items"] = page
        elif spec is not None:
            try:
                item["action"] = actions.parse(spec)
            except actions.ActionError as exc:
                raise MenuError("%s: %s" % (path, exc)) from exc
            if item["confirm"] and item["repeat"]:
                raise MenuError(
                    "%s: a row cannot both repeat and be confirmed" % path)
        elif (item["control"] in CONTROL_KINDS
                or item["control"] in (CLOCK, CHRONO)):
            # A control acts on what it reads. The press is the whole of it,
            # so there is nothing to repeat and nowhere to be thrown out to -
            # and a clock is here rather than below because it is a tile with
            # neither an action nor items on purpose. It has less to do than
            # any of them: A on a clock does nothing, for the readout's reason
            # with the reading taken out as well.
            if item["repeat"]:
                raise MenuError("%s: a control does not repeat" % path)
            if item["confirm"]:
                # Nothing a control does is one-way: a switch flips back, a
                # slider is pushed the other way, and B puts a taken one back
                # where it was. A hold in front of that is friction with
                # nothing to protect.
                raise MenuError("%s: a control is not confirmed" % path)
            item["stay"] = True
        else:
            raise MenuError("%s needs an action or items" % path)
        items.append(item)
    return items


def _rows(items, path):
    """The rows a card draws inside itself, checked for what a row may be.

    A row here is a verb and nothing else. It cannot open a page - the card is
    already the page, and there is nowhere further in for a level to be - and
    it cannot hold a value, because every control this surface has is a card's
    worth of drawing and a row is one line of text. Both are said here rather
    than drawn as a blank line: a tile that could never draw itself is what
    `omapad check` is for.

    A break is refused for the same reason it is a break: it ends a row of
    cells, and these are not cells.
    """
    for index, item in enumerate(items):
        where = "%s.items[%d]" % (path, index)
        if item["control"] == ROW_BREAK:
            raise MenuError(
                "%s: a break ends a row of cells, and this is a row" % where
            )
        if item["control"]:
            raise MenuError(
                "%s: a row here is a verb, not a %s" % (where, item["control"])
            )
        if item["items"] is not None:
            raise MenuError(
                "%s: a row here cannot open a page - the card is one" % where
            )
    return items


def _break_row():
    """A gap that ends the row it is in. Never drawn, never selected."""
    return {
        "label": "", "icon": "", "detail": "", "meta": _group_meta(None, ""),
        "items": None, "action": None,
        "repeat": False, "stay": False, "from": None, "template": None,
        "empty": "", "when": (), "control": ROW_BREAK, "id": "",
        "countdown": 0,
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

    Empty for a tile that is not a control, and for the two controls that hold
    no value anybody could name - a card of rows and a clock. A `reads` on any
    of them is a tile that would read something and then draw none of it, so
    it is said rather than ignored.

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
        if control:
            # A clock or a card of rows: a control, and still not one with a
            # value anybody could point a `reads` at. Named rather than
            # described, because "only a control reads something" is a baffling
            # thing to be told about a line that says `control = "clock"`.
            raise MenuError("%s: a %s reads nothing" % (path, control))
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


def _countdown(entry, item, path, default):
    """How long this row counts before it runs. 0 for one that just runs.

    `true` takes `[menu] countdown`; a number is that many seconds. Refused on
    anything that is not an action row, and refused beside the other two
    answers to "are you sure" - a row cannot be held *and* counted, and a row
    you nudge is one you mean to press again in a moment.
    """
    spec = entry.get("countdown")
    if spec is None or spec is False:
        return 0
    if entry.get("items") or entry.get("from"):
        # Asked of the entry rather than of `item["items"]`, which is not
        # settled yet: the branch that fills it runs after this.
        raise MenuError("%s: only an action row can count down" % path)
    if item["control"]:
        raise MenuError("%s: a control does not count down" % path)
    if item["confirm"]:
        # One says *keep meaning it* and the other says *you have ten seconds
        # to stop me*. Both on one row is a press nobody could describe.
        raise MenuError(
            "%s: a row is held or counted down, not both" % path)
    if item["repeat"]:
        raise MenuError("%s: a repeating row does not count down" % path)
    if spec is True:
        return int(default)
    try:
        seconds = int(spec)
    except (TypeError, ValueError):
        raise MenuError(
            "%s: 'countdown' is true or a number of seconds" % path)
    if seconds <= 0:
        raise MenuError("%s: a countdown is at least one second" % path)
    return seconds


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
        # Nor is it a row anybody wrote, so nobody wrote a hold onto it -
        # and picking the wrong speaker is undone by picking the right one.
        "confirm": False,
        # Nor a countdown: what a listing found is picked and picked again
        # until the room sounds right, which is the opposite of a press you
        # are given time to take back.
        "countdown": 0,
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

    **A cell is up to three lines and every one of them is the same kind of
    thing**: a time it renders itself (`format`, in strftime) or the last
    thing a command printed (`from`). `over` sits above the cell's own line
    and `under` below it, both set small; the middle one is the headline and
    is what the cell's height is spent on.

    Three lines in one cell rather than three cells, because the head is
    packed first fit - nothing here can promise that the cell holding the day
    lands under the one holding the time rather than beside it. A name over a
    clock over a weekday is one thing read at three sizes, and only a cell can
    say that.

    A line written as a bare string is a `format`, which is the common case
    and keeps `under = "%A"` the whole of what a weekday costs. A table is the
    long form, and it is how a line becomes a command:

        over = { from = "id -un", ttl = 0 }

    `ttl` is how long an answer stays fresh, which is not the same clock as
    the heartbeat: the surface is redrawn every couple of seconds, the weather
    is asked for every fifteen minutes, and a name is asked for once.

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
        line = _head_line(entry, path, where)
        item = {
            "control": "",
            "id": (str(entry.get("id", "")).strip()
                   or slug(line["format"] or line["from"])),
            "format": line["format"],
            "from": line["from"],
            # How long an answer stays fresh, in seconds. Zero asks once.
            "ttl": line["ttl"],
            # What the cell says before the first answer, and after a command
            # that had nothing to say. A blank cell in a grid reads as a
            # drawing fault rather than as a command that failed.
            "empty": line["empty"],
        }
        item["span"] = _span(entry, "", path, columns)
        if item["id"] in seen:
            raise MenuError(
                "%s: two cells here are called %r - give one an 'id'"
                % (path, item["id"])
            )
        seen[item["id"]] = True
        item["line"] = dict(line, id=item["id"])
        # The small lines are named after the cell, so the daemon has
        # somewhere to file what each command said without the config having
        # to name three things to get one clock.
        for key in ("over", "under"):
            spec = entry.get(key)
            if spec is None or (isinstance(spec, str) and not spec.strip()):
                item[key] = None
                continue
            sub = _head_line(spec, "%s.%s" % (path, key), where)
            sub["id"] = "%s.%s" % (item["id"], key)
            if sub["id"] in seen:
                raise MenuError(
                    "%s: two cells here are called %r - give one an 'id'"
                    % (path, sub["id"])
                )
            seen[sub["id"]] = True
            item[key] = sub
        items.append(item)
    return items


def _head_line(spec, path, where):
    """One line of a head cell, from a bare format or from the long form.

    The same two sources at every level, deliberately: a cell that could
    print a command's answer while the line under it could only print a time
    would be two grammars wearing one name, and the first thing anybody would
    want there is the one it does not have.
    """
    if isinstance(spec, str):
        spec = {"format": spec}
    if not isinstance(spec, dict):
        raise MenuError("%s is a strftime format or a table" % path)
    fmt = str(spec.get("format", "")).strip()
    source = str(spec.get("from", "")).strip()
    if bool(fmt) == bool(source):
        raise MenuError(
            "%s prints either a 'format' or a 'from', not both or neither"
            % path
        )
    if fmt:
        try:
            time.strftime(fmt)
        except ValueError as exc:
            raise MenuError("%s: %s" % (path, exc)) from exc
    return {
        "id": "",
        "format": fmt,
        "from": source,
        "ttl": _ttl(spec.get("ttl"), path),
        "empty": str(spec.get("empty", "")).strip(),
    }


def _group_meta(spec, path):
    """What a group says under its name on the bar.

    A literal, or a command with a `ttl` - the same long form a head cell's
    line takes, because it is the same question asked in a smaller box and
    two grammars for it would be one more thing to look up. A bare string is
    the literal here rather than a strftime format: a nav card saying the
    time would be the head strip said twice, and a place is not an hour.
    """
    empty = {"id": "", "text": "", "from": "", "ttl": 0.0, "empty": ""}
    if spec is None:
        return empty
    if isinstance(spec, str):
        return dict(empty, text=spec.strip())
    if not isinstance(spec, dict):
        raise MenuError("%s: 'meta' is a word or a table" % path)
    source = str(spec.get("from", "")).strip()
    if not source:
        raise MenuError("%s: a 'meta' table says what it runs, in 'from'"
                        % path)
    return {"id": "", "text": "",
            "from": source, "ttl": _ttl(spec.get("ttl"), path),
            "empty": str(spec.get("empty", "")).strip()}


def tile_meta(item, texts=None):
    """What a tile's heading or detail prints, or "" where it says nothing.

    `MenuModel.group_meta` one surface down, and deliberately the same three
    answers in the same order: a literal, the command's last word, then what
    to say when it has printed nothing. The difference is the fallback - a
    group with no meta says how many tiles it holds, and a tile with none
    says what the config called it, which the payload is already carrying.
    """
    meta = item.get("meta")
    if not meta:
        return ""
    if meta["text"]:
        return meta["text"]
    if not meta["from"]:
        return ""
    return (texts or {}).get(meta["id"]) or meta["empty"]


def meta_sources(items):
    """Every group whose meta is a command, with its id and its ttl.

    The bar's answer to `head_sources`: one place that knows where a meta
    lives, so the daemon asks for what has gone stale without learning the
    shape of a group.
    """
    for item in items:
        meta = item.get("meta")
        if meta and meta["from"]:
            yield meta


def head_sources(cell):
    """Every line of a head cell that is a command, with its id and its ttl.

    One place that knows a cell has three lines, so the daemon asks for what
    has gone stale without learning the shape of a cell.
    """
    for line in (cell.get("line"), cell.get("over"), cell.get("under")):
        if line and line["from"]:
            yield line


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
        # The last press, and the one thing on this surface that is an event
        # rather than a state. It travels the way `ripple.py`'s burst does -
        # a serial the panel compares with the last one it drew - because the
        # whole page is re-sent every `VIEW_HEARTBEAT` seconds and a payload
        # carrying a press it has already answered is a duplicate, not a
        # second press. Never sent as 0: a shell that connects mid-session
        # must not flash a tile for a press that happened before it came up.
        self.press_seq = 0
        self.press_hit = ""
        # Which way the page in front was arrived from, and the same kind of
        # event `press_seq` is: a serial the panel compares with the last one
        # it drew, because the whole page is re-sent twice a second and a
        # payload carrying a turn it has already animated is a duplicate.
        #
        # +1 is further in - a level down, the next group - and -1 is back
        # out. It is here rather than in the daemon because the model is what
        # knows a page changed at all; what a panel does with it is a
        # drawing, and the drawing belongs to the panel.
        self.turn_seq = 0
        self.turn_way = 0
        # What `group_move` knows and `enter_group` cannot work out: a walk
        # along a strip that wraps. Cleared as it is read.
        self._group_way = 0
        self.source = []
        self.items = []
        self.tiles = []
        self.rows = 0
        self.title = title
        # The model's own identity, and the reason it is a name rather than a
        # number: a tile changing size re-packs the page under it, so an index
        # is stale the moment it is used.
        self.selected = None
        # Which row of the card in front is selected, where that card is a
        # `rows` tile, and None everywhere else. **Not `self.rows`**, which is
        # how many rows of *cells* the page came to: this is one id inside one
        # tile, and it is an id for the reason `selected` is one.
        #
        # A second cursor rather than a second kind of `selected`, because
        # everything the page does to a tile - carry it, hide it, resize it,
        # scroll to it - is still being done to the tile. Only a *press* is
        # aimed further in, and `acting` is where that is asked.
        self.row = None
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

    def lone(self, item):
        """Whether a card that lists has anything to choose between.

        **A listing with one line is not a list.** One pair of speakers in the
        room is one row, picking it sets what is already set, and a column of
        alternatives with a single alternative in it is a card of furniture
        round a fact. What it is then is a *reading* - what the sound is going
        out of - so it is drawn as one and A does nothing on it.

        Only a card that **lists**. A card somebody wrote one row into meant
        that row, and a verb is a verb whether or not it has company.

        **And only where picking it would change nothing**, which is the
        other half of the same sentence. A listing marks the one in force -
        `*` from `pactl`, `on` here - so a lone row that is *marked* is the
        fact the card is furniture round, and a lone row that is not is
        something to run or to switch to. A folder with one script in it is a
        list of one, and A runs it. The `empty` placeholder is a reading
        whatever else is true: it carries no action, so there is nothing there
        to press.
        """
        if not item or item.get("control") != ROWS or not item.get("from"):
            return False
        rows = self.rows_of(item)
        if len(rows) > 1:
            return False
        if not rows:
            return True
        row = rows[0]
        return row["action"] is None or bool(row.get("on"))

    def rows_of(self, item):
        """The rows a card draws inside itself, as they are offered now.

        A row carries a `when` like any other entry, so a card can hold a verb
        that is only there in game mode - and the row cursor walks what is
        drawn rather than what was written.
        """
        if not item or not item.get("rows"):
            return []
        return self.visible(item["rows"])

    @property
    def acting(self):
        """What a press acts on: the row in the card, or the tile itself.

        A card of rows that has been **entered** is not pressed - the row in it
        is - and every question a press then asks is that row's: whether it
        has to be held, whether it stays, what it runs. Before it is entered
        the card is the answer, which is what lets `takeable()` catch the
        press and turn it into going in. Everything *else* a tile is asked,
        from being carried to being taken, is the tile's whether or not
        anybody is inside it, which is why this is a second question rather
        than a different `current`.
        """
        item = self.current
        if item is None or not self.entered:
            return item
        for row in self.rows_of(item):
            if row["id"] == self.row:
                return row
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

    def group_meta(self, item, texts=None):
        """The second line on a group's nav card.

        The word the config wrote, or the answer to the command it named -
        whichever the daemon last heard, because running one is not this
        module's business, the same split every head line is under.

        And if it wrote neither, how many tiles the page holds. The count is
        a fallback rather than an answer: it is the one fact about a group
        this module can know on its own, and it is the least of the things
        worth saying up there. A row break is not a tile; it ends one.
        """
        meta = item["meta"]
        if meta["text"]:
            return meta["text"]
        if meta["from"]:
            return (texts or {}).get(meta["id"]) or meta["empty"]
        drawn = [row for row in self.group_page(item)
                 if row["control"] != ROW_BREAK]
        return str(len(drawn)) if drawn else ""

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
        # Which way the thumb pushed, kept for `enter_group` to hand on: the
        # strip wraps, so the indexes cannot answer it - the last chip to the
        # first is a step to the right and looks like a jump to the left.
        self._group_way = 1 if step > 0 else -1
        self.enter_group((self.group + step) % len(self.groups))
        return True

    def enter_group(self, index):
        if not self.groups:
            self.group = 0
            self.stack = []
            self.page_item = None
            self._show([], self.root_title)
            return
        was = self.group
        self.group = max(0, min(int(index), len(self.groups) - 1))
        if self.group != was:
            # Which way along the bar, not which index is larger: the strip
            # wraps, and walking off the last chip onto the first is still
            # somebody going right. `group_move` is the only caller that
            # knows that, so it says so and this believes it.
            self.turned(self._group_way if self._group_way
                        else (1 if self.group > was else -1))
        self._group_way = 0
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

    def turned(self, way):
        """Mark that the page changed, and which way it was reached from.

        Called by the three things that replace a page and by nothing else:
        drilling in, coming back out, and walking the bar. Opening the menu is
        not one of them - a surface arriving has its own way of arriving, and
        a page that also slid in from somewhere would be two entrances for one
        press.
        """
        self.turn_seq += 1
        self.turn_way = way

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
        # A page placed again under a selection that has not moved keeps the
        # row it was on; a page arriving settles on the first one.
        self.settle_row()

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

    def _band(self, mine, boxes, horizontal):
        """The tiles a press may land on without leaving the band it walks.

        `snap.beside` is the whole of it: the rows a sideways press covers,
        the columns an up or down one does. A page is packed, so what is
        under your thumb is under the tile you are on - and where there is
        nothing, a press that took the nearest thing past the edge crossed
        the page instead. `Workspace lock` ends a row with a hole under it,
        and down found `Mute` at the other end of the row below, because
        nothing at all was underneath.

        Which is why the desktop is not handed the same list: a page is
        packed and a desktop is not, so a window with nothing beside it is
        one a flick still has to reach. `snap.beside` says the rest.
        """
        here = snap.rect(mine)
        return [box for box in boxes
                if box["id"] == mine["id"]
                or snap.beside(here, snap.rect(box), horizontal)]

    def step(self, direction):
        """Move the selection to the tile that way, or leave it alone.

        `snap.choose` is what decides, unchanged. It already answers "which
        rectangle is that way from here?" for the windows a flick lands on,
        and a tile is a rectangle in cells - so the pad walks a page the way
        it walks a desktop, by one rule rather than two that can disagree.

        What the menu hands it is narrower than what the desktop does: only
        the tiles **beside** this one, because a page is packed where a
        desktop is not. See `_band`.

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
        beside = self._band(self._rect(here), boxes,
                            direction in ("left", "right"))
        landed = snap.choose(beside, x, y, direction, self.bias)
        if landed is None:
            return False
        self.selected = landed["id"]
        self.taken = None
        # A card walked onto is a card nobody is inside, and its cursor starts
        # at the top: where you were in the *last* card is not a place in this
        # one.
        self.row = None
        self.settle_row()
        return True

    def _row_index(self, item):
        """Where the row cursor sits in one card. 0 where it sits nowhere."""
        for number, row in enumerate(self.rows_of(item)):
            if row["id"] == self.row:
                return number
        return 0

    def _step_row(self, item, direction):
        """Move within a card of rows. False where the press leaves it."""
        rows = self.rows_of(item)
        if not rows or direction not in ("up", "down"):
            return False
        landed = self._row_index(item) + (1 if direction == "down" else -1)
        if landed < 0 or landed >= len(rows):
            return False
        self.row = rows[landed]["id"]
        return True

    def settle_row(self):
        """Keep the row cursor somewhere real on the card now in front.

        It survives leaving the card and going back in - B out of a list and
        A into it again is one gesture somebody made twice, not a reason to be
        put back at the top - and it is dropped when the selection moves to
        another tile, where it would be a place in a list nobody is looking at.
        """
        rows = self.rows_of(self.current)
        if not rows:
            self.row = None
            return
        names = [row["id"] for row in rows]
        if self.row not in names:
            self.row = names[0]

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
            # A different card, so the row cursor is somewhere else entirely.
            self.row = None
        self.selected = self.tiles[index]["item"]["id"]
        self.settle_row()

    def select_id(self, name):
        """Jump the selection to a named tile. False when it is not here."""
        for tile in self.tiles:
            if tile["item"]["id"] == name:
                if name != self.selected:
                    self.taken = None
                    self.row = None
                self.selected = name
                self.settle_row()
                return True
        return False

    def select_row(self, name):
        """Name a row inside the card in front - what a pointer asks for.

        By id and not by number, for the reason a tile is: a row carrying a
        `when` comes and goes, and the row a cursor is over is the one it is
        over rather than the third one somebody wrote.
        """
        for row in self.rows_of(self.current):
            if row["id"] == name:
                self.row = name
                return True
        return False

    # -- holding a control --------------------------------------------------

    @property
    def entered(self):
        """Whether the card in front is a card of rows that has been gone into.

        `taken` on a slider means both axes are the tile's; here it means one
        of them is, and the difference between the two states is the whole of
        what A did. Until it is true, up and down belong to the **page**: a
        direction that meant the next row on one tile and the next tile on the
        one beside it is a page no thumb can be asked to read.
        """
        item = self.held
        return item is not None and item["control"] == ROWS

    def step_row(self, direction):
        """Walk the entered card. False at either end, and off one entirely.

        No wrapping, for the reason the grid does not wrap: a cursor that
        reappeared at the far end of a list a thumb was pushing away from is a
        cursor you have lost. The end of the list is the end of it, and B is
        the way out.
        """
        if not self.entered:
            return False
        return self._step_row(self.current, direction)

    def takeable(self):
        """The tile in front, if it is one that has to be held to be moved."""
        item = self.current
        if item is not None and item["control"] in TAKEABLE:
            if self.lone(item):
                # Nothing to go in for. The one tile this surface already had
                # with no press on it is the `readout`, for the same reason:
                # what the machine is doing is published rather than set, and
                # a press that finds nothing to do is worse than no press.
                return None
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
        of a twelve-column grid stops at twelve, which is what pushing it
        further could have meant - and a page with a **bottom** clamps the
        other axis the same way. Only the HUD's page has one (`rows_limit`),
        and a tile taller than the screen it is drawn on is a tile with rows
        nobody can see.
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
        limit = self.rows_limit()
        if limit is not None:
            height = min(height, limit)
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
        """Act on the selected tile, or on the row inside it.

        Returns ("enter", item) for a submenu, ("run", item) for a leaf, or
        ("none", None) when the page is empty. A card of rows always answers
        with one of its rows, which is never a page: `acting` is what makes
        the difference, and everything below here is the same press it was.
        """
        item = self.acting
        if item is None:
            return ("none", None)
        # Marked before the page can change under it. Drilling in draws no
        # flash, and should not: the tile it landed on is not on the page that
        # arrives, and the page arriving is the answer.
        self.press_seq += 1
        self.press_hit = item["id"]
        if item["items"] is not None:
            self.stack.append(
                (self.items, self.selected, self.title, self.page_item)
            )
            self.page_item = item
            self.turned(1)
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
            # And inside a card that lists, where the tick belongs to that
            # card's own rows. Only the card the pick landed in: two lists on
            # one page are two questions, and picking a speaker says nothing
            # about which microphone is in use.
            rows = other.get("rows") or ()
            if any(row is item for row in rows):
                for row in rows:
                    if row.get("listed") and row["action"] is not None:
                        row["on"] = row is item

    def back(self):
        """Leave the current submenu. False when there is nothing above it.

        False at depth 0 as well, where the group's own page is the top: the
        bar is not a level to climb to, so the daemon closes the menu there.
        """
        if not self.stack:
            return False
        items, selected, title, self.page_item = self.stack.pop()
        self.turned(-1)
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

    def _row_state(self, item, state, value):
        """One row of a card, as the panel draws it.

        The same three questions a tile is asked and no others: what it is
        called, whether what it sets is already the case, and what a row that
        steps a number has got to. A row has no cells, no control, no mark of
        its own to be carried by and nowhere to drill in to, so none of the
        rest of a tile's payload has anything to say here.
        """
        out = {"id": item["id"], "l": item["label"], "i": item["icon"],
               "d": item["detail"]}
        if item.get("icon_font"):
            out["f"] = item["icon_font"]
        if item.get("on") is not None:
            # A **listed** row knows its own answer, the way a listed tile
            # does: the daemon can ask a setting what it holds, but not a
            # device whether the sound is going to it.
            out["on"] = bool(item["on"])
            return out
        if item["action"] is None:
            return out
        if state is not None:
            answer = state(item["action"])
            if answer is not None:
                out["on"] = bool(answer)
        if value is not None:
            text = value(item["action"])
            if text:
                out["d"] = text
        return out

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
            cell = {
                "t": drawable(self._head_text(item["line"], texts)),
                "x": tile["at"][0], "y": tile["at"][1],
                "w": tile["size"][0], "h": tile["size"][1],
            }
            # A line the cell does not have is left off the wire rather than
            # sent empty, so `o !== undefined` is the whole of the panel's
            # test for whether a cell stacks - and a one-line cell, which is
            # nearly all of them, costs what it always did.
            for key, short in (("over", "o"), ("under", "u")):
                text = self._head_text(item[key], texts)
                if text:
                    cell[short] = drawable(text)
            out.append(cell)
        return out, rows

    def _head_text(self, line, texts):
        """What one line of a head cell says right now.

        A format is rendered here, because that costs nothing and a clock that
        waited on the daemon would be a clock that is wrong between presses. A
        command's answer is whatever the daemon last heard: running one is not
        this module's business.
        """
        if not line:
            return ""
        if line["format"]:
            return self._strftime(line["format"])
        return (texts or {}).get(line["id"]) or line["empty"]

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
                   keys=None, control=None, metas=None, chrono=None):
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

        `chrono` is the stopwatch, and it is **the one value that does not
        ride on its own tile**. What it holds changes between one payload and
        the next, and the panel decides whether to rebuild the page by
        comparing the tiles it was sent with the tiles it has - so a number
        that always differs is every delegate on the page rebuilt twice a
        second to move one hand. It is the gauge's thumb one control along,
        and `menu_gauge` had already written the warning down.

        Asked only where a tile would draw it, and called rather than passed
        for the same reason `control` is: nothing here asks the daemon for a
        thing no tile on this page can show.
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
            if item.get("icon_font"):
                # Off the wire where there is none, so the panel's test for
                # "is this glyph somebody else's" is one `undefined` check and
                # every other tile costs nothing.
                row["f"] = item["icon_font"]
            # Through `drawable` because it is somebody else's words: a
            # window titles itself, and a title is exactly the string qml.md
            # 8.6 is about.
            said = drawable(tile_meta(item, metas))
            if said:
                # The live line, where the tile has one: the heading of a card
                # of rows, the detail of anything else. Off the wire entirely
                # for a tile that has no `meta`, and for one whose command has
                # said nothing and left no `empty` word to say instead - so a
                # page draws what the config called it until there is
                # something truer to draw.
                row["m"] = said
            if self.edit and self.hidden(item["id"]):
                # Drawn only so it can be put back, and drawn as what it is.
                row["off"] = True
            if item["id"] == self.picked:
                row["p"] = True
            if item["control"]:
                row["k"] = item["control"]
                if item["control"] in (CLOCK, CHRONO):
                    # The time of day, on both faces that have hands. This
                    # module works it out itself - it can, because a clock
                    # reads nothing and there is no table to be handed;
                    # `minute_of_day` says why it is one number and why it is
                    # rendered on this side. A chronograph still tells the
                    # time: what it adds is the thing a clock cannot do.
                    row["mn"] = minute_of_day()
                if item["shows"]:
                    row["s"] = item["shows"]
                if item["id"] == self.taken:
                    # Held, so both axes belong to it rather than to getting
                    # about. Drawn differently because that is the one state
                    # of this surface a press means something else in.
                    row["hd"] = True
                if control is not None and item["reads"]:
                    # What it is on now. Merged rather than returned as the
                    # row, so a control tile keeps its label, its icon and its
                    # cells like any other.
                    #
                    # Asked of a control that **reads** something rather than
                    # of any control at all: a card of rows is a control with
                    # no value in it, and the daemon's answer to "what is this
                    # on?" begins by unpacking the pair it reads from.
                    #
                    # A chronograph reads nothing and is not asked here either,
                    # for a second reason that is the whole of `chrono` below:
                    # what it holds changes between one payload and the next,
                    # and a tile that changes is a page that is rebuilt.
                    row.update(control(item) or {})
            if item.get("rows") is not None:
                # The card's own rows, drawn in it rather than behind it. They
                # carry no cells: what places a row is the row above it.
                row["rs"] = [self._row_state(one, state, value)
                             for one in self.rows_of(item)]
                if self.lone(item):
                    # And that it has nothing to choose between, so the panel
                    # draws the one line as a reading rather than as a column
                    # of one. It is the model's to say: the rows are its, and
                    # what a card *is* should not be worked out twice.
                    row["one"] = True
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
        measured = None
        if chrono is not None and any(
                tile["item"]["control"] == CHRONO for tile in self.tiles):
            measured = chrono()
        state_out = {
            "open": opened,
            "title": self.title,
            "clock": self.clock(),
            "depth": self.depth,
            "sel": self.selected or "",
            # And which row of it, where the tile in front is a card of rows.
            # Its own field rather than a second meaning for `sel`: the page
            # still scrolls to a tile, the ring is still round a tile, and a
            # panel that had to work out which of the two `sel` meant would be
            # the place those two answers could disagree.
            "row": self.row or "",
            "hd": self.taken or "",
            "edit": self.edit,
            "pick": self.picked or "",
            "g": self.group,
            # Which tile the last press landed on, and which press that was.
            # An event among states: the panel flashes the tile only when the
            # serial moves, so a heartbeat re-sending the page does nothing.
            "n": self.press_seq,
            "hit": self.press_hit,
            # And which page turn this is, with the direction it was reached
            # from. The same event shape as `n` for the same reason: the page
            # is re-sent twice a second, and a turn the panel has already
            # drawn must not be drawn again.
            "turn": self.turn_seq,
            "way": self.turn_way,
            # `d` is the group's own detail, and it is what the title line
            # prints at the top level: the bar names the group and cannot say
            # what is inside it. On every group rather than only the current
            # one, because which one that is already travels as `g` and a
            # payload that answered the same question twice is a payload that
            # can disagree with itself.
            "groups": [{"l": item["label"], "i": item["icon"],
                        "d": item["detail"],
                        "m": drawable(self.group_meta(item, metas)),
                        "id": item["id"]}
                       for item in self.groups],
            "head": head_tiles,
            "headrows": head_rows,
            "keys": keys or [],
            "cols": self.columns,
            "rows": self.rows,
            "items": items,
        }
        if measured is not None:
            # Off the wire entirely for a page with no chronograph on it, so
            # every other page costs nothing for this one existing - and there
            # is one field rather than one per tile because there is one
            # stopwatch, however many faces are drawn of it.
            state_out["chrono"] = measured
        return state_out
