"""Command line entry point."""

import argparse
import errno
import logging
import select
import signal
import sys
import time

from . import __version__, config as config_module, linux_input as li
from . import live as live_module
from . import rumble as rumble_module
from . import sysinfo as sysinfo_module
from .config import DPAD_NAMES
from .daemon import Daemon
from .uinput import UinputError

log = logging.getLogger("omapad")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="omapad",
        description="Drive the Hyprland desktop with a game controller.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("-c", "--config", help="path to config.toml")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "--layout", action="store_true",
        help="for check: what the saved arrangement still resolves to",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=("run", "dump", "check", "ctl", "unit"),
        help="run the daemon (default), print controller events, validate the "
        "configuration, send a command to a running daemon, or write the "
        "systemd user unit for this checkout",
    )
    parser.add_argument(
        "args",
        nargs="*",
        help="for ctl: osk <toggle|open|close>, "
        "menu <toggle|open|close|up|down|left|right|press|back"
        "|group_prev|group_next|select N|group N>, "
        "guide <toggle|open|close|next|prev>, "
        "map <toggle|open|close|skip|back|restart|save|cancel>, "
        "surface <close|close_all|back>, ripple <left|right|middle>, "
        "press <BUTTON> [tap|hold], "
        "lock <on|off|toggle>, keep <on|off|toggle>, "
        "hud <on|off|toggle>, "
        "mode <toggle|desktop|game>, status; for unit: check",
    )
    return parser


def _no_controller(match):
    """Why nothing was found, naming the filter only when there is one."""
    if not match:
        return "no controller is connected"
    return (
        "no controller matching %s is connected"
        % ", ".join(repr(pattern) for pattern in match)
    )


def cmd_dump(config):
    """Print every event from the pad - useful for mapping a different pad."""
    device = li.find_device(config.device_match)
    if device is None:
        print(_no_controller(config.device_match), file=sys.stderr)
        return 1
    profile_name, buttons, trigger_axes = config.profile_for(
        device.name, device.vid_pid
    )
    print(
        "reading %s (%s) with the %s profile - Ctrl+C to stop"
        % (device.name, device.vid_pid, profile_name),
        flush=True,
    )
    # A held controller reaches its holder alone, and the daemon takes and
    # drops the pad as the app in front is handed it - so this prints nothing
    # at all, or half a press: a button going down inside one of those windows
    # and its release landing outside, reading exactly like a stuck button.
    # Say so, because an empty screen otherwise reads as a dead pad.
    try:
        device.grab()
        device.ungrab()
    except OSError as exc:
        if exc.errno != errno.EBUSY:
            raise
        print(
            "the controller is already taken by something else - usually "
            "omapad itself. Presses will be missed here, and a press caught "
            "half way looks stuck. Stop it first: systemctl --user stop omapad",
            file=sys.stderr,
            flush=True,
        )
    # Unbuffered, so events show up as they happen even when piped.
    hat = {"x": 0, "y": 0}
    poll_axes = {li.ABS_X: "LX", li.ABS_Y: "LY", li.ABS_RX: "RX", li.ABS_RY: "RY"}
    try:
        while True:
            select.select([device.fd], [], [])
            for etype, code, value in device.read_events():
                if etype == li.EV_KEY:
                    name = buttons.get(code, "UNMAPPED")
                    print(
                        "button 0x%03x %-8s %s"
                        % (code, name, "down" if value else "up"),
                        flush=True,
                    )
                elif etype == li.EV_ABS and code in (li.ABS_HAT0X, li.ABS_HAT0Y):
                    axis = "x" if code == li.ABS_HAT0X else "y"
                    previous, hat[axis] = hat[axis], value
                    if value:
                        print(
                            "dpad   %s down" % DPAD_NAMES.get((axis, value)),
                            flush=True,
                        )
                    elif previous:
                        print(
                            "dpad   %s up" % DPAD_NAMES.get((axis, previous)),
                            flush=True,
                        )
                elif etype == li.EV_ABS and code in trigger_axes:
                    info = device.absinfo(code)
                    span = max(info.maximum - info.minimum, 1)
                    print(
                        "trigger %-3s %.2f"
                        % (trigger_axes[code], (value - info.minimum) / span),
                        flush=True,
                    )
                elif etype == li.EV_ABS and code in poll_axes:
                    info = device.absinfo(code)
                    scaled = (value - info.center) / info.half_range if info else 0
                    if abs(scaled) > 0.2:
                        print(
                            "axis   %-3s %+.2f" % (poll_axes[code], scaled),
                            flush=True,
                        )
    except KeyboardInterrupt:
        return 0
    finally:
        device.close()


