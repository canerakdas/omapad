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
from omapad.rumble import Rumble, _magnitude


class FakeConfig:
    rumble_enabled = True
    rumble_strong = 0.20
    rumble_weak = 0.0
    rumble_duration = 60


class FakePad:
    def __init__(self, supported=True, fail_upload=False, fail_play=False):
        self.supported = supported
        self.fail_upload = fail_upload
        self.fail_play = fail_play
        self.uploads = []
        self.played = []
        self.erased = []

    def supports_rumble(self):
        return self.supported

    def upload_rumble(self, strong, weak, length_ms, effect_id=-1):
        if self.fail_upload:
            raise OSError(28, "no space left for effects")
        self.uploads.append((strong, weak, length_ms))
        return 7

    def play_effect(self, effect_id, count=1):
        if self.fail_play:
            raise OSError(19, "no such device")
        self.played.append((effect_id, count))

    def erase_effect(self, effect_id):
        self.erased.append(effect_id)


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
        rumble.pulse()
        rumble.pulse()
        self.assertEqual(len(pad.uploads), 1)
        self.assertEqual(pad.played, [(7, 1), (7, 1)])

    def test_detach_gives_the_slot_back(self):
        rumble = Rumble(FakeConfig())
        pad = FakePad()
        rumble.attach(pad)
        rumble.detach()
        self.assertEqual(pad.erased, [7])
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
        pad = FakePad(supported=False)
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

    def test_the_shipped_defaults_load(self):
        missing = os.path.join(tempfile.gettempdir(),
                               "omapad-no-such-config")
        config = config_module.load(path=missing, mapping=missing,
                                       settings=missing)
        rumble = Rumble(config)
        self.assertTrue(rumble.enabled)
        self.assertGreater(max(rumble.strong, rumble.weak), 0)
        self.assertGreater(rumble.duration_ms, 0)


if __name__ == "__main__":
    unittest.main()
