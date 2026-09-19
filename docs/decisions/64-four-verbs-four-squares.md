# 64. Four verbs drawn as four squares · ✅ Done · M

Asked for from the sofa with a picture: *menüde örneğin button style için şu
component kullanılmalı, work altında tasarımı da var, bu hali anlaşılmaz duruyor.*
The picture is `Console OS v2 UI mockups`' Power cell: a heading, three verbs
one to a line, the one in front on a ground, and a line along the foot.

The shape of what was wrong is a width. Item 50 made the menu a grid because
**a list says every row is worth the same** and what is playing is not worth
the same as the row beside it - which is true, and it cut the other way for
the rows that have nothing to be worth. A verb has no value to show, so a cell
spent on one says a single word, and the two pages where that lands hardest
say it plainly: `System` draws `Lock`, `Suspend`, `Logout` and `Reboot` as four
identical squares, and `Display` draws `Scale down` as `Scale do…` and
`Screensaver` as `Screensa…`. Four cells, four words, and an elision in two of
them.

`control = "rows"` is the answer, and it is a **card that holds a page rather
than opening one**: the `items` under it are drawn inside it, and each row has
the card's whole width to be as long as it is. It is not a submenu with the
drilling taken out - a submenu is a page you go to and come back from, and its
rows get a card each. These are already in front of you.

**It was built without a `taken` and that was wrong**, which the sofa found in
one press: *a'ya basmadan yukarı aşağı seçememem lazım, altta bir kart olsa ona
gitmesi beklenir, kendi içinde bir alttaki seçeneğe değil.* Walking the rows
with the page's own up and down is cheaper and reads fine on a card with
nothing under it. Put a tile below one and **down means two different things a
cell apart**: the next row here, the next card there, and the tile a thumb was
actually reaching for two presses further on. No page can be walked that way.

So a card is entered, and `TAKEABLE` already had the shape: `entered` is
`taken` narrowed to one axis. A slider took both and answers left and right; a
card took the one that runs down it and answers up and down. A goes in, A runs
the row, B comes out of the card without coming out of the page, and the row
you were on is waiting the next time. The walk does not wrap, for the reason
the grid does not.

**And the marks settled on a spine and a pointer**, asked for with a picture:
*bu itemlarin solunda bir cizgi olsa ve aktif olana dogru bir ok olsa ici dolu
cizgi ile birlesik nasil durur?* - and then *a'ya basili degilken de aktif
olani gostersin.*

The line is structure: it is what makes a stack of words read as a list rather
than as four labels that happen to be under one another, so it is there
whether or not anybody is inside the card. Every row draws its own segment and
the spacing between rows is 0, because a single `Column` child asking for the
`Column`'s own height is a binding loop - the one that happened drew a line
down the whole card with no rows on it.

The **pointer** marked the cursor at first - drawn either way, dim outside the
card and accent in - and that lasted one pass. From the sofa: *cizgi gibi ok da
surekli cizilsin aktif secili bir item varsa, arka plana da gerek kalmayacak
boylelikle. a'ya basinca aktif olana soluk bir arka plan ver.*

Which is the jobs the right way round. The card had **one line with a mark on
it** saying where A would land, and **a ground two pixels away** saying which
row was in force: two answers to *which row matters*, drawn at the same place
in the same row. Give the persistent mark the persistent state and the
transient mark the transient one and both become readable at a glance - the
pointer is the row in force, drawn always and on a card nobody has selected,
and the ground is the cursor, faint and only once A has gone in. A card of
verbs has no pointer at all, because nothing on it is in force.

The ground's left corners are square, so it meets the spine rather than
curving away and leaving a sliver of card between the two.

Two last measurements, both `Metrics.silver` and both asked for by eye from the
sofa. **The pointer's sides**: it was near enough equilateral and read as a
squat blob on the line, because a mark whose flat edge is the line it stands on
wants that edge to be the long one - base over length is the ratio now. And
**the ends of the spine**: the line carries on past the first row and the last
one and is capped at both, every arm the stroke weight set against itself at
the same ratio. A line that began exactly at the first row's top edge began
nowhere; it read as the edge of the ground behind it rather than as a thing of
its own.

