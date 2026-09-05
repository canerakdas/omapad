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
| `ctl <verb> <command>` | `cmd_ctl` | send a command to a running daemon |

Global flags: `-c/--config`, `-v/--verbose`, `--version` (which prints
`__version__` from `omapad/__init__.py` - the only thing that file holds).

`ctl` verbs: `osk`, `menu`, `guide`, `map`, `surface`, `mode`, `lock`,
`status` - the
same set `control.py` dispatches and `Surfaces.qml` shells out to.

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

## Rules

- A new subcommand is a `cmd_<name>` function and a row in the `choices` of
  `build_parser()`, and its help text says what it is for in one line.
- Anything a subcommand can report, `check` should be able to report too - it
  is the command a user is told to run.
- Output goes to stdout, diagnostics to stderr, and the exit status is
  meaningful: non-zero when the thing asked for could not be done.
