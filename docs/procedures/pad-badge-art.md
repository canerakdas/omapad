# Button art

> Change the controller buttons omapad draws - the SVG shapes in assets/shapes/
> and the generated assets/buttons/*.svg and shell-plugin/ButtonArt.qml. Use
> when adding support for a pad whose buttons print something new, when a badge
> shows typed text instead of a drawing, when tests/test_assets.py fails, or
> when asked to redraw a button shape. Owns the shape sources and the
> generator.

Every controller button omapad draws is **one hand-drawn SVG plus a label
punched through it**, generated into two outputs that cannot drift apart.

```bash
python3 assets/generate.py       # after editing ANYTHING in shapes/ or a table
omarchy-restart-shell            # so the shell picks up the new ButtonArt.qml
python3 -m unittest tests.test_assets -v
```

Read [`docs/components/assets.md`](../components/assets.md) for the
mechanism; this is the procedure and the traps.

## The one rule

**`assets/buttons/*.svg` and `shell-plugin/ButtonArt.qml` are generated. Edit
the shape or the table, never the output.** Both are checked in on purpose, so
a change to a shape shows up as a diff and `tests/test_assets.py` fails when
the output and the generator disagree.

That test is the only thing that notices. The daemon never reads any of this,
so redrawing a shape and forgetting to regenerate leaves the shell drawing
yesterday's button and nothing else complains.

## What is where

| Path | What |
|---|---|
| `shapes/` | **the source** - hand-drawn, unlabelled, one per control |
| `shapes/dpad-*.svg` | drawn *labels*, not controls: one arm of `dpad.svg` lit |
| `shapes/ps-*.svg` | PlayStation face symbols, set into `face.svg` like a letter |
| `shapes/sys-*.svg` | what consoles print on the small buttons, on a 48x40 grid. One drawing serves two: Xbox's Menu and PlayStation's Options are the same three bars |
| `shapes/sys-round.svg` | the small **round** button - every one of them but Create and Options |
| `shapes/sys-guide.svg` | the **Xbox button** alone, 36 of 40 against the others' 24, with `sys-nexus.svg` drawn to match |
| `shapes/system.svg` | the **oblong** - Create, Options, and the bare shape the shell types a word into |
| `shapes/stick.svg` | the **stick from above** - 56x40, one pill, wide because `L3` is two characters. No rim: every badge on the pad is a solid silhouette, and a ring among them reads as a different colour |
| `buttons/` | generated SVGs - portable, usable outside the shell |
| `shapes/ground-*.svg` | **a quarter of a menu tile** - one corner per tile state, and the one drawing here that answers to a size |
| `shapes/travel-*.svg` | **the strokes that stand on a line** - two reaches, and for each whether the line runs through it. Ten units across, which is the line's own weight, so the panel sizes them from `Metrics.spine` and they land on whole pixels |
| `shapes/key-*.svg` | **the key on a latching row and its window** - two drawings on one canvas, because the ring and what lights inside it are painted in two colours |
| `generate.py` | the generator; `truetype.py`, `svgpath.py`, `place.py` its parts |

## The four tables in `generate.py`

Between them they cover every kind the daemon can send, so no surface falls
back to a bordered rectangle.

| Table | Makes | Row shape |
|---|---|---|
| `BUTTONS_TO_DRAW` | a shape with **text labels** punched into it | `(kind, side, shape.svg, (labels...))` |
| `ICONS_TO_DRAW` | a label that is itself **a drawing** | `(kind, glyph, name, base.svg, overlay.svg)` |
| `BLANKS_TO_DRAW` | the shape only, for an oblong the shell types into | `(kind, side, shape.svg)` |
| `GROUNDS_TO_DRAW` | **a function**, not path data - a menu tile's outline at whatever size it turned out | `(name, quarter.svg)` |

## Adding a pad that prints something new

This is the common job, and it is **two edits, not one**:

1. `guide.LAYOUTS` gets the new console's table - what that pad prints on each
   logical button.
2. `BUTTONS_TO_DRAW` (a letter or word) or `ICONS_TO_DRAW` (a symbol) gets
   every new label, on the shape that button already uses.

**Every label of every layout in `guide.LAYOUTS` must have art**, or the badge
silently falls back to typed text. `tests/test_assets.py` fails on exactly
this, which is why it exists - a new logical button in `guide.py` with no
shape behind it is the other half of the same drift.

For a symbol, draw it on the **same grid as the shape it sits in** and
**filled, not stroked** - the generator raises on both, so you will be told.

Set it to **`MARK_CAPS[base]` units tall** - 14 on a face button and on a
small system one, 21 on the Xbox button - centred in the shape. That is the
height the letters are punched at plus a little overshoot, and
`MarksStandAtOneHeight` fails when a drawing misses it. It is not cosmetic:
the game bar's menu door scales the standard menu mark against the word
beside it by `ButtonArt.markCap`, so a mark drawn short lands short beside
the word no matter what the door's numbers say.

## Drawing a control part

The menu's tiles hold values, and the parts they are drawn from live in the
same `shapes/` directory - `dial-*`, `clock-*`, `switch-*`, `chev-*`,
`media-*`, `travel-*`, `key-*`, `grip`.
They go in `CONTROLS_TO_DRAW`, `(family, name, shape.svg)`, and come out in
`shell-plugin/ControlArt.qml`.

**This is not a font, and it is worth saying out loud.** `truetype.py` exists
to turn *letters* into outlines so they can be punched out of a silhouette.
Nothing in a dial has a letter in it, so nothing here goes near it - what is
generated is the same path data with that step skipped. "Generate a font for
these too" is the obvious reading of what the buttons do, and it is wrong.

**Draw every figure whose silhouette is the same at every value** - a
turning one included, because an angle is a transform and not a second
drawing. Leave what a number actually redraws:

| Draw | Leave to the panel |
|---|---|
| the rim, the thumb dot | where the dot sits, and the shaded zone - a circle of variable radius, which is `radius: width / 2` rather than a drawing |
| the switch's pill and knob | how far the knob has travelled |
| the chevrons, the transport marks | which one is drawn or dimmed |
| the strokes that stand on a line - a stop, an end, the value's own mark, the pair that bracket a row | the line itself, and how far along it anything stands |
| the key at the head of a latching row, and what is in its window | which of the two is drawn |
| the clock's rim, its twelve marks, the hub, both hands, the sweep, the register's ring and hand | which way each one points, and where the register sits and how big it is |
| the knob's cap, its index, one mark of its scale and the longer mark at each end | the scale's arc and the run of it the value has covered - an arc that grows with the number - and how many marks there are |

A shape parameterised by a number cannot be drawn once. Same split `BadgeArt`
already makes between a button and the label set into it - which is why
`BadgeArt` paints these without knowing there are two files.

**A figure sized from a line is the one exemption from the badge grid**, and
it earns it by being sized more strictly rather than less. A `travel-*.svg` is
drawn ten units across - the line's own weight - and a whole number of them
tall, so the panel hands it `spine.weight` and takes the height the drawing
asks for: five weights at a stop, seven at an end. `Metrics.spine` reads its
two reaches back off the drawings for that reason, and a new stroke drawn at
any other aspect fails `ShapesFitTheBadgeGrid` with that said in the message.

**Two strokes that differ only in a gap are two drawings, not one.** Whether
the line runs *through* a stroke or stops at it is the second question every
one of them answers, and it cannot be a colour: every ink on these surfaces is
the theme's own at a share of itself, so a bar run through the line paints that
square twice and lights it. It shipped as one solid rectangle for as long as
the strokes were rectangles, and the middle stops of a stepped slider are where
that showed.

**A turning figure is drawn standing at twelve, pinned at the middle of its
own canvas**, and the panel gives it the whole face to fill and rotates it.
That is why the hands are centred on 20,20 of a 40: a drawing positioned by
its angle as well as turned by it is arithmetic in two places.

`ShapesSitOnTheGrid` **exempts them**, and the exemption is the rule rather
than a hole in it. A straight run parallel to an axis lands on half a pixel
and is painted grey; a hand is parallel to one at four angles out of a full
turn and antialiased at every other. Holding it to the grid would force an
even width on a figure centred on its pivot, which would make the sweep hand
and the minute hand the same weight - the one thing two hands on one face may
not be.

The shape rules below all apply. Two do **not**:

- `MARK_CAPS` and `MarksStandAtOneHeight`. None of these is a mark set into
  a silhouette, and a chevron stands on nobody's baseline.
- `LabelsStandAtOneHeight`. There are no labels.

And one is theirs alone: **a shape with a hole in it is wound so the hole
survives both fill rules.** A badge is painted non-zero normally and even-odd
in the stencil style, so two same-wound circles are a ring in one and a disc
in the other. The dial's rim is an outer arc with `sweep 1` and an inner with
`sweep 0`; `AnnuliSurviveEitherFillRule` is what says so. It is the lesson
`stick.svg` taught before it gave its own rim up.

## Drawing a tile ground

The one drawing here that answers to a size, and the one place the rule above
bends. A menu tile is `w` cells by `h` rows - no fixed aspect at all - so a
drawing scaled by one factor cannot be its outline. That is exactly why the
slider's travel and the dial's shaded zone are *not* art.

A ground gets away with it because **only its edges are parameterised**. A
corner is not, and a straight line does not have to be drawn to be right. So
what you draw is a **quarter**: the corner, with the box it turns in filled in
behind it.

```
                       (0,0)        (c,0)
  in off the left edge   .  ‾ ‾ ‾ ‾ .  out onto the top edge
  at (0, c)              |  the     |
                         |  corner  |
                  (0,c)  ._ _ _ _ _ .  (c,c)  <- closes the quarter;
                                                 not generated
```

**Drawn clockwise, the way the outline runs.** In at `0 c`, round the corner,
out at `c 0`, then back through `c c` to close. `corner_run` raises on a
quarter drawn any other way, and that is the whole point of it: a run that
stops in the middle of its box still generates, still scales, and comes out as
a tile with a dent in one corner. Nothing downstream would notice.

Add a line to `GROUNDS_TO_DRAW`, `(name, quarter.svg)`, and `Menu.qml` asks for
that name in `tile.outline`. `tests/test_assets.py` fails on a state the menu
draws that the table does not generate, and the other way round.

Three things are already decided for you, and each has a test:

- **The corner is rotated into its four places, never mirrored.** A rotation
  carries an arc's sweep flag through unchanged; a mirror would have to flip
  every one of them, and a flag flipped in three corners out of four is a
  ground that draws inside out in one of them.
- **A run is generated as `[letter, numbers...]`, not as a string.** The shell
  shrinks the corner on a tile too small to hold four of them, and a string
  cannot be scaled without being parsed again.
- **Every ground is wound the same way round** - clockwise, a positive area
  with `y` down the screen. `GroundsCloseOnTheirOwnBox` is what says so: under
  an even-odd fill, a ground wound the other way is the state that draws as a
  hole.

How far the corner reaches into a tile is **`[menu] tile_corner`**, and it is
deliberately not `Style.cornerRadius` - that mirrors the compositor's own
`decoration:rounding`, it is 0 on plenty of setups, and at 0 every state of a
tile is drawn as the same square, which is the one thing a state silhouette
must not do.

## Drawing a shape

- **Everything is fill. `Shape` raises on a stroke.** `<path>` and `<circle>`
  only; a `<rect>` is refused, so draw a bar as a path. A stroke's weight is in
  pixels, not in the shape's units, so it stays a hairline on a badge twice
  the size and disappears entirely in the stencil style, where the surface
  paints the shape solid. A line that is part of the drawing is drawn as one:
  `dial-face.svg` is an outer arc and an inner wound the other way, so the
  same annulus comes out under either fill rule.

- **A badge is a solid silhouette.** Every one of them: a circle, a cross, a
  pill, a capsule, with the label punched out of it. A ring among them reads
  as a different colour rather than as a different button, which is why
  `stick.svg` stopped being one. What a badge says is which button it is, and
  it says that with its outline.
- **The shape has to carry its label at the full cap.** `fit` will shrink a
  label rather than fail, and a shipped shape that makes it do so is the wrong
  shape for that many characters - `LabelsStandAtOneHeight` is what says so.
  The stick is the worked example: two characters would not stand full height
  in a circle, so the circle became a pill.
- **A new canvas has to divide `Metrics.badgeGrid`** (5): `grid * w / h` whole,
  or every badge of that shape lands a fraction of a pixel off its own box and
  the flat edges in it come out grey. 32x32, 64x32, 48x40 and 56x40 do;
  44x32 does not. `ShapesFitTheBadgeGrid` is what says so.
- Figma's output dialect is what `svgpath.py` parses: `M C H V L Z` plus `A`
  for a circle, absolute or relative. Nothing round-trips - flattening is to
  polygons because placement rasterises the shape.
- **Do not centre the label yourself.** `place.py` decides where it sits from
  the shape: it rasterises, measures the distance from every inside point to
  the nearest outside one, slides the label's box over that field and puts it
  where the smallest clearance is largest. A shoulder is drawn with one corner
  rounded away, and a label centred on the bounding box crowds the cut.
- The font is Fira Code **Medium**, not Bold: at badge size Bold closes up the
  counters, and a knocked-through label already reads heavier than the same
  weight set solid.
- `CAP_RATIO`, `MIN_PADDING`, `MIN_SCALE`, `SAMPLES`, `SETTLE`, `CURVE_STEPS`
  are the generator's sampling and fitting trade-offs, **not** user settings -
  the one place in this project where a number stays a number, because nobody
  configures a drawing.

## Never do this in QML

- Hand-draw a button shape.
- Edit `ButtonArt.qml`.
- Inline an SVG from `assets/buttons/`: a badge takes the **theme's** colours,
  and an SVG carries only the colour it was drawn with. `BadgeArt.qml` paints
  it; the caller picks the entry, the colours and the stroke weight.
- Make `ButtonArt.qml` a `pragma Singleton`. It looks like 540 kB saved and it
  does not register from a plugin directory: the name resolves, the properties
  do not, and all four surfaces stop drawing badges.

## When a badge shows typed text

That is the fallback, and it means the label has no art. In order:

1. `python3 -m unittest tests.test_assets -v` - it names the missing label.
2. Check the label really is in `guide.LAYOUTS` spelled the same way.
3. Add it to the right table, regenerate, `omarchy-restart-shell`.
4. If it still types: `qs -p /usr/share/omarchy/shell log` is the only place
   the real error appears.
