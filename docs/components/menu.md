# Menu - `omapad/menu.py` + `shell-plugin/Menu.qml`

The controller HUD: a head, a bar of groups, a grid of tiles, and the payload
they are drawn from.

Shaped like the Omarchy menu once - one column of rows, a title line, submenus
you drill into - and that was right while every row was a verb. A list says
every row is worth the same; a grid says what is worth looking at, which is the
whole difference between a menu and the panel a console opens over a game. So
the top level is a **bar** of places, and the tiles of the group you are on
fill the card under it.

What it cost is the card's width: the Omarchy menu's 320 has nowhere to put six
columns, and that is the one measurement this surface no longer shares with it.

## The state machine

Nine behaviours share four face buttons, two sticks, two triggers and two
shoulders. Each is sensible alone; together they collide, so what each press
means in each state is written here rather than inferred from the code.

**The state.** Every field is orthogonal:

```
open      False | True
group     which chip
depth     0 = the group's tiles; >=1 = drilled into a submenu
selected  a tile id, never an index
taken     None | id     the control being adjusted
edit      False | True  the page is being rearranged
picked    None | id     the tile being carried
```

`taken` is an id like `selected`, and it is only ever the tile `selected`
names. It is cleared by every page change (`_show`) and by every selection
move, so there is no way to walk away still holding one. `picked` is the same
for the tile being carried.

**`taken` and `picked` are never both set.** Entering edit lets go of a
control, and a control cannot be taken while a page is being edited - both are
things you are in the middle of, and you cannot be in the middle of two.

**Identity is an id, never an index.** A tile changing size re-packs the page
under it, so an index is stale the moment it is used. `selected` is a name in
the model and a name in the payload; `MenuModel.index` exists only because a
pointer names a tile by where it is on screen, and nothing decides anything
from it.

**The transition table.** A blank cell is a press that does nothing.

| | browse | taken | edit | edit + picked |
|---|---|---|---|---|
| D-pad left/right | move the selection to the tile that way | adjust it, faster the longer it is held | move the selection | carry it one place |
| D-pad up/down | the same | - | the same | carry it a row |
| **Left stick** | the same as the D-pad, held rather than flicked | the same | the same | the same |
| **ZL / ZR**, as axes | sweep the tile in front, if it has a range | sweep it | - | - |
| **A**, Enter, Space | fire it, drill in, or **take** a control | let go, keeping the value | **pick up** | **put down** |
| **B**, Backspace | up one level; at depth 0 the menu closes | let go, **putting the value back** | leave edit, and save | leave edit, and save |
| **X**, Escape | close outright, from any depth - or the page's own verb | close | hide it, or put it back | hide it |
| **Y** | the bindings guide - or what the page reaches for | the guide | reset the page | reset the page |
| **L / R**, Tab | previous / next group | - | - | narrower / wider |

`bindings.md`'s word for A is **commit**, and it stays that. What the table
adds is which sentence commit is speaking in each state: fire it, drill in,
take it, keep it.

**A and B do not mean the same thing on a held control.** A keeps what it is
on, which is also the moment it is written down; B puts it back where it was,
which is what leave means in every other place on this pad. Two words, not one
said twice - `bindings.md` rule 4 holds here as everywhere.

**The triggers are read as axes, not bound.** `bindings.md` says of ZL that a
layer trigger has no binding of its own, in any layer or profile, and this
gives it none: a surface layer falls through to nothing, so both triggers are
free while the menu is up, and how far one is pulled is a question no binding
could have asked. It works in `browse` as well as in `taken`, which is the
point of it - a trigger needs no mode at all.

**Left and right are not a second way to say Back and Pick.** They were, while
this was one column and both were free to be. A grid spends both axes on
getting about, and A and B already say the other two things.

## The tree

`build(entries, where, columns)` normalises `[[menu.items]]` into a tree.
**Actions are parsed here, not when a tile is picked**, so a typo surfaces in
`omapad check` instead of doing nothing at the press. An entry needs a `label`,
and may have either an `action` or nested `items` - never both. `MenuError`
says which. A tile that carries `from` is the one place the two meet: the
action is the template its listed tiles run.

Entries use the same action grammar as a button binding, so the menu reaches
anything a button can.

### What a tile carries

| Key | Is |
|---|---|
| `label` | required, and the tile's name unless `id` says otherwise |
| `icon`, `detail` | what is drawn above and under it |
| `action` **xor** `items` | what it does, or what it opens |
| `from` + `empty` | a page it lists rather than holds |
| `repeat`, `stay` | what happens when it runs |
| `when` | the states it is offered in |
| `id` | what a layout calls it - a slug of the label by default |
| `span` | `[width, height]` in cells; `[1, 1]` unless said |
| `control` | what kind of tile it is; empty is a plain one |
| `reads` | where a control takes its value from, `pad:<setting>` |
| `open_on` | the menu opens on this tile while its `when` holds |

`id` is unique per page: two tiles that would answer to the same name fail
`omapad check` rather than one of them becoming unreachable.

`control` is the word, **not `kind`**: `kind` already means a badge shape on
`guide.sock` and `gamebar.sock`, and a third meaning for it is the drift
[`naming.md`](../conventions/naming.md) exists to stop. The payload field is
`k`, which was free here. `CONTROLS` is a closed list, and a name on it owes
generated art where it needs art, a QML delegate, a documented payload,
validation that fails `omapad check`, and a test - a control that can be added
by touching one file is one that can ship half-drawn.

## The bar

