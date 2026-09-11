"""Force feedback without a pad: the effect struct, and the policy around it.

The ioctl layer is exercised against a fake fcntl rather than /dev/input, the
way the uinput tests are exercised against recorders.
"""

import os
import struct
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad import config as config_module
from omapad import linux_input as li
from omapad import rumble as rumble_module
from omapad.rumble import Rumble, _amplitude, _magnitude


class FakeConfig:
    rumble_enabled = True
    rumble_strong = 0.20
    rumble_weak = 0.0
    rumble_duration = 60
    rumble_edge_strength = 0.35
    rumble_edge_duration = 70
    rumble_commit_strength = 0.28
    rumble_commit_duration = 90
    rumble_texture = False
    rumble_texture_strength = 0.12
    rumble_floor = 50


# Everything a pad that wires both motors and every waveform reports.
FULL = {li.FF_RUMBLE, li.FF_PERIODIC, li.FF_SQUARE, li.FF_TRIANGLE,
        li.FF_SINE}


class FakePad:
    def __init__(self, supported=FULL, fail_upload=False, fail_play=False,
                 slots=16, fail_slots=False):
        self.supported = set(supported)
        self.fail_upload = fail_upload
        self.fail_play = fail_play
        self.slots = slots
        self.fail_slots = fail_slots
        self.uploads = []
        self.periodics = []
        self.played = []
        self.erased = []
        self._next = 7

    def supports_effects(self):
        return set(self.supported)

    def supports_rumble(self):
        return li.FF_RUMBLE in self.supported

    def effect_slots(self):
        if self.fail_slots:
            raise OSError(25, "inappropriate ioctl")
        return self.slots

    def _claim(self):
        # A fresh id per upload, the way the kernel hands them out: an effect
        # remembered across a re-attach would otherwise pass unnoticed.
        effect = self._next
        self._next += 1
        return effect

    def upload_rumble(self, strong, weak, length_ms, effect_id=-1):
        if self.fail_upload:
            raise OSError(28, "no space left for effects")
        self.uploads.append((strong, weak, length_ms))
        return self._claim()

    def upload_periodic(self, waveform, magnitude, period_ms, length_ms,
                        effect_id=-1):
        if self.fail_upload:
            raise OSError(28, "no space left for effects")
        self.periodics.append((waveform, magnitude, period_ms, length_ms))
        return self._claim()

    def play_effect(self, effect_id, count=1):
        if self.fail_play:
            raise OSError(19, "no such device")
        self.played.append((effect_id, count))

    def erase_effect(self, effect_id):
        self.erased.append(effect_id)


def only_rumble():
    return FakePad(supported={li.FF_RUMBLE})


