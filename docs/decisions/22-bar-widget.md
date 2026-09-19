# 22. A bar that knows about the pad · ✅ Done (unverified on screen) · S

Everything omapad draws is summoned and then goes away, which leaves no
standing answer to *is the pad mine?* — the question you ask before pressing
anything. The obvious shapes were a widget in Omarchy's bar or a bar of our
own, and the second is wrong twice over: it would redraw the clock, the
battery and the network to be a bar at all, and it would fight Omarchy's for
the same screen edge.

So: one widget, in the bar that already exists. Omarchy takes third-party
`bar-widget` plugins (`shell.qml:672`), and a plugin already declaring `panel`
can carry one — the exclusion at `shell.qml:429` only decides which loader
answers `summon/hide/toggle`, which omapad does not use. `PadStatus.qml`
extends the host's own `BarWidget` and draws game mode in the bar's urgent
colour rather than one of ours, since the bar has a way of saying *look here*
already. It hides itself when the daemon stops talking: an icon for a service
that is not running is worse than a gap.

The daemon side is a fifth view socket, `status.sock`, carrying mode, whether
a pad is attached, its name and the active profile — pushed on every change
and on the same heartbeat as the rest, so a shell restart repaints it.

**What was rejected:** a per-mode bar *layout*. `shell.json` has no notion of
modes and Omarchy is explicit that the user's file is canonical with no
deep-merge, so switching layouts would mean a program rewriting a hand-edited
config on every mode toggle. Hiding the bar wholesale needs none of that —
`omarchy toggle bar off` parks it off-screen through a flag file the bar
watches, and `[mode] hide_bar_in_game` uses it. It is put back on the way out
*and at shutdown*, because a daemon that dies in game mode would otherwise
leave a desktop with no bar and no clue why.

**Found on the way:** `hide_bar_in_game = true` appended one table too low
landed under `[bindings.game]`, and `omapad check` answered a bool binding
with an `AttributeError` traceback instead of naming the row — the one job it
has. `parse()` now rejects a non-string spec as an `ActionError`.

**And the direction was backwards.** `omarchy toggle bar <action>` is a wrapper
around `omarchy-toggle bar-off <action>`, and the action names the *flag*, not
the bar: `on` creates `bar-off` and hides it, `off` removes it and brings it
back. Written the way it reads, entering game mode showed the bar and returning
to the desktop hid it. The test did not catch it because it asserted the string
the code sent — it pinned the assumption rather than the behaviour — so it now
pins the direction with the reason next to it, and the fix was verified against
the live layer geometry (`0 -26` in game mode, `0 0` on the desktop) rather
than against the test alone.

**Verified on screen** once the session unlocked: the widget sits between
`omarchy.agents` and `omarchy.bluetooth`, and game mode parks the whole bar
off-screen and gives the space back to the windows.

**Still open.** In desktop mode the widget is one icon and nothing else, which
is either exactly right or too quiet to be worth a slot — the payload already
carries the mode, the pad's name and the active profile, so a label costs
nothing but bar width. The mapping screen has still not been *driven*, only
loaded.
