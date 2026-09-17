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
group     which nav card
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
| **Left stick** | the same as the D-pad, held rather than flicked | the same - or, on a **knob**, its angle turns the value | the same | the same |
| **ZL / ZR**, as axes | sweep the tile in front, if it has a range | sweep it | - | shorter / taller |
| **A**, Enter, Space | fire it, drill in, or **take** a control | let go, keeping the value | **pick up** | **put down** |
| **B**, Backspace | up one level; at depth 0 the menu closes | let go, **putting the value back** | leave edit, and save | leave edit, and save |
| **X**, Escape | close outright, from any depth - or the page's own verb | close | hide it, or put it back | hide it |
| **Y** | rearrange this page - or what the page reaches for; **held**, the bindings guide | the guide | reset the page | reset the page |
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
| `icon_font` | the family that glyph is set in, where it is not the surface's own |
| `action` **xor** `items` | what it does, or what it opens |
| `from` + `empty` | a page it lists rather than holds |
| `repeat`, `stay` | what happens when it runs |
| `confirm` | it is **held**, not pressed - see below |
| `when` | the states it is offered in - `game`, `handed_over`, `locked`, `kept`, `first_run` |
| `id` | what a layout calls it - a slug of the label by default |
| `span` | `[width, height]` in cells; `[1, 1]` unless said |
| `control` | what kind of tile it is; empty is a plain one |
| `reads` | where a control takes its value from, `pad:<setting>` |
| `open_on` | the menu opens on this tile while its `when` holds |
| `meta` | a group only: the word under its name on the bar |

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

The top level is the nav cards. A row there is a **place**, not a verb -
though a config that puts a verb there still has somewhere to draw it, as a
page of one.

**A nav card is a tile that happens to be a place.** It is one cell of the
grid below it, drawn on the same ground with the same corner art, and the row
lands on the same columns the tiles do - so the surface has one module rather
than two. It was a row of words sized to the words for a long time, and a row
of words says every place is worth the same, which is the argument the grid
under it had already won. More cards than fit is what the `Flickable` is for,
and always was: the bar has scrolled to follow the current card since it held
chips.

**And it stands `huge` off the grid** - the rung two above the gap the rest of
the page's bands keep - where every other seam is one band. Being the same cell
on the same columns is what leaves the bar reading as the grid's first row at a
band's distance, which is the one thing it is not. `navGap` is only what the
`Column`'s own spacing does not cover, carried as the bar's trailing air inside
its clip; the distance that matters is the named rung, not two gaps added up,
which is a pixel out at this scale and further out at others.

**A nav card says what its place is doing.** `meta` is that line, and it
takes the same two forms a head cell's line does: a bare word printed as it
is, or a table with a `from` and a `ttl` whose command the daemon runs off the
loop while the menu is up. `empty` is what the card says when the command
prints nothing - `Quiet` where there is no music, `Up to date` where there is
no update - which is the one place a group's meta differs from a head line,
because a bar that has gone quiet has somewhere to say so.

`meta_sources` is the bar's `head_sources`: one place that knows where a meta
lives, so `menu_meta_refresh` can ask for what has gone stale without learning
the shape of a group. **A `ttl` is not optional politeness here.** A head has
two or three lines; a bar has one per group, so a card that reads a sink every
redraw is eight subprocesses a second for a row of two-word labels.

Left unset, a card falls back to how many tiles its page holds. That is a
fallback rather than an answer - it is the one fact about a group the model
can know on its own, and the least of the things worth saying up there.

**The card you are on is filled solid with the accent**, cut back to a facet,
and labelled in ink measured against that fill. It is the one fill on this
surface, and the only one that has to carry a label rather than sit under one -
everywhere else, a lit toggle included, a state is a fifth of the accent and
the theme's own ink still stands on it.
`Ink.qml` is what measures it, and `Color.menu.selectedText` is emphatically
not the answer: Omarchy defaults that key to the accent itself.

`build_groups()` filters the top level twice: a group whose own `when` is unmet
is not offered, and neither is one whose every tile is unmet, because a card
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

The bar stays drawn and stays on its card at depth 1 and beyond, dimmed, and
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

**A `knob` is the slider's twin**, and the pair is the one case on this
surface of two drawings of one control:

```toml
[[menu.items.items]]
label = "Volume"
control = "knob"
reads = "live:volume"
```

It reads what a slider reads, steps what a slider steps, is taken the way a
slider is taken and sends the same fields. What it is for is the gesture: a
slider is a length and a knob is an angle, and the stick this page is walked
with is the one thing on the pad that is already a turn - so on a held ring
the stick stops repeating a direction and carries the value round instead.
See *A ring, and the one gesture that is already a turn* below.

**It reads a list as well as a number**, which nothing else here does. A
selector with a stop per position is the oldest drawing there is of *one of
these*, and it is the half a slider has no figure for: a bar between `Filled`
and `Stencil` would be a length drawn over two words with no arithmetic
between them. `CONTROL_KINDS` is where that is written down, and it is the
only entry with two kinds in it.

**Neither of them is the better one, and the shipped page says so.** A length
is read faster and a ring is turned better, so `Volume` is a knob and
`Brightness` beside it is a bar - the page that holds both is where you find
out which you reach for. It takes the dial's square for the dial's reason.

**A `readout` is a control that is not a control.** What the machine is
doing is published rather than set - a temperature is not a setting - so the
tile commits to nothing and A on it does nothing rather than finding something
to do. It is not in `TAKEABLE` either, because there is no range to push. The
same tile is drawn by `Hud.qml` over whatever is playing, which is the other
half of [`hud.md`](hud.md): one page, two surfaces.

**A `clock` is the other one, and it goes further: it reads nothing at all.**

```toml
[[menu.items.items]]
label = "Time"
control = "clock"
```

What a clock is on is not a setting, not something the desktop is doing and
not something the kernel publishes, so there is no table to point a `reads` at
- one is refused by name, because "only a control reads something" is a
baffling thing to be told about a line that says `control = "clock"`. It is
the one tile whose value this module works out itself, and it may: `time` is
already imported for the head, and `minute_of_day()` is the whole of it.

**A face rather than a second `%H:%M`.** The head already prints the time, to
somebody who has just opened the menu and is reading words. A tile is glanced
at from across a room and over something else, and what a glance gets off two
hands is roughly when it is - which is the whole question anybody asks a clock
from a sofa. It takes the gauge's square for the gauge's reason, and the same
square: two circles on one page drawn at two sizes read as a fault rather than
as two tiles.

It is drawn by `Hud.qml` too, and that is what widened the rule over there:
what a tile needs in order to be allowed over a game is **nothing to press**,
not a reading to print. Game mode takes Omarchy's bar away, and the bar is
where the time was.

**A `chrono` is that face with a stopwatch in it**, which is what a
chronograph is:

```toml
[[menu.items.items]]
label = "Stopwatch"
control = "chrono"
```

It reads nothing either, and what it holds is a press somebody made - which no
table could have been pointed at, and which is not on its tile for the reason
the payload section below gives. The measurement itself is
[`chrono.md`](chrono.md): one stopwatch however many tiles draw one, and one
pusher because A is the only button a tile owns.

**A is a pusher on it**, and the legend under the card says which of the three
it is - `Start`, `Stop`, `Reset` - the way it already says `Hold to confirm`
for a row that has to be held. That is the same mechanism and the same
argument: this row is the page's own line about its buttons, and a button that
means something else on the tile in front is exactly what it is for.

And it is **not** drawn on the HUD, for the reason the clock beside it is: a
chronograph has a pusher, and a pusher over a game is a control with no way to
reach it.

`build()` hands both down its own recursion. It did not, once, and since every
control tile in the shipped tree lives a level down that meant the check above
was running on nothing at all - found by writing a slider onto a switch and
watching `omapad check` call the configuration fine.

A control needs neither an `action` nor `items` - it acts on what it reads -
and it cannot `repeat`: the press is the whole of it, so there is nothing to
hold down. `stay` is forced, because being thrown out to see what a press did
is how you open the menu twice.

### A card of verbs, drawn as rows

`rows` is the one control that holds no value at all. What it holds is the
page that would otherwise be a level down: its `items` are drawn **inside** it,
one to a line, and `build()` puts them in `item["rows"]` rather than
`item["items"]` so the card reads as a leaf everywhere that asks - the
payload's `sub`, the title line, and `press`.

The argument for it is width. A verb has nothing to show but its name, so a
cell spent on one says a single word, and a page of them is four words where a
sentence was meant: `Screensaver` drawn as `Screensa…` is the evidence, and
`Lock`, `Suspend`, `Logout` and `Reboot` as four identical squares is what a
scatter reads like. Stacked, each row has the card's whole width - and the
line under its name, which a tile one row tall draws nowhere at all, so the
sentence a scattered verb had to do without comes back with the card.

It is **not a submenu with the drilling taken out**. A submenu is a page you go
to and come back from and its rows get a card each; these are already in front
of you, and what buys them their length is that they are stacked.

`_rows()` is what a row may be, and it is a short list on purpose: a verb, with
no page under it and no control on it. A row that opened a page would have
nowhere to go, and every control this surface has is a card's worth of drawing
that a line of text cannot hold. A `row_break` is refused for the reason it is
a break - it ends a row of cells, and these are not cells. A card cannot
`from`-list its rows either: a listing is read at the press that enters the
page it fills, and this card is never entered. Nor does it carry an `icon`: a
tile's icon is the big mark in its top corner and a card of rows has no corner
to spare, so a glyph would land at the heading's size in front of tracked
capitals and read as a bullet. Marks belong to the rows.

