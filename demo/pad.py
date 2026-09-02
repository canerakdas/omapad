"""A virtual XInput pad on /dev/uinput, so a take can be driven without hands.

Demo tooling, not part of the daemon. It exists so the recording can hold a
trigger, roll a stick and fire a chord the way a thumb does, instead of poking
the surfaces through the control socket: everything the daemon sees arrives on
the same evdev path a real pad uses, so what the video shows is the whole input
path deciding, not a script pretending.

Only what a take needs is here - `uinput.py` covers the output devices and has
no absolute axes, which a pad is mostly made of. Force feedback is left out:
`rumble.py` uploads an effect to the pad, and a virtual one has no motor to
upload it to.
"""

import fcntl
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad import linux_input as li

EV_SYN = 0x00
EV_KEY = 0x01
EV_ABS = 0x03
SYN_REPORT = 0

ABS_X = 0x00
ABS_Y = 0x01
ABS_Z = 0x02
ABS_RX = 0x03
ABS_RY = 0x04
ABS_RZ = 0x05
ABS_HAT0X = 0x10
ABS_HAT0Y = 0x11

UINPUT_PATH = "/dev/uinput"
UINPUT_SETUP_FORMAT = "HHHH80sI"      # struct uinput_setup
UINPUT_ABS_SETUP_FORMAT = "@Hxx6i"    # struct uinput_abs_setup

_IOC_WRITE = 1


def _iow(typ, nr, size):
    return (_IOC_WRITE << 30) | (ord(typ) << 8) | nr | (size << 16)


UI_DEV_CREATE = (ord("U") << 8) | 1
UI_DEV_DESTROY = (ord("U") << 8) | 2
UI_DEV_SETUP = _iow("U", 3, struct.calcsize(UINPUT_SETUP_FORMAT))
UI_ABS_SETUP = _iow("U", 4, struct.calcsize(UINPUT_ABS_SETUP_FORMAT))
UI_SET_EVBIT = _iow("U", 100, 4)
UI_SET_KEYBIT = _iow("U", 101, 4)
UI_SET_ABSBIT = _iow("U", 103, 4)

BUS_USB = 0x03

# An Xbox 360 pad's identity, because `profile = "auto"` has to land on `xbox`
# for this device the same way it would for a real one. A demo-only vendor id
# would need a demo-only branch in `detect_profile`, and a demo that needs the
# daemon changed to work is not a demo of the daemon.
VENDOR = 0x045E
PRODUCT = 0x028E

# The xbox profile's table read the other way round: omapad's logical name to
# the code an XInput pad sends. ZL and ZR are absent because on this profile
# they are analog axes rather than keys - which is the case worth demoing,
# since it is the one with a threshold in it.
BUTTONS = {
    "A": 0x130, "B": 0x131, "X": 0x133, "Y": 0x134,
    "L": 0x136, "R": 0x137,
    "MINUS": 0x13A, "PLUS": 0x13B, "HOME": 0x13C,
    "LSTICK": 0x13D, "RSTICK": 0x13E,
}

DPAD = {
    "DPAD_LEFT": (ABS_HAT0X, -1), "DPAD_RIGHT": (ABS_HAT0X, 1),
    "DPAD_UP": (ABS_HAT0Y, -1), "DPAD_DOWN": (ABS_HAT0Y, 1),
}

TRIGGERS = {"ZL": ABS_Z, "ZR": ABS_RZ}

STICK_MIN = -32768
STICK_MAX = 32767
TRIGGER_MAX = 255

# min, max, fuzz, flat. The sticks carry the flat zone a real pad reports, so
# the daemon's own deadzone is doing the same job it does on hardware.
AXES = {
    ABS_X: (STICK_MIN, STICK_MAX, 16, 128),
    ABS_Y: (STICK_MIN, STICK_MAX, 16, 128),
    ABS_RX: (STICK_MIN, STICK_MAX, 16, 128),
    ABS_RY: (STICK_MIN, STICK_MAX, 16, 128),
    ABS_Z: (0, TRIGGER_MAX, 0, 0),
    ABS_RZ: (0, TRIGGER_MAX, 0, 0),
    ABS_HAT0X: (-1, 1, 0, 0),
    ABS_HAT0Y: (-1, 1, 0, 0),
}

# udev has to notice the node and apply its rules before anything can find it
# by name, and the daemon looks exactly once, at connect time.
SETTLE = 0.6


class PadError(RuntimeError):
    pass


