"""Drive the daemon with synthetic controller events.

Everything below the uinput write is exercised: profiles, layers, analog
triggers, tap/hold, pointer integration and game mode. The uinput layer itself
is replaced by recorders, so these run without /dev/uinput.
"""

import os
import select
import sys
import tempfile
import shutil
import time
import unittest
import unittest.mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad import config as config_module, daemon as daemon_module
from omapad import keymap
from omapad import linux_input as li
from omapad import linux_input as li
from omapad import uinput
from omapad import actions
from omapad import menu as menu_module
from omapad import guide as guide_module
from omapad.linux_input import AbsInfo

XBOX = ("Beitong KP20A/KP40A Controller", "20BC:5127")
NINTENDO = ("BEITONG  BTP-KP20 NS", "057E:2009")

STICK_INFO = AbsInfo(0, -32768, 32767, 0, 128, 0)
TRIGGER_INFO = AbsInfo(0, 0, 255, 0, 0, 0)
HAT_INFO = AbsInfo(0, -1, 1, 0, 0, 0)


def shipped_config():
    """The config as shipped, with nothing of the developer's own in it.

    `config_module.load()` merges ~/.config/omapad over the defaults, so a
    suite that called it tested whichever machine it ran on - and failed the
    day someone's own config bound something these tests assert about.
    """
    missing = os.path.join(tempfile.gettempdir(), "omapad-no-such-config")
    return config_module.load(path=missing, mapping=missing,
                              settings=missing, layout=missing)


class FakeMouse:
    def __init__(self):
        self.moves = []
        self.buttons = []
        self.scrolls = []
        self.released = 0

    def move(self, dx, dy):
        self.moves.append((dx, dy))

    def button(self, name, pressed):
        self.buttons.append((name, pressed))

    def scroll(self, hx, hy):
        self.scrolls.append((hx, hy))

    def release_all(self):
        self.released += 1

    def close(self):
        pass


class FakeKeyboard:
    def __init__(self):
        self.chords = []
        self.nudges = 0
        self.released = 0

    def chord(self, mods, code, pressed):
        self.chords.append((tuple(mods), code, pressed))

    def key(self, code, pressed):
        self.chords.append(((), code, pressed))

    # Counted rather than recorded with the rest: it types nothing, and a
    # test asking what a binding typed should not have to say "and the
    # keystroke that puts the pointer away" every time.
    def nudge(self):
        self.nudges += 1

    def release_all(self):
        self.released += 1

    def close(self):
        pass


class FakeHypr:
    def __init__(self):
        self.calls = []
        self.warps = []
        self.cursors = []
        # Lua run in the compositor's config namespace - the layer rule that
        # asks for a blur behind our own surfaces, and nothing else.
        self.evaluated = []
        # What `j/<command>` answers with, so a snap can be posed a whole
        # desktop without one being on screen.
        self.answers = {}
        # Every `j/` asked, so a role that promises to ask once per push can
        # be held to it.
        self.queries = []
        self.position = (0.0, 0.0)

    def evaluate(self, expression):
        self.evaluated.append(expression)
        return "ok"

    def dispatch(self, expression):
        self.calls.append(expression)
        return "ok"

    def query(self, command):
        self.queries.append(command)
        return self.answers.get(command)

    def window_floating(self):
        data = self.query("activewindow")
        if not isinstance(data, dict):
            return None
        value = data.get("floating")
        if value is None:
            return None
        return bool(value)

    def cursor_position(self):
        return self.position

    def warp(self, x, y):
        self.warps.append((int(x), int(y)))

    def set_cursor_theme(self, theme, size):
        self.cursors.append((theme, int(size)))
        return "ok"


class FakeSession:
    def __init__(self):
        self.spawned = []
        self.captured = []
        self.notifications = []
        self.env = {}
        # What a command an app page reads its entries from is to print.
        self.lines = []

    def spawn(self, command):
        self.spawned.append(command)

    def capture(self, command, timeout=2.0):
        self.captured.append(command)
        return list(self.lines)

    def notify(self, summary, body="", timeout=1500):
        self.notifications.append((summary, body))


class FakeViewClient:
    def __init__(self):
        self.sent = []

    def send(self, payload):
        self.sent.append(payload)
        return True

    def close(self):
        pass


class FakeDevice:
    fd = 99

    def __init__(self, identity=XBOX, rumble=True, rest=None):
        self.name, self.vid_pid = identity
        self.path = "/dev/input/event-fake"
        self.pending = []
        self.grabbed = False
        # Where each stick axis reports itself at rest, for the pads that do
        # not rest where they claim to.
        self.rest = rest or {}
        self.rumble = rumble
        self.effects = {}
        self.played = []
        self.stopped = []
        self._next_effect = 0

    def supports_effects(self):
        # A pad that wires a motor and every waveform: what the daemon tests
        # ask about is when a tick fires, never which wave carries it.
        if not self.rumble:
            return set()
        return {li.FF_RUMBLE, li.FF_PERIODIC, li.FF_SQUARE, li.FF_TRIANGLE,
                li.FF_SINE}

    def supports_rumble(self):
        return self.rumble

    def effect_slots(self):
        return 16

    def upload_periodic(self, waveform, magnitude, period_ms, length_ms,
                        effect_id=-1):
        if effect_id < 0:
            effect_id = self._next_effect
            self._next_effect += 1
        self.effects[effect_id] = (waveform, magnitude, period_ms, length_ms)
        return effect_id

    def upload_rumble(self, strong, weak, length_ms, effect_id=-1):
        if effect_id < 0:
            effect_id = self._next_effect
            self._next_effect += 1
        self.effects[effect_id] = (strong, weak, length_ms)
        return effect_id

    def play_effect(self, effect_id, count=1):
        if count:
            self.played.append(effect_id)
        else:
            self.stopped.append(effect_id)

    def erase_effect(self, effect_id):
        self.effects.pop(effect_id, None)

    def absinfo(self, code):
        if code in (li.ABS_X, li.ABS_Y, li.ABS_RX, li.ABS_RY):
            if code in self.rest:
                return AbsInfo(
                    self.rest[code], STICK_INFO.minimum, STICK_INFO.maximum,
                    STICK_INFO.fuzz, STICK_INFO.flat, STICK_INFO.resolution,
                )
            return STICK_INFO
        if code in (li.ABS_Z, li.ABS_RZ):
            return TRIGGER_INFO
        return HAT_INFO

    def read_events(self):
        events, self.pending = self.pending, []
        return iter(events)

    def grab(self):
        self.grabbed = True

    def ungrab(self):
        self.grabbed = False

    def close(self):
        pass


class DaemonTestCase(unittest.TestCase):
    identity = XBOX

    def setUp(self):
        self._real_mouse = daemon_module.VirtualMouse
        self._real_keyboard = daemon_module.VirtualKeyboard
        daemon_module.VirtualMouse = lambda *a, **k: FakeMouse()
        daemon_module.VirtualKeyboard = lambda *a, **k: FakeKeyboard()
        self.addCleanup(self._restore)

        self.config = shipped_config()
        self.config.notify = False
        directory = tempfile.mkdtemp(prefix="omapad-test-")
        self.addCleanup(shutil.rmtree, directory, True)
        # Never bind the real control socket: a live daemon may own it.
        self.config.control_socket = os.path.join(directory, "control.sock")
        # And never write the settings.toml of the machine the suite is run
        # on. A test that changes a setting on a real Daemon saves it at the
        # press, exactly as the daemon does, and `render_settings` writes the
        # whole file - so one such test replaces what this pad chose from the
        # sofa with what the test chose, and quietly loses every other line.
        # Named here rather than in the one class that needs to read the file
        # back: any test may set a setting, and none of them may cost the
        # developer theirs.
        patch = unittest.mock.patch.object(
            daemon_module, "settings_path",
            lambda: os.path.join(directory, "settings.toml"),
        )
        patch.start()
        self.addCleanup(patch.stop)
        self.daemon = daemon_module.Daemon(self.config)
        self.mouse = self.daemon.mouse
        self.keyboard = self.daemon.keyboard
        self.hypr = self.daemon.hypr = FakeHypr()
        self.session = self.daemon.session = FakeSession()
        # The worker was built with the real session, and a thread that runs
        # shell commands has no place in a suite that needs no machine. With
        # none, every caller reads its command on the loop instead - against
        # the fake session, which is what these tests are about. The worker's
        # own half is CommandWorkerTests.
        self.daemon.commands.close()
        self.daemon.commands = None
        self.daemon.ctx.hypr = self.hypr
        self.daemon.ctx.session = self.session
        self.osk_client = self.daemon.osk_client = FakeViewClient()
        self.menu_client = self.daemon.menu_client = FakeViewClient()
        self.hud_client = self.daemon.hud_client = FakeViewClient()
        self.guide_client = self.daemon.guide_client = FakeViewClient()
        # Swapped here rather than per-test: the real clients connect to the
        # live shell's sockets, so a suite that left them in place would push
        # test payloads at whatever is running on the machine.
        self.mapping_client = self.daemon.mapping_client = FakeViewClient()
        self.status_client = self.daemon.status_client = FakeViewClient()
        self.gamebar_client = self.daemon.gamebar_client = FakeViewClient()
        self.ripple_client = self.daemon.ripple_client = FakeViewClient()
        # Also exercises the shutdown path, and closes the control socket.
        self.addCleanup(self.daemon.shutdown)
        self.device = FakeDevice(self.identity)
        self.daemon.attach(self.device)

    def _restore(self):
        daemon_module.VirtualMouse = self._real_mouse
        daemon_module.VirtualKeyboard = self._real_keyboard

    def feed(self, *events):
        self.device.pending.extend(events)
        self.daemon.drain_events()

    def code_for(self, name):
        for code, button in self.daemon.buttons.items():
            if button == name:
                return code
        raise AssertionError("%s is not on this profile" % name)

    def press(self, name):
        if name in self.daemon.trigger_axes.values():
            self.pull(name, 1.0)
            return
        self.feed((li.EV_KEY, self.code_for(name), 1))

    def release(self, name):
        if name in self.daemon.trigger_axes.values():
            self.pull(name, 0.0)
            return
        self.feed((li.EV_KEY, self.code_for(name), 0))

    def pull(self, name, fraction):
        """Move an analog trigger; XInput reports ZL/ZR as axes, not buttons."""
        for code, trigger in self.daemon.trigger_axes.items():
            if trigger == name:
                info = self.device.absinfo(code)
                span = info.maximum - info.minimum
                self.feed((li.EV_ABS, code, int(info.minimum + fraction * span)))
                return
        raise AssertionError("%s is not an axis on this profile" % name)

    def tick(self, seconds=0.1, steps=1):
        for _ in range(steps):
            self.daemon.tick(seconds / steps)


class ProfileTests(DaemonTestCase):
    def test_xbox_profile_detected(self):
        self.assertEqual(self.daemon.buttons[0x130], "A")
        self.assertEqual(self.daemon.trigger_axes, {0x02: "ZL", 0x05: "ZR"})

    def test_nintendo_profile_uses_digital_triggers(self):
        daemon = daemon_module.Daemon(self.config)
        self.addCleanup(daemon.shutdown)
        daemon.osk_client = FakeViewClient()
        daemon.menu_client = FakeViewClient()
        daemon.hud_client = FakeViewClient()
        daemon.guide_client = FakeViewClient()
        daemon.attach(FakeDevice(NINTENDO))
        self.assertEqual(daemon.buttons[0x130], "B")
        self.assertEqual(daemon.buttons[0x139], "ZR")
        self.assertEqual(daemon.trigger_axes, {})


class PointerTests(DaemonTestCase):
    def test_full_deflection_moves_cursor_at_configured_speed(self):
        self.feed((li.EV_ABS, li.ABS_X, 32767))
        self.tick(1.0, steps=100)
        travelled = sum(dx for dx, _ in self.mouse.moves)
        self.assertAlmostEqual(travelled, self.config.pointer_speed, delta=5)
        self.assertTrue(all(dy == 0 for _, dy in self.mouse.moves))

    def test_stick_inside_deadzone_does_not_move(self):
        self.feed((li.EV_ABS, li.ABS_X, int(32767 * 0.05)))
        self.tick(1.0, steps=100)
        self.assertEqual(self.mouse.moves, [])

    def test_each_stick_carries_its_own_dead_zone_into_any_role(self):
        # The slop is in the hardware, so the zone follows the stick and not
        # what the stick is doing: a right stick handed the aiming role keeps
        # the wider zone it ships scrolling with until someone narrows it,
        # while the same deflection on the left is past its own.
        self.config.right_stick = "cursor"
        self.config.left_deadzone = 0.10
        self.config.right_deadzone = 0.60
        self.feed((li.EV_ABS, li.ABS_RX, int(32767 * 0.5)))
        self.tick(1.0, steps=100)
        self.assertEqual(self.mouse.moves, [])
        self.feed((li.EV_ABS, li.ABS_RX, 0),
                  (li.EV_ABS, li.ABS_X, int(32767 * 0.5)))
        self.tick(1.0, steps=100)
        self.assertTrue(self.mouse.moves)

    def test_a_stick_that_rests_off_centre_does_not_drift(self):
        # The Beitong KP20 in NS mode: every axis rests half a range off the
        # advertised centre and uses only that half - X spans -32767..0. Read
        # at face value an untouched stick is a half deflection, and the cursor
        # walks into a corner nothing can bring it back from.
        self.daemon.disconnect()
        self.device = FakeDevice(self.identity, rest={li.ABS_X: -16379})
        self.daemon.attach(self.device)

        self.feed((li.EV_ABS, li.ABS_X, -16379))
        self.tick(1.0, steps=100)
        self.assertEqual(self.mouse.moves, [])

    def test_both_ends_of_a_half_range_axis_still_reach_full_speed(self):
        self.daemon.disconnect()
        self.device = FakeDevice(self.identity, rest={li.ABS_X: -16379})
        self.daemon.attach(self.device)

        # 0 is as far right as this axis physically goes, -32767 as far left.
        self.feed((li.EV_ABS, li.ABS_X, 0))
        self.tick(1.0, steps=100)
        right = sum(dx for dx, _ in self.mouse.moves)
        self.mouse.moves.clear()
        self.feed((li.EV_ABS, li.ABS_X, -32767))
        self.tick(1.0, steps=100)
        left = sum(dx for dx, _ in self.mouse.moves)
        self.assertAlmostEqual(right, self.config.pointer_speed, delta=60)
        self.assertAlmostEqual(left, -self.config.pointer_speed, delta=60)

    def test_a_stick_held_at_connect_is_not_taken_for_the_rest_position(self):
        # Calibrating onto a held stick would freeze that direction for the
        # whole session, so a rest that far out is ignored.
        self.daemon.disconnect()
        self.device = FakeDevice(self.identity, rest={li.ABS_X: -32767})
        self.daemon.attach(self.device)
        center, half = self.daemon.axis_scale[li.ABS_X]
        self.assertEqual((center, half), (STICK_INFO.center, STICK_INFO.half_range))

    def test_a_stick_nearly_held_at_connect_is_not_taken_for_the_rest_either(self):
        # An Xbox Elite Series 2 connected with a thumb on the right stick:
        # `axis 0x04 rests -0.84 off centre` was under the old 0.90 limit, so
        # it calibrated - onto a neutral 0.84 out, with a sixth of the range
        # left. Every later reading, the stick's real centre among them,
        # clamped to a full deflection, and the scroll role it carries ran
        # the page down for as long as the daemon lived.
        self.daemon.disconnect()
        self.device = FakeDevice(self.identity, rest={li.ABS_RY: -27516})
        self.daemon.attach(self.device)
        center, half = self.daemon.axis_scale[li.ABS_RY]
        self.assertEqual((center, half), (STICK_INFO.center, STICK_INFO.half_range))

        # And with the pad back at rest, nothing scrolls.
        self.feed((li.EV_ABS, li.ABS_RY, 0))
        self.tick(1.0, steps=100)
        self.assertEqual(self.mouse.scrolls, [])

    def test_a_stick_resting_a_little_off_centre_still_recentres(self):
        # The common case the guard must not swallow: a worn stick a couple of
        # percent off, and a KP20 at its half range, both still calibrate.
        for rest in (-1200, -16379):
            self.daemon.disconnect()
            self.device = FakeDevice(self.identity, rest={li.ABS_X: rest})
            self.daemon.attach(self.device)
            center, half = self.daemon.axis_scale[li.ABS_X]
            self.assertEqual(center, float(rest))
            self.assertEqual(half, float(rest - STICK_INFO.minimum))

    def test_a_limit_outside_its_range_is_named(self):
        with self.assertRaises(config_module.ConfigError) as caught:
            config_module.Config({"pointer": {"recenter_limit": 0.0}})
        self.assertIn("recenter_limit", str(caught.exception))

    def test_an_axis_with_no_report_yet_calibrates_on_its_first_value(self):
        # The node can exist before the pad's first packet lands, and then
        # absinfo reads 0 for an axis that in truth rests nowhere near it.
        self.daemon.disconnect()
        self.device = FakeDevice(self.identity)
        self.daemon.attach(self.device)
        self.assertIn(li.ABS_X, self.daemon.uncalibrated)
        self.feed((li.EV_ABS, li.ABS_X, -16379))
        self.assertNotIn(li.ABS_X, self.daemon.uncalibrated)
        self.tick(1.0, steps=100)
        self.assertEqual(self.mouse.moves, [])

    def test_right_stick_scrolls_down_when_pushed_down(self):
        # The speed on its own, so the ramp is not measured here: it has its
        # own tests, and this one is about which way a stick sends the wheel.
        self.config.scroll_ramp = 1.0
        self.feed((li.EV_ABS, li.ABS_RY, 32767))
        self.tick(1.0, steps=100)
        total = sum(hy for _, hy in self.mouse.scrolls)
        self.assertLess(total, 0)
        self.assertAlmostEqual(
            abs(total), self.config.scroll_speed * 120, delta=130
        )


class PointerHidingTests(DaemonTestCase):
    """`[pointer] hide_on_press`: a press that is not pointing puts it away.

    What does the hiding is Hyprland, at a keystroke it is already watching
    for, so what these hold is which presses ask for one.
    """

    def test_a_press_with_nothing_to_do_with_the_pointer_puts_it_away(self):
        # From inside the menu, which is the surface that most wants the ring
        # off it: it is drawn over whatever the pointer was last left on. Y
        # here is a tap/hold - the hold rearranges the page - so it acts on
        # the release, the way every tap/hold does.
        self.daemon.set_menu(True)
        self.press("Y")                # guide:toggle, on the way back up
        self.release("Y")
        self.assertEqual(self.keyboard.nudges, 1)

    def test_a_click_leaves_it_where_it_is(self):
        # The one press that *is* the pointer working. Hiding it here would
        # take the ring away at the moment the burst says where it landed.
        self.press("X")                # click:middle
        self.release("X")
        self.assertEqual(self.keyboard.nudges, 0)

    def test_typing_is_left_to_the_compositor(self):
        # A key already hides it without being asked - that is the behaviour
        # this borrows - so asking again is a second keystroke per press.
        self.press("A")                # key:ENTER
        self.assertEqual(self.keyboard.nudges, 0)
        self.assertEqual(self.keyboard.chords,
                         [((), keymap.resolve("ENTER"), True)])

    def test_an_action_that_waits_for_the_release_hides_it_then(self):
        # The other way in: a binding that fires on the way up goes through
        # fire_once, and a workspace arriving with the ring still over the
        # last one is the whole complaint.
        self.press("R")
        self.assertEqual(self.keyboard.nudges, 0)
        self.release("R")
        self.assertEqual(self.keyboard.nudges, 1)

    def test_turned_off_nothing_touches_the_pointer(self):
        self.config.hide_pointer = False
        self.press("MINUS")
        self.assertEqual(self.keyboard.nudges, 0)

    def test_a_compositor_that_will_not_hide_it_says_so_once(self):
        # Turned off in Hyprland, every press here does nothing visible -
        # which looks exactly like a setting of ours that is broken.
        self.hypr.answers["getoption cursor:hide_on_key_press"] = {
            "option": "cursor:hide_on_key_press", "bool": False, "set": True,
        }
        with self.assertLogs("omapad", level="WARNING") as caught:
            self.daemon.check_pointer_hiding()
        self.assertIn("cursor:hide_on_key_press", caught.output[0])

    def test_a_compositor_that_will_says_nothing_at_all(self):
        self.hypr.answers["getoption cursor:hide_on_key_press"] = {
            "option": "cursor:hide_on_key_press", "bool": True, "set": True,
        }
        with self.assertNoLogs("omapad", level="WARNING"):
            self.daemon.check_pointer_hiding()

    def test_no_compositor_to_ask_is_not_a_complaint(self):
        # Everything that leaves this process is best-effort, this included:
        # the daemon runs with no Hyprland at all.
        with self.assertNoLogs("omapad", level="WARNING"):
            self.daemon.check_pointer_hiding()


class ScrollRampTests(DaemonTestCase):
    """[scroll] ramp: a stick held one way keeps getting faster."""

    def scrolled(self, seconds, steps=50):
        before = sum(abs(hy) for _, hy in self.mouse.scrolls)
        self.tick(seconds, steps=steps)
        return sum(abs(hy) for _, hy in self.mouse.scrolls) - before

    def push(self, value=32767, axis=None):
        self.feed((li.EV_ABS, axis or li.ABS_RY, value))

    def test_the_second_of_holding_beats_the_first(self):
        self.push()
        first = self.scrolled(0.4)
        second = self.scrolled(0.4)
        self.assertGreater(second, first * 1.3)

    def test_it_stops_climbing_at_the_ramp(self):
        self.config.scroll_ramp = 3.0
        self.config.scroll_ramp_ms = 500.0
        self.push()
        self.scrolled(1.0)                      # long past the top
        top = self.scrolled(0.5)
        self.assertAlmostEqual(
            top, self.config.scroll_speed * 120 * 0.5 * 3.0, delta=90
        )

    def test_letting_go_hands_the_speed_back(self):
        self.push()
        self.scrolled(1.5)                      # up at the top
        self.push(0)                            # back to rest
        self.tick(0.2, steps=10)
        self.push()
        self.assertAlmostEqual(
            self.scrolled(0.2), self.config.scroll_speed * 120 * 0.2, delta=60
        )

    def test_reversing_hands_it_back_too(self):
        """Somebody scrolling back up has gone too far, not warmed up."""
        self.push()
        self.scrolled(1.5)
        self.push(-32767)
        self.assertAlmostEqual(
            self.scrolled(0.2), self.config.scroll_speed * 120 * 0.2, delta=60
        )

    def test_a_wobble_across_the_other_axis_is_not_a_change_of_mind(self):
        self.push()
        self.scrolled(1.0)
        fast = self.scrolled(0.2)
        self.push(4000, axis=li.ABS_RX)         # a thumb wandering sideways
        self.assertAlmostEqual(self.scrolled(0.2), fast, delta=fast * 0.25)

    def test_it_can_be_turned_off(self):
        self.config.scroll_ramp = 1.0
        self.push()
        self.assertAlmostEqual(self.scrolled(0.4), self.scrolled(0.4), delta=60)

    def test_a_ramp_below_one_is_named(self):
        with self.assertRaises(config_module.ConfigError) as caught:
            config_module.Config({"scroll": {"ramp": 0.5}})
        self.assertIn("ramp", str(caught.exception))


class ButtonTests(DaemonTestCase):
    def test_enter_is_a_held_key(self):
        # Console scheme (07): A confirms with Enter.
        self.press("A")
        self.assertEqual(self.keyboard.chords, [((), keymap.resolve("ENTER"), True)])
        self.release("A")
        self.assertEqual(self.keyboard.chords[-1], ((), keymap.resolve("ENTER"), False))

    def test_right_trigger_is_a_held_left_click(self):
        # Console scheme (07): ZR clicks. ZL holds the window layer instead,
        # and its right click moved to Y.
        self.feed((li.EV_ABS, li.ABS_RZ, 255))
        self.assertEqual(self.mouse.buttons, [("left", True)])
        self.feed((li.EV_ABS, li.ABS_RZ, 0))
        self.assertEqual(self.mouse.buttons, [("left", True), ("left", False)])

    def test_y_is_a_held_right_click(self):
        self.press("Y")
        self.assertEqual(self.mouse.buttons, [("right", True)])
        self.release("Y")
        self.assertEqual(self.mouse.buttons[-1], ("right", False))

    def test_a_click_says_on_screen_where_it_landed(self):
        # The pad's own answer to a click is nothing at all - the thumb is on
        # a trigger that feels the same either way - so the screen has to
        # give one. See ripple.py.
        self.hypr.position = (640.0, 360.0)
        self.press("Y")
        state = self.ripple_client.sent[-1]
        self.assertEqual(state["b"], "right")
        self.assertEqual((state["x"], state["y"]), (640.0, 360.0))
        self.assertEqual(state["n"], 1)
        # Letting go is not a second click, and neither is it a burst.
        self.release("Y")
        self.assertEqual(len(self.ripple_client.sent), 1)

    def test_a_burst_turned_off_leaves_the_click_alone(self):
        self.daemon.config.ripple_enabled = False
        self.press("Y")
        self.assertEqual(self.mouse.buttons, [("right", True)])
        self.assertEqual(self.ripple_client.sent, [])

    def test_dpad_holds_the_arrow_key(self):
        self.feed((li.EV_ABS, li.ABS_HAT0Y, -1))
        self.assertEqual(self.keyboard.chords, [((), 103, True)])
        self.feed((li.EV_ABS, li.ABS_HAT0Y, 0))
        self.assertEqual(self.keyboard.chords[-1], ((), 103, False))

    def test_a_pad_that_drops_out_mid_press_does_not_leave_the_key_down(self):
        # The 2.4GHz dongle disappearing is a disconnect with no release
        # behind it. The key would stay down on the virtual keyboard, and the
        # compositor repeats a held key: one press of A typing Enter forever.
        self.press("A")
        self.assertEqual(self.keyboard.chords, [((), keymap.resolve("ENTER"), True)])
        self.daemon.disconnect()
        self.assertEqual(self.keyboard.chords[-1], ((), keymap.resolve("ENTER"), False))
        self.assertEqual(self.keyboard.released, 1)
        self.assertEqual(self.daemon.held, {})

    def test_a_pad_that_drops_out_mid_click_does_not_leave_the_button_down(self):
        self.press("Y")
        self.daemon.disconnect()
        self.assertEqual(self.mouse.buttons[-1], ("right", False))
        self.assertEqual(self.mouse.released, 1)

    def test_shoulder_switches_workspace_once_per_press(self):
        self.press("R")
        self.release("R")
        # 'r' walks the full workspace range so empty workspaces are not
        # skipped the way 'e' (existing) would.
        self.assertEqual(
            self.hypr.calls, ["hl.dsp.focus({ workspace = 'r+1' })"]
        )


class RumbleTests(DaemonTestCase):
    """`rumble = true` on a binding, and the tick a confirmation opens with."""

    def setUp(self):
        super().setUp()
        # Nothing shipped is marked any more - the shoulders stopped buzzing
        # when they moved to fire on release - so the flag needs its own
        # binding to be tested at all.
        self.config.bindings["base"]["Y"] = {
            "tap": "hypr:hl.dsp.window.center()", "rumble": True,
        }
        self.daemon.bindings.clear()

    def tick(self):
        """The effect id a plain tick plays - one of four uploaded now."""
        return self.daemon.rumble.effects["tick"]

    def test_a_binding_marked_rumble_ticks_the_pad(self):
        self.press("Y")
        self.release("Y")
        self.assertEqual(self.device.played, [self.tick()])

    def test_bindings_that_are_not_marked_stay_quiet(self):
        self.press("A")
        self.release("A")
        self.assertEqual(self.device.played, [])

    def test_switching_mode_ticks_the_pad_both_ways(self):
        # The switch is the press whose result you may not be looking at, so
        # it is felt going in and coming back out.
        self.daemon.set_mode("game")
        self.daemon.set_mode("desktop")
        self.assertEqual(self.device.played, [self.tick()] * 2)

    def test_a_switch_can_be_left_silent(self):
        self.config.mode_rumble = False
        self.daemon.set_mode("game")
        self.assertEqual(self.device.played, [])

    def test_a_tick_is_told_to_stop_once_its_length_is_up(self):
        # An Xbox pad runs its motors until something says otherwise, and the
        # stop the kernel owes the effect does not always arrive - which is
        # the tick that sticks on under a game or a browser.
        self.press("Y")
        self.release("Y")
        self.assertEqual(self.device.stopped, [])
        self.daemon.rumble.settle(time.monotonic() + 1.0)
        self.assertEqual(self.device.stopped, [self.tick()])

    def test_the_loop_stays_awake_for_a_tick_it_owes_a_stop(self):
        # On the idle poll the stop lands up to a quarter-second late, and a
        # click that long reads as a buzz.
        self.assertFalse(self.daemon.needs_tick())
        self.press("Y")
        self.release("Y")
        self.assertTrue(self.daemon.needs_tick())

    def test_a_pad_the_app_has_taken_neither_acts_nor_buzzes(self):
        self.daemon.handed_over = True
        self.press("Y")
        self.release("Y")
        self.assertEqual(self.hypr.calls, [])
        self.assertEqual(self.device.played, [])

    def test_a_pad_without_motors_costs_nothing(self):
        self.daemon.disconnect()
        self.device = FakeDevice(self.identity, rumble=False)
        self.daemon.attach(self.device)
        self.press("Y")
        self.release("Y")
        self.assertEqual(self.hypr.calls, ["hl.dsp.window.center()"])
        self.assertEqual(self.device.played, [])

    def test_the_effects_are_uploaded_once_and_given_back_on_unplug(self):
        # The three the shipped config asks for: the texture ships off.
        self.assertEqual(len(self.device.effects), 3)
        self.press("Y")
        self.release("Y")
        self.press("Y")
        self.release("Y")
        self.assertEqual(len(self.device.effects), 3)
        self.assertEqual(len(self.device.played), 2)
        self.daemon.disconnect()
        self.assertEqual(self.device.effects, {})


