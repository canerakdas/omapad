"""Point the cursor at the window next door.

Aiming a pointer with a thumbstick is the one thing a pad is worse at than a
mouse, and from the couch it is worse again. The console answer is to stop
aiming: press a direction and the focus jumps to whatever is over there.

What "whatever" can be is the whole question. Widget-level targets would need
the accessibility bus, which under Wayland reports every widget at screen
0,0 and which browsers, games and terminals do not join at all. Windows have
no such problem: Hyprland already knows exactly where each one is, on which
workspace, at what size. So this snaps between windows, which is the layer
omapad can be right about, and leaves aiming inside a window to the stick.

Geometry only - the caller does the talking to Hyprland, so the choice can be
tested against a canned window list.
"""

# Directions as (dx, dy) on screen coordinates: y grows downwards.
DIRECTIONS = {
    "left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1),
}

# What a window off to the side costs against one straight ahead by default,
# both
# measured edge to edge. Below 1 the nearest window wins whatever direction was
# pressed, which makes the press meaningless; far above it only a window
# perfectly in line is ever reachable. Two lets a clearly-nearer neighbour win a
# slightly crooked press without letting the press be ignored.
PERPENDICULAR_WEIGHT = 2.0


def rect(window):
    """(x0, y0, x1, y1) of a window as hyprctl reports it, or None.

    `at` and `size` are in logical pixels - the same space as `cursorpos` -
    so nothing here has to know about monitor scale.
    """
    at = window.get("at")
    size = window.get("size")
    if not isinstance(at, (list, tuple)) or not isinstance(size, (list, tuple)):
        return None
    if len(at) < 2 or len(size) < 2:
        return None
    try:
        x, y = float(at[0]), float(at[1])
        width, height = float(size[0]), float(size[1])
    except (TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    return (x, y, x + width, y + height)


def centre(window):
    box = rect(window)
    if box is None:
        return None
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)


def visible_workspaces(monitors):
    """The workspace ids on screen right now, one per monitor.

    A special workspace - a scratchpad pulled down over the others - counts
    too: it is on screen, so it is a window a flick can reach.
    """
    ids = set()
    for monitor in monitors or ():
        if not isinstance(monitor, dict):
            continue
        for key in ("activeWorkspace", "specialWorkspace"):
            workspace = monitor.get(key)
            if isinstance(workspace, dict) and workspace.get("id") is not None:
                ids.add(workspace["id"])
    # An id of 0 is Hyprland's "no special workspace here".
    ids.discard(0)
    return ids


def monitor_at(monitors, x, y):
    """Which monitor's id the point is on, or None.

    `x`/`y` on a monitor are already logical; `width`/`height` are the panel's
    own pixels, so they are the one pair that has to be divided by the scale.
    """
    for monitor in monitors or ():
        if not isinstance(monitor, dict):
            continue
        try:
            left, top = float(monitor["x"]), float(monitor["y"])
            scale = float(monitor.get("scale") or 1.0) or 1.0
            width = float(monitor["width"]) / scale
            height = float(monitor["height"]) / scale
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            continue
        if left <= x < left + width and top <= y < top + height:
            return monitor.get("id")
    return None


def candidates(clients, monitors, monitor=None):
    """The windows a snap may land on.

    Anything not mapped, hidden behind a fullscreen sibling or parked on a
    workspace nobody is looking at would be a jump into the dark.
    """
    workspaces = visible_workspaces(monitors)
    windows = []
    for window in clients or ():
        if not isinstance(window, dict):
            continue
        if not window.get("mapped", True) or window.get("hidden", False):
            continue
        workspace = window.get("workspace")
        if not isinstance(workspace, dict):
            continue
        if workspaces and workspace.get("id") not in workspaces:
            continue
        if monitor is not None and window.get("monitor") != monitor:
            continue
        if rect(window) is None:
            continue
        windows.append(window)
    return windows


def under(windows, x, y):
    """The window the pointer is already in, if any.

    Last one wins: hyprctl lists windows bottom-first, so with a float sitting
    over a tile the float is the one the pointer is actually on.
    """
    found = None
    for window in windows:
        box = rect(window)
        if box[0] <= x <= box[2] and box[1] <= y <= box[3]:
            found = window
    return found


def choose(windows, x, y, direction, bias=PERPENDICULAR_WEIGHT):
    """The window a flick in `direction` should land on, or None.

    Scored the way spatial navigation everywhere is scored: how far ahead the
    window is, plus `bias` times what it costs to be off to one side - and
    being off to one side costs nothing at all when the pointer already lies
    within the window's span across the press, which is what makes a column of
    tiles walk cleanly.

    "Ahead" is the window's near *edge*, not its centre. Two windows stacked in
    the same column share a centre x, so a centre test makes the one below
    count as being to the right of a pointer a few pixels left of it, and a
    press meant for the next column walks downwards instead.
    """
    step = DIRECTIONS.get(direction)
    if step is None:
        return None
    here = under(windows, x, y)
    horizontal = step[0] != 0
    forwards = (step[0] if horizontal else step[1]) > 0

    best = None
    best_score = None
    for window in windows:
        if window is here:
            continue
        box = rect(window)
        if horizontal:
            along = box[0] - x if forwards else x - box[2]
            low, high, at = box[1], box[3], y
        else:
            along = box[1] - y if forwards else y - box[3]
            low, high, at = box[0], box[2], x
        if along <= 0:
            continue
        perpendicular = 0.0 if low <= at <= high else min(
            abs(at - low), abs(at - high)
        )
        score = along + bias * perpendicular
        if best_score is None or score < best_score:
            best, best_score = window, score
    return best
