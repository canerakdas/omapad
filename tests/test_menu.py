"""The controller menu's tree, its navigation, and the payload it draws from."""

import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad import actions, config as config_module
from omapad.menu import (MenuError, MenuModel, ROOT_TITLE, arrange, build,
                         build_head, effective_span, head_sources, listed,
                         place, slug)

SAMPLE = [
    {"label": "Terminal", "icon": "T", "action": "exec:true"},
    {
        "label": "Audio",
        "items": [
            {"label": "Volume up", "action": "exec:true"},
            {"label": "Mute", "action": "exec:true"},
        ],
    },
    {"label": "Game mode", "detail": "hands the pad back", "action": "mode:game"},
    {"label": "Volume up", "repeat": True, "action": "exec:true"},
    {"label": "Xbox labels", "stay": True, "action": "pad:layout=xbox"},
]


# The shape the bar expects: a top level of places, each holding tiles. A
# top-level verb still works - it is a page of one - but the shipped tree has
# none, and neither does this.
GROUPED = [
    {"label": "Apps", "icon": "A", "items": [
        {"label": "Terminal", "icon": "T", "action": "exec:true"},
        {"label": "Browser", "action": "exec:true"},
    ]},
    {"label": "Audio", "items": [
        {"label": "Volume up", "repeat": True, "action": "exec:true"},
        {"label": "Game mode", "detail": "hands the pad back",
         "action": "mode:game"},
        {"label": "Devices", "items": [
            {"label": "Speakers", "action": "exec:true"},
            {"label": "Microphone", "action": "exec:true"},
        ]},
        {"label": "Xbox labels", "stay": True, "action": "pad:layout=xbox"},
    ]},
]


LISTED = {
    "label": "Output",
    "icon": "S",
    "detail": "Speakers, headphones, the TV",
    "empty": "No outputs found",
    "action": "exec:set-output %1 %2",
    "from": "list-outputs",
}


class BuildTests(unittest.TestCase):
    def test_actions_are_resolved_at_build_time(self):
        # A typo has to fail `omapad check`, not the moment it is picked.
        items = build(SAMPLE)
        self.assertIsInstance(items[0]["action"], actions.ExecAction)
        self.assertIsInstance(items[2]["action"], actions.ModeAction)

    def test_a_row_is_picked_once_unless_it_says_otherwise(self):
        items = build(SAMPLE)
        self.assertFalse(items[0]["repeat"])
        self.assertTrue(items[3]["repeat"])

    def test_a_row_that_stays_open_says_so(self):
        items = build(SAMPLE)
        self.assertFalse(items[0]["stay"])
        self.assertTrue(items[4]["stay"])
        # A row you nudge already stays: it is the same argument, one press
        # further on.
        self.assertTrue(items[3]["stay"])

    def test_a_submenu_cannot_stay_open(self):
        with self.assertRaises(MenuError):
            build([{"label": "Audio", "stay": True, "items": SAMPLE}])

    def test_a_submenu_cannot_repeat(self):
        with self.assertRaises(MenuError):
            build([{"label": "Audio", "repeat": True, "items": SAMPLE}])

    def test_a_submenu_carries_items_instead_of_an_action(self):
        items = build(SAMPLE)
        self.assertIsNone(items[1]["action"])
        self.assertEqual(len(items[1]["items"]), 2)

    def test_a_row_needs_a_label(self):
        with self.assertRaises(MenuError):
            build([{"action": "exec:true"}])

    def test_a_row_needs_something_to_do(self):
        with self.assertRaises(MenuError):
            build([{"label": "Nothing"}])

    def test_a_row_cannot_both_run_and_open(self):
        with self.assertRaises(MenuError):
            build([{"label": "Both", "action": "exec:true", "items": SAMPLE}])

    def test_an_empty_submenu_is_a_dead_end(self):
        with self.assertRaises(MenuError):
            build([{"label": "Empty", "items": []}])

    def test_a_bad_action_names_the_row(self):
        with self.assertRaises(MenuError) as caught:
            build([{"label": "Bad", "action": "nonsense:x"}])
        self.assertIn("menu.items[0]", str(caught.exception))

    def test_a_listed_row_holds_its_command_and_reads_as_a_submenu(self):
        # It drills in before anything has been read: what is plugged in is
        # not known until the row is entered.
        item = build([LISTED])[0]
        self.assertEqual(item["from"], "list-outputs")
        self.assertEqual(item["template"], "exec:set-output %1 %2")
        self.assertEqual(item["items"], [])
        self.assertIsNone(item["action"])

    def test_a_listed_row_needs_something_for_its_lines_to_run(self):
        with self.assertRaises(MenuError):
            build([{"label": "Output", "from": "list-outputs"}])

    def test_a_listed_row_cannot_also_hold_its_rows(self):
        with self.assertRaises(MenuError):
            build([dict(LISTED, items=[{"label": "One", "action": "exec:true"}])])

    def test_a_listed_row_is_still_a_submenu_and_cannot_repeat(self):
        with self.assertRaises(MenuError):
            build([dict(LISTED, repeat=True)])

    def test_a_bad_template_names_the_row(self):
        with self.assertRaises(MenuError) as caught:
            build([dict(LISTED, action="nonsense:%1")])
        self.assertIn("menu.items[0]", str(caught.exception))

    def test_a_row_says_what_an_empty_listing_looks_like(self):
        self.assertEqual(build([LISTED])[0]["empty"], "No outputs found")
        self.assertTrue(build([dict(LISTED, empty=None)])[0]["empty"])

    def test_the_shipped_menu_builds(self):
        missing = os.path.join(tempfile.gettempdir(),
                               "omapad-no-such-config")
        config = config_module.load(path=missing, mapping=missing,
                                    settings=missing, layout=missing)
        self.assertTrue(build(config.menu_items))

    def test_apps_leads_with_what_a_sofa_reaches_for(self):
        # The couch's short list, in the order it is reached for: the game,
        # the people you are playing with, the music, the television. What
        # comes after them is the desktop's own list, and last of all
        # everything installed - which no controller menu should try to be.
        missing = os.path.join(tempfile.gettempdir(),
                               "omapad-no-such-config")
        config = config_module.load(path=missing, mapping=missing,
                                    settings=missing, layout=missing)
        apps = [row for row in config.menu_items if row.get("label") == "Apps"]
        self.assertEqual(len(apps), 1)
        labels = [row["label"] for row in apps[0]["items"]]
        self.assertEqual(
            labels[:4], ["Steam", "Discord", "Spotify", "YouTube"]
        )
        self.assertEqual(labels[-1], "All apps")


    def test_the_mode_at_the_next_start_sits_where_the_restart_does(self):
        # It is not a Controller row: it decides nothing about the pad, and
        # the rows beside it are the ones that make it true.
        missing = os.path.join(tempfile.gettempdir(),
                               "omapad-no-such-config")
        config = config_module.load(path=missing, mapping=missing,
                                    settings=missing, layout=missing)
        system = [row for row in config.menu_items
                  if row.get("label") == "System"]
        self.assertEqual(len(system), 1)
        rows = system[0]["items"]
        self.assertEqual(rows[0]["label"], "Start in")
        # A card of rows rather than a chevron: both values are on screen,
        # each with the line saying how it differs, and the tick says which
        # one the next start is waiting on. A choice showed one value, so
        # that line had nowhere to go - and it is the line that makes this
        # card worth reading rather than pressing.
        self.assertEqual(rows[0]["control"], "rows")
        self.assertEqual(
            [(row["label"], row["action"]) for row in rows[0]["items"]],
            [("Game mode", "pad:start_mode=game"),
             ("Desktop", "pad:start_mode=desktop")],
        )
        self.assertTrue(all(row["detail"] for row in rows[0]["items"]))
        # And it builds, which is what says the rows are verbs the parser
        # accepts inside a card rather than only TOML that looks right.
        built = build(config.menu_items)
        card = [item for item in built
                if item["label"] == "System"][0]["items"][0]
        self.assertEqual(len(card["rows"]), 2)
        self.assertIsNone(card["items"])

    def test_the_pointer_row_sits_with_the_pointer_s_other_questions(self):
        # Under Controller, directly under the tile that opens the sticks:
        # both are asked while holding the pad and looking at the pointer,
        # and they are the column standing beside that page's three cards.
        missing = os.path.join(tempfile.gettempdir(),
                               "omapad-no-such-config")
        config = config_module.load(path=missing, mapping=missing,
                                    settings=missing, layout=missing)
        controller = [row for row in config.menu_items
                      if row.get("label") == "Controller"]
        self.assertEqual(len(controller), 1)
        rows = controller[0]["items"]
        labels = [row.get("label") for row in rows]
        self.assertEqual(labels[labels.index("Sticks"):],
                         ["Sticks", "Hide the pointer", "Button style"])
        pointer = rows[labels.index("Hide the pointer")]
        # A switch rather than two rows that both ticked: it has two states,
        # and the tile draws which one it is in.
        self.assertEqual(pointer["control"], "toggle")
        self.assertEqual(pointer["reads"], "pad:hide_pointer")
        # And the four numbers behind the sticks are bars, on one page: two
        # pages of four stepping rows was the shape eight rows forced.
        sticks = [row for row in rows[labels.index("Sticks")]["items"]
                  if row["control"] != "row_break"]
        bars = [row for row in sticks if row["control"] == "slider"]
        self.assertEqual([row["reads"] for row in bars],
                         ["pad:pointer_speed", "pad:scroll_speed",
                          "pad:left_deadzone", "pad:right_deadzone"])
        # ...and the dead zones say it twice: a bar sets the number, a dial
        # shows what it did to the stick you are holding.
        dials = [row for row in sticks if row["control"] == "gauge"]
        self.assertEqual([row["shows"] for row in dials], ["left", "right"])
        self.assertEqual([row["reads"] for row in dials],
                         ["pad:left_deadzone", "pad:right_deadzone"])


class WhenTests(unittest.TestCase):
    """`when`: the states a row is offered in."""

    TREE = [
        {"label": "Terminal", "action": "exec:true"},
        {"label": "Workspace lock", "action": "lock:toggle",
         "when": ["game", "handed_over"]},
        {"label": "Only locked", "action": "lock:off", "when": "locked"},
    ]

    def labels(self, *states):
        # The top level is the bar, so what a state decides here is which
        # chips there are.
        model = MenuModel(build(self.TREE))
        model.conditions = frozenset(states)
        model.reset()
        return [item["label"] for item in model.groups]

    def test_a_row_that_asks_for_nothing_is_always_there(self):
        self.assertEqual(self.labels(), ["Terminal"])

    def test_any_one_of_the_states_it_names_is_enough(self):
        self.assertEqual(self.labels("game"), ["Terminal", "Workspace lock"])
        self.assertEqual(self.labels("handed_over"),
                         ["Terminal", "Workspace lock"])

    def test_a_bare_string_is_one_state(self):
        self.assertEqual(self.labels("locked"), ["Terminal", "Only locked"])

    def test_a_group_whose_every_tile_is_unmet_draws_no_chip(self):
        # A chip that opens an empty page says the menu has somewhere to go
        # and then does not.
        tree = build([
            {"label": "Always", "action": "exec:true"},
            {"label": "Game things", "items": [
                {"label": "Lock", "action": "lock:toggle", "when": "game"},
            ]},
        ])
        model = MenuModel(tree)
        self.assertEqual([g["label"] for g in model.groups], ["Always"])
        model.conditions = frozenset(["game"])
        model.reset()
        self.assertEqual([g["label"] for g in model.groups],
                         ["Always", "Game things"])

    def test_a_state_nobody_has_is_named_at_build_time(self):
        # Otherwise it is a row that never appears and nothing says why.
        with self.assertRaises(MenuError) as caught:
            build([{"label": "X", "action": "exec:true", "when": "sofa"}])
        self.assertIn("sofa", str(caught.exception))

    def test_a_level_nobody_asks_about_keeps_its_list(self):
        # A listed submenu is filled in place after the page is entered, so a
        # level that filters nothing must hand back the list itself.
        model = MenuModel(build(self.TREE))
        inner = build([{"label": "One", "action": "exec:true"}])
        self.assertIs(model.visible(inner), inner)