class TriggerTests(DaemonTestCase):
    def test_left_trigger_activates_window_layer(self):
        self.assertEqual(self.daemon.current_layer, "base")
        self.press("ZL")
        self.assertEqual(self.daemon.current_layer, "window")
        self.release("ZL")
        self.assertEqual(self.daemon.current_layer, "base")

    def test_layer_binding_replaces_base_binding(self):
        self.press("ZL")
        self.press("A")
        self.release("A")
        self.release("ZL")
        self.assertEqual(
            self.hypr.calls,
            ["hl.dsp.window.fullscreen({ mode = 'fullscreen' })"],
        )
        self.assertEqual(self.mouse.buttons, [])
        self.assertEqual(self.keyboard.chords, [])

    def test_layer_sticks_resize_and_move_the_window(self):
        self.press("ZL")
        self.feed((li.EV_ABS, li.ABS_X, 32767))
        self.daemon._last_window_flush = 0.0
        self.tick(0.5, steps=10)
        resizes = [c for c in self.hypr.calls if "window.resize" in c]
        self.assertTrue(resizes, "expected a resize dispatch")
        self.assertIn("relative = true", resizes[0])
        self.assertIn("x = ", resizes[0])

    def test_l_cycles_the_previous_workspace(self):
        self.press("L")
        self.release("L")
        self.assertEqual(
            self.hypr.calls, ["hl.dsp.focus({ workspace = 'r-1' })"]
        )

    def test_releasing_the_layer_releases_its_held_bindings(self):
        self.press("ZL")
        self.feed((li.EV_ABS, li.ABS_HAT0Y, -1))
        self.hypr.calls.clear()
        self.release("ZL")
        self.assertEqual(self.daemon.held, {})


class TapHoldTests(DaemonTestCase):
    def test_short_press_fires_the_tap_action(self):
        self.press("HOME")
        self.assertEqual(self.hypr.calls, [])
        self.release("HOME")
        self.assertEqual(self.hypr.calls, ["hl.dsp.window.cycle_next()"])
        self.assertEqual(self.daemon.mode, "desktop")

    def test_long_press_fires_the_hold_action(self):
        self.press("HOME")
        pressed_at = self.daemon.held["HOME"].pressed_at
        self.daemon.check_hold_timers(pressed_at + 1.0)
        self.assertEqual(self.daemon.mode, "game")
        self.release("HOME")
        self.assertEqual(self.hypr.calls, [])


class GameModeTests(DaemonTestCase):
    def test_game_mode_keeps_the_pad_and_keeps_working(self):
        # It once released the pad and switched everything off. Releasing is
        # the handover's job now, and it happens when an app asks for it.
        self.daemon.set_mode("game")
        self.assertTrue(self.device.grabbed)
        self.feed((li.EV_ABS, li.ABS_X, 32767))
        self.tick(1.0, steps=10)
        self.assertTrue(self.mouse.moves)

    def test_hold_still_returns_from_game_mode(self):
        self.daemon.set_mode("game")
        self.press("HOME")
        pressed_at = self.daemon.held["HOME"].pressed_at
        self.daemon.check_hold_timers(pressed_at + 1.0)
        self.assertEqual(self.daemon.mode, "desktop")

    def test_switching_mode_releases_a_held_click(self):
        self.feed((li.EV_ABS, li.ABS_RZ, 255))
        self.assertEqual(self.mouse.buttons, [("left", True)])
        self.daemon.set_mode("game")
        self.assertEqual(self.mouse.buttons[-1], ("left", False))
        self.assertEqual(self.daemon.held, {})

    def test_desktop_mode_grabs_the_pad(self):
        self.assertTrue(self.device.grabbed)


class CouchModeTests(DaemonTestCase):
    """Game mode is the couch environment: the desktop, with a bar on it.

    It was once the opposite - a hand-off that switched almost everything off -
    and that was the wrong model. Handing the pad to a game is a separate
    thing, and it happens by itself; see HandoverTests.
    """

    def test_everything_the_desktop_does_works_here_too(self):
        self.daemon.set_mode("game")
        self.press("A")
        self.assertEqual(
            self.keyboard.chords[-1], ((), keymap.resolve("ENTER"), True)
        )

    def test_the_pointer_is_not_switched_off(self):
        self.daemon.set_mode("game")
        self.feed((li.EV_ABS, li.ABS_X, 32767))
        self.tick(1.0, steps=50)
        self.assertGreater(sum(dx for dx, _ in self.mouse.moves), 0)

    def test_a_held_layer_still_opens(self):
        self.daemon.set_mode("game")
        self.press("ZL")
        self.assertEqual(self.daemon.current_layer, "window")
        self.press("B")
        self.release("B")
        self.assertEqual(self.hypr.calls, ["hl.dsp.window.close()"])

    def test_the_couch_layer_overrides_what_it_names(self):
        self.config.bindings["game"] = {"A": "click:left"}
        self.daemon.bindings.clear()
        self.daemon.set_mode("game")
        self.press("A")
        self.assertEqual(self.mouse.buttons, [("left", True)])

    def test_and_falls_through_for_what_it_does_not(self):
        self.config.bindings["game"] = {"A": "click:left"}
        self.daemon.bindings.clear()
        self.daemon.set_mode("game")
        self.press("B")          # untouched: the base layer's Esc
        self.assertEqual(
            self.keyboard.chords[-1], ((), keymap.resolve("ESC"), True)
        )

    def test_the_pad_stays_ours(self):
        self.daemon.set_mode("game")
        self.assertTrue(self.device.grabbed)


class HandoverTests(DaemonTestCase):
    """The pad goes to the app in front when that app has opened it."""

    def hand_over(self, wanted=True):
        # The real answer comes from /proc; the decision it feeds is what
        # these are about.
        self.daemon.handed_over = wanted
        self.daemon.apply_grab()

    def test_handing_over_lets_go_of_the_pad(self):
        self.assertTrue(self.device.grabbed)
        self.hand_over()
        self.assertFalse(self.device.grabbed)

    def test_and_taking_it_back_grabs_again(self):
        self.hand_over()
        self.hand_over(False)
        self.assertTrue(self.device.grabbed)

    def test_the_grab_waits_for_a_button_the_app_is_still_holding(self):
        # The shoulder held to walk a workspace out of Steam is let go after
        # the focus change that takes the pad back. Grabbing on the change
        # would keep that release from Steam, which then reads every Guide
        # press as a chord and opens nothing.
        self.hand_over()
        self.press("L")
        self.hand_over(False)
        self.assertFalse(self.device.grabbed)
        self.release("L")
        self.assertTrue(self.device.grabbed)

    def test_but_not_for_ever(self):
        self.hand_over()
        self.press("L")
        self.hand_over(False)
        # A button the kernel believes is held for ever - a dongle that
        # dropped mid-press - must not cost the grab outright.
        self.daemon._grab_wait = 0.0
        self.daemon.apply_grab()
        self.assertTrue(self.device.grabbed)

    def test_and_not_at_all_when_the_wait_is_off(self):
        self.config.grab_settle = 0.0
        self.hand_over()
        self.press("L")
        self.hand_over(False)
        self.assertTrue(self.device.grabbed)

    def test_letting_go_of_the_pad_never_waits(self):
        # An app that gets a release it never saw the press of ignores it, so
        # only taking the pad has anything to strand.
        self.press("L")
        self.hand_over()
        self.assertFalse(self.device.grabbed)

    def test_ordinary_bindings_stop_while_the_app_has_it(self):
        self.hand_over()
        self.press("A")
        self.release("A")
        self.assertEqual(self.keyboard.chords, [])

    def test_the_chord_still_gets_through(self):
        # The one thing that would make the whole arrangement useless is a
        # menu you cannot open over a running game. Two buttons at once is not
        # an input a game asks for, so that is where the door went.
        self.hand_over()
        self.press("MINUS")
        self.press("PLUS")
        self.assertTrue(self.daemon.menu_open)

    def test_but_the_single_button_summons_stand_aside(self):
        # Back and Start are buttons every game binds. Summoning on them over
        # a cloud session puts our menu on screen every time you reach for the
        # game's own pause screen, which is the same fault the block exists to
        # prevent, pointing the other way.
        self.hand_over()
        self.press("PLUS")
        self.release("PLUS")
        self.assertFalse(self.daemon.menu_open)
        self.press("MINUS")
        self.release("MINUS")
        self.assertFalse(self.daemon.osk_open)

    def test_the_sticks_stop_driving_the_pointer(self):
        # A stray press is over as soon as the thumb comes off; a stick left
        # over is a pointer sliding across the game for as long as it is held,
        # and an app reading that pointer has stopped reading the pad.
        self.hand_over()
        self.feed((li.EV_ABS, li.ABS_X, 32767))
        self.tick(1.0, steps=100)
        self.assertEqual(self.mouse.moves, [])
        self.assertFalse(self.daemon.sticks_live())

    def test_and_start_again_when_the_pad_comes_back(self):
        self.hand_over()
        self.feed((li.EV_ABS, li.ABS_X, 32767))
        self.tick(1.0, steps=100)
        self.hand_over(False)
        self.tick(1.0, steps=100)
        self.assertTrue(any(dx for dx, _ in self.mouse.moves))

    def test_a_surface_takes_the_sticks_back_with_the_pad(self):
        # The keyboard is pointed at with a stick, so a surface that takes the
        # pad back has to take them too - the same rule the grab follows.
        self.hand_over()
        self.daemon.set_osk(True)
        self.feed((li.EV_ABS, li.ABS_X, 32767))
        self.tick(1.0, steps=100)
        self.assertTrue(any(dx for dx, _ in self.mouse.moves))

    def test_a_profile_may_refuse_the_pad_outright(self):
        # An application that opens the pad without being played with -
        # Discord polls the Gamepad API for its own keybinds - is a fact
        # /proc cannot see, so the profile says it instead.
        with unittest.mock.patch.object(daemon_module.handover, "wants_pad",
                                        return_value=True):
            self.daemon.focus_pid = 4321
            self.daemon.update_handover(force=True)
            self.assertTrue(self.daemon.handed_over)
            self.daemon.active_profile = {"name": "discord", "handover": False}
            self.daemon.update_handover(force=True)
        self.assertFalse(self.daemon.handed_over)
        self.assertTrue(self.device.grabbed)
        self.assertTrue(self.daemon.sticks_live())

    def test_the_profile_is_swapped_before_the_pad_is_asked_about(self):
        # The other way round, every focus change answered for the window
        # that had just left - and the refusal would land a window late.
        # A class whose profile does *not* refuse the pad: one that did would
        # short-circuit the question this is about.
        self.hypr.answers["activewindow"] = {
            "class": "foot", "title": "", "pid": 77,
        }
        seen = []
        real = self.daemon.set_active_profile

        def record(window_class):
            real(window_class)
            seen.append(("profile", window_class))

        self.daemon.set_active_profile = record
        with unittest.mock.patch.object(
            daemon_module.handover, "wants_pad",
            side_effect=lambda *a, **k: seen.append(("asked", None)) or False,
        ):
            self.daemon.seed_active_window()
        self.assertEqual([step for step, _ in seen], ["profile", "asked"])

    def test_a_summon_that_says_nothing_still_reaches_past(self):
        # `reaches_past = false` on PLUS and MINUS is the shipped config's
        # choice, not the rule: a summon nobody has ruled on is still what an
        # arrangement like this cannot do without.
        self.hand_over()
        self.press("HOME")
        pressed_at = self.daemon.held["HOME"].pressed_at
        self.daemon.check_hold_timers(pressed_at + 1.0)
        self.assertEqual(self.daemon.mode, "game")

    def test_an_open_surface_takes_the_pad_back(self):
        # Otherwise the D-pad drives the menu and the game at the same time.
        self.hand_over()
        self.assertFalse(self.device.grabbed)
        self.daemon.set_menu(True)
        self.assertTrue(self.device.grabbed)
        self.daemon.set_menu(False)
        self.assertFalse(self.device.grabbed)

    def test_and_the_surface_can_be_driven_while_it_is_up(self):
        self.hand_over()
        self.daemon.set_menu(True)
        before = self.daemon.menu.selected
        # Down: it opens on the first tile now, and up from there is the rim.
        self.feed((li.EV_ABS, li.ABS_HAT0Y, 1))
        self.assertNotEqual(self.daemon.menu.selected, before)

    def test_the_way_out_is_still_reachable(self):
        self.hand_over()
        self.press("HOME")
        pressed_at = self.daemon.held["HOME"].pressed_at
        self.daemon.check_hold_timers(pressed_at + 1.0)
        self.assertEqual(self.daemon.mode, "game")

    def test_an_announced_hold_reaches_past_the_app(self):
        # Steam owns the pad in Big Picture, which leaves no way back to the
        # desktop; a hold that ticks, says what is coming and can be cancelled
        # is deliberate enough to be that way.
        self.config.profiles.insert(0, {
            "name": "pretend",
            "match": ["pretendapp"],
            "bindings": {
                "R": {"hold": "hypr:hl.dsp.focus({ workspace = 'r+1' })",
                      "hold_ms": 2000, "confirm_ms": 2000},
            },
        })
        self.daemon.set_active_profile("pretendapp")
        self.hand_over()
        self.press("R")
        pressed_at = self.daemon.held["R"].pressed_at
        self.daemon.check_hold_timers(pressed_at + 2.1)   # announced
        self.assertEqual(self.hypr.calls, [])
        self.daemon.check_hold_timers(pressed_at + 4.1)   # and confirmed
        self.assertEqual(self.hypr.calls, ["hl.dsp.focus({ workspace = 'r+1' })"])

    def test_the_window_layer_stands_aside_too(self):
        # ZL is aim in a game and it holds a layer here; the layer opens, but
        # nothing inside it fires, because the game is using that trigger.
        self.hand_over()
        self.press("ZL")
        self.assertEqual(self.daemon.current_layer, "window")
        self.press("A")
        self.release("A")
        self.assertEqual(self.hypr.calls, [])

    def test_a_binding_marked_reaches_past_fires_anyway(self):
        # Nothing ships with this - the shipped answer over a game is the
        # chord and the confirmed hold - but a binding may say so, and a
        # cloud session that wants a pointer is why it can.
        self.config.profiles.insert(0, {
            "name": "pretend",
            "match": ["pretendapp"],
            "bindings": {"Y": {"tap": "click:left", "reaches_past": True}},
        })
        self.daemon.set_active_profile("pretendapp")
        self.hand_over()
        self.press("Y")
        self.assertEqual(self.mouse.buttons, [("left", True)])

    def test_a_layer_may_say_it_for_all_of_its_rows(self):
        window = self.config.layer("window")
        window.reaches_past = True
        self.daemon.bindings.clear()
        self.hand_over()
        self.press("ZL")
        self.press("A")
        self.release("A")
        self.assertEqual(
            self.hypr.calls,
            ["hl.dsp.window.fullscreen({ mode = 'fullscreen' })"],
        )

    def test_and_a_row_inside_it_may_still_opt_out(self):
        window = self.config.layer("window")
        window.reaches_past = True
        self.config.bindings["window"]["B"] = {
            "tap": "hypr:hl.dsp.window.close()", "reaches_past": False,
        }
        self.daemon.bindings.clear()
        self.hand_over()
        self.press("ZL")
        self.press("B")
        self.release("B")
        self.assertEqual(self.hypr.calls, [])

    def test_a_plain_hold_does_not(self):
        # Half a second is something you do by accident with a game running.
        self.config.profiles.insert(0, {
            "name": "pretend",
            "match": ["pretendapp"],
            "bindings": {"R": {"hold": "hypr:hl.dsp.window.close()",
                               "hold_ms": 500}},
        })
        self.daemon.set_active_profile("pretendapp")
        self.hand_over()
        self.press("R")
        pressed_at = self.daemon.held["R"].pressed_at
        self.daemon.check_hold_timers(pressed_at + 1.0)
        self.assertEqual(self.hypr.calls, [])

    def confirming_profile(self, hold_ms=2000, confirm_ms=2000):
        # Its own class rather than "steam": the shipped [profile.steam] would
        # match first and the test would be reading that instead.
        self.config.profiles.insert(0, {
            "name": "pretend",
            "match": ["pretendapp"],
            "bindings": {
                "R": {"hold": "hypr:hl.dsp.focus({ workspace = 'r+1' })",
                      "hold_ms": hold_ms, "confirm_ms": confirm_ms},
            },
        })
        self.daemon.set_active_profile("pretendapp")

    def test_a_binding_can_take_both_waits_from_the_config(self):
        """`confirm = true` is the shipped profiles' way of not repeating two
        numbers on every binding that reaches past an app."""
        binding = actions.Binding({"hold": "mode:toggle", "confirm": True},
                                  (900, 400))
        self.assertEqual((binding.hold_ms, binding.confirm_ms), (900, 400))

    def test_and_its_own_numbers_still_win(self):
        binding = actions.Binding(
            {"hold": "mode:toggle", "confirm": True, "confirm_ms": 100},
            (900, 400))
        self.assertEqual((binding.hold_ms, binding.confirm_ms), (900, 100))

    def test_while_a_plain_hold_is_left_short(self):
        # The announced pair is long because it reaches past an app; an
        # ordinary hold is a shortcut and answers to neither number.
        binding = actions.Binding({"hold": "mode:toggle"}, (900, 400))
        self.assertEqual((binding.hold_ms, binding.confirm_ms),
                         (actions.HOLD_MS, 0))

    def test_and_a_confirm_with_nothing_to_confirm_is_named_by_check(self):
        with self.assertRaises(actions.ActionError):
            actions.Binding({"tap": "mode:toggle", "confirm": True})

    def test_the_bar_is_told_a_countdown_has_started(self):
        # The countdown is otherwise invisible: a tick and a notification, both
        # away from the thing you are looking at.
        self.config.gamebar_enabled = True
        self.daemon.set_mode("game")
        self.confirming_profile()
        self.press("R")
        # The first phase is the ramp: dimmed to full over hold_ms. The badge
        # is the pad's own printing - RB, because the test pad is an XInput one.
        self.assertEqual(self.daemon.gamebar.holding,
                         {"b": "RB", "ms": 2000, "armed": False})

    def test_and_that_it_has_armed_when_the_pad_ticks(self):
        # The tick and the notification both happen away from the bar, so the
        # badge says it too rather than leaving the countdown to be felt.
        self.config.gamebar_enabled = True
        self.daemon.set_mode("game")
        self.confirming_profile()
        self.press("R")
        pressed_at = self.daemon.held["R"].pressed_at
        self.daemon.check_hold_timers(pressed_at + 2.1)
        self.assertEqual(self.daemon.gamebar.holding,
                         {"b": "RB", "ms": 2000, "armed": True})

    def test_and_that_it_has_stopped_when_the_button_comes_up(self):
        self.config.gamebar_enabled = True
        self.daemon.set_mode("game")
        self.confirming_profile()
        self.press("R")
        self.release("R")
        self.assertIsNone(self.daemon.gamebar.holding)

    def test_and_when_it_fires(self):
        self.config.gamebar_enabled = True
        self.daemon.set_mode("game")
        self.confirming_profile()
        self.press("R")
        pressed_at = self.daemon.held["R"].pressed_at
        self.daemon.check_hold_timers(pressed_at + 2.1)   # announces
        self.daemon.check_hold_timers(pressed_at + 4.1)   # then fires
        self.assertIsNone(self.daemon.gamebar.holding)

    def test_a_plain_hold_is_over_before_a_bar_could_say_anything(self):
        self.config.gamebar_enabled = True
        self.daemon.set_mode("game")
        self.config.profiles.insert(0, {
            "name": "pretend", "match": ["pretendapp"],
            "bindings": {"R": {"hold": "hypr:hl.dsp.window.close()",
                               "hold_ms": 500}},
        })
        self.daemon.set_active_profile("pretendapp")
        self.press("R")
        self.assertIsNone(self.daemon.gamebar.holding)

    def test_the_bar_gets_out_of_the_way(self):
        self.config.gamebar_enabled = True
        self.daemon.set_mode("game")
        self.assertTrue(self.daemon.gamebar_open)
        self.daemon.handed_over = True
        self.daemon.apply_gamebar()
        self.assertFalse(self.daemon.gamebar_open)

    def test_nothing_of_ours_stays_on_screen(self):
        self.daemon.set_osk(True)
        self.daemon.focus_pid = None
        self.daemon.handed_over = False
        with unittest.mock.patch.object(
            daemon_module.handover, "wants_pad", lambda *a, **k: True
        ):
            self.daemon.update_handover()
        self.assertTrue(self.daemon.handed_over)
        self.assertFalse(self.daemon.osk_open)

class WorkspaceLockTests(DaemonTestCase):
    """The hand-off said by hand: the pad is the app's, and a chord is all
    that is left of ours."""

    def unwanted(self):
        """No holder in the focused window's tree, whoever asks."""
        return unittest.mock.patch.object(daemon_module.handover, "wants_pad",
                                          return_value=False)

    def test_it_gives_the_pad_to_the_app_in_front(self):
        # The case /proc cannot answer: a game whose opening of the pad the
        # walk misses gets nothing, while the pad drives the desktop over it.
        with self.unwanted():
            self.daemon.focus_pid = 4321
            self.daemon.set_locked(True)
        self.assertTrue(self.daemon.handed_over)
        self.assertFalse(self.device.grabbed)

    def test_and_the_next_walk_of_proc_does_not_take_it_back(self):
        with self.unwanted():
            self.daemon.set_locked(True)
            self.daemon.update_handover(force=True)
        self.assertTrue(self.daemon.handed_over)

    def test_it_outranks_a_profile_that_refuses_the_hand_off(self):
        # `handover = false` is a fact about an application; the lock is a
        # person saying otherwise about this moment, which wins.
        self.daemon.active_profile = {"name": "discord", "handover": False}
        with self.unwanted():
            self.daemon.set_locked(True)
        self.assertTrue(self.daemon.handed_over)

    def test_unlocking_asks_the_program_again(self):
        with self.unwanted():
            self.daemon.set_locked(True)
            self.daemon.set_locked(False)
        self.assertFalse(self.daemon.handed_over)
        self.assertTrue(self.device.grabbed)

    def test_an_announced_hold_stops_reaching_past_it(self):
        # Steam's profile puts a workspace behind a shoulder held and
        # confirmed. That is deliberate at a desk and it is also a shoulder
        # rested on for four seconds, which happens mid-fight.
        self.daemon.set_active_profile("steam")
        self.daemon.handed_over = True
        self.press("R")
        pressed_at = self.daemon.held["R"].pressed_at
        self.daemon.check_hold_timers(pressed_at + 2.1)
        self.daemon.check_hold_timers(pressed_at + 4.1)
        self.assertEqual(self.hypr.calls,
                         ["hl.dsp.focus({ workspace = 'r+1' })"])
        self.release("R")
        self.hypr.calls = []
        self.daemon.locked = True
        self.press("R")
        pressed_at = self.daemon.held["R"].pressed_at
        self.daemon.check_hold_timers(pressed_at + 2.1)
        self.daemon.check_hold_timers(pressed_at + 4.1)
        self.assertEqual(self.hypr.calls, [])

    def test_and_it_does_not_announce_what_it_will_not_let_through(self):
        # The announcement is a tick and a notification, both of which land on
        # top of the game. A countdown to nothing is worse than silence.
        self.daemon.set_active_profile("steam")
        self.daemon.handed_over = True
        self.daemon.locked = True
        self.config.notify = True
        self.press("R")
        pressed_at = self.daemon.held["R"].pressed_at
        self.daemon.check_hold_timers(pressed_at + 2.1)
        self.assertEqual(self.session.notifications, [])
        self.assertEqual(self.device.played, [])
        self.assertIsNone(self.daemon.gamebar.holding)
        # And a hold that outlives the lock still announces itself.
        self.daemon.locked = False
        self.daemon.check_hold_timers(pressed_at + 2.2)
        self.assertEqual(len(self.session.notifications), 1)

    def test_and_so_does_a_binding_that_bought_its_way_past(self):
        self.config.profiles.insert(0, {
            "name": "pretend", "match": ["pretendapp"],
            "bindings": {"X": {"tap": "click:left", "reaches_past": True}},
        })
        self.daemon.set_active_profile("pretendapp")
        self.daemon.handed_over = True
        self.press("X")
        self.release("X")
        self.assertTrue(self.mouse.buttons)
        self.mouse.buttons = []
        self.daemon.locked = True
        self.press("X")
        self.release("X")
        self.assertEqual(self.mouse.buttons, [])

    def test_the_menu_chord_is_the_way_back_out(self):
        # The lock names the menu in what it says, so the menu has to answer.
        self.daemon.handed_over = True
        self.daemon.locked = True
        self.press("MINUS")
        self.press("PLUS")
        self.assertTrue(self.daemon.menu_open)

    def test_and_the_menu_it_opens_still_drives(self):
        self.daemon.handed_over = True
        self.daemon.locked = True
        self.daemon.set_menu(True)
        before = self.daemon.menu.selected
        # Down: it opens on the first tile now, and up from there is the rim.
        self.feed((li.EV_ABS, li.ABS_HAT0Y, 1))
        self.assertNotEqual(self.daemon.menu.selected, before)

    def test_a_trigger_and_b_locks_over_a_game(self):
        for trigger in ("ZR", "ZL"):
            self.daemon.locked = False
            self.daemon.handed_over = True
            self.press(trigger)
            self.press("B")
            self.assertTrue(self.daemon.locked, trigger)
            self.release("B")
            self.release(trigger)

    def test_but_leaves_the_same_two_buttons_alone_on_the_desktop(self):
        # ZL + B closes the window in every layer and every profile, and that
        # press is not the lock's to take.
        self.press("ZL")
        self.press("B")
        self.release("B")
        self.release("ZL")
        self.assertFalse(self.daemon.locked)
        self.assertEqual(self.hypr.calls, ["hl.dsp.window.close()"])

    def test_and_leaves_the_right_trigger_a_click_that_can_drag(self):
        # A chord member cannot fire on the way down, so a live lock chord on
        # ZR would cost the desktop its held left click.
        self.press("ZR")
        self.assertEqual(self.mouse.buttons, [("left", True)])

    def test_the_chord_does_not_fire_twice_over(self):
        self.daemon.handed_over = True
        self.daemon.locked = True
        self.config.notify = True
        self.press("ZR")
        self.press("B")
        self.assertEqual(self.session.notifications, [])

    def test_it_says_where_the_way_out_is(self):
        self.config.notify = True
        self.daemon.handed_over = True
        self.daemon.set_locked(True)
        self.assertIn("menu", self.session.notifications[-1][1])

    def test_the_row_ticks_while_it_is_on(self):
        # The tick is the only thing on screen that says the lock is on.
        row = actions.parse("lock:toggle")
        self.assertFalse(row.state(self.daemon.ctx))
        self.daemon.handed_over = True
        row.press(self.daemon.ctx)
        self.assertTrue(self.daemon.locked)
        self.assertTrue(row.state(self.daemon.ctx))
        row.press(self.daemon.ctx)
        self.assertFalse(self.daemon.locked)

    def menu_labels(self):
        return [tile["item"]["label"] for tile in self.daemon.menu.tiles]

    def pick_the_row(self):
        # The tile is offered only while there is something to lock to, and
        # it is on the chip the menu opens on. Walked to rather than opened
        # on: the menu comes back where it was left, and a tile that overrode
        # that would take that answer away - see `open_on`, which is still
        # there for anyone who wants the other behaviour.
        self.daemon.set_menu(True)
        self.assertIn("Workspace lock", self.menu_labels())
        self.assertEqual(self.daemon.menu.group, 0)
        self.assertTrue(self.daemon.menu.select_id("workspace-lock"))

    def test_the_row_is_not_offered_where_there_is_nothing_to_lock_to(self):
        # On a desktop the lock would hand the pad to a terminal and leave you
        # finding the menu again to take it back.
        self.daemon.set_menu(True)
        self.assertNotIn("Workspace lock", self.menu_labels())
        self.daemon.set_menu(False)
        self.daemon.handed_over = True
        self.daemon.set_menu(True)
        self.assertIn("Workspace lock", self.menu_labels())

    def test_the_menu_row_is_the_way_back_out(self):
        # Game mode is the couch, and the game the walk missed is exactly the
        # one you are sitting in front of there.
        self.daemon.set_mode("game")
        with self.unwanted():
            self.pick_the_row()
            self.daemon.menu_command("press")
            self.assertTrue(self.daemon.locked)
            self.assertTrue(self.daemon.handed_over)
            # Locking puts every surface of ours away - the pad is the app's.
            self.assertFalse(self.daemon.menu_open)
            self.pick_the_row()
            self.daemon.menu_command("press")
        self.assertFalse(self.daemon.locked)
        self.assertFalse(self.daemon.handed_over)
        self.assertTrue(self.daemon.menu_open, "unlocking leaves the menu up")

    def test_the_bar_widget_is_told(self):
        self.daemon.handed_over = True
        self.daemon.set_locked(True)
        self.assertTrue(self.daemon.status_state()["locked"])

    def test_it_can_be_driven_without_the_pad(self):
        self.assertIn("lock=on", self.daemon.handle_control("lock on"))
        self.assertTrue(self.daemon.locked)
        self.assertIn("lock=off", self.daemon.handle_control("lock toggle"))
        self.assertFalse(self.daemon.locked)
        self.assertIn("unknown lock command",
                      self.daemon.handle_control("lock sideways"))

    def test_a_lock_that_is_not_a_word_is_named(self):
        with self.assertRaises(actions.ActionError):
            actions.parse("lock:sideways")


