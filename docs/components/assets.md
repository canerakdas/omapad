# Button art - `assets/`

The controller buttons omapad badges with - a face button, the shoulders,
the triggers, a stick click, the D-pad, the system pills - drawn once and
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
| `shapes/sys-*.svg` | What every console prints on its small buttons, set into the system pill. One drawing serves two consoles: Menu on an Xbox pad and Options on a PlayStation one are the same three bars. |
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
| `BLANKS_TO_DRAW` | the shape only, for the system pill the shell types the word into |

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
- `CAP_RATIO`, `MIN_PADDING`, `MIN_SCALE`, `SAMPLES`, `SETTLE`, `CURVE_STEPS`
  are the generator's own trade-offs, not user settings - they are the sampling
  and fitting numbers behind a drawing nobody configures.
