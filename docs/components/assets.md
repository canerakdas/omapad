# Button art - `assets/`

The controller buttons omapad badges with - a face button, the shoulders,
the triggers, a stick click, the D-pad, the small system buttons - drawn once
and
generated everywhere else.

```bash
python3 assets/generate.py       # after editing anything in shapes/
python3 assets/sounds.py         # after changing a number in sounds.py
omarchy-restart-shell            # so the shell picks up the new ButtonArt.qml
```

## What is where

| Path | What |
|---|---|
| `shapes/` | **The source.** Hand-drawn SVGs, one per control, unlabelled. Edit these. |
| `shapes/dpad-*.svg` | The D-pad's drawn labels rather than controls: one arm of `dpad.svg` lit. |
| `shapes/ps-*.svg` | What a PlayStation pad prints on its face buttons, set into `face.svg` the way a letter is. |
| `shapes/sys-*.svg` | What every console prints on its small buttons, set into `sys-round.svg` or `system.svg`. One drawing serves two consoles: Menu on an Xbox pad and Options on a PlayStation one are the same three bars - but not the same button, so the marks share a 48x40 grid and the silhouettes do not. |
| `shapes/sys-round.svg` | The small round button, which is every one of them but PlayStation's Create and Options. |
| `shapes/sys-guide.svg` | The Xbox button, drawn 36 of 40 against the 24 the rest get - it is larger than every other button on that pad, face buttons included. Nothing else earns it. |
| `shapes/system.svg` | The oblong: Create, Options, and the bare shape the shell types a word into. |
| `shapes/stick.svg` | The stick, seen from above: one pill, 56 by 40. Wide because of what it carries - `L3` is two characters, and a circle the size of a face button will not hold two at the cap the rest of the pad is set at. It had a rim once, and lost it: every other badge on the pad is a solid silhouette with its label punched out, and one that was a ring read as a different colour in a row of them. |
| `shapes/dial-*.svg` etc. | The parts a **control tile** is drawn from - a dial, a clock's face, a switch, the chevrons, the transport, the grip. No labels on any of them, so no font. |
| `shapes/dial-pointer.svg`, `shapes/dial-notch.svg` | The knob's two turning figures: the pointer at the value, and the mark under a stop. Both drawn standing at twelve on the dial's own canvas, because a silhouette that is the same at every value is a shape and the value only decides the angle. The knob's *rim* is `dial-face.svg` - it is the same circle as the dial beside it and the clock under it. |
| *(the knob's scale has no row here)* | **And that is the entry.** The ring and the run of it the value has covered are an arc, not a drawing: the run grows with the number, and a track drawn once with that run computed against it would be two drawings of one figure. `dial-notch.svg` is drawn to hang off where that stroke ends, so a knob given a wider scale (`Knob.qml`'s `scaleRadius`) needs the notch redrawn with it. How many notches there are is the panel's too, which is where a knob parts company with a clock: twelve hour marks are the same twelve on every clock ever drawn, where a knob's marks are its *stops* - three on a ring reading a list of three, six on one reading a ladder of six. |
| `shapes/travel-*.svg` | The strokes that stand on a line - a slider's, a stepped slider's, a reading's, and the same line stood up down a card of rows. **Four of them, because one stroke answers two questions**: how far it reaches (five line weights at a stop, seven at an end) and whether the line runs *through* it or stops at it. `stop` and `end-open` leave the line's own weight of air between two arms, because every ink on these surfaces is the theme's own at a share of itself and a bar run through the line would light that square twice; `end` and `mark` own every pixel they stand on. `side` is the fifth and the odd one: the pair that bracket the row in force on a card, out of one face of the line, because what they mark is the length behind them. Drawn ten units wide, which is the line's own weight - so `Metrics.spine` reads its two reaches back off these rather than rounding its own, and a figure lands on whole pixels at every scale. The line itself is still geometry: it is as long as the tile, and a drawing cannot stretch. |
| `shapes/key-*.svg` | The key at the head of a row on a **latching** card, and what is in its window: `key-ring.svg` and `key-lit.svg`, on one 32-unit canvas and one box. Two drawings rather than one with its fill switched, because they are painted in two colours - the ring takes the card's line ink and does not light with the row, and the window takes the accent. The ring is wound so its hole survives either fill rule, like every annulus here. Its corner is the drawing's own: a key is 16 pixels square, and what was following the ladder had already hit the quarter-of-a-side cap it is drawn at. |
| `shapes/clock-*.svg` | Everything on a clock face and on the chronograph that shares it: the rim, its twelve marks, the hub, the hour and minute hands, the sweep hand, and the register's ring and hand - a line drawing of the Seiko 6139's dial, with no name on it. Drawn on the dial's own 40-unit canvas so the two circles a page may hold are one circle, with a double hairline case against the dial's one band three units thick, a track in fifths, slim batons and tapering hands all in outline - the Seiko 6139's dial, to the proportions of a reference drawing of it - except the register's pair, which is drawn on the register's own 40 so a hand there is measured against the circle it turns in. A hand stands at twelve, pinned at 20,20 where the hub is; the panel turns the whole face-sized box about its middle and names no length, weight or corner. What is left to it is where the register sits and how big it is. |
| `buttons/` | Generated: each shape with its label punched through it, one path with `evenodd`. Portable - use these outside the shell. |
| `generate.py` | The generator. |
| `sounds/` | Generated: the four WAVs a press is answered with. Nothing hand-made stands behind them - the source is the table in `sounds.py`. See [`sound.md`](sound.md). |
| `sounds.py` | The other generator, and the only one with no `shapes/`: a sound is arithmetic rather than a drawing, so its source is the numbers beside it. |
| `truetype.py`, `svgpath.py`, `place.py` | Its parts. |

