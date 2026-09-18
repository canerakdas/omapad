"""What the plugin must be true of, read rather than run.

There is no QML runtime in the suite, so the rules whose failure is silent on
screen are checked by reading the files. A `Text` left to detect its own
format is exactly that kind of rule: it draws every string anyone has ever
typed correctly, and fetches a resource for the one a device named itself.
"""

import io
import json
import os
import re
import unittest

PLUGIN = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shell-plugin"
)

OPENS = re.compile(r"^(\s*)(?:\w+\s*:\s*)?Text \{\s*$")
OPENS_TRAVEL = re.compile(r"^(\s*)(?:\w+\s*:\s*)?Travel \{\s*$")
OPENS_KNOB = re.compile(r"^(\s*)(?:\w+\s*:\s*)?Knob \{\s*$")


def text_blocks(source, opens=OPENS):
    """Every `Text { … }` in one file, as (line number, body)."""
    lines = source.split("\n")
    blocks = []
    for index, line in enumerate(lines):
        if not opens.match(line):
            continue
        depth = 1
        body = []
        for follow in lines[index + 1:]:
            depth += follow.count("{") - follow.count("}")
            if depth <= 0:
                break
            body.append(follow)
        blocks.append((index + 1, "\n".join(body)))
    return blocks


class LiveStreamTests(unittest.TestCase):
    """The one rule whose failure costs everything the gauge phase bought."""

    # Anything that makes the scene work out where things go. `x`, `y`,
    # `scale`, `opacity` and a colour are the graphics scene's own and cost
    # nothing; a width, a height, a margin or a spacing is a layout pass, and
    # a layout pass sixty times a second throws away the whole point of a
    # push that carries no items.
    LAYOUT = re.compile(
        r"^\s*(?:width|height|implicitWidth|implicitHeight|spacing"
        r"|anchors\.\w*[Mm]argin|Layout\.\w+)\s*:.*\broot\.live\b")

    def test_nothing_binds_a_layout_to_the_live_stream(self):
        path = os.path.join(PLUGIN, "Menu.qml")
        with open(path) as handle:
            for number, line in enumerate(handle, 1):
                self.assertIsNone(
                    self.LAYOUT.match(line),
                    "Menu.qml:%d lays out from root.live, which is a layout"
                    " pass per frame" % number)

    def test_the_rule_is_written_down_where_somebody_would_break_it(self):
        # A test nobody can find the reason for is a test that gets deleted.
        path = os.path.join(PLUGIN, "Menu.qml")
        with open(path) as handle:
            source = handle.read()
        self.assertIn("property var live", source)
        self.assertIn("LAYOUT WIDTH OR HEIGHT", source)


class TheGridFollowsACarriedTile(unittest.TestCase):
    """`reveal` is guarded on where the selection is, not on which it is.

    The guard has to exist: `reveal` runs on every arriving line and the
    heartbeat brings two a second, so scrolling to where the selection already
    is costs an animation nobody asked for. Keyed on the id alone it is wrong
    in exactly one case, and it is the case somebody hits: while a tile is
    being carried the selection does not change and its row does, so the guard
    fires, the view stands still, and the tile walks off the bottom of the
    grid while the button is still being pressed.

    Read rather than run, like everything else here - there is no QML runtime
    in the suite, and the symptom is a tile that is simply not on the screen.
    """

    def setUp(self):
        with open(os.path.join(PLUGIN, "Menu.qml")) as handle:
            self.source = handle.read()

    def test_the_grid_still_guards_against_the_heartbeat(self):
        # A refactor that dropped the guard would scroll twice a second.
        self.assertIn("root.revealed", self.source)

    def test_the_guard_is_not_the_selection_id_on_its_own(self):
        self.assertNotIn("if (root.sel === root.revealed) return", self.source)
        self.assertNotIn("root.revealed = root.sel\n", self.source)

    def test_the_key_carries_the_cell(self):
        # The row and the height, so a tile that moved is revealed again.
        body = self.source[self.source.index("function reveal()"):]
        body = body[:body.index("\n  }")]
        self.assertIn(".y", body)
        self.assertIn(".h", body)
        self.assertIn("root.revealed", body)


