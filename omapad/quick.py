"""The quick menu: one row of tiles over whatever is in front.

The controller menu is a *place* - a bar of groups, pages of tiles, a head -
and the HOME button is its door, because the button in the middle of the pad
is the one a console spends on its home. PLUS (Start, the Xbox pad's ☰) is the
button a game spends on pausing, and what somebody reaches for with it is not a
place but five or six things: louder, quieter, a screenshot, the next window,
the window gone. A page of the menu can hold those, and it is still a page
somebody has to walk to - a chip along the bar, then down the grid - while a
game is waiting behind the scrim.

So this is the other shape: one row, nothing to drill into, the D-pad walking
it end to end and wrapping, and a band under the row saying what the tile in
front is on and what A will do to it. The drawing is `Console Overlay` in the
Console OS v2 mockups: the row of square tiles, the band, the window in front
named at the top left.

A model, like `menu.py`: no I/O and no compositor. What a tile does is the
binding grammar, parsed at load so `omapad check` names a typo, and what a
tile is on is asked of its own action - `Action.state` for the tick,
`Action.value` for the number - so a volume tile is `live:volume=up` rather
than a second place that knows what a volume is.
"""

import re

from . import actions

# What a tile may say about itself. Anything else is a typo, and a typo in a
# file somebody edits by hand should be named rather than ignored.
KEYS = ("id", "label", "icon", "icon_font", "detail", "action", "up", "down",
        "stay", "arm", "danger", "when")

# What `when` may say about the place: a tile for a window in front, or for an
# empty workspace. Left out, the tile is on the row either way.
WHERE = ("window", "empty")

# And about the pad: the controller menu's states, less `first_run`, which is
# spent by opening the menu and would never be true here. The workspace lock
# is what asked for them - it is somebody's most-pressed tile over a game and
# was two pages into the menu, and on a desktop it has nothing to lock to.
STATES = ("game", "handed_over", "locked", "kept")

WHEN = WHERE + STATES

# What the band says under a tile that has been pressed once and wants a
# second press. A word for the pad rather than for the button: which letter
# A is printed as depends on the pad, and the legend along the foot already
# draws the badge beside the word `Confirm`.
ARMED = "Press again to confirm"


class QuickError(ValueError):
    pass


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "tile"


def build(entries, where="quick.items"):
    """`[[quick.items]]` -> a list of tiles, or QuickError naming the one.

    A tile needs a label and something to do: an `action` for A, or `up` and
    `down` for a value the D-pad nudges - or both, for a volume that A also
    mutes. `arm` asks for a second press before the action runs, for what
    nobody can take back; `danger` draws the tile in the theme's urgent
    colour, and says nothing about how it behaves. `when` puts the tile on
    the row only while a window is in front (`window`) or only while none is
    (`empty`), so one row can be two: a pause over something, and a way to
    start something over nothing. It may also list states the way a menu
    row's does, any one of them being enough - and a place listed beside
    them still has to be the place: `["window", "game"]` is a window, in
    game mode.
    """
    if entries is None:
        return []
    if not isinstance(entries, list):
        raise QuickError("%s must be a list of tables" % where)
    items = []
    seen = set()
    for index, entry in enumerate(entries):
        path = "%s[%d]" % (where, index)
        if not isinstance(entry, dict):
            raise QuickError("%s must be a table" % path)
        unknown = sorted(set(entry) - set(KEYS))
        if unknown:
            raise QuickError("%s: unknown key %s (try %s)"
                             % (path, ", ".join(unknown), ", ".join(KEYS)))
        label = str(entry.get("label", "")).strip()
        if not label:
            raise QuickError("%s needs a label" % path)
        parsed = {}
        for key in ("action", "up", "down"):
            spec = entry.get(key)
            if spec is None:
                parsed[key] = None
                continue
            try:
                parsed[key] = actions.parse(spec)
            except actions.ActionError as exc:
                raise QuickError("%s.%s: %s" % (path, key, exc)) from exc
        if (parsed["up"] is None) != (parsed["down"] is None):
            # One direction alone is a value that can only go one way, and a
            # band printing `Adjust` over it would be promising the other.
            raise QuickError("%s: up and down come as a pair" % path)
        if parsed["action"] is None and parsed["up"] is None:
            raise QuickError("%s needs an action, or up and down" % path)
        arm = bool(entry.get("arm", False))
        if arm and parsed["action"] is None:
            raise QuickError("%s: arm needs an action to hold back" % path)
        place, states = _when(entry.get("when"), path)
        ident = str(entry.get("id") or _slug(label)).strip()
        if ident in seen:
            raise QuickError("%s: a second tile called %r - give one an id"
                             % (path, ident))
        seen.add(ident)
        items.append({
            "id": ident,
            "label": label,
            "icon": str(entry.get("icon", "")),
            "icon_font": str(entry.get("icon_font", "")).strip(),
            "detail": str(entry.get("detail", "")).strip(),
            "action": parsed["action"],
            "up": parsed["up"],
            "down": parsed["down"],
            "stay": bool(entry.get("stay", False)),
            "arm": arm,
            "danger": bool(entry.get("danger", False)),
            "where": place,
            "states": states,
        })
    return items


