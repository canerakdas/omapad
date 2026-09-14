# Menu rows

> Add, reorder or review tiles in the omapad controller HUD - the
> [[menu.items]] tree the pad walks with the D-pad, and the [[menu.head]] grid
> above it. Use when asked to "add X to the menu", "put a
> launcher/setting/toggle on the pad", "reorganise the menu", or when a tile
> does nothing, does not tick, or throws you out of a page. Covers groups,
> tiles, spans, launch-or-focus, and what belongs on a sofa.

The controller menu is the one door that reaches past an app holding the pad,
so it is where a capability goes when it cannot have a button. It is a grid of
tiles under a bar of groups, not a radial: a radial reads a stick angle in one
flick but caps out at a handful of entries and has nowhere to put a page.

Read [`docs/components/menu.md`](../components/menu.md) first. Rows
use **the same action grammar as a button binding**, so the menu reaches
anything a button can - see
[`docs/conventions/bindings.md`](../conventions/bindings.md).

**What the row says is a second job**, with a standard of its own:
[`docs/conventions/writing.md`](../conventions/writing.md),
and [`pad-wording.md`](pad-wording.md). A row that does the right thing and
reads as a riddle from the sofa is not finished.

## The one question to ask first

**Does this belong on a sofa?** The menu is walked with a thumb from across a
room, not browsed. Two things disqualify a row:

- **It says nothing when it cannot work.** A launcher for something that is
  not installed is worse from a sofa than no row at all - you press it and the
  screen does not change. Battle.net is kept out of the shipped menu for
  exactly this. Either ask first (`omarchy-cmd-present`) or leave it out.
- **It wants a keyboard.** The real Omarchy menu is a hold on PLUS precisely
  because it is driven by typing. Do not reimplement it here.

## Groups: the top level is the bar

**A top-level entry is a group** - a chip on the bar, walked with the
shoulders - and it holds the tiles of one page. The bar holds *places*, so a
top-level label is a noun ([`pad-wording`](pad-wording.md) rule 11). A verb
there still works, as a page of one, but the shipped tree puts none there.

Which means a capability that used to be a loose top-level row now goes
**inside** a group. Where it needs to be found the moment the menu opens -
which is what the workspace lock needed, and why item 48 put it at the top
level - it says so:

```toml
[[menu.items.items]]
label = "Workspace lock"
action = "lock:toggle"
when = ["game", "handed_over"]
open_on = true                    # the menu opens ON this while `when` holds
```

`open_on` is valid only beside a `when`: only a tile that is sometimes offered
has anything to be nearer about. Earliest in the tree wins.

## Tiles

An entry needs a `label`, and has **either** an `action` **or** nested `items`
- never both. `build()` parses actions at load, so a typo surfaces in
`omapad check` rather than doing nothing at the press.

```toml
[[menu.items]]
icon = "󰀻"                      # any glyph in the shell's font
label = "All apps"
detail = "Everything installed"   # the second line; optional
action = "exec:omarchy-menu toggle apps"
```

| Field | What it does |
|---|---|
| `label` | required |
| `icon` | a glyph the shell's font has |
| `detail` | one line under the label - written once, so it cannot know anything live. ~40 characters, says what happens: [`pad-wording`](pad-wording.md) |
| `action` | the binding grammar, parsed at load |
| `items` | a submenu; mutually exclusive with `action` |
| `repeat` | a row you **nudge** rather than pick: hold A and it repeats, the menu stays put. Volume, brightness, a speed |
| `stay` | one press, menu stays up. What a row that changes a setting the menu itself prints needs |
| `from` | a command whose output **is** the submenu, read at the press. With `action` as the template each line runs, and `empty` for what the page says when it finds nothing |
| `when` | the states the row is offered in - `game`, `handed_over`, `locked`, any one of them being enough. Read when the menu opens. For a row that could do nothing useful elsewhere: the workspace lock has nothing to lock to on a desktop |
| `open_on` | the menu opens on this tile while its `when` holds. Needs a `when` |
| `id` | what a layout calls this tile. A slug of the label unless said, and unique on its page |
| `span` | `[width, height]` in cells. `[1, 1]` unless said, and never wider than `[menu] columns` |
| `control` | what kind of tile this is. `row_break` ends the row and draws nothing; `toggle`, `choice`, `slider`, `gauge` and `media` hold a value |
| `shows` | which stick a `gauge` draws the position of, `left` or `right`. Required on one, refused on anything else |
| `reads` | where a control takes its value, `pad:<setting>` or `live:<reading>`. Required on a control, refused on anything else |

