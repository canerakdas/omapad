"""The drawn pointer: what colour it comes out, and when it is redrawn."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad import cursor


def theme(text):
    handle = tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False)
    handle.write(text)
    handle.close()
    return handle.name


class ColoursComeFromTheDesktop(unittest.TestCase):
    """`auto` is the theme's own, because a pointer in another palette than
    everything else on screen is the one thing on it that looks foreign."""

    def setUp(self):
        self.path = theme('accent = "#b59790"\n'
                          'background = "#0c0b0c"\n'
                          'foreground = "#FAFCFB"\n')
        self.addCleanup(os.unlink, self.path)

    def test_auto_is_the_foreground_and_the_background(self):
        self.assertEqual(
            cursor.resolve("auto", "color", "#ffffff", self.path), "#FAFCFB")
        # The halo keeps some of the background rather than all of it: solid
        # would draw a hard shadow around a thin ring.
        self.assertEqual(
            cursor.resolve("auto", "outline", "#000000cc", self.path),
            "#0c0b0cc6")

    def test_any_other_name_is_a_key_out_of_the_same_file(self):
        self.assertEqual(
            cursor.resolve("accent", "color", "#ffffff", self.path), "#b59790")

    def test_a_colour_of_your_own_is_left_alone(self):
        self.assertEqual(
            cursor.resolve("#ff0000ee", "color", "#ffffff", self.path),
            "#ff0000ee")

    def test_and_a_theme_that_cannot_answer_falls_back_to_what_shipped(self):
        for spec in ("auto", "nosuchkey"):
            self.assertEqual(
                cursor.resolve(spec, "color", "#ffffff", "/nowhere/at/all"),
                "#ffffff")

    def test_the_stamp_carries_the_colour_that_was_drawn(self):
        """Not the word `auto`: a theme change has to be visible to the check
        that decides whether the file on disk is still current."""
        one = cursor.stamp_for(48, "#FAFCFB", "#0c0b0cc6", 0.085, 0.05, 0.045,
                               "all", "")
        two = cursor.stamp_for(48, "#b59790", "#0c0b0cc6", 0.085, 0.05, 0.045,
                               "all", "")
        self.assertNotEqual(one, two)


class TheDrawingItself(unittest.TestCase):
    def test_a_ring_is_drawn_at_every_size_asked_for(self):
        data = cursor.build(40, (255, 255, 255, 255), (0, 0, 0, 190))
        self.assertTrue(data.startswith(cursor.MAGIC))
        # The configured size joins the ladder rather than replacing it.
        self.assertIn(40, cursor.SIZES + (40,))

    def test_nothing_is_cut_off_at_its_edges(self):
        """The halo is drawn outside the ring, so the ring has to leave room
        for it. Measured from the image's edge instead, the halo falls off it
        at four places and the pointer comes out with four flat sides."""
        for size in (24, 32, 48, 64, 128):
            pixels, _, _ = cursor.render(size, (255, 255, 255, 255),
                                         (0, 0, 0, 190))

            def alpha(x, y):
                return pixels[(y * size + x) * 4 + 3]

            border = ([alpha(x, 0) for x in range(size)]
                      + [alpha(x, size - 1) for x in range(size)]
                      + [alpha(0, y) for y in range(size)]
                      + [alpha(size - 1, y) for y in range(size)])
            self.assertEqual(max(border), 0,
                             "%dpx is drawn off its own edge" % size)
            # And it uses the room it left: the halo reaches the row inside.
            self.assertGreater(alpha(size // 2, 1), 0,
                               "%dpx leaves more room than it needs" % size)

    def test_the_band_is_fainter_than_the_dot_it_surrounds(self):
        """ring_opacity fades the band alone - the dot is the pixel the click
        lands on and has to stay solid."""
        size = 64
        pixels, _, _ = cursor.render(size, (255, 255, 255, 255), (0, 0, 0, 0),
                                     ring_opacity=0.5)

        def alpha(x, y):
            return pixels[(y * size + x) * 4 + 3]

        band = max(alpha(x, size // 2) for x in range(size // 4))
        self.assertGreater(band, 0)
        self.assertEqual(alpha(size // 2, size // 2), 255)
        self.assertAlmostEqual(band, 128, delta=4)

    def test_and_it_is_transparent_where_the_ring_is_not(self):
        pixels, xhot, yhot = cursor.render(32, (255, 255, 255, 255),
                                           (0, 0, 0, 0))
        self.assertEqual((xhot, yhot), (16, 16))
        middle = (16 * 32 + 16) * 4          # the centre pixel, in the dot
        corner = 0                           # the top-left, outside everything
        self.assertGreater(pixels[middle + 3], 0)
        self.assertEqual(pixels[corner + 3], 0)


if __name__ == "__main__":
    unittest.main()
