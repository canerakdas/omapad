# 47. The badge that had never been drawn for what it carries · ✅ Done · S

Item 46 put R3 on the game bar and the drawing was the first thing seen:
*button olarak r3 baya kotu gorunuyor, duzeltelim. border varsa outline belli
bile olmuyor yazi da sikismis halde*. Two faults, and they had been there since
the badges were drawn - R3 had simply never stood anywhere anybody looked.

**The letters.** `fit` comes down in 4% steps until a label clears
`MIN_PADDING`, which is right for a shape it is handed and wrong for a shape
that ships. `L3` came out at **12.39** units inside a 26-unit circle where
every other badge is punched at **13.44**, with **0.25** units of air - two
characters running edge to edge next to an `A` sitting in three. `stick.svg`
was a circle *smaller* than a face button carrying *twice* the characters;
every other two-character label on the pad - LB, RT, ZL, R1 - has a wide shape.
So the stick got one: a pill inside its own rim, and all four of its labels are
at the full cap with air around them.

**The rim.** It was a stroked circle outside the filled one, and a stroke's
weight is in *pixels* rather than in the shape's units. So it stayed a hairline
on a badge twice the size - and in the stencil badge style, where the surface
paints the shape solid and every surface drew the rim in the *background*
colour, it was outside the fill with nowhere left to be. Painted background on
background: the style the reporter had turned on was the one where the rim did
not exist. It is an annulus in the same fill now - three subpaths wound the
opposite way in turn, so the same shape comes out under either fill rule - two
units thick at every size and in both styles. `Shape` raises on a stroke, and
`ring`/`ringWidth` are gone from `BadgeArt` and all four surfaces.

**56 by 40, and that is not a free choice.** A badge is `unit` tall and
`round(unit * w / h)` wide, scaled by one factor taken from the width, so a
shape whose aspect the unit does not divide stands a fraction of a pixel off
its own box and every flat edge in it is painted grey. `Metrics.badgeGrid` (5)
is what makes the division come out whole. The stick was drawn 44 by 32 first,
which wants a unit divisible by *eight*, and nothing would have said so - the
symptom is a slightly soft badge. `ShapesFitTheBadgeGrid` says it now, and
`LabelsStandAtOneHeight` says the other half: a shipped shape that makes `fit`
shrink its label is the wrong shape for what it carries.
