"""Where omapad's sockets live, and why the directory is not a guess.

Nothing on these sockets is authenticated: the control socket takes commands
that reach any `exec:` a binding can run, and the view sockets carry whatever
the surfaces are showing, which includes the lines an app's keyboard page was
filled with. What keeps another user on the machine away from all of that is
the directory - `$XDG_RUNTIME_DIR` is per-user and 0700, and every socket is
placed inside it.

So the fallback matters as much as the path. Falling back to `/tmp` hands the
directory to whoever creates it first: a socket planted there is one the
daemon connects to and streams its state into. When the variable is missing,
this falls back to a directory of its own instead - created 0700, owned by us
- and refuses a directory that is not private rather than using it.
"""

import os
import stat


class RuntimeDirError(RuntimeError):
    """The socket directory is not ours and not private, so nothing goes in it.

    A RuntimeError because that is what the daemon already treats as "this
    piece of plumbing is unavailable" rather than as a reason to stop.
    """


def socket_dir(create=False):
    """The directory omapad's sockets live in, once it is known to be private."""
    runtime = os.environ.get("XDG_RUNTIME_DIR") or "/run/user/%d" % os.getuid()
    if os.path.isdir(runtime):
        path = os.path.join(runtime, "omapad")
    else:
        # No per-user runtime directory at all - a shell started outside a
        # session does this. A directory of our own under /tmp is still
        # private; /tmp itself is every user on the machine.
        path = "/tmp/omapad-%d" % os.getuid()
    if create:
        os.makedirs(path, mode=0o700, exist_ok=True)
    ensure_private(path)
    return path


def socket_path(name, create=False):
    """`name` inside the socket directory - "osk.sock", "control.sock"."""
    return os.path.join(socket_dir(create=create), name)


def ensure_private(path):
    """Raise unless `path` is a directory of ours that only we can write to.

    `lstat`, not `stat`: a symlink pointing at a directory someone else owns
    would otherwise pass every check below by describing its target.
    """
    try:
        info = os.lstat(path)
    except OSError:
        # Not there yet. Whoever binds or connects will say so more usefully
        # than a guess made here would.
        return
    if not stat.S_ISDIR(info.st_mode):
        raise RuntimeDirError("%s is not a directory" % path)
    if info.st_uid != os.getuid():
        raise RuntimeDirError("%s belongs to uid %d, not to us"
                              % (path, info.st_uid))
    if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise RuntimeDirError("%s is writable by other users" % path)
