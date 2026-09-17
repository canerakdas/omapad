# The chronograph

| | |
|---|---|
| **Daemon** | `omapad/chrono.py` (the stopwatch), `omapad/menu.py` (the tile) |
| **Panel** | `shell-plugin/Clock.qml` |
| **Socket** | `menu.sock` - it is a menu tile, not a surface |
| **Config** | `control = "chrono"` on any `[[menu.items]]` tile |
| **Verb** | A, on the tile |

The only clock in this tree that **measures** rather than tells. `menu.py`
renders the time of day because that costs a `strftime` and cannot be wrong;
this holds something nobody can ask the machine for - when a press happened -
and so it is state, and state lives in the daemon.

## One chronograph, however many tiles draw one

A stopwatch is a thing in the room rather than a property of a cell: start it
on the page you were on, walk to another page, and it is the same measurement.
Two of them would be two answers to "how long has it been" with nothing on
screen saying which is which - and a second one is a thing to configure before
it is a thing to use. So `Daemon.chrono` is one `Chrono`, and every `chrono`
tile in the tree is a window onto it.

## One pusher, and the cycle is start, stop, reset

That is a monopusher chronograph, which is what a chronograph was before it had
two pushers, and it is what this pad has room for: **A is the only button a
tile owns**. B leaves the surface and X closes it in every layer
([`../conventions/bindings.md`](../conventions/bindings.md)), so a second
pusher would have to come out of the face-button contract - spent on a
stopwatch, on a surface where the same gesture already has to mean *press this
tile* everywhere else.

What the cycle costs is resuming: a stopped chronograph is reset by the next
press rather than restarted. That is the monopusher's own limitation on the
wrist too, and the honest half of it is that the pad says which press is
coming. `Chrono.verb()` is `Start`, `Stop` or `Reset`, and
`daemon.menu_legend()` prints it under the card the way it already prints
`Hold to confirm` for a row that has to be held - so *Reset* is read before it
is pressed rather than discovered by pressing.

The verbs live in `chrono.py` rather than in the daemon because the press and
the word are one decision: a cycle that gained a state and left the words
behind would be a legend that lies about the next press.

## Nothing here reads a clock of its own

Every entry point takes `now`, which is `time.monotonic()` in the daemon and a
number in the tests. A stopwatch that asked the wall clock what time it was
would measure a machine coming back from suspend as hours - and `elapsed()`
clamps a `now` that went backwards, because a negative elapsed draws a sweep
hand running backwards and nobody would think to look for that in the
arithmetic.

## What the tile carries

A `chrono` tile is an ordinary `clock` tile - the same `k` and `mn` and
nothing else - and **the stopwatch rides on the surface beside it**:

```json
{"open": true, "sel": "stopwatch", "hd": "",
 "chrono": {"run": true, "el": 12.5, "sc": 15.27},
 "items": [{"id": "stopwatch", "l": "Stopwatch", "k": "chrono",
            "x": 3, "y": 2, "w": 2, "h": 2, "mn": 1187}]}
```

`mn` is the minute of the day, the same field a clock carries and for the same
reason ([`menu.md`](menu.md)). `run` and `el` are the stopwatch - whether it
was going when the line was written and how long it had measured by then - and
`sc` is how far into the minute the clock was, which only a face with a running
register on it has any use for.

**Why it is not on the tile** is the whole performance story, and it cost 13%
of a core to learn: the panel decides whether to rebuild the page by comparing
the tiles it was sent with the tiles it has (qml.md 5.4), so a number that
differs on every push is every delegate on the page destroyed and rebuilt twice
a second to move one hand. `menu_gauge` had already written the warning down
for the thumb dot - *carrying it with the rest of the surface would rebuild
every tile on the page to move one dot* - and this is that sentence one control
along. One field rather than one per tile also happens to be the truth: there
is one stopwatch, however many faces are drawn of it.

`MenuModel.view_state` takes `chrono` as a **callable** and calls it only where
a tile on the page in front would draw one, so the field is off the wire
entirely for every other page and nothing is asked for a thing nobody can see.

## What it costs

Measured with `menu.sock` up and the page in front, against the same page with
no clock tile on it at all (1.1% of a core):

| | shell | daemon |
|---|---|---|
| menu closed, stopwatch running | 1.3% | 2.8% |
| chronograph on the page, idle | 2.0% | 4.1% |
| chronograph on the page, measuring | 2.4% | 4.1% |
| *the same, with `el`/`sc` on the tile* | *14.4%* | *4.1%* |

Three things hold that down, and each is a rule rather than a tuning:

- **The tiles are identical between two payloads**, which is the table's last
  row and the reason for all of this.
- **Nothing animates while the surface is down.** `Clock.qml` takes `awake`
  from the menu's own `opened`; a stopwatch left running costs exactly what a
  closed menu costs, which is what the first row says.
- **The face redraws four times a second idle and twenty while measuring**,
  because idle the only thing moving is the seconds hand of a register fifteen
  pixels across. Both are implementation trade-offs with a comment saying so,
  the way the generator's sampling constants are - nobody configures a repaint.

## Why the panel counts on from `el`

The page is re-sent every `VIEW_HEARTBEAT` seconds. A sweep hand redrawn twice
a second is a stopwatch that jumps, so `Clock.qml` stamps `Date.now()` when a
payload lands and draws `el` plus however long ago that was, re-syncing on
every push. The figures are spelled on that side for the same reason: a number
that changes ten times a second cannot come off a wire written twice a second.

That is animation rather than state (qml.md 10's rule is about a `Timer`
*polling* for what the daemon owns), and the timer sleeps whenever the surface
is down - a panel nobody can see has nothing to animate.

## Where it may be drawn

The menu, and not the HUD. [`hud.md`](hud.md)'s rule is that **a tile with
something to press is not drawn over a game**, and a chronograph has a pusher
on it; a clock does not, which is why the clock is the one that may be left on
screen. A `chrono` tile written onto the HUD's page is packed like any other
and simply not drawn, exactly as a switch is.

## Changing it

- **A fourth state, or a second pusher**, is `chrono.py` and the legend
  together: `VERBS` has a word per state because the word *is* the press.
- **The registers are not art.** Three sunk discs and three hands, all of them
  answering to a number - see [`assets.md`](assets.md) for why that keeps them
  out of the generator, and `Clock.qml` for the panda layout they are in.
- The tile's own shape, span and validation are the menu's:
  [`menu.md`](menu.md), and [`../procedures/pad-setting.md`](../procedures/pad-setting.md)
  if any of these numbers ever becomes a setting.