class EffectStructTests(unittest.TestCase):
    def test_the_union_starts_after_the_header_at_pointer_alignment(self):
        # The two u16s we set are ff_rumble_effect at the union's start; get
        # the offset wrong and the pad buzzes at whatever the padding held.
        self.assertEqual(li.FF_UNION_OFFSET % struct.calcsize("@P"), 0)
        self.assertGreaterEqual(
            li.FF_UNION_OFFSET, struct.calcsize(li.FF_HEADER)
        )

    @unittest.skipUnless(struct.calcsize("@P") == 8, "64-bit layout")
    def test_the_ioctl_numbers_match_the_kernel_headers(self):
        self.assertEqual(li.FF_EFFECT_SIZE, 48)
        self.assertEqual(li.EVIOCSFF, 0x40304580)
        self.assertEqual(li.EVIOCRMFF, 0x40044581)
        self.assertEqual(li.EVIOCGEFFECTS, 0x80044584)

    def test_a_periodic_effect_fits_the_buffer_rumble_already_sized(self):
        # FF_EFFECT_SIZE was sized from ff_periodic_effect in the first place -
        # it is the union's widest member - so the periodic upload needs no
        # more room. If that stopped being true the pad would buzz at whatever
        # ran off the end.
        self.assertLessEqual(
            li.FF_UNION_OFFSET + struct.calcsize(li.FF_PERIODIC_FORMAT),
            li.FF_EFFECT_SIZE,
        )

    def test_upload_packs_a_periodic_effect(self):
        captured = {}

        def fake_ioctl(fd, request, buf, mutate=False):
            captured["buf"] = bytes(buf)
            struct.pack_into("@h", buf, 2, 4)
            return 0

        device = li.InputDevice.__new__(li.InputDevice)
        device.fd = -1
        real_ioctl = li.fcntl.ioctl
        li.fcntl.ioctl = fake_ioctl
        try:
            effect_id = device.upload_periodic(li.FF_SQUARE, 0x2000, 35, 70)
        finally:
            li.fcntl.ioctl = real_ioctl

        self.assertEqual(effect_id, 4)
        buf = captured["buf"]
        self.assertEqual(len(buf), li.FF_EFFECT_SIZE)
        header = struct.unpack_from(li.FF_HEADER, buf, 0)
        self.assertEqual(header[0], li.FF_PERIODIC)
        self.assertEqual(header[1], -1)
        self.assertEqual(header[5], 70)          # replay.length
        body = struct.unpack_from(li.FF_PERIODIC_FORMAT, buf,
                                  li.FF_UNION_OFFSET)
        self.assertEqual(body[0], li.FF_SQUARE)  # waveform
        self.assertEqual(body[1], 35)            # period
        self.assertEqual(body[2], 0x2000)        # magnitude
        self.assertEqual(body[3:], (0, 0, 0, 0, 0, 0))  # offset, phase, env

    def test_upload_packs_a_rumble_effect(self):
        captured = {}

        def fake_ioctl(fd, request, buf, mutate=False):
            captured["request"] = request
            captured["buf"] = bytes(buf)
            struct.pack_into("@h", buf, 2, 3)  # the id the kernel hands back
            return 0

        device = li.InputDevice.__new__(li.InputDevice)
        device.fd = -1
        real_ioctl = li.fcntl.ioctl
        li.fcntl.ioctl = fake_ioctl
        try:
            effect_id = device.upload_rumble(0, 0x4000, 45)
        finally:
            li.fcntl.ioctl = real_ioctl

        self.assertEqual(effect_id, 3)
        self.assertEqual(captured["request"], li.EVIOCSFF)
        buf = captured["buf"]
        self.assertEqual(len(buf), li.FF_EFFECT_SIZE)
        header = struct.unpack_from(li.FF_HEADER, buf, 0)
        self.assertEqual(header[0], li.FF_RUMBLE)
        self.assertEqual(header[1], -1)          # a fresh slot, please
        self.assertEqual(header[5], 45)          # replay.length
        strong, weak = struct.unpack_from("@HH", buf, li.FF_UNION_OFFSET)
        self.assertEqual((strong, weak), (0, 0x4000))


class MagnitudeTests(unittest.TestCase):
    def test_the_range_is_clamped_to_the_kernels_16_bits(self):
        self.assertEqual(_magnitude(0.0), 0)
        self.assertEqual(_magnitude(1.0), 0xFFFF)
        self.assertEqual(_magnitude(2.0), 0xFFFF)
        self.assertEqual(_magnitude(-1.0), 0)


