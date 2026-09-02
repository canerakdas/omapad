# evdev - `omapad/linux_input.py`

Minimal evdev bindings on the standard library. `python-evdev` would be one
import and one dependency; this project takes none, and what it actually needs
from evdev is a struct format, a handful of ioctls and a device scan.

## What is here

- **The wire format**: `EVENT_FORMAT = "llHHi"` -
  `struct input_event { sec, usec, type, code, value }` - and the event type
  and code constants (`EV_KEY`, `EV_ABS`, `ABS_X`, `BTN_LEFT`, …). These are
  the kernel's numbers, not decisions: they stay hardcoded.
- **The ioctl encoding**: `_ioc`, `_ior`, `_iow` and the requests built from
  them - `EVIOCGID`, `EVIOCGNAME`, `EVIOCGABS`, `EVIOCGBIT`, `EVIOCGRAB`,
  `EVIOCSFF`, `EVIOCRMFF`. `FF_UNION_OFFSET` and `FF_EFFECT_SIZE` are computed
  from `struct.calcsize` rather than written down, because the union's
  alignment differs between architectures.
- **`AbsInfo`** - an axis's range, with `center` and `half_range` so callers
  do not repeat the arithmetic.
- **`InputDevice`** - open a node and ask it things: `name`, `ids`, `vid_pid`,
  `absinfo`, `capabilities`, `supports_rumble`, `upload_rumble`,
  `play_effect`, `erase_effect`, `grab`/`ungrab`/`grabbed`, `read_events`.
- **Discovery** - `is_gamepad(device)` (absolute axes are what separate a pad
  from a keyboard that also advertises `EV_KEY`), `device_matches(name,
  vid_pid, pattern)` and `find_device(match)` for `[device] match`.

## Rules

- Nothing here decides anything about *behaviour*. It reports what the kernel
  says; profiles, thresholds and names are `config.py`'s problem.
- A new ioctl is added the same way: build the request with `_ior`/`_iow`,
  compute sizes with `struct.calcsize`, and comment the C declaration above
  it. The comments naming the structs are what make this readable against
  `input.h`.
- `read_events()` returns whole events; a partial read is the caller's problem
  to never create.
- The grab is `EVIOCGRAB` and it is exclusive: whoever holds it, nobody else
  sees the pad. Who should hold it is decided in [`handover.md`](handover.md),
  never here.