`repeat` implies `stay`. Both are rejected on a submenu row - `MenuError` says
which path.

**The default is that the menu closes first and the command runs after**, so
the window you opened is not left behind the dimming. `stay` is the exception,
and it is what a setting row wants: choosing a badge layout and being thrown
out means opening the menu four times to try two of them.

## Rows that know the answer

A row that *sets* something is **ticked** while that thing is in force, which
is the whole difference between a list of choices and a list of guesses. The
daemon answers that, not the row: `view_state(opened, state, value)` takes
`state(action)` for the tick and `value(action)` for a row that steps a number.

A number cannot be ticked - every step is equally "not the case" - so those
rows print where they have got to instead (`9 notches a second`), and `value`
replaces the row's own `detail`. If a setting you add should tick or print,
it needs to be in `CHOSEN`; see [`pad-setting.md`](pad-setting.md).

## Rows you cannot write down

Which speakers are in the room is not something a config file knows: plug a
television in and there is one more. A row that could only name what was
written down would be pointing at whatever was there the day it was written, so
that row **lists** instead:

```toml
[[menu.items.items]]
label = "Output"
detail = "Speakers, headphones, the TV"
empty = "No outputs found"                            # if it prints nothing
action = "exec:omarchy-audio-output-set-default %1 %2"
from = "..."     # prints: label \t %1 \t %2, one row per line
```

- The command runs **every time the row is entered** - that is the point of it.
  It runs on the event loop, so `[menu] list_timeout_ms` is the pause a press
  may take; keep the command to one that answers quickly.
- A label that starts with `*` is **ticked** - the mark `pactl` and `wpctl`
  already print beside the current device. Without it the page is a list of
  guesses.
- Values are quoted as they go in, so a device that names itself from its own
  USB descriptor cannot become a second command. Write the command so each
  value is one argument.
- Picking a listed row keeps the menu up and moves the tick, so two of them can
  be tried without reopening anything.
- `empty` is a user-facing line like any other:
  [`pad-wording`](pad-wording.md), not a stack trace.

## Launching something

```toml
# Launch **or focus**: with a pointer this slow, a second copy of a chat client
# is never what was asked for.
action = "exec:omarchy-launch-or-focus discord \"...\""
```

- `omarchy-launch-or-focus <class> <command>` matches the class **and** the
  title, so it finds the window whichever way the thing was installed.
- `omarchy-cmd-present <cmd> && ... || ...` is how a row copes with an app
  that may be a native client **or** an Omarchy webapp - the two have nothing
  in common but the name.
- Omarchy has its own launcher for some apps (`omarchy-launch-spotify`) that
  focuses a running one and offers to install a missing one. Prefer it.
- `exec:` runs in a transient scope of its own, so a daemon restart does not
  kill what you opened.

## A tile that holds a value

A `control` tile is not a verb. It reads a setting, draws what that setting is
on, and A acts on it:

```toml
[[menu.items.items]]
label = "Vibration"
control = "toggle"          # a bool
reads = "pad:rumble"

[[menu.items.items]]
label = "Button style"
control = "choice"          # a choice; A walks it forward
reads = "pad:badge_style"

[[menu.items.items]]
label = "Pointer"
control = "slider"          # a number; A takes it, then left and right
reads = "pad:pointer_speed"

[[menu.items.items]]
label = "Left stick"
control = "gauge"           # the same number, as a dial
reads = "pad:left_deadzone"
shows = "left"              # and where the thumb is, which is no setting
```