class VirtualPad:
    """One pad, alive for as long as the object is."""

    def __init__(self, name="omapad demo pad"):
        # A uinput device outlives nothing but the process holding its fd, so
        # a second one under the same name means an earlier take was killed
        # rather than closed. `find_device` takes the first node that matches,
        # which would be the dead one - and the take would then record two
        # minutes of a pad nobody is listening to. Loudly, here, rather than
        # silently, there.
        stale = li.find_device([name])
        if stale is not None:
            stale.close()
            raise PadError(
                "a device called %r is already there - an earlier take was "
                "killed. Close it before recording." % name)
        try:
            self.fd = os.open(UINPUT_PATH, os.O_WRONLY | os.O_NONBLOCK)
        except OSError as exc:
            raise PadError("%s: %s - is the user in the input group?"
                           % (UINPUT_PATH, exc))
        self.name = name
        self._create()
        time.sleep(SETTLE)

    def _create(self):
        for evbit in (EV_KEY, EV_ABS):
            fcntl.ioctl(self.fd, UI_SET_EVBIT, evbit)
        for code in BUTTONS.values():
            fcntl.ioctl(self.fd, UI_SET_KEYBIT, code)
        for axis in sorted(AXES):
            low, high, fuzz, flat = AXES[axis]
            fcntl.ioctl(self.fd, UI_SET_ABSBIT, axis)
            fcntl.ioctl(self.fd, UI_ABS_SETUP, struct.pack(
                UINPUT_ABS_SETUP_FORMAT, axis, 0, low, high, fuzz, flat, 0))
        fcntl.ioctl(self.fd, UI_DEV_SETUP, struct.pack(
            UINPUT_SETUP_FORMAT, BUS_USB, VENDOR, PRODUCT, 1,
            self.name.encode("utf-8")[:79], 0))
        fcntl.ioctl(self.fd, UI_DEV_CREATE, 0)

    # -- the wire ----------------------------------------------------------

    def _write(self, etype, code, value):
        now = time.time()
        os.write(self.fd, struct.pack(
            "llHHi", int(now), int((now % 1) * 1e6), etype, code, value))

    def syn(self):
        self._write(EV_SYN, SYN_REPORT, 0)

    def emit(self, etype, code, value):
        self._write(etype, code, value)
        self.syn()

    # -- what a thumb does -------------------------------------------------

    def down(self, button):
        """Press, by omapad's logical name - trigger, hat or key alike."""
        if button in TRIGGERS:
            self.emit(EV_ABS, TRIGGERS[button], TRIGGER_MAX)
        elif button in DPAD:
            axis, value = DPAD[button]
            self.emit(EV_ABS, axis, value)
        elif button in BUTTONS:
            self.emit(EV_KEY, BUTTONS[button], 1)
        else:
            raise PadError("no such button: %s" % button)

    def up(self, button):
        if button in TRIGGERS:
            self.emit(EV_ABS, TRIGGERS[button], 0)
        elif button in DPAD:
            axis, _ = DPAD[button]
            self.emit(EV_ABS, axis, 0)
        elif button in BUTTONS:
            self.emit(EV_KEY, BUTTONS[button], 0)
        else:
            raise PadError("no such button: %s" % button)

    def tap(self, button, length=0.06):
        self.down(button)
        time.sleep(length)
        self.up(button)

    def chord(self, first, second, length=0.12):
        """Both down before either comes up, which is what a chord is: the
        daemon fires it on the second press and neither button does its own
        job."""
        self.down(first)
        time.sleep(0.04)
        self.down(second)
        time.sleep(length)
        self.up(second)
        time.sleep(0.03)
        self.up(first)

    def stick(self, which, x, y):
        """Hold a stick at -1..1 on each axis. "L" or "R"."""
        axes = (ABS_X, ABS_Y) if which == "L" else (ABS_RX, ABS_RY)
        for axis, value in zip(axes, (x, y)):
            value = max(-1.0, min(1.0, value))
            span = STICK_MAX if value >= 0 else -STICK_MIN
            self._write(EV_ABS, axis, int(value * span))
        self.syn()

    def stick_hold(self, which, x, y, seconds):
        self.stick(which, x, y)
        time.sleep(seconds)
        self.stick(which, 0, 0)

    def rest(self):
        """Both sticks centred - a take must not end mid-flick."""
        self.stick("L", 0, 0)
        self.stick("R", 0, 0)

    def close(self):
        try:
            fcntl.ioctl(self.fd, UI_DEV_DESTROY, 0)
        except OSError:
            pass
        os.close(self.fd)
