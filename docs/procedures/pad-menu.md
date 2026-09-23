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
- **It wants a keyboard.** The real Omarchy menu is one tile under System
  that opens it, precisely because it is driven by typing. Do not
  reimplement it here.

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
# icon_font = "omarchy"         # only where the glyph is not in that font
label = "All apps"
detail = "Everything installed"   # the second line; optional
action = "exec:omarchy-menu toggle apps"
```

| Field | What it does |
|---|---|
| `label` | required |
| `icon` | a glyph the shell's font has |
| `icon_font` | the family that glyph came from, where it is not the shell's - a glyph only exists in the font that drew it, and Omarchy's own mark (U+E900) is in `omarchy.ttf` and nowhere else |
| `detail` | one line under the label - written once, so it cannot know anything live. ~40 characters, says what happens: [`pad-wording`](pad-wording.md). Drawn only where the tile is two rows or taller; a one-row tile has no room for it |
| `meta` | the line the tile **cannot** write down: `{ from = "...", ttl = 2, empty = "..." }`, a command's answer standing where the written line stands - the heading on a card of rows, the detail on anything else. Run only while its page is in front. For the question a config file cannot answer, like which window `Windows` is about to close |
| `action` | the binding grammar, parsed at load |
| `items` | a submenu; mutually exclusive with `action` |
| `repeat` | a row you **nudge** rather than pick: hold A and it repeats, the menu stays put. Volume, brightness, a speed |
| `stay` | one press, menu stays up. What a row that changes a setting the menu itself prints needs |
| `countdown` | a row that is **pressed and then waits**: A starts `[menu] countdown` seconds (or the number this says), the row prints them, and B stops it. For what takes the screen away - logging out, rebooting. Only on an action row, and never beside `confirm` or `repeat` |
| `confirm` | a row that is **held** rather than pressed: A starts the announced hold every other one of ours makes - the tile fills, the pad ticks, a notification says what is coming, B and letting go both back out - and only when it has counted down does the row run. Both waits are `[confirm]`'s, `[confirm] scale` reaches them, and the legend says `Hold to confirm` while the tile is in front. Only on an action row, and never beside `repeat` |
| `from` | a command whose output **is** the submenu, read at the press. With `action` as the template each line runs, and `empty` for what the page says when it finds nothing |
| `when` | the states the row is offered in - `game`, `handed_over`, `locked`, `kept`, `first_run`, any one of them being enough. Read when the menu opens. For a row that could do nothing useful elsewhere: the workspace lock has nothing to lock to on a desktop |
| `open_on` | the menu opens on this tile while its `when` holds. Needs a `when` |
| `id` | what a layout calls this tile. A slug of the label unless said, and unique on its page |
| `span` | `[width, height]` in cells. `[1, 1]` unless said, and never wider than `[menu] columns` |
| `control` | what kind of tile this is. `row_break` ends the row and draws nothing; `rows` draws its own `items` as lines inside it; `toggle`, `choice`, `slider`, `gauge` and `media` hold a value |
| `many` | on a `rows` card: its keys **latch** rather than interlock, so any number of rows can be on at once. The line down the card goes and every row gets a key. Refused anywhere else, and on a card that lists |
| `shows` | which stick a `gauge` draws the position of, `left` or `right`. Required on one, refused on anything else |
| `reads` | where a control takes its value, `pad:<setting>` or `live:<reading>`. Required on a control, refused on anything else |

`repeat` implies `stay`. Both are rejected on a submenu row - `MenuError` says
which path.

**The default is that the menu closes first and the command runs after**, so
the window you opened is not left behind the dimming. `stay` is the exception,
and it is what a setting row wants: choosing a badge layout and being thrown
out means opening the menu four times to try two of them.

## Rows nobody can take back

The question to ask first is **what a second press undoes**. Not what sounds
serious: Lock and Suspend are one button away from where you were, and both
are a plain press. Logout, Reboot, Shutdown and Close window are not - whatever
was unsaved is gone.

There are **two** answers and they are for two different presses.

| | Gesture | For |
|---|---|---|
| `confirm = true` | A is **held**; the tile fills, the pad ticks, B or letting go backs out | where the gesture is already in the hand and is over in a second |
| `countdown = true` | A is **pressed**, then the row counts `[menu] countdown` seconds down and runs; B stops it | where what happens next takes the screen away |

**The hold** is the same gesture a binding's `confirm = true` makes,
deliberately: somebody who has held a shoulder to cross a workspace over a game
already knows what a filling badge means. `Close window` is the one the shipped
tree spends it on - you are looking at the window, and the answer is wanted
now.

**The countdown** is for the three under `System > Power`. Being sure that you
meant to log out is not a thing to do with a thumb; it is a thing to be given
long enough to change your mind about, and holding A for ten seconds is not a
gesture anybody makes. The menu stays up, the row prints the number, the legend
says `Cancel` on B - and **only** B stops it, because ten seconds is long
enough to want to look at something else on the page.

`countdown = 5` sets the length for one row; `true` takes `[menu] countdown`.
A row is held or counted, never both, and neither goes beside `repeat`. It
works on a plain **tile** as well as on a row in a card. `Reboot` and
`Shutdown` were written both ways for a while - a row in `Power` and a cell of
their own, because they are the two anybody walks to that page for - and are
one each now: a copy is the same word twice a cell apart, and a guard that has
to be kept in step in two places. **Write one of anything, and if you do write
two, give each its own `id`**: the flash and the countdown both name a tile by
id, and two things answering to one name is two things lighting up for one
press.

Spend either sparingly. A page where three rows in four have to be held is a
page where holding means nothing, and the one row that needed it is hidden
among them.

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
label = "Volume"
control = "knob"            # the same number, as a ring the stick turns
reads = "live:volume"

[[menu.items.items]]
label = "Left stick"
control = "gauge"           # the same number, as a dial
reads = "pad:left_deadzone"
shows = "left"              # and where the thumb is, which is no setting
```