**The row cursor is a second cursor, not a second kind of `selected`.**
`self.row` is an id inside `self.selected`'s tile, and everything the page does
to a tile - carry it, hide it, resize it, scroll to it, ring it - is still done
to the tile. Only a press reaches further in, and `acting` is where that is
asked: it is the row where there is one and `current` everywhere else, which is
what makes `confirm`, `stay` and `repeat` the row's answers rather than the
card's. The legend asks the same property, so `A` says `Hold to confirm` over a
row that has to be held and `Pick` over the one beside it.

**A card is entered before it is walked, and `TAKEABLE` is where that lives.**
It did not, at first: `step()` walked the rows and handed the press back to
`snap.choose` at either end, which is cheaper and looks fine until you stand on
a card with a tile underneath it. Down then means the next *row*, and the tile
below - which is what a thumb pushing down is reaching for - is two more
presses away. **One direction meaning two things depending on what it is
pointing at is a page nobody can read**, so A goes in and up and down belong to
the page until it does.

`entered` is that state, and it is `taken` narrowed: a slider takes both axes
and a card takes one, which is why left and right say nothing inside one rather
than doing a slider's job on a thing with no range. B leaves the card without
leaving the page, exactly as it leaves a slider. `step_row()` is the walk, it
does not wrap, and `menu_edge()` answers a push past either end.

Two things follow that the drawing has to say. **The row cursor is drawn only
while somebody is inside** - a card standing in the grid shows which row is in
force and no cursor at all, because a cursor would be promising a walk that
press does not make. And **an entered card is not `lifted`**: filling with the
accent and cutting its corners is what a tile *out of the page's order* does -
a tile in the hand, a slider being pushed - and a card being read is neither.
It was filled once, and it was the loudest thing on the page with the least
readable rows on it.

**What an entered card takes is the press ring**, and getting there took two
wrong answers first.

It was a **heavier ring** for a while - four pixels instead of one - and that
is the same figure drawn at two sizes, which is two focus marks rather than
one: a reader has to know the difference between a thin ring and a thick one
before either says anything. What the thick one was saying is not *where the
cursor is* but *what A is doing to this*, and the design has a mark for that
already and it is not a heavier border. A press is a **two-pixel ring inside
the edge**, so `hit` - which was drawn for `press_ms` after a press - is drawn
for as long as the press *lasts*: a control taken with both axes, a card gone
into, a tile in the hand. The vocabulary is two figures and no exceptions: a
hairline ring outside says **here**, a two-pixel ring inside says **and A has
hold of it**. Taking the ring away instead was the other wrong answer, and it
said so at once - the rail says which *row*, and a two-pixel mark on one row
is no answer at all to which *card*.

**One weight also holds the page's geometry still**, and that was the fault
under a corner that did not fit its ring. Every figure on a tile is concentric
with the ring - the halo outside it, the press ring inside it, the sheen on
its face, the sweep of a hold - and **concentric is a radius as much as a
centre**: a rounded rectangle drawn `d` pixels outside another one has to take
`d` more corner, or the two run parallel down the edges and part at the
corners, which is exactly where an eye checks whether two lines belong to one
drawing. `tile.concentric(d)` is that sum in one place, `d` measured from the
path the tile's own radius is measured on, and every figure asks it rather
than reaching for `metrics.radius.tile` and hoping. The ring changing weight
used to move all four corners at once.

Two more things the pair needs. `halo.out` is a hairline clear of the tile's
own **box** rather than of the ring: the ring is drawn *inward*, straddling a
path inset by half its weight, so it occupies the first `weight` pixels inside
the tile - a sum that was a one-pixel error while every ring was a hairline
and a four-pixel one the moment a ring was not, and the grid clipped the halo
on the leftmost tile of a page. And `hit.inset` keeps a hairline of the card's
own face between the two rings: touching, they are a three-pixel edge, which
is the thick ring this pair replaced rather than the two marks it is meant to
be.

### The spine and the ground

A row says two different things and they are often two different rows. Each
gets one mark, and which mark got which job took five passes to settle:

| | Says | Drawn as | When |
|---|---|---|---|
| `on` | this is the one in force | the row's length of the **spine**, lit, and a **stroke at each end of it**, to the right | always |
| `sel` + `row` | this is the row A would run | a faint **ground**, square down its left so it meets the spine | only while the card is entered |

**The spine** is one line down the side of the list, and it is structure rather
than state: it is what makes a stack of words read as a list rather than as
four labels that happen to be under one another. Every row draws its own
full-height segment of it and `rowStack.spacing` is 0, so the segments meet -
a single child of the `Column` cannot be the whole spine, because a `Column`
lays its children out and a child asking for the `Column`'s height is a binding
loop. The one that happened drew a line down the whole card with no rows on it.

It carries on a little **past the first row and the last one, and is capped
with a cross at both**. A line that began exactly at the first row's top edge
began nowhere: it read as the edge of the ground behind it rather than as a
thing of its own. A travel takes the same run of bare line at each end, which
is why a slider's range starts an arm inside the mark that ends its line.

**One stroke, and both drawings have only it.** The cap here, a stop on a
slider's travel and the place a value has got to are one figure: a bar of the
line's own weight crossing it, reaching the same distance either side.
`Metrics.spine.cross` is that distance for a stop - the arm stepped a rung of
the space ladder and halved - and `crossEnd` is a rung above it, for the marks
that **end** a line. The card's caps take `crossEnd` too: the end of a list and
the end of a travel are the same claim, *this is as far as it goes*, and a card
whose ends were a stop's size ended more quietly than the slider sitting beside
it on the same page.

It was a `T` with its own quantity for a while, and the quantity was wrong
twice over: a silver step *per arm* made the cap two and a half times as wide
as the line reaches - measured, 12 across against 5 along - and a cap that
out-reaches the line it caps is a cross-piece with a line through it. What
settled it was not a better number but the same number as the drawing next
door.

**A cross, not a corner.** Both caps turned right at first, which made the two
of them a bracket round the rows - and a bracket is a thing that *holds* what
is inside it, which is a claim about the rows. A cross is a stop: it says the
line ends here and nothing about what the line is next to. The two arms are the
same length, so the cap is centred on the line rather than hanging off one
face.

Both are siblings of the `Column` for the same reason the spine is not one
child of it - a child that wanted to sit above the first row would *be* the
first row.

**The arms do not cross the line**, and that is not tidiness. Every ink on this
surface is the theme's own at a share of itself, so a square painted twice is a
square painted brighter, and the pixel where the bars crossed was the brightest
thing on the card. The line takes the crossing; the arms start either side of
it. A travel's stops are drawn the same way for the same reason - and the one
stroke that *is* one piece is the value's own, which is the accent and opaque,
so it covers the line rather than tinting it twice.

**The row in force is a length of the line in the accent, with a stroke at
each end of it.** What it marks is a *state*, so all three are drawn always -
on a card nobody has selected, let alone entered - and a card of verbs shows
none, because nothing on one is in force.

The strokes are the silhouette the colour needs beside it (qml.md 8.1.1): a
theme whose accent sits close to its ink exists, and a state said once in
colour is a state that theme cannot say at all.

**They bracket the length rather than pointing at the middle of it**, which is
the truer thing to say: what is in force on a card is a *length* of line, and
these are where it starts and where it stops. They are the line's own weight
and a stop's own reach, to the right of the line and never across it, so the
card carries one figure and no exceptions - and the same reach a travel's stops
take, so the two drawings mark with one mark.

It was a **wedge in the middle** for four passes. A wedge points, and pointing
is right when the thing pointed at is beside the mark - the row is not beside
it, the row is the length behind it. It was also the one drawing on either
surface that was not a plain stroke, which is a thing to notice when the
argument for everything else is that there is one figure.

Before the wedge: a **tick at the far end of the row**, which says nothing - a
mark with no second state, at the opposite end of the card from the words it is
about. A **radio ring at the head of each row**, which says more (an empty ring
beside every row says *these are alternatives* before it says which one) and is
a second drawing for something the row can simply **be**, in the slot a row's
own glyph wants. And a **pointer**, which marked the *cursor* for a pass, drawn
dim outside the card and accent in - which reads well until you notice the
ground was saying *in force* two pixels away from it: one line, one mark, and
two different answers to which row matters. Giving the persistent mark the
persistent state and the transient mark the transient one is what made the card
readable at a glance.

**A card with no state draws no spine at all.** `Lock`, `Suspend`, `Logout`
are things that happen, and none of them is a thing the machine is currently
on - so the line that exists to carry *which row is in force* is, on a card of
verbs, a line drawn down a list for the sake of drawing one. The panel asks the
rows rather than the tile: `on` is the question, a row that has one carries it
even when the answer is no, and a card where nothing was asked is stateless.

Three things follow it out. The row takes **its own left corner back** - it was
square to meet the spine, and there is nothing to meet. The sweep and the press
ring start at the row's own edge instead of a stroke in. And the words move a
rung left: the column was held out by the line, so it comes in with it. A card
of verbs is then a list of words on a ground, which is all it ever had to be.

