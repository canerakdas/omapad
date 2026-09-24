# The readings

| | |
|---|---|
| **Daemon** | `omapad/hud.py` (the page), `omapad/sysinfo.py` (the numbers) |
| **Panel** | `shell-plugin/Hud.qml` |
| **Socket** | `hud.sock` |
| **Settings** | `[hud] show`, `page`, `rows`, `margin`, `opacity`, `socket`; `[sysinfo] *` |
| **Verb** | `omapad ctl hud <on\|off\|toggle>` |

Game mode takes Omarchy's bar away, which is the right trade for a screen
watched from a sofa and leaves one question unanswered: what the machine is
actually doing while it does it. This is the answer.

## What makes it different from every other surface

**It is not a surface of its own design.** What it draws is an ordinary
`[[menu.items]]` group - `[hud] page` says which, by id. `HudModel` packs it
with `menu.arrange` and `menu.place`, the same two functions the menu packs a
page with, and the panel draws those cells over the whole screen instead of
inside a card. So:

- the tiles are written where every other tile is written;
- they are arranged with the gesture that arranges every other page - Y in
  the menu, carry one, let go - and the arrangement lands in the same
  `layout.toml`, under the same page id;
- where a tile sits in the grid is where it sits on the screen, because it is
  the same grid.

There is no second place to configure this, and no second packer that could
disagree with the first about where a tile is.

**One arrangement, held not copied.** `HudModel` is handed `self.menu.layout`
- the dict, not `config.layout`. The menu takes its own copy of what came off
`layout.toml` so that rearranging never writes back into the config, which
means `config.layout` is the file as it was read and stops being true the
moment anybody carries a tile. A HUD reading that drew the arrangement
somebody had before they started.

**And the same arrangement is not the same packing.** Each model holds the
cells it last worked out, so `daemon.hud_rearranged()` repacks and pushes from
every place the menu mutates the arrangement - not from where it is written
down, because the file is written when edit mode is left and what somebody is
looking at must not wait for that. It returns at once while the readings are
off: `set_hud(True)` packs on the way up.

## The one thing that is not the menu's: the grid has a last row

A menu page is **as many rows as its tiles came to**, and it scrolls past the
fold. That is right for a card and it means nothing on such a page can mean
*the bottom* - there is no last row to be in. A screen has a bottom edge, so a
tile carried into the bottom right has to arrive in the corner of it rather
than a fixed number of pixels down from the top.

So `[hud] rows` is a fixed count, and **a cell here is a share of the screen
rather than a number of pixels**. The two are one decision: a grid cannot end
where the screen ends and also be measured in pixels from the top. The panel
divides the page by `rows` the way it already divided it by `cols`, and `n`
cells plus `n - 1` gaps add back up to the whole - which is what puts the far
edge of the last one exactly on the page's.

That makes `rows` the density control as well as the limit: raise it for
thinner tiles, finer placement and more presses to cross the page; lower it
for fewer, bigger ones. There is no arrangement of this in which those are two
settings. `[menu] cell_height` is the same question for the menu's own grid
and is deliberately a different answer.

`place(items, columns, plan, rows)` takes the count and **clamps a pin onto
the last row**, exactly as it clamps one onto the last column. It has to: the
menu is where a page is arranged, the menu has no last row, so a tile can be
carried further down there than this grid has. `omapad check --layout` names
both clamps.

`[hud] margin` is how far off the edge the grid starts, and it is not the
menu's `contentMargin`. A fullscreen card keeps a television's overscan clear
of its first tile; this is a corner somebody deliberately put something in, so
it defaults to a hair off the edge and 0 is the corner itself. The panel's
`ExclusionMode.Normal` does the rest - the last row stops where the bars
start, rather than under one.

**`[ui] safe_area` is the floor under it, and only in game mode.** The corner
is deliberate and stays deliberate on a monitor; on a television the corner is
the part of the picture the set does not draw, so the grid is held off to a
share of the screen instead - and two shares rather than one, because a
twentieth of the height and a twentieth of the width are different numbers.
`[hud] margin` stays one number for the reason it always was: it is the same
corner on either axis. Whichever is further in wins, so a margin raised past
the safe area is still the margin.

