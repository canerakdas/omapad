"""The readings, left on screen: one menu page, drawn where it was arranged.

Game mode takes Omarchy's bar away, which is the right trade for a screen
watched from a sofa and leaves one question unanswered: what the machine is
actually doing while it does it. This is the answer, and it is deliberately
**not a surface of its own design**.

The page it draws is an ordinary `[[menu.items]]` group. So the tiles are
written where every other tile is written, they are arranged with the gesture
that arranges every other page - hold Y, carry one, let go - and the
arrangement lands in the same `layout.toml`. Where a tile sits in the grid is
where it sits on the screen, because it is the same grid: this model packs the
page with `menu.place` exactly as the menu does, and the panel draws those
cells over the whole screen instead of inside a card.

Two things follow from that, and both are the point:

- **A tile that is not a readout is not drawn here.** The page holds its own
  switch, and a switch is a thing to press; this surface is never pressed.
- **A reading that has never answered draws nothing at all.** A fan this
  laptop publishes no number for is not a tile saying nothing, it is no tile -
  which is what makes one page of readings correct on two machines.

There is no `[bindings.hud]`, no entry in `SURFACE_LAYERS` and no grab: this
surface reads no pad input, takes no keyboard focus and passes every click
through. It is something you look at while doing something else, and the
moment it could take a press it would be in the way of the game it is over.
"""

from .menu import COLUMNS, arrange, place

# What this surface draws, and the only thing it draws.
READOUT = "readout"


class HudModel:
    """Which tiles the HUD has, and which cell each one sits in.

    Holds no values: what a reading says is the daemon's - `sysinfo.py` is
    what asks - and this module holds state and geometry, the same division
    `menu.py` keeps.
    """

    def __init__(self, items=None, page="hud", columns=COLUMNS, rows=12,
                 layout=None):
        # The whole menu tree, not one page of it: which group is the HUD is a
        # setting, and a tree that has been reloaded has to be re-searched
        # rather than a page held on to.
        self.root = items or []
        self.page = page
        self.columns = columns
        # **The grid here has a last row, and the menu's does not.** A menu
        # page is as many rows as its tiles came to and scrolls past the fold;
        # this one is the screen, and a screen has a bottom edge. Without a
        # fixed count there is no cell that means "the bottom", so a tile
        # carried to the corner would be drawn a fixed number of pixels down
        # from the top and the corner would be somewhere else entirely.
        #
        # It is the divisor as well as the limit: a cell is a share of the
        # screen rather than a number of pixels, which is the other half of
        # the same answer - the grid cannot end at the bottom of the screen
        # and also be measured in pixels from the top.
        self.rows = max(1, int(rows))
        # **Held, never copied.** This is the menu's own arrangement dict: the
        # menu is where a page is rearranged and it owns the working copy, so
        # a copy here would be the file as it was read and would stop being
        # true the moment anybody carried a tile. `repack()` is what turns a
        # change to it into cells; sharing the dict is what there is to
        # repack from.
        self.layout = layout if layout is not None else {}
        self.source = []
        self.items = []
        self.tiles = []
        self.repack()

    def group(self):
        """The menu group this draws, or None where the config has no such id.

        None is not an error: a config that renamed the page, or removed it,
        gets a HUD with nothing on it rather than a daemon that will not
        start.
        """
        for item in self.root:
            if item.get("id") == self.page:
                return item
        return None

    def repack(self):
        """Place the page again, against whatever the arrangement says now.

        The **whole** page is packed, including the tiles this surface will
        not draw. That is what keeps the promise the page makes: a readout
        lands in the cell the menu shows it in, and it cannot do that if the
        tiles before it were taken out of the packing first.
        """
        group = self.group()
        self.source = (group or {}).get("items") or []
        plan = self.layout.get(self.page)
        self.items = arrange(self.source, plan)
        # The row count is the page's, not the packing's - so `place` clamps a
        # pin onto the last row rather than reporting a taller page, and what
        # comes back is thrown away.
        self.tiles, _ = place(self.items, self.columns, plan, self.rows)

    def names(self):
        """The readings this page shows, in the order they are packed."""
        out = []
        for tile in self.tiles:
            item = tile["item"]
            if item["control"] == READOUT and item["reads"]:
                source, name = item["reads"]
                if source == "sys" and name not in out:
                    out.append(name)
        return out

    def view_state(self, opened, value=None):
        """The payload the panel draws.

        `value(item)` is the daemon's half - what the reading says now, and
        how far along its travel it is where it has one. A tile it answers
        nothing for is left out entirely: there is no such thing here as a
        tile with nothing in it, because nothing is what most of these
        readings are on most machines.
        """
        items = []
        for tile in self.tiles:
            item = tile["item"]
            if item["control"] != READOUT:
                continue
            found = value(item) if value is not None else None
            if not found or not found.get("t"):
                continue
            row = {
                "id": item["id"],
                "l": item["label"],
                "x": tile["at"][0], "y": tile["at"][1],
                "w": tile["size"][0], "h": tile["size"][1],
            }
            if item["icon"]:
                row["i"] = item["icon"]
            row.update(found)
            items.append(row)
        return {
            "open": opened,
            "cols": self.columns,
            "rows": self.rows,
            "items": items,
        }
