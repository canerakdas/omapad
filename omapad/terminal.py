"""Is the terminal in front waiting at a prompt, or running something?

`ZL` + B closes the window everywhere, and a terminal is the one window where
closing is not always what was meant: a command still running is the thing in
front of you, and `Ctrl+C` is what stops it. Closing the window kills it
instead, along with the scrollback that said what it had done. So the button
asks first - is there anything to stop? - and the kernel already knows.

A pty has a **foreground process group**: the one a `Ctrl+C` typed at that
terminal is delivered to. `/proc/<pid>/stat` publishes it as `tpgid`, and the
shell the terminal started is the session leader of that pty. So the whole
question is one comparison - while the shell's own process group is the
foreground one, the prompt is what is in front and there is nothing to
interrupt.

Only the process tree under the focused window is asked, which is what makes
the two blind spots safe ones:

- a shell inside **tmux or screen** belongs to the multiplexer's session, and
  the server is not under the window at all, so a busy pane reads as idle and
  the window closes - exactly what this button did before;
- a terminal serving several windows from **one process** (`foot --server`,
  `kitty --single-instance`) is the other way round: any busy tty under that
  pid answers for all of them, so an idle window declines to close while
  another is still compiling.

Neither can close a window over a command that is running in it, which is the
direction that costs something.
"""

import os

from .handover import PROC, children_of

# The ceiling on what one press may spend reading /proc, counted in the files
# the walk actually opens. Not a setting: it is the bound on what a button
# costs, not a preference.
#
# It counts *threads* because that is where the cost is - a child forked by any
# thread is listed under that thread's own `children` file, so finding the
# children of an 86-thread process means 86 reads, measured at 10-15 us each.
# A terminal's whole tree is 24 of them and 0.12 ms; Steam's window is 172 and
# 2 ms. Without a bound, 64 processes of 20 threads would be 15 ms on the event
# loop - two ticks of pointer movement dropped, for a question about a window
# that has no terminal in it. A tree this wide is a browser's renderers, and
# the answer the bound cuts short is the one this button gave before any of
# this existed: close the window.
READ_LIMIT = 256


def job_state(pid, proc=PROC):
    """`(process group, session, foreground group)` for a pid on a tty.

    None where /proc has nothing to say, and - the common case - where the
    process has no controlling terminal at all, which is every process that is
    not part of one.
    """
    try:
        with open(os.path.join(proc, str(pid), "stat")) as handle:
            text = handle.read()
    except OSError:
        return None
    # The command sits in brackets and may contain spaces; everything after the
    # closing bracket is fixed-width. In order: state, ppid, pgrp, session,
    # tty_nr, tpgid.
    close = text.rfind(")")
    if close < 0:
        return None
    fields = text[close + 2:].split()
    if len(fields) < 6:
        return None
    try:
        pgrp, session, tty, foreground = (
            int(fields[2]), int(fields[3]), int(fields[4]), int(fields[5])
        )
    except ValueError:
        return None
    if not tty or foreground <= 0:
        return None
    return pgrp, session, foreground


def _thread_count(pid, proc):
    """How many `children` files reading this pid's children will cost."""
    try:
        return len(os.listdir(os.path.join(proc, str(pid), "task")))
    except OSError:
        return 0


def busy(pid, proc=PROC, depth=4):
    """Is a command running in the terminal this window belongs to?

    False for everything that is not a terminal, which is the answer that
    matters: a window with no pty under it has nothing to interrupt, so the
    button that asks this does what it has always done.

    `depth` is how far below the window's process to look. The shell is a
    direct child of every emulator measured here, so the default is already
    generous; a wrapper script or a login shell in between is what the rest of
    it is for. `READ_LIMIT` is the other bound, and the one that holds when a
    window has dozens of children rather than one.

    It never raises. A press is what asks the question, and an action that
    throws takes the event loop with it - so a pid that is nonsense, a /proc
    that says nothing and a process that ended mid-walk are all False.
    """
    if not pid:
        return False
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        # This is asked from an action, and an action that raises takes the
        # loop down with it: every answer here is a False, never an exception.
        return False
    frontier = {pid}
    seen = set(frontier)
    budget = READ_LIMIT
    for _ in range(depth + 1):
        for entry in frontier:
            state = job_state(entry, proc)
            if state is None:
                continue
            pgrp, session, foreground = state
            # Only the session leader answers for its pty: it is the shell the
            # terminal started, and its process group is the one the prompt
            # sits in. Anything else on that tty *is* the job being asked
            # about, and would report itself busy while it ran.
            if entry == session and foreground != pgrp:
                return True
        following = set()
        for entry in frontier:
            # Charged before the read, not after: the point is to not do it.
            budget -= _thread_count(entry, proc)
            if budget < 0:
                return False
            following |= children_of(entry, proc) - seen
        if not following:
            return False
        seen |= following
        frontier = following
    return False
