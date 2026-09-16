# Button art

The controller buttons omapad badges with — a face button, the two shoulders,
the two triggers, a stick click — and the parts its control tiles are drawn
from, drawn once and generated everywhere else.

```bash
python3 assets/generate.py       # after editing anything in shapes/
omarchy-restart-shell            # so the shell picks up the new art
```

## What is here

| Path | What it is |
|---|---|
| `shapes/` | **The source.** Hand-drawn SVGs: one per control, plus the marks that go *into* them. Edit these. |
| `shapes/dpad-*.svg` | The D-pad's drawn labels rather than controls of their own — the arm one direction lights inside `dpad.svg`. |
| `shapes/ps-*.svg` | What a PlayStation pad prints on its face buttons, set into `face.svg` the way a letter is. |
| `shapes/sys-*.svg` | What every console prints on its small buttons, drawn on a 48x40 grid so either silhouette can carry it. One drawing can serve two consoles: Menu on an Xbox pad and Options on a PlayStation one are the same three bars. |
| `shapes/sys-round.svg` | The small **round** button — what every pad but one puts a mark on. |
| `shapes/sys-guide.svg` | The **Xbox button**, drawn 36 units of 40 against the 24 the rest get, with `sys-nexus.svg` scaled to match it. |
| `shapes/system.svg` | The **oblong** — PlayStation's Create and Options, and the bare shape the shell types a word into. |
| `shapes/dial-*.svg`, `switch-*.svg`, `chev-*.svg`, `media-*.svg`, `grip.svg` | The parts a **control tile** is drawn from — see below. No labels, so no font. |
| `shapes/ground-*.svg` | One **corner** of a menu tile, one file per state — see below. No labels either. |
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

* **`../shell-plugin/ControlArt.qml`** — the same, for the parts a control
  tile is drawn from.

* **`../shell-plugin/TileArt.qml`** — the ground a menu tile is drawn on, as a
  *function* rather than as path data. It is the only output here that has to
  be told how big the thing is before it is a drawing at all.

## Grounds, which are a corner and four numbers

Every state of a menu tile is drawn on its **own outline** — plain, selected,
and being carried — so which state a tile is in reads from its silhouette and
not only from its colour. A theme whose accent sits close to its surface leaves
a selection to the border alone, and the border is the thinnest thing on a tile.

A tile is `w` cells by `h` rows, though, which is the one aspect the badge rule
rules out: a drawing scaled by one factor cannot be a rectangle of any shape.
That is the rule the slider's travel and the dial's shaded zone are not drawn
under, and a ground would fall under it too — except that **only the edges are
parameterised**. A corner is not, and a straight line does not have to be drawn
to be right.

So the source is a **quarter**: the corner, with the box it turns in filled in
behind it. Drawn clockwise, the way the outline runs — in at `0 c` off the left
edge, round the corner, out at `c 0` onto the top edge, then back through `c c`
to close. Those last two sides are the tile's own edges and are not generated;
`corner_run` raises on a quarter drawn any other way, because nothing
downstream would notice one that stops in the wrong place — it still generates,
still scales, and comes out as a tile with a dent in it.

The corner is **rotated** into its four places, never mirrored: a rotation
carries an arc's sweep flag through unchanged, and a mirror would have to flip
every one of them. It is also why a run is generated as `[letter, numbers...]`
rather than as a string — the shell shrinks the corner on a tile too small to
hold four of them, and a string cannot be scaled without being parsed again.

`GROUNDS_TO_DRAW` is the table, `(name, quarter.svg)`, and the name is what
`Menu.qml` asks for. How far the corner reaches into a tile is
`[menu] tile_corner`, **not** `Style.cornerRadius`: that mirrors the
compositor's own window rounding, it is 0 on plenty of setups, and at 0 every
state would be drawn as the same square.

## Control tiles, which are not a font

The menu's tiles hold values — a dial, a switch, a walked choice, a transport —
and the parts they are drawn from are generated here alongside the buttons.
**This is not a TrueType font.** `truetype.py` exists to turn *letters* into
outlines so they can be punched out of a silhouette; nothing in a dial has a
letter in it, so nothing here goes near it. What comes out is the same path
data with that step skipped.

