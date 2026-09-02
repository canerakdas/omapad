"""Choosing the window next door, and drawing the pointer that points at it.

Both are pure: the geometry is posed a canned window list rather than a
compositor, and the cursor theme is decoded back out of the bytes it wrote.
"""

import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad import cursor, snap


def window(x, y, width, height, workspace=1, monitor=0, **extra):
    spec = {
        "address": "0x%x" % (x * 100000 + y * 100 + width),
        "at": [x, y],
        "size": [width, height],
        "workspace": {"id": workspace, "name": str(workspace)},
        "monitor": monitor,
        "mapped": True,
        "hidden": False,
    }
    spec.update(extra)
    return spec


MONITORS = [
    {
        "id": 0, "name": "eDP-1", "x": 0, "y": 0,
        "width": 1920, "height": 1200, "scale": 1.25,
        "activeWorkspace": {"id": 1}, "specialWorkspace": {"id": 0},
    },
]

# One tall window on the left, two stacked on the right - the layout every
# tiling desktop falls into, and the one a flick has to walk cleanly.
LEFT = window(0, 0, 760, 900)
TOP_RIGHT = window(768, 0, 760, 440)
BOTTOM_RIGHT = window(768, 450, 760, 450)
TILED = [LEFT, TOP_RIGHT, BOTTOM_RIGHT]


class GeometryTests(unittest.TestCase):
    def test_rect_and_centre_come_out_of_at_and_size(self):
        self.assertEqual(snap.rect(LEFT), (0.0, 0.0, 760.0, 900.0))
        self.assertEqual(snap.centre(LEFT), (380.0, 450.0))

    def test_a_window_without_geometry_is_not_a_target(self):
        self.assertIsNone(snap.rect({"at": [0, 0]}))
        self.assertIsNone(snap.rect({"at": [0, 0], "size": [0, 100]}))
        self.assertIsNone(snap.rect({"at": "x", "size": [1, 1]}))

    def test_monitor_at_divides_by_the_scale(self):
        # 1920 physical pixels at 1.25 is 1536 logical ones, and cursorpos and
        # window geometry are both logical - so a point at 1600 is off screen.
        self.assertEqual(snap.monitor_at(MONITORS, 768, 467), 0)
        self.assertIsNone(snap.monitor_at(MONITORS, 1600, 100))
        self.assertIsNone(snap.monitor_at(MONITORS, -1, 100))


class CandidateTests(unittest.TestCase):
    def test_only_windows_on_a_workspace_that_is_on_screen(self):
        elsewhere = window(0, 0, 100, 100, workspace=7)
        found = snap.candidates(TILED + [elsewhere], MONITORS)
        self.assertEqual(len(found), 3)
        self.assertNotIn(elsewhere, found)

    def test_a_special_workspace_pulled_down_is_on_screen(self):
        monitors = [dict(MONITORS[0], specialWorkspace={"id": -99})]
        scratch = window(200, 200, 400, 300, workspace=-99)
        self.assertIn(scratch, snap.candidates(TILED + [scratch], monitors))

    def test_unmapped_and_hidden_windows_are_not_targets(self):
        unmapped = window(10, 10, 100, 100, mapped=False)
        hidden = window(20, 20, 100, 100, hidden=True)
        found = snap.candidates(TILED + [unmapped, hidden], MONITORS)
        self.assertEqual(found, TILED)

    def test_the_other_monitor_is_left_alone_when_asked(self):
        second = window(1600, 0, 400, 400, monitor=1)
        self.assertEqual(snap.candidates(TILED + [second], MONITORS, 0), TILED)
        self.assertIn(second, snap.candidates(TILED + [second], MONITORS))


