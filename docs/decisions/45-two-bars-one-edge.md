# 45. Two bars along one edge · ✅ Done · S

Reported as a lock that doubled the bar: *workspace lock yapıp tekrar unlock
edince bar çiftleniyor* - both omapad's bar and Omarchy's on screen at once.

**The lock was the messenger.** `hyprctl layers` had `omarchy-bar` at y=1174
and `omapad-gamebar` at y=1134, both on screen, with `toggles/bar-off` gone
while omapad had been in game mode for four minutes. Nothing in the lock's
path touches the bar; what it does is take our bar away and give it back,
which is exactly the moment a second bar becomes visible.

**The real fault is that the desktop bar's state was said once, at the switch,
and never again.** It is a *file* - `omarchy toggle bar` creates and removes
`~/.local/state/omarchy/toggles/bar-off` - so anything may flip it, and
Omarchy's own bar carries a comment saying its watch on that directory can
stop delivering events when changes land together. A daemon that hears none of
that goes on believing what it said minutes ago.

So `set_gamebar()` says it again every time ours opens. The command names the
flag rather than toggling it, so a repeat costs one spawn and changes nothing
when nothing has changed - and it lands exactly where the doubling would be
seen. Measured on this machine: flag deleted by hand, both bars on screen,
then one lock and unlock and `omarchy-bar` is back at y=1200 with the flag
restored.

`Daemon.start()` came out of the same reading. `[mode] start = "game"` has no
switch to hang any of this off, and `run()` was already calling `apply_cursor`
for that reason and nothing else - so a session that started in game mode
opened our bar under the desktop's and stayed that way until the first switch.
