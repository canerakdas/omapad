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

from omapad import config, guide, menu


class AssetsAreCurrent(unittest.TestCase):
    def setUp(self):
        (self.svgs, self.qml, self.controls,
         self.grounds) = generate.build()

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

    def test_the_shell_plugin_draws_the_same_controls(self):
        with open(generate.CONTROL_QML) as handle:
            self.assertEqual(handle.read(), self.controls,
                             "ControlArt.qml is stale: run "
                             "python3 assets/generate.py")

    def test_the_control_art_carries_no_font(self):
        # The TrueType half of the generator turns letters into outlines so
        # they can be punched out of a button. Nothing here has a letter in
        # it, so a FontLoader arriving in this file means somebody has started
        # building the font this was deliberately not.
        self.assertNotIn("FontLoader", self.controls)
        # The field, not the word: the header comment says why there is no
        # label here, and a test that could not tell the two apart would fail
        # on its own explanation.
        self.assertNotIn('label: "', self.controls)

    def test_the_shell_plugin_draws_the_same_grounds(self):
        with open(generate.TILE_QML) as handle:
            self.assertEqual(handle.read(), self.grounds,
                             "TileArt.qml is stale: run "
                             "python3 assets/generate.py")

    def test_every_state_the_menu_draws_a_tile_in_has_a_ground(self):
        # The menu names a ground rather than asking for one, so a state whose
        # drawing is missing does not fall back to anything - `ground()`
        # returns an empty path and the tile is drawn as nothing at all.
        with open(os.path.join(ROOT, "shell-plugin", "Menu.qml")) as handle:
            menu_qml = handle.read()
        found = re.search(r"property string outline:(.*?)\n\s*\n",
                          menu_qml, re.S)
        self.assertIsNotNone(found, "Menu.qml no longer names a ground")
        wanted = set(re.findall(r'"(\w+)"', found.group(1)))
        drawn = set(name for name, _ in generate.GROUNDS_TO_DRAW)
        for name in sorted(wanted):
            self.assertIn(
                name, drawn,
                "Menu.qml draws a tile on the %r ground, which "
                "GROUNDS_TO_DRAW does not generate" % name)


