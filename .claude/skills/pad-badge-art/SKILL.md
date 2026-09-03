---
name: pad-badge-art
description: Change the drawn controller buttons omapad badges with - the SVG shapes in assets/shapes/ and the generated assets/buttons/*.svg and shell-plugin/ButtonArt.qml. Use when adding support for a pad whose buttons print something new, when a badge shows typed text instead of a drawing, when tests/test_assets.py fails, or when asked to redraw a button shape.
---

# Button art

Every controller button omapad draws is **one hand-drawn SVG plus a label
punched through it**, generated into two outputs that cannot drift apart.

```bash
python3 assets/generate.py       # after editing ANYTHING in shapes/ or a table
omarchy-restart-shell            # so the shell picks up the new ButtonArt.qml
python3 -m unittest tests.test_assets -v
```

Read [`docs/components/assets.md`](../../../docs/components/assets.md) for the
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
| `buttons/` | generated SVGs - portable, usable outside the shell |
| `generate.py` | the generator; `truetype.py`, `svgpath.py`, `place.py` its parts |

## The three tables in `generate.py`

Between them they cover every kind the daemon can send, so no surface falls
back to a bordered rectangle.

| Table | Makes | Row shape |
|---|---|---|
| `BUTTONS_TO_DRAW` | a shape with **text labels** punched into it | `(kind, side, shape.svg, (labels...))` |
| `ICONS_TO_DRAW` | a label that is itself **a drawing** | `(kind, glyph, name, base.svg, overlay.svg)` |
| `BLANKS_TO_DRAW` | the shape only, for an oblong the shell types into | `(kind, side, shape.svg)` |

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

## Drawing a shape

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
