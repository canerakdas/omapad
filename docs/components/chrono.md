# The stopwatch

| | |
|---|---|
| **Daemon** | `omapad/chrono.py` (the stopwatch), `omapad/menu.py` (the tile) |
| **Panel** | `shell-plugin/Menu.qml` (`chronoWords`, and the tile's figure line) |
| **Socket** | `menu.sock` - it is a menu tile, not a surface |
| **Config** | `control = "chrono"` on any `[[menu.items]]` tile; `[chrono] rumble` |
| **Verb** | A, on the tile |

The only clock in this tree that **measures** rather than tells. `menu.py`
renders the time of day because that costs a `strftime` and cannot be wrong;
this holds something nobody can ask the machine for - when a press happened -
and so it is state, and state lives in the daemon.

## One stopwatch, however many tiles show it

A stopwatch is a thing in the room rather than a property of a cell: start it
on the page you were on, walk to another page, and it is the same measurement.
Two of them would be two answers to "how long has it been" with nothing on
screen saying which is which - and a second one is a thing to configure before
it is a thing to use. So `Daemon.chrono` is one `Chrono`, and every `chrono`
tile in the tree is a window onto it.

## One pusher, and the cycle is start, stop, reset

One pusher is what this pad has room for: **A is the only button a tile
owns**. B leaves the surface and X closes it in every layer
([`../conventions/bindings.md`](../conventions/bindings.md)), so a second
pusher would have to come out of the face-button contract - spent on a
stopwatch, on a surface where the same gesture already has to mean *press this
tile* everywhere else.

What the cycle costs is resuming: a stopped stopwatch is reset by the next
press rather than restarted. The honest half of that is that the pad says which
press is coming. `Chrono.verb()` is `Start`, `Stop` or `Reset`, and
`daemon.menu_legend()` prints it under the card the way it already prints
`Hold to confirm` for a row that has to be held - so *Reset* is read before it
is pressed rather than discovered by pressing.

The verbs live in `chrono.py` rather than in the daemon because the press and
the word are one decision: a cycle that gained a state and left the words
behind would be a legend that lies about the next press.

## A running measurement strikes the minute

`Chrono.strike(now)` says, once a minute, that the measurement has rolled over
another one; `daemon.check_chrono` answers with `rumble`'s `tick`.
**That is the only thing a stopwatch can say to somebody who is not looking at
it** - and most of what one left running while you do something else is worth,
which is the difference between a stopwatch on a pad and a stopwatch on a
wall.

Three things about it are the design rather than the implementation:

- **The mark is the minute, not a length of time somebody set.** `MINUTE` is
  60 seconds and is not a setting: it is the unit the figures count in, and a
  strike at ninety seconds would land half way through one, saying nothing
  that can be read off the tile. An alarm after a length you set is a
  different instrument, and it would want a number on screen to set before it
  wanted a motor. `[chrono] rumble` is a switch, and the only one.
- **Asked on the loop's heartbeat, not on the menu's.** The measurement
  outlives the page it was started on, so the mark does too: the menu can be
  shut, and an app can be holding the pad - the stopwatch is the person's,
  not the focused window's. How late the mark is, is the idle poll, a quarter
  of a second at worst against a mark that comes once a minute.
- **The motor alone, never `say()`.** Nothing was pressed. `say()` is two
  vocabularies answering one press together ([`rumble.md`](rumble.md)), and a
  machine that made a noise at somebody once a minute for as long as a
  measurement ran would be answering a question nobody asked.

`strike()` is true once per minute however long it has been since the last ask,
so a loop that went quiet for five minutes has one thing to say rather than
five. The count goes with the measurement - a reset clears the minutes struck
with the seconds - and it is advanced whether the switch is on or not, so a
switch turned on halfway through a measurement waits for the next minute
instead of answering one that went by while nothing was listening.

## Nothing here reads a clock of its own

Every entry point takes `now`, which is `time.monotonic()` in the daemon and a
number in the tests. A stopwatch that asked the wall clock what time it was
would measure a machine coming back from suspend as hours - and `elapsed()`
clamps a `now` that went backwards, because a negative elapsed prints a
measurement counting down and nobody would think to look for that in the
arithmetic.

## What the tile carries

A `chrono` tile carries its `k` and nothing of its own - and **the stopwatch
rides on the surface beside it**:

```json
{"open": true, "sel": "stopwatch", "hd": "",
 "chrono": {"run": true, "el": 12.5},
 "items": [{"id": "stopwatch", "l": "Stopwatch", "k": "chrono",
            "x": 4, "y": 10, "w": 2, "h": 2}]}
```

`run` and `el` are the stopwatch - whether it was going when the line was
written and how long it had measured by then. The tile carried `mn`, the minute
of the day, while it was a watch face that also told the time; that went with
the face ([104](../decisions/104-a-clock-that-was-a-watch.md)).

**Why it is not on the tile** is the whole performance story, and it cost 13%
of a core to learn: the panel decides whether to rebuild the page by comparing
the tiles it was sent with the tiles it has (qml.md 5.4), so a number that
differs on every push is every delegate on the page destroyed and rebuilt twice
a second to move one figure. `menu_gauge` had already written the warning down
for the thumb dot - *carrying it with the rest of the surface would rebuild
every tile on the page to move one dot* - and this is that sentence one control
along. One field rather than one per tile also happens to be the truth: there
is one stopwatch, however many tiles show it.

`MenuModel.view_state` takes `chrono` as a **callable** and calls it only where
a tile on the page in front would draw one, so the field is off the wire
entirely for every other page and nothing is asked for a thing nobody can see.

## What it costs

Measured with `menu.sock` up and the page in front, against the same page with
no clock tile on it at all (1.1% of a core). Measured while the tile was still
a watch face and not again since: a line of figures is the lighter drawing, so
these are a ceiling rather than a reading.

| | shell | daemon |
|---|---|---|
| menu closed, stopwatch running | 1.3% | 2.8% |
| stopwatch on the page, idle | 2.0% | 4.1% |
| stopwatch on the page, measuring | 2.4% | 4.1% |
| *the same, with the stopwatch on the tile* | *14.4%* | *4.1%* |

Three things hold that down, and each is a rule rather than a tuning:

- **The tiles are identical between two payloads**, which is the table's last
  row and the reason for all of this.
- **Nothing counts while the surface is down.** The timer in `Menu.qml` runs
  only while `opened` is true; a stopwatch left running costs exactly what a
  closed menu costs, which is what the first row says.
- **The figures redraw twenty times a second while measuring and not at all
  otherwise.** An implementation trade-off with a comment saying so, the way
  the generator's sampling constants are - nobody configures a repaint.

## Why the panel counts on from `el`

The page is re-sent every `VIEW_HEARTBEAT` seconds. Tenths redrawn twice a
second are a stopwatch that jumps, so `Menu.qml` stamps `Date.now()` when a
payload lands and prints `el` plus however long ago that was, re-syncing on
every push - `chronoWords`, spelled on that side because a number that changes
ten times a second cannot come off a wire written twice a second.

That is animation rather than state (qml.md 10's rule is about a `Timer`
*polling* for what the daemon owns), and the timer sleeps whenever the surface
is down - a panel nobody can see has nothing to animate.

## Where it may be drawn

The menu, and not the HUD. [`hud.md`](hud.md)'s rule is that **a tile with
something to press is not drawn over a game**, and a stopwatch has a pusher
on it; a clock does not, which is why the clock is the one that may be left on
screen. A `chrono` tile written onto the HUD's page is packed like any other
and simply not drawn, exactly as a switch is.

## Changing it

- **A fourth state, or a second pusher**, is `chrono.py` and the legend
  together: `VERBS` has a word per state because the word *is* the press.
- **A mark somewhere other than the minute** - every five minutes, or at a
  time you set - is a countdown rather than a stopwatch, and it needs a tile
  that says what it is counting to before it needs a motor. `MINUTE` is not
  the place to start it.
- **A face is not coming back without a decision.** It was a watch dial with
  hands and a register, and then one that fell back to figures when drawn
  small; both went ([104](../decisions/104-a-clock-that-was-a-watch.md)).
- The tile's own shape, span and validation are the menu's:
  [`menu.md`](menu.md), and [`../procedures/pad-setting.md`](../procedures/pad-setting.md)
  if any of these numbers ever becomes a setting.
