#!/usr/bin/env python3
"""Draw every button badge from the shapes in `shapes/` and Fira Code.

    python3 assets/generate.py

The shapes are hand-drawn and are the source: one SVG per control, unlabelled.
Everything else here is derived from them, so a shape redrawn in Figma is the
only edit a new look needs.

Two things come out, from the same numbers, so they cannot drift apart:

* `buttons/*.svg` - the button with its label punched through it. Portable, and
  what anything outside the shell (a README, a screenshot) should use.
* `../shell-plugin/ButtonArt.qml` - the same geometry as path data, shape and
  label kept apart so the shell can paint them in the theme's own colours. An
  SVG carries the colour it was drawn with; a badge on the game bar has to
  take the colour the wallpaper decided.

The label is centred by the shape rather than by its line box - see place.py -
which is what the badge drawing in the shell used to approximate with a nudge
per surface.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import place
import svgpath
import truetype

HERE = os.path.dirname(os.path.abspath(__file__))
SHAPES = os.path.join(HERE, "shapes")
BUTTONS = os.path.join(HERE, "buttons")
# Fira Code lives in the plugin rather than beside the shapes: the shell
# loads it at runtime and Omarchy refuses a plugin folder containing a
# symlink, so the one copy has to be the one the plugin can reach.
# Medium rather than Bold: the label is punched out of the button, and a
# knocked-through letter picks up weight against the shape it is cut from -
# Bold closed up the counters of A and B at badge size.
FONT = os.path.join(HERE, os.pardir, "shell-plugin", "fonts",
                    "FiraCode-Medium.ttf")
QML = os.path.join(HERE, os.pardir, "shell-plugin", "ButtonArt.qml")
# A second generated file rather than more entries in the first. ButtonArt may
# not be a `pragma Singleton` - it does not register from a plugin directory -
# so every surface that badges anything instantiates a copy of it, and only
# the menu draws these. Keeping them apart also keeps `EveryBadgeIsDrawn`
# honest: that test says every label of every layout has art, and a map that
# also held dials would make the invariant read as a coincidence.
CONTROL_QML = os.path.join(HERE, os.pardir, "shell-plugin", "ControlArt.qml")
# A third, for the one drawing that has to answer to a size. See
# GROUNDS_TO_DRAW: it is generated as a *function* rather than as path data,
# which is not something either file above can hold.
TILE_QML = os.path.join(HERE, os.pardir, "shell-plugin", "TileArt.qml")

# How tall the capitals are, as a fraction of the button's own height, and the
# number the rest of the fit is measured down from. The hand-drawn examples
# used 0.53 - a 17-unit cap on a 32-unit face button - which reads too big
# once the badge has no outline to hold it: a letter that nearly touches the
# silhouette leaves nothing to see the silhouette by, and the silhouette is
# what says which control this is. Everything else follows this number: a
# mark drawn instead of a letter is set a shade over it (`MARK_CAPS`), and so
# is the word inside the game bar's menu button, through `capRatio` and
# `markCap` in ButtonArt.
CAP_RATIO = 0.42

# How tall every mark drawn instead of a letter is set, in a system shape's
# own units - 14 of the 40 a system shape is tall. One number rather than
# whatever each drawing happened to measure, because the game bar's menu door
# draws a mark on its own, outside the badge it belongs to, and has to size
# the word beside it to match. Sizing that word off the mark's own ink made it
# a sixth larger on a Switch (a 14-unit +) than on an Xbox (10-unit bars), so
# the height is decided here and both the drawings and the door follow it.
# `sys-nexus.svg` is the one exception, drawn 21 to match the larger button it
# sits on - the same fraction of it - and `sys-minus.svg` is a rule, which is
# 2 units tall whatever else is.
SYSTEM_MARK_CAP = 14.0

# And the same for a face button, which is 32 units tall rather than 40. Both
# are a little over `CAP_RATIO` times their shape - 14 against the 13.44 a
# capital is punched at - because a circle and a triangle set to a letter's
# exact cap height read smaller than the letter beside them. Overshoot is
# what a type designer would give them, and it is the same 14 either way only
# because a face button and a system one happen to want it.
FACE_MARK_CAP = 14.0

# Which of those a mark drawn on each shape is held to. A shape absent from
# here is one whose marks are not caps at all - the D-pad's arms are a lit
# segment of the cross, and answer to the cross.
MARK_CAPS = {
    "face.svg": FACE_MARK_CAP,
    "sys-round.svg": SYSTEM_MARK_CAP,
    "system.svg": SYSTEM_MARK_CAP,
    # The Xbox button is drawn 36 units against the small button's 24, and its
    # mark is scaled with it rather than left rattling around inside it.
    "sys-guide.svg": SYSTEM_MARK_CAP * 36 / 24,
}

# A rule is two units tall whatever else is. That is what a rule is, and
# stretching it to a cap height would draw a slab.
MARK_CAP_EXEMPT = ("sys-minus.svg",)

# How much empty button has to be left around the label, in shape units. No
# shipped shape reaches it any more: the one that did was the stick click,
# whose `L3` is two characters, and the answer was to draw the shape for what
# it carries rather than to keep shrinking the letters.
MIN_PADDING = 1.0

# How far the label is allowed to shrink before the shape is simply the wrong
# one for that many characters, and saying so beats shipping something
# unreadable.
MIN_SCALE = 0.45

# Which shape each control is drawn with, and which labels it is printed with.
# A pad's own printed labels: `L`/`ZL` is what Nintendo puts there, `LB`/`LT`
# is what Xbox puts there, and omapad badges whichever the connected pad
# says - so both are drawn.
BUTTONS_TO_DRAW = (
    ("face", None, "face.svg", ("A", "B", "X", "Y")),
    ("bumper", "l", "bumper-left.svg", ("L", "LB", "L1")),
    ("bumper", "r", "bumper-right.svg", ("R", "RB", "R1")),
    ("trigger", "l", "trigger-left.svg", ("ZL", "LT", "L2")),
    ("trigger", "r", "trigger-right.svg", ("ZR", "RT", "R2")),
    # A stick carries two badges: the click, which the pad prints as L3/R3,
    # and the stick itself, which the guide names by the side it is on. It is
    # drawn wide because of the first of those: `L3` is two characters, and a
    # circle the size of a face button will not hold two at the cap the rest
    # of the pad is set at. The rim is the stick seen from above, and it is
    # part of the fill - see `Shape`.
    ("stick", "l", "stick.svg", ("L3", "L")),
    ("stick", "r", "stick.svg", ("R3", "R")),
)

# Badges whose label is drawn rather than typed. A D-pad has no letters on it:
# what says which direction this is, is the arm the cross lights up, and that
# arm is a shape of its own set into the cross exactly the way a letter is set
# into a face button - same two roles, so a surface paints it with the same
# two colours. Filed under the arrow the daemon sends as the label
# (`guide.LAYOUTS`), because that is all the shell has to look it up with.
#
# The same goes for a PlayStation face button, which is printed with a shape
# rather than a letter, and for every system button on every pad: what is on
# one is a mark, and MINUS and PLUS were only ever − and + because those two
# marks happen to be characters. See `guide.LAYOUTS` for which label each
# console prints; one drawing can answer to two of them, because Menu on an
# Xbox pad and Options on a PlayStation one are the same three bars.
#
# The silhouette under the mark is a second question, and one pill was the
# wrong answer to it: the button a pad prints Guide, Home, View, Menu, Share,
# Capture, PS, Mute, - or + on is round on every pad that has one, and only
# PlayStation's Create and Options are the oblong. Drawing all of them as the
# oblong made the Xbox nexus the same outline as Menu - which is the one pair
# a player picks apart by outline before reading the mark at all.
#
# Size is the same question again. A pad draws its small buttons alike, with
# one exception: the Xbox button is larger than every other button on the pad,
# face buttons included, and is meant to be found without looking. So it gets
# a circle of its own - 36 of 40 against the 24 the rest are drawn at - and
# `sys-nexus.svg` is drawn to match it. Home on a Switch and PS on a DualSense
# are not drawn larger on the hardware, so they are not drawn larger here.
ICONS_TO_DRAW = (
    ("dpad", u"\u25b2", "up", "dpad.svg", "dpad-up.svg"),
    ("dpad", u"\u25bc", "down", "dpad.svg", "dpad-down.svg"),
    ("dpad", u"\u25c0", "left", "dpad.svg", "dpad-left.svg"),
    ("dpad", u"\u25b6", "right", "dpad.svg", "dpad-right.svg"),
    ("face", u"\u2715", "ps-cross", "face.svg", "ps-cross.svg"),
    ("face", u"\u25cb", "ps-circle", "face.svg", "ps-circle.svg"),
    ("face", u"\u25a1", "ps-square", "face.svg", "ps-square.svg"),
    ("face", u"\u25b3", "ps-triangle", "face.svg", "ps-triangle.svg"),
    ("system", u"\u2212", "minus", "sys-round.svg", "sys-minus.svg"),
    ("system", "+", "plus", "sys-round.svg", "sys-plus.svg"),
    ("system", "Home", "home", "sys-round.svg", "sys-house.svg"),
    ("system", "Capture", "capture", "sys-round.svg", "sys-dot.svg"),
    ("system", "Menu", "menu", "sys-round.svg", "sys-bars.svg"),
    ("system", "View", "view", "sys-round.svg", "sys-panes.svg"),
    ("system", "Guide", "guide", "sys-guide.svg", "sys-nexus.svg"),
    ("system", "Share", "share", "sys-round.svg", "sys-record.svg"),
    ("system", "Options", "options", "system.svg", "sys-bars.svg"),
    ("system", "Create", "create", "system.svg", "sys-panes.svg"),
    ("system", "PS", "ps", "sys-round.svg", "sys-orb.svg"),
    ("system", "Mute", "mute", "sys-round.svg", "sys-mic.svg"),
)

# Shapes with no label of their own, and none the generator could guess: what
# tells two system buttons apart is the word the shell types into them - START
# and SELECT are the same pill - so only the shape is generated here.
BLANKS_TO_DRAW = (
    ("dpad", None, "dpad.svg"),
    ("system", None, "system.svg"),
)

# The parts a control tile is drawn from. Not buttons: nothing here has a
# label, so nothing here goes near the font - what the TrueType half of this
# script exists for is punching *letters* out of silhouettes, and a dial has
# none. Generated all the same, and for the same reason: a drawing painted in
# the theme's colours cannot be an SVG, which carries the colour it was drawn
# with.
#
# Only the furniture is here - what does not depend on the value. The arc that
# follows a number, the dot that follows a thumb and the travel of a knob are
# geometry, and geometry is the panel's: a shape parameterised by a number is
# not a shape that can be drawn once. It is the same split BadgeArt already
# makes between a button and the label set into it.
CONTROLS_TO_DRAW = (
    ("dial", "face", "dial-face.svg"),
    ("dial", "ticks", "dial-ticks.svg"),
    ("dial", "thumb", "dial-thumb.svg"),
    ("switch", "body", "switch-body.svg"),
    ("switch", "knob", "switch-knob.svg"),
    ("chev", "left", "chev-left.svg"),
    ("chev", "right", "chev-right.svg"),
    ("media", "play", "media-play.svg"),
    ("media", "pause", "media-pause.svg"),
    ("media", "next", "media-next.svg"),
    ("media", "prev", "media-prev.svg"),
    ("tile", "grip", "grip.svg"),
)

# The grounds a menu tile is drawn on - one per state, so which state a tile
# is in is a thing about its *outline* rather than only about its colour. A
# theme whose accent is close to its surface leaves a selection to the border
# alone, and a border is the thinnest thing on the tile.
#
# This is the one drawing in this folder that answers to a size, and it
# answers by not being one drawing: **the corner is art and the four edges
# between the corners are a number.** A tile is `w` cells by `h` rows and a
# shape cannot stretch - that is the rule the slider's travel and the dial's
# zone are not drawn under - but a *corner* is not parameterised by anything,
# and a straight edge does not need to be drawn to be right.
#
# So the source is a quarter: the corner, with the box it turns in filled in
# behind it. `corner_run` takes the run from one edge to the other out of it
# and the generated function sets that run at all four corners, rotating it
# rather than mirroring it - a rotation carries an arc's sweep through
# unchanged, and a mirror would have to flip every one of them.
GROUNDS_TO_DRAW = (
    ("plain", "ground-plain.svg"),
    ("selected", "ground-selected.svg"),
    ("carried", "ground-carried.svg"),
)

# How each corner is turned to reach its own corner of the tile, clockwise
# from the top left, and where in the tile the turned run starts. A quarter is
# drawn as the top left corner and nothing else is drawn at all.
TURNS = (
    ("tl", 0, lambda x, y, c: (x, y)),
    ("tr", 90, lambda x, y, c: (c - y, x)),
    ("br", 180, lambda x, y, c: (c - x, c - y)),
    ("bl", 270, lambda x, y, c: (y, c - x)),
)

ATTR = re.compile(r'([-a-zA-Z:]+)\s*=\s*"([^"]*)"')
ELEMENT = re.compile(r"<(svg|path|circle|rect)\b([^>]*)>")


class Shape(object):
    """One hand-drawn button: everything it fills.

    Fill and nothing else, because a badge is the drawing scaled to whatever
    box the surface gave it and a stroke is not: its weight is in pixels, so a
    line drawn as one stays a hairline on a badge twice the size and vanishes
    entirely where the surface paints the shape solid. The rim of a stick is
    the case that taught this - see `stick.svg`, where it is an annulus in the
    same fill, two units thick at every size and in both badge styles.
    """

    def __init__(self, path):
        with open(path) as handle:
            text = handle.read()
        self.name = os.path.basename(path)
        self.fills = []
        # Figma writes `fill="none"` on the root and lets it inherit, so an
        # element that carries no fill of its own is not filled even though
        # SVG's own default fill is black.
        inherited = "black"
        for tag, attrs in ELEMENT.findall(text):
            attrs = dict(ATTR.findall(attrs))
            if tag == "svg":
                inherited = attrs.get("fill", inherited)
                self.width = float(attrs.get("width", 0))
                self.height = float(attrs.get("height", 0))
                box = attrs.get("viewBox", "").split()
                if len(box) == 4:
                    if [float(v) for v in box[:2]] != [0.0, 0.0]:
                        raise ValueError("%s: viewBox must start at 0 0"
                                         % self.name)
                    self.width, self.height = float(box[2]), float(box[3])
                continue
            if tag == "path":
                data = attrs.get("d", "")
            elif tag == "circle":
                data = svgpath.circle_path(float(attrs.get("cx", 0)),
                                           float(attrs.get("cy", 0)),
                                           float(attrs.get("r", 0)))
            else:
                raise ValueError("%s: <%s> is not supported" % (self.name, tag))
            fill = attrs.get("fill", inherited)
            if fill and fill != "none":
                self.fills.append(data)
            elif attrs.get("stroke", "none") != "none":
                raise ValueError(
                    "%s: a stroke does not scale with the badge - draw the "
                    "line as fill, the way stick.svg draws its rim"
                    % self.name)
        if not self.fills:
            raise ValueError("%s: nothing filled to punch a label through"
                             % self.name)
        if not self.width or not self.height:
            raise ValueError("%s: no size" % self.name)


def label_paths(font, text, size, origin_x, baseline_y):
    """Every glyph of `text` as path data, set at `size` px per em."""
    scale = float(size) / font.units_per_em
    paths = []
    pen = origin_x
    for char in text:
        paths.append(font.glyph_path(char, scale, pen, baseline_y))
        pen += font.advance(char) * scale
    return paths


def label_extent(font, text, size):
    """(width, height, left, top) of the label's ink, at `size` px per em."""
    scale = float(size) / font.units_per_em
    xs, ys = [], []
    pen = 0.0
    for char in text:
        glyph = font.cmap.get(ord(char))
        if glyph is None:
            raise ValueError("Fira Code has no glyph for %r" % char)
        for contour in font.contours(glyph):
            for x, y, _ in contour:
                xs.append(pen + x * scale)
                ys.append(-y * scale)
        pen += font.advance(char) * scale
    if not xs:
        raise ValueError("%r draws nothing" % text)
    return max(xs) - min(xs), max(ys) - min(ys), min(xs), min(ys)