class RumblePolicyTests(unittest.TestCase):
    def test_the_effect_is_uploaded_once_per_connection(self):
        rumble = Rumble(FakeConfig())
        pad = FakePad()
        rumble.attach(pad)
        uploaded = len(pad.uploads) + len(pad.periodics)
        rumble.pulse()
        rumble.pulse()
        self.assertEqual(len(pad.uploads) + len(pad.periodics), uploaded)
        self.assertEqual(pad.played, [(7, 1), (7, 1)])

    def test_detach_gives_every_slot_back(self):
        rumble = Rumble(FakeConfig())
        pad = FakePad()
        rumble.attach(pad)
        rumble.detach()
        self.assertEqual(sorted(pad.erased), [7, 8, 9])
        self.assertFalse(rumble.available)

    def test_disabled_never_touches_the_pad(self):
        config = FakeConfig()
        config.rumble_enabled = False
        rumble = Rumble(config)
        pad = FakePad()
        rumble.attach(pad)
        rumble.pulse()
        self.assertEqual(pad.uploads, [])
        self.assertEqual(pad.played, [])

    def test_a_pad_without_motors_is_not_an_error(self):
        rumble = Rumble(FakeConfig())
        pad = FakePad(supported=set())
        rumble.attach(pad)
        rumble.pulse()
        self.assertEqual(pad.played, [])

    def test_a_refused_upload_is_not_an_error(self):
        rumble = Rumble(FakeConfig())
        rumble.attach(FakePad(fail_upload=True))
        rumble.pulse()
        self.assertFalse(rumble.available)

    def test_a_pad_unplugged_mid_pulse_is_not_an_error(self):
        rumble = Rumble(FakeConfig())
        pad = FakePad(fail_play=True)
        rumble.attach(pad)
        rumble.pulse()
        # And it stops trying until the next connection.
        self.assertFalse(rumble.available)

    def test_a_tick_stops_itself(self):
        # The stop the kernel owes a finished effect does not always arrive,
        # and an Xbox pad told to buzz buzzes until something says otherwise.
        rumble = Rumble(FakeConfig())
        pad = FakePad()
        rumble.attach(pad)
        rumble.pulse()
        self.assertTrue(rumble.settling)
        rumble.settle(time.monotonic() + 1.0)
        self.assertEqual(pad.played, [(7, 1), (7, 0)])
        self.assertFalse(rumble.settling)

    def test_a_tick_still_running_is_left_alone(self):
        rumble = Rumble(FakeConfig())
        pad = FakePad()
        rumble.attach(pad)
        rumble.pulse()
        rumble.settle(time.monotonic())
        self.assertEqual(pad.played, [(7, 1)])
        self.assertTrue(rumble.settling)

    def test_a_second_tick_pushes_the_stop_out(self):
        # Otherwise a tick fired just as the last one was due to stop would
        # be cut short by the stop the first one armed.
        rumble = Rumble(FakeConfig())
        pad = FakePad()
        rumble.attach(pad)
        rumble.pulse()
        due = rumble._settle_at
        rumble.pulse()
        self.assertGreater(rumble._settle_at, due)

    def test_nothing_to_stop_is_not_a_stop(self):
        rumble = Rumble(FakeConfig())
        pad = FakePad()
        rumble.attach(pad)
        rumble.settle(time.monotonic() + 1.0)
        self.assertEqual(pad.played, [])

    def test_a_pad_that_left_owes_no_stop(self):
        # detach() erases the effect, which stops it; a stop written after
        # that would name a slot the kernel has handed to somebody else.
        rumble = Rumble(FakeConfig())
        pad = FakePad()
        rumble.attach(pad)
        rumble.pulse()
        rumble.detach()
        self.assertFalse(rumble.settling)
        rumble.settle(time.monotonic() + 1.0)
        self.assertEqual(pad.played, [(7, 1)])

    def test_a_pad_unplugged_before_the_stop_is_not_an_error(self):
        rumble = Rumble(FakeConfig())
        pad = FakePad()
        rumble.attach(pad)
        rumble.pulse()
        pad.fail_play = True
        rumble.settle(time.monotonic() + 1.0)
        self.assertFalse(rumble.available)

    def test_a_second_pulse_after_a_reattach_names_the_new_effect(self):
        # A dongle yanked mid-pulse comes back with a fresh slot table, and an
        # id remembered across that names somebody else's effect.
        rumble = Rumble(FakeConfig())
        first = FakePad()
        rumble.attach(first)
        rumble.pulse()
        second = FakePad()
        second._next = 21
        rumble.attach(second)
        rumble.pulse()
        self.assertEqual(second.played, [(21, 1)])

    def test_the_shipped_defaults_load(self):
        missing = os.path.join(tempfile.gettempdir(),
                               "omapad-no-such-config")
        config = config_module.load(path=missing, mapping=missing,
                                    settings=missing, layout=missing)
        rumble = Rumble(config)
        self.assertTrue(rumble.enabled)
        self.assertGreater(max(rumble.strong, rumble.weak), 0)
        self.assertGreater(rumble.duration_ms, 0)


