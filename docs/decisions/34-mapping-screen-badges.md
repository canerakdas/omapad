# 34. Asking for a button the pad does not print, and a menu for the pad · ✅ Done · M

The mapping screen shouted `MINUS` at an Xbox pad. The logical names are the
Switch's - that is what a binding is written against and what the mapping file
is keyed by - but nothing on an Xbox pad says *minus*, and the one screen where
the eyes are on the plastic rather than on the display is the worst place to
name a button after a different console. `guide.badge_of` had answered this
question everywhere else since **31**; the fourth surface had never been given
the answer.

**What landed:** `MappingModel` carries a `layout` like the guide and the bar
do, the daemon sets all three in one place (`apply_layout`), and the step is
drawn as the button it is - the same shapes, through `ButtonArt`, in the accent
colour - with the words underneath naming both printings, because a pad whose
profile is wrong is usually a pad printed unlike that profile's family. The
progress strip and the final confirmation moved with it: `A saves it` is
printed `✕ saves it` on a pad whose face buttons are shapes. Four face buttons
whose printing *is* a shape get words of their own (`Cross`, not `✕`), since
"press ✕" reads as a step that was crossed out.

**And the settings themselves became reachable.** Which profile a pad takes and
what its badges print are exactly the questions you have while holding the
thing and getting the wrong answer, and until now both were a file edit and a
`systemctl --user restart`. `pad:<setting>=<value>` is the action grammar's way
in - `pad:layout=xbox`, `pad:profile=auto`, `pad:rumble=toggle`,
`pad:rumble_strength=up`, and `next`/`prev` on any of them so one button can
walk what the menu offers as rows. What is chosen is applied to the running
daemon (a new profile re-reads the pad already open; a new layout repaints
every surface) and written to `~/.config/omapad/settings.toml`, merged last
so it wins over `config.toml` - the same shape `mapping.toml` already had, and
for the same reason: a hand-written file full of comments is not something a
program should rewrite.

The menu grew the two things a settings row needs and did not have: `stay =
true`, one press that leaves the menu up (a choice you cannot see the result of
without being thrown back to the desktop is a choice you make twice), and a
**tick** on the row that is already in force, which is the difference between a
list of choices and a list of guesses. The tick is `Action.state(ctx)` -
`None` for everything that is not a setting, since launching a browser is
neither on nor off - so the menu asks the daemon rather than knowing anything
itself.

`Controller` in the root menu now holds all five: Shortcuts, Remap the buttons,
Profile, Button labels, Vibration. The first two were loose rows in the root
menu before; a controller is one thing and reads as one row.

**What this does not fix:** item **21**'s open caveat, one layer down. The
`nintendo_pro` profile still names a KP20's face buttons by Nintendo printing,
so a fresh install of that pad is still wrong until someone opens the screen or
picks a profile - the difference is that picking one is now four button presses
rather than a file edit. Splitting a profile into *protocol* and *printing*
remains the fix that would make neither necessary.