class TheGridScrollsToTheHaloToo(unittest.TestCase):
    """`reveal` brings a tile's *halo* into view, not only its box.

    The glow is drawn `haloReach` outside the tile's own box and the grid
    clips, so a scroll that stops at the box stops with the ring on that side
    already cut: the tile arrives selected and reads as unmarked down one
    edge. It stayed hidden while a page fitted the card - the first column
    rests at `contentX` 0, where the reach is already in the content - and
    showed up the moment a scale put a page wider than the card on the screen
    and the grid had to come back to column 0.

    Read rather than run, like everything else here.
    """

    def setUp(self):
        with open(os.path.join(PLUGIN, "Menu.qml")) as handle:
            source = handle.read()
        self.body = source[source.index("function reveal()"):]
        self.body = self.body[:self.body.index("\n  }")]

    def test_all_four_bounds_carry_the_reach(self):
        # Two near edges out, two far edges out: top, left, bottom, right.
        self.assertEqual(self.body.count("- root.haloReach"), 2)
        self.assertEqual(self.body.count("+ root.haloReach"), 2)



class TheFoldFallsBetweenTwoCells(unittest.TestCase):
    """What a band may show is a whole number of cells, on both axes.

    A tile centres its ink, so the visible part of a cut one carries none at
    all: a page cropped mid-tile ends in a band of nothing and reads as bad
    padding rather than as "there is more below". The card's rows were cut to
    whole ones for that reason once; the columns and the fullscreen page were
    not, and a screen narrower than the page ended in a sliver of a tile.

    The trap this guards is the easy refactor: the clip is *not* the box it
    sits in. The box keeps the room the `Column` gave it - the legend hangs
    under it - and the `Flickable` inside stops short of that room. An
    `anchors.fill` put back there would fit the page to the screen again with
    nothing in any log to say so.

    Read rather than run, like everything else here.
    """

    def setUp(self):
        with open(os.path.join(PLUGIN, "Menu.qml")) as handle:
            self.source = handle.read()

    def test_the_arithmetic_is_written_once(self):
        # Every cut asks `wholeCells`; a second copy of the pitch is a second
        # answer to where the fold is.
        self.assertEqual(self.source.count("function wholeCells("), 1)
        self.assertEqual(
            self.source.count("/ (cell + root.cellGap)"), 1)

    def test_the_grid_clips_to_whole_cells_on_both_axes(self):
        body = self.source[self.source.index("id: grid"):]
        body = body[:body.index("Repeater {")]
        self.assertIn("width: root.shownCols(", body)
        self.assertIn("height: root.shownRows(", body)
        # The clip is not the box: an `anchors.fill` here is the bug.
        self.assertNotIn("anchors.fill", body)

    def test_the_bar_is_cut_to_whole_cards(self):
        # A nav card is a cell on the grid's own columns, so a half card at
        # the right edge is the two bands disagreeing about where the page
        # ends.
        body = self.source[self.source.index("id: bar"):]
        body = body[:body.index("Row {")]
        self.assertIn("width: root.shownCols(", body)

    def test_the_card_is_sized_to_whole_columns(self):
        # A card is as wide as the page it holds, and the screen's cap on that
        # is cut the same way - what it leaves over is a narrower card.
        self.assertIn("+ root.shownCols(card.roomAcross)", self.source)

    def test_a_page_may_not_be_shown_wider_than_it_is(self):
        # `cols` and `rows` are the page's own size; the cut may only take
        # away.
        self.assertIn("Math.min(root.cols, root.wholeCells(", self.source)
        self.assertIn("Math.min(root.rows, root.wholeCells(", self.source)


