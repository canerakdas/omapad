"""The omapad event loop."""

import errno
import json
import logging
import os
import select
import socket
import time

from . import actions, keymap, linux_input as li
from .actions import MappingAction
from .config import (
    CHOSEN, DPAD_NAMES, SURFACES, layout_path, mapping_path, render_layout,
    nearest_stop_index, render_settings, setting_share, setting_text,
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
from .hud import HudModel
from .mapping import MappingModel, render as render_mapping
from .menu import (CONTROL_KINDS, ROWS, MenuError, MenuModel,
                   build as build_menu, build_head, head_sources,
                   meta_sources, listed)
from .osk import OskModel, badge_index
from . import paths
from .ripple import RippleModel
from . import sound as sound_module
from .sound import SoundModel
from .live import Live
from . import live as live_module
from .sysinfo import Sysinfo
from . import sysinfo as sysinfo_module
from .rumble import Rumble
from . import xkb
from .viewsock import ViewClient, drawable
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

# The actions that leave the pointer on screen when they are pressed: the
# three that are the pointer's own work, and the one that hides it without
# being asked - a key, which is the compositor behaviour `pointer_away`
# borrows for every other press.
POINTER_STAYS = (actions.ClickAction, actions.ScrollAction,
                 actions.SnapAction, actions.KeyAction)

# The stick roles the tick knows how to integrate; anything else - "none" - is
# a stick with nothing to do.
STICK_ROLES = ("cursor", "scroll", "resize", "move", "snap", "focus",
               "swap")
def ramped(rate, ramp, ramp_time, held):
    """The gap before the next step of a direction held `held` seconds.

    A direction held down is somebody crossing a distance rather than picking
    the thing next door, and a walk that stays at one speed the whole way is
    most of why a long row is hard to cross at all: a keyboard page is
    fourteen keys wide, and fourteen steps is the same journey however quickly
    the last one arrives. So the steps close up the longer the thumb is on it -
    `ramp` times the shipped rate by `ramp_time`, and no faster after that.

    Linear in **speed** rather than in the gap, which is the one decision in
    here: ramping the gap spends most of the acceleration in the first tenth
    of the journey and then crawls, and what a thumb is doing is covering
    distance.
    """
    if ramp <= 1.0 or ramp_time <= 0:
        return rate
    share = min(1.0, held / ramp_time)
    return rate / (1.0 + (ramp - 1.0) * share)


RECONNECT_INTERVAL = 2.0
# When nothing is deflected or held there is nothing to integrate, so the loop
# blocks on poll() this long instead of waking at the full polling rate. Any
# event from the pad returns from poll() immediately, so latency is unaffected.
IDLE_POLL_MS = 250.0
# While a surface is up its state is re-sent this often. The shell can restart
# or reload the plugin underneath us - a theme change does it - and the fresh
# panel comes up empty with no way to know what it should be drawing.
VIEW_HEARTBEAT = 2.0

# The order the menu's legend prints its face buttons in. A commits, B leaves,
# X is this thing's own verb and Y is the reach - the order the contract reads
# in, so the strip teaches it every time it is glanced at.
MENU_LEGEND = ("A", "B", "X", "Y")

# The two triggers, read as axes while the menu is open. Named here rather
# than bound: `bindings.md` says of ZL that a layer trigger has no binding of
# its own, in any layer or profile, and this gives it none. A surface layer
# falls through to nothing, so both are free while the menu is up, and how far
# one is pulled is a question no binding could have asked anyway.
MENU_TRIGGERS = (("ZL", -1), ("ZR", 1))

# What the buttons mean while a page is being rearranged, as ordinary binding
# specs. A table rather than a branch in the press handler, because the legend
# along the foot of the card is built from exactly these - so what it prints
# and what a press does cannot drift apart, which is the whole reason the
# legend is worth having.
#
# A still commits and B still leaves: picking a tile up and putting it down is
# what "commit" is saying here, and leaving edit mode is leaving. X is this
# surface's own verb one mode along - `close` becomes `hide` - and Y is still
# the reach, for the arrangement that is not on screen because it is the one
# the config shipped.
#
# **L and R are the only controls taken from anything.** They walk the bar
# everywhere else in this layer, and while a page is being rearranged the bar
# is not what a thumb is aiming at. Nothing is taken from ZL or ZR: a height
# is a control's own shape - a bar is a bar and a dial is round - so what a
# person overrides is how much room across a tile gets, and that is two
# buttons rather than four.
EDIT_KEYS = {
    "A": {"tap": "menu:pick", "desc": "Pick it up or put it down",
          "short": "Move"},
    "B": {"tap": "menu:edit_off", "desc": "Done rearranging",
          "short": "Done"},
    "X": {"tap": "menu:hide", "desc": "Take it off, or put it back",
          "short": "Hide"},
    "Y": {"tap": "menu:restore", "desc": "Back to the shipped page",
          "short": "Reset"},
    "L": {"tap": "menu:narrower", "desc": "Narrower", "short": "Narrower"},
    "R": {"tap": "menu:wider", "desc": "Wider", "short": "Wider"},
}

# What the legend prints while rearranging: the four the contract owns, and
# the two the arrangement borrowed. Six is more than a legend usually holds,
# and it is what stops the two borrowed ones being a secret.
EDIT_LEGEND = ("A", "B", "X", "Y", "L", "R")

# How long a control keeps counting as being pushed after the last thing that
# pushed it. It has to outlast the gap between two repeats or the texture
# stutters in time with them, which is the buzzing-per-step this effect exists
# instead of. Counted down in `tick` off the same dt the sweep integrates over
# rather than against the clock: one clock, and a loop running slow slows both
# halves together. Not a setting: it is a property of the repeat rate rather
# than anything to taste.
MENU_SCRUB_HOLD = 0.2

# How often the desktop's theme is looked at. One `stat` of a file, on the
# same beat the surfaces already heartbeat at, so a pointer drawn from the old
# palette catches up before anybody has finished looking at the new one. Not a
# setting: it is the cadence of a file check, and nobody wants it different -
# what it decides is a delay too short to see.
THEME_POLL = 2.0


def _nothing(lines):
    """A command whose answer nobody wants. The write is the whole of it."""


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
    __slots__ = ("action", "binding", "pressed_at", "hold_fired", "warned",
                 "released_at")

    def __init__(self, action, binding, pressed_at):
        self.action = action
        self.binding = binding
        self.pressed_at = pressed_at
        # A confirming hold that has announced itself and is counting down.
        self.warned = False
        self.hold_fired = False
        # When the finger came off one that was already counting down, while
        # `[confirm] slack_ms` says the countdown survives a slip. None is a
        # button that is still down, which is every hold on a shipped config.
        self.released_at = None


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

        # The plugin binds its view sockets in this directory, and at login
        # the shell is up before us: Hyprland execs it the moment the
        # compositor is there, while this service is still starting Python.
        # Making the directory here rather than as a side effect of the
        # control socket means the plugin's next retry finds somewhere to bind
        # even when the control socket was pointed somewhere else or could not
        # be bound at all.
        try:
            paths.socket_dir(create=True)
        except (OSError, paths.RuntimeDirError) as exc:
            # The same best-effort the views themselves get: a daemon with
            # nowhere to draw still drives the desktop.
            log.warning("socket directory unavailable: %s", exc)

        try:
            self.control = ControlServer(config.control_socket)
        except (OSError, RuntimeError) as exc:
            # A daemon that cannot be scripted is still a working daemon.
            log.warning("control socket unavailable: %s", exc)
            self.control = None

        # Every shell command a surface asks for is run off the loop, and the
        # answer comes back down this pipe: `submit_command` hands out the
        # key, `drain_commands` gives the answer to whoever asked for it.
        self._command_wake = None
        self._command_jobs = {}
        self._command_seq = 0
        self.commands = None
        try:
            read_fd, write_fd = os.pipe()
            os.set_blocking(read_fd, False)
            self._command_wake = read_fd
            self.commands = actions.Commands(self.session, wake=write_fd)
        except OSError as exc:
            # No worker is still a working daemon: the callers fall back to
            # reading their command on the loop, which is where it was.
            log.warning("command worker unavailable: %s", exc)
            self.commands = None

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
        # Which profile's page has a command in flight, so opening the
        # keyboard twice while a slow history file is read asks once.
        self._osk_page_job = None

        try:
            items = build_menu(config.menu_items,
                               columns=config.menu_columns,
                               settings=CHOSEN,
                               readings=live_module.READINGS,
                               machine=sysinfo_module.READINGS,
                               countdown=config.menu_countdown)
        except MenuError as exc:
            # A broken entry must not take the daemon down with it; the menu
            # comes up empty and `omapad check` names the row.
            log.error("menu: %s", exc)
            items = []
        try:
            head = build_head(config.menu_head, columns=config.menu_columns)
        except MenuError as exc:
            # The same posture one grid up: a head that will not parse costs
            # the clock and the weather, not the menu under them.
            log.error("menu head: %s", exc)
            head = []
        self.menu = MenuModel(items, config.menu_title, config.menu_clock,
                              columns=config.menu_columns,
                              bias=config.menu_bias, head=head,
                              layout=config.layout,
                              # The one page that is also drawn on something
                              # with a bottom edge. The menu is where a page
                              # is arranged, so the menu is what has to stop
                              # a tile being carried off the end of it.
                              page_rows={config.hud_page: config.hud_rows})
        self.menu_client = ViewClient("menu.sock", config.menu_socket)
        self.menu_open = False
        self._menu_next_heartbeat = 0.0
        # When the chip the bar came to rest on is worth asking about. Zero is
        # nothing pending.
        self._menu_group_due = 0.0
        # A control being scrubbed: which way it is going and when that push
        # began, for the ramp; how much longer it counts as still moving, for
        # the texture; the setting whose new value has not been written down;
        # whether the end of the travel has already been announced; and what
        # the value was before it was taken, for the B that puts it back.
        self._menu_way = None
        self._menu_since = 0.0
        self._menu_moving = 0.0
        self._menu_dirty = None
        self._menu_edged = False
        self._menu_before = None
        self._menu_sweep = 0.0
        # The readings, left on screen. One of the menu's own pages, packed
        # the same way and drawn somewhere else - so it is built from the same
        # tree and reads the same arrangement, and a tile carried in edit mode
        # moves in both places at once.
        self.hud = HudModel(items, page=config.hud_page,
                            columns=config.menu_columns,
                            rows=config.hud_rows,
                            # **The menu's arrangement, not the config's**, and
                            # the same dict rather than a copy of it. The menu
                            # takes its own copy of what came off layout.toml
                            # so that rearranging never writes back into the
                            # config - which means `config.layout` is the file
                            # as it was read and stops being true the moment
                            # anybody carries a tile. This surface draws the
                            # page somebody is arranging, so it has to read
                            # the arrangement they are making.
                            layout=self.menu.layout)
        self.hud_client = ViewClient("hud.sock", config.hud_socket)
        # Not a surface that is opened: it is a setting somebody left on, so
        # it comes back up the way they left it.
        self.hud_open = bool(config.hud_show)
        self._hud_next_heartbeat = 0.0
        # What the machine underneath is doing, which readings have a helper's
        # question in flight, and when each may be asked again.
        self.sysinfo = Sysinfo(config)
        self._sys_asking = set()
        self._sys_poll = {}
        # What the machine is doing. Which readings have a question in flight,
        # when each may be asked again, and the one-shot after a write - the
        # helper has to have landed before asking it what it did.
        self.live = Live(config)
        self._live_asking = set()
        self._live_poll = {}
        self._live_due = {}
        # When the next gauge frame is due, and the last one sent. The floats
        # are quantised and compared so a thumb resting off the stick stops
        # the stream entirely rather than pushing ADC jitter at a screen
        # nothing is moving on.
        self._menu_live_due = 0.0
        self._menu_live_last = None
        # The chip and the tile the menu was on when it was last closed, so
        # opening it again picks up where the last press left off.
        self._menu_where = None
        # What the desktop's theme was when we last looked, and when to look
        # again. A theme change is the one thing that undoes what omapad has
        # asked the desktop for - see `check_theme`.
        self._theme_seen = None
        self._theme_next_check = 0.0
        # Whether the compositor animates anything at all. Cached rather
        # than asked per push: it is read on the theme beat, and a payload
        # goes out sixty times a second while a gauge is selected. True until
        # something says otherwise, so a desktop with no Hyprland to ask -
        # the tests, a bare session - draws the surfaces as designed.
        self._desktop_animates = True
        # The last thing each head cell's command said, and when it may be
        # asked again. The head is read-only, so a stale answer is drawn
        # rather than blanked: a cell that empties because a helper was slow
        # reads as a drawing fault.
        self._menu_head_text = {}
        self._menu_head_due = {}
        # The same pair for the bar: what each group's `meta` command last
        # said, and when it is worth asking again.
        self._menu_meta_text = {}
        self._menu_meta_due = {}
        # One built binding per page and button, for the keys a page spends.
        # Keyed by page rather than cleared on every move: what a page spends
        # never changes, and there are not many pages.
        self.page_keys = {}

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
        # The same answer given by hand, and it outranks the question: while
        # the lock is on the pad is the app's whatever /proc says, and nothing
        # of ours fires but a chord. Runtime state rather than a setting - a
        # lock that survived a restart would be a pad that does nothing for a
        # reason nobody remembers. See `set_locked`.
        self.locked = False
        # And the same answer given the other way: the pad is ours over a
        # window that has opened it and is not being played with - a cloud
        # client's launcher screen, which reads no pad and is the only thing
        # between you and the stream. Runtime state for the same reason the
        # lock is, and exclusive with it: two overrides arguing about one pad
        # is a state nobody could name. See `set_keeping`.
        self.keeping = False
        self.pad_nodes = frozenset()
        self.focus_pid = None
        self._next_handover_check = 0.0
        # When a wanted grab may be taken anyway. A grab taken while a button
        # is down strands that button in whatever had the pad, so it waits for
        # the hand to come off first - see `apply_grab`.
        self._grab_wait = None

        # What a click looks like. An event rather than a state, so there is
        # no `_open` and no `_next_heartbeat` beside it: a burst that is over
        # has nothing to repaint. See ripple.py.
        self.ripple = RippleModel(config)
        self.ripple_client = ViewClient("ripple.sock", config.ripple_socket)

        # What a press sounds like. The same shape for the same reason: a
        # sound that has finished has nothing to repaint, so there is no
        # heartbeat and no `open` here either. See sound.py.
        self.sound = SoundModel(config)
        self.sound_client = ViewClient("sound.sock", config.sound_socket)

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
        # When the pad was last touched, and whether that still counts as
        # somebody being there. Both start true: a daemon that came up has
        # just been started by somebody, and a screen that went dark the
        # moment the pad was plugged in would be the wrong first impression.
        self._touched = time.monotonic()
        self._awake = True
        # A menu row that is being held down towards running: the row, when
        # the thumb landed on it, and whether it has announced itself yet.
        # None almost always - only the handful of rows nobody can undo ask
        # for it. See `menu_arm`.
        self._menu_confirm = None
        # And a menu row that has been pressed and is **counting down** to
        # running: `{id, item, at}`. The other answer to *are you sure*, and
        # the one that asks nothing of the hand - see `menu_count`.
        self._menu_countdown = None
        # Which page's listing cards have been read, and when the page in
        # front is due to be asked. See `menu_cards_settled`.
        self._menu_cards_page = ""
        self._menu_cards_due = 0.0

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
        # How far each trigger is pulled, 0..1. Kept beside the digital answer
        # above rather than instead of it: a trigger is a button everywhere
        # else in this daemon, and only the menu asks the other question.
        self.trigger_level = {}
        self.hat = {"x": 0, "y": 0}
        self.pressed = set()
        self.chords = []                 # (frozenset of buttons, Action)
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
        # The Hyprland focus event socket. It streams `activewindow>>class,
        # title` and `activewindowv2>>address` lines; subscribing once swaps
        # the active profile as focus moves.
        self.hypr_ev = None
        self._hypr_ev_buf = b""
        self._next_hypr_reconnect = 0.0
        # Which window the stream last named, as the address `activewindowv2`
        # carries. What it is for is the difference between *a new window is
        # in front* and *the window in front renamed itself*: only the first
        # is worth asking /proc about, and a terminal running a command sends
        # the second about once a second.
        self._hypr_window = None

        self._cursor_remainder = [0.0, 0.0]
        self._scroll_remainder = [0.0, 0.0]
        # How long the wheel has been going one way without a break, which is
        # what [scroll] ramp turns into speed.
        self._scroll_held = 0.0
        self._scroll_way = None
        self._window_remainder = {"resize": [0.0, 0.0], "move": [0.0, 0.0]}
        # A stick with the "snap" role is a flick, not an integrator: it fires
        # once when it is pushed and re-arms only after it comes back. The
        # "swap" role is the same shape on its own thresholds, and so is the
        # tiled half of "move".
        self._snap_armed = {"left": True, "right": True}
        self._swap_armed = {"left": True, "right": True}
        # Which half of the "move" role this push is, asked once when the
        # stick leaves its rest and kept until it comes back. See move_drags().
        self._move_drag = {}
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
            except actions.ActionError as exc:
                log.error("bad chord %s: %s", "+".join(sorted(buttons)), exc)

    # -- shell commands off the loop ---------------------------------------

    def submit_command(self, command, done, timeout=2.0):
        """Run a shell command in the worker; `done(lines)` when it answers.

        False when there is no worker to run it, and the caller reads it on
        the loop instead - a daemon that could not make a pipe is slower, not
        broken. `done` is called on the loop, so it may touch any state and
        push any view.
        """
        if self.commands is None:
            return False
        self._command_seq += 1
        self._command_jobs[self._command_seq] = done
        self.commands.submit(self._command_seq, command, timeout)
        return True

    def drain_commands(self):
        """Give every finished command's answer to whoever asked for it."""
        if self._command_wake is not None:
            try:
                # One byte per answer, and the queue is what carries them;
                # this only has to empty the pipe.
                os.read(self._command_wake, 4096)
            except OSError:
                pass
        if self.commands is None:
            return
        for key, lines in self.commands.drain():
            done = self._command_jobs.pop(key, None)
            if done is not None:
                done(lines)

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
        self.trigger_level.clear()
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
                # The notification daemon is another `Text` nobody here owns,
                # and the name is the pad's own word for itself.
                "omapad", "%s connected - %s mode" % (drawable(device.name), self.mode)
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

        What the half-range costs is what `recenter_limit` is guarding: the
        nearer end is always `1 - |offset|` of the advertised half-range away,
        so calibrating on a rest 0.84 out leaves a sixth of the range to cross
        before the stick reads full - and every value past that sixth, the
        true centre included, clamps to a full deflection the stick is never
        let go of. A pad genuinely resting off centre sits at half a range
        (0.50); anything much beyond that is a thumb, not a rest.
        """
        info = self.axis_info.get(code)
        if info is None:
            self.axis_scale[code] = (0.0, 1.0)
            return
        if value is None:
            value = info.value
        offset = (value - info.center) / info.half_range
        if not self.config.recenter:
            self.axis_scale[code] = (info.center, info.half_range)
            return
        if abs(offset) >= self.config.recenter_limit:
            # A stick held at connect: centring on a held stick would freeze
            # that direction, so take the pad at its word. Logged because the
            # symptom of getting this wrong - an axis stuck at full travel -
            # says nothing about calibration on its own.
            self.axis_scale[code] = (info.center, info.half_range)
            log.info(
                "axis 0x%02x rests %+.2f off centre, past recenter_limit %.2f:"
                " not calibrating, it reads as a stick held at connect",
                code, offset, self.config.recenter_limit,
            )
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
        # A dongle that drops out mid-press never sends the release, and the
        # virtual keyboard advertises EV_REP: a key left down is auto-repeated
        # by the compositor for as long as the daemon lives. So a pad going
        # away lets go of everything it was holding, exactly as a mode switch
        # does - reset_state only forgets what the pad itself was doing.
        self.release_everything()
        self.reset_state()
        self.push_status_view()

    def apply_grab(self):
        """Take the pad, or let go of it - but wait for the hand to come off.

        A grab taken while a button is down strands that button in every other
        client: evdev feeds the grabber alone, so the release never reaches the
        app that saw the press and it goes on believing the button is held.
        That is the ordinary case rather than a rare one - the shoulder held to
        walk a workspace out of Steam is let go *after* the focus change that
        takes the pad back - and Steam then answered every Guide press with
        "skipped due to chording" for the rest of the evening, because a Guide
        press with a bumper down is a chord. Measured, in Steam's own log.

        So a wanted grab stands aside until the pad is let go, and the app sees
        both of us for that moment: a press arriving twice is worth a great
        deal less than a button stuck down for as long as the app runs.
        `grab_settle` bounds the wait, because a button the kernel believes is
        held for ever - a dongle that dropped mid-press - must not cost the
        grab outright. Letting go is never deferred: an app that gets a release
        it never saw the press of ignores it.
        """
        if self.device is None:
            return
        try:
            if self.wants_grab():
                if not self.device.grabbed and not self.pad_settled():
                    return
                self.device.grab()
            else:
                self.device.ungrab()
        except OSError as exc:
            log.warning("could not change grab state: %s", exc)
        self._grab_wait = None

    def pad_settled(self):
        """Is the hand off the pad - or has the grab waited long enough?"""
        if not self.pressed:
            self._grab_wait = None
            return True
        now = time.monotonic()
        if self._grab_wait is None:
            self._grab_wait = now + self.config.grab_settle
        return now >= self._grab_wait

    def surface_open(self):
        """Is a surface of ours on screen?

        The four are asked about together everywhere the pad is divided up -
        the grab, what a press may do, what the sticks are worth - because
        they say one thing between them: the pad is driving something of
        ours, whatever the app in front has open.
        """
        return bool(self.mapping_open or self.osk_open or self.menu_open
                    or self.guide_open)

    def wants_grab(self):
        """Should the pad be ours exclusively right now?

        Any surface of ours that is up takes it, whatever else is true: a press
        answering something on screen must not also reach the game underneath -
        that is what makes a menu summonable over a running game. Otherwise the
        pad is ours unless the app in front has opened it for itself.
        """
        if self.surface_open():
            return True
        if not self.config.grab:
            return False
        return not self.handed_over

    # -- handing the pad to whatever is in front ---------------------------

    def update_handover(self, force=False):
        """Ask whether the focused window's process has opened the pad.

        Unless its profile has already said no. `handover = false` is the
        answer for an application that opens the pad without being played
        with - /proc cannot tell those apart, and it should not try: whether
        holding this window's pad means driving this window is a fact about
        the application, and the profile is where an application is named.
        """
        self._next_handover_check = time.monotonic() + self.config.handover_poll
        if self.device is None:
            wanted = False
        elif self.locked:
            # Asked and answered by a person, which is the one answer /proc
            # cannot argue with: the lock is there for the game the walk
            # misses, and for the profile that refuses a hand-off it turns
            # out to want.
            wanted = True
        elif self.keeping:
            # The other answer a person can give, and the one /proc cannot
            # reach: the app has plainly opened the pad and is plainly doing
            # nothing with it.
            wanted = False
        elif self.active_profile and not self.active_profile["handover"]:
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

    def set_locked(self, locked):
        """Give the pad to the app in front outright, or take it back.

        The hand-off is a question about a program and this is a person
        answering it themselves, so it goes through the same door - forced,
        because it has to hold whatever the last walk of /proc decided.

        The notification names the menu because the menu is the only door
        left: a chord is the one gesture the lock lets through, and every
        other way of saying "give it back" is a button this has just switched
        off.
        """
        locked = bool(locked)
        if locked == self.locked:
            return
        self.locked = locked
        if locked:
            # The two overrides are one question with two answers, so the
            # second one asked is the one that stands. Silently, because the
            # notification below is already saying where the pad went.
            self.keeping = False
        log.info("workspace lock: %s", "on" if locked else "off")
        self.update_handover(force=True)
        if self.config.notify:
            self.session.notify(
                "omapad",
                "Workspace lock on - unlock it from the menu" if locked
                else "Workspace lock off",
            )

    def set_keeping(self, keeping):
        """Keep the pad ours over an app that has opened it, or stop.

        `set_locked`'s pair: the same question about the same window, answered
        the other way, and so the same door - forced, because it has to hold
        whatever the last walk of /proc decided.

        What it is for is the app that opens the pad before there is anything
        to play. A cloud client does it the moment its page loads, and the
        screen in front of the stream is a web page that reads no pad at all:
        the hand-off is correct about what the program did and wrong about
        what the person is looking at, and the pointer that could press Play
        has gone. Nothing announces itself, because from the pad's side
        nothing happened.

        The way back out needs no chord and no notification pointing at one -
        keeping the pad means every binding fires, so the menu is a plain
        press away. It does have to be found, though: the stream that starts
        after Play does want the pad, and this stays on until it is turned
        off.
        """
        keeping = bool(keeping)
        if keeping == self.keeping:
            return
        self.keeping = keeping
        if keeping:
            self.locked = False
        log.info("keep: %s", "on" if keeping else "off")
        self.update_handover(force=True)
        if self.config.notify:
            self.session.notify(
                "omapad",
                "Controller kept - every press drives the desktop" if keeping
                else "Controller no longer kept",
            )

    def apply_gamebar(self):
        """The bar belongs to the couch, and not over an app driving itself.

        Nor under a HUD that has printed the same row itself: a fullscreen
        menu covers the strip the bar stands in and puts its own four buttons
        in that exact band, so leaving the bar up would be two rows of words
        crossfading in one place. A card leaves the strip alone and the bar
        keeps answering for the screen around it.
        """
        self.set_gamebar(
            self.mode == "game"
            and self.config.gamebar_enabled
            and not self.handed_over
            and not (self.menu_open and self.config.menu_fullscreen)
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
        self.apply_idle()
        self.apply_cursor()
        self.apply_gamebar()
        # A surface that was up before the switch is still up, and the two
        # modes are read from different distances: redraw it at the new scale
        # instead of leaving it desk-sized on a screen across the room.
        self.push_open_views()
        self.push_status_view()
        log.info("mode: %s", mode)
        if self.config.mode_rumble:
            self.say("tick")
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
            # The bar ours stands in for can come back without us - the flag
            # it follows is a file anybody may flip, and the shell's watch on
            # it is documented as missing changes that land together - and
            # then the screen has two bars along one edge. Ours opening is the
            # moment to say again which one the screen is meant to have; the
            # command is the same one the mode switch spawns, and it names a
            # flag rather than toggling, so saying it twice costs nothing.
            self.apply_bar()
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

    def relabel_gamebar(self):
        """Repaint the bar for a layer that changed with no press behind it.

        Every hint on the bar belongs to the layer that is live, and a surface
        is a layer: opening the menu rewrites all four face buttons. A press
        repaints the bar itself (`handle_button`), but `omapad ctl` and a
        shell keybind open a surface without one, and until the next heartbeat
        the bar would be answering for the desktop underneath it.
        """
        if self.gamebar_open:
            self.push_gamebar_view()

    def refresh_workspaces(self):
        """Ask Hyprland for the workspaces, and only while the bar is up.

        Over the IPC socket rather than by spawning hyprctl: the answer comes
        back in well under a millisecond where a fork and an exec cost tens,
        and this runs on the loop. The list is still read only when the bar
        opens and when a workspace is created or destroyed - a plain switch
        carries the name it switched to, and needs no query at all.
        """
        rows, active = [], self.gamebar.active_workspace
        for command, into in (("workspaces", "list"), ("activeworkspace", "one")):
            data = self.hypr.query(command)
            if data is None:
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

    def touched(self):
        """Somebody is there: a press, a step, a thumb on a stick.

        Pad input is invisible to the compositor - walking a menu moves a
        selection over a socket and produces no Wayland input at all - which
        is why the surfaces hold an idle inhibitor while they are up. This is
        the other end of that hold: what it follows is the thumb rather than
        the surface, so a menu left open on a television stops holding the
        screensaver off all night.
        """
        self._touched = time.monotonic()
        if not self._awake:
            self._awake = True
            # The surfaces are told because each binds its inhibitor to this,
            # and the desktop because game mode asks it for `stay-awake`.
            self.push_open_views()
            self.apply_idle()

    def check_awake(self, now):
        """Has the pad been quiet long enough to hand idling back?"""
        if not self._awake or self.config.idle_awake <= 0:
            return
        if now - self._touched < self.config.idle_awake:
            return
        self._awake = False
        log.info("idle: the pad has been quiet, letting the screen go")
        self.push_open_views()
        self.apply_idle()

    def apply_idle(self, restore=False):
        """Keep the screen awake while game mode is up, and give idle back.

        Same shape and same best-effort rule as `apply_bar`: `stay-awake`
        while the game has the screen so the screensaver and lock cannot fire
        over it, `allow-idle` the moment the desktop is back. `restore` forces
        idle back on regardless of mode - the shutdown path, so a daemon that
        dies in game mode does not leave a desktop that never idles again by
        mistake.
        """
        if not self.config.stay_awake_in_game:
            return
        # A pad nobody has touched for `[idle] awake_ms` is not a game being
        # played: game mode is the couch environment rather than a session
        # somebody is in, and a television left on it all night is the one
        # screen this could cost the most.
        wanted = ("allow-idle"
                  if (restore or self.mode == "desktop" or not self._awake)
                  else "stay-awake")
        try:
            self.session.spawn("omarchy toggle idle %s" % wanted)
        except OSError as exc:
            log.warning("could not set idle %s: %s", wanted, exc)

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

    def pointer_away(self, action):
        """Take the pointer off screen for a press that is not pointing at all.

        The half of the couch problem the ring does not answer: a pointer
        stays where it was left, over whatever the press just opened, and no
        press moves it out of the way. A console shows none at all between one
        thing you point at and the next.

        The hiding is the compositor's rather than ours. Hyprland takes the
        pointer off screen at a keystroke and brings it back at the next
        movement of a mouse (`cursor:hide_on_key_press`), and a pad is a
        keyboard that does not type - so the press says so itself, with a
        keycode no layout gives a symbol to: a keystroke to the compositor and
        nothing at all to the window in front.

        Leaving both halves there is the point. Nothing here holds a "hidden"
        flag that could be wrong, a daemon that dies mid-press leaves nothing
        to put back, and what brings the pointer out again is any pointer at
        all - this one's stick, a snap, or a mouse on the desk.
        """
        if not self.config.hide_pointer or isinstance(action, POINTER_STAYS):
            return
        self.keyboard.nudge()

    def check_pointer_hiding(self):
        """Say so, once, when the compositor will not hide the pointer.

        `pointer_away` borrows `cursor:hide_on_key_press`, so a Hyprland with
        that turned off answers every press by doing nothing - which from the
        sofa looks exactly like a setting of ours that does not work. Nothing
        fails; this is the line in the log that tells the two apart.
        """
        if not self.config.hide_pointer:
            return
        answer = self.hypr.query("getoption cursor:hide_on_key_press")
        if not isinstance(answer, dict):
            return  # no compositor to ask, or a build without the option
        value = answer.get("bool", answer.get("int"))
        if value is not None and not value:
            log.warning(
                "pointer: hide_on_press has nothing to ask - Hyprland's "
                "cursor:hide_on_key_press is off, so the pointer stays on "
                "screen whatever is pressed"
            )

    def toggle_mode(self):
        self.set_mode("game" if self.mode == "desktop" else "desktop")

    # -- state -------------------------------------------------------------

    def reset_state(self):
        self.pressed.clear()
        self.gamebar.pressed = []
        self.active_chords.clear()
        self.trigger_down.clear()
        self.trigger_level.clear()
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
        # A held effect is a finger's, the same as a held key: a hum left
        # running across a mode switch is the tick that sticks on arriving
        # through a door with no press to blame it on.
        self.rumble.stop_held()
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
        # A page of the menu may spend X and Y on a job of its own, and while
        # it is the page in front that is what those buttons do. Asked first,
        # and cached per page: what a page spends never changes, but which
        # page is in front does.
        if layer == "menu" and self.menu_open:
            # Rearranging first: it is a mode inside this surface, and while
            # it is on it outranks both the page's own keys and the layer's.
            spec = EDIT_KEYS.get(button) if self.menu.edit else None
            if spec is None:
                spec = self.menu.page_keys().get(button)
            if spec is not None:
                return self.page_key_binding(button, spec)
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
                binding = (actions.Binding(spec, self.config.announced_hold,
                                           self.config.confirm_scale)
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

    def page_key_binding(self, button, spec):
        key = (self.menu.page_name(), button)
        if key not in self.page_keys:
            try:
                binding = actions.Binding(spec, self.config.announced_hold,
                                          self.config.confirm_scale)
            except actions.ActionError as exc:
                # `omapad check` names it; here the page simply keeps what the
                # layer said, which is the menu's own X and Y.
                log.error("bad menu page key %s: %s", button, exc)
                self.page_keys[key] = None
            else:
                binding.layer = "menu"
                self.page_keys[key] = binding
        return self.page_keys[key]

    def menu_key_spec(self, button):
        """The spec in force for one face button on the page in front.

        The page's own where it has one, the menu layer's otherwise. What the
        legend prints and what a press does have to come from the same place,
        or the legend is a second answer.
        """
        if self.menu.edit and button in EDIT_KEYS:
            return EDIT_KEYS[button]
        spec = self.menu.page_keys().get(button)
        if spec is not None:
            return spec
        return self.config.binding_with_profile(
            self.active_profile, "menu", button
        )

    def menu_legend(self):
        """What each face button does on this page, for the foot of the card.

        The guide already turns a binding into words and the bar already reads
        them short; this is the same pair one surface along, so a legend that
        disagreed with either would be the odd one out rather than the truth.
        """
        if not self.config.menu_keys:
            return []
        available = self.available_buttons()
        rows = []
        for button in (EDIT_LEGEND if self.menu.edit else MENU_LEGEND):
            if available is not None and button not in available:
                continue
            row = guide_module.button_row(
                button, self.menu_key_spec(button), self.guide.layout, True
            )
            if row is None:
                continue
            word = row["d"]
            if button == self.config.confirm_cancel \
                    and self._menu_countdown is not None:
                # While a row is counting, B is not the way back out of the
                # page - it is the way to stop what is about to happen, and
                # the row printing a number is no use to somebody who does
                # not know which button takes it back.
                word = "Cancel"
            if button == "A" and self.menu_holds():
                # The one tile where A is not a press. Said before it is
                # pressed rather than found out by pressing: this row is the
                # page's own line about its buttons, and a button that means
                # something else on the tile in front is exactly what it is
                # for.
                word = "Hold to confirm"
            rows.append({"b": row["b"], "k": row["k"], "n": word})
        return rows

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
        # And the address is forgotten first: focus can have moved while the
        # stream was down, so the next one to arrive has to count as new even
        # if it names the window that was in front before the drop.
        self._hypr_window = None
        self.seed_active_window()
        return True

    def seed_active_window(self):
        """Ask Hyprland which window is focused, to seed the profile.

        Called once on connect and again on reconnect, because subscribing to
        the event socket does not replay the current state.
        """
        info = self.hypr.query("activewindow")
        if not isinstance(info, dict):
            return
        self.focus_pid = info.get("pid") or None
        if info.get("class"):
            self.set_focus(
                str(info["class"]).strip(),
                str(info.get("title") or "").strip(),
            )
        # Asked after the class and not before it: a profile may refuse the
        # hand-off outright, and the profile is what set_focus swaps in. The
        # other way round, every focus change answered for the window that
        # had just left.
        self.update_handover()

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
            elif text.startswith("activewindowv2>>"):
                # **The same moment, told twice, and this is the half with the
                # window's identity in it.** Hyprland sends both lines for a
                # focus change - and both again every time the window in front
                # renames itself, which a terminal does while a command runs
                # and a browser does on every tab. `activewindow` cannot tell
                # those apart: its class and title are all a renamed window
                # has changed. So the class and the title are taken from it as
                # they arrive, and the question that costs something - a walk
                # of every open file descriptor in /proc, ~5 ms - is asked
                # here, only when the address differs from the last one.
                #
                # A compositor that sends no `activewindowv2` still hands the
                # pad over: `[mode] handover_poll` asks the same question on a
                # timer, so what is lost is the promptness, not the answer.
                window = text[len("activewindowv2>>"):].strip()
                if window != self._hypr_window:
                    self._hypr_window = window
                    # The event carries no pid, and who owns the pad is a
                    # question about the process rather than the class.
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
        in between. Past the ttl the command runs off the loop, so this
        answers with what the page held last and the fresh reading replaces it
        when it lands - a shell history that is slow to read must not be a
        keyboard that is slow to appear.
        """
        cached = self._osk_page_cache
        if (cached is not None and cached[0] == self.active_profile_name
                and time.monotonic() < cached[1]):
            return cached[2]
        if not page["from"]:
            # Nothing to read: the page is its own keys, and there is no
            # reading for the ttl to be about.
            return self.osk_page_entries(page, [])
        self.refill_osk_app_page(page)
        # Read again rather than trusting `cached`: with no worker the reading
        # happened inside that call, and the answer it just filed is the fresh
        # one this asked for.
        cached = self._osk_page_cache
        if cached is not None and cached[0] == self.active_profile_name:
            return cached[2]
        return self.osk_page_entries(page, [])

    def osk_page_entries(self, page, lines):
        """The page's own keys, then whatever its command printed."""
        entries = list(page["keys"])
        entries += [{"label": line, "text": line} for line in lines]
        return entries[: page["limit"]]

    def refill_osk_app_page(self, page):
        """Read the page's command in the worker and hand it the answer.

        One reading in flight per profile: the keyboard can be opened and
        closed faster than a history file is read, and a queue of the same
        command would land the same answer several times over.
        """
        name = self.active_profile_name
        if self._osk_page_job == name:
            return

        def fill(lines):
            if self._osk_page_job == name:
                self._osk_page_job = None
            if name != self.active_profile_name:
                return  # the app in front changed while the command ran
            entries = self.osk_page_entries(page, lines)
            self._osk_page_cache = (
                name, time.monotonic() + page["ttl"], entries
            )
            self.osk.set_app_page(page["label"], entries)
            if self.osk_open:
                self.push_osk_view()

        self._osk_page_job = name
        if not self.submit_command(page["from"], fill):
            self._osk_page_job = None
            fill(self.session.capture(page["from"]))

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
        self.relabel_gamebar()
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

    def view_motion(self):
        """How long the surfaces may take to move.

        Two answers, and the desktop's is a **veto rather than a scale**: it
        can take motion away and never add it, so a person who has set
        `[ui] motion = 0` is still answered on a desktop that animates, and
        one who has left it at 1 is answered by the desktop that does not.
        Multiplying the two would make the same claim in a way that reads as
        arithmetic instead of as a rule.
        """
        if self.config.ui_motion_follows_desktop and not self._desktop_animates:
            return 0.0
        return self.config.ui_motion

    def read_desktop_motion(self):
        """Ask the compositor whether it animates anything. True when changed.

        `animations:enabled` is this desktop's own answer to the question
        `[ui] motion` asks, given about every window on screen - the same
        standing this program gives `decoration:rounding` and `gaps_out`, one
        property along. No compositor to ask leaves the last answer alone:
        the surfaces keep moving rather than freezing because a socket went.
        """
        answer = self.hypr.query("getoption animations:enabled")
        if not isinstance(answer, dict):
            return False
        value = answer.get("bool", answer.get("int"))
        if value is None:
            return False  # a build without the option is not a desktop saying no
        animates = bool(value)
        if animates == self._desktop_animates:
            return False
        self._desktop_animates = animates
        log.info("the desktop %s animations; the surfaces follow",
                 "allows" if animates else "has turned off")
        return True

    def view_safe(self):
        """How much of the screen's edge the surfaces keep clear.

        Game mode only, and that is the whole of the rule: a television is
        the one screen that crops its own edges, and game mode is the only
        time this program is looking at one. A desk monitor draws every pixel
        it is sent, so a gap kept there is a gap for nothing.
        """
        if self.mode == "game":
            return self.config.ui_safe_area
        return 0.0

    def scaled(self, state):
        """One surface payload, stamped with how it should be drawn.

        None of these is one surface's own state - they are the scale, the
        style its badges take and what else is standing on the screen - and
        none of them can be read by a panel, so they are stamped in one place
        rather than remembered by six callers.
        """
        if isinstance(state, dict):
            state["scale"] = self.view_scale()
            state["badge"] = self.config.ui_badge_style
            # How long everything on it takes to move. Beside the scale
            # because it is the same kind of answer - how this surface is
            # drawn rather than what it holds - and because a person who has
            # turned motion off has turned it off on every surface at once.
            state["motion"] = self.view_motion()
            # And how much of its edge it keeps clear. A share rather than a
            # measurement, because what a television crops is a proportion
            # of the picture rather than a number of pixels.
            state["safe"] = self.view_safe()
            # Whether our own bar is holding a strip of the screen. A surface
            # that dims the desktop behind it must not dim that strip: the bar
            # is printing what the face buttons do *in the surface standing on
            # top of it*, and a legend read through a scrim is the last thing
            # on screen that should go dark.
            state["bar"] = self.gamebar_open
            # Whether this surface may still hold the screen awake. True of
            # every surface at once, because what it answers is whether
            # anybody is holding the pad rather than what is on screen.
            state["awake"] = self._awake
            # How hard a corner is rounded, against the desktop's own answer.
            # Beside the scale because it is the same kind of thing - how this
            # surface is drawn rather than what it holds - and because a
            # person who has rounded one of them has rounded all of them.
            state["radius"] = self.config.ui_radius
        return state

    def show_ripple(self, button):
        """Draw where a click just landed. False when nothing was drawn.

        Best-effort twice over - the compositor may not answer where the
        pointer is, the plugin may not be up - and neither is a reason for the
        click itself to have gone anywhere but through, which is why this is
        called after the button is already down.
        """
        if not self.config.ripple_enabled:
            return False
        if not self.ripple.mark(button, self.hypr.cursor_position()):
            return False
        self.ripple_client.send(self.scaled(self.ripple.view_state()))
        return True

    def say(self, name, rumble=True):
        """One press, answered in both the ways this program can answer it.

        The motor and the speakers are two things saying one word, so they
        are said together and named once at the call site: a moment that
        ticked but did not click would be two vocabularies to keep in step by
        hand, which is how they stop being in step.

        `rumble=False` is the one asymmetry, and `move` is why it exists: a
        motor that ticked on every step of a held direction buzzes the whole
        way down a list, and a speaker doing the same thing ticks, because a
        sound decays and a vibration does not.

        Best-effort at both ends - a pad with no motor, a shell that is not
        up - and neither is a reason for the press itself to have gone
        anywhere but through.
        """
        if rumble:
            # The motor says the nearest thing it has. `move` and `back` are
            # the two words it does not hold, and both are a press, so both
            # tick: the hands feel that something happened and the speakers
            # are what say which. See sound.py.
            self.rumble.play(
                "tick" if name in ("move", "back") else name)
        if not self.config.sound_enabled:
            return False
        if not self.sound.say(name):
            return False
        self.sound_client.send(self.sound_state())
        return True

    def sound_state(self):
        """The cue, with where its files live.

        Not through `scaled()`: nothing here is drawn, so a scale, a badge
        style and whether a bar is up are three answers to questions this
        payload does not ask. `dir` rides every line because there is no
        heartbeat to carry it on its own.
        """
        state = self.sound.view_state()
        state["dir"] = self.config.sound_pack
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
            # Toggled shut is closed: MINUS is the same button going the other
            # way, and a button that answered on the way in and said nothing
            # on the way out would be the surface keeping half a promise.
            if self.osk_open:
                self.say("back")
            self.set_osk(not self.osk_open)
            return
        if command == "open":
            self.set_osk(True)
            return
        if command == "close":
            if self.osk_open:
                self.say("back")
            self.set_osk(False)
            return
        if not self.osk_open:
            return  # navigation means nothing while the keyboard is down

        model = self.osk
        if command in ("up", "down", "left", "right"):
            # Heard, never felt, and the keyboard is the surface that makes
            # the case: crossing it is a dozen steps under a held direction,
            # which is a dozen ticks nobody would leave the motor on for.
            if command == "up":
                model.move_vertical(-1)
            elif command == "down":
                model.move_vertical(1)
            elif command == "left":
                model.move_horizontal(-1)
            else:
                model.move_horizontal(1)
            self.say("move", rumble=False)
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
        # A row counting down belongs to the page it is on. The menu going
        # away is not somebody deciding against it, so it is not announced as
        # a cancel - it simply stops, the way the hold does when the surface
        # holding it closes.
        self.menu_disarm()
        self.menu_uncount()
        if not opened:
            # Whatever was being pushed stops being pushed. Written down here
            # rather than lost: the menu closing is one of the four ways to
            # let go of a control, and the only one that takes the tile
            # showing the number away with it.
            self.menu.release()
            self._menu_before = None
            self.menu_settle(force=True)
            # Nothing is asked while the menu is shut, so nothing is due when
            # it opens again: what the machine was doing a minute ago is not
            # what it is doing now.
            self._live_poll.clear()
            self._live_due.clear()
            # Where it was, for the next press.
            self._menu_where = self.menu.where()
        if opened:
            # What a row is allowed to ask about is read here, before the
            # first level is built, and stands for as long as the menu is up.
            self.menu.conditions = self.menu_conditions()
            # A first start is answered once, and being shown it is what
            # answers it: the conditions a line above are already read and
            # stand for as long as this menu is up, so the `Start here` tile
            # keeps its place for this opening and is gone by the next.
            #
            # Not through `set_setting`: there is nothing to apply, nothing to
            # repaint, and a notification saying a mark had been written is
            # the machine talking about itself.
            if self.config.menu_first_run:
                self.config.set_setting("first_run", ("set", False))
                self.save_settings()
                log.info("menu: first run answered")
            # Back where it was, or the first tile of the first chip. Most of
            # what a HUD is for is coming back: you turn the volume down, go
            # back to the game, and come back to turn it down again.
            self.menu.reset(self._menu_where)
            self.menu_group_enter()
            self.menu_head_refresh()
            self.menu_meta_refresh()
            # Both surfaces read the D-pad, and stacking the menu over the
            # keyboard leaves no way to tell which one a press belongs to.
            self.set_osk(False)
            # Before the menu is pushed, never after: the bar stands in the
            # band a fullscreen HUD prints its own row of hints in, and two
            # rows of words crossfading in one place is what reads as a
            # flicker when the menu opens.
            self.apply_gamebar()
        self.push_menu_view()
        if not opened:
            # And back afterwards, for the same reason the other way round.
            self.apply_gamebar()
        self.apply_grab()
        self.relabel_gamebar()
        log.info("menu: %s", "open" if opened else "closed")

    def menu_conditions(self):
        """Which of the states a menu row may wait for are true right now.

        The row this exists for is the workspace lock, which has nothing to
        lock to on a desktop: offering it there is a way to hand the pad to a
        terminal and then have to find the menu again to take it back. Game
        mode is the couch, and a pad the app in front has already taken is a
        game whether or not anyone switched modes - either is enough.

        `first_run` is the other kind: true until the menu has been opened
        once, which is what puts the `Start here` tile in front of somebody
        who has never held this pad before.
        """
        states = set()
        if self.mode == "game":
            states.add("game")
        if self.handed_over:
            states.add("handed_over")
        if self.locked:
            states.add("locked")
        if self.keeping:
            states.add("kept")
        if self.config.menu_first_run:
            states.add("first_run")
        return frozenset(states)

    def push_menu_view(self):
        self._menu_next_heartbeat = time.monotonic() + VIEW_HEARTBEAT
        state = self.menu.view_state(
            self.menu_open, self.action_state, self.action_value,
            self._menu_head_text, self.menu_legend(), self.menu_control,
            self._menu_meta_text
        )
        # Stamped here rather than in the model: whether the card fills the
        # screen is a setting, and `menu.py` holds state and geometry and
        # reads no config. Not in `scaled()` either - that is for what is true
        # of every surface, and this is true of one.
        # Which row is being held down towards running, and how far it has
        # got. Stamped rather than in the model for the reason the rest of
        # these are: the two waits are `[confirm]`'s, and `menu.py` reads no
        # config. Absent while nothing is held.
        confirming = self.menu_confirm_state()
        if confirming is not None:
            state["confirm"] = confirming
        # And which row is counting down, with how many whole seconds are
        # left. The same shape and the same reason: the length is `[menu]
        # countdown`'s and `menu.py` reads no config. Absent while nothing is
        # counting, which is what ends one on the panel's side.
        left = self.menu_countdown_left()
        if left is not None:
            state["count"] = {"id": self._menu_countdown["id"], "left": left}
        state["full"] = self.config.menu_fullscreen
        state["dim"] = self.config.menu_dim
        # How much of a tile's corner is drawn art. Travels even though it
        # looks like a shell constant, for the reason every geometry setting
        # does: the shell cannot read the config.
        state["corner"] = self.config.menu_tile_corner
        # And how long a tile stays lit once a press has landed on it. The
        # model says which tile and which press; how long is a setting, and
        # `menu.py` reads no config.
        state["press_ms"] = self.config.menu_press_ms
        # And how tall a cell is, for the same reason: `columns` decides the
        # width of one and this decides the rest of it, and neither is
        # something the panel can look up.
        state["cell"] = self.config.menu_cell
        # How tall the game bar is, so a fullscreen HUD can put its own row of
        # hints in exactly the band the bar's row sits in. The buttons must
        # not move when the menu opens: it is the same four words about the
        # same four buttons, and a row that jumped an inch up the screen would
        # read as a different row.
        state["barh"] = self.config.gamebar_height
        self.menu_client.send(self.scaled(state))

    def menu_head_refresh(self):
        """Ask each head cell's command for anything that has gone stale.

        Off the loop, like every other command, and only while the menu is up:
        a daemon nobody is looking at must not spawn a weather lookup forever.
        `ttl` is how long an answer stays fresh, which is not the heartbeat -
        the surface redraws every couple of seconds and the weather is asked
        for every quarter of an hour.
        """
        if not self.menu_open:
            return
        now = time.monotonic()
        for cell in self.menu.head:
            # Every line of a cell, not the cell: a clock can carry a name
            # over it and a weekday under it, and the name is a command like
            # the weather is. `head_sources` is what knows that shape.
            for line in head_sources(cell):
                due = self._menu_head_due.get(line["id"], 0.0)
                if due and now < due:
                    continue
                # Written before the answer lands, so a command that takes
                # longer than its own ttl is not asked twice over.
                self._menu_head_due[line["id"]] = now + max(line["ttl"], 1.0)
                self.menu_head_read(line)

    def menu_meta_refresh(self):
        """Ask each group's `meta` command for anything that has gone stale.

        `menu_head_refresh` for the bar, and the same two rules: off the loop,
        and only while the menu is up. What is different is how many there
        are - a head has two or three lines and a bar has one per group - so a
        `ttl` here is not optional politeness. A group that reads a sink every
        redraw is eight subprocesses a second for a row of two-word labels.
        """
        if not self.menu_open:
            return
        now = time.monotonic()
        for meta in meta_sources(self.menu.groups):
            due = self._menu_meta_due.get(meta["id"], 0.0)
            if due and now < due:
                continue
            # Written before the answer lands, so a command slower than its
            # own ttl is not asked twice over.
            self._menu_meta_due[meta["id"]] = now + max(meta["ttl"], 1.0)
            self.menu_meta_read(meta)

    def menu_meta_read(self, meta):
        def took(lines):
            text = " ".join(part.strip() for part in lines if part.strip())
            if text:
                # A command that printed nothing leaves the last answer where
                # it is: a blank card says less than a stale one.
                self._menu_meta_text[meta["id"]] = text
                if meta["ttl"] <= 0:
                    self._menu_meta_due[meta["id"]] = float("inf")
            elif meta["empty"]:
                # Unlike a head line: a bar that went quiet has somewhere to
                # say so, and `empty` is the word for it.
                self._menu_meta_text.pop(meta["id"], None)
            self.push_menu_view()

        if not self.submit_command(
            meta["from"], took, self.config.menu_list_timeout
        ):
            took(self.session.capture(
                meta["from"], self.config.menu_list_timeout
            ))

    def menu_head_read(self, line):
        def took(lines):
            text = " ".join(part.strip() for part in lines if part.strip())
            if text:
                # A command that printed nothing leaves the last answer where
                # it is: a blank cell says less than a stale one.
                self._menu_head_text[line["id"]] = text
                if line["ttl"] <= 0:
                    # Zero is a line that never goes stale - a name, a
                    # hostname - so its answer is kept for the session. Set
                    # here rather than above, so a command that failed is
                    # asked again rather than the cell being empty until the
                    # daemon restarts.
                    self._menu_head_due[line["id"]] = float("inf")
            self.push_menu_view()

        if not self.submit_command(
            line["from"], took, self.config.menu_list_timeout
        ):
            took(self.session.capture(
                line["from"], self.config.menu_list_timeout
            ))

    def menu_fill(self, item):
        """Read a listed row's submenu from its command, if it is one.

        The command runs off the loop, so a device listing that has wedged is
        a page that fills late rather than a pad that has stopped answering;
        `menu.list_timeout_ms` is how long the worker waits before calling it
        empty. The press enters the page either way and the rows land in it
        when the answer does - which for a page entered before means the rows
        it held last, rather than a blink of nothing.

        A command that fails prints nothing, and an empty page says so.
        """
        if not item or not item.get("from"):
            return
        # A page that lists, or a **card** that does. The difference is only
        # which list the answer lands in: a submenu's rows are the page you
        # are about to be on, and a card's are drawn where they stand.
        held = (item["rows"] if item.get("control") == ROWS
                else item["items"])

        def fill(lines):
            try:
                # In place: the model is already drawing this very list, and a
                # fresh one bound here would be a page nobody is looking at.
                held[:] = listed(
                    item, lines, self.config.menu_list_limit
                )
            except MenuError as exc:
                # A page that will not build must not take the menu down.
                log.error("menu: %s", exc)
                return
            # The page was placed while it was empty, so it has to be placed
            # again now it is not.
            self.menu.repack()
            self.push_menu_view()

        if not self.submit_command(
            item["from"], fill, self.config.menu_list_timeout
        ):
            fill(self.session.capture(
                item["from"], self.config.menu_list_timeout
            ))

    def menu_select(self, index):
        """Jump the selection to one row - what a pointer hovering asks for.

        `menu_command` walks the list one step at a time, which is the shape
        of a D-pad press, not of a cursor. Nothing happens while the menu is
        down, the same rule navigation follows.
        """
        if not self.menu_open:
            return
        self.menu.select(index)
        self.push_menu_view()

    def menu_select_row(self, name):
        """Jump the row cursor inside the card in front, the way a pointer does.

        Two calls rather than one - the tile, then the row - because a cursor
        crossing from one card into another is two things changing, and a verb
        that took both would have to know the order they changed in.
        """
        if not self.menu_open:
            return
        self.menu.select_row(name)
        self.push_menu_view()

    def menu_control(self, item):
        """What a control tile is on, for the payload it is drawn from.

        `menu.py` holds state and geometry; what a setting holds is the
        config's, so this is the half that knows.
        """
        source, name = item["reads"]
        if source == "live":
            return self.live_control(item, name)
        if source == "sys":
            return self.sys_control(item)
        if source != "pad":
            return None
        try:
            value = self.config.setting(name)
        except KeyError:
            # A setting that has gone away under a config someone edited. The
            # tile draws bare rather than taking the menu down with it.
            log.warning("menu: nothing called %r to read", name)
            return None
        if item["control"] == "toggle":
            return {"on": bool(value)}
        if item["control"] == "gauge":
            return self.menu_gauge(item, name)
        if item["control"] == "slider":
            return self.slider_fields(CHOSEN[name], value,
                                      self.setting_words(name, value))
        return {"t": self.setting_words(name, value)}

    def menu_activate(self, item):
        """A on a control tile. One press is the whole of it.

        A switch has two states and a choice is a short list, so A acting is
        the answer and there is nothing to enter: taking a two-state control
        in order to then push it sideways is a mode nobody needed. What wants
        taking is a control with a range, and that arrives with one.
        """
        source, name = item["reads"]
        if item["control"] == "readout":
            # The one tile that is not a control. What the machine is doing is
            # published rather than set, so there is nothing here to commit
            # to - and a press that quietly did nothing else is better than
            # one that found something to do.
            return
        if source == "live":
            # What is playing has two states like a switch does, so A does the
            # same thing to it: the transport's two other marks are two more
            # tiles, and a tile costs nobody a reflex.
            if item["control"] == "media":
                self.live_write(name, ("do", "playPause"))
            else:
                self.live_write(name, ("toggle", None))
            return
        if source != "pad":
            return
        if item["control"] == "toggle":
            self.set_setting(name, ("toggle", None))
        else:
            self.set_setting(name, ("step", 1))

    # -- what the machine is doing -----------------------------------------

    def live_names(self, selected_only=False):
        """Which live readings the page in front is showing."""
        names = []
        for tile in self.menu.tiles:
            item = tile["item"]
            if not item["reads"] or item["reads"][0] != "live":
                continue
            if selected_only and item["id"] != self.menu.selected:
                continue
            if item["reads"][1] not in names:
                names.append(item["reads"][1])
        return names

    def live_read(self, names):
        """Ask the machine what it is doing, off the loop.

        One question in flight per reading: a helper that has wedged must not
        collect a queue of identical questions behind it, and the answer to
        the first is the answer to all of them.
        """
        for name in names:
            if name in self._live_asking:
                continue
            command, generation = self.live.ask(name)
            if command is None:
                continue
            self._live_asking.add(name)
            done = self._live_took(name, generation)
            timeout = self.config.live_timeout
            if not self.submit_command(command, done, timeout):
                done(self.session.capture(command, timeout))

    def _live_took(self, name, generation):
        def took(lines):
            self._live_asking.discard(name)
            if self.live.took(name, lines, generation) and self.menu_open:
                self.push_menu_view()
        return took

    def live_refresh(self, now):
        """Ask again for whatever is due. Called from the loop, menu up only.

        Three reasons to ask. A reading that has appeared on the page in front
        and has never been asked - which covers the menu opening, a chip
        walked to and a page drilled into, in one place rather than three call
        sites. One whose tile is *selected* and whose last answer is
        `[live] poll_ms` old; not everything on the page, and not at gauge
        rate, because a couch does not need the volume to track a keyboard
        nobody is at. And one a press has just written, asked once
        `[live] settle_ms` later, by which time the helper has landed.
        """
        if not self.menu_open:
            return
        selected = self.live_names(selected_only=True)
        names = []
        for name in self.live_names():
            due = self._live_due.get(name)
            if due is not None:
                if now >= due:
                    names.append(name)
                continue
            if name not in self._live_poll:
                names.append(name)
            elif name in selected and now >= self._live_poll[name]:
                names.append(name)
        for name in names:
            self._live_due.pop(name, None)
            self._live_poll[name] = now + self.config.live_poll
        if names:
            self.live_read(names)

    def live_write(self, name, asked):
        """Change what the machine is doing. True where anything was sent.

        The value moves on the tile at the press rather than a round trip
        later, and the generation counter is what keeps that honest: a read
        started before this can land after it, and would rewind the bar for a
        tenth of a second - a flicker nobody can reproduce.
        """
        command, value = self.live.apply(name, asked)
        if command is None:
            # Nothing to send. Either the machine has no such command, or the
            # value is already what it was asked to be - which for a number is
            # the end of its travel, and is what that tick is for.
            if value is not None or asked[0] == "do":
                self.menu_edge()
            return False
        if not self.submit_command(command, _nothing,
                                   self.config.live_timeout):
            # No worker to run it in, so it is run on the loop - a daemon that
            # could not make a pipe is slower, not broken.
            self.session.capture(command, self.config.live_timeout)
        # Asked again once, after the helper has had time to land: what it
        # actually did is the machine's answer rather than ours.
        self._live_due[name] = time.monotonic() + self.config.live_settle
        if self.menu_open:
            self.push_menu_view()
        return True

    def live_control(self, item, name):
        """What a live tile is on, for the payload it is drawn from."""
        value = self.live.value(name)
        control = item["control"]
        if control == "toggle":
            return {"on": bool(value)}
        if control == "media":
            return self.media_control(item, value)
        spec = live_module.READINGS[name]
        return self.slider_fields(spec, value, live_module.text(name, value))

    # -- what the machine underneath is doing ------------------------------

    def sys_control(self, item):
        """What a readout tile prints, or None where nothing has answered.

        None is drawn by leaving the tile out: a fan this machine publishes no
        number for is not a tile saying nothing, it is no tile. The menu draws
        the same answer as a line under the label, because a page of readings
        should look the same in both places it appears.
        """
        source, name = item["reads"]
        if source != "sys":
            return None
        words = self.sysinfo.words(name)
        if not words:
            return None
        found = {"t": words}
        share = self.sysinfo.fraction(name)
        if share is not None:
            # A percentage has a bar to draw and a temperature does not: the
            # top of a thermometer's scale is a number somebody would have to
            # invent, and a bar drawn against an invented maximum says a
            # different thing on every machine.
            found["v"] = round(share, 3)
        return found

    def sys_names(self):
        """Which readings are being drawn right now, in one list.

        Nothing is asked for a reading nobody can see. The HUD is one place
        they appear and a page of readouts in the menu is the other, and it is
        usually the same page in both - so the two are merged rather than
        polled separately.
        """
        names = []
        if self.hud_open:
            names.extend(self.hud.names())
        if self.menu_open:
            for tile in self.menu.tiles:
                item = tile["item"]
                if not item["reads"] or item["reads"][0] != "sys":
                    continue
                name = item["reads"][1]
                if name not in names:
                    names.append(name)
        return names

    def sys_refresh(self, now):
        """Ask again for whatever is due. Called from the loop.

        Everything this side can answer is a file read out of procfs or sysfs
        - microseconds, nothing to wait on - so it happens here rather than in
        the worker. A `cmd:` source is the exception and goes the way every
        other command does.
        """
        names = self.sys_names()
        if not names:
            # Nothing on screen wants them, so nothing is owed an answer and
            # nothing is remembered as asked: what the machine was doing a
            # minute ago is not what it is doing now.
            self._sys_poll.clear()
            return
        changed = False
        for name in names:
            due = self._sys_poll.get(name)
            if due is not None and now < due:
                continue
            self._sys_poll[name] = now + self.config.sysinfo_poll
            command = self.sysinfo.command(name)
            if command is None:
                changed = self.sysinfo.read(name) or changed
            else:
                self.sys_ask(name, command)
        for name in list(self._sys_poll):
            if name not in names:
                self._sys_poll.pop(name, None)
        if changed:
            self.push_sys_views()

    def sys_ask(self, name, command):
        """Run one reading's helper, off the loop.

        One question in flight per reading, for `live_read`'s reason: a helper
        that has wedged must not collect a queue of identical questions behind
        it, and the answer to the first is the answer to all of them.
        """
        if name in self._sys_asking:
            return
        self._sys_asking.add(name)

        def took(lines):
            self._sys_asking.discard(name)
            if self.sysinfo.answered(name, lines):
                self.push_sys_views()

        timeout = self.config.sysinfo_timeout
        if not self.submit_command(command, took, timeout):
            took(self.session.capture(command, timeout))

    def push_sys_views(self):
        """Redraw whatever is showing a reading that just moved."""
        if self.hud_open:
            self.push_hud_view()
        if self.menu_open:
            self.push_menu_view()

    def push_hud_view(self):
        self._hud_next_heartbeat = time.monotonic() + VIEW_HEARTBEAT
        state = self.hud.view_state(self.hud_open, self.sys_control)
        # The tile's corner is the menu's setting, because a tile is the same
        # shape in both places. Its *height* deliberately is not: the menu's
        # `cell_height` is a number of pixels down from the top of a page that
        # scrolls, and this grid has to end at the bottom of the screen. The
        # panel divides by `rows` instead, which is the whole of "a cell here
        # is a share rather than a measurement".
        state["corner"] = self.config.menu_tile_corner
        # Where the grid starts, so the corner a tile was carried into is the
        # corner of the screen rather than of some inset box.
        state["margin"] = self.config.hud_margin
        # How solid it is over what is behind it, which is the one thing this
        # surface decides for itself.
        state["opacity"] = self.config.hud_opacity
        self.hud_client.send(self.scaled(state))

    def hud_rearranged(self):
        """The page the readings draw has been rearranged, so pack it again.

        **The same arrangement is not the same packing.** `MenuModel` and
        `HudModel` share one `layout` dict, one page and one packer, which is
        what makes a tile carried in edit mode move in both places - but each
        holds the cells it last worked out, and nothing was telling this one
        to work them out again. So an arrangement made while the readings were
        on screen reached the file and reached the menu, and reached the
        screen only the next time they were switched on.

        Called from every place the menu mutates the arrangement rather than
        from where it is written down: the file is written when edit mode is
        left, and what somebody is looking at must not wait for that.
        """
        if not self.hud_open:
            # `set_hud(True)` packs on the way up, so an arrangement made
            # while they are off is picked up when they come back.
            return
        self.hud.repack()
        self.push_hud_view()

    def set_hud(self, on):
        """Put the readings on screen, or take them away.

        No grab, no layer and no surface to close first: this one reads
        nothing and stands in front of nothing. It is the only surface whose
        state is a setting, which is what makes it survive a restart.
        """
        on = bool(on)
        if on == self.hud_open:
            return
        self.hud_open = on
        if on:
            # Packed again on the way up: a page rearranged while the HUD was
            # off is rearranged when it comes back.
            self.hud.repack()
        else:
            self._sys_poll.clear()
        self.push_hud_view()
        log.info("hud: %s", "on" if on else "off")

    def media_control(self, item, found):
        """What is playing, as the fields a media tile draws.

        The daemon maps it rather than the reading reaching the wire as it
        arrived: an MPRIS field name is not a payload field name, and a rename
        upstream must not silently become a rename on the wire. Both strings
        go through `drawable` - a track title comes from outside this machine
        exactly as a sink description does.
        """
        if not found or not found.get("player"):
            return {"d": item["empty"], "on": False}
        # `canGoNext` and `canGoPrevious` are read and are not drawn: they
        # decide whether a press that way ticks `edge` instead of doing
        # nothing quietly, and a mark on screen that cannot be pressed would
        # be a third way to say what the tick already says.
        return {
            "l": drawable(found["title"]) or item["label"],
            "d": drawable(found["artist"]),
            "on": bool(found["playing"]),
        }

    def slider_fields(self, spec, value, words):
        """A bar's payload: where along it, and the real number beside it.

        Normalised here so the panel never sees a minimum or a maximum and
        cannot get the arithmetic wrong.
        """
        if value is None:
            return {"t": words}
        share = setting_share(spec, value)
        fields = {"v": round(max(0.0, min(1.0, share)), 3), "t": words}
        stops = spec.get("stops")
        if stops:
            # A ladder is drawn in its own stops rather than as a length: the
            # bar is that many segments and this many of them are filled, so
            # what the eye reads is which stop out of how many. A share alone
            # would be a bar four pixels further along than the last press
            # left it, on a control whose whole point is that it has places to
            # be rather than a distance to cover.
            fields["seg"] = len(stops)
            fields["at"] = nearest_stop_index(stops, value)
        return fields

    def menu_gauge(self, item, name):
        """A gauge's fields: the bar's two, plus the zone it shades.

        `z` is the dead zone as a fraction of the stick's own travel, which is
        not the same number as `v`: `v` is where the setting sits in its
        range, and the disc has to be drawn at the radius the stick actually
        loses. It rides on the **full** push rather than the live one - it is
        a setting, it changes only when something presses, and putting it in
        the stream would send it sixty times a second to say the same thing.

        Where the dot is does not come through here at all: that is no
        setting, and carrying it with the rest of the surface would rebuild
        every tile on the page to move one dot.
        """
        spec = CHOSEN[name]
        value = self.config.setting(name)
        fields = self.slider_fields(spec, value,
                                    self.setting_words(name, value))
        fields["z"] = round(self.config.stick_deadzone(item["shows"]), 3)
        return fields

    def menu_live(self):
        """Where the watched thumb is, quantised, or None for nothing to say.

        Read off `self.axes` **raw**, before the response curve: the curve
        exists to make small deflections aim finely, and this asks where the
        thumb is rather than how fast to move a pointer. A gauge drawn through
        the curve would show a stick resting somewhere it is not.

        Rounded to three places, and not as a noise filter: it is what makes
        the panel's own "same line as last time" guard work, so a hand off the
        pad stops the stream instead of streaming jitter.
        """
        if not self.menu_open:
            return None
        stick = self.menu.watching()
        if not stick or stick not in STICK_AXES:
            return None
        code_x, code_y = STICK_AXES[stick]
        return {
            "x": round(self.axes[code_x], 3),
            "y": round(self.axes[code_y], 3),
        }

    def push_menu_live(self, now):
        """Send the gauge frame, at most `[menu] live_hz` times a second.

        Rate limited off its own deadline here rather than from a timer:
        `live_hz` is a scheduler parameter, and the loop is already turning at
        `poll_hz` because `needs_tick` says a gauge is up.
        """
        if now < self._menu_live_due:
            return
        live = self.menu_live()
        if live is None:
            self._menu_live_last = None
            return
        self._menu_live_due = now + 1.0 / self.config.menu_live_hz
        if live == self._menu_live_last:
            # Nothing has moved. The panel would drop the line anyway; not
            # sending it is the daemon declining to say what it knows has not
            # changed.
            return
        self._menu_live_last = live
        self.menu_client.send(self.scaled(
            self.menu.live_state(self.menu_open, live)
        ))

    def check_menu_stick(self, stick, dt):
        """A stick whose role is `menu`: a direction held, not a shove.

        Modelled on `check_focus_stick` rather than on `check_flick`, and for
        the same reason it is: walking a grid is a thing you do several of in
        a row, so it repeats while the stick is over. On a tile that has been
        taken it moves the value instead - which is Phase 0's table, and the
        one place the stick and the D-pad have to agree exactly.
        """
        code_x, code_y = STICK_AXES[stick]
        x, y = self.axes[code_x], self.axes[code_y]
        magnitude = (x * x + y * y) ** 0.5
        if magnitude < self.config.traverse_release:
            self._focus_held.pop(("menu", stick), None)
            return
        if magnitude < self.config.traverse_flick:
            return
        if abs(x) >= abs(y):
            way = "right" if x > 0 else "left"
        else:
            way = "down" if y > 0 else "up"
        held = self._focus_held.get(("menu", stick))
        if held is None or held[0] != way:
            # Third slot: how long this direction has been held, which is what
            # the walk accelerates against. A reversal starts a new entry and
            # so starts it again - somebody who went too far is not somebody
            # crossing a distance.
            self._focus_held[("menu", stick)] = [
                way, self.config.traverse_repeat_delay, 0.0
            ]
        else:
            held[1] -= dt
            held[2] += dt
            if held[1] > 0:
                return
            held[1] = ramped(self.config.traverse_repeat_rate,
                             self.config.traverse_repeat_ramp,
                             self.config.traverse_repeat_ramp_time,
                             held[2])
        self.menu_command(way)

    def menu_take(self):
        """A on a control with a range: both axes become the tile's.

        What the value was is remembered here, because B means leave in every
        layer and every surface and leaving a control you have pushed too far
        is putting it back. A is what keeps it, which is also when it is
        written down: one decision made over a second, not thirty.
        """
        if self.menu.edit:
            return False
        item = self.menu.takeable()
        if item is None or not self.menu.take():
            return False
        if not item["reads"]:
            # A card of rows reads nothing, so there is nothing to put back:
            # going into a list is a place to be rather than a number being
            # pushed, and B out of it undoes a walk rather than a value.
            self._menu_before = None
            self.say("move", rumble=False)
            self.push_menu_view()
            return True
        source, name = item["reads"]
        if source == "live":
            # Nothing to put back: the value is the machine's rather than
            # ours, and undoing somebody's volume a second after they let go
            # of it is worse than leaving it where they left it.
            self._menu_before = None
        else:
            # What it was, and whether it was ever chosen from the pad. The
            # second half is what keeps a cancelled push from writing a
            # shipped default into settings.toml, which would freeze it: the
            # user would stop receiving the default that changes later.
            self._menu_before = (name, self.config.setting(name),
                                 name in self.config.chosen)
        self._menu_edged = False
        self._menu_sweep = 0.0
        self.say("commit")
        self.push_menu_view()
        return True

    def menu_untake(self, keep):
        """Let go of a held control, keeping the value or putting it back."""
        if self.menu.taken is None:
            return False
        self.menu.release()
        before = self._menu_before
        self._menu_before = None
        if not keep and before is not None:
            name, value, chosen = before
            if self.config.setting(name) != value:
                self.config.set_setting(name, ("set", value))
                if not chosen:
                    self.config.chosen.pop(name, None)
                self.apply_setting(name)
            # And nothing to write: what is on disk is what this put back, so
            # a cancel leaves the file exactly as it found it.
            self._menu_dirty = None
        self.menu_settle(force=True)
        # Two ways off a control and they are not the same event: A keeps
        # what it is on, B puts it back. One concluded and the other went the
        # other way, which is exactly the pair these two words are.
        self.say("commit" if keep else "back")
        self.push_menu_view()
        return True

    def menu_ramp(self, way):
        """How many steps one push of a held direction is worth now.

        `pointer_speed` is thirty-eight presses end to end at one step each,
        so a direction held has to cover ground the way a held wheel does.
        Shaped like `scroll_ramp`, and a reversal resets it for the same
        reason: somebody who has gone too far is not asking for the speed
        they overshot at.
        """
        now = time.monotonic()
        if way != self._menu_way:
            self._menu_way = way
            self._menu_since = now
        ramp = self.config.menu_ramp
        if ramp <= 1.0:
            return 1
        span = self.config.menu_ramp_ms / 1000.0
        share = 1.0 if span <= 0 else min(1.0, (now - self._menu_since) / span)
        return max(1, int(round(1.0 + (ramp - 1.0) * share)))

    def menu_feel(self, direction, sideways=True):
        """The motor, answering a push on the side the push was made.

        **The hand that moved it is the hand that feels it.** A pad wires its
        low-frequency motor on the left and its high-frequency one on the
        right, so a value taken to the right buzzes on the right - which is
        the one thing the motor can say that the screen cannot say faster,
        and the only thing a hand pushing a control is asking about.

        One level rather than a scale. A hum that rose with the distance from
        where a push began was a second reading of a number the tile is
        already printing, and a control being pushed wants *the push landed*
        rather than a measurement.

        **Up and down are the left motor**, both of them: a list is walked
        with the D-pad, the D-pad is under the left thumb, and a vertical
        movement has no left and right to answer with. `sideways` is False
        there, and the direction is then only about which way the list went -
        which the sound already says.
        """
        if not sideways:
            self.rumble.aim("texture", "left")
            return
        self.rumble.aim("texture", "right" if direction > 0 else "left")

    def menu_adjust(self, item, direction, steps=None):
        """Move a control one way. False where it has nowhere left to go.

        The new value lands in the config and on the tile, and nowhere else
        until the push settles: a slider is one decision made over a second,
        and writing the file thirty times is thirty chances to be interrupted
        halfway. Nothing is announced either - the tile is showing the number,
        and a notification per step is the screen saying twice what it already
        says once.
        """
        source, name = item["reads"]
        if steps is None:
            steps = self.menu_ramp((item["id"], direction))
            if source == "pad" and CHOSEN.get(name, {}).get("stops"):
                # No ramp on a ladder. It exists because a speed is
                # thirty-eight presses end to end; a ladder is six, and a
                # held direction would cross the whole of it in the first
                # push and sit at the end.
                steps = 1
        if source == "live":
            # No file to write and nothing to apply: the machine is where the
            # value lives, and the tile is showing what it last said.
            moved = self.live_write(name, ("step", direction * steps))
            if moved:
                self._menu_edged = False
                self._menu_moving = MENU_SCRUB_HOLD
                self.menu_feel(direction)
            return moved
        if source != "pad":
            return False
        try:
            before = self.config.setting(name)
            value = self.config.set_setting(name, ("step", direction * steps))
        except (KeyError, ValueError) as exc:
            # A setting that went away under a config someone edited.
            log.warning("menu: %s: %s", name, exc)
            return False
        if value == before:
            self.menu_edge()
            return False
        self._menu_dirty = name
        self._menu_edged = False
        self._menu_moving = MENU_SCRUB_HOLD
        # One continuous effect rather than a tick per step: `[snap] rumble`'s
        # rule is that a step repeating under a held button would buzz all the
        # way down a list, and a slider is that list with the numbers showing.
        self.menu_feel(direction)
        self.push_menu_view()
        return True

    def menu_edge(self):
        """The end of a control's travel, announced once per arrival.

        A wall you are still pushing against is still one wall, so the tick
        fires on the step that first found it and not on the twenty after.
        """
        if self._menu_edged:
            return
        self._menu_edged = True
        self._menu_moving = 0.0
        self.rumble.stop("texture")
        self.say("edge")

    def menu_sweep(self, dt):
        """The triggers, crossing a control's range rather than stepping it.

        Thirty-eight presses to cross `pointer_speed` is not a control, it is
        a chore, so a pull is a rate: fully in crosses the whole range in
        `[menu] sweep_ms`, and half in takes twice as long. It acts on the
        tile in front whether or not that tile has been taken - the point of
        a trigger here is that it needs no mode at all.

        Moved in whole steps, so a value a trigger swept to is one a D-pad
        could have landed on: two ways to the same set of numbers, not two
        sets.
        """
        if self.menu.edit:
            # Nothing here is a value while a page is being rearranged.
            self._menu_sweep = 0.0
            return
        item = self.menu.takeable()
        pull = 0.0
        for name, way in MENU_TRIGGERS:
            pull += way * self.trigger_pull(name)
        if item is None or not pull:
            self._menu_sweep = 0.0
            self._menu_way = None
            return
        source, name = item["reads"]
        if source != "pad":
            return
        spec = CHOSEN[name]
        stops = spec.get("stops")
        if stops:
            # A ladder is swept by its stops rather than along its numbers:
            # they are a proportion apart, so the value's own arithmetic range
            # would cross the bottom four of them in a sixth of the pull and
            # spend the rest of it on the top two.
            step, span = 1.0, float(len(stops) - 1)
        else:
            step = float(spec["step"])
            span = float(spec["max"]) - float(spec["min"])
        seconds = max(0.001, self.config.menu_sweep_ms / 1000.0)
        # The push is live from the moment the trigger is pulled, not from the
        # first whole step it lands: at a gentle pull a step is several ticks
        # away, and a settle in between would throw away what has been swept
        # so far, over and over, and the control would never move at all.
        self._menu_moving = MENU_SCRUB_HOLD
        self._menu_sweep += span / seconds * dt * max(-1.0, min(1.0, pull))
        steps = int(self._menu_sweep / step)
        if not steps:
            return
        self._menu_sweep -= steps * step
        direction = 1 if steps > 0 else -1
        self.menu_adjust(item, direction, abs(steps))

    def trigger_pull(self, name):
        """How far a trigger is pulled, 0..1.

        A pad that reports its triggers as buttons has no fraction to give, so
        down is all the way in: the sweep is a little blunter there and works.
        """
        level = self.trigger_level.get(name)
        if level is not None:
            return level
        return 1.0 if name in self.pressed else 0.0

    def menu_settle(self, dt=0.0, force=False):
        """End a push that has stopped, and write down what it left.

        Called every tick while the menu is open rather than hung off a
        release, because there are four ways to stop pushing - the direction
        let go, the trigger let go, the tile deselected, the menu closed - and
        a hum that survived any one of them is the tick that sticks on.
        """
        if not force:
            self._menu_moving = max(0.0, self._menu_moving - dt)
            if self._menu_moving > 0.0:
                return
        self._menu_moving = 0.0
        self._menu_way = None
        self._menu_sweep = 0.0
        self.rumble.stop("texture")
        name = self._menu_dirty
        if name is None:
            return
        self._menu_dirty = None
        # Applied and saved once, at the end: `rumble_strength` re-uploads the
        # whole vocabulary when it changes, and doing that per step of a sweep
        # is an ioctl storm for a level nobody stopped on.
        self.apply_setting(name)
        self.save_settings()

    def menu_layout_save(self):
        """Write the arrangement down. Inline, the way settings.toml is.

        Not on the worker thread: it is a few hundred bytes written whole and
        moved into place, which is the same work `save_settings` already does
        on every press of a setting row. What it must not do is fail loudly -
        a file omapad wrote itself is omapad's to survive.
        """
        # Pages the person has put back are dropped rather than written as an
        # empty table, so the file only ever holds arrangements that exist.
        layout = {page: plan for page, plan in self.menu.layout.items()
                  if page and (plan.get("order") or plan.get("hidden")
                               or plan.get("span") or plan.get("at"))}
        path = layout_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            temporary = path + ".new"
            with open(temporary, "w") as handle:
                handle.write(render_layout(layout))
            os.replace(temporary, path)
        except OSError as exc:
            log.warning("could not write the layout: %s", exc)

    def menu_group_enter(self):
        """A group has been walked to. Arm its listing, if it has one.

        Not read here: flicking across five chips in a second would spawn five
        commands, and the four you passed through are answers nobody asked
        for. `menu.group_settle_ms` is how long the bar has to stop moving
        before the chip you are on is worth asking about.
        """
        self._menu_group_due = 0.0
        if not self.menu.groups:
            return
        group = self.menu.groups[self.menu.group]
        if group.get("from"):
            self._menu_group_due = (
                time.monotonic() + self.config.menu_group_settle
            )

    def menu_group_settled(self, now):
        """Read the chip the bar came to rest on. Called from the loop."""
        if not self._menu_group_due or now < self._menu_group_due:
            return
        self._menu_group_due = 0.0
        if self.menu_open and self.menu.groups:
            self.menu_fill(self.menu.groups[self.menu.group])

    def menu_cards_settled(self, now):
        """Read the listing cards on the page in front. Called from the loop.

        A listed **submenu** is read at the press that enters it; nobody
        enters a card, so a card is read when the page it stands on stops
        changing. `[menu] group_settle_ms` is that wait, and it is the chip's
        own for the chip's reason: walking across four pages should spawn one
        command rather than four.

        Keyed on the page rather than on a turn, so every way onto a page -
        the bar, drilling in, coming back out, opening the menu where it was
        left - arms it once and the same way.
        """
        page = self.menu.page_name() if self.menu_open else ""
        if page != self._menu_cards_page:
            self._menu_cards_page = page
            self._menu_cards_due = (now + self.config.menu_group_settle
                                    if page else 0.0)
            return
        if not self._menu_cards_due or now < self._menu_cards_due:
            return
        self._menu_cards_due = 0.0
        for tile in self.menu.tiles:
            self.menu_fill(tile["item"])

    def menu_select_group(self, index):
        """Name a chip outright - what a pointer clicking one asks for."""
        if not self.menu_open:
            return
        self.menu.enter_group(index)
        self.menu_group_enter()
        self.push_menu_view()

    def menu_command(self, command):
        """Drive the menu. True when holding the button should keep firing."""
        if command == "toggle":
            self.set_menu(not self.menu_open)
            return False
        if command == "open":
            self.set_menu(True)
            return False
        if command == "close":
            # X and the four buttons that leave outright. The same word `back`
            # is: nothing was decided, and what a room hears is somebody
            # putting the surface away. A row that ran and took the menu with
            # it does not come through here - it has its own answer, and two
            # sounds for one press is one of them arguing with the other.
            if self.menu_open:
                self.say("back")
            self.set_menu(False)
            return False
        if not self.menu_open:
            return False  # navigation means nothing while the menu is down

        model = self.menu
        # Anything that is not the press keeping a held row down is that row
        # being let go of: walking away from a tile counting down, or closing
        # the page it is on, is not a thing to keep counting behind.
        if command != "press":
            self.menu_disarm()
        held = False
        if command in ("edit", "edit_on", "edit_off"):
            want = (not model.edit if command == "edit"
                    else command == "edit_on")
            if model.set_edit(want) and not want:
                # Leaving is when it is written down, which is what B means
                # here: the arrangement you walked away from is the one kept.
                self.menu_layout_save()
            self.push_menu_view()
            return False
        if command == "save":
            self.menu_layout_save()
            return False
        if command in ("pick", "hide", "restore", "wider", "narrower"):
            if not model.edit:
                # Said rather than done quietly: every one of these is a
                # gesture of a mode nobody is in.
                return False
            if command == "pick":
                model.pick()
                self.say("commit")
            elif command == "hide":
                model.hide()
                self.say("commit")
                self.hud_rearranged()
            elif command == "restore":
                if model.restore():
                    self.menu_layout_save()
                    self.hud_rearranged()
            elif model.resize(1 if command == "wider" else -1, 0):
                self.hud_rearranged()
            else:
                self.menu_edge()
            self.push_menu_view()
            return False
        if model.edit and command in ("press", "back"):
            # What A and B are bound to while editing - but a press can also
            # arrive from the control socket, which has no bindings at all,
            # and `omapad ctl menu press` has to mean what the pad means.
            return self.menu_command("pick" if command == "press"
                                     else "edit_off")
        if command in ("up", "down", "left", "right") and model.picked:
            # A tile being carried takes the directions the selection would
            # have had: it is the thing the thumb is moving.
            if model.carry(command):
                self.hud_rearranged()
            else:
                self.menu_edge()
            self.push_menu_view()
            return True
        if command in ("up", "down", "left", "right"):
            if model.entered:
                # A card of rows took **one** axis, and it is the other one: a
                # list runs down the card, so left and right say nothing here
                # rather than doing a slider's job on a thing with no range.
                if command in ("up", "down"):
                    if model.step_row(command):
                        self.say("move", rumble=False)
                        # The vertical instrument's own push, and it is felt
                        # the way the horizontal one is: held while the list
                        # is moving, let go of when it stops (`menu_settle`).
                        # On the left, because that is the thumb on the D-pad.
                        self._menu_moving = MENU_SCRUB_HOLD
                        self.menu_feel(0, sideways=False)
                    else:
                        self.menu_edge()
                    self.push_menu_view()
                    return True
                return False
            if model.taken is not None:
                # Both axes belong to the tile now. Only the one the control
                # has: a range is one dimension, and answering up and down
                # with it would step a value somebody was trying to leave.
                if command in ("left", "right"):
                    way = 1 if command == "right" else -1
                    return self.menu_adjust(model.held, way)
                return False
            # Four directions, one answer: the tile that way, decided by the
            # same geometry that decides which window a flick lands on. A
            # press with nothing that way leaves the selection alone rather
            # than wrapping - in two dimensions, wrapping is losing it.
            # The one event that is heard and never felt. A motor ticking on
            # every step of a held direction buzzes the whole way down a
            # page, which is the rule `[snap] rumble` exists for; a sound
            # decays, so it ticks instead. Only when the selection actually
            # went somewhere - a push into the edge of a page is not a step.
            if model.step(command):
                self.say("move", rumble=False)
            held = True
        elif command in ("group_prev", "group_next"):
            if model.group_move(-1 if command == "group_prev" else 1):
                self.say("move", rumble=False)
            self.menu_group_enter()
            held = True
        elif command == "back" and self._menu_countdown is not None:
            # **B, and only B.** Ten seconds is long enough to want to look at
            # something else on the page, so walking the cursor does not stop
            # a count the way it lets go of a hold - a count that died because
            # a thumb brushed a stick would be worse than no count at all.
            self.menu_uncount(True)
            return False
        elif command == "back" and model.taken is not None:
            # B leaves, here as everywhere - and leaving a control you have
            # pushed too far is putting it back where it was. A is the one
            # that keeps what it is on.
            self.menu_untake(False)
            return False
        elif command == "back":
            # Back at the top of a group is the way out, the way Esc is in the
            # Omarchy menu. The bar is not a level to climb to.
            self.say("back")
            if not model.back():
                self.set_menu(False)
                return False
        elif (command == "press" and model.taken is not None
                and not model.entered):
            # Let go, keeping what it is on: A commits, and committing a
            # control with a range is the moment it is written down.
            self.menu_untake(True)
            return False
        elif (command == "press" and model.taken is None
                and model.takeable() is not None):
            # And on a card of rows this is going *in* rather than taking hold
            # of a number. A inside one runs the row and falls through below,
            # which is why this asks that nothing is held yet: a card you are
            # already inside must not answer A by entering itself again.
            self.menu_take()
            return False
        elif command == "press" and model.current is not None \
                and model.current["control"] in CONTROL_KINDS:
            # A control acts on what it reads: there is nothing to enter and
            # nowhere to be thrown out to. `set_setting` pushes the view.
            self.menu_activate(model.current)
            return False
        elif command == "press" and self._menu_countdown is not None:
            # A row is already counting. A does nothing rather than starting a
            # second one or skipping to the end: the wait is the whole point
            # of it, and a second press is exactly the reflex it exists for.
            return False
        elif (command == "press" and model.acting is not None
                and model.acting.get("countdown")):
            # A row that takes the screen away. A starts the count, the row
            # prints it, B stops it - see `menu_count`.
            self.menu_count(model.acting)
            return False
        elif (command == "press" and model.acting is not None
                and model.acting["confirm"]):
            # A row nobody can take back. A is not the press that runs it: it
            # is the press that starts holding it, and the same two waits, the
            # same tick, the same notification and the same cancel button a
            # binding's `confirm = true` gets are what happens next.
            self.menu_arm(model.acting)
            return False
        elif command == "press":
            # A row that lists its submenu is read here, at the press. Caching
            # it would defeat the point: the reason a row lists devices rather
            # than naming them is that the answer changes while the daemon runs
            # - a television is plugged in and an output appears.
            self.menu_fill(model.current)
            kind, item = model.press()
            if kind == "run" and item["action"] is None:
                # All a listing found was that it found nothing. The row is an
                # answer rather than a choice, so the menu stays where it is.
                pass
            elif kind == "run" and item["repeat"]:
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
                if item.get("listed"):
                    model.choose(item)
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

    # -- a menu row that has to be held ------------------------------------

    def menu_holds(self):
        """Is the tile in front one that has to be held rather than pressed?"""
        if not self.menu_open or self.menu.edit:
            return False
        # What a press is aimed at, which inside a card of rows is the row:
        # the legend says what A does, and A on a card of rows does what the
        # row says rather than what the card does.
        current = self.menu.acting
        return current is not None and bool(current.get("confirm"))

    def menu_arm(self, item):
        """Start holding a row that cannot be taken back.

        The same gesture a binding's `confirm = true` makes, deliberately: a
        person who has held a shoulder to cross a workspace already knows what
        this is, and a second way of being sure about something would be a
        second thing to learn for the same promise. So the numbers are
        `[confirm]`'s, `[confirm] scale` reaches them, the tick and the
        notification are the ones `warn_confirm` sends, and the cancel button
        backs out of this exactly as it backs out of that.

        What is different is the drawing: a badge on the bar has a fill and a
        lean, and a tile is the thing you are looking at - so the tile fills
        instead, and the page says which row is counting rather than the bar
        saying which button is.
        """
        if self._menu_confirm is not None:
            return False
        self._menu_confirm = {
            "id": item["id"], "item": item, "at": time.monotonic(),
            "warned": False,
        }
        self.push_menu_view()
        return True

    def menu_count(self, item):
        """Start a row counting down to running. True if one started.

        The other answer to *are you sure*, and it is for a different press
        than the hold is. A hold is right where the gesture is already in the
        hand and is over in a second; this is right where what happens next
        takes the screen away, and being sure about that is not a thing to do
        with a thumb - it is a thing to be given long enough to change your
        mind about. Holding A for ten seconds is not a gesture anybody makes.

        So the menu stays where it is, the row prints how long is left, and B
        stops it. Nothing else does: ten seconds is long enough to want to
        look at something, and a count that died because a thumb brushed a
        stick would be worse than no count at all.
        """
        if self._menu_countdown is not None or self._menu_confirm is not None:
            return False
        self._menu_countdown = {
            "id": item["id"], "item": item, "at": time.monotonic(),
            "printed": None,
        }
        # Said once, at the start, and then the number is the whole of it. A
        # tick a second for ten seconds is a pad buzzing through a decision
        # somebody is in the middle of making.
        self.say("tick")
        self.session.notify(
            "omapad",
            "%s in %ds - %s to cancel" % (item["label"], item["countdown"],
                                          self.config.confirm_cancel),
            timeout=item["countdown"] * 1000,
        )
        self.push_menu_view()
        return True

    def menu_uncount(self, cancelled=False):
        """Stop a row that was counting. True if one was."""
        if self._menu_countdown is None:
            return False
        item = self._menu_countdown["item"]
        self._menu_countdown = None
        if cancelled:
            self.say("back")
            self.session.notify("omapad", "Cancelled", timeout=900)
            log.info("menu: countdown cancelled %s", item["id"])
        if self.menu_open:
            self.push_menu_view()
        return True

    def menu_countdown_left(self):
        """Whole seconds still to go, or None while nothing is counting.

        Rounded **up**, so a count with a fifth of a second left still prints
        1: a row that showed 0 for a moment and then ran would read as a row
        that had stopped and ran anyway.
        """
        pending = self._menu_countdown
        if pending is None:
            return None
        gone = time.monotonic() - pending["at"]
        left = pending["item"]["countdown"] - gone
        return max(0, int(-(-left // 1)))

    def check_menu_countdown(self, now):
        """Run a row whose count has reached zero. Called on the loop."""
        pending = self._menu_countdown
        if pending is None:
            return
        item = pending["item"]
        if now - pending["at"] < item["countdown"]:
            # The number on the row changes once a second and nothing else
            # does, so the view is pushed when it changes rather than on every
            # turn of the loop.
            left = self.menu_countdown_left()
            if left != pending["printed"]:
                pending["printed"] = left
                if self.menu_open:
                    self.push_menu_view()
            return
        self._menu_countdown = None
        log.info("menu: countdown ran %s", item["id"])
        # From here it is an ordinary row being picked, and it takes the
        # ordinary path - the same three lines a held row takes when its own
        # wait is over.
        self.menu.choose(item)
        if not item["stay"]:
            self.set_menu(False)
        self.fire_once(item["action"], "menu")

    def menu_disarm(self, cancelled=False):
        """Let go of a row that was counting down. True if one was.

        `cancelled` says it out loud, for the two ways out that are somebody
        deciding against it - the cancel button, and the thumb coming off -
        rather than the menu simply going away underneath it.
        """
        if self._menu_confirm is None:
            return False
        announced = self._menu_confirm["warned"]
        self._menu_confirm = None
        if cancelled and announced:
            # Only once it had announced itself: a press let go of before the
            # tick said nothing, so there is nothing to take back.
            self.say("back")
            self.session.notify("omapad", "Cancelled", timeout=900)
            log.info("menu: confirm cancelled")
        if self.menu_open:
            self.push_menu_view()
        return True

    def menu_confirm_state(self):
        """Where a held row has got to, for the tile to draw.

        The bar's shape for the same gesture (`set_holding`), one surface
        along: which tile, how long the phase it is in lasts, and whether the
        tick has gone. Absent while nothing is held, so a payload says
        nothing about a gesture nobody is making.
        """
        pending = self._menu_confirm
        if pending is None:
            return None
        hold_ms, confirm_ms = self.config.announced_scaled
        return {
            "id": pending["id"],
            "ms": confirm_ms if pending["warned"] else hold_ms,
            "armed": pending["warned"],
        }

    def check_menu_confirm(self, now):
        """The two waits of a held row, counted on the loop."""
        pending = self._menu_confirm
        if pending is None:
            return
        hold_ms, confirm_ms = self.config.announced_scaled
        elapsed = (now - pending["at"]) * 1000.0
        if not pending["warned"]:
            if elapsed < hold_ms:
                return
            pending["warned"] = True
            # The same announcement a binding makes, and it is made the same
            # way: a tick for the hands, a notification for the eyes that are
            # not on the tile, and the tile itself now filling.
            self.say("tick")
            self.session.notify(
                "omapad",
                "%s - %s to cancel" % (pending["item"]["label"],
                                       self.config.confirm_cancel),
                timeout=confirm_ms,
            )
            self.push_menu_view()
            return
        if elapsed < hold_ms + confirm_ms:
            return
        item = pending["item"]
        self._menu_confirm = None
        log.info("menu: confirmed %s", item["id"])
        # From here it is an ordinary row being picked, and it takes the
        # ordinary path: the menu goes away first so that whatever it opens
        # does not come up behind a scrim, and the action is tagged with the
        # menu so game mode lets it through.
        self.menu.choose(item)
        if not item["stay"]:
            self.set_menu(False)
        self.fire_once(item["action"], "menu")

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
            # Read before the menu is put away below: the guide is on Y
            # because you had forgotten what a button does, so the page it
            # answers about is the one you were looking at.
            spent = self.menu.page_keys() if self.menu_open else None
            page = self.menu.title if self.menu_open else ""
            self.guide.rebuild(self.available_buttons(), spent, page)
            self.guide.reset()
            # Only one surface may read the D-pad, and the guide is the one
            # being looked at.
            self.set_menu(False)
            self.set_osk(False)
        self.push_guide_view()
        self.apply_grab()
        self.relabel_gamebar()
        log.info("guide: %s", "open" if opened else "closed")

    def push_guide_view(self):
        self._guide_next_heartbeat = time.monotonic() + VIEW_HEARTBEAT
        self.guide_client.send(self.scaled(self.guide.view_state(self.guide_open)))

    def guide_command(self, command):
        # The card is read and put away, and every button on it puts it away -
        # so closing it is the one thing that happens here besides turning a
        # page, and it is the same word every other surface leaves on.
        if command == "toggle":
            if self.guide_open:
                self.say("back")
            self.set_guide(not self.guide_open)
            return
        if command == "open":
            self.set_guide(True)
            return
        if command == "close":
            if self.guide_open:
                self.say("back")
            self.set_guide(False)
            return
        if not self.guide_open:
            return  # turning a page means nothing while the guide is down
        if command in ("next", "prev"):
            self.guide.move(1 if command == "next" else -1)
            self.say("move", rumble=False)
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
        # A choice prints the word it is called rather than the word it is
        # stored as: `playstation` is a config value, not something anybody
        # reads from a sofa.
        words = CHOSEN.get(name, {}).get("words") or {}
        return words.get(value, str(value))

    def apply_setting(self, name):
        """Make a changed setting true of the daemon that is already running.

        Every one of these is something the config decides at startup, so a
        setting reachable from the pad is only half a setting until the thing
        it configures is told again.

        `start_mode` is the one that is not here, and its absence is the
        point: it decides which mode the *next* start comes up in, so acting
        on it would swap the mode under someone who only said what to do the
        time after this one.
        """
        if name == "profile":
            if self.device is not None:
                self.reapply_profile()
            self.apply_layout()
        elif name == "layout":
            self.apply_layout()
        elif name == "radius":
            # True of every surface at once, and the one setting somebody is
            # looking straight at while they change it: the tiles under the
            # slider have to round as it moves, not at the next heartbeat.
            self.push_open_views()
        elif name == "badge_style":
            # The other thing that is true of every surface at once. Without
            # this it waits out the heartbeat, and a menu row that ticks a
            # second before the bar behind it changes reads as a press that
            # did not take.
            self.push_open_views()
        elif name == "hud":
            # The one setting that is a surface: turning it on is the whole of
            # putting the readings on screen.
            self.set_hud(self.config.hud_show)
        elif name == "hold_scale":
            # Every binding was built with the old scale already in its two
            # waits - that is where it is applied, so that the number the bar
            # fills a badge over is the number the loop fires on - so the
            # cache of them is what a new scale invalidates.
            self.bindings.clear()
            self.page_keys.clear()
        elif name in ("rumble", "rumble_strength"):
            # The effect is uploaded once per connection, so a strength that
            # changed only reaches the motor by replacing it.
            self.rumble.configure(self.config)
            self.say("tick")
        elif name in ("sound", "sound_volume"):
            # The panel holds four loaded files and the volume it was last
            # told. There is no heartbeat on this socket to carry a changed
            # one, so the answer is the same as the motor's: say the word
            # again, and the line that carries it carries the new volume.
            self.say("tick")

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
        self.relabel_gamebar()
        log.info("mapping: %s", "open" if opened else "closed")

    def status_state(self):
        """What the bar widget draws: what omapad is doing, in one line."""
        return {
            "mode": self.mode,
            "connected": self.device is not None,
            "pad": drawable(self.device.name) if self.device else "",
            "profile": self.active_profile_name or "",
            "handed_over": self.handed_over,
            "locked": self.locked,
            "kept": self.keeping,
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
            self.say("tick")
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
        self.trigger_level.clear()
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
                "usage: osk <toggle|open|close> "
                "| menu <toggle|open|close|up|down|left|right|press|back"
                "|group_prev|group_next|select N|group N|row ID> "
                "| guide <toggle|open|close|next|prev> "
                "| map <toggle|open|close|skip|back|restart|save|cancel> "
                "| surface <close|close_all|back> "
                "| ripple <left|right|middle> "
                "| sound <move|back|tick|edge|commit> "
                "| pad <setting>=<value> | lock <on|off|toggle> "
                "| keep <on|off|toggle> "
                "| press <BUTTON> [tap|hold] "
                "| hud <on|off|toggle> "
                "| mode <toggle|desktop|game> | status"
            )
        verb, args = parts[0], parts[1:]
        if verb == "ping":
            return "ok"
        if verb == "status":
            return (
                # `pid` last but one, and `device` still last, because a
                # device names itself with spaces in it and everything after
                # it would have to be parsed backwards. It is here because
                # `omapad budget` has to find the process to read /proc for,
                # and asking the daemon is better than guessing from a
                # command line.
                "mode=%s pad=%s lock=%s keep=%s osk=%s menu=%s guide=%s "
                "map=%s hud=%s layer=%s pid=%d device=%s"
                % (
                    self.mode,
                    "app" if self.handed_over else "ours",
                    "on" if self.locked else "off",
                    "on" if self.keeping else "off",
                    "open" if self.osk_open else "closed",
                    "open" if self.menu_open else "closed",
                    "open" if self.guide_open else "closed",
                    "open" if self.mapping_open else "closed",
                    "on" if self.hud_open else "off",
                    self.current_layer,
                    os.getpid(),
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
            if command == "select" and len(args) > 1:
                # The row a pointer is hovering names itself: `select 3` with
                # no previous direction. Everything else the menu does lives
                # in MenuAction.SIMPLE below.
                try:
                    index = int(args[1])
                except ValueError:
                    return "unknown menu command: select %s" % args[1]
                self.menu_select(index)
            elif command == "row" and len(args) > 1:
                # A row inside a card of rows, named the way it is drawn. No
                # index: a row carries a `when` like anything else here.
                self.menu_select_row(args[1])
            elif command == "group" and len(args) > 1:
                # The chip a pointer clicked, the same way `select` names a
                # tile. Walking the bar is `group_prev` / `group_next`.
                try:
                    index = int(args[1])
                except ValueError:
                    return "unknown menu command: group %s" % args[1]
                self.menu_select_group(index)
            elif command in MenuAction.SIMPLE:
                self.menu_command(command)
            else:
                return "unknown menu command: %s" % command
            return "menu=%s title=%s group=%d sel=%s" % (
                "open" if self.menu_open else "closed",
                self.menu.title, self.menu.group, self.menu.selected or "",
            )
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
        if verb == "ripple" and args:
            # No binding can reach this surface - it answers the pointer, not
            # the pad - so this is the only way to see one without clicking,
            # which is what tuning `size` and `duration_ms` needs.
            if not self.show_ripple(args[0]):
                return "ripple: nothing drawn"
            return "ripple %s at %d,%d" % (
                self.ripple.button, self.ripple.x, self.ripple.y)
        if verb == "sound" and args:
            # Nothing on the pad plays a cue on its own, so this is the only
            # way to hear one without going and pressing something - which is
            # what deciding on a volume, or a pack of your own, needs. It
            # answers whether the daemon *sent* the line: whether anything
            # came out of the speakers is the plugin's half, and
            # `omarchy-shell ipc call omapad-sound state` is where that is.
            name = args[0]
            if name not in sound_module.VOICES:
                return "unknown sound: %s" % name
            if not self.config.sound_enabled:
                return "sound: off ([sound] enabled)"
            if not self.say(name, rumble=False):
                return "sound: nothing sent"
            return "sound %s (#%d)" % (self.sound.cue, self.sound.seq)
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
        if verb == "hud" and args:
            # The readings are a setting rather than a surface verb, so this
            # goes in by the same door the tile does - which is what makes
            # `omapad ctl hud on` something that is still true tomorrow.
            command = args[0]
            if command not in ("on", "off", "toggle"):
                return "unknown hud command: %s" % command
            if command == "toggle":
                self.set_setting("hud", ("toggle", None))
            else:
                self.set_setting("hud", ("set", command == "on"))
            return "hud=%s" % ("on" if self.hud_open else "off")
        if verb == "lock" and args:
            # The lock has one button-shaped way in - a chord over a game -
            # and this is the other, for a script and for seeing what it does
            # without a pad in front of a game.
            from .actions import LockAction

            command = args[0]
            if command not in LockAction.SIMPLE:
                return "unknown lock command: %s" % command
            if command == "toggle":
                self.set_locked(not self.locked)
            else:
                self.set_locked(command == "on")
            return "lock=%s pad=%s" % (
                "on" if self.locked else "off",
                "app" if self.handed_over else "ours",
            )
        if verb == "keep" and args:
            # The lock's other half, and the one with no button-shaped way in
            # at all: nothing ships a chord for it, so this and the menu row
            # are the two doors.
            from .actions import KeepAction

            command = args[0]
            if command not in KeepAction.SIMPLE:
                return "unknown keep command: %s" % command
            if command == "toggle":
                self.set_keeping(not self.keeping)
            else:
                self.set_keeping(command == "on")
            return "keep=%s pad=%s" % (
                "on" if self.keeping else "off",
                "app" if self.handed_over else "ours",
            )
        if verb == "mode" and args and args[0] in ("toggle", "desktop", "game"):
            if args[0] == "toggle":
                self.toggle_mode()
            else:
                self.set_mode(args[0])
            return "mode=%s" % self.mode
        return "unknown command: %s" % request

    # -- held-action repeat ------------------------------------------------

    def repeat_start(self, action, delay, rate, ramp=1.0, ramp_time=0.0):
        now = time.monotonic()
        # `now` twice, meaning two different things: when the first repeat is
        # due, and when the finger went down. The ramp is measured from the
        # second, so the delay before the first step counts towards it - a
        # thumb that has been on the button for the whole delay has been on
        # it, whatever the walk has to show for it yet.
        self.repeats[id(action)] = [action, now + delay, rate, ramp,
                                    ramp_time, now]

    def repeat_stop(self, action):
        self.repeats.pop(id(action), None)

    def fire_repeats(self, now):
        for entry in list(self.repeats.values()):
            action, due, rate, ramp, ramp_time, began = entry
            if now >= due:
                action.repeat(self.ctx)
                entry[1] = now + ramped(rate, ramp, ramp_time, now - began)

    def stick_roles(self):
        """What the sticks are worth right now.

        Nothing at all once the app in front has the pad. Every role a stick
        can carry is a desktop job - a pointer, a wheel, a window - and a
        thumb resting on the stick while a game, Steam or a stream holds the
        pad lands on top of it as mouse movement nobody asked for. That is
        worse than a stray press: it never stops, and an app reading the
        pointer stops reading the pad. So the sticks stand aside with the
        buttons, which `allowed()` already does.

        Unlike a button they get no `reaches_past` to buy their way back.
        What earns a button its way past is being a gesture the game does not
        ask for - a chord, an announced hold - and a stick pushed over is the
        one input every game does ask for.

        A surface of ours takes the pad back while it is up, exactly as it
        does for the grab, and takes the sticks with it: the keyboard is
        pointed at with one.
        """
        if self.handed_over and not self.surface_open():
            return ("none", "none")
        return self.config.stick_roles(self.current_layer, self.active_profile)

    def sticks_live(self):
        """Has either stick a role to integrate? Both are off in game mode
        unless [mode] hands one back, and off under an app holding the pad."""
        return any(role in STICK_ROLES for role in self.stick_roles())

    # -- input handling ----------------------------------------------------

    def handle_button(self, button, pressed):
        # Every button, trigger and D-pad direction arrives here, so this is
        # the one place that has to say somebody is there.
        self.touched()
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
        # A grab that stood aside for a held button takes the pad the moment
        # the hand comes off it, which is the whole of what it was waiting for.
        if self._grab_wait is not None and not self.pressed:
            self.apply_grab()
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
            if not action.claims_chord(self.ctx):
                # Nothing for it to do right now, and a chord that took the
                # press anyway would cost both buttons their own bindings for
                # it. See `LockAction.claims_chord`.
                continue
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
            self.fire_once(action, reaches=True, chord=True)
            return True
        return False

    def chord_pending(self, button):
        """Could a chord this button names still fire right now?

        Only then does the button have to wait for its release. A chord that
        cannot fire is no reason to hold anything back, and the lock's are
        dead on the desktop by design: `ZL` is the window layer's trigger
        there and `ZR` a left click held for a drag, and neither may become a
        press that only lands when the thumb comes off.
        """
        for buttons, action in self.chords:
            if button in buttons and action.claims_chord(self.ctx):
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

    def allowed(self, action, layer=None, confirmed=False, reaches=None,
                chord=False):
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

        The **workspace lock** is the end of all that while it is on:
        nothing but a chord, because the chord is the menu and the menu is the
        only way to turn it off again. See `set_locked`.
        """
        if not self.handed_over:
            return True
        if self.surface_open():
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
        if self.locked:
            # The lock is the whole of the answer while it is on: an announced
            # hold and a `reaches_past` binding are both things somebody asked
            # for at a desk, and neither is something they asked for mid-fight
            # - the shoulder Steam's profile holds a workspace on is two
            # seconds of resting a thumb on LB. A chord is what is left,
            # because the menu is the way back out and there is no other.
            return chord
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
        # A hold counting down with nothing on it: this press is the finger
        # coming back inside `[confirm] slack_ms`, not a press of its own. The
        # gesture it belongs to is already running - starting a second one
        # here would restart the wait the slip was forgiven for.
        resumed = self.held.get(button)
        if resumed is not None and resumed.released_at is not None:
            resumed.released_at = None
            return
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
        if binding.waits_for_release or self.chord_pending(button):
            self.held[button] = HeldAction(None, binding, now)
            self.set_holding(button, binding)
            return
        action = binding.tap
        if not self.allowed(action, binding.layer, reaches=binding.reaches_past):
            return
        if binding.rumble:
            self.say("tick")
        self.pointer_away(action)
        if binding.holdable:
            self.held[button] = HeldAction(action, binding, now)
            action.press(self.ctx)
        else:
            action.press(self.ctx)
            action.release(self.ctx)

    def release_binding(self, button):
        held = self.held.get(button)
        if held is None:
            return
        # A finger that comes off a hold which has **already announced
        # itself** has not necessarily changed its mind: a thumb resting on a
        # shoulder for two seconds slips, and losing the countdown to that is
        # the whole of why some hands cannot make this gesture at all. So the
        # hold keeps counting for `[confirm] slack_ms` and the press below
        # puts the finger back on it. Only after the announcement - before it,
        # letting go is how a tap is made.
        if (
            self.config.confirm_slack_ms
            and held.warned
            and not held.hold_fired
            and held.released_at is None
        ):
            held.released_at = time.monotonic()
            return
        self.held.pop(button, None)
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
                    self.say("tick")
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

    def fire_once(self, action, layer=None, confirmed=False, reaches=None,
                  chord=False):
        """Fire an action that has no press/release of its own. True if it ran."""
        if not self.allowed(action, layer, confirmed, reaches, chord):
            return False
        self.pointer_away(action)
        action.press(self.ctx)
        action.release(self.ctx)
        return True

    def check_hold_timers(self, now):
        # A hold action may switch modes, which clears self.held mid-loop.
        for button, held in list(self.held.items()):
            # A hold the finger came off inside the slack keeps counting -
            # that is what the slack is - so this only asks whether the finger
            # stayed off for longer than it. Then it is the release, arriving
            # late: popped rather than passed to `release_binding`, because a
            # hold that had announced itself is never also a tap.
            if (
                held.released_at is not None
                and (now - held.released_at) * 1000.0
                >= self.config.confirm_slack_ms
            ):
                self.held.pop(button, None)
                self.clear_holding(button)
                continue
            binding = held.binding
            if not binding.is_tap_hold or held.hold_fired:
                continue
            elapsed = (now - held.pressed_at) * 1000.0
            if not binding.confirm_ms:
                if elapsed >= binding.hold_ms:
                    held.hold_fired = True
                    if self.fire_once(binding.hold, binding.layer,
                                      reaches=binding.reaches_past) and binding.rumble:
                        self.say("tick")
                continue
            if not held.warned:
                if elapsed >= binding.hold_ms:
                    # An announcement is a promise that this is about to
                    # happen, and it is made with a tick and a notification -
                    # both of which land on top of the game. So it is only
                    # made when the hold would actually be let through: while
                    # the workspace lock is on it would not, and a countdown to
                    # nothing is worse than silence. Asked every tick rather
                    # than once, so a hold that outlives the lock still
                    # announces itself.
                    if not self.allowed(binding.hold, binding.layer,
                                        confirmed=True,
                                        reaches=binding.reaches_past):
                        continue
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
        self.say("tick")
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
        """Back out of every hold that is counting down. True if any was.

        A held menu row is one of them: the cancel button is the way out of
        this gesture wherever it is being made, and a button that backed out
        of the bar's version and not the menu's would be the surface deciding
        what a word means.
        """
        dropped = self.menu_disarm(cancelled=True)
        pending = self.pending_confirm()
        for held in pending:
            # Not `hold_fired` because it fired, but because nothing more may:
            # the release must not fall back to the tap either.
            held.hold_fired = True
        if pending:
            self.say("back")
            self.session.notify("omapad", "Cancelled", timeout=900)
            log.info("confirm: cancelled")
        return bool(pending) or dropped

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
                        # A thumb on a stick is somebody being there; a stick
                        # resting crooked is not, and a pad with drift would
                        # otherwise hold the screen awake for ever on its own.
                        stick = self.axis_stick(code)
                        if stick is not None and abs(self.axes[code]) > \
                                self.config.stick_deadzone(stick):
                            self.touched()
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
        self.say("tick")
        self.set_mapping(False)
        if self.config.notify:
            self.session.notify("omapad", "Mapping cancelled")

    def axis_stick(self, code):
        """Which stick an axis belongs to, or None for anything else."""
        for stick, codes in STICK_AXES.items():
            if code in codes:
                return stick
        return None

    def handle_trigger(self, code, value):
        """Turn an analog trigger into a button, with hysteresis.

        Pressing at one point and releasing at a lower one keeps a trigger
        rested halfway from rattling the layer it activates on and off.
        """
        minimum, span = self.trigger_scale.get(code, (0, 1))
        fraction = (value - minimum) / span
        name = self.trigger_axes[code]
        self.trigger_level[name] = max(0.0, min(1.0, fraction))
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
        if self._menu_confirm is not None:
            return True  # a row counting down towards running
        if self.rumble.settling:
            # A tick owed its stop. Without this the idle poll decides when
            # the motor goes quiet, and a click reads as a buzz.
            return True
        if self.menu_open and self.menu.watching():
            # A gauge on screen. The loop has to keep frame rate for it, and
            # nothing else on the surface asks the loop for anything.
            return True
        if self.menu_open and (self._menu_moving or self._menu_dirty
                               or any(self.trigger_pull(name)
                                      for name, _ in MENU_TRIGGERS)):
            # A trigger sweeping a control, or one that has just stopped and
            # owes the file a write. On the idle poll a sweep would move in
            # quarter-second jumps.
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
        if not all(self._swap_armed.values()):
            return True  # the same, for a swap
        if self._focus_held:
            return True  # a held direction still walking the focus
        if not self.sticks_live():
            return False
        deadzone = min(self.config.left_deadzone, self.config.right_deadzone)
        return any(abs(value) > deadzone for value in self.axes.values())

    def tick(self, dt):
        if self.menu_open:
            # Here rather than beside the heartbeat: a sweep is something to
            # integrate between events, which is exactly what this is for, and
            # it is the only place with a dt to integrate it over.
            self.menu_sweep(dt)
            self.menu_settle(dt)
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
                # One role, two answers - the window in front decides which.
                if self.move_drags(stick):
                    move = self.stick_vector(stick)
                else:
                    self.check_swap(stick)
            elif role == "swap":
                self.check_swap(stick)
            elif role == "snap":
                self.check_flick(stick)
            elif role == "focus":
                self.check_focus_stick(stick, dt)
            elif role == "menu":
                # Only while the menu is up. The role is the menu layer's, so
                # this is belt and braces - but a config that names it in
                # another layer must not silently turn that stick off.
                if self.menu_open:
                    self.check_menu_stick(stick, dt)

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
            self.say("tick")

    def move_drags(self, stick):
        """Which half of the `move` role this push is: drag, or swap.

        `window.move` does nothing to a tiled window and `window.swap` nothing
        to a floating one, so the role has to ask before it acts. Asked once,
        when the stick leaves its rest, and kept for the length of the push:
        one `j/activewindow` costs what a snap's three cost on a press, which
        a gesture can afford and a tick 30 times a second cannot. The question
        is settled at the deadzone rather than at `swap.flick`, so a floating
        window still drags from the smallest deflection.

        With no compositor to ask, it drags - which is what this role did
        before it had a second half.
        """
        code_x, code_y = STICK_AXES[stick]
        x, y = self.axes[code_x], self.axes[code_y]
        magnitude = (x * x + y * y) ** 0.5
        if magnitude < self.config.stick_deadzone(stick):
            self._move_drag.pop(stick, None)
            return False
        drag = self._move_drag.get(stick)
        if drag is None:
            floating = self.hypr.window_floating()
            drag = True if floating is None else floating
            self._move_drag[stick] = drag
        return drag

    def check_swap(self, stick):
        """A stick whose role is `swap`: one neighbour per push.

        The hysteresis of a snap for the same reason - a stick held over is
        one press, not a stream - and the direction is read off the raw axes,
        because the curve exists to make small deflections finer and this only
        ever asks whether the stick went all the way over.
        """
        code_x, code_y = STICK_AXES[stick]
        x, y = self.axes[code_x], self.axes[code_y]
        magnitude = (x * x + y * y) ** 0.5
        if magnitude < self.config.swap_release:
            self._swap_armed[stick] = True
            return
        if magnitude < self.config.swap_flick or not self._swap_armed[stick]:
            return
        self._swap_armed[stick] = False
        if abs(x) >= abs(y):
            way = "r" if x > 0 else "l"
        else:
            way = "d" if y > 0 else "u"
        self.hypr.dispatch(
            "hl.dsp.window.swap({ direction = '%s' })" % way
        )

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
            # way a held key does. The third slot is how long it has been
            # held, and the walk closes up against it.
            self._focus_held[stick] = [step, self.config.traverse_repeat_delay,
                                       0.0]
        else:
            held[1] -= dt
            held[2] += dt
            if held[1] > 0:
                return
            held[1] = ramped(self.config.traverse_repeat_rate,
                             self.config.traverse_repeat_ramp,
                             self.config.traverse_repeat_ramp_time,
                             held[2])
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

    def start(self):
        """What a session that has never switched modes still has to do.

        `[mode] start = "game"` has had no switch to hang any of this off. The
        pointer is one half - it would stay the desktop's, and it is the one
        thing that would show the mode - and the desktop bar is the other: it
        would stay where it is, with ours opening under it, two bars along one
        edge.
        """
        self.prepare_cursor()
        self.apply_cursor()
        self.apply_bar()
        self.apply_idle()
        self.apply_blur()
        self._theme_seen = self.theme_stamp()
        self.check_pointer_hiding()

    def theme_stamp(self):
        """Something that changes when the desktop's theme does, or None.

        The symlink's target as well as the file's time: a theme switched and
        switched back lands on a file that has not been written since.
        """
        path = cursor_theme.theme_path()
        try:
            return (os.path.realpath(path), os.stat(path).st_mtime_ns)
        except OSError:
            return None

    def check_theme(self, now):
        """Ask again for what the desktop may have changed underneath us.

        `omarchy-theme-set` ends in `hyprctl reload`, and a reload throws away
        every rule asked for at runtime - the blur behind our own surfaces is
        one of those. The game-mode pointer is the other: it is a file omapad
        drew from the palette that was in force, and a shell repainting itself
        cannot put either back.

        The third is not a theme change at all and rides here for its beat:
        whether the compositor animates anything (`[ui] motion`). It is asked
        every time rather than only when the theme moved, because turning
        animations off changes no file.

        Polled rather than subscribed to, because one `stat` on the beat the
        surfaces already heartbeat at is cheaper than a second socket to keep
        alive - and because the file is the thing that changed, which is what
        `cursor.py` already reads the theme out of.
        """
        if now < self._theme_next_check:
            return
        self._theme_next_check = now + THEME_POLL
        # Asked on every beat rather than only when the theme moved: a
        # `hyprctl keyword animations:enabled false` changes no file, and a
        # person who has just turned animations off is watching the screen to
        # see whether anything listened. One socket query on the beat the
        # surfaces already heartbeat at, which is the same class of cost as
        # the stat below.
        if self.read_desktop_motion():
            self.push_open_views()
        stamp = self.theme_stamp()
        if stamp is None or stamp == self._theme_seen:
            return
        first = self._theme_seen is None
        self._theme_seen = stamp
        if first:
            return  # the first look is where we came in, not a change
        log.info("the desktop theme changed; asking for ours again")
        self.apply_blur()
        # Redrawn only where the colours really moved: `prepare_cursor`
        # compares a stamp on disk, so this is a file read where nothing has.
        self.apply_cursor()

    def apply_blur(self):
        """Ask the compositor to blur behind our own surfaces.

        A layer rule on our own namespace and nothing else - asking for a blur
        behind your own panel is not reaching into somebody's setup. It is a
        *request*: Hyprland blurs only where blur is on at all, so this does
        nothing on a desktop that has turned it off, and `[menu] dim` is what
        carries the contrast there.

        Best-effort like everything else that talks to the compositor: no
        Hyprland is a working daemon, and a rule that did not take is a menu
        that looks plainer rather than one that does not open.
        """
        if not self.config.ui_blur:
            return
        answer = self.hypr.evaluate(
            self.config.ui_blur_rule % self.config.ui_blur_alpha
        )
        if answer is None or answer.strip() != "ok":
            log.info("the compositor did not take the blur rule: %s",
                     (answer or "no answer").strip()[:80])

    def run(self):
        self.start()
        interval = 1.0 / self.config.poll_hz
        last = time.monotonic()
        poller = select.poll()
        # The control socket is one listening fd plus whatever connections
        # the shell keeps open; watch them all, and refresh the registration
        # whenever the set changes (connections open on demand, close on
        # hang-up). Watching a stale fd is harmless but wastes a wakeup.
        control_fds = ()
        control_fd = self.control.fileno() if self.control else None
        if control_fd is not None:
            control_fds = (control_fd,)
            poller.register(control_fd, select.POLLIN)
        # The command worker writes a byte here whenever it has an answer, so
        # a page that was waiting on a listing fills at once rather than at
        # the end of the idle poll.
        command_fd = self._command_wake
        if command_fd is not None:
            poller.register(command_fd, select.POLLIN)
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

            if self.control is None:
                if control_fds:
                    for fd in control_fds:
                        poller.unregister(fd)
                    control_fds = ()
            else:
                want = (self.control.fileno(),) + tuple(self.control.open_fds())
                if want != control_fds:
                    for fd in control_fds:
                        try:
                            poller.unregister(fd)
                        except (KeyError, OSError):
                            pass
                    for fd in want:
                        poller.register(fd, select.POLLIN)
                    control_fds = want

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
                if control_fds and fd in control_fds:
                    self.control.serve(self.handle_control)
                elif self.device is not None and fd == self.device.fd:
                    self.drain_events()
                elif command_fd is not None and fd == command_fd:
                    self.drain_commands()
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
                self.check_menu_confirm(now)
                self.check_menu_countdown(now)
                self.check_awake(now)
                self.fire_repeats(now)
                # A tick that has run its length is told to stop, because the
                # stop the kernel owes it does not always arrive - see
                # rumble.SETTLE_MARGIN.
                self.rumble.settle(now)
                if self.osk_open and now >= self._osk_next_heartbeat:
                    self.push_osk_view()
                if self.menu_open:
                    self.menu_group_settled(now)
                    self.menu_cards_settled(now)
                    self.menu_head_refresh()
                    self.menu_meta_refresh()
                    self.live_refresh(now)
                    self.push_menu_live(now)
                    if now >= self._menu_next_heartbeat:
                        self.push_menu_view()
                if self.guide_open and now >= self._guide_next_heartbeat:
                    self.push_guide_view()
                # Both places a reading can be drawn are asked for in one
                # pass, and nothing is asked at all while neither is up.
                self.sys_refresh(now)
                if self.hud_open and now >= self._hud_next_heartbeat:
                    self.push_hud_view()
                if self.mapping_open:
                    self.check_mapping_hold(now)
                    if now >= self._mapping_next_heartbeat:
                        self.push_mapping_view()
                if self._grab_wait is not None and now >= self._grab_wait:
                    # The button that is never let go - see `apply_grab`.
                    self.apply_grab()
                if now >= self._next_handover_check:
                    # Most apps open the pad a moment after they come up, not
                    # while they are still being mapped.
                    self.update_handover()
                self.check_theme(now)
                if now >= self._status_next_heartbeat:
                    self.push_status_view()
                if self.gamebar_open and now >= self._gamebar_next_heartbeat:
                    self.push_gamebar_view()
                self.tick(dt)

    def shutdown(self):
        self.running = False
        self.release_everything()
        if self.commands is not None:
            # Told to stop rather than waited for: the thread is a daemon
            # thread, and a command still running is one nobody is left to
            # show the answer to.
            self.commands.close()
            self.commands = None
        self._command_jobs.clear()
        if self._command_wake is not None:
            try:
                os.close(self._command_wake)
            except OSError:
                pass
            self._command_wake = None
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
        self.apply_idle(restore=True)
        self.status_client.close()
        self.set_gamebar(False)
        self.gamebar_client.close()
        # The readings go with us: what is on screen is a view of a daemon
        # that is stopping, and a frozen one left over a game is worse than
        # none at all. The setting is untouched, so it comes back next start.
        self.set_hud(False)
        self.hud_client.close()
        self.ripple_client.close()
        self.sound_client.close()
        if self.control is not None:
            self.control.close()
        if self.hypr_ev is not None:
            self.hypr_ev.close()
            self.hypr_ev = None
        self.release_keys()
        self.keys.close()
        self.mouse.close()
        self.keyboard.close()