class ListedTests(unittest.TestCase):
    """The rows a listing command prints, and what they run."""

    def setUp(self):
        self.item = build([LISTED])[0]

    def rows(self, lines, limit=8):
        return listed(self.item, lines, limit)

    def test_a_line_becomes_a_row_that_runs_the_template(self):
        row = self.rows(["Television\t7\thdmi-out"])[0]
        self.assertEqual(row["label"], "Television")
        self.assertEqual(row["action"].command, "set-output 7 hdmi-out")

    def test_the_mark_pactl_prints_is_the_tick_and_is_not_drawn(self):
        rows = self.rows(["* Speakers\t1\tanalog", "Television\t7\thdmi-out"])
        self.assertEqual([row["label"] for row in rows], ["Speakers", "Television"])
        self.assertEqual([row["on"] for row in rows], [True, False])

    def test_a_value_cannot_become_a_second_command(self):
        # A device names itself from its own descriptor, which is to say from
        # outside this machine, and the name lands in a shell command.
        row = self.rows(["Rogue\t7\thdmi; rm -rf ~"])[0]
        self.assertEqual(row["action"].command, "set-output 7 'hdmi; rm -rf ~'")

    def test_a_missing_value_leaves_the_argument_empty(self):
        self.assertEqual(self.rows(["Speakers\t1"])[0]["action"].command,
                         "set-output 1")

    def test_a_row_picked_here_keeps_the_menu_up(self):
        # Choosing an output and being thrown out means reopening the menu to
        # hear whether it was the right one.
        self.assertTrue(self.rows(["Speakers\t1\tanalog"])[0]["stay"])

    def test_the_listing_is_capped(self):
        lines = ["Sink %d\t%d\tname%d" % (n, n, n) for n in range(20)]
        self.assertEqual(len(self.rows(lines, limit=4)), 4)

    def test_a_name_shaped_like_markup_is_not_drawn_as_markup(self):
        # The same descriptor the quoting above defends the shell from, one
        # step further on: the label is drawn by a Text, and one left to guess
        # its format fetches what an <img src=...> in a device name points at.
        row = self.rows(['<img src="http://elsewhere/x"> Sink\t1\tanalog'])[0]
        self.assertEqual(row["label"], 'img src="http://elsewhere/x" Sink')

    def test_a_name_too_long_for_a_row_is_cut(self):
        row = self.rows(["S" * 400 + "\t1\tanalog"])[0]
        self.assertEqual(len(row["label"]), 128)

    def test_a_line_with_no_label_is_dropped(self):
        self.assertEqual(
            self.rows(["\t1\tanalog", "Speakers\t1\tanalog"])[0]["label"],
            "Speakers")

    def test_nothing_found_says_so_and_does_nothing(self):
        # A page that opens with no rows on it is a press in the dark.
        row = self.rows([])[0]
        self.assertEqual(row["label"], "No outputs found")
        self.assertIsNone(row["action"])

    def test_a_line_whose_action_will_not_parse_is_dropped(self):
        item = build([dict(LISTED, action="exec:%1")])[0]
        rows = listed(item, ["Empty\t", "Speakers\tanalog"], 8)
        self.assertEqual([row["label"] for row in rows], ["Speakers"])


class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.model = MenuModel(build(GROUPED))

    def test_it_opens_on_the_first_tile_of_the_first_group(self):
        self.assertEqual(self.model.title, ROOT_TITLE)
        self.assertEqual(self.model.group, 0)
        self.assertEqual(self.model.selected, "terminal")
        self.assertEqual(self.model.depth, 0)

    def test_the_top_level_is_the_bar(self):
        self.assertEqual([item["label"] for item in self.model.groups],
                         ["Apps", "Audio"])

    def test_a_group_shows_its_own_tiles(self):
        self.assertEqual([t["item"]["label"] for t in self.model.tiles],
                         ["Terminal", "Browser"])

    def test_walking_the_bar_wraps_and_enters_what_it_lands_on(self):
        # A short strip rather than a page of tiles: there is no edge to be
        # lost at, and walking off one end is how you reach the other.
        self.assertTrue(self.model.group_move(1))
        self.assertEqual(self.model.group, 1)
        self.assertEqual(self.model.selected, "volume-up")
        self.assertTrue(self.model.group_move(1))
        self.assertEqual(self.model.group, 0)

    def test_a_bar_of_one_does_not_walk(self):
        model = MenuModel(build([GROUPED[0]]))
        self.assertFalse(model.group_move(1))

    def test_stepping_past_an_edge_leaves_the_selection_alone(self):
        # Wrapping in two dimensions is losing the cursor, not moving it.
        self.assertFalse(self.model.step("left"))
        self.assertEqual(self.model.selected, "terminal")
        self.assertTrue(self.model.step("right"))
        self.assertEqual(self.model.selected, "browser")
        self.assertFalse(self.model.step("right"))
        self.assertEqual(self.model.selected, "browser")

    def test_a_top_level_verb_is_a_page_of_one(self):
        # The bar holds places, and the shipped tree puts no verb there - but
        # a config that does still has somewhere to draw it.
        model = MenuModel(build([{"label": "Keyboard", "action": "osk:open"}]))
        self.assertEqual([t["item"]["label"] for t in model.tiles],
                         ["Keyboard"])
        self.assertEqual(model.press()[0], "run")

    def test_pressing_a_submenu_drills_in_and_takes_its_label_as_the_title(self):
        self.model.group_move(1)
        self.model.select_id("devices")
        kind, item = self.model.press()
        self.assertEqual(kind, "enter")
        self.assertEqual(self.model.title, "Devices")
        self.assertEqual(self.model.depth, 1)
        self.assertEqual(self.model.selected, "speakers")

    def test_pressing_a_leaf_hands_back_the_row(self):
        kind, item = self.model.press()
        self.assertEqual(kind, "run")
        self.assertIsInstance(item["action"], actions.ExecAction)
        self.assertFalse(item["repeat"])

    def test_back_restores_the_tile_you_left(self):
        self.model.group_move(1)
        self.model.select_id("devices")
        self.model.press()
        self.model.step("right")
        self.assertTrue(self.model.back())
        self.assertEqual(self.model.selected, "devices")
        self.assertEqual(self.model.title, ROOT_TITLE)

    def test_back_at_the_top_of_a_group_reports_nowhere_to_go(self):
        # The bar is not a level to climb to, so the daemon closes the menu.
        self.assertFalse(self.model.back())

    def test_select_names_a_tile_outright(self):
        self.model.select(1)
        self.assertEqual(self.model.selected, "browser")
        self.assertEqual(self.model.index, 1)

    def test_select_clamps_instead_of_wrapping(self):
        self.model.select(-1)
        self.assertEqual(self.model.index, 0)
        self.model.select(99)
        self.assertEqual(self.model.index, len(self.model.tiles) - 1)

    def test_select_by_name_says_whether_the_tile_is_here(self):
        self.assertTrue(self.model.select_id("browser"))
        self.assertFalse(self.model.select_id("mute"))
        self.assertEqual(self.model.selected, "browser")

    def test_select_works_inside_a_submenu(self):
        self.model.group_move(1)
        self.model.select_id("devices")
        self.model.press()
        self.model.select(1)
        self.assertEqual(self.model.selected, "microphone")
        self.assertEqual(self.model.title, "Devices")

    def test_select_on_an_empty_menu_is_safe(self):
        model = MenuModel([])
        model.select(3)
        self.assertEqual(model.index, 0)
        self.assertIsNone(model.selected)
        self.assertEqual(model.press(), ("none", None))

    def test_reset_climbs_all_the_way_out(self):
        self.model.group_move(1)
        self.model.select_id("devices")
        self.model.press()
        self.model.reset()
        self.assertEqual(self.model.depth, 0)
        self.assertEqual(self.model.group, 0)
        self.assertEqual(self.model.selected, "terminal")
        self.assertEqual(self.model.title, ROOT_TITLE)

    def test_choosing_a_listed_tile_moves_the_tick_to_it(self):
        # The command that changes the output is let go of rather than waited
        # for, so re-reading the listing here would race it. The press is the
        # answer until the page is entered again.
        item = build([LISTED])[0]
        item["items"] = listed(item, ["* Speakers\t1\ta", "Television\t7\tb"], 8)
        model = MenuModel([item])
        model.repack()
        model.step("right")
        picked = model.current
        model.choose(picked)
        self.assertEqual([row["on"] for row in model.items], [False, True])

    def test_an_empty_menu_navigates_without_raising(self):
        model = MenuModel([])
        self.assertFalse(model.step("down"))
        self.assertFalse(model.group_move(1))
        self.assertEqual(model.press(), ("none", None))
        self.assertFalse(model.back())


class PageTurnTests(unittest.TestCase):
    """Which way the page in front was reached from.

    The panel draws the new page arriving from that side. It is a serial
    rather than a state because the whole page is re-sent twice a second, and
    a turn already drawn must not be drawn again.
    """

    TREE = [
        {"label": "One", "items": [
            {"label": "Deeper", "items": [
                {"label": "Leaf", "action": "exec:true"},
            ]},
        ]},
        {"label": "Two", "items": [
            {"label": "Other", "action": "exec:true"},
        ]},
        {"label": "Three", "items": [
            {"label": "Third", "action": "exec:true"},
        ]},
    ]

    def model(self):
        model = MenuModel(build(self.TREE))
        model.reset()
        return model

    def test_opening_the_menu_is_not_a_turn(self):
        # A surface arriving has its own way of arriving; a page that also
        # slid in from somewhere would be two entrances for one press.
        model = self.model()
        self.assertEqual(model.turn_seq, 0)
        self.assertEqual(model.view_state(True)["way"], 0)

    def test_drilling_in_is_a_turn_inwards(self):
        model = self.model()
        model.press()
        self.assertEqual(model.turn_seq, 1)
        self.assertEqual(model.turn_way, 1)

    def test_and_coming_back_out_is_the_other_way(self):
        model = self.model()
        model.press()
        model.back()
        self.assertEqual(model.turn_seq, 2)
        self.assertEqual(model.turn_way, -1)

    def test_walking_the_bar_turns_the_way_the_thumb_pushed(self):
        model = self.model()
        model.group_move(1)
        self.assertEqual((model.turn_seq, model.turn_way), (1, 1))
        model.group_move(-1)
        self.assertEqual((model.turn_seq, model.turn_way), (2, -1))

    def test_and_the_wrap_is_still_the_way_the_thumb_pushed(self):
        # The last chip to the first is a step to the right, and looks like a
        # jump to the left to anything counting indexes.
        model = self.model()
        model.enter_group(len(model.groups) - 1)
        model.group_move(1)
        self.assertEqual(model.group, 0)
        self.assertEqual(model.turn_way, 1)

    def test_a_group_nobody_moved_to_is_not_a_turn(self):
        model = self.model()
        before = model.turn_seq
        model.enter_group(model.group)
        self.assertEqual(model.turn_seq, before)


