"""Drive the daemon with synthetic controller events.

Everything below the uinput write is exercised: profiles, layers, analog
triggers, tap/hold, pointer integration and game mode. The uinput layer itself
is replaced by recorders, so these run without /dev/uinput.
"""

import os
import sys
import tempfile
import shutil
import unittest
import unittest.mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad import config as config_module, daemon as daemon_module
from omapad import keymap
from omapad import linux_input as li
from omapad import uinput
from omapad import actions
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
                              settings=missing)


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
        self.released = 0

    def chord(self, mods, code, pressed):
        self.chords.append((tuple(mods), code, pressed))

    def key(self, code, pressed):
        self.chords.append(((), code, pressed))

    def release_all(self):
        self.released += 1

    def close(self):
        pass


class FakeHypr:
    def __init__(self):
        self.calls = []
        self.warps = []
        self.cursors = []
        # What `j/<command>` answers with, so a snap can be posed a whole
        # desktop without one being on screen.
        self.answers = {}
        self.position = (0.0, 0.0)

    def dispatch(self, expression):
        self.calls.append(expression)
        return "ok"

    def query(self, command):
        return self.answers.get(command)

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
        self._next_effect = 0

    def supports_rumble(self):
        return self.rumble

    def upload_rumble(self, strong, weak, length_ms, effect_id=-1):
        if effect_id < 0:
            effect_id = self._next_effect
            self._next_effect += 1
        self.effects[effect_id] = (strong, weak, length_ms)
        return effect_id

    def play_effect(self, effect_id, count=1):
        self.played.append(effect_id)

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
        # Never bind the real control socket: a live daemon may own it.
        self.config.control_socket = os.path.join(
            tempfile.mkdtemp(prefix="omapad-test-"), "control.sock"
        )
        self.daemon = daemon_module.Daemon(self.config)
        self.mouse = self.daemon.mouse
        self.keyboard = self.daemon.keyboard
        self.hypr = self.daemon.hypr = FakeHypr()
        self.session = self.daemon.session = FakeSession()
        self.daemon.ctx.hypr = self.hypr
        self.daemon.ctx.session = self.session
        self.osk_client = self.daemon.osk_client = FakeViewClient()
        self.menu_client = self.daemon.menu_client = FakeViewClient()
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

    def test_a_binding_marked_rumble_ticks_the_pad(self):
        self.press("Y")
        self.release("Y")
        self.assertEqual(self.device.played, [self.daemon.rumble.effect_id])

    def test_bindings_that_are_not_marked_stay_quiet(self):
        self.press("A")
        self.release("A")
        self.assertEqual(self.device.played, [])

    def test_switching_mode_ticks_the_pad_both_ways(self):
        # The switch is the press whose result you may not be looking at, so
        # it is felt going in and coming back out.
        self.daemon.set_mode("game")
        self.daemon.set_mode("desktop")
        self.assertEqual(
            self.device.played,
            [self.daemon.rumble.effect_id] * 2,
        )

    def test_a_switch_can_be_left_silent(self):
        self.config.mode_rumble = False
        self.daemon.set_mode("game")
        self.assertEqual(self.device.played, [])

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

    def test_the_effect_is_uploaded_once_and_given_back_on_unplug(self):
        self.assertEqual(len(self.device.effects), 1)
        self.press("Y")
        self.release("Y")
        self.press("Y")
        self.release("Y")
        self.assertEqual(len(self.device.effects), 1)
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
        before = self.daemon.menu.index
        self.feed((li.EV_ABS, li.ABS_HAT0Y, 1))
        self.assertNotEqual(self.daemon.menu.index, before)

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

    def test_off_by_default_nothing_touches_the_users_bar(self):
        self.daemon.set_mode("game")
        self.assertEqual(self.bar_calls(), [])

    def test_game_mode_hides_it_and_desktop_puts_it_back(self):
        # `omarchy toggle bar <action>` acts on the *bar-off flag*, so `on`
        # hides the bar and `off` restores it - the opposite of how it reads.
        # Getting this backwards hid the bar on the desktop and showed it in
        # game mode, which is why the direction is pinned here.
        self.config.hide_bar_in_game = True
        self.daemon.set_mode("game")
        self.assertEqual(self.bar_calls(), ["omarchy toggle bar on"])
        self.daemon.set_mode("desktop")
        self.assertEqual(self.bar_calls()[-1], "omarchy toggle bar off")

    def test_shutting_down_in_game_mode_still_gives_it_back(self):
        # Otherwise a daemon that dies there leaves a desktop with no bar and
        # no obvious way to work out why.
        self.config.hide_bar_in_game = True
        self.daemon.set_mode("game")
        self.daemon.shutdown()
        self.assertEqual(self.bar_calls()[-1], "omarchy toggle bar off")

    def test_a_machine_without_omarchy_is_not_a_daemon_that_stops(self):
        self.config.hide_bar_in_game = True

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


