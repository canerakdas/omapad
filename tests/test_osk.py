"""Layout, navigation and latch behaviour of the on-screen keyboard."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad import keymap
from omapad import xkb
from omapad.osk import (
    DEFAULT_BADGE_ALIGN, DEFAULT_LAYOUT, FN, LAYOUTS, MAIN, OskModel,
    badge_index, binding_target, row_centers,
)
from omapad.viewsock import ViewClient


def every_key():
    for layout_name, layers in LAYOUTS.items():
        for layer_name, rows in layers.items():
            for row in rows:
                for key in row:
                    yield layout_name, layer_name, key


class LayoutTests(unittest.TestCase):
    def test_rows_of_a_layer_share_one_width_budget(self):
        # Equal totals are what make the columns line up across rows.
        for layout_name, layers in LAYOUTS.items():
            for layer_name, rows in layers.items():
                totals = [round(sum(k["w"] for k in row), 6) for row in rows]
                with self.subTest(layout=layout_name, layer=layer_name):
                    self.assertEqual(len(set(totals)), 1, totals)

    def test_every_grid_page_spends_the_same_fourteen_units(self):
        # Widths differ key by key, the way a real keyboard's do; what has to
        # match is the budget, across pages as well as rows, because the three
        # pages share a bottom row.
        for name, rows in LAYOUTS["grid"].items():
            for index, row in enumerate(rows):
                with self.subTest(layer=name, row=index):
                    self.assertAlmostEqual(sum(k["w"] for k in row), 14.0)

    def test_the_wide_keys_are_the_ones_a_keyboard_makes_wide(self):
        widths = {}
        for row in LAYOUTS["grid"]["main"]:
            for key in row:
                widths.setdefault(key["label"], key["w"])
        for label in ("Tab", "Caps", "Shift", "Enter", "Space"):
            self.assertGreater(widths[label], 1.0, label)
        self.assertEqual(widths["q"], 1.0)

    def test_the_first_page_has_the_key_left_of_the_one(self):
        first_row = LAYOUTS["grid"]["main"][0]
        self.assertEqual(first_row[0]["action"], "GRAVE")
        self.assertEqual(first_row[1]["action"], "1")

    def test_the_first_page_carries_a_whole_keyboard(self):
        # Tab, Caps, Shift, Enter and Backspace are reached mid-word; a page
        # turn to get at them costs more than a narrower key.
        actions = {
            key["action"]
            for row in LAYOUTS["grid"]["main"]
            for key in row
        }
        for action in ("TAB", "CAPSLOCK", "mod:shift", "ENTER", "BACKSPACE"):
            self.assertIn(action, actions)

    def test_every_page_ends_with_the_same_bottom_row(self):
        # The keys you press without looking must not move when the page does.
        tails = [
            tuple(key["action"] for key in rows[-1][1:])
            for rows in LAYOUTS["grid"].values()
        ]
        self.assertEqual(len(set(tails)), 1, tails)

    def test_every_key_action_resolves(self):
        for layout_name, layer_name, key in every_key():
            action = key["action"]
            if action.startswith(("mod:", "layer:")) or action == "close":
                continue
            with self.subTest(layout=layout_name, key=key["label"]):
                keymap.parse_chord(action)

    def test_layer_switches_point_at_real_layers(self):
        for layout_name, _, key in every_key():
            if key["action"].startswith("layer:"):
                name = key["action"][6:]
                if name in ("next", "prev"):
                    continue  # a page turn, resolved against the model's order
                self.assertIn(name, LAYOUTS[layout_name])

    def test_every_page_turns_from_the_same_cell(self):
        # The cell names where it goes, and where that is depends on which
        # pages are up, so the layout can only say "turn the page".
        for rows in LAYOUTS["grid"].values():
            self.assertEqual(rows[-1][0]["action"], "layer:next")

    def test_every_layer_can_be_dismissed_from_its_bottom_right(self):
        for layout_name, layers in LAYOUTS.items():
            for layer_name, rows in layers.items():
                with self.subTest(layout=layout_name, layer=layer_name):
                    self.assertEqual(rows[-1][-1]["action"], "close")

    def test_default_layout_exists(self):
        self.assertIn(DEFAULT_LAYOUT, LAYOUTS)

    def test_row_centers_are_ordered_and_inside_the_row(self):
        centers = row_centers(MAIN[0])
        self.assertEqual(centers, sorted(centers))
        self.assertGreater(centers[0], 0.0)
        self.assertLess(centers[-1], 1.0)


class OverrideTests(unittest.TestCase):
    """A user's own labels and actions, from [osk.keys]."""

    def test_a_label_override_replaces_the_glyph_everywhere_it_appears(self):
        model = OskModel("grid", overrides={"BACKSPACE": {"label": "Erase"}})
        seen = [
            key["label"]
            for rows in model.layers.values()
            for row in rows
            for key in row
            if key["action"] == "BACKSPACE"
        ]
        self.assertTrue(seen)
        self.assertEqual(set(seen), {"Erase"})

    def test_an_override_does_not_leak_into_the_shipped_layout(self):
        OskModel("grid", overrides={"close": {"label": "X"}})
        plain = OskModel("grid")
        self.assertEqual(plain.rows[-1][-1]["label"], "▼")

    def test_an_action_override_changes_what_the_key_types(self):
        # The shipped one: Omarchy remaps Caps Lock to Compose, so caps lock is
        # reached by pressing both shifts together instead.
        model = OskModel(
            "grid", overrides={"CAPSLOCK": {"action": "LEFTSHIFT+RIGHTSHIFT"}}
        )
        for r, row in enumerate(model.rows):
            for c, key in enumerate(row):
                if key["label"] == "Caps":
                    model.row, model.col = r, c
        kind, mods, code = model.press()
        self.assertEqual(kind, "type")
        self.assertEqual(mods, [keymap.resolve("LEFTSHIFT")])
        self.assertEqual(code, keymap.resolve("RIGHTSHIFT"))

    def test_a_users_label_outranks_the_layout_lookup(self):
        table = xkb.compile_labels("us")
        if not table:
            self.skipTest("xkbcli unavailable")
        model = OskModel("grid", overrides={"1": {"label": "one"}})
        model.set_labels(table)
        key = model.rows[0][1]
        self.assertEqual(model.label_for(key), "one")

    def test_an_action_that_does_not_parse_is_refused(self):
        from omapad.osk import OverrideError

        with self.assertRaises(OverrideError):
            OskModel("grid", overrides={"CAPSLOCK": {"action": "NOSUCHKEY"}})


