# 99. No notification over an open menu · ✅ Done · S

Asked for from the sofa: *menu acikken bazen sag ustten bi notification
penceresi gibi bir pencere gorunuyor bu neden?* - with the menu open, a
window like a notification sometimes shows up at the top right; why?

**What the problem turned out to be.** It was ours. Every setting a row
flips, every lock, keep and mode switch, and both of the menu's announced
waits - the counted row and the held one - called `notify-send`, and the
shell draws that in the corner. The rows that stay open already say the same
thing in the place being looked at: the switch ticks, the setting prints its
value, the count prints its number, the held tile fills. The notification was
the screen answering twice, the second time from across the room.

**What was built:** `daemon.announce()`, which every press-made notification
now goes through. It is silent while the menu or the quick menu is open, and
otherwise does what the four `if self.config.notify:` blocks did. The counted
row, the held row and their `Cancelled` stop notifying at all, because the
menu is on screen for the whole of both by construction - closing it stops
them without a word already.

A row that is not `stay` closes its menu **before** it fires, so the check
sees no menu and the notification still comes; locking from the menu is the
same case by another road, since handing the pad over closes the menu first.
Both are wanted: the tile that would have answered is gone.

**Rejected:** muting notifications for the length of any surface
(`surface_open()`). The guide, the keyboard and the mapping wizard print
nothing about a setting or the lock, so over them the notification is still
the only answer.

**Left alone:** a binding's announced hold (`warn_confirm`) and the pad
connecting. Neither is a row's answer, and a binding has no tile to fill.