def _when(spec, path):
    """`when` -> (the place or None, the states as a tuple).

    Two questions in one key, because a tile is written by hand and one list
    reads better than two: where it is, and what is true. Both places at once
    is a tile for everywhere, which leaving the place out already says.
    """
    if spec is None:
        return None, ()
    names = [spec] if isinstance(spec, str) else spec
    if not isinstance(names, list):
        raise QuickError("%s.when is a word or a list of them" % path)
    where = None
    states = []
    for name in names:
        name = str(name).strip()
        if name in WHERE:
            if where not in (None, name):
                raise QuickError("%s.when: window and empty is everywhere - "
                                 "leave both out" % path)
            where = name
        elif name in STATES:
            states.append(name)
        else:
            raise QuickError("%s.when: %r (try %s)"
                             % (path, name, ", ".join(WHEN)))
    return where, tuple(states)


class QuickModel:
    """Which tile is in front, and whether it is waiting for a second press."""

    def __init__(self, items):
        self.items = list(items)
        # The ids of the tiles this machine cannot answer for, which the row
        # is drawn and walked without. The daemon decides - see `hide` - and
        # `index` counts along what is left.
        self.hidden = frozenset()
        self.index = 0
        # The id of a tile pressed once that wants pressing again. Anything
        # but that second press lets go of it: a step, a nudge, the surface
        # closing.
        self.armed = None

    @property
    def shown(self):
        """The tiles on the row, in order: every one that is not hidden."""
        return [item for item in self.items if item["id"] not in self.hidden]

    @property
    def current(self):
        shown = self.shown
        if not shown:
            return None
        return shown[self.index % len(shown)]

    def hide(self, ids):
        """Take these tiles off the row, keeping the one in front where it is.

        A tile arriving or leaving shifts every tile after it, so the tile in
        front is followed by name: a brightness tile appearing while somebody
        stands on Screenshot leaves them on Screenshot, not on whatever slid
        into its place. Where the one in front is the one going, the
        selection stays at the same place in the row.
        """
        ids = frozenset(ids)
        if ids == self.hidden:
            return False
        current = self.current
        self.hidden = ids
        shown = self.shown
        for index, item in enumerate(shown):
            if current is not None and item["id"] == current["id"]:
                self.index = index
                break
        else:
            self.index = min(self.index, max(0, len(shown) - 1))
        if self.armed is not None and self.armed in ids:
            self.armed = None
        return True

    def reset(self):
        """Back to the first tile, which is the way back to what was in front.

        Not back to where it was, the way the menu does: that one is a place
        somebody returns to, and this is a pause - the first thing it offers
        is to stop pausing, so PLUS then A is always back to the game.
        """
        self.index = 0
        self.armed = None

    def move(self, way):
        """One tile along, wrapping. False where there is nowhere to go.

        A row wraps where a grid must not: in two dimensions wrapping is
        losing the selection, and in one it is the short way round.
        """
        self.armed = None
        count = len(self.shown)
        if count < 2:
            return False
        self.index = (self.index + way) % count
        return True

    def select(self, index):
        """Name a tile outright - what `omapad ctl quick select N` asks."""
        if not 0 <= index < len(self.shown) or index == self.index:
            return False
        self.index = index
        self.armed = None
        return True

    def press(self):
        """What A does on the tile in front: `run`, `arm` or None.

        None where the tile has nothing for A - a value the D-pad nudges and
        A does not touch.
        """
        item = self.current
        if item is None or item["action"] is None:
            return None, item
        if item["arm"] and self.armed != item["id"]:
            self.armed = item["id"]
            return "arm", item
        self.armed = None
        return "run", item

    def nudge(self, way):
        """The action up or down stands for on the tile in front, or None."""
        self.armed = None
        item = self.current
        if item is None:
            return None
        return item["up"] if way > 0 else item["down"]

    def disarm(self):
        """Let go of a tile waiting for its second press. True if one was."""
        was = self.armed is not None
        self.armed = None
        return was

    def view_state(self, opened, state=None, value=None, share=None,
                   head=None, keys=None):
        """The payload `QuickMenu.qml` draws.

        `state(action)` and `value(action)` are the daemon's, the same pair
        `menu.view_state` takes: whether what the action sets is already in
        force, and what the thing it steps is on, in words. `share(action)` is
        where along its travel that thing is, 0..1, or None for one with no
        travel to draw.

        **The tiles and the band are two fields**, because walking the row
        changes only one of them. The tiles carry nothing that moves with the
        selection - which tile is in front is `sel`, beside them - so a step
        re-runs one binding in the panel rather than rebuilding the row
        (qml.md 5.4).
        """
        tiles = []
        shown = self.shown
        for item in shown:
            reading = item["up"] or item["action"]
            on = None
            if item["action"] is not None and state is not None:
                on = state(item["action"])
            words = value(reading) if value is not None else ""
            tile = {"id": item["id"], "l": item["label"], "i": item["icon"],
                    "m": words or "", "on": on is True, "x": item["danger"]}
            if item["icon_font"]:
                tile["f"] = item["icon_font"]
            tiles.append(tile)
        band = {}
        item = self.current
        if item is not None:
            reading = item["up"] or item["action"]
            words = value(reading) if value is not None else ""
            band = {
                "id": item["id"],
                "l": item["label"],
                "w": words or "",
                "t": ARMED if self.armed == item["id"] else item["detail"],
                "adj": item["up"] is not None,
                "arm": self.armed == item["id"],
                "x": item["danger"],
            }
            where = None
            if item["up"] is not None and share is not None:
                where = share(item["up"])
            if where is not None:
                band["v"] = round(max(0.0, min(1.0, where)), 3)
        return {
            "open": bool(opened),
            "sel": self.index if shown else -1,
            "tiles": tiles,
            "band": band,
            "head": head or {},
            "keys": keys or [],
        }