class ConfirmedRowTests(unittest.TestCase):
    """`confirm` on a row: what may carry it, and what may not."""

    def test_an_action_row_may_ask_to_be_held(self):
        items = build([{"label": "Shutdown", "action": "exec:off",
                        "confirm": True}])
        self.assertTrue(items[0]["confirm"])

    def test_and_every_other_row_says_nothing(self):
        items = build([{"label": "Lock", "action": "exec:lock"}])
        self.assertFalse(items[0]["confirm"])

    def test_a_page_is_not_a_thing_to_be_sure_about(self):
        with self.assertRaises(MenuError) as caught:
            build([{"label": "Windows", "confirm": True,
                    "items": [{"label": "Close", "action": "exec:x"}]}])
        self.assertIn("confirm", str(caught.exception))

    def test_nor_is_a_control_that_flips_back(self):
        with self.assertRaises(MenuError) as caught:
            build([{"label": "Vibration", "control": "toggle",
                    "reads": "pad:rumble", "confirm": True}],
                  settings=config_module.CHOSEN)
        self.assertIn("confirm", str(caught.exception))

    def test_and_a_row_cannot_both_repeat_and_be_confirmed(self):
        # One says a held A means this again, the other that it means this at
        # last.
        with self.assertRaises(MenuError) as caught:
            build([{"label": "Louder", "action": "exec:up",
                    "repeat": True, "confirm": True}])
        self.assertIn("confirm", str(caught.exception))


class OpenOnTests(unittest.TestCase):
    """`open_on`: the tile the menu opens on while its condition holds.

    It exists for the row the bar has no room for. The workspace lock used to
    sit at the top level because a row you have to go and find is a row that
    is not there, and the bar holds places rather than verbs.
    """

    TREE = [
        {"label": "Apps", "items": [
            {"label": "Steam", "action": "exec:true"},
        ]},
        {"label": "Controller", "items": [
            {"label": "Shortcuts", "action": "guide:open"},
            {"label": "Workspace lock", "action": "lock:toggle",
             "when": ["game", "handed_over"], "open_on": True},
        ]},
    ]

    def opened(self, *states):
        model = MenuModel(build(self.TREE))
        model.conditions = frozenset(states)
        model.reset()
        return (model.group, model.selected)

    def test_nothing_claims_it_and_the_menu_opens_where_it_always_did(self):
        self.assertEqual(self.opened(), (0, "steam"))

    def test_the_condition_holds_and_the_menu_opens_on_the_tile(self):
        self.assertEqual(self.opened("game"), (1, "workspace-lock"))
        self.assertEqual(self.opened("handed_over"), (1, "workspace-lock"))

    def test_the_earliest_claim_wins(self):
        tree = build([
            {"label": "One", "items": [
                {"label": "First", "action": "exec:true", "when": "game",
                 "open_on": True},
            ]},
            {"label": "Two", "items": [
                {"label": "Second", "action": "exec:true", "when": "game",
                 "open_on": True},
            ]},
        ])
        model = MenuModel(tree)
        model.conditions = frozenset(["game"])
        model.reset()
        self.assertEqual(model.selected, "first")

    def test_it_needs_a_when_to_be_nearer_about(self):
        # Only a tile that is sometimes offered has anything to be nearer
        # about; one that is always there is already wherever it is.
        with self.assertRaises(MenuError) as caught:
            build([{"label": "X", "action": "exec:true", "open_on": True}])
        self.assertIn("open_on", str(caught.exception))


class PageKeyTests(unittest.TestCase):
    """`keys`: what a page spends X and Y on while it is the page in front."""

    def page(self, keys):
        return build([{"label": "Apps", "keys": keys, "items": [
            {"label": "Steam", "action": "exec:true"},
        ]}])[0]

    def test_a_page_may_spend_x_and_y(self):
        item = self.page({
            "X": {"tap": "exec:true", "hold": "menu:close", "short": "Go"},
            "Y": "exec:true",
        })
        self.assertEqual(sorted(item["keys"]), ["X", "Y"])

    def test_a_page_spends_nothing_unless_it_says(self):
        items = build([{"label": "Apps", "items": [
            {"label": "Steam", "action": "exec:true"},
        ]}])
        self.assertEqual(items[0]["keys"], {})

    def test_a_page_may_not_spend_a_or_b(self):
        # The contract is that A commits and B leaves, in every layer and
        # every surface. A page that could take either would be the one place
        # on the pad where that stopped being true.
        for button in ("A", "B"):
            with self.assertRaises(MenuError) as caught:
                self.page({button: "exec:true"})
            self.assertIn(button, str(caught.exception))

    def test_taking_x_has_to_keep_close_on_the_hold(self):
        # X is how you leave from everywhere else in this surface.
        with self.assertRaises(MenuError) as caught:
            self.page({"X": "exec:true"})
        self.assertIn("menu:close", str(caught.exception))
        with self.assertRaises(MenuError):
            self.page({"X": {"tap": "exec:true", "hold": "exec:false"}})

    def test_y_needs_no_hold_because_it_displaced_nothing(self):
        item = self.page({"Y": "exec:true"})
        self.assertEqual(sorted(item["keys"]), ["Y"])

    def test_a_key_that_will_not_parse_names_the_page(self):
        with self.assertRaises(MenuError) as caught:
            self.page({"Y": "nonsense:thing"})
        self.assertIn("menu.items[0]", str(caught.exception))

    def test_a_tile_that_acts_has_no_page_to_spend_on(self):
        with self.assertRaises(MenuError) as caught:
            build([{"label": "Steam", "action": "exec:true",
                    "keys": {"Y": "exec:true"}}])
        self.assertIn("page", str(caught.exception))

    def test_a_keys_table_is_a_table(self):
        with self.assertRaises(MenuError):
            self.page("Y")

    def test_the_page_in_front_is_what_is_asked(self):
        tree = build([
            {"label": "Apps", "keys": {"Y": "exec:apps"}, "items": [
                {"label": "Steam", "action": "exec:true"},
                {"label": "More", "keys": {"Y": "exec:more"}, "items": [
                    {"label": "Deep", "action": "exec:true"},
                ]},
            ]},
            {"label": "Plain", "items": [
                {"label": "Thing", "action": "exec:true"},
            ]},
        ])
        model = MenuModel(tree)
        self.assertEqual(model.page_keys(), {"Y": "exec:apps"})
        model.select_id("more")
        model.press()
        self.assertEqual(model.page_keys(), {"Y": "exec:more"})
        model.back()
        self.assertEqual(model.page_keys(), {"Y": "exec:apps"})
        model.group_move(1)
        self.assertEqual(model.page_keys(), {})

    def test_a_page_names_itself_for_anything_that_caches(self):
        tree = build([{"label": "Apps", "items": [
            {"label": "More", "items": [
                {"label": "Deep", "action": "exec:true"},
            ]},
        ]}])
        model = MenuModel(tree)
        top = model.page_name()
        model.select_id("more")
        model.press()
        self.assertNotEqual(model.page_name(), top)
        model.back()
        self.assertEqual(model.page_name(), top)


class IdTests(unittest.TestCase):
    """What a saved layout names a tile by."""

    def test_an_id_comes_from_the_label(self):
        self.assertEqual(slug("Now playing"), "now-playing")
        self.assertEqual(slug("Volume  up!"), "volume-up")
        self.assertEqual(slug("!!!"), "row")

    def test_a_row_may_name_itself(self):
        # A label is allowed to change without orphaning a layout.
        items = build([{"label": "Volume", "id": "sound", "action": "nop"}])
        self.assertEqual(items[0]["id"], "sound")

    def test_two_tiles_on_one_page_cannot_share_a_name(self):
        with self.assertRaises(MenuError) as caught:
            build([{"label": "Volume", "action": "nop"},
                   {"label": "volume", "action": "nop"}])
        self.assertIn("volume", str(caught.exception))

    def test_the_same_name_on_two_pages_is_fine(self):
        build([{"label": "Close", "items": [
                    {"label": "Now", "action": "nop"}]},
               {"label": "Open", "items": [
                    {"label": "Now", "action": "nop"}]}])


class SpanTests(unittest.TestCase):
    def test_a_tile_is_one_cell_unless_it_says_otherwise(self):
        self.assertEqual(build([{"label": "A", "action": "nop"}])[0]["span"],
                         (1, 1))

    def test_a_span_is_two_numbers_of_cells(self):
        items = build([{"label": "A", "action": "nop", "span": [3, 2]}])
        self.assertEqual(items[0]["span"], (3, 2))

    def test_a_span_wider_than_the_page_names_the_row(self):
        with self.assertRaises(MenuError) as caught:
            build([{"label": "A", "action": "nop", "span": [9, 1]}],
                  columns=6)
        self.assertIn("wider", str(caught.exception))

    def test_a_span_of_nothing_is_not_a_tile(self):
        with self.assertRaises(MenuError):
            build([{"label": "A", "action": "nop", "span": [0, 1]}])

    def test_a_span_that_is_not_a_pair_says_so(self):
        with self.assertRaises(MenuError):
            build([{"label": "A", "action": "nop", "span": 3}])


class ControlTests(unittest.TestCase):
    def test_a_tile_declares_nothing_by_default(self):
        items = build([{"label": "A", "action": "nop"}])
        self.assertEqual(items[0]["control"], "")

    def test_a_control_nobody_has_is_named_at_build_time(self):
        with self.assertRaises(MenuError) as caught:
            build([{"label": "A", "action": "nop", "control": "dail"}])
        self.assertIn("dail", str(caught.exception))

    def test_a_break_needs_neither_a_label_nor_an_action(self):
        items = build([{"control": "row_break"}])
        self.assertEqual(items[0]["control"], "row_break")