class VocabularyTests(unittest.TestCase):
    """Four words, uploaded once, and what a pad that cannot say one does."""

    def full(self, **kwargs):
        config = FakeConfig()
        for key, value in kwargs.items():
            setattr(config, key, value)
        rumble = Rumble(config)
        pad = FakePad()
        rumble.attach(pad)
        return rumble, pad

    def test_the_shipped_default_is_three_words_and_no_texture(self):
        rumble, pad = self.full()
        self.assertEqual(sorted(rumble.effects), ["commit", "edge", "tick"])
        self.assertFalse(rumble.has("texture"))

    def test_texture_on_uploads_four_and_no_more(self):
        rumble, pad = self.full(rumble_texture=True)
        self.assertEqual(len(rumble.effects), 4)
        self.assertEqual(len(pad.uploads) + len(pad.periodics), 4)

    def test_each_word_gets_the_waveform_that_says_it(self):
        # The waveform is the meaning: a square is a wall, a triangle is a
        # thing landing, a sine is a surface moving under the thumb.
        rumble, pad = self.full(rumble_texture=True)
        self.assertEqual([entry[0] for entry in pad.periodics],
                         [li.FF_SQUARE, li.FF_TRIANGLE, li.FF_SINE])
        self.assertEqual(pad.uploads[0][2], 60)   # the tick, on FF_RUMBLE

    def test_the_edge_is_two_cycles_and_the_commit_is_one(self):
        # The cycle count is the waveform's argument one field along, so the
        # period is computed from the length rather than named in the config.
        rumble, pad = self.full()
        square, triangle = pad.periodics
        self.assertEqual((square[2], square[3]), (35, 70))    # 70ms / 2
        self.assertEqual((triangle[2], triangle[3]), (90, 90))  # 90ms / 1

    def test_the_texture_runs_until_stopped(self):
        rumble, pad = self.full(rumble_texture=True)
        length = [entry[3] for entry in pad.periodics
                  if entry[0] == li.FF_SINE][0]
        self.assertEqual(length, 0)

    def test_the_floor_lifts_a_pulse_shorter_than_a_packet(self):
        rumble, pad = self.full(rumble_duration=10, rumble_edge_duration=20)
        self.assertEqual(pad.uploads[0][2], 50)
        self.assertEqual(pad.periodics[0][3], 50)

    def test_a_periodic_magnitude_is_signed(self):
        # An s16 where rumble's is a u16: pack 0xFFFF into it and the pad gets
        # a phase inversion at full strength instead.
        self.assertEqual(_amplitude(1.0), 0x7FFF)
        self.assertEqual(_amplitude(2.0), 0x7FFF)
        self.assertEqual(_amplitude(-1.0), 0)

    def test_a_pad_with_no_periodic_effects_gets_three_ticks(self):
        config = FakeConfig()
        config.rumble_texture = True
        rumble = Rumble(config)
        pad = only_rumble()
        rumble.attach(pad)
        self.assertEqual(sorted(rumble.effects), ["commit", "edge", "tick"])
        self.assertEqual(pad.periodics, [])
        self.assertEqual(len(pad.uploads), 3)

    def test_the_texture_never_falls_back_to_a_pulse(self):
        # Degrading a continuous effect onto one that has to be stopped is the
        # tick that sticks on, arriving through a new door.
        config = FakeConfig()
        config.rumble_texture = True
        rumble = Rumble(config)
        rumble.attach(only_rumble())
        self.assertFalse(rumble.has("texture"))
        rumble.start("texture")
        self.assertEqual(rumble._held, set())

    def test_a_pad_with_no_force_feedback_uploads_nothing(self):
        rumble = Rumble(FakeConfig())
        pad = FakePad(supported=set())
        rumble.attach(pad)
        self.assertEqual(rumble.effects, {})
        self.assertEqual(pad.uploads, [])
        self.assertEqual(pad.periodics, [])

    def test_a_pad_with_one_slot_keeps_the_word_nearest_a_press(self):
        rumble, pad = self.full(rumble_texture=True)
        rumble.detach()
        small = FakePad(slots=1)
        rumble.attach(small)
        self.assertEqual(list(rumble.effects), ["tick"])

    def test_a_driver_that_will_not_count_slots_assumes_one(self):
        rumble = Rumble(FakeConfig())
        rumble.attach(FakePad(fail_slots=True))
        self.assertEqual(list(rumble.effects), ["tick"])

    def test_a_held_effect_is_started_and_stopped_once(self):
        rumble, pad = self.full(rumble_texture=True)
        effect = rumble.effects["texture"]
        rumble.start("texture")
        rumble.start("texture")
        rumble.stop("texture")
        rumble.stop("texture")
        self.assertEqual(pad.played, [(effect, 1), (effect, 0)])

    def test_stopping_what_was_never_started_writes_nothing(self):
        rumble, pad = self.full(rumble_texture=True)
        rumble.stop("texture")
        self.assertEqual(pad.played, [])

    def test_stop_held_ends_everything_still_running(self):
        # What a mode switch owes the motor: a hum left running across one is
        # the tick that sticks on with no press to blame.
        rumble, pad = self.full(rumble_texture=True)
        effect = rumble.effects["texture"]
        rumble.start("texture")
        rumble.stop_held()
        self.assertEqual(pad.played[-1], (effect, 0))
        self.assertEqual(rumble._held, set())

    def test_settling_a_pulse_does_not_cut_a_held_effect_short(self):
        rumble, pad = self.full(rumble_texture=True)
        texture = rumble.effects["texture"]
        tick = rumble.effects["tick"]
        rumble.start("texture")
        rumble.pulse()
        rumble.settle(time.monotonic() + 1.0)
        self.assertEqual(pad.played,
                         [(texture, 1), (tick, 1), (tick, 0)])
        self.assertEqual(rumble._held, {"texture"})

    def test_detach_forgets_a_held_effect_it_could_not_stop(self):
        rumble, pad = self.full(rumble_texture=True)
        rumble.start("texture")
        rumble.detach()
        self.assertEqual(rumble._held, set())

    def test_a_held_word_may_not_be_played(self):
        # A texture fired as a pulse would never be stopped by anything: it
        # has no length to run out. Caught here rather than on the sofa.
        rumble, _ = self.full(rumble_texture=True)
        with self.assertRaises(ValueError):
            rumble.play("texture")

    def test_a_word_the_pad_never_took_is_silent_rather_than_an_error(self):
        rumble, pad = self.full()
        rumble.play("edge")
        rumble.detach()
        pad.played = []
        rumble.play("edge")
        self.assertEqual(pad.played, [])

    def test_the_plan_is_what_attach_does(self):
        # `omapad check` prints plan(); the daemon uploads it. Two answers
        # would mean a report about a different pad than the one in the hand.
        config = FakeConfig()
        config.rumble_texture = True
        rumble = Rumble(config)
        pad = FakePad()
        rumble.attach(pad)
        taken = rumble_module.plan(rumble.levels, pad.supports_effects(),
                                   pad.effect_slots())
        self.assertEqual([name for name, _ in taken],
                         list(rumble.effects))

    def test_a_strength_of_zero_is_a_word_left_unsaid(self):
        rumble, pad = self.full(rumble_edge_strength=0.0)
        self.assertFalse(rumble.has("edge"))
        self.assertTrue(rumble.has("commit"))

    def test_configure_replaces_the_effects_on_a_connected_pad(self):
        rumble, pad = self.full()
        config = FakeConfig()
        config.rumble_strong = 0.5
        rumble.configure(config)
        self.assertEqual(sorted(pad.erased), [7, 8, 9])
        self.assertEqual(pad.uploads[-1][0], _magnitude(0.5))


class ShippedSettingsTests(unittest.TestCase):
    def test_the_shipped_defaults_describe_four_words(self):
        missing = os.path.join(tempfile.gettempdir(),
                               "omapad-no-such-config")
        config = config_module.load(path=missing, mapping=missing,
                                    settings=missing, layout=missing)
        rumble = Rumble(config)
        self.assertEqual(sorted(rumble.levels), sorted(rumble_module.EFFECTS))
        # The texture ships off, so the only word with no level is that one.
        silent = [name for name in rumble_module.EFFECTS
                  if rumble.levels[name][0] <= 0]
        self.assertEqual(silent, ["texture"])

    def test_a_strength_outside_the_range_is_named(self):
        with self.assertRaises(config_module.ConfigError) as caught:
            config_module.Config({"rumble": {"edge_strength": 4.0}})
        self.assertIn("edge_strength", str(caught.exception))

    def test_a_duration_of_zero_is_named(self):
        with self.assertRaises(config_module.ConfigError) as caught:
            config_module.Config({"rumble": {"commit_duration_ms": 0}})
        self.assertIn("commit_duration_ms", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
