"""The keyboard on the desk: which nodes it opens, and what a key does.

No hardware and no /dev/input: the device nodes are fakes handed to the finder,
the same way the pad's events are synthesised elsewhere in this suite.
"""

import os
import shutil
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad import config as config_module, daemon as daemon_module
from omapad import kbd
from omapad import keymap
from omapad import linux_input as li
from omapad import uinput

KEYBOARD_KEYS = {kbd.KEY_ESC} | set(range(kbd.KEY_Q, kbd.KEY_P + 1))
ESC = keymap.resolve("esc")


def shipped_config():
    missing = os.path.join(tempfile.gettempdir(), "omapad-no-such-config")
    return config_module.load(path=missing, mapping=missing, layout=missing,
                              settings=missing)


class FakeNode:
    _next_fd = 300

    def __init__(self, path, name, vid_pid, keys=KEYBOARD_KEYS, axes=()):
        self.path = path
        self.name = name
        self.vid_pid = vid_pid
        self.keys = set(keys)
        self.axes = set(axes)
        self.closed = False
        self.grabbed = False
        self.pending = []
        self.broken = False
        FakeNode._next_fd += 1
        self.fd = FakeNode._next_fd

    def capabilities(self, ev_type, max_code):
        source = self.keys if ev_type == li.EV_KEY else self.axes
        return {code for code in source if code < max_code}

    def read_events(self):
        if self.broken:
            raise OSError("gone")
        events, self.pending = self.pending, []
        return iter(events)

    def grab(self):
        self.grabbed = True

    def close(self):
        self.closed = True


def keyboard(name="Some Keyboard", vid_pid="1234:5678"):
    return FakeNode("/dev/input/event1", name, vid_pid)


def sysfs_bitmap(codes):
    """A capability set the way sysfs prints it: long-sized hex words, high first."""
    value = sum(1 << code for code in codes)
    words = []
    while True:
        words.append("%x" % (value & ((1 << kbd.LONG_BITS) - 1)))
        value >>= kbd.LONG_BITS
        if not value:
            break
    return " ".join(reversed(words))