class ControlTileTests(unittest.TestCase):
    """A tile that holds a value rather than doing something."""

    SETTINGS = {
        "rumble": {"kind": "bool"},
        "badge_style": {"kind": "choice", "choices": ("filled", "stencil")},
        "pointer_speed": {"kind": "number"},
    }

    def tile(self, **keys):
        entry = {"label": "Thing"}
        entry.update(keys)
        return build([entry], settings=self.SETTINGS)[0]

    def test_a_toggle_reads_a_switch(self):
        item = self.tile(control="toggle", reads="pad:rumble")
        self.assertEqual(item["control"], "toggle")
        self.assertEqual(item["reads"], ("pad", "rumble"))

    def test_a_choice_reads_a_choice(self):
        item = self.tile(control="choice", reads="pad:badge_style")
        self.assertEqual(item["reads"], ("pad", "badge_style"))

    def test_a_control_needs_no_action_and_no_page(self):
        # It acts on what it reads, so `needs an action or items` is
        # satisfied by being a control.
        self.tile(control="toggle", reads="pad:rumble")

    def test_a_control_has_to_say_what_it_reads(self):
        with self.assertRaises(MenuError) as caught:
            self.tile(control="toggle")
        self.assertIn("reads", str(caught.exception))

    def test_only_a_control_reads_something(self):
        with self.assertRaises(MenuError) as caught:
            self.tile(action="nop", reads="pad:rumble")
        self.assertIn("control", str(caught.exception))

    def test_a_reader_names_a_source_and_a_setting(self):
        for bad in ("rumble", "pad:", "sofa:rumble", ""):
            with self.assertRaises(MenuError, msg=bad):
                self.tile(control="toggle", reads=bad)

    def test_a_setting_nobody_has_is_named_at_build_time(self):
        with self.assertRaises(MenuError) as caught:
            self.tile(control="toggle", reads="pad:nonesuch")
        self.assertIn("nonesuch", str(caught.exception))

    def test_a_switch_pointed_at_a_number_is_a_tile_that_cannot_draw(self):
        with self.assertRaises(MenuError) as caught:
            self.tile(control="toggle", reads="pad:pointer_speed")
        self.assertIn("number", str(caught.exception))
        with self.assertRaises(MenuError):
            self.tile(control="choice", reads="pad:rumble")

    def test_a_control_does_not_repeat_and_always_stays(self):
        with self.assertRaises(MenuError):
            self.tile(control="toggle", reads="pad:rumble", repeat=True)
        item = self.tile(control="toggle", reads="pad:rumble")
        self.assertTrue(item["stay"])

    def test_a_control_takes_the_cells_its_shape_asks_for(self):
        self.assertEqual(
            self.tile(control="toggle", reads="pad:rumble")["span"], (1, 1))
        self.assertEqual(
            self.tile(control="choice", reads="pad:badge_style")["span"],
            (2, 1))

    def test_a_reader_is_only_checked_where_the_table_is_given(self):
        # Both real callers pass it; the default is what lets this module be
        # built against nothing at all.
        build([{"label": "T", "control": "toggle", "reads": "pad:nonesuch"}])

    def test_the_payload_carries_what_the_daemon_answered(self):
        tree = build([{"label": "Pad", "items": [
            {"label": "Vibration", "control": "toggle", "reads": "pad:rumble"},
            {"label": "Style", "control": "choice",
             "reads": "pad:badge_style"},
        ]}], settings=self.SETTINGS)
        model = MenuModel(tree)

        def control(item):
            if item["control"] == "toggle":
                return {"on": True}
            return {"t": "Stencil"}

        rows = model.view_state(True, control=control)["items"]
        self.assertEqual([row["k"] for row in rows], ["toggle", "choice"])
        self.assertTrue(rows[0]["on"])
        self.assertEqual(rows[1]["t"], "Stencil")
        # And it keeps everything a tile has: a control is a tile first.
        self.assertEqual(rows[0]["l"], "Vibration")
        self.assertEqual((rows[1]["x"], rows[1]["w"]), (1, 2))



class RowsTileTests(unittest.TestCase):
    """A card that holds a page rather than opening one."""

    POWER = {
        "label": "Power",
        "control": "rows",
        "detail": "Auto-sleep 30 min",
        "items": [
            {"label": "Rest mode", "action": "exec:rest"},
            {"label": "Restart", "action": "exec:restart"},
            {"label": "Full shutdown", "action": "exec:off",
             "confirm": True},
        ],
    }

    PAGE = [{"label": "System", "items": [
        {"label": "Lock", "action": "exec:lock"},
        dict(POWER),
        {"label": "Wake", "action": "exec:wake"},
    ]}]

    def card(self, **keys):
        entry = dict(self.POWER)
        entry.update(keys)
        return build([entry])[0]

    def model(self):
        return MenuModel(build(self.PAGE))

    # -- what the config may say ------------------------------------------

    def test_the_items_are_held_rather_than_opened(self):
        item = self.card()
        self.assertEqual(item["control"], "rows")
        self.assertEqual([row["label"] for row in item["rows"]],
                         ["Rest mode", "Restart", "Full shutdown"])
        # And it reads as a leaf everywhere that asks, which is what keeps
        # the payload's `sub`, the title line and `press` right.
        self.assertIsNone(item["items"])

    def test_a_card_with_nothing_in_it_says_so(self):
        with self.assertRaises(MenuError) as caught:
            build([{"label": "Power", "control": "rows",
                    "action": "exec:off"}])
        self.assertIn("has none", str(caught.exception))

    def test_a_row_here_cannot_open_a_page(self):
        # There is nowhere further in: the card is already the page.
        with self.assertRaises(MenuError) as caught:
            build([{"label": "Power", "control": "rows", "items": [
                {"label": "More", "items": [
                    {"label": "Deeper", "action": "exec:x"}]}]}])
        self.assertIn("cannot open a page", str(caught.exception))

    def test_nor_can_it_hold_a_value(self):
        with self.assertRaises(MenuError) as caught:
            build([{"label": "Power", "control": "rows", "items": [
                {"label": "Vibration", "control": "toggle",
                 "reads": "pad:rumble"}]}],
                settings=config_module.CHOSEN)
        self.assertIn("is a verb", str(caught.exception))

    def test_a_break_ends_a_row_of_cells_and_these_are_not_cells(self):
        with self.assertRaises(MenuError) as caught:
            build([{"label": "Power", "control": "rows", "items": [
                {"label": "Rest", "action": "exec:rest"},
                {"control": "row_break"}]}])
        self.assertIn("break", str(caught.exception))

    def test_a_card_may_list_its_rows_instead_of_holding_them(self):
        # Which is the whole point of one for a device: what is plugged in is
        # not something a config file knows, and the card is read when the
        # page it sits on settles rather than at a press, because nobody
        # enters a card.
        item = build([{"label": "Output", "control": "rows",
                       "empty": "No outputs found",
                       "action": "exec:set %1", "from": "list-outputs"}])[0]
        self.assertEqual(item["from"], "list-outputs")
        self.assertIsNone(item["items"])
        # Seeded with its own words rather than with nothing: a blank card on
        # a page you are looking at reads as a drawing fault.
        self.assertEqual([row["label"] for row in item["rows"]],
                         ["No outputs found"])

    def test_a_listing_with_one_line_is_a_reading_rather_than_a_list(self):
        # One pair of speakers in the room is one row: picking it sets what is
        # already set, and a column of alternatives with a single alternative
        # in it is a card of furniture round a fact.
        item = build([{"label": "Output", "control": "rows",
                       "action": "exec:set %1", "from": "list-outputs"}])[0]
        item["rows"][:] = listed(item, ["* Speakers\t1"], 10)
        model = MenuModel([dict(item)])
        self.assertTrue(model.lone(model.current))
        # So there is nothing to go in for, and A finds nothing to do.
        self.assertIsNone(model.takeable())
        card = [tile for tile in model.view_state(True)["items"]
                if tile["id"] == "output"][0]
        self.assertTrue(card["one"])

    def test_and_a_second_line_makes_it_a_list_again(self):
        item = build([{"label": "Output", "control": "rows",
                       "action": "exec:set %1", "from": "list-outputs"}])[0]
        item["rows"][:] = listed(item, ["* Speakers\t1", "The TV\t2"], 10)
        model = MenuModel([dict(item)])
        self.assertFalse(model.lone(model.current))
        self.assertIsNotNone(model.takeable())
        card = [tile for tile in model.view_state(True)["items"]
                if tile["id"] == "output"][0]
        self.assertNotIn("one", card)

    def test_but_a_card_somebody_wrote_one_row_into_is_still_a_card(self):
        # A verb is a verb whether or not it has company; only a *listing*
        # with one line is a fact rather than a choice.
        model = MenuModel(build([{"label": "Power", "control": "rows",
                                  "items": [{"label": "Rest",
                                             "action": "exec:rest"}]}]))
        self.assertFalse(model.lone(model.current))
        self.assertIsNotNone(model.takeable())

    def test_and_what_the_command_prints_becomes_its_rows(self):
        item = build([{"label": "Output", "control": "rows",
                       "action": "exec:set %1", "from": "list-outputs"}])[0]
        item["rows"][:] = listed(item, ["* Speakers\t1", "The TV\t2"], 10)
        model = MenuModel([dict(item)])
        self.assertEqual([row["label"] for row in model.rows_of(model.current)],
                         ["Speakers", "The TV"])
        self.assertEqual([row["on"] for row in model.rows_of(model.current)],
                         [True, False])

    def test_a_card_has_no_mark_of_its_own(self):
        # An icon everywhere else here is the big mark in a card's corner. A
        # card of rows has no corner to spare, and a glyph at the heading's
        # size in front of tracked capitals reads as a bullet - so it is said
        # rather than accepted and drawn nowhere.
        with self.assertRaises(MenuError) as caught:
            build([{"label": "Power", "control": "rows", "icon": "P",
                    "items": [{"label": "Rest", "action": "exec:rest"}]}])
        self.assertIn("no mark of its own", str(caught.exception))

    def test_but_a_row_in_one_may_carry_a_mark(self):
        item = build([{"label": "Power", "control": "rows", "items": [
            {"label": "Rest", "icon": "R", "action": "exec:rest"}]}])[0]
        self.assertEqual(item["rows"][0]["icon"], "R")

    def test_a_card_is_not_a_page_and_spends_no_key(self):
        with self.assertRaises(MenuError) as caught:
            build([{"label": "Power", "control": "rows",
                    "keys": {"Y": {"tap": "exec:x"}},
                    "items": [{"label": "Rest", "action": "exec:rest"}]}])
        self.assertIn("only a page can spend a key", str(caught.exception))

    def test_it_asks_for_a_stack_of_cells_by_default(self):
        self.assertEqual(self.card()["span"], (2, 3))

    def test_and_a_row_of_it_may_be_held_like_any_other(self):
        item = self.card()
        self.assertTrue(item["rows"][2]["confirm"])

    # -- going in, and walking it ------------------------------------------

    def test_a_card_is_entered_before_it_is_walked(self):
        model = self.model()
        model.select_id("power")
        self.assertFalse(model.entered)
        # Down is the page's until A goes in: the tile below is what a thumb
        # pushing down is reaching for, and a card that answered with its own
        # second row would make one direction mean two things.
        self.assertFalse(model.step_row("down"))
        self.assertEqual(model.row, "rest-mode")

    def test_and_a_is_what_goes_in(self):
        model = self.model()
        model.select_id("power")
        self.assertIs(model.takeable(), model.current)
        self.assertTrue(model.take())
        self.assertTrue(model.entered)

    def test_down_the_page_walks_past_the_card_rather_than_into_it(self):
        page = [{"label": "System", "items": [
            dict(self.POWER),
            {"control": "row_break"},
            {"label": "Wake", "action": "exec:wake"},
        ]}]
        model = MenuModel(build(page))
        model.select_id("power")
        self.assertTrue(model.step("down"))
        self.assertEqual(model.selected, "wake")

    def test_and_walking_off_a_card_puts_nobody_inside_the_next_one(self):
        page = [{"label": "System", "items": [
            dict(self.POWER),
            dict(self.POWER, label="Sound", id="sound"),
        ]}]
        model = MenuModel(build(page))
        model.select_id("power")
        model.take()
        model.step_row("down")
        model.step("right")
        self.assertEqual(model.selected, "sound")
        self.assertFalse(model.entered)
        # And its cursor starts at the top: where you were in the last card
        # is not a place in this one.
        self.assertEqual(model.row, "rest-mode")

    def test_inside_it_up_and_down_are_the_card_s(self):
        model = self.model()
        model.select_id("power")
        model.take()
        self.assertTrue(model.step_row("down"))
        self.assertEqual(model.row, "restart")
        self.assertTrue(model.step_row("down"))
        self.assertEqual(model.row, "full-shutdown")
        self.assertTrue(model.step_row("up"))
        self.assertEqual(model.row, "restart")

    def test_and_the_end_of_the_list_is_the_end_of_it(self):
        # No wrapping, for the reason the grid does not wrap: a cursor that
        # reappeared at the far end is a cursor you have lost. B is the way
        # out.
        model = self.model()
        model.select_id("power")
        model.take()
        self.assertFalse(model.step_row("up"))
        self.assertEqual(model.row, "rest-mode")
        for _ in range(2):
            model.step_row("down")
        self.assertFalse(model.step_row("down"))
        self.assertEqual(model.row, "full-shutdown")

    def test_leaving_keeps_the_row_for_the_next_time_in(self):
        model = self.model()
        model.select_id("power")
        model.take()
        model.step_row("down")
        self.assertTrue(model.release())
        self.assertFalse(model.entered)
        model.take()
        self.assertEqual(model.row, "restart")

    def test_a_row_that_is_not_offered_is_not_walked_to(self):
        page = [{"label": "System", "items": [
            {"label": "Power", "control": "rows", "items": [
                {"label": "Rest", "action": "exec:rest"},
                {"label": "Unlock", "action": "exec:unlock", "when": "locked"},
                {"label": "Restart", "action": "exec:restart"},
            ]},
        ]}]
        model = MenuModel(build(page))
        model.take()
        model.step_row("down")
        self.assertEqual(model.row, "restart")

    def test_naming_a_row_is_how_a_pointer_reaches_one(self):
        model = self.model()
        model.select_id("power")
        self.assertTrue(model.select_row("full-shutdown"))
        self.assertEqual(model.row, "full-shutdown")
        self.assertFalse(model.select_row("nothing-here"))

    def test_leaving_the_card_forgets_the_row(self):
        model = self.model()
        model.select_id("power")
        model.select_id("lock")
        self.assertIsNone(model.row)

    # -- pressing it -------------------------------------------------------

    def test_a_press_is_aimed_at_the_row_once_you_are_inside(self):
        model = self.model()
        model.select_id("power")
        model.take()
        model.step_row("down")
        kind, item = model.press()
        self.assertEqual(kind, "run")
        self.assertEqual(item["label"], "Restart")
        # And the flash lands on the row, which is the thing that was pressed.
        self.assertEqual(model.press_hit, "restart")

    def test_and_at_the_card_before_you_are(self):
        # Which is what lets `takeable()` catch the press and turn it into
        # going in, rather than a row running from outside the list.
        model = self.model()
        model.select_id("power")
        self.assertEqual(model.acting["label"], "Power")

    def test_and_a_card_with_no_row_under_the_cursor_presses_nothing(self):
        model = self.model()
        model.select_id("power")
        model.take()
        model.row = "gone"
        self.assertEqual(model.press()[0], "none")

    def test_acting_is_the_tile_itself_everywhere_else(self):
        model = self.model()
        self.assertEqual(model.acting["label"], "Lock")
        self.assertIs(model.acting, model.current)

    # -- drawing it --------------------------------------------------------

    def test_the_payload_carries_the_rows_and_the_one_in_front(self):
        model = self.model()
        model.select_id("power")
        model.take()
        model.step_row("down")
        state = model.view_state(True)
        # And that somebody is inside it, which is what says the row cursor
        # may be drawn at all.
        self.assertEqual(state["hd"], "power")
        self.assertEqual(state["row"], "restart")
        card = [tile for tile in state["items"] if tile["id"] == "power"][0]
        self.assertEqual(card["k"], "rows")
        self.assertFalse(card["sub"])
        self.assertEqual([row["l"] for row in card["rs"]],
                         ["Rest mode", "Restart", "Full shutdown"])
        self.assertEqual(card["d"], "Auto-sleep 30 min")

    def test_a_row_is_ticked_by_the_same_question_a_tile_is(self):
        model = self.model()
        state = model.view_state(
            True, state=lambda action: action.command == "restart")
        card = [tile for tile in state["items"] if tile["id"] == "power"][0]
        self.assertEqual([row.get("on") for row in card["rs"]],
                         [False, True, False])

    def test_and_a_row_that_steps_a_number_prints_where_it_got_to(self):
        model = self.model()
        state = model.view_state(True, value=lambda action: "9 a second")
        card = [tile for tile in state["items"] if tile["id"] == "power"][0]
        self.assertEqual(card["rs"][0]["d"], "9 a second")

    def test_a_card_is_not_asked_what_value_it_is_on(self):
        # It is a control that reads nothing, and the daemon's answer to that
        # question starts by unpacking the pair a tile reads from. Asked, it
        # took the whole daemon down on the next heartbeat.
        model = self.model()
        asked = []

        def control(item):
            asked.append(item["id"])
            return {}

        model.view_state(True, control=control)
        self.assertNotIn("power", asked)

    def test_a_page_placed_again_keeps_the_row_it_was_on(self):
        model = self.model()
        model.select_id("power")
        model.take()
        model.step_row("down")
        model.repack()
        self.assertEqual(model.selected, "power")
        self.assertEqual(model.row, "restart")