class KeepingThePadTests(DaemonTestCase):
    """The hand-off said by hand the other way: the app opened the pad and is
    not being played with, so we keep it."""

    def wanted(self):
        """/proc says the focused window's tree has the pad open."""
        return unittest.mock.patch.object(daemon_module.handover, "wants_pad",
                                          return_value=True)

    def test_it_takes_the_pad_back_from_an_app_that_has_opened_it(self):
        # A cloud client opens the pad as its page loads, and the launcher
        # screen in front of the stream reads no pad at all: /proc is right
        # and there is still nothing to press.
        with self.wanted():
            self.daemon.focus_pid = 4321
            self.daemon.update_handover(force=True)
            self.assertTrue(self.daemon.handed_over)
            self.daemon.set_keeping(True)
        self.assertFalse(self.daemon.handed_over)
        self.assertTrue(self.device.grabbed)

    def test_and_the_next_walk_of_proc_does_not_hand_it_over_again(self):
        with self.wanted():
            self.daemon.set_keeping(True)
            self.daemon.update_handover(force=True)
        self.assertFalse(self.daemon.handed_over)

    def test_turning_it_off_asks_the_program_again(self):
        with self.wanted():
            self.daemon.set_keeping(True)
            self.daemon.set_keeping(False)
        self.assertTrue(self.daemon.handed_over)

    def test_the_two_overrides_cannot_both_be_on(self):
        # One question with two answers: the second one asked is the one that
        # stands, rather than two overrides arguing about one pad.
        with self.wanted():
            self.daemon.set_keeping(True)
            self.daemon.set_locked(True)
            self.assertFalse(self.daemon.keeping)
            self.daemon.set_keeping(True)
        self.assertFalse(self.daemon.locked)

    def test_every_binding_fires_again(self):
        # The whole point: with the pad ours there is nothing to reach past,
        # so the menu is a plain press rather than a chord.
        self.daemon.handed_over = True
        self.assertFalse(self.daemon.allowed(actions.NoAction(), "base"))
        with self.wanted():
            self.daemon.set_keeping(True)
        self.assertTrue(self.daemon.allowed(actions.NoAction(), "base"))

    def menu_labels(self):
        return [item["label"] for item in self.daemon.menu.items]

    def test_the_row_is_offered_where_there_is_a_pad_to_keep(self):
        # On a desktop the pad is already ours, and a row that changes nothing
        # is a row that reads as broken.
        self.daemon.set_menu(True)
        self.assertNotIn("Keep the controller", self.menu_labels())
        self.daemon.set_menu(False)
        self.daemon.handed_over = True
        self.daemon.set_menu(True)
        self.assertIn("Keep the controller", self.menu_labels())

    def test_the_row_stays_while_it_is_on(self):
        # Otherwise turning it on takes away the only way of turning it off.
        with self.wanted():
            self.daemon.set_keeping(True)
        self.daemon.set_menu(True)
        self.assertIn("Keep the controller", self.menu_labels())

    def test_the_row_ticks_while_it_is_on(self):
        row = actions.parse("keep:toggle")
        self.assertFalse(row.state(self.daemon.ctx))
        row.press(self.daemon.ctx)
        self.assertTrue(self.daemon.keeping)
        self.assertTrue(row.state(self.daemon.ctx))
        row.press(self.daemon.ctx)
        self.assertFalse(self.daemon.keeping)

    def test_the_bar_widget_is_told(self):
        self.daemon.set_keeping(True)
        self.assertTrue(self.daemon.status_state()["kept"])

    def test_it_can_be_driven_without_the_pad(self):
        self.assertIn("keep=on", self.daemon.handle_control("keep on"))
        self.assertTrue(self.daemon.keeping)
        self.assertIn("keep=off", self.daemon.handle_control("keep toggle"))
        self.assertFalse(self.daemon.keeping)
        self.assertIn("unknown keep command",
                      self.daemon.handle_control("keep sideways"))
        self.assertIn("keep=off", self.daemon.handle_control("status"))

    def test_a_keep_that_is_not_a_word_is_named(self):
        with self.assertRaises(actions.ActionError):
            actions.parse("keep:sideways")


class BadConfigTests(unittest.TestCase):
    def test_a_setting_written_into_a_bindings_table_is_named_not_crashed_on(self):
        # `hide_bar_in_game = true` one table too low is a plain typo, and
        # `omapad check` exists to say which row is wrong.
        with self.assertRaises(actions.ActionError):
            actions.Binding(True)
        with self.assertRaises(actions.ActionError):
            actions.Binding({"tap": 12})


class StatusViewTests(DaemonTestCase):
    """What the bar widget is told, and when."""

    def setUp(self):
        super().setUp()
        self.status = self.status_client

    def test_the_payload_says_what_the_daemon_is_doing(self):
        self.daemon.push_status_view()
        state = self.status.sent[-1]
        self.assertEqual(state["mode"], "desktop")
        self.assertTrue(state["connected"])
        self.assertEqual(state["pad"], self.device.name.strip())
        self.assertEqual(state["profile"], "")

    def test_a_mode_switch_is_pushed_at_once(self):
        self.daemon.set_mode("game")
        self.assertEqual(self.status.sent[-1]["mode"], "game")

    def test_an_app_profile_is_pushed_as_focus_moves(self):
        self.config.profiles.append({
            "name": "browser", "match": ["chromium"], "bindings": {},
        })
        self.daemon.set_active_profile("chromium")
        self.assertEqual(self.status.sent[-1]["profile"], "browser")

    def test_a_pad_that_goes_away_says_so(self):
        self.daemon.disconnect()
        state = self.status.sent[-1]
        self.assertFalse(state["connected"])
        self.assertEqual(state["pad"], "")


class BarInGameModeTests(DaemonTestCase):
    """Omarchy's bar, while the game has the pad."""

    def bar_calls(self):
        return [c for c in self.session.spawned if "toggle bar" in c]

    def test_the_two_bars_are_one_decision_defaulted_twice(self):
        # Game mode that hid Omarchy's bar and drew nothing back left a blank
        # screen with no way out; game mode that hid neither was a mode you
        # could not see. Both ship on, and they ship on together.
        shipped = shipped_config()
        self.assertTrue(shipped.hide_bar_in_game)
        self.assertTrue(shipped.gamebar_enabled)

    def test_turning_it_off_leaves_the_users_bar_alone(self):
        # A config that says not to must not reach for the bar in either
        # direction - not on the way in, and not on the way back out.
        self.config.hide_bar_in_game = False
        self.daemon.set_mode("game")
        self.daemon.set_mode("desktop")
        self.assertEqual(self.bar_calls(), [])

    def test_game_mode_hides_it_and_desktop_puts_it_back(self):
        # `omarchy toggle bar <action>` acts on the *bar-off flag*, so `on`
        # hides the bar and `off` restores it - the opposite of how it reads.
        # Getting this backwards hid the bar on the desktop and showed it in
        # game mode, which is why the direction is pinned here.
        self.config.hide_bar_in_game = True
        self.daemon.set_mode("game")
        # Said once by the switch and again by our own bar opening: the
        # command names a flag rather than toggling one, so what matters is
        # which way every call points, not how many there are.
        self.assertEqual(set(self.bar_calls()), {"omarchy toggle bar on"})
        self.daemon.set_mode("desktop")
        self.assertEqual(self.bar_calls()[-1], "omarchy toggle bar off")

    def test_shutting_down_in_game_mode_still_gives_it_back(self):
        # Otherwise a daemon that dies there leaves a desktop with no bar and
        # no obvious way to work out why.
        self.config.hide_bar_in_game = True
        self.daemon.set_mode("game")
        self.daemon.shutdown()
        self.assertEqual(self.bar_calls()[-1], "omarchy toggle bar off")

    def test_ours_opening_says_again_which_bar_the_screen_should_have(self):
        # The flag Omarchy's bar follows is a file anybody may flip, and the
        # shell's own watch on it is documented as missing changes that land
        # together. Either way the desktop bar comes back under ours and the
        # screen has two along one edge, and nothing said otherwise until the
        # next mode switch.
        self.config.hide_bar_in_game = True
        self.config.gamebar_enabled = True
        self.daemon.set_mode("game")
        self.session.spawned.clear()
        self.daemon.set_locked(True)      # ours goes away with the pad
        self.assertEqual(self.bar_calls(), [])
        self.daemon.set_locked(False)     # and comes back saying it again
        self.assertEqual(self.bar_calls(), ["omarchy toggle bar on"])

    def test_a_session_that_starts_in_game_mode_hides_it_too(self):
        # No switch to hang it on, and our own bar opens there regardless.
        self.config.hide_bar_in_game = True
        self.daemon.mode = "game"
        self.daemon.start()
        self.assertEqual(self.bar_calls()[-1], "omarchy toggle bar on")

    def test_a_machine_without_omarchy_is_not_a_daemon_that_stops(self):
        self.config.hide_bar_in_game = True

        def refuse(command):
            raise OSError("no such command")

        self.session.spawn = refuse
        self.daemon.set_mode("game")
        self.assertEqual(self.daemon.mode, "game")


class IdleInGameModeTests(DaemonTestCase):
    """The screensaver and lock, while the game has the screen."""

    def idle_calls(self):
        return [c for c in self.session.spawned if "toggle idle" in c]

    def test_it_ships_on_with_game_mode(self):
        # Game mode is the couch; an idle-fallen desktop at its foot is game
        # mode talking over the one screen it exists for. So it ships on, the
        # same default as `hide_bar_in_game`.
        self.assertTrue(shipped_config().stay_awake_in_game)

    def test_turning_it_off_leaves_idle_alone(self):
        # A config that says not to must not reach for idle in either
        # direction - not on the way in, and not on the way back out.
        self.config.stay_awake_in_game = False
        self.daemon.set_mode("game")
        self.daemon.set_mode("desktop")
        self.assertEqual(self.idle_calls(), [])

    def test_game_mode_stays_awake_and_desktop_gives_idle_back(self):
        # `omarchy toggle idle <action>` is a flag flip; `stay-awake` while
        # the game is up, `allow-idle` the moment the desktop is back.
        self.config.stay_awake_in_game = True
        self.daemon.set_mode("game")
        self.assertEqual(self.idle_calls()[-1], "omarchy toggle idle stay-awake")
        self.daemon.set_mode("desktop")
        self.assertEqual(self.idle_calls()[-1], "omarchy toggle idle allow-idle")

    def test_shutting_down_in_game_mode_still_gives_idle_back(self):
        # Otherwise a daemon that dies there leaves a screen that never idles
        # by mistake, and the lock that hides the deck stays off.
        self.config.stay_awake_in_game = True
        self.daemon.set_mode("game")
        self.daemon.shutdown()
        self.assertEqual(self.idle_calls()[-1], "omarchy toggle idle allow-idle")

    def test_a_session_that_starts_in_game_mode_stays_awake_too(self):
        # No switch to hang it on, but the same rule must hold.
        self.config.stay_awake_in_game = True
        self.daemon.mode = "game"
        self.daemon.start()
        self.assertEqual(self.idle_calls()[-1], "omarchy toggle idle stay-awake")

    def test_a_machine_without_omarchy_is_not_a_daemon_that_stops(self):
        self.config.stay_awake_in_game = True

        def refuse(command):
            raise OSError("no such command")

        self.session.spawn = refuse
        self.daemon.set_mode("game")
        self.assertEqual(self.daemon.mode, "game")


class GameBarPressTests(DaemonTestCase):
    """The bar answers a thumb, and a pointer answers back."""

    def setUp(self):
        super().setUp()
        self.config.gamebar_enabled = True
        self.daemon.set_mode("game")

    def sent(self):
        return self.gamebar_client.sent[-1]

    def test_a_button_going_down_lights_the_badge_that_names_it(self):
        # The bar is the only thing on screen in game mode: a press it did not
        # answer reads as a pad that has stopped working.
        self.press("A")
        self.assertEqual(self.daemon.gamebar.pressed, ["A"])
        self.assertEqual(self.sent()["pressed"], ["A"])
        self.release("A")
        self.assertEqual(self.sent()["pressed"], [])

    def test_a_press_the_layer_trigger_takes_lights_it_too(self):
        # ZL opens the window layer and has no binding of its own, which is
        # exactly the press most worth answering: nothing else on screen says
        # the layer is open.
        self.press("ZL")
        self.assertEqual(self.sent()["pressed"], ["ZL"])

    def test_the_bar_opens_showing_the_hand_already_on_the_pad(self):
        # Not an empty bar it corrects at the next press.
        self.daemon.set_mode("desktop")
        self.press("Y")
        self.daemon.set_mode("game")
        self.assertEqual(self.daemon.gamebar.pressed, ["Y"])

    def test_a_pad_that_goes_away_leaves_no_badge_lit(self):
        self.press("A")
        self.daemon.reset_state()
        self.assertEqual(self.daemon.gamebar.pressed, [])

    def test_a_click_on_a_badge_fires_what_the_press_would(self):
        # Through the whole input path, so a click cannot mean something a
        # press does not: the daemon owns what a button is for.
        self.daemon.set_mode("desktop")
        self.daemon.handle_control("press ZR")
        self.assertEqual(self.mouse.buttons, [("left", True), ("left", False)])

    def test_a_click_names_the_button_in_omapads_own_names(self):
        # RB is what an Xbox pad prints on R; the printing is the guide's
        # question and cannot be what a click is sent as.
        self.assertEqual(self.daemon.handle_control("press RB"),
                         "unknown button: RB")

    def test_a_hint_with_only_a_hold_is_clicked_as_the_hold(self):
        # The badge reads "hold - ...", so a click that did nothing would be
        # the one thing on the bar promising less than it shows.
        self.daemon.set_mode("desktop")
        self.config.profiles.insert(0, {
            "name": "pretend", "match": ["pretendapp"],
            "bindings": {"Y": {"hold": "hypr:hl.dsp.window.close()"}},
        })
        self.daemon.set_active_profile("pretendapp")
        self.daemon.handle_control("press Y hold")
        self.assertEqual(self.hypr.calls, ["hl.dsp.window.close()"])

    def test_a_hold_nothing_is_bound_to_says_so(self):
        self.daemon.set_mode("desktop")
        self.assertEqual(self.daemon.handle_control("press A hold"),
                         "press A hold=nothing bound")

    def test_a_half_that_is_neither_is_refused(self):
        self.assertEqual(self.daemon.handle_control("press A sideways"),
                         "usage: press <BUTTON> [tap|hold]")


class MappingSurfaceTests(DaemonTestCase):
    """The screen reads the pad raw: the map it would use is the one in doubt."""

    def setUp(self):
        super().setUp()
        self.directory = tempfile.mkdtemp(prefix="omapad-mapping-")
        self.path = os.path.join(self.directory, "mapping.toml")
        patch = unittest.mock.patch.object(
            daemon_module, "mapping_path", lambda: self.path
        )
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(shutil.rmtree, self.directory, True)

    def raw(self, code, pressed=True):
        self.feed((li.EV_KEY, code, 1 if pressed else 0))

    def walk(self, first=0x130):
        """Answer every step with a code, starting from `first`."""
        for offset in range(len(self.daemon.mapper.steps)):
            self.raw(first + offset)
            self.raw(first + offset, False)

    def test_a_press_reaches_the_wizard_and_nothing_else(self):
        self.daemon.set_mapping(True)
        self.raw(0x130)          # the xbox profile calls this A: key:ENTER
        self.assertEqual(self.keyboard.chords, [])
        self.assertEqual(self.mouse.buttons, [])
        self.assertEqual(self.daemon.mapper.learned["A"], ("button", 0x130))

    def test_an_axis_that_is_pulled_is_learned_as_a_trigger(self):
        self.daemon.set_mapping(True)
        for _ in range(6):       # up to the step that asks for ZL
            self.daemon.mapper.skip()
        self.assertEqual(self.daemon.mapper.step, "ZL")
        self.feed((li.EV_ABS, 0x02, 255))
        self.assertEqual(self.daemon.mapper.triggers(), {0x02: "ZL"})

    def test_a_trigger_held_down_is_not_learned_twice(self):
        self.daemon.set_mapping(True)
        for _ in range(6):
            self.daemon.mapper.skip()
        self.feed((li.EV_ABS, 0x02, 255), (li.EV_ABS, 0x02, 250))
        self.assertEqual(self.daemon.mapper.step, "ZR")
        self.assertEqual(self.daemon.mapper.triggers(), {0x02: "ZL"})

    def test_the_sticks_and_the_dpad_are_not_offered_as_answers(self):
        self.daemon.set_mapping(True)
        self.feed((li.EV_ABS, li.ABS_X, 32767), (li.EV_ABS, li.ABS_HAT0X, 1))
        self.assertEqual(self.daemon.mapper.learned, {})
        self.assertEqual(self.daemon.mapper.step, "A")

    def test_holding_anything_long_enough_leaves_without_saving(self):
        # The only way out that assumes no working map, which is the whole
        # position the screen is opened from.
        self.daemon.set_mapping(True)
        self.raw(0x130)
        self.daemon.check_mapping_hold(
            self.daemon._mapping_down[1] + daemon_module.MAPPING_CANCEL_HOLD + 0.1
        )
        self.assertFalse(self.daemon.mapping_open)
        self.assertFalse(os.path.exists(self.path))

    def test_a_short_press_is_not_a_hold(self):
        self.daemon.set_mapping(True)
        self.raw(0x130)
        self.daemon.check_mapping_hold(self.daemon._mapping_down[1] + 0.2)
        self.assertTrue(self.daemon.mapping_open)

    def test_saving_writes_the_file_and_the_pad_answers_to_it_at_once(self):
        # No restart: the device is already open, so re-resolving the map is
        # all it takes for the next press to arrive under its new name.
        self.daemon.set_mapping(True)
        self.walk(0x131)         # every name one code along from the profile
        self.assertTrue(self.daemon.mapper.done)
        self.raw(0x131)          # the code just learned as A saves it
        self.assertFalse(self.daemon.mapping_open)
        self.assertTrue(os.path.exists(self.path))
        self.assertEqual(self.daemon.buttons[0x131], "A")
        self.assertEqual(self.daemon.buttons[0x132], "B")

    def test_and_then_the_new_names_are_the_ones_bindings_answer_to(self):
        self.daemon.set_mapping(True)
        self.walk(0x131)
        self.raw(0x131)
        self.raw(0x131, False)
        # 0x131 is A now, and A is key:ENTER on the base layer.
        self.raw(0x131)
        self.assertEqual(
            self.keyboard.chords[-1], ((), keymap.resolve("ENTER"), True)
        )

    def test_discarding_writes_nothing(self):
        self.daemon.set_mapping(True)
        self.walk(0x131)
        self.raw(0x132)          # learned as B
        self.assertFalse(self.daemon.mapping_open)
        self.assertFalse(os.path.exists(self.path))
        self.assertEqual(self.daemon.buttons[0x130], "A")  # profile, untouched

    def test_opening_it_puts_the_other_surfaces_away(self):
        self.daemon.set_osk(True)
        self.daemon.set_mapping(True)
        self.assertFalse(self.daemon.osk_open)
        self.assertFalse(self.daemon.menu_open)
        self.assertFalse(self.daemon.guide_open)

    def test_it_takes_the_pad_even_from_the_app_in_front(self):
        # Every press is an answer to what is on screen; the app underneath
        # must not also get it.
        self.daemon.handed_over = True
        self.daemon.apply_grab()
        self.assertFalse(self.device.grabbed)
        self.daemon.set_mapping(True)
        self.assertTrue(self.device.grabbed)
        self.daemon.set_mapping(False)
        self.assertFalse(self.device.grabbed)

    def test_a_pad_that_goes_away_takes_the_screen_with_it(self):
        self.daemon.set_mapping(True)
        self.daemon.disconnect()
        self.assertFalse(self.daemon.mapping_open)


class SpawnScopeTests(unittest.TestCase):
    """A command launched from the pad has to outlive the daemon."""

    def session_with(self, invocation_id):
        env = dict(os.environ)
        env.pop("INVOCATION_ID", None)
        if invocation_id:
            env["INVOCATION_ID"] = invocation_id
        with unittest.mock.patch.dict(os.environ, env, clear=True):
            return actions.Session()

    def test_a_systemd_started_daemon_spawns_into_a_scope_of_its_own(self):
        # Otherwise the unit's cgroup takes the browser down with the daemon on
        # the next `systemctl --user restart omapad`.
        if not shutil.which("systemd-run"):
            self.skipTest("systemd-run is not installed")
        session = self.session_with("0123456789abcdef0123456789abcdef")
        self.assertTrue(session.scope[0].endswith("systemd-run"))
        self.assertIn("--scope", session.scope)
        self.assertEqual(session.scope[-1], "--")

    def test_run_from_a_checkout_there_is_no_cgroup_to_escape(self):
        self.assertEqual(self.session_with(None).scope, [])


class VirtualKeyboardTests(unittest.TestCase):
    """What the uinput keyboard advertises decides what reads it."""

    def test_no_button_codes_are_declared(self):
        # A single BTN_* code is enough for joydev to attach a js node, and
        # then every controller scan on the machine - Steam runs one at
        # startup - finds a phantom pad made of this keyboard's keys.
        declared = set()
        for start, end in uinput.VirtualKeyboard.KEY_RANGES:
            declared |= set(range(start, end))
        buttons = (
            set(range(0x100, 0x160))     # BTN_MISC .. BTN_GEAR_UP
            | set(range(0x220, 0x224))   # BTN_DPAD_UP .. BTN_DPAD_RIGHT
            | set(range(0x2C0, 0x2E8))   # BTN_TRIGGER_HAPPY1 .. 40
        )
        self.assertEqual(declared & buttons, set())

    def test_every_key_omapad_can_type_is_declared(self):
        declared = set()
        for start, end in uinput.VirtualKeyboard.KEY_RANGES:
            declared |= set(range(start, end))
        self.assertTrue(set(keymap.KEYS.values()) <= declared)


class OskTests(DaemonTestCase):
    def open_osk(self):
        self.daemon.set_osk(True)
        self.osk_client.sent.clear()

    def test_keyboard_layer_takes_over_while_it_is_up(self):
        self.assertEqual(self.daemon.current_layer, "base")
        self.open_osk()
        self.assertEqual(self.daemon.current_layer, "osk")
        self.daemon.set_osk(False)
        self.assertEqual(self.daemon.current_layer, "base")

    def test_a_types_the_selected_key(self):
        self.open_osk()
        expected = self.daemon.osk.current_key["action"]
        from omapad import keymap
        code = keymap.resolve(expected)
        self.press("A")
        self.release("A")
        self.assertIn(((), code, True), self.keyboard.chords)
        self.assertIn(((), code, False), self.keyboard.chords)
        # The click binding from the base layer must not also fire.
        self.assertEqual(self.mouse.buttons, [])

    def test_left_trigger_is_shift_for_as_long_as_it_is_held(self):
        # A real Shift, not the one-shot latch: a whole capitalised word costs
        # one finger, and the window layer waits until the keyboard is down.
        self.open_osk()
        self.daemon.osk.row, self.daemon.osk.col = 1, 1     # 'q'
        self.press("ZL")
        self.assertTrue(self.daemon.osk.mods["shift"])
        self.assertEqual(self.daemon.current_layer, "osk",
                         "the window layer must not open over the keyboard")
        shift = keymap.resolve("LEFTSHIFT")
        for _ in range(2):
            self.press("A")
            self.release("A")
            self.assertTrue(self.daemon.osk.mods["shift"],
                            "a held Shift outlives the key it applies to")
        self.assertEqual(
            self.keyboard.chords[0], ((shift,), keymap.resolve("Q"), True))
        self.release("ZL")
        self.assertFalse(self.daemon.osk.mods["shift"])

    def test_the_window_layer_still_opens_once_the_keyboard_is_down(self):
        self.press("ZL")
        self.assertEqual(self.daemon.current_layer, "window")
        self.release("ZL")
        self.assertEqual(self.daemon.current_layer, "base")

    def test_a_held_shift_is_dropped_when_the_keyboard_closes(self):
        # The trigger's release is not routed to the keyboard once it is down,
        # so the hold has to go with it.
        self.open_osk()
        self.press("ZL")
        self.daemon.set_osk(False)
        self.assertFalse(self.daemon.osk.mods["shift"])
        self.assertFalse(self.daemon.osk.holds)

    def test_left_stick_click_toggles_caps_and_the_printed_letters(self):
        self.open_osk()
        self.press("LSTICK")
        self.release("LSTICK")
        self.assertTrue(self.daemon.osk.caps)
        # Omarchy remaps the Caps Lock key to Compose, so it goes out as both
        # shifts - whatever the Caps key itself is pointed at.
        self.assertEqual(
            self.keyboard.chords[0],
            ((keymap.resolve("LEFTSHIFT"),), keymap.resolve("RIGHTSHIFT"), True),
        )
        self.press("LSTICK")
        self.release("LSTICK")
        self.assertFalse(self.daemon.osk.caps)

    def test_right_trigger_submits_and_puts_the_keyboard_away(self):
        self.open_osk()
        self.press("ZR")
        code = keymap.resolve("ENTER")
        self.assertEqual(self.keyboard.chords, [((), code, True), ((), code, False)])
        self.assertFalse(self.daemon.osk_open)
        self.release("ZR")
        self.assertEqual(self.mouse.buttons, [], "the base click must not fire")

    def test_a_held_shift_rides_along_with_submit(self):
        self.open_osk()
        self.press("ZL")
        self.press("ZR")
        shift = keymap.resolve("LEFTSHIFT")
        self.assertEqual(self.keyboard.chords[0],
                         ((shift,), keymap.resolve("ENTER"), True))

    def test_right_stick_click_takes_over_the_left_click(self):
        # Displaced from ZR by Shift, and onto a button both profiles have -
        # CAPTURE exists only in NS mode.
        self.open_osk()
        self.press("RSTICK")
        self.assertEqual(self.mouse.buttons, [("left", True)])
        self.release("RSTICK")
        self.assertEqual(self.mouse.buttons[-1], ("left", False))
        self.assertTrue(self.daemon.osk_open, "clicking must not close it")

    def test_dpad_moves_the_selection_and_repaints(self):
        self.open_osk()
        before = (self.daemon.osk.row, self.daemon.osk.col)
        self.feed((li.EV_ABS, li.ABS_HAT0X, 1))
        after = (self.daemon.osk.row, self.daemon.osk.col)
        self.assertNotEqual(before, after)
        self.assertTrue(self.osk_client.sent, "the view should be pushed")
        self.assertEqual(self.osk_client.sent[-1]["sel"], list(after))

    def test_holding_a_direction_repeats(self):
        self.open_osk()
        self.feed((li.EV_ABS, li.ABS_HAT0X, 1))
        first = self.daemon.osk.col
        self.assertTrue(self.daemon.repeats, "a held direction should repeat")

        # Nothing happens before the delay, then one step per rate tick.
        entry = list(self.daemon.repeats.values())[0]
        due = entry[1]
        self.daemon.fire_repeats(due - 0.01)
        self.assertEqual(self.daemon.osk.col, first)
        self.daemon.fire_repeats(due)
        self.assertNotEqual(self.daemon.osk.col, first)

        self.feed((li.EV_ABS, li.ABS_HAT0X, 0))
        self.assertEqual(self.daemon.repeats, {})

    def test_the_keyboards_own_binding_outranks_the_layer_trigger(self):
        # ZL holds the window layer everywhere else, but the keyboard binds it
        # for Shift and typing is what the keyboard is for. A layer whose
        # trigger the surface has not claimed still opens.
        self.open_osk()
        self.press("ZL")
        self.assertEqual(self.daemon.current_layer, "osk")
        self.press("A")
        self.release("A")
        self.assertEqual(self.hypr.calls, [], "no window op while typing")

    def test_window_layer_toggles_the_keyboard(self):
        self.press("ZL")
        self.press("RSTICK")
        self.release("RSTICK")
        self.assertTrue(self.daemon.osk_open)
        self.press("RSTICK")
        self.release("RSTICK")
        self.assertFalse(self.daemon.osk_open)

    def test_game_mode_puts_the_keyboard_away(self):
        self.open_osk()
        self.daemon.set_mode("game")
        self.assertFalse(self.daemon.osk_open)
        self.assertFalse(self.osk_client.sent[-1]["open"])

    def test_closing_clears_a_pending_latch(self):
        self.open_osk()
        self.daemon.osk.latch("shift")
        self.daemon.set_osk(False)
        self.assertFalse(self.daemon.osk.mods["shift"])

    def test_navigation_does_nothing_while_the_keyboard_is_down(self):
        self.daemon.osk_command("right")
        self.assertEqual(self.osk_client.sent, [])

    def keys_on_screen(self):
        return dict(
            (key["l"], key)
            for row in self.osk_client.sent[-1]["rows"]
            for key in row
        )

    def test_a_key_prints_the_button_that_reaches_it(self):
        self.daemon.set_osk(True)
        keys = self.keys_on_screen()
        self.assertEqual(keys["Space"]["b"], "Y")
        self.assertEqual(keys["Space"]["k"], "face")
        # And in the printing of the pad that is plugged in: this one is an
        # Xbox, which calls ZL the left trigger.
        self.assertEqual(keys["Shift"]["b"], "LT")
        self.assertEqual(keys["Shift"]["k"], "trigger")
        # The trigger that finishes a line, not the quieter button that also
        # types Enter.
        self.assertEqual(keys["Enter"]["b"], "RT")
        # Nothing on the pad types a letter, so nothing is printed on one.
        self.assertNotIn("b", keys["q"])

    def test_the_badges_can_be_turned_off(self):
        self.config.osk_badges = False
        self.daemon.set_osk(True)
        self.assertFalse([
            key for key in self.keys_on_screen().values() if "b" in key
        ])


