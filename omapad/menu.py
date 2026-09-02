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
"""

import time

from . import actions

ROOT_TITLE = "Go"


class MenuError(ValueError):
    pass


def build(entries, where="menu.items"):
    """Normalise config entries into a tree, resolving every action.

    Actions are parsed here rather than when an entry is picked, so a typo
    surfaces in `omapad check` instead of doing nothing at the moment you
    press it.
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
        if children is not None and spec is not None:
            raise MenuError("%s has both an action and items" % path)
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
        }
        if children is not None:
            if item["repeat"]:
                raise MenuError("%s: only an action row can repeat" % path)
            if item["stay"]:
                raise MenuError("%s: only an action row can stay open" % path)
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
        self.items = self.root
        self.title = title
        self.index = 0

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
        self.items = self.root
        self.title = self.root_title
        self.index = 0

    def move(self, step):
        if not self.items:
            return
        self.index = (self.index + step) % len(self.items)

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
            self.items = item["items"]
            self.title = item["label"]
            self.index = 0
            return ("enter", item)
        return ("run", item)

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
            if item["action"] is not None:
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