class TakenTests(unittest.TestCase):
    """A control with a range, and the two axes it borrows while it is held."""

    SETTINGS = {
        "rumble": {"kind": "bool"},
        "pointer_speed": {"kind": "number"},
        "scroll_speed": {"kind": "number"},
    }

    def model(self):
        # One group: the top level is a bar of chips, so a flat list would be
        # four pages of one tile each.
        return MenuModel(build([{"label": "Sticks", "items": [
            {"label": "Pointer", "control": "slider",
             "reads": "pad:pointer_speed"},
            {"label": "Scroll", "control": "slider",
             "reads": "pad:scroll_speed"},
            {"label": "Vibration", "control": "toggle", "reads": "pad:rumble"},
            {"label": "More", "items": [{"label": "Deep", "action": "nop"}]},
        ]}], settings=self.SETTINGS))

    def test_a_slider_is_three_cells_wide(self):
        # A bar shorter than this cannot be aimed at: where along its travel
        # it is, is the whole of what a slider says.
        item = build([{"label": "Pointer", "control": "slider",
                       "reads": "pad:pointer_speed"}],
                     settings=self.SETTINGS)[0]
        self.assertEqual(item["span"], (3, 1))

    def test_a_nested_page_is_checked_the_way_the_top_level_is(self):
        # `settings` and `columns` have to travel down the recursion. They did
        # not, and the shipped tree keeps every control tile a level down - so
        # nothing in it was ever matched against the setting it reads.
        with self.assertRaises(MenuError) as caught:
            build([{"label": "Group", "items": [
                {"label": "Wrong", "control": "slider", "reads": "pad:rumble"},
            ]}], settings=self.SETTINGS)
        self.assertIn("items[0].items[0]", str(caught.exception))
        with self.assertRaises(MenuError) as caught:
            build([{"label": "Group", "items": [
                {"label": "Wide", "action": "nop", "span": [9, 1]},
            ]}], columns=6, settings=self.SETTINGS)
        self.assertIn("6 columns", str(caught.exception))

    def test_a_slider_reads_a_number_and_nothing_else(self):
        with self.assertRaises(MenuError) as caught:
            build([{"label": "Vibration", "control": "slider",
                    "reads": "pad:rumble"}], settings=self.SETTINGS)
        self.assertIn("slider", str(caught.exception))

    def test_a_switch_is_acted_on_rather_than_held(self):
        # Taking a two-state control in order to then push it sideways is a
        # mode nobody needed. What wants taking is a control with a range.
        model = self.model()
        self.assertTrue(model.select_id("vibration"))
        self.assertIsNone(model.takeable())
        self.assertFalse(model.take())
        self.assertIsNone(model.taken)

    def test_taking_and_letting_go(self):
        model = self.model()
        self.assertTrue(model.take())
        self.assertEqual(model.taken, "pointer")
        self.assertEqual(model.held["label"], "Pointer")
        self.assertTrue(model.release())
        self.assertIsNone(model.taken)
        # False the second time, so B can go on meaning back.
        self.assertFalse(model.release())

    def test_a_page_change_lets_go(self):
        model = self.model()
        model.select_id("more")
        model.press()
        self.assertIsNone(model.taken)
        model.back()
        self.assertIsNone(model.taken)

    def test_moving_the_selection_lets_go(self):
        # Both axes belong to a held tile, so this cannot happen from the pad
        # - but a pointer can name another tile, and a tile nobody is on must
        # not still be the one a direction moves.
        model = self.model()
        model.take()
        model.step("right")
        self.assertIsNone(model.taken)
        model.take()
        model.select(0)
        self.assertIsNone(model.taken)

    def test_a_repack_keeps_hold_of_what_was_being_pushed(self):
        # A listing landing beside a slider must not let go of it.
        model = self.model()
        model.take()
        model.repack()
        self.assertEqual(model.taken, "pointer")

    def test_the_payload_says_which_tile_is_held(self):
        model = self.model()
        model.take()
        state = model.view_state(True)
        held = [row for row in state["items"] if row.get("hd")]
        self.assertEqual([row["id"] for row in held], ["pointer"])
        self.assertEqual(state["hd"], "pointer")

    def test_nothing_held_says_so_plainly(self):
        state = self.model().view_state(True)
        self.assertEqual(state["hd"], "")
        self.assertFalse([row for row in state["items"] if "hd" in row])


class GroupDetailTests(unittest.TestCase):
    """What the bar cannot say, and the title line now does."""

    def state(self):
        model = MenuModel(build([
            {"label": "Now", "detail": "Sound, screen, what is playing",
             "items": [{"label": "One", "action": "nop"}]},
            {"label": "Apps", "items": [{"label": "Two", "action": "nop"}]},
        ]))
        return model.view_state(True)

    def test_a_group_carries_its_own_detail(self):
        rows = self.state()["groups"]
        self.assertEqual(rows[0]["d"], "Sound, screen, what is playing")

    def test_a_group_written_without_one_says_nothing(self):
        # Empty rather than absent: the panel reads `groups[g].d` and a key
        # that is sometimes there is a key it has to test for twice.
        rows = self.state()["groups"]
        self.assertEqual(rows[1]["d"], "")

    def test_every_group_carries_it_not_only_the_current_one(self):
        # Which group is in front already travels as `g`. A payload that
        # answered that twice is one that can disagree with itself.
        rows = self.state()["groups"]
        self.assertTrue(all("d" in row for row in rows))


class PressMarkTests(unittest.TestCase):
    """The one event on a surface of states: which tile A landed on."""

    def model(self):
        return MenuModel(build([{"label": "Group", "items": [
            {"label": "One", "action": "nop"},
            {"label": "Two", "action": "nop"},
            {"label": "Deeper", "items": [
                {"label": "Inside", "action": "nop"},
            ]},
        ]}]))

    def test_nobody_has_pressed_anything_yet(self):
        # Never 0 once a press has happened, so 0 is the panel's own proof
        # that it has nothing to draw - the same guard `ripple.py` keeps.
        state = self.model().view_state(True)
        self.assertEqual(state["n"], 0)
        self.assertEqual(state["hit"], "")

    def test_a_press_names_the_tile_it_landed_on(self):
        model = self.model()
        model.select(0)
        before = model.view_state(True)["n"]
        model.press()
        state = model.view_state(True)
        self.assertEqual(state["n"], before + 1)
        self.assertEqual(state["hit"], model.items[0]["id"])

    def test_the_count_moves_for_every_press(self):
        # A tile pressed twice has to read as two presses, or the second one
        # is a payload the panel throws away as a duplicate.
        model = self.model()
        model.select(0)
        model.press()
        first = model.view_state(True)["n"]
        model.press()
        self.assertEqual(model.view_state(True)["n"], first + 1)

    def test_an_empty_page_marks_nothing(self):
        model = MenuModel(build([]))
        model.press()
        self.assertEqual(model.view_state(True)["n"], 0)

    def test_drilling_in_still_counts_as_a_press(self):
        # The tile it names is not on the page that arrives, so the panel
        # finds nothing to light - which is right, because the page changing
        # is the answer. The count still moves: a serial with a hole in it is
        # one the panel cannot reason about.
        model = self.model()
        model.select_id("deeper")
        model.press()
        state = model.view_state(True)
        self.assertEqual(state["n"], 1)
        self.assertEqual(state["hit"], "deeper")
        self.assertNotIn("deeper", [row["id"] for row in state["items"]])


