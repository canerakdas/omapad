# Bash style guide

Three files: `bin/omapad`, `install.sh` and `boot.sh`. See
[`README.md`](README.md) for how MUST / SHOULD / MAY are meant here.

## 1 What shell is for here

**1.1** Shell is glue, never logic. Anything that makes a decision belongs in
Python, where a test can reach it. `bin/omapad` is six lines: find the
checkout, set `PYTHONPATH`, `exec`.

**1.2** A new script is almost always the wrong answer — a `omapad`
subcommand is the right one. `bin/` holds entry points, not behaviour.

## 2 Every script

**2.1** MUST begin `#!/usr/bin/env bash` and `set -euo pipefail`.

**2.2** MUST be `chmod +x`, with no extension: `omapad`, not `omapad.sh`.

**2.3** MUST open with a comment saying what it does and, for `install.sh`,
that it is safe to re-run.

**2.4** Find the checkout from the script itself, NEVER from `$PWD` — the
install paths are symlinks, which is what makes `readlink -f` load-bearing:

```bash
REPO="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
```

**2.5** Quote every expansion. Arrays for lists of candidates, never a
space-separated string.

**2.6** `exec` the real program last, so signals and exit status pass through
and no shell is left under systemd.

## 3 Settings

**3.1** Every knob is an environment variable with its default in place —
the same rule the config file follows, so the value in the script is the
default and not the decision:

```bash
HEIGHT="${OMAPAD_OSK_HEIGHT:-320}"                     # ✅
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/omapad"  # ✅
```

**3.2** Respect the XDG variables wherever a path is built.

## 4 `install.sh`

**4.1** NEVER run it from an agent session, and never as part of a change: it
uses `sudo`, writes a udev rule and touches the user's systemd units. It is
the user's to run. The same goes for `boot.sh`, which ends by `exec`ing it -
test that one against a local clone with `OMAPAD_REPO` and `OMAPAD_DIR`
instead.

**4.2** Every step MUST be idempotent and safe to re-run. A step already done
says so and moves on.

**4.3** Report with the two helpers already there — `say` for a step, `warn`
for something the user must act on — so the output is a narrative of what is
being changed on their machine.

**4.4** Anything needing `sudo` is announced in the line before it runs, with
the reason. The daemon MUST never need root; that is the whole point of the
udev rule.

**4.5** Numbered sections with a `# --- n. name ---` banner, in the order a
reader would do them by hand.

## 5 Checking

```bash
bash -n install.sh      # syntax
shellcheck install.sh   # if it is installed; not a dependency
```
