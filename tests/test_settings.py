"""The settings the pad can change about itself, and where they are kept."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad import actions, config as config_module

MISSING = os.path.join(tempfile.gettempdir(), "omapad-no-such-config")


def shipped():
    return config_module.load(path=MISSING, mapping=MISSING, settings=MISSING)


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