class ChooseTests(unittest.TestCase):
    def test_right_takes_the_window_the_pointer_lines_up_with(self):
        # y=450 is inside the bottom-right window's span and outside the top
        # one's, so the press is answered by the one straight ahead.
        self.assertIs(snap.choose(TILED, 380, 450, "right"), BOTTOM_RIGHT)
        self.assertIs(snap.choose(TILED, 380, 100, "right"), TOP_RIGHT)

    def test_a_column_walks_one_window_at_a_time(self):
        self.assertIs(snap.choose(TILED, 1140, 200, "down"), BOTTOM_RIGHT)
        self.assertIs(snap.choose(TILED, 1140, 700, "up"), TOP_RIGHT)

    def test_nothing_that_way_is_nothing(self):
        self.assertIsNone(snap.choose(TILED, 380, 450, "left"))
        self.assertIsNone(snap.choose(TILED, 1140, 200, "right"))

    def test_the_window_under_the_pointer_is_never_the_answer(self):
        self.assertIsNot(snap.choose(TILED, 380, 450, "right"), LEFT)

    def test_a_float_over_a_tile_is_the_window_the_pointer_is_in(self):
        # hyprctl lists bottom-first, so the last match is the one on top.
        float_window = window(300, 300, 200, 200)
        windows = [LEFT, float_window]
        self.assertIs(snap.under(windows, 350, 350), float_window)

    def test_the_bias_decides_between_near_and_in_line(self):
        # A window straight ahead but far, against a near one off to the side.
        ahead = window(1200, 400, 300, 200)
        aside = window(500, 900, 300, 200)
        pool = [ahead, aside]
        # Off to the side is cheap: the near one wins even though it is not
        # the direction pressed squarely.
        self.assertIs(snap.choose(pool, 400, 500, "right", 0.2), aside)
        # Off to the side is dear: only the one in line answers.
        self.assertIs(snap.choose(pool, 400, 500, "right", 6.0), ahead)

    def test_an_unknown_direction_asks_for_nothing(self):
        self.assertIsNone(snap.choose(TILED, 380, 450, "sideways"))


