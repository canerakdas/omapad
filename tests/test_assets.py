"""The drawn buttons are generated; this is what says they are still current.

`assets/generate.py` turns the hand-drawn shapes and Fira Code into the SVGs
and into `shell-plugin/ButtonArt.qml`. Redrawing a shape and forgetting to run
it leaves the shell drawing yesterday's button, and nothing else would notice -
the daemon never reads any of this.

It also checks that every badge omapad can actually send has a drawing,
which is the other half of the same drift: a new logical button in `guide.py`
with no shape behind it falls back to typed text.
"""

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "assets"))

import generate
import svgpath
import truetype

from omapad import config, guide


class AssetsAreCurrent(unittest.TestCase):
    def setUp(self):
        self.svgs, self.qml = generate.build()

    def test_every_generated_svg_is_what_is_on_disk(self):
        on_disk = sorted(name for name in os.listdir(generate.BUTTONS)
                         if name.endswith(".svg"))
        self.assertEqual(sorted(self.svgs), on_disk,
                         "run python3 assets/generate.py")
        for name, text in self.svgs.items():
            with open(os.path.join(generate.BUTTONS, name)) as handle:
                self.assertEqual(handle.read(), text,
                                 "%s is stale: run python3 assets/generate.py"
                                 % name)

    def test_the_shell_plugin_draws_the_same_buttons(self):
        with open(generate.QML) as handle:
            self.assertEqual(handle.read(), self.qml,
                             "ButtonArt.qml is stale: run "
                             "python3 assets/generate.py")

    def test_every_shape_carries_a_label_of_each_kind_it_is_used_for(self):
        for kind, _, _, labels in generate.BUTTONS_TO_DRAW:
            for label in labels:
                self.assertIn('"%s:%s"' % (kind, label), self.qml)


class ShapesSitOnTheGrid(unittest.TestCase):
    """A flat edge drawn on half a unit is grey at every badge size there is.

    A badge is the shape scaled by `unit / h`, and `Metrics.badge` snaps the
    unit so the box comes out whole - but nothing can snap what is inside the
    drawing. An edge on 12.5 lands on a half pixel wherever a whole unit lands
    on a whole one, and the shell paints it as a smear instead of a line. It
    is what a seven-unit box centred on a sixteen-unit axis costs, so features
    are drawn even.

    Curves are exempt: only a straight run parallel to an axis has a single
    coordinate to land badly.
    """

    # Shorter than this and there is no edge to see, only the tangent where a
    # corner leaves its arc.
    SEEN = 1.5

    def test_every_flat_edge_of_every_shape_is_on_a_whole_unit(self):
        for name in sorted(os.listdir(generate.SHAPES)):
            if not name.endswith(".svg"):
                continue
            shape = generate.Shape(os.path.join(generate.SHAPES, name))
            for edge in self.flat_edges(shape.fills):
                axis, at, length = edge
                self.assertAlmostEqual(
                    at, round(at), places=6,
                    msg="%s: a %.1f unit edge at %s=%g is off the grid"
                        % (name, length, axis, at))

    def flat_edges(self, paths):
        """(axis, coordinate, length) for every straight run along an axis."""
        for data in paths:
            for poly in svgpath.flatten(data):
                for i in range(len(poly)):
                    (x0, y0) = poly[i]
                    (x1, y1) = poly[(i + 1) % len(poly)]
                    if abs(y1 - y0) < 1e-6 and abs(x1 - x0) > self.SEEN:
                        yield ("y", y0, abs(x1 - x0))
                    elif abs(x1 - x0) < 1e-6 and abs(y1 - y0) > self.SEEN:
                        yield ("x", x0, abs(y1 - y0))


class ShapesFitTheBadgeGrid(unittest.TestCase):
    """`Metrics.badgeGrid` has to divide every shape's aspect, or none does.

    A badge is the drawing scaled by one factor taken from the *width*, so the
    box a surface reserves has to be whole pixels on both sides: the surface
    rounds `unit * w / h` and BadgeArt then scales by that rounded width, and
    a drawing whose aspect the unit does not divide stands a fraction of a
    pixel off its own box - every flat edge in it painted grey rather than
    drawn. `Metrics.badge` snaps the unit up to the grid so the division comes
    out whole; the grid can only do that for the aspects it was chosen for.

    Nothing else notices. The stick was redrawn 44 by 32 to make room for two
    characters, which wants a unit divisible by eight where every other shape
    wants five, and the only symptom would have been a slightly soft badge.
    It is 56 by 40 for this reason and no other.
    """

    def test_the_grid_divides_every_shape_s_aspect(self):
        metrics = os.path.join(ROOT, "shell-plugin", "Metrics.qml")
        with open(metrics) as handle:
            found = re.search(r"badgeGrid:\s*(\d+)", handle.read())
        self.assertIsNotNone(found, "Metrics.qml no longer names a badgeGrid")
        grid = int(found.group(1))
        for name in sorted(os.listdir(generate.SHAPES)):
            if not name.endswith(".svg"):
                continue
            shape = generate.Shape(os.path.join(generate.SHAPES, name))
            self.assertEqual(
                (grid * shape.width) % shape.height, 0,
                "%s is %g by %g, whose aspect a %d-unit grid does not divide: "
                "a badge of it lands off its own box"
                % (name, shape.width, shape.height, grid))


