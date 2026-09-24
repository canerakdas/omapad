# Quick menu - `omapad/quick.py` + `shell-plugin/QuickMenu.qml`

One row of tiles over whatever is in front: what PLUS opens. The controller
menu is a place and HOME is its door; this is what a pause button is for.
Why it exists and what it took from the design is
[decision 85](../decisions/85-two-menus-two-buttons.md).

## The model

`build(entries)` turns `[[quick.items]]` into tiles and raises `QuickError`
naming the one that is wrong: a missing label, nothing to do, `up` without
`down`, `arm` with no action, a `when` naming something that is neither a
place (`window`, `empty`) nor one of `STATES`, both places at once, an unknown
key, two tiles with one id. `when` is split into `where` (the place or None)
and `states` (a tuple): the states are the menu's less `first_run`, which the
menu spends by opening and so is never true here. Actions
are parsed at load with `actions.parse`, so a typo is what `omapad check`
names rather than a press that does nothing. The daemon builds the row the
way it builds the menu: a row that will not parse comes up empty and the
daemon stays up.

`QuickModel` holds three things: the tiles, which one is in front (`index`),
and the id of a tile pressed once that wants a second press (`armed`).

- `reset()` goes back to the first tile - every opening, deliberately. The
  menu comes back to where it was because it is a place somebody returns to;
  this is a pause, and its first tile is the way out of it.
- `move(way)` walks the row and **wraps**. A grid must not wrap (in two
  dimensions it is losing the selection); a row wrapping is the short way
  round.
- `press()` answers `run`, `arm` or None. `arm` is the first press on a tile
  that says `arm = true`; anything but the second press - a step, a nudge,
  B, the surface closing - lets go of it.
- `nudge(way)` is the tile's `up` or `down` action, or None.
- `hide(ids)` takes tiles off the row - `shown` is what is left, and `index`
  counts along it - keeping the tile in front by name. The daemon hides every
  tile whose `up` is a `live:` reading that has never answered
  (`quick_unanswered`), on opening and before every push: brightness on a
  monitor without DDC reads as nothing, and a tile turning a number nobody can
  read changes nothing on screen. Brightness left the shipped row in
  [90](../decisions/90-the-chord-is-the-pause.md), and the rule stays for a
  tile somebody writes. It also hides every tile whose `when` is
  not what is in front (`quick_elsewhere`): `"window"` tiles over an empty
  workspace, `"empty"` tiles over a window, and a tile listing states none of
  which `menu_conditions()` holds - any one is enough, the menu's rule. That
  is what puts the workspace lock and its pair straight after Resume only
  where they can do something: the lock in game mode or over a game holding
  the pad, keeping only while an app has the pad or it is kept. So the shipped row is two - a
  pause headed by Resume over a window, and Back then the apps over nothing,
  where there is nothing to resume, close or type into. The daemon hides
  before it resets on opening, because a hide follows the tile in front by
  name and would otherwise carry the last opening's tile past the first
  place.

## The payload

```
{open, sel, tiles:[{id, l, i, f?, m, on, x}], band:{id, l, w, t, adj, arm, x, v?},
 head:{k, t}, keys:[{b, k, n}], cell, corner, dim, barh}
```

- `tiles` carries **nothing that moves with the selection**: which tile is in
  front is `sel`, beside it. A step changes `sel` and `band` and leaves
  `tiles` byte-identical, so `fresh()` keeps the row's delegates (qml.md
  5.4). `m` is the value in words - `Action.value` of the tile's `up`, or of
  its action - and `on` is `Action.state` of its action, which is what lights
  a switch.
- `band` is the tile in front, worded: `l` its name, `w` its value, `t` the
  line under it (`quick.ARMED` while it waits for a second press), `v` where
  a `live:` number is along its travel, which the panel draws with the
  menu's own slider (`Travel.qml`) - a scale with a needle, continuous and
  never taken, so no ghost. A `pad:` number prints its words and draws no
  scale - the setting already names its own.
- `head` is `k` the mode and `t` the window's title, through `drawable()`: a
  title is typed by whatever owns the window.
- `keys` is the legend, built from `[bindings.quick]` like the menu's is from
  its layer: A says the tile's own name (`Confirm` while armed, nothing on a
  tile A does not touch), B says `Cancel` while a tile is armed, X is left
  off because a row has no levels and it is B's way out twice, and ↑ ↓
  appear only on a tile with a value.
- `cell`, `corner` and `dim` are the menu's settings, stamped here because the
  row is drawn from the menu's module; `barh` is the game bar's height, for
  the band the legend stands in.

## The daemon

`set_quick(opened)` closes the menu and the keyboard as it opens, and stands
the game bar down (`apply_gamebar`) - the row covers the whole screen and
prints the bar's row of buttons in the bar's band itself, the way a
fullscreen menu does. And
`set_menu(True)` and `set_guide(True)` close it: one surface reads the D-pad
at a time. The order in `config.SURFACES` puts it above the menu, which only
decides a tie that cannot happen.

`quick_command` is the whole of what a press does. A tile runs through
`fire_once(action, "quick")`, and `"quick"` is in `SURFACE_LAYERS` - so a tile
picked over a game runs even though the row has closed by the time it fires,
the argument `allowed()` makes for the menu. `QuickAction` is a summon, so
`quick:*` reaches past an app holding the pad unless a binding says
otherwise; the shipped PLUS says otherwise, and over a game - or under the
workspace lock, which lets nothing else through - the way in is the
`MINUS+PLUS` chord, `quick:open` rather than `toggle` so a PLUS that landed
first and opened the row is not shut again by it
([decision 90](../decisions/90-the-chord-is-the-pause.md)).

Live readings are asked while the row is up through `live_names()`, which
reads the `LiveAction`s on the row's tiles when the row is open, and the
selected tile's reading is polled at `[live] poll_ms` exactly as a menu tile
is. A nudge goes through `live_write`, so it coalesces and ticks at the end of
the travel the way a menu control does.

The layer's sticks are `none`: nothing on a row wants steering, and a pointer
drifting over the game behind it is worse than a stick that does nothing.

## The panel

`QuickMenu.qml`. Pad-only, like the guide: `WlrLayer.Overlay`, no keyboard
focus, an empty input region, and `ExclusionMode.Ignore` always - the bar's
strip is the legend's. Every colour is a theme role - the tiles are
the menu's `cellGround` / `cellEdge` / `cellLit`, the destructive tile takes
`Color.urgent` - and every size is off the silver ladder except the cell,
which is the menu's module, and the legend, which is Menu.qml's fullscreen
legend and so GameBar.qml's row: same badge, same words, same band, same edge
padding. The row shrinks to fit the screen rather than
scrolling: a row you can only see part of hides the tile you paused for. The
head and the foot stand against the screen edge, so both go through
`metrics.edge`.

## Driving it without a pad

```bash
omapad ctl quick toggle      # open | close | left | right | up | down | press | back
omapad ctl quick select 3    # name a tile outright
```