The caps turned **right** at first and that was one shape too many: two of them
facing the same way are a bracket, and a bracket *holds* what is inside it,
which is a claim about the rows. A `T` at the head and its mirror at the foot
is a stop instead - it says the line ends here and nothing about what the line
is next to.

**And then the mark on the line stopped being a drawing.** A pointer beside a
line that already changes colour at that row is the same thing said twice - one
of them a whole shape, on a card whose entire argument is that a row has
nothing to show but its name.

What replaced it first was **weight**: the lit length a hairline wider. That
was the wrong silhouette and the sofa found the second half of it before the
first - *bence 1px daha artsin ortali durmuyor*, because growing on one side
alone moves the line off its own centre. Centred it was honest and still wrong,
for a reason the fix makes plain: a line that changes *weight* for one row
reads as the line, not as the row. Something **leaving** the line reads as the
row.

So the mark leaves the line at that row, reaching as far sideways as the caps
reach along - one distance on the card rather than two that are nearly the
same - and centred on the row so it marks the row rather than a place in it.

It was a flat **stub** first, and a stub is a line crossing a line: two strokes
of the same weight meeting at a right angle, which is what the caps at the ends
of the spine already are. It is a **wedge** now, wider where it leaves and
flat at the line's own weight where it arrives. A taper is not a second cap: it
says the mark comes *out of* the line rather than across it, and keeping the
tip flat keeps what it reaches a measurement rather than a point. The rise
where it leaves is the reach at `Metrics.silver`, which is the proportion a
mark whose flat edge is the line it stands on wants.

Which is a triangle again, four marks later - but computed from the spine's own
numbers rather than drawn, so it follows the line at any scale. The drawing was
never the part that was wrong.

`rows:point` left `assets/shapes/` on the way. Three drawn marks were tried
here and none survived - a tick at the far end of the row, a radio ring at the
head of it, and the pointer - which is worth writing down next to the rule
about never hand-drawing a badge: that rule is about *what* a drawing is made
of, and says nothing about whether a drawing was the right answer at all.

And the `T` found the ratio in the wrong place, spotted by eye and confirmed
with a pixel scan: *solu ve sagi uzun gibi, silver ratio olduguna emin misin.*
It was, and on one **arm** - which is half a crossbar, so doubling it for the
cross left the cap 12 across against 5 along. The quantity is spent once now:
the line carries on past the rows by the stroke at silver, and the cap is as
wide as that, half either side.

**Two overlaps, and both are the same fault.** A corner's two bars start from
one origin if you write them the obvious way, and the cursor's ground fills the
row from its left edge, which is where the spine is. Every ink here is the
theme's own at a share of itself, so a thing painted twice is a thing painted
darker: the pixel where the corner's bars crossed was the brightest on the
card, and the spine changed colour for the length of whichever row the cursor
was on. Neither was a drawing decision - both were two things asked to occupy
one place. The horizontal bar takes the outermost weight and the vertical
starts under it; the ground starts where the spine ends, and so do the sweep
and the press ring.

