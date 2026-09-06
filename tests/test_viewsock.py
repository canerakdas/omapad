"""The line the daemon writes to a surface, and what it lets through.

`ViewClient` itself is exercised wherever a surface is; what is here is
`drawable`, the one thing on this side of the socket that treats a string as
coming from outside the machine.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad.viewsock import DRAWABLE, drawable


class DrawableTests(unittest.TestCase):
    def test_an_ordinary_name_is_left_alone(self):
        self.assertEqual(drawable("Beitong BT-G1 Gamepad"), "Beitong BT-G1 Gamepad")

    def test_a_name_shaped_like_markup_cannot_stay_markup(self):
        # The shell is up for the whole session, and a Text left to guess its
        # own format fetches what an <img src=...> points at.
        self.assertEqual(drawable('Pad <img src="http://elsewhere/x">'),
                         'Pad img src="http://elsewhere/x"')

    def test_a_name_that_would_not_fit_a_row_is_cut(self):
        cut = drawable("A" * 400)
        self.assertEqual(len(cut), DRAWABLE)
        self.assertTrue(cut.endswith("…"))

    def test_a_name_cannot_carry_lines_of_its_own(self):
        self.assertEqual(drawable("Pad\nSecond line\ttab"), "PadSecond linetab")

    def test_a_name_that_was_nothing_but_markup_comes_back_empty(self):
        self.assertEqual(drawable("<>"), "")


if __name__ == "__main__":
    unittest.main()
