# 80. Four strokes where there was one rectangle · ✅ Done · S

Asked for from the sofa, with the card open: *yatay ve dikey slider'i da
parcalara ayirip font yapabilir miyiz, ek olarak bu checkbox'in da dolu ve bos
halini svg'den font'a cevirebilir miyiz.* And then, to the first answer:
*hepsi tek gorsel/karakter olmak zorunda degil, bolerek kullanalim?*

The first answer was **no, and it was wrong**. What it said is true of the
line - a travel is as wide as the tile it sits in, a drawing cannot stretch,
and `EveryControlIsDrawn` has listed `slider` with no parts of its own since
the day the test was written. What it missed is that the line is not the
drawing: the *strokes standing on it* are, and split into parts each one is a
figure of fixed proportion, which is the only thing the rule was ever about.

- **A figure sized from the line is exact at every scale**, which is the
  objection turned round. A stroke is drawn ten units across - the line's own
  weight - and a whole number of them tall, so the panel hands it
  `spine.weight` and takes the height the drawing asks for: five weights at a
  stop, seven at an end. `Metrics.spine.cross` and `crossEnd` are read back
  off the drawings for that reason, and they are 4 and 6 at this surface's own
  scale, which is exactly what the silver ladder had rounded them to. It is
  the one exemption from `ShapesFitTheBadgeGrid`, and it earns it by being
  sized more strictly than the rule asks rather than less.
- **The split found a bug the comment had been describing for months.**
  "Two arms, and neither of them crosses the line" is what `Travel.qml` says
  about its stops, and what it drew was one solid bar through the line at
  every one of them - every ink here is the theme's own at a share of itself,
  so that square was painted twice and lit. The gap is in `travel-stop.svg`
  now, and `travel-mark.svg` is the same stroke without it, because the
  value's own mark is opaque and has to cover what it crosses.
- **That is the second question, and it is why there are four.** How far a
  stroke reaches is two of them and whether the line runs through it is the
  other two: `end` and `mark` own every pixel they stand on, `end-open` and
  `stop` leave the line's weight of air. A fifth, `side`, is the pair that
  bracket the row in force on a card - the one stroke that leaves the line on
  one side, because what it marks is the length behind it.
- **The vertical one is the horizontal one turned a quarter**, which
  `Metrics.qml` has claimed in a comment since the two were drawn and the code
  has never done: the card's caps were their own pair of rectangles in
  `Menu.qml`. They are `end-open` rotated 90 degrees now, placed by the middle
  of the figure the way a clock's hands are.
- **The key is two drawings, not one with its fill switched** -
  `key-ring.svg` and `key-lit.svg`, on one canvas and one box. Two because
  they are painted in two colours: the ring takes the card's line ink and does
  not light with the row, and the window takes the accent. The ring is wound
  so its hole survives either fill rule, the way every annulus here is.

**What it cost** is the key's corner, and it is worth saying out loud rather
than discovering later: it was the row's stepped a rung down and capped at a
quarter of its own side, and what is drawn is that cap. A theme that rounds
nothing at all keeps a rounded key now. The trade is that the figure a hand
reads at 16 pixels is redrawn in `shapes/` instead of computed in a binding -
which is the whole of what was asked for, and what it buys is that the filled
state can stop being a smaller square without a line of QML changing.