The top level is the chips. A row there is a **place**, not a verb - though a
config that puts a verb there still has somewhere to draw it, as a page of one.

`build_groups()` filters the top level twice: a group whose own `when` is unmet
is not offered, and neither is one whose every tile is unmet, because a chip
that opens an empty page says the menu has somewhere to go and then does not.

`group_move(step)` **wraps** - it is a short strip, not a page of tiles, so
there is no edge to be lost at and walking off one end is how you reach the
other. `enter_group(n)` resets the stack: the bar is not a level to climb to,
which is also why `back()` at depth 0 hands back False and the daemon closes
the menu there.

**`root` is not a group.** Three things are easy to conflate here:

```
root     the bar plus the current group's tiles - not a level, never stacked
depth 0  a group's tiles, bar live
depth 1+ drilled into a submenu, bar drawn but dimmed
```

The bar stays drawn and stays on its chip at depth 1 and beyond, dimmed, and
the shoulders do nothing there: a bar that vanished would resize the card under
a thumb that is aiming at a tile.

### The tile that used to be at the top level

`open_on` is what answers item 48's argument - *a row you have to go and find
is a row that is not there* - now that the bar holds no verbs. It is valid only
beside a `when`, because only a tile that is sometimes offered has anything to
be nearer about, and `open_at()` opens the menu **on** the first tile claiming
it whose condition holds. Earliest wins. Over a game the workspace lock is the
selected tile of the selected group with nothing at all to walk to, which is
nearer than a top-level row in a list of ten ever was.

### What a page spends

A group or a submenu tile may carry a `keys` table, and while it is the page in
front those buttons do what it says:

```toml
[menu.items.keys]
Y = { tap = "exec:omarchy-menu toggle apps", short = "All" }
```

**X and Y only**, and the parser is what says so: `PAGE_KEYS` is those two, and
`A` or `B` in the table fails `omapad check` naming the page. A commits and B
leaves in every layer and every surface, and a page that could take either
would be the one place on the pad where that stopped being true. X and Y are
exactly the pair the contract leaves free.

**A page taking X keeps `menu:close` on the hold** (`KEEPS_ON_HOLD`), because X
is how you leave from everywhere else here. That is
[`../conventions/bindings.md`](../conventions/bindings.md) rule 2 applied one
surface along, and `omapad check` enforces it.

The specs are held **as written** rather than built into bindings: turning a
spec into a `Binding` needs how long an announced hold counts for, which is a
setting this module has no business reading. They are parsed all the same, so a
nonsense one fails `omapad check` rather than a press.

`page_keys()` answers what the page in front spends, and `page_name()` names
that page for anything caching per page - `daemon.page_key_binding` does,
because what a page spends never changes but which page is in front does.

Nothing in the shipped tree spends a key. That is the answer rather than an
omission: an override earns a button only when what it would do is not
reachable on screen, and a page of tiles almost always has room for one more
tile.

## Tiles that hold a value

A tile with a `control` is not a verb. It reads a setting, draws what that
setting is on, and acts on it:

```toml
[[menu.items.items]]
label = "Vibration"
control = "toggle"
reads = "pad:rumble"
```

`CONTROL_KINDS` is which control a setting may be drawn as, by the kind of
thing it holds - a `toggle` reads a `bool`, a `choice` reads a `choice`, a
`slider` reads a `number`, a `media` reads a `media` and a `readout` reads a
`reading`. A switch pointed at a number is a tile that could never draw
itself, so it fails `omapad check` rather than the sofa. `READERS` is where a
value may come from; there are three: `pad:` is omapad's own settings, `live:`
is what the desktop is doing - see [`live.md`](live.md) - and `sys:` is what
the machine underneath is publishing, see [`hud.md`](hud.md). Each has its own
table and `_reads` picks by source, and **all three tables are passed into
`build()` rather than imported**, so this module stays the thing that holds
state and geometry and nothing else.

**A `readout` is the one control that is not a control.** What the machine is
doing is published rather than set - a temperature is not a setting - so the
tile commits to nothing and A on it does nothing rather than finding something
to do. It is not in `TAKEABLE` either, because there is no range to push. The
same tile is drawn by `Hud.qml` over whatever is playing, which is the other
half of [`hud.md`](hud.md): one page, two surfaces.

`build()` hands both down its own recursion. It did not, once, and since every
control tile in the shipped tree lives a level down that meant the check above
was running on nothing at all - found by writing a slider onto a switch and
watching `omapad check` call the configuration fine.

A control needs neither an `action` nor `items` - it acts on what it reads -
and it cannot `repeat`: the press is the whole of it, so there is nothing to
hold down. `stay` is forced, because being thrown out to see what a press did
is how you open the menu twice.

### What a press does, and what needs taking

`TAKEABLE` is the split. A switch has two states and a choice is a short list,
so **A acts**: it flips the one and walks the other forward, and there is
nothing to enter. Taking a two-state control in order to then push it sideways
is a mode nobody needed.

A control with a **range** is the other half, and it is why `taken` exists at
all: a grid spends both axes on getting about, so a tile the selection is only
passing over cannot also own left and right. **A takes it**, and while it is
held the two axes are the tile's.

### Moving a control with a range

Two ways to the same set of numbers, for two different presses:

- **The D-pad**, once taken, is how you land on the number you meant. One step
  per push, growing to `[menu] ramp` after `[menu] ramp_ms` of holding a
  direction - shaped like `scroll_ramp`, and a reversal starts it again for
  the same reason: somebody who has gone too far is not asking for the speed
  they overshot at.
