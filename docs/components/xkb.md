# XKB labels - `omapad/xkb.py`

What the keys are actually printed with, read back from the compositor's
layout. The on-screen keyboard types keycodes, and a keycode means a different
character on a Turkish layout than on a US one - so the *labels* are asked for
rather than assumed.

## How

- `active_layout(devices)` reads which layout and variant are in force out of
  Hyprland's `j/devices` answer, which the caller asks over the IPC socket.
  It used to spawn `hyprctl` itself, on the loop, at every opening of the
  keyboard ([93](../decisions/93-the-shell-that-stopped-reading.md)).
- `compile_command(layout, variant, model, options)` is the `xkbcli` line for
  a shell, quoted; the daemon runs it in its command worker and hands what it
  printed to `parse_keymap`. `compile_labels(...)` runs the same line and
  waits, for the tests and anything that is not the loop.
- `parse_keymap(text)` pulls `<AD01> = 24` style keycode definitions and
  `key <AD01> { [ q, Q ] }` blocks apart, with `EVDEV_OFFSET = 8` between XKB's
  numbering and the kernel's.
- `keysym_to_char(name)` turns a keysym name into the character to draw;
  `KEYSYM_CHARS` covers the names that are not just the character.
- `labels_for_active_layout(devices)` is the whole thing in one blocking
  call.

## Rules

- **Best-effort.** No compositor, no `xkbcomp`, an unparseable keymap: the
  answer is nothing and the keyboard falls back to the layout's own labels.
  `[osk] labels_follow_layout` turns it off outright.
- **Nothing here runs on the loop.** `Daemon.refresh_osk_labels()` asks the
  layout, and a layout it has not compiled goes to the worker: the keyboard
  opens on the labels it had and repaints when the table lands. One compile
  is in flight per layout, an answer overtaken by a newer layout is dropped,
  and `start()` compiles the first one, so the first opening already prints
  it.
- This decides what a key is *printed with*, never what it *types*. What it
  types is a keycode from [`keymap.md`](keymap.md), and that does not change
  with the layout.
- The parsing is regex over the compiled keymap on purpose: a real XKB parser
  is a dependency, and the five shapes needed here are stable.