class EverySocketIsDrawn(unittest.TestCase):
    """A socket the daemon writes to and nothing reads is a surface that is
    simply not there.

    This is the gap the HUD fell into: `hud.py`, its model, its settings and
    its wiring all landed, the daemon streamed to `hud.sock` twice a second,
    and nothing drew a pixel. Every test passed, `omapad check` was happy, and
    the only symptom was a blank screen - which is also what a surface that is
    switched off looks like. `pad-surface.md` calls a panel step 7 of nine for
    this reason; a checklist is a thing you can get to step 6 of.

    The bar widget is the one deliberate absence: `PadStatus.qml` is the other
    entry point and is not mounted as a surface.
    """

    WRITES = re.compile(r'ViewClient\(\s*"([\w.]+)"')
    LISTENS = re.compile(r'name:\s*"([\w.]+)"')

    def setUp(self):
        daemon = os.path.join(os.path.dirname(PLUGIN), "omapad", "daemon.py")
        with open(daemon) as handle:
            self.written = set(self.WRITES.findall(handle.read()))
        self.heard = {}
        for name in sorted(os.listdir(PLUGIN)):
            if not name.endswith(".qml"):
                continue
            with open(os.path.join(PLUGIN, name)) as handle:
                for sock in self.LISTENS.findall(handle.read()):
                    if sock.endswith(".sock"):
                        self.heard[sock] = name

    def test_the_daemon_has_sockets_to_check(self):
        self.assertGreater(len(self.written), 5)

    def test_something_draws_every_socket_the_daemon_writes(self):
        for sock in sorted(self.written):
            self.assertIn(
                sock, self.heard,
                "the daemon streams to %s and no panel listens on it" % sock)

    def test_nothing_listens_on_a_socket_the_daemon_never_writes(self):
        # The other way round: a renamed socket leaves a panel waiting on a
        # name that will never be bound, which looks exactly the same.
        for sock, name in sorted(self.heard.items()):
            self.assertIn(
                sock, self.written,
                "%s listens on %s and the daemon never writes it"
                % (name, sock))

    def test_every_panel_that_draws_one_is_reached(self):
        # A panel nobody instantiates is a file, not a surface. `Surfaces.qml`
        # is the plugin's only *panel* entry point, so a surface becomes
        # something on screen by being mounted there - or, for the bar widget,
        # by being an entry point in its own right.
        root = os.path.dirname(PLUGIN)
        with open(os.path.join(PLUGIN, "Surfaces.qml")) as handle:
            mounted = handle.read()
        with open(os.path.join(root, "manifest.json")) as handle:
            entries = json.load(handle).get("entryPoints", {}).values()
        named = set(os.path.basename(entry) for entry in entries)
        for sock, name in sorted(self.heard.items()):
            component = name[:-len(".qml")]
            reached = name in named or re.search(
                r"\b%s\s*\{" % re.escape(component), mounted)
            self.assertTrue(
                reached,
                "%s draws %s and is neither mounted in Surfaces.qml nor an "
                "entry point" % (name, sock))


class MotionTests(unittest.TestCase):
    """Every animation on every surface goes through one multiplier."""

    def setUp(self):
        self.files = sorted(
            name for name in os.listdir(PLUGIN) if name.endswith(".qml")
        )

    def test_every_panel_that_draws_takes_the_motion_off_the_payload(self):
        # A panel that kept its own 1.0 would animate at full speed after
        # somebody had turned motion off, and nothing on screen would say
        # which surface had not been told.
        for name in self.files:
            with open(os.path.join(PLUGIN, name)) as handle:
                source = handle.read()
            if "Metrics {" not in source:
                continue
            self.assertIn(
                "motion: root.motion", source,
                "%s builds Metrics without handing it the motion" % name)
            self.assertIn(
                "s.motion", source,
                "%s never reads the motion off its payload" % name)

    def test_every_surface_on_a_screen_edge_reads_the_safe_area(self):
        # The four that put something against the edge of the screen. A
        # panel that drew inside a card, or over a pointer, has no edge to
        # be cropped at and takes nothing.
        for name in ("Menu.qml", "Hud.qml", "GameBar.qml", "Keyboard.qml"):
            with open(os.path.join(PLUGIN, name)) as handle:
                source = handle.read()
            self.assertIn("safeArea: root.safeArea", source, name)
            self.assertIn("s.safe", source,
                          "%s never reads the safe area off its payload" % name)
            self.assertIn("metrics.edge(", source,
                          "%s takes the safe area and never spends it" % name)

    def test_no_animation_carries_its_own_number(self):
        # The exceptions are the two countdowns - `[ripple] ms` and the
        # confirm badge's lap - which are how long a promise takes rather
        # than how long a thing takes to move, and are settings already.
        allowed = ("duration: metrics.time.", "duration: root.burstMs",
                   "duration: Math.max(1, badge.lapMs)",
                   "duration: badge.arming ?")
        for name in self.files:
            with open(os.path.join(PLUGIN, name)) as handle:
                lines = handle.read().splitlines()
            for n, line in enumerate(lines, 1):
                if "duration:" not in line:
                    continue
                self.assertTrue(
                    any(word in line for word in allowed),
                    "%s:%d sets a duration off the ladder: %s"
                    % (name, n, line.strip()))