class ArrangeTests(unittest.TestCase):
    """A saved arrangement meeting a config that has moved on."""

    def page(self, *labels):
        return build([{"label": "Group", "items": [
            {"label": label, "action": "nop"} for label in labels
        ]}], settings={})[0]["items"]

    def test_nothing_saved_is_the_config_order(self):
        items = self.page("One", "Two", "Three")
        self.assertIs(arrange(items, None), items)
        self.assertIs(arrange(items, {}), items)

    def test_the_order_is_what_is_drawn(self):
        items = self.page("One", "Two", "Three")
        out = arrange(items, {"order": ["three", "one", "two"]})
        self.assertEqual([item["id"] for item in out],
                         ["three", "one", "two"])

    def test_a_tile_the_config_gained_is_appended(self):
        # Rule 2: so a newly shipped tile always appears, rather than being
        # invisible to everyone who has ever rearranged that page.
        items = self.page("One", "Two", "Three")
        out = arrange(items, {"order": ["three", "one"]})
        self.assertEqual([item["id"] for item in out],
                         ["three", "one", "two"])

    def test_an_id_the_config_lost_is_dropped(self):
        # Rule 3: so editing config.toml can never break a saved layout.
        items = self.page("One", "Two")
        out = arrange(items, {"order": ["gone", "two", "one"]})
        self.assertEqual([item["id"] for item in out], ["two", "one"])

    def test_hidden_suppresses_only_what_the_config_still_has(self):
        # Rule 1: it can never hide something that did not exist when it was
        # written, because there is nothing there to hide.
        items = self.page("One", "Two")
        out = arrange(items, {"order": [], "hidden": ["two", "never"]})
        self.assertEqual([item["id"] for item in out], ["one"])

    def test_a_hidden_tile_is_still_drawn_while_editing(self):
        # There is nowhere for it to have gone, so putting it back is the same
        # press that took it away.
        items = self.page("One", "Two")
        out = arrange(items, {"order": [], "hidden": ["two"]}, editing=True)
        self.assertEqual([item["id"] for item in out], ["one", "two"])

    def test_a_break_keeps_the_slot_it_was_written_in(self):
        # Authored rather than arranged: it is the page's paragraph mark, and
        # a tile moved past it crosses into the next paragraph.
        items = build([{"label": "Group", "items": [
            {"label": "One", "action": "nop"},
            {"control": "row_break"},
            {"label": "Two", "action": "nop"},
        ]}], settings={})[0]["items"]
        out = arrange(items, {"order": ["two", "one"]})
        self.assertEqual([item["control"] for item in out],
                         ["", "row_break", ""])
        self.assertEqual([item["id"] for item in out if item["id"]],
                         ["two", "one"])

    def test_a_saved_span_is_the_one_that_applies(self):
        # One function, one authority: nothing else may ask which span wins.
        item = self.page("One")[0]
        self.assertEqual(effective_span(item, None), (1, 1))
        self.assertEqual(
            effective_span(item, {"span": {"one": [3, 2]}}), (3, 2))


class RearrangeTests(unittest.TestCase):
    """Picking a tile up, walking it about, and putting it down."""

    def model(self):
        return MenuModel(build([{"label": "Group", "items": [
            {"label": "One", "action": "nop"},
            {"label": "Two", "action": "nop"},
            {"label": "Three", "action": "nop"},
            {"label": "Four", "action": "nop"},
            {"label": "Five", "action": "nop"},
            {"label": "Six", "action": "nop"},
            {"label": "Seven", "action": "nop"},
        ]}], settings={}), columns=6)

    def order(self, model):
        return [tile["item"]["id"] for tile in model.tiles]

    def test_nothing_moves_outside_edit_mode(self):
        model = self.model()
        self.assertFalse(model.pick())
        self.assertFalse(model.carry("right"))
        self.assertFalse(model.hide())

    def cells(self, model):
        return dict((tile["item"]["id"], tile["at"]) for tile in model.tiles)

    def test_a_tile_is_carried_one_cell_sideways(self):
        model = self.model()
        model.set_edit(True)
        self.assertTrue(model.pick())
        self.assertEqual(model.picked, "one")
        self.assertTrue(model.carry("right"))
        self.assertEqual(self.cells(model)["one"], (1, 0))
        self.assertTrue(model.carry("left"))
        self.assertEqual(self.cells(model)["one"], (0, 0))

    def test_the_row_closes_up_behind_a_tile_that_moved(self):
        # What the old reorder gesture did, and it still happens - the tile
        # is pinned where it was put and everything unpinned flows round it.
        model = self.model()
        model.set_edit(True)
        model.pick()
        model.carry("right")
        cells = self.cells(model)
        self.assertEqual(cells["one"], (1, 0))
        self.assertEqual(cells["two"], (0, 0))
        self.assertEqual(cells["three"], (2, 0))

    def test_the_edge_of_the_page_is_the_edge_of_it(self):
        model = self.model()
        model.set_edit(True)
        model.pick()
        self.assertFalse(model.carry("left"))
        self.assertFalse(model.carry("up"))
        self.assertEqual(self.cells(model)["one"], (0, 0))

    def test_a_tile_stops_at_the_last_column(self):
        model = self.model()
        model.set_edit(True)
        model.pick()
        for _ in range(5):
            self.assertTrue(model.carry("right"))
        self.assertEqual(self.cells(model)["one"], (5, 0))
        self.assertFalse(model.carry("right"))

    def test_down_is_one_row(self):
        model = self.model()
        model.set_edit(True)
        model.select_id("one")
        model.pick()
        self.assertEqual(self.cells(model)["one"], (0, 0))
        self.assertTrue(model.carry("down"))
        self.assertEqual(self.cells(model)["one"], (0, 1))

    def test_up_is_the_same_the_other_way(self):
        model = self.model()
        model.set_edit(True)
        model.select_id("seven")
        model.pick()
        self.assertEqual(self.cells(model)["seven"], (0, 1))
        self.assertTrue(model.carry("up"))
        self.assertEqual(self.cells(model)["seven"], (0, 0))


    def test_a_carried_tile_keeps_being_carried_across_a_repack(self):
        model = self.model()
        model.set_edit(True)
        model.pick()
        model.repack()
        self.assertEqual(model.picked, "one")

    def test_leaving_edit_puts_down_whatever_was_being_carried(self):
        model = self.model()
        model.set_edit(True)
        model.pick()
        model.set_edit(False)
        self.assertIsNone(model.picked)
        self.assertFalse(model.edit)

    def test_hiding_and_putting_back_are_the_same_press(self):
        model = self.model()
        model.set_edit(True)
        model.select_id("three")
        self.assertTrue(model.hide())
        self.assertTrue(model.hidden("three"))
        # Still on the page while editing, so there is nothing to go and find.
        self.assertIn("three", self.order(model))
        model.select_id("three")
        self.assertTrue(model.hide())
        self.assertFalse(model.hidden("three"))
        model.set_edit(False)
        self.assertIn("three", self.order(model))

    def test_a_hidden_tile_is_gone_once_editing_stops(self):
        model = self.model()
        model.set_edit(True)
        model.select_id("three")
        model.hide()
        model.set_edit(False)
        self.assertNotIn("three", self.order(model))

    def test_a_tile_is_widened_and_clamped_to_the_page(self):
        model = self.model()
        model.set_edit(True)
        model.pick()
        self.assertTrue(model.resize(1, 0))
        self.assertEqual(model.tiles[0]["size"], (2, 1))
        for _ in range(10):
            model.resize(1, 0)
        self.assertEqual(model.tiles[0]["size"], (6, 1))
        # And it says so rather than pretending, so a tick can fire.
        self.assertFalse(model.resize(1, 0))

    def test_the_order_is_still_written_in_names(self):
        # A cell is what a *moved* tile gets; the order is still what every
        # other tile on the page is held by, and it is still names - which is
        # what makes a page survive a tile being added to the config.
        model = self.model()
        model.set_edit(True)
        model.pick()
        model.carry("right")
        plan = model.layout["group"]
        self.assertEqual(plan["order"][:2], ["one", "two"])
        self.assertTrue(all(isinstance(name, str)
                            for name in plan["order"]))

    def test_reset_hands_the_page_back_to_the_config(self):
        model = self.model()
        model.set_edit(True)
        model.pick()
        model.carry("right")
        model.hide()
        self.assertTrue(model.restore())
        self.assertEqual(self.order(model)[:2], ["one", "two"])
        self.assertFalse(model.restore())

    def test_the_tree_itself_is_never_rearranged(self):
        # The arrangement lives in `layout` and is applied when a page is
        # shown, so walking away and back reads the same - and the config's
        # own order is still there to be reset to.
        model = self.model()
        before = [item["id"] for item in model.root[0]["items"]]
        model.set_edit(True)
        model.pick()
        model.carry("right")
        self.assertEqual([item["id"] for item in model.root[0]["items"]],
                         before)

    def test_the_payload_says_what_is_being_rearranged(self):
        model = self.model()
        model.set_edit(True)
        model.pick()
        model.select_id("two")
        model.hide()
        state = model.view_state(True)
        self.assertTrue(state["edit"])
        rows = dict((row["id"], row) for row in state["items"])
        self.assertTrue(rows["two"]["off"])
        self.assertNotIn("off", rows["one"])


class APageIsAGridNotAList(unittest.TestCase):
    """A tile can be put in a cell with nothing leading to it.

    The thing reordering could not express. With one tile on a page there is
    no order to be third in, so there was no way to put it anywhere but the
    top left - and a page of readings drawn over a game is exactly the case
    where where it sits is the whole point.
    """

    def model(self, count=1):
        rows = [{"label": "Tile %d" % number, "action": "nop"}
                for number in range(1, count + 1)]
        return MenuModel(build([{"label": "Group", "items": rows}],
                               settings={}), columns=6)

    def cells(self, model):
        return dict((tile["item"]["id"], tile["at"]) for tile in model.tiles)

    def carry(self, model, *directions):
        for direction in directions:
            self.assertTrue(model.carry(direction), direction)

    def test_the_only_tile_on_a_page_reaches_the_middle_of_it(self):
        model = self.model()
        model.set_edit(True)
        model.pick()
        self.carry(model, "right", "right", "right",
                   "down", "down", "down")
        self.assertEqual(self.cells(model)["tile-1"], (3, 3))

    def test_a_page_grows_a_row_at_a_time_and_no_faster(self):
        # One press past the bottom, which is what makes an empty cell below
        # everything reachable at all - and a held direction cannot fling a
        # tile somewhere a thumb has to walk all the way back from.
        model = self.model()
        model.set_edit(True)
        model.pick()
        self.assertEqual(model.rows, 1)
        self.assertTrue(model.carry("down"))
        self.assertEqual(model.rows, 2)
        self.assertEqual(self.cells(model)["tile-1"], (0, 1))

    def test_where_it_was_put_is_where_it_is_when_you_come_back(self):
        model = self.model(3)
        model.set_edit(True)
        model.select_id("tile-2")
        model.pick()
        self.carry(model, "down", "right", "right")
        model.pick()
        model.set_edit(False)
        model.repack()
        self.assertEqual(self.cells(model)["tile-2"], (3, 1))

    def test_the_cell_is_what_is_written_down(self):
        model = self.model(2)
        model.set_edit(True)
        model.pick()
        self.carry(model, "down", "right")
        self.assertEqual(model.layout["group"]["at"], {"tile-1": (1, 1)})

    def test_a_tile_will_not_walk_onto_one_somebody_placed(self):
        # It would lose the cell in `place` and be handed back to the flow,
        # which is a press that goes somewhere nobody pointed at.
        model = self.model(2)
        model.set_edit(True)
        model.select_id("tile-1")
        model.pick()
        self.carry(model, "down", "down")
        model.pick()
        model.select_id("tile-2")
        model.pick()
        self.carry(model, "down")
        self.assertEqual(self.cells(model)["tile-2"], (0, 1))
        self.assertFalse(model.carry("down"))

    def test_an_unpinned_tile_is_walked_through_rather_than_into(self):
        # The other half of the same rule: a tile in the flow flows out of the
        # way, which is how a tile is moved into the middle of a row.
        model = self.model(3)
        model.set_edit(True)
        model.select_id("tile-3")
        model.pick()
        self.carry(model, "left", "left")
        cells = self.cells(model)
        self.assertEqual(cells["tile-3"], (0, 0))
        self.assertEqual(cells["tile-1"], (1, 0))
        self.assertEqual(cells["tile-2"], (2, 0))

    def test_reset_takes_the_cells_back_too(self):
        model = self.model(2)
        model.set_edit(True)
        model.pick()
        self.carry(model, "down", "right")
        self.assertTrue(model.restore())
        self.assertEqual(self.cells(model)["tile-1"], (0, 0))