class FindTests(unittest.TestCase):
    def scan(self, nodes, match="auto", ignore=(), described=None):
        """Find keyboards among `nodes`; `described` are the ones sysfs knows.

        Every node is in sysfs unless `described` says otherwise, which is
        how a machine without it is posed.
        """
        paths = ["/dev/input/event%d" % i for i in range(len(nodes))]
        by_path = dict(zip(paths, nodes))
        root = tempfile.mkdtemp(prefix="omapad-sysfs-")
        self.addCleanup(shutil.rmtree, root, True)
        for path, node in by_path.items():
            if described is not None and node not in described:
                continue
            base = os.path.join(root, os.path.basename(path), "device")
            os.makedirs(os.path.join(base, "id"))
            os.makedirs(os.path.join(base, "capabilities"))
            vendor, product = node.vid_pid.split(":")
            for name, text in (("name", node.name), ("id/vendor", vendor.lower()),
                               ("id/product", product.lower()),
                               ("capabilities/key", sysfs_bitmap(node.keys)),
                               ("capabilities/abs", sysfs_bitmap(node.axes))):
                with open(os.path.join(base, name), "w") as handle:
                    handle.write(text + "\n")
        self.opened = []

        def open_node(path):
            self.opened.append(by_path[path])
            return by_path[path]

        real_open, real_glob = kbd.li.InputDevice, kbd.glob.glob
        kbd.li.InputDevice = open_node
        kbd.glob.glob = lambda pattern: paths
        try:
            found = kbd.find_keyboards(match, ignore, root=root)
        finally:
            kbd.li.InputDevice, kbd.glob.glob = real_open, real_glob
        # Anything opened and not kept must be closed: a scan that leaks
        # descriptors runs every time a surface opens.
        for node in self.opened:
            self.assertEqual(node.closed, node not in found, node.name)
        return found

    def test_it_finds_a_keyboard(self):
        node = keyboard()
        self.assertEqual(self.scan([node]), [node])

    def test_it_skips_the_pad(self):
        # A pad in XInput mode carries EV_KEY too.
        pad = FakeNode("/dev/input/event0", "Beitong", "20BC:5127",
                       keys=set(range(0x130, 0x140)), axes={li.ABS_X})
        self.assertEqual(self.scan([pad]), [])

    def test_it_skips_a_node_that_only_has_a_power_button(self):
        lid = FakeNode("/dev/input/event0", "Lid Switch", "0000:0005",
                       keys={116})
        self.assertEqual(self.scan([lid]), [])

    def test_it_never_reads_back_what_we_type(self):
        # The one that would loop: everything the on-screen keyboard types
        # would arrive here as a keypress driving the surface that typed it.
        own = keyboard("omapad virtual keyboard", uinput.IDENTITIES[1])
        self.assertEqual(self.scan([own]), [])

    def test_ignore_drops_by_name(self):
        node = keyboard("Fancy KVM Console")
        self.assertEqual(self.scan([node], ignore=("kvm",)), [])

    def test_match_narrows_by_name(self):
        wanted = keyboard("Wanted Keyboard", "1111:2222")
        other = keyboard("Other Keyboard", "3333:4444")
        self.assertEqual(self.scan([wanted, other], match="wanted"), [wanted])

    def test_match_narrows_by_id(self):
        wanted = keyboard("Wanted Keyboard", "1111:2222")
        other = keyboard("Other Keyboard", "3333:4444")
        self.assertEqual(self.scan([wanted, other], match="3333:4444"), [other])

    def test_a_node_that_is_not_kept_is_never_opened(self):
        # Closing an evdev node waits out an RCU grace period, ~6 ms each,
        # and this runs on the loop as a surface comes up: eighteen of them
        # held the first press on a menu for 200 ms. sysfs answers instead.
        pad = FakeNode("/dev/input/event0", "Beitong", "20BC:5127",
                       keys=set(range(0x130, 0x140)), axes={li.ABS_X})
        lid = FakeNode("/dev/input/event1", "Lid Switch", "0000:0005",
                       keys={116})
        node = keyboard()
        self.assertEqual(self.scan([pad, lid, node]), [node])
        self.assertEqual(self.opened, [node])

    def test_a_node_sysfs_does_not_describe_is_asked_directly(self):
        # Missed would be worse than slow: the keyboard is the way out of a
        # surface the pad cannot close.
        lid = FakeNode("/dev/input/event0", "Lid Switch", "0000:0005",
                       keys={116})
        node = keyboard()
        self.assertEqual(self.scan([lid, node], described=[]), [node])
        self.assertEqual(self.opened, [lid, node])
        self.assertTrue(lid.closed)

    @unittest.skipUnless(kbd.LONG_BITS == 64, "the words are 64-bit ones")
    def test_a_real_keyboard_bitmap_reads_as_a_keyboard(self):
        # Word for word what an AT keyboard printed under
        # /sys/class/input/event2/device/capabilities/key: four words, high
        # first, the letter row in the lowest.
        bits = kbd.SysfsNode._bitmap(
            "402000007 ff803078f800d001 feffffdfffcfffff fffffffffffffffe")
        keys = {code for code in range(256) if bits >> code & 1}
        self.assertIn(kbd.KEY_ESC, keys)
        self.assertTrue(all(code in keys
                            for code in range(kbd.KEY_Q, kbd.KEY_P + 1)))
        self.assertNotIn(0, keys)


class FakeConfig:
    keyboard_enabled = True
    keyboard_match = "auto"
    keyboard_ignore = ()
    keyboard_grab = False


