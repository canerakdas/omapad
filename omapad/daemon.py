"""The omapad event loop."""

import errno
import json
import logging
import os
import select
import socket
import subprocess
import time

from . import actions, keymap, linux_input as li
from .actions import MappingAction
from .config import (
    DPAD_NAMES, SURFACES, mapping_path, render_settings, setting_text,
    settings_path,
)
from .control import ControlServer
from . import guide as guide_module
from . import handover
from . import kbd
from . import cursor as cursor_theme
from . import snap as snap_module
from .gamebar import GameBarModel
from .guide import GuideModel
from .mapping import MappingModel, render as render_mapping
from .menu import MenuError, MenuModel, build as build_menu
from .osk import OskModel, badge_index
from .rumble import Rumble
from . import xkb
from .viewsock import ViewClient
from .uinput import WHEEL_HI_RES_STEP, VirtualKeyboard, VirtualMouse

log = logging.getLogger("omapad")

STICK_AXES = {
    "left": (li.ABS_X, li.ABS_Y),
    "right": (li.ABS_RX, li.ABS_RY),
}
# Hold any button this long while the mapping screen is up and it lets go of
# the pad. It is the only way out that needs no working button map, which is
# the one thing the screen cannot assume it has.
MAPPING_CANCEL_HOLD = 2.5
# How far an axis has to travel from where it rests before the mapping screen
# reads it as a trigger being pulled, as a fraction of its range.
MAPPING_AXIS_ON = 0.6
MAPPING_AXIS_OFF = 0.3

# The stick roles the tick knows how to integrate; anything else - "none" - is
# a stick with nothing to do.
STICK_ROLES = ("cursor", "scroll", "resize", "move", "snap", "focus")
RECONNECT_INTERVAL = 2.0
# When nothing is deflected or held there is nothing to integrate, so the loop
# blocks on poll() this long instead of waking at the full polling rate. Any
# event from the pad returns from poll() immediately, so latency is unaffected.
IDLE_POLL_MS = 250.0
# While a surface is up its state is re-sent this often. The shell can restart
# or reload the plugin underneath us - a theme change does it - and the fresh
# panel comes up empty with no way to know what it should be drawing.
VIEW_HEARTBEAT = 2.0


def apply_curve(x, y, deadzone, exponent):
    """Radial deadzone plus a response curve, preserving direction.

    A radial (rather than per-axis) deadzone is what keeps diagonal motion from
    snapping to the axes near the center of the stick.
    """
    magnitude = (x * x + y * y) ** 0.5
    if magnitude <= deadzone:
        return 0.0, 0.0
    if magnitude > 1.0:
        x, y, magnitude = x / magnitude, y / magnitude, 1.0
    scaled = (magnitude - deadzone) / (1.0 - deadzone)
    factor = (scaled ** exponent) / magnitude
    return x * factor, y * factor


class HeldAction:
    __slots__ = ("action", "binding", "pressed_at", "hold_fired", "warned")

    def __init__(self, action, binding, pressed_at):
        self.action = action
        self.binding = binding
        self.pressed_at = pressed_at
        # A confirming hold that has announced itself and is counting down.
        self.warned = False
        self.hold_fired = False