The kinds have to match, and `omapad check` says so: a `toggle` reads a
`bool`, a `choice` reads a `choice`, a `slider` and a `gauge` read a `number`,
a `media` reads a `media`. A control needs no `action` and no `items`, cannot
`repeat`, and always stays.

**Two sources.** `pad:` is one of omapad's own settings, and `live:` is what
the machine is doing - `volume`, `mute`, `brightness`, `media`. A `live:`
reading is also drivable from a button, as `live:volume=up`, exactly the way
`pad:` is. See [`../components/live.md`](../components/live.md).

**Reach for one when the old shape was two rows that both ticked.** `On` and
`Off` as separate rows was always a switch written out longhand. Two rows
became one tile; four became one.

**Do not reach for one when the choices need explaining.** A choice tile shows
one value, so the line each row of a tick submenu carried saying *how the
choices differ* has nowhere to go. `Button labels` and `Profile` keep their
submenus for exactly that: getting either wrong scrambles the face buttons,
and the sentence under each choice is what stops you. `Button style` and
`Start in` converted because their two values say the difference themselves.

Give a control tile room for its name **over** the control - `Hide the
pointer` is `span = [2, 1]` because three words over a switch do not fit in
one cell. A control tile draws no icon: the control is the picture. A slider
is three cells by default and reads left to right - its name and its number
share one line and the bar goes under both - so it needs no `span` and no
`detail`; the number is the detail.

**A gauge is the one tile that makes the menu stream.** Only while it is the
tile in front, and only while the menu is open - so reach for one when the
thing being set is about a *stick*, and not otherwise. Everything else on this
surface costs the loop nothing.

**A slider is how a number gets a tile.** `pad:<name>=up|down` rows are the
shape a number had before there was one: two rows saying "faster" and
"slower", neither of which could say what the number was or that it had
stopped at an end. Write a slider instead. The only thing still worth a
stepping row is a number that is *not* a `pad:` setting.

Two ways to move one: **A takes it and the D-pad lands on the number you
meant** (faster the longer a direction is held), and **either trigger sweeps
it** whether or not it has been taken. Once it is taken, **A keeps what it is
on and B puts it back** - leaving is what B means everywhere, and a slider is
where that finally has something to undo.

## A page the person has rearranged

Anything written here is the **shipped** arrangement, not the final one:
holding Y on a page turns on edit mode, and what somebody does there lands in
`~/.config/omapad/layout.toml` and is applied over this. Three rules keep the
two from breaking each other:

1. A tile hidden from the pad is hidden **only while the config still has it**.
2. A tile you add here **always appears**, at the end of the page, even for
   somebody who rearranged it a year ago.
3. A tile you remove here is **dropped from their saved order**, silently.

So changing this file is safe, and the only thing to keep in mind is that a
tile you add lands at the end of an arranged page rather than where you wrote
it. `omapad check --layout` says what a saved arrangement still resolves to.

A fourth thing a person can do is **put a tile in a cell**, which is stronger
than the three above: a pinned tile is out of the flow entirely, so the order
you write here decides only where the tiles *around* it go. That is the one
case where the page somebody sees can have gaps the page you wrote does not -
and it is their gap, so leave it alone.

**Never edit `layout.toml` by hand to change what ships.** It is one person's
arrangement of the page; the page is here.

## How a page is laid out

Tiles are packed **first fit, in the order you wrote them**, left to right and
top to bottom. So the order is still what you decide - it is the same order a
thumb reaches in - and a small tile is allowed to backfill the hole a big one
left rather than the order being rewritten to avoid holes.

A `row_break` tile ends the row it is in:

