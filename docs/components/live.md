# What the machine is doing - `omapad/live.py`

How loud it is, how bright, and what is playing. A **source rather than a
surface**, the same shape [`snap.md`](snap.md) and [`handover.md`](handover.md)
have: there is no socket and no control verb, because nothing here is drawn.
It answers three questions the daemon then puts on a tile.

## Nothing here runs a command

`live.py` returns the **string** to run. The daemon submits it to the same
worker thread every other slow thing goes through - a press must never wait on
`pactl`. `tests/test_live.py` asserts structurally that this module imports
neither `subprocess` nor `os`, because that is the rule most easily broken
without anybody noticing.

The parsers are pure functions over canned output, which is the whole reason
they are pure: `pactl`, a backlight and an MPRIS player are three things a test
cannot have.

## Every command is a setting

`[live] <name>_read` and `<name>_set`, one pair per reading. A machine that
answers these questions some other way answers them by editing that table, not
by patching this file. `%1` is where the new value goes, as a whole percent -
the same numbered-field substitution a listed submenu's template uses. An
**empty string is a reading this machine does not have**: nothing is asked for
it, nothing can be written, and a tile pointed at it draws blank.

| Reading | Kind | Shipped read | Shipped write |
|---|---|---|---|
| `volume` | number | `pactl get-sink-volume "$(omarchy-audio-output-sink)"` | `pactl set-sink-volume … %1%` |
| `mute` | bool | `pactl get-sink-mute …` | `pactl set-sink-mute … %1` |
| `brightness` | number | `omarchy-brightness-display` | `omarchy-brightness-display --no-osd %1%` |
| `media` | media | `omarchy-shell media status` | `omarchy-shell media %1` |

**Why volume bypasses `omarchy-audio-output-volume`.** That helper always ends
in `omarchy-osd`, so every press from the HUD would raise Omarchy's own overlay
**over the tile showing the same number** - the opposite of what putting volume
on a tile is for. `--no-osd` exists for brightness and not for volume, so
volume talks to the sink `omarchy-audio-output-sink` resolves, which is what
the helper itself resolves with, so a speaker tuning chain is still respected.
Anyone who wants the OSD back puts the helper in `volume_set`.

**Why brightness keeps its helper.** DDC, Apple displays and backlights are
three code paths omapad must not reimplement, and that helper offers the flag.

## The stale-read race

A read started *before* a write can land *after* it and rewind the bar for a
tenth of a second - a flicker nobody can reproduce. So **every reading carries
a generation counter**: `apply()` bumps it, and `took()` throws away an answer
whose generation is older than the last write. It is the one bug in this
component that would not look like a bug.

A reading that **times out keeps its last value**. A parser returning `None`
means *no answer*, not *zero*: a tile that empties because a helper was slow is
worse than one that is a second stale, and a helper that hangs must never be
able to empty the HUD.

## When it is asked

All of this is the daemon's, in `live_refresh(now)`, called from the loop.

- **Nothing while the menu is shut.** A daemon nobody is looking at must not
  poll a sound server.
- **Once when a reading appears on the page in front**, which covers the menu
  opening, a chip walked to and a page drilled into - one place rather than
  three call sites. Closing the menu forgets every deadline, because what the
  machine was doing a minute ago is not what it is doing now.
- **Every `[live] poll_ms` while its own tile is selected.** Not everything on
  the page, and not at gauge rate: a couch does not need the volume to track a
  keyboard nobody is at. The cost is that a value changed from *elsewhere*
  while the menu is up goes unnoticed on an unselected tile, which is the right
  trade for a HUD that is open for seconds at a time.
- **Once `[live] settle_ms` after a write**, by which time the helper has
  landed and the machine can say what it actually did.

One question in flight per reading: a helper that has wedged must not collect a
queue of identical questions behind it, and the answer to the first is the
answer to all of them.

## `live:` is `pad:`'s twin

```toml
action = "live:volume=up"      # a notch louder, from any button
action = "live:media=next"     # what is playing, walked on
reads  = "live:brightness"     # a tile that shows it and pushes it
```

Same grammar as `pad:`, on purpose: a button reads the same whichever of the
two it is pointed at, and a capability reachable only from the shape it first
shipped in is a gap rather than a design. Both are validated at load, so a typo
fails `omapad check` rather than a press.

`READINGS` describes each reading the way `config.CHOSEN` describes a setting -
its `kind`, and for a number the arithmetic a bar needs. `menu.build()` takes
it as `readings=` beside `settings=`, so the module that holds state and
geometry learns about neither.

## The media tile

`control = "media"`, three cells by two, reading `live:media`.

**The daemon maps it; the reading does not reach the wire as it arrived.** An
MPRIS field name is not a payload field name, and a rename upstream must not
silently become a rename on the wire. The tile's `l` becomes the title and `d`
the artist, both through `viewsock.drawable()` - a track title comes from
outside this machine exactly as a sink description does - and `on` says whether
it is running. Nothing playing falls back to the tile's own `empty`.

**A plays or pauses it.** It has two states, so A does to it what A does to a
switch, and it needs no mode of its own. Not X: `bindings.md` rule 3 makes X
the app's own verb, and here the app is the menu and its verb is *leave
outright* - a close button that pauses your music on one tile in eight is
unsafe, and rule 5 forbids a meaning that moves.

**Previous and Next are two more tiles**, either side of it, running
`live:media=previous` and `live:media=next`. Not a transport drawn inside the
one tile: left and right already mean *the tile that way*, so the grid walks to
them without a button learning a second meaning anywhere. A tile costs nobody a
reflex, which is the same argument that keeps every page's X and Y unspent.

`canGoNext` and `canGoPrevious` are **read and not drawn**: they decide whether
a press that way fires `edge` instead of doing nothing quietly. A mark on
screen that cannot be pressed would be a third way to say what that tick
already says.

## Rules

- **Nothing here knows about PulseAudio, backlights or MPRIS.** It runs a
  string somebody else wrote and parses what comes back.
- **No network, ever**, the same as everywhere else in this tree.
- `[live]` is a fixed table of four readings whose commands are settings. It is
  not an extension point, and a fifth reading is a change here, in `READINGS`,
  with a parser and a test - not something a config file can invent.
- A parser returns `None` for *no answer*. Never a zero, never an empty string.