def walk_menu(daemon, labels, press):
    """Walk the shipped menu to a tile, pressing on the way in.

    The tree was one list and a test could name a row by its index. It is a
    bar of pages now: a name that is not on the page in front is a chip, and a
    chip is walked to rather than pressed.
    """
    for label in labels:
        for tile in daemon.menu.tiles:
            if tile["item"]["label"] == label:
                daemon.menu.select_id(tile["item"]["id"])
                break
        else:
            for number, group in enumerate(daemon.menu.groups):
                if group["label"] == label:
                    daemon.menu_select_group(number)
                    break
            else:
                raise AssertionError(
                    "no menu tile labelled %r on %r"
                    % (label, daemon.menu.title)
                )
            continue
        press()


class MenuTests(DaemonTestCase):
    def open_menu(self):
        self.daemon.set_menu(True)
        self.menu_client.sent.clear()

    def select(self, label):
        """Put the selection on a tile, walking the bar to find it."""
        walk_menu(self.daemon, [label], lambda: None)

    def drill(self, label):
        """Get to the page behind a name - a chip, or a tile that opens one."""
        walk_menu(self.daemon, [label],
                  lambda: self.daemon.menu_command("press"))

    def test_menu_layer_takes_over_while_it_is_up(self):
        self.assertEqual(self.daemon.current_layer, "base")
        self.open_menu()
        self.assertEqual(self.daemon.current_layer, "menu")
        self.daemon.set_menu(False)
        self.assertEqual(self.daemon.current_layer, "base")

    def test_plus_summons_it(self):
        self.press("PLUS")
        self.release("PLUS")
        self.assertTrue(self.daemon.menu_open)
        self.assertTrue(self.menu_client.sent[-1]["open"])

    def test_dpad_moves_the_selection_and_repaints(self):
        self.open_menu()
        before = self.daemon.menu.selected
        self.feed((li.EV_ABS, li.ABS_HAT0Y, 1))
        self.assertNotEqual(self.daemon.menu.selected, before)
        self.assertEqual(self.menu_client.sent[-1]["sel"],
                         self.daemon.menu.selected)

    def test_the_dpad_walks_the_grid_both_ways(self):
        # Left and right used to be a second way to say Back and Pick, which a
        # single column left them free to be. A grid spends both axes.
        self.open_menu()
        self.daemon.menu_command("down")
        first = self.daemon.menu.selected
        self.daemon.menu_command("right")
        self.assertNotEqual(self.daemon.menu.selected, first)
        self.daemon.menu_command("left")
        self.assertEqual(self.daemon.menu.selected, first)
        self.assertTrue(self.daemon.menu_open)

    def test_holding_a_direction_walks_the_grid(self):
        self.open_menu()
        self.feed((li.EV_ABS, li.ABS_HAT0Y, 1))
        self.assertTrue(self.daemon.repeats, "a held direction should repeat")
        first = self.daemon.menu.selected
        entry = list(self.daemon.repeats.values())[0]
        self.daemon.fire_repeats(entry[1])
        self.assertNotEqual(self.daemon.menu.selected, first)
        self.feed((li.EV_ABS, li.ABS_HAT0Y, 0))
        self.assertEqual(self.daemon.repeats, {})

    def test_the_shoulders_walk_the_bar(self):
        self.open_menu()
        self.assertEqual(self.daemon.menu.group, 0)
        self.daemon.menu_command("group_next")
        self.assertEqual(self.daemon.menu.group, 1)
        self.assertEqual(self.menu_client.sent[-1]["g"], 1)
        self.daemon.menu_command("group_prev")
        self.assertEqual(self.daemon.menu.group, 0)

    def test_the_bar_says_what_is_on_it(self):
        self.open_menu()
        self.daemon.push_menu_view()
        self.assertEqual(
            [group["l"] for group in self.menu_client.sent[-1]["groups"]],
            ["Now", "Apps", "Windows", "Audio", "Display", "Controller",
             "Readings", "System"],
        )

    def test_a_drills_into_a_submenu(self):
        self.open_menu()
        self.drill("Audio")
        self.select("Devices")
        self.press("A")
        self.release("A")
        self.assertTrue(self.daemon.menu_open)
        self.assertEqual(self.daemon.menu.title, "Devices")
        self.assertEqual(self.menu_client.sent[-1]["title"], "Devices")

    def test_b_climbs_back_out_and_then_closes(self):
        self.open_menu()
        self.drill("Audio")
        self.select("Devices")
        self.daemon.menu_command("press")
        self.daemon.menu_command("back")
        self.assertTrue(self.daemon.menu_open)
        self.assertEqual(self.daemon.menu.depth, 0)
        self.daemon.menu_command("back")
        self.assertFalse(self.daemon.menu_open)

    def test_picking_an_entry_runs_it_and_puts_the_menu_away(self):
        self.open_menu()
        self.drill("Apps")
        self.select("Terminal")
        self.press("A")
        self.release("A")
        self.assertEqual(self.session.spawned, ["omarchy-launch-terminal"])
        self.assertFalse(self.daemon.menu_open)
        # The base layer's own A binding must not also fire.
        self.assertEqual(self.keyboard.chords, [])

    def test_the_window_rows_reach_past_an_app_holding_the_pad(self):
        # Launching a game from Big Picture is exactly this shape: Steam holds
        # the pad, its floating window covers the tiled game, and the menu is
        # the only thing that still gets through. Fullscreen is the row that
        # clears it - a tiled window cannot be raised over a floating one.
        self.daemon.handed_over = True
        self.open_menu()
        self.drill("Windows")
        self.select("Fullscreen")
        self.press("A")
        self.release("A")
        self.assertEqual(
            self.hypr.calls,
            ["hl.dsp.window.fullscreen({ mode = 'fullscreen' })"],
        )

    def test_a_row_still_runs_once_the_menu_has_closed_over_a_game(self):
        # The menu is put away before the row fires, so by then the pad looks
        # handed over again - and every row that is not itself a summon used to
        # die there silently, in the one place the menu exists for.
        self.daemon.handed_over = True
        self.open_menu()
        self.drill("Apps")
        self.select("Terminal")
        self.press("A")
        self.release("A")
        self.assertEqual(self.session.spawned, ["omarchy-launch-terminal"])

    def test_a_repeat_row_leaves_the_menu_where_it_is(self):
        # A row you nudge rather than pick: reopening the menu per step is
        # absurd. Nothing shipped is marked any more - what used to be marked
        # was the volume and brightness stepping rows, and those are bars now
        # - so the flag needs its own tile to be tested at all.
        self.config.menu_items[0]["items"].append({
            "label": "Nudge", "action": "exec:nudge-it", "repeat": True,
        })
        self.daemon.menu = daemon_module.MenuModel(
            daemon_module.build_menu(
                self.config.menu_items, columns=self.config.menu_columns,
                settings=config_module.CHOSEN,
                readings=daemon_module.live_module.READINGS),
            self.config.menu_title, self.config.menu_clock,
            columns=self.config.menu_columns, bias=self.config.menu_bias)
        self.open_menu()
        self.select("Nudge")
        self.press("A")
        self.assertTrue(self.daemon.menu_open)
        self.assertEqual(len(self.session.spawned), 1)

        # ...and holding it keeps firing.
        self.assertTrue(self.daemon.repeats)
        entry = list(self.daemon.repeats.values())[0]
        self.daemon.fire_repeats(entry[1])
        self.assertEqual(len(self.session.spawned), 2)
        self.release("A")
        self.assertEqual(self.daemon.repeats, {})

    def test_an_ordinary_row_never_repeats_under_a_resting_thumb(self):
        self.open_menu()
        self.drill("Apps")
        self.select("Terminal")
        self.press("A")
        self.assertEqual(self.daemon.repeats, {})
        self.release("A")
        self.assertEqual(len(self.session.spawned), 1)

    def test_the_first_time_it_opens_on_the_first_tile(self):
        # Nowhere to come back to yet, so the first chip and the first thing
        # on it.
        self.daemon.set_menu(True)
        self.assertEqual(self.daemon.menu.depth, 0)
        self.assertEqual(self.daemon.menu.group, 0)
        self.assertEqual(self.daemon.menu.index, 0)

    def test_afterwards_it_opens_where_it_was_left(self):
        # Most of what a HUD is for is coming back: you turn the volume down,
        # you go back to the game, and you come back to turn it down again.
        self.open_menu()
        walk_menu(self.daemon, ["Audio"],
                  lambda: self.daemon.menu_select_group(0))
        here = self.daemon.menu.selected
        group = self.daemon.menu.group
        self.daemon.set_menu(False)
        self.daemon.set_menu(True)
        self.assertEqual(self.daemon.menu.group, group)
        self.assertEqual(self.daemon.menu.selected, here)

    def test_it_comes_back_to_the_chip_and_not_into_the_page(self):
        # The tile at the bottom of the stack, not the one in front: coming
        # back inside a submenu you had drilled into is coming back somewhere
        # you did not leave from.
        self.open_menu()
        self.drill("Audio")
        self.select("Devices")
        self.daemon.menu_command("press")
        self.assertGreater(self.daemon.menu.depth, 0)
        self.daemon.set_menu(False)
        self.daemon.set_menu(True)
        self.assertEqual(self.daemon.menu.depth, 0)
        self.assertEqual(self.daemon.menu.selected, "devices")

    def test_a_chip_that_has_gone_away_is_not_come_back_to(self):
        self.open_menu()
        self.daemon.set_menu(False)
        self.daemon._menu_where = ("no-such-chip", "no-such-tile")
        self.daemon.set_menu(True)
        self.assertEqual(self.daemon.menu.group, 0)
        self.assertEqual(self.daemon.menu.index, 0)

    def test_opening_it_puts_the_keyboard_away(self):
        self.daemon.set_osk(True)
        self.daemon.set_menu(True)
        self.assertFalse(self.daemon.osk_open)
        self.assertEqual(self.daemon.current_layer, "menu")

    def test_held_layer_still_wins_over_the_menu(self):
        self.open_menu()
        self.press("ZL")
        self.assertEqual(self.daemon.current_layer, "window")

    def test_game_mode_puts_the_menu_away(self):
        self.open_menu()
        self.daemon.set_mode("game")
        self.assertFalse(self.daemon.menu_open)
        self.assertFalse(self.menu_client.sent[-1]["open"])

    def test_navigation_does_nothing_while_the_menu_is_down(self):
        self.daemon.menu_command("down")
        self.assertEqual(self.menu_client.sent, [])

    def test_mouse_hover_names_a_row(self):
        # A cursor points at a row outright; the daemon turns that into the
        # selection, the same way every D-pad press lands in `menu.index`.
        self.open_menu()
        named = self.daemon.menu.tiles[3]["item"]["id"]
        reply = self.daemon.handle_control("menu select 3")
        self.assertIn("sel=%s" % named, reply)
        self.assertEqual(self.daemon.menu.index, 3)
        self.assertEqual(self.menu_client.sent[-1]["sel"], named)

    def test_mouse_hover_out_of_range_clamps(self):
        self.open_menu()
        self.daemon.handle_control("menu select 999")
        self.assertEqual(self.daemon.menu.index,
                         len(self.daemon.menu.tiles) - 1)

    def test_a_pointer_click_names_a_chip(self):
        self.open_menu()
        self.daemon.handle_control("menu group 2")
        self.assertEqual(self.daemon.menu.group, 2)
        self.assertEqual(self.daemon.menu.title, "Go")

    def test_a_chip_out_of_range_clamps(self):
        self.open_menu()
        self.daemon.handle_control("menu group 999")
        self.assertEqual(self.daemon.menu.group,
                         len(self.daemon.menu.groups) - 1)

    def test_a_chip_takes_a_bad_index_without_guessing(self):
        self.open_menu()
        self.assertIn("group nonsense",
                      self.daemon.handle_control("menu group nonsense"))
        self.assertEqual(self.daemon.menu.group, 0)

    def test_mouse_hover_does_nothing_while_the_menu_is_down(self):
        self.daemon.handle_control("menu select 2")
        self.assertEqual(self.menu_client.sent, [])

    def test_mouse_hover_takes_a_bad_index_without_guessing(self):
        self.open_menu()
        self.assertIn("select nonsense",
                      self.daemon.handle_control("menu select nonsense"))
        self.assertEqual(self.daemon.menu.index, 0)

    def test_a_pointer_click_picks_the_tile_it_lands_on(self):
        # The panel sends the tile and the press in one go, so a click cannot
        # land on one tile and pick another.
        self.open_menu()
        self.drill("System")
        self.daemon.handle_control("menu select %d"
                                   % (len(self.daemon.menu.tiles) - 1))
        self.daemon.handle_control("menu press")
        self.assertEqual(self.session.spawned, ["omarchy-menu toggle"])
        self.assertFalse(self.menu_client.sent[-1]["open"])


class ControlTileTests(DaemonTestCase):
    """A tile that reads a setting, and what A does to it."""

    def open_at(self, label):
        self.daemon.set_menu(True)
        walk_menu(self.daemon, ["Controller", label], lambda: None)
        self.menu_client.sent.clear()

    def drawn(self, label):
        for row in self.menu_client.sent[-1]["items"]:
            if row["l"] == label:
                return row
        raise AssertionError("no tile labelled %r" % label)

    def test_a_switch_says_what_it_is_on(self):
        self.open_at("Vibration")
        self.daemon.push_menu_view()
        row = self.drawn("Vibration")
        self.assertEqual(row["k"], "toggle")
        self.assertEqual(row["on"], self.config.rumble_enabled)

    def test_and_a_presses_flips_it(self):
        self.open_at("Vibration")
        before = self.config.rumble_enabled
        self.press("A")
        self.release("A")
        self.assertEqual(self.config.rumble_enabled, not before)
        # The menu stays: a control acts on what it reads, and being thrown
        # out to see what it did is how you open the menu twice.
        self.assertTrue(self.daemon.menu_open)
        self.assertEqual(self.drawn("Vibration")["on"], not before)

    def test_a_choice_prints_the_word_it_is_called(self):
        # Not the word it is stored as: `stencil` is a config value.
        self.open_at("Button style")
        self.daemon.push_menu_view()
        row = self.drawn("Button style")
        self.assertEqual(row["k"], "choice")
        self.assertIn(row["t"], ("Filled", "Stencil"))

    def test_and_a_walks_it_forward(self):
        self.open_at("Button style")
        first = self.config.ui_badge_style
        self.press("A")
        self.release("A")
        self.assertNotEqual(self.config.ui_badge_style, first)
        self.press("A")
        self.release("A")
        self.assertEqual(self.config.ui_badge_style, first)

    def test_a_control_tile_is_never_the_whole_story_of_a_tile(self):
        self.open_at("Vibration")
        self.daemon.push_menu_view()
        row = self.drawn("Vibration")
        for field in ("id", "l", "x", "y", "w", "h"):
            self.assertIn(field, row)

    def test_a_setting_that_has_gone_away_draws_bare_rather_than_raising(self):
        item = dict(self.daemon.menu.current or {})
        item["control"] = "toggle"
        item["reads"] = ("pad", "nonesuch")
        self.assertIsNone(self.daemon.menu_control(item))


class PageKeyTests(DaemonTestCase):
    """A page of the menu spending X and Y on a job of its own."""

    TREE = [
        {"label": "Apps", "items": [
            {"label": "Steam", "action": "exec:steam"},
        ], "keys": {
            # `desc` is the phrase the guide prints and `short` the one word
            # the legend does - the same binding read at two distances.
            "X": {"tap": "exec:page-x", "hold": "menu:close",
                  "desc": "My own verb", "short": "Mine"},
            "Y": {"tap": "exec:page-y", "desc": "The reach",
                  "short": "Also"},
        }},
        {"label": "Plain", "items": [
            {"label": "Thing", "action": "exec:thing"},
        ]},
    ]

    def setUp(self):
        super().setUp()
        self.daemon.menu = menu_module.MenuModel(
            menu_module.build(self.TREE, columns=self.config.menu_columns),
            columns=self.config.menu_columns,
        )
        self.daemon.set_menu(True)
        self.menu_client.sent.clear()
        self.session.spawned.clear()

    def test_the_page_s_own_key_is_what_the_button_does(self):
        self.press("Y")
        self.release("Y")
        self.assertEqual(self.session.spawned, ["page-y"])
        self.assertFalse(self.daemon.guide_open)

    def test_and_the_layer_s_own_comes_back_on_a_page_that_spends_none(self):
        self.daemon.menu_command("group_next")
        self.press("Y")
        self.release("Y")
        self.assertEqual(self.session.spawned, [])
        self.assertTrue(self.daemon.guide_open)

    def test_taking_x_keeps_the_way_out_on_the_hold(self):
        self.press("X")
        self.release("X")
        self.assertEqual(self.session.spawned, ["page-x"])
        self.assertTrue(self.daemon.menu_open)

    def test_a_page_key_means_nothing_once_the_menu_is_down(self):
        self.daemon.set_menu(False)
        self.press("Y")
        self.release("Y")
        self.assertEqual(self.session.spawned, [])

    def test_the_legend_says_what_this_page_spent_them_on(self):
        self.daemon.push_menu_view()
        keys = self.menu_client.sent[-1]["keys"]
        said = dict((row["b"], row["n"]) for row in keys)
        self.assertEqual(said.get("X"), "Mine")
        self.assertEqual(said.get("Y"), "Also")

    def test_and_the_layer_s_words_where_it_spent_nothing(self):
        self.daemon.menu_command("group_next")
        keys = self.menu_client.sent[-1]["keys"]
        said = dict((row["b"], row["n"]) for row in keys)
        self.assertEqual(said.get("X"), "Close")
        self.assertEqual(said.get("Y"), "Guide")

    def test_the_legend_prints_the_contract_in_its_own_order(self):
        self.daemon.push_menu_view()
        keys = self.menu_client.sent[-1]["keys"]
        self.assertEqual([row["b"] for row in keys], ["A", "B", "X", "Y"])

    def test_the_legend_can_be_turned_off_for_anyone_running_the_bar(self):
        self.config.menu_keys = False
        self.daemon.push_menu_view()
        self.assertEqual(self.menu_client.sent[-1]["keys"], [])

    def test_the_guide_answers_about_the_page_it_was_opened_from(self):
        # Y is the guide because you had forgotten what a button does, so a
        # guide that printed the layer's X rather than this page's would be
        # wrong about exactly what was asked.
        self.daemon.set_guide(True)
        # The phrase, not the word: the guide is read from a page with the pad
        # in your lap, and the legend is glanced at over a game.
        self.assertIn(("X", "My own verb"), self.guide_words())

    def test_and_about_the_menu_at_large_when_it_was_not(self):
        self.daemon.set_menu(False)
        self.daemon.set_guide(True)
        self.assertNotIn(("X", "My own verb"), self.guide_words())

    def guide_words(self):
        words = []
        for page in self.daemon.guide.pages:
            for column in page["cols"]:
                for group in column:
                    for row in group["rows"]:
                        words.append((row["b"], row["d"]))
        return words


class ListedMenuTests(DaemonTestCase):
    """A row whose submenu is a command's output - the audio devices."""

    def setUp(self):
        super().setUp()
        # The head runs a command of its own when the menu opens, and this
        # suite counts commands. It has a test of its own.
        self.daemon.menu.head = []
        self.daemon.set_menu(True)
        self.session.lines = [
            "* Speakers\t1\tanalog-out",
            "Television\t7\thdmi-out",
        ]

    def enter(self, *labels):
        walk_menu(self.daemon, labels,
                  lambda: self.daemon.menu_command("press"))

    def test_the_devices_are_read_when_the_row_is_entered(self):
        # Not at load: which outputs exist changes while the daemon runs, and
        # the answer a television adds is the whole reason for the row.
        self.enter("Audio", "Devices")
        self.assertEqual(self.session.captured, [])
        self.enter("Output")
        self.assertEqual(len(self.session.captured), 1)
        self.assertIn("pactl", self.session.captured[0])
        self.assertEqual([row["l"] for row in self.menu_client.sent[-1]["items"]],
                         ["Speakers", "Television"])
        self.assertEqual([row["on"] for row in self.menu_client.sent[-1]["items"]],
                         [True, False])

    def test_it_is_asked_again_every_time_the_row_is_entered(self):
        self.enter("Audio", "Devices", "Output")
        self.daemon.menu_command("back")
        self.session.lines.append("Headphones\t9\tusb-out")
        self.enter("Output")
        self.assertEqual(len(self.session.captured), 2)
        self.assertEqual(len(self.menu_client.sent[-1]["items"]), 3)

    def test_picking_a_device_runs_the_row_and_keeps_the_menu_up(self):
        self.enter("Audio", "Devices", "Output")
        self.daemon.menu_command("right")
        self.daemon.menu_command("press")
        self.assertEqual(self.session.spawned,
                         ["omarchy-audio-output-set-default 7 hdmi-out"])
        self.assertTrue(self.daemon.menu_open)
        # The tick follows the press: the command that moves the sound was let
        # go of, so asking again here would race it.
        self.assertEqual([row["on"] for row in self.menu_client.sent[-1]["items"]],
                         [False, True])

    def test_a_listing_that_finds_nothing_says_so_and_runs_nothing(self):
        self.session.lines = []
        self.enter("Audio", "Devices", "Output")
        rows = self.menu_client.sent[-1]["items"]
        self.assertEqual([row["l"] for row in rows], ["No outputs found"])
        self.daemon.menu_command("press")
        self.assertEqual(self.session.spawned, [])
        self.assertTrue(self.daemon.menu_open)

    def test_the_microphones_are_a_listing_of_their_own(self):
        self.enter("Audio", "Devices", "Microphone")
        self.daemon.menu_command("press")
        self.assertEqual(self.session.spawned,
                         ["omarchy-audio-input-set-default 1 analog-out"])


class FakeCommands:
    """The worker as a queue the test empties by hand.

    The command is run at the submit, so `session.captured` says what was
    asked for; the answer waits in `drain` until the test calls
    `drain_commands`, which is the beat between the press and the fill that
    the real worker puts there.
    """

    def __init__(self, session):
        self.session = session
        self.submitted = []
        self.answers = []
        self.closed = False

    def submit(self, key, command, timeout=2.0):
        self.submitted.append((command, timeout))
        self.answers.append((key, self.session.capture(command, timeout)))

    def drain(self):
        found, self.answers = self.answers, []
        return found

    def close(self):
        self.closed = True


class CommandWorkerTests(unittest.TestCase):
    """The thread the shell commands a surface asks for are run on."""

    def worker(self):
        read_fd, write_fd = os.pipe()
        os.set_blocking(read_fd, False)
        self.addCleanup(os.close, read_fd)
        worker = actions.Commands(actions.Session(), wake=write_fd)
        self.addCleanup(worker.close)
        return worker, read_fd

    def answer(self, worker, read_fd):
        """Wait for the byte, then take what it announced."""
        ready = select.select([read_fd], [], [], 5.0)[0]
        self.assertTrue(ready, "the worker never woke the loop")
        os.read(read_fd, 4096)
        return worker.drain()

    def test_the_answer_comes_back_under_the_key_it_was_asked_with(self):
        worker, read_fd = self.worker()
        worker.submit(7, "printf 'one\\ntwo\\n'")
        self.assertEqual(self.answer(worker, read_fd), [(7, ["one", "two"])])

    def test_a_command_that_hangs_is_given_up_on_rather_than_waited_out(self):
        # The whole point of the thread: the loop is not what is waiting.
        worker, read_fd = self.worker()
        worker.submit(1, "sleep 30", timeout=0.2)
        self.assertEqual(self.answer(worker, read_fd), [(1, [])])

    def test_a_command_that_fails_answers_empty_rather_than_dying(self):
        worker, read_fd = self.worker()
        worker.submit(1, "exit 3")
        self.assertEqual(self.answer(worker, read_fd), [(1, [])])
        worker.submit(2, "printf 'still here\\n'")
        self.assertEqual(self.answer(worker, read_fd), [(2, ["still here"])])


class LiveTests(DaemonTestCase):
    """The tiles that read the machine rather than the config."""

    VOLUME = ["Volume: front-left: 39321 /  60% / -13.31 dB"]
    MEDIA = ['{"hasPlayer":true,"hasMedia":true,"playing":true,'
             '"title":"Sunset Roller","artist":"My Jinji",'
             '"canGoNext":true,"canGoPrevious":false}']

    def setUp(self):
        super().setUp()
        self.commands = self.daemon.commands = FakeCommands(self.session)
        self.daemon.menu.head = []
        # A settings file of its own, so "nothing was written" is a claim this
        # test can make about the machine it runs on.
        directory = tempfile.mkdtemp(prefix="omapad-live-")
        self.addCleanup(shutil.rmtree, directory, True)
        self.settings = os.path.join(directory, "settings.toml")
        patch = unittest.mock.patch.object(
            daemon_module, "settings_path", lambda: self.settings
        )
        patch.start()
        self.addCleanup(patch.stop)

    def answer(self, *lines):
        """Ask for whatever is due, with this as what comes back.

        The canned lines answer every question at once, which is safe because
        the four parsers are mutually exclusive: a `pactl` line is not JSON
        and a JSON line has no percentage in it, so three of the four return
        None and leave their readings alone.
        """
        self.session.lines = list(lines)
        self.daemon.live_refresh(time.monotonic())
        self.daemon.drain_commands()

    def asked(self):
        return [command for command, _ in self.commands.submitted]

    def open_on(self, label):
        self.daemon.set_menu(True)
        walk_menu(self.daemon, [label], lambda: None)

    def tile(self, label):
        rows = self.menu_client.sent[-1]["items"]
        return [row for row in rows if row["l"] == label][0]

    def test_nothing_is_asked_while_the_menu_is_shut(self):
        self.daemon.live_refresh(time.monotonic())
        self.assertEqual(self.asked(), [])

    def test_every_reading_on_the_page_is_asked_once_when_it_appears(self):
        self.daemon.set_menu(True)
        self.daemon.live_refresh(time.monotonic())
        asked = self.asked()
        self.assertEqual(len(asked), 4)
        self.assertTrue(any("get-sink-volume" in one for one in asked))
        self.assertTrue(any("get-sink-mute" in one for one in asked))
        self.assertTrue(any("brightness" in one for one in asked))
        self.assertTrue(any("media status" in one for one in asked))

    def test_a_volume_answer_reaches_its_tile(self):
        self.open_on("Volume")
        self.answer(*self.VOLUME)
        volume = self.tile("Volume")
        self.assertEqual(volume["k"], "slider")
        self.assertAlmostEqual(volume["v"], 0.6, places=2)
        self.assertEqual(volume["t"], "60%")

    def test_only_the_selected_tile_keeps_being_asked(self):
        # A couch does not need the volume to track a keyboard nobody is at.
        self.open_on("Volume")
        now = time.monotonic()
        self.daemon.live_refresh(now)
        self.answer(*self.VOLUME)
        self.commands.submitted = []
        later = now + self.daemon.config.live_poll + 0.1
        self.daemon.live_refresh(later)
        self.assertEqual([one for one in self.asked()
                          if "get-sink-volume" in one], self.asked())

    def test_a_question_in_flight_is_not_asked_again(self):
        # A helper that has wedged must not collect a queue of identical
        # questions behind it: the answer to the first is the answer to all.
        self.open_on("Volume")
        now = time.monotonic()
        self.daemon.live_refresh(now)
        self.commands.submitted = []
        self.daemon.live_refresh(now + self.daemon.config.live_poll + 0.1)
        self.assertEqual(self.asked(), [])

    def test_a_press_writes_and_then_asks_what_it_actually_did(self):
        self.open_on("Volume")
        self.answer(*self.VOLUME)
        self.commands.submitted = []
        self.daemon.menu_command("press")            # A takes it
        self.daemon.menu_command("right")
        written = self.asked()
        self.assertEqual(len(written), 1)
        self.assertIn("set-sink-volume", written[0])
        self.assertIn(" 65%", written[0])
        # The tile moves at the press rather than a round trip later.
        self.assertAlmostEqual(self.tile("Volume")["v"], 0.65, places=2)
        # ...and the machine is asked what it did, once the helper has landed.
        self.commands.submitted = []
        self.daemon.live_refresh(
            time.monotonic() + self.daemon.config.live_settle + 0.1)
        self.assertEqual([one for one in self.asked()
                          if "get-sink-volume" in one], self.asked())
        self.assertEqual(len(self.asked()), 1)

    def test_a_live_push_writes_no_settings_file(self):
        # The value is the machine's, not ours: there is nothing to keep.
        self.open_on("Volume")
        self.answer(*self.VOLUME)
        self.daemon.menu_command("press")
        self.daemon.menu_command("right")
        self.assertFalse(os.path.exists(self.settings))

    def test_a_switch_flips_what_the_machine_holds(self):
        self.open_on("Mute")
        self.answer("Mute: no")
        self.assertFalse(self.tile("Mute")["on"])
        self.commands.submitted = []
        self.daemon.menu_command("press")
        self.assertIn("set-sink-mute", self.asked()[0])
        self.assertTrue(self.tile("Mute")["on"])

    def test_the_media_tile_says_what_is_playing(self):
        self.open_on("Music")
        self.answer(*self.MEDIA)
        music = self.tile("Sunset Roller")
        self.assertEqual(music["k"], "media")
        self.assertEqual(music["d"], "My Jinji")
        self.assertTrue(music["on"])
        # What the player can and cannot do is read and is not drawn.
        self.assertNotIn("n", music)
        self.assertNotIn("p", music)

    def test_nothing_playing_falls_back_to_the_tiles_own_words(self):
        self.open_on("Music")
        self.answer('{"hasPlayer":false,"hasMedia":false,"playing":false}')
        music = self.tile("Music")
        self.assertEqual(music["d"], "Nothing playing")
        self.assertFalse(music["on"])

    def test_a_on_the_media_tile_plays_or_pauses_it(self):
        # Two states, so A does to it what A does to a switch. The transport's
        # two other marks are two more tiles, and a tile costs nobody a reflex.
        self.open_on("Music")
        self.answer(*self.MEDIA)
        self.commands.submitted = []
        self.daemon.menu_command("press")
        self.assertEqual(self.asked(), ["omarchy-shell media playPause"])

    def test_a_direction_the_player_closed_ticks_instead_of_going_quiet(self):
        self.open_on("Music")
        self.answer(*self.MEDIA)          # canGoPrevious is false
        self.commands.submitted = []
        self.device.played = []
        walk_menu(self.daemon, ["Previous"], lambda: None)
        self.daemon.menu_command("press")
        self.assertEqual(self.asked(), [])
        self.assertIn(self.daemon.rumble.effects["edge"], self.device.played)

    def test_a_direction_the_player_allows_is_sent(self):
        self.open_on("Music")
        self.answer(*self.MEDIA)
        self.commands.submitted = []
        walk_menu(self.daemon, ["Next"], lambda: None)
        self.daemon.menu_command("press")
        self.assertEqual(self.asked(), ["omarchy-shell media next"])

    def test_closing_the_menu_forgets_when_anything_was_read(self):
        # What the machine was doing a minute ago is not what it is doing now.
        self.daemon.set_menu(True)
        self.answer(*self.VOLUME)
        self.daemon.set_menu(False)
        self.commands.submitted = []
        self.daemon.set_menu(True)
        self.daemon.live_refresh(time.monotonic())
        self.assertEqual(len(self.asked()), 4)