class MenuTests(DaemonTestCase):
    def open_menu(self):
        self.daemon.set_menu(True)
        self.menu_client.sent.clear()

    def select(self, label):
        for index, item in enumerate(self.daemon.menu.items):
            if item["label"] == label:
                self.daemon.menu.index = index
                return
        raise AssertionError("no menu row labelled %r" % label)

    def drill(self, label):
        """Open a submenu, so a row inside it can be selected by name."""
        self.select(label)
        self.daemon.menu_command("press")

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
        self.feed((li.EV_ABS, li.ABS_HAT0Y, 1))
        self.assertEqual(self.daemon.menu.index, 1)
        self.assertEqual(self.menu_client.sent[-1]["sel"], 1)

    def test_holding_a_direction_walks_the_list(self):
        self.open_menu()
        self.feed((li.EV_ABS, li.ABS_HAT0Y, 1))
        self.assertTrue(self.daemon.repeats, "a held direction should repeat")
        entry = list(self.daemon.repeats.values())[0]
        self.daemon.fire_repeats(entry[1])
        self.assertEqual(self.daemon.menu.index, 2)
        self.feed((li.EV_ABS, li.ABS_HAT0Y, 0))
        self.assertEqual(self.daemon.repeats, {})

    def test_a_drills_into_a_submenu(self):
        self.open_menu()
        self.select("Audio")
        self.press("A")
        self.release("A")
        self.assertTrue(self.daemon.menu_open)
        self.assertEqual(self.daemon.menu.title, "Audio")
        self.assertEqual(self.menu_client.sent[-1]["title"], "Audio")

    def test_b_climbs_back_out_and_then_closes(self):
        self.open_menu()
        self.select("Audio")
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
        self.select("Windows")
        self.daemon.menu_command("press")
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
        # Volume is nudged, not picked: reopening the menu per step is absurd.
        self.open_menu()
        self.select("Audio")
        self.daemon.menu_command("press")
        self.select("Volume up")
        self.press("A")
        self.assertTrue(self.daemon.menu_open)
        self.assertEqual(self.daemon.menu.title, "Audio")
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

    def test_it_always_opens_at_the_root(self):
        self.open_menu()
        self.select("Audio")
        self.daemon.menu_command("press")
        self.daemon.set_menu(False)
        self.daemon.set_menu(True)
        self.assertEqual(self.daemon.menu.depth, 0)
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
        reply = self.daemon.handle_control("menu select 3")
        self.assertIn("sel=3", reply)
        self.assertEqual(self.daemon.menu.index, 3)
        self.assertEqual(self.menu_client.sent[-1]["sel"], 3)

    def test_mouse_hover_out_of_range_clamps(self):
        self.open_menu()
        self.daemon.handle_control("menu select 999")
        self.assertEqual(self.daemon.menu.index, len(self.daemon.menu.items) - 1)

    def test_mouse_hover_does_nothing_while_the_menu_is_down(self):
        self.daemon.handle_control("menu select 2")
        self.assertEqual(self.menu_client.sent, [])

    def test_mouse_hover_takes_a_bad_index_without_guessing(self):
        self.open_menu()
        self.assertIn("select nonsense",
                      self.daemon.handle_control("menu select nonsense"))
        self.assertEqual(self.daemon.menu.index, 0)

    def test_a_pointer_click_picks_the_row_it_lands_on(self):
        # The panel sends the row and the press in one go, so a click cannot
        # land on one row and pick another. The last root row is a leaf; the
        # row right in front of the fold is the whole point of having a
        # cursor.
        self.open_menu()
        self.daemon.handle_control("menu select %d"
                                   % (len(self.daemon.menu.items) - 1))
        self.daemon.handle_control("menu press")
        self.assertEqual(self.session.spawned, ["omarchy-menu toggle"])
        self.assertFalse(self.menu_client.sent[-1]["open"])


