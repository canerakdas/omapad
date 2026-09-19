# 70. The arrangement behind a hold, and the axis nobody could reach · ✅ Done · S

Two asks from the same sitting, and both are about the page being the person's
rather than the config's: *hold y ile y yer degistirsin, edit cok daha fazla
kullanisli*, and *kutularin genislik belirlenebiliyor ama yukseklik
belirlenemiyor.*

**The tap arranges and the hold opens the guide**, which is the reverse of
what shipped. The old order had an argument - the guide is what somebody
opening the menu in a hurry wants, and rearranging is something you sit down
to do - and use says otherwise: the guide is a page read once, an arrangement
is one somebody comes back to tile by tile. The guide also has a row of its
own (`Controller > Buttons > Shortcuts`), so of the two it is the one with a
second door, which is what settles which goes behind the longer gesture.

**Both axes, because a cell is a shape rather than a width.** `resize` took
`(wider, taller)` from the day it was written and nothing ever passed anything
but zero to the second: what was missing was two buttons and the argument for
spending them. The old one - a height is a control's own shape, a bar is a bar
and a dial is round - is true of what a control *draws* and not of the cell it
is drawn in. A card of rows with a row too many, a reading you want from
further away, a keyboard tile that wants two rows rather than four: each is a
height somebody can only fix from a text editor. ZL and ZR are shorter and
taller now, `rows_limit` clamps the new axis on the page the HUD draws, and
the legend prints eight rows rather than six.

**A borrowed button has to outrank a layer trigger**, and that is the bug this
found. `surface_override` asked the *config* whether the menu binds a button,
so ZL - the window layer's trigger and the pointer's precision modifier - was
never going to reach the binding `binding_for` was already willing to hand it:
the window layer would have opened silently while the legend said `Shorter`.
It answers "menu" for any button in `EDIT_KEYS` while the mode is on, and the
test presses the trigger through the button path rather than calling the
command, because calling the command is exactly what did not catch it.