def cmd_check_layout(config):
    """What a saved arrangement still resolves to, page by page.

    A layout that has quietly lost half its tiles is exactly the kind of thing
    this project makes a command say out loud rather than leaving somebody to
    notice. Nothing here is a fault - an id the config no longer has is
    ignored by design, and this is where you find out it was.
    """
    from . import menu as menu_module

    path = config_module.layout_path()
    if not config.layout:
        print("no saved arrangement (%s)" % path)
        return 0
    pages = {}

    def walk(items, owner=""):
        for item in items:
            if item.get("items"):
                pages.setdefault(
                    menu_module.slug(str(item.get("id")
                                         or item.get("label", ""))),
                    [child for child in item["items"]])
                walk(item["items"])

    walk(config.menu_items)
    print("arrangement: %s" % path)
    for page in sorted(config.layout):
        plan = config.layout[page]
        tiles = pages.get(page)
        if tiles is None:
            print("  %s: no such page any more - it is ignored" % page)
            continue
        names = set()
        for item in tiles:
            names.add(menu_module.slug(str(item.get("id")
                                           or item.get("label", ""))))
        lost = [name for name in plan["order"] if name not in names]
        hidden = [name for name in plan["hidden"] if name in names]
        added = [name for name in names
                 if name and name not in plan["order"]]
        kept = len(plan["order"]) - len(lost)
        print("  %s: %d tile%s" % (page, kept, "" if kept == 1 else "s"))
        if lost:
            print("    gone from the config, ignored: %s" % ", ".join(lost))
        if added:
            print("    new since it was saved, added at the end: %s"
                  % ", ".join(sorted(added)))
        if hidden:
            print("    hidden: %s" % ", ".join(hidden))
        # The cells somebody put a tile in, and the column they would be
        # clamped to. A pin is the one part of an arrangement whose meaning
        # depends on how wide the page is drawn, so this is where the two are
        # printed together - `menu.place` clamps silently by design, and a
        # tile that has been quietly pulled back onto the page is exactly the
        # kind of thing this command exists to say out loud.
        placed = [(name, cell) for name, cell in sorted(plan.get("at", {}).items())
                  if name in names]
        if placed:
            # The page drawn over the whole screen has a last row; a menu page
            # does not, so only that one can be clamped downwards.
            last = config.hud_rows - 1 if page == config.hud_page else None
            right = config.menu_columns - 1
            said = []
            for name, (x, y) in placed:
                out = []
                if x > right:
                    out.append("column %d" % right)
                if last is not None and y > last:
                    out.append("row %d" % last)
                said.append("%s at %d,%d%s"
                            % (name, x, y,
                               " (clamped to %s)" % " and ".join(out)
                               if out else ""))
            print("    put in a cell: %s" % ", ".join(said))
        off = [name for name in plan.get("at", {}) if name not in names]
        if off:
            print("    placed, and gone from the config: %s"
                  % ", ".join(sorted(off)))
    return 0


def _report_rumble(config, device):
    words = rumble_module.Rumble(config).levels
    if not config.rumble_enabled:
        print("rumble: off")
        return
    try:
        supported = device.supports_effects()
        slots = max(1, device.effect_slots())
    except OSError as exc:
        log.debug("could not ask the pad about force feedback: %s", exc)
        print("rumble: cannot be asked - run this with the pad's udev rules")
        return
    taken = rumble_module.plan(words, supported, slots)
    if not taken:
        print("rumble: no usable motor")
        return
    said = [name if waveform is not None or name == "tick"
            else "%s (as a tick)" % name for name, waveform in taken]
    silent = [name for name in rumble_module.EFFECTS
              if words[name][0] > 0 and name not in dict(taken)]
    line = "rumble: %s" % ", ".join(said)
    if silent:
        line += " - no %s" % ", ".join(silent)
    print(line)