def fit(font, shape, text):
    """Place `text` in `shape`: the paths, and how they were sized.

    The size starts from the cap height the examples used and comes down only
    as far as the shape makes it. Nothing shipped comes down at all: a shape
    that will not carry its own label at the cap every other badge is set at
    is the wrong shape for that many characters, and `MIN_SCALE` is where the
    generator says so instead of shipping something unreadable.
    """
    mask = place.shape_mask(shape.fills, shape.width, shape.height)
    field = place.distance_field(mask)
    full = CAP_RATIO * shape.height * font.units_per_em / font.cap_height
    size = full
    while size >= full * MIN_SCALE:
        width, height, left, top = label_extent(font, text, size)
        spot = place.best_centre(mask, field, width + MIN_PADDING * 2,
                                 height + MIN_PADDING * 2)
        if spot is not None:
            cx, cy, clearance = spot
            paths = label_paths(font, text, size,
                                cx - width / 2.0 - left,
                                cy - height / 2.0 - top)
            return paths, size, cx, cy, clearance
        size *= 0.96
    raise ValueError("%r does not fit %s at any readable size"
                     % (text, shape.name))


def svg_file(shape, label_paths_data):
    """The button with its label punched through, as a standalone SVG.

    One path with `evenodd`, which is how a hole works without having to care
    which way round either outline was drawn.
    """
    lines = ['<svg width="%g" height="%g" viewBox="0 0 %g %g" fill="none"'
             ' xmlns="http://www.w3.org/2000/svg">'
             % (shape.width, shape.height, shape.width, shape.height)]
    lines.append('<path fill-rule="evenodd" clip-rule="evenodd" d="%s"'
                 ' fill="white"/>'
                 % "".join(shape.fills + label_paths_data))
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def entry(shape, label):
    """One badge for the shell: the shape, and the label already set into it."""
    made = {"w": shape.width, "h": shape.height,
            "shape": "".join(shape.fills), "label": label}
    if label:
        # Where the label's own ink sits, in the shape's units. A surface that
        # wants the mark and not the button it is drawn on - the game bar's
        # menu, which is one wide pill with a mark and a word in it - can only
        # place and scale it if it knows this, and only this side does.
        made.update(zip(("mx", "my", "mw", "mh"), ink_box(label)))
    return made