- **Either trigger**, taken or not, is how you cross the distance to it. A
  pull is a rate rather than a repeat: fully in crosses the whole range in
  `[menu] sweep_ms`, half in takes twice as long. The two pull against each
  other, so both in is still.

The sweep moves in **whole steps** of the setting's own `step`, so a value a
trigger swept to is one the D-pad could have landed on. Two ways to one set of
numbers, not two sets.

`pointer_speed` is thirty-eight steps end to end, which is what makes both of
these load-bearing rather than a flourish: a slider stepping once per press
would be worse than the two rows it replaced.

### When a push is over, and what that costs

`menu_settle` runs every tick while the menu is open rather than hanging off a
release, because there are four ways to stop pushing - the direction let go,
the trigger let go, the tile deselected, the menu closed - and a hum that
survived any one of them is [`rumble.md`](rumble.md)'s tick that sticks on. It
counts down `MENU_SCRUB_HOLD` off the same `dt` the sweep integrates over, so
there is one clock rather than two that can disagree.

Nothing is saved or announced **until it settles**. A slider is one decision
made over a second, not thirty: writing `settings.toml` per step is thirty
chances to be interrupted halfway, `apply_setting` per step re-uploads the
whole haptic vocabulary for a level nobody stopped on, and a notification per
step is the screen saying twice what the tile already says once.

**A cancel leaves no trace.** B restores the value *and* takes the setting back
out of `config.chosen` if it was not there before - writing a shipped default
into `settings.toml` would freeze it, and the user would stop receiving the
default that changes later - see
[`../conventions/data.md`](../conventions/data.md).
So a cancelled push writes nothing at all.

### A gauge, and the one thing on this surface that streams

`Controller > Sticks` was four blind stepping rows: change a number, then go
and find out. A gauge is a dial per stick showing **where the thumb actually
is**, with the dead zone drawn at the radius that swallows it.

```toml
label = "Left stick"
control = "gauge"
reads = "pad:left_deadzone"     # the number, as a shaded disc
shows = "left"                  # the thumb, which is no setting at all
```

`shows` is what makes it the only control that draws two things: one that a
config file holds, and one that no config file could.

**The rule: the menu streams only while a gauge carrying `shows` is the tile
in front, and only while the menu is open.** The *tile's* kind decides, not the
surface's - `MenuModel.watching()` is the whole question - so a menu open on a
page of buttons costs the loop nothing at all. Measured on the machine: about
1.5% of a core while a dial is selected and a hand is resting on the pad, and
a quarter of that otherwise.

### Two pushes, and why the second one costs nothing

- `push_menu_view()` - the whole surface, including `items`. Unchanged.
- `push_menu_live()` - `{open, sel, g, live: {x, y}}` and **no `items` key at
  all**.

The panel's `applyState` gets past its own "same line as last time" guard,
finds `s.items === undefined`, and so never reaches `fresh()` - the model is
not reassigned and **no delegate is rebuilt**. One binding re-runs instead of
twenty tiles being built, sixty times a second. This is not a new rule:
[`../conventions/qml.md`](../conventions/qml.md) §5.4 already says the panel
decides a line says nothing new, and this is the daemon declining to send what
it knows has not changed. [`viewsock.md`](viewsock.md)'s *every push is the
whole surface* gains its one exception, safe because the heartbeat still
carries the whole thing.

`sel` rides along **on purpose**: the stream has to be meaningful on its own,
so the panel never has to correlate two of them to know which gauge these
floats belong to.

**The floats are quantised in the daemon**, `round(x, 3)`, and not as a noise
filter: it is what makes the guard work, so a thumb resting off the stick stops
the stream entirely rather than pushing ADC jitter at a screen nothing is
moving on. The daemon compares the quantised frame to the last one it sent and
declines the repeat.

**The dead zone rides on the *full* push**, as `z`, not on the stream: it is a
setting, it changes only when something presses, and sending it sixty times a
second would say the same thing sixty times. That is one field the plan put in
the stream and the code does not.

**Nothing in `Menu.qml` may bind a layout width or height to `root.live`.** A
layout pass at frame rate throws away everything this buys. It is written at
the top of the property and `tests/test_shell_plugin.py` fails on it.

**Measured, not assumed.** `tests/test_shell_plugin.py` reads QML as text and
cannot see a delegate being built, so this was checked on screen with a
creation counter in the tile delegate, across five things that happen to a
page. Only one of them rebuilds anything:

| | delegates built |
|---|---|
| three seconds of streaming, forty lines | **none** |
| the selection moving to another tile | **none** |
| entering edit mode with nothing hidden | **none** |
| hiding a tile | the page |
| walking to another chip | the page |

The last two are right: the page is a different list of tiles, so the model is
a different model. The first three are `fresh()` doing its job - a live line
never reaches it, and a full push whose `items` are unchanged is dropped
before it does.

`push_menu_live` reads `self.axes` **raw, before the response curve** - the
same choice `check_flick` makes, because this asks where the thumb is rather
than how fast to move a pointer.

## A card, or the screen

`[menu] fullscreen` decides which, and the daemon stamps it on the payload as
`full` - menu-only, so it goes in `push_menu_view` rather than in `scaled()`,
and not in the model, which reads no config.

**A card reads as a menu and a whole screen reads as a page** - the difference
between *I am picking a thing* and *I am in the panel*. Across a room the
second one is what a HUD is for, so it ships fullscreen; `false` gives back
the centred card, which is the better shape at a desk.

