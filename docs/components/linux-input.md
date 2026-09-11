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
  `EVIOCSFF`, `EVIOCRMFF`, `EVIOCGEFFECTS`. `FF_UNION_OFFSET` and
  `FF_EFFECT_SIZE` are computed from `struct.calcsize` rather than written
  down, because the union's alignment differs between architectures.
- **`AbsInfo`** - an axis's range, with `center` and `half_range` so callers
  do not repeat the arithmetic.
- **`InputDevice`** - open a node and ask it things: `name`, `ids`, `vid_pid`,
  `absinfo`, `capabilities`, `supports_effects`, `supports_rumble`,
  `effect_slots`, `upload_rumble`, `upload_periodic`, `play_effect`,
  `erase_effect`, `grab`/`ungrab`/`grabbed`, `read_events`.
- **Discovery** - `is_gamepad(device)` (absolute axes are what separate a pad
  from a keyboard that also advertises `EV_KEY`), `device_matches(name,
  vid_pid, pattern)` and `find_device(match)` for `[device] match`.

## Force feedback

`FF_EFFECT_SIZE` was sized from `"@HHhhHHHHHIP"` at `FF_UNION_OFFSET` from the
first day there was a tick, and that format string **is**
`ff_periodic_effect` - the union's widest member. So a periodic effect needs
no more room than the rumble one already reserved, and `FF_PERIODIC_FORMAT` is
the same bytes named rather than counted. `EVIOCSFF` encodes that size in its
number, so it has to stay right; a test asserts the periodic body fits.

`upload_periodic`'s `magnitude` is an **s16** where `upload_rumble`'s pair are
u16s. Pack a full-scale unsigned value into it and the pad gets a phase
inversion at full strength rather than what was asked for.

`supports_effects()` returns one set because the kernel reports effect types
and waveforms in the same bitmap: `FF_PERIODIC` says a periodic effect is
possible and `FF_SINE` says which one, and a pad answering the first without
the second takes the upload and plays nothing. Which words get built out of
that is [`rumble.md`](rumble.md)'s decision, not this file's.

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
