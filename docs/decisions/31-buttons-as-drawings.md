# 31. Buttons drawn as drawings, not as rounded rectangles · ✅ Done · M

Item 11 got the shapes right in principle and wrong in fact. Every surface drew
its own badge out of a `Rectangle` with a radius per kind, a second rectangle
inset for a stick's ring, and a `Text` on top - three copies of it, in
`Guide.qml`, `Assist.qml` and `GameBar.qml`, drifting apart a little each time
one of them was touched. A bumper was a lozenge, a trigger was the same lozenge
with two corners squared, and neither looked like the thing under a thumb.

The shapes are now **drawn**, once, and everything else is generated from them.
`assets/shapes/*.svg` holds one unlabelled SVG per control; `assets/generate.py`
sets the label into it in **Fira Code** and writes two things from the same
numbers - `assets/buttons/*.svg`, the button with its label punched through it,
and `shell-plugin/ButtonArt.qml`, the same geometry as path data with the shape
and the label kept apart so a surface can paint them in its own colours. The
guide fills the button faintly under a solid label; the game bar draws it as an
outline over the wallpaper. `BadgeArt.qml` is the one thing that paints either,
so the three surfaces cannot drift again.

**Nobody types a nudge per shape.** A shoulder is cut away at one corner, so a
label centred on its bounding box crowds the cut. `assets/place.py` rasterises
the filled shape, measures how far every point inside it is from the outside,
slides the label's box over that field and puts the label where the box sits
deepest, preferring the middle when several positions tie. On a circle that is
the centre; on a shoulder it lands within a unit of where the hand-drawn
examples put it. It also decides the size: the label starts at the cap height
those examples used and shrinks only where the shape makes it, which is `L3`
inside a stick click and nothing else.

The font parsing is 200 lines of `truetype.py` rather than a dependency -
`cmap`, `loca`, `glyf`, `hmtx`, `OS/2` - because this project takes no
third-party packages and the job is capitals and digits out of a monospaced
face, which is the one case where an outline dump is the whole truth.

Everything the daemon names is drawn: the D-pad as a cross with the arm its
direction lights set into it the way a letter is set into a face button, and
the system buttons as a pill the shell types the word into, since what tells
MINUS from HOME is the word and not the shape. A new drawing plugs in the same
way - add the SVG, add a line to `BUTTONS_TO_DRAW` (or to `ICONS_TO_DRAW` for
a badge whose label is drawn, `BLANKS_TO_DRAW` for a shape the shell types
into), re-run. `tests/test_assets.py` rebuilds everything in memory
and fails if what is checked in no longer matches, because forgetting to re-run
the generator is the one mistake nothing else would catch.
