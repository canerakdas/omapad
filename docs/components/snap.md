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

## Two callers, one rule

`choose()` answers "which rectangle is that way from here?", and a window is
not the only thing that is a rectangle. The menu's grid asks it about **tiles
in cells** ([`menu.md`](menu.md)), so the pad walks a page of tiles by the same
rule it walks a desktop of windows rather than by two that can disagree. The
menu passes `[menu] bias` rather than this one's: windows are large and sparse,
tiles are small and touching, and the number was measured on windows.

## Surface

Geometry only. The caller does the talking to Hyprland, so every choice can be
tested against a canned window list.

| Function | Does |
|---|---|
| `rect(window)`, `centre(window)` | a window's box in logical pixels - the same space as `cursorpos`, so nothing here knows about monitor scale |
| `visible_workspaces(monitors)`, `monitor_at(monitors, x, y)` | which windows are on screen at all |
| `candidates(clients, monitors, monitor)` | the windows a jump may land on |
| `under(windows, x, y)` | what the pointer is over now |
| `beside(one, other, horizontal)` | whether two rectangles share the band a press walks along |
| `choose(windows, x, y, direction, bias)` | the answer |

`DIRECTIONS` is `(dx, dy)` in screen coordinates - y grows downwards.

## What counts as that way

Two gates, then the score.

**A candidate has to be past the edge the press pushed against** - the near
edge of the window the pointer is *in*, not the pointer. A point in the middle
of a wide window has half that window's neighbours behind it, so measuring from
the point makes anything overlapping what you are standing on count as being
beside it: the tile one row up and a column to the left has a right edge left
of your centre, and a press of left walked up. Nothing overlapping the
rectangle you are on is that way from it, whatever the bias makes of the
distance. With nothing under the pointer there is no edge, and the point is the
whole of the answer.

**What is past the edge is still scored**, so a window that is genuinely over
there but not squarely so is still reachable. The gate answers *whether*, the
bias answers *which*.

**Whether that is enough depends on the caller**, which is what `beside` is
for. A desktop is sparse: a window with nothing beside it is one a flick still
has to reach, so `choose` is handed every window and the bias decides. A menu
page is packed: something is beside every tile, so the menu hands `choose`
only the tiles that are, and a press into a hole moves nothing rather than
crossing the page. Same function, same rule - the caller says which rectangles
are in the running. See [`menu.md`](menu.md).

## The one number

`PERPENDICULAR_WEIGHT` (default 2.0, `[snap] bias`) is what a window off to
the side costs against one straight ahead, edge to edge. Below 1 the nearest
window wins whatever direction was pressed, which makes the press meaningless;
far above it, only a perfectly aligned window is ever reachable.

Related settings: `[snap] flick`, `release`, `focus`, `rumble`,
`same_monitor`.