class GaugeTests(DaemonTestCase):
    """The one tile that draws something no config file holds."""

    def land(self, *labels):
        self.daemon.set_menu(True)
        walk_menu(self.daemon, labels[:-1],
                  lambda: self.daemon.menu_command("press"))
        for tile in self.daemon.menu.tiles:
            if tile["item"]["label"] == labels[-1]:
                self.daemon.menu.select_id(tile["item"]["id"])
                return tile["item"]
        raise AssertionError("no tile labelled %r" % labels[-1])

    def lines(self):
        return [line for line in self.menu_client.sent]

    def push(self, now=None):
        self.daemon.push_menu_live(
            time.monotonic() if now is None else now)

    def test_the_menu_streams_only_while_a_gauge_is_the_tile_in_front(self):
        # The *tile's* kind decides, not the surface's: a menu open on a page
        # of buttons costs the loop nothing at all.
        self.daemon.set_menu(True)
        self.assertFalse(self.daemon.menu.watching())
        self.assertFalse(self.daemon.needs_tick())
        self.land("Controller", "Sticks", "Left stick")
        self.assertEqual(self.daemon.menu.watching(), "left")
        self.assertTrue(self.daemon.needs_tick())

    def test_nothing_streams_while_the_menu_is_shut(self):
        # A daemon nobody is looking at must not be pushing sixty lines a
        # second at a socket with no panel on the other end.
        self.land("Controller", "Sticks", "Left stick")
        self.daemon.set_menu(False)
        self.assertIsNone(self.daemon.menu_live())

    def test_a_live_line_carries_no_items_at_all(self):
        # The whole claim of this phase: `applyState` gets past its own guard,
        # finds no items, and never reaches `fresh()` - so no delegate is
        # rebuilt to move one dot.
        self.land("Controller", "Sticks", "Left stick")
        self.menu_client.sent.clear()
        self.feed((li.EV_ABS, li.ABS_X, 20000))
        self.push()
        self.assertEqual(len(self.lines()), 1)
        line = self.lines()[0]
        self.assertNotIn("items", line)
        self.assertIn("live", line)
        # ...and it says which gauge the floats belong to, so the stream is
        # meaningful without correlating it against the other one.
        self.assertEqual(line["sel"], "left-stick")
        self.assertEqual(line["g"], self.daemon.menu.group)

    def test_the_thumb_is_read_raw_rather_than_through_the_curve(self):
        # The curve exists to make small deflections aim finely; this asks
        # where the thumb is, not how fast to move a pointer. Half over is
        # half over, and a curved reading would draw the stick somewhere it
        # is not.
        self.land("Controller", "Sticks", "Left stick")
        self.feed((li.EV_ABS, li.ABS_X, 0))
        self.feed((li.EV_ABS, li.ABS_X, 16384))
        live = self.daemon.menu_live()
        self.assertAlmostEqual(live["x"], 0.5, places=1)
        self.assertAlmostEqual(live["y"], 0.0, places=2)

    def test_a_resting_stick_stops_the_stream_entirely(self):
        # Quantised not as a noise filter but so the panel's own "same line as
        # last time" guard works: a hand off the pad must cost nothing.
        self.land("Controller", "Sticks", "Left stick")
        self.push()
        self.menu_client.sent.clear()
        for _ in range(5):
            self.push(time.monotonic() + 10)
        self.assertEqual(self.lines(), [])

    def test_the_stream_is_rate_limited_to_live_hz(self):
        self.land("Controller", "Sticks", "Left stick")
        now = time.monotonic()
        self.feed((li.EV_ABS, li.ABS_X, 20000))
        self.push(now)
        self.menu_client.sent.clear()
        self.feed((li.EV_ABS, li.ABS_X, 30000))
        self.push(now)                       # too soon
        self.assertEqual(self.lines(), [])
        self.push(now + 1.0 / self.daemon.config.menu_live_hz + 0.001)
        self.assertEqual(len(self.lines()), 1)

    def test_the_zone_rides_on_the_full_push_rather_than_the_stream(self):
        # It is a setting: it changes only when something presses, and putting
        # it in the stream would send it sixty times a second to say the same
        # thing.
        self.land("Controller", "Sticks", "Left stick")
        self.daemon.push_menu_view()
        rows = self.menu_client.sent[-1]["items"]
        dial = [row for row in rows if row["l"] == "Left stick"][0]
        self.assertEqual(dial["k"], "gauge")
        self.assertEqual(dial["s"], "left")
        self.assertAlmostEqual(dial["z"], self.config.left_deadzone)
        self.assertNotIn("z", self.daemon.menu_live())

    def test_the_left_stick_walks_the_tiles_and_the_right_one_aims(self):
        self.daemon.set_menu(True)
        self.assertEqual(self.daemon.stick_roles(), ("menu", "cursor"))

    def test_a_held_stick_walks_the_grid_the_way_a_held_key_does(self):
        # A direction held, not a shove: walking a grid is a thing you do
        # several of in a row.
        self.land("Controller", "Sticks", "Pointer")
        self.feed((li.EV_ABS, li.ABS_Y, 32767))
        self.daemon.tick(0.05)
        self.assertEqual(self.daemon.menu.selected, "left-dead-zone")
        # ...and it waits out the delay before the next one, rather than
        # running the length of the page in one push.
        self.daemon.tick(0.05)
        self.assertEqual(self.daemon.menu.selected, "left-dead-zone")
        self.daemon.tick(self.config.traverse_repeat_delay)
        self.assertEqual(self.daemon.menu.selected, "left-stick")

    def test_a_stick_let_go_of_walks_again_at_once(self):
        # A new direction steps immediately and then waits, the way a key
        # pressed again does - so two deliberate pushes are two tiles.
        self.land("Controller", "Sticks", "Pointer")
        self.feed((li.EV_ABS, li.ABS_Y, 32767))
        self.daemon.tick(0.05)
        self.feed((li.EV_ABS, li.ABS_Y, 0))
        self.daemon.tick(0.05)
        self.feed((li.EV_ABS, li.ABS_Y, 32767))
        self.daemon.tick(0.05)
        self.assertEqual(self.daemon.menu.selected, "left-stick")

    def test_a_stick_on_a_taken_control_moves_it_rather_than_the_selection(
            self):
        # Phase 0's table, and the one place the stick and the D-pad have to
        # agree exactly.
        self.land("Controller", "Sticks", "Pointer")
        self.daemon.menu_command("press")
        before = self.config.pointer_speed
        self.feed((li.EV_ABS, li.ABS_X, 32767))
        self.daemon.tick(0.05)
        self.assertEqual(self.daemon.menu.selected, "pointer")
        self.assertGreater(self.config.pointer_speed, before)


class FullscreenTests(DaemonTestCase):
    """Whether the card is a card or the screen, which the panel cannot ask."""

    def test_the_payload_says_which_shape_the_card_takes(self):
        self.daemon.set_menu(True)
        self.assertTrue(self.menu_client.sent[-1]["full"])
        self.config.menu_fullscreen = False
        self.daemon.push_menu_view()
        self.assertFalse(self.menu_client.sent[-1]["full"])

    def test_it_is_stamped_on_the_menu_rather_than_on_every_surface(self):
        # `scaled()` is for what is true of every surface; this is true of
        # one, so it goes on the menu's own payload and nowhere else.
        self.daemon.set_menu(True)
        self.daemon.set_guide(True)
        self.assertNotIn("full", self.guide_client.sent[-1])

    def test_the_model_knows_nothing_about_it(self):
        # `menu.py` holds state and geometry and reads no config.
        state = self.daemon.menu.view_state(True)
        self.assertNotIn("full", state)
        self.assertNotIn("dim", state)

    def test_how_dark_it_goes_travels_with_it(self):
        # The shell cannot read the config, so a number it draws with has to
        # arrive in the payload like the scale does.
        self.daemon.set_menu(True)
        self.assertEqual(self.menu_client.sent[-1]["dim"],
                         self.config.menu_dim)

    def test_how_tall_a_cell_is_travels_with_it(self):
        # `cols` says how wide a cell is and this says the rest of its shape.
        # Both have to arrive: the panel has no config to look either up in.
        self.daemon.set_menu(True)
        self.assertEqual(self.menu_client.sent[-1]["cell"],
                         self.config.menu_cell_height)

    def test_the_blur_is_asked_for_once_at_start(self):
        # A layer rule on our own namespace and nothing else: asking for a
        # blur behind your own panel is not reaching into somebody's setup.
        self.hypr.evaluated = []
        self.daemon.apply_blur()
        self.assertEqual(len(self.hypr.evaluated), 1)
        self.assertIn("omapad-", self.hypr.evaluated[0])
        self.assertIn("blur = true", self.hypr.evaluated[0])
        self.assertNotIn("decoration", self.hypr.evaluated[0])

    def test_a_desktop_that_wants_no_blur_is_asked_nothing(self):
        self.config.ui_blur = False
        self.hypr.evaluated = []
        self.daemon.apply_blur()
        self.assertEqual(self.hypr.evaluated, [])


class ThemeChangeTests(DaemonTestCase):
    """What a `hyprctl reload` takes away, and asking for it again."""

    def setUp(self):
        super().setUp()
        directory = tempfile.mkdtemp(prefix="omapad-theme-")
        self.addCleanup(shutil.rmtree, directory, True)
        self.colors = os.path.join(directory, "colors.toml")
        self.write('foreground = "#112233"')
        patch = unittest.mock.patch.object(
            daemon_module.cursor_theme, "theme_path", lambda: self.colors)
        patch.start()
        self.addCleanup(patch.stop)
        self.daemon._theme_seen = self.daemon.theme_stamp()

    def write(self, text):
        with open(self.colors, "w") as handle:
            handle.write(text + "\n")

    def later(self, seconds=daemon_module.THEME_POLL + 1.0):
        return time.monotonic() + seconds

    def test_nothing_happens_while_the_theme_stands_still(self):
        self.hypr.evaluated = []
        self.daemon.check_theme(self.later())
        self.assertEqual(self.hypr.evaluated, [])

    def test_a_changed_theme_asks_for_the_blur_again(self):
        # `omarchy-theme-set` ends in `hyprctl reload`, and a reload throws
        # away every rule asked for at runtime - ours included.
        self.write('foreground = "#445566"')
        self.hypr.evaluated = []
        self.daemon.check_theme(self.later())
        self.assertEqual(len(self.hypr.evaluated), 1)
        self.assertIn("blur = true", self.hypr.evaluated[0])

    def test_it_is_not_asked_more_often_than_the_poll(self):
        # One `stat` on the beat the surfaces heartbeat at, not one per turn
        # of a loop running at frame rate.
        now = self.later()
        self.daemon.check_theme(now)
        self.write('foreground = "#445566"')
        self.hypr.evaluated = []
        self.daemon.check_theme(now + daemon_module.THEME_POLL / 2)
        self.assertEqual(self.hypr.evaluated, [])
        self.daemon.check_theme(now + daemon_module.THEME_POLL + 0.1)
        self.assertEqual(len(self.hypr.evaluated), 1)

    def test_the_first_look_is_not_a_change(self):
        # Where we came in, not something that moved under us.
        self.daemon._theme_seen = None
        self.hypr.evaluated = []
        self.daemon.check_theme(self.later())
        self.assertEqual(self.hypr.evaluated, [])

    def test_a_theme_that_is_not_there_is_not_a_change_either(self):
        os.unlink(self.colors)
        self.hypr.evaluated = []
        self.daemon.check_theme(self.later())
        self.assertEqual(self.hypr.evaluated, [])

    def test_the_pointer_is_redrawn_without_a_mode_switch(self):
        # The case that matters: the theme most often changes while somebody
        # is already sitting in game mode looking at the pointer.
        self.write('foreground = "#445566"')
        with unittest.mock.patch.object(
                self.daemon, "apply_cursor") as redraw:
            self.daemon.check_theme(self.later())
        self.assertEqual(redraw.call_count, 1)


class EditModeTests(DaemonTestCase):
    """Rearranging a page from the pad, and what it writes down."""

    def setUp(self):
        super().setUp()
        directory = tempfile.mkdtemp(prefix="omapad-layout-")
        self.addCleanup(shutil.rmtree, directory, True)
        self.layout = os.path.join(directory, "layout.toml")
        patch = unittest.mock.patch.object(
            daemon_module, "layout_path", lambda: self.layout
        )
        patch.start()
        self.addCleanup(patch.stop)
        self.daemon.menu.head = []
        self.daemon.set_menu(True)
        walk_menu(self.daemon, ["Controller"], lambda: None)

    def order(self):
        return [tile["item"]["id"] for tile in self.daemon.menu.tiles]

    def cells(self):
        return dict((tile["item"]["id"], tile["at"])
                    for tile in self.daemon.menu.tiles)

    def written(self):
        if not os.path.exists(self.layout):
            return ""
        with open(self.layout) as handle:
            return handle.read()

    def test_holding_y_is_what_turns_it_on(self):
        # The reach, one press longer: holding the button that shows you what
        # the buttons do is where you find out the tiles are yours.
        self.assertFalse(self.daemon.menu.edit)
        self.press("Y")
        self.daemon.check_hold_timers(time.monotonic() + 1.0)
        self.assertTrue(self.daemon.menu.edit)

    def test_the_legend_says_what_every_button_means_now(self):
        # It is the discoverability surface: six rows, because the two
        # borrowed shoulders must not be a secret.
        self.daemon.menu_command("edit")
        rows = self.menu_client.sent[-1]["keys"]
        self.assertEqual([row["n"] for row in rows],
                         ["Move", "Done", "Hide", "Reset",
                          "Narrower", "Wider"])

    def test_what_the_legend_prints_is_what_a_press_does(self):
        # One table, read by both, so they cannot drift apart.
        self.daemon.menu_command("edit")
        for button, command in (("A", "menu:pick"), ("B", "menu:edit_off"),
                                ("X", "menu:hide"), ("Y", "menu:restore"),
                                ("L", "menu:narrower"), ("R", "menu:wider")):
            self.assertEqual(
                self.daemon.menu_key_spec(button)["tap"], command, button)
            binding = self.daemon.binding_for("menu", button)
            self.assertIsNotNone(binding, button)

    def test_a_tile_is_picked_up_carried_and_put_down(self):
        before = self.order()
        self.daemon.menu_command("edit")
        self.daemon.menu_command("pick")
        self.assertEqual(self.daemon.menu.picked, before[0])
        where = self.cells()[before[0]]
        self.daemon.menu_command("right")
        # A cell, not a place in the order: the tile is where it was put and
        # the one it stepped over has flowed into the space behind it.
        self.assertEqual(self.cells()[before[0]],
                         (where[0] + 1, where[1]))
        self.assertEqual(self.cells()[before[1]], where)
        self.daemon.menu_command("pick")
        self.assertIsNone(self.daemon.menu.picked)

    def open_readings(self):
        """The HUD's page, with its readings answering.

        Seeded rather than read: `sysinfo` is pointed at this machine's own
        /proc, and a tile whose reading has never answered is deliberately not
        drawn at all - so without this the assertions below would be about an
        empty payload, on one machine and not another.
        """
        page = self.daemon.config.hud_page
        for name in ("cpu", "memory", "disk"):
            self.daemon.sysinfo.took(name, 0.5)
        for number, group in enumerate(self.daemon.menu.groups):
            if group["id"] == page:
                self.daemon.menu_select_group(number)
                return
        raise AssertionError("the shipped tree has no %s page" % page)

    def drawn(self):
        return dict((row["id"], (row["x"], row["y"]))
                    for row in self.hud_client.sent[-1]["items"])

    def test_the_two_surfaces_hold_one_arrangement(self):
        # The same dict, not a copy of the same file. The menu takes its own
        # copy of what came off layout.toml so rearranging never writes back
        # into the config - so `config.layout` is the file as it was read and
        # stops being true the moment anybody carries a tile. A HUD reading
        # that instead drew the arrangement somebody had before they started.
        self.assertIs(self.daemon.hud.layout, self.daemon.menu.layout)
        self.assertIsNot(self.daemon.menu.layout, self.daemon.config.layout)

    def test_the_readings_are_packed_again_when_the_page_is_rearranged(self):
        """The same arrangement is not the same packing.

        `MenuModel` and `HudModel` share one layout dict, one page and one
        packer - and each holds the cells it last worked out. Nothing told the
        HUD to work them out again, so an arrangement made while the readings
        were on screen reached the file and the menu, and reached the screen
        only the next time they were switched on: you left the menu and the
        tile was still where it had been.
        """
        self.open_readings()
        self.daemon.set_hud(True)
        before = self.drawn()
        self.daemon.menu_command("edit")
        self.daemon.menu_command("pick")
        name = self.daemon.menu.picked
        self.assertIn(name, before)
        self.daemon.menu_command("down")
        after = self.drawn()
        self.assertEqual(after[name],
                         (before[name][0], before[name][1] + 1))

    def test_hiding_a_reading_takes_it_off_the_screen_too(self):
        self.open_readings()
        self.daemon.set_hud(True)
        self.daemon.menu_command("edit")
        name = self.daemon.menu.selected
        self.assertIn(name, self.drawn())
        self.daemon.menu_command("hide")
        self.daemon.menu_command("edit_off")
        self.assertNotIn(name, self.drawn())

    def test_resetting_the_page_resets_the_screen(self):
        self.open_readings()
        self.daemon.set_hud(True)
        before = self.drawn()
        self.daemon.menu_command("edit")
        self.daemon.menu_command("pick")
        self.daemon.menu_command("down")
        self.assertNotEqual(self.drawn(), before)
        self.daemon.menu_command("pick")
        self.daemon.menu_command("restore")
        self.assertEqual(self.drawn(), before)

    def test_nothing_is_pushed_while_the_readings_are_off(self):
        # The HUD packs on the way up, so an arrangement made while they are
        # off is picked up when they come back - and a surface nobody can see
        # is not worth a repack per press.
        self.open_readings()
        self.daemon.set_hud(False)
        sent = len(self.hud_client.sent)
        self.daemon.menu_command("edit")
        self.daemon.menu_command("pick")
        self.daemon.menu_command("down")
        self.assertEqual(len(self.hud_client.sent), sent)

    def test_a_tile_reaches_a_cell_with_nothing_leading_to_it(self):
        # The whole of why this is a cell now: with reordering there was no
        # way to say "third column, fourth row" on a page that has no third
        # tile, and a page drawn over a game is where that is the point.
        name = self.order()[0]
        self.daemon.menu_command("edit")
        self.daemon.menu_command("pick")
        for command in ("right", "right", "down", "down"):
            self.daemon.menu_command(command)
        self.assertEqual(self.cells()[name], (2, 2))
        self.daemon.menu_command("edit_off")
        self.assertIn("[layout.controller.at]", self.written())

    def test_leaving_is_when_it_is_written_down(self):
        self.daemon.menu_command("edit")
        self.daemon.menu_command("pick")
        self.daemon.menu_command("right")
        self.assertEqual(self.written(), "")
        self.daemon.menu_command("edit_off")
        self.assertIn("[layout.controller]", self.written())
        self.assertIn("order = [", self.written())

    def test_the_arrangement_comes_back_on_the_next_start(self):
        self.daemon.menu_command("edit")
        self.daemon.menu_command("pick")
        self.daemon.menu_command("right")
        self.daemon.menu_command("edit_off")
        walked = self.order()
        again = config_module.load(
            path=os.devnull, mapping=os.devnull, settings=os.devnull,
            layout=self.layout)
        fresh = daemon_module.MenuModel(
            daemon_module.build_menu(
                again.menu_items, columns=again.menu_columns,
                settings=config_module.CHOSEN,
                readings=daemon_module.live_module.READINGS),
            again.menu_title, again.menu_clock, columns=again.menu_columns,
            bias=again.menu_bias, layout=again.layout)
        for number, group in enumerate(fresh.groups):
            if group["label"] == "Controller":
                fresh.enter_group(number)
                break
        self.assertEqual([tile["item"]["id"] for tile in fresh.tiles], walked)

    def test_nothing_arranges_outside_edit_mode(self):
        before = self.order()
        for command in ("pick", "hide", "wider", "narrower", "restore"):
            self.daemon.menu_command(command)
        self.assertEqual(self.order(), before)
        self.assertEqual(self.written(), "")

    def test_a_control_cannot_be_taken_while_the_page_is_being_arranged(self):
        walk_menu(self.daemon, ["Sticks"],
                  lambda: self.daemon.menu_command("press"))
        self.daemon.menu_command("edit")
        self.daemon.menu_command("press")   # A is `pick` now, not `take`
        self.assertIsNone(self.daemon.menu.taken)
        self.assertIsNotNone(self.daemon.menu.picked)

    def test_a_tile_that_will_not_move_ticks_rather_than_going_quiet(self):
        self.daemon.menu_command("edit")
        self.daemon.menu_command("pick")
        self.device.played = []
        self.daemon.menu_command("left")     # already first
        self.assertIn(self.daemon.rumble.effects["edge"], self.device.played)

    def test_hiding_takes_a_tile_off_the_page_and_says_so(self):
        self.daemon.menu_command("edit")
        name = self.order()[0]
        self.daemon.menu_command("hide")
        rows = dict((row["id"], row) for row in
                    self.menu_client.sent[-1]["items"])
        self.assertTrue(rows[name]["off"])
        self.daemon.menu_command("edit_off")
        self.assertNotIn(name, self.order())
        self.assertIn("hidden = [", self.written())

    def test_reset_hands_the_page_back_and_writes_that_down(self):
        before = self.order()
        self.daemon.menu_command("edit")
        self.daemon.menu_command("pick")
        self.daemon.menu_command("right")
        self.daemon.menu_command("restore")
        self.assertEqual(self.order(), before)
        self.assertNotIn("[layout.controller]", self.written())

    def test_a_layout_that_cannot_be_written_is_not_a_crash(self):
        # A file omapad wrote itself is omapad's to survive.
        self.daemon.menu_command("edit")
        self.daemon.menu_command("pick")
        self.daemon.menu_command("right")
        with unittest.mock.patch.object(
                daemon_module, "layout_path",
                lambda: "/proc/nothing/layout.toml"):
            self.daemon.menu_command("edit_off")
        self.assertFalse(self.daemon.menu.edit)


class ListedMenuWorkerTests(DaemonTestCase):
    """A listed page filled from the worker rather than on the loop."""

    def setUp(self):
        super().setUp()
        self.commands = self.daemon.commands = FakeCommands(self.session)
        self.daemon.menu.head = []
        self.daemon.set_menu(True)
        self.session.lines = [
            "* Speakers\t1\tanalog-out",
            "Television\t7\thdmi-out",
        ]

    def enter(self, *labels):
        walk_menu(self.daemon, labels,
                  lambda: self.daemon.menu_command("press"))

    def test_the_press_enters_the_page_before_the_answer_arrives(self):
        self.enter("Audio", "Devices", "Output")
        self.assertEqual(len(self.commands.submitted), 1)
        self.assertIn("pactl", self.commands.submitted[0][0])
        self.assertEqual(self.commands.submitted[0][1],
                         self.config.menu_list_timeout)
        # In the page, drawing nothing yet: the pad answered the press.
        self.assertEqual(self.daemon.menu.title, "Output")
        self.assertEqual(self.menu_client.sent[-1]["items"], [])
        self.daemon.drain_commands()
        self.assertEqual([row["l"] for row in self.menu_client.sent[-1]["items"]],
                         ["Speakers", "Television"])

    def test_the_rows_land_in_the_list_the_model_is_drawing(self):
        # In place rather than bound afresh: `press` took the list itself, so
        # a new one would fill a page nobody is looking at.
        self.enter("Audio", "Devices", "Output")
        self.daemon.drain_commands()
        self.assertEqual([item["label"] for item in self.daemon.menu.items],
                         ["Speakers", "Television"])
        self.daemon.menu_command("right")
        self.daemon.menu_command("press")
        self.assertEqual(self.session.spawned,
                         ["omarchy-audio-output-set-default 7 hdmi-out"])

    def test_a_page_entered_again_keeps_its_rows_until_the_fresh_ones_land(self):
        self.enter("Audio", "Devices", "Output")
        self.daemon.drain_commands()
        self.daemon.menu_command("back")
        self.session.lines.append("Headphones\t9\tusb-out")
        self.enter("Output")
        self.assertEqual([row["l"] for row in self.menu_client.sent[-1]["items"]],
                         ["Speakers", "Television"])
        self.daemon.drain_commands()
        self.assertEqual([row["l"] for row in self.menu_client.sent[-1]["items"]],
                         ["Speakers", "Television", "Headphones"])


class AppPageWorkerTests(DaemonTestCase):
    """The keyboard page a profile lends, read off the loop."""

    def setUp(self):
        super().setUp()
        self.commands = self.daemon.commands = FakeCommands(self.session)
        self.config.profiles = [
            {
                "name": "shell",
                "match": ["foot"],
                "bindings": {},
                "osk": {
                    "label": "Term",
                    "keys": [{"label": "Paste", "text": "Paste"}],
                    "from": "history",
                    "ttl": 10.0,
                    "limit": 8,
                },
            },
        ]
        self.daemon.set_active_profile("foot")
        self.session.lines = ["git status"]

    def page_actions(self):
        self.daemon.osk.set_layer("app")
        return [key["action"] for key in self.daemon.osk.rows[0]]

    def test_the_keyboard_opens_on_its_own_keys_and_fills_after(self):
        self.daemon.set_osk(True)
        self.assertEqual(self.commands.submitted, [("history", 2.0)])
        self.assertEqual(self.page_actions(), ["text:Paste"])
        self.daemon.drain_commands()
        self.assertEqual(self.page_actions(), ["text:Paste", "text:git status"])

    def test_the_page_is_asked_for_once_while_the_reading_is_in_flight(self):
        self.daemon.set_osk(True)
        self.daemon.set_osk(False)
        self.daemon.set_osk(True)
        self.assertEqual(len(self.commands.submitted), 1)
        self.daemon.drain_commands()
        # And again once the answer has landed and its ttl has run out.
        self.daemon._osk_page_cache = None
        self.daemon.set_osk(False)
        self.daemon.set_osk(True)
        self.assertEqual(len(self.commands.submitted), 2)

    def test_an_answer_for_an_app_no_longer_in_front_is_dropped(self):
        self.daemon.set_osk(True)
        self.daemon.set_active_profile("chromium")
        self.daemon.drain_commands()
        self.assertIsNone(self.daemon._osk_page_cache)


