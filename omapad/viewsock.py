"""Line-delimited JSON to a shell plugin's socket, with reconnect.

Both surfaces omapad draws - the keyboard and the menu - are best-effort
views: the state lives in the daemon, the plugin only paints it. So `send`
never raises and never waits, and the daemon re-sends periodically, which is
what lets a shell restart (a theme change does it) repaint itself with no
handshake.
"""

import errno
import json
import logging
import os
import socket
import time

from . import paths

log = logging.getLogger("omapad")

# The longest a string that came from a device may be when it reaches a
# surface. Not a setting: it bounds what something outside this machine can
# say, rather than expressing a preference about it - every row that draws one
# elides far short of this.
DRAWABLE = 128

# How long the shell may leave a socket unread before the journal says so.
# Not a setting: it decides nothing but whether a line is logged, and a tenth
# of a second is where a stall stops being a frame and starts being a press
# that looked ignored.
STALL_LOGGED = 0.1


def drawable(text, limit=DRAWABLE):
    """A string a device named itself with, made fit to hand a surface.

    A pad's name and an audio sink's description arrive from outside this
    machine - a USB descriptor, whatever a daemon was told to call a device -
    and land in a shell that stays up for the whole session. Two things happen
    to one before it goes on the wire. It is cut to a length a row can hold,
    because a name three screens long is not drawable and was not typed by
    anyone. And the characters that make Qt guess a string is rich text are
    dropped: a `Text` left to detect its own format renders `<img src=...>` in
    a device name by fetching what it points at. The panels here all say
    `textFormat: Text.PlainText`, but the bar's tooltip is Omarchy's `Text` and
    not ours to set - so the string itself is what has to be safe.
    """
    text = "".join(ch for ch in str(text) if ch >= " " and ch != "\x7f")
    text = text.replace("<", "").replace(">", "").strip()
    if len(text) > limit:
        text = text[:limit - 1].rstrip() + "\u2026"
    return text


class ViewClient:
    """One surface's socket, written without ever waiting on the shell.

    The shell is one thread for every panel it draws, and it stops reading
    for as long as it is busy: building a panel that is opening, or
    collecting what one that closed left behind. Measured under
    `budget stress`, every omapad socket sat unread for 0.3 to 1.2 seconds
    at a time around a surface opening. A blocking `sendall` spent that
    stall on the loop - half a second of timeout, then the line thrown away
    - so a pad nobody was pressing anything wrong on answered nothing, and
    the screen kept the old state until the next heartbeat.

    So the socket never blocks. What it will not take waits here, and only
    the newest of it: every line is the whole surface, so a line that has
    been overtaken is a line nobody needs. `flush` is the loop's end of it,
    on every pass while anything is waiting.
    """

    def __init__(self, name, path=None):
        self.name = name
        self.sock = None
        # The unsent end of a line the socket took part of. It goes before
        # anything else, or the panel reads half a line glued to the next.
        self._tail = b""
        # (line, whole) pairs behind it. A whole line supersedes everything
        # before it, so this is at most the last whole line and one short
        # line after it - see `send`.
        self._waiting = []
        # When the shell stopped reading, for the one log line saying so.
        self._stalled = None
        try:
            self.path = path or paths.socket_path(name)
            if path:
                reason = paths.private_dir_reason(path)
                if reason:
                    # What goes down here is whatever the surface is showing,
                    # which includes the line a keyboard page was filled with.
                    log.warning("%s is not private: %s - what it draws is "
                                "readable by anyone who binds there",
                                name, reason)
        except paths.RuntimeDirError as exc:
            # Best-effort here too: a directory private enough to bind in is
            # the same one we are willing to stream state into, and a daemon
            # that draws nothing still drives the desktop.
            log.warning("%s unavailable: %s", name, exc)
            self.path = None

    def connect(self):
        if self.sock is not None:
            return True
        if self.path is None or not os.path.exists(self.path):
            return False
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        except OSError:
            return False
        try:
            # Before the connect as well: a unix connect waits when the
            # listener's backlog is full, which is the shell not accepting -
            # the same stall as it not reading.
            sock.setblocking(False)
            sock.connect(self.path)
        except OSError:
            sock.close()
            return False
        self.sock = sock
        return True

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None
        self._tail = b""
        self._waiting = []
        self._stalled = None

    def waiting(self):
        """Is there anything the shell has not taken yet?"""
        return bool(self._tail or self._waiting)

    def send(self, payload, whole=True):
        """Push one state update. Never raises, and never waits.

        True when the line reached the socket, False when it is waiting for
        the shell or there is no shell to take it. `whole` is False only for
        the menu's short gauge line (viewsock.md), which says less than the
        whole surface and so cannot stand in for one: it is kept behind the
        last whole line rather than in place of it.
        """
        line = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        for _ in range(2):
            if not self.connect():
                return False
            if whole:
                self._waiting = [(line, True)]
            else:
                self._waiting = [entry for entry in self._waiting
                                 if entry[1]][-1:] + [(line, False)]
            written = self.flush()
            if written is not None:
                return written
            # The shell restarted under us: the socket is closed, and one
            # fresh connection gets this line.
        return False

    def flush(self):
        """Hand the shell as much as it will take.

        True when nothing is left waiting, False when the shell is not
        reading, None when the socket broke and has been closed - which
        `send` answers with one reconnect, as it always has.
        """
        if self.sock is None:
            return False
        while True:
            if not self._tail:
                if not self._waiting:
                    break
                self._tail = self._waiting.pop(0)[0]
            try:
                count = self.sock.send(self._tail)
            except (BlockingIOError, InterruptedError):
                if self._stalled is None:
                    self._stalled = time.monotonic()
                return False
            except OSError as exc:
                self.close()
                if exc.errno in (errno.EPIPE, errno.ECONNRESET,
                                 errno.ENOTCONN):
                    return None
                return False
            self._tail = self._tail[count:]
        if self._stalled is not None:
            took = time.monotonic() - self._stalled
            self._stalled = None
            if took >= STALL_LOGGED:
                log.info("%s: the shell took nothing for %d ms",
                         self.name, took * 1000.0)
        return True
