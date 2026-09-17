"""The readings, left on screen: which tiles, and which cell each one is in.

The HUD is deliberately not a surface of its own design - it is one of the
menu's own pages, packed by the menu's own code and drawn somewhere else. So
almost everything here is about that promise holding: the same grid, the same
arrangement, the same ids, and two rules that are the HUD's alone about what
it refuses to draw.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad import hud as hud_module
from omapad import menu as menu_module
from omapad import sysinfo as sysinfo_module
from omapad.hud import HudModel


def tree(*entries):
    """One group called `hud`, holding whatever is passed."""
    return menu_module.build(
        [{"id": "hud", "label": "Readings", "items": list(entries)}],
        settings={"hud": {"kind": "bool"}},
        machine=sysinfo_module.READINGS,
    )


def readout(label, name, **extra):
    row = {"label": label, "control": "readout", "reads": "sys:" + name}
    row.update(extra)
    return row


def answers(**words):
    """A stand-in for the daemon's half: what each reading says now."""
    def value(item):
        name = item["reads"][1]
        if name not in words:
            return None
        said = words[name]
        return said if isinstance(said, dict) else {"t": said}
    return value


class ThePageIsAnOrdinaryMenuGroup(unittest.TestCase):
    def test_the_group_is_found_by_id(self):
        model = HudModel(tree(readout("Processor", "cpu")), page="hud")
        self.assertIsNotNone(model.group())
        self.assertEqual(len(model.tiles), 1)

    def test_a_page_that_is_not_there_is_an_empty_hud(self):
        # Not an error: a config that renamed or removed the group gets a HUD
        # with nothing on it rather than a daemon that will not start.
        model = HudModel(tree(readout("Processor", "cpu")), page="nowhere")
        self.assertIsNone(model.group())
        self.assertEqual(model.tiles, [])
        self.assertEqual(model.view_state(True, answers(cpu="1%"))["items"],
                         [])

    def test_no_tree_at_all_is_an_empty_hud(self):
        # What the daemon hands over when `build_menu` raised and the menu
        # came up empty. The HUD must not be the second thing that breaks.
        model = HudModel(None)
        self.assertEqual(model.tiles, [])

    def test_the_cells_are_the_ones_the_menu_packed(self):
        # The whole promise of the design: where a tile sits in the grid is
        # where it sits on the screen, because it is the same grid.
        entries = [readout("Processor", "cpu"), readout("Memory", "memory")]
        model = HudModel(tree(*entries), columns=6)
        placed = menu_module.place(
            menu_module.build(entries, machine=sysinfo_module.READINGS), 6,
            None)[0]
        self.assertEqual(
            [tile["at"] for tile in model.tiles],
            [tile["at"] for tile in placed],
        )


class WhatThisSurfaceRefusesToDraw(unittest.TestCase):
    """Two rules, and both of them are the point of the surface."""

    def test_a_tile_with_something_to_press_is_not_drawn(self):
        # The page holds its own switch - it has to, because this surface is
        # never pressed - and a switch drawn here would be a control over a
        # game with no way to reach it. The rule is the press, not the
        # reading: a clock has nothing to press either, and is drawn.
        model = HudModel(tree(
            readout("Processor", "cpu"),
            {"label": "Keep on screen", "control": "toggle",
             "reads": "pad:hud"},
        ))
        drawn = model.view_state(True, answers(cpu="37%"))["items"]
        self.assertEqual([row["l"] for row in drawn], ["Processor"])

    def test_a_reading_that_has_never_answered_draws_nothing(self):
        # A fan this laptop publishes no number for is not a tile saying
        # nothing, it is no tile - which is what makes one page of readings
        # correct on two machines.
        model = HudModel(tree(
            readout("Processor", "cpu"), readout("Fan", "fan")))
        drawn = model.view_state(True, answers(cpu="37%"))["items"]
        self.assertEqual([row["l"] for row in drawn], ["Processor"])

    def test_an_answer_with_no_words_in_it_is_no_answer(self):
        # The shape `sys_control` returns when a source is pointed at
        # something that is not there: a dict is not the same as a reading.
        model = HudModel(tree(readout("Fan", "fan")))
        drawn = model.view_state(True, answers(fan={"v": 0.5}))["items"]
        self.assertEqual(drawn, [])

    def test_nothing_is_drawn_with_no_daemon_to_ask(self):
        # `value=None` is the heartbeat before anything has been read. An
        # empty HUD is right; a page of labels with no numbers is not.
        model = HudModel(tree(readout("Processor", "cpu")))
        self.assertEqual(model.view_state(True)["items"], [])

    def test_the_whole_page_is_still_packed(self):
        # Including the tiles this surface will not draw. That is what keeps
        # the promise: a readout lands in the cell the menu shows it in, and
        # it cannot do that if the tiles before it were taken out first.
        model = HudModel(tree(
            {"label": "Keep on screen", "control": "toggle",
             "reads": "pad:hud", "span": [6, 1]},
            readout("Processor", "cpu"),
        ))
        drawn = model.view_state(True, answers(cpu="37%"))["items"]
        self.assertEqual(len(drawn), 1)
        # Pushed onto the second row by a switch that is not drawn at all.
        self.assertEqual(drawn[0]["y"], 1)