Fullscreen changes four things, and each is the same argument:

- The card fills the panel and draws **no fill, no border and no radius**. The
  scrim behind is what there is, and a panel painted over it would be the same
  rectangle twice.
- **The tiles carry their own ground.** The six percent that reads as a tile
  against an opaque card reads as nothing at all against a desktop; with no
  page behind them the tiles are the only thing there is. The chips get the
  same, for the same reason.
- `contentMargin` grows. With a card's padding the first tile sits against the
  edge of the screen, which on a television is the part of it that is not
  there.
- `gridHeight` stops capping at a little over half the screen and takes
  whatever the head, the bar and the legend leave. That cap existed *because*
  a card that swallowed the screen would read as a page, which is what this
  asks for.

- **The legend moves into the game bar's own band.** Not the bottom right
  corner: the same four words about the same four buttons must not move when
  the menu opens, and a row that jumped an inch up the screen would read as a
  different row. So it takes the bar's height (`barh` on the payload, which
  is `[gamebar] height`) and the bar's edge padding, and sits flush at the
  foot - whether or not the bar is actually up, because "where the bar would
  be" is the answer either way. On a card it stays centred under the tiles,
  because a card's foot is its middle. It also takes the bar's colours:
  `LegendBadge` draws its buttons in `Color.bar.text` at the bar's resting
  fills, and the words beside them at the bar's own weight, so the row that
  answers the menu is the row the bar answered before it - in geometry and
  in colour.
- The grid takes the space above it whether or not it fills it: a legend that
  floated up under a short page would not be at the foot of anything.
- **The bars underneath are covered.** `exclusionMode` stops asking for what
  is left once every bar has taken its strip: a fullscreen HUD prints its own
  row of hints, so there is nothing down there worth leaving room for, and a
  screen with a strip cut off it is not fullscreen. The menu is on
  `WlrLayer.Overlay` and both bars are on `Top`, so covering them is a size
  rather than a fight.

**What it costs:** anything not on a tile - the head's clock and weather, the
title, the legend's words - is read against whatever is behind the menu. Two
things answer that, and both are settings.

## What is behind, and how much of it

`[menu] dim` is how dark the screen behind goes, over whatever the theme's own
scrim already does. It is drawn in `Color.menu.background` rather than in
black: darkening a themed surface towards something that is not in the theme
is how a warm palette goes grey.

`[ui] blur` asks the **compositor** to blur behind omapad's own surfaces -
`hl.layer_rule` on the `omapad-.*` namespace, sent once at start over the same
IPC socket the `hypr:` actions use. That is the only place in this program
that writes to Hyprland's configuration, and it writes about windows this
program owns: asking for a blur behind your own panel is not reaching into
somebody's setup, and nothing here touches a global.

**It is a request, not a promise.** Hyprland blurs only where blur is on at
all, so on a desktop with `decoration.blur.enabled = false` the rule is a
no-op and `[menu] dim` is the whole of the contrast. Turning blur on globally
is the person's call, not ours - it changes every window on the machine.

### The bar goes first

A fullscreen HUD covers the strip the game bar stands in and prints the same
four buttons in that exact band, so `apply_gamebar()` takes the bar down while
the menu is up - **before** the menu is pushed, never after. Two rows of words
crossfading in one place is what reads as a flicker when the menu opens, and
the order is what stops it.

A card leaves the strip alone, so the bar stays and keeps answering for the
screen around it - which is what `bar` on the payload has always been about.

## Where it opens

**It comes back where it was.** `where()` names the chip and the tile as ids,
the daemon remembers them across a close, and `reset(where)` goes there. Most
of what a HUD is for is coming back: you turn the volume down, you go back to
the game, and you come back to turn it down again - a menu that started at the
top every time would make you walk there every time.

The tile it remembers is the one at the **bottom of the stack**, not the one
in front: coming back inside a submenu you had drilled into would be coming
back somewhere you did not leave from.

With nowhere to come back to - the first press of a session, or a chip that
has gone away since - a tile carrying `open_on` gets to say where it starts,
and otherwise it is **the first tile of the first chip**.

**Nothing in the shipped tree carries `open_on` any more.** It was item 48's
answer - the workspace lock, near enough to reach over a game - and coming
back where you were is the better one: use the tile once and it is what the
next press opens on, at no cost to any other page. A tile that overrode where
you left off would take that away. The key is still there for anyone who
wants the other behaviour.

## The title, and when there is one

At the top level there is none. The bar of chips is already saying where you
are, in the same words and an inch below; a line above it saying `Go…` is the
card telling you twice. Drilled in, the bar is dimmed on the chip you came
from and the title is the only thing naming the page - so that is where it
appears, and `headerSpace` is zero everywhere else so nothing is left holding
its place.

## Rearranging a page

The tiles are the person's, not the config's. **Hold Y** on any page and every
button on the card means something else; the legend along the foot says which,
which is what makes the mode findable at all.

### The gesture, as a table rather than a branch

`EDIT_KEYS` in `daemon.py` is six ordinary binding specs, and `binding_for`
consults it before the page's own keys and before the layer's. **The legend is
built from exactly those specs**, so what it prints and what a press does
cannot drift apart - which is the whole reason the legend is worth having.

The contract holds: A still commits (picking a tile up and putting it down is
what commit is saying here), B still leaves (leaving edit mode is leaving), X
is this surface's own verb one mode along (`close` becomes `hide`), and Y is
still the reach - for the arrangement that is not on screen because it is the
one the config shipped.

