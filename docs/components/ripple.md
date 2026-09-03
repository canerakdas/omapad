# Click burst - `omapad/ripple.py` + `shell-plugin/Ripple.qml`

A mouse answers a click three ways: the finger feels the switch, the hand is
already on the thing that moved, and the arrow sits on what was hit. A pad
answers none of them - the thumb is on a trigger that feels the same whatever
it did, and the pointer game mode draws is a ring that looks identical before
and after - so a click that landed and a click that went nowhere are the same
picture. This draws the difference: one ring leaving the pointer, with the
half of it on the side of the button that was pressed drawn solid.

**The side, not only the colour.** The two buttons have to be told apart by
someone who cannot tell the theme's accent from its foreground, and left and
right are where those buttons are on the mouse this is standing in for. The
colour is the second, faster answer for everyone else.

## The two ways it is not like the other surfaces

It draws an **event**, not a state, and both differences follow from that:

- **No heartbeat.** Every other surface is re-sent every `VIEW_HEARTBEAT`
  seconds so a restarted shell repaints itself; a burst that is over has
  nothing to repaint, and re-sending it would replay the animation twice a
  second forever. `Daemon` therefore has no `_ripple_next_heartbeat` and no
  `ripple_open`.
- **No `open`.** What the panel watches is `n`, a counter the daemon
  increments per click and never sends as 0, so a line carrying a sequence
  number already drawn is a duplicate rather than a second click. It is
  assigned **last** in `applyState` for the same reason `open` is elsewhere:
  it is what starts the animation, and everything the burst is drawn from has
  to be in place first.

## Where the pointer is

Asked of the compositor at the moment of the press - one `cursorpos` over the
Hyprland socket, the same well-under-a-millisecond class the button path
already spends on `snap`. The daemon moves the pointer in relative steps and
never learns where that put it, and a position it tracked itself would be
wrong the first time a real mouse touched the desk.

`ClickAction.press` emits the click **first** and asks second: nothing the
screen has to say about a click may stand between the trigger and the click.
A compositor that cannot answer, or a button no half of a ring means
(`click:back`, `click:forward`), leaves the last burst alone - a ring drawn
where nobody clicked is worse than no ring.

## Payload - `ripple.sock`

```
n, b, x, y, size, ms, th
```

`x` and `y` are the compositor's own logical pixels - global, the space the
monitors are laid out in - so the panel subtracts its own monitor's origin and
nobody has to agree on a scale.

## The panel

`Ripple.qml` is mounted in `Surfaces.qml` and is neither summonable nor
`opened`: it answers a click rather than a button.

**One window per monitor** (`Variants` over `Quickshell.screens`), because the
pointer roams across all of them; only the monitor the click landed on maps at
all. It stays mapped for `duration_ms` plus a couple of seconds after the
burst is over - a layer surface mapping and unmapping is a compositor
animation each way, and a double click should not pay for two of them, while a
transparent overlay left permanently over a fullscreen game would be the worse
trade.

One `NumberAnimation` drives a `phase` on the root from 0 to 1 and every
monitor's copy binds its geometry to it, rather than each keeping its own
clock.

## Settings

`[ripple] enabled`, `size` (0 = twice `[cursor] size`, so the burst reads as
leaving the ring rather than happening beside it), `duration_ms`, `thickness`
(a fraction of the size, the way `[cursor] thickness` is), `socket`.

Its `IpcHandler` carries a `burst()` beside the usual `state`, `socket` and
`ping` - `<n> <button> <x>,<y>`, the last line the panel actually painted -
because "the daemon says it sent one" and "the panel drew one there" are two
questions and the gap between them is where a burst in the wrong place lives.

```bash
qs -p /usr/share/omarchy/shell ipc call omapad-ripple burst
```

## Driving it without a pad

```bash
omapad ctl ripple left|right|middle
```

The one surface no binding can reach - it answers the pointer, not the pad -
so this is the only way to see one without clicking, which is what tuning
`size` and `duration_ms` needs.