def ink_box(data):
    """(x, y, width, height) of everything `data` draws."""
    xs, ys = [], []
    for poly in svgpath.flatten(data):
        for x, y in poly:
            xs.append(x)
            ys.append(y)
    if not xs:
        raise ValueError("a label that draws nothing")
    return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)


def qml_file(entries, bare, font_cap):
    """The same geometry for the shell, with the colours left out."""
    head = '''// Every controller button omapad badges, as path data.
//
// GENERATED by assets/generate.py from assets/shapes/*.svg and fonts/ -
// do not edit. Redraw the shape or change the label table there and run the
// script again.
//
// Path data rather than the SVGs beside it because a badge is painted in the
// theme's colours: the guide tints it with the menu's text colour, the game
// bar with whatever the wallpaper made the bar's foreground. An SVG carries
// the colour it was drawn with, so it cannot answer to either. The shape and
// the label are kept apart for the same reason - the guide fills the shape
// faintly behind a solid label, the bar draws it as an outline.
//
// Coordinates are in the shape's own units (`w` x `h`); a Shape scales them.
// The label is already centred where the shape is roomiest, so nothing here
// needs a per-surface nudge to look centred.
import QtQuick

QtObject {
  id: art

  // Fira Code, shipped in fonts/ beside this file. Loaded here rather than
  // per surface because the labels below are this font's outlines: a badge
  // whose drawn label and whose typed fallback came from two different faces
  // would read as two different badges.
  readonly property FontLoader loader: FontLoader {
    source: Qt.resolvedUrl("fonts/FiraCode-Medium.ttf")
  }
  readonly property string family: loader.status === FontLoader.Ready
    ? loader.name : "monospace"

  // What to set a *typed* label at so it stands as tall as a drawn one:
  // `CAP_RATIO` over this font's own cap height, in ems. Multiply by the
  // height of the shape the label sits on, in badge pixels. Generated rather
  // than typed into a surface, because it is only right for as long as it
  // agrees with the size the generator punches labels at.
  readonly property real capSize: %(cap_size).4f

  // And how tall that is as a fraction of the shape it stands on, which is
  // what a mark drawn instead of a letter should measure too.
  readonly property real capRatio: %(cap_ratio).4f

  // How tall a drawn mark stands in a system shape's own units. The game bar
  // draws the menu door's mark outside its badge and sets the word beside it
  // from this, so the two match on every pad rather than on whichever one the
  // mark's own ink happened to round with.
  readonly property real markCap: %(mark_cap)g

  readonly property var buttons: ({
'''
    body = []
    for key in sorted(entries):
        made = entries[key]
        fields = ['w: %g' % made["w"], 'h: %g' % made["h"],
                  'shape: "%s"' % made["shape"],
                  'label: "%s"' % made["label"]]
        if "mx" in made:
            fields.extend('%s: %g' % (name, made[name])
                          for name in ("mx", "my", "mw", "mh"))
        body.append('    "%s": { %s }' % (key, ", ".join(fields)))
    tail = '''  })

  // The shapes on their own, for a label no pad here is printed with - a
  // remapped button, a profile someone added. The shell draws its own text
  // into these in Fira Code, which is the face the labels above are set in.
  readonly property var shapes: ({
'''
    shapes = []
    for key in sorted(bare):
        made = bare[key]
        fields = ['w: %g' % made["w"], 'h: %g' % made["h"],
                  'shape: "%s"' % made["shape"]]
        shapes.append('    "%s": { %s }' % (key, ", ".join(fields)))
    foot = '''  })

  // A left shoulder and a right one are different shapes, and a badge row
  // only carries the printed label, so the side is read back off that: R is
  // in every right-hand label on either pad - R, RB, RT, ZR, R3 - and in none
  // of the left-hand ones.
  function side(label) {
    return String(label).indexOf("R") >= 0 ? "r" : "l"
  }

  // The drawn button for a badge, or null when there is none and the caller
  // should fall back to a shape with text in it.
  function find(kind, label) {
    var found = art.buttons[kind + ":" + label]
    return found !== undefined ? found : null
  }

  // The bare shape for a badge, or null when that kind is not drawn here -
  // the D-pad and the small system buttons are still the shell's own.
  function shape(kind, label) {
    var found = art.shapes[kind + ":" + art.side(label)]
    if (found === undefined) found = art.shapes[kind]
    return found !== undefined ? found : null
  }
}
'''
    head = head % {"cap_size": CAP_RATIO * font_cap, "cap_ratio": CAP_RATIO,
                   "mark_cap": SYSTEM_MARK_CAP}
    return head + ",\n".join(body) + "\n" + tail + ",\n".join(shapes) + "\n" + foot


