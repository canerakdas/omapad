# 08. A menu instead of a keyboard shortcut · ✅ Done · M

Config-driven entries summoned by one button — **PLUS** taps it open, and
holding PLUS still reaches the real Omarchy menu, which wants a keyboard.

**Shipped as a list, not a radial.** The original write-up wanted a radial
picked by stick angle. A radial reads one flick well, but it caps out at a
handful of entries, has nowhere to put a submenu, and is a shape the desktop
teaches nowhere else. So the menu is shaped like the Omarchy menu instead:
centred card, a title line, one column of rows, `›` where a row drills in — the
same measurements and theme tokens, so the two read as one family. A D-pad
walks a list predictably, which is the same argument that shaped the keyboard's
grid (item 06).

**What shipped:**

- `omapad/menu.py` — the tree, the selection and the drill-down stack, with
  the position you left restored when you climb back out.
- `[[menu.items]]` in the config: `label`, `icon`, optional `detail`, and
  either an `action` from the ordinary binding grammar or an `items` submenu.
  Actions are parsed at build time, so a typo fails `omapad check`.
- `repeat = true` on a row you *nudge* rather than *pick* — volume, brightness.
  The menu stays put and a held button keeps firing, the way Omarchy's own
  volume keybind repeats `omarchy-audio-output-volume raise`. Every other row
  closes the menu on pick, and no ordinary row repeats under a resting thumb.
- Default tree, grouped so the root stays short and the couch-frequent rows sit
  nearest the opening selection: Apps (Steam · Browser · Terminal · All apps) ·
  Keyboard · Windows · Audio · Display · Game mode · Controller · System ·
  Omarchy menu — including the media rows item 07 parked.
- `[bindings.menu]`, an implicit layer like the keyboard's, that outranks it:
  opening the menu closes the keyboard so only one surface reads the D-pad.
- `shell-plugin/Menu.qml`, drawn from a second socket. The plugin's entry point
  is now `Panel.qml`, which mounts the keyboard and the menu together — a
  plugin gets one `panel` entry point, and two sockets do not need two plugins.
- `omapad ctl menu <toggle|open|close|up|down|press|back>`.

**Left out on purpose:** stick navigation. The sticks keep their base roles
while the menu is up, the way they do under the keyboard, so the pointer never
dies under you. Turning stick deflection into discrete row steps is a separate
mechanism and the D-pad already does the job.

*(Taken back in item 50.* It was right while every row was a verb in one
column. A grid of tiles that hold values is a different thing for a thumb to
be doing, so the left stick walks the tiles and the right one keeps the
pointer - and the promise above is kept by the thumb that was aiming with it
anyway.)*

**Since:** the menu also takes the keyboard and the mouse while it is open -
ther Omarchy menu's own focus rules - so the arrows,Enter and Esc drive it
over the same control socket the pad uses, and a cursor hovers, clicks and
dismisses the same way. Esc now leaves outright from any depth (strictly
closing,where it used to climb back level by level on the desk keyboard),and
clicking the scrim closes the menu,so the pointer is not handed through to
the window under it while the menu is up.