class WatchTests(unittest.TestCase):
    def setUp(self):
        self.config = FakeConfig()
        self.nodes = [keyboard()]
        self.scans = 0
        self.watch = kbd.KeyboardWatch(self.config, finder=self.finder)

    def finder(self, match, ignore):
        self.scans += 1
        return list(self.nodes)

    def test_it_opens_only_while_a_surface_is_up(self):
        self.assertFalse(self.watch.follow(False))
        self.assertEqual(self.scans, 0)
        self.assertTrue(self.watch.follow(True))
        self.assertEqual(self.watch.fds(), (self.nodes[0].fd,))
        # Nothing changed, so the loop is not asked to register anything again.
        self.assertFalse(self.watch.follow(True))
        self.assertEqual(self.scans, 1)
        self.assertTrue(self.watch.follow(False))
        self.assertEqual(self.watch.fds(), ())
        self.assertTrue(self.nodes[0].closed)

    def test_disabled_never_opens_anything(self):
        self.config.keyboard_enabled = False
        self.assertFalse(self.watch.follow(True))
        self.assertEqual(self.scans, 0)

    def test_grab_is_asked_for_only_when_configured(self):
        self.watch.follow(True)
        self.assertFalse(self.nodes[0].grabbed)
        self.watch.follow(False)
        self.config.keyboard_grab = True
        self.watch.follow(True)
        self.assertTrue(self.nodes[0].grabbed)

    def test_finding_nothing_does_not_rescan_every_loop(self):
        self.nodes = []
        self.assertTrue(self.watch.follow(True))
        self.assertFalse(self.watch.follow(True))
        self.assertEqual(self.scans, 1)

    def test_a_keyboard_unplugged_mid_surface_is_dropped_and_looked_for_again(self):
        self.watch.follow(True)
        node = self.nodes[0]
        node.broken = True
        self.assertEqual(self.watch.read(node.fd), [])
        self.assertEqual(self.watch.fds(), ())
        self.assertTrue(node.closed)
        # The loop is told the descriptors changed, and the next look finds
        # whatever came back in its place.
        self.nodes = [keyboard("Replacement")]
        self.assertTrue(self.watch.follow(True))
        self.assertEqual(self.watch.fds(), (self.nodes[0].fd,))

    def test_reading_an_unknown_descriptor_is_harmless(self):
        self.assertEqual(self.watch.read(12345), [])


class FakeViewClient:
    def __init__(self):
        self.sent = []

    def send(self, payload, whole=True):
        self.sent.append(payload)
        return True

    def waiting(self):
        return False

    def flush(self):
        return True

    def close(self):
        pass


class FakeUinput:
    def __init__(self):
        self.chords = []
        self.nudges = 0

    def chord(self, mods, code, pressed):
        self.chords.append((tuple(mods), code, pressed))

    def nudge(self):
        self.nudges += 1

    def move(self, dx, dy):
        pass

    def button(self, name, pressed):
        pass

    def scroll(self, hx, hy):
        pass

    def release_all(self):
        pass

    def close(self):
        pass