## Two outputs, same numbers

`buttons/*.svg` and `../shell-plugin/ButtonArt.qml` come out of the same pass,
so they cannot drift apart. The QML is path data with **the shape and the
label kept apart**, because a badge is painted in the theme's colours - the
guide fills the button faintly under a solid label, the game bar draws it as an
outline over whatever the wallpaper left readable - and an SVG can only carry
the colour it was drawn with.

## The four tables

In `generate.py`. The first three cover every badge kind the daemon sends, so
no surface falls back to a bordered rectangle; the fourth is the menu's:

| Table | What it makes |
|---|---|
| `BUTTONS_TO_DRAW` | a shape plus the labels punched into it |
| `ICONS_TO_DRAW` | a label that is itself a drawing (a D-pad arm set into the cross) |
| `BLANKS_TO_DRAW` | the shape only, for the oblong the shell types the word into |
| `CONTROLS_TO_DRAW` | the parts a control tile is drawn from, into a second file |

## The control parts, which are not a font

`CONTROLS_TO_DRAW` writes `../shell-plugin/ControlArt.qml`, and **nothing in it
goes near the font**: `truetype.py` exists to turn letters into outlines so
they can be punched out of a silhouette, and a dial has no letters. What is
generated is the same path data with that step skipped. Say so wherever this
is described - "generate a font for the elements too" is the obvious reading of
what the buttons do, and it is the wrong one.

**Every figure whose silhouette is the same at every value is generated**,
the turning ones included: a clock's hands and a knob's pointer are drawings
standing at twelve, and where they point is a rotation rather than a second
drawing. What is left to the panel is what a number genuinely redraws - where
the thumb dot sits, how far a switch's knob has travelled, an arc that grows
along a ring, a disc whose radius is a setting, a line as long as the tile it
sits in - though what *stands* on that line is drawn, and one of the two
things a stroke has to say (whether the line runs through it) could never be
said by the ladder that sized it. A shape parameterised by a number cannot be drawn once; an angle does
not parameterise a shape. It is the same split
`BadgeArt.qml` already makes between a button and the label set into it, which
is also why `BadgeArt` paints both files without knowing there are two.

A second file rather than more entries in the first, for two reasons.
`ButtonArt` cannot be a `pragma Singleton` - it does not register from a plugin
directory - so every surface that badges anything instantiates a copy of it,
and only the menu draws these. And `EveryBadgeIsDrawn` says every label of
every layout in `guide.LAYOUTS` has art; a map that also held dials would make
that invariant read as a coincidence.