class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.model = OskModel()

    def select(self, label):
        for r, row in enumerate(self.model.rows):
            for c, key in enumerate(row):
                if key["label"] == label:
                    self.model.row, self.model.col = r, c
                    return
        raise AssertionError("no key labelled %r" % label)

    def test_horizontal_movement_wraps(self):
        self.model.row, self.model.col = 0, 0
        self.model.move_horizontal(-1)
        self.assertEqual(self.model.col, len(self.model.rows[0]) - 1)
        self.model.move_horizontal(1)
        self.assertEqual(self.model.col, 0)

    def test_vertical_movement_keeps_the_column_position(self):
        # 'g' sits under 't' on a real keyboard; the selection should too.
        self.select("g")
        self.model.move_vertical(-1)
        self.assertEqual(self.model.current_key["label"], "t")
        self.model.move_vertical(1)
        self.assertEqual(self.model.current_key["label"], "g")

    def test_vertical_movement_wraps_through_the_layout(self):
        self.model.row = len(self.model.rows) - 1
        self.model.col = 0
        self.model.move_vertical(1)
        self.assertEqual(self.model.row, 0)

    def test_switching_to_a_shorter_layer_clamps_the_selection(self):
        self.model.row, self.model.col = 4, 7
        self.model.set_layer("fn")
        self.assertLess(self.model.row, len(FN))
        self.assertLess(self.model.col, len(FN[self.model.row]))

    def test_layer_cycling_walks_every_layer_and_returns(self):
        order = list(self.model.layers)
        seen = [self.model.layer]
        for _ in range(len(order) - 1):
            self.model.cycle_layer(1)
            seen.append(self.model.layer)
        self.assertEqual(sorted(seen), sorted(order))
        self.model.cycle_layer(1)
        self.assertEqual(self.model.layer, seen[0])


