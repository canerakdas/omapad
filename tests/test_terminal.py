"""Is there anything to interrupt, answered from /proc rather than guessed."""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad import terminal


class RealProcTests(unittest.TestCase):
    """Against the real /proc: the point is that it answers truthfully."""

    def test_this_process_reads_its_own_job_state(self):
        # Run under a terminal there is a tty and a foreground group; run from
        # a service or a pipeline there is neither, and that is the answer for
        # every window that is not a terminal.
        state = terminal.job_state(os.getpid())
        if state is None:
            self.skipTest("no controlling terminal")
        pgrp, session, foreground = state
        self.assertGreater(pgrp, 0)
        self.assertGreater(session, 0)
        self.assertGreater(foreground, 0)

    def test_a_pid_that_is_gone_says_nothing(self):
        self.assertIsNone(terminal.job_state(0x7FFFFFFF))

    def test_no_window_is_no_terminal(self):
        self.assertFalse(terminal.busy(None))

    def test_nothing_it_is_asked_can_make_it_raise(self):
        # A press is what asks, and an action that throws takes the event loop
        # with it. Every answer is a False.
        for nonsense in ("", "not-a-pid", -1, object()):
            self.assertFalse(terminal.busy(nonsense))


class FakeProcTests(unittest.TestCase):
    """The shapes that matter, built to order: /proc cannot be arranged."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="omapad-proc-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def process(self, pid, parent=0, children=(), pgrp=0, session=0,
                tty=0, foreground=-1):
        base = os.path.join(self.root, str(pid))
        os.makedirs(os.path.join(base, "task", str(pid)), exist_ok=True)
        with open(os.path.join(base, "stat"), "w") as handle:
            # pid (comm) state ppid pgrp session tty_nr tpgid - the shape
            # job_state reads, with a bracketed name that has a space in it
            # for the same reason parent_of splits on the last bracket.
            handle.write("%d (some shell) S %d %d %d %d %d 0 0" % (
                pid, parent, pgrp or pid, session or pid, tty, foreground
            ))
        with open(os.path.join(base, "task", str(pid), "children"), "w") as f:
            f.write(" ".join(str(child) for child in children))

    def terminal_window(self, foreground):
        """A window whose shell is a session leader on a pty, as foot's is."""
        self.process(100, parent=1, children=[200])
        self.process(200, parent=100, tty=34816, foreground=foreground)
        return 100

    def test_a_prompt_has_nothing_to_interrupt(self):
        # The shell's own process group is the foreground one: what is in front
        # is the prompt, and Ctrl+C there would do nothing.
        window = self.terminal_window(foreground=200)
        self.assertFalse(terminal.busy(window, proc=self.root))

    def test_a_command_in_the_foreground_is_something_to_interrupt(self):
        # Anything else in the foreground is a job, and closing the window
        # would take it with the scrollback that said what it had done.
        window = self.terminal_window(foreground=250)
        self.assertTrue(terminal.busy(window, proc=self.root))

    def test_a_window_with_no_pty_under_it_is_not_a_terminal(self):
        # The answer for every other window on the desktop, and the reason the
        # binding is the window layer's rather than a profile's.
        self.process(100, parent=1, children=[200])
        self.process(200, parent=100)
        self.assertFalse(terminal.busy(100, proc=self.root))

    def test_a_background_job_is_not_in_front_of_anybody(self):
        # `sleep 100 &` leaves the shell in the foreground, and a Ctrl+C aimed
        # at the prompt would not reach it.
        window = self.terminal_window(foreground=200)
        self.process(300, parent=200, pgrp=300, session=200, tty=34816,
                     foreground=200)
        self.assertFalse(terminal.busy(window, proc=self.root))

    def test_the_job_itself_does_not_answer_for_the_tty(self):
        # Only the session leader is asked. The command *is* the answer, and a
        # process reading its own group off the tty would say "busy" for as
        # long as it ran - which is every terminal, always.
        self.process(100, parent=1, children=[200])
        self.process(200, parent=100, tty=34816, foreground=200)
        self.process(300, parent=200, pgrp=300, session=200, tty=34816,
                     foreground=200)
        self.assertFalse(terminal.busy(100, proc=self.root))

    def test_a_shell_under_a_wrapper_script_is_still_found(self):
        # What `depth` is for: the emulators measured here start the shell as a
        # direct child, and a login shell or a wrapper puts one more in the way.
        self.process(100, parent=1, children=[150])
        self.process(150, parent=100, children=[200])
        self.process(200, parent=150, tty=34816, foreground=250)
        self.assertTrue(terminal.busy(100, proc=self.root))

    def test_and_not_past_the_depth_it_was_given(self):
        self.process(100, parent=1, children=[150])
        self.process(150, parent=100, children=[200])
        self.process(200, parent=150, tty=34816, foreground=250)
        self.assertFalse(terminal.busy(100, proc=self.root, depth=1))

    def test_a_tree_too_wide_to_read_on_a_press_is_not_read(self):
        # A browser's renderers, not a terminal: the walk runs out of
        # READ_LIMIT, and what it gives up is the answer this button had
        # before any of this existed - close the window.
        wide = list(range(1000, 1000 + terminal.READ_LIMIT + 10))
        self.process(100, parent=1, children=wide)
        for child in wide:
            self.process(child, parent=100, children=[child + 5000])
            self.process(child + 5000, parent=child, tty=34816, foreground=1)
        self.assertFalse(terminal.busy(100, proc=self.root))

    def test_one_process_serving_two_windows_answers_for_both(self):
        # foot --server and kitty --single-instance: the busy tty is not
        # necessarily the window in front, so an idle one declines to close
        # while another is still compiling. The safe direction - the other one
        # closes a window over a running command.
        self.process(100, parent=1, children=[200, 300])
        self.process(200, parent=100, tty=34816, foreground=200)
        self.process(300, parent=100, tty=34817, foreground=350)
        self.assertTrue(terminal.busy(100, proc=self.root))