`CONTROLS_TO_DRAW` is the table, `(family, name, shape.svg)`, and it writes
`ControlArt.qml` rather than adding to `ButtonArt.qml`. Two reasons:
`ButtonArt` cannot be a `pragma Singleton` (it does not register from a
plugin directory), so every surface that badges anything instantiates a copy,
and only the menu draws these. Keeping them apart also keeps
`EveryBadgeIsDrawn` honest, which says every label of every layout has art.

**Only the furniture is generated** — what does not depend on the value:

| Generated | Left to the panel |
|---|---|
| the dial's rim, its notches, the thumb dot | where the dot sits, and the shaded zone - a circle of variable radius, which a drawing cannot be |
| the switch's pill and its knob | how far the knob has travelled |
| the two chevrons | which one is dimmed at an end |
| the four transport marks | which one is drawn |

A shape parameterised by a number cannot be drawn once, so it is not drawn
here. It is the same split `BadgeArt` already makes between a button and the
label set into it.

The rules are the buttons' rules: **fill, never a stroke**; flat edges on whole
units; a canvas `Metrics.badgeGrid` divides. `MARK_CAPS` and the centring test
do **not** apply — none of these is a mark set into a silhouette. One rule of
their own: a shape with a hole in it (the dial's rim) is wound so the hole
survives **both** fill rules, because a
badge is painted non-zero normally and even-odd in the stencil style. That is
the trap `stick.svg`'s rim taught before it lost it, and
`tests/test_assets.py::AnnuliSurviveEitherFillRule` is what says so now.

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
  console's small buttons are the same arrangement: `face.svg`, `sys-round.svg`
  or `system.svg` as the shape, a `ps-*` or `sys-*` mark as the label.

  Which silhouette a small button gets is the pad's answer, not ours. Guide,
  Home, View, Menu, Share, Capture, PS, Mute, − and + are **round** on every
  pad that has them; only PlayStation's Create and Options are the oblong. One
  shape for all of them drew the Xbox nexus as the same outline as Menu, which
  is the pair a thumb tells apart by outline before it reads the mark.

  Size is the pad's answer too, and only one button changes it: the Xbox
  button is larger than everything else on that pad, face buttons included,
  and is meant to be found without looking — `sys-guide.svg`, 36 units of 40
  where the rest are 24. A Switch's Home and a DualSense's PS are not drawn
  larger on the hardware, so they are not drawn larger here.

  A mark is set to the height in `MARK_CAPS` - 14 units on a face button and
  on a small system one, 21 on the larger Xbox button - and centred in its
  shape, so a row of them stands on one baseline. That is a shade over the
  `CAP_RATIO` the letters are punched at, because a circle or a triangle set
  to a letter's exact cap reads smaller than the letter beside it. The system
  one also reaches the shell as `ButtonArt.markCap`, since the game bar's
  menu door draws the standard menu mark outside its badge and scales it to
  match the word beside it.
  `sys-minus.svg` is exempt: a rule is two units tall whatever else is.

  A mark is drawn as **non-overlapping contours**, with a ring's inside wound
  the other way round. The generator joins the whole label into one path, and
  that path is painted even-odd in the SVG and non-zero in the shell: only
  contours that do not cross come out the same under both. It is why the two
  panes of the View mark are drawn as a pane and two edges rather than as two
  rectangles, one over the other.
* **`BLANKS_TO_DRAW`** — the shape alone, for a control whose badge is a word.
  A remapped button and a pad nobody here has a printing for both arrive as
  text, and the oblong is the shape wide enough to hold one, so that is the
  one generated. Its viewBox carries the empty room around it (48×40 for a
  40×24 oblong), which is how a badge line's worth of height comes out right
  without any surface knowing that a system button is drawn shorter than a
  face button — and `sys-round.svg` shares that box, so a round badge and an
  oblong one reserve the same width. Nothing is written to `buttons/` for
  these: half a badge is not something to hand a README.

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
