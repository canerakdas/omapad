# Socket directory - `omapad/paths.py`

Where the daemon's sockets live, and the one check that has to pass before
anything is bound or connected there.

## Why it is a module

Nothing on omapad's sockets is authenticated. The control socket takes
`press A`, which runs whatever that button is bound to, up to any `exec:`;
the view sockets carry what the surfaces are showing, and an app's keyboard
page can be filled from a command's output - a clipboard history, a list of
branches. There is no handshake anywhere, by design: a keypress must not wait
for one.

What stands in for authentication is the **directory**. `$XDG_RUNTIME_DIR` is
per-user and 0700, so a socket inside it is reachable by one account and no
other. That makes the fallback a security decision rather than a convenience:
`os.environ.get("XDG_RUNTIME_DIR") or "/tmp"` - what this used to be, in seven
places - hands the directory to whichever user creates it first. The daemon
*connects* to the view sockets, so a planted `osk.sock` does not just refuse
service; it receives everything the daemon would have drawn.

## The contract

- `socket_dir(create=False)` - `$XDG_RUNTIME_DIR/omapad`, or, when there is no
  per-user runtime directory at all, `/tmp/omapad-<uid>`. Under `/tmp` is
  fine; being `/tmp`, or a name every user would pick, is not.
- `socket_path(name, create=False)` - a socket inside it.
- `ensure_private(path)` - raises `RuntimeDirError` unless the path is a
  directory, owned by this uid, that no one else can write to. It uses
  `lstat`, so a symlink cannot pass the checks by describing its target. A
  path that does not exist yet is not an error: bind and connect report that
  better than a guess here would.

`RuntimeDirError` is a `RuntimeError` because that is already what the daemon
treats as "this plumbing is unavailable" rather than as a reason to stop
(`daemon.py` catches `(OSError, RuntimeError)` around `ControlServer`).

## Who follows the rule

| Where | What happens without a private directory |
|---|---|
| `control.py` (`ControlServer`) | Refuses to bind; the daemon logs it and runs on, unscriptable. |
| `control.py` (`send`) | `omapad ctl` prints the reason instead of connecting. |
| `viewsock.py` (`ViewClient`) | `path` is `None`, `connect()` is `False`, `send` still never raises. |
| `shell-plugin/*.qml` | `socketDir` is `""` and the `SocketServer` is not `active`: the surface binds nowhere rather than somewhere public. |

A socket path written in the config is the **user's own choice** and is taken
as written - `[control] socket`, `[osk] socket` and the rest skip these checks.
The default is ours, so making it private is ours too.