class TheClockIsTheOtherTileWithNothingToPress(unittest.TestCase):
    """What a bar was for, on the surface that replaces one.

    Game mode takes Omarchy's bar away, which is the right trade for a screen
    watched from a sofa and leaves the time with nowhere to be. A clock reads
    nothing, so neither of this surface's two rules is about it: there is no
    press to keep it off, and no source that could have gone quiet.
    """

    def clock(self, **extra):
        row = {"label": "Time", "control": "clock"}
        row.update(extra)
        return row

    def test_a_clock_is_drawn_over_a_game(self):
        model = HudModel(tree(readout("Processor", "cpu"), self.clock()))
        drawn = model.view_state(True, answers(cpu="37%"))["items"]
        self.assertEqual([row["l"] for row in drawn], ["Processor", "Time"])

    def test_a_clock_is_drawn_with_no_daemon_to_ask(self):
        # `value=None` is the heartbeat before anything has been read, which
        # empties a page of readings and cannot empty this tile: there is
        # nothing to have answered.
        model = HudModel(tree(self.clock()))
        drawn = model.view_state(True)["items"]
        self.assertEqual([row["l"] for row in drawn], ["Time"])

    def test_it_carries_both_hands_and_which_tile_it_is(self):
        model = HudModel(tree(self.clock()))
        row = model.view_state(True)["items"][0]
        self.assertEqual(row["k"], "clock")
        self.assertIn(row["mn"], (menu_module.minute_of_day(),
                                  menu_module.minute_of_day() + 1))

    def test_a_reading_still_says_which_tile_it_is(self):
        # One field for the panel's whole choice of drawing, on every tile
        # that reaches this surface rather than on one of the two.
        model = HudModel(tree(readout("Processor", "cpu")))
        row = model.view_state(True, answers(cpu="37%"))["items"][0]
        self.assertEqual(row["k"], "readout")
        self.assertNotIn("mn", row)

    def test_nothing_is_asked_about_a_clock(self):
        # `names()` is what the daemon polls for. A clock is not a reading and
        # must not put a name on that list.
        model = HudModel(tree(readout("Processor", "cpu"), self.clock()))
        self.assertEqual(model.names(), ["cpu"])

    def test_a_chronograph_is_not_drawn_here(self):
        # The rule is the press, and a chronograph has one: A on it starts,
        # stops and resets a measurement, and a pusher over a game is a
        # pusher with no way to reach it. The clock beside it stays, because
        # there is nothing on a clock to press.
        model = HudModel(tree(
            self.clock(), {"label": "Stopwatch", "control": "chrono"}))
        drawn = model.view_state(True)["items"]
        self.assertEqual([row["l"] for row in drawn], ["Time"])

    def test_it_takes_the_cells_the_menu_gave_it(self):
        # Square, because it is round - and the same square on both surfaces,
        # because it is the same tile.
        model = HudModel(tree(self.clock()))
        row = model.view_state(True)["items"][0]
        self.assertEqual((row["w"], row["h"]), (2, 2))