The kinds have to match, and `omapad check` says so: a `toggle` reads a
`bool`, a `choice` reads a `choice`, a `slider` and a `gauge` read a `number`,
a `media` reads a `media`, and a `knob` reads **either** a number or a choice -
the only control with two kinds. A control needs no `action` and no `items`,
cannot `repeat`, and always stays.

**A knob rather than a slider is a question about the hand, not the page.**
They read the same things and step the same steps; what a ring adds is that a
held one is turned by carrying the thumb round the stick, which is the one
gesture on this pad that is already what the drawing does. Reach for it where
somebody arrives at the value often and does not want to step towards it - how
loud it is - and leave a bar where the value is read more than it is set. Two
cells square, like the dial: a page that holds one of each has a length and an
angle answering one question, which is the honest way to find out which you
reach for.

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
and the sentence under each choice is what stops you. `Button style` converted
because its two values say the difference themselves.

**Where the sentence is the problem, the answer is a card of rows** rather
than a submenu - see below. `Start in` is the worked example: as a choice it
read `Game mode` and you had to press it to find out what else there was; as a
card it shows both values, each with its own line, and fills the one waiting.

Give a control tile room for its name **over** the control - `Hide the
pointer` is `span = [3, 1]` because three words over a switch do not fit in
one cell, and because three is the width of the column it stands in. A control tile draws no icon: the control is the picture. A slider
is three cells by default and reads left to right - its name and its number
share one line and the bar goes under both - so it needs no `span` and no
`detail`; the number is the detail.

**A gauge is the one tile that makes the menu stream.** Only while it is the
tile in front, and only while the menu is open - so reach for one when the
thing being set is about a *stick*, and not otherwise. Everything else on this
surface costs the loop nothing.

**A slider whose setting has `stops` draws itself differently**, and the
setting decides rather than the row: the bar becomes one segment per stop, lit
up to the one you are on, and the line above it prints that stop's word rather
than a percentage. `Corners` is the one that ships. See
[`pad-setting.md`](pad-setting.md).

**A bar is aimed at, so give it the width the band can spare.** Three cells
is the default and the floor; the shipped sliders run to four and six where
the row had the room, and the longest of them are the three on `Display` -
the numbers you set by looking at what they did.

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

## A card of verbs, drawn as rows

`control = "rows"` draws a tile's `items` **inside** it, one to a line, instead
of drilling into them:

```toml
[[menu.items.items]]
label = "Power"
control = "rows"
detail = "Auto-sleep 30 min"      # the line along the foot; optional
span = [2, 3]                     # the default, and usually right

  [[menu.items.items.items]]
  label = "Rest mode"
  action = "exec:systemctl suspend"

  [[menu.items.items.items]]
  label = "Full shutdown"
  action = "exec:systemctl poweroff"
  confirm = true
```

**Reach for one when the tiles you are about to write are verbs.** A verb has
nothing to show but its name, so a cell spent on one says a single word - and
four side by side say four words in the room one sentence needs. `Screensaver`
drawn as `Screensa…` is what that costs - it is a row on `Display ▸ Screen`
now - and it is the test: if the labels on a run of tiles do not fit a cell and
none of them has a value to show, they are a card of rows. The line under a
name is the other half of the test: a tile one row tall draws no `detail` at
all, so a verb that needs a sentence needs a card.

