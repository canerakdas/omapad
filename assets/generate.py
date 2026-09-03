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

# How much empty button has to be left around the label, in shape units. Only
# the crowded shapes ever reach it - two characters inside a stick click - and
# they are shrunk until they clear it.
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
    # and the stick itself, which the guide names by the side it is on.
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

ATTR = re.compile(r'([-a-zA-Z:]+)\s*=\s*"([^"]*)"')
ELEMENT = re.compile(r"<(svg|path|circle|rect)\b([^>]*)>")


class Shape(object):
    """One hand-drawn button: what is filled, and what is only stroked."""

    def __init__(self, path):
        with open(path) as handle:
            text = handle.read()
        self.name = os.path.basename(path)
        self.fills = []
        self.strokes = []
        # Figma writes `fill="none"` on the root and lets it inherit, so a
        # circle that only carries a stroke - the ring around a stick click -
        # is not filled even though SVG's own default fill is black.
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
                self.strokes.append((data, float(attrs.get("stroke-width", 1))))
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
    as far as the shape makes it - a stick click is a small circle and `L3` is
    two characters wide, so that one really does have to shrink.
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
    for data, width in shape.strokes:
        lines.append('<path d="%s" stroke="white" stroke-width="%g"'
                     ' fill="none"/>' % (data, width))
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def entry(shape, label):
    """One badge for the shell: the shape, and the label already set into it."""
    made = {"w": shape.width, "h": shape.height,
            "shape": "".join(shape.fills), "label": label}
    if shape.strokes:
        made["ring"] = "".join(data for data, _ in shape.strokes)
        made["ringWidth"] = shape.strokes[0][1]
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
        if made.get("ring"):
            fields.append('ring: "%s"' % made["ring"])
            fields.append('ringWidth: %g' % made["ringWidth"])
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
        if made.get("ring"):
            fields.append('ring: "%s"' % made["ring"])
            fields.append('ringWidth: %g' % made["ringWidth"])
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
        if mark.strokes:
            raise ValueError("%s: a drawn label is filled, not stroked"
                             % mark.name)
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
    # Ems per cap height: what a typed label has to be set at to match a
    # punched one, which only this side knows.
    return svgs, qml_file(entries, bare,
                          float(font.units_per_em) / font.cap_height)


def main():
    svgs, qml = build(report=print)
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
    print("wrote %d buttons and %s" % (len(svgs), os.path.relpath(QML, HERE)))


if __name__ == "__main__":
    main()