class TheGridIsTheScreen(unittest.TestCase):
    """The one thing here that is not the menu's geometry.

    A menu page is as many rows as its tiles came to and scrolls, so nothing
    on it means "the bottom". A screen has a bottom edge, so this grid takes a
    fixed row count - which is what makes a cell a share of the screen rather
    than a number of pixels, and what puts a tile carried into the last row
    and the last column in the corner.
    """

    def test_the_row_count_is_the_settings_not_the_packings(self):
        model = HudModel(tree(readout("Processor", "cpu")), rows=9)
        self.assertEqual(model.rows, 9)
        self.assertEqual(model.view_state(True, answers(cpu="1%"))["rows"], 9)

    def test_an_empty_page_still_has_its_rows(self):
        # The panel divides by this, so a page with nothing on it must not
        # hand it a 0 to divide by.
        model = HudModel(None, rows=9)
        self.assertEqual(model.view_state(True, answers())["rows"], 9)

    def test_a_row_count_below_one_is_still_one(self):
        self.assertEqual(HudModel(None, rows=0).rows, 1)

    def test_a_tile_reaches_the_last_row(self):
        plan = {"order": [], "hidden": [], "span": {},
                "at": {"processor": (4, 7)}}
        model = HudModel(tree(readout("Processor", "cpu")), rows=8,
                         layout={"hud": plan})
        row = model.view_state(True, answers(cpu="1%"))["items"][0]
        self.assertEqual((row["x"], row["y"]), (4, 7))

    def test_a_tile_below_the_last_row_is_pulled_onto_it(self):
        # The same clamp as the right-hand edge, downwards. A menu page has no
        # last row, so a tile can be carried further down there than this grid
        # has - and a pin drawn off the end of the screen is the arrangement
        # breaking rather than adapting.
        plan = {"order": [], "hidden": [], "span": {},
                "at": {"processor": (0, 40)}}
        model = HudModel(tree(readout("Processor", "cpu")), rows=8,
                         layout={"hud": plan})
        row = model.view_state(True, answers(cpu="1%"))["items"][0]
        self.assertEqual(row["y"], 7)

    def test_a_tall_tile_is_clamped_by_its_own_height(self):
        plan = {"order": [], "hidden": [], "span": {"processor": (2, 3)},
                "at": {"processor": (0, 7)}}
        model = HudModel(tree(readout("Processor", "cpu")), rows=8,
                         layout={"hud": plan})
        row = model.view_state(True, answers(cpu="1%"))["items"][0]
        self.assertEqual((row["y"], row["h"]), (5, 3))

    def test_a_tile_taller_than_the_page_is_the_page(self):
        plan = {"order": [], "hidden": [], "span": {"processor": (2, 9)},
                "at": {"processor": (0, 2)}}
        model = HudModel(tree(readout("Processor", "cpu")), rows=4,
                         layout={"hud": plan})
        row = model.view_state(True, answers(cpu="1%"))["items"][0]
        self.assertEqual((row["y"], row["h"]), (0, 4))


class WhatTheDaemonIsAskedFor(unittest.TestCase):
    def test_only_the_readings_on_this_page(self):
        model = HudModel(tree(
            readout("Processor", "cpu"), readout("Disk", "disk")))
        self.assertEqual(model.names(), ["cpu", "disk"])

    def test_a_reading_named_twice_is_asked_for_once(self):
        model = HudModel(tree(
            readout("Processor", "cpu"), readout("Busy", "cpu")))
        self.assertEqual(model.names(), ["cpu"])

    def test_a_tile_that_reads_something_else_is_not_a_reading(self):
        # `pad:` and `live:` are answered by other things entirely, and asking
        # sysinfo for one is a KeyError on the loop.
        model = HudModel(tree(
            {"label": "Keep on screen", "control": "toggle",
             "reads": "pad:hud"},
            readout("Processor", "cpu"),
        ))
        self.assertEqual(model.names(), ["cpu"])

    def test_the_order_is_the_order_they_are_packed(self):
        # So the first thing asked for is the first thing on screen, which is
        # what makes the top-left tile fill first on a cold start.
        model = HudModel(tree(
            readout("Disk", "disk"), readout("Processor", "cpu")))
        self.assertEqual(model.names(), ["disk", "cpu"])


class ThePayload(unittest.TestCase):
    def setUp(self):
        self.model = HudModel(tree(
            readout("Processor", "cpu", icon="C"),
            readout("Fan", "fan"),
        ))

    def test_a_tile_carries_its_id_label_and_cells(self):
        row = self.model.view_state(
            True, answers(cpu={"t": "37%", "v": 0.37}))["items"][0]
        self.assertEqual(row["id"], "processor")
        self.assertEqual(row["l"], "Processor")
        self.assertEqual(row["i"], "C")
        self.assertEqual((row["x"], row["y"]), (0, 0))
        self.assertEqual((row["w"], row["h"]), (2, 1))

    def test_the_reading_is_merged_onto_the_tile(self):
        row = self.model.view_state(
            True, answers(cpu={"t": "37%", "v": 0.37}))["items"][0]
        self.assertEqual(row["t"], "37%")
        self.assertAlmostEqual(row["v"], 0.37)

    def test_a_reading_with_no_bar_carries_no_bar(self):
        # A temperature has no top of scale that is not invented, so the field
        # is absent rather than 0 - which would draw an empty bar and say
        # something false.
        row = self.model.view_state(
            True, answers(cpu={"t": "54°C"}))["items"][0]
        self.assertNotIn("v", row)

    def test_a_tile_with_no_icon_carries_none(self):
        model = HudModel(tree(readout("Processor", "cpu")))
        row = model.view_state(True, answers(cpu="37%"))["items"][0]
        self.assertNotIn("i", row)

    def test_the_grid_travels_with_it(self):
        # The panel cannot read the config, so how many cells across and down
        # the screen is cut into are both the daemon's to say.
        state = self.model.view_state(True, answers(cpu="37%"))
        self.assertEqual(state["cols"], menu_module.COLUMNS)
        self.assertEqual(state["rows"], self.model.rows)

    def test_open_says_whether_it_is_on(self):
        self.assertTrue(self.model.view_state(True, answers(cpu="1%"))["open"])
        self.assertFalse(
            self.model.view_state(False, answers(cpu="1%"))["open"])