class PressTests(unittest.TestCase):
    def setUp(self):
        self.model = OskModel()

    def select(self, label):
        for r, row in enumerate(self.model.rows):
            for c, key in enumerate(row):
                if key["label"] == label:
                    self.model.row, self.model.col = r, c
                    return
        raise AssertionError("no key labelled %r" % label)

    def select_action(self, action):
        for r, row in enumerate(self.model.rows):
            for c, key in enumerate(row):
                if key["action"] == action:
                    self.model.row, self.model.col = r, c
                    return
        raise AssertionError("no key doing %r" % action)

    def test_plain_key_types_itself(self):
        self.select("a")
        self.assertEqual(self.model.press(), ("type", [], keymap.resolve("A")))

    def test_shift_latches_then_releases_after_one_key(self):
        self.select("Shift")
        self.assertEqual(self.model.press(), ("mod", "shift"))
        self.assertTrue(self.model.mods["shift"])

        self.select("a")
        kind, mods, code = self.model.press()
        self.assertEqual(kind, "type")
        self.assertEqual(mods, [keymap.resolve("LEFTSHIFT")])
        self.assertEqual(code, keymap.resolve("A"))
        self.assertFalse(self.model.mods["shift"], "latch should be one-shot")

    def test_modifiers_combine(self):
        self.select("Ctrl")
        self.model.press()
        self.select("Shift")
        self.model.press()
        self.select("c")
        kind, mods, _ = self.model.press()
        self.assertEqual(kind, "type")
        self.assertEqual(
            sorted(mods),
            sorted([keymap.resolve("LEFTCTRL"), keymap.resolve("LEFTSHIFT")]),
        )

    def test_layer_key_switches_layer(self):
        self.select_action("layer:next")
        self.assertEqual(self.model.press(), ("layer", "sym"))
        self.assertEqual(self.model.layer, "sym")

    def test_shift_swaps_a_key_that_carries_an_alternative(self):
        # Four arrows in two cells: shifted, left/right are up/down, and the
        # shift is spent on the swap rather than sent along with the key.
        self.select("←")
        self.assertEqual(self.model.press(), ("type", [], keymap.resolve("LEFT")))
        self.model.latch("shift")
        self.select("←")
        self.assertEqual(self.model.press(), ("type", [], keymap.resolve("UP")))

    def test_an_alternative_keeps_the_other_latched_modifiers(self):
        self.select("Ctrl")
        self.model.press()
        self.model.latch("shift")
        self.select("→")
        kind, mods, code = self.model.press()
        self.assertEqual(kind, "type")
        self.assertEqual(mods, [keymap.resolve("LEFTCTRL")])
        self.assertEqual(code, keymap.resolve("DOWN"))

    def test_close_key_reports_close(self):
        self.model.set_layer("fn")
        for r, row in enumerate(self.model.rows):
            for c, key in enumerate(row):
                if key["action"] == "close":
                    self.model.row, self.model.col = r, c
        self.assertEqual(self.model.press(), ("close", None))


class SymbolLayerTests(unittest.TestCase):
    def test_symbol_key_carries_its_own_shift(self):
        model = OskModel("grid")
        model.set_layer("sym")
        model.row, model.col = 0, 0          # '!' == shift+1
        kind, mods, code = model.press()
        self.assertEqual(kind, "type")
        self.assertEqual(mods, [keymap.resolve("LEFTSHIFT")])
        self.assertEqual(code, keymap.resolve("1"))

    def test_a_latch_does_not_duplicate_the_keys_own_shift(self):
        model = OskModel("grid")
        model.set_layer("sym")
        model.row, model.col = 0, 0
        model.latch("shift")
        _, mods, _ = model.press()
        self.assertEqual(mods.count(keymap.resolve("LEFTSHIFT")), 1)


