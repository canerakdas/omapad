# 98. One backdrop under two menus · 🗑 Removed · S

Asked for from the sofa: *quick menuden menuye gecerken quick menu kapaniyor
sonra menu aciliyor. bu kismen kotu bir goruntu olusturuyor. arka plan
overlayini tutup oyle mi gecis yapsak* - going from the quick menu to the
menu, one closes and then the other opens, and it looks bad; keep the
backdrop and change over on top of it.

**What the problem turned out to be.** The menu and the quick menu are two
layer-shell windows dimming the screen by the same amount (`Color.menu.scrim`
under `[menu] dim`). Opening one shut the other, and the one shutting was
unmapped at once - `visible: root.opened` - while the one opening faded its
scrim in from nothing over `metrics.time.follow`. So HOME from the row, or
PLUS from the menu, went dark, then light for a tenth of a second, then dark
again: the desktop showing through between two screens that meant to be one
place. It read as the thing closing rather than as going somewhere else.

A console does not do this. Moving between two overlays that are siblings -
the PS5's control centre to its home, the Xbox guide's tabs - keeps the
backdrop still and changes only what stands on it, and Material's transitions
say the same for two unrelated containers: the ground stays, the content fades
through. Dismissing one modal and presenting another is the pattern each of
them avoids.

**What was built:** the push that trades the two carries `swap` - on the menu
going and the row coming, and the other way round - and nowhere else, so its
absence on the next heartbeat is what ends it. `set_menu` and `set_quick` pass
it to the sibling they shut and read it for themselves from whether the
sibling was open. `Backdrop.qml` holds the rest, and each panel keeps one:

- **arriving**, the scrim is up at once with no fade - there is a backdrop
  on screen already - and only the content fades in;
- **leaving**, the window stays and its scrim with it until the other
  window is on screen (`partnerDrawn`, each panel's `backingWindowVisible`
  wired to the other in `Surfaces.qml`) and one `follow` more; then the scrim
  fades out and the window goes once it has. The content fades as the scrim
  holds.

**It took three tries, each measured on the machine with bursts of `grim`
frames over the swap, and each failure is a rule now written into the
component.**

1. Holding the leaving scrim for a fixed time, from `onOpenedChanged`. The
   desktop still showed whole for a frame: a binding on `opened` re-runs
   before the handler of the same change, so `visible` went false for an
   instant and Quickshell tore the surface down on the spot. The hold is set
   by `turn(open, swap)`, called before `open` is assigned.
2. The fade flag set in the same handler came a change too late the same way,
   and the arriving scrim faded in from nothing. The Behavior reads the
   panel's own `swap`, which is assigned before `open`.
3. Letting go two frames after the other window reported visible. Still a
   gap: *visible* is the window shown, not its first buffer on the glass. The
   hold runs a whole fade past it and ends in a fade, never a snap - and it
   is never shorter than three frames, so `[ui] motion = 0` keeps it.

The compositor stacks the two in the order the windows were made, not by who
came last, so where the leaving one is on top the arriving page sits under its
scrim for the hold. A scrim lifting slowly off the page reads as the page
arriving; one snapping off read as the flash. Where both scrims are up the
screen is a shade darker, and nobody sees it. None of these waits is a
setting: they are the Wayland hazard rather than a taste.

The quick menu's head, row and legend fade with `opened` now, as the menu's
card always did, so there is something to fade on a hand-over; the row
leaving keeps its head and legend rather than taking the daemon's empty ones.
The menu gives up its keyboard focus and its pointer the moment it is closed,
since a menu handing over stays on screen a moment longer and neither is its
to take by then.

Still true: the menu's card leaves the game bar's strip undimmed while the
quick menu covers it, so on the trade the bar comes back or steps down. The
bar is a separate surface with its own reason to be there, and it moves
either way.

**Rejected:**

- **One shared backdrop window** under both. On `Overlay` its place among the
  other two is the compositor's to decide; on `Top` it is under a fullscreen
  game, which is the case the quick menu exists for.
- **Keeping both windows mapped** and trading only opacity. No map latency to
  wait out - and two fullscreen overlay surfaces over every game for the rest
  of the session, which is what a compositor stops scanning out directly for.
- **Crossfading the two scrims.** Two layers at half their alpha are lighter
  than one at full - `1 - (1 - a/2)²` - so the light breath gets shallower and
  stays.
- **The row growing into the card** (Material's container transform). The
  prettiest, and the menu is a card or the whole screen depending on a
  setting; the cost is two geometries animated across two windows for what a
  still backdrop mostly answers.
- **Fading on every close** in the same pass. A plain close is still a cut,
  and the scrims' fade-out `Behavior` still never plays on one: the window is
  unmapped under it. B going straight back to the game is not what looked
  wrong, and it is a separate change if it ever does.

**Removed by [102](102-a-page-not-a-second-menu.md).** The quick menu became
a page of the menu, so there is one window and nothing to hand over;
`Backdrop.qml` and `swap` went with the second surface. What the three tries
measured - that *visible* is not the first buffer on the glass - is still
true of any two layer-shell windows traded in one place.