Nothing is written to `buttons/` for them - a dial is not a button, and half a
control is not something to hand a README. That is the argument
`BLANKS_TO_DRAW` already carries.

## The parts

- **`truetype.py`** - just enough TrueType to turn a string into path data:
  `head` for the em square, `cmap`, `loca`/`glyf` for outlines, `hmtx`, `OS/2`
  for the cap height. No hinting, no ligatures, no kerning - the labels are two
  or three capitals from a monospaced face, which is the one case where that is
  the whole truth rather than a simplification.
- **`svgpath.py`** - parse, flatten and measure the path data Figma writes
  (`M C H V L Z` plus `A`, absolute and relative). Flattening is to polygons
  because the placement pass rasterises the shape; nothing round-trips.
- **`place.py`** - where the label sits, decided by the shape rather than by
  eye. A shoulder is drawn with one corner rounded away, so a label centred on
  the bounding box crowds the cut. Instead: rasterise the shape, take the
  distance from every inside point to the nearest outside one, slide the
  label's box over that field, and put it where the smallest clearance is
  largest - nearest the middle when several tie. Shrink and retry when it does
  not fit.

The font is Fira Code **Medium**: Bold at badge size closed up the counters of
the letters it is punched out of, and a knocked-through label reads heavier
than the same weight set solid. It lives in `../shell-plugin/fonts/`; see
[`shell-plugin.md`](shell-plugin.md) for why.

## Rules

- `ButtonArt.qml` and `buttons/*.svg` are **generated**. Edit the shape or the
  table, never the output.
- **Every label of every layout in `guide.LAYOUTS` must have art**, or the
  badge falls back to typed text. `tests/test_assets.py` fails both when a
  label has no art and when the checked-in output no longer matches the
  generator.
- **Whether the label is set on the shape or punched out of it is
  `BadgeArt.qml`'s job, not the generator's.** `knockout` appends the label to
  the shape's own path under an odd-even fill rule, so the letter becomes a
  hole and whatever is behind the badge shows through it. The drawing is the
  same one either way - which is what makes `[ui] badge_style` a look rather
  than a second set of shapes to keep in step.
- **A drawn label is set at the same cap the letters are.** `MARK_CAPS` in
  `generate.py` is the height each shape holds its marks to - 14 units on both
  a 32-unit face button and a 40-unit system one, a shade over `CAP_RATIO`
  because a circle or a triangle set to a letter's exact cap reads smaller
  than the letter. `tests/test_assets.py::MarksStandAtOneHeight` fails when a
  drawing drifts off it, which is the mistake that put four PlayStation
  symbols on four different baselines in one row. A rule (`sys-minus.svg`) is
  exempt and named in `MARK_CAP_EXEMPT`: a rule is two units tall whatever
  else is.

  The system cap reaches the shell as `ButtonArt.markCap`, because the game
  bar's menu door draws the standard menu mark **outside** its badge and
  scales it against the word beside it: the mark's ink is drawn to the word's
  capitals, so `markCap` is what turns the word's height into the mark's
  scale. Dividing by each mark's own ink instead is what once made that word
  a sixth larger on a Switch than on an Xbox.
- **Draw a shape's flat edges on whole units.** A badge is scaled by
  `unit / h`, so an edge on a half unit lands mid-pixel at every badge size
  there is and comes out grey rather than drawn - `Metrics.badge` can snap the
  box, not the drawing inside it. What put the drawings off the grid was
  Figma's own habit: a seven-unit box centred on a sixteen-unit axis has to
  have `.5` edges. So features are drawn **even**, and
  `tests/test_assets.py::ShapesSitOnTheGrid` fails when one is not. Curves are
  exempt - only a straight run has a single coordinate to land badly.