class LabelTests(unittest.TestCase):
    """Labels must say what the key will actually type."""

    def test_without_a_layout_table_the_built_in_labels_are_used(self):
        model = OskModel("grid")
        model.row, model.col = 1, 1
        self.assertEqual(model.label_for(model.current_key), "q")

    def test_labels_follow_a_non_us_layout(self):
        table = xkb.compile_labels("tr")
        if not table:
            self.skipTest("xkbcli could not compile the tr layout")
        model = OskModel("grid")
        model.set_labels(table)
        # On a Turkish layout this keycode types 'ş', not ';'.
        for row in model.rows:
            for key in row:
                if key["action"] == "SEMICOLON":
                    self.assertEqual(model.label_for(key), "ş")
                    return
        self.fail("no semicolon key in the symbol layer")

    def test_special_keys_keep_their_own_glyphs(self):
        table = xkb.compile_labels("us")
        if not table:
            self.skipTest("xkbcli unavailable")
        model = OskModel("grid")
        model.set_labels(table)
        # Space resolves to a blank in the layout table; it must stay drawn.
        for row in model.rows:
            for key in row:
                if key["action"] == "SPACE":
                    self.assertEqual(model.label_for(key), "Space")
                    return
        self.fail("no space key")


class ViewStateTests(unittest.TestCase):
    def test_payload_carries_what_the_view_needs(self):
        model = OskModel()
        state = model.view_state(True)
        self.assertTrue(state["open"])
        self.assertEqual(state["sel"], [model.row, model.col])
        self.assertEqual(len(state["rows"]), len(model.rows))
        first = state["rows"][0][0]
        self.assertIn("l", first)
        self.assertIn("w", first)
        self.assertIn("s", first)

    def test_shift_swaps_the_printed_labels(self):
        model = OskModel("grid")
        plain = model.view_state(True)["rows"][1][1]["l"]
        model.mods["shift"] = True
        shifted = model.view_state(True)["rows"][1][1]["l"]
        self.assertEqual(plain, "q")
        self.assertEqual(shifted, "Q")

    def test_a_key_prints_what_shift_would_make_of_it(self):
        # The corner glyph, the way a console keyboard shows it.
        model = OskModel("grid")
        digit = model.view_state(True)["rows"][0][1]     # the backtick is [0]
        self.assertEqual(digit["l"], "1")
        self.assertEqual(digit["x"], "!")
        model.mods["shift"] = True
        digit = model.view_state(True)["rows"][0][1]
        self.assertEqual(digit["l"], "!")
        self.assertEqual(digit["x"], "1")

    def test_a_letter_prints_no_corner_hint(self):
        # 'Q' over every 'q' is twenty-six hints for what every keyboard
        # already teaches, and it drowns out the ones worth reading.
        model = OskModel("grid")
        letter = model.view_state(True)["rows"][1][1]
        self.assertEqual(letter["l"], "q")
        self.assertEqual(letter["x"], "")
        model.mods["shift"] = True
        letter = model.view_state(True)["rows"][1][1]
        self.assertEqual(letter["l"], "Q")
        self.assertEqual(letter["x"], "")

    def test_a_key_shift_does_not_change_prints_nothing_in_the_corner(self):
        model = OskModel("grid")
        space = [
            key
            for row in model.view_state(True)["rows"]
            for key in row
            if key["l"] == "Space"
        ]
        self.assertEqual([key["x"] for key in space], [""])

    def test_modifier_keys_are_tagged_for_the_view(self):
        model = OskModel("grid")
        tags = {
            key["m"]
            for row in model.view_state(True)["rows"]
            for key in row
            if key["m"]
        }
        self.assertEqual(tags, {"shift", "ctrl", "alt", "caps"})


