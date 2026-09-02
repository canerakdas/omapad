# Real keyboards - `omapad/kbd.py`

`uinput.py` is the keyboard omapad writes; this is the one the user types
on. It exists for the case the pad cannot answer: a surface summoned from a
keybind or a terminal, a pad that went flat mid-menu, a panel left up when the
couch session ended. A window that can only be dismissed by the thing that
opened it is a trap.

## The two limits that keep it honest

- **The nodes are opened only while a surface of ours is on screen.** A daemon
  holding every keyboard on the machine open the rest of the time has the
  shape of a keylogger whatever it does with the events.
- **They are not grabbed unless `[keyboard] grab` asks**, so the key still
  reaches whatever is underneath and a mistake here cannot leave the desk with
  a dead keyboard.

Keep both. They are the reason this module is allowed to exist.

## What is here

- `is_keyboard(device)` - Escape plus the whole `Q`–`P` row, and no `ABS_X`.
  `KEY_ESC`, `KEY_Q`, `KEY_P` are not settings: they are what separates
  something a person types on from the lids, power buttons and volume keys
  that also advertise `EV_KEY`. A pad in XInput mode carries `EV_KEY` too,
  which is why the absolute-axis test is there.
- `find_keyboards(match, ignore)` - `[keyboard] match` and
  `[keyboard] ignore`.
- `KeyboardWatch` - `follow(wanted)` opens the nodes when a surface goes up and
  `stop()` closes them when the last one comes down; `fds()` feeds the
  daemon's `poll()`, `read(fd)` yields events.

## What a key does

`config.keyboard_binding_for(surface, code)` decides, from
`[keyboard.bindings.<surface>]` - one table per surface plus `base`. The
daemon routes it through `key_event()`.
