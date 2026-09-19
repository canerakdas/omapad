# 75. The clock that could measure, and the pusher it had room for · ✅ Done · M

Asked for from the sofa, one message after the clock landed: *kronograf olsun
now ekranda gorunsun, islevsel olsun tuslar kronograf tusu gibi davransin* -
and then, looking at the first one: *panda dial gibi yapamaz miyiz, 3 kadranli
fiziksel kol saati gibi.*

**A second control rather than an option on the clock**, and the reason is the
HUD. A clock may be drawn over a game because there is nothing on it to reach
for; a chronograph has a pusher, and a pusher over a game is a control with no
way to reach it. That is one rule with two answers rather than a flag, so
`clock` stayed exactly what it was and `chrono` is a name of its own.

**One pusher, and it is A.** The face-button contract leaves a tile one
button: B leaves the surface and X closes it in every layer, so a second
pusher would have to be taken out of the contract and spent on a stopwatch.
What A does is the monopusher cycle - start, stop, reset, round again - which
is what a chronograph was before it had two pushers, and the legend under the
card prints which of the three the next press is, exactly where it already
prints `Hold to confirm`. What the cycle costs is resuming, on the wrist as
here; what it buys is that nothing in the contract had to move.

**The state is the daemon's and the motion is the panel's.** `chrono.py` holds
one stopwatch - a measurement is a thing in the room rather than a property of
a cell, so every tile that draws one draws that one - and sends how long it had
measured and whether it is still going. A sweep hand re-sent twice a second is
a stopwatch that jumps, so `Clock.qml` stamps its own clock when a payload
lands and counts on from there, re-syncing on every push. It is the one drawing
on these surfaces that animates itself and the one that spells its own figures,
and both have the same cause: a number that changes ten times a second cannot
come off a wire written twice a second.

**The registers took three passes and the last one was the ask.** One counter
at six o'clock, drawn as four dots, read as four more hour marks among the
twelve already there - which is exactly what it looked like. Sinking it into a
disc of ground fixed the legibility and the sofa named what it had been
reaching for: a panda dial. So there are three, where a three-register
chronograph has them - running seconds at nine, minutes measured at three,
hours at six - and **what says a register is a register is the ground rather
than anything drawn on it**: marks inside a disc fifteen pixels across are
two-pixel dots. The contrast is the theme's, a step off the dial in whichever
direction that theme runs, so it reads as a panda on a dark one and a reverse
panda on a light one without the plugin naming a colour.

**And then the sofa asked what it cost, which found the real bug.** The tile
measured 14.4% of a core against 1.1% for the same page without it - and it
measured the same with its animation *hard disabled*, which is what said the
timer was innocent. What was not innocent was `sc`: a number that differs on
every payload, carried inside `items`, makes the whole model differ on every
payload, and `fresh()` then rebuilds every delegate on the page twice a second
to move one hand. `menu_gauge` had written that warning down for the thumb dot
years earlier - *carrying it with the rest of the surface would rebuild every
tile on the page to move one dot* - and this walked into it anyway.

So the stopwatch came off the tile and onto the surface, beside `hd` and
`count`: **2.0% idle, 2.4% measuring, and 1.3% with the menu closed**, which is
what a closed menu costs anyway. The face also redraws four times a second
while it is idle rather than twenty, because the only thing moving then is the
seconds hand of a register fifteen pixels across. qml.md 5.4 has the rule from
this side now; it had only ever had it from the panel's.

Which also took the last of the generated art out of it: three discs and four
hands all answer to a number, so `chrono-counter.svg` was drawn, generated,
looked at and deleted. `EveryControlIsDrawn` lists the kind with the clock's
three parts and nothing of its own, the way `slider` and `readout` are listed
with none.

**And then it struck the minute.** Asked from the sofa once it had been lived
with: *chrono her 1dkda dolunca kolu titretsin.* A stopwatch on a pad can do
the one thing a stopwatch on a wall cannot - say something to a hand that is
not looking at it - and that is most of what one left running while you do
something else is worth. `Chrono.strike()` says, once per turn of the sweep
hand, that it has come back to twelve; `daemon.check_chrono` answers with
`rumble`'s tick, on the loop's own heartbeat rather than the menu's, because
the measurement outlives the page it was started on and an app holding the pad
does not own the stopwatch either. The mark is the hand coming round rather
than a length anybody set - a strike at ninety seconds lands with the hand at
six, saying nothing you could read off the face - so `[chrono] rumble` is a
switch with no number beside it. An alarm you set is a different instrument,
and it would want a face saying what it is counting to before it wanted a
motor.
