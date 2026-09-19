# 74. A clock you can read from the sofa · ✅ Done · S

Asked for from the sofa: *analog bir saat eklemek istiyorum 2x2 olan bir kartin
icinde kullanmak icin bir saat kadrani ciz fonta cevir, akrep ve yelkovan'i
geometri olarak cizebiliriz.* The last clause is the design, and it is the
split this project already draws everywhere else: the face is furniture and
the hands are geometry.

**The font half is the one thing that did not happen, and it never could.**
`truetype.py` exists to turn *letters* into outlines so they can be punched out
of a silhouette, and a clock face has no letters in it - so `clock-face.svg`,
`clock-ticks.svg` and `clock-hub.svg` go through `CONTROLS_TO_DRAW` into
`ControlArt.qml` as path data with that step skipped, which is where every
dial, switch and chevron on this pad already comes from. "Generate a font for
these too" is the obvious reading of what the buttons do and `assets.md` has
said for some time that it is the wrong one; this is the first time somebody
read it that way out loud.

**`control = "clock"` rather than a second kind of head cell.** A tile is
written where every other tile is written, arranged with the gesture that
arranges every other page, and - because the HUD draws a menu page - it can be
left on screen over a game. A head cell is none of those things: it is above
the bar, in the menu, and only there.

Which widened a rule the HUD had: **a tile with something to press is not
drawn**, where it used to say *a tile that is not a readout*. The wording was
the accident, not the rule - what a tile needs in order to stand over a game is
nothing to press, and a clock has nothing to press. Game mode takes Omarchy's
bar away and the bar is where the time was, so the surface standing in for the
bar is exactly where a clock belongs. It is outside the other rule too, without
being an exception to it: nothing publishes the time and nothing could fail to,
so there is no source to have gone quiet and no machine the tile is untrue on.

**Both hands travel as one number.** `mn` is the minute of the day, worked out
in `menu.py` the way the head's own `%H:%M` is - a clock that waited on
somebody else is wrong between draws. An hour and a minute sent separately
could arrive disagreeing about where the hour hand stands at half past, and
the panel would then have to know how to settle that; one number cannot.

**And there is no second hand.** The page arrives every `VIEW_HEARTBEAT`
seconds, so a hand that moved every second would be visibly wrong most of the
time - on the one surface whose whole argument is that nothing on it twitches.
Two hands answer what a glance asks; the head is where the exact minute is.

The face is the gauge's own circle, 40 units and the same square - two circles
on one page at two sizes read as a fault rather than as two tiles - with a rim
two units thick against the dial's three, because this one has hands inside it
and a rim as heavy as a hand draws a ring with sticks in it. Twelve marks: the
quarters as bars, the hours between them as dots, which is also the one mark
on this pad that could not stand on a whole unit and does not have to.
