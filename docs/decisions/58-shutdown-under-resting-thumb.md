# 58. A machine that shut down under a resting thumb · ✅ Done · S

§4.3: *hold A to confirm destructive or irreversible actions*. The pad had the
gesture already - an announced hold, with a tick, a notification, a filling
badge and a cancel button - and it was reachable **only from a binding**.
`System ▸ Shutdown` was one press of A, the same press as `Volume`.

So `confirm = true` on a menu row, and deliberately the same gesture rather
than a second one: the two waits are `[confirm]`'s, item 55's scale reaches
them, letting go and the cancel button both back out, and somebody who has held
a shoulder to cross a workspace over a game already knows what a filling shape
means.

- **The tile fills, not a badge.** The bar says which *button* is counting
  down; the tile is the thing being looked at, so the page says which *row* is.
  Clipped to the tile's own ground the way the badge's sweep is clipped to the
  badge's drawing, in over `hold_ms` and back out over `confirm_ms` - empty at
  the moment it runs.
- **The legend says it before anybody presses anything.** While the tile is in
  front, A's word on the foot of the card is `Hold to confirm`. A gesture you
  find out about by making it is a gesture nobody makes on purpose.
- **What earns it is what a second press does not undo**, not what sounds
  serious. Logout, Reboot, Shutdown and Close window; Lock and Suspend stay a
  press, because both are one button away from where you were.
- `build()` refuses it on a page (opening one is not a thing to be sure about),
  on a control (nothing a switch or a slider does is one-way) and beside
  `repeat` (one says *this again*, the other *this at last*).