def _report_readings(config):
    """Which readings this machine actually answers, and which it cannot.

    Printed for `_report_rumble`'s reason one component along: what a source
    resolves to is the kernel's and the helper's rather than the config's, and
    the tile a reading does not answer is *not drawn at all* - so a HUD that
    is missing one looks exactly like a HUD that was never asked for it. The
    ladder is the same either way and this is the top of it.

    A `cmd:` source is named rather than run: `check` parses, and running
    somebody's helper to write a line of output is a different promise.
    """
    from . import sysinfo

    reader = sysinfo.Sysinfo(config)
    here = [name for name in sysinfo.READINGS
            if config.sysinfo_sources.get(name)
            and config.sysinfo_sources[name][0] != "cmd"]
    # Twice, with a gap. A busy share is measured *across* an interval - one
    # read of /proc/stat says what the machine has averaged since it was
    # switched on, which is why the first one deliberately answers nothing -
    # so a single pass here would print the one reading everybody looks for as
    # the one reading that is broken. The gap is the shortest one two samples
    # can be told apart over, and this is a command that runs once.
    for _ in range(2):
        for name in here:
            reader.read(name)
        if here:
            time.sleep(0.05)

    said, quiet, asked = [], [], []
    for name in sysinfo.READINGS:
        found = config.sysinfo_sources.get(name)
        if not found:
            quiet.append(name)
        elif found[0] == "cmd":
            asked.append(name)
        elif reader.value(name) is not None:
            said.append("%s %s" % (name, reader.words(name)))
        else:
            # A source pointed at nothing: a hwmon chip that is not on this
            # machine, a path that is not a mount. The one case worth a word,
            # because it is the one somebody has got wrong rather than left
            # out - and on screen it looks identical to never asking.
            said.append("%s - %s says nothing" % (name, ":".join(found)))
    line = "readings: %s" % (", ".join(said) if said else "none")
    if asked:
        line += " - and %s from a helper" % ", ".join(asked)
    if quiet:
        line += " - no source for %s" % ", ".join(quiet)
    print(line)


def cmd_check(config):
    """Parse every binding so mistakes surface before the daemon starts."""
    from . import actions, menu, osk

    problems = 0
    for layer_name, bindings in config.bindings.items():
        for button, spec in bindings.items():
            try:
                actions.Binding(spec, config.announced_hold)
            except actions.ActionError as exc:
                problems += 1
                print("%s.%s: %s" % (layer_name, button, exc), file=sys.stderr)
    for surface, table in config.keyboard_bindings.items():
        for code, spec in table.items():
            try:
                actions.parse(spec)
            except actions.ActionError as exc:
                problems += 1
                print("keyboard.bindings.%s (code %d): %s"
                      % (surface, code, exc), file=sys.stderr)
    for buttons, spec in config.chords:
        try:
            actions.parse(spec)
        except actions.ActionError as exc:
            problems += 1
            print("chord %s: %s" % ("+".join(sorted(buttons)), exc),
                  file=sys.stderr)
    for profile in config.profiles:
        for button, spec in profile["bindings"].items():
            try:
                actions.Binding(spec, config.announced_hold)
            except actions.ActionError as exc:
                problems += 1
                print(
                    "profile %s.%s: %s" % (profile["name"], button, exc),
                    file=sys.stderr,
                )
    try:
        menu.build(config.menu_items, columns=config.menu_columns,
                   settings=config_module.CHOSEN,
                   readings=live_module.READINGS,
                   machine=sysinfo_module.READINGS)
    except menu.MenuError as exc:
        problems += 1
        print("%s" % exc, file=sys.stderr)
    try:
        menu.build_head(config.menu_head, columns=config.menu_columns)
    except menu.MenuError as exc:
        problems += 1
        print("%s" % exc, file=sys.stderr)
    try:
        osk.OskModel(config.osk_layout,
                     overrides=config.osk_key_overrides,
                     badge_align=config.osk_badge_align)
    except osk.OverrideError as exc:
        problems += 1
        print("%s" % exc, file=sys.stderr)
    device = li.find_device(config.device_match)
    if device is None:
        print(
            "warning: %s" % _no_controller(config.device_match),
            file=sys.stderr,
        )
    else:
        profile_name, buttons, _ = config.profile_for(
            device.name, device.vid_pid
        )
        # The layout as well as the profile: badges printing the wrong pad's
        # letters is the sort of thing you look here to find out about.
        print(
            "controller: %s (%s), profile %s, %s badges"
            % (device.name, device.vid_pid, profile_name,
               config.badge_layout(profile_name))
        )
        # Which of the four words this pad can say. Printed because the
        # answer is the device's and the driver's rather than the config's -
        # a pad with no periodic effects answers an edge with a plain tick,
        # and has no texture at all - and the only other way to find out is
        # to press something and notice it felt like something else.
        _report_rumble(config, device)
        # Only when there is something to say: a hand on the pad is the usual
        # reason, so this is not a problem and does not count as one. It is
        # printed because the other reason is a button stuck at the hardware,
        # and `dump` cannot see one - the daemon holds the pad, and asking is
        # the only way through a grab.
        try:
            held = device.held_keys()
        except OSError as exc:
            held = []
            log.debug("could not read the held buttons: %s", exc)
        if held:
            print(
                "held right now: %s - with nothing touching the pad, that is "
                "a stuck button"
                % ", ".join(
                    buttons.get(code, "0x%03x" % code) for code in held
                )
            )
        device.close()
    _report_readings(config)
    _check_settings(config)
    _check_keyboards(config)
    if problems:
        print("%d invalid binding(s)" % problems, file=sys.stderr)
        return 1
    print("configuration OK")
    return 0