**The ground is the cursor**, and it needs the card to have been entered: up
and down belong to the page until A goes in, so a mark for where A would land
would be promising a walk that press does not make. Its left corners are
square, so it meets the spine instead of curving away and leaving a sliver of
card between the two - and it **starts where the spine ends** rather than under
it. Every ink here is the theme's own at a share of itself, so a line drawn
over a ground is a different line from the one drawn over the card beside it: a
spine that changed colour for the length of one row read as the two of them
overlapping, which is exactly what it was. The sweep a held row fills with and
the ring a pressed one flashes start there too.

**It reached for a drawn mark three times before this.** A tick at the far end
of the row said nothing: a mark with no second state, at the opposite end of
the card from the words it is about. A radio ring at the head of each row said
more - an empty ring beside every row says *these are alternatives* before it
says which one - and was a second drawing for something the row can simply
*be*, in the slot a row's own glyph wants. A pointer on the line said it best
and was still one shape too many: the line it stands on already changes colour
at that row, and a card whose whole argument is that a row has nothing to show
but its name is the last place to spend a drawing on saying which row.

The pointer also marked the *cursor* for a pass, drawn dim outside the card and
accent in, which reads well until you notice the ground was saying *in force*
two pixels away from it: one line, one mark, and two different answers to which
row matters. Giving the persistent mark the persistent state and the transient
mark the transient one is what made the card readable at a glance.

**A tick at the far end of the row** was first, because it is what the grid
drew then - the grid has since dropped it for the same reason, and says it with
the tile's own ground instead. It says nothing there: a tick has no second
state, so a reader sees one row carrying a mark and three carrying a gap, at
the opposite end of the card from the words it is about.

**A radio ring at the head of each row** was second, and it is what the design
draws. It says more - an empty ring beside every row says *these are
alternatives* before it says which one - but it is a second drawing for
something the row can simply **be**, and it put a mark in the slot a row's own
glyph wants.

**A ground** is what survived. A filled row among unfilled ones needs no mark
read at all, which is the whole argument for it at three metres. That freed the
cursor to be the rail, and freed the row's ring and ground - which the card
already wears to say *it* is selected - from saying the same sentence twice at
two sizes.

The `rs` payload is unchanged through all three: `on` is the question, and how
it is drawn is the panel's.

### The travel, which is the spine turned on its side

The line above is drawn a second time, along the foot of a card, and it is the
same line: `Travel.qml` draws it for a slider, for a slider with stops, and for
a reading, in this surface and on the HUD. What noticed it was reading the row
card back and saying out loud that it is a vertical slider: a stack of rows
with one row's length of line lit and marked at both ends is exactly that, and
the thing at the foot of the card beside it was a rounded eight-pixel trough. Two drawings of one idea, and the line is the one that
survived: a card that draws one kind of line is a card read once.

So the five measurements are the ladder's (`metrics.spine`), not either
surface's, and the marks are the same marks:

| On a card of rows | On a slider, a stepped slider, a reading |
|---|---|
| the spine, down the left | the travel, along the foot |
| a cross capping each end | the same cross at each end, out where the line ends |
| the row in force lights its length of it | the line behind the value is lit up to it |
| a stroke at each end of the row in force | the same cross again, in the accent, at the value |
| - | that run is solid where the value has stops, a tint where it has none |
| - | the same cross at each place a stepped value may stand |

**Nothing fills.** A bar filled to the value draws a number as mass, which is a
second answer to a question the figure at the top of the card has already
answered in words - and on a stepped control it was mass that disagreed with
the word, four pixels along from where the last press left it. What is drawn in
the accent is **where the value is**: one stroke across the line at that place,
with the run behind it saying how far it has come.

**The mark alone does not show a press, though**, and that took a screen to
find: a press moves it by a few pixels, which is not a change anybody sees from
a sofa - on the plain line there was nothing else to see move. So the line
**behind** the value is drawn in the accent at half. What changes at every
press is then a length, read against the length ahead of it, and the full
accent still belongs to one place: where the value is.

**A line with stops fills that run; a line without them tints it**, and the
two are different claims rather than two strengths of one. A stop is a place
the value has *stood on*, and every stop behind the mark is a place it has
been - so the run is as solid as the mark that ends it, and the stepped control
keeps exactly what its segments shipped for: *how far along* readable without
arithmetic. A continuous value has been at every point behind it and stood at
none, so its run is the accent at **half** - a tint rather than a fill (qml.md
8.1), which leaves the full accent to the one place the value is.

Half, and not the fifth a lit ground takes: a two-pixel line has no area to
carry a tint that faint, and at a fifth it is not there at all. Nor the ink at
its dim level, which was tried and made the run the brightest thing on the card
- the eye then lands behind the value rather than on it.

**What a press is measured against is drawn too.** A step moves the mark a few
pixels, so the one question a hand asks while it pushes - *what have I done to
this* - was answered by a mark that had barely moved. So while a control is
**held**, the line carries one more thing: a **faint mark where A took the
value from**. The solid run still ends at the value, whichever way the press
went; what the ghost adds is the other end of the comparison.

`b` on the payload is that place, and it is on the wire only while the tile is
held and only while it differs from `v`. Let go with A and it goes; let go with
B and the value goes back to exactly where it stands.

**The ghost is the line's alone: a ring does not draw one.** It is the fourth
place the knob parts company with the travel, and the circle's rather than a
preference - a mark on a line has somewhere of its own to stand, while *where
was it* on a ring can only be a second pointer out of the same middle, and two
rectangles turned out of one hub is a clock. The tile would stop reading as a
value and start reading as a time. What a turn has done is legible anyway, in
the run lengthening behind the pointer.

**The length between the two was drawn for three passes and none of them
lived.** A dashed run on the line read as the line itself gone faint. A row of
chevrons was a second alphabet on a drawing that has one figure. A leaning
hatch fixed the direction and then wanted its own spacing, its own clearance
from the line, its own rule for standing aside from a stop - four decisions to
say a thing the two marks already say by standing where they stand. What a hand
is asking is *where was it*; a mark answers that, and the distance is read the
way every other distance on this line is, by looking.

**The run starts where the mark that ends the travel stops**, with nothing
between the two. It began an arm later while the line still had a tail, and
read as a second line starting somewhere of its own; what the eye wants at that
end is one stroke leaving the mark.

**And every mark the run has passed takes the run's colour.** A stop already
stood on, or the end the value started from, is not a place it might go - so
the marks behind the value belong to what is covered and the marks ahead of it
belong to the scale. It is the same two colours the run itself has: solid on a
line with stops, the tint on a line without them.

**The mark stands at the far edge of the stop it is on**, not in the middle of
it: a stop is a length the value has reached the end of, so the mark is where
the reaching stopped. In the middle it read as something sitting inside the
segment rather than as the point the segment runs up to. It stands exactly
where that stop's own stroke stands, so the accent covers the stroke instead of
landing half a weight beside it and reading as one stroke drawn twice.

**The value is marked with the same stroke as everything else on the line**,
in the accent. It was a wedge first - the mark the row card carried then, at a
quarter turn - and a wedge lying on a horizontal line is an arrow: an arrow
points somewhere,
and beside a horizontal line there is nothing to point at. Then it was the line
thickened, which came out as a block sitting on a stroke. What it is now is the
stop's own figure, drawn where the value is and filled with the accent, so the
drawing has one stroke in it and three things to say with it: the ends, the
places, and where you are.

**Nothing on this drawing is painted twice.** Every ink here is the theme's own
at a share of itself, so a bar run through the line lights the pixel where they
meet - which is what the first pass did, seven times along a stepped control,
and the second pass hid by hanging the stops under the line instead of across
it. The dim strokes are two arms with the line taking the crossing between
them; the value's own stroke is one piece, because the accent is opaque and
covers the line rather than tinting it.

**The stops are the cap repeated.** A cross at the end of a line says *the
line ends here*; the same cross partway along says it about a place the value
may stand. So a stepped travel and a continuous one differ by exactly what the
two controls differ by, which is whether the line has places printed on it -
and nothing else in the drawing has to know which kind it is. `seg` and `at` on
the payload are unchanged.

**The ends of the travel are values, and the line stops at them.** Each end
reads as a `T`: the stroke standing across, the line leaving it inwards, and
nothing past it. It carried on an arm past both for two passes, which is what
the spine does above a list - and a line beside a list wants that, because the
list simply stops and the line has to say so. A line **under a value** does
not: its ends are values. The tail read as a drawing that had not been trimmed,
and it put the end marks out of the value's reach, so a slider pushed the whole
way stopped short of the mark it was reaching for.

**The two that end the travel are longer than the stops between them**, by one
rung of the space ladder - `spine.crossEnd` against `spine.cross`. An
instrument of one stroke weight has only length to tell one kind of mark from
another with, and the two kinds here are *this is as far as it goes* and *this
is a place it can stand*, which is one rung's worth of difference. It was the
whole silver step for a pass and read as two marks of two different sizes
rather than as one scale. The value's own mark takes the reach of whatever mark
it is standing on, so at either end it covers that mark exactly instead of
sitting inside it with the tips showing.

**Every stroke owns its own pixels.** The line runs *between* the two marks
rather than under them, and the covered run starts where the first mark stops -
every ink here is the theme's own at a share of itself, so a square painted
twice is a square painted brighter, and a line running under the mark that ends
it lit exactly that square. At the far end, where nothing is lit and both are
the dim ink, it read as the two of them interlocked.