class APageThatIsAlsoAScreenHasALastRow(unittest.TestCase):
    """A menu page has no bottom, and one drawn over a screen does.

    The menu is where a page is arranged, so the menu is what has to stop a
    tile being carried off the end of a page it is only half the surface for.
    Without this a tile walked past the last row went somewhere worse than
    nowhere: `place` pulled it back onto the last row, and where something was
    already pinned there it lost the cell and fell into the flow - a press
    that teleports a tile to the top left.
    """

    def model(self, count=3, limit=4):
        rows = [{"label": "Tile %d" % number, "action": "nop"}
                for number in range(1, count + 1)]
        return MenuModel(
            build([{"id": "page", "label": "Page", "items": rows}],
                  settings={}),
            columns=6, page_rows={"page": limit})

    def cells(self, model):
        return dict((tile["item"]["id"], tile["at"]) for tile in model.tiles)

    def carry_down(self, model, times):
        for _ in range(times):
            if not model.carry("down"):
                return False
        return True

    def test_a_tile_stops_on_the_last_row(self):
        model = self.model(limit=4)
        model.set_edit(True)
        model.pick()
        self.assertTrue(self.carry_down(model, 3))
        self.assertEqual(self.cells(model)["tile-1"], (0, 3))
        self.assertFalse(model.carry("down"))

    def test_a_tall_tile_stops_where_its_own_bottom_does(self):
        model = self.model(limit=4)
        model.set_edit(True)
        model.pick()
        model.resize(0, 1)
        self.assertTrue(self.carry_down(model, 2))
        self.assertEqual(self.cells(model)["tile-1"], (0, 2))
        self.assertFalse(model.carry("down"))

    def test_a_page_with_no_last_row_still_grows(self):
        # Every other page. One row past the bottom each press, forever.
        model = MenuModel(
            build([{"id": "page", "label": "Page",
                    "items": [{"label": "One", "action": "nop"}]}],
                  settings={}),
            columns=6)
        model.set_edit(True)
        model.pick()
        self.assertTrue(self.carry_down(model, 20))
        self.assertEqual(self.cells(model)["one"], (0, 20))

    def test_the_menu_places_the_page_the_way_the_screen_will(self):
        # One answer rather than two that can disagree: a layout hand-edited
        # past the end reads the same in the place it is arranged and the
        # place it is drawn.
        model = self.model(limit=4)
        model.layout["page"] = {"order": [], "hidden": [], "span": {},
                                "at": {"tile-1": (0, 40)}}
        model.repack()
        self.assertEqual(self.cells(model)["tile-1"], (0, 3))

    def test_only_the_named_page_is_bounded(self):
        model = MenuModel(
            build([{"id": "page", "label": "Page",
                    "items": [{"label": "One", "action": "nop"}]},
                   {"id": "other", "label": "Other",
                    "items": [{"label": "Two", "action": "nop"}]}],
                  settings={}),
            columns=6, page_rows={"page": 2})
        model.enter_group(1)
        model.set_edit(True)
        model.pick()
        self.assertTrue(self.carry_down(model, 9))
        self.assertEqual(self.cells(model)["two"], (0, 9))


class APinIsClampedNeverLost(unittest.TestCase):
    """The cost of a cell over a name, and what keeps the cost small.

    A layout written as names survives a different column count; one written
    as cells does not, and that was the argument for reordering. It is
    answered here rather than given up: a pin off the edge of a narrower page
    is pulled back onto it, so the arrangement adapts instead of breaking.
    """

    def page(self, count=2):
        rows = [{"label": "Tile %d" % number, "action": "nop"}
                for number in range(1, count + 1)]
        return build([{"label": "Group", "items": rows}],
                     settings={})[0]["items"]

    def test_a_pin_past_the_last_column_is_pulled_back_onto_the_page(self):
        plan = {"order": [], "hidden": [], "span": {}, "at": {"tile-1": (5, 0)}}
        tiles, _ = place(self.page(), 3, plan)
        cells = dict((tile["item"]["id"], tile["at"]) for tile in tiles)
        self.assertEqual(cells["tile-1"], (2, 0))

    def test_a_wide_tile_is_clamped_by_its_own_width(self):
        plan = {"order": [], "hidden": [],
                "span": {"tile-1": (3, 1)}, "at": {"tile-1": (4, 0)}}
        tiles, _ = place(self.page(), 6, plan)
        cells = dict((tile["item"]["id"], tile["at"]) for tile in tiles)
        self.assertEqual(cells["tile-1"], (3, 0))

    def test_two_pins_over_one_cell_leave_the_first_where_it_is(self):
        # Only a hand-edited file or two of those clamps can make this, and
        # the page still has to be a packing rather than a pile.
        plan = {"order": [], "hidden": [], "span": {},
                "at": {"tile-1": (0, 0), "tile-2": (0, 0)}}
        tiles, _ = place(self.page(), 6, plan)
        cells = dict((tile["item"]["id"], tile["at"]) for tile in tiles)
        self.assertEqual(cells["tile-1"], (0, 0))
        self.assertNotEqual(cells["tile-2"], (0, 0))

    def test_a_pin_is_placed_before_anything_flows_into_it(self):
        # Pins first, or where a tile ended up would depend on what else
        # happened to be on the page.
        plan = {"order": [], "hidden": [], "span": {}, "at": {"tile-2": (0, 0)}}
        tiles, _ = place(self.page(), 6, plan)
        cells = dict((tile["item"]["id"], tile["at"]) for tile in tiles)
        self.assertEqual(cells["tile-2"], (0, 0))
        self.assertEqual(cells["tile-1"], (1, 0))

    def test_the_rows_a_page_needs_count_a_pin_below_everything(self):
        plan = {"order": [], "hidden": [], "span": {}, "at": {"tile-1": (0, 3)}}
        _, rows = place(self.page(), 6, plan)
        self.assertEqual(rows, 4)

    def test_a_pinned_tile_is_neither_moved_by_a_break_nor_moves_one(self):
        items = build([{"label": "Group", "items": [
            {"label": "One", "action": "nop"},
            {"control": "row_break"},
            {"label": "Two", "action": "nop"},
        ]}], settings={})[0]["items"]
        plan = {"order": [], "hidden": [], "span": {}, "at": {"one": (0, 4)}}
        tiles, _ = place(items, 6, plan)
        cells = dict((tile["item"]["id"], tile["at"]) for tile in tiles)
        self.assertEqual(cells["one"], (0, 4))
        # The break's floor counts only what has flowed, and nothing had.
        self.assertEqual(cells["two"], (0, 0))


class PlaceTests(unittest.TestCase):
    """Where the tiles go. First fit, in the order the page holds them."""

    def page(self, *spans):
        return build([
            {"label": "T%d" % n, "action": "nop", "span": list(span)}
            for n, span in enumerate(spans)
        ], columns=6)

    def boxes(self, items, columns=6):
        tiles, rows = place(items, columns)
        return [(t["item"]["id"], t["at"], t["size"]) for t in tiles], rows

    def test_tiles_fill_a_row_before_starting_the_next(self):
        boxes, rows = self.boxes(self.page((3, 1), (2, 1), (1, 1)))
        self.assertEqual([b[1] for b in boxes], [(0, 0), (3, 0), (5, 0)])
        self.assertEqual(rows, 1)

    def test_a_tile_that_will_not_fit_starts_a_new_row(self):
        boxes, rows = self.boxes(self.page((4, 1), (3, 1)))
        self.assertEqual([b[1] for b in boxes], [(0, 0), (0, 1)])
        self.assertEqual(rows, 2)

    def test_a_small_tile_backfills_the_hole_a_big_one_left(self):
        # The order is authorial, so the packing keeps it rather than being
        # rewritten to avoid holes.
        boxes, rows = self.boxes(self.page((4, 1), (4, 1), (2, 1)))
        self.assertEqual([b[1] for b in boxes], [(0, 0), (0, 1), (4, 0)])

    def test_a_tall_tile_holds_the_cells_under_it(self):
        boxes, rows = self.boxes(self.page((2, 2), (2, 1), (2, 1), (2, 1)))
        self.assertEqual([b[1] for b in boxes],
                         [(0, 0), (2, 0), (4, 0), (2, 1)])
        self.assertEqual(rows, 2)

    def test_a_break_ends_the_row(self):
        items = build([
            {"label": "A", "action": "nop"},
            {"control": "row_break"},
            {"label": "B", "action": "nop"},
        ])
        boxes, rows = self.boxes(items)
        self.assertEqual([b[0] for b in boxes], ["a", "b"])
        self.assertEqual([b[1] for b in boxes], [(0, 0), (0, 1)])

    def test_a_break_is_never_drawn(self):
        items = build([{"control": "row_break"},
                       {"label": "A", "action": "nop"}])
        boxes, rows = self.boxes(items)
        self.assertEqual([b[0] for b in boxes], ["a"])

    def test_nothing_ever_overlaps_or_leaves_the_page(self):
        # The invariant, over every shape worth generating rather than one
        # example of it.
        import itertools
        for columns in (3, 4, 6):
            for shape in itertools.product((1, 2, 3), repeat=4):
                items = build([
                    {"label": "T%d" % n, "action": "nop",
                     "span": [min(w, columns), 1 + (n % 2)]}
                    for n, w in enumerate(shape)
                ], columns=columns)
                tiles, rows = place(items, columns)
                filled = set()
                for tile in tiles:
                    x, y = tile["at"]
                    w, h = tile["size"]
                    self.assertGreaterEqual(x, 0)
                    self.assertGreaterEqual(y, 0)
                    self.assertLessEqual(x + w, columns)
                    self.assertLessEqual(y + h, rows)
                    for down in range(h):
                        for across in range(w):
                            cell = (x + across, y + down)
                            self.assertNotIn(cell, filled)
                            filled.add(cell)


