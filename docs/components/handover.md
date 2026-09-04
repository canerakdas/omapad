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
