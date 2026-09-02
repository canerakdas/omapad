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

The one command a stranger runs: `curl -fsSL .../boot.sh | bash`. It fetches
and hands over, nothing else - it clones into
`~/.config/omarchy/plugins/canerakdas.omapad`, so the checkout is the plugin
itself, then `exec`s that checkout's `install.sh`.

It exists because Omarchy has **no post-install hook for plugins**: `omarchy
plugin add` clones, validates and enables, and `omarchy plugin update` only
pulls. Neither can grant `/dev/uinput` or install a user service, so without
this the first install is always two commands.

Where it fetches from is settings, defaulted in place - `OMAPAD_REPO`,
`OMAPAD_BRANCH`, `OMAPAD_PLUGIN_ID`, `OMAPAD_DIR` - which is also how it is
tested against a local clone without touching the machine.

It refuses rather than guesses: a target that exists but is not a checkout is
left alone, and an update is `--ff-only`, because a checkout someone has edited
is theirs.

See [`../conventions/bash.md`](../conventions/bash.md) for how to change it.