def _near(point, want, slack=1e-6):
    return (abs(point[0] - want[0]) < slack and abs(point[1] - want[1]) < slack)


def corner_run(shape):
    """The corner itself, out of the quarter it is drawn as.

    Drawn clockwise, the way a tile's own outline runs: in at `0, c` off the
    left edge, round the corner, out at `c, 0` onto the top edge, then back
    through `c, c` to close the quarter. Everything up to that last corner is
    the drawing; the two sides that close it are the tile's own edges, and a
    tile is as wide as it is.

    Raises on a quarter drawn any other way. A corner that does not start and
    end on the box's edges cannot be set at four corners of a rectangle - the
    edges between them would not meet it - and the symptom is a ground that
    draws as a crumpled star rather than as a tile.
    """
    if len(shape.fills) != 1:
        raise ValueError("%s: a corner is one filled path, not %d"
                         % (shape.name, len(shape.fills)))
    if shape.width != shape.height:
        raise ValueError("%s: a corner turns in a square, not %g by %g"
                         % (shape.name, shape.width, shape.height))
    size = shape.width
    parts = svgpath.segments(shape.fills[0])
    if not parts or parts[0][0] != "M" or not _near(parts[0][1], (0, size)):
        raise ValueError("%s: a corner comes in off the left edge, so the "
                         "quarter starts at 0,%g" % (shape.name, size))
    run = []
    cur = (0.0, size)
    for part in parts[1:]:
        # The box's own inner corner closes the quarter and is not drawn.
        if part[0] == "Z" or _near(part[-1], (size, size)):
            break
        run.append(part)
        cur = part[-1]
    if not run:
        raise ValueError("%s: nothing drawn between the two edges"
                         % shape.name)
    if not _near(cur, (size, 0)):
        raise ValueError("%s: a corner goes out onto the top edge at %g,0 - "
                         "this one stops at %g,%g"
                         % (shape.name, size, cur[0], cur[1]))
    return size, run


