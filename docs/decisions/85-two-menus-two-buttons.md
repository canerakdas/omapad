# 85. Two menus, two buttons · ✅ Done · M

Asked for from the sofa: *mevcut menü xbox butonu ile çalışmalı, bir de düz
menü butonu var ve o menu butonu ile düz arayüzde menü arayüzü yapılmalı ve
açılmalı. Localdeki tasarım dosyalarına olması lazım. Oyunda da mevcut menu ve
select aynı anda basınca açılsın, oradan düz menü gidebilsin.* The menu that
exists belongs on the Xbox button; the plain Menu button (☰) gets a plain menu
of its own, drawn from the design files; and over a game, Menu + Select opens
the existing menu and the plain one is reachable from there.

**A console already splits these two, and for a reason.** The button in the
middle of the pad opens the system's home - a place with everything in it -
and Start pauses whatever is running. omapad had both jobs on PLUS and the
next window on HOME, which was the right trade while there was one menu: the
next window is pressed more often than the mode is switched, and PLUS was the
button nearest a thumb that was not a face button. With two menus, which one
goes where is the console's answer rather than ours: HOME opens the controller
menu, and PLUS the quick menu.

**The quick menu is `Console Overlay`**, the one screen in the Console OS v2
mockups that is not the home: a row of square tiles across the middle, a band
under it for the tile in front, the thing paused over named at the top left,
the machine's readings at the top right, the buttons along the foot. What was
taken from it:

- **One row, walked with left and right, wrapping.** The mockup's own. A row of
  eight is walked end to end often enough that the shoulders walk it too.
- **Up and down turn the value on the tile in front**, also the mockup's - its
  band prints `↑ ↓ ADJUST` beside a bar. That is what `up` and `down` on a tile
  are, in the binding grammar, so a tile reading the volume is
  `live:volume=up` and not a second way of knowing what a volume is.
- **The band.** A tile is a cell and says two words; what A will do to it
  needs a line, and the band is where that line goes - and the bar of a value,
  which a 128-pixel tile has no room to draw legibly.
- **The destructive tile in the alert colour.** The mockup's clay is the
  theme's `urgent` here. And it is pressed twice: the first A says so in the
  band, B lets go of it. Not the menu's held `confirm` - a hold is a gesture
  that needs a badge filling on the tile to be read, and the band already has
  the words to say it outright.

What was not taken, or was taken and then taken back out:

- **The readings at the top right.** Built first - frame rate, temperature,
  load, a clock - and removed on the first look at it on the screen: the row
  is what the screen is for, and a column of numbers in the corner was a
  second thing to read. The HUD is where readings live.
- **A legend of its own.** The first one was drawn on the design's own
  23-pixel ring, larger than the game bar's, in its own corner. The row now
  stands the bar down (`apply_gamebar`) and prints the bar's row in the bar's
  band at the bar's sizes - what a fullscreen menu already does - so the
  buttons do not move or grow when PLUS is pressed.
- **The window's name at the largest rung.** It is a heading over the row,
  not the screen's title, and set at `lead`.

And, from the start: the mockup's palette (every colour is a theme role, as on
every other surface - qml.md 8.1), its `transform: scale` on the focused tile
(the design system itself forbids that; the ring and the halo carry focus, as
in the menu), and `PAUSED` as the kicker - nothing here pauses anything, so it
says which mode the desktop is in instead.

**The tiles that ship** are what a pause is for: Resume first, so PLUS then A
is always back; volume and brightness; a screenshot; the keyboard; the menu;
and closing the window last. HOME's old tap, the next window, was a tile for a
day and came off: it is not something a pause is for, and the menu has the
row under `Workspaces › Windows`.

**A tile that turns a value waits for the value.** Brightness is not something
every machine can set - a desktop monitor without DDC, a machine with no
backlight - and the helper answers those with nothing. Rather than a list of
machines, the tile is left off the row until its `live:` reading has answered
once (`quick_unanswered`), and the read is asked the moment the row opens. The
model hides it by name, so a tile arriving does not move the selection off the
tile somebody is standing on.

**Over a game** nothing about the door changes. PLUS keeps
`reaches_past = false` - it is the game's own pause button - so the MINUS+PLUS
chord still opens the controller menu, and PLUS *inside* the menu goes on to
the row: the menu layer's PLUS was a third way to close the menu and is the
way to the quick menu now. HOME says nothing about reaching past, so both its
halves do: its hold is the mode switch, which has to work over a game, and a
binding has one `reaches_past` for both halves. Its tap therefore opens the
controller menu over a game as well. Where a launcher spends that button on
an overlay of its own, `reaches_past = false` on HOME gives up both halves and
leaves the chord as the only way in - written down in the config beside the
binding rather than decided here.

**PLUS acts on the way down, and holds nothing.** The first version kept the
real Omarchy menu on a 400 ms hold of PLUS, as before, and it was confusing
from the first press: PLUS is half of the MINUS+PLUS chord, so it waited for
its release to find out which it was, and the row only appeared when the
thumb came off - a button that seemed to want holding, with a different menu
waiting a beat further in. So the hold went (the Omarchy menu is a tile under
System) and the binding grew `on_press = true`: act at once, and let the
chord take over if MINUS lands while PLUS is still down - `fire_chord` reads
what is pressed rather than what has fired, and the menu opening closes the
row.

**HOME the same way, found the same way.** "Sometimes it does not work" was
the log showing the mode flipping desktop, game, desktop inside fifteen
seconds: HOME's tap waited for the release because its hold is the mode, so
a press that seemed to have done nothing was held a little longer - and at
700 ms it was the hold. HOME says `on_press` too now. A tap/hold with it fires
the tap on the way down and keeps the hold's clock; when the hold comes due,
a tap that was a `toggle` is pressed again first, so the menu HOME opened is
not left behind the mode switch it was held for.

Rejected:

- **A tile in the menu that opens the row.** Every shipped page comes to whole
  rows (83), and a ninth thing on the `Now` page is a page re-tiled for a
  door PLUS already is. The legend and the guide both print what PLUS does
  inside the menu.
- **Keeping the next window on HOME and the menu on a hold.** A hold is 700 ms
  of waiting for the most-pressed door on the pad, and HOME's hold is already
  the mode.
- **Taking the desk as well, the way the menu does.** The row is pad-only, like
  the guide: it is driven by the thumb that paused, and a click that landed on
  the game behind would be worse than a click that did nothing.
  `omapad ctl quick` drives it without a pad.
