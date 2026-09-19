# 24. Game mode was the wrong shape · ✅ Done · L

The model was backwards, and the whole of items 20–23 was built on it.

What was believed: game mode hands the pad to the game, so almost nothing of
ours runs there. What it is for: **the couch environment** - the same desktop,
driven from a sofa, with a bar sized to be read from one. Handing the pad to a
game is a *separate* thing that should happen by itself, because there are a
million games and no list of them stays right. At most the keyboard or the menu
is summoned over a running game.

Every symptom of that evening follows from the inverted model. The keyboard
"not opening", the menu opening and closing without selecting, the shoulders
doing nothing, the window layer "breaking" - each was game mode correctly
switching off something the model said should be off, reported as a fault by
someone whose model was the right one.

**Handing over is now asked of the program rather than guessed at.** A gamepad
is a file; anything that wants to read one has to open it, and `/proc` says
who has. So the question is *has the window in front opened the pad*, and it
has a real answer: a terminal never opens it, a browser opens it the moment a
page asks for a gamepad (which is exactly when a cloud session wants it), a
game opens it because that is what a game does. `handover.py`, with two details
that the naive version gets wrong - Steam holds every input device open for as
long as it runs, so the question is about the *focused* window and not about
anybody; and Steam launches the game as a separate process, so the tree around
that window counts, three generations either way (further up is `systemd`, and
then every window looks like a game).

`EVIOCGRAB` blocks events rather than opens, so all of this stays visible while
omapad holds the pad: the app opens the device, receives nothing, and we
notice and let go.

What follows from it: `mode` decides presentation only (the bar, the couch
sizing); the grab follows the handover; `[bindings.game]` becomes a *difference
list* over the base layer rather than the short list of what survives;
`allowed()` stops restricting game mode at all and instead restricts only while
an app holds the pad - where a summon still gets through, and an open surface
takes the pad back for as long as it is up, since otherwise the D-pad would
drive the menu and the game at once. `mode_only`, `game_left_stick`,
`game_right_stick` and the `in_game` layer flag all existed to soften the wrong
model and are gone.

**Steam does not open the event node at all**, which the first version missed
entirely. It reads controllers through `hidraw`: with Big Picture running and
focused, Steam held `/dev/hidraw1` and nothing whatever under `/dev/input`, so
`wants_pad` said no and the pad would never have been handed to the one
application most likely to want it. A pad's nodes are now all three kinds -
event, `js*`, and the `hidraw` of the HID device underneath both. Found by
asking the running system rather than by reasoning about it, which is the only
reason it was found at all.

That opened a second gap. Once Steam has the pad, nothing of omapad's fires,
so there is no way back to the desktop from inside Big Picture or a game -
`[profile.steam]`'s bindings would never run. So a **confirmed** hold now
reaches past an app holding the pad: announced at `hold_ms` with a tick and a
notification, fired `confirm_ms` later, cancellable by letting go or with the
cancel button. Only that; a plain hold stays blocked, because the app sees the
same button and half a second is something you do by accident while playing.
The shipped `[profile.steam]` puts the workspace switch there.

**Verified live** both ways: a process holding the pad in a different tree from
the focused window does *not* take it (Steam sitting in the background all
evening), and focusing Big Picture does - `pad: handed to the focused app`,
`profile: None -> steam`, `ctl status` reporting `pad=app`. The positive path is
covered by unit tests against a `/proc` built to the Steam → reaper → game
shape, since the real one cannot be arranged on demand.
