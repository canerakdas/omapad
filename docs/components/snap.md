# Snap - `omapad/snap.py`

Point the cursor at the window next door.

Aiming a pointer with a thumbstick is the one thing a pad is worse at than a
mouse, and from the couch it is worse again. The console answer is to stop
aiming: press a direction, and focus jumps to whatever is over there.

**Why windows and not widgets:** widget-level targets would need the
accessibility bus, which under Wayland reports every widget at screen 0,0 and
which browsers, games and terminals do not join at all. Hyprland already knows
exactly where each window is, on which workspace, at what size. So this snaps
between windows - the layer omapad can be right about - and leaves aiming
inside a window to the stick.

## Surface

Geometry only. The caller does the talking to Hyprland, so every choice can be
tested against a canned window list.

| Function | Does |
|---|---|
| `rect(window)`, `centre(window)` | a window's box in logical pixels - the same space as `cursorpos`, so nothing here knows about monitor scale |
| `visible_workspaces(monitors)`, `monitor_at(monitors, x, y)` | which windows are on screen at all |
| `candidates(clients, monitors, monitor)` | the windows a jump may land on |
| `under(windows, x, y)` | what the pointer is over now |
| `choose(windows, x, y, direction, bias)` | the answer |

`DIRECTIONS` is `(dx, dy)` in screen coordinates - y grows downwards.

## The one number

`PERPENDICULAR_WEIGHT` (default 2.0, `[snap] bias`) is what a window off to
the side costs against one straight ahead, edge to edge. Below 1 the nearest
window wins whatever direction was pressed, which makes the press meaningless;
far above it, only a perfectly aligned window is ever reachable.

Related settings: `[snap] flick`, `release`, `focus`, `rumble`,
`same_monitor`.
