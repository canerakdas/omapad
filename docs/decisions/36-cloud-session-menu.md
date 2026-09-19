# 36. The cloud session, and the menu that opened on top of it · ✅ Done · M

Reported from the sofa: *with GeForce Now open RT and LT do nothing, and with
Discord open I could not close the window with the LT modifier.* One cause, and
not a bug: measured live, `GeForceNOW` held `/dev/input/event17` and
`/dev/input/js0` with Fortnite on screen, `ctl status` said `pad=app`, and
`allowed()` was doing exactly what 24 built it to do - while an app holds the
pad, nothing but a summon and an announced hold gets through. `ZR`
(`click:left`) was blocked, and ZL opened a layer whose every row was blocked,
which from the outside reads as "LT does nothing".

**The first answer was the wrong one and is worth recording.** `reaches_past`
was built to let named bindings through, and shipped on for the whole window
layer and for `ZR` - and that is the 20 mistake inverted. The pad had been
handed to the app *because the app is using it*: in a game ZL is aim and ZR is
fire, so a left click on ZR fires at the desktop with every shot and ZL + A puts
the window full-screen mid-fight. Asked for again with the constraint stated -
*do not override the buttons the game is using* - it inverted cleanly.

**What gets through is a gesture the game does not ask for.** Two of them, and
neither is a plain press: a **chord**, because two buttons at once is not an
input any game binds, and an **announced hold**, which 24 already had. So
`fire_chord` reaches past whatever it runs, and the chord became the door.

**`MINUS+PLUS` now opens the menu.** It was `mode:toggle`, which did not need a
chord: HOME held for 700ms toggles the mode in every layer, and the menu has a
`Game mode` row. The menu had no second way in, and it is the one thing that has
to be reachable from inside a game - the keyboard, the window ops, the guide and
the launcher are all rows behind it.

**And the single-button summons stand aside**, which is the part that had never
been questioned. A summon reaching past an app holding the pad was 24's rule and
it is right as a *default*; on `PLUS` and `MINUS` it is wrong, because Back and
Start are buttons every game binds, so our menu came up every time you reached
for the game's own pause screen. `reaches_past` earns its keep here instead:
tri-state, so `false` keeps a summon back, `true` lets a non-summon through, and
undecided leaves 24's rule alone. The decision moved into the config rather than
being re-hardcoded the other way.

`[profile.cloud]` (GeForce NOW, Moonlight, Chiaki, xCloud) is `[profile.steam]`'s
shape for the same situation: the shoulders held and confirmed walk the
workspaces, and that is deliberately all. A session in a browser matches
`[profile.browser]`, which already had it.

**Also still open: the chord is not drawn anywhere.** The guide has a page per
layer and reads `[bindings.*]`; `[chords]` is not in it, and neither is the game
bar's hint strip, which withdraws entirely while an app has the pad. So the one
gesture that now matters most over a game is the one nothing on screen mentions.
It was as true when the chord was `mode:toggle`, and it matters more now.

**Still open: Discord.** It is not a game and it takes the pad anyway - the
Gamepad API is polled for its own keybinds - so `[profile.discord]`'s voice
panel stands aside with everything else for as long as Discord is focused. No
binding flag is the right answer to that; a handover **ignore list by window
class** is, and it is not built. Measured far enough to be sure of the shape:
Discord runs here as an Omarchy webapp, class
`chrome-discord.com__channels_@me-Default`, and it holds the pad only while
focused - which is exactly when handover fires.