def _check_settings(config):
    """Say what was changed from the pad, since it outranks the config file.

    Nothing else says so, and a layout set from the menu months ago is exactly
    the kind of thing you go looking for in config.toml and cannot find.
    """
    if not config.chosen:
        return
    print(
        "chosen from the pad: %s (%s)"
        % (", ".join("%s = %r" % (name, config.chosen[name])
                     for name in sorted(config.chosen)),
           config_module.settings_path())
    )


def _check_keyboards(config):
    """Say which keyboards could send a surface away, since none is a warning.

    A keyboard nobody may read is the ordinary way this fails - the user is not
    in the `input` group yet - and it fails silently at the moment a panel is
    stuck, which is the worst moment to find out.
    """
    from . import kbd

    if not config.keyboard_enabled:
        print("keyboard: off", file=sys.stderr)
        return
    found = kbd.find_keyboards(config.keyboard_match, config.keyboard_ignore)
    if not found:
        print(
            "warning: no keyboard matching %r could be opened - a surface can "
            "then only be closed from the pad or `omapad ctl`"
            % config.keyboard_match,
            file=sys.stderr,
        )
        return
    print(
        "keyboard: %s%s"
        % (
            ", ".join("%s (%s)" % (device.name, device.vid_pid)
                      for device in found),
            " [grabbed while a surface is up]" if config.keyboard_grab else "",
        )
    )
    for device in found:
        device.close()


def cmd_ctl(config, words):
    from . import control, paths

    if not words:
        print("usage: omapad ctl "
              "<osk|menu|guide|map|pad|lock|keep|hud|ripple|press|mode|status>"
              " [...]",
              file=sys.stderr)
        return 2
    try:
        print(control.send(" ".join(words), config.control_socket))
    except paths.RuntimeDirError as exc:
        print("omapad: %s" % exc, file=sys.stderr)
        return 1
    except (OSError, ConnectionRefusedError) as exc:
        print("omapad: no running daemon (%s)" % exc, file=sys.stderr)
        return 1
    return 0


def cmd_unit(words):
    """Write the systemd user unit for this checkout - what `install.sh` calls.

    `unit check` answers the one question without writing anything, so the
    installer can ask whether this checkout can be baked into a unit at all
    before it has written a file or asked for a password.

    Both print one path and nothing else, so the installer can say the
    sentence around it.
    """
    from . import unit

    if words and words != ["check"]:
        print("usage: omapad unit [check]", file=sys.stderr)
        return 2
    try:
        if words:
            print(unit.check_repo(unit.checkout()))
        else:
            print(unit.install_service())
    except (unit.UnitError, OSError) as exc:
        print("omapad: %s" % exc, file=sys.stderr)
        return 1
    return 0


def cmd_run(config):
    try:
        daemon = Daemon(config)
    except UinputError as exc:
        print("omapad: %s" % exc, file=sys.stderr)
        return 1

    def stop(signum, frame):
        log.info("stopping")
        daemon.running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        daemon.run()
    finally:
        daemon.shutdown()
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    if args.command == "unit":
        # Answered before the config is loaded, on purpose: this is what the
        # installer runs, and someone re-running the installer to repair a
        # broken config must not be stopped by that config.
        return cmd_unit(args.args)
    try:
        config = config_module.load(args.config)
    except (config_module.ConfigError, OSError) as exc:
        print("omapad: %s" % exc, file=sys.stderr)
        return 1
    if args.command == "ctl":
        return cmd_ctl(config, args.args)
    if args.command == "check" and args.layout:
        return cmd_check_layout(config)
    return {"run": cmd_run, "dump": cmd_dump,
            "check": cmd_check}[args.command](config)


if __name__ == "__main__":
    sys.exit(main())
