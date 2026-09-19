# 53. Six sizes that are all the same size · ✅ Done · M

Asked for from the sofa: *menünün stilini toplayacağız, öncelikle spacingler
ve tipografi için silver ratio kullanacağız. sol köşede sade saat yazsın, gün
bilgisi saat altında.*

**The menu had no scale of its own.** It took Omarchy's - `caption` 10,
`bodySmall` 11, `body` 12, `subtitle` 13, `title` 14, `heading` 16 - and used
five of the six on one card, plus fifteen loose `metrics.space(N)` calls
between 2 and 40. That is a scale designed to be read at a keyboard, where a
pixel of difference *is* a difference. Across a room it is one size printed
six ways, and the card had no hierarchy at all: the clock, a tile's label and
a tile's detail line were within three pixels of each other.

So `Metrics` gained a ladder of its own, and the silver ratio sets the rung.
Nine gaps (3, 4, 6, 8, 11, 16, 23, 32, 45) and five type sizes (10, 12, 16,
24, 47), both anchored at the *small* end - the smallest thing a surface
prints is the one that must not shrink, and a ladder hung from body text has
nowhere legible to put a detail line.

**The ratio answers it twice, at two rates, and the first attempt did not.**
Space climbs by √2, the ratio less one: a gap either separates two things or
it does not, nobody reads the difference between 14 and 16 pixels of air, so
it wants few rungs far apart - and √2 doubles in exactly two of them, which
keeps the ladder landing on 4, 8, 16, 32 rather than drifting off the familiar
numbers and taking every rounding decision with it.

Type was √2 as well for about an hour, and the sofa said so at once:
*yazılar fazla büyüdü, tabler vs onlar standart kalsın.* One rung of √2 above
a 10px mark is 14, so every label, chip and slider name on the card went up
two or three pixels at once - and the reason is structural rather than a bad
anchor. **A √2 ladder cannot hold both 10 and 12, and a surface needs both:**
a detail line has to be smaller than the label over it and still legible from
the same distance, which is a 20% difference, not a 41% one.

So type climbs by the **fourth root** of the ratio, ≈1.2465, and the named
sizes are rungs 0, 1, 2, 4 and 7 - not consecutive, because the ladder is
finer than the set of jobs a surface has. The first three land on 10, 12 and
16, which is exactly where the shell's `caption`, `body` and `heading` already
were. Those three were never the problem; using five sizes within six pixels
of each other was. And four rungs is the silver ratio itself, which is what
makes it that root and not any other: `loud` is `fine` at 1 + √2, and
`metrics.silver` is there for the split a headline over its second line is.

The rest of the value is that this is a *decision*, written in one place,
rather than sixteen call sites each having had one. `metrics.rung` and
`metrics.step` make a size between the named ones say it is a step down the
same ladder instead of being arithmetic that happens to come out right.

**A surface is on one ladder or the other, never both.** `Menu.qml` is across
and says so in its header; the guide, the keyboard, the mapping screen and the
game bar are not yet.

**And what is mirrored from another surface is not on either ladder** - which
the sofa found before the argument did: *menünün sağ altındaki butonların
boyutu da büyümüş, desktop modu ile aynı olmalı.* The legend along the foot of
a fullscreen HUD sits in the game bar's own band, saying the same four words
about the same four buttons, and its badge had gone from 25 to 30 while the
bar's stayed at 25 - so opening the menu resized a row that must not move.
The whole row is `GameBar.qml`'s expressions character for character now:
badge, typed letter, hint word and both spacings. The badge's letter in
particular is sized off the *badge* (0.44 of it) rather than off any type
scale, which is a rule the bar already carries for its own reason - a three
character label has to fit the shape one letter does by being squeezed at one
shared size, not by stepping down one.

Two other numbers stayed off as well: the card's own width, and two stroke
weights.

**And then the ladder was climbed rather than rebuilt**, which is the point of
having one: *saat daha büyük olsun, spacingler artsın silver ratioya göre.*
`vast` moved off rung 6, and the card's rhythm went up a rung with it: the gap
between bands `xl` → `xxl`, the gap between tiles `xxs` → `xs`, a card's own
padding `xl` → `xxl`, and the leading inside a stacked head cell `xxs` → `sm`,
which is two rungs because what it separates is three sizes of one block rather
than two things side by side.

**It went to rung 8 first, and that was a rung too far** - *saati biraz
küçültelim çok büyümüş* - so it sits on 7. Which is the useful thing this item
learned about its own ladder: **the scale decides the steps and the screen
decides which one to stop on.** Rung 8 was tidier on paper, because it made the
top of the ladder the silver ratio twice over, and it was wrong on the wall. A
scale is what stops sizes drifting to whatever looked right that afternoon; it
was never going to say which rung a clock wants, and reaching for the tidy
answer over the legible one is the failure mode of having a system at all.

The fullscreen margin did **not** move, and for a reason worth keeping: it is
a television's overscan, a fact about the screen rather than a proportion of
the layout, so it has no business travelling with a rhythm.

**A tile's insides did not move either, and that turned out to be the wrong
call** - *şimdi menüdeki tile'lara da aynı spacing'leri uygula.* The reason
they were held back was real: a cell is `[menu] cell_height` tall whatever the
ladder does, and a switch grown a rung came to more than a cell at `[ui] scale
= 1`. But the conclusion drawn from it - leave the tiles behind - was the
wrong half of the problem to give way. **A cell shorter than its own contents
does not make them smaller.** `Column` has no clip, so they hang over the edge
of the ground the tile is drawn on, and the old 34 was already a pixel under
what a switch and its label came to; nobody had noticed because a pixel is not
a thing you see.

So the tile's insides went up a rung with everything else - the gap under a
label, the switch, the chevrons either side of a value, the slider's track,
the dial's face, the mark in a carried tile's corner - and `cell_height`'s
default went with them, to 45, which is a rung of the same ladder. **It is the
one setting whose default is derived rather than chosen**, because it is the
room the ladder needs rather than a preference about density, and the comment
beside it now says so. Type was left alone: the ask was the spacing, and the
sizes had already been settled two items ago.

**And the clock became the thing the head is for.** It was `format = "%A %H:%M"`
in a cell one row tall - the day and the time on one line at 13px, in the
corner, saying both at the strength of neither. A `[[menu.head]]` cell now
takes `under`, a second strftime format set beneath the first, and **the
cell's height decides its treatment**: two rows and the first line is set at
the top of the ladder with `under` small and in capitals beneath it, one row
and it is a line of text. So the shipped clock is `[2, 2]`, `%H:%M` over `%A`,
and turning it down is giving it fewer rows rather than a new key.

One cell holding two lines rather than two cells, because the head packs first
fit like everything else here - two cells could land side by side as easily as
stacked. `under` goes with a `format` and is refused under a `from`: a second
line under a command's answer would be a second command, with its own `ttl`
and its own failure to word. The capitals are the panel's and not the
config's - `%A` returns whatever the locale's own weekday is, and casing it is
typography.

**Two things the screen said that the code did not.** The bands of the card
were `md` apart - six pixels, against three between tiles - so the head read
as the grid's first row rather than as a band of its own; they are `xl` now,
five rungs clear of the cell gap. And the head's text carried a tile's inset
without a tile's ground behind it, which put the clock four pixels right of
the first chip and the first tile. A head cell prints on nothing, so it lines
up with the cell's own edge; only the far side is held off, far enough that a
line elides before it reaches the cell beside it.