def turned(run, size, turn, place):
    """One corner run, rotated into place, as relative commands.

    Relative so the run is the same wherever the corner it belongs to lands:
    only the point it starts from depends on how wide the tile is, and the
    generated function is what computes that. Each command is `[letter,
    numbers...]` rather than a string, because the shell scales the corner
    down on a tile too small to hold four of them, and a string cannot be
    scaled without being parsed again.
    """
    out = []
    cur = place(0.0, size, size)
    for part in run:
        kind = part[0]
        if kind == "A":
            rx, ry, rotation, large, sweep, end = part[1:]
            end = place(end[0], end[1], size)
            # A rotation carries the sweep through: it is the mirror that
            # would have to flip it, and nothing here mirrors. The arc's own
            # x-axis rotation is the one number a mapped endpoint cannot say.
            out.append(["a", rx, ry, (rotation + turn) % 360.0, large, sweep,
                        end[0] - cur[0], end[1] - cur[1]])
            cur = end
        else:
            points = [place(x, y, size) for (x, y) in part[1:]]
            numbers = []
            # Every point of a relative curve is measured from where the
            # command started, not from the point before it.
            for point in points:
                numbers.extend([point[0] - cur[0], point[1] - cur[1]])
            out.append([kind.lower()] + numbers)
            cur = points[-1]
    return out