class StepTests(unittest.TestCase):
    """Which tile is that way. `snap.choose`, over rectangles in cells.

    Golden fixtures rather than examples: `snap.PERPENDICULAR_WEIGHT` was
    measured on windows, which are large and sparse, and these are small and
    touching. What the bias is worth here is what these say.
    """

    def model(self, *spans):
        # One group holding them all: a flat list of verbs is a bar of chips
        # now, and a chip is a page of one.
        items = build([{"label": "Page", "items": [
            {"label": "T%d" % n, "action": "nop", "span": list(span)}
            for n, span in enumerate(spans)
        ]}], columns=6)
        return MenuModel(items, columns=6)

    def walk(self, model, *directions):
        out = []
        for direction in directions:
            model.step(direction)
            out.append(model.selected)
        return out

    def test_a_row_of_three_walks_across_and_stops(self):
        #  [ t0  t0 ][ t1 ][ t2  t2  t2 ]
        model = self.model((2, 1), (1, 1), (3, 1))
        self.assertEqual(self.walk(model, "right", "right", "right"),
                         ["t1", "t2", "t2"])
        self.assertEqual(self.walk(model, "left", "left", "left"),
                         ["t1", "t0", "t0"])

    def test_a_tall_tile_beside_two_short_ones(self):
        #  [ t0 t0 ][ t1 t1 t1 t1 ]
        #  [ t0 t0 ][ t2 t2 t2 t2 ]
        model = self.model((2, 2), (4, 1), (4, 1))
        self.assertEqual(self.walk(model, "right"), ["t1"])
        self.assertEqual(self.walk(model, "down"), ["t2"])
        self.assertEqual(self.walk(model, "left"), ["t0"])

    def test_a_ragged_last_row_is_still_reachable(self):
        #  [ t0 t0 t0 ][ t1 t1 t1 ]
        #  [ t2 ]
        model = self.model((3, 1), (3, 1), (1, 1))
        model.select_id("t1")
        self.assertEqual(self.walk(model, "down"), ["t2"])
        self.assertEqual(self.walk(model, "up"), ["t0"])

    def test_straight_ahead_beats_nearer_but_crooked(self):
        #  [ t0 ][ t1 ][ t2 t2 t2 t2 ]
        #  [ t3 t3 t3 t3 t3 t3 ]
        model = self.model((1, 1), (1, 1), (4, 1), (6, 1))
        model.select_id("t0")
        self.assertEqual(self.walk(model, "right"), ["t1"])

    def test_the_selection_only_ever_lands_on_a_tile_that_is_here(self):
        model = self.model((2, 1), (1, 1), (3, 2), (2, 1))
        names = set(t["item"]["id"] for t in model.tiles)
        for direction in ("up", "down", "left", "right") * 4:
            model.step(direction)
            self.assertIn(model.selected, names)


class HeadTests(unittest.TestCase):
    """The read-only grid above the bar."""

    def test_a_cell_prints_a_time_it_renders_itself(self):
        head = build_head([{"format": "%H:%M", "span": [2, 1]}])
        model = MenuModel([], head=head)
        cells, rows = model.head_state()
        self.assertRegex(cells[0]["t"], r"^\d{2}:\d{2}$")
        self.assertEqual(cells[0]["w"], 2)

    def test_a_cell_prints_the_last_thing_its_command_said(self):
        head = build_head([{"from": "weather",
                            "empty": "Weather unavailable"}])
        model = MenuModel([], head=head)
        cells, _ = model.head_state({head[0]["id"]: "Istanbul 22C"})
        self.assertEqual(cells[0]["t"], "Istanbul 22C")

    def test_a_cell_with_no_answer_yet_says_so_rather_than_nothing(self):
        # A blank cell in a grid reads as a drawing fault rather than as a
        # command that has not answered.
        head = build_head([{"from": "weather",
                            "empty": "Weather unavailable"}])
        model = MenuModel([], head=head)
        cells, _ = model.head_state()
        self.assertEqual(cells[0]["t"], "Weather unavailable")

    def test_a_cell_can_carry_a_second_line_under_the_first(self):
        head = build_head([{"format": "%H:%M", "under": "%A",
                            "span": [2, 2]}])
        model = MenuModel([], head=head)
        cells, rows = model.head_state()
        self.assertRegex(cells[0]["t"], r"^\d{2}:\d{2}$")
        self.assertEqual(cells[0]["u"], time.strftime("%A"))
        self.assertEqual(rows, 2)

    def test_a_cell_with_one_line_carries_no_second_one(self):
        # Left off the wire rather than sent empty: `u !== undefined` is the
        # whole of the panel's test for whether a cell stacks.
        head = build_head([{"format": "%H:%M"}])
        cells, _ = MenuModel([], head=head).head_state()
        self.assertNotIn("u", cells[0])

    def test_a_line_can_be_a_command_as_easily_as_a_time(self):
        # The same two sources at every level: a cell that could print a
        # command's answer while the line under it could only print a time
        # would be two grammars wearing one name.
        head = build_head([{"format": "%H:%M",
                            "over": {"from": "id -un", "ttl": 0}}])
        model = MenuModel([], head=head)
        cells, _ = model.head_state({"h-m.over": "fishy"})
        self.assertEqual(cells[0]["o"], "fishy")

    def test_a_small_line_is_named_after_the_cell_it_is_in(self):
        # So the daemon has somewhere to file what each command said without
        # the config having to name three things to get one clock.
        head = build_head([{"id": "clock", "format": "%H:%M",
                            "over": {"from": "id -un"},
                            "under": {"from": "hostname"}}])
        self.assertEqual([line["id"] for line in head_sources(head[0])],
                         ["clock.over", "clock.under"])

    def test_only_the_lines_that_are_commands_are_asked_for(self):
        head = build_head([{"from": "weather", "under": "%A"}])
        self.assertEqual([line["id"] for line in head_sources(head[0])],
                         ["weather"])

    def test_a_line_prints_one_thing_or_the_other(self):
        with self.assertRaises(MenuError):
            build_head([{"format": "%H:%M",
                         "under": {"format": "%A", "from": "x"}}])
        with self.assertRaises(MenuError):
            build_head([{"format": "%H:%M", "under": {"ttl": 60}}])
        with self.assertRaises(MenuError):
            build_head([{"format": "%H:%M", "under": 3}])

    def test_a_cell_prints_one_thing_or_the_other(self):
        with self.assertRaises(MenuError):
            build_head([{"format": "%H:%M", "from": "weather"}])
        with self.assertRaises(MenuError):
            build_head([{"span": [1, 1]}])

    def test_a_ttl_is_a_number_of_seconds_that_is_not_negative(self):
        self.assertEqual(build_head([{"from": "x", "ttl": 900}])[0]["ttl"],
                         900.0)
        with self.assertRaises(MenuError):
            build_head([{"from": "x", "ttl": -1}])
        with self.assertRaises(MenuError):
            build_head([{"from": "x", "ttl": "soon"}])

    def test_a_command_that_names_itself_cannot_collide(self):
        with self.assertRaises(MenuError):
            build_head([{"from": "x", "id": "w"}, {"from": "y", "id": "w"}])

    def test_a_name_shaped_like_markup_is_not_drawn_as_markup(self):
        # A command's output is text from outside this machine on its way to
        # a Text, the same as a device description.
        head = build_head([{"from": "weather"}])
        model = MenuModel([], head=head)
        cells, _ = model.head_state({head[0]["id"]: "<img src=x> 22C"})
        self.assertNotIn("<", cells[0]["t"])


class ViewTests(unittest.TestCase):
    def setUp(self):
        self.model = MenuModel(build(GROUPED))

    def test_the_payload_carries_what_the_plugin_draws(self):
        state = self.model.view_state(True)
        self.assertTrue(state["open"])
        self.assertEqual(state["title"], ROOT_TITLE)
        self.assertEqual(state["sel"], "terminal")
        self.assertEqual(state["depth"], 0)
        self.assertEqual(state["g"], 0)
        self.assertEqual(state["cols"], 6)
        self.assertEqual([g["l"] for g in state["groups"]], ["Apps", "Audio"])
        self.assertEqual([row["l"] for row in state["items"]],
                         ["Terminal", "Browser"])

    def test_every_tile_carries_its_cells(self):
        rows = self.model.view_state(True)["items"]
        self.assertEqual([(r["x"], r["y"], r["w"], r["h"]) for r in rows],
                         [(0, 0, 1, 1), (1, 0, 1, 1)])

    def test_every_tile_carries_the_name_a_layout_knows_it_by(self):
        rows = self.model.view_state(True)["items"]
        self.assertEqual([row["id"] for row in rows], ["terminal", "browser"])

    def test_a_listed_row_is_ticked_by_the_listing_that_made_it(self):
        item = build([LISTED])[0]
        item["items"] = listed(item, ["* Speakers\t1\ta", "Television\t7\tb"], 8)
        model = MenuModel([item])
        model.repack()
        rows = model.view_state(True)["items"]
        self.assertEqual([row["on"] for row in rows], [True, False])

    def test_a_row_a_listing_could_not_fill_is_neither_ticked_nor_untidy(self):
        item = build([LISTED])[0]
        item["items"] = listed(item, [], 8)
        model = MenuModel([item])
        model.repack()
        row = model.view_state(True)["items"][0]
        self.assertEqual(row["l"], "No outputs found")
        self.assertNotIn("on", row)

    def test_only_submenu_rows_are_flagged_as_drilling_in(self):
        self.model.group_move(1)
        rows = self.model.view_state(True)["items"]
        self.assertEqual([row["sub"] for row in rows],
                         [False, False, True, False])

    def test_a_row_is_ticked_when_what_it_sets_is_already_in_force(self):
        # Nobody but the daemon can answer that, so the payload only carries
        # it for the rows it was answered for.
        rows = self.model.view_state(True, lambda action: True)["items"]
        self.assertEqual([row.get("on") for row in rows], [True, True])
        rows = self.model.view_state(True, lambda action: None)["items"]
        self.assertEqual([row.get("on") for row in rows], [None, None])

    def test_a_stepping_row_prints_the_number_instead_of_its_detail(self):
        # "Faster" says nothing about where faster has got to, and every step
        # of a number is equally not-the-case, so a tick cannot say it either.
        self.model.group_move(1)
        rows = self.model.view_state(
            True, None, lambda action: "9 notches a second"
        )["items"]
        self.assertEqual(rows[1]["d"], "9 notches a second")
        rows = self.model.view_state(True, None, lambda action: "")["items"]
        self.assertEqual(rows[1]["d"], "hands the pad back")

    def test_nothing_is_ticked_when_nobody_is_asked(self):
        rows = self.model.view_state(True)["items"]
        self.assertNotIn("on", rows[0])

    def test_a_submenu_reports_its_own_rows(self):
        self.model.group_move(1)
        self.model.select_id("devices")
        self.model.press()
        state = self.model.view_state(True)
        self.assertEqual(state["title"], "Devices")
        self.assertEqual(state["depth"], 1)
        self.assertEqual([row["l"] for row in state["items"]],
                         ["Speakers", "Microphone"])


class ClockTests(unittest.TestCase):
    """The menu carries the day and the time.

    It sat on the bar for a while, next to the menu's own badge, and read as
    clutter there: the bar's left end is the menu's place.
    """

    def test_the_head_of_the_menu_carries_the_day_and_the_hour(self):
        clock = MenuModel([], "Go", "%A %H:%M").view_state(True)["clock"]
        self.assertRegex(clock, r"^[A-Za-z]+ \d{2}:\d{2}$")

    def test_an_empty_format_means_no_clock(self):
        self.assertEqual(MenuModel([], "Go", "").view_state(True)["clock"], "")
