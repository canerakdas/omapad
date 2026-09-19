# 69. One focus, and a corner that did not fit its ring · ✅ Done · S

Said from the sofa while walking the rebuilt pages: *bir karta hover
yapildiginda kartin kosesindeki radius ile disaridaki ring arasinda bir bosluk
oluyor px perfect degil, ek olarak 2 farkli focus tipi var suan hepsini
tekillestirsek nasil olur.* Two complaints, and they turned out to be one
fault seen from two sides.

**The two focus types were one figure at two sizes.** A selected tile took a
hairline ring; a tile in the hand and a card you had gone into took four
pixels of the same ring. That asks a reader to know the difference between a
thin ring and a thick one before either says anything - and what the thick one
was saying is not *where the cursor is* but *what A is doing to this*. The
design has a mark for that already and it is not a heavier border: focus is a
1px ring plus the rim light, a press is a **2px ring inside the edge**. So
`hit` - which existed, and was drawn for `press_ms` after a press - is now
drawn for as long as the press *lasts*: `acting` is `flashing || taken ||
carried`. The vocabulary is two figures and no exceptions: a hairline outside
says **here**, two pixels inside say **and A has hold of it**.

**And the gap at the corner was the ring's weight, unaccounted for.** Every
figure on a tile is concentric with the ring, and concentric is a radius as
much as a centre: a rounded rectangle drawn `d` pixels outside another one has
to take `d` more corner, or the two run parallel down the edges and part at
the corners - which is where an eye checks. The halo asked for
`radius.tile + halo.out`, which is short by half the ring's weight: half a
pixel while the ring was a hairline, two pixels the moment it was four. The
press ring and the sheen had the same error with the sign the other way.
`tile.concentric(out)` is the sum in one place now and all four go through it;
`qml.md` 8.2.6 is the rule, because this is the kind of fault that is
invisible at a hairline and obvious at four pixels.

Two smaller things fell out of it. `hit.inset` keeps a hairline of the card's
own face between the two rings - touching, they are a three-pixel edge, which
is the thick ring this replaced rather than the two marks it is meant to be.
And the press brightening the design pairs with its inner ring is **not** here:
these faces are translucent tints over whatever is behind them, so
`Qt.lighter` on one is a change nobody can see. If it comes back it comes back
as a measured ground, not as a filter.
