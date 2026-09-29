# What is still open

Every decision is kept, one entry per number, in a log outside this repository.
This is the short list of what those decisions leave unfinished: each row says
which one it belongs to, because the reasoning is there and is not repeated
here.

Nothing below is scheduled. Within each section the order is the order the
numbers happened in, not a priority.

## Waiting on a decision, not on work

**12 · the keyboard in a password field ·
Constrained.** The signal is unreachable on this stack - Hyprland answers a
second input method with `unavailable` and fcitx5 holds the first - and what
would be left sees GTK and Qt but not Chromium, which is a protection that is
off exactly where it matters. The entry argues the premise is wrong too: the
real difference is shoulder surfing, and suppressing the pressed-key highlight
is cheaper and works everywhere. What is missing is somebody choosing.

**29 · the assistant · 📦 Shelved.** Built, worked,
taken back out on 2026-08-31 to keep the shipped set small. The code is kept and
the entry is the design for putting it back; the cost it was taken out for - a
model, a recorder and a transcriber, four more ways for the pad to stop working
- has not changed.

**94 · a move that comes
from where the ring is · Buildable · S.** Xbox pans its focus sound by the
element's place on screen; ours are mono on purpose, because a cue *happened
nowhere* - true of a commit, not of a move. The work is small, a pan in
`Sound.qml` from the ring's position. What is missing is deciding what a cue
is. The same entry owes the set its listen: every level is measured through a
model of a television, and none has been heard on one -
decision 101's marimba and vibraphone
included.

**97 · an answer on the card · Buildable ·
S.** The card reads a file and draws Markdown; nothing writes one yet. What it
was built for is a model's answer, which is decision 29's
to write, and that entry's cost has not changed. What is missing is deciding
whether the assistant comes back, and on which page its card stands.

## Built, and short of what it promised

**10 · the hint bar, on the desktop · Buildable ·
M.** decision 23 shipped the game-mode half as the right-hand
end of the game bar, printing only what is live. The same strip has never been
shown outside game mode, where a profile's bindings change under you as focus
moves, and where decision 18's countdown behind
a hold would have somewhere to draw itself.

**18 /
11 · the guide does not know about
profiles.** `build_pages()` reads `[bindings.*]`, so inside the browser the
guide prints the base map - the shoulders it shows are not the shoulders the
press would use. The game bar already prints through the profile in front; the
guide is the one surface that does not. As much 10's territory as 11's.

**22 · the desktop widget is one icon.** Either
exactly right or too quiet to be worth a slot. The payload already carries the
mode, the pad's name and the active profile, so a label costs nothing but bar
width.

**36 · the chord is drawn nowhere.** The
one gesture that reaches past an app holding the pad is in `[chords]`, and
nothing on screen mentions it: the guide has a page per layer and reads
`[bindings.*]`, and the game bar's hint strip withdraws entirely while an app
has the pad. The gesture that matters most over a game is the one nothing
announces.

## Caveats worth knowing before touching the area

**01 · `r±1` does not stop at ten.** It
follows the monitor's workspace range. A fixed 1-10 loop means omapad holding
the number itself and dispatching the absolute id, which would also make
wrap-around predictable.

**20 · nothing says which buttons a
game already uses.** A config that names too many is a config that eats the
game's own controls, and the guide page is the only warning. Suspicion rather
than measurement: the sticks are the part worth being careful with, since a game
reading the pad directly sees them too.

**21 · a fresh KP20 is still
wrong until someone runs the mapping screen.** The shipped `nintendo_pro`
profile names its face buttons by Nintendo printing. What a badge prints is
already a setting of its own - `[device] layout`, chosen from the menu since
decision 34 - but which name a code gets is
not. The fix is splitting a profile into *protocol* - codes, whether the
triggers are analog - and *printing* - which letter sits at which position -
with `[device] labels = "xbox" | "nintendo"`, which would make the screen
unnecessary for pads we already know. The screen also cannot map the D-pad: it
is a hat, not a button, on every pad seen so far.

**93 · what selection churn
leaves in the shell · measured, and left.** The four things 93 left are taken
and recorded there. What remains is a number to watch: at 30 ms a command the
guide kept 16 MB over forty cycles, and at a thumb's pace (150 ms) no surface
kept anything. The quick menu's 36 MB was measured while it was a surface of
its own; as a page of the menu (decision 102)
it has not been measured again. `budget stress` is the tool
([cli.md](components/cli.md)); nothing here is worth a change yet.
