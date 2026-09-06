"""Line-delimited JSON to a shell plugin's socket, with reconnect.

Both surfaces omapad draws - the keyboard and the menu - are best-effort
views: the state lives in the daemon, the plugin only paints it. So `send`
never raises, and the daemon re-sends periodically, which is what lets a shell
restart (a theme change does it) repaint itself with no handshake.
"""

import errno
import json
import logging
import os
import socket

from . import paths

log = logging.getLogger("omapad")

# The longest a string that came from a device may be when it reaches a
# surface. Not a setting: it bounds what something outside this machine can
# say, rather than expressing a preference about it - every row that draws one
# elides far short of this.
DRAWABLE = 128


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
    def __init__(self, name, path=None):
        self.sock = None
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
            sock.settimeout(0.5)
            sock.connect(self.path)
            self.sock = sock
            return True
        except OSError:
            self.sock = None
            return False

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    def send(self, payload):
        """Push one state update. Never raises: the view is best-effort."""
        line = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        for _ in range(2):
            if not self.connect():
                return False
            try:
                self.sock.sendall(line)
                return True
            except OSError as exc:
                # The shell restarted: drop the socket and try once more.
                self.close()
                if exc.errno not in (errno.EPIPE, errno.ECONNRESET, errno.ENOTCONN):
                    return False
        return False
