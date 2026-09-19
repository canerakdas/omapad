# 43. The game that only ever saw a keyboard · ✅ Done · S

Reported from the sofa, with 41 and 42 already in: *Steam is fixed, but I open
Palworld and it is still wrong - the right stick opens menus, and inside the
game the pad reads as a keyboard and a mouse.*

**Which is exactly what a pad that was never handed over looks like.** The grab
kept the physical pad from the game's own SDL, so the only pad-shaped thing
reaching it was our virtual keyboard and mouse, and the right stick's `focus`
role was walking the game's controls with Tab. Nothing above the hand-off was
broken; the hand-off never happened.

**Steam's window handed the pad over and the game it started did not**, and the
difference is depth. `wants_pad` asks whether a holder is in the process tree
around the focused window, and that tree was bounded by a count: three, chosen
from `Steam -> reaper -> wrapper -> game`. Measured on this machine, `steam ->
srt-bwrap -> pv-adverb -> steamwebhelper` is *already* three, before a Proton
game adds the reaper and wine's own wrapper. Steam's own window worked because
Steam's window pid is Steam, which holds the pad itself.

**Raising the count was the wrong repair**, and worth writing down as such: the
same number applied to a terminal walks to the compositor, and everything under
the compositor is every window on the screen. A count cannot mean "the same
application" - it means "this far", which is a different thing in every tree.

**The cgroup already meant it.** systemd gives each launched application its
own scope, and everything Steam starts - pressure-vessel, wine, the game -
stays
inside Steam's: measured, one `run-p<pid>-i<id>.scope` holds the lot, while
two terminals sit in two scopes of their own. So the climb is bounded by scope
instead of by a number, and ends exactly where the application ends. `depth`
keeps its other job - how far *down* to look - and is the only bound left on a
machine that gives applications no scope to read.

**What it does not fix, and is not ours:** Steam reads controllers through
`hidraw`, which `EVIOCGRAB` does not cover, so Steam sees the pad whatever the
daemon holds. The overlay opening on the right stick is Steam's own desktop
layout answering a pad it thinks nothing else is using - Settings > Controller,
not a binding here.
