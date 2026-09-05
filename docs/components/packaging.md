# Packaging - `boot.sh`, `install.sh`, `systemd/`, `udev/`, `bin/`

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

## `systemd/omapad.service`

A user unit, `PartOf=graphical-session.target`. `__REPO__` in `ExecStart` is
substituted by `install.sh`. It sets `Environment=XDG_RUNTIME_DIR=%t` because
that one variable is what lets `actions.Session` rediscover the rest - a
systemd user service does not reliably inherit the compositor's.

```bash
systemctl --user restart omapad     # required after ANY code or config change
journalctl --user -u omapad -f
```

## `install.sh`

Idempotent, and **never run it from an agent session**: it uses `sudo`, writes
a udev rule and touches the user's systemd units. It is the user's to run.

It does five things: grant `/dev/uinput` to `input`, put a starter config in
`~/.config/omapad/`, link `bin/omapad` into `~/.local/bin`, link the checkout
into `~/.config/omarchy/plugins/` as `canerakdas.omapad` (validating the
manifest first), and install the user unit with the checkout path baked in.

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
