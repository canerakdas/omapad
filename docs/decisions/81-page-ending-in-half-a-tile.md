# 81. The page that ended in half a tile · ✅ Done · S

Asked for from the sofa: *menude ekrana sigmayan tile'lar kesik gorunuyor
sadece belirli bir kismi gorunen tile'lar icin shadow gibi bir sey mi eklesek
sagdan veya daha iyi bir fikrin var mi, tam grid sayisi kadar gostermek de
mantikli olabilir.*

The second half of that is the answer, and it is item 25's answer: **cut to
whole cells.** A gradient down the cut column would be a gradient over the one
tile on the page nobody can read - a tile centres its ink, so the visible part
of a cut one carries none at all, which is why a cropped page ends in a band
of nothing rather than in "there is more below". That was measured against
Omarchy's own menu once and fixed for the card's rows; it was never applied to
the columns, and the fullscreen page had been exempt from it since the day it
was added.

- **One rule, two axes, both shapes.** `wholeCells` is the arithmetic item 25
  wrote inline, and `shownRows` / `shownCols` are what a band may show against
  what it was given. The card is sized to the page it holds, so there the cut
  stays in the height and the width themselves - that is what keeps its foot
  off the floor of the screen and its last column off its own border, and what
  the cut leaves over is a narrower card, which is centred. The fullscreen
  page keeps the room it was given, because the legend sits under it and a
  legend that floated up under a short page would not be at the foot of
  anything; there the clip stops short inside that room and the remainder is
  air where nothing is drawn.
- **The bar is cut the same way.** A nav card is a cell standing on the grid's
  own columns an inch above the tiles, so a half card at the right edge is the
  one place the two bands would disagree about where the page ends.
- **A fold that lands in a gap came out of it for free.** `reveal` scrolls the
  least it can to bring a tile and its halo into view; against a viewport that
  is a whole number of cells, both of its answers are a multiple of the cell
  pitch. Nothing in `reveal` changed, and there is no page snapping to write.

**And the measurement was worth taking.** This monitor is 1920x1200 at a
Hyprland scale of 1.25, so the surface is drawn on 1536 logical pixels - and
the shipped `columns = 12` at `cell = 128` comes to 1712 before the fullscreen
page's 91 either side, which leaves room for **nine of the twelve columns**.
Three of them have been living past the fold. That is `config.toml`'s own
arithmetic - `columns * cell * scale + (columns - 1) * 16 * scale` against the
screen less twice the padding - and the screen it is written against is 1920
with nothing scaling it. `cell = 96` is what puts the whole page on this one.

**The one cut left is a tile wider than a cell.** `Workspace lock` is three of
them, and on the card the fold falls inside it. A fold between two *tiles*
cannot be a rule: it would be a different width in every row and would move as
the page scrolled - so it is between two cells, and a tile that spans it
carries on past the edge. What settles that page is the paragraph above, which
is a setting rather than a drawing.

**Verified live** at both shapes: the fullscreen page ends after a whole
column where it used to show a sliver of the next one, and the card comes up a
column narrower and centred. No fade and no row of dots - what says there is
more is still the page moving when a thumb pushes into it.