def grounds_qml(entries):
    """The tile grounds, as a function of the box a tile turned out to be."""
    head = '''// The ground a menu tile is drawn on, one outline per state.
//
// GENERATED by assets/generate.py from assets/shapes/ground-*.svg - do not
// edit. Redraw a corner or change the table there and run the script again.
//
// **The corner is drawn art; the edges between the corners are a number.** A
// tile is `w` cells by `h` rows, and a shape scaled by one factor cannot be a
// rectangle of any aspect - which is the rule the slider\'s travel and the
// dial\'s shaded zone are not drawn under. A corner is not parameterised by
// anything, though, and a straight edge does not have to be drawn to be
// right, so a ground is the one and the other: the same quarter set at four
// corners with lines run between them.
//
// Why at all, when a Rectangle has a radius: a radius is the only outline a
// Rectangle has, and the states of a tile want more than one. A theme whose
// accent sits close to its surface leaves a selection to the border alone,
// and the border is the thinnest thing on the tile.
//
// The corner is rotated into its four places rather than mirrored, because a
// rotation carries an arc\'s sweep flag through unchanged and a mirror would
// have to flip every one of them.
import QtQuick

QtObject {
  id: art

  readonly property var grounds: ({
'''
    body = []
    for name in sorted(entries):
        made = entries[name]
        parts = ["corner: %g" % made["corner"]]
        for key, _turn, _place in TURNS:
            runs = ", ".join(
                "[%s]" % ", ".join(
                    ('"%s"' % n) if isinstance(n, str) else ("%g" % n)
                    for n in command)
                for command in made[key])
            parts.append("%s: [%s]" % (key, runs))
        body.append('    "%s": { %s }' % (name, ", ".join(parts)))
    foot = '''  })

  // An arc\'s rotation and its two flags are not lengths, so they are the
  // three arguments a corner being scaled down leaves alone.
  function scaled(commands, factor) {
    var out = ""
    for (var i = 0; i < commands.length; i++) {
      var command = commands[i]
      out += command[0]
      for (var j = 1; j < command.length; j++) {
        var flag = command[0] === "a" && j >= 3 && j <= 5
        out += (j > 1 ? " " : "") + (flag ? command[j] : command[j] * factor)
      }
    }
    return out
  }

  // The outline of a tile `w` by `h` with `corner` pixels of drawing in each
  // corner. Clockwise from where the left edge runs into the top left corner,
  // so the fill rule sees one contour wound one way whatever the state is.
  //
  // The corner shrinks rather than the tile: four corners of a tile narrower
  // than two of them would overlap, and an outline that crosses itself is
  // painted with a hole in it.
  function ground(name, w, h, corner) {
    var found = art.grounds[name]
    if (found === undefined || w <= 0 || h <= 0) return ""
    var c = Math.min(corner, w / 2, h / 2)
    var factor = c / found.corner
    return "M0 " + c + art.scaled(found.tl, factor)
      + "L" + (w - c) + " 0" + art.scaled(found.tr, factor)
      + "L" + w + " " + (h - c) + art.scaled(found.br, factor)
      + "L" + c + " " + h + art.scaled(found.bl, factor)
      + "Z"
  }
}
'''
    return head + ",\n".join(body) + "\n" + foot


