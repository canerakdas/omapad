"""Minimal evdev bindings built on stdlib only (no python-evdev dependency)."""

import fcntl
import glob
import os
import struct

# struct input_event { __kernel_ulong_t sec, usec; __u16 type, code; __s32 value; }
EVENT_FORMAT = "llHHi"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)

EV_SYN = 0x00
EV_KEY = 0x01
EV_REL = 0x02
EV_ABS = 0x03
EV_MSC = 0x04
EV_REP = 0x14
EV_FF = 0x15

SYN_REPORT = 0

ABS_X = 0x00
ABS_Y = 0x01
ABS_RX = 0x03
ABS_RY = 0x04
ABS_Z = 0x02
ABS_RZ = 0x05
ABS_HAT0X = 0x10
ABS_HAT0Y = 0x11

REL_X = 0x00
REL_Y = 0x01
REL_HWHEEL = 0x06
REL_WHEEL = 0x08
REL_WHEEL_HI_RES = 0x0B
REL_HWHEEL_HI_RES = 0x0C

BTN_LEFT = 0x110
BTN_RIGHT = 0x111
BTN_MIDDLE = 0x112
BTN_SIDE = 0x113
BTN_EXTRA = 0x114

_IOC_NRBITS, _IOC_TYPEBITS, _IOC_SIZEBITS = 8, 8, 14
_IOC_NRSHIFT = 0
_IOC_TYPESHIFT = _IOC_NRSHIFT + _IOC_NRBITS
_IOC_SIZESHIFT = _IOC_TYPESHIFT + _IOC_TYPEBITS
_IOC_DIRSHIFT = _IOC_SIZESHIFT + _IOC_SIZEBITS
_IOC_WRITE, _IOC_READ = 1, 2


def _ioc(direction, typ, nr, size):
    return (
        (direction << _IOC_DIRSHIFT)
        | (ord(typ) << _IOC_TYPESHIFT)
        | (nr << _IOC_NRSHIFT)
        | (size << _IOC_SIZESHIFT)
    )


def _ior(typ, nr, size):
    return _ioc(_IOC_READ, typ, nr, size)


def _iow(typ, nr, size):
    return _ioc(_IOC_WRITE, typ, nr, size)


EVIOCGID = _ior("E", 0x02, 8)  # struct input_id: bustype, vendor, product, version
EVIOCGRAB = _iow("E", 0x90, 4)

FF_RUMBLE = 0x50
FF_MAX = 0x7F

# struct ff_effect is a run of u16 fields followed by a union whose widest
# member (ff_periodic_effect) ends in a pointer. So both the union's offset and
# the struct's size follow the platform's alignment rather than the bytes we
# actually set - which are the two u16s of ff_rumble_effect at the union's
# start. EVIOCSFF encodes that size, so it has to be right.
FF_HEADER = "@HhHHHHH"  # type, id, direction, trigger{button, interval},
                        # replay{length, delay}
_FF_UNION_ALIGN = struct.calcsize("@P")
FF_UNION_OFFSET = (
    (struct.calcsize(FF_HEADER) + _FF_UNION_ALIGN - 1)
    // _FF_UNION_ALIGN * _FF_UNION_ALIGN
)
FF_EFFECT_SIZE = FF_UNION_OFFSET + struct.calcsize("@HHhhHHHHHIP")

EVIOCSFF = _iow("E", 0x80, FF_EFFECT_SIZE)
EVIOCRMFF = _iow("E", 0x81, 4)


def EVIOCGNAME(length):
    return _ior("E", 0x06, length)


def EVIOCGABS(axis):
    # struct input_absinfo: value, minimum, maximum, fuzz, flat, resolution (6 * s32)
    return _ior("E", 0x40 + axis, 24)


def EVIOCGBIT(ev_type, length):
    return _ior("E", 0x20 + ev_type, length)


class AbsInfo:
    __slots__ = ("value", "minimum", "maximum", "fuzz", "flat", "resolution")

    def __init__(self, value, minimum, maximum, fuzz, flat, resolution):
        self.value = value
        self.minimum = minimum
        self.maximum = maximum
        self.fuzz = fuzz
        self.flat = flat
        self.resolution = resolution

    @property
    def center(self):
        return (self.minimum + self.maximum) / 2.0

    @property
    def half_range(self):
        return max((self.maximum - self.minimum) / 2.0, 1.0)