**It is a setting, not a surface that is opened.** `[hud] show` is in
`config.CHOSEN`, so the switch on the page, `omapad ctl hud on` and the
settings file are three doors onto one value - and it is still on tomorrow.
Every other surface is opened and closed; this one is decided once and left.
`set_hud()` is deliberately not `set_menu()`: there is nothing to close first,
no `apply_grab()` and no layer.

**It reads no pad input at all.** No `[bindings.hud]`, no entry in
`SURFACE_LAYERS`, no grab, `WlrKeyboardFocus.None` and an empty input region,
so every click goes to the window underneath. The moment it could take a press
it would be in the way of the game it is over.

**It is `WlrLayer.Top`.** The menu, the guide and the keyboard are Overlay, so
opening one of them covers the readings rather than fighting them for the same
band of screen. `ExclusionMode.Normal` with the zero exclusive zone it defaults
to asks for what is left once the bars have taken their strips, which is why no
bar geometry has to travel in the payload and the top row can never come up
underneath the game bar.

## Two rules about what it refuses to draw

Both are in `HudModel.view_state`, and both are the point of the surface.

1. **A tile with something to press is not drawn.** The page holds its own
   switch - it has to, because this surface is never pressed - and a switch
   drawn over a game would be a control with no way to reach it. `DRAWN` is
   what is left: a `readout` and a `clock`, neither of which is a control.
2. **A reading that has never answered draws nothing at all.** A fan this
   laptop publishes no number for is not a tile saying nothing, it is no tile.
   That is what makes one page of readings correct on two machines.

**The first rule was about readings until a clock asked to be here**, and the
wording is the change: what a tile needs in order to stand over a game is
nothing to press, not a number to print. Game mode takes Omarchy's bar away,
and the bar is where the time was - so the surface that stands in for the bar
is where the clock belongs. A clock is also outside rule 2 without being an
exception to it: nothing publishes the time and nothing could fail to, so
there is no source to have gone quiet and no machine this tile is untrue on.
It is never asked, and never dropped. See [`menu.md`](menu.md) for the tile
itself, and `Clock.qml` for the drawing, which is the menu's own.

**A chronograph is the case that shows the rule is the press.** It is the same
face with a stopwatch in it and it is not drawn here, because A on it starts,
stops and resets a measurement - a pusher over a game is a control with no way
to reach it, which is the switch's own argument on a tile that looks like the
clock. Written onto this page it is packed like any other tile and simply not
drawn. See [`chrono.md`](chrono.md).

The **whole** page is still packed, including the tiles that will not be
drawn. That is what keeps the promise: a readout lands in the cell the menu
shows it in, and it cannot do that if the tiles before it were taken out of
the packing first.

The menu draws the same page and does **not** follow rule 2: a readout there
keeps its label with the value blank. The menu is where you go to find out
that a reading has no source on this machine, and a row that vanished could
not tell you.

## Where the numbers come from

`sysinfo.py` is a source rather than a surface - the same shape `live.py` and
`snap.py` have. `live.py` is what the *desktop* is doing and every one of its
answers is a helper's; these are what the *kernel* publishes about the machine
underneath, so almost all of them are a file read.

**Where each reading comes from is a setting**, in one grammar:

| Source | Reads |
|---|---|
| `proc:stat` | the busy share, across an interval |
| `proc:meminfo` | memory in use, against `MemAvailable` |
| `mount:<path>` | how full a filesystem is, by any path on it |
| `hwmon:<chip>/<file>` | a sensor, by the name the chip publishes |
| `file:<path>` | one number, from one file |
| `cmd:<command>` | a helper that prints one number |

Because there is no answer here that is true of every machine: which chip holds
a temperature, whether the graphics card publishes a load at all, whether
anything on this desktop knows a game's frame rate. **An empty source is a
reading this machine does not have** - nothing asks for it, and no tile is
drawn. Three ship with a source because three are true of every Linux; the rest
are empty, because a sensor picked for somebody prints the wrong number under
the right word.

