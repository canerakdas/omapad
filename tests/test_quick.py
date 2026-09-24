"""The quick menu's model: building the row, walking it, the second press."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from omapad import actions
from omapad import config as config_module
from omapad import quick


def row(*entries):
    return quick.build(list(entries))


RESUME = {"label": "Resume", "action": "quick:close"}
VOLUME = {"label": "Volume", "up": "live:volume=up", "down": "live:volume=down",
          "detail": "Up and down turn it"}
CLOSE = {"label": "Close window", "action": "hypr:hl.dsp.window.close()",
         "arm": True, "danger": True}


class BuildTests(unittest.TestCase):
    def test_the_shipped_row_builds(self):
        # With none of the developer's own files under it: see `only()` in
        # test_daemon.py.
        missing = os.path.join(tempfile.gettempdir(), "omapad-no-such-config")
        shipped = config_module.load(path=missing, mapping=missing,
                                     layout=missing, settings=missing)
        items = quick.build(shipped.quick_items)
        self.assertGreater(len(items), 3)
        # PLUS then A is back to what was in front, so the first tile of
        # each of the two rows is the way out.
        self.assertEqual([item["label"] for item in items
                          if item["when"] == "window"][0], "Resume")
        self.assertEqual([item["label"] for item in items
                          if item["when"] == "empty"][0], "Back")

    def test_actions_are_parsed_at_load(self):
        items = row(RESUME, VOLUME)
        self.assertIsInstance(items[0]["action"], actions.QuickAction)
        self.assertIsInstance(items[1]["up"], actions.LiveAction)
        self.assertIsNone(items[1]["action"])

    def test_a_typo_names_the_tile(self):
        with self.assertRaises(quick.QuickError) as caught:
            row(RESUME, {"label": "Oops", "action": "nope:what"})
        self.assertIn("quick.items[1].action", str(caught.exception))

    def test_a_tile_needs_a_label(self):
        with self.assertRaises(quick.QuickError):
            row({"action": "quick:close"})

    def test_a_tile_needs_something_to_do(self):
        with self.assertRaises(quick.QuickError):
            row({"label": "Nothing"})

    def test_up_and_down_come_as_a_pair(self):
        with self.assertRaises(quick.QuickError):
            row({"label": "Half", "up": "live:volume=up"})

    def test_arm_needs_an_action(self):
        with self.assertRaises(quick.QuickError):
            row({"label": "Armed", "up": "live:volume=up",
                 "down": "live:volume=down", "arm": True})

    def test_an_unknown_key_is_named(self):
        with self.assertRaises(quick.QuickError) as caught:
            row({"label": "Resume", "action": "quick:close", "colour": "red"})
        self.assertIn("colour", str(caught.exception))

    def test_a_tile_can_say_when_it_is_on_the_row(self):
        items = row(dict(RESUME, when="window"), VOLUME)
        self.assertEqual(items[0]["when"], "window")
        self.assertIsNone(items[1]["when"])
        with self.assertRaises(quick.QuickError) as caught:
            row(dict(RESUME, when="always"))
        self.assertIn("quick.items[0].when", str(caught.exception))

    def test_two_tiles_may_not_share_a_name(self):
        with self.assertRaises(quick.QuickError):
            row(RESUME, dict(RESUME))
        # An id is how the second one is told apart.
        row(RESUME, dict(RESUME, id="again"))


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.model = quick.QuickModel(row(RESUME, VOLUME, CLOSE))

    def test_the_row_wraps_both_ways(self):
        self.assertTrue(self.model.move(-1))
        self.assertEqual(self.model.current["label"], "Close window")
        self.assertTrue(self.model.move(1))
        self.assertEqual(self.model.current["label"], "Resume")

    def test_reset_goes_back_to_the_first_tile(self):
        self.model.move(1)
        self.model.reset()
        self.assertEqual(self.model.index, 0)

    def test_a_tile_with_an_action_runs(self):
        kind, item = self.model.press()
        self.assertEqual((kind, item["label"]), ("run", "Resume"))

    def test_a_value_tile_has_nothing_for_a(self):
        self.model.move(1)
        kind, _ = self.model.press()
        self.assertIsNone(kind)
        self.assertIsInstance(self.model.nudge(1), actions.LiveAction)

    def test_an_armed_tile_wants_a_second_press(self):
        self.model.move(-1)
        self.assertEqual(self.model.press()[0], "arm")
        self.assertEqual(self.model.armed, "close-window")
        self.assertEqual(self.model.press()[0], "run")
        self.assertIsNone(self.model.armed)

    def test_walking_away_lets_go_of_it(self):
        self.model.move(-1)
        self.model.press()
        self.model.move(1)
        self.model.move(-1)
        self.assertEqual(self.model.press()[0], "arm")

    def test_a_hidden_tile_is_walked_past(self):
        self.model.hide(["volume"])
        self.assertTrue(self.model.move(1))
        self.assertEqual(self.model.current["label"], "Close window")

    def test_hiding_keeps_the_tile_in_front_by_name(self):
        self.model.move(-1)
        self.model.hide(["volume"])
        self.assertEqual(self.model.current["label"], "Close window")
        self.model.hide([])
        self.assertEqual(self.model.current["label"], "Close window")

    def test_hiding_the_armed_tile_lets_go_of_it(self):
        self.model.move(-1)
        self.model.press()
        self.model.hide(["close-window"])
        self.assertIsNone(self.model.armed)

    def test_disarm_says_whether_there_was_anything(self):
        self.assertFalse(self.model.disarm())
        self.model.move(-1)
        self.model.press()
        self.assertTrue(self.model.disarm())


class ViewTests(unittest.TestCase):
    def setUp(self):
        self.model = quick.QuickModel(row(RESUME, VOLUME, CLOSE))

    def test_the_payload_carries_the_row_and_the_band(self):
        state = self.model.view_state(True)
        self.assertTrue(state["open"])
        self.assertEqual(state["sel"], 0)
        self.assertEqual([t["l"] for t in state["tiles"]],
                         ["Resume", "Volume", "Close window"])
        self.assertEqual(state["band"]["l"], "Resume")
        self.assertTrue(state["tiles"][2]["x"])

    def test_a_step_changes_the_band_and_not_the_tiles(self):
        # The panel rebuilds the row only when `tiles` differs, so nothing in
        # it may move with the selection - qml.md 5.4.
        before = self.model.view_state(True)
        self.model.move(1)
        after = self.model.view_state(True)
        self.assertEqual(before["tiles"], after["tiles"])
        self.assertNotEqual(before["band"], after["band"])

    def test_a_value_is_worded_and_placed(self):
        self.model.move(1)
        state = self.model.view_state(
            True, value=lambda action: "40%", share=lambda action: 0.4)
        self.assertEqual(state["tiles"][1]["m"], "40%")
        self.assertEqual(state["band"]["w"], "40%")
        self.assertEqual(state["band"]["v"], 0.4)
        self.assertTrue(state["band"]["adj"])

    def test_no_travel_draws_no_bar(self):
        state = self.model.view_state(True, share=lambda action: None)
        self.assertNotIn("v", state["band"])

    def test_the_armed_tile_says_so_in_the_band(self):
        self.model.move(-1)
        self.model.press()
        band = self.model.view_state(True)["band"]
        self.assertTrue(band["arm"])
        self.assertEqual(band["t"], quick.ARMED)

    def test_a_switch_is_lit_while_it_is_on(self):
        model = quick.QuickModel(row({"label": "Mute",
                                      "action": "live:mute=toggle"}))
        state = model.view_state(True, state=lambda action: True)
        self.assertTrue(state["tiles"][0]["on"])

    def test_a_hidden_tile_is_not_drawn(self):
        self.model.hide(["volume"])
        state = self.model.view_state(True)
        self.assertEqual([t["l"] for t in state["tiles"]],
                         ["Resume", "Close window"])

    def test_an_empty_row_still_draws(self):
        state = quick.QuickModel([]).view_state(True)
        self.assertEqual(state["sel"], -1)
        self.assertEqual(state["band"], {})


if __name__ == "__main__":
    unittest.main()
