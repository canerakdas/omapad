"""Who wants the pad, answered from /proc rather than from a list of games."""

import os
import sys
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad import handover


class HoldersTests(unittest.TestCase):
    """Read against the real /proc: the point is that it answers truthfully."""

    def setUp(self):
        # A file of our own rather than a device: half the system holds
        # /dev/null open, which would make every answer here true.
        handle, path = tempfile.mkstemp(prefix="omapad-node-")
        os.close(handle)
        self.addCleanup(os.unlink, path)
        self.handle = open(path, "rb")
        self.addCleanup(self.handle.close)
        self.nodes = {path}

    def test_a_process_holding_the_node_is_found(self):
        self.assertIn(os.getpid(), handover.holders(self.nodes))

    def test_our_own_pid_can_be_left_out(self):
        # omapad holds the pad itself, and would otherwise hand it to
        # whatever window happens to be in front of its own process tree.
        found = handover.holders(self.nodes, skip_pid=os.getpid())
        self.assertNotIn(os.getpid(), found)

    def test_a_node_nobody_has_open_finds_nobody(self):
        self.assertEqual(handover.holders({"/dev/input/by-id/no-such-pad"}), set())


class NodeTests(unittest.TestCase):
    def test_the_hidraw_node_counts_as_the_same_pad(self):
        # Steam reads controllers through hidraw and opens nothing under
        # /dev/input, so a check that watched only the event node would decide
        # Steam had never asked for the pad. Measured on this machine before it
        # was believed.
        import glob
        events = glob.glob("/sys/class/input/event*")
        if not events:
            self.skipTest("no input devices")
        for path in events:
            node = path.replace("/sys/class/input", "/dev/input")
            nodes = handover.device_nodes(node)
            if any(node.startswith("/dev/hidraw") for node in nodes):
                return
        self.skipTest("no HID input device on this machine")


class TreeTests(unittest.TestCase):
    def test_a_process_knows_its_parent(self):
        self.assertEqual(handover.parent_of(os.getpid()), os.getppid())

    def test_related_reaches_up_the_tree(self):
        # Steam launches a game through a reaper and a wrapper, so the window's
        # own pid is not always the process that opened the device.
        family = handover.related(os.getpid())
        self.assertIn(os.getpid(), family)
        self.assertIn(os.getppid(), family)

    def test_but_not_all_the_way_to_init(self):
        # Walking to the session leader would make every window on the desktop
        # look like the one that opened the pad.
        self.assertNotIn(1, handover.related(os.getpid()))