class CursorThemeTests(unittest.TestCase):
    def test_the_file_is_an_xcursor_with_one_image_per_size(self):
        data = cursor.build(64, (255, 255, 255, 255), (0, 0, 0, 204))
        magic, header, version, count = struct.unpack_from("<4sIII", data, 0)
        self.assertEqual(magic, b"Xcur")
        self.assertEqual(header, 16)
        self.assertEqual(version, cursor.FILE_VERSION)
        self.assertEqual(count, len(cursor.SIZES))

        sizes = []
        for index in range(count):
            kind, nominal, position = struct.unpack_from(
                "<III", data, 16 + 12 * index
            )
            self.assertEqual(kind, cursor.CHUNK_IMAGE)
            sizes.append(nominal)
            chunk = struct.unpack_from("<9I", data, position)
            # header, type, subtype, version, width, height, xhot, yhot, delay
            self.assertEqual(chunk[0], 36)
            self.assertEqual(chunk[4], nominal)
            self.assertEqual(chunk[5], nominal)
            # The hotspot is the middle of the ring: what it circles is what
            # a click lands on.
            self.assertEqual((chunk[6], chunk[7]), (nominal // 2, nominal // 2))
            self.assertGreaterEqual(
                len(data), position + 36 + nominal * nominal * 4
            )
        self.assertEqual(sizes, list(cursor.SIZES))

    def test_the_ring_is_a_ring(self):
        size = 48
        pixels, xhot, yhot = cursor.render(
            size, (255, 255, 255, 255), (0, 0, 0, 255)
        )
        self.assertEqual((xhot, yhot), (24, 24))

        def alpha(x, y):
            return pixels[(y * size + x) * 4 + 3]

        # Opaque on the rim and at the dot in the middle, clear between them,
        # and clear again in the corner - which is what makes it a ring around
        # what it points at rather than a blob over it.
        self.assertGreater(alpha(1, 24), 0)
        self.assertGreater(alpha(24, 24), 200)
        self.assertEqual(alpha(24, 34), 0)
        self.assertEqual(alpha(0, 0), 0)

    def test_the_size_asked_for_joins_the_ladder(self):
        # A compositor asked for a size the file does not carry picks the
        # nearest and scales it, so the one actually asked for is the one
        # worth having exact.
        data = cursor.build(40, (255, 255, 255, 255), (0, 0, 0, 204))
        count = struct.unpack_from("<4sIII", data, 0)[3]
        sizes = [
            struct.unpack_from("<III", data, 16 + 12 * i)[1]
            for i in range(count)
        ]
        self.assertIn(40, sizes)
        self.assertEqual(sizes, sorted(sizes))
        for standard in cursor.SIZES:
            self.assertIn(standard, sizes)

    def test_the_dot_and_the_halo_can_be_left_off(self):
        size = 48
        plain, _, _ = cursor.render(
            size, (255, 255, 255, 255), (0, 0, 0, 255), dot=0.0, halo=0.0
        )

        def alpha(pixels, x, y):
            return pixels[(y * size + x) * 4 + 3]

        self.assertEqual(alpha(plain, 24, 24), 0)  # no dot in the middle
        # The halo is a band drawn under the ring on both of its edges, so
        # turning it on widens the ink across the middle row.
        haloed, _, _ = cursor.render(
            size, (255, 255, 255, 255), (0, 0, 0, 255), dot=0.0, halo=0.2
        )

        def inked(pixels):
            return len([
                x for x in range(size) if alpha(pixels, x, 24) > 0
            ])

        self.assertGreater(inked(haloed), inked(plain))

    def test_a_thicker_ring_is_thicker(self):
        size = 48
        counts = []
        for thickness in (0.06, 0.25):
            pixels, _, _ = cursor.render(
                size, (255, 255, 255, 255), (0, 0, 0, 0),
                thickness=thickness, dot=0.0, halo=0.0,
            )
            row = [pixels[(24 * size + x) * 4 + 3] for x in range(size)]
            counts.append(len([a for a in row if a > 0]))
        self.assertGreater(counts[1], counts[0])

    def test_pointer_only_leaves_the_other_shapes_to_the_desktop(self):
        root = tempfile.mkdtemp(prefix="omapad-icons-")
        path = cursor.install("test-ring", 24, "#ffffff", "#000000", root=root)
        cursors = os.path.join(path, "cursors")
        self.assertTrue(os.path.exists(os.path.join(cursors, "text")))

        cursor.install(
            "test-ring", 24, "#ffffff", "#000000", root=root,
            shapes="pointer", inherits="Adwaita",
        )
        # The names it no longer carries are gone, or a pointer-only theme
        # would keep whatever the previous "all" left behind.
        self.assertFalse(os.path.exists(os.path.join(cursors, "text")))
        self.assertTrue(os.path.exists(os.path.join(cursors, "default")))
        with open(os.path.join(path, "index.theme")) as handle:
            self.assertIn("Inherits=Adwaita", handle.read())

    def test_a_theme_that_carries_everything_inherits_nothing(self):
        root = tempfile.mkdtemp(prefix="omapad-icons-")
        path = cursor.install(
            "test-ring", 24, "#ffffff", "#000000", root=root,
            shapes="all", inherits="Adwaita",
        )
        with open(os.path.join(path, "index.theme")) as handle:
            self.assertNotIn("Inherits", handle.read())

    def test_a_changed_proportion_redraws(self):
        root = tempfile.mkdtemp(prefix="omapad-icons-")
        path = cursor.install("test-ring", 24, "#ffffff", "#000000", root=root)
        primary = os.path.join(path, "cursors", "default")
        stamped = os.stat(primary).st_mtime_ns
        cursor.install("test-ring", 24, "#ffffff", "#000000", root=root)
        self.assertEqual(os.stat(primary).st_mtime_ns, stamped)
        cursor.install(
            "test-ring", 24, "#ffffff", "#000000", root=root, thickness=0.3
        )
        self.assertNotEqual(os.stat(primary).st_mtime_ns, stamped)

    def test_colours_that_do_not_parse_fall_back(self):
        self.assertEqual(cursor._parse_color("#ff8800", None), (255, 136, 0, 255))
        self.assertEqual(cursor._parse_color("#ff880040", None), (255, 136, 0, 64))
        self.assertEqual(cursor._parse_color("puce", "fallback"), "fallback")
        self.assertEqual(cursor._parse_color(None, "fallback"), "fallback")

    def test_install_writes_a_theme_and_then_leaves_it_alone(self):
        root = tempfile.mkdtemp(prefix="omapad-icons-")
        path = cursor.install("test-ring", 24, "#ffffff", "#000000", root=root)
        self.assertIsNotNone(path)
        cursors = os.path.join(path, "cursors")
        for name in ("default", "text", "pointer", "ns-resize"):
            self.assertTrue(os.path.exists(os.path.join(cursors, name)), name)
        self.assertTrue(os.path.exists(os.path.join(path, "index.theme")))

        # Drawing it is a quarter of a second, so the stamp is what stops it
        # happening again for a theme that is already on disk.
        primary = os.path.join(cursors, cursor.NAMES[0])
        stamped = os.stat(primary).st_mtime_ns
        cursor.install("test-ring", 24, "#ffffff", "#000000", root=root)
        self.assertEqual(os.stat(primary).st_mtime_ns, stamped)
        # A different size is a different pointer, and is redrawn.
        cursor.install("test-ring", 32, "#ffffff", "#000000", root=root)
        self.assertNotEqual(os.stat(primary).st_mtime_ns, stamped)

    def test_a_home_that_cannot_be_written_costs_nothing(self):
        blocked = os.path.join(tempfile.mkdtemp(prefix="omapad-icons-"), "f")
        with open(blocked, "w") as handle:
            handle.write("not a directory")
        self.assertIsNone(cursor.install("test-ring", 24, "#fff", "#000", root=blocked))


if __name__ == "__main__":
    unittest.main()