class GroundsCloseOnTheirOwnBox(unittest.TestCase):
    """A ground is four corners and four edges, and has to come out a tile.

    The one drawing here that answers to a size, so the one that can be wrong
    at a size nobody drew it at. Everything else is checked by being compared
    with what is on disk; this has to be *run* - built at a few shapes of tile
    and measured - because the corner is rotated into three places it was not
    drawn in, and a rotation that is off by a quarter turn still generates.

    Three things say it came out a tile: one closed contour, a bounding box
    that is exactly the tile, and a winding that does not change with the
    state. The last is what a fill rule needs - BadgeArt paints even-odd in
    the stencil style, and a ground wound the other way in one state would be
    the state that draws as a hole.
    """

    # A wide tile, a square one, a tall one, and one too small to hold four
    # corners at all - which is the case that makes `ground()` shrink the
    # corner rather than let the outline cross itself.
    BOXES = ((240.0, 68.0, 12.0), (68.0, 68.0, 12.0), (68.0, 208.0, 12.0),
             (400.0, 144.0, 24.0), (10.0, 8.0, 12.0))

    def setUp(self):
        _, _, _, self.qml = generate.build()
        self.grounds = {}
        for name, filename in generate.GROUNDS_TO_DRAW:
            shape = generate.Shape(os.path.join(generate.SHAPES, filename))
            size, run = generate.corner_run(shape)
            made = {"corner": size}
            for key, turn, place in generate.TURNS:
                made[key] = generate.turned(run, size, turn, place)
            self.grounds[name] = made

    def path(self, ground, w, h, corner):
        """What TileArt.ground() builds, in Python. Kept in step by the test
        below, which fails when the generated function stops saying this."""
        def scaled(commands, factor):
            out = ""
            for command in commands:
                out += command[0]
                for i in range(1, len(command)):
                    flag = command[0] == "a" and 3 <= i <= 5
                    out += (" " if i > 1 else "") + "%g" % (
                        command[i] if flag else command[i] * factor)
            return out

        c = min(corner, w / 2.0, h / 2.0)
        factor = c / ground["corner"]
        return ("M0 %g" % c + scaled(ground["tl"], factor)
                + "L%g 0" % (w - c) + scaled(ground["tr"], factor)
                + "L%g %g" % (w, h - c) + scaled(ground["br"], factor)
                + "L%g %g" % (c, h) + scaled(ground["bl"], factor) + "Z")

    def test_every_ground_comes_out_the_box_it_was_asked_for(self):
        for name in sorted(self.grounds):
            for (w, h, corner) in self.BOXES:
                data = self.path(self.grounds[name], w, h, corner)
                polys = svgpath.flatten(data)
                self.assertEqual(
                    len(polys), 1,
                    "the %s ground of a %gx%g tile is %d contours, not one: "
                    "an outline that crosses itself is painted with a hole"
                    % (name, w, h, len(polys)))
                xs = [x for (x, _) in polys[0]]
                ys = [y for (_, y) in polys[0]]
                for got, want, edge in ((min(xs), 0.0, "left"),
                                        (min(ys), 0.0, "top"),
                                        (max(xs), w, "right"),
                                        (max(ys), h, "bottom")):
                    self.assertAlmostEqual(
                        got, want, places=6,
                        msg="the %s ground of a %gx%g tile has its %s edge at "
                            "%g, not %g - a corner rotated into the wrong "
                            "place" % (name, w, h, edge, got, want))

    def test_every_ground_is_wound_the_same_way_round(self):
        for name in sorted(self.grounds):
            data = self.path(self.grounds[name], 240.0, 68.0, 12.0)
            poly = svgpath.flatten(data)[0]
            area = 0.0
            for i in range(len(poly)):
                (x0, y0) = poly[i]
                (x1, y1) = poly[(i + 1) % len(poly)]
                area += x0 * y1 - x1 * y0
            # Clockwise, with y down the screen, which is a positive area.
            self.assertGreater(
                area, 0,
                "the %s ground is wound the other way from the rest: under an "
                "even-odd fill it is the state that draws as a hole" % name)

    def test_the_shell_builds_the_outline_the_same_way(self):
        # `path()` above is this test's own copy of `TileArt.ground()`, and a
        # copy is only worth anything while it is the same copy. These are the
        # four edges it runs between the corners, in order.
        for line in ('"M0 " + c + art.scaled(found.tl, factor)',
                     '"L" + (w - c) + " 0" + art.scaled(found.tr, factor)',
                     '"L" + w + " " + (h - c) + art.scaled(found.br, factor)',
                     '"L" + c + " " + h + art.scaled(found.bl, factor)'):
            self.assertIn(line, self.qml,
                          "TileArt.ground() no longer builds the outline the "
                          "way this test does")
        self.assertIn("Math.min(corner, w / 2, h / 2)", self.qml,
                      "TileArt.ground() no longer shrinks the corner on a "
                      "tile too small to hold four of them")


class CornersAreDrawnToBeTurned(unittest.TestCase):
    """A quarter that cannot be set at four corners draws a crumpled star.

    `corner_run` raises on each of these, which is the whole point of it: the
    corner is drawn once and rotated into three places it was never seen in,
    so the drawing has to promise where it starts and where it stops. Nothing
    downstream could notice - a run that ends in the middle of the box still
    generates, still scales, and comes out as a tile with a dent in it.
    """

    QUARTER = ('<svg width="16" height="16" viewBox="0 0 16 16" fill="none" '
               'xmlns="http://www.w3.org/2000/svg">\n<path d="%s" '
               'fill="white"/>\n</svg>\n')

    def quarter(self, data):
        import tempfile
        handle = tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False)
        handle.write(self.QUARTER % data)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return generate.Shape(handle.name)

    def test_a_corner_that_comes_in_off_the_wrong_edge_raises(self):
        with self.assertRaises(ValueError):
            generate.corner_run(self.quarter("M0 0L16 0L16 16Z"))

    def test_a_corner_that_stops_short_of_the_top_edge_raises(self):
        with self.assertRaises(ValueError):
            generate.corner_run(self.quarter("M0 16L8 4L16 16Z"))

    def test_a_corner_drawn_on_a_rectangle_raises(self):
        shape = self.quarter("M0 16L16 0L16 16Z")
        shape.width = 32.0
        with self.assertRaises(ValueError):
            generate.corner_run(shape)

    def test_the_shipped_corners_all_pass(self):
        for name, filename in generate.GROUNDS_TO_DRAW:
            shape = generate.Shape(os.path.join(generate.SHAPES, filename))
            size, run = generate.corner_run(shape)
            self.assertEqual(size, shape.width)
            self.assertTrue(run, "%s: %s draws no corner" % (name, filename))