class InputDevice:
    """A handle on /dev/input/eventN: read-only unless the node lets us write.

    Writing is only ever for force feedback - an effect is uploaded with an
    ioctl and played by writing an EV_FF event to the same fd. The udev rules
    hand the `input` group write access, but a pad we may only read is still a
    perfectly good pad, so a refused O_RDWR is not an error.
    """

    def __init__(self, path):
        self.path = path
        try:
            self.fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
            self.writable = True
        except OSError:
            self.fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            self.writable = False
        self._grabbed = False

    def close(self):
        if self.fd is not None:
            try:
                if self._grabbed:
                    self.ungrab()
            except OSError:
                pass
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None

    @property
    def name(self):
        buf = bytearray(256)
        fcntl.ioctl(self.fd, EVIOCGNAME(len(buf)), buf)
        return buf.split(b"\x00", 1)[0].decode("utf-8", "replace").strip()

    @property
    def ids(self):
        buf = fcntl.ioctl(self.fd, EVIOCGID, bytes(8))
        bustype, vendor, product, version = struct.unpack("HHHH", buf)
        return {
            "bustype": bustype,
            "vendor": vendor,
            "product": product,
            "version": version,
        }

    @property
    def vid_pid(self):
        ids = self.ids
        return "%04X:%04X" % (ids["vendor"], ids["product"])

    def absinfo(self, axis):
        try:
            buf = fcntl.ioctl(self.fd, EVIOCGABS(axis), bytes(24))
        except OSError:
            return None
        return AbsInfo(*struct.unpack("iiiiii", buf))

    def capabilities(self, ev_type, max_code):
        """Return the set of codes supported for ev_type."""
        nbytes = (max_code + 7) // 8
        buf = bytearray(nbytes)
        try:
            fcntl.ioctl(self.fd, EVIOCGBIT(ev_type, nbytes), buf)
        except OSError:
            return set()
        return {i for i in range(max_code) if buf[i // 8] >> (i % 8) & 1}

    def supports_rumble(self):
        if not self.writable:
            return False
        if EV_FF not in self.capabilities(0, EV_FF + 1):
            return False
        return FF_RUMBLE in self.capabilities(EV_FF, FF_MAX + 1)

    def upload_rumble(self, strong, weak, length_ms, effect_id=-1):
        """Upload a rumble effect, or replace the one already at effect_id.

        Returns the id the kernel assigned, which is what plays it.
        """
        buf = bytearray(FF_EFFECT_SIZE)
        struct.pack_into(
            FF_HEADER, buf, 0, FF_RUMBLE, effect_id, 0, 0, 0, length_ms, 0
        )
        struct.pack_into("@HH", buf, FF_UNION_OFFSET, strong, weak)
        fcntl.ioctl(self.fd, EVIOCSFF, buf, True)
        return struct.unpack_from("@h", buf, 2)[0]

    def play_effect(self, effect_id, count=1):
        """Play an uploaded effect; count=0 stops it."""
        os.write(
            self.fd, struct.pack(EVENT_FORMAT, 0, 0, EV_FF, effect_id, count)
        )

    def erase_effect(self, effect_id):
        fcntl.ioctl(self.fd, EVIOCRMFF, effect_id)

    def grab(self):
        if not self._grabbed:
            fcntl.ioctl(self.fd, EVIOCGRAB, 1)
            self._grabbed = True

    def ungrab(self):
        if self._grabbed:
            fcntl.ioctl(self.fd, EVIOCGRAB, 0)
            self._grabbed = False

    @property
    def grabbed(self):
        return self._grabbed

    def read_events(self):
        """Yield (type, code, value). Raises OSError when the device goes away."""
        try:
            data = os.read(self.fd, EVENT_SIZE * 64)
        except BlockingIOError:
            return
        for offset in range(0, len(data) - EVENT_SIZE + 1, EVENT_SIZE):
            _, _, etype, code, value = struct.unpack_from(
                EVENT_FORMAT, data, offset
            )
            yield etype, code, value


def is_gamepad(device):
    """Does this node look like a pad, rather than the rest of what a pad opens?

    Absolute axes and buttons in the joystick range, both. The IMU, touch and
    consumer-control nodes some pads enumerate carry one or the other and never
    both, and a wireless Xbox pad brings keyboard and mouse nodes of its own -
    this is the test that leaves all of them behind. It is what makes a pad a
    pad here, so an unknown pad needs nothing written in the config to be found.
    """
    if ABS_X not in device.capabilities(EV_ABS, ABS_HAT0Y + 1):
        return False
    keys = device.capabilities(EV_KEY, 0x150)
    return any(code in keys for code in range(0x130, 0x140))


def device_matches(name, vid_pid, pattern):
    """Does one `[device] match` pattern name this device?

    "VVVV:PPPP" is compared against the identity, anything else is taken as a
    case-insensitive part of the name.
    """
    wanted = pattern.strip().upper()
    if ":" in wanted:
        return vid_pid.upper() == wanted
    return wanted in name.upper()


def find_device(match=()):
    """The pad to drive, or None if none is connected.

    `match` is empty for any pad at all, or a pattern - or a list of them,
    tried in the order written, so a preferred pad beats one that merely
    happens to be plugged in too. Whatever is asked, only nodes that pass
    `is_gamepad` are considered, so naming a pad cannot land on the keyboard
    node it also opens.
    """
    if isinstance(match, str):
        match = [match] if match.strip() else []
    patterns = list(match) or [None]
    pads = []
    for path in sorted(glob.glob("/dev/input/event*")):
        try:
            device = InputDevice(path)
        except OSError:
            continue
        try:
            keep = is_gamepad(device)
        except OSError:
            keep = False
        if keep:
            pads.append(device)
        else:
            device.close()
    chosen = None
    for pattern in patterns:
        for device in pads:
            try:
                hit = pattern is None or device_matches(
                    device.name, device.vid_pid, pattern
                )
            except OSError:
                hit = False
            if hit:
                chosen = device
                break
        if chosen is not None:
            break
    for device in pads:
        if device is not chosen:
            device.close()
    return chosen
