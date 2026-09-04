"""The controller menu's tree, its navigation, and the payload it draws from."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad import actions, config as config_module
from omapad.menu import MenuError, MenuModel, ROOT_TITLE, build, listed

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
                                       settings=missing)
        self.assertTrue(build(config.menu_items))

    def test_apps_leads_with_what_a_sofa_reaches_for(self):
        # The couch's short list, in the order it is reached for: the game,
        # the people you are playing with, the music, the television. What
        # comes after them is the desktop's own list, and last of all
        # everything installed - which no controller menu should try to be.
        missing = os.path.join(tempfile.gettempdir(),
                               "omapad-no-such-config")
        config = config_module.load(path=missing, mapping=missing,
                                       settings=missing)
        apps = [row for row in config.menu_items if row.get("label") == "Apps"]
        self.assertEqual(len(apps), 1)
        labels = [row["label"] for row in apps[0]["items"]]
        self.assertEqual(
            labels[:4], ["Steam", "Discord", "Spotify", "YouTube"]
        )
        self.assertEqual(labels[-1], "All apps")


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
        self.model = MenuModel(build(SAMPLE))

    def test_it_starts_at_the_top_of_the_root_level(self):
        self.assertEqual(self.model.title, ROOT_TITLE)
        self.assertEqual(self.model.index, 0)
        self.assertEqual(self.model.depth, 0)

    def test_moving_wraps(self):
        self.model.move(-1)
        self.assertEqual(self.model.index, len(SAMPLE) - 1)
        self.model.move(1)
        self.assertEqual(self.model.index, 0)

    def test_pressing_a_submenu_drills_in_and_takes_its_label_as_the_title(self):
        self.model.move(1)
        kind, item = self.model.press()
        self.assertEqual(kind, "enter")
        self.assertEqual(self.model.title, "Audio")
        self.assertEqual(self.model.depth, 1)
        self.assertEqual(self.model.index, 0)

    def test_pressing_a_leaf_hands_back_the_row(self):
        kind, item = self.model.press()
        self.assertEqual(kind, "run")
        self.assertIsInstance(item["action"], actions.ExecAction)
        self.assertFalse(item["repeat"])

    def test_back_restores_the_row_you_left(self):
        self.model.move(1)
        self.model.press()
        self.model.move(1)
        self.assertTrue(self.model.back())
        self.assertEqual(self.model.index, 1)
        self.assertEqual(self.model.title, ROOT_TITLE)

    def test_back_at_the_root_reports_there_is_nowhere_to_go(self):
        self.assertFalse(self.model.back())

    def test_select_names_a_row_outright(self):
        # The pointer hovers a row and names it; there is no direction to it.
        self.model.select(3)
        self.assertEqual(self.model.index, 3)

    def test_select_clamps_instead_of_wrapping(self):
        # A pointer is aiming somewhere; a selection that wraps across the
        # fold reads as a mistake.
        self.model.select(-1)
        self.assertEqual(self.model.index, 0)
        self.model.select(len(SAMPLE) + 10)
        self.assertEqual(self.model.index, len(SAMPLE) - 1)

    def test_select_works_inside_a_submenu(self):
        self.model.move(1)
        self.model.press()
        self.model.select(1)
        self.assertEqual(self.model.index, 1)
        self.assertEqual(self.model.title, "Audio")

    def test_select_on_an_empty_menu_is_safe(self):
        model = MenuModel([])
        model.select(3)
        self.assertEqual(model.index, 0)
        self.assertEqual(model.press(), ("none", None))

    def test_reset_climbs_all_the_way_out(self):
        self.model.move(1)
        self.model.press()
        self.model.reset()
        self.assertEqual(self.model.depth, 0)
        self.assertEqual(self.model.index, 0)
        self.assertEqual(self.model.title, ROOT_TITLE)

    def test_choosing_a_listed_row_moves_the_tick_to_it(self):
        # The command that changes the output is let go of rather than waited
        # for, so re-reading the listing here would race it. The press is the
        # answer until the page is entered again.
        item = build([LISTED])[0]
        item["items"] = listed(item, ["* Speakers\t1\ta", "Television\t7\tb"], 8)
        model = MenuModel([item])
        model.press()
        model.move(1)
        picked = model.current
        model.choose(picked)
        self.assertEqual([row["on"] for row in model.items], [False, True])

    def test_an_empty_menu_navigates_without_raising(self):
        model = MenuModel([])
        model.move(1)
        self.assertEqual(model.press(), ("none", None))
        self.assertFalse(model.back())


class ViewTests(unittest.TestCase):
    def setUp(self):
        self.model = MenuModel(build(SAMPLE))

    def test_the_payload_carries_what_the_plugin_draws(self):
        state = self.model.view_state(True)
        self.assertTrue(state["open"])
        self.assertEqual(state["title"], ROOT_TITLE)
        self.assertEqual(state["sel"], 0)
        self.assertEqual(state["depth"], 0)
        self.assertEqual([row["l"] for row in state["items"]],
                         ["Terminal", "Audio", "Game mode", "Volume up",
                          "Xbox labels"])

    def test_a_listed_row_is_ticked_by_the_listing_that_made_it(self):
        item = build([LISTED])[0]
        item["items"] = listed(item, ["* Speakers\t1\ta", "Television\t7\tb"], 8)
        model = MenuModel([item])
        self.assertTrue(model.view_state(True)["items"][0]["sub"])
        model.press()
        rows = model.view_state(True)["items"]
        self.assertEqual([row["on"] for row in rows], [True, False])

    def test_a_row_a_listing_could_not_fill_is_neither_ticked_nor_untidy(self):
        item = build([LISTED])[0]
        item["items"] = listed(item, [], 8)
        model = MenuModel([item])
        model.press()
        row = model.view_state(True)["items"][0]
        self.assertEqual(row["l"], "No outputs found")
        self.assertNotIn("on", row)

    def test_only_submenu_rows_are_flagged_as_drilling_in(self):
        rows = self.model.view_state(True)["items"]
        self.assertEqual([row["sub"] for row in rows],
                         [False, True, False, False, False])

    def test_a_row_is_ticked_when_what_it_sets_is_already_in_force(self):
        # Nobody but the daemon can answer that, so the payload only carries
        # it for the rows it was answered for.
        rows = self.model.view_state(True, lambda action: True)["items"]
        self.assertEqual([row.get("on") for row in rows],
                         [True, None, True, True, True])
        rows = self.model.view_state(True, lambda action: None)["items"]
        self.assertEqual([row.get("on") for row in rows], [None] * 5)

    def test_a_stepping_row_prints_the_number_instead_of_its_detail(self):
        # "Faster" says nothing about where faster has got to, and every step
        # of a number is equally not-the-case, so a tick cannot say it either.
        rows = self.model.view_state(
            True, None, lambda action: "9 notches a second"
        )["items"]
        self.assertEqual(rows[2]["d"], "9 notches a second")
        rows = self.model.view_state(True, None, lambda action: "")["items"]
        self.assertEqual(rows[2]["d"], "hands the pad back")

    def test_nothing_is_ticked_when_nobody_is_asked(self):
        rows = self.model.view_state(True)["items"]
        self.assertNotIn("on", rows[0])

    def test_a_submenu_reports_its_own_rows(self):
        self.model.move(1)
        self.model.press()
        state = self.model.view_state(True)
        self.assertEqual(state["title"], "Audio")
        self.assertEqual(state["depth"], 1)
        self.assertEqual([row["l"] for row in state["items"]],
                         ["Volume up", "Mute"])


if __name__ == "__main__":
    unittest.main(verbosity=2)


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
