"""Which node the daemon picks up, and how `[device] match` narrows it.

Discovery is capability-based, so this is what stops a pad's own keyboard node
- or a touchpad - from being adopted as the pad, without either being named.
"""

import unittest
from unittest import mock

from omapad import config as config_module
from omapad import linux_input as li


class FakeDevice(object):
    def __init__(self, path, name, vid_pid, abs_codes, key_codes):
        self.path = path
        self.name = name
        self.vid_pid = vid_pid
        self.abs_codes = set(abs_codes)
        self.key_codes = set(key_codes)
        self.closed = False

    def capabilities(self, etype, limit):
        codes = self.abs_codes if etype == li.EV_ABS else self.key_codes
        return set(code for code in codes if code < limit)

    def close(self):
        self.closed = True


def pad(path, name, vid_pid):
    return FakeDevice(
        path, name, vid_pid,
        [li.ABS_X, li.ABS_Y, li.ABS_HAT0X, li.ABS_HAT0Y],
        [0x130, 0x131, 0x133, 0x134],
    )


XBOX = pad("/dev/input/event17", "Xbox Wireless Controller", "045E:028E")
BEITONG = pad("/dev/input/event5", "BEITONG  BTP-KP20 NS", "057E:2009")
# The extra nodes a wireless Xbox pad enumerates alongside the pad itself.
XBOX_KEYBOARD = FakeDevice(
    "/dev/input/event19", "Xbox Wireless Controller Keyboard", "045E:028E",
    [], [1, 16, 17, 18],
)
XBOX_MOUSE = FakeDevice(
    "/dev/input/event20", "Xbox Wireless Controller Mouse", "045E:028E",
    [], [li.BTN_LEFT, li.BTN_RIGHT],
)
# Absolute axes but no joystick buttons.
TOUCHPAD = FakeDevice(
    "/dev/input/event6", "SynPS/2 Synaptics TouchPad", "0002:0007",
    [li.ABS_X, li.ABS_Y], [li.BTN_LEFT, 0x145],
)


def discover(devices, match=()):
    """Run find_device over a fixed set of nodes instead of /dev/input."""
    by_path = dict((device.path, device) for device in devices)
    with mock.patch.object(li.glob, "glob", return_value=list(by_path)), \
            mock.patch.object(li, "InputDevice", by_path.get):
        return li.find_device(match)


class TestIsGamepad(unittest.TestCase):
    def test_a_pad_is_one(self):
        self.assertTrue(li.is_gamepad(XBOX))
        self.assertTrue(li.is_gamepad(BEITONG))

    def test_the_nodes_a_pad_brings_with_it_are_not(self):
        self.assertFalse(li.is_gamepad(XBOX_KEYBOARD))
        self.assertFalse(li.is_gamepad(XBOX_MOUSE))

    def test_axes_alone_are_not_enough(self):
        self.assertFalse(li.is_gamepad(TOUCHPAD))


class TestFindDevice(unittest.TestCase):
    def test_an_unnamed_pad_is_found(self):
        """The point of the change: no pattern, and the Xbox pad still wins."""
        self.assertIs(discover([XBOX_KEYBOARD, XBOX_MOUSE, XBOX]), XBOX)

    def test_nothing_connected(self):
        self.assertIsNone(discover([TOUCHPAD, XBOX_MOUSE]))

    def test_a_name_fragment_picks_between_two_pads(self):
        self.assertIs(discover([XBOX, BEITONG], ["BEITONG"]), BEITONG)
        self.assertIs(discover([BEITONG, XBOX], ["xbox"]), XBOX)

    def test_an_identity_picks_between_two_pads(self):
        self.assertIs(discover([XBOX, BEITONG], ["057E:2009"]), BEITONG)

    def test_a_list_is_tried_in_order(self):
        both = [BEITONG, XBOX]
        self.assertIs(discover(both, ["Xbox", "BEITONG"]), XBOX)
        self.assertIs(discover(both, ["BEITONG", "Xbox"]), BEITONG)

    def test_a_later_pattern_wins_when_the_first_is_absent(self):
        self.assertIs(discover([XBOX], ["BEITONG", "Xbox"]), XBOX)

    def test_a_pattern_cannot_land_on_the_keyboard_node(self):
        """"Xbox" names three nodes; only the pad may be adopted."""
        self.assertIs(
            discover([XBOX_KEYBOARD, XBOX_MOUSE, XBOX], ["Xbox"]), XBOX
        )

    def test_a_pattern_that_names_nothing_finds_nothing(self):
        self.assertIsNone(discover([XBOX], ["8BitDo"]))

    def test_the_nodes_not_taken_are_closed(self):
        loser = pad("/dev/input/event9", "Some Other Pad", "1234:5678")
        winner = pad("/dev/input/event3", "Xbox Wireless Controller", "045E:028E")
        self.assertIs(discover([loser, winner], ["Xbox"]), winner)
        self.assertTrue(loser.closed)
        self.assertFalse(winner.closed)