Every mark on the line is one series: `edge(n)` places the two ends and every
stop between them, and the value's own mark lands on one of them. **A stepped
value's stops *are* the marks** - five stops are five marks with four divisions
between them, the bottom stop is the mark that begins the travel and the top
one is the mark that ends it.

It stood at the far edge of the stop it was on for a pass, on item 63's
argument that the first stop of a ladder is still somewhere to be. What that
drew is a control printing `Off` with a division lit behind it, which is the
bar disagreeing with the word above it - the same fault the segments were meant
to cure, one place along. Nothing is covered at the bottom stop now, and the
mark sits on the mark that begins the scale.

`metrics.time.fill` went with the troughs. A mark is where the value *is*
rather than a length growing towards it, so it lands on the frame the value
changes - qml.md 8.2.4.1, which is the rule the bar was the exception to.

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

Three ways to the same set of numbers, for three different hands - the third
is a knob's alone and has its own section below:

- **The D-pad**, once taken, is how you land on the number you meant. One step
  per push, growing to `[menu] ramp` after `[menu] ramp_ms` of holding a
  direction - shaped like `scroll_ramp`, and a reversal starts it again for
  the same reason: somebody who has gone too far is not asking for the speed
  they overshot at.
- **Either trigger**, taken or not, is how you cross the distance to it. A
  pull is a rate rather than a repeat: fully in crosses the whole range in
  `[menu] sweep_ms`, half in takes twice as long. The two pull against each
  other, so both in is still. Half in is half of the travel *past*
  `[device] trigger_rest`: a rate is the one reading where a trigger resting
  off its minimum moves a value on its own, and that floor is where the pull
  starts - see [daemon](daemon.md).

The sweep moves in **whole steps** of the setting's own `step`, so a value a
trigger swept to is one the D-pad could have landed on. Three ways to one set
of numbers, not three sets.

**`menu_range` is the one place that knows how long a control is**, and all
three gestures ask it: the whole travel and one step of it, in the value's own
units, for a range, a ladder and a list alike. The sweep read `CHOSEN`
directly for as long as there was one kind of range to cross, which left the
trigger dead on the two tiles most likely to be swept - how loud it is and how
bright, which are the machine's numbers rather than ours - and took the loop
down outright on a card of rows, which is takeable and has no range at all.

`pointer_speed` is thirty-eight steps end to end, which is what makes both of
these load-bearing rather than a flourish: a slider stepping once per press
would be worse than the two rows it replaced.

### A ring, and the one gesture that is already a turn

`check_menu_turn` is the third way into a value and the only one that is not a
translation. A direction is pushed and a number goes up; a trigger is pulled
and a number crosses; a **knob is turned**, and a thumb going round the edge
of a stick is that movement rather than a stand-in for it. It is the whole
argument for the control - a ring that could only be pushed sideways would be
a slider drawn round a corner.

**Two gestures, and `[menu] turn` picks between them.** They are not a tuning
of each other; they are different controls that happen to share a drawing.

- **`aim`** (`menu_turn_aim`, and what ships) puts the value **where the thumb
  points**. The ring has a pointer and the stick is one, so they are the same
  figure: take it, point at the number, let go. Winding a dial round to a
  place you can already see is the long way round a thing you are looking
  straight at. A number is **followed rather than stepped** - see below.
- **`carry`** (`menu_turn_carry`) moves it by **how far the thumb has
  travelled** since the last frame, never by where it is pointing. Nothing can
  jump on the frame a hand lands on the stick, which is the whole of its
  argument: an aimed dial grabbed at two o'clock puts the volume at two
  o'clock, and on a sink that is a loud press made by not looking.

`aim` is the default because the drawing was already a dial. The promise it
gives up is written down in `AimedKnobTests` rather than left to be
discovered - `test_an_aimed_ring_moves_on_the_frame_the_thumb_lands` is that
entry - and `carry`, which keeps it, is one word away in the config with its
own ledger in `KnobTests`.

**The gap under the dial is the two end stops.** `Knob.qml` leaves the bottom
quarter of the circle open - the scale is 270 degrees from half past seven to
half past four - and under `aim` a thumb pointing into that quarter is past
one end or the other: nearer the left foot is the bottom of the range, nearer
the right is the top. So the quarter that has no scale is not a dead sector
that ignores a hand, it is the hole a real knob's stops sit either side of,
and a ring still does not wrap. `knob_place()` is that arithmetic, and
`KNOB_ARC_FROM` / `KNOB_ARC_SWEEP` are the same two numbers `Knob.qml` draws
from - **not settings: an aimed knob is only honest while the daemon's
arithmetic and the panel's arc are the same arc.** The panel cannot read the
config and the daemon cannot read the QML, so they are written twice and
`test_shell_plugin.KnobArcTests` holds them to each other.

The rest are promises rather than tunings, and both gestures make them:

- **The grip is what makes an angle measurable - and the two gestures need
  different amounts of it.** Near the middle of a stick's travel a degree is
  noise, a resting thumb crossing whole quadrants without moving. What that
  noise *does* is what differs: `carry` integrates travel, so a wobble adds up
  into real movement and the radius has to keep the sum honest
  (`[menu] turn_grip`, half the stick); `aim` reads a bearing and keeps
  nothing, so a wobble is an error that corrects itself the moment the thumb
  moves on, and the radius only has to make the bearing mean something
  (`[menu] aim_grip`, a quarter).

  **The second number is measured rather than chosen.** An aimed dial
  inherited `carry`'s half and that was a wall: logged on the machine, a thumb
  turning the volume the way a hand turns a dial reached **0.44 to 0.49** of
  the stick's travel and was refused on every frame, so the ring did nothing
  until it was shoved past half. It read as a control answering late - and
  every other suspect (the loop at 125 Hz, the pad at 500-2000 axis events a
  second, the stream, the panel) measured clean first. `pad-diagnose`'s ladder
  is what found it; a guess would have changed the wrong number.

  Coming off the grip drops the angle rather than remembering it. Gripping
  again starts from wherever the thumb landed, which is the other half of
  `carry`'s no-jump promise.

- **The motor says nothing while an aimed dial follows.** `texture` answers a
  direction, and a control you point at has its direction already - the hand's
  own, with the ring under the thumb making it. [`rumble.md`](rumble.md) holds
  the argument and the measurement; `edge` stays, and `carry` keeps the hum
  because winding is a push.

- **A dial follows the hand, not the spring** (`menu_letting_go`). A stick let
  go of does not return straight to the middle: its two axes come back at
  their own rates, so the bearing swings on the way in. Measured on the
  machine, a ring released at 18 degrees read 27 and then 38 over the two
  frames it took to fall past the grip, and dragged the volume four percent up
  behind it - the value ending where the spring passed rather than where the
  thumb pointed, which is the one thing a control you aim at must not do.
  Lowering the grip for `aim` made it worse by leaving more of the return
  inside the reading, so the answer is here rather than in a radius.

  The spring is told from the thumb by **how fast the stick is falling
  inward**, and nothing about it is marginal: aiming moves about a thousandth
  of the travel a frame, a released stick a quarter of it, and
  `[menu] turn_return` sits between two numbers two orders of magnitude apart.
  It is **latched** rather than judged per frame - letting go is a thing that
  has happened, not a thing that is true this instant - and holds until the
  stick is pushed back out or comes to rest under the grip. `carry` winds on
  that same swing, more quietly: nineteen degrees is most of a step at the
  shipped gearing, so both gestures read it.
- **Whole steps under `carry`**, like the sweep: a value a thumb *wound* to is
  one the D-pad could have landed on. Three ways in, one set of numbers.

  **`aim` follows a number instead, and that is not a relaxation of the
  rule - it is the rule meeting a gesture that is not a press.** A step is how
  far one press moves a value; it was never what the value is *allowed to be*,
  and the two are the same question only where the places are countable.
  Quantised to `step`, a volume aimed at moved five percent at a time under a
  thumb travelling smoothly, which reads as the dial jumping rather than as
  the hand being followed - the control's one promise, broken by the one
  gesture it was built for. So an aimed number lands on anything it can
  *say*: `knob_fine()` is `1/scale` - whole percent for a level, because that
  is what `_word` writes into the command, and whole pixels a second for a
  speed, because that is what it prints. A ladder and a list keep their stops,
  there being nothing between two rungs or two words to land on
  (`menu_turn_stop`).

  What that costs is a level per frame instead of per step, which is why
  `live_write` coalesces onto `[live] write_ms`: a helper is about thirty
  milliseconds and the loop runs at `poll_hz`, so the machine is told where
  the thumb *is* rather than everywhere it has been. Sent one per frame, a
  swept dial queued most of a second of `pactl` - the sound arrived late, and
  the `settle_ms` check that landed mid-queue reported a sink halfway through
  it and rewound the ring. A switch and the player's own buttons never
  coalesce: two presses of Next mean two tracks.