def controls_qml(entries):
    """The control furniture for the shell, with the colours left out."""
    head = '''// Every part omapad draws a control tile from, as path data.
//
// GENERATED by assets/generate.py from assets/shapes/*.svg - do not edit.
// Redraw the shape or change the table there and run the script again.
//
// **Not a font.** The TrueType half of the generator exists to turn letters
// into outlines so they can be punched out of a button; nothing here has a
// letter in it, so nothing here goes near it. What is generated is the same
// path data with that step skipped.
//
// Only the furniture is here - what does not depend on the value. The arc
// that follows a number, the dot that follows a thumb and the travel of a
// knob are geometry, and geometry is the panel's: a shape parameterised by a
// number cannot be drawn once. It is the same split BadgeArt already makes
// between a button and the label set into it.
//
// Coordinates are in the shape's own units (`w` x `h`); a Shape scales them.
// Painted by BadgeArt, like any other drawn entry.
import QtQuick

QtObject {
  id: art

  readonly property var controls: ({
'''
    body = []
    for key in sorted(entries):
        made = entries[key]
        body.append('    "%s": { w: %g, h: %g, shape: "%s" }'
                    % (key, made["w"], made["h"], made["shape"]))
    foot = '''  })

  // One part, or null where that family has no such part - a caller that
  // asked for one is a control shipped with a hole in it, which
  // tests/test_assets.py is what notices.
  function find(family, name) {
    var found = art.controls[family + ":" + name]
    return found !== undefined ? found : null
  }
}
'''
    return head + ",\n".join(body) + "\n" + foot