class FakeProcTests(unittest.TestCase):
    """The tree walk, against a /proc built to a known shape.

    Steam -> reaper -> game is the shape that matters, and the real /proc
    cannot be arranged into it on demand.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="omapad-proc-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def process(self, pid, parent=0, children=(), holds=(), cgroup=None):
        base = os.path.join(self.root, str(pid))
        os.makedirs(os.path.join(base, "fd"), exist_ok=True)
        os.makedirs(os.path.join(base, "task", str(pid)), exist_ok=True)
        if cgroup is not None:
            with open(os.path.join(base, "cgroup"), "w") as handle:
                handle.write("0::%s\n" % cgroup)
        with open(os.path.join(base, "stat"), "w") as handle:
            # pid (comm) state ppid ... - the shape parent_of reads.
            handle.write("%d (some app) S %d 0 0 0" % (pid, parent))
        with open(os.path.join(base, "task", str(pid), "children"), "w") as handle:
            handle.write(" ".join(str(child) for child in children))
        for index, node in enumerate(holds):
            os.symlink(node, os.path.join(base, "fd", str(index)))

    def test_the_launcher_that_opened_it_counts_for_the_game_it_started(self):
        # The window is the game's; the device was opened by the wrapper that
        # started it. Same tree, same answer.
        self.process(100, parent=1, children=[200], holds=["/dev/input/event9"])
        self.process(200, parent=100)
        self.assertTrue(
            handover.wants_pad(200, {"/dev/input/event9"}, proc=self.root)
        )

    def test_a_window_from_a_different_tree_does_not(self):
        # Steam holds every device open for as long as it runs; the terminal
        # in front of it has not asked for anything.
        self.process(100, parent=1, holds=["/dev/input/event9"])
        self.process(300, parent=1)
        self.assertFalse(
            handover.wants_pad(300, {"/dev/input/event9"}, proc=self.root)
        )

    def test_a_child_that_opened_it_counts_for_the_window_above(self):
        self.process(100, parent=1, children=[200])
        self.process(200, parent=100, holds=["/dev/input/event9"])
        self.assertTrue(
            handover.wants_pad(100, {"/dev/input/event9"}, proc=self.root)
        )

    def wine_shape(self, scope="/app.slice/game.scope", sibling_scope=None):
        """Proton: the adverb starts the game and wine's HID service beside it.

        The window belongs to the game; the pad was opened by the sibling.
        """
        self.process(100, parent=1, children=[200], cgroup=scope)
        self.process(200, parent=100, children=[300, 400], cgroup=scope)
        self.process(300, parent=200, cgroup=scope)  # the game's window
        self.process(
            400,
            parent=200,
            holds=["/dev/input/event9"],
            cgroup=sibling_scope or scope,
        )
        return 300

    def test_a_sibling_in_the_same_scope_counts(self):
        # winedevice.exe opens the pad; the game's own process never does.
        window = self.wine_shape()
        self.assertTrue(
            handover.wants_pad(window, {"/dev/input/event9"}, proc=self.root)
        )

    def test_a_sibling_in_another_scope_does_not(self):
        # The shape a terminal makes: its parent is the compositor, and the
        # game beside it is somebody else's app.
        window = self.wine_shape(sibling_scope="/app.slice/other.scope")
        self.assertFalse(
            handover.wants_pad(window, {"/dev/input/event9"}, proc=self.root)
        )

    def test_without_a_cgroup_to_read_the_step_sideways_is_not_taken(self):
        # No boundary, no way to tell an app's other half from the desktop's.
        self.process(100, parent=1, children=[200])
        self.process(200, parent=100, children=[300, 400])
        self.process(300, parent=200)
        self.process(400, parent=200, holds=["/dev/input/event9"])
        self.assertFalse(
            handover.wants_pad(300, {"/dev/input/event9"}, proc=self.root)
        )

    def test_siblings_off_keeps_to_the_window_own_line(self):
        window = self.wine_shape()
        self.assertFalse(
            handover.wants_pad(
                window, {"/dev/input/event9"}, proc=self.root, siblings=False
            )
        )

    def test_depth_bounds_how_far_the_launchers_reach(self):
        # Steam holds the pad all evening, and it sits four up from the game.
        self.process(5, parent=1, children=[10], holds=["/dev/input/event9"])
        self.process(10, parent=5, children=[100])
        self.process(100, parent=10, children=[200])
        self.process(200, parent=100, children=[300])
        self.process(300, parent=200)
        self.assertFalse(
            handover.wants_pad(300, {"/dev/input/event9"}, proc=self.root)
        )
        self.assertTrue(
            handover.wants_pad(
                300, {"/dev/input/event9"}, proc=self.root, depth=4
            )
        )


class WantsPadTests(unittest.TestCase):
    def setUp(self):
        handle, path = tempfile.mkstemp(prefix="omapad-node-")
        os.close(handle)
        self.addCleanup(os.unlink, path)
        self.handle = open(path, "rb")
        self.addCleanup(self.handle.close)
        self.nodes = {path}

    def test_the_focused_process_holding_it_wants_it(self):
        self.assertTrue(handover.wants_pad(os.getpid(), self.nodes))

    def test_nothing_focused_means_nothing_to_hand_it_to(self):
        self.assertFalse(handover.wants_pad(None, self.nodes))

    def test_a_pad_nobody_has_opened_stays_ours(self):
        self.assertFalse(
            handover.wants_pad(os.getpid(), {"/dev/input/by-id/no-such-pad"})
        )

    def test_our_own_hold_does_not_count_as_the_app_wanting_it(self):
        # The daemon has the pad open at all times; if that counted, it would
        # hand the pad away the moment its own process tree held focus.
        self.assertFalse(
            handover.wants_pad(os.getpid(), self.nodes, skip_pid=os.getpid())
        )


if __name__ == "__main__":
    unittest.main()