class ListedMenuTests(DaemonTestCase):
    """A row whose submenu is a command's output - the audio devices."""

    def setUp(self):
        super().setUp()
        self.daemon.set_menu(True)
        self.session.lines = [
            "* Speakers\t1\tanalog-out",
            "Television\t7\thdmi-out",
        ]

    def enter(self, *labels):
        for label in labels:
            for index, item in enumerate(self.daemon.menu.items):
                if item["label"] == label:
                    self.daemon.menu.index = index
                    break
            else:
                raise AssertionError("no menu row labelled %r" % label)
            self.daemon.menu_command("press")

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
        self.daemon.menu_command("down")
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
        for label in ("Controller", "Shortcuts"):
            for index, item in enumerate(self.daemon.menu.items):
                if item["label"] == label:
                    self.daemon.menu.index = index
                    break
            else:
                raise AssertionError("the shipped menu has no %s row" % label)
            self.press("A")
            self.release("A")
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
            config = config_module.load(path, settings=os.devnull)
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
                     layers=None):
        self.config.profiles.append(
            {
                "name": name,
                "match": [m.lower() for m in match],
                "bindings": bindings or {},
                "layers": layers or {},
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
        self.assertEqual(self.device.played, [self.daemon.rumble.effect_id])
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
        # [profile.shell] spends X on the paste and the left stick on Ctrl+L.
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

    def test_neither_face_button_is_a_click_here(self):
        # The price of the two overrides above: X was the middle click - and
        # with it the PRIMARY selection - and Y was the right click. Neither
        # is reachable from the pad in a terminal any more.
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
        self.assertEqual(self.device.played, [self.daemon.rumble.effect_id])

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
        # shell - and the scrim it draws would cover the row of hints that
        # says what its own face buttons do.
        self.config.gamebar_enabled = True
        self.daemon.set_mode("game")
        self.daemon.set_menu(True)
        self.assertTrue(self.menu_client.sent[-1]["bar"])

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
        for label in labels:
            for index, item in enumerate(self.daemon.menu.items):
                if item["label"] == label:
                    self.daemon.menu.index = index
                    break
            else:
                raise AssertionError("no %s row in %s"
                                     % (label, self.daemon.menu.title))
            self.press("A")
            self.release("A")

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
            path=os.devnull, mapping=os.devnull, settings=self.settings
        )
        self.assertEqual(again.layout_name, "xbox")

    def test_the_motor_is_told_rather_than_only_the_config(self):
        self.pick("Controller", "Vibration", "Off")
        self.assertFalse(self.daemon.rumble.enabled)
        self.assertFalse(self.daemon.rumble.available)
        self.pick("Controller", "Vibration", "On")
        self.assertTrue(self.daemon.rumble.enabled)

    def test_a_strength_step_re_uploads_the_effect_it_lives_in(self):
        before = self.daemon.rumble.strong
        self.pick("Controller", "Vibration", "Stronger")
        self.assertGreater(self.daemon.rumble.strong, before)
        self.assertIn("rumble_strength", self.written())

    def test_the_two_speeds_are_reachable_from_the_pad(self):
        before = self.daemon.config.scroll_speed
        self.pick("Controller", "Speed", "Scroll faster")
        self.assertEqual(self.daemon.config.scroll_speed, before + 1.0)
        self.assertIn("scroll_speed", self.written())
        before = self.daemon.config.pointer_speed
        self.pick("Controller", "Speed", "Pointer slower")
        self.assertEqual(self.daemon.config.pointer_speed, before - 100.0)
        self.assertIn("pointer_speed", self.written())

    def test_a_speed_row_prints_where_the_number_has_got_to(self):
        # Stepping blind is the failure here: nothing else on screen says what
        # the number is, or that it has stopped at the end of its range.
        self.pick("Controller", "Speed", "Scroll faster")
        rows = self.menu_client.sent[-1]["items"]
        # Both numbers are on the one screen, each under its own pair of rows.
        self.assertEqual(
            [row["d"] for row in rows],
            ["%g pixels a second" % self.daemon.config.pointer_speed] * 2
            + ["%g notches a second" % self.daemon.config.scroll_speed] * 2,
        )

    def test_a_faster_pointer_is_felt_at_once(self):
        # Read every tick rather than at startup, so there is nothing to apply
        # - but that is a promise worth a test, since the menu is drawn over a
        # pointer the same stick is still moving.
        self.pick("Controller", "Speed", "Pointer faster")
        self.feed((li.EV_ABS, li.ABS_X, 32767))
        self.tick(0.5, steps=25)
        moved = sum(dx for dx, _ in self.mouse.moves)
        self.assertAlmostEqual(
            moved, self.daemon.config.pointer_speed * 0.5, delta=60
        )

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