class BadgeTests(unittest.TestCase):
    """The pad button printed on the key it reaches."""

    # The shipped keyboard layer, near enough: what a key badge has to survive.
    BINDINGS = {
        "A": "osk:press",
        "B": "osk:close",
        "X": "key:BACKSPACE",
        "Y": "key:SPACE",
        "R": "osk:layer:next",
        "ZL": "osk:hold:shift",
        "ZR": "osk:submit",
        "PLUS": "key:ENTER",
        "LSTICK": "osk:caps",
        "HOME": {"tap": "osk:close", "hold": "mode:toggle"},
    }

    def badged(self, model):
        """{printed label: badge} for every key that carries one."""
        return dict(
            (key["l"], key["b"])
            for row in model.view_state(True)["rows"]
            for key in row
            if "b" in key
        )

    def model(self, bindings=None, available=None, overrides=None):
        model = OskModel("grid", overrides=overrides)
        index = badge_index(
            self.BINDINGS if bindings is None else bindings, available
        )
        model.set_badges(dict(
            (identity, {"b": button, "k": "face"})
            for identity, button in index.items()
        ))
        return model

    def test_a_chord_lands_on_the_key_that_types_it(self):
        badges = self.badged(self.model())
        self.assertEqual(badges["Bksp"], "X")
        self.assertEqual(badges["Space"], "Y")

    def test_the_keys_that_drive_the_keyboard_are_matched_by_identity(self):
        badges = self.badged(self.model())
        self.assertEqual(badges["Shift"], "ZL")
        self.assertEqual(badges["Caps"], "LSTICK")
        self.assertEqual(badges["▼"], "B")
        # The page-turn cell prints where it goes, not "next".
        self.assertEqual(badges["&123"], "R")

    def test_a_button_that_reaches_no_single_key_is_not_printed(self):
        # Pressing the selection is whatever is under it; there is nothing to
        # put it beside.
        self.assertNotIn("A", self.badged(self.model()).values())

    def test_the_button_that_finishes_a_line_is_printed_on_enter(self):
        # osk:submit sends Enter and then puts the keyboard away. Enter is the
        # half of that you can point at, and the trigger is the button the line
        # actually gets finished with - so it outranks the quieter one that
        # only types the same key.
        badges = self.badged(self.model())
        self.assertEqual(badges["Enter"], "ZR")
        self.assertNotIn("PLUS", badges.values())

    def test_the_caps_key_keeps_its_badge_when_it_is_pointed_elsewhere(self):
        # As it ships: Omarchy's layout turns Caps Lock into Compose, so the
        # key sends both shifts instead - and is still what osk:caps reaches.
        model = self.model(
            overrides={"CAPSLOCK": {"action": "LEFTSHIFT+RIGHTSHIFT"}}
        )
        self.assertEqual(self.badged(model)["Caps"], "LSTICK")

    def test_a_button_the_pad_does_not_have_prints_nothing(self):
        model = self.model(available={"A", "B", "X"})
        self.assertNotIn("Y", self.badged(model).values())
        self.assertEqual(self.badged(model)["Bksp"], "X")

    def test_the_first_binding_to_reach_a_key_keeps_it(self):
        # Four buttons close the keyboard and the key can only print one.
        self.assertEqual(self.badged(self.model())["▼"], "B")

    def test_a_rebound_scheme_badges_itself(self):
        badges = self.badged(self.model({"Y": "key:BACKSPACE"}))
        self.assertEqual(badges["Bksp"], "Y")

    def test_a_binding_that_is_not_the_keyboard_s_reaches_nothing(self):
        self.assertIsNone(binding_target("click:left"))
        self.assertIsNone(binding_target("menu:toggle"))
        self.assertIsNone(binding_target(None))
        # An unparseable chord is `omapad check`'s to complain about.
        self.assertIsNone(binding_target("key:NOSUCHKEY"))

    def test_a_key_no_button_reaches_carries_no_badge_field(self):
        model = self.model()
        letter = model.view_state(True)["rows"][1][1]
        self.assertEqual(letter["l"], "q")
        self.assertNotIn("b", letter)

    def test_where_the_badge_sits_is_forwarded_to_the_plugin(self):
        # The placing is the plugin's - only the side that drew the key knows
        # how wide it came out - so the model just carries the choice.
        self.assertEqual(OskModel("grid").view_state(True)["balign"], "right")
        model = OskModel("grid", badge_align="label")
        self.assertEqual(model.view_state(True)["balign"], "label")

    def test_an_alignment_nobody_draws_falls_back(self):
        # config rejects it; a model handed one anyway still draws something.
        model = OskModel("grid", badge_align="sideways")
        self.assertEqual(model.badge_align, DEFAULT_BADGE_ALIGN)


