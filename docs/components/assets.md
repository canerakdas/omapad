# Button art - `assets/`

The controller buttons omapad badges with - a face button, the shoulders,
the triggers, a stick click, the D-pad, the small system buttons - drawn once
and
generated everywhere else.

```bash
python3 assets/generate.py       # after editing anything in shapes/
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
| `shapes/stick.svg` | The stick, seen from above: a pill inside its own rim, 56 by 40. Wide because of what it carries - `L3` is two characters, and a circle the size of a face button will not hold two at the cap the rest of the pad is set at. The rim is three subpaths of the same fill, not a stroke. |
| `buttons/` | Generated: each shape with its label punched through it, one path with `evenodd`. Portable - use these outside the shell. |
| `generate.py` | The generator. |
| `truetype.py`, `svgpath.py`, `place.py` | Its parts. |

## Two outputs, same numbers

`buttons/*.svg` and `../shell-plugin/ButtonArt.qml` come out of the same pass,
so they cannot drift apart. The QML is path data with **the shape and the
label kept apart**, because a badge is painted in the theme's colours - the
guide fills the button faintly under a solid label, the game bar draws it as an
outline over whatever the wallpaper left readable - and an SVG can only carry
the colour it was drawn with.

## The three tables

In `generate.py`, and between them they cover every kind the daemon sends, so
no surface falls back to a bordered rectangle:

| Table | What it makes |
|---|---|
| `BUTTONS_TO_DRAW` | a shape plus the labels punched into it |
| `ICONS_TO_DRAW` | a label that is itself a drawing (a D-pad arm set into the cross) |
| `BLANKS_TO_DRAW` | the shape only, for the oblong the shell types the word into |

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
- `CAP_RATIO`, `MIN_PADDING`, `MIN_SCALE`, `SAMPLES`, `SETTLE`, `CURVE_STEPS`
  are the generator's own trade-offs, not user settings - they are the sampling
  and fitting numbers behind a drawing nobody configures.
