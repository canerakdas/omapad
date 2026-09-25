# Tests - `tests/`

```bash
python3 -m unittest discover -s tests -v
```

No hardware, no `/dev/uinput`, no compositor, no shell. That is a design
constraint on the code, not a property of the tests: **new code is written so
it can be tested that way.**

## How it works

Synthetic evdev events are fed into `Daemon`, and the uinput layer is replaced
by recorders - fakes that write down what would have been typed, clicked or
scrolled. Everything below the uinput write is exercised: profiles, layers,
analog triggers, tap/hold, pointer integration, game mode.

The same trick everywhere else: a module that would talk to the outside takes
the outside as an argument.

| Module | Testable because |
|---|---|
| `snap.py` | it is geometry over a canned window list; the caller talks to Hyprland |
| `handover.py` | every function takes `proc=PROC`, so it walks a fake `/proc` |
| `gamebar.py` | `view_state` takes a `resolve` callback instead of reading the config |
| `menu.py`, `guide.py`, `osk.py`, `mapping.py` | the models return a payload dict; nothing touches a socket |
| `cursor.py` | `render`/`encode` are pure; only `install` touches the disk |

## The files

| Test | Covers |
|---|---|
| `test_daemon.py` | the loop, end to end through the recorders (the largest file in the project after `daemon.py`) |
| `test_osk.py`, `test_menu.py`, `test_guide.py`, `test_gamebar.py`, `test_mapping.py` | the surface models and their payloads |
| `test_settings.py` | what the controller menu may change, and its ranges |
| `test_device.py`, `test_kbd.py`, `test_rumble.py` | device discovery, keyboard selection, force feedback |
| `test_handover.py` | the `/proc` walk, against a fake tree |
| `test_snap.py` | which window is next door |
| `test_cursor.py` | the drawn pointer and the XCursor it encodes |
| `test_assets.py` | that every badge the daemon can send has art, and that the checked-in generated files still match the generator |
| `test_viewsock.py` | what `drawable` lets through, for the strings a device names itself with |
| `test_unit.py` | installing the user unit: which checkout paths can be baked into it, a symlink or a directory sitting at the destination, and a write interrupted before the rename |
| `test_packaging.py`, `test_shell_plugin.py` | what a release and the plugin look like with nothing running: the version, the boot pin, the udev rule the installer writes from its own bytes, and that every `Text` says `textFormat: Text.PlainText` |
| `test_cli.py` | what `omapad budget` reads out of `/proc`, the price it puts on the shipped menu, that `budget stress` sends nothing that runs a row or moves a value, and that `ShellWatch` times a shell that stops reading |

## What costs something is tested as a count, never as a clock

A loop that runs for as long as the desktop is up has a second kind of
correctness: not *what does it do* but *how often does it do it*. Both
regressions found in the daemon's idle cost were of that kind, and both were
exact numbers rather than slow ones:

| Regression | As a clock | As a count |
|---|---|---|
| a window renaming itself read as a focus change | "~5 ms a second" | **37 walks of `/proc`, one was owed** |
| `wants_pad` asking every opener before narrowing | "4 ms an ask" | **276 processes read, 4 were the question** |

So the rule is: **assert the count, never the duration or the resident size.**
A count is exact, needs no hardware and no clock, and says which line is
wrong. `assertLess(elapsed, 0.005)` fails when a browser is open, and a test
that fails for a reason nobody caused is a test somebody deletes. Resident
size is worse again - it moves with the allocator, the interpreter and the
arena.

What that looks like in practice, and where each one lives:

| What is held to a number | Where |
|---|---|
| one command per `meta` per `ttl`, however many ticks went past | `MetaRefreshTests` |
| the same for a head cell's lines | `HeadRefreshTests` |
| no reading asked for that no surface is drawing | `SysRefreshBudgetTests` |
| one walk of `/proc` per *window*, not per title | `HandoverTests` |
| the descriptors read only inside the focused tree | `WantsPadTests` |
| one gauge frame per `live_hz`, and none at all when nothing moved | `GaugeTests` |

The half a count cannot answer - whether the number is *affordable* on this
machine, with this config - is [`omapad budget`](cli.md), which measures and
never asserts. Add a row to one when you add a row to the other.

## Rules

- One test module per daemon module, named `test_<module>.py`.
- A new surface gets its model tested through `view_state`, and its payload
  keys asserted - they are a contract with the plugin.
- A new badge kind, a new label in `guide.LAYOUTS`, a redrawn shape: re-run
  `python3 assets/generate.py`, or `test_assets.py` fails.
- No test may need a running daemon, a real pad or the shell.
- Anything the loop does on a timer is held to a count, in the test module of
  the component that does it - never in a file of its own, and never with a
  stopwatch.
