"""The keyboard on the desk: which nodes it opens, and what a key does.

No hardware and no /dev/input: the device nodes are fakes handed to the finder,
the same way the pad's events are synthesised elsewhere in this suite.
"""

import os
import sys
import tempfile
import unittest

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
    return config_module.load(path=missing, mapping=missing,
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


class FindTests(unittest.TestCase):
    def scan(self, nodes, match="auto", ignore=()):
        opened = list(nodes)
        paths = ["/dev/input/event%d" % i for i in range(len(nodes))]
        by_path = dict(zip(paths, nodes))
        real_open, real_glob = kbd.li.InputDevice, kbd.glob.glob
        kbd.li.InputDevice = lambda path: by_path[path]
        kbd.glob.glob = lambda pattern: paths
        try:
            found = kbd.find_keyboards(match, ignore)
        finally:
            kbd.li.InputDevice, kbd.glob.glob = real_open, real_glob
        # Anything not kept must be closed: a scan that leaks descriptors runs
        # every time a surface opens.
        for node in opened:
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

    def send(self, payload):
        self.sent.append(payload)
        return True

    def close(self):
        pass


class FakeUinput:
    def __init__(self):
        self.chords = []

    def chord(self, mods, code, pressed):
        self.chords.append((tuple(mods), code, pressed))

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
        self.config.control_socket = os.path.join(
            tempfile.mkdtemp(prefix="omapad-test-"), "control.sock"
        )
        self.daemon = daemon_module.Daemon(self.config)
        for name in ("osk", "menu", "guide", "mapping", "status",
                     "gamebar"):
            setattr(self.daemon, "%s_client" % name, FakeViewClient())
        self.addCleanup(self.daemon.shutdown)

    def key(self, code, value=1):
        self.daemon.key_event(code, value)

    def test_escape_closes_the_keyboard(self):
        self.daemon.set_osk(True)
        self.key(ESC)
        self.assertFalse(self.daemon.osk_open)

    def test_escape_leaves_a_submenu_before_it_leaves_the_menu(self):
        self.daemon.set_menu(True)
        self.daemon.menu.index = next(
            i for i, item in enumerate(self.daemon.menu.items)
            if item["items"] is not None
        )
        self.daemon.menu_command("press")
        self.assertEqual(self.daemon.menu.depth, 1)
        self.key(ESC)
        self.assertEqual(self.daemon.menu.depth, 0)
        self.assertTrue(self.daemon.menu_open)
        self.key(ESC)
        self.assertFalse(self.daemon.menu_open)

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
        return config_module.load(path=path, mapping=missing,
                                  settings=missing)

    def test_escape_closes_by_default(self):
        config = shipped_config()
        self.assertEqual(config.keyboard_binding_for("osk", ESC),
                         "surface:close")
        self.assertEqual(config.keyboard_binding_for("menu", ESC),
                         "surface:back")

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