**Do not reach for one where a tile has something to show.** A value, what is
playing, where a stick is - those are cards because the drawing needs the room,
and a row is one line of text. `omapad check` refuses a control inside a card
rather than letting it draw a blank line.

The tile's own `label` is the heading and its `detail` the line along the foot,
both small and in capitals - the two ends of a card, the way every other tile
on this surface is read. A row takes `label`, `icon`, `action`, and `confirm`,
`repeat` or `stay` like any other row; the hold fills the **row**, and the
legend says `Hold to confirm` over the row that carries one rather than over
the whole card.

**A row may carry its own `detail`**, and that is the thing a choice tile could
never have: the sentence saying how this value differs from the one under it.
It is drawn small under the name, dim until the row is in front.

```toml
[[menu.items.items]]
label = "Start in"
detail = "The mode at the next start"
control = "rows"
span = [3, 2]                     # three, because a sentence needs the width

  [[menu.items.items.items]]
  label = "Game mode"
  detail = "A bigger bar; nothing else changes"
  action = "pad:start_mode=game"
  stay = true

  [[menu.items.items.items]]
  label = "Desktop"
  detail = "Omarchy's own bar, at its own size"
  action = "pad:start_mode=desktop"
  stay = true
```

A row that sets something answers the same question a tile does, and in a card
it is said by **filling the row** rather than by a mark: the one in force has a
ground and the rest are words on the card. `stay` is what keeps the menu up
while you watch it move. Give a card carrying detail lines **three cells** -
forty characters do not fit in two.

What a card may not do, each of which `omapad check` names:

- **A row cannot open a page.** The card is already the page, so there is
  nowhere further in for a level to be.
- **A row cannot hold a value**, and a `row_break` is not a row: a break ends a
  row of cells, and these are not cells.
- **A card spends no X or Y.** A key is spent while a page is *in front*, and
  nothing is ever in front of a card of rows.
- **A card takes no `icon`.** An icon everywhere else here is the big mark in a
  tile's top corner - what says which tile this is from across a room - and a
  card of rows has no corner to spare. Set at the heading's size in front of
  tracked capitals a glyph reads as a bullet. The marks go on the **rows**,
  where a row that needs one says so.

### A card of switches, whose keys latch

`many = true` is the same card with the rows latching rather than
interlocking. Reach for one where the rows are **not** alternatives - where
two of them being on at once is an ordinary thing to want:

```toml
[[menu.items.items]]
label = "Feedback"
detail = "What a press answers with"
control = "rows"
many = true
span = [3, 2]

  [[menu.items.items.items]]
  label = "Vibration"
  detail = "The motor, in the hands"
  action = "pad:rumble=toggle"

  [[menu.items.items.items]]
  label = "Sounds"
  detail = "A cue, in the room"
  action = "live:mute=toggle"
```

The ordinary card says which row is in force by lighting its **length** of the
line beside the rows, and a length has one start and one end - so on a card
where two rows are on there is nothing for it to light. The old radio is the
whole argument: the band buttons are interlocked and pressing one lets the last
one out; the tone keys beside them each stay down on their own. So a latching
card drops the line and gives every row a **key** - a small rectangle at the
head of it, with a lit core in the middle while it is down.

- **The row's action is what flips it**, and for a switch that is
  `pad:<name>=toggle` or `live:<name>=toggle`. Those answer which way the
  switch is set, which is what lights the key: a row written as
  `pad:rumble=on` would light while it was on and never turn it off again.
- **Every row on one stays**, without being asked. A key that sent the menu
  away as it went down would be a bank nobody could set.
- **A latching row carries no glyph.** The key stands in the slot a glyph
  wants, and two marks at the head of one row is a card asking a reader to
  learn which of them means what.
- **A card that lists cannot latch.** The `*` a listing prints is the mark of
  the one in force and a press moves it, so there is nothing there to latch.
- Give one the width its sentences need, like any card of rows.

**Do not reach for one where the rows are alternatives.** `Start in` is a card
of two rows and exactly one of them is true; drawn as keys it would be offering
a state - both of them - that the setting behind it cannot hold. The test is
whether pressing the second row should let the first one out.

### A card that lists what is plugged in

A card takes `from` like a submenu does, and that is what `Sound` ends in:
two cards, one of outputs and one of inputs, each a command's output drawn
where it stands.

```toml
[[menu.items.items]]
label = "Output"
detail = "Speakers, headphones, the TV"
control = "rows"
span = [3, 3]
empty = "No outputs found"
action = "exec:omarchy-audio-output-set-default %1 %2"
from = "..."          # prints: label \t %1 \t %2, one row per line
```

