# Packaging - `install.sh`, `systemd/`, `udev/`, `bin/`

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

See [`../conventions/bash.md`](../conventions/bash.md) for how to change it.