class FontTests(unittest.TestCase):
    """**Two font groups, and only one of them moves.**

    The badges are lettered in the face `assets/generate.py` punched their
    labels out of - `buttonArt.family`, shipped beside the drawings - and a
    typed label in any other would stand next to a drawn one that did not
    match it. Everything else a surface writes is set in the family the
    payload names (`[ui] font`), which is empty for the desktop's own.

    A surface that forgot to take it would go on drawing in the session's
    font while the rest changed, and nothing on screen or in any log would
    say which one had not been told - the same silence the motion multiplier
    is guarded against above.
    """

    def setUp(self):
        self.files = sorted(
            name for name in os.listdir(PLUGIN) if name.endswith(".qml")
        )

    def test_every_panel_that_writes_a_word_takes_the_family(self):
        # Keyed on using the group rather than on building `Metrics`: a
        # surface with no words in it - the ripple is one - has no family to
        # be told about, and listing the exceptions by name is how a list
        # goes stale.
        for name in self.files:
            with open(os.path.join(PLUGIN, name)) as handle:
                source = handle.read()
            if "metrics.font." not in source:
                continue
            self.assertIn(
                "fontFamily: root.fontFamily", source,
                "%s builds Metrics without handing it the family" % name)
            self.assertIn(
                "s.font", source,
                "%s never reads the family off its payload" % name)

    def test_no_surface_reaches_past_the_group_for_the_session_font(self):
        # `Style.font.family` is the desktop's answer and the group already
        # falls back to it. A surface asking for it directly is one the
        # setting cannot reach.
        for name in self.files:
            if name == "Metrics.qml":
                continue
            with open(os.path.join(PLUGIN, name)) as handle:
                source = handle.read()
            self.assertNotIn(
                "Style.font.family", source,
                "%s takes the session's font instead of the surface's" % name)


class TravelTests(unittest.TestCase):
    """The line a value sits on takes everything it draws with from the call
    site, and says nothing when it is handed none of it.

    `Travel.qml` names no colour (qml.md 8.1) and builds neither a `Metrics`
    nor a `ControlArt` of its own - the scale on the payload belongs to the
    surface, and a component that built its own art would build one per slider
    on the page. So a travel missing `ladder` draws a one-pixel line with no
    mark anywhere on it, one missing `art` draws the line and nothing standing
    on it, and one missing a colour draws nothing at all: a slider that looks
    like an empty card, with nothing in any log about it.
    """

    REQUIRED = ("ladder:", "art:", "value:", "ink:", "trail:", "ghost:",
                "mark:")

    def setUp(self):
        self.files = sorted(
            name for name in os.listdir(PLUGIN) if name.endswith(".qml")
        )

    def test_the_plugin_still_draws_a_travel(self):
        # A rename would otherwise turn the test below into a pass over
        # nothing, the way it would for `Text`.
        found = 0
        for name in self.files:
            with open(os.path.join(PLUGIN, name)) as handle:
                found += len(text_blocks(handle.read(), OPENS_TRAVEL))
        self.assertGreater(found, 1)

    def test_every_travel_is_handed_what_it_draws_with(self):
        for name in self.files:
            with open(os.path.join(PLUGIN, name)) as handle:
                blocks = text_blocks(handle.read(), OPENS_TRAVEL)
            for number, body in blocks:
                for field in self.REQUIRED:
                    self.assertIn(
                        field, body,
                        "%s:%d draws a travel with no %s"
                        % (name, number, field))


