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
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "assets"))

import generate
import svgpath

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
    are drawn even and the strokes around them whole.

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
            data = list(shape.fills) + [path for path, _ in shape.strokes]
            for edge in self.flat_edges(data):
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
