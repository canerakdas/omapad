"""The control socket: one connection, many commands, line at a time.

The pad-and-desk story depends on this staying fast: the shell holds one
connection open and streams `menu up`/`menu down` as the user presses keys,
so a command must never wait for a connect, and the daemon must never block
its device loop on an idle open connection.
"""

import os
import socket
import tempfile
import time
import unittest

import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad import control as control_module


class LineReader:
    """Read one line-terminated reply at a time, keeping what is left over.

    The daemon writes every reply into the socket in one pass, so a single
    recv often returns several replies; the reader must not discard the ones
    that overran the requested line.
    """

    def __init__(self, connection):
        self.connection = connection
        self.buffer = b""

    def readline(self):
        while b"\n" not in self.buffer:
            chunk = self.connection.recv(4096)
            if not chunk:
                break
            self.buffer += chunk
        line, _, self.buffer = self.buffer.partition(b"\n")
        return line.decode("utf-8", "replace")


class ControlServerTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="omapad-control-test-")
        self.path = os.path.join(self.dir, "control.sock")
        self.server = control_module.ControlServer(self.path)
        self.handled = []

    def tearDown(self):
        self.server.close()
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)

    def dispatch(self, command):
        self.handled.append(command)
        return "ack:%s" % command

    def connect(self):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        sock.connect(self.path)
        return sock

    def serve_once(self):
        self.server.serve(self.dispatch)

    def test_one_connection_answers_many_commands(self):
        # The shell's pattern: open once, stream. Every line gets its own
        # answer and the connection stays usable.
        client = self.connect()
        replies = LineReader(client)
        client.sendall(b"menu up\nmenu down\nmenu press\n")
        time.sleep(0.05)
        self.serve_once()
        self.assertEqual(replies.readline(), "ack:menu up")
        self.assertEqual(replies.readline(), "ack:menu down")
        self.assertEqual(replies.readline(), "ack:menu press")
        # The connection is still open: another command works without a
        # reconnect.
        client.sendall(b"menu up\n")
        time.sleep(0.05)
        self.serve_once()
        self.assertEqual(replies.readline(), "ack:menu up")
        self.assertEqual(self.handled,
                         ["menu up", "menu down", "menu press", "menu up"])
        client.close()

    def test_two_connections_are_independent(self):
        first = self.connect()
        second = self.connect()
        first.sendall(b"menu up\n")
        second.sendall(b"menu down\n")
        time.sleep(0.05)
        self.serve_once()
        # Each answer goes to the connection that asked for it.
        self.assertEqual(LineReader(first).readline(), "ack:menu up")
        self.assertEqual(LineReader(second).readline(), "ack:menu down")
        first.close()
        second.close()

    def test_an_idle_connection_never_blocks_the_loop(self):
        # Accept the connection, then serve with nothing pending: it must
        # return immediately rather than waiting for data.
        client = self.connect()
        time.sleep(0.05)
        start = time.monotonic()
        self.serve_once()
        self.assertLess(time.monotonic() - start, 0.1)
        client.close()

    def test_a_partial_line_is_held_until_the_newline(self):
        # The daemon answers commands, not fragments: half a command means
        # nothing, and the rest arrives later.
        client = self.connect()
        replies = LineReader(client)
        client.sendall(b"menu u")
        time.sleep(0.05)
        self.serve_once()
        self.assertEqual(self.handled, [])
        client.sendall(b"p\n")
        time.sleep(0.05)
        self.serve_once()
        self.assertEqual(self.handled, ["menu up"])
        client.close()

    def test_hang_up_drops_the_connection(self):
        client = self.connect()
        time.sleep(0.05)
        self.serve_once()
        self.assertEqual(len(self.server.open_fds()), 1)
        client.close()
        time.sleep(0.05)
        self.serve_once()
        self.assertEqual(self.server.open_fds(), [])

    def test_a_shell_reconnect_takes_over_cleanly(self):
        # A restarted shell (the daemon restarted, or the plugin reloaded)
        # opens a fresh connection; the old dead one must not hold a reply
        # hostage.
        old = self.connect()
        old_replies = LineReader(old)
        old.sendall(b"menu up\n")
        time.sleep(0.05)
        self.serve_once()
        self.assertEqual(old_replies.readline(), "ack:menu up")
        old.close()
        time.sleep(0.05)
        self.serve_once()
        new = self.connect()
        new.sendall(b"menu down\n")
        time.sleep(0.05)
        self.serve_once()
        self.assertEqual(LineReader(new).readline(), "ack:menu down")
        new.close()

    def test_the_cli_helper_round_trips(self):
        # `omapad ctl` goes through send(): one command, one reply, close.
        # In the daemon the serve loop runs in parallel; here a thread stands
        # in for it while the blocking send waits for its reply.
        import threading
        import select

        stop = threading.Event()

        def run_server():
            poller = select.poll()
            fd = self.server.fileno()
            poller.register(fd, select.POLLIN)
            while not stop.is_set():
                for _, _ in poller.poll(0.05):
                    self.server.serve(self.dispatch)

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        try:
            reply = control_module.send("mode status", self.path)
            self.assertEqual(reply, "ack:mode status")
        finally:
            stop.set()
            thread.join(timeout=1.0)
        time.sleep(0.05)
        self.serve_once()
        # And the connection the CLI left is gone.
        self.assertEqual(self.server.open_fds(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)