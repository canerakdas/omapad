"""What a press sounds like: what is said, and what is deliberately silent."""

import math
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

    def test_the_vocabulary_is_the_motor_s_plus_what_it_cannot_say(self):
        # `move` is quiet enough to repeat, which a motor is not: one that
        # ticked on every step of a held direction buzzes the whole way down
        # a list. `back` is lower and softer than a commit, which a motor
        # cannot be either - it can be shorter or weaker, and that says "less
        # happened" rather than "this went the other way". `show` is the
        # back upside down, and `next` / `prev` are a direction, which is a
        # pitch and not a buzz.
        from omapad import rumble
        played = set(name for name in rumble.VOCABULARY
                     if not rumble.VOCABULARY[name]["held"])
        self.assertTrue(played.issubset(set(sound.VOICES)),
                        "a word the motor plays that the speakers cannot")
        self.assertEqual(set(sound.VOICES) - played,
                         {"move", "prev", "next", "show", "back"})

    def test_what_repeats_under_a_held_button_is_never_felt(self):
        # A shoulder held down turns page after page the way a held D-pad
        # walks tile after tile; a motor ticking at each is a buzz.
        self.assertEqual(set(sound.UNFELT), {"move", "prev", "next"})
        self.assertTrue(set(sound.UNFELT).issubset(set(sound.VOICES)))

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
    """The files are generated and checked in, like the badges."""

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
        limits = {"move": 25, "prev": 45, "next": 45, "show": 110,
                  "back": 90, "tick": 40, "edge": 70, "commit": 120}
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

    def test_the_generator_and_the_daemon_name_the_same_five(self):
        sys.path.insert(0, os.path.join(ROOT, "assets"))
        try:
            import sounds as generator
        finally:
            sys.path.pop(0)
        self.assertEqual(sorted(generator.VOICES), sorted(sound.VOICES))


def _generator():
    sys.path.insert(0, os.path.join(ROOT, "assets"))
    try:
        import sounds as generator
    finally:
        sys.path.pop(0)
    return generator


class LoudnessTests(unittest.TestCase):
    """How loud each cue is, measured the way a broadcaster measures it."""

    def setUp(self):
        self.generator = _generator()
        self.files = {}
        for name in sound.VOICES:
            self.files[name] = self.generator.read(
                os.path.join(SOUNDS, "%s.wav" % name))

    def test_the_meter_is_bs1770_where_the_standard_prints_it(self):
        # The standard's table is for 48 kHz and the files are not, so the
        # meter builds its filters from the analog design; at 48 kHz that
        # has to land on the printed coefficients or it is some other meter.
        shelf, lowcut = self.generator.k_weighting(48000)
        expected = (
            ((1.53512485958697, -2.69169618940638, 1.19839281085285),
             (1.0, -1.69065929318241, 0.73248077421585)),
            ((1.0, -2.0, 1.0),
             (1.0, -1.99004745483398, 0.99007225036621)),
        )
        for got, want in zip((shelf, lowcut), expected):
            for side in range(2):
                for a, b in zip(got[side], want[side]):
                    self.assertAlmostEqual(a, b, places=12)

    def test_a_full_scale_sine_reads_what_the_standard_says(self):
        # BS.1770's own check: a 997 Hz sine at full scale in one channel
        # reads -3.01.
        rate = 48000
        samples = [math.sin(2.0 * math.pi * 997.0 * n / rate)
                   for n in range(int(rate * self.generator.BLOCK))]
        measured = self.generator.loudness(samples, rate, heard=False)
        self.assertAlmostEqual(measured, -3.01, delta=0.05)

    def test_each_file_measures_the_loudness_its_voice_names(self):
        for name in sound.VOICES:
            samples, rate = self.files[name]
            self.assertAlmostEqual(
                self.generator.loudness(samples, rate),
                self.generator.VOICES[name]["lufs"], delta=0.1,
                msg="%s is not as loud as assets/sounds.py says" % name)

    def test_they_rise_in_the_order_they_cost(self):
        # `sound.VOICES` is ordered by what each costs, move first and
        # commit last. Set by a share of a peak, the back came out louder
        # than the tick and the edge as quiet as it on a television; a
        # loudness is what the order is a claim about.
        levels = [self.generator.VOICES[name]["lufs"]
                  for name in sound.VOICES]
        self.assertEqual(levels, sorted(levels))
        # Two apart at the least, or a room hears one size of press twice.
        # The one pair that shares a level is one gesture in two directions.
        for (a, low), (b, high) in zip(zip(sound.VOICES, levels),
                                       zip(sound.VOICES[1:], levels[1:])):
            if {a, b} == {"prev", "next"}:
                self.assertEqual(low, high)
            else:
                self.assertGreaterEqual(high - low, 2.0, "%s, %s" % (a, b))

    def test_nothing_goes_over_the_ceiling(self):
        for name in sound.VOICES:
            samples, _ = self.files[name]
            self.assertLessEqual(max(abs(x) for x in samples),
                                 self.generator.PEAK, name)

    def test_nothing_was_made_for_the_desk(self):
        # A cue whose loudness lives below what a television's drivers play
        # is one that has to be pushed until the desk hears it too loud
        # before the set hears it at all. The edge is the one near that
        # line, and holds its level with its own harmonics rather than
        # with a louder fundamental.
        for name in sound.VOICES:
            samples, rate = self.files[name]
            lost = (self.generator.loudness(samples, rate, heard=False)
                    - self.generator.loudness(samples, rate))
            self.assertLess(lost, 5.0, "%s loses %.1f on a set" % (name, lost))


if __name__ == "__main__":
    unittest.main()
