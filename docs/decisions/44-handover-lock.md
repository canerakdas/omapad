# 44. The lock, for the game /proc argues about · ✅ Done · S

Asked from the sofa with 43 in: *give me a way to say "this is a game, leave
it alone", from inside the game, and a row in the menu to take it back.*

**The hand-off is a question about a program and it is right about the games
it can see.** What is left over is two things, and both are the same shape: a
person can see something `/proc` cannot.

A game the walk misses never gets the pad at all - and 43 was one of those,
found only because the pad read as a keyboard inside Palworld. Every fix for
that class is a better guess about process trees, and there will always be one
more launcher. And a game that *has* the pad still sees what reaches past it:
`[profile.steam]` puts a workspace on a shoulder held two seconds (`[confirm]`
1.2 s, then 0.8 s), which is deliberate at a desk and is also a thumb resting
on LB mid-fight.

**So the lock is the same question answered by hand.** `daemon.set_locked()`
pins `handed_over` on ahead of every other test - including a profile's
`handover = false`, which is a fact about an application and not about this
moment - and `allowed()` then refuses everything but a chord. Not the
announced hold, not `reaches_past`, not a single-button summon.

**And a refusal has to reach the announcement, not just the act.** Locked,
the shoulder still ticked and still said *Next workspace* two seconds in:
`allowed()` was asked when the hold fired and never when it announced itself.
An announcement is a promise, and both halves of it - the motor and the
notification - land on top of the game. `check_hold_timers()` now asks before
it warns, every tick rather than once, so a hold that outlives the lock still
announces itself.

**It is called the workspace lock**, in the row, on the guide page and in the
notification alike. *Game lock* was the first name and it says the wrong
thing: nothing about it belongs to the game, and what a person turns it on to
stop is the workspace walking away under a held shoulder.

**A chord is what is left because the menu has to stay reachable.** The lock's
own notification says "unlock it from the menu", and a lock that closed that
door would be a pad that does nothing until you find a keyboard.

**The way in is `ZL + B` or `ZR + B`, and it fires only over an app that
already has the pad.** Both triggers because which one a thumb is already
using is the game's business. The condition is not decoration: on the desktop
`ZL` + B closes the window and `ZR` is a left click held for a drag, and a
chord takes both buttons' own jobs the moment it exists - a chord member
cannot fire on the way down, since whether it is a chord is not known until
its partner has had a chance to land. So `Action.claims_chord(ctx)` was added
for it: a chord whose action can do nothing right now neither fires nor makes
its buttons wait. Over a game the same two cost nothing at all - the grab is
off there, so the game sees both whatever omapad does with them.

**Runtime state, not a setting.** A lock written to `settings.toml` is a pad
that does nothing at the next boot for a reason nobody remembers.

The menu row is at the top level rather than under Controller: it is the row
looked for while a game has the pad, and a row you have to go and find is a
row that is not there. It ticks while the lock is on, and the bar widget wears
a padlock in the same colour game mode uses - by then omapad's own bar has
gone, because the pad is the app's.

**And it is not there the rest of the time**, which the first cut got wrong:
the row sat in the desktop menu, where picking it hands the pad to a terminal
and leaves you finding the menu again to take it back. Hiding it needed
something the menu did not have - a row that is only offered in some states -
so `when` was added: `game`, `handed_over`, `locked`, any one of them enough,
read when the menu opens rather than per draw, because a row appearing under
the selection moves every row below it while a thumb is aiming at one. The
control socket asks nothing: `omapad ctl lock on` is typed on purpose, and it
is the door a script has.
