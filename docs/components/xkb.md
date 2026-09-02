# XKB labels - `omapad/xkb.py`

What the keys are actually printed with, read back from the compositor's
layout. The on-screen keyboard types keycodes, and a keycode means a different
character on a Turkish layout than on a US one - so the *labels* are asked for
rather than assumed.

## How

- `active_layout()` asks Hyprland which layout, variant, model and options are
  in force.
- `compile_labels(layout, variant, model, options)` compiles that keymap and
  reads the symbol lists out of it.
- `parse_keymap(text)` pulls `<AD01> = 24` style keycode definitions and
  `key <AD01> { [ q, Q ] }` blocks apart, with `EVDEV_OFFSET = 8` between XKB's
  numbering and the kernel's.
- `keysym_to_char(name)` turns a keysym name into the character to draw;
  `KEYSYM_CHARS` covers the names that are not just the character.
- `labels_for_active_layout()` is the whole thing in one call.

## Rules

- **Best-effort.** No compositor, no `xkbcomp`, an unparseable keymap: the
  answer is nothing and the keyboard falls back to the layout's own labels.
  `[osk] labels_follow_layout` turns it off outright.
- This decides what a key is *printed with*, never what it *types*. What it
  types is a keycode from [`keymap.md`](keymap.md), and that does not change
  with the layout.
- The parsing is regex over the compiled keymap on purpose: a real XKB parser
  is a dependency, and the five shapes needed here are stable.