**L and R are the only controls taken from anything.** They walk the bar
everywhere else in this layer, and while a page is being rearranged the bar is
not what a thumb is aiming at. Nothing is taken from ZL or ZR: a height is a
control's own shape - a bar is a bar and a dial is round - so what a person
overrides is how much room *across* a tile gets, and that is two buttons
rather than four.

The cost of putting edit on Y's hold is that **Y acts on the way back up**
rather than on the way down, the way every tap/hold does. HOME already has
that beat in this layer.

### Moving is a cell, and it used to be a place in the order

`carry(direction)` puts the carried tile in the next cell that way, writes it
to `plan["at"]`, and `place()` packs again.

**It was a reorder for a long time, and the argument for that was good.**
First fit always produces a valid packing, so a tile could only ever land
somewhere real, and a layout written as names survives a different column
count, a new tile and another screen. What an order cannot express is an
**empty cell**: with one tile on a page there is nothing to be third in, so
there was no gesture that put it anywhere but the top left - and the page the
HUD draws is one whose whole content is where it sits. Item 52 in the roadmap
is the reversal and why.

`place()` is therefore two passes, and the order of them is the design:

1. **The pins.** Every tile with a cell in `plan["at"]` claims it, clamped to
   the page - `x` is pulled back to `columns - width`, a collision hands the
   later tile to the flow.
2. **The flow.** Everything else first fits, in the arranged order, around
   what pass one took.

Pins first, or a flowed tile would take the cell one was put in and where a
tile ended up would depend on what else happened to be on the page.

**A pin does not reorder anything**, and that is what keeps the old gesture's
job done: carrying a tile left into the middle of a row pins it there and the
rest of the row closes up behind it, because the flow runs after. So the order
is still names, and it is still what holds every tile nobody has moved.

**Clamping is the whole of what the cell costs.** A pin off the edge of a
narrower screen is pulled back onto it rather than lost, which keeps the
property the reorder rule actually wanted: a page is always a packing, never a
pile. `omapad check --layout` prints the cells and says which ones would be
clamped, because clamping is silent by design.

Three refusals, each an edge the motor answers:

- the sides and the top of the page;
- **the bottom, and what that is depends on the page.** `page_rows` maps a
  page id to its last row, and `rows_limit()` is what asks. A page that is
  also drawn somewhere with a bottom edge - the HUD is the whole screen - has
  one, and a tile stops on it; every other page has none and grows a row at a
  time, which is the only way to reach an empty cell below everything and is
  bounded so a held direction cannot fling a tile somewhere a thumb has to
  walk all the way back from.

  The limit is applied when the page is **placed** as well, not only when a
  tile is carried, so what the menu draws while somebody is arranging is what
  the other surface will draw. Without the bound a tile could be carried past
  the end of a page it is only half the surface for, and `place` would pull it
  back onto the last row - onto whatever was already pinned there, which costs
  it the cell and drops it into the flow;
- **a cell another *pinned* tile is in.** It would lose that cell in pass one
  and be handed to the flow, which is a press that goes somewhere nobody
  pointed at. An unpinned tile is walked *through* rather than into, because
  that one flows out of the way - `_room` is the two halves of that one rule.

`pinned_cell(item, plan)` is **one function, one authority**, the way
`effective_span` is: a pin is the only thing that takes a tile out of the
flow, so nothing else may ask whether one was placed.

**The grid has to follow the tile being carried, and nearly did not.**
`Menu.qml`'s `reveal` is guarded so it does not scroll on every arriving line
- the heartbeat brings two a second, and scrolling to where the selection
already is costs an animation nobody asked for. The guard was the selection's
*id*, and carrying a tile is the one gesture on this surface that moves a tile
without changing the selection: the guard fired, the view stood still, and the
tile walked off the bottom of the visible grid while the button was still
being pressed. The key is the id **and the cell** now. A guard on identity
where the question was position - the same shape of mistake as an index for a
tile id, one surface along, and `tests/test_shell_plugin.py` is what says so.

### Hiding, and why there is no add page

While editing, a hidden tile is **still drawn where it sits**, faded. So
removing and restoring are the same press on the same tile: there is no page
it has gone to, nothing to go and find, and no second surface to build. It
disappears when editing stops.

### The arrangement, and the tree

`MenuModel.layout` is the arrangement page by page, and **the tree is never
mutated**: `_show` keeps the page as the config holds it in `source` and
`arrange()` produces `items` from it. So a page reads the same whether it was
just rearranged or just walked back into, and the config's own order is still
there for Y to reset to.

`arrange(items, plan, editing)` is the merge, as three deterministic rules -
this is where a saved arrangement and a changed config meet, and it is not
allowed to be something anybody has to interpret:

1. `hidden` suppresses **only ids the config still has**, so it can never hide
   something that did not exist when it was written.
2. Every tile in neither list is **appended**, in config order, so a newly
   shipped tile always appears.
3. An id in `order` that no longer resolves is **dropped**, so editing
   `config.toml` can never break a saved layout.

A `row_break` is authored rather than arranged and keeps the slot it was
written in: it is the page's paragraph mark, and a tile moved past it crosses
into the next paragraph.

`effective_span(item, plan)` is **one function, one authority** - the config's
`span` is the tile's intrinsic size and the layout's is the person's override,
and nothing else in the daemon or the panel may ask which applies.

### Where it is written

