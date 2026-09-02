# Button art

The controller buttons omapad badges with — a face button, the two shoulders,
the two triggers, a stick click — drawn once and generated everywhere else.

```bash
python3 assets/generate.py       # after editing anything in shapes/
omarchy-restart-shell            # so the shell picks up the new ButtonArt.qml
```

## What is here

| Path | What it is |
|---|---|
| `shapes/` | **The source.** Hand-drawn SVGs: one per control, plus the marks that go *into* them. Edit these. |
| `shapes/dpad-*.svg` | The D-pad's drawn labels rather than controls of their own — the arm one direction lights inside `dpad.svg`. |
| `shapes/ps-*.svg` | What a PlayStation pad prints on its face buttons, set into `face.svg` the way a letter is. |
| `shapes/sys-*.svg` | What every console prints on its small buttons, set into `system.svg`. One drawing can serve two consoles: Menu on an Xbox pad and Options on a PlayStation one are the same three bars. |
| `buttons/` | Generated: each shape with a label punched through it. |
| `generate.py` | The generator. `truetype.py`, `svgpath.py` and `place.py` are its parts. |

The font is Fira Code Medium — Bold at badge size closed up the counters of
the letters it is punched out of, and a knocked-through label reads heavier
than the same weight set solid. It lives in `../shell-plugin/fonts` rather than
here: the shell loads it at runtime and Omarchy refuses a plugin folder that
contains a symlink, so the one copy has to be the one the plugin can reach. It
is under the SIL Open Font License; `OFL.txt` sits beside it.

## What comes out

Two things, from the same numbers, so they cannot drift apart:

* **`buttons/*.svg`** — the button with its label as a hole in it, one path
  with `evenodd`. Portable and self-contained: use these in a README, a
  screenshot, anything outside the shell.
* **`../shell-plugin/ButtonArt.qml`** — the same geometry as path data, with
  the shape and the label kept apart. The shell paints a badge in the theme's
  colours (the guide fills the button faintly under a solid label; the game bar
  draws it as an outline over the wallpaper), and an SVG can only carry the
  colour it was drawn with.

## Adding a button

Drop the unlabelled shape in `shapes/`, add a line to `BUTTONS_TO_DRAW` in
`generate.py` naming the badge kind, the side and the labels the pad prints on
it, and run the script. The kind and the label are what omapad sends on the
view socket — `guide.KINDS` and `guide.LAYOUTS` — so a name that does not match
one draws nothing and the shell falls back to typed text.

The shapes may use `<path>` and `<circle>`, filled or stroked, in a viewBox
starting at `0 0`. A stroked-only element (the ring around a stick click) is
carried through untouched; the filled ones are what the label is punched out
of, and what the placement measures.

Two tables beside it, for the badges a letter cannot carry. Between them they
cover every label in `guide.LAYOUTS` — the three consoles' printings — because a
badge with no drawing falls back to typed text, and one typed badge in a row of
drawn ones reads as a bug:

* **`ICONS_TO_DRAW`** — the label is a drawing, not text. A D-pad direction is
  the plainest case: the cross is `dpad.svg`, the direction is the arm it lights
  (`dpad-up.svg`, a fill on the same grid and nothing else), and the generator
  sets one into the other exactly the way it sets `A` into a face button. The
  badge is filed under the label the daemon sends, and a surface paints the mark
  with the same ink it paints a letter with. A PlayStation face symbol and every
  console's small buttons are the same arrangement: `face.svg` or `system.svg`
  as the shape, a `ps-*` or `sys-*` mark as the label.

  A mark is drawn as **non-overlapping contours**, with a ring's inside wound
  the other way round. The generator joins the whole label into one path, and
  that path is painted even-odd in the SVG and non-zero in the shell: only
  contours that do not cross come out the same under both. It is why the two
  panes of the View mark are drawn as a pane and two edges rather than as two
  rectangles, one over the other.
* **`BLANKS_TO_DRAW`** — the shape alone, for a control whose badge is a word.
  Every system button is the same pill; MINUS, PLUS and HOME differ only in
  what the shell types into it, so only the pill is generated. Its viewBox
  carries the empty room above and below the pill (64×40 for a 64×24 pill),
  which is how a badge line's worth of height comes out right without any
  surface knowing that a system button is drawn shorter than a face button.
  Nothing is written to `buttons/` for these: half a badge is not something to
  hand a README.

## Where the label goes

Nobody types a nudge per shape. `place.py` rasterises the filled shape,
measures how far every point inside it is from the outside, slides the label's
box over that field and puts the label where the box sits deepest — nearest the
middle of the shape when several positions tie. On a circle that is the centre;
on a shoulder cut away at one corner it is over towards the corner that is
still there, which is where the hand-drawn examples put it too.

The label starts at `CAP_RATIO` of the button's height (0.42; the hand-drawn
examples used 0.53, which reads too big now that a badge has no outline around
it) and shrinks only when the shape makes it: `L3` inside a stick click is the
one that really has to.
