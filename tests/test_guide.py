"""The bindings guide: what it reads out of a config, and how it pages."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad import actions, config as config_module, guide


class DescribeTests(unittest.TestCase):
    def test_a_key_chord_is_spelled_the_way_a_keyboard_prints_it(self):
        self.assertEqual(guide.describe("key:ENTER"), "Enter")
        self.assertEqual(guide.describe("key:ESC"), "Esc")
        self.assertEqual(guide.describe("key:SUPER+RETURN"), "Super+Enter")

    def test_the_surfaces_are_named_rather_than_spelled_out(self):
        self.assertEqual(guide.describe("osk:toggle"), "On-screen keyboard")
        self.assertEqual(guide.describe("osk:hold:shift"), "Shift, while held")
        self.assertEqual(guide.describe("osk:layer:next"), "Next keyboard page")
        self.assertEqual(guide.describe("menu:press"), "Pick")
        self.assertEqual(guide.describe("guide:next"), "Next page")

    def test_a_command_loses_the_prefix_every_row_would_carry(self):
        self.assertEqual(
            guide.describe("exec:omarchy-launch-terminal"), "Launch terminal"
        )
        self.assertEqual(
            guide.describe("exec:omarchy-menu toggle apps"), "Menu toggle apps"
        )

    def test_a_dispatcher_is_read_back_as_words(self):
        self.assertEqual(
            guide.describe("hypr:hl.dsp.window.close()"), "Window close"
        )
        self.assertEqual(
            guide.describe("hypr:hl.dsp.layout('togglesplit')"),
            "Layout togglesplit",
        )

    def test_an_argument_that_repeats_the_dispatcher_is_dropped(self):
        # `mode = 'fullscreen'` on hl.dsp.window.fullscreen says it twice.
        self.assertEqual(
            guide.describe("hypr:hl.dsp.window.fullscreen({ mode = 'fullscreen' })"),
            "Window fullscreen",
        )

    def test_a_binding_that_does_nothing_prints_nothing(self):
        self.assertEqual(guide.describe("nop"), "")
        self.assertEqual(guide.describe(None), "")


class RowTests(unittest.TestCase):
    def test_a_bindings_own_words_outrank_the_derivation(self):
        row = guide.button_row("L", {"tap": "hypr:hl.dsp.focus({ workspace = 'r-1' })",
                               "desc": "Previous workspace"})
        self.assertEqual(row["d"], "Previous workspace")

    def test_a_tap_hold_pair_prints_both_halves(self):
        row = guide.button_row("HOME", {"tap": "menu:close", "hold": "mode:toggle"})
        self.assertEqual(row["d"], "Close the menu")
        self.assertEqual(row["h"], "Desktop / game mode")

    def test_a_badge_carries_the_shape_and_what_the_pad_prints(self):
        self.assertEqual(guide.button_row("A", "key:ENTER")["k"], "face")
        self.assertEqual(guide.button_row("ZL", "click:right")["k"], "trigger")
        self.assertEqual(guide.button_row("L", "scroll:up")["k"], "bumper")
        dpad = guide.button_row("DPAD_UP", "key:UP")
        self.assertEqual((dpad["k"], dpad["b"]), ("dpad", "▲"))
        self.assertEqual(guide.button_row("LSTICK", "click:middle")["b"], "L3")

    def test_a_button_bound_to_nothing_gets_no_row(self):
        self.assertIsNone(guide.button_row("A", "nop"))
        self.assertIsNone(guide.button_row("A", None))


def build(data):
    return config_module.Config(data)


def shipped_config():
    """The config as shipped, with nothing of the developer's own in it.

    `config_module.load()` merges ~/.config/omapad over the defaults, so a
    suite that called it tested whichever machine it ran on - and failed the
    day someone's own config bound something these tests assert about.
    """
    missing = os.path.join(tempfile.gettempdir(), "omapad-no-such-config")
    return config_module.load(path=missing, mapping=missing,
                              settings=missing)


BASE = {
    "bindings": {
        "base": {"A": "key:ENTER", "B": "key:ESC", "L": "scroll:up"},
        "guide": {"L": "guide:prev", "R": "guide:next", "A": "guide:close",
                  "B": "guide:close"},
    },
    "layers": {"window": {"button": "ZL", "left_stick": "resize"}},
}


class PageTests(unittest.TestCase):
    def setUp(self):
        self.config = build({
            "bindings": dict(BASE["bindings"],
                             window={"A": "hypr:hl.dsp.window.close()"}),
            "layers": BASE["layers"],
        })

    def test_a_page_per_layer_in_the_order_you_meet_them(self):
        titles = [page["title"] for page in guide.build_pages(self.config)]
        self.assertEqual(titles[0], "Base")
        self.assertIn("Window layer", titles[1])

    def test_a_layer_with_no_bindings_gets_no_page(self):
        titles = [page["title"] for page in guide.build_pages(self.config)]
        self.assertNotIn("Keyboard", titles)
        self.assertNotIn("Menu", titles)
        # Game mode is empty until someone fills it in, and a page saying so
        # would be a page about nothing.
        self.assertNotIn("Game mode", titles)

    def test_a_filled_game_layer_earns_a_page_of_its_own(self):
        # The couch layer is an override on the desktop's map, so a page for
        # it is worth having only once it overrides something.
        config = build({
            "bindings": dict(BASE["bindings"], game={"ZR": "click:left"}),
            "layers": BASE["layers"],
        })
        page = [p for p in guide.build_pages(config)
                if p["title"] == "Game mode"][0]
        rows = [row for column in page["cols"]
                for group in column for row in group["rows"]]
        self.assertIn(("ZR", "Left click"),
                      [(row["b"], row["d"]) for row in rows])

    def test_rows_are_grouped_by_the_region_they_sit_in(self):
        page = guide.build_pages(self.config)[0]
        groups = [group for column in page["cols"] for group in column]
        self.assertEqual([group["t"] for group in groups],
                         ["Face buttons", "Shoulders", "Sticks"])

    def test_a_page_that_fits_is_cut_where_the_columns_come_out_even(self):
        page = guide.build_pages(shipped_config())[0]
        heights = [
            sum(len(group["rows"]) + 1 for group in column)
            for column in page["cols"]
        ]
        self.assertEqual(len(heights), 2)
        # Filling the first column to the brim next to a half-empty second one
        # is what this is not: a few rows apart is even enough.
        self.assertLessEqual(abs(heights[0] - heights[1]), 4)

    def test_the_layers_own_trigger_says_so_instead_of_looking_unbound(self):
        page = guide.build_pages(self.config)[1]
        rows = [row for column in page["cols"]
                for group in column for row in group["rows"]]
        self.assertIn(("ZL", "Hold for this layer"),
                      [(row["b"], row["d"]) for row in rows])

    def test_the_sticks_carry_their_role_rather_than_a_binding(self):
        page = guide.build_pages(self.config)[1]
        rows = [row for column in page["cols"]
                for group in column for row in group["rows"]]
        self.assertIn(("L", "Resize the window"),
                      [(row["b"], row["d"]) for row in rows])

    def test_a_button_the_pad_does_not_have_is_not_printed(self):
        # CAPTURE only exists on the nintendo_pro profile; printing it while an
        # XInput pad is connected would be a lie.
        config = build({"bindings": {"base": {"A": "key:ENTER",
                                              "CAPTURE": "key:F12"}}})
        rows = [
            row
            for page in guide.build_pages(config, available={"A", "B"})
            for column in page["cols"] for group in column
            for row in group["rows"] if group["t"] != "Sticks"
        ]
        self.assertEqual([row["b"] for row in rows], ["A"])

    def test_a_layer_taller_than_a_page_is_split_and_says_so(self):
        crowded = {"base": {}}
        for _, buttons in guide.REGIONS:
            for button in buttons:
                crowded["base"][button] = "key:ENTER"
        # A pad with more buttons than the regions know about - [device.buttons]
        # allows exactly that - is the case that cannot fit one page.
        for index in range(20):
            crowded["base"]["PADDLE%d" % index] = "key:ENTER"
        base = [page for page in guide.build_pages(build({"bindings": crowded}))
                if page["title"].startswith("Base")]
        # Every region bound at once is more than two columns hold.
        self.assertGreater(len(base), 1)
        self.assertEqual(base[0]["title"], "Base 1/%d" % len(base))

    def test_a_page_never_holds_more_than_two_columns(self):
        for page in guide.build_pages(self.config):
            self.assertLessEqual(len(page["cols"]), 2)
            for column in page["cols"]:
                rows = sum(len(group["rows"]) + 1 for group in column)
                self.assertLessEqual(rows, guide.COLUMN_ROWS)

    def test_the_shipped_config_builds_pages_that_fit(self):
        config = shipped_config()
        pages = guide.build_pages(config)
        self.assertTrue(pages)
        for page in pages:
            self.assertLessEqual(len(page["cols"]), 2)


class LayoutTests(unittest.TestCase):
    """What a badge prints is the pad's own printing, per console."""

    def test_the_same_button_is_printed_three_ways(self):
        self.assertEqual(guide.badge_of("B", "nintendo"), "B")
        self.assertEqual(guide.badge_of("B", "xbox"), "B")
        self.assertEqual(guide.badge_of("B", "playstation"), "○")
        self.assertEqual(guide.badge_of("ZL", "nintendo"), "ZL")
        self.assertEqual(guide.badge_of("ZL", "xbox"), "LT")
        self.assertEqual(guide.badge_of("ZL", "playstation"), "L2")
        self.assertEqual(guide.badge_of("PLUS", "nintendo"), "+")
        self.assertEqual(guide.badge_of("PLUS", "xbox"), "Menu")
        self.assertEqual(guide.badge_of("PLUS", "playstation"), "Options")

    def test_a_layout_nobody_has_heard_of_prints_the_names_it_knows(self):
        # Config refuses an unknown one, so this is only about not exploding
        # if one ever reaches here another way.
        self.assertEqual(guide.badge_of("A", "dreamcast"), "A")

    def test_the_pages_carry_the_layout_they_were_built_with(self):
        config = build(BASE)
        page = guide.build_pages(config, layout="playstation")[0]
        badges = [row["b"] for col in page["cols"] for group in col
                  for row in group["rows"]]
        self.assertIn("✕", badges)
        self.assertNotIn("A", badges)

    def test_and_every_row_of_every_page_does(self):
        """One row built through a path that forgot the layout is a page in
        two consoles' names, which is worse than being in the wrong one."""
        config = build({
            "bindings": {"base": dict((button, "key:ENTER") for button
                                      in guide.LAYOUTS["nintendo"])},
        })
        printed = set()
        for page in guide.build_pages(config, layout="playstation"):
            for col in page["cols"]:
                for group in col:
                    for row in group["rows"]:
                        printed.add(row["b"])
        allowed = set(guide.LAYOUTS["playstation"].values())
        # The sticks carry a role rather than a binding, and are badged by the
        # side they are on in every layout.
        allowed.update(("L", "R"))
        self.assertEqual(printed - allowed, set())

    def test_and_a_layer_is_named_by_the_button_that_holds_it(self):
        config = build(BASE)
        titles = dict((name, note) for name, _, note
                      in guide._layer_titles(config, "xbox"))
        self.assertIn("Hold LT", titles["window"])


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.model = guide.GuideModel(build({
            "bindings": dict(BASE["bindings"],
                             window={"A": "hypr:hl.dsp.window.close()"}),
            "layers": BASE["layers"],
        }))

    def test_it_opens_on_the_first_page(self):
        self.assertEqual(self.model.index, 0)
        self.assertEqual(self.model.title, "Base")

    def test_turning_the_page_wraps(self):
        self.model.move(-1)
        self.assertEqual(self.model.index, len(self.model.pages) - 1)
        self.model.move(1)
        self.assertEqual(self.model.index, 0)

    def test_rebuilding_for_a_pad_keeps_the_position_valid(self):
        self.model.move(-1)
        self.model.rebuild(available={"A", "B"})
        self.assertLess(self.model.index, max(1, len(self.model.pages)))

    def test_a_config_that_binds_nothing_still_has_a_base_page(self):
        # The sticks carry a role whether or not a button is bound, so Base is
        # never empty - and it is the only page a bare config gets.
        model = guide.GuideModel(build({}))
        model.move(1)
        state = model.view_state(True)
        self.assertEqual(state["count"], 1)
        self.assertEqual(state["title"], "Base")

    def test_the_payload_carries_what_the_plugin_draws(self):
        state = self.model.view_state(True)
        self.assertTrue(state["open"])
        self.assertEqual(state["title"], "Base")
        self.assertEqual(state["page"], 0)
        self.assertEqual(state["count"], len(self.model.pages))
        self.assertTrue(state["cols"])


class ActionTests(unittest.TestCase):
    def test_the_grammar_accepts_only_what_the_guide_can_do(self):
        self.assertIsInstance(actions.parse("guide:toggle"), actions.GuideAction)
        with self.assertRaises(actions.ActionError):
            actions.parse("guide:sideways")

    def test_a_table_that_only_annotates_still_fires_on_the_way_down(self):
        # `desc` next to an action must not turn a plain binding into a
        # tap/hold one, which would wait for the release before doing anything.
        binding = actions.Binding({"tap": "click:left", "desc": "Left click"})
        self.assertFalse(binding.is_tap_hold)
        self.assertTrue(binding.holdable)


if __name__ == "__main__":
    unittest.main(verbosity=2)