Sources are parsed in `config.py` and raise `ConfigError`, so `omapad check`
names one that cannot work - and `check` also prints what each reading
currently says, because a source pointed at nothing looks exactly like a
reading nobody asked for.

Four things worth knowing before changing any of it:

- **A busy share is measured across an interval.** `/proc/stat` counts ticks
  since boot, so one read says what the machine has averaged since it was
  switched on. The first read therefore answers `None` deliberately, and
  `parse_stat` keeps the sample so the next one has an interval to measure.
- **hwmon is found by name, never by number.** `hwmon4` is a battery on one
  boot and a network card on the next. `*` takes whichever chip has a file of
  that name.
- **A reading that stops answering keeps its last value.** A sensor briefly
  busy, or a helper a second late, must not be able to empty the HUD. A source
  that has *never* answered has no value, and that is how a tile knows not to
  draw itself.
- **A reading is words.** The tile is its name and its figure on one line,
  and the menu's readout tile is the same two things - a page of readings has
  to read the same in both places it appears. A share drew the menu's slider
  line under itself until [92](../decisions/92-a-tuning-scale.md), and on a
  surface nothing can push it read as a control that had lost its thumb.

  `fraction()` still answers a share for anything with a `full` in
  `READINGS`, and the daemon still sends it as `v`: it is a fact about the
  reading, and no panel draws it. A thermometer has none, because its top of
  scale is a number somebody would have to invent.

## Asking, and not asking

`sys_refresh()` runs from the poll loop. **Nothing is asked for a reading
nobody can see**: `sys_names()` merges what the HUD is drawing with what the
menu is drawing, and with neither up the poll table is cleared - what the
machine was doing a minute ago is not what it is doing now.

Everything this side can answer is a file read out of procfs or sysfs, which
is microseconds with nothing to block on, so it happens on the loop. A `cmd:`
source is the exception and goes through `submit_command` like every other
slow thing, one question in flight per reading - a helper that has wedged must
not collect a queue of identical questions behind it.

## The payload

`hud.sock`, one line per update, `VIEW_HEARTBEAT` apart or whenever a reading
moves:

```json
{"open": true, "cols": 6, "rows": 12, "corner": 10, "margin": 16,
 "opacity": 0.9, "scale": 1.0, "badge": "stencil", "bar": true,
 "items": [{"id": "processor", "l": "Processor", "i": "a",
            "k": "readout", "x": 0, "y": 0, "w": 2, "h": 1,
            "t": "37%", "v": 0.37},
           {"id": "time", "l": "Time", "k": "clock",
            "x": 0, "y": 1, "w": 2, "h": 2, "mn": 825}]}
```

`rows` is `[hud] rows` - how many the screen is cut into, **not** how tall
the page came out. `corner` is `[menu] tile_corner`, so a tile is the same
shape in both places - the base of `metrics.radius` where the compositor
rounds nothing, not a radius; there is no `cell`, because a cell's height is
this grid's to work out. They travel for the reason every geometry setting does:
the shell cannot read the config. `v` is a share's place along its scale, absent
for anything that is not a share, and nothing draws it (see above).

`k` is which of the two kinds of tile this is, and it rides on every one of
them rather than on the clock alone: the panel has two drawings to choose
between and this is the whole of the choice. `mn` is the clock's own - both
hands as one number, minutes since midnight, worked out here rather than
asked of the daemon so the two surfaces that draw one page cannot be a minute
apart. See [`menu.md`](menu.md) for why it is one number.

## Changing it

Read [`../procedures/pad-surface.md`](../procedures/pad-surface.md) first.
Two things here are not in that checklist:

- **Adding a reading** is four places: `sysinfo.READINGS`, a parser if the
  shape is new, a line in `[sysinfo]` with its default and a comment, and a
  test over canned text. Then it can be put on a tile with
  `control = "readout"`, `reads = "sys:<name>"`. Nothing in the panel changes.
- **The two panels draw one page.** A field added to a readout tile has to
  land in `Menu.qml` and `Hud.qml` both, or the page reads differently in the
  two places it appears - which is a page somebody has to learn twice.