class GuideTests(DaemonTestCase):
    def open_guide(self):
        self.daemon.set_guide(True)
        self.guide_client.sent.clear()

    def test_the_guide_layer_takes_over_while_it_is_up(self):
        self.open_guide()
        self.assertEqual(self.daemon.current_layer, "guide")
        self.daemon.set_guide(False)
        self.assertEqual(self.daemon.current_layer, "base")

    def test_the_menu_row_opens_it_and_the_menu_gets_out_of_the_way(self):
        self.daemon.set_menu(True)
        # It lives under Controller with everything else about the pad.
        def press():
            self.press("A")
            self.release("A")

        walk_menu(self.daemon, ("Controller", "Shortcuts"), press)
        self.assertTrue(self.daemon.guide_open)
        self.assertFalse(self.daemon.menu_open)

    def test_it_outranks_the_keyboard_and_puts_it_away(self):
        self.daemon.set_osk(True)
        self.open_guide()
        self.assertFalse(self.daemon.osk_open)
        self.assertEqual(self.daemon.current_layer, "guide")

    def test_the_bumpers_turn_the_page_and_repaint(self):
        self.open_guide()
        pages = len(self.daemon.guide.pages)
        self.assertGreater(pages, 1)
        self.press("R")
        self.release("R")
        self.assertEqual(self.daemon.guide.index, 1)
        self.assertEqual(self.guide_client.sent[-1]["page"], 1)
        self.press("L")
        self.release("L")
        self.assertEqual(self.daemon.guide.index, 0)

    def test_b_closes_it(self):
        self.open_guide()
        self.press("B")
        self.release("B")
        self.assertFalse(self.daemon.guide_open)
        self.assertFalse(self.guide_client.sent[-1]["open"])

    def test_it_only_prints_buttons_the_connected_pad_has(self):
        # An XInput pad has no CAPTURE, and the shipped menu layer binds one.
        self.open_guide()
        badges = set()
        for page in self.daemon.guide.pages:
            for column in page["cols"]:
                for group in column:
                    for row in group["rows"]:
                        badges.add(row["b"])
        self.assertNotIn("CAP", badges)
        self.assertIn("A", badges)

    def test_game_mode_puts_it_away(self):
        self.open_guide()
        self.daemon.set_mode("game")
        self.assertFalse(self.daemon.guide_open)

    def test_turning_the_page_does_nothing_while_it_is_down(self):
        self.daemon.guide_command("next")
        self.assertEqual(self.guide_client.sent, [])

    def test_the_control_socket_drives_it_without_the_pad(self):
        reply = self.daemon.handle_control("guide toggle")
        self.assertTrue(self.daemon.guide_open)
        self.assertIn("guide=open", reply)
        self.assertIn("guide=open", self.daemon.handle_control("status"))
        self.daemon.handle_control("guide next")
        self.assertEqual(self.daemon.guide.index, 1)
        self.assertIn("unknown guide command",
                      self.daemon.handle_control("guide sideways"))


class ChordTests(DaemonTestCase):
    """MINUS + PLUS opens the menu, whichever button lands first."""

    def test_minus_first(self):
        self.press("MINUS")
        self.press("PLUS")
        self.assertTrue(self.daemon.menu_open)
        self.release("PLUS")
        self.release("MINUS")
        self.assertTrue(self.daemon.menu_open)
        # Neither button also did its own job: MINUS did not open the keyboard,
        # and PLUS's own menu:toggle did not fire a second time and close it.
        self.assertFalse(self.daemon.osk_open)

    def test_plus_first(self):
        self.press("PLUS")
        self.press("MINUS")
        self.assertTrue(self.daemon.menu_open)
        self.release("PLUS")
        self.release("MINUS")
        self.assertTrue(self.daemon.menu_open)
        self.assertFalse(self.daemon.osk_open)

    def test_a_chord_member_waits_for_its_release(self):
        # Whether MINUS is a chord or a keyboard toggle is not knowable until
        # its partner has had a chance to land, so it cannot fire on the way
        # down.
        self.press("MINUS")
        self.assertFalse(self.daemon.osk_open)
        self.release("MINUS")
        self.assertTrue(self.daemon.osk_open)

    def test_it_is_the_way_in_from_inside_a_game(self):
        # PLUS and MINUS stand aside while an app holds the pad - they are
        # buttons every game binds - so the chord is the only door left, and
        # game mode is a row behind it.
        self.daemon.handed_over = True
        self.press("MINUS")
        self.press("PLUS")
        self.assertTrue(self.daemon.menu_open)

    def test_it_fires_once_per_press_not_once_per_button(self):
        self.press("MINUS")
        self.press("PLUS")
        self.assertTrue(self.daemon.menu_open)
        self.release("PLUS")
        self.press("PLUS")
        self.assertFalse(self.daemon.menu_open)

    def test_either_button_alone_still_does_its_own_job(self):
        self.press("PLUS")
        self.release("PLUS")
        self.assertTrue(self.daemon.menu_open)
        self.assertEqual(self.daemon.mode, "desktop")
        self.daemon.set_menu(False)
        self.press("MINUS")
        self.release("MINUS")
        self.assertTrue(self.daemon.osk_open)
        self.assertEqual(self.daemon.mode, "desktop")


class TerminalCloseTests(DaemonTestCase):
    """`ZL` + B, and the one window it asks a question of first."""

    def close_the_window(self):
        # B is half of the `ZL+B` chord, so the press waits for the release -
        # the chord's own action stands aside on the desktop, where the pad is
        # ours and the layer's binding is what was meant.
        self.press("ZL")
        self.press("B")
        self.release("B")
        self.release("ZL")

    def test_a_terminal_running_a_command_is_interrupted_instead(self):
        # Closing the window would kill the command and take the scrollback
        # that said what it had done with it.
        self.daemon.focus_pid = 4321
        with unittest.mock.patch("omapad.terminal.busy", return_value=True) as busy:
            self.close_the_window()
        self.assertEqual(busy.call_args[0][0], 4321)
        mods, code = keymap.parse_chord("CTRL+C")
        self.assertEqual(self.keyboard.chords,
                         [(tuple(mods), code, True), (tuple(mods), code, False)])
        self.assertEqual(self.hypr.calls, [])

    def test_and_closes_the_window_once_there_is_nothing_to_interrupt(self):
        with unittest.mock.patch("omapad.terminal.busy", return_value=False):
            self.close_the_window()
        self.assertEqual(self.hypr.calls, ["hl.dsp.window.close()"])
        self.assertEqual(self.keyboard.chords, [])

    def test_every_window_that_is_not_a_terminal_closes_as_it_always_did(self):
        # Nothing with a prompt under it, nothing to ask: the /proc walk
        # answers False and the binding is the close it has always been.
        self.daemon.focus_pid = os.getpid()
        self.close_the_window()
        self.assertEqual(self.hypr.calls, ["hl.dsp.window.close()"])


class ModifierButtonTests(DaemonTestCase):
    def test_modifier_never_fires_its_own_binding(self):
        # ZL is a layer trigger (window ops); it must not also right-click.
        self.press("ZL")
        self.assertEqual(self.mouse.buttons, [])
        self.assertEqual(self.hypr.calls, [])
        self.assertEqual(self.session.spawned, [])
        self.release("ZL")


class AppPageConfigTests(unittest.TestCase):
    """What a [profile.<name>.osk] table is allowed to say."""

    def parse(self, spec):
        return config_module.parse_app_page("shell", spec)

    def test_a_bare_string_is_its_own_label(self):
        page = self.parse({"keys": ["git status"]})
        self.assertEqual(
            page["keys"], [{"label": "git status", "text": "git status",
                            "action": None}]
        )

    def test_an_entry_can_send_a_chord_instead_of_typing(self):
        page = self.parse({"keys": [{"label": "Paste", "action": "CTRL+SHIFT+V"}]})
        self.assertEqual(page["keys"][0]["action"], "CTRL+SHIFT+V")
        self.assertIsNone(page["keys"][0]["text"])

    def test_a_chord_that_does_not_parse_names_the_profile(self):
        # `omapad check` has to catch this, not the daemon drawing the page.
        with self.assertRaises(config_module.ConfigError) as caught:
            self.parse({"keys": [{"label": "x", "action": "CTRL+NOSUCHKEY"}]})
        self.assertIn("shell", str(caught.exception))

    def test_an_entry_does_one_thing_or_the_other(self):
        with self.assertRaises(config_module.ConfigError):
            self.parse({"keys": [{"text": "ls", "action": "ENTER"}]})

    def test_an_entry_that_does_nothing_is_rejected(self):
        with self.assertRaises(config_module.ConfigError):
            self.parse({"keys": [{"label": "empty"}]})

    def test_the_shipped_terminal_page_parses_and_pastes(self):
        from omapad import osk

        page = shipped_config().profile_matching("foot")["osk"]
        model = osk.OskModel()
        model.set_app_page(page["label"], page["keys"])
        model.set_layer("app")
        self.assertEqual(
            model.rows[0][0]["chord"],
            ([keymap.resolve("LEFTCTRL"), keymap.resolve("LEFTSHIFT")],
             keymap.resolve("V")),
            "a terminal pastes with Ctrl+Shift+V, not the bottom row's Ctrl+V",
        )


class ProfileHandoverConfigTests(unittest.TestCase):
    """`handover` on a [profile.<name>] table."""

    def test_a_profile_may_refuse_the_hand_off(self):
        config = config_module.Config(
            {"profile": {"chat": {"match": "chat", "handover": False}}}
        )
        self.assertFalse(config.profile_matching("chat")["handover"])

    def test_and_every_other_profile_still_takes_it(self):
        config = config_module.Config({"profile": {"chat": {"match": "chat"}}})
        self.assertTrue(config.profile_matching("chat")["handover"])

    def test_a_value_that_is_not_a_yes_or_a_no_is_named_at_load(self):
        with self.assertRaises(config_module.ConfigError) as caught:
            config_module.Config(
                {"profile": {"chat": {"match": "chat", "handover": "never"}}}
            )
        self.assertIn("handover", str(caught.exception))
        self.assertIn("chat", str(caught.exception))

    def test_the_shipped_discord_profile_keeps_the_pointer(self):
        # Discord is the reason the key exists: it opens the pad to read its
        # own keybinds, and taking that at face value costs the pointer for
        # as long as it is focused.
        self.assertFalse(shipped_config().profile_matching("discord")["handover"])


class ConfigTests(unittest.TestCase):
    def test_every_shipped_binding_parses(self):
        from omapad import actions

        config = shipped_config()
        for layer, bindings in config.bindings.items():
            for button, spec in bindings.items():
                with self.subTest(layer=layer, button=button):
                    actions.Binding(spec)

    def test_an_alignment_the_plugin_cannot_draw_is_named_at_load(self):
        # `omapad check` names it; the alternative is a keyboard that comes
        # up with every badge in the wrong place and nothing to say why.
        with self.assertRaises(config_module.ConfigError) as caught:
            config_module.Config({"osk": {"badge_align": "sideways"}})
        self.assertIn("badge_align", str(caught.exception))
        self.assertEqual(
            config_module.Config({"osk": {"badge_align": "label"}}).osk_badge_align,
            "label",
        )

    def test_user_config_overrides_shipped_defaults(self):
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
            f.write('[pointer]\nspeed = 42.0\n\n[bindings.base]\nA = "nop"\n')
            path = f.name
        try:
            config = config_module.load(path, settings=os.devnull,
                                        layout=os.devnull)
            self.assertEqual(config.pointer_speed, 42.0)
            self.assertEqual(config.binding_for("base", "A"), "nop")
            # Untouched keys still come from the shipped defaults.
            self.assertEqual(config.binding_for("base", "ZR"), "click:left")
        finally:
            os.unlink(path)


class AppProfileTests(DaemonTestCase):
    """Per-application profiles (item 09): match, layering and live swap."""

    def setUp(self):
        super().setUp()
        # The mechanism, not the shipped profiles: one of those matches a
        # terminal too, and declared first it would answer these instead.
        self.config.profiles = []

    def _add_profile(self, name="shell", match=("foot",), bindings=None,
                     layers=None, handover=True):
        self.config.profiles.append(
            {
                "name": name,
                "match": [m.lower() for m in match],
                "bindings": bindings or {},
                "layers": layers or {},
                "handover": handover,
            }
        )

    def test_matching_is_case_insensitive_substring(self):
        self._add_profile(name="shell", match=("foot",))
        self.assertEqual(self.config.profile_matching("foot")["name"], "shell")
        self.assertEqual(self.config.profile_matching("FOOT")["name"], "shell")
        self.assertEqual(self.config.profile_matching("Alacritty"), None)
        self.assertEqual(self.config.profile_matching(""), None)
        self.assertEqual(self.config.profile_matching(None), None)

    def test_a_match_list_accepts_any_of_them(self):
        self._add_profile(name="shell", match=("alacritty", "wezterm"))
        self.assertEqual(self.config.profile_matching("wezterm")["name"], "shell")
        self.assertIsNone(self.config.profile_matching("firefox"))

    def test_first_declared_profile_wins_a_tie(self):
        self._add_profile(name="foot", match=("foot",))
        self._add_profile(name="server", match=("foot",))
        self.assertEqual(self.config.profile_matching("foot")["name"], "foot")

    def test_focusing_a_matching_app_swaps_the_profile(self):
        self._add_profile(name="shell", match=("foot",))
        self.daemon.set_active_profile("")
        self.assertIsNone(self.daemon.active_profile_name)
        self.daemon.set_active_profile("foot")
        self.assertEqual(self.daemon.active_profile_name, "shell")
        self.daemon.set_active_profile("firefox")
        self.assertIsNone(self.daemon.active_profile_name)

    def test_profile_overrides_the_base_binding(self):
        self._add_profile(bindings={"A": "click:middle"})
        self.daemon.set_active_profile("foot")
        self.press("A")
        self.assertEqual(self.mouse.buttons, [("middle", True)])
        self.release("A")
        self.assertEqual(self.mouse.buttons[-1], ("middle", False))

    def test_a_button_the_profile_does_not_name_falls_through_to_base(self):
        self._add_profile(bindings={"Y": "click:right"})
        self.daemon.set_active_profile("foot")
        # A is untouched by the profile, so it still confirms with Enter.
        self.press("A")
        self.assertEqual(self.keyboard.chords, [((), keymap.resolve("ENTER"), True)])
        self.release("A")

    def test_the_profile_stops_where_the_modifier_starts(self):
        # Item 38: the app owns the face buttons at rest, the modifier is the
        # desktop's. ZL + B closes the window whatever B is worth in the app
        # in front, which is what the guide's window page has always said.
        self._add_profile(bindings={"A": "click:middle",
                                    "B": "key:CTRL+SHIFT+D"})
        self.daemon.set_active_profile("foot")
        self.press("ZL")
        self.assertEqual(self.daemon.current_layer, "window")
        for button in ("A", "B"):
            self.press(button)
            self.release(button)
        self.assertEqual(self.mouse.buttons, [])
        self.assertEqual(
            self.hypr.calls,
            [
                "hl.dsp.window.fullscreen({ mode = 'fullscreen' })",
                "hl.dsp.window.close()",
            ],
        )
        self.release("ZL")

    def test_unless_it_names_the_layer_it_wants(self):
        self._add_profile(layers={"window": {"A": "click:middle"}})
        self.daemon.set_active_profile("foot")
        self.press("ZL")
        self.press("A")
        self.assertEqual(self.mouse.buttons, [("middle", True)])
        self.release("A")
        # The rest of the layer is untouched: only the button it names moves.
        self.press("B")
        self.release("B")
        self.assertEqual(self.hypr.calls, ["hl.dsp.window.close()"])
        self.release("ZL")

    def test_no_profile_means_the_ordinary_map(self):
        self.daemon.set_active_profile("firefox")
        self.assertIsNone(self.daemon.active_profile_name)
        self.press("A")
        self.assertEqual(
            self.keyboard.chords, [((), keymap.resolve("ENTER"), True)]
        )
        self.release("A")


class AppPageTests(DaemonTestCase):
    """The keyboard page a profile lends the app it matches."""

    def setUp(self):
        super().setUp()
        self.config.profiles = []

    def _add_profile(self, source="history", keys=(), ttl=10.0, limit=8):
        self.config.profiles.append(
            {
                "name": "shell",
                "match": ["foot"],
                "bindings": {},
                "osk": {
                    "label": "Term",
                    "keys": [{"label": k, "text": k} for k in keys],
                    "from": source,
                    "ttl": ttl,
                    "limit": limit,
                },
            },
        )
        self.daemon.set_active_profile("foot")

    def test_the_page_arrives_when_the_keyboard_opens(self):
        # Not when focus moves: a window change is not worth spawning a shell
        # for, and the page cannot be read while the keyboard is down.
        self._add_profile()
        self.session.lines = ["git status", "ls -la"]
        self.assertEqual(self.session.captured, [])
        self.daemon.set_osk(True)
        self.assertEqual(self.session.captured, ["history"])
        self.assertIn("app", self.daemon.osk.order)
        self.daemon.osk.set_layer("app")
        self.assertEqual(
            [key["action"] for key in self.daemon.osk.rows[0]],
            ["text:git status", "text:ls -la"],
        )

    def test_an_app_with_no_page_leaves_the_pages_alone(self):
        self.daemon.set_osk(True)
        self.assertNotIn("app", self.daemon.osk.order)
        self.assertEqual(self.session.captured, [])

    def test_the_page_goes_away_with_the_window_it_belonged_to(self):
        self._add_profile()
        self.session.lines = ["ls"]
        self.daemon.set_osk(True)
        self.daemon.set_osk(False)
        self.daemon.set_active_profile("firefox")
        self.daemon.set_osk(True)
        self.assertNotIn("app", self.daemon.osk.order)

    def test_the_command_is_not_run_again_inside_its_ttl(self):
        self._add_profile()
        self.session.lines = ["ls"]
        self.daemon.set_osk(True)
        self.daemon.set_osk(False)
        self.daemon.set_osk(True)
        self.assertEqual(self.session.captured, ["history"])

    def test_moving_focus_asks_again(self):
        self._add_profile()
        self.session.lines = ["ls"]
        self.daemon.set_osk(True)
        self.daemon.set_osk(False)
        self.daemon.set_active_profile("firefox")
        self.daemon.set_active_profile("foot")
        self.daemon.set_osk(True)
        self.assertEqual(self.session.captured, ["history", "history"])

    def test_written_down_entries_need_no_command(self):
        self._add_profile(source=None, keys=("git status",))
        self.daemon.set_osk(True)
        self.assertEqual(self.session.captured, [])
        self.daemon.osk.set_layer("app")
        self.assertEqual(self.daemon.osk.rows[0][0]["action"], "text:git status")

    def test_the_limit_is_what_reaches_the_page(self):
        self._add_profile(keys=("kept",), limit=2)
        self.session.lines = ["one", "two", "three"]
        self.daemon.set_osk(True)
        self.daemon.osk.set_layer("app")
        actions_on_page = [
            key["action"]
            for row in self.daemon.osk.rows
            for key in row
            if key["action"].startswith("text:")
        ]
        self.assertEqual(actions_on_page, ["text:kept", "text:one"])

    def test_pressing_an_entry_types_the_whole_command(self):
        self._add_profile(source=None, keys=("ls",))
        self.daemon.set_osk(True)
        self.daemon.osk.set_layer("app")
        self.daemon.osk.row, self.daemon.osk.col = 0, 0
        self.press("A")
        self.release("A")
        self.assertEqual(
            self.keyboard.chords,
            [((), keymap.resolve("L"), True), ((), keymap.resolve("L"), False),
             ((), keymap.resolve("S"), True), ((), keymap.resolve("S"), False)],
        )


class ShoulderConfirmTests(DaemonTestCase):
    """Item 18, piloted on the browser: a tap is the app's, a hold is ours.

    The shipped [profile.browser] gives L and R the browser's tab switcher on a
    tap and the workspace on a deliberate hold, announced two seconds in and
    acted on two seconds after that.
    """

    def _hold(self, button, ms):
        """Press and let the hold timer run to `ms`, without releasing."""
        self.press(button)
        pressed_at = self.daemon.held[button].pressed_at
        self.daemon.check_hold_timers(pressed_at + ms / 1000.0)
        return pressed_at

    def test_the_shoulders_switch_workspace_on_release_not_on_press(self):
        self.press("R")
        self.assertEqual(self.hypr.calls, [])
        self.release("R")
        self.assertEqual(self.hypr.calls, ["hl.dsp.focus({ workspace = 'r+1' })"])

    def test_in_the_browser_a_tap_switches_tabs_instead(self):
        self.daemon.set_active_profile("chromium")
        self.press("R")
        self.release("R")
        self.assertEqual(self.hypr.calls, [])
        self.assertEqual(
            self.keyboard.chords,
            [((keymap.resolve("CTRL"),), keymap.resolve("TAB"), True),
             ((keymap.resolve("CTRL"),), keymap.resolve("TAB"), False)],
        )

    def test_l_and_r_walk_tabs_in_opposite_directions(self):
        self.daemon.set_active_profile("chromium")
        self.press("L")
        self.release("L")
        self.assertEqual(
            self.keyboard.chords[0],
            ((keymap.resolve("CTRL"), keymap.resolve("SHIFT")),
             keymap.resolve("TAB"), True),
        )

    def test_a_hold_announces_itself_before_it_acts(self):
        self.daemon.set_active_profile("chromium")
        pressed_at = self._hold("R", 2000)
        # Two seconds in: a tick, a notification, and nothing has happened yet.
        self.assertEqual(self.device.played,
                         [self.daemon.rumble.effects["tick"]])
        self.assertEqual(len(self.session.notifications), 1)
        self.assertIn("Next workspace", self.session.notifications[0][1])
        self.assertIn("B to cancel", self.session.notifications[0][1])
        self.assertEqual(self.hypr.calls, [])
        # Two more, and it happens.
        self.daemon.check_hold_timers(pressed_at + 4.0)
        self.assertEqual(self.hypr.calls, ["hl.dsp.focus({ workspace = 'r+1' })"])

    def test_letting_go_during_the_countdown_backs_out(self):
        self.daemon.set_active_profile("chromium")
        self._hold("R", 2000)
        self.release("R")
        # Neither the workspace nor - and this is the point - the tab switch
        # the tap would otherwise have fired on the way up.
        self.assertEqual(self.hypr.calls, [])
        self.assertEqual(self.keyboard.chords, [])

    def test_the_cancel_button_backs_out_without_doing_its_own_job(self):
        self.daemon.set_active_profile("chromium")
        pressed_at = self._hold("R", 2000)
        self.press("B")
        self.assertTrue(self.daemon.pending_confirm() == [])
        # B is Esc at rest; while a confirmation is up it is only the way out.
        self.assertEqual(self.keyboard.chords, [])
        self.daemon.check_hold_timers(pressed_at + 4.0)
        self.assertEqual(self.hypr.calls, [])
        self.release("B")
        self.release("R")
        self.assertEqual(self.hypr.calls, [])

    def test_the_cancel_button_is_itself_again_once_nothing_is_pending(self):
        self.press("B")
        self.release("B")
        self.assertEqual(
            self.keyboard.chords,
            [((), keymap.resolve("ESC"), True), ((), keymap.resolve("ESC"), False)],
        )

    def test_a_hold_that_is_not_confirmed_still_fires_at_hold_ms(self):
        # HOME's hold has no confirm_ms, so it acts the moment it is due.
        self.press("HOME")
        pressed_at = self.daemon.held["HOME"].pressed_at
        self.daemon.check_hold_timers(pressed_at + 1.0)
        self.assertEqual(self.daemon.mode, "game")


class BrowserProfileTests(DaemonTestCase):
    """The rest of the shipped [profile.browser]: tab, reload, back, forward."""

    def setUp(self):
        super().setUp()
        self.daemon.set_active_profile("chromium")

    def chord(self, *names):
        code = keymap.resolve(names[-1])
        mods = tuple(keymap.resolve(name) for name in names[:-1])
        return [(mods, code, True), (mods, code, False)]

    def test_x_opens_a_tab_on_a_tap_and_reloads_on_a_hold(self):
        self.press("X")
        self.assertEqual(self.keyboard.chords, [])  # waits to see which it is
        self.release("X")
        self.assertEqual(self.keyboard.chords, self.chord("CTRL", "T"))

        self.keyboard.chords.clear()
        self.press("X")
        pressed_at = self.daemon.held["X"].pressed_at
        self.daemon.check_hold_timers(pressed_at + 1.0)
        self.assertEqual(self.keyboard.chords, self.chord("F5"))
        self.release("X")
        # The tap must not also fire once the hold has gone out.
        self.assertEqual(self.keyboard.chords, self.chord("F5"))

    def test_the_stick_clicks_walk_history(self):
        self.press("RSTICK")
        self.release("RSTICK")
        self.assertEqual(self.keyboard.chords, self.chord("ALT", "LEFT"))
        self.keyboard.chords.clear()
        self.press("LSTICK")
        self.release("LSTICK")
        self.assertEqual(self.keyboard.chords, self.chord("ALT", "RIGHT"))
        # Neither is a mouse click any more while the browser has focus.
        self.assertEqual(self.mouse.buttons, [])

    def test_outside_the_browser_they_are_mouse_buttons_again(self):
        # A window no profile names: the terminal would not do, since
        # [profile.shell] spends X on Backspace and both stick clicks on keys.
        self.daemon.set_active_profile("kate")
        self.press("X")
        self.assertEqual(self.mouse.buttons, [("middle", True)])
        self.release("X")
        self.press("RSTICK")
        self.assertEqual(self.mouse.buttons[-1], ("back", True))
        self.release("RSTICK")
        self.assertEqual(self.keyboard.chords, [])

    def test_the_browser_lends_the_keyboard_a_page_of_its_own(self):
        # A URL is what the keyboard is opened for in a browser, so the page
        # leads with the address bar and the prefix nothing guesses.
        self.daemon.set_osk(True)
        self.assertIn("app", self.daemon.osk.order)
        self.assertEqual(self.daemon.osk.app_label, "Web")
        self.daemon.osk.set_layer("app")
        on_page = [key["action"] for row in self.daemon.osk.rows for key in row]
        self.assertEqual(
            on_page[:3], ["CTRL+L", "text:https://", "CTRL+ENTER"]
        )

    def test_an_entry_on_that_page_sends_its_chord(self):
        self.daemon.set_osk(True)
        self.daemon.osk.set_layer("app")
        self.daemon.osk.row, self.daemon.osk.col = 0, 0
        self.press("A")
        self.release("A")
        self.assertEqual(self.keyboard.chords, self.chord("CTRL", "L"))

    def test_what_the_profile_does_not_name_still_works(self):
        # Left click, right click, Enter, Esc and the arrows are untouched -
        # a browser is useless without them.
        self.press("ZR")
        self.assertEqual(self.mouse.buttons, [("left", True)])
        self.release("ZR")
        self.press("Y")
        self.assertEqual(self.mouse.buttons[-1], ("right", True))
        self.release("Y")
        self.press("A")
        self.assertEqual(self.keyboard.chords[0], ((), keymap.resolve("ENTER"), True))
        self.release("A")
        self.feed((li.EV_ABS, li.ABS_HAT0Y, 1))
        self.assertEqual(self.keyboard.chords[-1], ((), keymap.resolve("DOWN"), True))
        self.feed((li.EV_ABS, li.ABS_HAT0Y, 0))


class FileManagerProfileTests(DaemonTestCase):
    """The shipped [profile.files]: B walks out of a folder instead of Esc."""

    def chord(self, *names):
        code = keymap.resolve(names[-1])
        mods = tuple(keymap.resolve(name) for name in names[:-1])
        return [(mods, code, True), (mods, code, False)]

    def test_b_goes_up_one_directory(self):
        # The class Nautilus reports is org.gnome.Nautilus; `match` is a
        # case-insensitive substring, so the bare name is enough to catch it.
        self.daemon.set_active_profile("org.gnome.Nautilus")
        self.press("B")
        self.release("B")
        self.assertEqual(self.keyboard.chords, self.chord("ALT", "UP"))

    def test_outside_a_file_manager_b_is_esc_again(self):
        self.daemon.set_active_profile("foot")
        self.press("B")
        self.release("B")
        self.assertEqual(self.keyboard.chords, self.chord("ESC"))