- **Two numbers gear `carry`, and the slower wins.** An aimed dial has no
  gearing to have - the scale is the whole of it - so these do nothing under
  `aim`. `[menu] turn_degrees` is how
  far round the whole range is, and `[menu] turn_step_degrees` is the floor
  under one step of that - because the range is the *control's* length and a
  thumb aims at a *step*. The knobs a page can hold run from one step end to
  end (a pair of words) to thirty-eight (the pointer's speed); geared by the
  range alone, the same 270 degrees is a quarter turn per step on the first
  and seven degrees on the last. Seven degrees is a wobble, not an aim, and
  volume at 13.5 was close enough to it that a thumb crossing the rim carried
  a third of the range it was only passing over. `menu_turn_step()` takes the
  larger of the two, so the floor only ever slows a dial down: a ladder of
  five stops is 67 degrees a stop already and is untouched, while volume
  becomes a dozen detents to the turn and the range takes two of them.

**A ring does not wrap.** A list walked with A comes back round to where it
started, and that is right for a press - there is one way through it, and
coming out of the far end is how you reach what you walked past. A turn is
continuous and the value has a *position*, so a thumb that carries the pointer
clockwise past the last stop and finds it at the bottom of the dial has lost
what it was moving. That is the grid's own rule about wrapping, arriving on
the one control where going round is visible. `menu_request` is where the
clamp lives, and the value that did not move becomes the end stop
`menu_adjust` already announces.

**The turn is the held tile's, and only the held tile's.** A tile the
selection is passing over cannot own the stick any more than it can own left
and right, which is what `TAKEABLE` is for. `menu_turning()` is the whole
question, and it is the one place on this surface where the same stick means
two things.

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
- `push_menu_live()` - `{open, sel, g, live: {x, y, hid, hv, ht}}` and **no
  `items` key at all**. `x`/`y` are where the watched thumb is; `hid`/`hv`/`ht`
  are the ring being turned - which tile it is, where round it the value has
  got, and the number in words.

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

**`hv`/`ht` are here because an aimed dial broke `menu_gauge`'s premise.** That
doc says a setting rides the *full* push - it changes only when something
presses, and streaming it would send it sixty times a second to say the same
thing. A number followed rather than stepped changes on every frame a thumb
moves, so the premise stopped holding for the one tile that is turned: the
surface was being rebuilt at `poll_hz` to move one pointer, which is the cost
this section exists to avoid, and it read as a ring lagging the hand. A held
ring's value is therefore a gauge like any other. Only a **continuous** one:
a ladder and a list step rarely enough to ride the surface, and their drawing
needs `seg` and `at`, which are on the full push alone. `menu_adjust(quiet=)`
is what stands the full push down, and `menu_settle` pays it back with one
rebuild when the hand comes off - the tiles behind the ring were drawn from a
payload that is by then a push old.

**`hid` is `sel`'s rule one field along, and it was learned the hard way.** A
stream that carries almost nothing is still read on its own, so a value has to
name its tile. `hv`/`ht` first shipped without one and the panel matched them
to whatever tile was *held* - which is right for exactly as long as something
is being turned. The stream falls silent when nothing is (there is nothing to
say, and saying nothing is the point of the guard above), so the last line it
sent stands: let go of the volume ring, take the Strength slider next, and the
slider wore the volume's percentage. Two tiles, one number, and nothing in any
log. The fix is the field, not the panel's cleverness.

The words are the daemon's rather than spelled in the panel, unlike the clock:
what a value is called is a wording decision, and the panel holds no minimum,
maximum or unit to spell one with.

**Only the whole surface may say that something has ended.** Three fields mean
*gone* by being absent - `chrono`, `confirm` and `count` - and the short push
carries none of them, because it carries almost nothing. Read as
authoritative it ends all three, which on screen was a clock losing its three
sub-dials for as long as a ring was being turned beside it. It went unnoticed
for as long as the short push only flew for a gauge; a held ring streams on
any page, clocks included. `applyState` takes `s.items !== undefined` as the
mark of a whole surface - the same absence that makes the short push cheap -
and guards the three with it. `test_shell_plugin.ShortPushTests` holds both
halves of that contract, the guard and the daemon's leaving `items` off.

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
| walking to another card | the page |

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
  page behind them the tiles are the only thing there is. The nav cards get
  the same, for the same reason - they are made of the same thing.
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

**It comes back where it was.** `where()` names the card and the tile as ids,
the daemon remembers them across a close, and `reset(where)` goes there. Most
of what a HUD is for is coming back: you turn the volume down, you go back to
the game, and you come back to turn it down again - a menu that started at the
top every time would make you walk there every time.

The tile it remembers is the one at the **bottom of the stack**, not the one
in front: coming back inside a submenu you had drilled into would be coming
back somewhere you did not leave from.

With nowhere to come back to - the first press of a session, or a card that
has gone away since - a tile carrying `open_on` gets to say where it starts,
and otherwise it is **the first tile of the first card**.

**One tile in the shipped tree carries `open_on`, and it is the one that can
never take anything away: `Start here`.** It was item 48's answer too - the
workspace lock, near enough to reach over a game - and for that one, coming
back where you were turned out to be the better answer: use the tile once and
it is what the next press opens on, at no cost to any other page.

`Start here` is the exception because of when it is offered. Its `when` is
`first_run`, which is true until the menu has been opened at all, and a menu
that has never been opened has nowhere to come back to either - so the two
rules never disagree over it. The daemon writes the mark false as it opens
(`[menu] first_run`, through `settings.toml`), which makes this the one tile
whose whole life is one opening.

## The title, and what it says at each level

It is not the same sentence at both levels, and it used to be nothing at one
of them.

Drilled in, it is the page you are on, with the Omarchy menu's trailing
ellipsis for *this is where you are, pick something*: the bar is dimmed on the
card you came from and the title is the only thing naming the page.

At the top level it is the current group's **detail**. There was nothing here
for a good reason - the bar is already saying where you are, in the
same words and an inch below, and a line above it saying `Go…` is the card
telling you twice. But what a group *holds* is the one thing the bar cannot
say, and every group in the shipped config has already been written a detail
that nothing was drawing: `Sound, screen, what is playing`, `Where the sound
goes`. No ellipsis on it - it is a description, not a place.

It is a fixed-height line either way, so walking the bar never resizes the
card under a thumb that is aiming at a tile. That is why the detail is not on
the card: a card that grew when you walked onto it would move every card
after it. `headerSpace` is zero when the line has nothing to say at all, so nothing
is left holding its place.

## Rearranging a page

The tiles are the person's, not the config's. **Y** on any page and every
button on the card means something else; the legend along the foot says which,
which is what makes the mode findable at all.

**It was Y's hold for a while**, on the argument that the guide is what
somebody opening the menu in a hurry wants and rearranging is a thing you sit
down to do. Against use that is the wrong way round: the guide is a page read
once, and an arrangement is one somebody comes back to tile by tile. So the
tap arranges, the hold opens the guide - which also has a row of its own on
`Controller > Buttons`, and is the one of the two with a second door.

### The gesture, as a table rather than a branch

`EDIT_KEYS` in `daemon.py` is eight ordinary binding specs, and `binding_for`
consults it before the page's own keys and before the layer's. **The legend is
built from exactly those specs**, so what it prints and what a press does
cannot drift apart - which is the whole reason the legend is worth having.

The contract holds: A still commits (picking a tile up and putting it down is
what commit is saying here), B still leaves (leaving edit mode is leaving), X
is this surface's own verb one mode along (`close` becomes `hide`), and Y is
still the reach - for the arrangement that is not on screen because it is the
one the config shipped.

**The shoulders and the triggers are what a mode borrows.** L and R walk the
bar everywhere else in this layer, and while a page is being rearranged the
bar is not what a thumb is aiming at; ZL and ZR are unbound here. L and R are
narrower and wider, ZL and ZR shorter and taller - the pair a thumb reads as
side to side, and the pair under it.

**Both axes, which used to be one.** The argument for width alone was that a
height is a control's own shape - a bar is a bar and a dial is round - and
that is true of what a control *draws*, not of the cell it is drawn in: a card
of rows with a row too many, a reading you want from further away, a keyboard
tile that wants two rows rather than four. `MenuModel.resize` took both axes
from the day it was written; it was the two buttons that were missing.
`rows_limit` clamps the new one, because a tile taller than the page the HUD
draws is a tile with rows nobody can see.

**A borrowed button has to outrank a layer trigger.** ZL opens the window
layer out here and is the pointer's precision modifier, and neither may
swallow the press: `surface_override` answers "menu" for any button in
`EDIT_KEYS` while the mode is on, because the alternative is a layer opening
silently while the legend says `Shorter`.

The cost of the hold is that **Y acts on the way back up** rather than on the
way down, the way every tap/hold does. HOME already has that beat in this
layer.

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
slider is that list with the numbers showing.

**What that effect says is which way you just pushed.** `menu_feel()` hands
the motor a side rather than a level: the right motor where the value went
right, the left where it went left, and the left again for a list walked up or
down inside a card - the D-pad is under that thumb, and a vertical push has no
left and right to answer with. One level, flat, for as long as the control is
moving; it rose with the distance from where the push began for a pass, which
is a second reading of the number the tile is already printing.

A row stepped inside a card takes the same hold a scrubbed slider does
(`MENU_SCRUB_HOLD`), so a list being walked is felt exactly as a value being
pushed is. See [`rumble.md`](rumble.md).

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
decided which submenus converted: `Button style` has two values whose names say
the difference, and `Button labels` and `Profile` kept their submenus because
getting either wrong scrambles the face buttons and the sentence under each
choice is what stops you. See
[`../conventions/writing.md`](../conventions/writing.md).

**A card of rows is the third answer, and it is the one that pays nothing.** A
row has the card's width and its own line under it, so the values are all on
screen *and* each keeps the sentence. `Start in` is the worked example: it was
a choice, which meant a card reading `Game mode` was a card you had to press to
find out what else there was. There are now two rows, two lines and a ground
filling the one the next start is waiting on.

So the three shapes answer three different questions. A **submenu** is for
choices that are a place of their own. A **choice** is for two values whose
names are the whole difference, in one cell. A **card of rows** is for a short
list you want to read rather than press - which is every tick submenu that
converted for the room rather than because a chevron suited it.

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

**What `choose` is handed is narrower here than on a desktop: the tiles
`snap.beside` says are beside this one** - the rows a sideways press covers,
the columns an up or down one does. A desktop is sparse, so a window with
nothing beside it is one a flick still has to reach; a page is *packed*, so
what is under your thumb is under the tile you are on, and a press that left
the band was a thumb pushing down and a cursor crossing the page.

Both halves of that were reported from the sofa. Scored from the tile's
centre, a press of left at the start of a band found the tile one row up and a
column back - `Button labels` landing on `Vibration`, because a one-cell
tile's right edge is left of a three-cell tile's centre. And scored without a
band, a press into a hole found whatever was nearest past the edge: `Profile`
answered down with `Button style` at the far right, `Screen` answered up with
`Corners` beside it, and `Workspace lock` - which ends a row while the pad is
in game mode, with nothing under it until `Keep the controller` joins it -
answered down with `Mute`, at the other end of the row below.

**The band is the one rule that can strand somebody**, and that is what
`ShippedPageTests` is for: tiles are packed first fit, so a small one can
backfill a hole and end up with nothing beside it, and a tile you can see and
cannot select is worse than any crooked jump. Every shipped page is walked end
to end in every state a `when` can put it in. The looser rule was measured
against it over twenty thousand generated pages and reached nothing the band
does not, so there is no fallback: a page that strands a tile strands it
either way, and that is a packing to fix rather than a press to bend.

`[menu] bias` is its own number rather than `[snap] bias`, and it is measured
rather than inherited: windows are large and sparse, tiles are small and
touching, and `tests/test_menu.py`'s golden fixtures are what it was set from.

## The head

`build_head(entries)` is the read-only grid above the bar. **Nothing on it is
selectable** - a clock is not a button, and a cursor that can wander into one
is a cursor that has to come back out again.

**A cell is up to three lines and every one of them is the same kind of
thing**: a `format`, which is strftime and rendered in the model, or the last
thing a command said, which the daemon supplies. `over` sits above the cell's
own line and `under` below it, sent as `o` and `u`; a cell without one sends
neither at all, so `o !== undefined` is the whole of the panel's test for
whether it stacks.

The same two sources at every level, deliberately. A cell that could print a
command's answer while the line under it could only print a time would be two
grammars wearing one name, and the first thing anybody would want there is the
one it does not have - a name over a clock is not a time. A bare string is a
`format`, which keeps `under = "%A"` the whole of what a weekday costs; a table
is the long form, and it is how a line becomes a command:

```toml
over = { from = "id -un", ttl = 0 }
```

Three lines in one cell rather than three cells, because `place()` packs the
head first fit - nothing can promise that the cell holding the day lands under
the one holding the time rather than beside it. **`head_sources(cell)` is the
one thing that knows a cell has three lines**, so `daemon.menu_head_refresh`
asks for whatever has gone stale without learning the shape of a cell, and each
line files its answer under an id named after the cell (`clock.over`).

`ttl` is how long an answer stays fresh, and **it is not the heartbeat**: the
surface redraws every couple of seconds and the weather is asked for every
quarter of an hour. **Zero means it never goes stale** - a name, a hostname -
so it is asked once a session. The due is written before the answer lands, so a
slow command is not asked twice over, and the *never again* is written when an
answer arrives rather than when one is asked for: a command that failed is
tried again instead of leaving the cell empty until the daemon restarts.

**The cell's height is what decides its treatment**, not a key saying so. More
than one row and the panel sets the middle line at the top of the ladder
(`metrics.type.vast`) with `over` and `under` small and in capitals around it;
one row and it is a line of text at `metrics.type.lead`. Which is why the
shipped clock is three rows tall - a name over it and a weekday under it need
the height around a headline set at the top of the scale - and why the weather is one: a cell that asked for a headline
without the room would clip. The capitals are the panel's decision and not the
config's: `%A` returns whatever the locale's own weekday is, `id -un` whatever
the machine calls you, and casing either is typography.

`from` + `ttl` is not new - it is what a `[profile.<app>.osk]` page already
uses, one surface along - but the two share syntax and validation, not
internals: a submenu source turns lines into selectable tiles, a head source
turns output into one drawn string.

**Why the weather is here at all**, when `roadmap.md` refused it. It was
refused because *"putting it here means network I/O in an input daemon, with
caching, failures and a location to own"*, and none of that lands here.
`omarchy-weather-status` owns the lookup, `omarchy-weather-icon` owns the
condition - the same glyph Omarchy's own bar draws, and it knows whether the
sun is up - `omarchy-weather-location` owns where, and each prints its own
failure. omapad runs a string from the config and draws what comes back; it
never learns what weather is. A cell whose command answers with nothing keeps
the last answer rather than blanking - a blank cell in a grid reads as a
drawing fault rather than as a slow helper.

What the shipped cell's `sed` does is **wording**, which is omapad's business
where the lookup is not: it drops the place, puts the condition glyph where the
word `Temp` was, and drops `Wind` because the arrow after it already says so.
The two helpers are one pipeline rather than one after the other so their
network calls overlap - half a second rather than most of a second, against a
`list_timeout_ms` that has to cover both. A failure has no place, no `Temp` and
no `Wind` in it, so the sentence the helper wrote passes straight through.

## A row that counts down rather than being held

The other answer to *are you sure*, and the second of two on purpose: they are
for two different presses. A **hold** is right where the gesture is already in
the hand and is over in a second - `Close window`, with the window in front of
you. A **countdown** is right where what happens next takes the screen away.
Being sure you meant to log out is not a thing to do with a thumb; it is a
thing to be given long enough to change your mind about, and holding A for ten
seconds is not a gesture anybody makes.

`countdown` on a **row or a tile** is seconds - `true` takes `[menu]
countdown`. Both, because a tile may carry one: `Reboot` and `Shutdown` were
written both ways on the System page for a while - rows in the `Power` card
like the other three, and a cell of their own, because they are the two
anybody walks to that page for. The copies are gone (a page saying the same
two words twice, and a guard to keep in step in two places), the drawing is
not: the number is drawn on a tile as well as in a row, in the corner the tick
and the chevron share, neither of which can be true of a tile that is about to
run.

Two copies of one action need **two `id`s**. The flash, the countdown and the
fill all name a tile by id, and two things answering to one name is two things
lighting up for one press.

 `menu_count`
starts one, `check_menu_countdown` runs it on the loop, `menu_uncount` stops
it, and the payload carries `count` as `{id, left}` with the whole seconds
remaining, **rounded up**: a row that showed 0 for a moment and then ran would
read as a row that had stopped and ran anyway. The view is pushed when the
number changes rather than every turn.

Three things it deliberately does not do:

- **It does not tick per second.** A pad buzzing ten times through a decision
  somebody is in the middle of making is the opposite of what the wait is for.
  One tick at the start, one notification, and then the number.
- **`[confirm] scale` does not reach it.** That setting is for a hand that
  cannot keep a button down; this asks nobody to keep anything down.
- **Only B stops it.** Walking the cursor lets go of a *hold*, because a hold
  is a thumb staying still. Ten seconds is long enough to want to look at
  something else on the page, so a count that died because a thumb brushed a
  stick would be worse than no count at all. A second press does nothing
  either - the wait is the point, and a second press is exactly the reflex it
  exists for.

## A row that is held rather than pressed

`confirm = true` on an action row, and A stops being the press that runs it:
`menu_command("press")` calls `daemon.menu_arm()` instead, and what follows is
the announced hold a binding's own `confirm = true` makes. The same two waits
(`[confirm] hold_ms`, `confirm_ms`, both through `[confirm] scale` -
`Config.announced_scaled`), the same tick, the same notification, the same
cancel button.

Four things end it, and only two of them are somebody deciding against it:

| | |
|---|---|
| the thumb comes off A | `MenuAction.release` → `menu_disarm(cancelled=True)` |
| the cancel button | `cancel_confirm()` drops it before it looks at the held buttons |
| the selection moves, or the page changes | any `menu_command` that is not `press` disarms |
| the menu closes | `set_menu` disarms, and **quietly** - the surface going away is not a decision |

`menu_confirm_state()` is what the tile draws from - `{id, ms, armed}`, the
game bar's `holding` one surface along - and it is stamped onto the payload by
`push_menu_view` rather than held in the model, because the two waits are
config and `menu.py` reads none. `check_menu_confirm(now)` is the clock, on
the loop beside `check_hold_timers`, and `needs_tick()` knows about it so a
row counting down is not timed by the idle poll.

**The tile fills, the bar does not.** A badge on the game bar says which
*button* is counting down; a tile is the thing being looked at, so here the
page says which *row* is - `Menu.qml`'s `lapping`, clipped to the tile's own
ground the way the badge's sweep is clipped to the badge's drawing. The fill
runs in over `hold_ms` and back out over `confirm_ms`, so the tile is empty at
the moment the row runs.

`menu_holds()` is the other half, and it is what the legend reads: while the
tile in front is one of these, A's word is `Hold to confirm` rather than
`Pick`. Said before it is pressed, because a gesture you find out about by
making it is a gesture nobody makes on purpose.

## Which way a page was reached from

`turn_seq` and `turn_way` on the payload, and they are `press_seq`'s shape for
`press_seq`'s reason: the page is re-sent every heartbeat, so a turn the panel
has already drawn must not be drawn again. `+1` is further in - a level down,
the next chip along - and `-1` is back out.

`MenuModel.turned(way)` is called by the three things that replace a page and
by nothing else: `press()` drilling in, `back()` popping, and `enter_group()`
when the group actually changed. **Opening the menu is not one of them** - a
surface arriving has its own way of arriving, and a page that also slid in
from somewhere would be two entrances for one press.

`group_move` is the one that has to say the direction rather than let it be
worked out: the bar wraps, so the last chip to the first is a step to the
right that looks like a jump to the left to anything comparing indexes. It
leaves `_group_way` behind for `enter_group` to pick up and clear.

What the panel does with it is a drawing and belongs to the panel: `Menu.qml`
offsets every tile by one shared `shift` - added to `cellX`, so there is no
container between the Flickable and the tiles for the sake of a number that is
only ever on its way back to zero - and runs it home over `time.follow`. A
page reached by going in arrives from the right and settles leftwards. At
`[ui] motion = 0` the duration is 0 and the page is simply there.

## Tiles that are not always there

`when` on a tile is the states it is offered in - `game`, `handed_over`,
`locked`, `kept`, `first_run` from `menu.WHEN`, any one of them being enough; a
tile that says nothing is always there, which is nearly all of them. `build()`
rejects a name that is not one of those, so `omapad check` says which tile
would never appear.

Every state but the last is something the person holding the pad can see for
themselves, which is the rule the list is kept short by: a tile that comes and
goes for a reason nobody can point at is worse than one that is always there
and sometimes does nothing. `first_run` breaks that rule deliberately - it is
true exactly once, which is what a first start *is* - and it is spent on the
one page that says what the buttons do, so the opening it appears in is the
opening that explains it.

`daemon.menu_conditions()` reads the states **when the menu opens** and
`MenuModel.conditions` holds them until it closes: a tile that came and went
under the selection would move every tile after it while a thumb was aiming at
one.

## Cards that list what is plugged in

A `rows` card takes `from` like a submenu does, and `Audio` is made of two of
them - the outputs and the inputs, each drawn where it stands. It was `Devices`
opening on `Output` opening on the outputs: two presses in before a name you
could pick, and each of those pages held exactly one thing.

The only difference from a listed page is **when it is read**. A submenu is
filled at the press that enters it; nobody enters a card, so
`menu_cards_settled` fills every listing card on the page in front once the
page has stopped changing. `[menu] group_settle_ms` is that wait and it is the
bar's own, for the bar's reason: walking across four pages should spawn one
command rather than four. It is keyed on `page_name()` rather than on a turn,
so every way onto a page - the bar, drilling in, coming back out, opening the
menu where it was left - arms it once and the same way.

**A listing with one line is not a list.** One pair of speakers in the room is
one row: picking it sets what is already set, and a column of alternatives with
a single alternative in it is a card of furniture round a fact. `lone()` is
what says so, the payload carries `one` on the card, and the panel draws that
line as a **reading** - the heading names it, the line is the answer, and none
of the spine, the lit length or the ground applies. `takeable()` refuses it too,
which is the `readout` tile's own argument one control along: a press that
finds nothing to do is worse than no press. Plug a television in and the second
row makes it a list again.

Only a card that *lists*. A card somebody wrote one row into meant that row,
and a verb is a verb whether or not it has company.

**And only where picking it would change nothing**, which is the other half of
the same sentence and was found by the first listing that is not a set of
devices. What says a lone row is the fact the card is furniture round is the
**mark**: `*` from `pactl`, `on` here. A lone row without one is something to
run or to switch to - `Scripts` lists a folder, and a folder with one script in
it is a list of one that A runs. The `empty` placeholder is a reading whatever
else is true, because it carries no action at all.

`build()` seeds such a card with a single row carrying its own `empty` words
rather than with nothing: a blank card on a page you are looking at reads as a
drawing fault rather than as a question nobody has answered yet. `menu_fill`
picks which list the answer lands in - `rows` for a card, `items` for a page -
and `choose()` moves the fill among **that card's** rows only, because two
lists on one page are two questions and picking a speaker says nothing about
which microphone is in use.

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

Walking to a card whose page is listed does **not** read it at once:
`[menu] group_settle_ms` is how long the bar has to stop moving first, because
flicking across five cards should spawn one command rather than five.

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
open, title, clock, depth, sel, row, g, n, hit, groups, head, headrows, keys,
cols, rows,
items: [ {id, l, i, d, sub, x, y, w, h, on?, k?, rs?} ]
```

`sel` is a tile **id**, not an index. `g` is which nav card. `groups` is
`[{id, l, i, d, m}]` - `d` being the group's own detail, which the title line
prints at the top level, and `m` the word under its name on its nav card. It rides on every group rather than only the current
one because which one that is already travels as `g`, and a payload that
answered the same question twice is one that can disagree with itself. `head` is `[{t, x, y, w, h}]`, `keys` is `[{b, k, n}]` - the
same three letters a badge takes on `gamebar.sock` - and `cols`, `rows` and
`headrows` are the grids' shapes. On a tile, `l` label, `i` icon, `d` detail,
`sub` whether it drills in, `x`/`y`/`w`/`h` its cells, and `k` its control
where it has one.

`f` rides beside `i` where a glyph is somebody else's: a glyph only exists in
the font that drew it, and Omarchy's own mark is at U+E900 in `omarchy.ttf` and
nowhere in a Nerd Font. It is off the wire for every row that has nothing to
say about it, so the panel's test is one `undefined` and every other tile costs
nothing - `root.glyphFont()` is the one place that asks. A row inside a card
carries it the same way.

**`m` is the line a config file could not write.** A tile's `meta` is the same
`{from, ttl, empty}` table a nav card's is, run by the same refresh, and what
it says stands where the tile's *written* line stands: the heading of a card
of rows, the detail of anything else. `Windows` is what it ships for - the
card is about the window in front, the menu has blurred that window, and
`WINDOWS` over four verbs says only what the page is already called. `System >
Update` is the second, and it is the same argument about the machine rather
than about a window: how many packages are waiting is a number nothing written
in a config file can hold, and it is the number the tile exists to be pressed
about. Off the wire for a tile with no `meta` and for one whose command has
said nothing and left no `empty` word, so the panel falls back to `l` and never
draws a blank heading while a command is thinking. It goes through
`drawable()` like every other string somebody else wrote: a window titles
itself.

Only the tiles of the **page in front** are refreshed, with the bar's chips -
a `meta` is a subprocess with a clock on it, and a command answering for a
page nobody is looking at is the cost that refresh is written to avoid.

A control tile adds what it is on: `on` for a switch, `t`
for the words a choice, a slider or a knob is showing, `v` for how far along a
slider is or how far round a knob is (0..1), `b` for where it stood when A
took it - which the travel draws and the ring ignores - and `hd` where it is
the one being held. A knob adds no field of its own at all - `seg` and `at` are the slider's ladder fields doing a second job,
so a list is drawn from which place out of how many exactly as a ladder is,
and the two drawings of one control cannot disagree about what they were
sent. `b` is on the wire **only while the tile is held and only
while it differs from `v`**: a control nobody is holding has no *before*, and
the panel draws the distance between the two rather than either of them. A media tile's `l` and `d`
are overwritten with the title and the artist. The surface carries `hd`
too, as the held tile's id or empty.

A `chrono` tile adds **nothing at all**, and that is the design: the stopwatch
rides on the surface as `chrono`, `{run, el, sc}`, beside `hd` and `count`. A
value that differs on every push, carried inside `items`, makes the whole model
differ on every push - and the panel rebuilds every delegate on the page when
it does (qml.md 5.4). It was measured at 13% of a core for one moving hand.
`menu_gauge` had written the warning down for the thumb dot already; this is
that sentence one control along, and [`chrono.md`](chrono.md) has the numbers.

It is asked for through a **callable**, like `control`, and only where a tile
on the page in front would draw one: off the wire entirely everywhere else.

A `clock` tile adds `mn`, **both hands as one number**: minutes since
midnight, from `minute_of_day()`. One number rather than an hour and a minute
because an hour hand stands between two hours by exactly how far round the
minute hand has got, so a pair of fields could be sent disagreeing about that
- and the panel would then have to know how to settle it, which is geometry
this side does not owe it. It rides on the clock alone, so a page of switches
costs nothing for having one on it.

A `rows` tile adds `rs`, its own rows as `[{id, l, i, d, on?}]` - the three
questions a tile is asked and no others, because a row has no cells, no control
and nowhere to drill in to. `d` is **the line a choice tile had nowhere to
put**: a row is as wide as the card, so it can carry the sentence saying how it
differs from the row under it, and `value()` still replaces it for a row that
steps a number. Which of them the cursor is on is the surface's
`row`, an id like `sel`, and it is its own field rather than a second meaning
for `sel`: the grid scrolls to a tile and rings a tile, and only the press
reaches the row, so a panel that had to work out which of the two `sel` meant
would be the one place those answers could disagree. `confirm`'s `{id, ms,
armed}` names the **row** while one is being held, so the row fills and the
verbs beside it do not.

`count` is the third of these stamped fields and the newest: `{id, left}` while
a row is counting down, absent otherwise, with `left` the whole seconds
remaining. `confirm` is its held twin.

`n` and `hit` are **the one event on a surface of states**: the count of
presses this session, and the tile the last one landed on. They travel this
way rather than as a flag because the whole page is re-sent every
`VIEW_HEARTBEAT` seconds - a flag would light the tile again twice a second
forever, and a serial that has not moved says nothing. `n` is never 0 once
anything has been pressed, which is how a panel tells "no press yet" from
"a press I have already drawn"; `Ripple.qml` reads a click the same way.

The panel keeps one guard the ripple does not need: the first line a restarted
shell is handed carries whatever the count had reached before that panel
existed, so it is adopted rather than drawn. Drilling into a submenu still
moves the count, and the tile it names is not on the page that arrives - so
nothing lights, which is right, because the page changing is the answer.

What those strings may say is
[`../conventions/writing.md`](../conventions/writing.md): a tile is read from
across a room by someone deciding whether to press it, so a `detail` says what
happens rather than why the tile exists.

## The panel

`Menu.qml`. Centred card; a head grid, a title line, a scrolling bar of nav
cards, and a `Flickable` of absolutely-positioned tiles. Overlay layer, `Exclusive`
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
| Click a nav card | Walk the bar to it |
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

**A toggle that is on is a lit card**, not a filled one and not a pill in the
middle of one. The pill went first: the body and the knob that slides in it is
how a switch looks in a *row* of settings, and the design uses one there too,
but a cell has a whole card's worth of room to say one bit with and a pill
floating in the middle of it is a diagram of a switch rather than a switch. So
the card became the switch, and for a while the card filled with the accent
outright.

**The fill went second, for two halves of one reason.** A solid accent ground
already means something on this surface - it is the nav card you are standing
on, the one fill that has to carry a label rather than sit under one - and a
page with a lit toggle on it had two of them, the larger one down in the grid.
A bar outshouted by a tile has stopped saying which place you are in. And a
filled tile had nothing left to be *selected* with: the ring, the halo and the
light are all drawn in the accent, so on an accent ground all three came out in
`Ink.on`'s answer - a border, a glow and a face within one step of each other,
and no way to tell which of six tiles the selection was on.

So a toggle says on the way every state on this surface says one. `cellLit` is
a fifth of the accent over the cell's own ground, resolved to a solid the way
`cellGround` is, and the theme's own ink still stands on it - `qml.md` 8.1.1's
rule rather than an exception to it. The second channel is the **mark**, which
takes `Color.accent`: the one glyph on this surface drawn in a colour of its
own, because it is the one that is also a state. The edge is deliberately not a
third. A lit tile keeps the ordinary hairline, because an accent border is what
says *which tile you are at*, and a ring already drawn round everything that is
switched on has stopped being a ring that moves as you walk.

**A tile that knows a bool about itself is a switch**, however the config
happened to say so: `control = "toggle"` is one way, and an action the daemon
can ask a question about - `lock:toggle`, `keep:toggle`, a listed device that
knows it is the current one - is the other. From a sofa they are the same tile,
a thing that is on or off, and they are drawn the same. They were not: a
declared toggle filled its card and an action toggle put a tick in its corner,
which on one page read as two unrelated facts. `switchable` is the one question
now, and a control that draws its own picture is not one of these - `media`
carries `on` for *playing* and says so with the mark it already draws.

**A lamp at the foot was a third channel, and it is gone.** It was a disc
beside the name, the height of that name's ink, the accent when the tile was on
and a dim share of the ink when it was not - the status said in the one channel
that does not rest on a contrast, for the theme whose accent sits close to its
surface and leaves a tinted ground and a lit mark both saying little. Against
every theme that does not, it was a full stop nobody had asked a question in
front of: the tile was already lit, the mark was already in the accent, and the
disc said it a third time in the corner the name then had to be held clear of.
`lampReach` went with it, so a name and its second line take the tile's whole
width again. A state drawn twice is not a state said twice as well.

What carries it is the pair above: the ground and the mark. The tick that used
to sit in a tile's top corner stays gone for its own reason - one state wants
one mark, and a tick at the far end of a tile is the furthest point from the
name it is about - and that corner is left to the chevron, which says there is
a page behind the tile.

A toggle keeps its mark for that reason, where every other control drops one:
`holds` drops the mark because the control *is* the picture, and a toggle's
picture is the mark. What it costs is that an off toggle looks like a tile that
merely does something - the design pays that too, `CLIP` and `SHADER` sitting
beside a lit `MIC LIVE` and looking exactly like it unlit. The trade is that
*on* is the state worth seeing across a room, and a tinted ground under a lit
mark is seen across one without spending the bar's word to do it.

`assets/shapes/switch-*.svg` stay generated and unused: a settings row is
still the shape they are right for, and this surface has no rows.

**The selected tile is lit, not just outlined.** Its face is a gradient with
one source above it - brightest along the top edge, a third of that a quarter
of the way down, gone by a little over half - which is how a leaf held against
a window looks, and what still says *focus* at a distance where a one-pixel
ring has stopped being a ring. Drawn as a gradient on every tile rather than a
colour on some: `ground.face(extra)` answers the same three cases the flat
tint always did and an unselected tile ignores `extra`, so its four stops come
back identical and the gradient it draws is a flat fill. The falloff is not on
the ladder and is not a setting - it is the shape of a drawn light, and it
changes when the light is redrawn.

**Every tile carries an edge, not only the selected one.** The ground under an
unselected tile is the ink at six percent, which is a tile on a dark theme and
nothing at all on a light one - six percent of near-black over near-white is a
shade the eye does not find, and six tiles that cannot be found read as a
scatter of labels rather than as a grid. So the fill is what makes a tile
comfortable and a hairline at fourteen percent is what makes it a tile. Off
the ink rather than off `menu.border`: that key is what the card's *frame* is
drawn with, and a theme that set it has said nothing about what a tile is
edged with. `Hud.qml` draws the same edge on the same ground, where there is
no card behind the tiles at all.

The outlines are drawn art, generated from `assets/shapes/ground-*.svg` into
`shell-plugin/TileArt.qml`. A tile is `w` cells by `h` rows, though, and a
shape scaled by one factor cannot be a rectangle of any aspect - the rule the
slider's travel and the dial's shaded zone are not drawn under. So a ground is
**the corner as drawing and the four edges as a number**: the same quarter set
at all four corners, rotated rather than mirrored, with straight lines run
between them. `docs/components/assets.md` is the mechanism.

How far that corner reaches into the tile is `metrics.radius.tile`, and that
is **one base stepped by the ladder** rather than a number of its own. There
were two unrelated answers before: `Style.cornerRadius` drew the card and the
bar, `[menu] tile_corner` drew the tiles, and on a setup that rounds nothing
- Omarchy ships as one - a square card held a page of rounded tiles.

The base is the compositor's when it has one. `decoration:rounding` is this
desktop's own answer to how hard a corner is rounded, and a surface that
picked its own would be the one thing on screen not answering to it. Where it
rounds nothing it is saying that about *windows*, and a tile is not a window -
so `[menu] tile_corner` is the base there, which is the job it now has: not a
tile's radius, but the base the compositor has when the compositor has none.

Two rungs are named, because two have call sites. `radius.card` is
`Style.cornerRadius` raw, square included, and anything that reads as a window
takes it - the menu's card, the guide's. `radius.tile` is the base, scaled,
and everything inside a card takes it: a tile, a nav card. Anything between them
is `metrics.rung(metrics.radius.tile, n)` like every other size off the named
ones. A pill never joins the ladder: a switch knob is round because it is
round, and `height / 2` is how that is said. The sentence used to name the
slider's trough beside it; there is no trough now - see **The travel** above.

A cell is `[menu] columns` wide and `[menu] cell_height` tall, and both travel
in the payload for the reason every geometry setting does: the shell cannot
read the config. A tile shorter than an icon over a label **drops the icon**
rather than pushing the label out past the ground it is drawn on - the label
is the half that says which tile this is, and `cell_height` being a setting is
what makes a tile that short reachable at all.

**`cell_height`'s default is a rung of the silver ladder, and it has to be.**
A tile's insides are on that ladder - the gap under a label, the mark above
it, the chevrons either side of a value - so the room they need is decided by
it too, and a switch and its label come to a little over forty pixels. A cell
shorter than its own contents does not make them smaller: `Column` has no
clip, so they hang over the edge of the ground the tile is drawn on. It is the
one setting that moves when the ladder does, which is also why it is the one
whose default is worth re-deriving rather than nudging.

Settings: `[menu] title`, `clock`, `columns`, `cell_height`, `bias`, `keys`,
`tile_corner`, `press_ms`, `countdown`,
`repeat_delay_ms`, `repeat_rate_ms`, `group_settle_ms`, `list_timeout_ms`,
`list_limit`, `socket`,
`[[menu.head]]`, `[[menu.items]]`, `[bindings.menu]`.