`~/.config/omapad/layout.toml`, the third program-written file, keyed by page
id. Separate from `settings.toml` because that one is scalars and this one is
structure: a layout that will not parse must not take the settings down with
it. See [`../conventions/data.md`](../conventions/data.md) for how it is read,
and `omapad check --layout` for what a saved one still resolves to.

Four parts per page, and `read_layout` reads each one on its own so a mistake
in one costs only that one:

```toml
[layout.hud]
order = ["processor", "memory", "disk"]   # the flow, in names
hidden = ["fan"]

[layout.hud.span]
processor = [3, 1]                        # cells across, cells down

[layout.hud.at]
memory = [3, 3]                           # the cell somebody put it in
```

`at` is the only part whose meaning depends on how wide the page is drawn, so
it is the only part `read_layout` does not fully validate: a negative cell is
dropped and a far-right one is kept, because `place` is what knows the column
count and clamps.

Written when edit mode is left, which is what B means there: the arrangement
you walked away from is the one kept. Inline rather than on the worker thread,
because it is a few hundred bytes written whole and moved into place - the
same work `save_settings` already does on every press of a setting row.

### The sticks

A stick role of its own, **`menu`**, and `config.stick_roles()` gains a branch
for `layer_name == "menu"`: every other implicit surface layer keeps the base
roles - the pointer still works under the keyboard - and this one does not,
because it is the one with something for a thumb to do. Shipped as
`[menu] left_stick = "menu"`, `right_stick = "cursor"`, so the promise that
the pointer stays live under the open card is kept by the thumb that was
aiming with it anyway.

`check_menu_stick(stick, dt)` is modelled on `check_focus_stick`, not on
`check_flick`: this is a direction *held*, because walking a grid is a thing
you do several of in a row. Per Phase 0's table, on an untaken tile it moves
the selection and on a taken one it moves the value - the one place the stick
and the D-pad have to agree exactly, which they do by both going through
`menu_command`.

**Analogue input arrives only here, and that is the point.** The grid and the
controls are fully verifiable with a D-pad, so a stick problem can never be
confused with a navigation or a stepping problem.

### What the motor says

`edge` on the step that first finds the end of the travel, once per arrival: a
wall you are still pushing against is still one wall. `commit` on taking and
on letting go. And `texture` - one continuous effect - while the value is
actually moving, rather than a tick per step: `[snap] rumble`'s rule is that a
step repeating under a held button would buzz all the way down a list, and a
slider is that list with the numbers showing. The texture ships off; see
[`rumble.md`](rumble.md).

### What the daemon answers

`view_state`'s `control` callback is the other half: `menu.py` holds state and
geometry, and what a setting holds is the config's. `daemon.menu_control(item)`
returns the fields to merge - `on` for a switch, `t` for a choice, `v` and `t`
for a slider, `l`/`d`/`on` for a media tile - and `menu_activate(item)` is the
press. **`v` is normalised in the daemon**, so the panel never sees a `min` or
a `max` and cannot get the arithmetic wrong; `t` is the real number in the
unit the setting is counted in. A setting that has gone away under an edited
config draws bare and logs; it does not take the menu down.

A choice prints the word it is **called**, not the word it is stored as:
`CHOSEN` carries a `words` map beside the choices it describes, so
`playstation` reaches a tile as `PlayStation`. Beside the choices rather than
in a table of its own - a second place to say what a value is called is a
second place for it to be wrong - and a value with no word prints itself,
which is right for the ones that are already words.

### What a choice tile costs

It shows one value, so it has nowhere to put the line each row of a tick
submenu carried saying **how the choices differ**. That is a real loss, and it
is what decides which submenus convert: `Button style` and `Start in` have two
values whose names say the difference, and `Button labels` and `Profile` keep
their submenus because getting either wrong scrambles the face buttons and the
sentence under each choice is what stops you. See
[`../conventions/writing.md`](../conventions/writing.md).

## The legend

The strip along the foot of the card prints what each face button does **on
this page**, in the contract's own order - A, B, X, Y - so the strip teaches it
every time it is glanced at.

The daemon resolves it, through `guide.button_row(..., brief=True)`: the guide
already turns a binding into words and the bar already reads them short, so
this is the same pair one surface along rather than a third opinion. It reads
the **page's** spec where there is one and the layer's otherwise - the same
place a press reads, so the legend cannot be a second answer to what a button
does.

`[menu] keys` turns it off. In game mode omapad's own bar is already along an
edge saying the same kind of thing, and somebody running that may not want it
said twice; the two are not the same answer in general, though, because only
this one is page-scoped.

## The grid

Two pure functions, no I/O, testable against a canned page - the shape
[`snap.md`](snap.md) is already written in.

**`place(items, columns, plan)`** claims the cells somebody put tiles in, then
packs everything else first-fit around them, in the order the page holds them.
The order is authorial - `pad-menu.md` places a tile by how often a thumb
reaches for it - so the flow keeps it, and a small tile is allowed to backfill
the hole a big one left rather than the order being rewritten to avoid holes.
Deterministic either way, which is what lets a page that nobody has rearranged
be a list of names and a page somebody has still be a valid packing. It
returns tiles shaped `{item, at, size}` - `at` and `size` named for what
`snap.rect` reads. See *Moving is a cell* above for the two passes and why a
pin is clamped.

A **`row_break`** tile ends the row it is in and draws nothing. Not a one-cell
spacer: a spacer holds a hole open at one column count and shifts everything
under it at another, and the same page has to read on a laptop panel and on a
television.

