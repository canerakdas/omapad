# 28. Not having to aim: the ring cursor, snap and traversal · ✅ Done · M

The one thing a thumbstick is definitively worse at than a mouse is aiming.
From the couch that is two separate problems: **finding** the pointer and
**taking it somewhere**.

**The pointer.** Game mode switches to an XCursor theme it draws itself — a ring
with a dot in the middle and a dark halo underneath (`cursor.py`). The format is
small enough to be worth writing (a header, a table of contents, premultiplied
ARGB per size), and it needs no xcursorgen dependency. The theme is written
under `~/.local/share/icons` **at daemon startup** rather than at the mode
switch: drawing takes 0.26 s, which would be felt in a mode switch and is not
felt at startup — a config change wants a restart anyway. The switch itself is
one line to the compositor's socket.
Every cursor name in the theme points at the same ring: from the couch an I-beam
is an unreadable smudge too, and one shape that never changes is easier to
follow than the correct shape that keeps changing.

The way back is the desktop's own theme, read **at the moment of the swap**
(`gsettings get org.gnome.desktop.interface cursor-theme`, with `XCURSOR_THEME`
behind it) — not at startup, so that a theme changed while the daemon runs comes
back too. It is done at shutdown as well, so a daemon that dies in game mode
does not leave the desktop with the ring.

**Snap.** `snap:left|right|up|down` teleports the pointer to the middle of the
window that way and focuses it. Measured: `cursorpos` over the socket is
**0.03 ms**, `j/clients` **0.32 ms** — so asking on every press is both cheaper
and more correct than keeping state. `hl.dsp.cursor.move({ x = , y = })` and
`hl.dsp.focus({ window = 'address:0x…' })` were verified live. The choice is
edge-based: the window's *near edge* has to be ahead of the pointer. The first,
centre-based version gave the wrong answer for two windows in the same column —
the lower window's centre sat a few pixels to the right of the pointer, so it
counted as "the window on the right".

**What could not be done: the widget level.** AT-SPI was tested live. Part of it
works — zenity's tree arrived with its roles and the right rectangles, and
`GetAccessibleAtPoint` answered correctly. Three obstacles:

1. `GetExtents(coordType=0 /*screen*/)` returns `x=0, y=0` for every node —
   under Wayland an application does not know its own window position. The
   window-relative coordinate is right, and could be added to `at` from
   `hyprctl clients`.
2. `org.a11y.Status.IsEnabled` and `ScreenReaderEnabled` are both `false`, and
   Chromium/Electron never register on the bus without that flag (GTK ones do —
   zenity did). Games, Steam and terminals under no circumstances.
3. There is no D-Bus in the stdlib. Shelling out to `busctl` (~7 ms per call) or
   ~400 lines of raw D-Bus client — either is a design decision under the "no
   third party" rule.

It was not built because its coverage stops exactly short of what game mode uses
most. If it is reopened: point probing (`GetAccessibleAtPoint`) is far cheaper
than walking the tree, and that is where to start.

**Traversal.** The only thing that knows where a widget is is the application
itself, and every toolkit already answers Tab and the arrow keys correctly.
`focus:next|prev|…` sends the configured key (`[traverse]`) and the application
moves the focus. A stick can be given the `focus` role: not one shot but a
direction that walks while held — the repeat ours rather than the compositor's,
because an application that saw a key held down would run far past where the
finger stopped.

**Where it ended up bound.** A layer was tried first (`[layers.traverse]`,
trigger X) and taken back out: because `layer_for_button` is checked before
every binding, the button that opens the layer has no job of its own in any
layer or any profile. X's cost was not just the duplicate middle click on the
base layer — float/tile in the window layer and `Ctrl+T`/`F5` in
`[profile.browser]` went with it, and neither had a free button to move to.

**A stick instead**: `[mode] right_stick = "focus"`, on by default in game mode.
It spends no button, the wheel on the desktop stays, and the game-mode scrolling
it loses comes back anyway because focus scrolls itself into view. That required
game mode to be able to name its own stick roles; under `[mode]` rather than
`[layers.game]`, because game mode is not held by a button, and a layer without
a button would make the layer's `button` requirement meaningless.
