"""What a press sounds like: what is said, and what is deliberately silent."""

import os
import re
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad import config as config_module, sound

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOUNDS = os.path.join(ROOT, "assets", "sounds")


def build(data=None):
    return config_module.Config(data or {})


class SayTests(unittest.TestCase):
    def setUp(self):
        self.model = sound.SoundModel(build())

    def test_a_cue_counts_up_from_one(self):
        # The panel plays any sequence number it has not seen, so a shell
        # that connects mid-session must never be handed the 0 a fresh model
        # would otherwise send - it would announce a press that happened
        # before the shell came up.
        self.assertTrue(self.model.say("move"))
        self.assertEqual(self.model.seq, 1)
        self.assertTrue(self.model.say("commit"))
        self.assertEqual(self.model.seq, 2)
        self.assertEqual(self.model.cue, "commit")

    def test_a_word_that_is_not_one_of_the_five_says_nothing(self):
        # Called from the input path, where a sound is the least important
        # thing happening: it declines rather than raises.
        self.assertFalse(self.model.say("texture"))
        self.assertFalse(self.model.say(""))
        self.assertEqual(self.model.seq, 0)

    def test_the_held_effect_has_no_sound_and_cannot_gain_one(self):
        # A motor can hold a texture under a slider for a second and a half.
        # A speaker holding a note for the same second and a half is the
        # loudest thing in the room.
        self.assertNotIn("texture", sound.VOICES)

    def test_the_vocabulary_is_the_motor_s_plus_the_two_it_cannot_say(self):
        # `move` is quiet enough to repeat, which a motor is not: one that
        # ticked on every step of a held direction buzzes the whole way down
        # a list. `back` is lower and softer than a commit, which a motor
        # cannot be either - it can be shorter or weaker, and that says "less
        # happened" rather than "this went the other way".
        from omapad import rumble
        played = set(name for name in rumble.VOCABULARY
                     if not rumble.VOCABULARY[name]["held"])
        self.assertTrue(played.issubset(set(sound.VOICES)),
                        "a word the motor plays that the speakers cannot")
        self.assertEqual(set(sound.VOICES) - played, {"move", "back"})

    def test_the_volume_rides_every_cue(self):
        # There is no heartbeat on this socket, so a panel that had missed
        # the one line carrying the volume would play at the wrong one until
        # the next restart.
        model = sound.SoundModel(build({"sound": {"volume": 0.25}}))
        model.say("tick")
        self.assertEqual(model.view_state()["gain"], 0.25)
        self.assertEqual(model.view_state()["c"], "tick")


class ConfigTests(unittest.TestCase):
    def test_it_ships_off(self):
        # The one answer this program gives to the room rather than to the
        # hands, so it is switched on by whoever decides that.
        # The shipped file alone: `load(path)` would merge this machine's own
        # settings.toml over it, and a suite that asked what *this* desk had
        # chosen from the pad is a suite that passes until somebody turns the
        # sound on.
        missing = os.path.join(tempfile.gettempdir(), "omapad-no-such-config")
        shipped = config_module.load(
            path=os.path.join(ROOT, "config", "config.toml"),
            mapping=missing, settings=missing, layout=missing)
        self.assertFalse(shipped.sound_enabled)

    def test_a_volume_out_of_range_is_named(self):
        with self.assertRaises(config_module.ConfigError) as caught:
            build({"sound": {"volume": 4}})
        self.assertIn("sound.volume", str(caught.exception))

    def test_a_pack_that_is_not_a_directory_is_named(self):
        # `omapad check` names it, rather than four cues silently going
        # missing on the next press.
        with self.assertRaises(config_module.ConfigError) as caught:
            build({"sound": {"pack": os.path.join(ROOT, "README.md")}})
        self.assertIn("sound.pack", str(caught.exception))

    def test_a_pack_is_expanded_here_because_the_shell_cannot(self):
        config = build({"sound": {"pack": "~"}})
        self.assertEqual(config.sound_pack, os.path.expanduser("~"))

    def test_both_halves_are_reachable_from_the_pad(self):
        self.assertIn("sound", config_module.CHOSEN)
        self.assertIn("sound_volume", config_module.CHOSEN)


class ShippedFilesTests(unittest.TestCase):
    """The four files are generated and checked in, like the badges."""

    def test_every_voice_has_a_file(self):
        for name in sound.VOICES:
            self.assertTrue(
                os.path.isfile(os.path.join(SOUNDS, "%s.wav" % name)),
                "%s has no sound - run python3 assets/sounds.py" % name)

    def test_nothing_is_shipped_that_no_cue_names(self):
        extra = set(
            name[:-len(".wav")] for name in os.listdir(SOUNDS)
            if name.endswith(".wav")
        ) - set(sound.VOICES)
        self.assertEqual(extra, set(), "a file no cue plays")

    def test_they_are_short_enough_to_be_a_cue(self):
        # A sound longer than the gap between two presses is a chord rather
        # than an answer. The move is the one that has to be shortest: it
        # fires six times a second while somebody crosses a page.
        limits = {"move": 25, "back": 90, "tick": 40, "edge": 70,
                  "commit": 120}
        for name in sound.VOICES:
            with wave.open(os.path.join(SOUNDS, "%s.wav" % name)) as handle:
                ms = handle.getnframes() * 1000.0 / handle.getframerate()
            self.assertLessEqual(ms, limits[name], "%s is %d ms" % (name, ms))

    def test_the_panel_loads_exactly_what_the_daemon_can_say(self):
        # The one place a new voice has to be named that no Python import
        # would ever notice: a cue the bank does not load is a press that
        # ticks the hands and says nothing to the room.
        with open(os.path.join(ROOT, "shell-plugin", "SoundBank.qml")) as f:
            text = f.read()
        found = re.search(r"property var voices: \[(.*?)\]", text)
        self.assertIsNotNone(found, "SoundBank.qml names no voices")
        named = [word.strip().strip('"')
                 for word in found.group(1).split(",")]
        self.assertEqual(named, list(sound.VOICES))

    def test_they_match_what_the_generator_writes_now(self):
        # The same promise `tests/test_assets.py` makes about the badges: a
        # number changed in `assets/sounds.py` and not re-run is a file that
        # no longer says what the source says.
        sys.path.insert(0, os.path.join(ROOT, "assets"))
        try:
            import sounds as generator
        finally:
            sys.path.pop(0)
        for name in sound.VOICES:
            with open(os.path.join(SOUNDS, "%s.wav" % name), "rb") as handle:
                on_disk = handle.read()
            fresh = os.path.join(
                os.environ.get("TMPDIR", "/tmp"), "omapad-%s.wav" % name)
            generator.write(fresh, generator.render(generator.VOICES[name]))
            try:
                with open(fresh, "rb") as handle:
                    self.assertEqual(
                        handle.read(), on_disk,
                        "%s.wav is not what assets/sounds.py writes now" % name)
            finally:
                os.unlink(fresh)

    def test_the_generator_and_the_daemon_name_the_same_four(self):
        sys.path.insert(0, os.path.join(ROOT, "assets"))
        try:
            import sounds as generator
        finally:
            sys.path.pop(0)
        self.assertEqual(sorted(generator.VOICES), sorted(sound.VOICES))


if __name__ == "__main__":
    unittest.main()
