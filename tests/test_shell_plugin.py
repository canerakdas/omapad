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


class TravelTests(unittest.TestCase):
    """The line a value sits on takes everything it draws with from the call
    site, and says nothing when it is handed none of it.

    `Travel.qml` names no colour (qml.md 8.1) and builds no `Metrics` of its
    own - the scale on the payload belongs to the surface, not to a component
    inside one. So a travel missing `ladder` draws a one-pixel line with no
    mark anywhere on it, and one missing a colour draws nothing at all: a
    slider that looks like an empty card, with nothing in any log about it.
    """

    REQUIRED = ("ladder:", "value:", "ink:", "trail:", "ghost:", "mark:")

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