**A listed card is read when the page it stands on settles**, not at a press -
nobody enters a card, it is already open. `[menu] group_settle_ms` is that
wait, the same one the bar takes, so walking across four pages spawns one
command rather than four. Until the first answer the card draws its own
`empty` words: a blank card on a page you are looking at reads as a drawing
fault rather than as a question nobody has answered yet.

**A listing that finds one thing it has marked is drawn as a reading**, not as
a list: the heading names it, the line is the answer, and A does nothing -
picking it would set what is already set. Plug a second device in and it is a
list again. A card you wrote one row into is unaffected; a verb is a verb
whether or not it has company - and so is a **listed** one: a lone row with no
`*` in front of it is something to run or to switch to, so a folder with one
script in it is a list of one.

Everything else about a listing is unchanged - `*` marks the one in force, the
values are quoted on the way in, and picking one keeps the menu up and moves
the fill. It was `Devices` opening on `Output` opening on the outputs: two
presses in before a name you could pick, and each of those pages held exactly
one thing.

### Going in, and coming back out

**A card is entered with A**, the way a slider is taken, and up and down belong
to the page until it is. That is not friction, it is the only way one direction
can mean one thing: with the rows walked in place, down on a card meant the
next *row* while down on the tile beside it meant the next tile, and the tile
underneath - which is what a thumb pushing down is reaching for - was two more
presses away.

Inside, up and down walk the rows and stop at either end (left and right say
nothing - a list runs down the card), A runs the row in front, and **B leaves
the card without leaving the page**. The row you were on is still there the
next time you go in.

**Two marks, one thing each.** A line runs down the side of the list. The row
**in force** is its length of that line, lit, with a small wedge leaving it to
the right - a state,
so it is drawn always, on a card nobody has selected. The row **A would run**
has a faint ground instead, and only while the card has been entered: up and
down belong to the page until A goes in.

A card of verbs has nothing lit, because nothing on one is in force.

The line is capped with a small cross at each end, so it begins and ends
somewhere rather than at the edge of whatever is behind it.

## A page the person has rearranged

Anything written here is the **shipped** arrangement, not the final one:
Y on a page turns on edit mode, and what somebody does there lands in
`~/.config/omapad/layout.toml` and is applied over this. Four rules keep the
two from breaking each other:

1. A tile taken off the pad is off **only while the config still has it**.
2. A tile another page was given is **on that page and off this one**, and
   only the page holding it says so - so the two can never disagree.
3. A tile you add here **always appears**, at the end of the page, even for
   somebody who rearranged it a year ago.
4. A tile you remove here is **dropped from their saved order**, silently.

So changing this file is safe, and the only thing to keep in mind is that a
tile you add lands at the end of an arranged page rather than where you wrote
it. `omapad check --layout` says what a saved arrangement still resolves to,
which page is holding what, and which references no longer name anything.

Two more things a person can do. **Put a tile in a cell**, which is stronger
than the rules above: a pinned tile is out of the flow entirely, so the order
you write here decides only where the tiles *around* it go. That is the one
case where the page somebody sees can have gaps the page you wrote does not -
and it is their gap, so leave it alone. And **move a tile to another page
entirely**: X takes it off into the strip along the foot of the card, the
shoulders walk to another page, and A puts it there. So the page a row is
written on is where it *ships*, not where it will be found - which is one
more reason to place a row by how often a thumb reaches for it rather than
by category, and no reason at all to write the same row on two pages.

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

**A page is bands, and a band comes to twelve.** The card is `[menu] columns`
wide whatever is on it, so a page whose tiles come to eight columns is a page
with a third of itself blank - which reads as a drawing fault rather than as
air. Add the spans up before you write them: every shipped page but one is a
whole number of rows of twelve, and the spans are what gets adjusted to make
it so. A tile is widened to the width of what it is under, not to fill a hole
with nothing in it - `Previous` is four cells because the row is three verbs
under a media tile, and it says its whole name at four.

Two things that will not bend for the arithmetic. **A circle is two by two** -
the knob, the dial, the clock and the stopwatch are one drawing at one size,
and a page that holds two of them at two sizes reads as a fault. And **a span
is never wider than six**: `build` refuses one wider than the columns there
are, `[menu] columns` is a setting somebody may turn down, and six is the
width below which there is nowhere to put a bar.

So a band of two-row tiles takes its squares with it, and a band of one-row
tiles is bars and verbs. Mixing the two heights in one band is what leaves a
row with a hole at one end and a tile hanging under it.

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
Nothing in the shipped tree spends a key. Play / pause on `Sound` is the worked
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
