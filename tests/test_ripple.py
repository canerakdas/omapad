"""The burst a click leaves behind: what is sent, and what is not drawn."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad import config as config_module, ripple


def build(data=None):
    return config_module.Config(data or {})


class MarkTests(unittest.TestCase):
    def setUp(self):
        self.model = ripple.RippleModel(build())

    def test_a_click_counts_up_from_one(self):
        # The panel treats the first payload it sees as a click, so a shell
        # that connects mid-session must never be handed the 0 a fresh model
        # would otherwise send.
        self.assertTrue(self.model.mark("left", (120.0, 80.0)))
        self.assertEqual(self.model.seq, 1)
        self.assertTrue(self.model.mark("right", (121.0, 80.0)))
        self.assertEqual(self.model.seq, 2)
        self.assertEqual(self.model.button, "right")

    def test_a_button_with_no_half_of_a_ring_draws_nothing(self):
        self.assertFalse(self.model.mark("back", (10.0, 10.0)))
        self.assertEqual(self.model.seq, 0)

    def test_a_compositor_that_cannot_say_where_the_pointer_is_draws_nothing(self):
        # A ring at a position nobody clicked at is worse than no ring.
        self.assertFalse(self.model.mark("left", None))
        self.assertEqual(self.model.seq, 0)

    def test_a_position_that_is_not_a_pair_of_numbers_draws_nothing(self):
        self.assertFalse(self.model.mark("left", ("x", "y")))
        self.assertEqual(self.model.seq, 0)


class ViewTests(unittest.TestCase):
    def test_the_payload_carries_the_click_and_how_to_draw_it(self):
        model = ripple.RippleModel(build())
        model.mark("right", (1920.5, 12.0))
        state = model.view_state()
        self.assertEqual(state["n"], 1)
        self.assertEqual(state["b"], "right")
        self.assertEqual((state["x"], state["y"]), (1920.5, 12.0))
        # No `open` and no heartbeat behind it: this surface is an event.
        self.assertNotIn("open", state)

    def test_a_size_of_zero_is_twice_the_pointer_it_leaves(self):
        state = ripple.RippleModel(build({"cursor": {"size": 64}})).view_state()
        self.assertEqual(state["size"], 128)
        chosen = ripple.RippleModel(build({"ripple": {"size": 40}})).view_state()
        self.assertEqual(chosen["size"], 40)

    def test_the_look_travels_with_it_because_the_panel_cannot_read_the_config(self):
        state = ripple.RippleModel(build({
            "ripple": {"duration_ms": 400, "thickness": 0.2},
        })).view_state()
        self.assertEqual(state["ms"], 400)
        self.assertEqual(state["th"], 0.2)


class SettingTests(unittest.TestCase):
    def test_a_burst_nobody_could_see_is_named(self):
        with self.assertRaises(config_module.ConfigError):
            build({"ripple": {"duration_ms": 0}})
        with self.assertRaises(config_module.ConfigError):
            build({"ripple": {"size": -1}})
        with self.assertRaises(config_module.ConfigError):
            build({"ripple": {"thickness": 0.0}})
        with self.assertRaises(config_module.ConfigError):
            build({"ripple": {"thickness": 0.9}})


if __name__ == "__main__":
    unittest.main()
