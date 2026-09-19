# 18. Shoulders that are global except where they aren't · ✅ Done (browser pilot) · M

In Chromium — and in anything else built for a pad — L and R are the app's own
tab switcher. Ours took them outright, so inside those apps the app's own
navigation was gone; but they cannot simply be given away either, because
walking workspaces is exactly what you need while a full-screen app is up.

**What landed.** The shipped `[profile.browser]` gives L and R the browser's tab
switcher on a tap and the workspace on a hold. Two seconds in, the pad ticks and
a notification says what is coming and which button stops it; two seconds later
it happens. Letting go backs out, and so does the cancel button (`[confirm]
cancel_button`, B) — which is what makes a tap that ran long harmless. A warned
hold also swallows its own tap on release: you were plainly not asking for a
tab.

Three pieces, each general rather than special-cased: `on_release` on a binding,
so the shoulders fire coming back up and the same button can carry a hold
without its tap having already gone out; `confirm_ms` beside `hold_ms`, which
turns any hold into an announced one; and 17's tick, which is the half of the
announcement that survives a full-screen window or a dark screen — the case the
whole thing exists for.

**Still open.** Steam Big Picture is next and wants the same table with its own
match and its own tap. Two seconds and two seconds were guesses; they are now
`[confirm] hold_ms` and `confirm_ms` (1.2 s and 0.8 s), shorter because the game
bar draws the countdown - the badge fills in from the left over each wait - and
a wait you can watch does not have to be as long as one you cannot. The guide (item 11) knows nothing about profile bindings, so inside the
browser it still prints the base map — that is 10's territory as much as 11's.
And the cheaper alternative is worth remembering: ask once, on screen, the first
time a claiming app takes focus — *this app uses L/R; hand them over?* — a
decision made once per app rather than a gesture repeated. If the hold turns out
to feel like a chore, that is the fallback.