class EveryControlIsDrawn(unittest.TestCase):
    """A control tile cannot ship with a hole in it.

    The analogue of `EveryBadgeIsDrawn` one file along: a kind the daemon can
    send and the generator has no part for is a tile that draws blank, and
    nothing else in the tree would say so.
    """

    # What each kind of tile is drawn from. The daemon's `menu.CONTROLS` is
    # what may be declared; this is what each of them needs to exist.
    NEEDS = {
        # No zone: the shaded disc is a circle of *variable* radius, and a
        # drawing cannot stretch - the same argument the slider's track
        # carries, one shape along. `radius: width / 2` is what a circle of
        # any size is, and it keeps a one-pixel outline one pixel wide at the
        # two-percent values this setting is actually set to.
        "gauge": ("dial:face", "dial:ticks", "dial:thumb"),
        # The hands as well: what the time decides is the angle one is
        # turned to, and an angle is a transform rather than a shape. The hub
        # is here because the join under them is not parameterised by
        # anything either.
        "clock": ("clock:face", "clock:ticks", "clock:hub",
                  "clock:hour", "clock:minute"),
        # The clock's, and everything a chronograph adds on top. A register is
        # a disc and a hand drawn on the register's own canvas - one pair
        # turned to three angles and set in three places, because what a panel
        # decides about a register is where it sits and how big it is.
        "chrono": ("clock:face", "clock:ticks", "clock:hub",
                   "clock:hour", "clock:minute", "clock:sweep",
                   "clock:register", "clock:register-hand"),
        # **The dial's own rim**, because a knob is the same circle as the
        # gauge beside it and the clock under it - a page holding three
        # circles at three weights reads as a fault rather than as three
        # tiles - plus the two figures it turns: the pointer at the value and
        # the notch under a stop.
        #
        # Its *scale* is still not art, which is the one place it parts
        # company with the clock. The run of it the value has covered grows
        # with the number, and a track drawn once with that run computed
        # against it would be two drawings of one figure - which is exactly
        # how two drawings of one thing quietly stop matching. How many
        # notches there are is the panel's for the same reason: twelve marks
        # are the same twelve on every clock ever drawn, and a knob reading a
        # list of three has three where one reading a ladder of six has six.
        "knob": ("dial:face", "dial:pointer", "dial:notch"),
        "toggle": ("switch:body", "switch:knob"),
        "choice": ("chev:left", "chev:right"),
        # **The strokes on the line, not the line.** The line itself is as
        # long as the tile it sits in and a drawn shape cannot stretch - that
        # part is still geometry, and always was. What stands *on* it is four
        # drawings: how far a stroke reaches is two of them, and whether the
        # line runs through it or stops at it is the other two. A stepped
        # travel needs all three of these; the fourth (`end-open`) is the
        # card's, below.
        "slider": ("travel:end", "travel:stop", "travel:mark"),
        "media": ("media:play", "media:pause", "media:next", "media:prev"),
        # The slider's line with nothing to stand on it: a reading has no
        # stops, because what it answers is how far along a scale it has got
        # and the scale is the machine's rather than a list of places somebody
        # chose. So the two ends and the mark, and no `stop`.
        "readout": ("travel:end", "travel:mark"),
        # Nothing, and it reached for art three times to get here. A tick at
        # the far end of the row said nothing - a mark with no second state,
        # at the opposite end of the card from the words it is about. A radio
        # ring at the head of each row said more and was a second drawing for
        # something the row can simply *be*. A pointer on the line said it
        # best and was still one shape too many: the line it stood on already
        # changes colour at that row, and a card whose whole argument is that
        # a row has nothing to show but its name is the last place to spend a
        # drawing on saying which row.
        #
        # What is left is a **hairline** of extra weight where the line is
        # lit, which is the silhouette the colour needs beside it (qml.md
        # 8.1.1). Like the ground under the cursor and the spine itself, it is
        # the slider's track argument one shape along: a rectangle as tall as
        # whatever it is drawn on, which no drawing can be.
        #
        # **The card is the travel stood up**, so what stands on its line is
        # the travel's own drawing turned a quarter: `end-open` at both ends,
        # where the line carries on past the crossing, and `side` for the two
        # marks that bracket the row in force - the one stroke on either
        # drawing that leaves the line on one side, because what it marks is
        # the length behind it.
        #
        # And the key, where the card latches: a bank of switches has no one
        # row to point at, so the state is drawn on the row. Two drawings
        # rather than a fill switched, because the ring and the window are
        # painted in two colours.
        "rows": ("travel:end-open", "travel:side", "key:ring", "key:lit"),
    }

    # Drawn for a *state* rather than for a kind of tile: the grip is the mark
    # a tile wears while it is being carried, which belongs to edit mode and
    # to no control at all.
    ELSEWHERE = ("tile:grip",)

    def test_every_part_a_kind_needs_is_generated(self):
        _, _, controls, _ = generate.build()
        for kind, parts in sorted(self.NEEDS.items()):
            for part in parts:
                self.assertIn(
                    '"%s"' % part, controls,
                    "%s is drawn with %s, which nothing generates"
                    % (kind, part))

    def test_nothing_is_generated_that_no_kind_is_drawn_from(self):
        # The other way round again: a shape nobody draws is weight in four
        # surfaces and a thing the next person has to work out is dead. The
        # dial's needle was one - drawn for a rotary the gauge turned out not
        # to be, since a stick has a position rather than a bearing.
        wanted = set(self.ELSEWHERE)
        for parts in self.NEEDS.values():
            wanted.update(parts)
        for family, name, _ in generate.CONTROLS_TO_DRAW:
            self.assertIn(
                "%s:%s" % (family, name), wanted,
                "%s:%s is generated and nothing is drawn from it"
                % (family, name))

    def test_every_declared_control_is_one_this_knows_how_to_draw(self):
        # The other direction: a control added to the daemon with no art and
        # no entry here would ship drawing nothing at all.
        drawn = set(self.NEEDS) | set(menu.CONTROLS)
        for kind in menu.CONTROLS:
            if kind == menu.ROW_BREAK:
                continue  # a gap is drawn by not being drawn
            self.assertIn(
                kind, self.NEEDS,
                "menu.CONTROLS has %r, which this test cannot say is drawn"
                % kind)
        self.assertTrue(drawn)