class TheArrangementIsTheSameOne(unittest.TestCase):
    """A tile carried in the menu's edit mode moves on the HUD too.

    Same tree, same layout file, same packer - so there is no second place a
    person would have to arrange this page, and no way for the two to
    disagree about where a tile is.
    """

    def setUp(self):
        self.entries = [
            readout("Processor", "cpu"),
            readout("Memory", "memory"),
            readout("Disk", "disk"),
        ]

    def test_a_saved_order_is_the_order_drawn(self):
        plan = {"order": ["disk", "processor", "memory"]}
        model = HudModel(tree(*self.entries), layout={"hud": plan})
        drawn = model.view_state(
            True, answers(cpu="1%", memory="2%", disk="3%"))["items"]
        self.assertEqual([row["l"] for row in drawn],
                         ["Disk", "Processor", "Memory"])

    def test_a_hidden_tile_is_not_on_the_hud(self):
        plan = {"hidden": ["memory"]}
        model = HudModel(tree(*self.entries), layout={"hud": plan})
        drawn = model.view_state(
            True, answers(cpu="1%", memory="2%", disk="3%"))["items"]
        self.assertEqual([row["l"] for row in drawn], ["Processor", "Disk"])

    def test_a_hidden_tile_is_not_asked_for_either(self):
        # Nothing is polled for a reading nobody can see.
        plan = {"hidden": ["memory"]}
        model = HudModel(tree(*self.entries), layout={"hud": plan})
        self.assertEqual(model.names(), ["cpu", "disk"])

    def test_a_reading_put_in_a_cell_is_drawn_in_that_cell(self):
        # The reason the carry gesture became a cell at all: over a game,
        # where a reading sits is the whole of what the page says, and the top
        # left corner is where the game puts its own.
        plan = {"order": [], "hidden": [], "span": {},
                "at": {"memory": (3, 2)}}
        model = HudModel(tree(*self.entries), layout={"hud": plan})
        drawn = model.view_state(
            True, answers(cpu="1%", memory="2%", disk="3%"))["items"]
        cells = dict((row["l"], (row["x"], row["y"])) for row in drawn)
        self.assertEqual(cells["Memory"], (3, 2))
        # And everything else still flows from the top left around it.
        self.assertEqual(cells["Processor"], (0, 0))
        self.assertEqual(cells["Disk"], (2, 0))

    def test_a_saved_span_is_the_span_drawn(self):
        plan = {"span": {"processor": [3, 1]}}
        model = HudModel(tree(*self.entries), layout={"hud": plan})
        row = model.view_state(
            True, answers(cpu="1%", memory="2%", disk="3%"))["items"][0]
        self.assertEqual(row["w"], 3)

    def test_repacking_picks_up_an_arrangement_made_since(self):
        # What `set_hud(True)` calls: a page rearranged while the readings
        # were off is rearranged when they come back.
        model = HudModel(tree(*self.entries), layout={})
        model.layout["hud"] = {"order": ["disk", "processor", "memory"]}
        model.repack()
        self.assertEqual(model.names(), ["disk", "cpu", "memory"])


class TheModuleHoldsNoValues(unittest.TestCase):
    def test_it_reads_nothing_and_runs_nothing(self):
        # State and geometry, the same division `menu.py` keeps: what a
        # reading says is the daemon's, and a model that went and looked
        # would be a file read inside a draw.
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "omapad", "hud.py")
        with open(path) as handle:
            source = handle.read()
        for word in ("import subprocess", "import os", "open(", "popen"):
            self.assertNotIn(word, source)

    def test_it_is_not_a_layer_and_takes_no_bindings(self):
        # No grab, no entry in either SURFACE_LAYERS, no `[bindings.hud]`. The
        # moment it could take a press it would be in the way of the game it
        # is over.
        from omapad import daemon as daemon_module
        self.assertNotIn("hud", daemon_module.Daemon.SURFACE_LAYERS)

    def test_a_readout_is_the_one_control_that_cannot_be_taken(self):
        # Taking a tile is how a control with a range is adjusted sideways.
        # There is nothing here to adjust, so there is nothing to take.
        self.assertNotIn(hud_module.READOUT, menu_module.TAKEABLE)
        self.assertIn(hud_module.READOUT, menu_module.CONTROLS)


if __name__ == "__main__":
    unittest.main()
