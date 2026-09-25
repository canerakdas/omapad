# What is still open

Everything that has been decided is in [`decisions/`](decisions/), one file per
decision, numbered. This is the short list of what those files leave unfinished:
each row says which decision it belongs to, because the reasoning is there and
is not repeated here.

Nothing below is scheduled. The order is the order the numbers happened in, not
a priority.

## Waiting on a decision, not on work

**[12](decisions/12-password-fields.md) · the keyboard in a password field ·
Constrained.** The signal is unreachable on this stack - Hyprland answers a
second input method with `unavailable` and fcitx5 holds the first - and what
would be left sees GTK and Qt but not Chromium, which is a protection that is
off exactly where it matters. The entry argues the premise is wrong too: the
real difference is shoulder surfing, and suppressing the pressed-key highlight
is cheaper and works everywhere. What is missing is somebody choosing.

**[29](decisions/29-assistant.md) · the assistant · 📦 Shelved.** Built, worked,
taken back out on 2026-08-31 to keep the shipped set small. The code is kept and
the entry is the design for putting it back; the cost it was taken out for - a
model, a recorder and a transcriber, four more ways for the pad to stop working
- has not changed.

## Built, and short of what it promised

**[10](decisions/10-hint-bar.md) · the hint bar, on the desktop · Buildable ·
M.** [23](decisions/23-game-bar.md) shipped the game-mode half as the right-hand
end of the game bar, printing only what is live. The same strip has never been
shown outside game mode, where a profile's bindings change under you as focus
moves, and where [18](decisions/18-shoulders-per-profile.md)'s countdown behind
a hold would have somewhere to draw itself.

**[18](decisions/18-shoulders-per-profile.md) /
[11](decisions/11-bindings-guide.md) · the guide does not know about
profiles.** `build_pages()` reads `[bindings.*]`, so inside the browser the
guide prints the base map - the shoulders it shows are
not the shoulders the press would use. As much 10's territory as 11's.

**[36](decisions/36-cloud-session-menu.md) · the chord is drawn nowhere.** The
one gesture that reaches past an app holding the pad is in `[chords]`, and
nothing on screen mentions it: the guide has a page per layer and reads
`[bindings.*]`, and the game bar's hint strip withdraws entirely while an app
has the pad. The gesture that matters most over a game is the one nothing
announces.

**[22](decisions/22-bar-widget.md) · the desktop widget is one icon.** Either
exactly right or too quiet to be worth a slot. The payload already carries the
mode, the pad's name and the active profile, so a label costs nothing but bar
width.

**[93](decisions/93-the-shell-that-stopped-reading.md) · the latency the
daemon stopped paying for is still on screen.** The loop no longer waits on a
stalled shell, and four things were left - all four now measured, and
the two worth a change made:

- **Why the shell stopped, for 0.3 to 1.2 s, around a surface opening ·
  measured away.** Not reproducible once the menu's tiles stopped building
  every kind (qml.md 5.6): on a shell restarted a few seconds earlier, the
  first opening of each surface froze it 10 to 49 ms and the second 4 to 31,
  menu with the game bar standing down included. The second-long freezes
  are `budget stress`'s own first second - eighteen opens and closes sent
  back to back, which no hand makes. What is left is memory: under selection
  churn at 30 ms a command the quick menu kept 36 MB over forty cycles and
  the guide 16, which the menu and the keyboard do not, and at a thumb's
  pace (150 ms) none of them kept anything. Worth watching with the tool
  below, not worth a change yet.
- **The rest of a page turn · measured, and left.** 110 to 215 ms before the
  ring, the clock and the travel went behind `Loader`s (qml.md 5.6); after,
  on a warm shell, 17 to 24 ms into most pages and a median of 33 to 37 into
  the Controller page, the slowest at fifteen tiles - two frames. What else
  every tile builds was tried one at a time: the row stack of a card of rows
  builds nothing off a card (its repeater is over `rs`, empty there), the
  `figureHead` is two `Text`s, and the halo, sheen and hit shapes left out
  altogether bought 4 ms, inside the noise - not worth a fade they would have
  to be born halfway through (qml.md 5.5). The rest is the tile itself.
- **The keyboards on the desk were let go of on the loop · done.** Closing
  an evdev node waits out an RCU grace period, 3 to 11 ms a keyboard here, at
  every surface closing. `KeyboardWatch.stop()` hands them to `close_aside`
  now, a thread of their own (kbd.md); the slowest tenth of `budget stress`
  went from 8-12 ms to 2-5 on every surface.
- **`budget stress` could not see the shell · done.** It prints `stalls:`
  now, timed by `ShellWatch` from the bar widget's socket, and `budget
  pages` times the shell at every menu page turn (cli.md). The mapping screen
  stays out of both: a thumb on the pad during a run would be recorded.

## Caveats worth knowing before touching the area

**[01](decisions/01-empty-workspaces.md) · `r±1` does not stop at ten.** It
follows the monitor's workspace range. A fixed 1-10 loop means omapad holding
the number itself and dispatching the absolute id, which would also make
wrap-around predictable.

**[20](decisions/20-left-click-after-handover.md) · nothing says which buttons a
game already uses.** A config that names too many is a config that eats the
game's own controls, and the guide page is the only warning. Suspicion rather
than measurement: the sticks are the part worth being careful with, since a game
reading the pad directly sees them too.

**[21](decisions/21-pad-answered-neighbours-name.md) · a fresh KP20 is still
wrong until someone runs the mapping screen.** The shipped `nintendo_pro`
profile names its face buttons by Nintendo printing. The fix is splitting a
profile into *protocol* - codes, whether the triggers are analog - and
*printing* - which letter sits at which position - with
`[device] labels = "xbox" | "nintendo"`, which would make the screen unnecessary
for pads we already know. The screen also cannot map the D-pad: it is a hat, not
a button, on every pad seen so far.