- **The drawing had to say it twice.** A card nobody is inside draws **no
  cursor** - a cursor would promise a walk that press does not make. And an
  entered card is not *lifted*: filling with the accent and cutting its corners
  is what a tile out of the page's order does, and it made the card the loudest
  thing on the page with the least readable rows on it.

  It takes a **heavier ring** instead - and that found a real fault two moves
  later. Four pixels cut the border (*a'ya basinca border kesiliyor*): the halo
  sat `ring + its own half` outside the tile, in the gap between cells, so at
  four it went past the gap and the grid clipped it on the leftmost tile of a
  page. **The sum was wrong rather than the ring.** The ring is drawn *inward*,
  straddling a path inset by half its weight, so it occupies the first `weight`
  pixels inside the tile and the halo has only the box to clear - a one-pixel
  error while every ring was a hairline, and a four-pixel one the moment one
  was not. `halo.out` is a hairline clear of the tile now and a ring may be any
  weight without moving it.

  Taking the ring away instead was the wrong repair, and it said so at once
  (*kartin secildigi anlasilmiyor*): the rail says which **row**, and a
  two-pixel mark on one row is no answer at all to which **card**.

**And then the two marks on a row, which took three passes.** Asked for from
the sofa twice: *yandaki tik bir sey anlatmiyor ve fontlar cok soluk*, and then
*soldaki tick de kotu sadece arka plan olsun, a'ya basinca solda 2px genislikli
bir cizgi olsun aktif olani gosteren.* Both were right and the second one is
the better design.

- **A tick at the far end of the row** was the grid's own mark, and out there
  it says nothing: a tick has no second state, so a reader sees one row
  carrying something and three carrying a gap, at the opposite end of the card
  from the words it is about.
- **A radio ring at the head of each row** was the design's, and it says more -
  an empty ring beside every row says *these are alternatives* before it says
  which one. But it is a second drawing for something the row can simply
  **be**, and it took the slot a row's own glyph wants.
- **The ground says it now**, and the cursor is **two pixels of rule** down the
  row's left edge, drawn only inside the card. One mark each, and the card's
  own ring and ground go back to meaning the card is selected rather than
  saying the same sentence twice at two sizes.

**The inks were the other half of it, and they were a real fault.** The surface
had picked a number at each call site - 0.36, 0.42, 0.52, 0.58 - and the design
publishes exactly three levels, each *measured* at 4.5:1 or better on the
ground it sits on. A second line at 0.36 is a sentence you have to walk onto in
order to read, which is a line not doing the job it exists for. `inkMuted` and
`inkDim` are those two levels named once, and the call sites take them.

- **The row cursor is a second cursor, not a second kind of `selected`.**
  Everything the page does to a tile - carry it, hide it, resize it, scroll to
  it, ring it - is still done to the tile; only a press reaches further in.
  `acting` is that one question, and it is what makes `confirm`, `stay` and
  `repeat` the row's answers. The legend asks it too, so `A` reads `Hold to
  confirm` over `Full shutdown` and `Pick` over `Rest mode` beside it, and the
  hold fills the row rather than the card.
- **What a row may be is a short list, and the parser holds it**: a verb, with
  no page under it, no control on it, and no `from` listing to fill it. Each
  of those is a tile that could never draw itself, and `omapad check` is where
  that gets said. A card spends no X or Y either - a key is spent while a page
  is in front, and nothing is ever in front of a card of rows.
- **Found on the way**, and it took the daemon down twice a second rather
  than quietly: `view_state` asked the daemon what every tile with a `control`
  was *on*, and the daemon's answer starts by unpacking the pair a tile reads
  from. A card of rows is a control that reads nothing. The condition is
  whether a tile **reads** something, not whether it is a control, and it has
  a test now.

**And then the first page that asked for one**, from the sofa: *system altında
game mode kartı var ve bu kartta yeni yaptığımız tasarımı kullanmak
istiyorum.* `System › Start in` was a `choice` - a card reading `Game mode`
with a chevron either side, which is a card you have to press to find out what
else there is. It is a card of two rows now, and converting it settled the one
thing the control was still missing.

**A row carries its own line.** Item 50 named the price of a choice tile: it
shows one value, so *the sentence saying how the choices differ has nowhere to
go*, and `Button labels` and `Profile` kept their submenus for exactly that. A
row is as wide as the card it sits in, so it has somewhere to put one - which
makes a card of rows the third shape, and the only one that pays nothing. The
three answer three questions now: a **submenu** is for choices that are a place
of their own, a **choice** for two values whose names are the whole difference
in one cell, and a **card of rows** for a short list you want to *read* rather
than press.

- **Three cells, not two.** Forty characters do not fit in two beside a tick,
  and `pad-menu.md` says so where somebody would write the next one.
- **A row that sets something ticks**, by the same `state(action)` a tile is
  asked, so a card of them is a list of choices rather than a list of guesses -
  and `stay` is what keeps the menu up while the tick moves.
- `Button labels` and `Profile` are the two this now unblocks, and they are
  deliberately not converted here: that is a face-button question and it gets
  its own pass.

`README.md` and `pad-menu.md` carry the worked example both ways round - the
verbs, and the settings. The test for *when* to reach for one is the elision: a
run of tiles whose labels do not fit a cell and none of which has a value to
show is a card of rows.

**Then the rest of the tree, from a list the sofa picked off.** Four pages
converted, and each was a different argument for the same shape:

- **`Windows`** was four cells reading `Fullscre…`, `Next win…`, `Float / …`
  and `Close wi…` - four words cut in half on a page two thirds empty. The
  whole group is one card now.
- **`Controller › Button labels`** and **`Profile`** were submenus, and item
  50 said why they had to stay ones: a `choice` tile shows one value, so the
  sentence saying how the choices differ had nowhere to go, and getting either
  wrong scrambles the face buttons. A row is as wide as the card, so it keeps
  the sentence - and all of them are in front of you rather than a level down.
- **`System`** was five power verbs as five squares, which is the scatter the
  control exists to end. `Omarchy menu` stayed a tile: it is a door out of this
  menu rather than something the machine does.

**And the three under Power stopped being a hold**, asked for from the sofa:
*basili tutmasin 10 9 8 diye geri sayim yapsin b ile cancel edilebilsin.*
Which is right, and it splits one question into two.

A **hold** is the right gesture where it is already in the hand and is over in
a second - `Close window`, with the window in front of you, wanting an answer
now. It is the wrong one for logging out. What those three do is take the
screen away, and being sure about that is not something to do with a thumb: it
is something to be given long enough to change your mind about. Holding A for
ten seconds is not a gesture anybody makes.

So `countdown` is a second answer rather than a replacement. A is an ordinary
press, the row prints `[menu] countdown` seconds beside its name, and B stops
it - the legend says `Cancel` while it runs. Three things it does not do: no
tick per second (a pad buzzing ten times through a decision is the opposite of
what the wait is for), no `[confirm] scale` (that is for a hand that cannot
keep a button down, and this asks nobody to keep anything down), and no
stopping on a cursor move - ten seconds is long enough to want to look at
something else, and a count that died because a thumb brushed a stick would be
worse than no count at all.

**Reboot and Shutdown are written twice, and that is the point**, asked for
from the sofa: *reboot ve shutdown bu grup disinda ayri 1x1 tile olarak da
dursun.* They are rows in the card like the other three, and they are also the
two anybody walks to that page for - so they are a cell each as well, where a
thumb reaches them without going into a card first. Item 48's argument about a
row you have to go and find, spent on the two rows it is true of.

Two things that had to follow. **Both copies count down** - a press guarded in
one place and cheap in the other is worse than not guarding it - which meant
the number had to be drawable on a *tile* as well as on a row, in the corner
the tick and the chevron share. And **each copy needs its own id**: the flash,
the countdown and the fill all name a tile by id, and two things answering to
one name is two things lighting up for one press.

**And a card can list**, which the first pass refused. `Audio` was `Devices`
opening on `Output` opening on the outputs: two presses in before a name you
could pick, and each of those pages held exactly one thing. It is two cards on
one page now. The refusal had a real reason - a listing is read at the press
that enters the page it fills, and nobody enters a card - and the answer was a
second lifetime rather than a special case: `menu_cards_settled` reads the
listing cards on the page in front once the page stops changing, on the bar's
own `group_settle_ms` and for the bar's own reason. A card is seeded with its
`empty` words so it is never blank while the command runs.

**And a listing that finds one thing is not a list**, said from the sofa the
moment it was on screen: *tek secenek varsa boyle gorunmesin, output ve
microphone kotu gorunuyor, kullanici da secim yapamaz zaten.* One pair of
speakers in the room is one row - picking it sets what is already set - and a
column of alternatives with a single alternative in it is a card of furniture
round a fact. It is a **reading** then, and drawn as one: the heading names it,
the line is the answer, and `takeable()` refuses the card, which is the
`readout` tile's own argument one control along. Plug a television in and the
second row makes it a list again. Only a card that *lists*: a card somebody
wrote one row into meant that row.

**Found on the way**, and both were the same shape of fault - a field asked of
the wrong thing:

- `_row_state` did not carry a **listed** row's own `on`, so the card of
  outputs drew every device unfilled. A listed row knows its own answer; the
  daemon can ask a setting what it holds but not a device whether the sound is
  going to it, and the tile payload had said so for a year.
- `choose()` moved the fill among the page's tiles and not among a card's
  rows, and then among *every* card's rows when it was taught to - picking a
  speaker said something about which microphone was in use.

**And one that cost an afternoon of drawing**: a `readonly property int left`
on the row delegate. `Item` has a FINAL `left`, so the whole component failed
to compile - and the way that fails is the panel never coming up at all, with
one line about it in `qs -p /usr/share/omarchy/shell log` and nothing anywhere
else. The rule in `qml.md` about reading that log first is what found it.
