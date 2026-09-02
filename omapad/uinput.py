"""Virtual mouse and keyboard devices via /dev/uinput, stdlib only."""

import fcntl
import os
import struct
import time

from .linux_input import (
    BTN_EXTRA,
    BTN_LEFT,
    BTN_MIDDLE,
    BTN_RIGHT,
    BTN_SIDE,
    EVENT_FORMAT,
    EV_KEY,
    EV_REL,
    EV_REP,
    EV_SYN,
    REL_HWHEEL,
    REL_HWHEEL_HI_RES,
    REL_WHEEL,
    REL_WHEEL_HI_RES,
    REL_X,
    REL_Y,
    SYN_REPORT,
    _iow,
)

UINPUT_PATH = "/dev/uinput"
UINPUT_SETUP_FORMAT = "HHHH80sI"  # struct uinput_setup

UI_DEV_CREATE = _iow("U", 1, 0) & ~(1 << 30)  # _IO('U', 1)
UI_DEV_DESTROY = _iow("U", 2, 0) & ~(1 << 30)  # _IO('U', 2)
UI_DEV_SETUP = _iow("U", 3, struct.calcsize(UINPUT_SETUP_FORMAT))
UI_SET_EVBIT = _iow("U", 100, 4)
UI_SET_KEYBIT = _iow("U", 101, 4)
UI_SET_RELBIT = _iow("U", 102, 4)

BUS_VIRTUAL = 0x06

MOUSE_BUTTONS = {
    "left": BTN_LEFT,
    "right": BTN_RIGHT,
    "middle": BTN_MIDDLE,
    "back": BTN_SIDE,
    "forward": BTN_EXTRA,
}

# One wheel notch in high-resolution units, as reported by real mice.
WHEEL_HI_RES_STEP = 120


class UinputError(RuntimeError):
    pass


# What our own virtual devices answer to. Named because anything that reads
# /dev/input has to be able to tell them from a real device: kbd.py opens
# every keyboard it finds, and reading this one back would feed everything the
# on-screen keyboard types straight into the surface that typed it.
VENDOR = 0x1D6B
MOUSE_PRODUCT = 0x0101
KEYBOARD_PRODUCT = 0x0102
IDENTITIES = (
    "%04X:%04X" % (VENDOR, MOUSE_PRODUCT),
    "%04X:%04X" % (VENDOR, KEYBOARD_PRODUCT),
)


class VirtualDevice:
    def __init__(self, name, vendor=VENDOR, product=0x0001, version=1):
        try:
            self.fd = os.open(UINPUT_PATH, os.O_WRONLY | os.O_NONBLOCK)
        except FileNotFoundError as exc:
            raise UinputError(
                "/dev/uinput does not exist - run: sudo modprobe uinput"
            ) from exc
        except PermissionError as exc:
            raise UinputError(
                "no permission on /dev/uinput - install the udev rule "
                "(see install.sh) and re-login"
            ) from exc
        self.name = name
        self._vendor = vendor
        self._product = product
        self._version = version
        self._created = False

    def _set_bit(self, request, value):
        fcntl.ioctl(self.fd, request, value)

    def _create(self):
        setup = struct.pack(
            UINPUT_SETUP_FORMAT,
            BUS_VIRTUAL,
            self._vendor,
            self._product,
            self._version,
            self.name.encode("utf-8")[:79],
            0,
        )
        fcntl.ioctl(self.fd, UI_DEV_SETUP, setup)
        fcntl.ioctl(self.fd, UI_DEV_CREATE)
        self._created = True
        # Give udev/libinput a moment to pick the new node up before we
        # start pushing events at it.
        time.sleep(0.1)

    def write(self, etype, code, value):
        os.write(self.fd, struct.pack(EVENT_FORMAT, 0, 0, etype, code, value))

    def syn(self):
        self.write(EV_SYN, SYN_REPORT, 0)

    def close(self):
        if self.fd is None:
            return
        try:
            if self._created:
                fcntl.ioctl(self.fd, UI_DEV_DESTROY)
        except OSError:
            pass
        try:
            os.close(self.fd)
        except OSError:
            pass
        self.fd = None


