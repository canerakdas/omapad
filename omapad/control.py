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
    """Answer commands over one or more connections, in the shape hyprctl uses.

    The CLI opens one connection, sends one command and hangs up; the shell
    keeps one connection open and streams commands. Both are answered line by
    line: every request is terminated by a newline and every reply is one
    newline-terminated line, so a stream never has to guess where a reply
    ends.
    """

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
        # Every open connection and the bytes it has sent but we have not yet
        # split into lines. Keyed by fd so the daemon's poll loop can watch
        # each one next to the listening socket.
        self.connections = {}
        self.buffers = {}

    def fileno(self):
        return self.sock.fileno()

    def open_fds(self):
        """Fds of the live connections, for the poll loop to watch."""
        return sorted(self.connections)

    def serve(self, dispatch):
        """Answer whatever is ready: new connections and buffered lines.

        Accepting and reading are non-blocking, so an idle open connection
        never stalls the daemon's loop; every complete line is answered in the
        pass in which it arrived. A client that hangs up mid-line loses the
        command - it was never complete, so there is nothing to answer.
        """
        # Accept everything pending before reading, so a burst of connections
        # is drained in one pass and no fd waits for the next tick.
        while True:
            try:
                connection, _ = self.sock.accept()
            except (BlockingIOError, OSError):
                break
            try:
                connection.setblocking(False)
            except OSError:
                try:
                    connection.close()
                except OSError:
                    pass
                continue
            self.connections[connection.fileno()] = connection
            self.buffers[connection.fileno()] = b""

        for fd in list(self.connections):
            connection = self.connections[fd]
            buffer = self.buffers[fd]
            try:
                chunk = connection.recv(4096)
            except (BlockingIOError, socket.timeout):
                continue
            except OSError:
                chunk = b""
            if not chunk:
                # EOF: the client hung up. Its fds are gone with it.
                del self.connections[fd]
                del self.buffers[fd]
                try:
                    connection.close()
                except OSError:
                    pass
                continue
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                command = line.decode("utf-8", "replace").strip()
                if not command:
                    continue
                reply = dispatch(command)
                try:
                    connection.sendall(
                        ((reply or "ok") + "\n").encode("utf-8")
                    )
                except (OSError, BlockingIOError):
                    # The client vanished mid-reply; it will reconnect.
                    pass
            self.buffers[fd] = buffer

    def close(self):
        for connection in self.connections.values():
            try:
                connection.close()
            except OSError:
                pass
        self.connections.clear()
        self.buffers.clear()
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
        sock.sendall(command.encode("utf-8") + b"\n")
        chunks = []
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
            if b"\n" in chunk:
                break
    return b"".join(chunks).decode("utf-8", "replace").strip()