class LabelsStandAtOneHeight(unittest.TestCase):
    """A shape too small for its label shrinks the letters, and says nothing.

    `fit` comes down in 4% steps until the label clears `MIN_PADDING`, which
    is the right thing to do with a shape it is handed - but a shipped shape
    that needs it is the wrong shape for what it carries, and the badge is
    the only place that shows. `L3` was punched at 12.39 units inside a
    26-unit circle where every other badge is set at 13.44, with a quarter of
    a unit to spare, so the two characters ran edge to edge while an `A` beside
    them sat in three units of air. The answer was to draw the stick wide, and
    this is what says a shape has not quietly gone back to shrinking its label.
    """

    def test_every_drawn_label_is_punched_at_the_full_cap(self):
        font = truetype.Font(generate.FONT)
        for kind, _, filename, labels in generate.BUTTONS_TO_DRAW:
            shape = generate.Shape(os.path.join(generate.SHAPES, filename))
            full = generate.CAP_RATIO * shape.height
            for label in labels:
                _, size, _, _, _ = generate.fit(font, shape, label)
                cap = size * font.cap_height / font.units_per_em
                self.assertAlmostEqual(
                    cap, full, places=3,
                    msg="%s is punched at %.2f on %s, where a label stands "
                        "%.2f: the shape is too small for %d characters"
                        % (label, cap, shape.name, full, len(label)))


class MarksStandAtOneHeight(unittest.TestCase):
    """A drawn label is a label, so it is set at the same cap the letters are.

    Nothing else notices when one is not. Four PlayStation symbols drawn 16,
    16, 14 and 13.1 units tall sat on four different baselines in the same
    row, and the three bars an Xbox prints on Menu were drawn 10 where every
    other system mark was 14 - which the game bar's menu door once divided by
    to size the word beside it, so the same pill came out a sixth larger on a
    Switch than on an Xbox. `generate.MARK_CAPS` is the height each shape
    holds its marks to, `ButtonArt.markCap` is the system one handed to the
    shell - the door draws the standard menu mark on its own grid and scales
    it against the word's capitals by this - and this is what says the
    drawings still agree with both.
    """

    def test_every_drawn_label_is_its_shape_s_cap_tall(self):
        for _, _, _, base, overlay in generate.ICONS_TO_DRAW:
            cap = generate.MARK_CAPS.get(base)
            if cap is None or overlay in generate.MARK_CAP_EXEMPT:
                continue
            mark = generate.Shape(os.path.join(generate.SHAPES, overlay))
            height = generate.ink_box("".join(mark.fills))[3]
            self.assertAlmostEqual(
                height, cap, places=3,
                msg="%s is %.4f units tall on %s, which holds its marks to %g"
                    % (overlay, height, base, cap))

    def test_every_drawn_label_is_centred_in_its_shape(self):
        """Off centre, a mark's two ends land on different subpixel phases.

        A badge is the drawing scaled by `unit / h`, and only the box comes
        out whole - so an edge inside it is painted at whatever fraction of a
        pixel it lands on. Mirrored about the middle, the top edge and the
        bottom one land on the *same* fraction and are painted alike. The
        PlayStation triangle sat a unit and a half low and the mute mic a unit
        high, and both read as one heavy end and one thin one.
        """
        for _, _, _, base, overlay in generate.ICONS_TO_DRAW:
            if base not in generate.MARK_CAPS:
                continue
            shape = generate.Shape(os.path.join(generate.SHAPES, base))
            mark = generate.Shape(os.path.join(generate.SHAPES, overlay))
            x, y, width, height = generate.ink_box("".join(mark.fills))
            for axis, low, size, span in (("x", x, width, shape.width),
                                          ("y", y, height, shape.height)):
                self.assertAlmostEqual(
                    low + size / 2.0, span / 2.0, places=3,
                    msg="%s sits at %s=%g in %s, whose middle is %g"
                        % (overlay, axis, low + size / 2.0, base, span / 2.0))

    def test_the_shell_is_told_the_system_cap(self):
        """The door scales its mark against the word's cap height by this, so
        a mark redrawn to another height has to reach the shell or it lands
        the wrong size beside the word."""
        _, qml = generate.build()
        self.assertIn("markCap: %g" % generate.SYSTEM_MARK_CAP, qml)


class EveryBadgeIsDrawn(unittest.TestCase):
    """Every label the daemon can print has to have a drawing behind it.

    Every layout, not just the connected pad's: a badge falls back to typed
    text, and a set where three consoles are drawn and the fourth label is a
    word reads as a bug rather than as a choice.
    """

    def test_no_badge_falls_back_to_typed_text(self):
        _, qml = generate.build()
        for layout in sorted(guide.LAYOUTS):
            for button, kind in sorted(guide.KINDS.items()):
                label = guide.badge_of(button, layout)
                self.assertIn('"%s:%s"' % (kind, label), qml,
                              "%s badges as %s on a %s pad and has no drawing"
                              % (button, label, layout))

    def test_every_kind_has_a_shape_of_its_own(self):
        """No surface draws a bordered rectangle any more, so nothing may
        arrive without a shape: a kind ButtonArt has never heard of would come
        out as bare text on the bar with nothing around it."""
        _, qml = generate.build()
        for kind in sorted(set(guide.KINDS.values())):
            self.assertTrue('"%s"' % kind in qml or '"%s:l"' % kind in qml,
                            "%s badges have no shape" % kind)

    def test_the_sticks_own_rows_are_drawn(self):
        """A stick carries a role as well as a click, badged L and R."""
        # The shipped defaults only: what someone's own config says about
        # their sticks is not what this is asking about.
        shipped = config.load(path=os.devnull, mapping=os.devnull,
                             settings=os.devnull)
        rows = guide._stick_rows(shipped, "base")
        self.assertTrue(rows)
        _, qml = generate.build()
        for row in rows:
            self.assertIn('"%s:%s"' % (row["k"], row["b"]), qml)
