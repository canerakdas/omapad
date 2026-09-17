"""The settings the pad can change about itself, and where they are kept."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad import actions, config as config_module

MISSING = os.path.join(tempfile.gettempdir(), "omapad-no-such-config")


def shipped():
    return config_module.load(path=MISSING, mapping=MISSING,
                              settings=MISSING, layout=MISSING)


class RequestTests(unittest.TestCase):
    def test_a_choice_takes_its_own_words(self):
        self.assertEqual(
            config_module.setting_request("layout", "xbox"), ("set", "xbox")
        )

    def test_a_word_no_setting_holds_is_named_rather_than_ignored(self):
        # The whole point of parsing this when the config is read: a row that
        # silently does nothing is the failure `omapad check` exists to
        # catch.
        with self.assertRaises(config_module.SettingError) as caught:
            config_module.setting_request("layout", "switch")
        self.assertIn("nintendo", str(caught.exception))

    def test_an_unknown_setting_is_named_too(self):
        with self.assertRaises(config_module.SettingError):
            config_module.setting_request("colour", "red")

    def test_every_kind_can_be_stepped(self):
        # So one button can walk a setting the menu offers as a list of rows.
        for name in ("layout", "rumble", "rumble_strength"):
            self.assertEqual(config_module.setting_request(name, "next"),
                             ("step", 1))
            self.assertEqual(config_module.setting_request(name, "prev"),
                             ("step", -1))

    def test_a_switch_takes_on_off_and_toggle(self):
        self.assertEqual(config_module.setting_request("rumble", "on"),
                         ("set", True))
        self.assertEqual(config_module.setting_request("rumble", "off"),
                         ("set", False))
        self.assertEqual(config_module.setting_request("rumble", "toggle"),
                         ("toggle", None))

    def test_a_number_is_clamped_to_what_the_motor_has(self):
        self.assertEqual(
            config_module.setting_request("rumble_strength", "4"), ("set", 1.0)
        )


class IdleConfigTests(unittest.TestCase):
    def test_the_hold_on_the_screen_ships_with_an_end(self):
        self.assertGreater(shipped().idle_awake, 0.0)

    def test_a_wait_that_is_not_a_length_of_time_is_named(self):
        with self.assertRaises(config_module.ConfigError) as caught:
            config_module.Config({"idle": {"awake_ms": -1}})
        self.assertIn("idle.awake_ms", str(caught.exception))


class TurnGearingConfigTests(unittest.TestCase):
    """The two numbers that gear a knob, and what `[menu]` refuses."""

    def test_both_ship_and_the_floor_is_the_slower_on_a_fine_control(self):
        config = shipped()
        self.assertGreater(config.menu_turn_degrees, 0.0)
        # Volume is twenty steps: the range alone would put them 13.5 degrees
        # apart, which is the wobble this floor exists to be above.
        self.assertGreater(config.menu_turn_step_degrees,
                           config.menu_turn_degrees * 0.05)

    def test_the_shipped_gesture_is_the_one_the_drawing_already_was(self):
        self.assertEqual(shipped().menu_turn, "aim")

    def test_a_gesture_no_ring_has_is_named(self):
        with self.assertRaises(config_module.ConfigError) as caught:
            config_module.Config({"menu": {"turn": "spin"}})
        self.assertIn("menu.turn", str(caught.exception))

    def test_each_gesture_carries_its_own_grip(self):
        config = shipped()
        self.assertLess(config.menu_aim_grip, config.menu_turn_grip)

    def test_a_grip_that_is_not_a_share_of_the_stick_is_named(self):
        for key in ("turn_grip", "aim_grip"):
            for value in (0, 1.0, -0.2):
                with self.assertRaises(config_module.ConfigError) as caught:
                    config_module.Config({"menu": {key: value}})
                self.assertIn("menu.%s" % key, str(caught.exception))

    def test_a_return_speed_that_is_not_a_rate_is_named(self):
        for value in (0, -1.0):
            with self.assertRaises(config_module.ConfigError) as caught:
                config_module.Config({"menu": {"turn_return": value}})
            self.assertIn("menu.turn_return", str(caught.exception))

    def test_a_gearing_that_is_not_an_angle_is_named(self):
        for key in ("turn_degrees", "turn_step_degrees"):
            with self.assertRaises(config_module.ConfigError) as caught:
                config_module.Config({"menu": {key: 0}})
            self.assertIn("menu.%s" % key, str(caught.exception))


class TriggerRestConfigTests(unittest.TestCase):
    """The floor under an analog trigger, and what `[device]` refuses."""

    def test_the_shipped_floor_clears_a_pad_that_rests_off_its_minimum(self):
        # A Beitong KP40A in XInput mode rests ABS_RZ at 47 of 255. The
        # shipped answer has to be above that or the sweep runs on its own on
        # a pad this project names in its own config.
        self.assertGreater(shipped().trigger_rest, 47 / 255.0)

    def test_a_floor_outside_the_travel_is_named(self):
        for value in (-0.1, 1.0, 2.0):
            with self.assertRaises(config_module.ConfigError) as caught:
                config_module.Config({"device": {"trigger_rest": value}})
            self.assertIn("device.trigger_rest", str(caught.exception))

    def test_a_floor_over_the_release_point_is_named(self):
        # A trigger held as a button and reading as not pulled at the same
        # time: the sweep would stop halfway in while its layer stayed open.
        with self.assertRaises(config_module.ConfigError) as caught:
            config_module.Config({"device": {"trigger_rest": 0.4,
                                             "trigger_release": 0.3}})
        self.assertIn("device.trigger_rest", str(caught.exception))
        self.assertIn("device.trigger_release", str(caught.exception))


class RepeatRampConfigTests(unittest.TestCase):
    """The three tables that say how a held direction accelerates."""

    def test_every_walk_on_the_pad_ships_with_one(self):
        config = shipped()
        for ramp, over in ((config.menu_repeat_ramp,
                            config.menu_repeat_ramp_time),
                           (config.osk_repeat_ramp,
                            config.osk_repeat_ramp_time),
                           (config.traverse_repeat_ramp,
                            config.traverse_repeat_ramp_time)):
            self.assertGreater(ramp, 1.0)
            self.assertGreater(over, 0.0)

    def test_a_ramp_that_would_slow_a_walk_down_is_named(self):
        for table in ("menu", "osk", "traverse"):
            with self.assertRaises(config_module.ConfigError) as caught:
                config_module.Config({table: {"repeat_ramp": 0.5}})
            self.assertIn("%s.repeat_ramp" % table, str(caught.exception))

    def test_and_a_ramp_time_that_is_not_a_length_of_time(self):
        with self.assertRaises(config_module.ConfigError) as caught:
            config_module.Config({"osk": {"repeat_ramp_ms": -1}})
        self.assertIn("osk.repeat_ramp_ms", str(caught.exception))


class HoldAssistConfigTests(unittest.TestCase):
    """What `[confirm]` refuses, so `omapad check` names it rather than a press."""

    def test_a_scale_outside_the_gesture_is_named(self):
        for value in (0.4, 2.5, 0):
            with self.assertRaises(config_module.ConfigError) as caught:
                config_module.Config({"confirm": {"scale": value}})
            self.assertIn("confirm.scale", str(caught.exception))

    def test_and_a_slack_that_is_not_a_length_of_time(self):
        with self.assertRaises(config_module.ConfigError) as caught:
            config_module.Config({"confirm": {"slack_ms": -1}})
        self.assertIn("confirm.slack_ms", str(caught.exception))

    def test_the_shipped_answers_are_the_gesture_as_it_was(self):
        # Both ship neutral: every hold is the length its binding was written
        # at, and letting go is how you back out.
        config = shipped()
        self.assertEqual(config.confirm_scale, 1.0)
        self.assertEqual(config.confirm_slack_ms, 0)


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.config = shipped()

    def set(self, name, word):
        return self.config.set_setting(
            name, config_module.setting_request(name, word)
        )

    def test_a_setting_reaches_the_attribute_the_daemon_reads(self):
        self.assertEqual(self.set("layout", "playstation"), "playstation")
        self.assertEqual(self.config.layout_name, "playstation")
        self.assertEqual(self.config.badge_layout("xbox"), "playstation")

    def test_stepping_a_choice_walks_it_and_comes_back_round(self):
        choices = config_module.CHOSEN["layout"]["choices"]
        first = self.config.layout_name
        seen = [self.set("layout", "next") for _ in choices]
        self.assertEqual(seen[-1], first)
        self.assertEqual(sorted(seen), sorted(choices))

    def test_a_switch_toggles(self):
        before = self.config.rumble_enabled
        self.assertEqual(self.set("rumble", "toggle"), not before)
        self.assertEqual(self.set("rumble", "toggle"), before)

    def test_a_number_steps_and_stops_at_the_end_of_its_range(self):
        self.set("rumble_strength", "0.95")
        self.assertEqual(self.set("rumble_strength", "up"), 1.0)
        self.assertEqual(self.set("rumble_strength", "up"), 1.0)
        self.set("rumble_strength", "0.0")
        self.assertEqual(self.set("rumble_strength", "down"), 0.0)

    def test_the_two_speeds_step_and_reach_the_daemon(self):
        # Both are read every tick rather than at startup, so the attribute is
        # the whole of applying them.
        self.assertEqual(self.set("scroll_speed", "12"), 12.0)
        self.assertEqual(self.config.scroll_speed, 12.0)
        self.assertEqual(self.set("scroll_speed", "up"), 13.0)
        self.assertEqual(self.set("pointer_speed", "up"),
                         shipped().pointer_speed + 100.0)
        self.assertEqual(self.set("pointer_speed", "40"), 200.0)  # clamped

    def test_the_two_dead_zones_step_and_stop_short_of_the_whole_stick(self):
        # Half the travel is as far as the ceiling goes: past it there is not
        # enough stick left on the far side to aim with, and a whole one would
        # divide apply_curve by nothing.
        self.assertEqual(self.set("left_deadzone", "up"),
                         round(shipped().left_deadzone + 0.01, 3))
        self.assertEqual(self.config.stick_deadzone("left"),
                         round(shipped().left_deadzone + 0.01, 3))
        self.assertEqual(self.set("right_deadzone", "1"), 0.5)  # clamped
        self.assertEqual(self.config.stick_deadzone("right"), 0.5)
        self.assertEqual(self.set("left_deadzone", "0"), 0.0)
        self.assertEqual(self.set("left_deadzone", "down"), 0.0)

    def test_a_stepping_row_says_where_the_number_is(self):
        self.set("scroll_speed", "9")
        self.assertEqual(
            config_module.setting_text("scroll_speed", 9.0),
            "9 notches a second",
        )
        self.assertEqual(
            config_module.setting_text("pointer_speed", 1100.0),
            "1100 pixels a second",
        )
        self.assertEqual(config_module.setting_text("rumble_strength", 0.2), "20%")
        self.assertEqual(config_module.setting_text("left_deadzone", 0.1), "10%")
        # A choice or a switch is ticked instead, so it has nothing to add.
        self.assertEqual(config_module.setting_text("layout", "xbox"), "")
        self.assertEqual(config_module.setting_text("rumble", True), "")

    def test_the_few_placed_settings_walk_stops_and_the_rest_do_not(self):
        """Which settings are places to be, and which are amounts to cover.

        A control drawn in segments has to have few enough of them to count
        from a sofa. Twenty-one is not few, and a pointer speed is a distance
        to cross rather than a handful of places to stand.
        """
        placed, swept = set(), set()
        for name, spec in config_module.CHOSEN.items():
            if spec["kind"] != "number":
                continue
            (placed if spec.get("stops") else swept).add(name)
        self.assertEqual(placed, {"radius", "motion", "hold_scale"})
        for name in placed:
            self.assertLessEqual(len(config_module.CHOSEN[name]["stops"]), 7)
        self.assertEqual(swept, {"sound_volume", "rumble_strength",
                                 "scroll_speed", "pointer_speed",
                                 "left_deadzone", "right_deadzone"})

    def test_motion_is_worded_because_off_is_the_stop_that_matters(self):
        # It exists for somebody who cannot read a moving screen, and the stop
        # that answers them should say so rather than print 0%.
        self.assertEqual(config_module.setting_text("motion", 0.0), "Off")
        self.assertEqual(config_module.setting_text("motion", 1.0), "Full")
        self.assertEqual(self.set("motion", "down"), 0.75)
        self.assertEqual(config_module.setting_text("motion", 0.75), "Most")

    def test_hold_time_keeps_its_number_because_it_is_an_amount(self):
        # Seven segments and a percentage: a hold at 150% is half again as
        # long as the one the binding was written at, and a word standing
        # there would say less than the quantity does.
        self.assertEqual(config_module.setting_text("hold_scale", 1.5), "150%")
        self.assertEqual(self.set("hold_scale", "down"), 0.75)
        self.assertEqual(config_module.setting_text("hold_scale", 0.75), "75%")

    def test_a_corner_walks_a_ladder_rather_than_a_range(self):
        # A corner is a size, and every size on these surfaces climbs by the
        # silver ratio. Six presses cross the whole of it, and each one is a
        # corner you can tell from the last - which a tenth of a step is not.
        self.assertEqual(self.config.ui_radius, 1.0)
        self.assertEqual(self.set("radius", "up"), 1.414)
        self.assertEqual(self.set("radius", "up"), 1.414)   # the top stop
        for expected in (1.0, 0.707, 0.5, 0.0):
            self.assertEqual(self.set("radius", "down"), expected)
        # Zero is the stop under the bottom of the ladder, and it is square:
        # no amount of dividing reaches it, so it is a stop rather than a sum.
        self.assertEqual(self.set("radius", "down"), 0.0)
        self.assertEqual(self.set("radius", "up"), 0.5)

    def test_a_corner_somebody_wrote_by_hand_steps_from_where_it_is(self):
        # Not moved onto the ladder and then stepped: one press from 1.2 is
        # the stop above it, rather than a number 1.2 was rounded to first.
        self.config.ui_radius = 1.2
        self.assertEqual(self.set("radius", "up"), 1.414)

    def test_a_corner_bar_is_drawn_by_its_stops(self):
        # The stops are a proportion apart, so a bar that spaced them by their
        # arithmetic would bunch the bottom half into its first third.
        spec = config_module.CHOSEN["radius"]
        self.assertEqual(config_module.setting_share(spec, 0.0), 0.0)
        self.assertEqual(config_module.setting_share(spec, 1.0), 0.75)
        self.assertEqual(config_module.setting_share(spec, 1.414), 1.0)
        # And a plain number is still measured along its range.
        speed = config_module.CHOSEN["scroll_speed"]
        self.assertAlmostEqual(
            config_module.setting_share(speed, 20.5), 0.5, places=2)

    def test_a_stop_says_which_corner_it_is_rather_than_a_percentage(self):
        # A ladder has somewhere to be rather than an amount to be at, and
        # "141%" is a number you have to divide before it says anything -
        # against what? The segments under it already say how far along.
        self.assertEqual(config_module.setting_text("radius", 1.0),
                         "The desktop's")
        self.assertEqual(config_module.setting_text("radius", 0.0), "Square")
        self.assertEqual(config_module.setting_text("radius", 1.414), "Round")
        # And every stop has one, in the order somebody walking them reads.
        spec = config_module.CHOSEN["radius"]
        self.assertEqual(
            [spec["words"][stop] for stop in spec["stops"]],
            ["Square", "Barely", "Slight", "The desktop's", "Round"])

    def test_a_number_written_between_two_stops_still_says_itself(self):
        self.assertEqual(config_module.setting_text("radius", 1.2), "1.2")

    def test_the_hold_time_steps_between_a_half_and_a_double(self):
        # The ends are the gesture's: under a half a tap and a hold stop being
        # different presses, and over a double a hold is one nobody reaches
        # the end of.
        self.assertEqual(self.config.confirm_scale, 1.0)
        self.assertEqual(self.set("hold_scale", "down"), 0.75)
        self.assertEqual(self.set("hold_scale", "0.1"), 0.5)   # clamped
        self.assertEqual(self.set("hold_scale", "down"), 0.5)
        self.assertEqual(self.set("hold_scale", "9"), 2.0)     # and the other end
        self.assertEqual(config_module.setting_text("hold_scale", 0.5), "50%")

    def test_the_first_start_is_a_mark_the_pad_writes_down(self):
        # Not a preference anybody browses: it is in this table because
        # settings.toml is where the pad writes things down, and a mark it
        # could not write is a first start that happens every morning.
        self.assertTrue(self.config.menu_first_run)
        self.assertEqual(self.set("first_run", "off"), False)
        self.assertEqual(self.config.chosen, {"first_run": False})

    def test_the_mode_at_the_next_start_is_chosen_from_the_pad(self):
        # The one setting here that is about a start other than this one, so
        # what proves it took is what was written down, not what the daemon
        # is doing a moment later.
        self.assertEqual(self.config.start_mode, "desktop")
        self.assertEqual(self.set("start_mode", "game"), "game")
        self.assertEqual(self.config.start_mode, "game")
        self.assertEqual(self.config.chosen, {"start_mode": "game"})
        # Two of them, so one button walks between them as well as two rows.
        self.assertEqual(self.set("start_mode", "toggle"), "desktop")

    def test_a_mode_the_daemon_cannot_come_up_in_is_refused(self):
        with self.assertRaises(config_module.SettingError):
            config_module.setting_request("start_mode", "couch")

    def test_hiding_the_pointer_is_switched_from_the_pad(self):
        # Read at every press rather than at startup, so the attribute is the
        # whole of applying it - there is no branch in `apply_setting`.
        self.assertIs(self.config.hide_pointer, True)
        self.assertIs(self.set("hide_pointer", "off"), False)
        self.assertIs(self.config.hide_pointer, False)
        self.assertIs(self.set("hide_pointer", "toggle"), True)
        self.assertEqual(self.config.chosen, {"hide_pointer": True})

    def test_only_what_was_changed_is_remembered(self):
        # settings.toml holds what the pad chose, not a frozen copy of every
        # default - which is what would make improving the defaults pointless.
        self.assertEqual(self.config.chosen, {})
        self.set("rumble", "off")
        self.assertEqual(self.config.chosen, {"rumble": False})


class FileTests(unittest.TestCase):
    def load_with(self, text, user=""):
        directory = tempfile.mkdtemp(prefix="omapad-settings-")
        path = os.path.join(directory, "settings.toml")
        with open(path, "w") as handle:
            handle.write(text)
        user_path = MISSING
        if user:
            user_path = os.path.join(directory, "config.toml")
            with open(user_path, "w") as handle:
                handle.write(user)
        return config_module.load(
            layout=MISSING,
            path=user_path, mapping=MISSING, settings=path
        )

    def test_what_was_chosen_survives_being_written_and_read_back(self):
        config = shipped()
        for name, word in (("layout", "xbox"), ("rumble", "off"),
                           ("rumble_strength", "0.35")):
            config.set_setting(name, config_module.setting_request(name, word))
        again = self.load_with(config_module.render_settings(config.chosen))
        self.assertEqual(again.layout_name, "xbox")
        self.assertFalse(again.rumble_enabled)
        self.assertEqual(again.rumble_strong, 0.35)
        self.assertEqual(again.chosen, config.chosen)

    def test_it_wins_over_the_config_file(self):
        # What "I just changed it" means: the file that was written a second
        # ago is the one that answers.
        config = self.load_with('layout = "playstation"\n',
                                user='[device]\nlayout = "nintendo"\n')
        self.assertEqual(config.layout_name, "playstation")

    def test_a_dead_zone_that_leaves_no_stick_is_named(self):
        # `apply_curve` divides by what is left of the travel, so this is the
        # difference between `omapad check` naming the key and the daemon
        # dividing by zero under a thumb.
        for key in ("left_deadzone", "right_deadzone"):
            with self.assertRaises(config_module.ConfigError) as caught:
                self.load_with("", user="[pointer]\n%s = 1.0\n" % key)
            self.assertIn("pointer.%s" % key, str(caught.exception))

    def test_a_dead_zone_written_under_its_old_name_still_answers(self):
        # Both halves of the rename: a config file that still says what the
        # role's zone was, and a settings.toml the menu wrote before the
        # setting moved to the stick. Neither is a typo to reject - one is
        # hand-written, the other was chosen from the sofa.
        config = self.load_with(
            "", user="[pointer]\ndeadzone = 0.2\n\n[scroll]\ndeadzone = 0.3\n"
        )
        self.assertEqual(config.stick_deadzone("left"), 0.2)
        self.assertEqual(config.stick_deadzone("right"), 0.3)
        config = self.load_with("pointer_deadzone = 0.25\n")
        self.assertEqual(config.stick_deadzone("left"), 0.25)
        self.assertEqual(config.chosen, {"left_deadzone": 0.25})

    def test_the_mode_chosen_from_the_pad_is_the_one_the_next_start_reads(self):
        # The menu writes a flat name; `[mode] start` is what comes up in it.
        config = self.load_with('start_mode = "game"\n',
                                user='[mode]\nstart = "desktop"\n')
        self.assertEqual(config.start_mode, "game")

    def test_a_setting_that_does_not_exist_is_named(self):
        with self.assertRaises(config_module.ConfigError) as caught:
            self.load_with('colour = "red"\n')
        self.assertIn("colour", str(caught.exception))


class ActionTests(unittest.TestCase):
    def test_a_binding_is_validated_where_it_is_written(self):
        action = actions.parse("pad:layout=xbox")
        self.assertEqual(action.setting, "layout")
        self.assertEqual(action.request, ("set", "xbox"))
        with self.assertRaises(actions.ActionError):
            actions.parse("pad:layout=switch")
        with self.assertRaises(actions.ActionError):
            actions.parse("pad:layout")

    def test_a_row_knows_whether_it_is_already_the_answer(self):
        class Ctx:
            class daemon:
                config = shipped()

        ctx = Ctx()
        ctx.daemon.config.set_setting("layout", ("set", "xbox"))
        self.assertTrue(actions.parse("pad:layout=xbox").state(ctx))
        self.assertFalse(actions.parse("pad:layout=nintendo").state(ctx))
        # A step is not a value, so nothing about it is in force.
        self.assertIsNone(actions.parse("pad:layout=next").state(ctx))
        # And almost nothing else answers the question at all.
        self.assertIsNone(actions.parse("exec:true").state(ctx))


class BadgeStyleTests(unittest.TestCase):
    """The style is chosen from the sofa, so it is held to the same rules."""

    def test_the_pad_can_ask_for_either_style(self):
        for style in ("filled", "stencil"):
            self.assertEqual(
                config_module.setting_request("badge_style", style),
                ("set", style),
            )

    def test_a_style_nothing_draws_is_named_rather_than_ignored(self):
        with self.assertRaises(config_module.SettingError) as caught:
            config_module.setting_request("badge_style", "outline")
        self.assertIn("stencil", str(caught.exception))

    def test_a_bad_style_in_the_config_names_the_key(self):
        # `omapad check` has to say where the mistake is, not fail at the
        # first badge someone looks at.
        with self.assertRaises(config_module.ConfigError) as caught:
            config_module.Config({"ui": {"badge_style": "outline"}})
        self.assertIn("ui.badge_style", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
