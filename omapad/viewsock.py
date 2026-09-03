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


class ViewClient:
    def __init__(self, name, path=None):
        self.sock = None
        try:
            self.path = path or paths.socket_path(name)
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