class CapsLockTests(unittest.TestCase):
    """Caps Lock is a state, not a modifier omapad sends."""

    def caps_key(self, model):
        for r, row in enumerate(model.rows):
            for c, key in enumerate(row):
                if key["id"] == "CAPSLOCK":
                    model.row, model.col = r, c
                    return
        raise AssertionError("no caps key")

    def test_pressing_caps_flips_the_state_and_the_letters(self):
        model = OskModel("grid")
        self.assertEqual(model.label_for(model.rows[1][1]), "q")
        self.caps_key(model)
        model.press()
        self.assertTrue(model.caps)
        self.assertEqual(model.label_for(model.rows[1][1]), "Q")
        self.caps_key(model)
        model.press()
        self.assertFalse(model.caps)
        self.assertEqual(model.label_for(model.rows[1][1]), "q")

    def test_shift_over_caps_goes_back_down(self):
        model = OskModel("grid")
        model.caps = True
        model.mods["shift"] = True
        self.assertEqual(model.label_for(model.rows[1][1]), "q")

    def test_caps_leaves_everything_that_is_not_a_letter_alone(self):
        model = OskModel("grid")
        digit = model.rows[0][1]
        self.assertEqual(model.label_for(digit), "1")
        model.caps = True
        self.assertEqual(model.label_for(digit), "1")

    def test_caps_follows_the_layout_it_is_printing(self):
        table = xkb.compile_labels("tr")
        if not table:
            self.skipTest("xkbcli could not compile the tr layout")
        model = OskModel("grid")
        model.set_labels(table)
        model.caps = True
        # On a Turkish layout this key types 'ı'/'I'.
        for row in model.rows:
            for key in row:
                if key["chord"] and key["chord"][1] == keymap.resolve("I"):
                    self.assertEqual(model.label_for(key), "I")
                    return
        self.fail("no I key")

    def test_caps_outlives_the_keyboard_closing(self):
        # It is the compositor's state, not a latch: closing a panel does not
        # turn a real Caps Lock off either.
        model = OskModel("grid")
        model.caps = True
        model.reset_mods()
        self.assertTrue(model.caps)

    def test_the_toggle_reports_the_chord_the_key_would_send(self):
        model = OskModel(
            "grid", overrides={"CAPSLOCK": {"action": "LEFTSHIFT+RIGHTSHIFT"}}
        )
        self.assertEqual(
            model.toggle_caps(),
            ([keymap.resolve("LEFTSHIFT")], keymap.resolve("RIGHTSHIFT")),
        )
        self.assertTrue(model.caps)


class AppPageTests(unittest.TestCase):
    """The page an app profile lends the keyboard while its window is up."""

    def setUp(self):
        self.model = OskModel()
        self.entries = [
            {"label": "git status", "text": "git status"},
            {"label": "ls", "text": "ls"},
        ]

    def page(self):
        for row in self.model.rows:
            for key in row:
                if key["action"].startswith("text:"):
                    return key
        self.fail("no entry on the page")

    def test_the_page_joins_the_cycle_last_and_leaves_again(self):
        base = list(self.model.order)
        self.model.set_app_page("Term", self.entries)
        self.assertEqual(self.model.order, base + ["app"])
        self.model.clear_app_page()
        self.assertEqual(self.model.order, base)

    def test_no_entries_means_no_page(self):
        # A command that printed nothing is not worth a page turn.
        self.model.set_app_page("Term", [])
        self.assertNotIn("app", self.model.order)

    def test_the_page_turn_cell_names_where_it_goes(self):
        self.model.set_app_page("Term", self.entries)
        self.model.set_layer("fn")
        self.assertEqual(self.model.view_state(True)["rows"][-1][0]["l"], "Term")
        self.model.set_layer("app")
        self.assertEqual(self.model.view_state(True)["rows"][-1][0]["l"], "abc")

    def test_the_page_spends_the_same_width_as_every_other(self):
        # Its rows have to line up with the pages either side of it.
        self.model.set_app_page("Term", self.entries)
        self.model.set_layer("app")
        budget = sum(key["w"] for key in LAYOUTS["grid"]["fn"][-1])
        for index, row in enumerate(self.model.rows):
            with self.subTest(row=index):
                self.assertAlmostEqual(sum(key["w"] for key in row), budget)

    def test_a_long_entry_takes_the_row_alone(self):
        self.model.set_app_page("Term", [
            {"label": "x" * 40, "text": "x" * 40},
            {"label": "ls", "text": "ls"},
            {"label": "cd", "text": "cd"},
        ])
        self.model.set_layer("app")
        self.assertEqual(len(self.model.rows[0]), 1)
        self.assertEqual(len(self.model.rows[1]), 2)

    def test_the_page_keeps_the_keyboard_its_height(self):
        entries = [{"label": str(n), "text": str(n)} for n in range(40)]
        self.model.set_app_page("Term", entries)
        self.model.set_layer("app")
        self.assertLessEqual(len(self.model.rows), len(LAYOUTS["grid"]["main"]))

    def test_the_page_can_be_dismissed_from_its_bottom_right(self):
        self.model.set_app_page("Term", self.entries)
        self.model.set_layer("app")
        self.assertEqual(self.model.rows[-1][-1]["action"], "close")

    def test_losing_the_page_underneath_the_selection_falls_back(self):
        self.model.set_app_page("Term", self.entries)
        self.model.set_layer("app")
        self.model.clear_app_page()
        self.assertEqual(self.model.layer, "main")
        self.model.current_key  # the selection still points at something

    def test_an_entry_asks_for_its_whole_string(self):
        self.model.set_app_page("Term", self.entries)
        self.model.set_layer("app")
        self.model.row, self.model.col = 0, 0
        self.assertEqual(self.model.press(), ("text", "git status"))

    def test_an_entry_can_send_a_chord_instead_of_a_string(self):
        # What a key that is wrong in exactly one app needs: a terminal pastes
        # with Ctrl+Shift+V, where the bottom row's Paste sends Ctrl+V.
        self.model.set_app_page("Term", [
            {"label": "Paste", "action": "CTRL+SHIFT+V"},
        ])
        self.model.set_layer("app")
        self.model.row, self.model.col = 0, 0
        self.assertEqual(
            self.model.press(),
            ("type",
             [keymap.resolve("LEFTCTRL"), keymap.resolve("LEFTSHIFT")],
             keymap.resolve("V")),
        )

    def test_an_entry_drops_a_latch_rather_than_applying_it(self):
        # Ctrl over a whole command is not something anybody asked for, and
        # leaving it latched would apply it to the next key instead.
        self.model.set_app_page("Term", self.entries)
        self.model.set_layer("app")
        self.model.row, self.model.col = 0, 0
        self.model.latch("ctrl")
        self.model.press()
        self.assertFalse(self.model.mods["ctrl"])


