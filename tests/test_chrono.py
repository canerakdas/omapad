"""The stopwatch behind a chronograph tile: three states and one pusher.

Every entry point takes `now`, so none of this needs a clock to run against -
which is the same reason the daemon hands it `time.monotonic()` rather than
letting it read one: a stopwatch that asked the wall clock what time it was
would measure a machine coming back from suspend as hours.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad.chrono import Chrono, IDLE, RUNNING, STOPPED


class TheCycle(unittest.TestCase):
    """Start, stop, reset, round again - a monopusher's whole vocabulary."""

    def setUp(self):
        self.chrono = Chrono()

    def test_it_begins_holding_nothing(self):
        self.assertEqual(self.chrono.state, IDLE)
        self.assertEqual(self.chrono.elapsed(1000.0), 0.0)

    def test_the_first_press_starts_it(self):
        self.assertEqual(self.chrono.press(100.0), RUNNING)
        self.assertAlmostEqual(self.chrono.elapsed(105.5), 5.5)

    def test_the_second_press_stops_it_where_it_was(self):
        self.chrono.press(100.0)
        self.assertEqual(self.chrono.press(112.25), STOPPED)
        # And it stays there however long nobody presses anything: a stopped
        # measurement is the number the tile is being read for.
        self.assertAlmostEqual(self.chrono.elapsed(112.25), 12.25)
        self.assertAlmostEqual(self.chrono.elapsed(900.0), 12.25)

    def test_the_third_press_throws_it_away(self):
        self.chrono.press(100.0)
        self.chrono.press(112.0)
        self.assertEqual(self.chrono.press(113.0), IDLE)
        self.assertEqual(self.chrono.elapsed(900.0), 0.0)

    def test_and_the_fourth_starts_a_new_one(self):
        for at in (100.0, 112.0, 113.0):
            self.chrono.press(at)
        self.assertEqual(self.chrono.press(200.0), RUNNING)
        self.assertAlmostEqual(self.chrono.elapsed(203.0), 3.0)

    def test_a_stopped_measurement_is_not_resumed(self):
        # The monopusher's own limitation, and it is here as a test rather
        # than as a comment because it is the thing somebody will try to
        # "fix": the next press after a stop resets, and the legend says so
        # before it is pressed.
        self.chrono.press(100.0)
        self.chrono.press(110.0)
        self.assertEqual(self.chrono.verb(), "Reset")
        self.assertEqual(self.chrono.press(120.0), IDLE)

    def test_a_clock_that_goes_backwards_does_not_run_the_hands_back(self):
        # `time.monotonic()` cannot, and a test's `now` is whatever it was
        # handed. A negative elapsed would draw a sweep hand running
        # backwards, which is a fault nobody would think to look for in the
        # arithmetic.
        self.chrono.press(100.0)
        self.assertEqual(self.chrono.elapsed(99.0), 0.0)


class WhatTheLegendSays(unittest.TestCase):
    """The one word under the card, and it names the *next* press."""

    def test_each_state_names_what_a_press_would_do(self):
        chrono = Chrono()
        self.assertEqual(chrono.verb(), "Start")
        chrono.press(10.0)
        self.assertEqual(chrono.verb(), "Stop")
        chrono.press(20.0)
        self.assertEqual(chrono.verb(), "Reset")
        chrono.press(30.0)
        self.assertEqual(chrono.verb(), "Start")

    def test_the_words_are_one_each(self):
        # The legend is a row of four buttons across the foot of a card, so a
        # verb that came to three words would be the one that pushed the other
        # three off it.
        chrono = Chrono()
        for _ in range(3):
            self.assertEqual(len(chrono.verb().split()), 1)
            chrono.press(1.0)


class ThePayload(unittest.TestCase):
    """Two fields: where it had got to, and whether it is still going."""

    def test_it_carries_the_measurement_and_whether_it_is_running(self):
        chrono = Chrono()
        self.assertEqual(chrono.view_state(100.0), {"run": False, "el": 0.0})
        chrono.press(100.0)
        self.assertEqual(chrono.view_state(103.5), {"run": True, "el": 3.5})
        chrono.press(103.5)
        self.assertEqual(chrono.view_state(900.0), {"run": False, "el": 3.5})

    def test_it_is_rounded_to_what_anybody_can_read(self):
        # Tenths are what the tile prints, so a float carrying more precision
        # than that is bytes twice a second for a digit nobody has.
        chrono = Chrono()
        chrono.press(0.0)
        self.assertEqual(chrono.view_state(1.239876)["el"], 1.24)


if __name__ == "__main__":
    unittest.main()