class KnobTests(unittest.TestCase):
    """The ring a value turns in takes everything it draws with from the call
    site, and says nothing when it is handed none of it.

    `Knob.qml` is `Travel.qml` bent round a circle and inherits its whole
    argument, this one included: it names no colour (qml.md 8.1) and builds no
    `ControlArt` of its own - a copy per knob on the page is what a component
    that cannot be a singleton costs. So a knob missing `art` draws a scale
    with no rim round it, and one missing a colour draws nothing at all.

    No `ghost:`, and that is the one field it does not inherit: a ring draws
    nothing where the value started, because a second pointer out of the same
    middle reads as a clock.
    """

    REQUIRED = ("art:", "value:", "ink:", "trail:", "mark:")

    def setUp(self):
        self.files = sorted(
            name for name in os.listdir(PLUGIN) if name.endswith(".qml")
        )

    def test_the_plugin_still_draws_a_knob(self):
        # A rename would otherwise turn the test below into a pass over
        # nothing, the way it would for `Travel`.
        found = 0
        for name in self.files:
            with open(os.path.join(PLUGIN, name)) as handle:
                found += len(text_blocks(handle.read(), OPENS_KNOB))
        self.assertGreater(found, 0)

    def test_every_knob_is_handed_what_it_draws_with(self):
        for name in self.files:
            with open(os.path.join(PLUGIN, name)) as handle:
                blocks = text_blocks(handle.read(), OPENS_KNOB)
            for number, body in blocks:
                for field in self.REQUIRED:
                    self.assertIn(
                        field, body,
                        "%s:%d draws a knob with no %s"
                        % (name, number, field))


class PlainTextTests(unittest.TestCase):
    def setUp(self):
        self.files = sorted(
            name for name in os.listdir(PLUGIN) if name.endswith(".qml")
        )

    def test_the_plugin_has_text_to_check(self):
        # A refactor that renamed the element would otherwise turn every test
        # below into a pass over nothing.
        found = 0
        for name in self.files:
            with open(os.path.join(PLUGIN, name)) as handle:
                found += len(text_blocks(handle.read()))
        self.assertGreater(found, 20)

    def test_every_text_says_what_format_it_is(self):
        for name in self.files:
            with open(os.path.join(PLUGIN, name)) as handle:
                for line, body in text_blocks(handle.read()):
                    self.assertIn(
                        "textFormat: Text.PlainText", body,
                        "%s:%d draws text with no format of its own" % (name, line))

    def test_nothing_asks_for_rich_text(self):
        for name in self.files:
            with open(os.path.join(PLUGIN, name)) as handle:
                source = handle.read()
            for wanted in ("Text.RichText", "Text.StyledText", "Text.AutoText"):
                self.assertNotIn(wanted, source, "%s: %s" % (name, wanted))


if __name__ == "__main__":
    unittest.main()


class KnobArcTests(unittest.TestCase):
    """The one arc, written in two files that cannot read each other.

    An aimed knob puts the value where the thumb points, and "where it points"
    is only true against the arc actually drawn. The panel cannot read the
    config and the daemon cannot read the QML, so the numbers are in both -
    and this is what stops them drifting apart in silence, which on screen
    would look like a dial that is simply a bit wrong.
    """

    def test_the_daemon_aims_at_the_arc_the_panel_draws(self):
        import sys
        sys.path.insert(0, os.path.dirname(PLUGIN))
        from omapad import daemon as daemon_module

        source = io.open(os.path.join(PLUGIN, "Knob.qml")).read()
        for name, attribute in (("arcFrom", "KNOB_ARC_FROM"),
                                ("arcSweep", "KNOB_ARC_SWEEP")):
            found = re.search(r"property real %s:\s*(-?[\d.]+)" % name, source)
            self.assertIsNotNone(found, "Knob.qml has no %s" % name)
            self.assertEqual(float(found.group(1)),
                             getattr(daemon_module, attribute))