class AnnuliSurviveEitherFillRule(unittest.TestCase):
    """A ring drawn as two same-wound circles is a disc in the filled style.

    The rim of a stick was a stroked circle for exactly as long as it took
    somebody to turn the stencil style on and find the stick had no rim - and
    then a solid pill, because a ring among solid silhouettes reads as a
    different colour. The trap outlived the shape: a badge is painted
    `WindingFill` normally and
    `OddEvenFill` when the label is knocked out of it, so a hole only survives
    both where the two subpaths are wound the opposite way round.
    """

    # And the key at the head of a latching row, which is the first one of
    # these that is not a circle: a rounded square with a rounded square out
    # of the middle of it is the same trap with corners on.
    RINGS = ("dial-face.svg", "clock-face.svg", "key-ring.svg")

    def test_a_ring_is_wound_so_the_hole_survives(self):
        # A drawing may be more than one ring - the clock's rim is the case
        # and the chapter ring inside it, which is two - so what has to hold
        # is each pair on its own: an outer wound one way and its hole the
        # other, in that order. A shape that came out odd is a ring somebody
        # drew without a hole, and it would paint as a disc over everything
        # the face is meant to show through.
        for name in self.RINGS:
            shape = generate.Shape(os.path.join(generate.SHAPES, name))
            areas = []
            for data in shape.fills:
                for poly in svgpath.flatten(data):
                    areas.append(self.signed_area(poly))
            self.assertTrue(areas and len(areas) % 2 == 0,
                            "%s is %d subpaths, which is not a whole number "
                            "of rings" % (name, len(areas)))
            for outer, inner in zip(areas[0::2], areas[1::2]):
                self.assertLess(outer * inner, 0,
                                "%s: two subpaths of a ring wind the same "
                                "way, so the filled style paints it solid"
                                % name)

    def signed_area(self, poly):
        total = 0.0
        for i in range(len(poly)):
            x0, y0 = poly[i]
            x1, y1 = poly[(i + 1) % len(poly)]
            total += x0 * y1 - x1 * y0
        return total / 2


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

    # **The figures that turn are exempt, and it is the rule rather than a
    # hole in it.** What this test is about is a straight run landing on half
    # a pixel and being painted grey instead of drawn; a hand, a sweep, a
    # register's hand, a knob's pointer and the notch under a stop are all
    # drawn standing at twelve and then rotated to wherever a number puts
    # them, so their long edges are parallel to an axis at four angles out of
    # a full turn and antialiased at every other one. Holding them to the
    # grid would buy nothing and would cost the drawing: a hand is centred on
    # the pivot, so a whole-unit edge means an even width, and the sweep and
    # the minute hand would have to be the same weight as each other - which
    # is the one thing two hands on one face may not be.
    TURNS = ("clock-hour.svg", "clock-minute.svg", "clock-sweep.svg",
             "clock-register-hand.svg", "dial-pointer.svg", "dial-notch.svg")

    def test_every_flat_edge_of_every_shape_is_on_a_whole_unit(self):
        for name in sorted(os.listdir(generate.SHAPES)):
            if not name.endswith(".svg") or name in self.TURNS:
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

    # **The strokes on a line are exempt, and the exemption is the rule read
    # twice.** What the grid is for is a box a *surface* reserves: it rounds
    # `unit * w / h` and BadgeArt then scales by that rounded width, so the
    # aspect has to survive the rounding. Nothing reserves a box for these.
    # A travel hands the figure the line's own weight and takes the height the
    # drawing asks for, which is that weight times a whole number - five for a
    # stop, seven for an end - so the box is whole pixels on both sides at
    # every scale there is, and `Metrics.spine` reads its two reaches back off
    # these drawings rather than rounding its own.
    SIZED_BY_THE_LINE = "travel-"

    def test_the_grid_divides_every_shape_s_aspect(self):
        metrics = os.path.join(ROOT, "shell-plugin", "Metrics.qml")
        with open(metrics) as handle:
            found = re.search(r"badgeGrid:\s*(\d+)", handle.read())
        self.assertIsNotNone(found, "Metrics.qml no longer names a badgeGrid")
        grid = int(found.group(1))
        for name in sorted(os.listdir(generate.SHAPES)):
            if not name.endswith(".svg"):
                continue
            if name.startswith(self.SIZED_BY_THE_LINE):
                # And the one thing that does have to hold: a figure sized
                # from the line is only whole on both sides while its aspect
                # is a whole number of line weights.
                shape = generate.Shape(os.path.join(generate.SHAPES, name))
                ratio = max(shape.width, shape.height) / min(shape.width,
                                                             shape.height)
                self.assertEqual(
                    ratio, round(ratio),
                    "%s is %g by %g: a stroke is handed the line's own weight "
                    "and takes the height its aspect asks for, so an aspect "
                    "that is not a whole number of them lands off its box"
                    % (name, shape.width, shape.height))
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
        _, qml, _controls, _grounds = generate.build()
        self.assertIn("markCap: %g" % generate.SYSTEM_MARK_CAP, qml)


class EveryBadgeIsDrawn(unittest.TestCase):
    """Every label the daemon can print has to have a drawing behind it.

    Every layout, not just the connected pad's: a badge falls back to typed
    text, and a set where three consoles are drawn and the fourth label is a
    word reads as a bug rather than as a choice.
    """

    def test_no_badge_falls_back_to_typed_text(self):
        _, qml, _controls, _grounds = generate.build()
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
        _, qml, _controls, _grounds = generate.build()
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
        _, qml, _controls, _grounds = generate.build()
        for row in rows:
            self.assertIn('"%s:%s"' % (row["k"], row["b"]), qml)
