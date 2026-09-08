# Packaging - `boot.sh`, `install.sh`, `omapad/unit.py`, `systemd/`, `udev/`, `bin/`

There is no build step. `bin/omapad` sets `PYTHONPATH` and runs the package
straight out of the checkout, which is why development needs nothing installed
and why the systemd unit points back at the tree.

## `bin/`

One file: `omapad`, the wrapper - find the checkout, set `PYTHONPATH`,
`exec python3 -m omapad "$@"`. Everything else is a subcommand of it.

## `udev/99-omapad-uinput.rules`

The daemon creates a virtual mouse and keyboard, which needs write access to
`/dev/uinput`. The rule gives it to the `input` group so **the daemon never
runs as root**, with `static_node=uinput` so the mode applies before the module
is loaded on demand.

This file is the copy for packagers. `install.sh` does **not** install it:
it carries the same bytes in a quoted here-document and writes those. The
checkout is writable by the user running the installer, and `sudo` opens a
source path only when it finally runs - after a password prompt someone stood
waiting at - so a rule read from the tree is a file another process of the same
user had a window to swap, and a udev rule can name something to run as root.
`tests/test_packaging.py` compares the two and fails if they drift, and it also
fails if any `sudo` line in the installer grows a `$REPO` path again.

## `systemd/omapad.service`

A user unit, `PartOf=graphical-session.target`. `__REPO__` in `ExecStart` is
substituted by `omapad unit` - see below. It sets
`Environment=XDG_RUNTIME_DIR=%t` because
that one variable is what lets `actions.Session` rediscover the rest - a
systemd user service does not reliably inherit the compositor's.

```bash
systemctl --user restart omapad     # required after ANY code or config change
journalctl --user -u omapad -f
```

## `omapad/unit.py`

Installing the unit is a template and a path, and it used to be one line of
shell:

```bash
sed "s|__REPO__|$REPO|g" "$REPO/systemd/omapad.service" > "$UNIT_DIR/omapad.service"
```

Both halves of that line were wrong, and both were wrong in a way that only
shows up on somebody else's machine:

- **A path is not replacement syntax.** In a `sed` replacement `&` is the whole
  match, `|` was the delimiter, a backslash escapes and a newline ends the
  command - so a checkout at a path carrying any of them writes a unit nobody
  wrote, and a unit is a thing systemd starts.
- **`>` opens the destination through whatever name is already there.** A
  symlink planted at `~/.config/systemd/user/omapad.service` made the installer
  truncate and rewrite the file it pointed at, anywhere the user can write. And
  the redirection truncates first: an interruption, a full disk, a `sed` that
  failed, and what is left where systemd reads it is half a unit.

So the substitution is `str.replace` and the write is a rename:

| | |
|---|---|
| `check_repo(repo)` | Refuses a path that cannot be baked in **unchanged** rather than escaping it. `SAFE` is the unit's own grammar: systemd splits `ExecStart` on whitespace and reads `%` as a specifier, so a space or a `%` cannot be quoted into meaning the path. A checkout is somewhere the user chose, so saying which characters are impossible costs them a `mv`. |
| `read_template(path)` | Bounded - a unit is a page of text, and a larger file is not the template. |
| `render(template, repo)` | `str.replace`, after `check_repo`. The path is data in every layer it passes through, and `%t` in the template stays the specifier it is. |
| `refuse_planted(dest)` | `lstat` the destination immediately before the rename: a symlink or anything that is not a regular file stops the install. `rename` never follows a symlink at the name, so this is not what makes the write safe - it is what stops it being silent. |
| `install(text, dest)` | `mkstemp` in the destination's **own directory** (so the rename is a rename), write, `fsync`, `chmod 0644`, check, `rename`. Cleanup is under `except BaseException`, because a Ctrl-C is the interruption the shape exists for, and the temporary file must not outlive it in a directory systemd reads. |
| `verify(text, dest)` | Reads the unit back before `systemctl daemon-reload` - the same move the udev rule makes, for the same reason: the reload is what makes a unit real. |

`omapad unit` runs all of it; `omapad unit check` runs only `check_repo`, which
is why `install.sh` can refuse a checkout it cannot install **before** its
first `sudo`. `tests/test_unit.py` covers the failing paths - a planted
symlink, a path that used to be syntax, a write interrupted before the rename -
and `tests/test_packaging.py` fails if the installer grows a `sed` or a
redirection into a unit again.

## `install.sh`

Idempotent, and **never run it from an agent session**: it uses `sudo`, writes
a udev rule and touches the user's systemd units. It is the user's to run.

It does five things, after asking `omapad unit check` whether this checkout
can be installed at all: grant `/dev/uinput` to `input` (writing the udev rule
from its own bytes and reading it back before `udevadm` acts on it), put a
starter config in
`~/.config/omapad/`, link `bin/omapad` into `~/.local/bin`, link the checkout
into `~/.config/omarchy/plugins/` as `canerakdas.omapad` (validating the
manifest first), and install the user unit with the checkout path baked in.

Two of those steps write a file at a name the user's own machine already has
an opinion about. The unit is written by `omapad unit`, above. The config stub
keeps a symlink it finds rather than writing through it - `-f` is true through
a link and `cat >` follows one, so a stub would otherwise land on whatever the
link points at.

## `boot.sh`

The two lines a stranger runs: `export OMAPAD_SHA=<commit>`, then `curl -fsSL
.../$OMAPAD_SHA/boot.sh | bash`. It fetches
and hands over, nothing else - it clones into
`~/.config/omarchy/plugins/canerakdas.omapad`, so the checkout is the plugin
itself, then `exec`s that checkout's `install.sh`.

It exists because Omarchy has **no post-install hook for plugins**: `omarchy
plugin add` clones, validates and enables, and `omarchy plugin update` only
pulls. Neither can grant `/dev/uinput` or install a user service, so without
this the first install is always two commands.

Where it fetches from is settings, defaulted in place - `OMAPAD_REPO`,
`OMAPAD_PLUGIN_ID`, `OMAPAD_DIR` - which is also how it is tested against a
local clone without touching the machine. `OMAPAD_SHA` is the exception with no
default: the commit to install is **named from outside**, because a default
written into `boot.sh` cannot name the commit that contains it. Carrying one
cost a "move the pin" commit per release, which left the submitted snapshot,
the attested snapshot and the branch tip as three different objects - the
mismatch a marketplace review reports, rather than anything wrong with the
code.

It refuses rather than guesses: a target that exists but is not a checkout is
left alone, an update stops rather than reset a checkout someone has edited,
and `OMAPAD_SHA` must be set and a full 40-character commit SHA, never a branch
name. That commit is checked out in detached mode and verified against `HEAD`
before anything from the remote executes, so a branch moving after a review can
never change what an install runs. `tests/test_packaging.py` is what keeps the
pin from creeping back and the manifest's version in step with
`omapad.__version__`.

See [`../conventions/bash.md`](../conventions/bash.md) for how to change it.