class VirtualMouse(VirtualDevice):
    def __init__(self, name="omapad virtual mouse"):
        super().__init__(name, product=MOUSE_PRODUCT)
        self._set_bit(UI_SET_EVBIT, EV_KEY)
        for code in MOUSE_BUTTONS.values():
            self._set_bit(UI_SET_KEYBIT, code)
        self._set_bit(UI_SET_EVBIT, EV_REL)
        for code in (
            REL_X,
            REL_Y,
            REL_WHEEL,
            REL_HWHEEL,
            REL_WHEEL_HI_RES,
            REL_HWHEEL_HI_RES,
        ):
            self._set_bit(UI_SET_RELBIT, code)
        self._create()
        self._pressed = set()

    def move(self, dx, dy):
        if not dx and not dy:
            return
        if dx:
            self.write(EV_REL, REL_X, int(dx))
        if dy:
            self.write(EV_REL, REL_Y, int(dy))
        self.syn()

    def button(self, name, pressed):
        code = MOUSE_BUTTONS.get(name)
        if code is None:
            return
        if pressed:
            self._pressed.add(code)
        else:
            self._pressed.discard(code)
        self.write(EV_KEY, code, 1 if pressed else 0)
        self.syn()

    def scroll(self, hi_res_x, hi_res_y):
        """Scroll by high-resolution units (120 = one notch).

        Both the hi-res and the legacy discrete axes are emitted, exactly as
        real high-resolution mice do; libinput prefers the hi-res axis and
        discards the legacy one, so this never double-scrolls.
        """
        if not hi_res_x and not hi_res_y:
            return
        if hi_res_y:
            self.write(EV_REL, REL_WHEEL_HI_RES, int(hi_res_y))
            notches = int(hi_res_y / WHEEL_HI_RES_STEP)
            if notches:
                self.write(EV_REL, REL_WHEEL, notches)
        if hi_res_x:
            self.write(EV_REL, REL_HWHEEL_HI_RES, int(hi_res_x))
            notches = int(hi_res_x / WHEEL_HI_RES_STEP)
            if notches:
                self.write(EV_REL, REL_HWHEEL, notches)
        self.syn()

    def release_all(self):
        for code in list(self._pressed):
            self.write(EV_KEY, code, 0)
        self._pressed.clear()
        self.syn()


class VirtualKeyboard(VirtualDevice):
    # Keep to the KEY_* ranges and skip every BTN_* block, so this is a
    # keyboard to everything that looks at it. Three blocks, not one: BTN_MISC
    # through BTN_GEAR_UP (0x100-0x15f) is the obvious one, but BTN_DPAD_*
    # (0x220-0x223) and the forty BTN_TRIGGER_HAPPY (0x2c0-0x2e7) sit in the
    # middle of the high KEY_* range. Declaring those is enough for joydev to
    # attach a /dev/input/js* node, and then anything scanning for controllers
    # - Steam does it at startup - finds a phantom pad whose buttons are this
    # keyboard's keys, and starts sending whatever its desktop layout maps
    # them to. Nothing omapad types reaches past KEY_MICMUTE (0xf8) anyway.
    KEY_RANGES = ((1, 0x100), (0x160, 0x220), (0x224, 0x2C0))

    def __init__(self, name="omapad virtual keyboard"):
        super().__init__(name, product=KEYBOARD_PRODUCT)
        self._set_bit(UI_SET_EVBIT, EV_KEY)
        for start, end in self.KEY_RANGES:
            for code in range(start, end):
                self._set_bit(UI_SET_KEYBIT, code)
        # Advertising EV_REP lets the compositor apply the user's own key
        # repeat delay/rate to held keys such as the D-pad arrows.
        self._set_bit(UI_SET_EVBIT, EV_REP)
        self._create()
        self._pressed = set()

    def key(self, code, pressed):
        if pressed:
            self._pressed.add(code)
        else:
            self._pressed.discard(code)
        self.write(EV_KEY, code, 1 if pressed else 0)
        self.syn()

    def chord(self, mods, code, pressed):
        """Press/release `code` with `mods` held around it."""
        if pressed:
            for mod in mods:
                self.key(mod, True)
            self.key(code, True)
        else:
            self.key(code, False)
            for mod in reversed(mods):
                self.key(mod, False)

    def release_all(self):
        for code in list(self._pressed):
            self.write(EV_KEY, code, 0)
        self._pressed.clear()
        self.syn()