class DiscordProfileTests(DaemonTestCase):
    """The shipped [profile.discord]: the face buttons are the voice panel."""

    def chord(self, *names):
        code = keymap.resolve(names[-1])
        mods = tuple(keymap.resolve(name) for name in names[:-1])
        return [(mods, code, True), (mods, code, False)]

    def setUp(self):
        super().setUp()
        self.daemon.set_active_profile("discord")

    def test_a_and_b_mute_and_deafen(self):
        # Both carry a hold, so the tap goes out on the way back up.
        self.press("A")
        self.assertEqual(self.keyboard.chords, [])
        self.release("A")
        self.assertEqual(self.keyboard.chords, self.chord("CTRL", "SHIFT", "M"))
        self.keyboard.chords = []
        self.press("B")
        self.release("B")
        self.assertEqual(self.keyboard.chords, self.chord("CTRL", "SHIFT", "D"))

    def test_holding_them_still_means_enter_and_esc(self):
        for button, key in (("A", "ENTER"), ("B", "ESC")):
            self.keyboard.chords = []
            self.press(button)
            pressed_at = self.daemon.held[button].pressed_at
            self.daemon.check_hold_timers(pressed_at + 1.0)
            self.assertEqual(self.keyboard.chords, self.chord(key))
            self.release(button)

    def test_x_and_y_are_the_two_a_pointer_is_worst_at(self):
        self.press("X")
        self.release("X")
        self.assertEqual(self.keyboard.chords, self.chord("CTRL", "K"))
        self.keyboard.chords = []
        self.press("Y")
        self.release("Y")
        self.assertEqual(self.keyboard.chords, self.chord("CTRL", "ENTER"))

    def test_the_right_click_y_gave_up_moves_to_the_left_stick(self):
        # A context menu is how Discord replies to and reacts to a message, so
        # it is displaced rather than dropped.
        self.press("LSTICK")
        self.assertEqual(self.mouse.buttons[-1], ("right", True))
        self.release("LSTICK")

    def test_the_webapp_beats_the_browser_profile_to_the_class(self):
        # Omarchy installs Discord as a webapp as readily as pacman installs
        # the client, and a webapp is a Chromium window: its class matches
        # "chrome" as squarely as it matches "discord". The first profile
        # declared wins, so this one is declared before [profile.browser] -
        # written after it, none of it would fire on the install that needs
        # it most.
        webapp = "chrome-discord.com__channels_@me-Default"
        self.assertEqual(
            self.config.profile_matching(webapp)["name"], "discord"
        )

    def test_a_fork_is_matched_by_its_own_name(self):
        self.assertEqual(
            self.config.profile_matching("Vesktop")["name"], "discord"
        )
        # "discord" is a substring, so Canary and PTB come along for free.
        self.assertEqual(
            self.config.profile_matching("discordcanary")["name"], "discord"
        )

    def test_the_keyboard_outranks_the_profile(self):
        # A surface on screen is what the buttons belong to: muting the mic
        # while typing would eat the key that presses the selected cell.
        self.daemon.set_osk(True)
        self.keyboard.chords = []
        self.press("A")
        self.release("A")
        self.assertNotIn(self.chord("CTRL", "SHIFT", "M")[0], self.keyboard.chords)

    def test_discord_lends_the_keyboard_a_chat_page(self):
        # A chat app's page is the sentences you send without meaning anything
        # by them - three keys instead of nine aimed letters.
        self.daemon.set_osk(True)
        self.assertEqual(self.daemon.osk.app_label, "Chat")
        self.daemon.osk.set_layer("app")
        on_page = [key["action"] for row in self.daemon.osk.rows for key in row]
        self.assertEqual(
            on_page[:3], ["text:brb", "text:omw", "text:gg"]
        )


class YouTubeProfileTests(DaemonTestCase):
    """The shipped [profile.youtube]: the television's two controls."""

    WEBAPP = "chrome-www.youtube.com__-Default"

    def chord(self, *names):
        code = keymap.resolve(names[-1])
        mods = tuple(keymap.resolve(name) for name in names[:-1])
        return [(mods, code, True), (mods, code, False)]

    def setUp(self):
        super().setUp()
        self.daemon.set_active_profile(self.WEBAPP)

    def test_x_plays_and_y_fills_the_screen(self):
        # `k` rather than Space: Space scrolls the page whenever the player is
        # not the focused element.
        self.press("X")
        self.release("X")
        self.assertEqual(self.keyboard.chords, self.chord("K"))
        self.keyboard.chords = []
        self.press("Y")
        self.release("Y")
        self.assertEqual(self.keyboard.chords, self.chord("F"))

    def test_a_and_b_are_left_alone_because_they_already_fit(self):
        # Enter opens the thumbnail the stick walked to; Esc is how a browser
        # leaves fullscreen, which is B going back in the player's own words.
        for button, key in (("A", "ENTER"), ("B", "ESC")):
            self.keyboard.chords = []
            self.press(button)
            self.release(button)
            self.assertEqual(self.keyboard.chords, self.chord(key))

    def test_the_stick_clicks_carry_the_search_and_the_way_back(self):
        self.press("LSTICK")
        self.release("LSTICK")
        self.assertEqual(self.keyboard.chords, self.chord("SLASH"))
        self.keyboard.chords = []
        self.press("RSTICK")
        self.release("RSTICK")
        self.assertEqual(self.keyboard.chords, self.chord("ALT", "LEFT"))

    def test_the_webapp_beats_the_browser_profile_to_the_class(self):
        # 35's trap: a webapp class matches "chrome" as squarely as it matches
        # its own host, and the first profile declared wins.
        self.assertEqual(
            self.config.profile_matching(self.WEBAPP)["name"], "youtube"
        )
        self.assertEqual(
            self.config.profile_matching("chrome-youtube.com__-Default")["name"],
            "youtube",
        )

    def test_youtube_music_is_not_youtube(self):
        # None of these keys exist there, so the host is matched with its
        # leading dash rather than as the bare word "youtube".
        self.assertEqual(
            self.config.profile_matching(
                "chrome-music.youtube.com__-Default"
            )["name"],
            "browser",
        )

    def test_the_shoulders_stay_the_workspaces(self):
        # A webapp has no tabs to walk, so the one thing [profile.browser]
        # spends them on does not apply here.
        self.press("L")
        self.release("L")
        self.assertEqual(
            self.hypr.calls, ["hl.dsp.focus({ workspace = 'r-1' })"]
        )


class ShellProfileTests(DaemonTestCase):
    """The shipped [profile.shell]: the keys a shell is driven with."""

    def chord(self, *names):
        code = keymap.resolve(names[-1])
        mods = tuple(keymap.resolve(name) for name in names[:-1])
        return [(mods, code, True), (mods, code, False)]

    def setUp(self):
        super().setUp()
        self.daemon.set_active_profile("foot")

    def test_x_deletes_on_the_way_down_so_it_repeats(self):
        # Written plain rather than as a tap/hold: a tap/hold binding waits for
        # the release before its key goes down, and the autorepeat is the whole
        # point of a Backspace button.
        self.press("X")
        self.assertEqual(self.keyboard.chords, self.chord("BACKSPACE")[:1])
        self.release("X")
        self.assertEqual(self.keyboard.chords, self.chord("BACKSPACE"))

    def test_backspace_is_on_the_same_button_as_the_keyboards(self):
        # The pattern's whole point, and the one pair of surfaces a command is
        # typed across: the key must not move under the thumb when the
        # on-screen keyboard opens over the prompt and closes again.
        profile = self.config.profile_matching("foot")
        self.assertEqual(profile["bindings"]["X"], "key:BACKSPACE")
        self.assertEqual(self.config.binding_for("osk", "X"), "key:BACKSPACE")

    def test_y_pastes_the_clipboard(self):
        # Y carries a hold, so the tap goes out on the way back up.
        self.press("Y")
        self.assertEqual(self.keyboard.chords, [])
        self.release("Y")
        self.assertEqual(self.keyboard.chords, self.chord("CTRL", "SHIFT", "V"))

    def test_holding_y_interrupts(self):
        self.press("Y")
        pressed_at = self.daemon.held["Y"].pressed_at
        self.daemon.check_hold_timers(pressed_at + 1.0)
        self.assertEqual(self.keyboard.chords, self.chord("CTRL", "C"))
        self.release("Y")

    def test_the_left_stick_click_clears_the_screen(self):
        self.press("LSTICK")
        self.release("LSTICK")
        self.assertEqual(self.keyboard.chords, self.chord("CTRL", "L"))

    def test_the_right_stick_click_copies(self):
        # The shifted one: Ctrl+C is the interrupt in all five emulators, and
        # here it is already on Y's hold.
        self.press("RSTICK")
        self.release("RSTICK")
        self.assertEqual(self.keyboard.chords, self.chord("CTRL", "SHIFT", "C"))
        # And it is a key rather than the back click it is everywhere else.
        self.assertEqual(self.mouse.buttons, [])

    def test_b_is_left_alone_so_the_window_layer_can_still_close(self):
        # The reason Ctrl+C is not on B: a profile reaches into the held
        # layers, so binding B here would take ZL + B - close the window -
        # away from every terminal.
        profile = self.config.profile_matching("foot")
        self.assertNotIn("B", profile["bindings"])
        self.assertEqual(
            self.config.binding_with_profile(profile, "window", "B"),
            self.config.binding_for("window", "B"),
        )

    def test_no_face_button_is_a_click_here(self):
        # The price of the overrides above: X was the middle click - and with
        # it the PRIMARY selection - and Y was the right click. Neither is
        # reachable from the pad in a terminal any more, which is what R3's
        # copy gives back, on the clipboard rather than in PRIMARY.
        for button in ("X", "Y"):
            self.press(button)
            self.release(button)
        self.assertEqual(self.mouse.buttons, [])


class ConfigProfileResolutionTests(unittest.TestCase):
    """config.binding_with_profile: profile -> layer -> base, surfaces exempt."""

    def _config(self):
        data = config_module._load_toml(config_module.DEFAULT_CONFIG_PATH)
        data["profile"] = {
            "shell": {"match": "foot", "bindings": {"A": "click:middle"}}
        }
        return config_module.Config(data)

    def test_unbound_button_keeps_the_layer_semantics(self):
        cfg = self._config()
        profile = cfg.profile_matching("foot")
        # base A overridden by the profile
        self.assertEqual(cfg.binding_with_profile(profile, "base", "A"), "click:middle")
        # base Y is untouched -> falls through to the shipped base binding
        self.assertIsNotNone(cfg.binding_with_profile(profile, "base", "Y"))
        # A in the window layer: the modifier is the desktop's, so the layer
        # keeps its own binding and Y is untouched either way.
        self.assertEqual(
            cfg.binding_with_profile(profile, "window", "A"),
            cfg.binding_for("window", "A"),
        )
        self.assertIsNotNone(cfg.binding_with_profile(profile, "window", "Y"))

    def test_a_profile_may_name_a_held_layer_to_reach_it(self):
        # The capability the rule above takes away, given back by name: an app
        # that really does want a window op of its own says which layer.
        data = config_module._load_toml(config_module.DEFAULT_CONFIG_PATH)
        data["profile"] = {
            "shell": {
                "match": "foot",
                "bindings": {"A": "click:middle"},
                "window": {"A": "exec:tile-me"},
            }
        }
        cfg = config_module.Config(data)
        profile = cfg.profile_matching("foot")
        self.assertEqual(
            cfg.binding_with_profile(profile, "window", "A"), "exec:tile-me"
        )
        # And only the button it names: B still closes the window.
        self.assertEqual(
            cfg.binding_with_profile(profile, "window", "B"),
            cfg.binding_for("window", "B"),
        )

    def test_a_profile_key_that_is_no_layer_is_named_at_load(self):
        # Silent otherwise: [profile.shell.windows] would simply never fire.
        with self.assertRaises(config_module.ConfigError):
            config_module.Config(
                {"profile": {"shell": {"match": "foot", "windows": {}}}}
            )
        with self.assertRaises(config_module.ConfigError):
            config_module.Config(
                {
                    "layers": {"window": {"button": "ZL"}},
                    "profile": {"shell": {"match": "foot", "window": "bad"}},
                }
            )

    def test_a_profile_stick_stops_at_the_held_layer_too(self):
        data = config_module._load_toml(config_module.DEFAULT_CONFIG_PATH)
        data["profile"] = {
            "browser": {"match": "chromium", "right_stick": "scroll"}
        }
        cfg = config_module.Config(data)
        profile = cfg.profile_matching("chromium")
        self.assertEqual(cfg.stick_roles("base", profile)[1], "scroll")
        # ZL down: both sticks are the window's, wheel or no wheel.
        self.assertEqual(
            cfg.stick_roles("window", profile), cfg.stick_roles("window")
        )

    def test_a_surface_is_never_overridden_by_a_profile(self):
        cfg = self._config()
        profile = cfg.profile_matching("foot")
        # osk/menu/guide are surfaces; a profile must not reach them.
        self.assertEqual(
            cfg.binding_with_profile(profile, "osk", "A"),
            cfg.binding_for("osk", "A"),
        )
        self.assertEqual(
            cfg.binding_with_profile(profile, "menu", "A"),
            cfg.binding_for("menu", "A"),
        )
        self.assertEqual(
            cfg.binding_with_profile(profile, "guide", "A"),
            cfg.binding_for("guide", "A"),
        )

    def test_broken_profile_binding_is_rejected_at_load(self):
        # a profile must say what it matches to exist
        with self.assertRaises(config_module.ConfigError):
            config_module.Config({"profile": {"shell": {}}})
        with self.assertRaises(config_module.ConfigError):
            config_module.Config({"profile": {"shell": {"match": ""}}})
        with self.assertRaises(config_module.ConfigError):
            config_module.Config({"profile": {"shell": "not a table"}})
        # bindings must be a table of actions
        with self.assertRaises(config_module.ConfigError):
            config_module.Config(
                {"profile": {"shell": {"match": "foot", "bindings": "bad"}}}
            )
        # but match-with-no-bindings is a valid empty override
        config = config_module.Config(
            {"profile": {"shell": {"match": "foot"}}}
        )
        self.assertEqual(config.profile_matching("foot")["bindings"], {})


def snap_window(address, x, y, width, height):
    return {
        "address": address,
        "at": [x, y],
        "size": [width, height],
        "workspace": {"id": 1, "name": "1"},
        "monitor": 0,
        "mapped": True,
        "hidden": False,
    }


SNAP_MONITORS = [
    {
        "id": 0, "x": 0, "y": 0, "width": 1536, "height": 960, "scale": 1.0,
        "activeWorkspace": {"id": 1}, "specialWorkspace": {"id": 0},
    },
]


class SnapTests(DaemonTestCase):
    """Pointing at the window next door, over a canned desktop."""

    def setUp(self):
        super().setUp()
        self.left = snap_window("0xaaa", 0, 0, 760, 900)
        self.right = snap_window("0xbbb", 768, 0, 760, 900)
        self.hypr.answers = {
            "clients": [self.left, self.right],
            "monitors": SNAP_MONITORS,
            "activewindow": self.left,
        }
        self.hypr.position = (380.0, 450.0)

    def test_a_snap_warps_the_pointer_and_focuses_what_it_lands_on(self):
        self.assertTrue(self.daemon.snap_cursor("right"))
        self.assertEqual(self.hypr.warps, [(1148, 450)])
        self.assertEqual(
            self.hypr.calls, ["hl.dsp.focus({ window = 'address:0xbbb' })"]
        )

    def test_nothing_that_way_moves_nothing(self):
        self.assertFalse(self.daemon.snap_cursor("left"))
        self.assertEqual(self.hypr.warps, [])
        self.assertEqual(self.hypr.calls, [])

    def test_the_bias_reaches_the_choice(self):
        # A window closer to the right but well off the pointer's line,
        # against one further right that the pointer lines up with.
        aside = snap_window("0xccc", 500, 900, 300, 200)
        self.hypr.answers["clients"] = [self.left, self.right, aside]
        self.config.snap_bias = 0.1
        self.assertTrue(self.daemon.snap_cursor("right"))
        self.assertEqual(self.hypr.warps, [(650, 1000)])
        self.hypr.warps.clear()
        self.config.snap_bias = 8.0
        self.assertTrue(self.daemon.snap_cursor("right"))
        self.assertEqual(self.hypr.warps, [(1148, 450)])

    def test_focus_can_be_left_to_the_pointer(self):
        self.config.snap_focus = False
        self.assertTrue(self.daemon.snap_cursor("right"))
        self.assertEqual(self.hypr.warps, [(1148, 450)])
        self.assertEqual(self.hypr.calls, [])

    def test_centre_lands_in_the_middle_of_the_window_in_front(self):
        self.hypr.position = (10.0, 10.0)
        self.assertTrue(self.daemon.snap_cursor("centre"))
        self.assertEqual(self.hypr.warps, [(380, 450)])

    def test_no_compositor_is_not_a_crash(self):
        self.hypr.position = None
        self.assertFalse(self.daemon.snap_cursor("right"))
        self.hypr.position = (380.0, 450.0)
        self.hypr.answers = {}
        self.assertFalse(self.daemon.snap_cursor("right"))
        self.assertEqual(self.hypr.warps, [])

    def test_the_binding_grammar_reaches_it(self):
        self.config.bindings["base"]["Y"] = "snap:right"
        self.daemon.bindings.clear()
        self.press("Y")
        self.release("Y")
        self.assertEqual(self.hypr.warps, [(1148, 450)])

    def test_a_bad_direction_does_not_parse(self):
        with self.assertRaises(actions.ActionError):
            actions.parse("snap:sideways")


class SnapStickTests(DaemonTestCase):
    """A stick whose role is `snap`: one window per push, not a stream."""

    def setUp(self):
        super().setUp()
        self.config.left_stick = "snap"
        self.left = snap_window("0xaaa", 0, 0, 760, 900)
        self.right = snap_window("0xbbb", 768, 0, 760, 900)
        self.hypr.answers = {
            "clients": [self.left, self.right],
            "monitors": SNAP_MONITORS,
        }
        self.hypr.position = (380.0, 450.0)

    def push(self, fraction):
        self.feed((li.EV_ABS, li.ABS_X, int(32767 * fraction)))
        self.tick(0.05)

    def test_pushing_the_stick_over_snaps_once(self):
        self.push(1.0)
        self.push(1.0)
        self.push(1.0)
        self.assertEqual(self.hypr.warps, [(1148, 450)])

    def test_it_re_arms_only_after_the_stick_comes_back(self):
        self.push(1.0)
        self.push(0.2)
        self.hypr.position = (380.0, 450.0)
        self.push(1.0)
        self.assertEqual(len(self.hypr.warps), 2)

    def test_a_nudge_is_not_a_flick(self):
        self.push(0.5)
        self.assertEqual(self.hypr.warps, [])

    def test_a_snap_that_lands_can_tick_the_pad(self):
        self.config.snap_rumble = True
        self.push(1.0)
        self.assertEqual(self.device.played,
                         [self.daemon.rumble.effects["tick"]])

    def test_a_flick_into_an_empty_edge_stays_quiet(self):
        self.config.snap_rumble = True
        self.hypr.position = (1148.0, 450.0)  # already in the rightmost window
        self.push(1.0)
        self.assertEqual(self.hypr.warps, [])
        self.assertEqual(self.device.played, [])

    def test_the_tick_is_off_by_default(self):
        self.push(1.0)
        self.assertEqual(self.device.played, [])

    def test_the_loop_keeps_ticking_until_the_stick_is_let_go(self):
        # Without this a stick released between two ticks would never re-arm,
        # and the snap would work exactly once per session.
        self.push(1.0)
        self.assertFalse(self.daemon._snap_armed["left"])
        self.assertTrue(self.daemon.needs_tick())


class SwapStickTests(DaemonTestCase):
    """A stick whose role is `swap`: one neighbour per push."""

    def setUp(self):
        super().setUp()
        self.config.left_stick = "swap"

    def push(self, fraction):
        self.feed((li.EV_ABS, li.ABS_X, int(32767 * fraction)))
        self.tick(0.05)

    def test_pushing_the_stick_over_swaps_once(self):
        self.push(1.0)
        self.push(1.0)
        self.push(1.0)
        self.assertEqual(
            self.hypr.calls,
            ["hl.dsp.window.swap({ direction = 'r' })"],
        )

    def test_it_re_arms_only_after_the_stick_comes_back(self):
        self.push(1.0)
        self.push(0.2)
        self.push(-1.0)
        self.assertEqual(
            self.hypr.calls,
            [
                "hl.dsp.window.swap({ direction = 'r' })",
                "hl.dsp.window.swap({ direction = 'l' })",
            ],
        )

    def test_a_nudge_is_not_a_flick(self):
        self.push(0.5)
        self.assertEqual(self.hypr.calls, [])

    def test_the_vertical_axis_says_up_and_down(self):
        self.feed((li.EV_ABS, li.ABS_Y, -32767))
        self.tick(0.05)
        self.assertEqual(
            self.hypr.calls,
            ["hl.dsp.window.swap({ direction = 'u' })"],
        )

    def test_the_loop_keeps_ticking_until_the_stick_is_let_go(self):
        self.push(1.0)
        self.assertFalse(self.daemon._swap_armed["left"])
        self.assertTrue(self.daemon.needs_tick())


class MoveStickTests(DaemonTestCase):
    """The `move` role, which is a drag or a swap depending on the window."""

    def setUp(self):
        super().setUp()
        self.config.left_stick = "move"

    def push(self, fraction, seconds=0.05):
        self.feed((li.EV_ABS, li.ABS_X, int(32767 * fraction)))
        self.tick(seconds)

    def floating(self, yes):
        self.hypr.answers = {"activewindow": {"floating": yes}}

    def test_a_floating_window_is_dragged(self):
        self.floating(True)
        self.push(1.0)
        self.assertEqual(len(self.hypr.calls), 1)
        self.assertIn("hl.dsp.window.move(", self.hypr.calls[0])

    def test_a_tiled_window_is_swapped(self):
        self.floating(False)
        self.push(1.0)
        self.assertEqual(
            self.hypr.calls,
            ["hl.dsp.window.swap({ direction = 'r' })"],
        )

    def test_a_tiled_window_swaps_once_per_push(self):
        self.floating(False)
        self.push(1.0)
        self.push(1.0)
        self.push(1.0)
        self.assertEqual(len(self.hypr.calls), 1)

    def test_the_window_is_asked_once_per_push(self):
        # A `j/` on every tick is 30 a second under a resting thumb; the
        # answer cannot change while one window stays focused under it.
        self.floating(False)
        self.push(1.0)
        self.push(1.0)
        self.push(1.0)
        self.assertEqual(self.hypr.queries.count("activewindow"), 1)

    def test_letting_go_asks_again(self):
        self.floating(False)
        self.push(1.0)
        self.push(0.0)
        self.push(1.0)
        self.assertEqual(self.hypr.queries.count("activewindow"), 2)

    def test_no_compositor_drags(self):
        # What this role did before it had a second half.
        self.hypr.answers = {}
        self.push(1.0)
        self.assertEqual(len(self.hypr.calls), 1)
        self.assertIn("hl.dsp.window.move(", self.hypr.calls[0])

    def test_a_resting_stick_asks_nothing(self):
        self.push(0.0)
        self.assertEqual(self.hypr.queries, [])
        self.assertEqual(self.hypr.calls, [])


class GameCursorTests(DaemonTestCase):
    """The pointer game mode wears, and the desktop's coming back."""

    def setUp(self):
        super().setUp()
        # Pretend the theme is already drawn: writing one is tested in
        # test_snap, and a mode switch must not depend on the filesystem.
        self.daemon._cursor_ready = "omapad-ring"
        self.session.lines = ["'Bibata-Modern-Ice'", "28"]

    def test_game_mode_swaps_the_pointer_and_desktop_mode_puts_it_back(self):
        self.daemon.set_mode("game")
        self.assertEqual(
            self.hypr.cursors, [("omapad-ring", self.config.cursor_size)]
        )
        self.daemon.set_mode("desktop")
        self.assertEqual(self.hypr.cursors[-1], ("Bibata-Modern-Ice", 28))

    def test_the_theme_is_read_off_the_desktop_at_the_moment_of_the_swap(self):
        self.assertEqual(
            self.daemon.desktop_cursor(), ("Bibata-Modern-Ice", 28)
        )

    def test_a_desktop_that_answers_nothing_still_has_a_pointer(self):
        self.session.lines = []
        theme, size = self.daemon.desktop_cursor()
        self.assertTrue(theme)
        self.assertGreater(size, 0)

    def test_the_config_can_name_what_comes_back(self):
        self.config.cursor_restore_theme = "Adwaita"
        self.config.cursor_restore_size = 24
        self.assertEqual(self.daemon.desktop_cursor(), ("Adwaita", 24))

    def test_shutting_down_in_game_mode_gives_the_pointer_back(self):
        self.daemon.set_mode("game")
        self.daemon.shutdown()
        self.assertEqual(self.hypr.cursors[-1], ("Bibata-Modern-Ice", 28))

    def test_always_wears_the_ring_on_the_desktop_too(self):
        self.config.cursor_apply = "always"
        self.daemon.apply_cursor()
        self.assertEqual(
            self.hypr.cursors, [("omapad-ring", self.config.cursor_size)]
        )
        # And a switch to game mode does not swap it a second time.
        self.daemon.set_mode("game")
        self.assertEqual(len(self.hypr.cursors), 2)

    def test_a_pointer_only_theme_inherits_the_desktop_s(self):
        seen = {}

        def fake_install(name, size, color, outline, **kwargs):
            seen.update(kwargs)
            return "/tmp/whatever"

        self.config.cursor_shapes = "pointer"
        with unittest.mock.patch.object(
            daemon_module.cursor_theme, "install", fake_install
        ):
            self.daemon.prepare_cursor()
        self.assertEqual(seen["shapes"], "pointer")
        self.assertEqual(seen["inherits"], "Bibata-Modern-Ice")

    def test_the_ring_s_proportions_reach_the_drawing(self):
        seen = {}

        def fake_install(name, size, color, outline, **kwargs):
            seen.update(kwargs)
            return "/tmp/whatever"

        self.config.cursor_thickness = 0.3
        self.config.cursor_dot = 0.0
        self.config.cursor_halo = 0.02
        with unittest.mock.patch.object(
            daemon_module.cursor_theme, "install", fake_install
        ):
            self.daemon.prepare_cursor()
        self.assertEqual(
            (seen["thickness"], seen["dot"], seen["halo"]), (0.3, 0.0, 0.02)
        )

    def test_nothing_drawn_leaves_the_pointer_alone(self):
        # Drawing that fails, not a flag poked from outside: game mode draws
        # again on the way in - the colours can be the desktop theme's, and a
        # theme changed since startup is a different pointer - so "nothing
        # drawn" has to mean the writing itself came back empty.
        with unittest.mock.patch.object(
            daemon_module.cursor_theme, "install", lambda *a, **k: None
        ):
            self.daemon.set_mode("game")
            self.assertEqual(self.hypr.cursors, [])
            self.daemon.set_mode("desktop")
            self.assertEqual(self.hypr.cursors, [])

    def test_and_the_theme_is_drawn_again_when_the_desktop_changes_its_own(self):
        """`color = "auto"` is the desktop theme's, so entering game mode has
        to ask again rather than trust what was drawn at startup."""
        drawn = []
        with unittest.mock.patch.object(
            daemon_module.cursor_theme, "install",
            lambda *a, **k: drawn.append(a[3]) or "/tmp/whatever"
        ):
            self.config.cursor_color = "auto"
            self.daemon.set_mode("game")
            self.daemon.set_mode("desktop")
            self.daemon.set_mode("game")
        self.assertEqual(len(drawn), 2)


class TraversalTests(DaemonTestCase):
    """Walking the focus with the app's own keys."""

    def chords(self):
        return [(mods, code, down) for mods, code, down in self.keyboard.chords]

    def test_a_focus_step_sends_the_configured_chord(self):
        self.config.bindings["base"]["Y"] = "focus:next"
        self.daemon.bindings.clear()
        self.press("Y")
        self.release("Y")
        tab = keymap.resolve("TAB")
        self.assertEqual(self.chords(), [((), tab, True), ((), tab, False)])

    def test_prev_carries_its_modifier(self):
        self.config.bindings["base"]["Y"] = "focus:prev"
        self.daemon.bindings.clear()
        self.press("Y")
        self.release("Y")
        shift = keymap.resolve("SHIFT")
        tab = keymap.resolve("TAB")
        self.assertEqual(
            self.chords(), [((shift,), tab, True), ((shift,), tab, False)]
        )

    def test_activate_is_space_by_default(self):
        self.assertEqual(
            self.config.traverse_keys["activate"][1], keymap.resolve("SPACE")
        )

    def test_a_step_turned_off_sends_nothing(self):
        self.config.traverse_keys.pop("back", None)
        self.assertFalse(self.daemon.focus_step("back", True))
        self.assertEqual(self.chords(), [])

    def test_a_key_that_does_not_parse_is_caught_by_check(self):
        with self.assertRaises(config_module.ConfigError):
            config_module.Config({"traverse": {"next": "NOT_A_KEY"}})

    def test_a_bad_step_does_not_parse(self):
        with self.assertRaises(actions.ActionError):
            actions.parse("focus:sideways")


