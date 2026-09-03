# Menu - `omapad/menu.py` + `shell-plugin/Menu.qml`

The controller menu: the entry tree, its navigation,and the view payload.

Shaped like the Omarchy menu rather than a radial: one column of rows, a title
line,and submenus you drill into. A radial reads a stick angle in one flick,
but it caps out at a handful of entries and has nowhere to put a submenu, while
a list is what a D-pad already walks well and is the shape the desktop teaches
everywhere else.

## The tree

`build(entries)` normalises `[[menu.items]]` into a tree. **Actions are parsed
here, not when a row is picked**, so a typo surfaces in `omapad check`
instead of doing nothing at the press. An entry needs a `label`,and may have
either an `action` or nested `items` - never both. `MenuError` says which.


Entries use the same action grammar as a button binding, so the menu reaches
anything a button can.



##`MenuModel`

`move(step)`, `press()`, `back()`, `reset()`,with `depth` and `current`
tracking the drill-down stack. `clock()` renders `[menu] clock`. `select(n)` is
the pointer's way in: a row names itself outright,where `move` only knows
how far to walk. Out of range clamps to the nearest row rather than wrapping:
a pointer is aiming somewhere, and a selection that wraps across the fold reads
as a mistake.


##Rows that know the answer

`view_state(opened, state, value)` takes two callbacks from the daemon:

- `state(action)` answers "is this already the case?" - the row is ticked
  (`on`). That is the whole difference between a list of choices and a list of
  guesses.
- `value(action)` answers the other half for a row that steps a number,and
  replaces the row's own `detail`,which is a sentence written once and cannot
  know. Ticking cannot say it: every step of a number is equally "not the
  case".


##Payload - `menu.sock`

```
open, title, clock, depth, sel, items: [ {l, i, d, sub, on?} ]
```


`l` label, `i` icon, `d` detail, `sub` whether it drills in.



What those strings may say is [`../conventions/writing.md`](../conventions/writing.md):
the row is read from across a room by someone deciding whether to press it,
so a `detail` says what happens rather than why the row exists.



##The panel

`Menu.qml`. Centred card, title line, one column, `›` where a row drills in
(the same measurements and theme tokens the Omarchy menu draws with, so the two
read as one family). Overlay layer, `Exclusive` keyboard focus,and the whole
screen as its input region -the Omarchy menu's own window rules. While it is
open the keyboard and the pointer drive it,on top of the pad

| Input | Job |
|---|---|
| Pad D-pad / arrows | Walk the rows (both hold and keep walking) |
| A · D-pad right · Enter · Space | Pick; dive in, if it is a submenu |
| B · D-pad left · Backspace | Back to the menu above; at the top it closes |
| Esc · X · click the scrim | Close the menu outright,from any depth |
| Click a row | Pick the row it lands on |
| Hover a row | Move the selection to it (after the cursor has travelled) |
| Home / End · PageUp / PageDown | Jump to the ends,or six rows at a time |


The keyboard and the mouse drive the same `MenuModel` the pad does,over the
same control socket `omapad ctl menu` uses: each key and each pointer event
sends a command and the daemon's next view line answers it. A held arrow key
auto-repeats the way a held D-pad does,so the two hands feel the same. A
stationary cursor never steals a selection the pad put somewhere on purpose:
the pointer must travel a little before hover selects

This is the one omapad surface that takes input at all:the keyboard and the
guide stay pad-only,with an empty input region,so they never swallow a
click meant for the window under their scrims. The menu swallows them -that
is what "close on a scrim click" means - until it goes away.


Settings: `[menu] title`, `clock`, `repeat_delay_ms`, `repeat_rate_ms`,
`socket`, `[[menu.items]]`, `[bindings.menu]`.