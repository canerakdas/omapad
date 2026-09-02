# Handover - `omapad/handover.py`

Who wants the pad: the app in front, or us.

Game mode is the couch environment, not a hand-off - omapad drives the
desktop there, only bigger. Handing the pad to a game is separate, and it
should not be a mode anybody has to remember to switch: there are a million
games and no list of them stays right. So ask the program instead of guessing.
A gamepad on Linux is a file; anything that wants to read one has to open it,
and `/proc` shows who has.

## The four details that break the simple version

1. **Steam does not open the event node at all.** It reads controllers through
   `hidraw`, so watching only `/dev/input` would decide Steam had never asked
   for the pad. `_hidraw_nodes()` is why.
2. **Steam holds every input device open for as long as it runs**, focused or
   not, so "somebody has it open" is true all evening. The question has to be
   about the window in front.
3. **A window's pid is not always the process that opened the device** - a
   launcher, a wrapper script and the game are three pids - so the whole
   process tree around the focused window counts.
4. **The opener is not always above or below the window's process.** Under
   Proton it is `winedevice.exe`, wine's HID service, a *sibling*. So the walk
   goes sideways too, bounded by the cgroup.

## Surface

| Function | Answers |
|---|---|
| `device_nodes(path)` | the event node and its `hidraw` siblings |
| `holders(nodes, skip_pid, proc)` | which pids have any of them open |
| `parent_of`, `children_of`, `cgroup_of` | the walk's steps, straight out of `/proc` |
| `related(pid, depth, siblings)` | the process tree around the focused window |
| `wants_pad(focus_pid, nodes, ...)` | the whole question, in one call |

Settings: `[mode] handover_depth`, `handover_siblings`, `handover_poll`.

## Rules

- Everything takes `proc=PROC` so tests can point it at a fake tree; that is
  how this is tested without Steam. See `tests/test_handover.py`.
- `/proc` disappears under you constantly - a pid that existed when the
  directory was listed is gone when it is read. Every read tolerates that.
- The answer is a hint, not a lock: a summon still works while an app holds the
  pad, and an open surface takes it back until it closes. That decision lives
  in `daemon.wants_grab()`, not here.

## What still fires while the app has the pad

`daemon.allowed()` owns this. What gets through is a gesture the game does not
ask for:

1. **A chord.** Two buttons at once is not an input any game binds, so a chord
   reaches past whatever it runs. `[chords] "MINUS+PLUS" = "menu:toggle"` is
   the shipped one, and over an app holding the pad it is the only door: the
   keyboard, the window ops, game mode and the guide are all rows behind it.
2. **An announced hold** (`confirm = true`): held for seconds, ticked,
   cancellable. Same reason at the other end of the clock. `[profile.steam]`
   and `[profile.cloud]` put the workspace switch here.
3. **Whatever a binding says with `reaches_past`**, which overrules the kind of
   the action in both directions.

A **summon** is the default for a binding that says nothing, because a menu you
cannot open over a running game would make the whole arrangement useless. It is
only a default, though: the shipped config writes `reaches_past = false` on
`PLUS` and `MINUS`, because Back and Start are buttons every game binds and our
menu appearing every time you reach for the game's pause screen is the same
fault pointing the other way. `reaches_past = true` is how the opposite case -
a left click over a cloud session, which no announced hold can be - buys its
way in. Nothing ships with that on.

`Layer.reaches_past` says it once for every row in a layer; a row can still
opt out. Nothing ships with that on either - in a game ZL is aim, and ZL + A
would put the window full-screen mid-fight.

## What this does not answer

**An app that is not a game but opens the pad anyway.** Discord polls the
Gamepad API for its own keybinds, so it counts as having the pad for as long as
it is focused, and its profile - the voice panel on the face buttons - stands
aside with everything else. The honest fix is not a binding flag but a handover
*ignore list* by window class: some applications should never be handed the pad
at all. Not built.