```toml
[[menu.items.items]]
control = "row_break"
```

Reach for one to group tiles that belong together, and **not** to nudge a tile
into place: the same page has to read at six columns and at four, and a break
is the one gap that means the same thing at both.

## Spending a page's X or Y

A page may take **X and Y** for a job of its own; the legend along the foot
prints what it took them for.

```toml
[[menu.items]]
label = "Apps"

  [menu.items.keys]
  Y = { tap = "exec:omarchy-menu toggle apps", short = "All" }
```

Three things the parser enforces, so `omapad check` names the page rather than
a press finding out:

- **Only X and Y.** A commits and B leaves, everywhere.
- **X keeps `menu:close` on the hold.** It is how you leave from every other
  page.
- `short` is the one word the legend prints;
  [`pad-wording`](pad-wording.md) owns it, and it is required wherever the
  first word of `desc` is not the meaning.

**Ask whether it is reachable on screen first.** That is
[`bindings.md`](../conventions/bindings.md) rule 2's own test, and a page of
tiles almost always has room for one more tile - which costs nobody a reflex.
Nothing in the shipped tree spends a key. Play / pause on `Now` is the worked
example of when *not* to: the tile is right there.

## The head

`[[menu.head]]` is the read-only grid above the bar. Nothing on it is
selectable, so nothing on it is a row - a cell prints a time or the last thing
a command said, and that is all it does.

```toml
[[menu.head]]
span = [2, 3]
over = { from = "id -un", ttl = 0 }   # a line above, small and in capitals
format = "%H:%M"                      # the headline - strftime
under = "%A"                          # and a line below it

[[menu.head]]
span = [4, 1]
from = "omarchy-weather-status"
ttl = 900                     # seconds before it is asked again
empty = "Weather unavailable" # before the first answer, and after a failure
```

**A cell is up to three lines and every one of them is the same kind of
thing**: a `format` or a `from`. `over` sits above the cell's own line and
`under` below it, both set small. A bare string is a `format`, which keeps
`under = "%A"` the whole of what a weekday costs; a table is the long form,
and it is how a line becomes a command:

```toml
over = { from = "id -un", ttl = 0 }
```

Three lines in one cell rather than three cells, because the head packs first
fit like everything else here: two cells could land side by side as easily as
stacked.

`ttl` is data freshness, not redraw: the card repaints every couple of seconds
whatever this says. **Zero never goes stale** and is asked once a session -
which is what a name or a hostname wants, and what a clock would be wrong to
use, because a `format` is rendered on every redraw and costs nothing.

**A cell more than one row tall prints a headline**, the biggest thing the
surface draws, with `over` and `under` small and in capitals around it; a cell
one row tall prints a line of text. The height is the whole of that decision,
so the way to turn the clock down is to give it fewer rows - and a `from` cell
stays one row tall unless you want its answer set like a headline.

**Give a stacked cell the rows its lines need.** The shipped clock is three
because a name, a time at the top of the ladder and a weekday do not fit in
two, and a cell that asked for a headline without the room would clip rather
than shrink.

**A `from` cell owns nothing.** The command is a string from the config, and
whatever it names owns the network, the location, the caching and what to say
when it fails. That is what keeps a weather cell from being weather support:
put a helper there that already answers those, or leave the cell out.

## Ordering

The shipped order is the argument: **what a couch reaches for first**. Steam
leads because on a sofa that is what the menu is opened for; the apps that
make a sofa a sofa follow; "All apps" is last because it is a list no
controller menu should try to be.

When adding a row, place it by frequency from the couch, not by category.

## Verifying

```bash
./bin/omapad check              # parses every row; names the path of a bad one
systemctl --user restart omapad
./bin/omapad ctl menu toggle    # walk it without the pad
```

Then walk it with the D-pad and check three things: the row does something
visible, a setting row is ticked when it is in force, and getting back out is
one press of B per level.