class TextTests(unittest.TestCase):
    """Turning a string into the chords that type it."""

    def setUp(self):
        self.model = OskModel()

    def typed(self, text):
        return self.model.text_chords(text)

    def test_a_string_types_as_its_characters(self):
        self.assertEqual(
            self.typed("ls "),
            [
                ([], keymap.resolve("L")),
                ([], keymap.resolve("S")),
                ([], keymap.resolve("SPACE")),
            ],
        )

    def test_a_capital_carries_shift(self):
        self.assertEqual(
            self.typed("A"), [([keymap.resolve("LEFTSHIFT")], keymap.resolve("A"))]
        )

    def test_a_symbol_carries_the_shift_its_key_needs(self):
        self.assertEqual(
            self.typed("!"), [([keymap.resolve("LEFTSHIFT")], keymap.resolve("1"))]
        )

    def test_caps_flips_the_shift_a_letter_needs(self):
        # The compositor is applying caps to every letter already, so the shift
        # this table asked for is the one that must not be sent.
        self.model.caps = True
        self.assertEqual(self.typed("a"),
                         [([keymap.resolve("LEFTSHIFT")], keymap.resolve("A"))])
        self.assertEqual(self.typed("A"), [([], keymap.resolve("A"))])
        self.assertEqual(self.typed("1"), [([], keymap.resolve("1"))])

    def test_a_character_the_layout_cannot_make_is_dropped(self):
        # Half a command in the prompt is easier to see and fix than a command
        # with the wrong character in the middle of it.
        self.assertEqual(self.typed("a\tb"), self.typed("ab"))

    def test_the_characters_follow_the_compositor_layout(self):
        table = xkb.compile_labels("tr")
        if not table:
            self.skipTest("xkbcli could not compile the tr layout")
        self.model.set_labels(table)
        chords = self.typed("ş")
        self.assertEqual(len(chords), 1)
        # On a Turkish layout 'ş' is where a US layout keeps the semicolon.
        self.assertEqual(chords[0], ([], keymap.resolve("SEMICOLON")))


class ClientTests(unittest.TestCase):
    def test_send_without_a_listening_socket_fails_quietly(self):
        client = ViewClient("osk.sock", "/nonexistent/omapad-test.sock")
        self.assertFalse(client.send({"open": True}))
        client.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