**`step(direction)`** is `snap.choose()`, unchanged. It already answers "which
rectangle is that way from here?" for the windows a flick lands on, and a tile
is a rectangle in cells - so the pad walks a page by the same rule it walks a
desktop, rather than by two that can disagree. Nothing that way leaves the
selection where it is: a grid that wrapped would put the cursor at the far side
of a page a thumb was pushing away from, which in two dimensions is losing it.

`[menu] bias` is its own number rather than `[snap] bias`, and it is measured
rather than inherited: windows are large and sparse, tiles are small and
touching, and `tests/test_menu.py`'s golden fixtures are what it was set from.

## The head

`build_head(entries)` is the read-only grid above the bar. **Nothing on it is
selectable** - a clock is not a button, and a cursor that can wander into one
is a cursor that has to come back out again.

A cell prints either a `format`, which is strftime and rendered in the model,
or the last thing a command said, which the daemon supplies. `ttl` is how long
that answer stays fresh, and **it is not the heartbeat**: the surface redraws
every couple of seconds and the weather is asked for every quarter of an hour.

A `format` cell may also carry `under`, a second format rendered the same way
and sent as the cell's `u`; a cell without one sends no `u` at all, so
`u !== undefined` is the whole of the panel's test for whether it stacks. It
is one cell holding two lines rather than two cells because `place()` packs
the head first fit - nothing here can promise the cell holding the day lands
under the cell holding the time rather than beside it. Under a `from` it is
refused: a second line under a command's answer would be a second command,
with its own `ttl` and its own failure to word.

**The cell's height is what decides its treatment**, not a key saying so. Two
rows and the panel sets the first line at the top of the ladder
(`metrics.type.vast`) and the line under it small and in capitals; one row and
it is a line of text at `metrics.type.lead`. Which is why the shipped clock is
`span = [2, 2]` - a cell one row tall has nowhere to put a headline, and a
cell that asked for one anyway would clip. The capitals are the panel's
decision and not the config's: `%A` returns whatever the locale's own weekday
is, and casing it is typography.

`from` + `ttl` is not new - it is what a `[profile.<app>.osk]` page already
uses, one surface along - but the two share syntax and validation, not
internals: a submenu source turns lines into selectable tiles, a head source
turns output into one drawn string.

**Why the weather is here at all**, when `roadmap.md` refused it. It was
refused because *"putting it here means network I/O in an input daemon, with
caching, failures and a location to own"*, and none of that lands here.
`omarchy-weather-status` owns the lookup, `omarchy-weather-location` owns the
location, and the helper prints its own failure. omapad runs a string from the
config and draws what comes back; it never learns what weather is. A cell whose
command answers with nothing keeps the last answer rather than blanking - a
blank cell in a grid reads as a drawing fault rather than as a slow helper.

## Tiles that are not always there

`when` on a tile is the states it is offered in - `game`, `handed_over`,
`locked`, `kept` from `menu.WHEN`, any one of them being enough; a tile that
says nothing is always there, which is nearly all of them. `build()` rejects a
name that is not one of those, so `omapad check` says which tile would never
appear.

`daemon.menu_conditions()` reads the states **when the menu opens** and
`MenuModel.conditions` holds them until it closes: a tile that came and went
under the selection would move every tile after it while a thumb was aiming at
one.

## Tiles that list what is plugged in

A tile may **list** its page rather than hold one. `from` is a command and
`action` is the template each of its lines runs; `build()` parses that template
the way it parses any other action, so a nonsense one still fails `omapad
check`. Which audio outputs exist is not something a config file can know - the
answer changes when a television is plugged in - and a menu that can only name
what was written down cannot ask.

`listed(item, lines, limit)` turns the command's output into the tiles. One per
line, tab separated: the label, then the values the template takes as `%1` to
`%9`. A label beginning with `*` is the one in force and is ticked - the mark
`pactl` and `wpctl` already put beside the current device - and the mark is not
drawn. **Every value is quoted as it goes in**: a device names itself from its
own USB descriptor, and the action it lands in is usually a shell command.
**The label goes through `viewsock.drawable`** for the same reason on the
drawing side. A line whose action will not parse is dropped; a page with no
tiles left says so in the tile's own `empty` words rather than opening blank.

The daemon reads it at the press (`menu_fill`), not at load and not from a
cache. The command runs off the loop, so the press enters the page at once and
the tiles land in it when the answer does - and `repack()` is what places them,
because the page was packed while it was still empty. `[menu] list_timeout_ms`
is how long the worker waits before calling the listing empty, and `list_limit`
is how many lines reach the page.

Walking to a chip whose page is listed does **not** read it at once:
`[menu] group_settle_ms` is how long the bar has to stop moving first, because
flicking across five chips should spawn one command rather than five.

## `MenuModel`

`step(direction)`, `press()`, `back()`, `reset()`, `repack()`, with `depth` and
`stack` tracking the drill-down and `group`, `groups`, `group_move`,
`enter_group` tracking the bar. `select(n)` and `select_id(name)` are the two
ways in from outside: a pointer names a tile by where it is, and everything
else names it by what it is called. `clock()` renders `[menu] clock`, which the
shipped config leaves empty because the head carries the time now.

## Tiles that know the answer

`view_state(opened, state, value, head)` takes three callbacks from the daemon:

- `state(action)` answers "is this already the case?" - the tile is ticked
  (`on`). That is the whole difference between a list of choices and a list of
  guesses.
- a **listed** tile answers for itself: its `on` came from the listing that
  made it, since the daemon can ask a setting what it holds but not a device
  whether the sound is going to it.
