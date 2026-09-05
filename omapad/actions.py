"""Actions a binding can perform, and the session plumbing they need."""

import glob
import json
import logging
import os
import queue
import shlex
import shutil
import socket
import subprocess
import threading

from . import keymap

OMARCHY_BIN = "/usr/share/omarchy/bin"

log = logging.getLogger("omapad")


class ActionError(ValueError):
    pass


class Session:
    """Environment a graphical command needs when spawned from a daemon.

    systemd user services do not always inherit the compositor's variables,
    so they are rediscovered from the runtime directory when missing.
    """

    def __init__(self):
        self.runtime_dir = (os.environ.get("XDG_RUNTIME_DIR")
                            or "/run/user/%d" % os.getuid())
        self.env = dict(os.environ)
        self.env["XDG_RUNTIME_DIR"] = self.runtime_dir
        if "WAYLAND_DISPLAY" not in self.env:
            sockets = sorted(glob.glob(os.path.join(self.runtime_dir, "wayland-*")))
            sockets = [s for s in sockets if not s.endswith(".lock")]
            if sockets:
                self.env["WAYLAND_DISPLAY"] = os.path.basename(sockets[0])
        signature = self.env.get("HYPRLAND_INSTANCE_SIGNATURE") or self.hypr_signature()
        if signature:
            self.env["HYPRLAND_INSTANCE_SIGNATURE"] = signature
        path = self.env.get("PATH", "/usr/local/bin:/usr/bin")
        if OMARCHY_BIN not in path.split(":") and os.path.isdir(OMARCHY_BIN):
            self.env["PATH"] = path + ":" + OMARCHY_BIN
        self.scope = self.scope_prefix()

    def scope_prefix(self):
        """Prefix that puts a spawned command in a transient scope of its own.

        A child of a systemd service stays in that service's cgroup, and the
        default KillMode is control-group: `systemctl --user restart omapad`,
        which every config change asks for, would then SIGTERM the browser or
        the game just launched from the pad. Their logs land in omapad's
        journal too, which is how this was found. A scope moves the command
        into a unit of its own, so it outlives the daemon that started it.

        INVOCATION_ID is what says systemd started us. Run straight from a
        checkout there is no cgroup to escape, so there is nothing to pay for.
        """
        if not os.environ.get("INVOCATION_ID"):
            return []
        systemd_run = shutil.which("systemd-run", path=self.env.get("PATH"))
        if not systemd_run:
            log.warning(
                "systemd-run is missing: commands launched from the pad will "
                "die with the daemon"
            )
            return []
        return [systemd_run, "--user", "--scope", "--collect", "--quiet", "--"]

    def hypr_socket(self):
        """Path of the live Hyprland IPC socket, or None."""
        signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
        if signature:
            candidate = os.path.join(
                self.runtime_dir, "hypr", signature, ".socket.sock"
            )
            if os.path.exists(candidate):
                return candidate
        candidates = glob.glob(
            os.path.join(self.runtime_dir, "hypr", "*", ".socket.sock")
        )
        if not candidates:
            return None
        # Several instances can leave stale directories behind; the newest wins.
        return max(candidates, key=lambda p: os.stat(p).st_mtime)

    def hypr_signature(self):
        socket_path = self.hypr_socket()
        if socket_path is None:
            return None
        return os.path.basename(os.path.dirname(socket_path))

    def spawn(self, command):
        """Run a shell command detached from the daemon."""
        subprocess.Popen(
            self.scope + ["/bin/sh", "-c", command],
            env=self.env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    def capture(self, command, timeout=2.0):
        """Run a shell command and return the non-empty lines it printed.

        Not `spawn`: this one is read from rather than let go of, so it is
        neither detached nor given a scope of its own. It blocks for as long
        as the command takes, which is why callers reach it through
        `Commands` rather than from the loop; the timeout is the floor under
        that - a command that hangs must not hold the thread for ever.
        """
        try:
            result = subprocess.run(
                ["/bin/sh", "-c", command],
                env=self.env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            log.warning("command %r failed: %s", command, exc)
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def notify(self, summary, body="", timeout=1500):
        try:
            self.spawn(
                "notify-send -a omapad -t %d %s %s"
                % (timeout, shlex.quote(summary), shlex.quote(body))
            )
        except OSError:
            pass


class Commands:
    """The thread that runs the shell commands a surface asks for.

    `Session.capture` waits on a subprocess, and every caller of it sits on
    the event loop: a listing that wedges is a pad that answers nothing until
    the timeout runs out. The waiting moves here, and the answer comes back
    through a queue the loop hears about from one byte down `wake` - so a
    finished command lands on screen at once rather than at the next idle
    poll.

    One command at a time, in the order they were asked for. Two of them are
    a menu page and a keyboard page, neither of which is opened often enough
    to want a pool, and a queue keeps a slow one from being outrun by the
    press after it.
    """

    def __init__(self, session, wake=None):
        self.session = session
        self.wake = wake
        self.jobs = queue.Queue()
        self.results = queue.Queue()
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="omapad-commands")
        self._thread.daemon = True
        self._thread.start()

    # -- the loop's side ---------------------------------------------------

    def submit(self, key, command, timeout=2.0):
        """Queue one command. `key` comes back beside whatever it printed."""
        self.jobs.put((key, command, timeout))

    def drain(self):
        """Every (key, lines) that has finished since the last call."""
        found = []
        while True:
            try:
                found.append(self.results.get_nowait())
            except queue.Empty:
                return found

    def close(self):
        self._running = False
        self.jobs.put(None)

    # -- the thread's side -------------------------------------------------

    def _loop(self):
        try:
            self._work()
        finally:
            # Closed here rather than in `close`, so the only thread that can
            # write to it is the only one that can take it away: a number
            # closed under this one could be handed straight back out and
            # given a byte meant for the loop.
            if self.wake is not None:
                try:
                    os.close(self.wake)
                except OSError:
                    pass
                self.wake = None

    def _work(self):
        while self._running:
            job = self.jobs.get()
            if job is None:
                return
            key, command, timeout = job
            try:
                lines = self.session.capture(command, timeout)
            except Exception:  # noqa: BLE001
                # `capture` already answers its own failures with an empty
                # list. Anything left is a bug, and a thread that dies of one
                # would be every later page silently never filling - so it is
                # logged and answered empty, the same as a command that failed.
                log.exception("command %r died", command)
                lines = []
            self.results.put((key, lines))
            if self.wake is None:
                continue
            try:
                os.write(self.wake, b"a")
            except OSError:
                # A closed pipe costs a late answer, not a lost one: the loop
                # still drains at its next wake-up.
                pass


class Hypr:
    """Hyprland IPC over its unix socket.

    This build routes /dispatch through Lua, so a dispatcher is written the way
    it is in hyprland.lua - hl.dsp.focus({ workspace = 'e+1' }) - rather than in
    the old `workspace e+1` form. Talking to the socket directly avoids
    spawning hyprctl on every stick tick.
    """

    def __init__(self, session):
        self.session = session
        self._socket_path = session.hypr_socket()

    def request(self, message):
        """Send one IPC message and return the answer, or None."""
        for attempt in (0, 1):
            if self._socket_path is None or not os.path.exists(self._socket_path):
                self._socket_path = self.session.hypr_socket()
            if self._socket_path is None:
                return None
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                    sock.settimeout(1.0)
                    sock.connect(self._socket_path)
                    sock.sendall(message.encode("utf-8"))
                    chunks = []
                    while True:
                        chunk = sock.recv(65536)
                        if not chunk:
                            break
                        chunks.append(chunk)
                return b"".join(chunks).decode("utf-8", "replace")
            except (OSError, socket.timeout):
                # Hyprland restarted: drop the stale path and retry once.
                self._socket_path = None
                if attempt:
                    return None
        return None

    def dispatch(self, expression):
        return self.request("/dispatch " + expression)

    def query(self, command):
        """A `j/` query, parsed. None when the compositor is not there.

        Cheap enough to ask on a button press - the whole client list comes
        back over the socket in well under a millisecond, where spawning
        hyprctl for it costs tens.
        """
        raw = self.request("j/" + command)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except ValueError:
            log.debug("could not parse the answer to %r: %r", command, raw[:120])
            return None

    def cursor_position(self):
        """Where the pointer is, in the same logical pixels windows use."""
        data = self.query("cursorpos")
        if not isinstance(data, dict):
            return None
        try:
            return float(data["x"]), float(data["y"])
        except (KeyError, TypeError, ValueError):
            return None

    def warp(self, x, y):
        self.dispatch("hl.dsp.cursor.move({ x = %d, y = %d })" % (int(x), int(y)))

    def set_cursor_theme(self, theme, size):
        """Swap the pointer the compositor draws. Best-effort, like the rest."""
        return self.request("setcursor %s %d" % (theme, int(size)))


class Context:
    """Everything an action needs to act on."""

    def __init__(self, mouse, keyboard, hypr, session, daemon):
        self.mouse = mouse
        self.keyboard = keyboard
        self.hypr = hypr
        self.session = session
        self.daemon = daemon
        self.held_scrolls = {}


class Action:
    holdable = False

    def press(self, ctx):
        pass

    def release(self, ctx):
        pass

    def claims_chord(self, ctx):
        """Whether a chord may take the press for this action right now.

        Yes for everything but the lock. A chord costs both its buttons their
        own jobs - `ZL` + B closes the window in every layer - so an action
        that could do nothing at this moment must not spend them.
        """
        return True

    def state(self, ctx):
        """Whether what this action would do is already the case.

        `None` - the answer for almost everything - means the question does
        not apply: launching a browser is neither on nor off. A setting row
        answers it, and the menu ticks the row that says what is in force.
        """
        return None

    def value(self, ctx):
        """What the thing this acts on is on right now, in words.

        Empty for almost everything, for the same reason `state` is None. A
        row that steps a number answers it, because a tick cannot: nothing
        else on screen says what the number is, or that it has reached an end.
        """
        return ""


class NoAction(Action):
    pass


class ClickAction(Action):
    holdable = True

    def __init__(self, button):
        from .uinput import MOUSE_BUTTONS

        if button not in MOUSE_BUTTONS:
            raise ActionError("unknown mouse button: %r" % button)
        self.button = button

    def press(self, ctx):
        ctx.mouse.button(self.button, True)
        # After the click, never before it: the burst asks the compositor
        # where the pointer is, and nothing the screen has to say about a
        # click may stand between the trigger and the click itself.
        ctx.daemon.show_ripple(self.button)

    def release(self, ctx):
        ctx.mouse.button(self.button, False)


class KeyAction(Action):
    holdable = True

    def __init__(self, spec):
        try:
            self.mods, self.code = keymap.parse_chord(spec)
        except keymap.KeyParseError as exc:
            raise ActionError(str(exc)) from exc

    def press(self, ctx):
        ctx.keyboard.chord(self.mods, self.code, True)

    def release(self, ctx):
        ctx.keyboard.chord(self.mods, self.code, False)


class ScrollAction(Action):
    holdable = True
    DIRECTIONS = {
        "up": (0, 1), "down": (0, -1), "left": (-1, 0), "right": (1, 0),
    }

    def __init__(self, direction):
        if direction not in self.DIRECTIONS:
            raise ActionError("unknown scroll direction: %r" % direction)
        self.direction = direction

    def press(self, ctx):
        ctx.held_scrolls[self.direction] = self.DIRECTIONS[self.direction]

    def release(self, ctx):
        ctx.held_scrolls.pop(self.direction, None)


class HyprAction(Action):
    def __init__(self, expression):
        self.expression = expression.strip()
        if not self.expression:
            raise ActionError("empty hypr action")

    def press(self, ctx):
        ctx.hypr.dispatch(self.expression)


class ExecAction(Action):
    def __init__(self, command):
        self.command = command.strip()
        if not self.command:
            raise ActionError("empty exec action")

    def press(self, ctx):
        ctx.session.spawn(self.command)


class OskAction(Action):
    """Drive the on-screen keyboard."""

    # Holding a direction should walk the keys, the way a held arrow key walks
    # a text cursor; the rest fire once per press.
    REPEATABLE = {"up", "down", "left", "right"}
    SIMPLE = {
        "up", "down", "left", "right", "press", "open", "close", "toggle",
        "shift", "ctrl", "alt", "submit", "caps",
    }
    # A modifier that follows the finger instead of latching for one key.
    HOLD = {"hold:shift", "hold:ctrl", "hold:alt"}
    holdable = True

    def __init__(self, command):
        command = command.strip()
        if (command not in self.SIMPLE and command not in self.HOLD
                and not command.startswith("layer:")):
            raise ActionError("unknown osk command: %r" % command)
        self.command = command

    def press(self, ctx):
        if self.command in self.HOLD:
            ctx.daemon.osk_hold(self.command[5:], True)
            return
        ctx.daemon.osk_command(self.command)
        if self.command in self.REPEATABLE:
            ctx.daemon.repeat_start(
                self,
                ctx.daemon.config.osk_repeat_delay,
                ctx.daemon.config.osk_repeat_rate,
            )

    def release(self, ctx):
        if self.command in self.HOLD:
            ctx.daemon.osk_hold(self.command[5:], False)
            return
        ctx.daemon.repeat_stop(self)

    def repeat(self, ctx):
        ctx.daemon.osk_command(self.command)


class MenuAction(Action):
    """Drive the controller menu."""

    SIMPLE = {
        "up", "down", "left", "right", "press", "back",
        "open", "close", "toggle",
    }
    holdable = True

    def __init__(self, command):
        command = command.strip()
        if command not in self.SIMPLE:
            raise ActionError("unknown menu command: %r" % command)
        self.command = command

    def press(self, ctx):
        # Whether a hold should keep firing depends on the row under the
        # selection, not on the command alone, so the daemon decides: walking
        # the list repeats, and so does a row marked `repeat`. Picking an
        # ordinary row twice because a thumb rested on A never is what was
        # meant.
        if ctx.daemon.menu_command(self.command):
            ctx.daemon.repeat_start(
                self,
                ctx.daemon.config.menu_repeat_delay,
                ctx.daemon.config.menu_repeat_rate,
            )

    def release(self, ctx):
        ctx.daemon.repeat_stop(self)

    def repeat(self, ctx):
        ctx.daemon.menu_command(self.command)


class GuideAction(Action):
    """Drive the bindings guide."""

    SIMPLE = {"toggle", "open", "close", "next", "prev"}

    def __init__(self, command):
        command = command.strip()
        if command not in self.SIMPLE:
            raise ActionError("unknown guide command: %r" % command)
        self.command = command

    def press(self, ctx):
        ctx.daemon.guide_command(self.command)


class MappingAction(Action):
    """Drive the controller mapping screen."""

    SIMPLE = {"toggle", "open", "close", "skip", "back", "restart",
              "save", "cancel"}

    def __init__(self, command):
        command = command.strip()
        if command not in self.SIMPLE:
            raise ActionError("unknown map command: %r" % command)
        self.command = command

    def press(self, ctx):
        ctx.daemon.mapping_command(self.command)


class SurfaceAction(Action):
    """Act on whichever surface of ours is on top, without naming it.

    `osk:close` closes the keyboard and nothing else, which is right for a
    button that means one thing. A key on the desk cannot know what is up -
    Escape has to send away whatever is on screen - so this asks the daemon
    which surface that is. See daemon.surface_top().
    """

    SIMPLE = {"close", "close_all", "back"}

    def __init__(self, command):
        command = command.strip()
        if command not in self.SIMPLE:
            raise ActionError("unknown surface command: %r" % command)
        self.command = command

    def press(self, ctx):
        ctx.daemon.surface_command(self.command)


class FocusAction(Action):
    """Move the focus the way the app moves it itself.

    Nothing outside an application knows where its buttons are - the
    accessibility bus is the only thing that could say, it reports every
    widget at screen 0,0 under Wayland, and browsers, games and terminals do
    not join it at all. But every toolkit already answers Tab and the arrows,
    and it answers them correctly, because it is the thing that knows. So this
    asks rather than aims: the daemon sends the key the app expects and the
    app does the geometry.
    """

    holdable = True
    SIMPLE = ("next", "prev", "up", "down", "left", "right", "activate", "back")

    def __init__(self, step):
        step = step.strip().lower()
        if step not in self.SIMPLE:
            raise ActionError("unknown focus step: %r" % step)
        self.step = step

    def press(self, ctx):
        ctx.daemon.focus_step(self.step, True)

    def release(self, ctx):
        ctx.daemon.focus_step(self.step, False)


class SnapAction(Action):
    """Put the pointer on the window next door, instead of walking it there."""

    SIMPLE = {"left", "right", "up", "down", "centre", "center"}

    def __init__(self, direction):
        direction = direction.strip().lower()
        if direction not in self.SIMPLE:
            raise ActionError("unknown snap direction: %r" % direction)
        self.direction = "centre" if direction == "center" else direction

    def press(self, ctx):
        ctx.daemon.snap_cursor(self.direction)


class PadAction(Action):
    """One of the settings the pad can change about itself.

        pad:layout=xbox            print Xbox names on every badge
        pad:profile=auto           work out which pad this is again
        pad:rumble=toggle          the motor, on or off
        pad:rumble_strength=up     one step louder

    A value is a setting's own word, or `next`/`prev` to step through what it
    holds - so the same mechanism reads as a list of rows in the menu and as a
    single button that walks it. Validated here rather than at the press: a
    typo is what `omapad check` is for.
    """

    def __init__(self, spec):
        from .config import setting_request, SettingError

        name, separator, raw = spec.partition("=")
        if not separator:
            raise ActionError(
                "pad: takes a setting and a value, as pad:layout=xbox"
            )
        self.setting = name.strip().lower()
        try:
            self.request = setting_request(self.setting, raw)
        except SettingError as exc:
            raise ActionError(str(exc)) from exc

    def press(self, ctx):
        ctx.daemon.set_setting(self.setting, self.request)

    def state(self, ctx):
        """True when the setting already holds what this would set it to.

        None for one that steps rather than sets: no single step of a number
        is the one the setting is on.
        """
        if self.request[0] != "set":
            return None
        return ctx.daemon.config.setting(self.setting) == self.request[1]

    def value(self, ctx):
        from .config import setting_text

        return setting_text(self.setting, ctx.daemon.config.setting(self.setting))


class LockAction(Action):
    """Give the pad to the app in front outright, and stand aside.

        lock:on      the app has it, and nothing of ours fires but the menu
        lock:off     ask /proc again, which is the ordinary arrangement
        lock:toggle  the two of them on one button or one row

    The hand-off is automatic and asks the program itself, which is right
    about every game whose opening of the pad /proc can see. This is the same
    answer given by hand, for the two things that question cannot settle: a
    game the walk misses, which then gets nothing while the pad drives the
    desktop over the top of it, and a game that has the pad and is still
    being interrupted - an announced hold is deliberate at a desk and a
    shoulder rested on for a second and a half mid-fight is not.

    Locked, the only thing left is a chord, which is the menu and so the way
    back out. See `Daemon.set_locked` and `Daemon.allowed`.
    """

    SIMPLE = ("toggle", "on", "off")

    def __init__(self, target):
        if target not in self.SIMPLE:
            raise ActionError("unknown lock: %r" % target)
        self.target = target

    def press(self, ctx):
        if self.target == "toggle":
            ctx.daemon.set_locked(not ctx.daemon.locked)
        else:
            ctx.daemon.set_locked(self.target == "on")

    def claims_chord(self, ctx):
        """A lock chord fires only over an app that already has the pad.

        There it costs nothing: the grab is off, so the app sees both buttons
        whatever this does with them. On the desktop the same chord would take
        `ZL` + B away from closing a window, and locking the pad to the
        terminal in front of you is not what that press meant.
        """
        if self.target == "off":
            return ctx.daemon.locked
        return ctx.daemon.handed_over and not ctx.daemon.locked

    def state(self, ctx):
        """So the menu row ticks while the lock is on - the tick is the only
        thing on screen that says so."""
        if self.target == "off":
            return not ctx.daemon.locked
        return ctx.daemon.locked


class ModeAction(Action):
    def __init__(self, target):
        if target not in ("toggle", "desktop", "game"):
            raise ActionError("unknown mode: %r" % target)
        self.target = target

    def press(self, ctx):
        if self.target == "toggle":
            ctx.daemon.toggle_mode()
        else:
            ctx.daemon.set_mode(self.target)


PARSERS = {
    "osk": OskAction,
    "menu": MenuAction,
    "guide": GuideAction,
    "map": MappingAction,
    "click": ClickAction,
    "key": KeyAction,
    "scroll": ScrollAction,
    "hypr": HyprAction,
    "exec": ExecAction,
    "mode": ModeAction,
    "lock": LockAction,
    "pad": PadAction,
    "snap": SnapAction,
    "focus": FocusAction,
    "surface": SurfaceAction,
}


def parse(spec):
    """Turn "click:left" into an Action instance."""
    if spec is None:
        return NoAction()
    if not isinstance(spec, str):
        # A setting written into a bindings table by mistake - `hide_bar_in_game
        # = true` under [bindings.game] - arrives here as a bool. Naming it is
        # what `omapad check` is for; a traceback is not.
        raise ActionError("expected an action, got %r" % (spec,))
    spec = spec.strip()
    if not spec or spec == "nop":
        return NoAction()
    kind, _, argument = spec.partition(":")
    kind = kind.strip()
    if kind not in PARSERS:
        raise ActionError("unknown action kind %r in %r" % (kind, spec))
    return PARSERS[kind](argument.strip())


# How long a plain hold waits before it fires, when a binding does not say.
# Short, because a plain hold is a shortcut and not a decision.
HOLD_MS = 500

# And what an *announced* hold costs: the wait before it ticks and says what
# is coming, then the countdown it can still be backed out of. Longer, because
# this is the one thing that reaches past an app holding the pad - and the
# defaults, because `[confirm]` in the config is what really decides.
ANNOUNCED_MS = (1200, 800)


class Binding:
    """A button binding: a plain action, or a tap/hold pair."""

    layer = "base"
    hold_desc = ""
    # Whether this binding still fires while the pad is the app's. None means
    # "whatever the layer it was found in says"; the daemon resolves it once,
    # when the binding is built, because the layer is what knows.
    reaches_past = None

    def __init__(self, spec, announced=ANNOUNCED_MS):
        self.tap = None
        self.hold = None
        self.hold_ms = 0
        # Whether firing this binding should tick the pad's motor. Off by
        # default: a scheme where everything buzzes says nothing.
        self.rumble = False
        # Fire the tap when the button comes back up rather than on the way
        # down. Costs nothing you can feel, and it is what lets a button carry
        # a hold later without its tap having already gone out.
        self.on_release = False
        # A hold that announces itself before it acts: at hold_ms it warns
        # (a tick and a notification), and only confirm_ms later does it fire,
        # if the button is still down and nobody cancelled.
        self.confirm_ms = 0
        if isinstance(spec, dict):
            # A binding that reaches past an app holding the pad without being
            # a summon or an announced hold. Written on the binding rather
            # than inferred, because nothing about an action says whether the
            # game underneath also wants that button: `click:left` in a cloud
            # session is the desktop's, and in a shooter it is the trigger.
            if spec.get("reaches_past") is not None:
                self.reaches_past = bool(spec["reaches_past"])
            self.rumble = bool(spec.get("rumble", False))
            self.on_release = bool(spec.get("on_release", False))
            self.hold_desc = str(spec.get("hold_desc", "")).strip()
            self.tap = parse(spec.get("tap"))
            # A table is also how a binding says what it means - `desc`, for
            # the guide - so one that names no hold has to behave exactly like
            # the plain string it replaced: fire on the way down rather than
            # wait to see whether a hold was coming.
            if spec.get("hold") is not None:
                self.hold = parse(spec["hold"])
                # `confirm = true` is a binding asking for the announced hold
                # without naming its two numbers, so a user who wants theirs
                # faster changes one setting rather than every binding that
                # reaches past an app.
                wants = bool(spec.get("confirm", False))
                counted = wants or spec.get("confirm_ms") is not None
                self.hold_ms = int(spec.get(
                    "hold_ms", announced[0] if counted else HOLD_MS))
                if self.hold_ms <= 0:
                    raise ActionError("hold_ms must be positive")
                self.confirm_ms = int(spec.get(
                    "confirm_ms", announced[1] if wants else 0))
                if self.confirm_ms < 0:
                    raise ActionError("confirm_ms cannot be negative")
            elif spec.get("confirm_ms") or spec.get("confirm"):
                raise ActionError("confirm needs a hold to confirm")
        else:
            self.tap = parse(spec)

    @property
    def is_tap_hold(self):
        return self.hold is not None

    @property
    def waits_for_release(self):
        """True when the press must not act until the button comes back up."""
        return self.is_tap_hold or self.on_release

    @property
    def holdable(self):
        return not self.is_tap_hold and self.tap.holdable