class TileFillTests(unittest.TestCase):
    """`menu.tile_fill`, whose two halves fail quietly in opposite ways.

    A fill read through `|| 1` turns the one page this setting exists to
    reach - no grounds at all - back into the opaque one. And a fill applied
    to the tile rather than to its ground would fade every label with it,
    which is a page you cannot read rather than one you can see through.
    """

    def test_a_fill_of_zero_survives_the_payload(self):
        source = io.open(os.path.join(PLUGIN, "Menu.qml")).read()
        found = re.search(r"if \(s\.fill !== undefined\)\s*\n"
                          r"\s*root\.tileFill = Math\.max\(0, Math\.min\(1,"
                          r" Number\(s\.fill\)\)\)", source)
        self.assertIsNotNone(
            found, "menu.tile_fill is not read, or falls back over a real 0")

    def test_it_is_the_ground_that_thins_and_not_the_tile(self):
        source = io.open(os.path.join(PLUGIN, "Menu.qml")).read()
        self.assertIn("Util.alpha(root.cellGround, ground.fill)", source)
        # Never on the delegate itself: `opacity` there takes the label, the
        # icon and every figure on the tile with it.
        self.assertIsNone(
            re.search(r"^\s*opacity:.*\btileFill\b", source, re.M),
            "tile_fill is fading the whole tile, not its ground")

    def test_the_bar_thins_with_the_grid(self):
        # A row of solid cards over a page of glass would be the bar saying it
        # is a different kind of thing from the tiles it names. The bar is a
        # row of cells over a grid of them.
        source = io.open(os.path.join(PLUGIN, "Menu.qml")).read()
        self.assertIn("Util.alpha(root.cellGround, root.tileFill)", source)

    def test_but_the_card_you_are_on_keeps_its_accent_solid(self):
        # Its label sits *on* the fill and `onAccent` is measured against a
        # solid accent, so a thinned one is a contrast ratio worked out
        # against a colour no longer on the screen.
        source = io.open(os.path.join(PLUGIN, "Menu.qml")).read()
        found = re.search(r"fillColor: nav\.here\s*\n\s*\? Color\.accent",
                          source)
        self.assertIsNotNone(
            found, "the nav card you are on no longer fills with the accent")
        self.assertIsNone(
            re.search(r"Util\.alpha\(Color\.accent, root\.tileFill", source),
            "tile_fill is thinning the accent a label is measured against")

    def test_both_lit_channels_of_the_focus_come_down_with_the_page(self):
        # The halo and the sheen lift one card out of a page of cards. With
        # less page to lift it out of they are saying a second time what the
        # solid ground has already said - which on screen is a selection that
        # gets louder every step the fill comes down.
        source = io.open(os.path.join(PLUGIN, "Menu.qml")).read()
        self.assertEqual(source.count("opacity: tile.focusLight"), 2)
        found = re.search(r"readonly property real focusLight:\s*\n"
                          r"\s*tile\.selected \? root\.tileFill : 0", source)
        self.assertIsNotNone(found, "the focus lights no longer follow it")

    def test_but_the_ring_is_not_light_and_does_not(self):
        # It is the mark rather than a glow, and it is the one thing on a
        # selected tile that has to mean *here* at every fill.
        source = io.open(os.path.join(PLUGIN, "Menu.qml")).read()
        found = re.search(
            r"strokeColor: tile\.selected \? tile\.mark : root\.cellEdge",
            source)
        self.assertIsNotNone(found, "the focus ring has started fading")

    def test_the_tile_under_the_thumb_is_always_solid(self):
        source = io.open(os.path.join(PLUGIN, "Menu.qml")).read()
        found = re.search(
            r"readonly property real fill:\s*\n"
            r"\s*tile\.selected \? 1\.0 : root\.tileFill", source)
        self.assertIsNotNone(
            found, "a lowered fill takes the selected tile down with it")


