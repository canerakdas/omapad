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
5. **The launchers are deeper than any count.** `steam -> srt-bwrap ->
   pv-adverb -> steamwebhelper` is three before a game's own wrapper, so a
   climb bounded by generations found Steam from Steam's window and never from
   the game it started - the pad stayed ours over a running game. The cgroup
   bounds the climb instead: it is exactly as long as the application is,
   where a count is either too short for Proton or long enough to reach the
   compositor from a terminal.

## Surface

| Function | Answers |
|---|---|
| `device_nodes(path)` | the event node and its `hidraw` siblings |
| `holders(nodes, skip_pid, proc)` | which pids have any of them open |
| `parent_of`, `children_of`, `cgroup_of` | the walk's steps, straight out of `/proc` |
| `related(pid, depth, siblings)` | the process tree around the focused window - the cgroup bounds the climb, `depth` the descent |
| `wants_pad(focus_pid, nodes, ...)` | the whole question, in one call |

Settings: `[mode] handover_depth`, `handover_siblings`, `handover_poll`,
and `handover` on any `[profile.<name>]`.

## Rules

- Everything takes `proc=PROC` so tests can point it at a fake tree; that is
  how this is tested without Steam. See `tests/test_handover.py`.
- `/proc` disappears under you constantly - a pid that existed when the
  directory was listed is gone when it is read. Every read tolerates that.
- The answer is a hint, not a lock: a summon still works while an app holds the
  pad, and an open surface takes it back until it closes. That decision lives
  in `daemon.wants_grab()`, not here.

## What the sticks do while the app has the pad

Nothing. `daemon.stick_roles()` returns `("none", "none")` the moment the pad
is handed over, so `sticks_live()` is false and the tick integrates nothing.
The buttons are a question of which gesture reaches past; a stick is not, and
the asymmetry is the point: a press ends when the thumb comes off, while a
stick left over drives the pointer across the game for as long as it is held -
and an app reading that pointer has stopped reading the pad. There is no
`reaches_past` for a stick, because what buys a button its way past is being a
gesture the game does not ask for, and a stick pushed over is the one input
every game does ask for.

An open surface takes them back with the pad, on the same condition the grab
uses (`surface_open()`): the keyboard is pointed at with a stick.

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

## The workspace lock: the question answered by hand

`/proc` is right about every game whose opening of the pad it can see, and
that leaves two cases over. A game the walk misses gets nothing while the
sticks drive the desktop over the top of it. A game that does have the pad
still sees what reaches past it - and the announced hold `[profile.steam]`
puts a workspace on is two seconds of resting a thumb on a shoulder, which
happens mid-fight.

So a person can answer it instead. `daemon.set_locked(True)` - the `ZL+B` /
`ZR+B` chords, the **Workspace lock** menu row (offered in game mode or while
the app in front has the pad; see `when` in [`menu.md`](menu.md)), `omapad ctl
lock on` - pins
`handed_over` on ahead of every other test in `update_handover()`, including a
profile's `handover = false`, and `allowed()` then refuses everything but a
chord. `check_hold_timers()` asks the same question before it *announces* a
confirming hold, so a lock does not leave a tick and a notification counting
down to nothing over the game. The chord is the menu and the menu is the way out, which is why the
notification names it.

The chords fire only while the pad is already the app's
(`LockAction.claims_chord`), because on the desktop `ZL + B` closes the window
and `ZR` is a left click held for a drag. Over a game they cost nothing: the
grab is off, so the app sees both buttons whatever omapad does with them.

The lock is runtime state and is not written to `settings.toml`. A pad that
did nothing at the next boot for a reason nobody remembers is worse than
locking again.

## The app that opens the pad without being a game

Discord polls the Gamepad API for its own keybinds, so `/proc` sees it holding
the pad for as long as it is focused and hands it over: the voice panel on the
face buttons stands aside, and the sticks stop pointing at the window those
bindings exist to aim at. No amount of looking at `/proc` fixes that, because
what is being asked is not *has this app opened the pad* but *does holding
this app's pad mean driving this app*, and that is a fact about the
application.

So the profile says it - `handover = false` on a `[profile.<name>]` table, the
place an application is already named by class:

```toml
[profile.discord]
match = ["discord", "vesktop", "webcord", "legcord", "armcord"]
handover = false
```

`daemon.update_handover()` asks the active profile before it asks `/proc`, and
`seed_active_window()` swaps the profile in *before* it asks about the pad -
the other way round, a refusal would land a window late. Only for an
application nobody plays through: a game with this on is a game the pad cannot
reach.