- `value(action)` answers the other half for a tile that steps a number, and
  replaces the tile's own `detail`, which is a sentence written once and cannot
  know. Ticking cannot say it: every step of a number is equally not the case.
- `head` is what each head command last said, keyed by cell id.

## Payload - `menu.sock`

```
open, title, clock, depth, sel, g, groups, head, headrows, keys, cols, rows,
items: [ {id, l, i, d, sub, x, y, w, h, on?, k?} ]
```

`sel` is a tile **id**, not an index. `g` is which chip. `groups` is
`[{id, l, i}]`, `head` is `[{t, x, y, w, h}]`, `keys` is `[{b, k, n}]` - the
same three letters a badge takes on `gamebar.sock` - and `cols`, `rows` and
`headrows` are the grids' shapes. On a tile, `l` label, `i` icon, `d` detail,
`sub` whether it drills in, `x`/`y`/`w`/`h` its cells, and `k` its control
where it has one. A control tile adds what it is on: `on` for a switch, `t`
for the words a choice or a slider is showing, `v` for how far along a slider
is (0..1), and `hd` where it is the one being held. A media tile's `l` and `d`
are overwritten with the title and the artist. The surface carries `hd`
too, as the held tile's id or empty.

What those strings may say is
[`../conventions/writing.md`](../conventions/writing.md): a tile is read from
across a room by someone deciding whether to press it, so a `detail` says what
happens rather than why the tile exists.

## The panel

`Menu.qml`. Centred card; a head grid, a title line, a scrolling bar of chips,
and a `Flickable` of absolutely-positioned tiles. Overlay layer, `Exclusive`
keyboard focus, and the whole screen as its input region - the Omarchy menu's
own window rules. While it is open the keyboard and the pointer drive it, on
top of the pad.

**Neither scroller is interactive**, and both are settled from the root rather
than from a delegate: the selection lives in the daemon, so a drag here would
be a second answer to where you are. Both are also re-run when the geometry
changes rather than only when the state does - a delegate is laid out after it
is built, so a scroll worked out at construction is worked out against a width
of nothing, and the answer sticks. That is how a grid that fitted ended up
scrolled past its own last row with everything above it off screen.

The one departure from the Omarchy menu's rules is the game bar. `bar` in the
payload says it is up, and the window turns `ExclusionMode.Normal` on and takes
what is left of the screen rather than all of it, so the scrim stops where the
strip starts.

| Input | Job |
|---|---|
| Pad D-pad / arrows | Walk the tiles, all four ways; a hold repeats |
| A · Enter · Space | Pick; dive in, if it opens a page |
| B · Backspace | Back to the page above; at depth 0 it closes |
| Esc · X · click the scrim | Close the menu outright, from any depth |
| L / R · Tab / Shift+Tab | Previous / next group |
| Click a tile | Pick the tile it lands on |
| Hover a tile | Move the selection to it (after the cursor has travelled) |
| Click a chip | Walk the bar to it |
| Home / End | Jump to the ends of the page |

The keyboard and the mouse drive the same `MenuModel` the pad does, over the
same control socket `omapad ctl menu` uses: each key and each pointer event
sends a command and the daemon's next view line answers it. A held arrow key
auto-repeats the way a held D-pad does, so the two hands feel the same. A
stationary cursor never steals a selection the pad put somewhere on purpose:
the pointer must travel a little before hover selects.

This is the one omapad surface that takes input at all: the keyboard and the
guide stay pad-only, with an empty input region, so they never swallow a click
meant for the window under their scrims. The menu swallows them - that is what
"close on a scrim click" means - until it goes away.

## What a tile is drawn on

Every state of a tile is drawn on its **own outline**, not on one rectangle in
a different colour: a plain tile is rounded, a selected one is cut back to a
facet, and a tile being carried has a bite out of its corner. The state is
said twice - once in ink and once in the silhouette - because a theme whose
accent sits close to its surface leaves a selection to the border alone, and
the border is the thinnest thing on the tile.

The outlines are drawn art, generated from `assets/shapes/ground-*.svg` into
`shell-plugin/TileArt.qml`. A tile is `w` cells by `h` rows, though, and a
shape scaled by one factor cannot be a rectangle of any aspect - the rule the
slider's track and the dial's shaded zone are not drawn under. So a ground is
**the corner as drawing and the four edges as a number**: the same quarter set
at all four corners, rotated rather than mirrored, with straight lines run
between them. `docs/components/assets.md` is the mechanism.

How far that corner reaches into the tile is `[menu] tile_corner`, and it is
deliberately **not** `Style.cornerRadius`: that mirrors the compositor's own
`decoration:rounding`, it is 0 on plenty of setups, and at 0 every state of a
tile is the same square - which is the one thing this must not do.

A cell is `[menu] columns` wide and `[menu] cell_height` tall, and both travel
in the payload for the reason every geometry setting does: the shell cannot
read the config. A tile shorter than an icon over a label **drops the icon**
rather than pushing the label out past the ground it is drawn on - the label
is the half that says which tile this is, and `cell_height` being a setting is
what makes a tile that short reachable at all.

Settings: `[menu] title`, `clock`, `columns`, `cell_height`, `bias`, `keys`,
`tile_corner`,
`repeat_delay_ms`, `repeat_rate_ms`, `group_settle_ms`, `list_timeout_ms`,
`list_limit`, `socket`,
`[[menu.head]]`, `[[menu.items]]`, `[bindings.menu]`.