class Daemon:
    def __init__(self, config):
        self.config = config
        self.session = actions.Session()
        self.hypr = actions.Hypr(self.session)
        self.mouse = VirtualMouse()
        self.keyboard = VirtualKeyboard()
        self.ctx = actions.Context(
            self.mouse, self.keyboard, self.hypr, self.session, self
        )
        self.device = None
        # Which controller profile the connected pad took, for the settings
        # that follow it: `auto` badges resolve through it, and a menu row has
        # to be able to say which profile is the one in force.
        self.pad_profile = None
        self.rumble = Rumble(config)
        self.mode = config.start_mode
        self.running = True

        try:
            self.control = ControlServer(config.control_socket)
        except (OSError, RuntimeError) as exc:
            # A daemon that cannot be scripted is still a working daemon.
            log.warning("control socket unavailable: %s", exc)
            self.control = None

        self.osk = OskModel(config.osk_layout,
                            overrides=config.osk_key_overrides,
                            badge_align=config.osk_badge_align)
        self.osk_client = ViewClient("osk.sock", config.osk_socket)
        self.osk_open = False
        self._osk_label_key = None
        self._osk_labels = {}
        self._osk_next_heartbeat = 0.0
        # What the focused app's keyboard page last held, and until when:
        # (profile name, expiry, entries). Dropped whenever focus moves.
        self._osk_page_cache = None

        try:
            items = build_menu(config.menu_items)
        except MenuError as exc:
            # A broken entry must not take the daemon down with it; the menu
            # comes up empty and `omapad check` names the row.
            log.error("menu: %s", exc)
            items = []
        self.menu = MenuModel(items, config.menu_title, config.menu_clock)
        self.menu_client = ViewClient("menu.sock", config.menu_socket)
        self.menu_open = False
        self._menu_next_heartbeat = 0.0

        self.guide = GuideModel(config)
        self.guide_client = ViewClient("guide.sock", config.guide_socket)
        self.guide_open = False
        self._guide_next_heartbeat = 0.0

        # The bar widget's view: not a surface anyone navigates, just what the
        # daemon knows about itself, pushed the same best-effort way.
        self.status_client = ViewClient("status.sock", config.status_socket)
        self._status_next_heartbeat = 0.0

        # Whether the app in front has opened the pad and should have it.
        # Not a mode anyone switches: there is no list of games worth keeping,
        # so the question is asked of the program itself. See handover.py.
        self.handed_over = False
        self.pad_nodes = frozenset()
        self.focus_pid = None
        self._next_handover_check = 0.0

        self.gamebar = GameBarModel(config)
        self.gamebar_client = ViewClient("gamebar.sock", config.gamebar_socket)
        self.gamebar_open = False
        self._gamebar_next_heartbeat = 0.0

        # `auto` cannot be answered before a pad connects, so this is what a
        # layout someone chose says, and the Switch's printing until then.
        self.mapper = MappingModel(layout=config.badge_layout(None))
        self.mapping_client = ViewClient("mapping.sock", config.mapping_socket)
        self.mapping_open = False
        self._mapping_next_heartbeat = 0.0
        # While the screen is up the pad is read raw, so these track the parts
        # of a press the logical map would otherwise have handled: which code
        # is down and since when (the way out), and which axes are pulled.
        self._mapping_down = None
        self._mapping_axis_hot = set()
        self.repeats = {}

        # The keyboard on the desk. Opened only while one of our surfaces is
        # up, so a panel is never something you have to find the pad to send
        # away; see kbd.py. `_keys_down` holds the actions a key is still
        # holding, so a release reaches the action that took the press even if
        # the surface has changed underneath it.
        self.keys = kbd.KeyboardWatch(config)
        self._keys_down = {}
        self._key_actions = {}          # cache: action spec -> Action

        self.axes = {code: 0.0 for pair in STICK_AXES.values() for code in pair}
        self.axis_scale = {}
        self.buttons = {}                # evdev code -> logical name
        self.trigger_axes = {}           # evdev abs code -> logical name
        self.trigger_scale = {}
        self.trigger_down = set()
        self.hat = {"x": 0, "y": 0}
        self.pressed = set()
        self.chords = []                 # (frozenset of buttons, Action)
        self.chord_buttons = set()       # every button any chord names
        self.active_chords = []          # chords whose buttons are still down
        self.active_layers = []          # layer names, most recent last
        self.held = {}                   # button -> HeldAction
        self.bindings = {}               # cache: (layer, button) -> Binding

        # The app profile currently in effect (item 09). `active_profile` is
        # the Config profile dict; `active_profile_name` its name, or None with
        # no match. Empty until the Hyprland event socket first reports focus.
        self.active_profile = None
        self.active_profile_name = None
        # The focused window itself, rather than the profile it matched:
        # most games match no profile at all.
        self.focus_class = ""
        self.focus_title = ""
        # The Hyprland focus event socket. It streams `activewindow>>class,title`
        # lines; subscribing once swaps the active profile as focus moves.
        self.hypr_ev = None
        self._hypr_ev_buf = b""
        self._next_hypr_reconnect = 0.0

        self._cursor_remainder = [0.0, 0.0]
        self._scroll_remainder = [0.0, 0.0]
        # How long the wheel has been going one way without a break, which is
        # what [scroll] ramp turns into speed.
        self._scroll_held = 0.0
        self._scroll_way = None
        self._window_remainder = {"resize": [0.0, 0.0], "move": [0.0, 0.0]}
        # A stick with the "snap" role is a flick, not an integrator: it fires
        # once when it is pushed and re-arms only after it comes back.
        self._snap_armed = {"left": True, "right": True}
        # A stick with the "focus" role: which way it is being held and when
        # it is next due to step. Unlike a snap it repeats, because walking a
        # long list one shove at a time is worse than not walking it.
        self._focus_held = {}
        self._last_window_flush = 0.0
        self._next_reconnect = 0.0
        # What the desktop's pointer was before game mode swapped it, learned
        # at the swap rather than at startup so a theme changed underneath us
        # is still what comes back.
        self._cursor_restore = None
        # The game-mode theme's name once it is on disk; None until then, and
        # a mode switch with nothing drawn leaves the pointer alone.
        self._cursor_ready = None

        # Stick calibration (see Config.recenter): the AbsInfo each axis was
        # calibrated from, and the axes still waiting for a first value to
        # calibrate on.
        self.axis_info = {}
        self.uncalibrated = set()

        for buttons, spec in config.chords:
            try:
                self.chords.append((buttons, actions.parse(spec)))
                self.chord_buttons |= buttons
            except actions.ActionError as exc:
                log.error("bad chord %s: %s", "+".join(sorted(buttons)), exc)

    # -- device ------------------------------------------------------------

    def connect(self):
        device = li.find_device(self.config.device_match)
        if device is None:
            return False
        self.attach(device)
        return True

    def attach(self, device):
        """Adopt an open device: resolve its profile and calibrate its axes."""
        self.device = device
        profile_name, self.buttons, self.trigger_axes = self.config.profile_for(
            device.name, device.vid_pid
        )
        # Which console's printing to badge with. `auto` is the profile's own,
        # so this can only be answered once there is a pad to ask about.
        self.pad_profile = profile_name
        self.apply_layout()
        self.trigger_scale.clear()
        self.trigger_down.clear()
        for code in self.trigger_axes:
            info = device.absinfo(code)
            span = max(info.maximum - info.minimum, 1) if info else 1
            self.trigger_scale[code] = (info.minimum if info else 0, span)
        log.info(
            "connected to %s (%s) at %s using the %s profile",
            device.name, device.vid_pid, device.path, profile_name,
        )
        self.uncalibrated.clear()
        for code in self.axes:
            info = device.absinfo(code)
            self.axis_info[code] = info
            self.calibrate_axis(code)
            if info is None or info.value == 0:
                # Either the driver has had no report from this axis yet - the
                # node can exist before the pad's first packet arrives - or the
                # stick really does rest at zero. Either way the first value it
                # sends is the one worth calibrating on, and in the second case
                # calibrating on it changes nothing.
                self.uncalibrated.add(code)
        # Every node this pad answers on, so "has the app opened it" covers
        # the js node a game is just as likely to reach for.
        self.pad_nodes = frozenset(handover.device_nodes(device.path))
        self.update_handover(force=True)
        self.rumble.attach(device)
        self.push_status_view()
        if self.config.notify:
            self.session.notify(
                "omapad", "%s connected - %s mode" % (device.name, self.mode)
            )

    def apply_layout(self):
        """Give every surface the same printing, and repaint what is up.

        One place asks `badge_layout`, because the answer has to be the same
        on the bar as in the guide as on the mapping screen - a pad printed
        one way in one panel and another way in the next is worse than a pad
        printed wrongly in both.
        """
        layout = self.config.badge_layout(self.pad_profile)
        self.guide.layout = layout
        self.gamebar.layout = layout
        self.mapper.layout = layout
        # Both are rebuilt when their surface opens, so this is only for the
        # one that is already up while the layout changes underneath it.
        if self.guide_open:
            self.guide.rebuild(self.available_buttons())
        if self.osk_open:
            self.refresh_osk_badges()
        self.push_open_views()

    def calibrate_axis(self, code, value=None):
        """Scale an axis around where its stick actually rests.

        The advertised centre is a claim, not a measurement. A Beitong KP20 in
        NS mode rests every axis half a range off it and then uses only that
        half - X spans -32767..0, Y spans 0..32767 - so a stick nobody is
        touching reads as a half deflection and the cursor walks into a corner,
        while a full push the other way only cancels it out.

        Centring on the resting value and taking the *nearer* advertised end as
        the half-range recovers both: rest reads 0, and each end still reaches
        full speed. A pad that rests where it claims to is untouched by this,
        since both ends are then the same distance away.
        """
        info = self.axis_info.get(code)
        if info is None:
            self.axis_scale[code] = (0.0, 1.0)
            return
        if value is None:
            value = info.value
        offset = (value - info.center) / info.half_range
        if not self.config.recenter or abs(offset) >= self.config.recenter_limit:
            # Turned off, or a stick held at connect: centring on a held stick
            # would freeze that direction, so take the pad at its word.
            self.axis_scale[code] = (info.center, info.half_range)
            return
        half = min(value - info.minimum, info.maximum - value)
        self.axis_scale[code] = (float(value), max(float(half), 1.0))
        if abs(offset) > 0.01:
            log.info(
                "axis 0x%02x rests %+.2f off centre: neutral %+d, half-range %d",
                code, offset, value, half,
            )

    def disconnect(self):
        # The screen is about a particular pad; without one there is nothing
        # to ask and nothing to save it against.
        self.set_mapping(False)
        if self.device is not None:
            log.info("controller disconnected")
            self.rumble.detach()
            self.device.close()
            self.device = None
        self.reset_state()
        self.push_status_view()

    def apply_grab(self):
        if self.device is None:
            return
        try:
            if self.wants_grab():
                self.device.grab()
            else:
                self.device.ungrab()
        except OSError as exc:
            log.warning("could not change grab state: %s", exc)

    def wants_grab(self):
        """Should the pad be ours exclusively right now?

        Any surface of ours that is up takes it, whatever else is true: a press
        answering something on screen must not also reach the game underneath -
        that is what makes a menu summonable over a running game. Otherwise the
        pad is ours unless the app in front has opened it for itself.
        """
        if (self.mapping_open or self.osk_open or self.menu_open
                or self.guide_open):
            return True
        if not self.config.grab:
            return False
        return not self.handed_over

    # -- handing the pad to whatever is in front ---------------------------

    def update_handover(self, force=False):
        """Ask whether the focused window's process has opened the pad."""
        self._next_handover_check = time.monotonic() + self.config.handover_poll
        if self.device is None:
            wanted = False
        else:
            wanted = handover.wants_pad(
                self.focus_pid,
                self.pad_nodes,
                skip_pid=os.getpid(),
                depth=self.config.handover_depth,
                siblings=self.config.handover_siblings,
            )
        if wanted == self.handed_over and not force:
            return
        self.handed_over = wanted
        log.info("pad: %s", "handed to the focused app" if wanted else "ours")
        if wanted:
            # The app in front is driving now; nothing of ours belongs on
            # screen over it, and a held binding must not stay down.
            self.set_osk(False)
            self.set_menu(False)
            self.set_guide(False)
            self.release_everything()
        self.apply_grab()
        self.apply_gamebar()
        self.push_status_view()

    def apply_gamebar(self):
        """The bar belongs to the couch, and not over an app driving itself."""
        self.set_gamebar(
            self.mode == "game"
            and self.config.gamebar_enabled
            and not self.handed_over
        )

    # -- mode --------------------------------------------------------------

    def set_mode(self, mode):
        if mode == self.mode:
            return
        self.mode = mode
        if mode == "game":
            # The pad is going back to the game; no surface of ours has any
            # business staying on screen.
            self.set_osk(False)
            self.set_menu(False)
            self.set_guide(False)
        self.release_everything()
        self.apply_grab()
        self.apply_bar()
        self.apply_cursor()
        self.apply_gamebar()
        # A surface that was up before the switch is still up, and the two
        # modes are read from different distances: redraw it at the new scale
        # instead of leaving it desk-sized on a screen across the room.
        self.push_open_views()
        self.push_status_view()
        log.info("mode: %s", mode)
        if self.config.mode_rumble:
            self.rumble.pulse()
        if self.config.notify:
            self.session.notify(
                "omapad",
                "Desktop control on" if mode == "desktop"
                else "Controller released to games",
            )

    # -- the game-mode bar -------------------------------------------------

    def gamebar_spec(self, button):
        """The binding the bar may print for a button: what actually runs.

        The same resolution the pad itself goes through, so the bar cannot
        promise something a press would not do.
        """
        return self.config.binding_with_profile(
            self.active_profile, self.current_layer, button
        )

    def set_gamebar(self, opened):
        if opened == self.gamebar_open:
            return
        self.gamebar_open = opened
        if opened:
            self.refresh_workspaces()
            # Whatever is already down: the bar has to open showing the hand
            # that is on the pad, not an empty one it corrects at the next
            # press.
            self.gamebar.pressed = sorted(self.pressed)
        self.push_gamebar_view()
        log.info("gamebar: %s", "open" if opened else "closed")

    def push_gamebar_view(self):
        self._gamebar_next_heartbeat = time.monotonic() + VIEW_HEARTBEAT
        self.gamebar_client.send(
            self.scaled(self.gamebar.view_state(
                self.gamebar_open,
                self.gamebar_spec,
                self.available_buttons(),
                self.mode,
                self.config.gamebar_omit,
            ))
        )

    def refresh_workspaces(self):
        """Ask Hyprland for the workspaces, and only while the bar is up.

        A query per workspace event would spawn hyprctl for a strip nobody is
        looking at the rest of the time, so the list is read when the bar
        opens and when one is created or destroyed; a plain switch carries the
        name it switched to, and needs no query at all.
        """
        rows, active = [], self.gamebar.active_workspace
        for command, into in (("workspaces", "list"), ("activeworkspace", "one")):
            try:
                result = subprocess.run(
                    ["hyprctl", command, "-j"],
                    env=self.session.env,
                    capture_output=True, text=True, timeout=2.0,
                )
                data = json.loads(result.stdout)
            except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
                log.debug("could not read %s: %s", command, exc)
                continue
            if into == "one" and isinstance(data, dict):
                # By id, the way Omarchy's own widget matches: a workspace can
                # be renamed, and the number is what is printed either way.
                active = data.get("id")
            elif isinstance(data, list):
                rows = [
                    {
                        "id": entry.get("id"),
                        "name": str(entry.get("name", "")),
                        "windows": entry.get("windows", 0),
                    }
                    for entry in data
                    if isinstance(entry, dict) and entry.get("id", 0) > 0
                ]
                rows.sort(key=lambda row: row["id"])
        self.gamebar.set_workspaces(rows, active)

    def apply_bar(self, restore=False):
        """Hide Omarchy's bar while the game has the pad, and put it back.

        Best-effort like everything else that leaves this process: a machine
        without Omarchy, or with the command missing, must not stop the daemon
        switching modes. `restore` forces it back on regardless of mode - the
        shutdown path, so a daemon that dies in game mode does not leave the
        user staring at a desktop with no bar.
        """
        if not self.config.hide_bar_in_game:
            return
        # The argument names the *flag*, not the bar: `omarchy toggle bar` is a
        # wrapper around `omarchy-toggle bar-off`, so `on` creates the bar-off
        # flag and hides the bar, and `off` removes it and brings it back. Read
        # the wrong way round it does exactly the opposite of what it says.
        wanted = "off" if (restore or self.mode == "desktop") else "on"
        try:
            self.session.spawn("omarchy toggle bar %s" % wanted)
        except OSError as exc:
            log.warning("could not turn the bar %s: %s", wanted, exc)

    # -- the game-mode pointer ---------------------------------------------

    def desktop_cursor(self):
        """(theme, size) of the pointer the desktop uses, so it can come back.

        Hyprland has no IPC for reading the cursor theme, so this asks where
        Hyprland itself reads it from: gsettings, which `cursor:
        sync_gsettings_theme` follows by default, with XCURSOR_* behind it.
        Asked at the swap rather than at startup, so a theme changed while the
        daemon runs is still the one restored.
        """
        theme = str(self.config.cursor_restore_theme or "").strip()
        size = self.config.cursor_restore_size
        if not theme or not size:
            lines = self.session.capture(
                "gsettings get org.gnome.desktop.interface cursor-theme; "
                "gsettings get org.gnome.desktop.interface cursor-size"
            )
            if not theme and len(lines) > 0:
                theme = lines[0].strip().strip("'\"")
            if not size and len(lines) > 1:
                try:
                    size = int(lines[1].strip())
                except ValueError:
                    size = 0
        theme = theme or os.environ.get("XCURSOR_THEME") or "Adwaita"
        if not size:
            try:
                size = int(os.environ.get("XCURSOR_SIZE") or 24)
            except ValueError:
                size = 24
        return theme, size

    def prepare_cursor(self):
        """Draw the game-mode pointer once, before the loop starts.

        Drawing it is a quarter of a second of arithmetic - nothing at startup,
        a stutter you can feel on a mode switch. A config change needs a
        restart anyway, so startup is the only moment it can change, and after
        this a switch costs one line down the compositor's socket.

        Best-effort: a home that cannot be written to costs the desktop's own
        arrow and a log line, never a daemon that will not start.
        """
        self._cursor_ready = None
        if not self.config.cursor_enabled:
            return
        name = self.config.cursor_theme
        # A theme that leaves shapes out needs somewhere for them to come from,
        # and the desktop's own theme is the only honest answer.
        inherits = ""
        if self.config.cursor_shapes == "pointer":
            inherits = self.desktop_cursor()[0]
        drawn = cursor_theme.install(
            name,
            self.config.cursor_size,
            self.config.cursor_color,
            self.config.cursor_outline,
            thickness=self.config.cursor_thickness,
            dot=self.config.cursor_dot,
            halo=self.config.cursor_halo,
            ring_opacity=self.config.cursor_ring_opacity,
            shapes=self.config.cursor_shapes,
            inherits=inherits,
        )
        if drawn is not None:
            self._cursor_ready = name

    def apply_cursor(self, restore=False):
        """Swap the pointer for the drawn one, and put the desktop's back.

        `restore` forces the desktop's back whatever mode we are in, which is
        what the shutdown path wants - a daemon that dies in game mode must not
        leave the desktop wearing a ring.
        """
        wanted = self.config.cursor_apply == "always" or self.mode == "game"
        # Drawn again on the way in rather than only at startup: the colours
        # can be the desktop theme's, and a theme changed since then is a
        # different pointer. The stamp on disk makes this a file read and a
        # string compare when nothing has moved.
        if wanted and not restore:
            self.prepare_cursor()
        if restore or not wanted or self._cursor_ready is None:
            if self._cursor_restore is None:
                return  # never swapped: nothing of ours to undo
            theme, size = self._cursor_restore
            self._cursor_restore = None
            self.hypr.set_cursor_theme(theme, size)
            log.info("cursor: back to %s at %dpx", theme, size)
            return
        if self._cursor_restore is None:
            self._cursor_restore = self.desktop_cursor()
        self.hypr.set_cursor_theme(self._cursor_ready, self.config.cursor_size)
        log.info("cursor: %s at %dpx", self._cursor_ready, self.config.cursor_size)

    def toggle_mode(self):
        self.set_mode("game" if self.mode == "desktop" else "desktop")

    # -- state -------------------------------------------------------------

    def reset_state(self):
        self.pressed.clear()
        self.gamebar.pressed = []
        self.active_chords.clear()
        self.trigger_down.clear()
        self.active_layers.clear()
        self.hat["x"] = self.hat["y"] = 0
        for code in self.axes:
            self.axes[code] = 0.0

    def release_everything(self):
        """Let go of every synthetic press, so nothing sticks down."""
        for held in list(self.held.values()):
            if held.action is None:
                continue  # tap/hold still undecided: nothing was pressed yet
            try:
                held.action.release(self.ctx)
            except OSError:
                pass
        self.held.clear()
        self.clear_holding()
        # A layer is held open by a finger, and this is the moment nothing is
        # held: leaving one open across a mode switch would answer the next
        # press from a layer whose trigger was let go while the game had it.
        self.active_layers.clear()
        self.repeats.clear()
        self.ctx.held_scrolls.clear()
        self.mouse.release_all()
        self.keyboard.release_all()
        self._cursor_remainder = [0.0, 0.0]
        self._scroll_remainder = [0.0, 0.0]
        self._scroll_held = 0.0
        self._scroll_way = None
        for key in self._window_remainder:
            self._window_remainder[key] = [0.0, 0.0]
        for stick in self._snap_armed:
            self._snap_armed[stick] = True
        self._focus_held.clear()

    def binding_for(self, layer, button):
        # The cache is keyed on layer+button and cleared out when the active
        # profile changes (which is also why it cannot hold a stale profile).
        key = (layer, button)
        if key not in self.bindings:
            spec = self.config.binding_with_profile(
                self.active_profile, layer, button
            )
            source = layer
            if layer == "game" and spec is None:
                # Game mode still reads the base layer, but the binding it
                # finds there is tagged with where it came from: allowed() lets
                # a mode: action out of it and nothing else, so the way back to
                # the desktop keeps working without the game layer having to
                # repeat it. What [bindings.game] names itself runs whole.
                spec = self.config.binding_with_profile(
                    self.active_profile, "base", button
                )
                source = "base"
            try:
                binding = (actions.Binding(spec, self.config.announced_hold)
                           if spec is not None else None)
                if binding is not None:
                    binding.layer = source
                    if binding.reaches_past is None:
                        # The layer it was actually found in decides, not the
                        # one that was asked for: a game-mode button that fell
                        # through to base takes base's answer. A layer that
                        # says nothing leaves the binding undecided, which is
                        # not the same as `false` - see `allowed()`.
                        found = self.config.layer(source)
                        if found is not None and found.reaches_past:
                            binding.reaches_past = True
                self.bindings[key] = binding
            except actions.ActionError as exc:
                log.error("bad binding %s.%s: %s", layer, button, exc)
                self.bindings[key] = None
        return self.bindings[key]

    # The layers that are ours rather than the game's: a surface drawn on
    # screen reads the pad even in game mode, because it was opened on purpose
    # and nothing else is looking at those buttons while it is up.
    SURFACE_LAYERS = ("guide", "menu", "osk")

    @property
    def current_layer(self):
        if self.active_layers:
            return self.active_layers[-1]
        # The guide, the menu and the keyboard own the face buttons and the
        # D-pad while they are up; a held modifier still wins, so window
        # controls stay reachable. Each sits on top of the one it can be
        # opened over, so the surface you are looking at is the one that reads
        # the pad - and that holds in game mode too, where the menu can be
        # opened from [bindings.game]. A menu whose D-pad does nothing is a
        # menu you can open and not use.
        if self.guide_open:
            return "guide"
        if self.menu_open:
            return "menu"
        if self.osk_open:
            return "osk"
        # The couch layer, which falls through to base for everything it does
        # not override - game mode is the desktop with a bar on it.
        if self.mode == "game":
            return "game"
        return "base"

    # -- app profiles ------------------------------------------------------

    def _hypr_event_path(self):
        """Path of the live Hyprland event socket, or None."""
        path = self.session.hypr_socket()
        if path is None:
            return None
        return os.path.join(os.path.dirname(path), ".socket2.sock")

    def _connect_hypr_events(self):
        """Subscribe to Hyprland's event socket, if the session exposes one.

        Non-blocking, because the daemon drives it through the poll loop. The
        socket streams the compositor's current focus shortly after connecting,
        so the first `activewindow` line also sets the profile the daemon
        starts with.
        """
        path = self._hypr_event_path()
        if path is None or not os.path.exists(path):
            return False
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(path)
            sock.setblocking(False)
        except OSError as exc:
            log.warning("hypr event socket unavailable: %s", exc)
            sock.close()
            return False
        self.hypr_ev = sock
        log.debug("subscribed to Hyprland events at %s", path)
        # Connecting streams nothing on its own: socket2 only pushes events as
        # they happen, so a fresh or reconnected stream needs the current
        # window queried once before it can trust the live `activewindow` lines.
        self.seed_active_window()
        return True

    def seed_active_window(self):
        """Ask Hyprland which window is focused, to seed the profile.

        Called once on connect and again on reconnect, because subscribing to
        the event socket does not replay the current state.
        """
        try:
            result = subprocess.run(
                ["hyprctl", "activewindow", "-j"],
                env=self.session.env,
                capture_output=True,
                text=True,
                timeout=2.0,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            log.debug("could not seed the active window: %s", exc)
            return
        try:
            info = json.loads(result.stdout)
        except ValueError:
            return
        if not isinstance(info, dict):
            return
        self.focus_pid = info.get("pid") or None
        self.update_handover()
        if info.get("class"):
            self.set_focus(
                str(info["class"]).strip(),
                str(info.get("title") or "").strip(),
            )

    def _drain_hypr_events(self):
        """Read the Hyprland event stream. False means the socket died."""
        try:
            chunk = self.hypr_ev.recv(65536)
        except socket.timeout:
            return True
        except BlockingIOError:
            return True
        except OSError:
            return False
        if not chunk:
            return False
        self._hypr_ev_buf = self._hypr_ev_buf + chunk
        if b"\n" not in self._hypr_ev_buf:
            return True
        ready, _, self._hypr_ev_buf = self._hypr_ev_buf.rpartition(b"\n")
        for line in ready.split(b"\n"):
            text = line.decode("utf-8", "replace")
            if text.startswith("activewindow>>"):
                payload = text[len("activewindow>>"):]
                cls, _, title = payload.partition(",")
                self.set_focus(cls.strip(), title.strip())
                # The event carries no pid, and who owns the pad is a question
                # about the process rather than the class.
                self.seed_active_window()
            elif self.gamebar_open:
                self.handle_workspace_event(text)
        return True

    def handle_workspace_event(self, text):
        """Keep the bar's workspace strip current, while it is on screen."""
        verb, _, payload = text.partition(">>")
        if verb == "workspacev2":
            # `workspacev2>>id,name` - the id is what the strip matches on.
            try:
                self.gamebar.active_workspace = int(payload.split(",")[0])
            except (TypeError, ValueError):
                return
        elif verb == "workspace":
            # The v1 event carries the name alone, so the id has to be looked
            # up; a workspace we have never seen means the list is stale.
            name = payload.strip()
            for row in self.gamebar.workspaces:
                if row["name"] == name:
                    self.gamebar.active_workspace = row["id"]
                    break
            else:
                self.refresh_workspaces()
        elif verb.startswith("createworkspace") or verb.startswith("destroyworkspace"):
            self.refresh_workspaces()
        else:
            return
        self.push_gamebar_view()

    def set_focus(self, window_class, title):
        """Remember what is in front, and swap the profile that follows it."""
        self.focus_class = window_class
        self.focus_title = title
        self.set_active_profile(window_class)

    def set_active_profile(self, window_class):
        """Swap the active app profile for the focused window's class."""
        profile = self.config.profile_matching(window_class)
        name = profile["name"] if profile else None
        previous = self.active_profile_name
        if name == previous:
            return
        self.active_profile = profile
        self.active_profile_name = name
        # The resolved bindings cache exists per (layer, button); with a new
        # profile the profile half of every answer is stale, so it all goes.
        self.bindings.clear()
        # The keyboard's app page is rebuilt when the keyboard is opened, not
        # here: a focus change is not worth spawning a shell for, and the page
        # cannot be read while it is down anyway.
        self._osk_page_cache = None
        log.info("profile: %s -> %s", previous, name)
        self.push_status_view()
        if self.gamebar_open:
            # The hints are the focused window's, so they change with it.
            self.push_gamebar_view()

    # -- on-screen keyboard ------------------------------------------------

    def refresh_osk_labels(self):
        """Follow the compositor's layout, so the printed keys tell the truth.

        Asking Hyprland which layout is live is cheap; compiling it is not, so
        the compiled table is kept until the layout actually changes.
        """
        if not self.config.osk_labels_follow_layout:
            return
        try:
            key = xkb.active_layout()
        except Exception as exc:  # a keyboard with no labels still types
            log.warning("could not read the active layout: %s", exc)
            return
        if key != self._osk_label_key:
            self._osk_label_key = key
            self._osk_labels = xkb.compile_labels(*key)
            log.info("keyboard labels follow layout %s", key[0] or "unknown")
        self.osk.set_labels(self._osk_labels)

    def refresh_osk_badges(self):
        """Which pad button reaches each key, for the badges beside them.

        Worked out on the way in rather than once at startup: which buttons
        exist is the connected pad's answer, and what one prints is its
        layout's - both change when a pad is swapped between NS and XInput
        mode while we run.
        """
        if not self.config.osk_badges:
            self.osk.set_badges({})
            return
        index = badge_index(
            self.config.bindings.get("osk", {}), self.available_buttons()
        )
        self.osk.set_badges(dict(
            (identity, {
                "b": guide_module.badge_of(button, self.guide.layout),
                "k": guide_module.KINDS.get(button, "system"),
            })
            for identity, button in index.items()
        ))

    def osk_app_entries(self, page):
        """What the focused app's page should hold, freshly enough.

        Kept for the page's own ttl: opening the keyboard twice to type two
        commands should not re-read a history file that nothing has written to
        in between, and the command runs on the event loop.
        """
        now = time.monotonic()
        cached = self._osk_page_cache
        if cached and cached[0] == self.active_profile_name and now < cached[1]:
            return cached[2]
        entries = list(page["keys"])
        if page["from"]:
            entries += [
                {"label": line, "text": line}
                for line in self.session.capture(page["from"])
            ]
        entries = entries[: page["limit"]]
        self._osk_page_cache = (
            self.active_profile_name, now + page["ttl"], entries
        )
        return entries

    def refresh_osk_app_page(self):
        """Give the keyboard the page the app in front lends it, if it has one."""
        page = (self.active_profile or {}).get("osk")
        if not page:
            self.osk.clear_app_page()
            return
        self.osk.set_app_page(page["label"], self.osk_app_entries(page))

    # -- the surfaces as one thing -----------------------------------------

    def surface_top(self):
        """Which surface of ours is on screen, or None.

        In the order they outrank one another, the same order surface_override()
        walks. Opening any of them closes the ones below, so at most one is
        really up; asking in a fixed order means there is still one answer if
        that ever stops being true.
        """
        opened = {
            "map": self.mapping_open,
            "guide": self.guide_open,
            "menu": self.menu_open,
            "osk": self.osk_open,
        }
        for name in SURFACES:
            if opened[name]:
                return name
        return None

    def set_surface(self, name, opened):
        setter = {
            "map": self.set_mapping,
            "guide": self.set_guide,
            "menu": self.set_menu,
            "osk": self.set_osk,
        }.get(name)
        if setter is not None:
            setter(opened)

    def surface_command(self, command):
        """Act on whatever is on top, for a key that cannot know what that is."""
        if command == "close_all":
            for name in SURFACES:
                self.set_surface(name, False)
            return
        top = self.surface_top()
        if top is None:
            return
        if command == "back":
            # Only two surfaces have anywhere to go back to, and both already
            # treat "back" at the top as the way out.
            if top == "menu":
                self.menu_command("back")
                return
            if top == "map":
                self.mapping_command("back")
                return
        self.set_surface(top, False)

    # -- the keyboard on the desk ------------------------------------------

    def drain_keys(self, fd):
        for etype, code, value in self.keys.read(fd):
            if etype == li.EV_KEY:
                self.key_event(code, value)

    def key_event(self, code, value):
        """One key from a real keyboard, while a surface of ours is up."""
        action = self._keys_down.get(code)
        if not value:
            if action is not None:
                del self._keys_down[code]
                action.release(self.ctx)
            return
        if action is None:
            surface = self.surface_top()
            if surface is None:
                # The surface went away between the press and this drain. A
                # key means something only while one is on screen: that is
                # what keeps this from being a global hotkey daemon.
                return
            spec = self.config.keyboard_binding_for(surface, code)
            if spec is None:
                return
            action = self._key_actions.get(spec)
            if action is None:
                try:
                    action = actions.parse(spec)
                except actions.ActionError as exc:
                    log.error("bad keyboard binding %r: %s", spec, exc)
                    return
                self._key_actions[spec] = action
            self._keys_down[code] = action
        # value 2 is the kernel's own auto-repeat, which is what lets a held
        # arrow walk a list; an action that holds something just sees the
        # press it already had.
        action.press(self.ctx)

    def release_keys(self):
        """Let go of whatever a key was holding when we stopped listening."""
        for action in self._keys_down.values():
            action.release(self.ctx)
        self._keys_down = {}

    def set_osk(self, opened):
        if opened == self.osk_open:
            return
        self.osk_open = opened
        if opened:
            self.refresh_osk_labels()
            self.refresh_osk_badges()
            self.refresh_osk_app_page()
        else:
            # Including whatever a trigger was holding: the button's release
            # will not be routed here once the keyboard is down.
            self.osk.reset_mods()
        self.push_osk_view()
        self.apply_grab()
        log.info("osk: %s", "open" if opened else "closed")

    def view_scale(self):
        """How big the surfaces draw right now.

        Stamped on every payload rather than read from config by the plugin:
        the mode lives here, the plugin has no idea which one is on, and the
        scale has to change with it on the same line that changes everything
        else about the surface.
        """
        if self.mode == "game":
            return self.config.ui_game_scale
        return self.config.ui_scale

    def scaled(self, state):
        """One surface payload, stamped with how it should be drawn.

        Both of these are settings the panel cannot read for itself, and both
        are answers every surface needs, so they are stamped in one place
        rather than remembered by six callers.
        """
        if isinstance(state, dict):
            state["scale"] = self.view_scale()
            state["badge"] = self.config.ui_badge_style
        return state

    def push_osk_view(self):
        self._osk_next_heartbeat = time.monotonic() + VIEW_HEARTBEAT
        self.osk_client.send(self.scaled(self.osk.view_state(self.osk_open)))

    def type_text(self, text):
        """Type a whole string, character by character.

        Whichever key the active layout puts a character on is the model's
        answer, not this one's - the same table the printed labels come from.
        """
        for mods, code in self.osk.text_chords(text):
            self.keyboard.chord(mods, code, True)
            self.keyboard.chord(mods, code, False)

    def osk_hold(self, name, down):
        """A modifier held on the pad for as long as the button is down."""
        if not self.osk_open:
            return
        self.osk.hold(name, down)
        self.push_osk_view()

    def osk_command(self, command):
        if command == "toggle":
            self.set_osk(not self.osk_open)
            return
        if command == "open":
            self.set_osk(True)
            return
        if command == "close":
            self.set_osk(False)
            return
        if not self.osk_open:
            return  # navigation means nothing while the keyboard is down

        model = self.osk
        if command == "up":
            model.move_vertical(-1)
        elif command == "down":
            model.move_vertical(1)
        elif command == "left":
            model.move_horizontal(-1)
        elif command == "right":
            model.move_horizontal(1)
        elif command in ("shift", "ctrl", "alt"):
            model.latch(command)
        elif command.startswith("layer:"):
            name = command[6:]
            if name == "next":
                model.cycle_layer(1)
            elif name == "prev":
                model.cycle_layer(-1)
            else:
                model.set_layer(name)
        elif command == "caps":
            # Through the model so the printed letters follow the state, and
            # with whatever chord the Caps key itself sends - one source of
            # truth for a layout that has Caps Lock somewhere unusual.
            chord = model.toggle_caps()
            if chord:
                mods, code = chord
                self.keyboard.chord(mods, code, True)
                self.keyboard.chord(mods, code, False)
        elif command == "submit":
            # Enter and away: the keyboard's "done". Latched or held modifiers
            # ride along, so Shift+Enter still reaches a chat box.
            mods = model.modifier_codes()
            code = keymap.resolve("ENTER")
            self.keyboard.chord(mods, code, True)
            self.keyboard.chord(mods, code, False)
            self.set_osk(False)
            return
        elif command == "press":
            result = model.press()
            if result[0] == "type":
                _, mods, code = result
                self.keyboard.chord(mods, code, True)
                self.keyboard.chord(mods, code, False)
            elif result[0] == "text":
                self.type_text(result[1])
            elif result[0] == "close":
                self.set_osk(False)
                return
        self.push_osk_view()

    # -- menu --------------------------------------------------------------

    def set_menu(self, opened):
        if opened == self.menu_open:
            return
        self.menu_open = opened
        if opened:
            # A menu always opens at its root: coming back to where you left
            # off is right inside one session of pointing at rows, and wrong
            # the next time you summon it.
            self.menu.reset()
            # Both surfaces read the D-pad, and stacking the menu over the
            # keyboard leaves no way to tell which one a press belongs to.
            self.set_osk(False)
        self.push_menu_view()
        self.apply_grab()
        log.info("menu: %s", "open" if opened else "closed")

    def push_menu_view(self):
        self._menu_next_heartbeat = time.monotonic() + VIEW_HEARTBEAT
        self.menu_client.send(self.scaled(
            self.menu.view_state(
                self.menu_open, self.action_state, self.action_value
            )
        ))

    def menu_command(self, command):
        """Drive the menu. True when holding the button should keep firing."""
        if command == "toggle":
            self.set_menu(not self.menu_open)
            return False
        if command == "open":
            self.set_menu(True)
            return False
        if command == "close":
            self.set_menu(False)
            return False
        if not self.menu_open:
            return False  # navigation means nothing while the menu is down

        model = self.menu
        held = False
        if command == "up":
            model.move(-1)
            held = True
        elif command == "down":
            model.move(1)
            held = True
        elif command in ("back", "left"):
            # Back at the root level is the way out, the way Esc is in the
            # Omarchy menu.
            if not model.back():
                self.set_menu(False)
                return False
        elif command in ("press", "right"):
            kind, item = model.press()
            if kind == "run" and item["repeat"]:
                # A row you nudge rather than pick - volume, brightness. The
                # menu stays where it is and the button keeps firing, the way
                # a held volume key does; picking it once per step would mean
                # summoning the menu once per step.
                self.fire_once(item["action"], "menu")
                held = True
            elif kind == "run" and item["stay"]:
                # A row that changes something the menu itself prints - which
                # badge layout is in force, whether the motor is on. Picking
                # one and being thrown back to the desktop to see what it did
                # is how you end up opening the menu once per thing you try.
                self.fire_once(item["action"], "menu")
            elif kind == "run":
                # Otherwise the menu goes away before the entry fires: whatever
                # it opens should not come up behind a scrim, and a command that
                # takes a moment should not leave the menu looking stuck.
                self.set_menu(False)
                # Tagged with the menu, so game mode lets it run: the menu can
                # be opened from [bindings.game], and a row that closes the
                # menu and then does nothing is worse than no menu at all.
                self.fire_once(item["action"], "menu")
                return False
        self.push_menu_view()
        return held

    # -- bindings guide ----------------------------------------------------

    def available_buttons(self):
        """Every logical name the connected pad actually has.

        None while nothing is plugged in: with no pad to be wrong about, the
        whole config is worth showing.
        """
        if self.device is None:
            return None
        names = set(self.buttons.values())
        names.update(self.trigger_axes.values())
        names.update(DPAD_NAMES.values())
        return names

    def set_guide(self, opened):
        if opened == self.guide_open:
            return
        self.guide_open = opened
        if opened:
            # Rebuilt on the way in rather than once at startup: which buttons
            # exist depends on the profile of whatever is plugged in now, and
            # a pad can be swapped between NS and XInput mode while we run.
            self.guide.rebuild(self.available_buttons())
            self.guide.reset()
            # Only one surface may read the D-pad, and the guide is the one
            # being looked at.
            self.set_menu(False)
            self.set_osk(False)
        self.push_guide_view()
        self.apply_grab()
        log.info("guide: %s", "open" if opened else "closed")

    def push_guide_view(self):
        self._guide_next_heartbeat = time.monotonic() + VIEW_HEARTBEAT
        self.guide_client.send(self.scaled(self.guide.view_state(self.guide_open)))

    def guide_command(self, command):
        if command == "toggle":
            self.set_guide(not self.guide_open)
            return
        if command == "open":
            self.set_guide(True)
            return
        if command == "close":
            self.set_guide(False)
            return
        if not self.guide_open:
            return  # turning a page means nothing while the guide is down
        if command == "next":
            self.guide.move(1)
        elif command == "prev":
            self.guide.move(-1)
        self.push_guide_view()

    # -- the settings the pad can change -----------------------------------

    def set_setting(self, name, request):
        """Apply one `pad:` setting and write it down.

        Written to settings.toml on every press rather than at shutdown: a
        daemon that is killed - or a machine that goes down - must not be how
        you find out that what you chose from the sofa was never kept.
        """
        try:
            before = self.config.setting(name)
            value = self.config.set_setting(name, request)
        except (KeyError, ValueError) as exc:
            # Parsed when the binding was read, so this is a setting that has
            # gone away under a config someone edited - not worth a traceback.
            log.warning("setting: %s: %s", name, exc)
            return
        if value != before:
            log.info("setting: %s %r -> %r", name, before, value)
            self.apply_setting(name)
        self.save_settings()
        if self.config.notify:
            self.session.notify(
                "omapad",
                "%s: %s" % (guide_module.PAD_NAMES.get(name, name),
                            self.setting_words(name, value)),
            )
        if self.menu_open:
            # The tick moves to the row that was just picked.
            self.push_menu_view()

    def setting_words(self, name, value):
        """What a setting now holds, in the words the menu prints.

        The number settings each carry their own unit - a speed is not a
        percentage of anything - so they answer for themselves; what is left
        here is the switch and the choice.
        """
        text = setting_text(name, value)
        if text:
            return text
        if isinstance(value, bool):
            return "on" if value else "off"
        return str(value)

    def apply_setting(self, name):
        """Make a changed setting true of the daemon that is already running.

        Every one of these is something the config decides at startup, so a
        setting reachable from the pad is only half a setting until the thing
        it configures is told again.
        """
        if name == "profile":
            if self.device is not None:
                self.reapply_profile()
            self.apply_layout()
        elif name == "layout":
            self.apply_layout()
        elif name == "badge_style":
            # The other thing that is true of every surface at once. Without
            # this it waits out the heartbeat, and a menu row that ticks a
            # second before the bar behind it changes reads as a press that
            # did not take.
            self.push_open_views()
        elif name in ("rumble", "rumble_strength"):
            # The effect is uploaded once per connection, so a strength that
            # changed only reaches the motor by replacing it.
            self.rumble.configure(self.config)
            self.rumble.pulse()

    def save_settings(self):
        path = settings_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            # Written whole and moved into place, the way the mapping is: a
            # half-written file here is one the daemon will not boot on.
            temporary = path + ".new"
            with open(temporary, "w") as handle:
                handle.write(render_settings(self.config.chosen))
            os.replace(temporary, path)
        except OSError as exc:
            # The setting is already in force; only remembering it failed.
            log.error("setting: could not write %s: %s", path, exc)

    def action_state(self, action):
        """Whether an action's answer is already the case. See menu.view_state."""
        try:
            return action.state(self.ctx)
        except Exception as exc:  # a menu that cannot be drawn is worse
            log.debug("state: %s", exc)
            return None

    def action_value(self, action):
        """What the setting an action steps is on now. See menu.view_state."""
        try:
            return action.value(self.ctx)
        except Exception as exc:  # as above: a row with no number still draws
            log.debug("value: %s", exc)
            return ""

    # -- controller mapping ------------------------------------------------

    def set_mapping(self, opened):
        if opened == self.mapping_open:
            return
        self.mapping_open = opened
        if opened:
            # Every other surface goes away: this one reads the pad raw, so
            # nothing else can be listening to the same buttons.
            self.set_guide(False)
            self.set_menu(False)
            self.set_osk(False)
            self.release_everything()
            identity = self.device.vid_pid if self.device else ""
            name = self.device.name if self.device else ""
            self.mapper.start(identity, name)
        self._mapping_down = None
        self._mapping_axis_hot = set()
        self.apply_grab()
        self.push_mapping_view()
        log.info("mapping: %s", "open" if opened else "closed")

    def status_state(self):
        """What the bar widget draws: what omapad is doing, in one line."""
        return {
            "mode": self.mode,
            "connected": self.device is not None,
            "pad": self.device.name.strip() if self.device else "",
            "profile": self.active_profile_name or "",
            "handed_over": self.handed_over,
        }

    def push_open_views(self):
        """Redraw whatever is on screen, without waiting for the heartbeat.

        For the things that are true of every surface at once - the scale the
        mode asks for, the style its badges are drawn in - rather than for one
        surface's own state, which pushes itself.
        """
        if self.osk_open:
            self.push_osk_view()
        if self.menu_open:
            self.push_menu_view()
        if self.guide_open:
            self.push_guide_view()
        if self.mapping_open:
            self.push_mapping_view()
        if self.gamebar_open:
            self.push_gamebar_view()

    def push_status_view(self):
        self._status_next_heartbeat = time.monotonic() + VIEW_HEARTBEAT
        self.status_client.send(self.status_state())

    def push_mapping_view(self):
        self._mapping_next_heartbeat = time.monotonic() + VIEW_HEARTBEAT
        self.mapping_client.send(self.scaled(self.mapper.view_state(self.mapping_open)))

    def mapping_command(self, command):
        if command == "toggle":
            self.set_mapping(not self.mapping_open)
            return
        if command == "open":
            self.set_mapping(True)
            return
        if command in ("close", "cancel"):
            self.set_mapping(False)
            return
        if not self.mapping_open:
            return  # nothing to walk while the screen is down
        if command == "skip":
            self.mapper.skip()
        elif command == "back":
            self.mapper.back()
        elif command == "restart":
            self.mapper.restart()
        elif command == "save":
            self.save_mapping()
            return
        self.push_mapping_view()

    def mapping_press(self, kind, code):
        """One raw press, while the screen is up. Nothing else sees it."""
        result = self.mapper.learn(kind, code)
        if result == "save":
            self.save_mapping()
            return
        if result == "discard":
            self.set_mapping(False)
            return
        if result in ("learned", "skipped"):
            self.rumble.pulse()
        self.push_mapping_view()

    def save_mapping(self):
        """Write what was measured, and put it to work without a restart."""
        identity = (self.mapper.identity or "").strip().upper()
        if not identity:
            log.warning("mapping: no device to save it against")
            self.set_mapping(False)
            return
        entry = {
            "name": self.mapper.pad_name,
            "buttons": self.mapper.buttons(),
            "triggers": self.mapper.triggers(),
        }
        self.config.pad_mappings[identity] = entry
        path = mapping_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            # Written whole and moved into place, so a crash halfway through
            # cannot leave a half-parsed mapping that stops the daemon booting.
            temporary = path + ".new"
            with open(temporary, "w") as handle:
                handle.write(render_mapping(self.config.pad_mappings))
            os.replace(temporary, path)
        except OSError as exc:
            log.error("mapping: could not write %s: %s", path, exc)
            self.session.notify("omapad", "Could not save the mapping")
            self.set_mapping(False)
            return
        log.info("mapping: saved %d buttons for %s to %s",
                 len(entry["buttons"]), identity, path)
        # The device is already open; re-resolving is all it takes for the new
        # names to be the ones the next press arrives under.
        if self.device is not None:
            self.reapply_profile()
        self.set_mapping(False)
        if self.config.notify:
            self.session.notify("omapad", "Controller mapping saved")

    def reapply_profile(self):
        """Re-read the button map for the device already attached."""
        self.pad_profile, self.buttons, self.trigger_axes = self.config.profile_for(
            self.device.name, self.device.vid_pid
        )
        self.trigger_scale.clear()
        self.trigger_down.clear()
        for code in self.trigger_axes:
            info = self.device.absinfo(code)
            span = max(info.maximum - info.minimum, 1) if info else 1
            self.trigger_scale[code] = (info.minimum if info else 0, span)
        # Bindings are cached per layer and button, and which physical button
        # carries which name just changed underneath them. Chords are named in
        # logical names too, but they are parsed from those names rather than
        # resolved through the map, so they need nothing.
        self.bindings.clear()

    def handle_control(self, request):
        """Answer one control-socket command."""
        parts = request.split()
        if not parts:
            return (
                "usage: osk <toggle|open|close> | menu <toggle|open|close> "
                "| guide <toggle|open|close|next|prev> "
                "| map <toggle|open|close|skip|back|restart|save|cancel> "
                "| surface <close|close_all|back> "
                "| pad <setting>=<value> "
                "| press <BUTTON> [tap|hold] "
                "| mode <toggle|desktop|game> | status"
            )
        verb, args = parts[0], parts[1:]
        if verb == "ping":
            return "ok"
        if verb == "status":
            return (
                "mode=%s pad=%s osk=%s menu=%s guide=%s map=%s "
                "layer=%s device=%s"
                % (
                    self.mode,
                    "app" if self.handed_over else "ours",
                    "open" if self.osk_open else "closed",
                    "open" if self.menu_open else "closed",
                    "open" if self.guide_open else "closed",
                    "open" if self.mapping_open else "closed",
                    self.current_layer,
                    self.device.name if self.device else "none",
                )
            )
        if verb == "osk" and args:
            # Every osk: action a binding can take is reachable here too, so the
            # keyboard can be scripted and inspected without the pad.
            from .actions import OskAction

            command = args[0]
            if command in OskAction.HOLD:
                # There is no button to let go of here, so which way the
                # modifier goes has to be said out loud: "hold:shift off".
                self.osk_hold(command[5:], args[1:2] != ["off"])
            elif command in OskAction.SIMPLE or command.startswith("layer:"):
                self.osk_command(command)
            else:
                return "unknown osk command: %s" % command
            return "osk=%s layer=%s sel=%d,%d" % (
                "open" if self.osk_open else "closed",
                self.osk.layer, self.osk.row, self.osk.col,
            )
        if verb == "menu" and args:
            from .actions import MenuAction

            command = args[0]
            if command in MenuAction.SIMPLE:
                self.menu_command(command)
                return "menu=%s title=%s sel=%d" % (
                    "open" if self.menu_open else "closed",
                    self.menu.title, self.menu.index,
                )
            return "unknown menu command: %s" % command
        if verb == "map" and args:
            command = args[0]
            if command in MappingAction.SIMPLE:
                self.mapping_command(command)
                step = self.mapper.step
                return "map=%s step=%s %d/%d learned=%d" % (
                    "open" if self.mapping_open else "closed",
                    step or ("confirm" if self.mapper.done else "-"),
                    min(self.mapper.index + 1, len(self.mapper.steps)),
                    len(self.mapper.steps),
                    len(self.mapper.learned),
                )
            return "unknown map command: %s" % command
        if verb == "pad" and args:
            # The settings the pad can change about itself, without one: the
            # same grammar a binding writes, so `pad:layout=xbox` and
            # `omapad ctl pad layout=xbox` are one mechanism.
            from . import config as config_module

            name, separator, raw = args[0].partition("=")
            if not separator:
                return "usage: pad <setting>=<value>, as pad layout=xbox"
            name = name.strip().lower()
            try:
                request = config_module.setting_request(name, raw)
            except config_module.SettingError as exc:
                return str(exc)
            self.set_setting(name, request)
            return "pad %s=%s" % (
                name, self.setting_words(name, self.config.setting(name)))
        if verb == "guide" and args:
            from .actions import GuideAction

            command = args[0]
            if command in GuideAction.SIMPLE:
                self.guide_command(command)
                return "guide=%s page=%d/%d title=%s" % (
                    "open" if self.guide_open else "closed",
                    self.guide.index + 1, len(self.guide.pages),
                    self.guide.title,
                )
            return "unknown guide command: %s" % command
        if verb == "surface" and args:
            from .actions import SurfaceAction

            command = args[0]
            if command not in SurfaceAction.SIMPLE:
                return "unknown surface command: %s" % command
            self.surface_command(command)
            return "surface=%s" % (self.surface_top() or "none")
        if verb == "press" and args:
            # Where a click on the game bar lands, and a second door onto the
            # pad for a script or a keybind: the button is named in omapad's
            # own logical names, never in what a badge happens to print.
            button = args[0].upper()
            if button not in guide_module.KINDS:
                return "unknown button: %s" % args[0]
            half = args[1] if len(args) > 1 else "tap"
            if half not in ("tap", "hold"):
                return "usage: press <BUTTON> [tap|hold]"
            fired = self.click_button(button, half)
            if half == "hold":
                # A tap is delivered rather than judged - what it fires is the
                # binding's business, and the reply says only that it went in.
                return "press %s hold=%s" % (
                    button, "fired" if fired else "nothing bound")
            return "press %s" % button
        if verb == "mode" and args and args[0] in ("toggle", "desktop", "game"):
            if args[0] == "toggle":
                self.toggle_mode()
            else:
                self.set_mode(args[0])
            return "mode=%s" % self.mode
        return "unknown command: %s" % request

    # -- held-action repeat ------------------------------------------------

    def repeat_start(self, action, delay, rate):
        self.repeats[id(action)] = [action, time.monotonic() + delay, rate]

    def repeat_stop(self, action):
        self.repeats.pop(id(action), None)

    def fire_repeats(self, now):
        for entry in list(self.repeats.values()):
            action, due, rate = entry
            if now >= due:
                action.repeat(self.ctx)
                entry[1] = now + rate

    def stick_roles(self):
        return self.config.stick_roles(self.current_layer, self.active_profile)

    def sticks_live(self):
        """Has either stick a role to integrate? Both are off in game mode
        unless [mode] hands one back."""
        return any(role in STICK_ROLES for role in self.stick_roles())

    # -- input handling ----------------------------------------------------

    def handle_button(self, button, pressed):
        if pressed:
            self.pressed.add(button)
        else:
            self.pressed.discard(button)
            self.forget_chords(button)
        # The bar lights the badge of whatever is down, and a press a chord or
        # a layer trigger takes is still a press - so it is recorded here,
        # before the routing that can return early, and drawn by the one push
        # that follows it. Sorted so an unchanged hand does not redraw the bar.
        self.gamebar.pressed = sorted(self.pressed)
        self.route_button(button, pressed)
        # Every button event repaints the bar while it is up: what is down has
        # changed, and so may the layer that decides every hint on it. Presses
        # arrive at the speed of a thumb, and this is one JSON line.
        if self.gamebar_open:
            self.push_gamebar_view()

    def route_button(self, button, pressed):
        """What the press means: a cancel, a chord, a layer, or a binding."""
        # A confirmation counting down owns the cancel button outright: while
        # a hold is announced, that button backs out instead of doing whatever
        # it usually does.
        if (
            pressed
            and button == self.config.confirm_cancel
            and self.cancel_confirm()
        ):
            return
        # A completed chord owns the press outright: neither button may also do
        # its own job, and a layer trigger inside one must not open its layer.
        if pressed and self.fire_chord(button):
            return

        # A surface that binds the button itself outranks a layer trigger. The
        # keyboard and the menu are implicit layers, so an ordinary binding in
        # them cannot shadow a trigger the way one layer shadows another - and
        # the keyboard needs the left trigger for a held Shift. Window ops wait
        # until the keyboard is down.
        override = self.surface_override(button)
        layer = None if override else self.config.layer_for_button(button)
        if layer is not None:
            if pressed:
                if layer.name not in self.active_layers:
                    self.active_layers.append(layer.name)
            else:
                if layer.name in self.active_layers:
                    self.active_layers.remove(layer.name)
                # Bindings held from inside the layer must not stay down.
                self.release_layer_holds(layer.name)
            # Every hint on the bar belongs to the layer that is live, so
            # opening one repaints it - which handle_button does for any
            # button event, this one included.
            return
        if not override and button in self.config.modifier_buttons:
            return  # precision modifier: no binding of its own

        if pressed:
            self.press_binding(button)
        else:
            self.release_binding(button)

    def surface_override(self, button):
        """The open surface that binds this button itself, if any.

        Checked before the layer triggers, and in the same order the surfaces
        outrank each other, so a keyboard binding can take a button that is a
        layer trigger everywhere else.
        """
        for name, opened in (("guide", self.guide_open),
                             ("menu", self.menu_open),
                             ("osk", self.osk_open)):
            if opened and self.config.binding_for(name, button) is not None:
                return name
        return None

    # -- chords ------------------------------------------------------------

    def fire_chord(self, button):
        """Did this press complete a chord? Then the chord takes the press.

        Order must not matter - two buttons pressed together arrive as two
        events, and which one lands first is not something a thumb decides - so
        completion is tested against everything currently held rather than
        against a sequence.
        """
        for buttons, action in self.chords:
            if button not in buttons or not buttons <= self.pressed:
                continue
            if buttons in self.active_chords:
                continue  # still held from the press that completed it
            self.active_chords.append(buttons)
            # A partner pressed first is either sitting on an undecided
            # tap/hold or holding its own binding down; the chord meant
            # neither.
            for partner in buttons:
                if partner != button:
                    self.cancel_button(partner)
            # A chord reaches past an app holding the pad whatever it runs.
            # Two buttons at once is not something a game asks you to press,
            # which is exactly why the way back in is one - and with `PLUS`
            # and `MINUS` standing aside over a game, it is the only way in.
            self.fire_once(action, reaches=True)
            return True
        return False

    def forget_chords(self, button):
        self.active_chords = [
            buttons for buttons in self.active_chords if button not in buttons
        ]

    def cancel_button(self, button):
        """Undo a press that a chord has just taken over."""
        self.clear_holding(button)
        held = self.held.pop(button, None)
        if held is not None and held.action is not None:
            held.action.release(self.ctx)

    def release_layer_holds(self, layer_name):
        for button, held in list(self.held.items()):
            if held.binding.layer == layer_name:
                if held.action is not None:
                    held.action.release(self.ctx)
                del self.held[button]

    # Actions that still answer while the pad is the app's: the ones that put
    # something of ours on screen, and the mode switch.
    SUMMONS = (actions.MenuAction, actions.OskAction, actions.GuideAction,
               actions.MappingAction, actions.ModeAction)
    # The layers a surface owns while it is up. A row picked on one of them
    # is allowed even once the surface has gone: see `allowed`.
    SURFACE_LAYERS = ("osk", "menu", "guide")

    def allowed(self, action, layer=None, confirmed=False, reaches=None):
        """Whether an action may run at all right now.

        Game mode is the couch environment, not a hand-off: everything works
        there, exactly as on the desktop. What does restrict things is the pad
        having been handed to the app in front, and what gets through then is
        a gesture the game does not ask for. A **chord**, because two buttons
        at once is not an input any game binds. An announced hold that has
        counted down (`confirm_ms`), for the same reason at the other end of
        the clock. And whatever a binding says with `reaches_past`, which
        overrules the kind of the action in both directions.

        A summon is the default for a binding that says nothing, because a
        menu you cannot open over a running game would make the whole
        arrangement useless. But it is only a default now: the app sees `PLUS`
        too, and a menu that opens on top of a cloud session every time you
        reach for its pause screen is the same fault in the other direction.
        So the shipped config takes those two off the single buttons and puts
        the way in on the chord, and `reaches_past = true` is how a binding
        that is not a summon at all - a left click in a stream - buys its way
        back.
        """
        if not self.handed_over:
            return True
        if self.osk_open or self.menu_open or self.guide_open or self.mapping_open:
            return True  # what is on screen is what the pad is driving
        # A row picked on a surface fires *after* that surface is put away -
        # the menu closes first, so what it opens does not come up behind a
        # scrim - and by then the pad looks handed over again. It is not: the
        # button that chose the row was ours, on a surface the pad was driving.
        # Without this every menu row that is not itself a summon is silently
        # dead while a game holds the pad, which is the one place the menu
        # exists for.
        if layer in self.SURFACE_LAYERS:
            return True
        if confirmed:
            return True
        # `reaches_past` is the binding's own answer, and it overrules the kind
        # of action in both directions: `true` lets a click past, `false` keeps
        # a summon back. Undecided falls to the rule that a summon is what an
        # arrangement like this cannot do without.
        if reaches is not None:
            return reaches
        return isinstance(action, self.SUMMONS)

    def press_binding(self, button):
        layer = self.current_layer
        binding = self.binding_for(layer, button)
        if binding is None:
            return
        now = time.monotonic()
        # A button a chord names cannot fire on the way down: whether this is a
        # chord or a press of its own is only known once its partner has had a
        # chance to land. So it waits for the release, the way a tap/hold
        # binding does - which also means a chord member is a poor place for a
        # drag.
        if binding.waits_for_release or button in self.chord_buttons:
            self.held[button] = HeldAction(None, binding, now)
            self.set_holding(button, binding)
            return
        action = binding.tap
        if not self.allowed(action, binding.layer, reaches=binding.reaches_past):
            return
        if binding.rumble:
            self.rumble.pulse()
        if binding.holdable:
            self.held[button] = HeldAction(action, binding, now)
            action.press(self.ctx)
        else:
            action.press(self.ctx)
            action.release(self.ctx)

    def release_binding(self, button):
        held = self.held.pop(button, None)
        if held is None:
            return
        self.clear_holding(button)
        if held.action is None:
            # Nothing went down: a tap/hold that never reached its hold, a
            # button that only acts on release, or a chord member whose chord
            # never completed. Either way the plain action is what was meant,
            # and now is when it fires - unless a confirming hold already
            # announced itself, in which case letting go is how you back out
            # and the tap was plainly not what you were after.
            if not held.hold_fired and not held.warned:
                if (
                    self.fire_once(held.binding.tap, held.binding.layer,
                                   reaches=held.binding.reaches_past)
                    and held.binding.rumble
                ):
                    self.rumble.pulse()
            return
        held.action.release(self.ctx)

    def click_button(self, button, half="tap"):
        """Fire a button from somewhere that is not the pad.

        The game bar was drawn for a thumb, but game mode is the couch
        environment rather than a hand-off: the desktop is still under the bar
        and whatever pointer it has is still on it. A badge that says what a
        button does is then the obvious thing to click, and a click has to
        reach the binding the press would - so a tap is replayed through the
        whole input path, where the chords, the layers and the tap/hold timing
        decide it exactly as they would for a thumb. Nothing here knows what a
        button is for; that stays one question with one answer.

        `hold` fires the other half outright, for a badge whose binding only
        has one: a hint reading "hold - Fullscreen" that did nothing when
        clicked would be worse than not being clickable. It does not re-ask the
        confirmation a held button asks, because that window exists for a thumb
        resting on a pad and a pointer aimed at a badge is already deliberate.
        """
        if half == "hold":
            binding = self.binding_for(self.current_layer, button)
            if binding is None or binding.hold is None:
                return False
            return self.fire_once(binding.hold, binding.layer, confirmed=True,
                                  reaches=binding.reaches_past)
        # A press and a release with nothing in between, which is a tap: what
        # fires is whatever the binding says a tap does.
        self.handle_button(button, True)
        self.handle_button(button, False)
        return True

    def set_holding(self, button, binding, armed=False):
        """Tell the bar where a confirming hold has got to.

        Two phases, because the gesture has two and only one of them was
        visible. Holding walks the badge from dimmed to full over `hold_ms` -
        "keep holding" - and at the tick it arms: full, and in the colour the
        bar keeps for something about to happen, for `confirm_ms` more. Only a
        confirming hold gets any of this; a plain one is over before a bar
        could say anything useful about it.
        """
        if not self.gamebar_open or not binding.confirm_ms:
            return
        self.gamebar.holding = {
            "b": guide_module.badge_of(button, self.gamebar.layout),
            "ms": binding.confirm_ms if armed else binding.hold_ms,
            "armed": armed,
        }
        self.push_gamebar_view()

    def clear_holding(self, button=None):
        if self.gamebar.holding is None:
            return
        if button is not None:
            badge = guide_module.badge_of(button, self.gamebar.layout)
            if self.gamebar.holding.get("b") != badge:
                return
        self.gamebar.holding = None
        if self.gamebar_open:
            self.push_gamebar_view()

    def fire_once(self, action, layer=None, confirmed=False, reaches=None):
        """Fire an action that has no press/release of its own. True if it ran."""
        if not self.allowed(action, layer, confirmed, reaches):
            return False
        action.press(self.ctx)
        action.release(self.ctx)
        return True

    def check_hold_timers(self, now):
        # A hold action may switch modes, which clears self.held mid-loop.
        for button, held in list(self.held.items()):
            binding = held.binding
            if not binding.is_tap_hold or held.hold_fired:
                continue
            elapsed = (now - held.pressed_at) * 1000.0
            if not binding.confirm_ms:
                if elapsed >= binding.hold_ms:
                    held.hold_fired = True
                    if self.fire_once(binding.hold, binding.layer,
                                      reaches=binding.reaches_past) and binding.rumble:
                        self.rumble.pulse()
                continue
            if not held.warned:
                if elapsed >= binding.hold_ms:
                    held.warned = True
                    self.warn_confirm(binding)
                    # The tick and the notification both happen away from the
                    # bar, so the badge says it too: the ramp has just reached
                    # full, and now it goes to the colour the bar keeps for
                    # "look here".
                    self.set_holding(button, binding, armed=True)
            elif elapsed >= binding.hold_ms + binding.confirm_ms:
                held.hold_fired = True
                self.clear_holding()
                # Announced, counted down and not cancelled - deliberate
                # enough to run even while an app holds the pad.
                self.fire_once(binding.hold, binding.layer, confirmed=True)

    def warn_confirm(self, binding):
        """Announce a hold that is about to act, and how to back out.

        The tick is the half of this that works with the screen off or the
        window full-screen, which is the case it exists for; the notification
        says what is coming and which button stops it.
        """
        self.rumble.pulse()
        what = binding.hold_desc or "Something is about to happen"
        self.session.notify(
            "omapad",
            "%s - %s to cancel" % (what, self.config.confirm_cancel),
            timeout=binding.confirm_ms,
        )

    def pending_confirm(self):
        return [held for held in self.held.values()
                if held.warned and not held.hold_fired]

    def cancel_confirm(self):
        """Back out of every hold that is counting down. True if any was."""
        pending = self.pending_confirm()
        for held in pending:
            # Not `hold_fired` because it fired, but because nothing more may:
            # the release must not fall back to the tap either.
            held.hold_fired = True
        if pending:
            self.session.notify("omapad", "Cancelled", timeout=900)
            log.info("confirm: cancelled")
        return bool(pending)

    def drain_events(self):
        try:
            for etype, code, value in self.device.read_events():
                if self.mapping_open:
                    self.mapping_event(etype, code, value)
                    continue
                if etype == li.EV_KEY:
                    if value == 2:
                        continue  # kernel auto-repeat: the edge already fired
                    name = self.buttons.get(code)
                    if name:
                        self.handle_button(name, value == 1)
                elif etype == li.EV_ABS:
                    if code in self.axes:
                        if code in self.uncalibrated:
                            self.uncalibrated.discard(code)
                            self.calibrate_axis(code, value)
                        center, half = self.axis_scale.get(code, (0.0, 1.0))
                        raw = (value - center) / half
                        self.axes[code] = max(-1.0, min(1.0, raw))
                    elif code == li.ABS_HAT0X:
                        self.handle_hat("x", value)
                    elif code == li.ABS_HAT0Y:
                        self.handle_hat("y", value)
                    elif code in self.trigger_axes:
                        self.handle_trigger(code, value)
        except OSError as exc:
            if exc.errno in (errno.ENODEV, errno.EIO, errno.EBADF):
                self.disconnect()
            else:
                raise

    def mapping_event(self, etype, code, value):
        """Read the pad with the map switched off, for the screen that makes one.

        Nothing here goes through self.buttons: the whole point is that the
        names it holds are the ones in doubt. A press is a code, a trigger is
        an axis that has left where it rests, and everything else - the sticks,
        the hat, the syn - is ignored rather than guessed at.
        """
        if etype == li.EV_KEY:
            if value == 2:
                return  # kernel auto-repeat
            if value == 1:
                self._mapping_down = (code, time.monotonic())
                self.mapping_press("button", code)
            elif self._mapping_down and self._mapping_down[0] == code:
                self._mapping_down = None
            return
        if etype != li.EV_ABS or code in self.axes:
            return
        if code in (li.ABS_HAT0X, li.ABS_HAT0Y):
            return
        info = self.device.absinfo(code) if self.device else None
        if info is None:
            return
        # A trigger rests at its minimum and travels towards its maximum, so
        # how far it has left the minimum is how far it is pulled. Hysteresis,
        # as everywhere else a trigger is read as a button: pulled past ON,
        # and not pullable again until it has fallen back under OFF.
        span = max(info.maximum - info.minimum, 1)
        travel = (value - info.minimum) / span
        if code in self._mapping_axis_hot:
            if travel <= MAPPING_AXIS_OFF:
                self._mapping_axis_hot.discard(code)
            return
        if travel >= MAPPING_AXIS_ON:
            self._mapping_axis_hot.add(code)
            self.mapping_press("axis", code)

    def check_mapping_hold(self, now):
        """The way out that needs no map: hold anything long enough."""
        if not self.mapping_open or self._mapping_down is None:
            return
        if now - self._mapping_down[1] < MAPPING_CANCEL_HOLD:
            return
        self._mapping_down = None
        self.rumble.pulse()
        self.set_mapping(False)
        if self.config.notify:
            self.session.notify("omapad", "Mapping cancelled")

    def handle_trigger(self, code, value):
        """Turn an analog trigger into a button, with hysteresis.

        Pressing at one point and releasing at a lower one keeps a trigger
        rested halfway from rattling the layer it activates on and off.
        """
        minimum, span = self.trigger_scale.get(code, (0, 1))
        fraction = (value - minimum) / span
        name = self.trigger_axes[code]
        if name in self.trigger_down:
            if fraction <= self.config.trigger_release:
                self.trigger_down.discard(name)
                self.handle_button(name, False)
        elif fraction >= self.config.trigger_threshold:
            self.trigger_down.add(name)
            self.handle_button(name, True)

    def handle_hat(self, axis, value):
        previous = self.hat[axis]
        if previous == value:
            return
        self.hat[axis] = value
        if previous:
            name = DPAD_NAMES.get((axis, previous))
            if name:
                self.handle_button(name, False)
        if value:
            name = DPAD_NAMES.get((axis, value))
            if name:
                self.handle_button(name, True)

    # -- continuous output -------------------------------------------------

    def stick_vector(self, stick):
        code_x, code_y = STICK_AXES[stick]
        return apply_curve(
            self.axes[code_x],
            self.axes[code_y],
            self.config.stick_deadzone(stick),
            self.config.pointer_accel,
        )

    def scroll_vector(self, stick):
        code_x, code_y = STICK_AXES[stick]
        return apply_curve(
            self.axes[code_x],
            self.axes[code_y],
            self.config.stick_deadzone(stick),
            self.config.scroll_accel,
        )

    def needs_tick(self):
        """Is there anything to integrate or time out between events?"""
        if self.repeats:
            return True
        if self.mapping_open and self._mapping_down is not None:
            return True  # a hold that is counting down towards cancelling
        for held in self.held.values():
            if held.binding.is_tap_hold and not held.hold_fired:
                return True
        if self.ctx.held_scrolls:
            return True
        if not all(self._snap_armed.values()):
            # A flick that has fired and not been let go of yet. Without this
            # a stick released between two ticks would never re-arm, and the
            # snap would work exactly once.
            return True
        if self._focus_held:
            return True  # a held direction still walking the focus
        if not self.sticks_live():
            return False
        deadzone = min(self.config.left_deadzone, self.config.right_deadzone)
        return any(abs(value) > deadzone for value in self.axes.values())

    def tick(self, dt):
        left_role, right_role = self.stick_roles()
        cursor = scroll = None
        resize = move = None
        for stick, role in (("left", left_role), ("right", right_role)):
            if role == "cursor":
                cursor = self.stick_vector(stick)
            elif role == "scroll":
                scroll = self.scroll_vector(stick)
            elif role == "resize":
                resize = self.stick_vector(stick)
            elif role == "move":
                move = self.stick_vector(stick)
            elif role == "snap":
                self.check_flick(stick)
            elif role == "focus":
                self.check_focus_stick(stick, dt)

        if cursor is not None:
            self.emit_cursor(cursor, dt)
        self.emit_scroll(scroll, dt)
        if resize is not None or move is not None:
            self.emit_window(resize, move, dt)

    def check_flick(self, stick):
        """A stick whose role is `snap`: one window per push, not a stream.

        Read off the raw axes rather than the curved vector - the curve exists
        to make small deflections finer, and this only ever asks whether the
        stick went all the way over.
        """
        code_x, code_y = STICK_AXES[stick]
        x, y = self.axes[code_x], self.axes[code_y]
        magnitude = (x * x + y * y) ** 0.5
        if magnitude < self.config.snap_release:
            self._snap_armed[stick] = True
            return
        if magnitude < self.config.snap_flick or not self._snap_armed[stick]:
            return
        self._snap_armed[stick] = False
        if abs(x) >= abs(y):
            landed = self.snap_cursor("right" if x > 0 else "left")
        else:
            landed = self.snap_cursor("down" if y > 0 else "up")
        # Only when it went somewhere: a flick into an empty edge that buzzed
        # would say the same thing as one that worked.
        if landed and self.config.snap_rumble:
            self.rumble.pulse()

    def focus_step(self, step, pressed):
        """Send the key the focused app walks its own focus with.

        Held rather than tapped, so the compositor's key repeat applies to a
        button held down exactly as it would to a real keyboard.
        """
        chord = self.config.traverse_keys.get(step)
        if chord is None:
            return False
        mods, code = chord
        self.keyboard.chord(mods, code, pressed)
        return True

    def check_focus_stick(self, stick, dt):
        """A stick whose role is `focus`: a direction, and it repeats.

        The repeat is ours rather than the compositor's: nothing stays down
        between steps, because a stick pushed over is not a key held down and
        an app that saw one would autorepeat straight past wherever the thumb
        stopped. Counted down off the tick's own `dt` like the other
        integrators, rather than against the clock, so it walks at the same
        rate whenever the loop happens to wake.
        """
        code_x, code_y = STICK_AXES[stick]
        x, y = self.axes[code_x], self.axes[code_y]
        magnitude = (x * x + y * y) ** 0.5
        if magnitude < self.config.traverse_release:
            self._focus_held.pop(stick, None)
            return
        if magnitude < self.config.traverse_flick:
            return
        if abs(x) >= abs(y):
            way = "right" if x > 0 else "left"
        else:
            way = "down" if y > 0 else "up"
        step = self.config.traverse_stick.get(way)
        if step is None:
            return  # a direction the config turned off
        held = self._focus_held.get(stick)
        if held is None or held[0] != step:
            # A new direction steps at once and then waits out the delay, the
            # way a held key does.
            self._focus_held[stick] = [step, self.config.traverse_repeat_delay]
        else:
            held[1] -= dt
            if held[1] > 0:
                return
            held[1] = self.config.traverse_repeat_rate
        self.focus_step(step, True)
        self.focus_step(step, False)

    def snap_cursor(self, direction):
        """Put the pointer on the window next door, or in the middle of this one.

        Every fact here is asked of Hyprland at the moment of the press rather
        than kept: windows move, and a snap aimed at where one used to be is
        worse than no snap at all. Three `j/` queries cost well under a
        millisecond between them, which a button press can afford.
        """
        position = self.hypr.cursor_position()
        if position is None:
            return False
        x, y = position
        monitors = self.hypr.query("monitors")

        if direction == "centre":
            target = self.hypr.query("activewindow")
            if not isinstance(target, dict) or snap_module.rect(target) is None:
                return False
        else:
            clients = self.hypr.query("clients")
            if clients is None:
                return False
            monitor = None
            if self.config.snap_same_monitor:
                monitor = snap_module.monitor_at(monitors, x, y)
            windows = snap_module.candidates(clients, monitors, monitor)
            target = snap_module.choose(
                windows, x, y, direction, self.config.snap_bias
            )
            if target is None:
                return False

        point = snap_module.centre(target)
        if point is None:
            return False
        self.hypr.warp(point[0], point[1])
        # focus_follows_mouse would do this for us where it is on, and doing
        # it anyway costs one dispatch and works where it is off.
        address = target.get("address")
        if self.config.snap_focus and address:
            self.hypr.dispatch(
                "hl.dsp.focus({ window = 'address:%s' })" % address
            )
        return True

    def emit_cursor(self, vector, dt):
        speed = self.config.pointer_speed
        if (
            self.config.precision_button
            and self.config.precision_button in self.pressed
        ):
            speed *= self.config.precision_factor
        self._cursor_remainder[0] += vector[0] * speed * dt
        self._cursor_remainder[1] += vector[1] * speed * dt
        dx = int(self._cursor_remainder[0])
        dy = int(self._cursor_remainder[1])
        if dx or dy:
            self._cursor_remainder[0] -= dx
            self._cursor_remainder[1] -= dy
            self.mouse.move(dx, dy)

    def scroll_ramp(self, x, y, dt):
        """How much faster the wheel goes for having been held.

        A page is long and a thumb is not: the deflection alone has to serve
        both the line you are nudging towards and the thousand lines below,
        and it cannot. So time counts as well - the longer a direction is
        held, the faster it goes, up to `ramp` after `ramp_ms`.

        Held one *way*, though: a reversal is somebody who has gone too far,
        and handing them the speed they overshot at is the opposite of what
        they asked for. Letting go does the same, in emit_scroll.

        The way is the dominant axis and its sign rather than both signs: a
        thumb pushed straight down still wanders a little sideways, and a
        sideways wobble across zero is not a change of mind.
        """
        if abs(y) >= abs(x):
            way = ("y", (y > 0) - (y < 0))
        else:
            way = ("x", (x > 0) - (x < 0))
        if way != self._scroll_way:
            self._scroll_way = way
            self._scroll_held = 0.0
        self._scroll_held += dt
        if self.config.scroll_ramp <= 1.0:
            return 1.0
        if self.config.scroll_ramp_ms <= 0:
            return self.config.scroll_ramp
        share = min(1.0, self._scroll_held / (self.config.scroll_ramp_ms / 1000.0))
        return 1.0 + (self.config.scroll_ramp - 1.0) * share

    def emit_scroll(self, vector, dt):
        x = vector[0] if vector else 0.0
        # Stick y is positive downwards; a wheel's positive direction is up.
        y = -vector[1] if vector else 0.0
        for dx, dy in self.ctx.held_scrolls.values():
            x += dx
            y += dy
        if not x and not y:
            self._scroll_held = 0.0
            self._scroll_way = None
            return
        if self.config.scroll_natural:
            x, y = -x, -y
        rate = (
            self.config.scroll_speed
            * WHEEL_HI_RES_STEP
            * dt
            * self.scroll_ramp(x, y, dt)
        )
        self._scroll_remainder[0] += x * rate
        self._scroll_remainder[1] += y * rate
        hx = int(self._scroll_remainder[0])
        hy = int(self._scroll_remainder[1])
        if hx or hy:
            self._scroll_remainder[0] -= hx
            self._scroll_remainder[1] -= hy
            self.mouse.scroll(hx, hy)

    def emit_window(self, resize, move, dt):
        step = self.config.window_step * dt
        for name, vector in (("resize", resize), ("move", move)):
            if not vector:
                continue
            remainder = self._window_remainder[name]
            remainder[0] += vector[0] * step
            remainder[1] += vector[1] * step
        now = time.monotonic()
        if now - self._last_window_flush < 1.0 / self.config.window_hz:
            return
        self._last_window_flush = now
        for name in ("resize", "move"):
            remainder = self._window_remainder[name]
            dx, dy = int(remainder[0]), int(remainder[1])
            if not dx and not dy:
                continue
            remainder[0] -= dx
            remainder[1] -= dy
            self.hypr.dispatch(
                "hl.dsp.window.%s({ x = %d, y = %d, relative = true })"
                % (name, dx, dy)
            )

    # -- main loop ---------------------------------------------------------

    def run(self):
        self.prepare_cursor()
        # A session configured to start in game mode has had no switch to hang
        # the swap off, and the pointer is the one thing that would show it.
        self.apply_cursor()
        interval = 1.0 / self.config.poll_hz
        last = time.monotonic()
        poller = select.poll()
        control_fd = self.control.fileno() if self.control else None
        if control_fd is not None:
            poller.register(control_fd, select.POLLIN)
        device_fd = None
        hypr_ev_fd = None
        key_fds = ()

        while self.running:
            now = time.monotonic()
            if self.device is None and now >= self._next_reconnect:
                self._next_reconnect = now + RECONNECT_INTERVAL
                self.connect()

            if self.device is None:
                if device_fd is not None:
                    poller.unregister(device_fd)
                    device_fd = None
            elif device_fd != self.device.fd:
                if device_fd is not None:
                    poller.unregister(device_fd)
                device_fd = self.device.fd
                poller.register(device_fd, select.POLLIN)

            # The keyboards on the desk are opened only while a surface of
            # ours is up: that is the whole scope of what they may drive, and
            # holding them open the rest of the time would not be.
            if self.keys.follow(self.surface_top() is not None):
                for fd in key_fds:
                    poller.unregister(fd)
                # Whatever a key was holding, it will send no release now.
                self.release_keys()
                key_fds = self.keys.fds()
                for fd in key_fds:
                    poller.register(fd, select.POLLIN)

            # Subscribe (and re-subscribe) to the Hyprland focus event stream.
            # It dies when the compositor restarts, so keep trying periodically
            # rather than treating a drop as permanent.
            if self.hypr_ev is None and now >= self._next_hypr_reconnect:
                self._next_hypr_reconnect = now + RECONNECT_INTERVAL
                self._connect_hypr_events()
            if self.hypr_ev is None:
                if hypr_ev_fd is not None:
                    poller.unregister(hypr_ev_fd)
                    hypr_ev_fd = None
            elif self.hypr_ev.fileno() != hypr_ev_fd:
                if hypr_ev_fd is not None:
                    poller.unregister(hypr_ev_fd)
                hypr_ev_fd = self.hypr_ev.fileno()
                poller.register(hypr_ev_fd, select.POLLIN)

            if self.device is None:
                timeout_ms = min(interval, RECONNECT_INTERVAL) * 1000.0
            elif self.needs_tick():
                timeout_ms = max(0.0, (last + interval - now)) * 1000.0
            else:
                timeout_ms = IDLE_POLL_MS

            try:
                events = poller.poll(timeout_ms)
            except InterruptedError:
                continue

            for fd, _ in events:
                if control_fd is not None and fd == control_fd:
                    self.control.serve(self.handle_control)
                elif self.device is not None and fd == self.device.fd:
                    self.drain_events()
                elif fd in key_fds:
                    self.drain_keys(fd)
                elif self.hypr_ev is not None and fd == self.hypr_ev.fileno():
                    if not self._drain_hypr_events():
                        self.hypr_ev.close()
                        self.hypr_ev = None
                        log.warning(
                            "Hyprland event socket closed; resubscribing"
                        )

            now = time.monotonic()
            if now - last >= interval:
                dt = now - last
                last = now
                self.check_hold_timers(now)
                self.fire_repeats(now)
                if self.osk_open and now >= self._osk_next_heartbeat:
                    self.push_osk_view()
                if self.menu_open and now >= self._menu_next_heartbeat:
                    self.push_menu_view()
                if self.guide_open and now >= self._guide_next_heartbeat:
                    self.push_guide_view()
                if self.mapping_open:
                    self.check_mapping_hold(now)
                    if now >= self._mapping_next_heartbeat:
                        self.push_mapping_view()
                if now >= self._next_handover_check:
                    # Most apps open the pad a moment after they come up, not
                    # while they are still being mapped.
                    self.update_handover()
                if now >= self._status_next_heartbeat:
                    self.push_status_view()
                if self.gamebar_open and now >= self._gamebar_next_heartbeat:
                    self.push_gamebar_view()
                self.tick(dt)

    def shutdown(self):
        self.running = False
        self.release_everything()
        if self.device is not None:
            self.rumble.detach()
            self.device.close()
            self.device = None
        self.set_osk(False)
        self.osk_client.close()
        self.set_menu(False)
        self.menu_client.close()
        self.set_guide(False)
        self.guide_client.close()
        self.set_mapping(False)
        self.mapping_client.close()
        # Whatever mode we died in, the bar and the pointer are the user's,
        # not ours.
        self.apply_bar(restore=True)
        self.apply_cursor(restore=True)
        self.status_client.close()
        self.set_gamebar(False)
        self.gamebar_client.close()
        if self.control is not None:
            self.control.close()
        if self.hypr_ev is not None:
            self.hypr_ev.close()
            self.hypr_ev = None
        self.release_keys()
        self.keys.close()
        self.mouse.close()
        self.keyboard.close()
