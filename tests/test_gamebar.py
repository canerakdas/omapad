"""The game-mode bar: what it prints, and what it refuses to promise."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad import config as config_module, gamebar, guide


def build(data):
    return config_module.Config(data)


class ModeOnlyTests(unittest.TestCase):
    """Game mode reads the base layer for `mode:` actions and nothing else."""

    def test_a_tap_hold_keeps_only_the_half_that_still_fires(self):
        kept = gamebar.mode_only({
            "tap": "hypr:hl.dsp.window.cycle_next()",
            "hold": "mode:toggle",
            "desc": "Next window",
            "hold_desc": "Game mode",
        })
        self.assertEqual(kept, {"hold": "mode:toggle", "hold_desc": "Game mode"})

    def test_a_binding_with_no_way_out_in_it_promises_nothing(self):
        self.assertIsNone(gamebar.mode_only("key:ENTER"))
        self.assertIsNone(gamebar.mode_only({"tap": "click:left"}))

    def test_a_plain_mode_action_survives_whole(self):
        self.assertEqual(gamebar.mode_only("mode:desktop"), "mode:desktop")


class ViewTests(unittest.TestCase):
    def setUp(self):
        self.config = build({"bindings": {"game": {}}})
        self.model = gamebar.GameBarModel(self.config)

    def view(self, bindings, available=None):
        return self.model.view_state(
            True, lambda button: bindings.get(button), available, "game"
        )

    def test_every_badge_on_it_is_printed_in_the_pads_own_names(self):
        """The hints, the workspace walkers and the door, all three: one of
        them built without the layout puts two consoles on one bar."""
        self.model.layout = "playstation"
        state = self.view({
            "A": "click:left",
            "L": "hypr:hl.dsp.focus({ workspace = 'e-1' })",
            "R": "hypr:hl.dsp.focus({ workspace = 'e+1' })",
            "PLUS": "menu:toggle",
        })
        self.assertEqual([row["b"] for row in state["actions"]], ["✕"])
        self.assertEqual(state["wsprev"]["b"], "L1")
        self.assertEqual(state["wsnext"]["b"], "R1")
        self.assertEqual(state["menu"]["b"], "Options")

    def test_the_bar_follows_omarchys_own_edge_unless_it_is_pinned(self):
        # The plugin is the one that can see Omarchy's bar, so "auto" is
        # carried through to it rather than resolved here.
        self.assertEqual(self.view({})["pos"], "auto")
        pinned = gamebar.GameBarModel(build({
            "bindings": {"game": {}},
            "gamebar": {"position": "bottom"},
        }))
        state = pinned.view_state(True, lambda button: None, None, "game")
        self.assertEqual(state["pos"], "bottom")

    def test_the_bar_carries_its_height_so_the_sofa_can_set_it(self):
        # How far away you sit is a setting, not a shell constant.
        self.assertEqual(self.view({})["h"], 32)
        short = gamebar.GameBarModel(build({
            "bindings": {"game": {}},
            "gamebar": {"height": 26},
        }))
        state = short.view_state(True, lambda button: None, None, "game")
        self.assertEqual(state["h"], 26)

    def test_a_height_that_cannot_hold_a_bar_is_named(self):
        with self.assertRaises(config_module.ConfigError):
            build({"gamebar": {"height": 0}})

    def test_the_bar_carries_the_lean_an_armed_badge_makes(self):
        # Same reason as the height: it has to be seen from wherever the sofa
        # is, so the shell is told rather than deciding. No duration travels
        # beside it - the lean is one flick, and the confirm window it sits
        # out already reaches the badge in `holding`.
        state = self.view({})
        self.assertEqual(state["lean"], 2)
        self.assertNotIn("tremble_ms", state)
        still = gamebar.GameBarModel(build({
            "bindings": {"game": {}},
            "gamebar": {"confirm_lean": 0},
        }))
        state = still.view_state(True, lambda button: None, None, "game")
        self.assertEqual(state["lean"], 0)

    def test_the_bar_carries_how_long_a_fill_waits_before_it_starts(self):
        # A fill that began on contact flickered under a shoulder tapped to
        # walk browser tabs; how long that flick lasts is the user's hands,
        # not ours.
        state = self.view({})
        self.assertEqual(state["fill_delay_ms"], 60)
        prompt = gamebar.GameBarModel(build({
            "bindings": {"game": {}},
            "gamebar": {"confirm_fill_delay_ms": 0},
        }))
        state = prompt.view_state(True, lambda button: None, None, "game")
        self.assertEqual(state["fill_delay_ms"], 0)

    def test_the_bar_carries_the_hand_that_is_on_the_pad(self):
        # A badge that did not answer the button under it would read, on the
        # one thing left on screen, as a pad that had stopped working.
        self.assertEqual(self.view({})["pressed"], [])
        self.model.pressed = ["A", "ZL"]
        self.assertEqual(self.view({})["pressed"], ["A", "ZL"])

    def test_a_binding_that_clicks_the_pointer_is_not_offered_to_one(self):
        # It would click wherever the pointer is, which is the badge that was
        # clicked: the answer lands back on it and asks for another. And a
        # click aimed at the bar reaches the bar, not what the badge offered.
        state = self.view({"A": "click:left", "B": "scroll:down",
                           "X": "key:SUPER+SPACE"})
        offered = dict((row["b"], row["c"]) for row in state["actions"])
        self.assertEqual(offered, {"A": False, "B": False, "X": True})

    def test_a_hold_that_clicks_is_only_refused_where_it_is_what_fires(self):
        # The bar clicks the half it prints: a row showing only a hold is
        # fired as one, so that is the half the question is asked about.
        state = self.view({
            "A": {"hold": "click:left", "hold_desc": "Left click"},
            "B": {"tap": "key:SUPER+SPACE", "desc": "Launcher",
                  "hold": "click:left", "hold_desc": "Left click"},
        }, available=None)
        offered = dict((row["b"], row["c"]) for row in state["actions"])
        self.assertEqual(offered, {"A": False, "B": True})

    def test_the_bar_carries_whether_a_pointer_may_use_it(self):
        # The shell cannot read the config, and the bar has to be able to go
        # back to being a strip that swallows no clicks at all.
        self.assertTrue(self.view({})["click"])
        quiet = gamebar.GameBarModel(build({
            "bindings": {"game": {}},
            "gamebar": {"click": False},
        }))
        state = quiet.view_state(True, lambda button: None, None, "game")
        self.assertFalse(state["click"])

    def test_every_badge_carries_the_button_under_its_printing(self):
        # What a click is sent back as: the printed label is for the eye, and
        # the same one names a different button on another pad.
        self.model.layout = "xbox"
        state = self.view({
            "A": "click:left",
            "L": "hypr:hl.dsp.focus({ workspace = 'e-1' })",
            "R": "hypr:hl.dsp.focus({ workspace = 'e+1' })",
            "PLUS": "menu:toggle",
        })
        self.assertEqual(state["menu"]["n"], "PLUS")
        self.assertEqual(state["wsprev"]["n"], "L")
        self.assertEqual(state["wsnext"]["n"], "R")
        self.assertEqual([row["n"] for row in state["actions"]], ["A"])

    def test_a_lean_that_could_not_be_drawn_is_named(self):
        # A badge cannot lean a negative distance; 0 is "stay put and let the
        # sweep say the window on its own".
        with self.assertRaises(config_module.ConfigError):
            build({"gamebar": {"confirm_lean": -1}})
        # A wait cannot be negative; 0 is "fill from the press".
        with self.assertRaises(config_module.ConfigError):
            build({"gamebar": {"confirm_fill_delay_ms": -1}})

    def test_an_empty_game_layer_says_so_rather_than_printing_nothing(self):
        # An empty strip is indistinguishable from a bar that failed to load.
        state = self.view({})
        self.assertEqual(state["actions"], [])
        self.assertEqual(state["note"], "The pad is the game's")

    def test_a_bound_button_is_printed_in_one_word(self):
        state = self.view({"Y": "click:left"})
        self.assertEqual(state["actions"], [
            # `c` false: a click on this badge would click the pointer, and
            # the pointer is on the badge.
            {"b": "Y", "k": "face", "n": "Y", "c": False,
             "d": "Click", "h": ""},
        ])
        self.assertEqual(state["note"], "")

    def test_the_long_form_is_one_setting_away(self):
        """`[gamebar] brief = false` puts the guide's own phrase on the bar."""
        spelt = gamebar.GameBarModel(build({"gamebar": {"brief": False}}))
        state = spelt.view_state(
            True, lambda button: {"Y": "click:left"}.get(button), None, "game"
        )
        self.assertEqual(state["actions"][0]["d"], "Left click")

    def test_a_binding_that_names_its_own_short_word_keeps_it(self):
        """The first word is the verb often enough to be the rule, and where
        it is not - "New tab" is a tab, not a new - the binding says so."""
        state = self.view({
            "X": {"tap": "key:CTRL+T", "desc": "New tab", "short": "Tab",
                  "hold": "key:F5", "hold_desc": "Reload"},
        })
        self.assertEqual(state["actions"][0]["d"], "Tab")
        self.assertEqual(state["actions"][0]["h"], "Reload")

    def test_a_phrase_with_no_short_word_is_cut_to_its_first(self):
        state = self.view({
            "X": {"tap": "key:CTRL+SHIFT+M", "desc": "Mute the microphone"},
        })
        self.assertEqual(state["actions"][0]["d"], "Mute")

    def test_the_row_is_the_face_buttons_because_they_are_what_changes(self):
        # A shoulder or a trigger carries the same job wherever the scheme
        # goes, so a slot spent on one repeats what the pad said the first
        # time you pressed it. The face buttons are what a profile rewrites
        # under you, which is what three slots are worth spending on.
        state = self.view({"ZR": "click:left", "HOME": "mode:toggle",
                           "X": "key:SUPER+SPACE"})
        self.assertEqual([row["b"] for row in state["actions"]], ["X"])

    def test_another_region_of_the_pad_is_one_setting_away(self):
        wider = gamebar.GameBarModel(build({
            "bindings": {"game": {}},
            "gamebar": {"kinds": ["face", "trigger"]},
        }))
        bindings = {"ZR": "click:left", "X": "key:SUPER+SPACE"}
        state = wider.view_state(
            True, lambda button: bindings.get(button), None, "game"
        )
        # Still offered thumbs-first: the order is PREFERRED's, not the list's.
        self.assertEqual([row["b"] for row in state["actions"]], ["X", "ZR"])

    def test_a_kind_the_pad_has_no_buttons_of_is_named(self):
        with self.assertRaises(config_module.ConfigError):
            build({"gamebar": {"kinds": ["face", "shoulder"]}})
        # And a list that could print nothing at all: the row of hints is the
        # only place the bar says what the pad does where you are standing.
        with self.assertRaises(config_module.ConfigError):
            build({"gamebar": {"kinds": []}})

    def test_a_gesture_that_means_the_same_everywhere_is_not_printed(self):
        # Three slots, spent on what is different about where you are. Confirm
        # and go back are the same wherever you are, so they teach nothing.
        state = self.view({"A": "key:ENTER", "B": "key:ESC", "X": "click:left"})
        self.assertEqual([row["b"] for row in state["actions"]], ["X"])

    def test_the_omission_follows_the_action_not_the_button(self):
        # Move Enter and it stays unprinted; give A something else and A comes
        # back. A list of button names would go stale the first time the
        # scheme changed.
        state = self.view({"A": "click:left", "Y": "key:ENTER"})
        self.assertEqual([row["b"] for row in state["actions"]], ["A"])

    def test_it_stops_before_it_becomes_a_list(self):
        # Every region of the pad offered, so the count is what stops it.
        every = gamebar.GameBarModel(build({
            "bindings": {"game": {}},
            "gamebar": {"kinds": sorted(set(guide.KINDS.values()))},
        }))
        bindings = {b: "click:left" for b in gamebar.PREFERRED}
        state = every.view_state(
            True, lambda button: bindings.get(button), None, "game"
        )
        self.assertEqual(len(state["actions"]), gamebar.MAX_ACTIONS)
        self.assertEqual(gamebar.MAX_ACTIONS, 3)

    def test_a_button_the_pad_does_not_have_is_not_printed(self):
        state = self.view({"X": "key:F12", "A": "click:left"},
                          available={"A", "B"})
        self.assertEqual([row["b"] for row in state["actions"]], ["A"])

    def test_the_menu_button_is_not_printed_twice(self):
        # It has its own place on the left; repeating it on the right reads as
        # two different things you can press.
        state = self.view({"PLUS": "menu:toggle", "A": "click:left"})
        self.assertEqual(state["menu"]["b"], "+")
        self.assertEqual([row["b"] for row in state["actions"]], ["A"])

    def test_the_menu_is_drawn_only_when_a_button_really_opens_it(self):
        self.assertIsNone(self.view({"ZR": "click:left"})["menu"])
        state = self.view({"PLUS": "menu:toggle"})
        self.assertEqual(state["menu"], {"b": "+", "k": "system", "n": "PLUS"})

    def test_a_button_that_only_closes_the_menu_is_not_a_way_in(self):
        self.assertIsNone(self.view({"PLUS": "menu:close"})["menu"])

    def test_the_menu_can_be_a_hold(self):
        state = self.view({"PLUS": {"tap": "click:left", "hold": "menu:open"}})
        self.assertEqual(state["menu"]["b"], "+")

    def test_workspaces_are_passed_through_with_the_live_one_named(self):
        self.model.set_workspaces(
            [{"id": 1, "name": "1", "windows": 2},
             {"id": 2, "name": "2", "windows": 0}], 2)
        state = self.view({})
        self.assertEqual(state["active"], 2)
        self.assertEqual([w["name"] for w in state["workspaces"]], ["1", "2"])

    def test_the_buttons_that_walk_workspaces_are_drawn_beside_them(self):
        # Next to what they move rather than in the row of hints: a button
        # drawn beside the strip it steps through needs no words.
        state = self.view({
            "ZL": "hypr:hl.dsp.focus({ workspace = 'r-1' })",
            "ZR": "hypr:hl.dsp.focus({ workspace = 'r+1' })",
        })
        self.assertEqual(state["wsprev"],
                         {"b": "ZL", "k": "trigger", "n": "ZL", "locked": False})
        self.assertEqual(state["wsnext"],
                         {"b": "ZR", "k": "trigger", "n": "ZR", "locked": False})
        # And not a second time on the right.
        self.assertEqual(state["actions"], [])

    def test_a_step_behind_a_confirming_hold_is_marked_locked(self):
        # The app in front has the plain press - a browser's tabs, a game - so
        # the badge cannot promise a tap will walk the workspace.
        state = self.view({
            "L": {"tap": "key:CTRL+SHIFT+TAB",
                  "hold": "hypr:hl.dsp.focus({ workspace = 'r-1' })",
                  "hold_ms": 2000, "confirm_ms": 2000},
        })
        self.assertEqual(state["wsprev"]["b"], "L")
        self.assertTrue(state["wsprev"]["locked"])

    def test_and_one_on_the_tap_is_not(self):
        state = self.view({
            "L": {"tap": "hypr:hl.dsp.focus({ workspace = 'r-1' })"},
        })
        self.assertFalse(state["wsprev"]["locked"])

    def test_a_workspace_binding_that_is_not_a_step_is_left_alone(self):
        state = self.view({"A": "hypr:hl.dsp.window.move({ workspace = 'e+1' })"})
        # Moving a window to the next workspace is not walking to it, but it
        # names a direction, so this is the honest limit of the heuristic.
        self.assertIsNotNone(state["wsnext"])


if __name__ == "__main__":
    unittest.main()