class KeyRoutingTests(unittest.TestCase):
    """What a physical key does, once the daemon is holding one open."""

    def setUp(self):
        real_mouse = daemon_module.VirtualMouse
        real_keyboard = daemon_module.VirtualKeyboard
        daemon_module.VirtualMouse = lambda *a, **k: FakeUinput()
        daemon_module.VirtualKeyboard = lambda *a, **k: FakeUinput()

        def restore():
            daemon_module.VirtualMouse = real_mouse
            daemon_module.VirtualKeyboard = real_keyboard

        self.addCleanup(restore)
        self.config = shipped_config()
        self.config.notify = False
        directory = tempfile.mkdtemp(prefix="omapad-test-")
        self.config.control_socket = os.path.join(directory, "control.sock")
        # Never the settings.toml of the machine the suite runs on. Opening
        # the menu writes one - that is how a first start is answered - and a
        # test that opened a menu would otherwise replace what this pad chose
        # from the sofa with a file holding nothing but that mark.
        patch = unittest.mock.patch.object(
            daemon_module, "settings_path",
            lambda: os.path.join(directory, "settings.toml"),
        )
        patch.start()
        self.addCleanup(patch.stop)
        self.daemon = daemon_module.Daemon(self.config)
        for name in ("osk", "menu", "quick", "guide", "mapping", "status",
                     "gamebar"):
            setattr(self.daemon, "%s_client" % name, FakeViewClient())
        self.addCleanup(self.daemon.shutdown)

    def key(self, code, value=1):
        self.daemon.key_event(code, value)

    def test_escape_closes_the_keyboard(self):
        self.daemon.set_osk(True)
        self.key(ESC)
        self.assertFalse(self.daemon.osk_open)

    def test_escape_closes_the_menu_from_any_depth(self):
        # Esc is the "leave" key. The menu surface's own focus handles Esc as
        # "close outright" (the Omarchy menu's way), and this channel agrees:
        # nothing is bound for the menu, so base's `surface:close` applies and
        # a key that cannot know where in the menu you were still sends the whole
        # thing away. Backspace and Left are the level-climbers, on the menu
        # itself.
        self.daemon.set_menu(True)
        # Somewhere with a level above it: the bar is not one, so this has to
        # be a tile that drills in rather than a chip.
        for number, group in enumerate(self.daemon.menu.groups):
            drilling = [tile for tile in self.daemon.menu.tiles
                        if tile["item"]["items"] is not None]
            if drilling:
                self.daemon.menu.select_id(drilling[0]["item"]["id"])
                break
            self.daemon.menu_select_group(number + 1)
        self.daemon.menu_command("press")
        self.assertEqual(self.daemon.menu.depth, 1)
        self.key(ESC)
        self.assertFalse(self.daemon.menu_open)
        self.assertEqual(self.daemon.current_layer, "base")

    def test_a_key_means_nothing_with_no_surface_up(self):
        self.daemon.set_mode("game")
        self.key(ESC)
        self.assertEqual(self.daemon.mode, "game")
        self.assertEqual(self.daemon._keys_down, {})

    def test_an_unbound_key_does_nothing(self):
        self.daemon.set_menu(True)
        self.key(keymap.resolve("f7"))
        self.assertTrue(self.daemon.menu_open)

    def test_a_held_key_is_let_go_of_when_the_keyboards_close(self):
        self.config.keyboard_bindings["base"][ESC] = "key:ENTER"
        self.daemon.set_osk(True)
        self.key(ESC)
        self.assertEqual(self.daemon.keyboard.chords, [((), 28, True)])
        # The auto-repeat the kernel sends while the finger is down.
        self.key(ESC, 2)
        self.assertEqual(len(self.daemon.keyboard.chords), 2)
        self.key(ESC, 0)
        self.assertEqual(self.daemon.keyboard.chords[-1], ((), 28, False))
        self.assertEqual(self.daemon._keys_down, {})

    def test_release_keys_lets_go_of_what_is_still_down(self):
        self.config.keyboard_bindings["base"][ESC] = "key:ENTER"
        self.daemon.set_osk(True)
        self.key(ESC)
        self.daemon.release_keys()
        self.assertEqual(self.daemon.keyboard.chords[-1], ((), 28, False))
        self.assertEqual(self.daemon._keys_down, {})

    def test_the_top_surface_is_the_one_that_closes(self):
        self.daemon.set_osk(True)
        self.daemon.set_guide(True)   # closes the keyboard on its way up
        self.assertEqual(self.daemon.surface_top(), "guide")
        self.daemon.surface_command("close")
        self.assertIsNone(self.daemon.surface_top())

    def test_close_all_takes_every_surface_down(self):
        self.daemon.set_osk(True)
        self.daemon.set_mapping(True)
        self.daemon.surface_command("close_all")
        self.assertIsNone(self.daemon.surface_top())

    def test_a_bad_binding_is_logged_rather_than_raised(self):
        self.config.keyboard_bindings["base"][ESC] = "nonsense:boom"
        self.daemon.set_osk(True)
        with self.assertLogs("omapad", level="ERROR"):
            self.key(ESC)
        self.assertTrue(self.daemon.osk_open)


class ConfigTests(unittest.TestCase):
    def parse(self, text):
        """Load the shipped defaults with this written over them."""
        path = os.path.join(tempfile.mkdtemp(prefix="omapad-test-"),
                            "config.toml")
        with open(path, "w") as handle:
            handle.write(text)
        missing = os.path.join(tempfile.gettempdir(), "omapad-no-such-config")
        return config_module.load(path=path, mapping=missing, layout=missing,
                                  settings=missing)

    def test_escape_closes_by_default(self):
        config = shipped_config()
        self.assertEqual(config.keyboard_binding_for("osk", ESC),
                         "surface:close")
        # The menu takes the keyboard itself, so nothing is bound for the
        # surface it drives; Escape still works through base (and the menu's
        # own surface focus), as the same "leave" it means everywhere.
        self.assertEqual(config.keyboard_binding_for("menu", ESC),
                         "surface:close")

    def test_an_unknown_key_name_is_named(self):
        with self.assertRaises(config_module.ConfigError) as caught:
            self.parse('[keyboard.bindings.base]\nnosuchkey = "surface:close"\n')
        self.assertIn("nosuchkey", str(caught.exception))

    def test_an_unknown_surface_is_named(self):
        with self.assertRaises(config_module.ConfigError) as caught:
            self.parse('[keyboard.bindings.gamebar]\nesc = "surface:close"\n')
        self.assertIn("gamebar", str(caught.exception))

    def test_a_binding_must_be_a_plain_action(self):
        with self.assertRaises(config_module.ConfigError):
            self.parse(
                '[keyboard.bindings.base]\n'
                'esc = { tap = "surface:close", hold = "surface:close_all" }\n'
            )


if __name__ == "__main__":
    unittest.main()
