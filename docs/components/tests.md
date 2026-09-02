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

## Rules

- One test module per daemon module, named `test_<module>.py`.
- A new surface gets its model tested through `view_state`, and its payload
  keys asserted - they are a contract with the plugin.
- A new badge kind, a new label in `guide.LAYOUTS`, a redrawn shape: re-run
  `python3 assets/generate.py`, or `test_assets.py` fails.
- No test may need a running daemon, a real pad or the shell.
