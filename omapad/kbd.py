"""The keyboard already on the desk, as a way out of a surface on screen.

`uinput.py` is the keyboard omapad writes; this is the one the user types
on. It exists for the case the pad cannot answer: a surface summoned from a
keybind or a terminal, a pad that went flat mid-menu, a panel left up when the
couch session ended. A window that can only be dismissed by the thing that
opened it is a trap, and "go and pick the pad back up" is not a way out of one.

Two limits keep this from being more than that. The nodes are opened only
while a surface of ours is on screen - a daemon holding every keyboard on the
machine open the rest of the time has the shape of a keylogger whatever it
does with the events - and they are not grabbed unless `[keyboard] grab` asks,
so the key still reaches whatever is underneath and a mistake here cannot
leave the desk with a dead keyboard.
"""

import glob
import logging
import os
import struct

from . import linux_input as li
from . import uinput

log = logging.getLogger("omapad")

# Escape and the letter row. Not a setting: it is what separates something a
# person types on from the lids, power buttons and volume keys that also
# advertise EV_KEY and would otherwise all be opened.
KEY_ESC = 1
KEY_Q = 16
KEY_P = 25

SYSFS_INPUT = "/sys/class/input"

# sysfs prints a capability bitmap as one hex word per kernel `long`, the most
# significant first. The kernel's long is the native one for a native Python,
# so this is a fact about the build rather than a choice.
LONG_BITS = struct.calcsize("@l") * 8


def is_keyboard(device):
    """Does this node look like something a person types on?"""
    keys = device.capabilities(li.EV_KEY, KEY_P + 1)
    if KEY_ESC not in keys:
        return False
    if not all(code in keys for code in range(KEY_Q, KEY_P + 1)):
        return False
    # A pad in XInput mode carries EV_KEY too; absolute axes are what tell the
    # two apart, the same test find_device() makes from the other side.
    return li.ABS_X not in device.capabilities(li.EV_ABS, li.ABS_HAT0Y + 1)


class SysfsNode:
    """What an event node says about itself in sysfs, without opening it.

    The reason this exists is what closing one costs. evdev waits out an RCU
    grace period on every close - about 6 ms here - so a scan that opened all
    eighteen nodes to look at them and closed the seventeen that were not
    keyboards held the loop for up to 200 ms after every surface came up, and
    the first press on it waited that long. The same name, ids and capability
    bits are readable under /sys/class/input with nothing opened, so only a
    node that is going to be kept is ever opened, and nothing is closed.

    Answers the three things `is_keyboard` and `_wanted` ask of an
    `InputDevice`, in the same shapes.
    """

    def __init__(self, path, root=SYSFS_INPUT):
        base = os.path.join(root, os.path.basename(path), "device")
        self.path = path
        self.name = self._read(base, "name")
        self.vid_pid = "%04X:%04X" % (int(self._read(base, "id/vendor"), 16),
                                      int(self._read(base, "id/product"), 16))
        self._bits = {
            li.EV_KEY: self._bitmap(self._read(base, "capabilities/key")),
            li.EV_ABS: self._bitmap(self._read(base, "capabilities/abs")),
        }

    @staticmethod
    def _read(base, name):
        with open(os.path.join(base, name)) as handle:
            return handle.read().strip()

    @staticmethod
    def _bitmap(text):
        value = 0
        for word in text.split():
            value = (value << LONG_BITS) | int(word, 16)
        return value

    def capabilities(self, ev_type, max_code):
        bits = self._bits.get(ev_type, 0)
        return {code for code in range(max_code) if bits >> code & 1}


def _wanted(device, wanted, ignore):
    """Is this node one to listen on, by `[keyboard] match` and `ignore`?"""
    name = device.name
    keep = (
        is_keyboard(device)
        and device.vid_pid not in uinput.IDENTITIES
        and not any(token.upper() in name.upper()
                    for token in ignore if token.strip())
    )
    if keep and wanted != "AUTO":
        keep = (device.vid_pid == wanted if ":" in wanted
                else wanted in name.upper())
    return keep


def find_keyboards(match="auto", ignore=(), root=SYSFS_INPUT):
    """Every keyboard node worth listening to.

    `match` is "auto" for all of them, or one "VVVV:PPPP" / name substring,
    spelled the way `[device] match` spells one (this side takes a single
    pattern, not a list of them). `ignore` drops nodes by name substring. Our
    own virtual devices are dropped whatever is configured: reading what the
    on-screen keyboard types would feed every keystroke straight back into the
    surface that typed it.

    Decided from sysfs and opened only once kept - see `SysfsNode`. A node
    sysfs will not describe is opened and asked instead, the slow way, rather
    than missed: a keyboard left out is a way out of a surface gone.
    """
    wanted = (match or "auto").strip().upper()
    found = []
    for path in sorted(glob.glob("/dev/input/event*")):
        try:
            node = SysfsNode(path, root)
        except (OSError, ValueError):
            node = None
        if node is not None:
            if not _wanted(node, wanted, ignore):
                continue
            try:
                found.append(li.InputDevice(path))
            except OSError:
                pass
            continue
        try:
            device = li.InputDevice(path)
        except OSError:
            continue
        keep = False
        try:
            keep = _wanted(device, wanted, ignore)
        except OSError:
            keep = False
        finally:
            if not keep:
                device.close()
        if keep:
            found.append(device)
    return found


class KeyboardWatch:
    """The open keyboards, for exactly as long as a surface needs them."""

    def __init__(self, config, finder=find_keyboards):
        self.config = config
        self._find = finder
        self.devices = {}
        self.listening = False
        # A node died mid-surface and its descriptor is gone; the loop has to
        # be told even though nothing about what it wants has changed.
        self.stale = False

    def follow(self, wanted):
        """Match the open keyboards to whether a surface needs them.

        True when the set of descriptors changed and the caller must register
        them again.
        """
        wanted = bool(wanted) and self.config.keyboard_enabled
        changed, self.stale = self.stale, False
        if wanted and not self.listening:
            self.start()
            changed = True
        elif not wanted and self.listening:
            self.stop()
            changed = True
        elif wanted and changed and not self.devices:
            # Every keyboard we had went away - a dock unplugged, a receiver
            # reset - while a surface is still up. Look again rather than stay
            # deaf until the next time one opens.
            self.start()
        return changed

    def start(self):
        self.stop()
        devices = self._find(self.config.keyboard_match,
                             self.config.keyboard_ignore)
        self.devices = dict((device.fd, device) for device in devices)
        self.listening = True
        if not devices:
            log.info("no keyboard matching %r to listen on",
                     self.config.keyboard_match)
            return
        log.debug("listening on %d keyboard(s)", len(devices))
        if not self.config.keyboard_grab:
            return
        for device in devices:
            try:
                device.grab()
            except OSError as exc:
                # Someone else has it, or we may only read it. Ungrabbed is
                # the ordinary way to run; it is not worth refusing over.
                log.warning("could not grab %s: %s", device.path, exc)

    def stop(self):
        for device in self.devices.values():
            device.close()
        self.devices = {}
        self.listening = False

    def fds(self):
        return tuple(self.devices)

    def read(self, fd):
        """Drain one keyboard. Yields (type, code, value); [] once it is gone."""
        device = self.devices.get(fd)
        if device is None:
            return []
        try:
            return list(device.read_events())
        except OSError:
            log.info("keyboard %s went away", device.path)
            device.close()
            del self.devices[fd]
            self.stale = True
            return []

    def close(self):
        self.stop()
