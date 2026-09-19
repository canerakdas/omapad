# 23. A bar for game mode, and item 10 arriving through the side door · ✅ Done · M

Hiding Omarchy's bar (22) left game mode with nothing on screen at all — no
clock, no workspaces, and no reminder of how to get back out. A second
general-purpose bar was the wrong answer for the reason 22 gives, but the
*gap* was real, and what fills it is not a bar in the desktop sense: every
widget on Omarchy's opens a popup you click, and in game mode there is no
pointer to click with. So this one is a readout. Left: the menu and the button
that opens it. Centre: the workspaces. Right: what the buttons under your
thumbs do.

That right-hand strip is **item 10** — the hint bar — arriving from a
direction the plan did not expect. 10 was blocked on per-app profiles (09)
so it could stop guessing what a keystroke would do; the honest version turned
out to be narrower and better: print what is *actually bound in the layer that
is live*, resolved through exactly the path a press takes, including game
mode's rule that an unbound button reaches the base layer for its `mode:`
action and nothing else. So HOME still says how to leave, and a game layer
that binds nothing says "The pad is the game's" rather than printing a row of
buttons that do nothing. Same for the menu: it appears only once some button
really opens it. `guide._row` became `guide.button_row` so the bar and the
guide cannot describe the same binding differently.

Sized for the couch — 44px against the desktop bar's 26 — and it carries an
exclusion zone like a real bar, so windows sit under it; a full-screen game
covers it, which is the right outcome and needed no special case. Workspaces
come from Hyprland, queried when the bar opens and on create/destroy only: a
plain switch carries the name it switched to, so the common case spawns
nothing, and none of it runs while the bar is down.

The clock lives at the left end of the bar (`[gamebar] clock`, strftime). It
was briefly at the head of the controller menu instead, which was wrong for a
reason worth keeping: a clock is a thing you glance at, and a menu you have to
open first is not a glance.

**Looking like Omarchy took three separate answers, not one.** Colours come
from `Color.bar.*` rather than the menu's tokens. Transparency follows
`bar.transparent` out of `shell.json`, watched live — on this desktop the bar
*is* transparent, so its real background is the wallpaper and matching the
token would have matched nothing. And a transparent bar cannot use the theme's
bar text: Omarchy runs `omarchy-bar-text-color`, which samples the pixels under
the bar and returns whichever of two colours survives them. Asking the same
question, with this bar's own height, is the only way to get the same answer —
the first attempt used the token and produced pale blue on a cream wallpaper.
The workspaces are drawn the way `omarchy.workspaces` draws them, down to the
dot the focused one becomes, and the buttons that step between them sit either
end of the strip rather than in the row of hints: a button drawn beside what it
moves needs no words. A button is never drawn twice.

**Not built, deliberately.** Wi-Fi and weather were asked for in the same
breath and neither is a bar problem. Weather has no source in the daemon —
Omarchy's widget fetches it from wttr.in in the shell — so putting it here
means network I/O in an input daemon, with caching, failures and a location to
own. Wi-Fi needs the menu to hold *dynamic* rows (a scan is not a config file)
and a password path through the on-screen keyboard; that is a feature of its
own, not a row. Both are worth doing and neither should be smuggled in as part
of a bar. **Half of that landed in 40**, which the audio devices asked for: the
menu holds listed rows now, and what Wi-Fi still wants is the password path.

**Found on the way:** the suite swapped only three of the daemon's view
clients for fakes, so the two new ones pushed test payloads into whichever
shell was running on the developer's machine. All of them are swapped in the
base case now.

**And two more, both reported as "game mode is broken":**

Picking a row from the menu closed it and then did nothing. `allowed()` blocked
any action that carried no layer, and a menu row carries none - which was right
while the menu could not be opened in game mode at all, and became wrong the
moment it could. Rows are tagged with the menu now. A menu that closes on a
press and does nothing is indistinguishable from a menu that ignored the press,
which is exactly how it was reported.

The measurement that found it is worth keeping: reading the pad's raw codes in
parallel while the daemon ran (game mode leaves it ungrabbed, so nothing had to
be stopped) and lining the timestamps up against the daemon's own journal.
`0x13b -> PLUS` opened the menu, the D-pad moved, `0x131 -> A` closed it. Every
code was the one the profile expected - so the pad was not the problem, and
three earlier rounds of theorising about a shifted button map had been aimed at
the wrong thing.

**And the first of the two:** item 20 made
`current_layer` return `game` ahead of everything, so a surface opened *from*
the game layer could not be driven - the menu came up on `PLUS` and then
ignored its own D-pad. Three opens and closes in the journal inside twelve
seconds is what that looks like from the outside. Surfaces now outrank game
mode (a held layer still outranks both, as it always did) and `allowed()` lets
their bindings through, because opening one is a decision to look at it rather
than at the game. The first fix put surfaces above held layers too and broke
two older tests that had pinned exactly that order - they were right and it
was wrong.