class GameStickTests(DaemonTestCase):
    """What game mode does with a thumb the desktop spends on the wheel."""

    def test_game_mode_walks_the_focus_where_the_desktop_scrolls(self):
        self.assertEqual(self.config.stick_roles("base"), ("cursor", "scroll"))
        self.assertEqual(self.config.stick_roles("game"), ("cursor", "focus"))

    def test_the_pointer_is_the_pointer_wherever_you_sit(self):
        # Only the right stick changes: an empty role means "as on the desktop".
        self.assertEqual(self.config.game_left_stick, "")
        self.assertEqual(self.config.stick_roles("game")[0], "cursor")

    def test_a_held_layer_still_outranks_the_mode(self):
        self.assertEqual(self.config.stick_roles("window"), ("resize", "move"))

    def test_the_wheel_can_be_asked_for_back(self):
        cfg = config_module.Config({"mode": {"right_stick": "scroll"}})
        self.assertEqual(cfg.stick_roles("game"), ("cursor", "scroll"))

    def test_the_daemon_reads_the_role_from_the_mode_it_is_in(self):
        self.daemon.set_mode("game")
        self.assertEqual(self.daemon.stick_roles(), ("cursor", "focus"))
        self.daemon.set_mode("desktop")
        self.assertEqual(self.daemon.stick_roles(), ("cursor", "scroll"))

    def test_the_guide_names_the_role_it_walks(self):
        rows = guide_module._stick_rows(self.config, "game")
        self.assertEqual(
            [row["d"] for row in rows],
            ["Move the pointer", "Walk the focus"],
        )

    def test_the_browser_keeps_the_wheel_the_focus_stick_takes_away(self):
        """A browser scrolls what holds the focus, not what the pointer is over."""
        browser = self.config.profile_matching("chromium")
        self.assertEqual(browser["name"], "browser")
        self.assertEqual(
            self.config.stick_roles("game", browser), ("cursor", "scroll")
        )
        # And only there: the app in front is the whole question.
        self.assertEqual(self.config.stick_roles("game", None), ("cursor", "focus"))

    def test_the_terminal_keeps_the_wheel_too(self):
        """At a prompt the focus keys are Tab and the shell's history."""
        shell = self.config.profile_matching("foot")
        self.assertEqual(shell["name"], "shell")
        self.assertEqual(
            self.config.stick_roles("game", shell), ("cursor", "scroll")
        )

    def test_the_daemon_swaps_the_role_with_the_focused_window(self):
        self.daemon.set_mode("game")
        self.daemon.set_active_profile("chromium")
        self.assertEqual(self.daemon.stick_roles(), ("cursor", "scroll"))
        # A class no profile matches, so the layer's own role is what is left.
        self.daemon.set_active_profile("pretendapp")
        self.assertEqual(self.daemon.stick_roles(), ("cursor", "focus"))

    def test_a_surface_on_screen_outranks_the_app_underneath(self):
        browser = self.config.profile_matching("chromium")
        self.assertEqual(self.config.stick_roles("osk", browser), ("cursor", "scroll"))
        loud = dict(browser, left_stick="snap")
        self.assertEqual(self.config.stick_roles("osk", loud)[0], "cursor")

    def test_a_profile_that_names_no_stick_leaves_both_alone(self):
        quiet = {"name": "quiet", "match": ["foot"], "bindings": {}}
        self.assertEqual(self.config.stick_roles("game", quiet), ("cursor", "focus"))

    def test_an_unknown_role_is_named_rather_than_silently_dead(self):
        for spec in (
            {"pointer": {"right_stick": "wheel"}},
            {"mode": {"right_stick": "wheel"}},
            {"layers": {"window": {"button": "ZL", "left_stick": "wheel"}}},
            {"profile": {"browser": {"match": "chromium", "right_stick": "wheel"}}},
        ):
            with self.assertRaises(config_module.ConfigError) as caught:
                config_module.Config(spec)
            self.assertIn("wheel", str(caught.exception))


class FocusStickTests(DaemonTestCase):
    """A stick whose role is `focus`: a direction, and it repeats."""

    def setUp(self):
        super().setUp()
        self.config.left_stick = "focus"
        self.tab = keymap.resolve("TAB")

    def taps(self, code):
        return len([c for c in self.keyboard.chords if c[1] == code and c[2]])

    def hold(self, fraction, seconds, steps=1):
        self.feed((li.EV_ABS, li.ABS_X, int(32767 * fraction)))
        self.tick(seconds, steps=steps)

    def test_pushing_it_over_steps_once_straight_away(self):
        self.hold(1.0, 0.01)
        self.assertEqual(self.taps(self.tab), 1)

    def test_the_key_does_not_stay_down_between_steps(self):
        # A stick pushed over is not a key held down: an app that saw one
        # would autorepeat straight past wherever the thumb stopped.
        self.hold(1.0, 0.01)
        self.assertEqual(
            [down for _, code, down in self.keyboard.chords if code == self.tab],
            [True, False],
        )

    def test_it_waits_out_the_delay_and_then_walks(self):
        self.config.traverse_repeat_delay = 0.05
        self.config.traverse_repeat_rate = 0.02
        self.hold(1.0, 0.01)
        self.assertEqual(self.taps(self.tab), 1)
        self.tick(0.2, steps=20)
        self.assertGreater(self.taps(self.tab), 3)

    def test_a_nudge_is_not_a_direction(self):
        self.hold(0.4, 0.2, steps=10)
        self.assertEqual(self.taps(self.tab), 0)

    def test_letting_go_stops_it_and_re_arms(self):
        self.hold(1.0, 0.01)
        self.hold(0.0, 0.01)
        self.assertEqual(self.daemon._focus_held, {})
        self.hold(1.0, 0.01)
        self.assertEqual(self.taps(self.tab), 2)

    def test_turning_the_stick_steps_the_new_way_at_once(self):
        self.hold(1.0, 0.01)
        self.feed((li.EV_ABS, li.ABS_X, 0))
        self.feed((li.EV_ABS, li.ABS_Y, 32767))
        self.tick(0.01)
        self.assertEqual(self.taps(keymap.resolve("DOWN")), 1)

    def test_the_loop_keeps_ticking_while_it_is_held(self):
        self.hold(1.0, 0.01)
        self.assertTrue(self.daemon.needs_tick())

    def test_which_way_means_what_is_config(self):
        # A vertical list walked with Tab is as common as a horizontal one.
        self.config.traverse_stick = {"up": "prev", "down": "next"}
        self.feed((li.EV_ABS, li.ABS_Y, 32767))
        self.tick(0.01)
        self.assertEqual(self.taps(self.tab), 1)

    def test_a_direction_turned_off_does_nothing(self):
        self.config.traverse_stick = {"left": "prev"}
        self.hold(1.0, 0.01)
        self.assertEqual(self.taps(self.tab), 0)
        self.assertEqual(self.daemon._focus_held, {})


class BadgeStyleTests(DaemonTestCase):
    """How a badge is drawn is the daemon's answer, not the panel's."""

    def test_a_payload_says_which_style_to_draw(self):
        # The shell cannot read the config, so a surface that is never told
        # draws the shipped style for the life of the session.
        self.config.ui_badge_style = "stencil"
        self.daemon.set_menu(True)
        self.assertEqual(self.menu_client.sent[-1]["badge"], "stencil")

    def test_the_shipped_style_travels_too(self):
        # Not only the changed one: a panel started against an older daemon
        # has to be able to tell the default from a missing field.
        self.daemon.set_menu(True)
        self.assertEqual(self.menu_client.sent[-1]["badge"], "filled")

    def test_choosing_it_redraws_what_is_already_up(self):
        # Otherwise the menu row ticks and the surface behind it keeps the old
        # drawing until the heartbeat, which reads as a press that missed.
        self.daemon.set_menu(True)
        self.menu_client.sent.clear()
        self.daemon.set_setting("badge_style", ("set", "stencil"))
        self.assertTrue(self.menu_client.sent, "the menu should be redrawn")
        self.assertEqual(self.menu_client.sent[-1]["badge"], "stencil")


class BarFollowsTheSurfaceTests(DaemonTestCase):
    """A surface is a layer, and every hint on the bar belongs to one."""

    def bar(self):
        return self.gamebar_client.sent[-1]

    def in_game_mode(self):
        self.config.gamebar_enabled = True
        self.daemon.set_mode("game")

    def test_a_menu_opened_with_no_press_behind_it_repaints_the_bar(self):
        # A press repaints the bar on its way out of `handle_button`, but
        # `omapad ctl menu open` and a shell keybind have none - so without
        # this the bar answers for the desktop under the menu for two seconds.
        self.in_game_mode()
        self.daemon.set_menu(True)
        self.assertEqual([row["n"] for row in self.bar()["actions"]],
                         ["A", "B", "X"])

    def test_and_the_strip_goes_with_the_buttons_that_walked_it(self):
        # The menu owns the shoulders while it is up, so nothing steps
        # through the workspaces from inside it.
        self.in_game_mode()
        self.daemon.gamebar.set_workspaces(
            [{"id": 1, "name": "1", "windows": 1}], 1)
        self.daemon.push_gamebar_view()
        self.assertTrue(self.bar()["workspaces"], "the game layer walks them")
        self.assertIsNotNone(self.bar()["wsprev"])
        self.daemon.set_menu(True)
        self.assertEqual(self.bar()["workspaces"], [])
        self.assertIsNone(self.bar()["wsprev"])

    def test_and_closing_it_brings_them_back(self):
        # A card leaves the bar up, so the workspaces it was showing are
        # simply repainted rather than asked for again.
        self.config.menu_fullscreen = False
        self.in_game_mode()
        self.daemon.gamebar.set_workspaces(
            [{"id": 1, "name": "1", "windows": 1}], 1)
        self.daemon.set_menu(True)
        self.daemon.set_menu(False)
        self.assertTrue(self.bar()["workspaces"])


class ScrimOverTheBarTests(DaemonTestCase):
    """A surface that dims the desktop must not dim omapad's own bar."""

    def test_a_payload_says_whether_a_bar_is_holding_a_strip(self):
        # The panel cannot see the bar - it is another window in the same
        # shell - and the scrim a *card* draws would cover the row of hints
        # that says what its own face buttons do.
        self.config.gamebar_enabled = True
        self.config.menu_fullscreen = False
        self.daemon.set_mode("game")
        self.daemon.set_menu(True)
        self.assertTrue(self.menu_client.sent[-1]["bar"])

    def test_a_fullscreen_hud_takes_the_bar_away_instead(self):
        # It covers the strip and prints the same four buttons in that exact
        # band, so leaving the bar up would be two rows of words crossfading
        # in one place - which is what reads as a flicker when it opens.
        self.config.gamebar_enabled = True
        self.config.menu_fullscreen = True
        self.daemon.set_mode("game")
        self.assertTrue(self.daemon.gamebar_open)
        self.daemon.set_menu(True)
        self.assertFalse(self.daemon.gamebar_open)
        self.assertFalse(self.menu_client.sent[-1]["bar"])
        self.daemon.set_menu(False)
        self.assertTrue(self.daemon.gamebar_open)

    def test_the_bar_goes_before_the_menu_is_pushed(self):
        # Order, not just outcome: the row has to be gone by the time the
        # menu draws its own, or both are on screen for the length of a fade.
        self.config.gamebar_enabled = True
        self.config.menu_fullscreen = True
        self.daemon.set_mode("game")
        self.gamebar_client.sent.clear()
        self.menu_client.sent.clear()
        self.daemon.set_menu(True)
        self.assertFalse(self.gamebar_client.sent[-1]["open"])
        self.assertTrue(self.menu_client.sent[-1]["open"])

    def test_and_says_so_where_there_is_none(self):
        # False rather than absent: a panel that is never told keeps the last
        # answer for the life of the session, and a menu standing off a strip
        # no bar is holding ends in a band of desktop below it.
        self.daemon.set_menu(True)
        self.assertFalse(self.menu_client.sent[-1]["bar"])

    def test_leaving_game_mode_redraws_the_menu_that_stayed_up(self):
        # Desktop mode takes the bar away and leaves the menu where it is, so
        # a menu told once would keep standing off a strip nothing holds.
        self.config.gamebar_enabled = True
        self.daemon.set_mode("game")
        self.daemon.set_menu(True)
        self.menu_client.sent[:] = []
        self.daemon.set_mode("desktop")
        self.assertTrue(self.menu_client.sent, "the menu should be redrawn")
        self.assertFalse(self.menu_client.sent[-1]["bar"])


class SurfaceScaleTests(DaemonTestCase):
    """Every surface is drawn at the scale the current mode reads at."""

    def test_a_payload_carries_the_desktop_scale(self):
        self.config.ui_scale = 1.0
        self.daemon.set_menu(True)
        self.assertEqual(self.menu_client.sent[-1]["scale"], 1.0)

    def test_game_mode_draws_at_its_own_scale(self):
        self.config.ui_game_scale = 1.6
        self.daemon.set_mode("game")
        self.daemon.set_menu(True)
        self.assertEqual(self.menu_client.sent[-1]["scale"], 1.6)

    def test_a_surface_that_is_up_is_redrawn_when_the_mode_changes(self):
        # Going the other way closes the surfaces, so this is the direction
        # where a menu outlives the switch that changes how big it should be.
        self.config.ui_scale = 1.0
        self.config.ui_game_scale = 1.6
        self.daemon.set_mode("game")
        self.daemon.set_menu(True)
        self.menu_client.sent.clear()
        self.daemon.set_mode("desktop")
        self.assertTrue(self.menu_client.sent, "the menu should be redrawn")
        self.assertEqual(self.menu_client.sent[-1]["scale"], 1.0)

    def test_the_game_bar_is_scaled_too(self):
        self.config.gamebar_enabled = True
        self.config.ui_game_scale = 1.4
        self.daemon.set_mode("game")
        self.assertEqual(self.gamebar_client.sent[-1]["scale"], 1.4)


class UiScaleConfigTests(unittest.TestCase):
    def test_game_mode_is_bigger_by_default(self):
        config = shipped_config()
        self.assertEqual(config.ui_scale, 1.0)
        self.assertGreater(config.ui_game_scale, config.ui_scale)

    def test_a_scale_of_zero_is_named(self):
        for line in ("scale = 0", "game_scale = -1"):
            with tempfile.NamedTemporaryFile("w", suffix=".toml",
                                             delete=False) as f:
                f.write("[ui]\n%s\n" % line)
                path = f.name
            try:
                with self.assertRaises(config_module.ConfigError) as caught:
                    config_module.load(path)
                self.assertIn("ui.", str(caught.exception))
            finally:
                os.unlink(path)


class SettingTests(DaemonTestCase):
    """The settings the pad changes about itself, from the menu it is in."""

    def setUp(self):
        super().setUp()
        directory = tempfile.mkdtemp(prefix="omapad-settings-")
        self.addCleanup(shutil.rmtree, directory, True)
        self.settings = os.path.join(directory, "settings.toml")
        patch = unittest.mock.patch.object(
            daemon_module, "settings_path", lambda: self.settings
        )
        patch.start()
        self.addCleanup(patch.stop)

    def written(self):
        with open(self.settings) as handle:
            return handle.read()

    def pick(self, *labels):
        """Walk the shipped menu to a row and press A on it."""
        # From the root every time: a setting row leaves the menu where it
        # was, which is the point of it, and this walks from the top.
        self.daemon.set_menu(False)
        self.daemon.set_menu(True)
        def press():
            self.press("A")
            self.release("A")

        walk_menu(self.daemon, labels, press)

    def land(self, *labels):
        """Walk the shipped menu to a tile and stop on it, without pressing."""
        self.daemon.set_menu(False)
        self.daemon.set_menu(True)
        walk_menu(self.daemon, labels[:-1], lambda: (self.press("A"),
                                                     self.release("A")))
        for tile in self.daemon.menu.tiles:
            if tile["item"]["label"] == labels[-1]:
                self.daemon.menu.select_id(tile["item"]["id"])
                return tile["item"]
        raise AssertionError("no tile labelled %r" % labels[-1])

    def nudge(self, way="right"):
        """One press of the D-pad sideways, which is a hat on this profile."""
        self.feed((li.EV_ABS, li.ABS_HAT0X, 1 if way == "right" else -1))
        self.feed((li.EV_ABS, li.ABS_HAT0X, 0))

    def push(self, *labels, way="right", times=1, keep=True):
        """Take a slider, push it, and let go keeping or dropping the value.

        A commits and B puts it back, which is the face-button contract one
        control along - so what the tests below drive is the whole of how a
        control with a range is used.
        """
        self.land(*labels)
        self.press("A")
        self.release("A")
        for _ in range(times):
            self.nudge(way)
        self.press("A" if keep else "B")
        self.release("A" if keep else "B")

    def test_a_layout_row_reaches_every_surface_at_once(self):
        # A pad printed one way in the guide and another on the bar is worse
        # than one printed wrongly in both.
        self.pick("Controller", "Button labels", "PlayStation")
        self.assertEqual(self.daemon.guide.layout, "playstation")
        self.assertEqual(self.daemon.gamebar.layout, "playstation")
        self.assertEqual(self.daemon.mapper.layout, "playstation")

    def test_a_setting_row_leaves_the_menu_where_it_is(self):
        self.pick("Controller", "Button labels", "Xbox")
        self.assertTrue(self.daemon.menu_open)
        # And the row that is now in force is the ticked one.
        rows = self.menu_client.sent[-1]["items"]
        ticked = [row["l"] for row in rows if row.get("on")]
        self.assertEqual(ticked, ["Xbox"])

    def test_what_was_chosen_is_written_down_at_the_press(self):
        # Not at shutdown: a daemon that is killed must not be how you find
        # out that what you chose from the sofa was never kept.
        self.pick("Controller", "Button labels", "Xbox")
        self.assertIn('layout = "xbox"', self.written())
        again = config_module.load(
            path=os.devnull, mapping=os.devnull, layout=os.devnull,
            settings=self.settings
        )
        self.assertEqual(again.layout_name, "xbox")

    def test_the_motor_is_told_rather_than_only_the_config(self):
        # A switch now, so A flips it rather than picking one of two rows.
        self.assertTrue(self.daemon.rumble.enabled)
        self.pick("Controller", "Vibration")
        self.assertFalse(self.daemon.rumble.enabled)
        self.assertFalse(self.daemon.rumble.available)
        self.pick("Controller", "Vibration")
        self.assertTrue(self.daemon.rumble.enabled)

    def test_a_strength_lands_on_the_motor_when_it_is_let_go_of(self):
        # Not per step: the whole vocabulary is re-uploaded when a strength
        # changes, and doing that thirty times across a sweep is an ioctl
        # storm for a level nobody stopped on. The tick you feel is the one at
        # the level you kept.
        before = self.daemon.rumble.strong
        self.land("Controller", "Strength")
        self.press("A")
        self.release("A")
        self.nudge()
        self.assertGreater(self.daemon.config.rumble_strong,
                           self.daemon.config.setting("rumble_strength")
                           - self.daemon.config.rumble_strong)
        self.assertEqual(self.daemon.rumble.strong, before)
        self.press("A")
        self.release("A")
        self.assertGreater(self.daemon.rumble.strong, before)
        self.assertIn("rumble_strength", self.written())

    def test_the_two_speeds_are_reachable_from_the_pad(self):
        before = self.daemon.config.scroll_speed
        self.push("Controller", "Sticks", "Scroll")
        self.assertEqual(self.daemon.config.scroll_speed, before + 1.0)
        self.assertIn("scroll_speed", self.written())
        before = self.daemon.config.pointer_speed
        self.push("Controller", "Sticks", "Pointer", way="left")
        self.assertEqual(self.daemon.config.pointer_speed, before - 100.0)
        self.assertIn("pointer_speed", self.written())

    def test_the_first_push_of_a_direction_is_exactly_one_step(self):
        # The ramp grows with how long a direction has been held, and a
        # reversal starts it again - so the press that changes direction is
        # always worth one step, whatever the one before it had got up to.
        before = self.daemon.config.scroll_speed
        self.land("Controller", "Sticks", "Scroll")
        self.press("A")
        self.release("A")
        for _ in range(4):
            self.nudge()
        self.assertGreater(self.daemon.config.scroll_speed, before)
        walked = self.daemon.config.scroll_speed
        self.nudge("left")
        self.assertEqual(self.daemon.config.scroll_speed, walked - 1.0)

    def test_a_slider_says_where_it_is_and_how_far_along(self):
        # Stepping blind is the failure this replaces: nothing else on screen
        # said what the number was, or that it had stopped at an end. `v` is
        # normalised here so the panel never sees a minimum or a maximum, and
        # `t` is the real number in the unit it is counted in.
        self.push("Controller", "Sticks", "Scroll")
        rows = self.menu_client.sent[-1]["items"]
        scroll = [row for row in rows if row["l"] == "Scroll"][0]
        self.assertEqual(scroll["k"], "slider")
        self.assertEqual(
            scroll["t"],
            "%g notches a second" % self.daemon.config.scroll_speed)
        share = (self.daemon.config.scroll_speed - 1.0) / 39.0
        self.assertAlmostEqual(scroll["v"], round(share, 3), places=3)

    def test_b_puts_a_control_back_where_it_was(self):
        # B leaves, here as everywhere, and leaving a control you have pushed
        # too far is putting it back. A is the one that keeps it.
        before = self.daemon.config.pointer_speed
        self.push("Controller", "Sticks", "Pointer", times=3, keep=False)
        self.assertEqual(self.daemon.config.pointer_speed, before)
        self.assertIsNone(self.daemon.menu.taken)
        # And it leaves no trace: writing a shipped default into settings.toml
        # would freeze it, so the user stops receiving the one that changes
        # later. A push nobody kept must not do that.
        self.assertNotIn("pointer_speed", self.daemon.config.chosen)
        self.assertFalse(os.path.exists(self.settings))

    def test_a_control_at_its_end_says_so_once(self):
        self.daemon.config.scroll_speed = 40.0
        self.land("Controller", "Sticks", "Scroll")
        self.press("A")
        self.release("A")
        self.device.played = []
        for _ in range(3):
            self.nudge()
        edge = self.daemon.rumble.effects["edge"]
        self.assertEqual([played for played in self.device.played
                          if played == edge], [edge])

    def test_a_faster_pointer_is_felt_at_once(self):
        # Read every tick rather than at startup, so there is nothing to apply
        # - but that is a promise worth a test, since the menu is drawn over a
        # pointer that is still live under it. The *right* stick is the one
        # that still aims there: the left one walks the tiles.
        self.push("Controller", "Sticks", "Pointer")
        self.feed((li.EV_ABS, li.ABS_RX, 32767))
        self.tick(0.5, steps=25)
        moved = sum(dx for dx, _ in self.mouse.moves)
        self.assertAlmostEqual(
            moved, self.daemon.config.pointer_speed * 0.5, delta=60
        )

    def test_a_pulled_trigger_crosses_a_range_in_a_couple_of_seconds(self):
        # Thirty-eight presses to cross `pointer_speed` is a chore, not a
        # control. A pull is a rate: fully in crosses the whole range in
        # `[menu] sweep_ms`, whether or not the tile has been taken.
        self.land("Controller", "Sticks", "Pointer")
        self.daemon.config.pointer_speed = 200.0
        self.feed((li.EV_ABS, li.ABS_RZ, 255))
        self.tick(self.daemon.config.menu_sweep_ms / 1000.0, steps=30)
        self.assertEqual(self.daemon.config.pointer_speed, 4000.0)

    def test_half_a_pull_takes_twice_as_long(self):
        self.land("Controller", "Sticks", "Pointer")
        self.daemon.config.pointer_speed = 200.0
        self.feed((li.EV_ABS, li.ABS_RZ, 128))
        self.tick(self.daemon.config.menu_sweep_ms / 2000.0, steps=15)
        moved = self.daemon.config.pointer_speed - 200.0
        self.assertAlmostEqual(moved, 3800.0 * 0.25, delta=200.0)

    def test_the_two_triggers_pull_against_each_other(self):
        self.land("Controller", "Sticks", "Pointer")
        self.daemon.config.pointer_speed = 2000.0
        self.feed((li.EV_ABS, li.ABS_Z, 255), (li.EV_ABS, li.ABS_RZ, 255))
        self.tick(1.0, steps=20)
        self.assertEqual(self.daemon.config.pointer_speed, 2000.0)

    def test_a_swept_value_lands_where_a_step_could_have(self):
        # Two ways to the same set of numbers, not two sets: the sweep moves
        # in whole steps, so a trigger cannot leave a value between two the
        # D-pad can reach.
        self.land("Controller", "Sticks", "Pointer")
        self.daemon.config.pointer_speed = 200.0
        self.feed((li.EV_ABS, li.ABS_RZ, 255))
        self.tick(0.4, steps=8)
        self.assertEqual(self.daemon.config.pointer_speed % 100.0, 0.0)

    def test_a_trigger_hums_while_it_moves_and_stops_when_it_does_not(self):
        # One continuous effect rather than a tick per step: a step repeating
        # under a held control would buzz all the way down its range. The
        # texture ships off, so it is turned on here rather than assumed.
        self.config.rumble_texture = True
        self.daemon.rumble.configure(self.config)
        self.land("Controller", "Sticks", "Pointer")
        self.daemon.config.pointer_speed = 1000.0
        self.feed((li.EV_ABS, li.ABS_RZ, 255))
        self.tick(0.3, steps=6)
        self.assertIn("texture", self.daemon.rumble._held)
        self.feed((li.EV_ABS, li.ABS_RZ, 0))
        self.tick(0.5, steps=10)
        self.assertEqual(self.daemon.rumble._held, set())

    def test_a_sweep_writes_the_file_once_when_it_stops(self):
        # A slider is one decision made over a second, and writing the file
        # thirty times is thirty chances to be interrupted halfway.
        self.land("Controller", "Sticks", "Pointer")
        self.daemon.config.pointer_speed = 1000.0
        self.feed((li.EV_ABS, li.ABS_RZ, 255))
        self.tick(0.3, steps=6)
        self.assertFalse(os.path.exists(self.settings))
        self.feed((li.EV_ABS, li.ABS_RZ, 0))
        self.tick(0.5, steps=10)
        self.assertIn("pointer_speed", self.written())

    def test_a_trigger_says_nothing_over_a_tile_with_no_range(self):
        self.land("Controller", "Vibration")
        before = self.daemon.config.rumble_enabled
        self.feed((li.EV_ABS, li.ABS_RZ, 255))
        self.tick(1.0, steps=20)
        self.assertEqual(self.daemon.config.rumble_enabled, before)

    def test_a_pad_whose_triggers_are_buttons_sweeps_all_the_way_in(self):
        # No fraction to give, so down is all the way: blunter, and it works.
        self.daemon.trigger_level.clear()
        self.daemon.pressed.add("ZR")
        self.assertEqual(self.daemon.trigger_pull("ZR"), 1.0)
        self.assertEqual(self.daemon.trigger_pull("ZL"), 0.0)

    def test_a_profile_row_re_reads_the_pad_that_is_already_open(self):
        # An Xbox pad's 0x130 is A; the Nintendo profile calls it B. Nothing
        # is re-plugged, so the map has to be re-resolved underneath.
        self.assertEqual(self.daemon.buttons[0x130], "A")
        self.pick("Controller", "Profile", "Nintendo Pro")
        self.assertEqual(self.daemon.buttons[0x130], "B")
        self.assertEqual(self.daemon.pad_profile, "nintendo_pro")
        # `auto` badges follow the profile, so those move with it.
        self.assertEqual(self.daemon.guide.layout, "nintendo")

    def test_a_setting_that_changes_nothing_is_still_remembered(self):
        # Picking the value already in force is how you pin it against a
        # config file that might say something else tomorrow.
        self.pick("Controller", "Profile", "Detect it")
        self.assertIn('profile = "auto"', self.written())

    def test_a_button_can_walk_a_setting_the_menu_lists(self):
        walk = actions.parse("pad:layout=next")
        first = self.daemon.config.layout_name
        walk.press(self.daemon.ctx)
        self.assertNotEqual(self.daemon.config.layout_name, first)
        self.assertEqual(self.daemon.guide.layout,
                         self.daemon.config.badge_layout(
                             self.daemon.pad_profile))


class SocketDirectoryTests(unittest.TestCase):
    """The directory the plugin binds in is made by whoever starts first.

    The shell is usually that: Hyprland execs it the moment the compositor is
    there, while omapad.service is still starting Python. Quickshell's bind
    into a directory that is not there fails once and gives up, so the daemon
    makes the directory whatever else it does - including when the control
    socket was pointed somewhere else entirely.
    """

    def setUp(self):
        self._real_mouse = daemon_module.VirtualMouse
        self._real_keyboard = daemon_module.VirtualKeyboard
        daemon_module.VirtualMouse = lambda *a, **k: FakeMouse()
        daemon_module.VirtualKeyboard = lambda *a, **k: FakeKeyboard()
        self.runtime = tempfile.mkdtemp(prefix="omapad-runtime-")
        self.saved = os.environ.get("XDG_RUNTIME_DIR")
        os.environ["XDG_RUNTIME_DIR"] = self.runtime
        self.addCleanup(self._restore)

    def _restore(self):
        daemon_module.VirtualMouse = self._real_mouse
        daemon_module.VirtualKeyboard = self._real_keyboard
        if self.saved is None:
            os.environ.pop("XDG_RUNTIME_DIR", None)
        else:
            os.environ["XDG_RUNTIME_DIR"] = self.saved
        shutil.rmtree(self.runtime, ignore_errors=True)

    def test_the_daemon_makes_the_socket_directory(self):
        config = shipped_config()
        config.notify = False
        config.control_socket = os.path.join(
            tempfile.mkdtemp(prefix="omapad-test-"), "control.sock"
        )
        daemon_module.Daemon(config)
        self.assertTrue(os.path.isdir(os.path.join(self.runtime, "omapad")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
