"""The controller menu: the entry tree, its navigation, and the view payload.

Shaped like the Omarchy menu rather than a radial: one column of rows, a title
line, and submenus you drill into. A radial reads a stick angle in one flick,
but it caps out at a handful of entries and has nowhere to put a submenu, while
a list is what a D-pad already walks well and is the shape the desktop teaches
everywhere else.

Same split as the keyboard: the tree, the selection and the drill-down stack
live here, and the shell plugin is handed rows and an index and only draws
them. Entries come from `[[menu.items]]` in the config and use the same action
grammar as a button binding, so the menu can reach anything a button can.

A row may also **list** its submenu instead of holding one: `from` is a command
whose output is one row per line. Which audio outputs exist is not something a
config file can know - the answer changes when a television is plugged in - and
a menu that can only name what was written down cannot ask.
"""

import re
import shlex
import time

from . import actions

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
WHEN = ("game", "handed_over", "locked")

# The values a listed line carries, in the order the row's action takes them.
# Numbered rather than one `%s` because the command a row runs often wants two
# of them - a node id and a device name - and unnumbered fields could not say
# which was which. A bare `%` is left alone, so `5%-` still steps a brightness.
FIELD = re.compile(r"%([1-9])")


class MenuError(ValueError):
    pass


def build(entries, where="menu.items"):
    """Normalise config entries into a tree, resolving every action.

    Actions are parsed here rather than when an entry is picked, so a typo
    surfaces in `omapad check` instead of doing nothing at the moment you
    press it. A row that lists its submenu (`from`) is checked the same way,
    against the template each of its lines will run.
    """
    items = []
    for index, entry in enumerate(entries or []):
        path = "%s[%d]" % (where, index)
        if not isinstance(entry, dict):
            raise MenuError("%s must be a table" % path)
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
        }
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
            item["items"] = build(children, path + ".items")
            if not item["items"]:
                raise MenuError("%s opens an empty submenu" % path)
        elif spec is not None:
            try:
                item["action"] = actions.parse(spec)
            except actions.ActionError as exc:
                raise MenuError("%s: %s" % (path, exc)) from exc
        else:
            raise MenuError("%s needs an action or items" % path)
        items.append(item)
    return items


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


class MenuModel:
    """Which level is showing, what is selected, and how to get back."""

    def __init__(self, items=None, title=ROOT_TITLE, clock_format="%A %H:%M"):
        self.root = items or []
        self.root_title = title
        # strftime, or empty for none. The menu carries it because game mode
        # takes Omarchy's bar away and the pad can reach no other clock.
        self.clock_format = clock_format
        # One entry per level above the current one: its rows, the row that was
        # selected, and its title. Going back restores the position you left,
        # which is what makes drilling in and out feel like one place.
        self.stack = []
        # Which of `WHEN` are true, set by the daemon when the menu opens -
        # once, not per draw: a row that appeared or vanished under the
        # selection would move every row below it while a thumb was aiming at
        # one.
        self.conditions = frozenset()
        self.items = self.visible(self.root)
        self.title = title
        self.index = 0

    def visible(self, items):
        """The rows of one level that are offered right now.

        The same list object where no row on the level asks anything, which is
        every level but one: a listed submenu is filled in place after the
        page has been entered, and a copy here would be a page nobody is
        looking at.
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
        if not self.items:
            return None
        return self.items[self.index]

    def reset(self):
        """Back to the root level, the way a menu looks when it opens."""
        self.stack = []
        self.items = self.visible(self.root)
        self.title = self.root_title
        self.index = 0

    def move(self, step):
        if not self.items:
            return
        self.index = (self.index + step) % len(self.items)

    def select(self, index):
        """Jump the selection to one row, the way a pointer names it.

        `move` walks the list one step at a time - the shape of a D-pad press
        and of an arrow key - while a cursor points at a row outright. Out of
        range clamps to the nearest row rather than wrapping: a pointer is
        aiming somewhere, and a selection that wraps across the fold reads as
        a mistake.
        """
        if not self.items:
            return
        if index <= 0:
            self.index = 0
        elif index >= len(self.items):
            self.index = len(self.items) - 1
        else:
            self.index = index

    def press(self):
        """Act on the selected row.

        Returns ("enter", item) for a submenu, ("run", item) for a leaf, or
        ("none", None) when the level is empty.
        """
        item = self.current
        if item is None:
            return ("none", None)
        if item["items"] is not None:
            self.stack.append((self.items, self.index, self.title))
            self.items = self.visible(item["items"])
            self.title = item["label"]
            self.index = 0
            return ("enter", item)
        return ("run", item)

    def choose(self, item):
        """Move the tick to the row just picked, on the level it sits on.

        A listed row's tick came from the listing, and the command it runs is
        let go of rather than waited for - so re-reading the listing here would
        race the thing this press has only just started. The press is the
        answer until the page is entered again and the command asked afresh.
        """
        for other in self.items:
            if other.get("listed") and other["action"] is not None:
                other["on"] = other is item

    def back(self):
        """Leave the current submenu. False when there is nothing above it."""
        if not self.stack:
            return False
        self.items, self.index, self.title = self.stack.pop()
        return True

    def clock(self):
        if not self.clock_format:
            return ""
        try:
            return time.strftime(self.clock_format)
        except ValueError:
            return ""

    def view_state(self, opened, state=None, value=None):
        """The payload the shell plugin draws.

        `state` answers "is this already the case?" for one action - the
        daemon's own question, since a row cannot ask a setting anything. A
        row it answers about is ticked, which is the whole difference between
        a list of choices and a list of guesses.

        `value` answers the other half of that question for a row that steps a
        number: what the number is now. It replaces the row's own detail,
        which is a sentence written once and cannot know. Ticking cannot say
        it - every step of a number is equally "not the case".
        """
        items = []
        for item in self.items:
            row = {
                "l": item["label"],
                "i": item["icon"],
                "d": item["detail"],
                "sub": item["items"] is not None,
            }
            if item.get("on") is not None:
                # A listed row knows its own answer: the daemon can ask a
                # setting what it holds, but not a device whether it is the one
                # the sound is going to.
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
        return {
            "open": opened,
            "title": self.title,
            "clock": self.clock(),
            "depth": self.depth,
            "sel": self.index,
            "items": items,
        }
