# Components

One document per component. A component is the unit that owns a decision: a
daemon module, plus the panel that draws it where there is one, plus the
socket between them.

## The daemon

| Component | Files | What it owns |
|---|---|---|
| [Event loop](daemon.md) | `omapad/daemon.py` | The one loop. Layers, chords, tap/hold, repeats, sticks, mode, grab, and every surface's lifetime. |
| [Configuration](config.md) | `omapad/config.py`, `config/config.toml` | The merge, the profiles, the validation, the settings written from the pad. |
| [Actions](actions.md) | `omapad/actions.py` | The action grammar, the Hyprland socket, spawning commands. |
| [CLI](cli.md) | `omapad/__main__.py`, `bin/omapad` | `run`, `dump`, `check`, `ctl`. |
| [Control socket](control.md) | `omapad/control.py` | Driving the daemon without the pad. |
| [View socket](viewsock.md) | `omapad/viewsock.py` | Line-delimited JSON to the plugin, best-effort. |
| [Socket directory](paths.md) | `omapad/paths.py` | Where the sockets live, and refusing one that is not private. |

## Talking to the hardware

| Component | Files | What it owns |
|---|---|---|
| [evdev](linux-input.md) | `omapad/linux_input.py` | The ioctls, device discovery, `EVIOCGRAB`. |
| [uinput](uinput.md) | `omapad/uinput.py` | The virtual mouse and keyboard. |
| [Keymap](keymap.md) | `omapad/keymap.py` | Key name → Linux keycode. |
| [Real keyboards](kbd.md) | `omapad/kbd.py` | The way out of a surface when the pad cannot answer. |
| [Rumble](rumble.md) | `omapad/rumble.py` | One uploaded effect, best-effort. |
| [Handover](handover.md) | `omapad/handover.py` | Whether the app in front has the pad open. |

## Talking to the desktop

| Component | Files | What it owns |
|---|---|---|
| [XKB labels](xkb.md) | `omapad/xkb.py` | What the keys are printed with, read back from the compositor. |
| [Snap](snap.md) | `omapad/snap.py` | Which window is next door, as geometry. |
| [Cursor](cursor.md) | `omapad/cursor.py` | A pointer you can find from a sofa, drawn into an XCursor theme. |

## The surfaces

Each is a model in the daemon, a socket, and a panel that only draws.

| Component | Daemon | Panel | Socket |
|---|---|---|---|
| [On-screen keyboard](osk.md) | `osk.py` | `Keyboard.qml` | `osk.sock` |
| [Menu](menu.md) | `menu.py` | `Menu.qml` | `menu.sock` |
| [Bindings guide](guide.md) | `guide.py` | `Guide.qml` | `guide.sock` |
| [Game bar](gamebar.md) | `gamebar.py` | `GameBar.qml` | `gamebar.sock` |
| [Mapping wizard](mapping.md) | `mapping.py` | `Mapping.qml` | `mapping.sock` |
| [Click burst](ripple.md) | `ripple.py` | `Ripple.qml` | `ripple.sock` |
| [Bar widget](status.md) | `daemon.status_state()` | `PadStatus.qml` | `status.sock` |

## Everything else

| Component | Files | What it owns |
|---|---|---|
| [Shell plugin](shell-plugin.md) | `shell-plugin/`, `manifest.json` | The plugin itself: entry points, shared pieces, hot reload. |
| [Button art](assets.md) | `assets/` | The drawn buttons and the generator that turns them into badges. |
| [Packaging](packaging.md) | `boot.sh`, `install.sh`, `systemd/`, `udev/`, `bin/` | Fetching, permissions, the user unit, running from the checkout. |
| [Tests](tests.md) | `tests/` | Synthetic events into fake recorders; no hardware. |
