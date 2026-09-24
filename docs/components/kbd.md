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
  `[keyboard] ignore`, decided from sysfs through `SysfsNode` and opened only
  once kept. A node sysfs will not describe is opened and asked instead,
  because a keyboard missed is a way out of a surface gone.

## Why the scan never opens a node to look at it

It runs on the loop, as a surface comes up. evdev waits out an RCU grace
period on every **close** - about 6 ms a node here, while the open costs
nothing - so opening all eighteen of this machine's nodes to ask each one and
closing the seventeen that were not keyboards held the loop for 150-200 ms
after every surface opened, and the first press on a menu waited that long.
`omapad budget stress` found it: a fast median with a slow slowest tenth, the
command *after* each open paying for it. `/sys/class/input/eventN/device`
carries the same name, ids and capability bitmaps with nothing opened, so the
scan now costs about a millisecond and closes nothing. `SysfsNode` answers
`name`, `vid_pid` and `capabilities()` in the shapes `InputDevice` does, so
`is_keyboard` asks both the same question.
- `KeyboardWatch` - `follow(wanted)` opens the nodes when a surface goes up and
  `stop()` closes them when the last one comes down; `fds()` feeds the
  daemon's `poll()`, `read(fd)` yields events.

## What a key does

`config.keyboard_binding_for(surface, code)` decides, from
`[keyboard.bindings.<surface>]` - one table per surface plus `base`. The
daemon routes it through `key_event()`.
