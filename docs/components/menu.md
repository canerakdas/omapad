# Menu - `omapad/menu.py` + `shell-plugin/Menu.qml`

The controller menu: the entry tree, its navigation, and the view payload.

Shaped like the Omarchy menu rather than a radial: one column of rows, a title
line, and submenus you drill into. A radial reads a stick angle in one flick,
but it caps out at a handful of entries and has nowhere to put a submenu, while
a list is what a D-pad already walks well and is the shape the desktop teaches
everywhere else.

## The tree

`build(entries)` normalises `[[menu.items]]` into a tree. **Actions are parsed
here, not when a row is picked**, so a typo surfaces in `omapad check`
instead of doing nothing at the press. An entry needs a `label`, and may have
either an `action` or nested `items` - never both. `MenuError` says which.

Entries use the same action grammar as a button binding, so the menu reaches
anything a button can.

## `MenuModel`

`move(step)`, `press()`, `back()`, `reset()`, with `depth` and `current`
tracking the drill-down stack. `clock()` renders `[menu] clock`.

## Rows that know the answer

`view_state(opened, state, value)` takes two callbacks from the daemon:

- `state(action)` answers "is this already the case?" - the row is ticked
  (`on`). That is the whole difference between a list of choices and a list of
  guesses.
- `value(action)` answers the other half for a row that steps a number, and
  replaces the row's own `detail`, which is a sentence written once and cannot
  know. Ticking cannot say it: every step of a number is equally "not the
  case".

## Payload - `menu.sock`

```
open, title, clock, depth, sel, items: [ {l, i, d, sub, on?} ]
```

`l` label, `i` icon, `d` detail, `sub` whether it drills in.

What those strings may say is [`../conventions/writing.md`](../conventions/writing.md):
the row is read from across a room by someone deciding whether to press it,
so a `detail` says what happens rather than why the row exists.

## The panel

`Menu.qml`. Centred card, title line, one column, `›` where a row drills in.
Overlay layer, no keyboard focus, empty input region - the pad drives it, so it
must never swallow a click meant for the window under the scrim.

Settings: `[menu] title`, `clock`, `repeat_delay_ms`, `repeat_rate_ms`,
`socket`, `[[menu.items]]`, `[bindings.menu]`.
