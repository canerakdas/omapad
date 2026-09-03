---
name: pad-diagnose
description: Diagnose omapad at runtime - a pad that does nothing, a button doing the wrong thing, a surface that will not draw, a pointer that drifts, a pad that will not hand over to a game, or a binding that silently does nothing. Use when something works in the tests but not on the machine. Walks the diagnostic ladder in order instead of guessing.
---

# Diagnosing a live pad

Almost everything here fails **silently** - the daemon is built so that no
compositor, no plugin, no control socket and no pad each cost a log line
rather than a crash. So the method is a ladder, not a guess: find the lowest
rung that is wrong, because everything above it will lie.

```bash
./bin/omapad check                     # config + which pad + which profile
./bin/omapad ctl status                # what the running daemon thinks
journalctl --user -u omapad -f         # the daemon's own account
./bin/omapad dump                      # raw evdev codes as you press
qs -p /usr/share/omarchy/shell log     # the plugin's, and the only place its errors appear
```

**After any code or config change: `systemctl --user restart omapad`.** More
"it did not work" than anything else on this list is a daemon still running
the old file.

## The ladder

### 1. Is the config even loading?

`./bin/omapad check`. Everything that can be wrong is validated at load, so
this is where a bad binding, a bad menu row or an out-of-range setting is
named - `ConfigError`, `ActionError`, `MenuError`, `OverrideError`,
`KeyParseError`. It also prints the pad it found, the profile it picked and
the badge layout that follows.

Remember the merge order when a value is not what the file says:
`config/config.toml` → `~/.config/omapad/config.toml` →
`mapping.toml` → `settings.toml`, **last wins**. A setting changed from the
controller menu months ago is in `settings.toml` and outranks what you just
typed. `check` prints what is in there for exactly this reason.

### 2. Is the daemon getting the buttons?

`./bin/omapad dump` prints raw codes as you press. If nothing arrives, it is
permissions or the device filter, not bindings.

- `no permission on /dev/uinput` → run `./install.sh`, then **log out and back
  in**: `input` group membership only takes effect in a new session.
- The pad is there but named oddly → the profile was picked from the device
  identity, and pads lie. See §5.

### 3. Is the *right* button arriving?

**Logical button names follow the pad's own printed labels, so `A` is a
different physical button in NS mode than in XInput mode.** A pad answering to
its neighbour's name is the classic symptom: every binding fires, but one
button over.

`dump` says which code arrives; the mapping wizard (`omapad ctl map toggle`)
asks for each button by name, writes down the code, and saves it per device
identity in `~/.config/omapad/mapping.toml`. **Delete that file** to put every
pad back on its shipped profile.

### 4. Is the binding resolving to what you think?

`omapad ctl status` prints the live layer, the mode, and the active app
profile. Then read the scheme back in words rather than pressing buttons:

```bash
./bin/omapad ctl guide toggle
```

The guide prints what is **actually bound in the layer that is live**, through
exactly the path a press takes. If the guide disagrees with the config file,
the resolution order is the answer: **profile → layer → base**, with a surface
on screen outranking everything. Two more traps:

- A **layer trigger has no binding of its own** in any layer or profile. `ZL`
  holds the window layer, so `ZL` cannot also do something.
- A **profile stops at a held layer**: an app binding `X` still leaves `ZL` +
  `X` alone, so a window op behaving normally under an app is not the bug.
  Only `[profile.<app>.window]` changes that, and nothing ships with one.

### 5. Is it the pad's identity?

Pads change identity with their hardware mode - the Beitong KP20 is
`057E:2009` in NS mode and `20BC:5127` in XInput, with different button
numbering and analog vs digital triggers. `check` prints which one it decided.
`[device] profile` forces it; `[device] layout` forces what the badges
*print*, which is a separate question.

### 6. Is a surface not drawing?

Split it: does the daemon think it is open, and is the plugin alive?

```bash
omapad ctl status                          # osk=open menu=closed ...
omarchy-plugin-list | grep omapad          # enabled?
ls $XDG_RUNTIME_DIR/omapad/                # the sockets
```

- Plugin not `enabled` → `omarchy-plugin-enable canerakdas.omapad`.
- Daemon says open, nothing on screen → it is the panel. See the three silent
  QML failures in the `pad-surface` skill; the shell log is the only place the
  real error appears.
- It drew once and then went away → the daemon stopped talking. State is
  re-sent every 2 s and the panel takes itself down when the heartbeat stops.

### 7. Is the pad the game's?

By design: the daemon lets go when the focused window's process tree has the
pad open, and takes it back when it stops. `omapad ctl status` says
`pad=app` or `pad=ours`.

- Pad does not show up in a game → you are in desktop mode and it is grabbed
  exclusively. Hold HOME, or set `[mode] grab = false`.
- A Proton game leaves the pointer driving the desktop over the top → the
  opener is `winedevice.exe`, a **sibling** of the game rather than its child.
  `[mode] handover_siblings` must be on.
- Steam holds every input device open all evening, focused or not, and reads
  controllers through `hidraw` rather than the event node - which is why the
  question is asked about the window in front, not about the machine.
- Nothing answers over a game → that is correct. Only a summon, an announced
  hold (`confirm = true`) and the `MINUS+PLUS` chord reach past an app holding
  the pad.

### 8. Is it Hyprland's fault?

- `hypr:` bindings are **Lua**: `hl.dsp.focus({ workspace = 'e+1' })`. The old
  `workspace e+1` form is dead. Try the expression by hand:
  `hyprctl dispatch "hl.dsp...."`, and check
  `/usr/share/hypr/stubs/hl.meta.lua` for valid dispatchers.
- `omarchy toggle bar on|off` names the **`bar-off` flag**, not the bar: `on`
  hides the bar.
- **LB/RB skipping workspaces is a monitor-assignment fault, not a bug here.**
  `r±1` walks the monitor's own workspace range; a workspace stranded on
  another monitor is skipped because it is not in this monitor's range.

## Known-good symptoms with surprising causes

| Symptom | Cause |
|---|---|
| Pointer drifts into a corner untouched | the pad lies about where its sticks rest. `recenter` calibrates at connect; holding a stick while it connects skips that axis. `dump` shows the raw values |
| Pointer drifts a little | not enough dead zone on that stick - raise `[pointer] left_deadzone` (or `right_deadzone`) 0.10 → 0.15, or step it from Controller > Dead zone with the pointer live under the menu |
| Steam presses keys at startup | a virtual keyboard declaring `BTN_*` gets a `js*` node and Steam reads it as a ghost pad. Ours declares none - check with `grep -A5 "omapad virtual keyboard" /proc/bus/input/devices`, there must be **no `js`** on `Handlers`. If it persists it is Steam seeing the real pad through `js0`: Settings → Controller → Desktop layout |
| The screensaver interrupts a surface | pad activity produces no Wayland input at all, so the idle timer runs. The keyboard holds an `IdleInhibitor`; anything else does not |
| A badge prints typed text | the label has no art - see the `pad-badge-art` skill |

## What not to do

- Do not run `./install.sh` while diagnosing: it uses `sudo`, writes udev
  rules and touches the user's systemd units. `boot.sh` `exec`s it, so the
  same applies. Test either against a local clone with `OMAPAD_REPO` /
  `OMAPAD_DIR`.
- Do not add a `Timer` or a poll to a panel to find something out. If the
  panel needs to know, the daemon sends it.
