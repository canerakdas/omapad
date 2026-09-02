"""A small control socket, so the daemon can be driven without the pad.

Useful for binding the keyboard to a Hyprland shortcut, for scripts, and for
checking state:

    omapad ctl osk toggle
    omapad ctl mode game
    omapad ctl status
"""

import os
import socket


class ControlServer:
    """One short request per connection, in the shape hyprctl uses."""

    def __init__(self, path=None):
        runtime = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
        self.path = path or os.path.join(runtime, "omapad", "control.sock")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        # A socket left behind by a killed daemon would block the bind.
        if os.path.exists(self.path):
            try:
                probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                probe.settimeout(0.2)
                probe.connect(self.path)
                probe.close()
                raise RuntimeError("another omapad is listening on %s" % self.path)
            except (ConnectionRefusedError, FileNotFoundError, socket.timeout):
                os.unlink(self.path)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.setblocking(False)
        self.sock.bind(self.path)
        self.sock.listen(4)

    def fileno(self):
        return self.sock.fileno()

    def serve(self, dispatch):
        """Accept whatever is pending and answer each caller."""
        while True:
            try:
                connection, _ = self.sock.accept()
            except (BlockingIOError, OSError):
                return
            with connection:
                connection.settimeout(0.5)
                try:
                    request = connection.recv(1024).decode("utf-8", "replace")
                    reply = dispatch(request.strip())
                    connection.sendall((reply or "ok").encode("utf-8"))
                except (OSError, socket.timeout):
                    pass

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass
        try:
            os.unlink(self.path)
        except OSError:
            pass


def send(command, path=None):
    """Client side: send one command, return the daemon's reply."""
    runtime = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    path = path or os.path.join(runtime, "omapad", "control.sock")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(2.0)
        sock.connect(path)
        sock.sendall(command.encode("utf-8"))
        chunks = []
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
    return b"".join(chunks).decode("utf-8", "replace")