- **Draw on a canvas `Metrics.badgeGrid` divides.** A surface reserves a badge
  `unit` tall and `round(unit * w / h)` wide, and BadgeArt scales the drawing
  by that rounded width - so a shape whose aspect the unit does not divide
  stands a fraction of a pixel off its own box, and every flat edge in it is
  painted grey. `Metrics.badge` snaps the unit up to the grid, and the grid is
  five because 32-by-32, 64-by-32, 48-by-40 and 56-by-40 all divide it. The
  stick was drawn 44 by 32 first, which needs a unit divisible by eight and
  would have made every stick badge on the pad slightly soft with nothing to
  say so; `tests/test_assets.py::ShapesFitTheBadgeGrid` is what says it now.

  **The strokes on a line are exempt, and the exemption is this rule read
  twice.** What the grid is for is a box a *surface* reserves and rounds.
  Nothing reserves a box for a `travel-*.svg`: the panel hands it the line's
  own weight and takes the height the drawing asks for, so what has to be
  whole is the aspect itself - five line weights at a stop, seven at an end -
  and then the box is whole pixels on both sides at every scale there is. The
  same test checks that instead.

  It buys the flat edge, not the whole drawing: a coordinate is *painted*
  crisply only where `unit / h` also makes it whole. That is every multiple of
  five for the system pill's own rim (8 and 32 of 40), and `unit` a multiple of
  16 for the D-pad's arms (10 and 22 of 32) - which is why the cross still
  reads a shade softer than the pill it sits beside.
- **A drawing is fill, never a stroke**, and `Shape` raises on one. A stroke's
  weight is in pixels rather than in the shape's units, so a line drawn as one
  stays a hairline on a badge twice the size, and where a surface paints the
  shape solid - the stencil badge style - it has nowhere left to be. The rim
  of a stick was a stroked circle for exactly as long as it took somebody to
  turn stencil on and find the stick had no rim; it is an annulus in the same
  fill now, three subpaths wound the opposite way in turn so the same shape
  comes out under either fill rule, two units thick at every size.
- **A shape has to carry its own label at the full cap.** `fit` shrinks a
  label in 4% steps until it clears `MIN_PADDING`, which is the right answer
  for a shape it is handed and the wrong one for a shape that ships: `L3` came
  out at 12.39 units inside a 26-unit circle where every other badge is set at
  13.44, with a quarter of a unit of air, and the badge is the only place that
  showed. Draw the shape for what it carries -
  `tests/test_assets.py::LabelsStandAtOneHeight` is what says one still does.
- **A ground is the one drawing that answers to a size, and it answers by not
  being one drawing.** A menu tile is `w` cells by `h` rows, so it has no fixed
  aspect and the rule above would rule it out entirely - which is exactly why
  the slider's *line* and the dial's shaded zone are not drawn art, where the
  strokes standing on that line are. A corner
  is not parameterised by anything, though, and a straight edge does not have
  to be drawn to be right. So `assets/shapes/ground-*.svg` is a **quarter**:
  the corner, with the box it turns in filled behind it. `corner_run` takes out
  the run from one edge to the other and `shell-plugin/TileArt.qml` is
  generated as a *function* rather than as path data - the same run set at four
  corners with lines between them.

  The quarter is drawn clockwise, the way the outline runs: in at `0, c` off
  the left edge, round the corner, out at `c, 0` onto the top edge, then back
  through `c, c` to close. `corner_run` raises on a quarter drawn any other
  way, because nothing downstream would notice - a run that stops in the middle
  of its box still generates, still scales, and comes out as a tile with a dent
  in it.

  The corner is **rotated** into its four places rather than mirrored. A
  rotation carries an arc's sweep flag through unchanged; a mirror would have
  to flip every one of them, and a flag flipped in three corners out of four is
  a ground that draws inside out in one of them. It is also why the run is
  generated as `[letter, numbers...]` rather than as a string: the shell shrinks
  the corner on a tile too small to hold four of them, and a string cannot be
  scaled without being parsed again.
- `CAP_RATIO`, `MIN_PADDING`, `MIN_SCALE`, `SAMPLES`, `SETTLE`, `CURVE_STEPS`
  are the generator's own trade-offs, not user settings - they are the sampling
  and fitting numbers behind a drawing nobody configures.
