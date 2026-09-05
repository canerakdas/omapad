"""Command line entry point."""

import argparse
import errno
import logging
import select
import signal
import sys

from . import __version__, config as config_module, linux_input as li
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
        "command",
        nargs="?",
        default="run",
        choices=("run", "dump", "check", "ctl"),
        help="run the daemon (default), print controller events, validate the "
        "configuration, or send a command to a running daemon",
    )
    parser.add_argument(
        "args",
        nargs="*",
        help="for ctl: osk <toggle|open|close>, menu <toggle|open|close>, "
        "guide <toggle|open|close|next|prev>, "
        "map <toggle|open|close|skip|back|restart|save|cancel>, "
        "surface <close|close_all|back>, ripple <left|right|middle>, "
        "press <BUTTON> [tap|hold], "
        "lock <on|off|toggle>, mode <toggle|desktop|game>, status",
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
        menu.build(config.menu_items)
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
              "<osk|menu|guide|map|pad|lock|ripple|press|mode|status> [...]",
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
    try:
        config = config_module.load(args.config)
    except (config_module.ConfigError, OSError) as exc:
        print("omapad: %s" % exc, file=sys.stderr)
        return 1
    if args.command == "ctl":
        return cmd_ctl(config, args.args)
    return {"run": cmd_run, "dump": cmd_dump, "check": cmd_check}[args.command](config)


if __name__ == "__main__":
    sys.exit(main())
