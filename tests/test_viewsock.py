"""The line the daemon writes to a surface, and what it lets through.

What the daemon does with a line is exercised wherever a surface is; what is
here is the socket itself - that a shell which stops reading costs the loop
nothing - and `drawable`, the one thing on this side of the socket that treats
a string as coming from outside the machine.
"""

import json
import os
import shutil
import socket
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad.viewsock import DRAWABLE, ViewClient, drawable


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


class StalledShellTests(unittest.TestCase):
    """A shell that has stopped reading, which it does whenever it is busy."""

    # Big enough that a few of them fill the socket, which is the stall.
    BULK = "x" * 65536

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="omapad-view-")
        os.chmod(self.dir, 0o700)
        self.addCleanup(shutil.rmtree, self.dir, True)
        path = os.path.join(self.dir, "menu.sock")
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(path)
        self.server.listen(1)
        self.addCleanup(self.server.close)
        self.client = ViewClient("menu.sock", path)
        self.addCleanup(self.client.close)
        self.peer = None

    def accept(self):
        if self.peer is None:
            self.peer, _ = self.server.accept()
            self.peer.setblocking(False)
            self.addCleanup(self.peer.close)

    def stall(self):
        """Send until the socket will take no more, the way a stall ends up."""
        for n in range(1000):
            if not self.client.send({"n": n, "bulk": self.BULK}):
                self.accept()
                return n
        self.fail("the socket never filled")

    def read_all(self):
        """What the shell reads once it is back, the loop flushing as it goes."""
        data = b""
        for _ in range(10000):
            self.client.flush()
            try:
                chunk = self.peer.recv(1 << 20)
            except BlockingIOError:
                chunk = b""
            data += chunk
            if not chunk and not self.client.waiting():
                break
        return [json.loads(line) for line in data.decode().splitlines()]

    def test_a_shell_that_reads_nothing_costs_the_loop_nothing(self):
        self.stall()
        start = time.monotonic()
        for n in range(50):
            self.client.send({"n": 5000 + n, "bulk": self.BULK})
        # Fifty sends into a full socket. The blocking version waited half a
        # second on the first and threw the line away.
        self.assertLess(time.monotonic() - start, 0.2)
        self.assertTrue(self.client.waiting())

    def test_the_shell_gets_the_newest_line_and_no_torn_ones(self):
        self.stall()
        for n in range(20):
            self.client.send({"n": 5000 + n, "bulk": self.BULK})
        lines = self.read_all()
        self.assertEqual(lines[-1]["n"], 5019)
        # Everything in between was overtaken, and nothing arrived in halves
        # - `json.loads` above would have said so.
        self.assertNotIn(5010, [line["n"] for line in lines])

    def test_a_short_line_waits_behind_the_whole_one(self):
        self.stall()
        self.client.send({"n": 7000, "items": [], "bulk": self.BULK})
        self.client.send({"n": 7001, "live": 1}, whole=False)
        self.client.send({"n": 7002, "live": 2}, whole=False)
        lines = self.read_all()
        # The gauge line says less than the surface, so it cannot stand in
        # for it: the whole line still arrives, and then the newest gauge.
        self.assertEqual([line["n"] for line in lines[-2:]], [7000, 7002])

    def test_a_shell_that_restarted_is_reconnected(self):
        self.assertTrue(self.client.send({"n": 1}))
        self.accept()
        self.peer.close()
        self.peer = None
        # The first write after a hang-up can still land in the kernel; the
        # one after it finds the pipe broken and reconnects.
        self.client.send({"n": 2})
        self.assertTrue(self.client.send({"n": 3}))
        self.accept()
        lines = self.read_all()
        self.assertEqual(lines[-1]["n"], 3)


if __name__ == "__main__":
    unittest.main()
