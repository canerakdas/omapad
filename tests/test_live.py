"""What the machine is doing, without a machine.

The parsers are pure functions over canned output, which is the whole reason
they are pure: `pactl`, a backlight and an MPRIS player are three things a
test cannot have, and three things this module must never run itself.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad import config as config_module
from omapad import live as live_module
from omapad.live import Live, LiveError, READINGS


VOLUME = [
    "Volume: front-left: 39321 /  60% / -13.31 dB,   "
    "front-right: 39321 /  60% / -13.31 dB",
    "        balance 0.00",
]

MEDIA = ('{"hasPlayer":true,"hasMedia":true,"playing":true,'
         '"identity":"Spotify","desktopEntry":"spotify",'
         '"title":"Sunset Roller","artist":"My Jinji","album":"",'
         '"artUrl":"","canGoNext":true,"canGoPrevious":false,'
         '"canTogglePlaying":true}')

NOTHING = ('{"hasPlayer":false,"hasMedia":false,"playing":false,'
           '"identity":"","title":"","artist":"","canGoNext":false,'
           '"canGoPrevious":false,"canTogglePlaying":false}')


def shipped():
    missing = os.path.join(tempfile.gettempdir(), "omapad-no-such-config")
    return config_module.load(path=missing, mapping=missing,
                              settings=missing, layout=missing)


class NothingHereRunsACommand(unittest.TestCase):
    def test_the_module_does_not_import_subprocess(self):
        # A press must never wait on `pactl`. This module returns the string
        # to run and the daemon submits it to the worker every other slow
        # thing goes through; importing subprocess here is how that stops
        # being true without anybody noticing.
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "omapad", "live.py")
        with open(path) as handle:
            source = handle.read()
        for word in ("import subprocess", "import os", "popen", "system("):
            self.assertNotIn(word, source)


class ParserTests(unittest.TestCase):
    def test_volume_takes_the_first_percentage(self):
        self.assertAlmostEqual(live_module.parse_volume(VOLUME), 0.60)

    def test_a_volume_past_full_draws_full(self):
        # A sink may be turned past 100% and a bar cannot draw it; saying full
        # beats lying about the shape of its own travel.
        self.assertEqual(
            live_module.parse_volume(["Volume: front-left: 0 / 140% / 0 dB"]),
            1.0)

    def test_nothing_said_is_not_silence(self):
        # None rather than zero: a helper that answered nothing must not
        # overwrite a good value with a wrong one.
        self.assertIsNone(live_module.parse_volume([]))
        self.assertIsNone(live_module.parse_volume(["Failure: no such sink"]))
        self.assertIsNone(live_module.parse_mute([]))
        self.assertIsNone(live_module.parse_brightness(["nonsense"]))
        self.assertIsNone(live_module.parse_media([]))

    def test_mute_reads_the_word_pactl_prints(self):
        self.assertTrue(live_module.parse_mute(["Mute: yes"]))
        self.assertFalse(live_module.parse_mute(["Mute: no"]))

    def test_vrr_is_on_at_any_of_the_three_values_that_are_not_off(self):
        # Hyprland's 1, 2 and 3 are all a rate that may follow the game; the
        # switch only says whether one of them is in force.
        self.assertFalse(live_module.parse_vrr(["int: 0", "set: true"]))
        self.assertTrue(live_module.parse_vrr(["int: 2", "set: true"]))
        self.assertIsNone(live_module.parse_vrr(["no such option"]))

    def test_brightness_is_one_number(self):
        self.assertAlmostEqual(live_module.parse_brightness(["95"]), 0.95)
        self.assertAlmostEqual(live_module.parse_brightness([" 5% "]), 0.05)

    def test_media_is_mapped_rather_than_passed_through(self):
        # An MPRIS field name is not a payload field name: a rename upstream
        # must not silently become a rename on the wire.
        found = live_module.parse_media([MEDIA])
        self.assertEqual(found, {
            "player": True, "playing": True, "title": "Sunset Roller",
            "artist": "My Jinji", "next": True, "previous": False,
        })

    def test_nothing_playing_is_still_an_answer(self):
        found = live_module.parse_media([NOTHING])
        self.assertFalse(found["player"])
        self.assertEqual(found["title"], "")

    def test_output_that_is_not_json_leaves_the_last_answer_standing(self):
        self.assertIsNone(live_module.parse_media(["{oh dear"]))
        self.assertIsNone(live_module.parse_media(["[1, 2]"]))


class RequestTests(unittest.TestCase):
    def test_a_number_takes_a_step_or_a_value(self):
        self.assertEqual(live_module.request("volume", "up"), ("step", 1))
        self.assertEqual(live_module.request("volume", "down"), ("step", -1))
        self.assertEqual(live_module.request("volume", "0.4"), ("set", 0.4))

    def test_a_value_out_of_range_is_clamped_rather_than_refused(self):
        self.assertEqual(live_module.request("volume", "9"), ("set", 1.0))

    def test_a_switch_takes_the_three_words_a_switch_takes(self):
        self.assertEqual(live_module.request("mute", "toggle"),
                         ("toggle", None))
        self.assertEqual(live_module.request("mute", "on"), ("set", True))

    def test_the_transport_takes_its_own_three(self):
        self.assertEqual(live_module.request("media", "next"),
                         ("do", "next"))
        with self.assertRaises(LiveError) as caught:
            live_module.request("media", "skip")
        self.assertIn("playPause", str(caught.exception))

    def test_a_reading_nobody_has_is_named(self):
        with self.assertRaises(LiveError) as caught:
            live_module.request("loudness", "up")
        self.assertIn("loudness", str(caught.exception))
        self.assertIn("volume", str(caught.exception))


class CommandTests(unittest.TestCase):
    def live(self):
        return Live(shipped())

    def test_a_write_puts_the_value_where_the_template_says(self):
        live = self.live()
        command, value = live.apply("volume", ("set", 0.6))
        self.assertIn(" 60%", command)
        self.assertEqual(value, 0.6)

    def test_a_step_needs_something_to_step_from(self):
        # Nothing has answered yet, so there is no number: stepping from a
        # guess would jump the volume to somewhere nobody asked for.
        live = self.live()
        self.assertEqual(live.apply("volume", ("step", 1)), (None, None))
        live.took("volume", VOLUME, live.generation)
        command, value = live.apply("volume", ("step", 1))
        self.assertAlmostEqual(value, 0.65)
        self.assertIn(" 65%", command)

    def test_the_end_of_the_travel_sends_nothing_and_says_so(self):
        live = self.live()
        live.took("volume", ["Volume: 100%"], live.generation)
        self.assertEqual(live.apply("volume", ("step", 1)), (None, 1.0))

    def test_a_transport_direction_the_player_closed_sends_nothing(self):
        live = self.live()
        live.took("media", [MEDIA], live.generation)
        self.assertEqual(live.apply("media", ("do", "previous")),
                         (None, False))
        command, _ = live.apply("media", ("do", "next"))
        self.assertEqual(command, "omarchy-shell media next")

    def test_a_reading_this_machine_does_not_have_asks_nothing(self):
        config = shipped()
        config.live_reads["volume"] = ""
        config.live_writes["volume"] = ""
        live = Live(config)
        self.assertEqual(live.ask("volume"), (None, 0))
        self.assertEqual(live.apply("volume", ("set", 0.5)), (None, None))


class StaleReadTests(unittest.TestCase):
    """The one bug here that would look like a flicker nobody can reproduce."""

    def test_an_answer_older_than_the_last_write_is_thrown_away(self):
        live = Live(shipped())
        live.took("volume", VOLUME, live.generation)
        command, generation = live.ask("volume")
        # The press lands while that read is still in flight.
        live.apply("volume", ("set", 0.9))
        self.assertAlmostEqual(live.value("volume"), 0.9)
        # ...and the read comes back with what it was before.
        self.assertFalse(live.took("volume", VOLUME, generation))
        self.assertAlmostEqual(live.value("volume"), 0.9)

    def test_an_answer_from_after_the_write_is_taken(self):
        live = Live(shipped())
        live.apply("volume", ("set", 0.9))
        _, generation = live.ask("volume")
        self.assertTrue(live.took("volume", VOLUME, generation))
        self.assertAlmostEqual(live.value("volume"), 0.60)

    def test_a_reading_that_said_nothing_keeps_its_last_value(self):
        # A tile that empties because a helper was slow is worse than one
        # that is a second stale, and a helper that hangs must never be able
        # to empty the HUD.
        live = Live(shipped())
        live.took("volume", VOLUME, live.generation)
        self.assertFalse(live.took("volume", [], live.generation))
        self.assertAlmostEqual(live.value("volume"), 0.60)


class ShippedCommandTests(unittest.TestCase):
    def test_every_reading_ships_a_way_to_ask_and_a_way_to_set(self):
        config = shipped()
        for name in READINGS:
            self.assertTrue(config.live_reads[name], name)
            self.assertTrue(config.live_writes[name], name)
            self.assertIn("%1", config.live_writes[name], name)

    def test_volume_does_not_go_through_the_helper_that_raises_the_osd(self):
        # The whole argument for putting volume on a tile: the helper always
        # ends in `omarchy-osd`, so every press would raise Omarchy's own
        # overlay over the tile showing the same number.
        config = shipped()
        for command in (config.live_reads["volume"],
                        config.live_writes["volume"]):
            self.assertNotIn("omarchy-audio-output-volume", command)
            self.assertIn("omarchy-audio-output-sink", command)

    def test_brightness_keeps_its_helper_and_silences_its_osd(self):
        # DDC, Apple displays and backlights are three code paths omapad must
        # not reimplement, and this helper offers the flag.
        config = shipped()
        self.assertIn("--no-osd", config.live_writes["brightness"])

    def test_a_write_template_with_nowhere_to_put_the_value_is_named(self):
        with self.assertRaises(config_module.ConfigError) as caught:
            config_module.Config({"live": {"volume_set": "pactl thing"}})
        self.assertIn("volume_set", str(caught.exception))

    def test_a_timing_of_zero_is_named(self):
        with self.assertRaises(config_module.ConfigError) as caught:
            config_module.Config({"live": {"poll_ms": 0}})
        self.assertIn("poll_ms", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