def build(report=None):
    """Everything the generator produces: {filename: text}, plus the QML.

    Nothing is written here, so a test can build the same bytes and compare
    them with what is checked in - forgetting to re-run this after redrawing a
    shape is the one mistake that leaves the shell drawing yesterday's button.
    """
    font = truetype.Font(FONT)
    svgs = {}
    entries = {}
    bare = {}
    for kind, side, filename, labels in BUTTONS_TO_DRAW:
        shape = Shape(os.path.join(SHAPES, filename))
        for label in labels:
            paths, size, cx, cy, clearance = fit(font, shape, label)
            name = "%s%s-%s.svg" % (kind, "-" + side if side else "",
                                    label.lower())
            svgs[name] = svg_file(shape, paths)
            entries["%s:%s" % (kind, label)] = entry(shape, "".join(paths))
            key = kind if side is None else "%s:%s" % (kind, side)
            bare.setdefault(key, entry(shape, ""))
            if report is not None:
                report("%-22s cap %5.2f  at (%.1f, %.1f)  clearance %.2f"
                       % (name, size * font.cap_height / font.units_per_em,
                          cx, cy, clearance))
    for kind, label, name, base, overlay in ICONS_TO_DRAW:
        shape = Shape(os.path.join(SHAPES, base))
        mark = Shape(os.path.join(SHAPES, overlay))
        # Filled rather than stroked is `Shape`'s own rule now, and it raises.
        if (mark.width, mark.height) != (shape.width, shape.height):
            raise ValueError("%s: drawn on a different grid from %s"
                             % (mark.name, shape.name))
        name = "%s-%s.svg" % (kind, name)
        svgs[name] = svg_file(shape, mark.fills)
        entries["%s:%s" % (kind, label)] = entry(shape, "".join(mark.fills))
        if report is not None:
            report("%-22s %s, drawn not typed" % (name, label))
    # Written to the QML only: a shape the shell types into is half a badge,
    # and half a badge is not something to hand a README.
    for kind, side, filename in BLANKS_TO_DRAW:
        shape = Shape(os.path.join(SHAPES, filename))
        key = kind if side is None else "%s:%s" % (kind, side)
        bare[key] = entry(shape, "")
        if report is not None:
            report("%-22s blank, the shell types into it" % key)
    # No SVG beside these: a dial is not a button, and half a control is not
    # something to hand a README - the same argument the blanks above carry.
    controls = {}
    for family, name, filename in CONTROLS_TO_DRAW:
        shape = Shape(os.path.join(SHAPES, filename))
        controls["%s:%s" % (family, name)] = entry(shape, "")
        if report is not None:
            report("%-22s control furniture" % ("%s:%s" % (family, name)))
    # No SVG beside these either, and for a stronger reason than the controls
    # have: a ground is not a drawing until it is told how big a tile is, so
    # there is nothing here that a file could hold.
    grounds = {}
    for name, filename in GROUNDS_TO_DRAW:
        shape = Shape(os.path.join(SHAPES, filename))
        size, run = corner_run(shape)
        made = {"corner": size}
        for key, turn, place in TURNS:
            made[key] = turned(run, size, turn, place)
        grounds[name] = made
        if report is not None:
            report("%-22s tile ground, %d command%s of corner"
                   % (name, len(run), "" if len(run) == 1 else "s"))
    # Ems per cap height: what a typed label has to be set at to match a
    # punched one, which only this side knows.
    return (svgs,
            qml_file(entries, bare,
                     float(font.units_per_em) / font.cap_height),
            controls_qml(controls),
            grounds_qml(grounds))


def main():
    svgs, qml, controls, grounds = build(report=print)
    if not os.path.isdir(BUTTONS):
        os.makedirs(BUTTONS)
    for stale in os.listdir(BUTTONS):
        if stale.endswith(".svg") and stale not in svgs:
            os.remove(os.path.join(BUTTONS, stale))
    for name, text in svgs.items():
        with open(os.path.join(BUTTONS, name), "w") as handle:
            handle.write(text)
    with open(QML, "w") as handle:
        handle.write(qml)
    with open(CONTROL_QML, "w") as handle:
        handle.write(controls)
    with open(TILE_QML, "w") as handle:
        handle.write(grounds)
    print("wrote %d buttons, %s, %s and %s"
          % (len(svgs), os.path.relpath(QML, HERE),
             os.path.relpath(CONTROL_QML, HERE),
             os.path.relpath(TILE_QML, HERE)))


if __name__ == "__main__":
    main()
