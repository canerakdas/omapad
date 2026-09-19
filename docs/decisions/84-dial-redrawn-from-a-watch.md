# 84. The dial, redrawn from a watch · ✅ Done · S

Asked for from the sofa, with a drawing attached: *bu saati chrono'ya
uyarlayabilir miyiz, ai oldugu icin biraz kotu gorunuyor ek olarak saat 3
yonundeki tarih alani olmayacak.* The drawing was a generated line-art watch -
a case with a chapter ring inside it, a minute track, applied batons at every
hour with the twelve doubled, outlined hands, a sub-dial at six and a day-date
window at three.

**What was asked for is the dial's language, not the drawing.** The file is a
render at 700 pixels; the tile is two cells square, which is about 200 on this
screen and less on the HUD. So each part of it was taken on whether it still
says anything at the size it will be drawn:

- **Twelve applied batons, and the twelve doubled.** This is the whole of it.
  74 drew the quarters as bars and the eight hours between them as dots, on
  the grounds that a bar at 30 degrees could not stand on a whole unit - and
  that is the hands' own exemption read the wrong way round.
  `ShapesSitOnTheGrid` is about *a straight run parallel to an axis* landing
  on half a pixel; a baton at 30 degrees has no such edge to land badly, which
  is exactly why the hands are exempt. Twelve of one mark also gives the face
  the one thing a ring of dots cannot: a doubled twelve, which says which way
  up the dial is without printing a number on it.
- **A hairline case with a chapter ring inside it**, against 74's single rim
  two units thick. A rim as heavy as a hand made the face read as a ring with
  sticks in it; two thin ones read as a case, and leave the marks the heaviest
  thing on the dial - which is what a glance from the sofa is looking for.
- **Hands with a point and a tail.** Batons tapering to a tip, the hour short
  and wide against the minute long and thin, each with a short tail past the
  pivot. Now that all twelve marks are batons too, the taper is what separates
  a hand from a mark; a pill among batons was a mark that happened to be
  moving.
- **The hub is a ring** rather than a disc, which is what covers the corners
  five rotating batons make at the middle while still showing the dial through
  it.

Three things in the reference were left out, and each for a reason the
reference cannot have: it is not drawn at the size this is.

- **The day-date window at three.** Asked for by name, and it was never
  available anyway: three o'clock is where the minutes measured are counted,
  and a date is a second thing to read on a face that already has five hands
  on it.
- **The minute track.** Sixty ticks between the two rims looks like an
  instrument at 700 pixels and like a grey fog at 96, which is the size the
  tile is actually glanced at. It is also the one figure on the dial the grid
  cannot hold: a tick is a fifth of a unit wide, and the four at the cardinals
  are straight runs parallel to an axis, so they would have to be two units
  wide - six times the others - or be left out, which is a track with four
  holes at the four places anybody looks first.
- **Outlined hands.** Drawn and looked at: at 200 pixels they are close to the
  reference and at 96 they are wire. A hand is the figure a glance is for, so
  it stays solid; the drawn comparison is what settled it rather than an
  argument.

**The registers grew with the dial.** The marks now begin at 12 of the face's
20 rather than at 10, so `Clock.qml`'s two register numbers - how big one is,
how far out its middle sits - moved to 6.8 and 7.4. They are the same
decision they always were: the room between the hub and the marks, with the
drawing inside unchanged, because a register is a disc and a hand wherever
the three of them are put ([75](75-clock-that-could-measure.md)).

**And one test got stricter by being loosened.**
`AnnuliSurviveEitherFillRule` counted the subpaths of a ring and insisted on
two. A rim drawn as a case and a chapter ring is two rings, so it now checks
each pair in turn - an outer and its hole, wound against each other - and
fails a shape that came out odd, which is a ring somebody drew without a
hole. The old form would have passed a four-subpath face drawn entirely the
wrong way round; this one cannot.

Everything here is `assets/shapes/clock-*.svg` and one regeneration
([`../procedures/pad-badge-art.md`](../procedures/pad-badge-art.md)); no
daemon code moved, and the chronograph's state, its pusher and its wire
format are as 75 left them.