class ShortPushTests(unittest.TestCase):
    """What a payload that carries almost nothing is not allowed to say.

    Three fields on this surface mean *gone* by being absent: the
    chronograph, the row held towards running, the row counting down. The
    short push carries none of them because it carries almost nothing, so
    read as authoritative it ends all three - which on screen is a clock
    losing its sub-dials for as long as a ring is being turned. The guard is
    one `var whole` and it is the kind of thing a later edit drops without
    noticing, so it is held here.
    """

    ENDED = ("root.chronoState =", "root.holding =", "root.counting =")

    def test_only_the_whole_surface_may_end_something(self):
        source = io.open(os.path.join(PLUGIN, "Menu.qml")).read()
        lines = source.split("\n")
        self.assertIn("var whole = s.items !== undefined", source)
        for needle in self.ENDED:
            found = [n for n, line in enumerate(lines) if needle in line]
            self.assertEqual(len(found), 1, "%s once" % needle)
            guard = lines[found[0] - 1].strip()
            self.assertEqual(guard, "if (whole)",
                             "%s is not guarded by the whole-surface test"
                             % needle)

    def test_a_streamed_value_is_matched_to_its_own_tile(self):
        # Never `taken`: the stream falls silent when nothing is turned, and
        # the last line stands - so "whatever is held" wore a stale number.
        source = io.open(os.path.join(PLUGIN, "Menu.qml")).read()
        self.assertIn("root.live.hid === tile.modelData.id", source)
        lines = source.split("\n")
        for field in ("root.live.ht", "root.live.hv"):
            used = [n for n, line in enumerate(lines) if field in line]
            self.assertTrue(used, "%s is not read at all" % field)
            for n in used:
                # The guard may sit a line above, the expressions here being
                # wrapped: the test is that it is in the same one.
                near = "\n".join(lines[max(0, n - 2):n + 1])
                self.assertIn("tile.streaming", near,
                              "%s on line %d is not scoped to its tile"
                              % (field, n + 1))

    def test_the_short_push_really_does_leave_the_items_out(self):
        # The guard reads `items` as the mark of a whole surface, so the
        # daemon has to keep leaving it off - the two halves of one contract.
        import sys
        sys.path.insert(0, os.path.dirname(PLUGIN))
        from omapad import menu as menu_module

        short = menu_module.MenuModel.live_state(
            menu_module.MenuModel([], columns=6), True, {"hv": 0.5})
        self.assertNotIn("items", short)



class LatchingCardTests(unittest.TestCase):
    """A card of rows carries its state in one drawing or the other.

    The line down a card says which row is in force by lighting a *length* of
    itself, which is a figure with one start and one end - so on a card where
    three rows may be on there is nothing for it to light. The keys say it
    there instead. Both at once would be a card with a line on it that means
    nothing beside keys that mean everything, and it is the kind of thing an
    edit adds back by making one of them unconditional.
    """

    def setUp(self):
        self.source = io.open(os.path.join(PLUGIN, "Menu.qml")).read()

    def test_the_line_is_not_drawn_where_the_keys_are(self):
        self.assertIn("readonly property bool railed: tile.stated "
                      "&& !tile.many", self.source)
        # And nothing draws the line off `stated` any more, which is the
        # question about whether a row was *asked* rather than about which
        # drawing answers it.
        for line in self.source.split("\n"):
            if "tile.stated" in line:
                self.assertIn("railed", line, "%s draws off `stated`" % line)

    def test_and_the_keys_are_not_drawn_where_the_line_is(self):
        self.assertIn("visible: tile.many && line.asked", self.source)
