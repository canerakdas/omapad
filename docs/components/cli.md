# CLI - `omapad/__main__.py`, `bin/omapad`

`bin/omapad` is six lines of bash: work out the checkout, set `PYTHONPATH`,
`exec python3 -m omapad "$@"`. There is no build or install step while
developing - the wrapper runs straight from the tree.

## Commands

| Command | Function | Does |
|---|---|---|
| `run` (default) | `cmd_run` | the daemon: build the `Config`, start the `Daemon`, handle signals |
| `dump` | `cmd_dump` | print every event from the pad, for mapping a pad by hand. Says so when something else holds the pad exclusively - a running daemon makes it a partial witness, and a press caught half way reads as a stuck button |
| `check` | `cmd_check` | parse every binding, report the pad, and say what is wrong. Names any button the kernel has down (`held_keys`), which is the one thing that can be asked about a pad the daemon has grabbed |
| `budget [seconds]` | `cmd_budget` | what the daemon costs while nothing is happening: its memory, its share of a core over a sample, what one ask of *does the window in front hold the pad* costs here, and how many shells an open menu runs a minute |
| `ctl <verb> <command>` | `cmd_ctl` | send a command to a running daemon |
| `unit [check]` | `cmd_unit` | write the systemd user unit for this checkout, with the checkout's path baked into `ExecStart`; `check` answers whether that path can be baked in and writes nothing. What `install.sh` calls, at its last step and at its first. Prints the path alone, so the installer can say the sentence around it |

Global flags: `-c/--config`, `-v/--verbose`, `--version` (which prints
`__version__` from `omapad/__init__.py` - the only thing that file holds).

`ctl` verbs: `osk`, `menu`, `guide`, `map`, `surface`, `mode`, `lock`,
`status` - the
same set `control.py` dispatches and `Surfaces.qml` shells out to.

`unit` is the one command answered **before the config is loaded**: it is what
the installer runs, and someone re-running the installer to repair a broken
config must not be stopped by that config. Everything it decides lives in
[`omapad/unit.py`](packaging.md), because the installer used to decide it in
one line of shell where no test could reach it.

## `check` is the error surface

Everything that can be wrong in the config is validated at load, so `check` is
where a user finds out: it loads the config (surfacing `ConfigError`,
`ActionError`, `MenuError`, `OverrideError`, `KeyParseError`), then
`_check_settings` validates what the menu may change and `_check_keyboards`
reports which real keyboards would be opened. It also names the connected pad,
the profile it picked and the badge layout that follows from it.

`_no_controller(match)` is the shape to copy for a diagnostic: it names the
filter only when there is one, so the message is never "no controller matching
() is connected".

## `budget` is the other half of a counting test

The suite holds the loop to a **count** - one command per `ttl`, one walk of
`/proc` per focus change, no reading asked for that nothing draws. Counts are
what regress and counts are what a test can assert without a clock. What a
count cannot say is whether it is *affordable*, which depends on how many
processes this machine is running and how many rows this config gave the menu.
`budget` is that half, and the two are meant to be read together: a count
nobody has priced is not a budget, and a millisecond nobody has counted is not
one either.

What it prints, and where each figure comes from:

| Line | Source | Needs a daemon |
|---|---|---|
| `daemon:` | `ctl status`, which carries `pid` for exactly this | yes |
| `memory:` | `VmRSS` and `VmHWM` out of `/proc/<pid>/status`, and the drift across the sample | yes |
| `cpu:` | `utime + stime` out of `/proc/<pid>/stat`, over the sample | yes |
| `the pad question:` | `handover.wants_pad` timed here, against `[mode] handover_poll` | no |
| `menu commands:` | every `meta` and head line in the config, with its `ttl` | no |

Two things it deliberately does not do. It does not assert - nothing here is
a pass or a fail, because every figure moves with what else is running, and a
threshold would be a test that fails when a browser is open. And it does not
profile: `cProfile` on a running daemon needs `ptrace`, which is the sort of
thing a diagnostic must not ask a user for. When a figure here is wrong, the
ladder is [`pad-diagnose`](../procedures/pad-diagnose.md) and the tool is
`python3 -m cProfile -o out.prof -m omapad run` against a stopped service.

The CPU figure is read in **clock ticks** - hundredths of a second - so a
short sample of a quiet daemon is a number with no digits in it. Under five
ticks it says so and names a longer sample rather than printing a confident
`0.00%`.

## Rules

- A new subcommand is a `cmd_<name>` function and a row in the `choices` of
  `build_parser()`, and its help text says what it is for in one line.
- Anything a subcommand can report, `check` should be able to report too - it
  is the command a user is told to run.
- Output goes to stdout, diagnostics to stderr, and the exit status is
  meaningful: non-zero when the thing asked for could not be done.
