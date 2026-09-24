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
stalled shell, but the shell still stalls, and four things are left:

- **Why the shell stops, for 0.3 to 1.2 s, around a surface opening ·
  Buildable · M.** Measure first: a timestamp on the payload and the panel
  logging parse-to-applied, or the QML profiler. The suspects are each panel
  being a `PanelWindow` made and destroyed with `visible: root.opened`; the
  game bar closing and opening under a fullscreen menu or the quick menu,
  whose `ExclusionMode.Auto` re-tiles every window each time; and the shell
  growing 110 MB over twenty stress cycles, which is a collector with work
  to do. Keeping the bar's layer and zone standing and hiding only what it
  draws is the likely first change; keeping panels mapped behind an empty
  input mask is the larger one, and needs its own decision about focus.
- **The rest of a page turn · Buildable · S.** It froze the shell 110 to 215
  ms; with the ring, the clock and the travel behind `Loader`s it is 13 to 94,
  median ~47 (qml.md 5.6). What every tile still builds, whatever its kind,
  in the order worth trying:
  - the **row stack** of a card of rows (`rowStack`, some five hundred lines)
    and the spine repeater beside it, on every tile that is not a card of rows;
  - the **`figureHead`** - the figure and its words - on every tile that is
    not a slider, a knob or a reading;
  - the **halo, sheen and hit** shapes, which draw only while their opacity
    is above nought and are built on every tile regardless. These animate in,
    so a Loader that starts them has to be born at the right point of the
    animation (qml.md 5.5);
  - the **choice** row and the dead zone's drawing in the tile's middle, and
    the media and icon marks.
  Measured one at a time on the Controller page (fifteen tiles, 94 ms, the
  slowest), and each one checked on screen before the next.
- **The keyboards on the desk are reopened at every surface · Buildable ·
  S.** `kbd.follow()` scans `/dev/input` and opens and closes each keyboard
  whenever a surface opens or closes, and every close waits in
  `synchronize_rcu` - 10 to 17 ms on the loop, measured. Doing it off the
  loop, or holding them a moment past a close so a quick reopen costs
  nothing, keeps the rule that they are only ours while a surface is up.
- **`budget stress` cannot see the shell · Buildable · S.** It times the
  control round trip, which is the daemon's. It should also say how long each
  view socket went unread and how often the daemon logged a stall, and cover
  the mapping screen, so the items above have a number to beat. The page turn
  was measured by hand: a byte every 20 ms into `status.sock`, `ss` watching
  how long it sat unread, while the control socket turned the pages - which
  is the shape of a `budget pages` of its own.

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