class TestHeldKeys(unittest.TestCase):
    """The one question a grabbed pad still answers - see cmd_check."""

    def held(self, codes):
        device = li.InputDevice.__new__(li.InputDevice)
        device.fd = 7

        def ioctl(fd, request, buffer):
            self.assertEqual((fd, request), (7, li.EVIOCGKEY))
            for code in codes:
                buffer[code // 8] |= 1 << (code % 8)
            return 0

        with mock.patch("omapad.linux_input.fcntl.ioctl", ioctl):
            return device.held_keys()

    def test_a_pad_on_the_table_holds_nothing(self):
        self.assertEqual(self.held([]), [])

    def test_every_bit_set_is_a_code_back(self):
        # BTN_TL is the one this was written for: a shoulder reported down
        # with nothing touching the pad.
        self.assertEqual(self.held([0x136]), [0x136])
        self.assertEqual(self.held([0x130, 0x136, 0x13E]),
                         [0x130, 0x136, 0x13E])


class TestMatchPatterns(unittest.TestCase):
    def test_auto_means_no_pattern(self):
        self.assertEqual(config_module._match_patterns("auto"), [])
        self.assertEqual(config_module._match_patterns("  AUTO "), [])
        self.assertEqual(config_module._match_patterns(""), [])
        self.assertEqual(config_module._match_patterns([]), [])

    def test_a_string_becomes_one_pattern(self):
        self.assertEqual(config_module._match_patterns("Xbox"), ["Xbox"])

    def test_a_list_is_kept_in_order(self):
        self.assertEqual(
            config_module._match_patterns(["Xbox", " BEITONG "]),
            ["Xbox", "BEITONG"],
        )

    def test_the_default_finds_any_pad(self):
        self.assertEqual(config_module.Config({}).device_match, [])

    def test_a_bad_match_is_named_by_check(self):
        for bad in (5, {"name": "Xbox"}, ["Xbox", 7], ["Xbox", "  "]):
            with self.assertRaises(config_module.ConfigError):
                config_module._match_patterns(bad)



class TestBadgeLayout(unittest.TestCase):
    """Which console's printing the badges carry, and where it comes from."""

    def test_auto_follows_the_profile_of_the_pad_that_connected(self):
        config = config_module.Config({})
        self.assertEqual(config.badge_layout("xbox"), "xbox")
        self.assertEqual(config.badge_layout("nintendo_pro"), "nintendo")

    def test_and_falls_back_to_the_names_the_bindings_are_written_in(self):
        # No pad yet: the logical names are the Switch's, so that is what a
        # badge says until something is plugged in.
        self.assertEqual(config_module.Config({}).badge_layout(None), "nintendo")

    def test_a_layout_of_your_own_wins_over_the_profile(self):
        # The case this setting exists for: a PlayStation pad reports itself
        # as an XInput device, so nothing can detect it.
        config = config_module.Config({"device": {"layout": "playstation"}})
        self.assertEqual(config.badge_layout("xbox"), "playstation")

    def test_an_unknown_one_is_named_by_check(self):
        with self.assertRaises(config_module.ConfigError):
            config_module.Config({"device": {"layout": "dreamcast"}})

if __name__ == "__main__":
    unittest.main()
