# omapad

A small user-space daemon for driving an Omarchy / Hyprland desktop with a game
controller. It reads the pad from `evdev`, creates a virtual mouse and keyboard
through `uinput`, and talks to Hyprland's IPC socket for window work.

No dependencies: the Python 3.11+ standard library alone (`tomllib`, `fcntl`,
`struct`, `select`).

It has two parts:

| Part | What it does |
|---|---|
| `omapad` (systemd user service) | Reads the pad, drives the pointer and the keyboard, holds the on-screen keyboard's layout and selection |
| `shell-plugin/` (Omarchy shell plugin) | **Draws** the on-screen keyboard, the menu, the bindings guide and the mapping screen — and nothing else |

The on-screen keyboard's layout, selection and modifier latches live in the
daemon; the plugin is only a view. That is why pressing a key does not wait for
a round trip to the shell: by the time the plugin repaints, the character has
already been typed.

## Contents

[Installation](#installation) · [Removal](#removal) ·
[Two modes](#two-modes-desktop-and-game) ·
[Handing the pad to a game](#handing-the-pad-to-a-game) · [Game bar](#game-bar) ·
[The pointer and snap](#not-having-to-aim-the-pointer-and-snap) ·
[Focus traversal](#inside-the-window-focus-traversal) ·
[The default bindings](#the-default-bindings) ·
[What each button means](#the-face-buttons-mean-the-same-thing-everywhere) ·
[Controller modes](#controller-modes) · [Configuration](#configuration) ·
[Application profiles](#application-profiles) · [The menu](#the-menu) ·
[The readings](#the-readings-how-busy-how-full-how-hot) ·
[The bindings guide](#the-bindings-guide) · [The bar widget](#the-bar-widget) ·
[Controller mapping](#controller-mapping) · [Typing](#typing) ·
[Using another controller](#using-another-controller) ·
[Development](#development) · [Troubleshooting](#troubleshooting) ·
[Licence](#licence)

## Why not a Hyprland plugin

There are two different "plugins" here, and they are worth keeping apart. The
on-screen keyboard is an **Omarchy shell plugin** (Quickshell/QML) — the
supported road, the one that hands you the theme and the margins for free. A
**Hyprland plugin** (`hyprpm`, C++) is another thing entirely: the ABI breaks
on every Hyprland release, every update wants a rebuild, and sending keyboard
input to applications would still have been a separate job on top. So the input
side is a daemon of its own: updates do not touch it, `systemctl --user
restart` puts it right, and it gets out of the way completely when you want to
leave the pad to a game.

## Installation

Two lines, from nothing:

```bash
export OMAPAD_SHA=<the commit the release names>
curl -fsSL "https://raw.githubusercontent.com/canerakdas/omapad/$OMAPAD_SHA/boot.sh" | bash
```

Every [release](https://github.com/canerakdas/omapad/releases) names the commit
to put there. `boot.sh` clones the repo straight into
`~/.config/omarchy/plugins/canerakdas.omapad` — `manifest.json` is at the root,
so the checkout **is** the plugin, with no symlink — and hands over to
`install.sh` for the parts that need permissions. The commit is named twice on
purpose: in the URL it fixes the script you are piping into a shell, and in
`OMAPAD_SHA` it fixes the tree that gets installed, so neither half can be a
branch that moved after the release was reviewed. It is ninety lines; read it
first if you would rather not pipe a script into a shell.

Or use Omarchy's own plugin command, which is two steps:

```bash
omarchy plugin add https://github.com/canerakdas/omapad.git
~/.config/omarchy/plugins/canerakdas.omapad/install.sh
```

`omarchy plugin add` clones, validates and enables the drawing half. Nothing in
the plugin system can grant `/dev/uinput` or install a user service — there is
no post-install hook — so the installer is still its own step.

Or keep the checkout wherever you keep things, and let `install.sh` link it
into the plugins directory:

```bash
git clone https://github.com/canerakdas/omapad.git
cd omapad
./install.sh
```

What `install.sh` does:

1. Installs a udev rule giving the `input` group write access to `/dev/uinput`,
   and arranges for the `uinput` module to load at boot (**asks for sudo**).
   This is the only reason the daemon does not have to run as root.
2. Writes a commented stub at `~/.config/omapad/config.toml` if there is none
   there, and keeps the one you have if there is. It is a stub rather than a
   copy of the defaults on purpose: your file is merged *over* the shipped
   one, so a copy would freeze today's defaults and shadow every later
   improvement.
3. Links the `omapad` command into `~/.local/bin`.
4. Validates the manifest, links the checkout into `~/.config/omarchy/plugins/`
   as `canerakdas.omapad`, and enables it. If you came through `omarchy plugin
   add`, the checkout is already there and this step only enables it.
5. Installs and starts the `omapad.service` user service, with the path of
   this checkout baked into it.

Before any of that, it checks that the checkout is somewhere whose path can be
written into a systemd unit at all. A space or a `%` in it is something systemd
reads rather than keeps — `%t` is its own runtime directory — so a checkout at
`~/my games/gamepadd` is refused with a line saying to move it, rather than
installed as a service that will not start. Anywhere ordinary is fine; the
default `~/.config/omarchy/plugins/canerakdas.omapad` always is.

Updating it — `omarchy plugin update` only pulls, so re-run the installer when
the pull touched the service or the udev rule. Because an install is the
commit you named, the way to update is to re-run those two lines with the
commit the new release names, or, after a `git pull`, the installer:

```bash
omarchy plugin update canerakdas.omapad
~/.config/omarchy/plugins/canerakdas.omapad/install.sh
```

Checking it:

```bash
omapad check                    # config + the connected pad
omapad budget                   # what it costs while nothing is happening
systemctl --user status omapad
journalctl --user -u omapad -f
```

## Removal

To undo the install, in reverse order:

```bash
# The drawing half: the shell plugin. Remove it with the shell's own command
# if one exists, otherwise delete the directory.
rm -rf ~/.config/omarchy/plugins/canerakdas.omapad

# The daemon half.
systemctl --user disable --now omapad.service
rm -f ~/.config/systemd/user/omapad.service
systemctl --user daemon-reload
rm -f ~/.local/bin/omapad
```

`~/.config/omapad/` and the uinput permissions are left in place unless you
remove them: they are harmless without the daemon, and the group membership
is yours to keep or revoke. To take those out too:

```bash
rm -rf ~/.config/omapad
sudo rm /etc/udev/rules.d/99-omapad-uinput.rules \
      /etc/modules-load.d/omapad-uinput.conf
sudo udevadm control --reload-rules
sudo gpasswd -d "$USER" input    # the new session after this has no input group
```

## Two modes: desktop and game

- **desktop** — the ordinary desktop. The pad drives the pointer.
- **game** — the same desktop, **from the couch**. omapad's bar takes the
  place of Omarchy's, the surfaces are drawn at `[ui] game_scale` instead of
  `[ui] scale` so they read from a distance, and
  **everything works**: bindings, layers, profiles, the pointer. Not a
  restriction, a difference in presentation.

Switching between them: **hold HOME for 0.7 s** — on the desktop, in the menu
or over a game. Every switch drops a notification **and ticks the motor** —
one tick each way, because the switch is the press whose result you may not be
looking at: the bar is swapping itself out across the room while the pad is on
your lap. Either answer can be turned off on its own:

```toml
[mode]
notify = true   # the desktop notification
rumble = true   # the tick under the thumb
```

**Which mode it comes up in** is `[mode] start`, which ships `desktop`. It is
the one thing about the couch that could only be decided at a keyboard - the
machine you never walk to one for is exactly the machine that wants to come up
from the couch - so it is in the menu as well, under **System › Start in**: a
card with both modes on it, a line under each saying what it does, and a ground
filling the one that is waiting. Picking one moves nothing; what it names is the
next start, which is a reboot, a fresh login or
`systemctl --user restart omapad`.

```toml
[mode]
start = "desktop"   # or "game", to come back up from the couch
```

(MINUS + PLUS used to be the chord for this; it opens the **menu** now, which
had no second way in — see below.)

While game mode is up the screen is the couch's, so omapad also tells Omarchy
to **stay awake** (`omarchy toggle idle stay-awake`): the screensaver and the
lock cannot fire over a game or a paused cloud session. Idle is given back the
moment the desktop returns, and at shutdown, so a daemon that dies in game mode
does not leave a screen that stops locking. Turn it off with
`stay_awake_in_game = false` under `[mode]`.

**It follows the thumb, not the mode.** Pad input is invisible to the
compositor — walking a menu moves a selection over a socket and produces no
Wayland input at all — which is why omapad holds the screen awake here and
binds an idle inhibitor under the keyboard, the guide, the mapping screen and
the game bar. What that leaves is a hold with nobody at the other end of it: a
television left on game mode, or a keyboard left open on one, never sleeps. So
the hold lets go `[idle] awake_ms` after the pad was last touched — a press, a
D-pad step, a stick past its dead zone — and the desktop's own screensaver and
lock decide from there. The next press takes it back. Five minutes ships,
because that is about what a screensaver waits anyway; `0` never lets go,
which is what this did before it was a setting.

**Handing the pad to a game is separate from all this, and happens by
itself** — the next section.

## Handing the pad to a game

This is not a mode, and not a button anybody has to remember. There are
millions of games; no list of them stays right. So we **ask the program**
instead.

On Linux a controller is a file (`/dev/input/event*`), and any program that
wants to read it **has to open** that file. The kernel keeps track of who has,
and `/proc` says so. So "has the app in front opened the pad?" is a question
with a real answer — and it is exactly the right question.

| Situation | Who has the pad |
|---|---|
| Terminal, editor, file manager | omapad — none of them opens that file |
| Reading the news in a browser | omapad — the browser does not open it either |
| A cloud gaming session in a browser | **the app** — the browser opens it the moment the page asks for the Gamepad API |
| Steam Big Picture, a game, an emulator | **the app** |
| You alt-tabbed out of the game | omapad — focus changed, the pad comes back |

There are four subtleties, and all four are handled:

- **Steam never opens the evdev node** — it reads controllers through `hidraw`.
  Measured on this machine: Steam holds `/dev/hidraw1` and nothing at all under
  `/dev/input`. So *every* node of one pad counts: the event node, the `js*`
  one, and the `hidraw` of the HID device underneath them.
- **Steam holds the devices open for as long as it runs**, focused or not. So
  the question is not "has somebody opened it" but has **the focused window's
  process** opened it.
- **Steam starts the game as a separate process**, so the window's pid and the
  pid that opened the file can differ. That is why the ancestors and children
  of the focused process count too (three generations; further up you reach
  `systemd` and start taking every window for a game).
- **The process that opens the file is not always in that family tree.** Under
  Proton the pad is opened by `winedevice.exe` — wine's HID service — and it is
  the game's *sibling*: both hang off the same pressure-vessel process.
  Measured with Balatro; a search that only looked up and down could not see
  it, so the pointer went on driving the desktop while the game was in front.
  So it looks **sideways** as well — bounded by the cgroup: a terminal's parent
  is the compositor, and its siblings are every window on screen. A process
  outside the same cgroup is not the same application.
- **The launchers are deeper than any count.** Measured: `steam → srt-bwrap →
  pv-adverb → steamwebhelper` is already three, and a game adds the reaper and
  wine's own wrapper below that. Counting generations found Steam from Steam's
  own window and never from the game it started — so the pad stayed the
  desktop's over a running game, which saw a keyboard and a mouse instead of a
  controller. A longer count is not the repair: the same number applied to a
  terminal reaches the compositor, whose children are every window on screen.
  **The cgroup is the bound that fits** — systemd gives a launched application
  its own scope, everything Steam starts stays inside Steam's, and the climb
  ends exactly where the application does.

```toml
[mode]
handover_depth = 3       # how far *down*, and how far up with no cgroup to bound the climb
handover_siblings = true # trust the cgroup as the edge of an application (required for Proton)
```

**The sticks stop altogether.** Every role a stick carries is a desktop job —
the pointer, the wheel, moving a window — and a thumb resting on one while the
game has the pad slides the pointer across it for as long as it is held. That
is worse than a stray press, which is over when the thumb comes off, and an
application reading the pointer has stopped reading the pad. Unlike the buttons
they get no way back: what earns a button its way past is being a gesture the
game does not ask for, and a stick pushed over is the one input every game
does ask for.

**What still gets through is a gesture the game does not ask for**, and there
are two of them.

First: **the MINUS + PLUS chord, which opens the controller menu.** Two buttons
at once is not an input any game binds, and this is the door — the keyboard, the
window controls, the guide and the app launcher are all rows behind it. The
moment the menu opens omapad takes the pad back (otherwise the D-pad
would drive both the menu and the game), and lets go again when it closes.

Second: **an announced hold that counts down** (`confirm_ms`).
The app already sees that button, so the only gesture that may get through is
one nobody could make by accident — held for seconds, saying what is about to
happen through a rumble and a notification, and abandoned by letting go or by
pressing the cancel button.

**Single-button summons stand aside.** On the desktop PLUS opens the menu and
MINUS the keyboard; over an app that has the pad, both do nothing, because Back
and Start are buttons every game binds and our menu appearing every time you
reach for the game's pause screen is the same fault pointing the other way. That
is the shipped config's choice, not a rule — `reaches_past` is the key, and
removing it puts them back:

```toml
[bindings.base]
PLUS  = { tap = "menu:toggle", hold = "exec:omarchy-menu toggle", hold_ms = 400, reaches_past = false }
MINUS = { tap = "osk:toggle", reaches_past = false }
```

The shipped `[profile.steam]` uses this: hold a shoulder inside Big Picture or a
game and the badge on the bar fills in; when it is full the pad ticks and says
what is coming, and the badge leans towards the workspace it is about to reach
while the fill runs back out of it. It exists
because once Steam has the pad there is no other way back to the desktop. Both
waits come from `[confirm]` (1.2 s, then 0.8 s) — raise them there if a shoulder
ever fires while you are playing.

`reaches_past = true` is the same key the other way round: it lets a binding
that is **not** a summon through, which is the only way to have something like a
pointer click over a stream (no announced hold is a click). Nothing ships with
it on, because the app sees that button too — in a game ZL is aim and ZR is
fire, so a left click on ZR would fire at the desktop with every shot. It can
also be said once for a whole layer, and a row inside can still opt out:

```toml
[layers.window]
reaches_past = true                                               # all of it

[bindings.window]
B = { tap = "hypr:hl.dsp.window.close()", reaches_past = false }  # except this
```

### The button held when the pad changes hands

The grab is exclusive: while omapad holds the pad the kernel gives its events
to omapad alone. So a grab taken **while a button is down** costs the app that
had the pad the release of that button — it saw the press, it never sees the
letting go, and it goes on believing the button is held for as long as it runs.

That is the ordinary case rather than a rare one, because the gesture that
takes the pad back is itself a held one. Hold `L` inside Big Picture to walk a
workspace: the focus change lands first and the thumb comes off after it, so
the release reaches omapad and Steam is left with a bumper down for ever.
Measured, in Steam's own log — every Guide press after that reads

```
Guide button skipped due to chording
```

because a Guide press with a bumper down is a chord (Guide + LB), and the Steam
menu never opens again for the rest of the session.

So a grab waits for the pad to be let go before it takes it:

```toml
[mode]
grab_settle = 2.0   # seconds a wanted grab waits for the hand to come off
```

While it waits the app sees our presses too, which is the trade: a press
arriving twice is worth a great deal less than a button stuck down until the
app is restarted. The wait is bounded for the button that is never released — a
dongle that drops mid-press — and `0` takes the pad the moment it is wanted.
Letting go of the pad never waits: an app that gets a release it never saw the
press of ignores it.

### The workspace lock

The hand-off asks the program itself and is right about the games it can see.
Two things are left over, and the lock is the answer to both.

A game the walk **misses** never gets the pad, and then the sticks drive the
desktop over the top of it. And a game that *has* the pad still sees the two
gestures above: a shoulder held for two seconds is a workspace change, and
mid-fight a thumb rests there for two seconds often enough.

**Hold either trigger and press B** — `ZL + B` or `ZR + B` — and the pad is the
app in front's outright: it is handed over whatever `/proc` thinks, and nothing
of omapad's fires any more. Not an announced hold, not a `reaches_past`
binding, not a single-button summon. A hold it will not let through does not
**announce** itself either — the tick and the notification are a promise that
something is about to happen, and they land on top of the game. What is left is the MINUS + PLUS chord,
which opens the menu, and **Workspace lock** is a row in it — that is the way
back out, and the notification says so as it locks.

The chord fires **only while the app in front already has the pad**. On the
desktop `ZL + B` closes the window and `ZR` is a left click you can drag with,
and neither press is the lock's to take; over a game it costs nothing at all,
because the grab is already off and the game sees both buttons anyway.

The menu row is the same switch and ticks while the lock is on, so it locks a
game the hand-off missed as well as unlocking one it did not. It is offered in
game mode and while the app in front has the pad, and nowhere else (`when`,
below): on a desktop the lock would hand the pad to a terminal and leave you
finding the menu again to take it back. `omapad ctl lock
on|off|toggle` is the same thing without a pad, and the bar widget wears a
padlock while it is on.

### Keeping the pad over an app that asked for it

The hand-off can be right about the program and wrong about the screen. A cloud
client opens the pad as its page loads, which is long before there is a game:
the launcher in front of the stream is a web page that reads no pad at all, so
the pointer that could press its **Play** button has already been handed away.
Nothing on the pad does anything and nothing says why — measured with GeForce
NOW, whose session then never starts.

**Keep the controller** is the row that takes it back. Every binding fires
again over a window that had already claimed the pad, so the menu is a plain
press away rather than a chord — and it stays on until it is turned off,
because the stream that starts after **Play** does want the pad. The row is
offered while an app has the pad and for as long as it is on, so turning it on
never takes away the way of turning it off. `omapad ctl keep on|off|toggle` is
the same switch without a pad, and the bar widget lights up while it is on.

It is the workspace lock's pair and the two cannot both be on: one question
with two answers, and the second one asked is the one that stands.

### Cloud gaming and remote play

GeForce NOW, Moonlight, Chiaki and xCloud open the pad the moment a session
starts — measured with GeForce NOW, which held `/dev/input/event17` and
`/dev/input/js0` while a game was on screen. So the pad goes to them, and that is
right: the game is being played, and a button of ours firing on top of it is a
button taken away from the game.

`[profile.cloud]` gives them the same shape as `[profile.steam]`: **the
shoulders, held and confirmed, walk the workspaces** — the one thing worth doing
without leaving the stream — and everything else is a row in the menu, which is
the MINUS + PLUS chord away.

```toml
[profile.cloud]
match = ["geforcenow", "moonlight", "chiaki", "xcloud", "greenlight"]

[profile.cloud.bindings]
L = { hold = "hypr:hl.dsp.focus({ workspace = 'r-1' })", hold_desc = "Previous workspace", confirm = true }
R = { hold = "hypr:hl.dsp.focus({ workspace = 'r+1' })", hold_desc = "Next workspace", confirm = true }
```

A session run in a **browser** instead matches `[profile.browser]`, which already
puts the same confirmed hold on the same two buttons.

`omapad ctl status` says which it is: `pad=ours` / `pad=app`, and whether the
lock below is on: `lock=on` / `lock=off`.

Game mode also takes Omarchy's bar away, and puts
[omapad's own](#game-bar) in its place.

It does that with `omarchy toggle bar off` — the bar parks off screen and the
shell is not restarted. It comes back on the way out, **and on the way down
too**: a daemon that dies in game mode must not leave you with a barless
desktop. On a machine with no Omarchy it is skipped quietly.

The reason: every widget on that bar opens a popup you click, and in game mode
the pad is in the game — so the whole bar is out of reach. A fullscreen game
should have the screen to itself.

To keep the desktop bar in game mode instead:

```toml
[mode]
hide_bar_in_game = false
```

Both bars reserve their own strip, so that leaves the one you cannot reach
above the one you can. Turn `[gamebar] enabled` off in the same pass for a
game mode that changes what the sticks do and nothing you can see.

### A game that opens behind Steam Big Picture

Launch a game from Big Picture and the game can come up **behind** Steam, with
no way to reach it from the pad. This is not omapad's doing and it is worth
knowing why, because the obvious fixes do not work.

Omarchy floats every Steam window (`o.window("steam", { float = true })`), and
that rule matches the class exactly: Big Picture is class `steam` and floats,
while a game launched from it is class `steam_app_<id>` and tiles. **In Hyprland
a floating window is always drawn above a tiled one** — that is a layering rule,
not a stacking order — so Big Picture covers the game. Measured on this machine:
`cyclenext` moves focus to the game (its border lights up) and
`bringactivetotop` leaves it exactly where it was, still covered. Nothing raises
a tiled window over a floating one.

**Fullscreen is what clears it**, because a fullscreen window does cover the
floating one. One line in `~/.config/hypr/hyprland.lua` makes it happen by
itself, and it is the same answer Omarchy already gives RetroArch and Moonlight:

```lua
o.window("steam_app_.*", { fullscreen = true, idle_inhibit = "fullscreen" })
```

`idle_inhibit` comes with it: a pad-only session produces no Wayland input at
all, so without it the screensaver arrives mid-game. Games that use a class of
their own rather than `steam_app_*` need their own line.

**And the way out with the pad in your hands**, for when it happens anyway:
`PLUS` → **Workspaces** → **Fullscreen**. The menu is the only thing that reaches
past an app holding the pad, which is why those rows are in it and not only on
the `ZL` window layer.

### Game bar

Hiding the bar leaves the screen empty; this is what takes its place. On by
default for that reason, and shown in game mode only:

| Where | What is there |
|---|---|
| Left | **The button that opens the menu** — its own mark and the word *Menu* in one pill, at face-button height |
| Centre | The workspaces, flanked by **the badges of the buttons that walk them** |
| Right | The **face buttons** that are **really bound right now**, and what they do |

Omarchy's 26 px bar could not be read from the couch; this one defaults to
32 px — a row of badges plus a little air. The height is set with
`[gamebar] height` (multiplied by the shell's spacing scale and by
`[ui] game_scale`, so a theme that tightens things tightens the bar too); it never goes below what the badges need,
so a very small number does not clip the bar, it only makes it as tight as it
gets. In everything else it follows Omarchy:

- **The colours** come from `Color.bar.*`, not the menu's — so that changing
  mode reads as the same bar idea changed, rather than as another program
  having taken the screen.
- **Transparency** follows the `bar.transparent` setting in `shell.json` (the
  file is watched live). While transparent it asks Omarchy's own
  `omarchy-bar-text-color` command for the text colour: it looks at the
  wallpaper's pixels along that strip and picks whichever of two colours reads.
  Asking the same question is the only way to get the same answer.
- **The workspaces** are drawn the way `omarchy.workspaces` draws them: 1–5
  always there, the focused one a dot instead of a number, the empty ones
  faded.
- **The badges** share the guide's geometry — so the same button looks the same
  in both places.

**The words are one each.** The bar is glanced at over the top of a game with
three slots to spend; the [guide](#the-bindings-guide) is a page you sit and
read. So the bar prints the verb and stops — *Keyboard*, not *On-screen
keyboard*; *Mute*, not *Mute the microphone*. It is the same meaning said
shorter and never a different one: the word is the binding's own `short` where
it names one, the first word of its `desc` where it does not.

```toml
# "New tab" would cut to "New", so this one says its word itself.
X = { tap = "key:CTRL+T", desc = "New tab", short = "Tab", hold = "key:F5", hold_desc = "Reload" }
```

`hold_short` is the same for the other half, and `[gamebar] brief = false` puts
the guide's full phrase on the bar as well — for a bar read across a room, or a
scheme whose bindings are hard to name in one word.

Two buttons are **never** printed: the ones bound to Enter and Esc
(`[gamebar] omit`). A gesture that means the same wherever you are teaches
nothing by being repeated, and on the shipped scheme that is exactly A and B —
so the moment an application profile takes one of them for something of its
own, it starts being printed.

**And only the half of the pad that changes is printed at all**
(`[gamebar] kinds`, `["face", "stick"]`) — the face buttons and the two stick
clicks, which are exactly the four an application profile has to spend. A
shoulder or a trigger means the same thing wherever the scheme goes — RT
clicks, LB and RB walk the workspaces — so a slot spent on one repeats what the
pad told you the first time you pressed it. Nothing is lost by leaving them off
this row: the two that walk the workspaces are drawn beside the workspaces, and
the one that opens the menu stands on the left. Name the regions you want back
— `kinds = ["face", "stick", "trigger"]`, out of `face`, `bumper`, `trigger`,
`dpad`, `stick`, `system` — and they are offered in the order the thumbs reach
them. Four buttons into three slots means one falls off, thumbs-first, so L3
is it — the cheapest of the four wherever it is spent, and the guide is where
the whole scheme is read.

**Every badge lights up while its button is down** — the pill on the left, the
two beside the workspaces, the hints on the right. The bar is the only thing on
screen in game mode, and on the one surface whose job is to say what the buttons
do, saying which one you just pressed is the same sentence finished. That is
what a `filled` badge does; a `stencil` one inverts instead — see [how the
badges are drawn](#how-the-badges-are-drawn).

**And nothing of ours dims it.** The menu, the guide and the mapping screen
dim the desktop they stand in front of — but the bar is not that desktop.
While one of them is up it is printing what *that* screen's face buttons do,
which is the moment the row is worth the most, so they stop where the bar
starts instead of covering it. It stays as bright, and as clickable, as it is
over a game.

What it says there changes with them, badges and workspaces alike. Inside the
menu the shoulders pick and go back rather than walking workspaces, so **the
workspace strip goes away with the badges that flanked it** — it is drawn
where a button walks it and nowhere else. The same holds for a layer of your
own that spends the shoulders on something else: numbers you cannot step
through are the one thing this bar will not print.

If Omarchy's bar ever comes back **under** omapad's — its flag is a file
anything can flip, and the shell can miss a change to it — the next time
omapad's own bar opens says which one the screen should have, so a mode switch
or a lock and unlock puts it right.

**And you can click them.** Game mode is the couch environment, not a hand-off:
the desktop is still under the bar and the mouse is still on the desk. Clicking
a badge fires exactly the binding the press would — the same layer, the same
profile, the same tap-or-hold — because the click is sent to the daemon
(`omapad ctl press <BUTTON>`) rather than worked out by the bar. A hint that
reads *hold · …* is clicked as a hold; a pointer aimed at a badge is already
deliberate, so it does not re-ask the confirmation a resting thumb has to.

One badge refuses: a button whose binding is itself **a click or a scroll**.
Firing it would click wherever the pointer is — on that badge — so the click
would come straight back and ask for another, and a left click aimed at the bar
reaches the bar rather than the thing you meant to click on. Those badges are
still drawn, and still light up when you press the button.

Only the badges do anything; a click anywhere else on the strip lands on the
bar and stops there, the way it does on a desktop bar's background.
`[gamebar] click = false` turns the strip back into something a click passes
straight through — and the badges still light up under a press.

The bar carries no clock of its own: the day and the time are in the controller
menu's title row (`[menu] clock`). At this end of the bar there is only ever one
thing, and a badge with a caption beside it reads as two.

A button is **never drawn twice** on the bar: the one that opens the menu is on
the left, the ones that walk workspaces are in the centre, and both drop out of
the list on the right.

If the focused window has claimed the shoulders (tabs in a browser, everything
in Steam) the workspace badges are drawn **faded**: they still show the
workspace, just not one press away. The gesture has three phases, and the badge
shows all three:

| Phase | Badge |
|---|---|
| Idle, locked | faded |
| Held | stays put for `confirm_fill_delay_ms`, then **fills in from the left** over what is left of `hold_ms`, coming up to full brightness as it goes |
| **The tick** (the pad rumbles, a notification drops) | **leans** once towards the workspace it will reach and stays there, while the fill **runs back out** over `confirm_ms` — empty at the moment the press fires. Which way is a fact, so it is said once; how much longer is a countdown, so the sweep says it |

The third phase is there because the rumble and the notification happen away
from where you are looking — the badge should say so too. All of it is drawn in
contrast rather than colour: a fixed tone can become unreadable on a bar whose
text colour is picked against the wallpaper.

| Setting | What it decides |
|---|---|
| `[gamebar] confirm_lean` | how far the badge leans at the tick, in the units `height` is 32 of; 0 leaves it where it is and lets the sweep say the whole window. Anything but the two shoulders has no direction to lean in and stays put either way |
| `[gamebar] confirm_fill_delay_ms` | how long the badge sits still before it starts filling, so a shoulder flicked to walk browser tabs does not flash a fill nobody asked for. The wait comes out of the ramp rather than off the end, so the badge is still exactly full at the tick; 0 fills from the press |
| `[gamebar] click` | whether a pointer can fire what a badge names; `false` leaves the bar a readout that swallows no clicks |
| `[gamebar] brief` | one word per hint (the default) or the guide's full phrase; see [the words above](#game-bar) |
| `[gamebar] kinds` | which regions of the pad the hints are about; `["face", "stick"]` — the half that changes under you, and a profile's whole budget |

Both waits themselves are `[confirm] hold_ms` and `[confirm] confirm_ms`, and a
binding takes them by saying `confirm = true` rather than naming its own
numbers.

### Holding, for a hand that cannot

Two seconds of keeping a shoulder down is a gesture some hands cannot make at
all, and others make by accident. Neither is a reason to lose what the hold
reaches, so two numbers say what holding costs — over every hold on the pad
rather than one binding at a time.

| Setting | What it decides |
|---|---|
| `[confirm] scale` | every wait on the pad multiplied together — the two above, a binding's own `hold_ms`, the half-second a plain hold takes. `0.5` halves the lot, `1.5` makes each one more deliberate. Half is the floor because below it a tap and a hold stop being different gestures, double the ceiling because a hold nobody reaches the end of is a binding that has gone. It is also `Controller ▸ Hold time` on the pad, so the person who cannot make the gesture does not have to find a text editor to say so |
| `[confirm] slack_ms` | how long the finger may come off a hold **that has already announced itself** before the countdown is abandoned. Set it to the countdown's own length (`confirm_ms`, 0.8 s) and letting go after the announcement stops cancelling at all: hold until the pad ticks, take your thumb off, and it still fires. Ships `0`, which is the promise the shipped config makes — letting go is how you back out |

The slack starts **at the announcement** and never before it: until then,
letting go is how a tap is made, and a browser tab that waited on a slack
nobody turned on for tabs would be the cost of a setting about something else.
The cancel button still backs out of a countdown with nothing on it.

### A direction held is a distance being crossed

A walk at one speed is most of why a long row is hard to cross: a keyboard page
is fourteen keys wide, and fourteen steps is the same journey however quickly
the fourteenth arrives. So a held direction **closes up** — `repeat_ramp` times
the shipped rate once it has been held for `repeat_ramp_ms`, and no faster
after that. A reversal starts it again, because somebody pushing the other way
has gone too far.

| Where | What it walks |
|---|---|
| `[menu] repeat_ramp` | the D-pad on the menu's grid |
| `[osk] repeat_ramp` | the D-pad on the keyboard, which is the page it matters most on |
| `[traverse] repeat_ramp` | every stick walk on the pad — a window's own controls, and the menu's grid, which takes its rate from there |

`2.5` over a second ships in all three; `1.0` turns it off and every step is
the rate above it again.

### Pages arrive from the side you reached them from

Going into a submenu, walking the bar to the next chip, turning a page of the
bindings guide with a shoulder: the new page **slides in from that side** and
settles, rather than being swapped for the old one where it stood. On the
guide the gesture is literally a direction — L or R — and this is the surface
that says so most clearly.

It is a short move (one rung of the menu's spacing ladder, one column gap on
the guide) over the same 110 ms everything else on these surfaces takes, and
it is motion like any other: at `[ui] motion = 0` the page is simply there.

At most **three actions** stand on the right, and they **do not lie**: they are
the face buttons and stick clicks really bound in the layer that is live right
now, resolved through exactly the path a press takes — `[gamebar] kinds` is what
widens that to the rest of the pad. Gestures that mean the same thing everywhere (confirm,
back) are left unwritten — `[gamebar] omit`. The list is **by
action**, not by button: move Enter to another button and the omission follows
it; give A something else to do and A starts being shown. Hold the window layer
and the hints become that layer's. The menu follows the same rule: if no button
really binds `menu:toggle`, no menu appears on the left. While the pad is handed
to an app the bar withdraws completely: a strip of ours across a running game is
worse than the hints are worth, and most of what it would list does not answer
there anyway.

```toml
[gamebar]
enabled = false             # a game mode with nothing of ours on screen
```

Everything on the bar comes from the base layer; you do not have to bind
anything extra. If the pad is printed LB/RB, those are `L`/`R` in omapad, and
LT/RT are `ZL`/`ZR` — the names follow the profile's family, not the pad's *own
printing*.

This is **the only thing that makes the game layer visible**: discovering what
is in that layer by pressing buttons is exactly what game mode prevents.

### The couch layer

`[bindings.game]` is a **list of differences**, not a restriction: you write
what you want game mode to change about the desktop, and the rest works as it
is. Every button it does not name keeps doing its base-layer job; layers,
profiles and the pointer work exactly as they do anywhere else.

```toml
[bindings.game]
Y = "exec:steam steam://open/bigpicture"
```

It is empty by default, and most of the time that is right. Fill it in and the
guide grows a page for it — the page that shows what it changed.

### Not having to aim: the pointer and snap

The one thing a thumbstick is definitively worse at than a mouse is aiming, and
from the couch it is worse still. Game mode answers that from two sides.

**The pointer becomes a ring.** The desktop's arrow is eleven pixels from across
the room; game mode switches to a cursor theme it draws itself — a ring with a
dot in the middle and a halo underneath. The theme is written under
`~/.local/share/icons` the first time, and switching mode only sends the
compositor one line. On the way out — and at shutdown even if the daemon dies in
game mode — the desktop's own cursor comes back.

**It is drawn in the desktop's own colours.** `color = "auto"` takes the theme's
foreground and `outline = "auto"` its background, read from the same
`colors.toml` the shell reads, so the pointer changes with the theme instead of
being the one white thing on a themed desktop. Any other name is a key out of
that file — `color = "accent"` is a pointer in the theme's accent — and a
`#rrggbb` is used as written. Game mode redraws on the way in, so a theme
changed while omapad runs is the theme the pointer wears.

**Every cursor shape in the theme is the same ring**, deliberately: from the
couch the I-beam over a text field is an unreadable smudge too, and following
one shape that never changes is easier than following the correct shape that
keeps changing.

```toml
[cursor]
enabled = true
apply = "game"           # "always" = for people who use the pad all day long
size = 48                # 32 is an ordinary large pointer, 96 is a target
color = "auto"           # the theme's foreground; "accent", or a #rrggbb
outline = "auto"         # the theme's background, so a pale pointer shows on a
                         # pale window
thickness = 0.085        # the ring's band - all of these are fractions of the
                         # size, not pixels
dot = 0.05               # the dot in the middle; 0 = none
halo = 0.045             # the width of the halo; 0 = none
ring_opacity = 0.75      # how solid the band is; the dot stays solid
shapes = "all"           # "pointer" = only the arrow changes, the rest comes
                         # from the desktop's theme (Inherits= is written into
                         # index.theme)
```

**A press puts the pointer away.** The ring answers where the pointer is, not
whether it should be there at all: it stays wherever it was left, over the menu
that just opened or the window that just moved, and no press moves it out of
the way. A console shows no pointer at all between one thing you point at and
the next.

So the desktop's own answer is borrowed. Hyprland already takes the pointer off
screen at a keystroke and brings it back at the next movement of a mouse
(`cursor:hide_on_key_press`, which Omarchy ships on), and a pad is a keyboard
that does not type — so a press says as much itself, with a keycode no layout
gives a symbol to. The stick brings the pointer back by moving it, and so does
a mouse on the desk, because both halves stay the compositor's. Clicking and
scrolling never hide it: those are the pointer at work.

```toml
[pointer]
hide_on_press = true     # false leaves the ring on screen whatever is pressed
```

**Controller › Hide the pointer** is the same switch from the couch, and
`pad:hide_pointer=toggle` puts it on a button. With
`cursor:hide_on_key_press` turned off in Hyprland nothing here can work, and
`journalctl --user -u omapad` says so once at startup rather than leaving you
looking for the setting that broke.

**A click shows where it landed.** A mouse answers a click three ways — the
finger feels the switch, the hand is on the thing that moved, the arrow sits on
what was hit — and a pad answers none of them: the thumb is on a trigger that
feels the same whatever it did, and the ring looks identical before and after.
So every click the pad makes leaves a burst at the pointer, and the half of the
ring on the side of the button that was pressed is the solid one, so left and
right differ by more than a colour. It is drawn in the theme's own colours like
every other surface, on whichever monitor the pointer is on, and it works in
desktop mode too — the click is just as silent there.

```toml
[ripple]
enabled = true
size = 0                 # the burst's diameter; 0 = twice [cursor] size, so it
                         # reads as leaving the ring rather than beside it
duration_ms = 260        # much longer and a double click draws over itself
thickness = 0.09         # the ring's band, a fraction of the size
```

`omapad ctl ripple left` draws one without clicking, which is what tuning those
two numbers wants.

**Snap teleports the pointer instead of walking it.** `snap:right` puts the
pointer in the middle of the window to the right and focuses it:

```toml
[bindings.window]
DPAD_UP    = "snap:up"
DPAD_DOWN  = "snap:down"
DPAD_LEFT  = "snap:left"
DPAD_RIGHT = "snap:right"
```

How the choice is made is configurable too: `[snap] bias` says how much more
expensive a window off to the side is than one straight ahead (below 1 the
nearest window wins whichever way you press, very high and only the perfectly
aligned one is reachable), `focus` whether it takes focus, `same_monitor`
whether it may cross to the other screen, `rumble` whether the pad ticks when it
lands.

You can give a whole stick to it as well — a stick in the `snap` role is a
*throw*: push it all the way and one window is jumped, and there is no second
jump until it comes back (the same hysteresis the triggers use).

```toml
[pointer]
right_stick = "snap"
```

**Windows, not buttons.** The only thing that knows where a button on screen is
is the accessibility bus (AT-SPI); under Wayland it reports every widget at
screen coordinate 0,0, and browsers, games and terminals do not join it at all.
Hyprland, on the other hand, knows exactly where every window is — which is why
that is the layer snap can be right about. Aiming *inside* a window is the next
section's job.

### How fast a thumb is, and the wheel's ramp

The pointer's speed and the wheel's are the two settings nobody can pick for
you: they depend on the pad, on the screen, and on how far away the sofa is. So
they are also the two the pad can change about itself — **Controller › Sticks**
in the menu, or `pad:pointer_speed=up` and `pad:scroll_speed=down` on a button.
Each is a bar there: A takes it and left and right walk it, faster the longer
you hold a direction, and either trigger sweeps its whole range in about a
second and a half whether you have taken it or not. The bar says where the
number is and where the ends are, the pointer keeps moving under the open menu,
and the motor ticks once when you reach an end — so you set them by feel. A
keeps what you land on and writes it to `settings.toml`; **B puts it back**.

```toml
[pointer]
speed = 1100.0      # pixels per second at full deflection
accel = 2.2         # the response curve: 1.0 linear, higher = finer near centre
left_deadzone = 0.10   # how much of each stick's travel does nothing
right_deadzone = 0.18  # wider, because the right one ships scrolling

[scroll]
speed = 8.0         # wheel notches per second at full deflection
accel = 2.0         # the same curve, for the wheel
ramp = 3.0          # …and how much faster a stick held one way gets
ramp_ms = 900       # after this long holding it. 1.0 = off
natural = false     # true inverts the direction
```

**How much of a stick does nothing** is the same argument at the other end of
its travel, so the pad sets that too — two more bars on **Controller ›
Sticks**, and under them **a dial per stick**. The dial is the answer to the
question a number cannot give you: it shows the dead zone as a shaded disc and
puts a dot where the thumb actually is, **dim while the stick is being
swallowed and lit the moment it is not**. Rest your hand on the pad and watch
which way the dot creeps; push slowly and the moment it lights is the edge you
have set. `pad:left_deadzone=up` and `pad:right_deadzone=down` do the same
from a button.

The dial is the one thing in omapad that draws at frame rate, and it does so
**only while it is the tile you are on** — the menu stops the moment you move
off it. Widen one
when an untouched stick still creeps the pointer along; a worn pad rests a
percent or two off centre. Narrow it when small corrections are swallowed and
aiming feels like it starts late. A pointer that bolts for a corner rather than
creeping is a different fault — the pad is lying about where its sticks rest,
and `recenter` is what answers it.

**One zone per stick, not per job.** The slop is in the hardware, so the right
stick carries the same number whether it is scrolling the desktop or walking a
game's controls in game mode — you fix the stick you are complaining about
rather than looking up what it is currently doing. It ships wider than the left
because it ships scrolling, where a page sliding away under a thumb that never
asked costs more than a notch that arrives late; hand it `right_stick =
"cursor"` and it is worth bringing down to the left one's. A config written
against the old per-job keys (`deadzone` under `[pointer]` and `[scroll]`) is
still read, each for the stick that ships in its role.

Two different things get called acceleration and `[scroll]` has both. `accel` is
the **response curve** — how far the stick is over, into how fast it goes.
`ramp` is **time**: a page is long and a thumb is not, so a stick held one way
keeps getting faster until it is `ramp` times the speed above. Letting go hands
the speed straight back, and so does reversing — a reversal is somebody who has
gone too far, and the speed they overshot at is the last thing they want. A
sideways wobble is not a reversal: the ramp watches the direction the stick is
mostly pushed in, not both axes, because a thumb pushed straight down wanders.

### Inside the window: focus traversal

Snap brings the pointer to the right window; nobody outside that window knows
where the button in it is. But **every toolkit already answers Tab and the arrow
keys correctly** — because it is the one that knows. So omapad asks instead of
aiming: `focus:next` sends Tab, and the application moves its own focus ring.

```toml
[traverse]
next = "TAB"
prev = "SHIFT+TAB"
activate = "SPACE"   # not Enter: the key that presses the focused button is Space
back = "ESC"
```

Which key sends what is written here rather than in the code, because the answer
is not the same everywhere — a list wants an arrow key, a form wants Tab — and
an application that does not play along can be given a profile of its own.

**This is on by default in game mode**, and it costs no button at all: the right
stick is the wheel on the desktop and the focus walker in game mode.

```toml
[mode]
left_stick = ""        # empty = the same as on the desktop; a pointer is a pointer
right_stick = "focus"  # write "scroll" and the wheel comes back
```

The stick is not one shot like `snap` but a **direction**: hold it pushed and it
walks (first `repeat_delay_ms`, then `repeat_rate_ms`, closing up to
`repeat_ramp` times that rate once it has been held for `repeat_ramp_ms` —
see [below](#a-direction-held-is-a-distance-being-crossed)). The only thing you lose
is scrolling, and you get that back because focus scrolls itself into view
anyway — everywhere except a browser, which scrolls whatever holds the keyboard
focus rather than what the pointer is over, so the page carries on scrolling
where you first clicked while the cursor sits somewhere else. The shipped
`[profile.browser]` therefore hands that one application its wheel back; see
[Application profiles](#application-profiles).

Which direction means what is yours too: by default the horizontal axis is the
Tab order and the vertical axis the arrow keys — but walking a vertical list
with Tab is every bit as common, so it is not assumed, it is written:

```toml
[traverse.stick]
left = "prev"
right = "next"
up = "up"        # write "prev" and the vertical axis walks the Tab order
down = "down"    # leave it empty and that direction is off
```

It can be bound as a layer too (`[layers.traverse]` plus `focus:*` bindings),
but that is not the default: **a layer trigger eats a button outright.**
`layer_for_button` is checked before every binding, so the button that opens the
layer has no job of its own in any layer or any profile. Even X, the cheapest
candidate on this pad, would have taken float/tile out of the window layer and
`Ctrl+T` out of the browser. The stick takes nothing.

> Chromium has a mode that makes the arrow keys jump to the nearest control; on
> a web page `focus:up|down|left|right` wants exactly that. It is off by
> default: `chromium --enable-features=SpatialNavigation`.

## The default bindings

A console-shaped scheme: **A** confirms, **B** goes back, **X** does the thing
in front of you and **Y** reaches for what is not on screen; **ZR** clicks. The
window layer opens while **ZL** (the left trigger) is held. Those four meanings
hold in every layer and every application —
[what each button means](#the-face-buttons-mean-the-same-thing-everywhere).

| Button | Base | ZL held (window) |
|---|---|---|
| Left stick | pointer | resize the window |
| Right stick | scroll (in game mode: **walk focus**) | move a floating window, **swap** a tiled one with its neighbour |
| A | Enter / confirm | fullscreen |
| B | Esc / back | close the window — in a terminal, **interrupt** what it is running first |
| X | middle click | float/tile |
| Y | **right click** | take the window out (float+pin) |
| ZR | left click | – |
| ZL | **window layer (hold)** | – |
| L / R | previous / next workspace (the pad ticks) | move the window to the previous / next workspace |
| D-pad | arrow keys | window focus (by direction) |
| PLUS | tap: **the controller menu**, hold: the Omarchy menu | toggle split |
| MINUS | tap: **the on-screen keyboard**, hold: **push to talk** | – |
| MINUS + PLUS | **the controller menu** (a chord, everywhere, and the only way in over a game) | – |
| ZL + B, ZR + B | **the workspace lock** — a chord, and only over an app that already has the pad | – |
| HOME | tap: switch window, hold: **switch mode** | centre the window |
| Left stick click | middle click | pin the window |
| Right stick click | back (mouse 4) | the on-screen keyboard |
| Capture* | tap: screenshot, hold: region | screen recording |

\* The Capture button only exists in NS mode (see below).

**Moving a window with the right stick** means two different things, and the
stick works out which one it is holding. A **floating** window is dragged where
you point; a **tiled** one changes places with the window that way — one
neighbour per push, so a stick held over does not walk the layout apart. That is
Hyprland having two verbs rather than a mood: `movewindow` ignores a tiled
window and `swapwindow` a floating one, and a stick that only knew the first
looked dead in the layout most windows are actually in. `[swap] flick` and
`release` are how hard the push has to be; `right_stick = "swap"` under
`[layers.window]` keeps the tiled half alone.

**Why the modifier is on a trigger:** inside the window layer the left thumb is
on the D-pad and the right one on A/B/X/Y — so the modifier has to be held by a
finger that is **not a thumb**. That leaves the shoulders and the triggers; the
shoulders walk workspaces and that is not worth giving up. Right click sits on
**Y**, and **MINUS** carries the on-screen keyboard on its own.

**Note:** because ZL is the window layer's trigger it runs no binding of its own
here; while the window layer is open **L** and **R** move the focused window to
the previous / next workspace.
**L** and **R** walk the previous / next workspace on the base layer. The one
exception is the [keyboard layer](#the-keyboard-layer): while the keyboard is up
ZL becomes Shift, because an open surface's own binding outranks the layer
trigger.
Volume and playback are in the [menu](#the-menu) rather than on a layer of their
own. Edit `[bindings.base]`, `[layers.window]`, `[bindings.menu]` and
`[bindings.osk]` to bend the scheme to your own taste.

While the menu or the on-screen keyboard is up a separate layer takes over —
[The menu](#the-menu), [Typing](#typing).

### The face buttons mean the same thing everywhere

The scheme above is not four arbitrary choices repeated in each layer. Someone
who has used the pad for a week presses **A** without deciding to, and that
reflex is the only thing this project has instead of labels on the buttons. So
each face button carries one meaning, and it holds in every layer, on every
surface and in every application:

| Button | Means | On the desktop | In the menu | In the keyboard | In a browser |
|---|---|---|---|---|---|
| **A** | **confirm** — enter, activate, open what is selected | Enter | pick the row | press the key | Enter |
| **B** | **back** — escape, cancel, up one level, out | Esc | up one level | close the keyboard | Esc |
| **X** | **do** — the app's own verb, the thing you press most often | middle click | leave the menu outright | Backspace | new tab |
| **Y** | **reach** — for something not on screen: a menu, a switcher, another view | right click | the bindings guide | Space | right click |

**A and B are not ours to move.** They are the console standard, and an
application profile may only take them when the thing it needs is not reachable
on screen at all — and then it keeps Enter and Esc on the *hold*.
[Discord](#discord-the-face-buttons-are-the-voice-controls) is the one shipped
profile that does: its mute and deafen buttons sit in a thumbnail-sized strip
in the corner of the screen furthest from wherever you are aiming.

**X and Y are the application's**, and the split follows the thumb: X is nearer
where a thumb rests than Y, so the button pressed more often is X. That is why
`Ctrl+T` is on X in a browser and Backspace is on X in a terminal, while the
context menu, the quick switcher and the window popped out are all on Y. Where
an app has no reach worth having — a terminal's right-click menu is two entries
in kitty and nothing at all in foot — Y carries a second verb instead.

**A meaning never moves between two places you cross.** Backspace is X on the
on-screen keyboard, so Backspace is X in a terminal too: those are the two
surfaces a command is typed across, and a key that moved under your thumb when
the keyboard opened over the prompt would be worse than no key at all.

When you write your own bindings, the same four questions are the whole method
— what can a pointer not reach, what is the verb, what is the reach, and does
the app already own L or R. The rules, and the ledger of where the shipped
config bends one, are in
[`docs/conventions/bindings.md`](docs/conventions/bindings.md).

## Controller modes

Pads like the Beitong KP20/KP40 change identity when their hardware mode
changes:

| Pad mode | Name to the kernel | VID:PID | ZL/ZR |
|---|---|---|---|
| NS | `BEITONG BTP-KP20 NS` | `057E:2009` | digital buttons |
| XInput | `Beitong KP20A/KP40A Controller` | `20BC:5127` | **analog axes** |

`profile = "auto"` detects this at connect time, so you do not have to change
the config. In XInput mode the analog triggers are turned into buttons with a
threshold (and hysteresis), so a trigger resting half-pressed does not make a
layer flicker.

Careful: the logical names follow the pad's *own labels*. On a Nintendo pad A is
the button on the right, on an Xbox one it is the bottom button — so changing
mode drops "A = left click" onto a different physical button.

And these two things are independent: omapad names the buttons **by what is
printed on the pad**, but picks the profile **from the identity the driver
reports**. A pad can send Switch Pro codes while carrying Xbox letters on its
shell — the Beitong KP20's NS mode does exactly that — and then every face
button answers to its neighbour's name: press X and you get a right click. The
profile cannot know this, because the driver does not say what is printed on the
shell.

The answer is not to guess but to measure: the [mapping
screen](#controller-mapping) asks for the buttons one by one and writes down the
code that arrives.

### Which console the badges are printed for

The profile says what a button *is*. Which console's printing the badges carry
is a separate setting, because it is a separate question:

```toml
[device]
layout = "auto"     # nintendo | xbox | playstation
```

| Layout | Face | Shoulders | The small ones |
|---|---|---|---|
| `nintendo` | A B X Y | L R ZL ZR | − + Home Capture |
| `xbox` | A B X Y | LB RB LT RT | View Menu Guide Share |
| `playstation` | ✕ ○ □ △ | L1 R1 L2 R2 | Create Options PS Mute |

Every one of those is **drawn** rather than typed — the PlayStation symbols and
each console's small buttons are shapes in `assets/shapes/`, set into the same
face circle the letters are set into and into the small button the pad actually
has - round for all of them but PlayStation's Create and Options, which are the
only oblong ones, and the Xbox button drawn larger than the rest because it is
the one button a pad draws larger than everything else on it. Nothing on a
badge is a character the font happened to have.

`auto` follows the profile, which is right for the two the driver can tell
apart. A PlayStation pad reports itself as an XInput device, so `auto` lands on
`xbox` and prints letters on a pad that has shapes on it — that is the one worth
setting by hand. Setting it to a pad you are not holding is the way to get this
wrong: the face symbols land in the wrong corners, for the same reason the
profiles do.

`omapad check` prints which one is in effect, and **Controller › Button
labels** in the menu changes it without a config file or a restart — every
badge on every surface follows at once.

### How the badges are drawn

What a badge prints is one question. Whether it is a shape with a label set on
it, or a label punched out of a solid shape, is another:

```toml
[ui]
badge_style = "filled"   # filled | stencil
```

| Style | The badge | What a press does to it on the bar |
|---|---|---|
| `filled` | the shape washed in the surface's own colour, the label solid on top | it brightens |
| `stencil` | that colour at full strength, the label the hole in it | it inverts — the fill drains out and the label fills in |

`filled` is the quiet one, and the default. `stencil` is the one for a sofa: a
solid shape carries about twice as far as a washed one, and a badge that turns
inside out under your thumb is a change you catch out of the corner of your
eye rather than one you have to be watching for. A shape already at full
strength has nowhere brighter to go, which is why the two press differently
rather than one borrowing the other's answer.

It is the same drawing either way — nothing in `assets/shapes/` knows which
style is on — so a button looks like the same button in both, and each surface
keeps its own colour: the accent on the guide and the mapping screen, the
bar's own text colour on the bar, the key's colour on the keyboard. The one
exception is the menu's legend: it is the bar's row — the same kind of words
in the bar's band, while the bar itself is down — so it wears the bar's colour
and the bar's resting fills rather than the menu's.

The label is a **hole**, not a letter painted the colour of the background. A
badge sits over a wallpaper, over a card that fades, and on the keyboard over
a key that inverts under it when the selection lands — a faked background is
right on one of those and wrong on the other two.

**Controller › Button style** changes it from the menu, and every surface that
is already up redraws at the press rather than at the next heartbeat.

## Configuration

`~/.config/omapad/config.toml`. Everything you do not write falls back to the
shipped default, so write only what you want changed:

```toml
[pointer]
speed = 1400.0        # a faster pointer

[bindings.base]
Y = "key:SUPER+SPACE" # let Y open the Omarchy menu now
X = "nop"             # turn X off entirely
```

After a change: `systemctl --user restart omapad`

A restart does **not kill** the applications you opened from the menu or from a
binding: `exec:` commands are put in a transient unit of their own with
`systemd-run --user --scope`. Otherwise they would stay in the daemon's cgroup,
and systemd's default `KillMode=control-group` would SIGTERM all of them on
restart — so every config change would close your Steam.

### The action grammar

| Form | What it does |
|---|---|
| `click:left\|right\|middle\|back\|forward` | a mouse button — held down, so dragging works |
| `key:SUPER+RETURN` | a virtual keyboard chord; held down, and follows the compositor's repeat setting |
| `scroll:up\|down\|left\|right` | the wheel, repeating while held |
| `hypr:hl.dsp.focus({ workspace = 'e+1' })` | Hyprland IPC |
| `exec:omarchy-menu toggle` | run a command |
| `osk:toggle\|open\|close\|up\|down\|left\|right\|press` | the on-screen keyboard |
| `osk:shift\|ctrl\|alt` | latch a modifier for the next key |
| `osk:caps` | toggle Caps Lock (the labels grow too) |
| `osk:hold:shift\|ctrl\|alt` | hold a modifier for as long as the button is down |
| `osk:submit` | press Enter, then put the keyboard away |
| `osk:dictate` | start dictation, or stop it — what the microphone key does |
| `osk:talk` | push to talk: the microphone is open while the button is held |
| `menu:toggle\|open\|close\|up\|down\|press\|back` | the controller menu |
| `guide:toggle\|open\|close` | the bindings guide |
| `guide:next\|prev` | turn the guide's page |
| `mode:toggle\|desktop\|game` | switch mode |
| `lock:on\|off\|toggle` | the workspace lock — the pad is the app in front's, outright |
| `keep:on\|off\|toggle` | the same question the other way — the pad is ours over an app that opened it and is not being played with |
| `pad:profile=auto\|nintendo_pro\|xbox` | which codes this pad is read with |
| `pad:layout=auto\|nintendo\|xbox\|playstation` | which console's names the badges print |
| `pad:rumble=on\|off\|toggle` | the motor |
| `pad:rumble_strength=up\|down\|<0..1>` | how hard it ticks |
| `pad:pointer_speed=up\|down\|<200..4000>` | how fast the pointer aims |
| `pad:hide_pointer=on\|off\|toggle` | whether a press that is not aiming puts the pointer away |
| `pad:scroll_speed=up\|down\|<1..40>` | how fast the wheel turns |
| `pad:left_deadzone=up\|down\|<0..0.5>` | how much of the left stick does nothing |
| `pad:right_deadzone=up\|down\|<0..0.5>` | the same, for the right one |
| `pad:dictate_clipboard=on\|off\|toggle` | whether dictation lands on the clipboard instead of at the cursor |
| `live:volume=up\|down\|<0..1>` | how loud the machine is — the twin of `pad:`, for what the machine holds rather than what omapad does |
| `live:mute=on\|off\|toggle` | the speakers |
| `live:brightness=up\|down\|<0..1>` | how bright the screen in front is |
| `live:media=playPause\|next\|previous` | what is playing |
| `snap:left\|right\|up\|down` | move the pointer to the window that way and focus it |
| `snap:centre` | put the pointer in the middle of the window in front |
| `focus:next\|prev` | walk the application's own controls (Tab / Shift+Tab) |
| `focus:up\|down\|left\|right` | the same, with the arrow keys |
| `focus:activate\|back` | press the focused control / step back out |
| `term:interrupt` | the window layer's close, asked of the terminal first — `Ctrl+C` while a command is running, the close where there is none. Both halves are `[terminal]` settings |
| `nop` | cancel an inherited binding |

Every `pad:` value also takes `next` / `prev`, which steps through what that
setting holds — so one button can walk what the menu offers as a list of rows.
What is chosen from the pad is written to `~/.config/omapad/settings.toml`
and wins over `config.toml` until you delete it; see [the Controller
menu](#the-controller-submenu). A page you rearrange lands in
`layout.toml` beside it, and works the same way.

`hypr:` values are written as **Lua**. This Hyprland routes `dispatch` through
Lua; the old `workspace e+1` syntax no longer works. The spelling is exactly the
one in `~/.config/hypr/bindings.lua`, and the list of valid dispatchers is in
`/usr/share/hypr/stubs/hl.meta.lua`.

To tell a tap from a hold:

```toml
[bindings.base]
PLUS = { tap = "exec:omarchy-menu toggle", hold = "mode:toggle", hold_ms = 500 }
```

Everything a binding table can say:

| Key | What it decides |
|---|---|
| `tap` · `hold` | the two halves. A table with no `hold` fires on the way down, exactly like the plain string it replaces |
| `hold_ms` | how long the hold waits — 500 ms by default, 1200 for an announced one. Every one of them is multiplied by [`[confirm] scale`](#holding-for-a-hand-that-cannot), which is how a hand that cannot hold says so once rather than binding by binding |
| `confirm` · `confirm_ms` | an **announced** hold: at `hold_ms` it ticks and says what is coming, and only `confirm_ms` later does it fire. `confirm = true` takes both numbers from `[confirm]` |
| `desc` · `hold_desc` | what the [guide](#the-bindings-guide) prints for each half |
| `short` · `hold_short` | what the [game bar](#game-bar) prints — one word |
| `on_release` | fire the tap when the button comes back up, so the same button can grow a hold later without its tap having already gone out |
| `rumble` | tick the motor when this one fires |
| `reaches_past` | whether it still fires while the pad has been handed to an app |

Which button to spend on what is a question of its own —
[what each button means](#the-face-buttons-mean-the-same-thing-everywhere).

### Chords: two buttons at once

```toml
[chords]
"MINUS+PLUS" = "menu:toggle"
"ZL+B" = "lock:on"
"ZR+B" = "lock:on"
```

A chord **takes the press outright**: neither button does its own job, and a
layer trigger inside one does not open its layer. Which button goes down first
does not matter — "at the same time" arrives as two separate events, and no
finger decides their order.

The price is this: a button named in a chord fires **on the way up, not on the
way down**. Whether it is a chord or a press of its own cannot be known until
its partner has had its chance to go down. An imperceptible delay, but a chord
button is a bad place for dragging (a click held down).

Chords are bound **everywhere**, not to a layer. The reason is the first chord
that ships: over an app that has taken the pad it is the only way in, and that
has to work wherever you are. A chord is also the one gesture that **always
reaches past** an app holding the pad, whatever it runs — two buttons at once
is not an input any game asks you for.

The other two are [the workspace lock](#the-workspace-lock), and they are the
exception to the price above: a chord whose action can do nothing right now does not take
the press, so `ZL` and `ZR` keep the window layer and the held left click on
the desktop, where the lock has nothing to lock.

### Adding a layer

```toml
[layers.apps]
button = "PLUS"
left_stick = "none"       # cursor | scroll | resize | move | swap | none
right_stick = "none"
fallthrough = false       # true: unbound buttons fall back to the base layer

[bindings.apps]
A = "exec:omarchy-launch-terminal"
B = "exec:omarchy-launch-browser"
```

### Application profiles

You may want the same button to do something else depending on which
application has focus: `Paste` really pasting in a terminal, the right trigger
taking a screenshot in a browser. A `[profile.<name>]` section matches focus by
the window **class** and
lays its own `[bindings]` over the defaults. The match is a case-insensitive
substring (`"foot"` catches both `foot` and most natural names like
`Alacritty`; `match` can be a list too, so that any one of them is enough).

```toml
[profile.shell]
match = ["alacritty", "foot", "wezterm"]
right_stick = "scroll"      # the wheel, even where game mode walks the focus

[profile.shell.bindings]
X = "key:BACKSPACE"         # the letter back, in a terminal only
LSTICK = "key:CTRL+L"

[profile.browser]
match = "chromium"

[profile.browser.bindings]
ZR = "exec:omarchy-capture-screenshot"
```

Profiles behave in three ways:

- **They change only the buttons you name.** A button the profile does not bind
  is resolved through the ordinary `profile → layer → base` chain, so walking
  workspaces and the arrow keys keep working. A button you write `nop` on does
  nothing at all.
- **They stop where a modifier starts.** The bindings are the app's scheme *at
  rest*: hold **ZL** and the window layer is the desktop's again, so `ZL` + `B`
  closes the window in every application whatever `B` is worth in the one in
  front. An app that really does want a window op of its own says which layer —
  `[profile.<app>.window]` is read in `[bindings.window]`'s place while that
  app has focus — and nothing that ships does.
- **They do not fight the surfaces on screen.** While the keyboard, the menu or
  the guide is up, those always win — what you can see outranks the application
  underneath. A profile touches none of those three surfaces.

A profile may also refuse the hand-off, with `handover = false`. The pad is
normally given to the focused application when that application has opened it,
which is right for anything you open a pad *to play*; it is wrong for one that
opens a pad for some other reason, and `/proc` cannot tell those apart. Discord
polls the Gamepad API for its own keybinds, so this is what keeps the pointer
alive in it. Do not write it on anything you play through — a game with this on
is a game the pad never reaches.

A profile may also say what a **stick** is for, with the same `left_stick` /
`right_stick` roles a layer takes (`cursor`, `scroll`, `resize`, `move`, `snap`,
`focus`, `swap`, `none`). It has the last word at rest and in game mode, on the same
layers its bindings reach — while **ZL** is held both sticks belong to the
window, whatever the app says; leave it out and both thumbs keep whatever the
layer gives them. This is what the shipped browser profile uses: game mode gives
the right stick to `focus`, and a browser is the one place that answers those
keys somewhere other than under the pointer.

The daemon swaps the profile as focus moves; which one is active shows up in
`journalctl --user -u omapad`. With an unmatched window in front there is no
profile and the plain base behaviour applies. If a profile could match more than
one class (say `foot` and `foot-server`), the one declared **first** wins — so
write the more specific one first. A bad binding is caught immediately by
`omapad check`.

### The keyboard page an application lends it

Alongside button bindings, a profile can lend the on-screen keyboard **a page of
its own**. The page joins the cycle L/R already walks — `abc`, `&123`, `Fn`,
then this — and drops out of it when the window it belongs to leaves the front.
Every key on the page types **a whole piece of text**, so running the command is
left to ZR (the key that presses Enter and puts the keyboard away).

The page the terminal profile ships with is this:

```toml
[profile.shell]
match = ["foot", "alacritty", "ghostty", "kitty", "wezterm"]

[profile.shell.osk]
label = "Term"                 # the name the page-turn cell prints
keys = [
  { label = "Paste", action = "CTRL+SHIFT+V" },
  "git status",
  "sudo pacman -Syu",
]
from = "tac ~/.bash_history | awk '!/^#/ && length > 2 && length < 60 && !seen[$0]++' | head -8"
ttl = 10                       # how many seconds the output counts as fresh
limit = 8                      # how many entries the page takes at most
```

Both sources are optional, and `keys` is drawn first:

| Field | What it does |
|---|---|
| `keys` | Entries you wrote by hand and want up front. A plain string, or `{ label = "...", text = "..." }` |
| `from` | A shell command each line of whose output is one entry |
| `label` | The page's name; the profile's name if you leave it out |
| `ttl` | How long (s) `from`'s output is used without asking again |
| `limit` | How many entries the two make between them at most |

A `keys` entry can carry an **`action`** instead of `text`; then it sends a
**chord** rather than typing text, spelled the way `[osk.keys]` spells one.
Exactly for "this one key has to be something else in this application":
`Paste` on the bottom row types `Ctrl+V` — right everywhere outside a terminal —
and the terminal's own paste lives on this page. An `action` that does not parse
is named by `omapad check`, along with the profile it is in.

Thanks to `from` the daemon **has to know no shell at all**: which history file,
bash or atuin — all of it stays in the config. The command runs every time the
keyboard opens (and if `ttl` has expired), not every time focus changes.

The page holds **four rows**: a short entry shares a row, a long one takes a row
to itself, and an entry that does not fit is not drawn. A character with no
equivalent in the active XKB layout is not typed — a command left half-written
is easier to spot than one with a wrong letter in the middle.

> **bash only writes its history when the shell closes.** So the command you
> just typed in the terminal in front of you is not in the file yet. One line in
> `~/.bashrc` fixes that:
>
> ```bash
> PROMPT_COMMAND='history -a'
> ```
>
> With atuin or zsh only the command changes:
>
> ```toml
> from = "atuin history list --reverse --format '{command}' | head -8"
> ```

#### The browser's page: `Web`

The browser gets one too, and it is a different kind of page — a terminal's is
the commands you have already run, a browser's is **the address bar**, which is
the one string on this desktop that has to be typed exactly and the one a
thumbstick is worst at:

```toml
[profile.browser.osk]
label = "Web"
keys = [
  { label = "Address bar", action = "CTRL+L" },
  "https://",
  { label = "Go .com", action = "CTRL+ENTER" },
  { label = "Find", action = "CTRL+F" },
  { label = "Search tabs", action = "CTRL+SHIFT+A" },
  { label = "Reopen tab", action = "CTRL+SHIFT+T" },
  { label = "Zoom −", action = "CTRL+MINUS" },
  { label = "Zoom +", action = "CTRL+EQUAL" },
]
```

| Key | What it does |
|---|---|
| `Address bar` | `Ctrl+L` — puts the caret where you are about to type, without aiming at it |
| `https://` | types the prefix the omnibox does not guess once what follows is not a plain domain |
| `Go .com` | `Ctrl+Enter` — wraps what you typed in `www.`/`.com` and opens it, so a domain is the few letters in the middle |
| `Find` | `Ctrl+F` — find in the page, which is typed at anyway |
| `Search tabs` | `Ctrl+Shift+A` — Chromium's tab search: type part of a title, Enter to jump |
| `Reopen tab` | `Ctrl+Shift+T` — the one-key undo of a mis-click |
| `Zoom −` / `Zoom +` | `Ctrl+-` / `Ctrl+=` — a page written for a desk, read from a sofa |

Four rows is the whole page, so those eight are all of it. What did not fit, if
you would rather have one of them: bookmark (`Ctrl+D`), history (`Ctrl+H`),
downloads (`Ctrl+J`), close the tab (`Ctrl+W`), full screen (`F11`), reset the
zoom (`Ctrl+0`), a private window (`Ctrl+Shift+N`).

These are **Chromium's** shortcuts, which is what the profile's `match` names.
Firefox reads `Ctrl+Shift+A` as its add-on manager rather than tab search, so a
Firefox profile wants a page of its own.

#### Discord's page: `Chat`

A chat app is typed at, and typing is the one thing a thumbstick cannot do
quickly. So half of this page is **the sentences you send without meaning
anything by them** — three keys instead of nine aimed letters, which is what
most of a couch conversation actually is:

```toml
[profile.discord.osk]
label = "Chat"
keys = [
  "brb",
  "omw",
  "gg",
  { label = "Search", action = "CTRL+F" },
  { label = "Emoji", action = "CTRL+E" },
  { label = "GIF", action = "CTRL+G" },
  { label = "Mark read", action = "SHIFT+ESC" },
  { label = "Pins", action = "CTRL+P" },
]
```

| Key | What it does |
|---|---|
| `brb` / `omw` / `gg` | typed whole; `ZR` sends them and puts the keyboard away |
| `Search` | `Ctrl+F` — search the messages, which is typed at anyway |
| `Emoji` / `GIF` | `Ctrl+E` / `Ctrl+G` — both pickers are searched by name, so the keyboard is already open |
| `Mark read` | `Shift+Esc` — marks the whole server read: the one-key answer to a wall of bold channels |
| `Pins` | `Ctrl+P` — the pinned messages, where the link somebody left you is |

The quick switcher is not on the page: it is on `X`, where it costs no page
turn. Four rows is the whole page, so those eight are all of it. What did not
fit: the sticker picker (`Ctrl+S`), the inbox (`Ctrl+I`), uploading a file
(`Ctrl+Shift+U`), editing the message you last sent (`↑`, which the D-pad
already sends) and the previous / next unread channel
(`Alt+Shift+↑` / `Alt+Shift+↓`).

### Per-application profiles and the shoulder buttons

[Application profiles](#application-profiles) above says how a profile is
matched and what it may reach. This is what the shipped browser profile does
with the shoulders, and why.

```toml
[profile.browser]
match = ["chromium", "chrome", "brave", "vivaldi"]

[profile.browser.bindings]
X = { tap = "key:CTRL+T", desc = "New tab", hold = "key:F5", hold_desc = "Reload", hold_ms = 500 }
R = { tap = "key:CTRL+TAB", desc = "Next tab",
      hold = "hypr:hl.dsp.focus({ workspace = 'r+1' })",
      hold_desc = "Next workspace", hold_ms = 2000, confirm_ms = 2000 }
```

None of it reaches the window layer: hold **ZL** in a browser and the left
stick still pins the window, the right stick click is still the keyboard, and
`ZL` + `X` is still float / tile. What a profile spends, it spends at rest.

The buttons of the `browser` profile that ships:

| Button | In a browser | Otherwise |
|---|---|---|
| L / R | previous / next tab | previous / next workspace |
| L / R **held** | workspace (confirmed, see below) | – |
| X | **new tab** (`Ctrl+T`) | middle click |
| X **held** | **reload the page** (`F5`) | – |
| Right stick click | **back** (`Alt+←`) | back (mouse 4) |
| Left stick click | **forward** (`Alt+→`) | middle click |

There were three free buttons for four jobs, so the two that belong to the page
share one: a new tab is frequent, a reload rare, and both are about the tab in
front of you. What that costs inside a browser: the middle click (which stood on
X and on the left stick click, twice) is gone. The right stick click already
went back with mouse 4, and now it no longer depends on the application knowing
that button. Left click (ZR), right click (Y), Enter (A), Esc (B), the arrows
(D-pad), the keyboard (MINUS) and the menu (PLUS) all stay as they are.

What the buttons ran out of room for is on the keyboard instead: with a browser
focused the keyboard grows a `Web` page — the address bar, `https://`, `.com`,
find, tab search, reopen a tab and zoom — see [the browser's page](#the-browsers-page-web).

The shoulders are the pilot's real subject: L and R are the browser's own tab
switcher as much as they are our workspace switcher. So with a browser focused
**a short press belongs to the application**, and a workspace only to a
deliberate **hold**:

| | What happens |
|---|---|
| Short press (on release) | previous / next tab |
| Held for 2 s | the pad ticks + a notification: *"Next workspace — B to cancel"* |
| Held 2 s more | the workspace changes |
| Letting go in between | nothing happens — not even the tab changes |
| **B** in between | cancel, and B does not do its own job (Esc) |

Letting go cancelling too is what makes an over-long short press harmless: pull
your finger back and neither the workspace nor the tab changes. **B** is the way
out without waiting; which button that is is set by `[confirm] cancel_button`.

Everywhere without a profile the shoulders plainly change the workspace — but
now **on release**, not on the way down (`on_release = true`). That way the same
button can gain a hold in a profile without its tap having already gone out.

`confirm_ms` belongs to a binding: it cannot be written without a `hold`, and
`hold_desc` is the text that appears in the notification.

### The file manager: B goes up a directory

The same mechanism, one line of it. A file manager is walked into folders and
back out of them, and the way back out is the one thing a pad has no button
for — while `B`, its Esc, is a key a file manager does nothing with. So with
one focused, `B` goes **up one directory** instead:

```toml
[profile.files]
match = ["nautilus", "thunar", "nemo", "dolphin", "pcmanfm"]

[profile.files.bindings]
B = { tap = "key:ALT+UP", desc = "Up one directory" }
```

`Alt+↑` is the shortcut every desktop file manager agrees on, so the one
binding covers all five names — add yours to `match` if it is not there. Every
other button is untouched: the arrows walk the listing, `A` opens what is
selected, `Y` is the right click that gets you the context menu.

### Discord: the face buttons are the voice controls

Discord is the one application whose most-pressed controls are **not on screen
where a pointer can reach them**. Mute and deafen sit in a strip the size of a
thumbnail, in the corner furthest from wherever you are aiming — from a sofa
the worst target on the desktop, and the one you have to hit mid-sentence. So
with Discord focused the four face buttons stop being the console scheme and
become the voice panel:

```toml
[profile.discord]
match = ["discord", "vesktop", "webcord", "legcord", "armcord"]
handover = false   # it opens the pad for its own keybinds, not to be played

[profile.discord.bindings]
A = { tap = "key:CTRL+SHIFT+M", desc = "Mute the microphone", hold = "key:ENTER", hold_desc = "Enter" }
B = { tap = "key:CTRL+SHIFT+D", desc = "Deafen - mic and sound", hold = "key:ESC", hold_desc = "Esc / decline a call" }
X = { tap = "key:CTRL+K", desc = "Jump to a channel" }
Y = { tap = "key:CTRL+ENTER", desc = "Answer the call" }
LSTICK = { tap = "click:right", desc = "Context menu" }
```

| Button | In Discord | Otherwise |
|---|---|---|
| A | **mute the microphone** (`Ctrl+Shift+M`) | Enter |
| A **held** | Enter | – |
| B | **deafen** — mic *and* sound (`Ctrl+Shift+D`) | Esc |
| B **held** | Esc, which is also how Discord declines a call | – |
| X | **jump to a channel** (`Ctrl+K`) | middle click |
| Y | **answer the call** (`Ctrl+Enter`) | right click |
| Left stick click | **right click** — the context menu | middle click |

`A` and `B` are the pair, next to each other on the pad the way they are in the
app: mute is what you press constantly, deafen — the microphone and everybody
else's sound at once — is what you press when the room you are in gets loud
rather than the call. Both keep what they meant everywhere else **on a hold**,
which is all Enter and Esc are worth in a chat window: a message is sent by the
keyboard's own `ZR` (Enter, and the keyboard away) rather than by `A`.

`X` and `Y` are the two things a pointer is worst at. `Ctrl+K` is Discord's
quick switcher — a server, a channel or a DM by name, which beats walking a
sidebar with a cursor. `Ctrl+Enter` answers an incoming call: the one thing
here that is *timed*, and cannot wait for you to aim at a small button.

What this costs, in Discord only: the middle click (which stood on `X` and on
the left stick click) is gone, and Enter and Esc are a hold rather than a
press. The right click is **not** gone — it moves to the left stick click,
because the context menu is how Discord replies to and reacts to a message.
None of it reaches the window layer: `ZL` + `A`, `B`, `X`, `Y` and the left
stick are fullscreen, **close the window**, float, pop out and pin here exactly
as they are anywhere else.

`handover = false` is the other half of it. Discord polls the Gamepad API for
its own keybinds, so it counts as having opened the pad for as long as it is
focused — and taken at face value that hands it the pad, which stands every
binding above aside and stops the sticks pointing at the window they exist to
aim at. It is the one shipped profile that says this, and the reason the key
exists.

`match` is a substring, so `"discord"` covers Canary and PTB as well; the forks
are named separately because their class is their own. These are Discord's own
in-app shortcuts and they fire only while it has focus — the global keybinds in
its own settings are a different list. And with Discord focused the keyboard
grows a `Chat` page: three canned replies, the pickers and the pins — see
[Discord's page](#discords-page-chat).

> **The order it is declared in is load-bearing.** Omarchy installs Discord as
> a webapp as readily as pacman installs the client, and a webapp's window
> class is `chrome-discord.com__channels_@me-Default` — which matches `chrome`
> as squarely as it matches `discord`. The first profile declared wins, so
> `[profile.discord]` comes **before** `[profile.browser]`; written after it,
> none of this would ever fire on the install that needs it most. In a webapp
> window the shortcuts are also Chromium's to claim first, and the native
> client is the one that has all of them.

### YouTube: the television's two controls

A game console has a television and a desktop does not, which is most of what
this project is about. The menu launches YouTube as a **webapp window** rather
than a tab, so the pad can walk to it — and what a television asks for from a
sofa is two things: whether it is playing, and whether it fills the screen.
Both are the player's own controls, both sit along the bottom edge of the video
behind an overlay that hides itself, and that is the definition of a target a
pointer on a sofa is worst at.

```toml
[profile.youtube]
match = ["-www.youtube.com", "-youtube.com"]

[profile.youtube.bindings]
X = { tap = "key:K", desc = "Play / pause" }
Y = { tap = "key:F", desc = "Fullscreen" }
LSTICK = { tap = "key:SLASH", desc = "Search" }
RSTICK = { tap = "key:ALT+LEFT", desc = "Back" }
```

| Button | In YouTube | Otherwise |
|---|---|---|
| X | **play / pause** (`k`) | middle click |
| Y | **fullscreen** (`f`) | right click |
| Left stick click | **search** (`/`) | middle click |
| Right stick click | **back** (`Alt+←`) | back (mouse 4) |
| A / B | Enter and Esc, untouched | the same |
| D-pad ←/→, ↑/↓ | seek and volume, YouTube's own | the arrow keys |

`k` rather than Space, because Space scrolls the page whenever the player is
not the focused element — `k` is answered by YouTube's own handler wherever the
focus is, as long as it is not in a text box.

**`A` and `B` are left alone, and both already fit.** `A` is Enter, which opens
the thumbnail [focus traversal](#inside-the-window-focus-traversal) walked to
with the right stick in game mode; `B` is Esc, which is how a browser leaves
fullscreen — "B goes back", said in the player's own words. The D-pad costs
nothing either: YouTube reads the arrows as seek and volume for as long as the
player has the focus.

**Search is on the left stick click, not on `Y`.** The pattern puts the app's
*reach* on `Y` ([the face buttons](#the-face-buttons-mean-the-same-thing-everywhere)),
and here that would be the search box — but searching needs the on-screen
keyboard anyway, so it costs nothing to move one button along: press the left
stick, then `MINUS` for the keyboard, then `ZR` to send it and put the keyboard
away. Fullscreen takes the button a thumb finds first because it is the control
every video needs.

What this costs, in YouTube only: the middle click (`X` and the left stick
click) and the right click (`Y`). Mouse button 4 is handed straight back as
`Alt+←`, the way [the browser profile](#per-application-profiles-and-the-shoulder-buttons)
does it and for the same reason. What did not fit: `shift+n` / `shift+p` (next
and previous video), `m` (mute) and `c` (captions) — the first is what the
budget would buy next.

> **`match` is the host, not the word.** The class here is
> `chrome-www.youtube.com__-Default`, and matching the bare word `youtube`
> would take **YouTube Music** (`chrome-music.youtube.com__…`) with it, where
> none of these keys exist. The leading dash is what keeps the two apart. Like
> `[profile.discord]`, it is declared **before** `[profile.browser]` — a webapp
> class matches `chrome` as squarely as it matches its own host.

### The terminal: Backspace, the interrupt and the scrollback

A shell is driven with keys the pad has no button for. The one it needs most
from the sofa is **Backspace**: a command is typed by aiming a thumbstick at
letters, and the letter aimed at is regularly not the letter that lands.
`Ctrl+C` is the other — the way out of something that is not coming back.
Neither is anywhere on a controller, and neither is anything a pointer can
reach.

```toml
[profile.shell]
match = ["foot", "alacritty", "ghostty", "kitty", "wezterm"]
right_stick = "scroll"

[profile.shell.bindings]
X = "key:BACKSPACE"
Y = { tap = "key:CTRL+SHIFT+V", desc = "Paste", hold = "key:CTRL+C", hold_desc = "Interrupt" }
LSTICK = { tap = "key:CTRL+L", desc = "Clear the screen" }
RSTICK = { tap = "key:CTRL+SHIFT+C", desc = "Copy" }
```

| Button | In a terminal | Otherwise |
|---|---|---|
| X | **Backspace** — repeats while held | middle click |
| Y | **paste** (`Ctrl+Shift+V`) | right click |
| Y **held** | **`Ctrl+C`** — interrupt | – |
| Left stick click | **clear the screen** (`Ctrl+L`) | middle click |
| Right stick click | **copy** (`Ctrl+Shift+C`) | back click |
| Right stick | **the wheel** — the scrollback | game mode walks the focus |

Every key here is the **shell's own** rather than an emulator's, so the one
profile covers all five names in `match`: foot and alacritty have neither tabs
nor a context menu, and a scheme built on those would be dead in two of the
five.

**Backspace is on `X` because that is where the keyboard puts it.** `X` is the
[app's own verb](#the-face-buttons-mean-the-same-thing-everywhere), and erasing
what you have typed is a terminal's — but the real reason is that
`[bindings.osk]` has had Backspace on `X` since it was drawn, and the terminal
and the on-screen keyboard are exactly the pair of surfaces a command is typed
across. A key that moved under your thumb when the keyboard opened over the
prompt would be worse than no key.

**It is written plain, and that is deliberate.** A tap/hold binding waits for
the release before its key goes down, which costs the autorepeat — and
Backspace is the one key that is held rather than pressed. So `X` carries
nothing else, and Backspace repeats the way it does on a keyboard.

**Tab is not on a button, because the keyboard already has one.** It held this
button until it turned out to be the wrong shape for it: completing a command
meant putting the keyboard away, pressing a button and summoning it again, once
per completion. The on-screen keyboard's first page has had a `Tab` key all
along — with the line you are typing still in front of you, it is aimed at like
any other key.

`Ctrl+C` rides `Y`'s hold rather than `B`'s. When it was written, a profile
reached into the window layer as well, and putting it on `B` — where it first
looks like it belongs, next to Esc — would have taken `ZL` + `B`, **closing the
window**, away from every terminal. Profiles [stop at the window
layer](#per-application-profiles-and-the-shoulder-buttons) now, and it stays on
`Y` regardless: `B` is the Esc that vim, less and every full-screen program in
a terminal want, and a hold is the right shape for an interrupt — killing a
command by accident is worse than pasting one by accident.

**And `ZL` + `B` asks the terminal before it closes it.** The window layer's
close is the one binding that reads the window in front of it: while a command
is running it sends `Ctrl+C` instead, and the press after that — with the
command gone — closes the window as it always did. Nothing else changes, and
nothing else has to: a browser, a game or a file manager has no shell under it
and takes the close straight.

The question is answered from `/proc` rather than guessed at. A pty publishes
the process group a `Ctrl+C` typed at that terminal would be delivered to, and
while that is the shell's own, the prompt is what is in front and there is
nothing to interrupt. A shell inside **tmux** or **screen** belongs to the
multiplexer's session rather than to the window, so a busy pane there reads as
idle and the window closes — the same as before. A terminal that serves several
windows from one process (`foot --server`, `kitty --single-instance`) is the
other way round: any busy terminal under that process answers for all of them,
so an idle window declines to close while another one is still compiling.
Neither can close a window over a command that is running in it, which is the
mistake worth avoiding.

Both halves are settings, so a scheme that closes windows some other way does
not lose the interrupt along with the close:

```toml
[terminal]
interrupt = "key:CTRL+C"                    # while a command is running
idle = "hypr:hl.dsp.window.close()"         # with nothing to interrupt
depth = 4                                   # how far below the window to look
                                            # for the shell
```

`Y`'s tap is the paste that works. The middle click `X` carries elsewhere pastes
the PRIMARY selection, which wants a selection made with a mouse and a pointer
parked on the prompt; `Ctrl+Shift+V` pastes the clipboard the rest of the
desktop fills. `Y` is the cheaper of the two face buttons to spend it on: it is
the right click, which in a terminal opens a menu of two entries in kitty and
ghostty and nothing at all in foot and alacritty. The left stick click is then
the cheapest click left — the same displacement the browser and Discord
profiles make, and it costs `ZL` + left stick, the window pin.

**The stick is the reason this profile needed one at all.** Game mode hands the
right stick to `focus` (see [Focus traversal](#inside-the-window-focus-traversal)),
which sends the keys under `[traverse]` — and at a prompt those are the worst
keys on the keyboard: `next` is Tab, so the stick completes, and `up` / `down`
walk the shell's history, so it rewrites the line you were reading. A terminal
answers the wheel with its scrollback, which is what the stick is being pushed
for. That is the same exception `[profile.browser]` makes for the opposite
reason — there the focus keys go somewhere real but not where the pointer is,
here they go somewhere actively wrong.

**`R3` copies, and it is what makes the paste a round trip.** Selecting is the
one half of this a pointer on a sofa still does well — `ZR` drags a selection
the way a mouse would — and until this binding the only way to put one back
was the middle click the profile had already spent. `Ctrl+Shift+C` rather than
`Ctrl+C` because a terminal's copy is the shifted one in all five, and because
the unshifted one is the interrupt on `Y`'s hold. The button is the last cheap
one a terminal has: `R3` is the back click everywhere else, and no terminal
answers a back click at all.

What is **left alone**: `A` is Enter, `B` is Esc, `ZR` is the left click, and
the D-pad is the arrows the line editor and the history are walked with.

What the profile **spends**: `X` and the left stick were the pad's two middle
clicks, so a terminal now has none — text selected with a mouse but never
copied is unreachable from the pad, which is exactly what `R3` gives back, on
the clipboard rather than in PRIMARY. `Y` was the right click, which is the one
this profile is happiest to lose, and `R3` was the back click, which a terminal
never had a use for.

That is the whole budget: four buttons, and the game bar has three slots for
them — *Backspace*, *Paste*, *Copy*, with `Ctrl+L` left to the guide, since
`A` and `B` keep their meaning here and are not printed.

### Rumble

Write `rumble = true` on a binding and the pad gives a short tick when that
binding fires:

```toml
[bindings.base]
Y = { tap = "hypr:hl.dsp.window.center()", rumble = true }
```

In the shipped scheme this flag is not on anywhere. The rumble's standing jobs
are elsewhere. One is the **confirmation countdown**: the pad ticks when
the `confirm_ms` above runs out. With the screen off or a window fullscreen you
do not see the notification but you do feel the rumble — and that situation is
the whole reason the countdown exists. Another is the **mode switch**
(`[mode] rumble`), which is the same problem: what changes is across the room,
so one tick goes in and one comes back out. The third is the one nobody
presses: a running [stopwatch](#tiles-that-hold-a-value) ticks every time
its sweep hand comes back to twelve, so a measurement can be followed without
looking at it (`[chrono] rumble`).

**Controller › Vibration** in the menu turns it on and off and steps the
strength, ticking the motor at each step so you set it by feel rather than by
number; what you pick lands in `settings.toml`. The defaults, and the knobs the
menu does not reach, are under `[rumble]`:

```toml
[rumble]
enabled = true
strong = 0.20         # 0..1, the low-frequency motor - this is the real "tick"
weak = 0.0            # 0..1, the high-frequency motor, on pads that have one
duration_ms = 60      # short enough to read as a tick rather than a buzz
floor_ms = 50         # the shortest pulse worth asking any driver for
```

The defaults were picked **by hand on a Beitong KP20 in NS mode**: this pad has
only wired up the low-frequency motor, and you cannot feel the high-frequency
one even at full power. On pads that wire up both, the really clean tick is
usually on `weak`, so the knob stays.

`floor_ms` is why: `hid-nintendo` sends rumble packets **on a 50 ms period**,
so a pulse shorter than that can fall between two of them and be swallowed
entirely. Nothing is ever asked for shorter. If you feel nothing, lengthen
`duration_ms` first, then try the motors one at a time. On a pad with no motor,
or one opened read-only, rumble turns itself off quietly — one line lands in
`journalctl --user -u omapad` and nothing else changes.

#### The motor says four things

The tick is one of four, and each is a different shape rather than the same
buzz at another length:

| | Says | Where you feel it |
|---|---|---|
| **tick** | a press landed | the two standing jobs above |
| **edge** | you cannot go further | a control at the end of its range, the rim of the menu grid |
| **commit** | that took | a switch flipped, a choice walked on |
| **texture** | which way you just pushed | held under a thumb while a control is moving |

How hard and how long each one is are settings; the *waveform* is not. A square
wave is what makes an edge feel like an edge, and turning that into a knob is
offering to turn a bump into a hum.

```toml
edge_strength = 0.35
edge_duration_ms = 70
commit_strength = 0.28
commit_duration_ms = 90
texture = true
texture_strength = 0.25
```

The **texture** is the one that uses both motors. A pad has a heavy motor on
the left and a light one on the right, so **the hand that made the move is the
hand that feels it**: push a value right and the right motor answers, push it
left and the left one does. A list walked up or down inside a card answers on
the left — that is the thumb on the D-pad, and up and down have no left and
right of their own.

It is one level rather than a scale. It rose with the distance from where you
started pushing for a while, which is a second reading of the number already
on the tile; what a hand on a control is asking is whether the push landed.

It used to be one flat hum whichever way you pushed, and shipped off, because
a scheme where everything buzzes says nothing. Something that says *which way*
is not that.

`omapad check` prints which of the four **your** pad took, and says which it
could not.

The rumble fires when the action **really runs**: in game mode a binding outside
`[bindings.game]` does not run, so the pad does not tick either.

### Sounds

The motor is in your hands, so it says nothing while the pad is on a knee,
nothing on a pad that has no motor, and nothing at all once you turn it off.
The third answer is a noise, and it is the only one the room hears:

```toml
[sound]
enabled = false       # ships off - see below
volume = 0.6          # against the files' own level, which is quiet on purpose
pack = ""             # a directory of your own move/back/tick/edge/commit .wav
```

**Controller › Sounds** turns it on, and **Loudness** beside it is the same
kind of slider **Strength** is for the motor. `omapad ctl sound commit` plays
one without pressing anything, which is what setting a volume needs.

It **ships off**, and that is the one difference from rumble. Every other
answer omapad gives is to the person holding the pad; this one is to everybody
else in the room as well, so a desktop that started clicking because a
controller had been plugged into it would be omapad deciding something about
the room rather than about the pad.

#### It says the motor's three words, and two more

| | Says | Where you hear it |
|---|---|---|
| **move** | the selection went somewhere | walking the menu's tiles, its bar, the keyboard's keys, the guide's pages |
| **back** | that went the other way | B up a level, leaving a page, putting a control back, a countdown backed out of, any surface put away |
| **tick** | a press landed | everywhere the motor ticks |
| **edge** | you cannot go further | a control at the end of its range |
| **commit** | that took | a switch flipped, a choice walked on |

**`move` and `back` are the two the motor cannot say.** Nothing buzzes on a
plain step, and that is deliberate: a motor ticking under a held direction
buzzes all the way down a list. A sound decays, so it *ticks* instead — which
means walking a page is the one thing you hear and never feel.

`back` is the other kind of thing a motor cannot be. It can be shorter or
weaker, which says *less happened*; it cannot fall a fourth, which says *this
one went the other way*. So `back` is the commit's own note and the commit's
own interval upside down — that one bends up, this one bends down from the
same place — and softer and shorter besides, because leaving is the smaller
event. A press still ticks the hands either way; only the room is told which
of the two it was.

`texture` goes the other way and has no sound at all: a hum a motor can hold
under a thumb for a second and a half becomes the loudest thing in the room
coming out of a speaker.

The five files ship beside the plugin and are **generated, not recorded** —
`python3 assets/sounds.py` writes them from a table of about eighty lines, so
changing what a commit sounds like is changing a number. Point `pack` at a
directory of your own to replace them; a name it does not hold falls back to
the shipped one, so a pack of a single `commit.wav` is worth writing.

Playing anything needs **`qt6-multimedia`**, which Quickshell does not depend
on. Without it the sounds are simply absent and nothing else in the plugin is
affected — `omarchy-shell ipc call omapad-sound state` says which it is.

## The menu

Press **PLUS**. Three things open together, stacked down the middle of the
screen:

- **the head** — the day, the time, and whatever else you point a command at.
  Game mode takes Omarchy's bar away and there is no other clock the pad can
  reach, so the menu carries one.
- **the bar** — one card per group, walked with the shoulders. `Now`,
  `Apps`, `Workspaces`, `Audio`, `Display`, `Controller`, `System`. A nav card is
  one cell of the grid below it, drawn on the same ground and standing over
  the same columns — the one you are on is filled with the accent outright.
- **the grid** — the tiles of the group you are on, some of them wider or
  taller than others.

**Hold** PLUS and the real Omarchy menu opens. That one wants a keyboard and a
mouse; this one takes them both — the same Exclusive focus, hover-to-select and
clicks — so whichever hand you are holding, the menu reads the same way.

The pad and the desk drive the same selection: whatever moves it — a thumb, an
arrow, a cursor — ends up naming one tile in the daemon, over the same control
socket `omapad ctl` uses. A held D-pad direction and a held arrow key both walk
the grid; Enter and A both pick; Backspace and B climb one level; Esc and X
leave outright; hover names a tile, a click picks one, and a click on the scrim
leaves.

It was a single column for a long time, and it is a grid now for one reason: a
list says every row is worth the same. What is playing is not worth the same as
a tile beside it, and a grid is how you say so. It is still not a radial — a
radial reads a stick angle in one flick but takes no more than a handful of
entries, and has nowhere to put a page.

| Button | Job |
|---|---|
| D-pad | Walk the tiles, all four ways (hold it and it keeps walking) |
| L / R | Previous / next group |
| A | Pick — and go in, if it opens a page |
| B | Back to the page above; at the top it closes the menu |
| X · PLUS · Capture · Right stick click | Close the menu outright, from any depth |
| Y | Open [the bindings guide](#the-bindings-guide) |
| HOME | Tap: close the menu · Hold: switch mode |

**Left and right walk the grid; they used to be a second way to say Back and
Pick.** A single column left both free for that, and a grid spends both axes on
getting about — A and B already say the other two things.

`X` and `B` are not the same button twice: `B` walks back up **one** page at a
time - and out of a card of rows before it leaves the page - while `X` leaves
outright. `Y` is the pad's reach for something not on screen, and it carries
two of them: a press [rearranges the page](#arranging-a-page-from-the-pad) —
the tiles are yours, which is the thing no page can show you — and **holding
it** opens the bindings guide, the same view `Controller › Buttons ›
Shortcuts` opens, for when you opened the menu *because* you had forgotten
which button does what.

The arrangement is the tap and the guide is the hold, rather than the other
way round, because the guide is a page you read once and an arrangement is one
you come back to tile by tile — and the guide has a row of its own, so it is
the one of the two with a second door.

The keyboard and the mouse drive the same menu,on top of the pad:

| Key / mouse | Job |
|---|---|
| ↑ ↓ ← → | Walk the tiles (hold and it keeps walking) |
| Tab · Shift+Tab | Next / previous group |
| Enter · Space | Pick — and go in, if it opens a page |
| Backspace | Back to the page above; at the top it closes |
| Esc | Close the menu outright, from any depth |
| Hover a tile | Move the selection to it (once the cursor has travelled) |
| Click a tile | Pick the tile it lands on |
| Click a nav card | Walk the bar to that group |
| Click the scrim | Close the menu |
| Home · End | Jump to the ends of the page |

The menu takes the keyboard exclusively while it is open -ther Omarchy
menu's own window rules - so the arrows reach it rather than the window
underneath;and it swallows the pointer too - a scrim click leaves,and a
row click picks,which is what makes it feel the same in the hand as
Omarchy's own. Once it closes,ther keys and the pointer go back to the
window under it.

The menu layer sits above the keyboard layer: opening the menu closes the
on-screen keyboard, so that exactly one surface reads the D-pad. Holding MINUS
still wins.

When a tile is picked the menu **closes first and the command runs after** — so
the window you opened is not left behind the dimming. There are two exceptions.
Tiles with `repeat = true` are things you *nudge* rather than *pick*: they
leave the menu where it is, hold A and it repeats like a held keyboard key, and
B is the way out. Nothing shipped uses it any more — the volume and brightness
tiles that did are bars now — but it is still the right answer for a step with
no value to show. Tiles with `stay = true` are
the quieter half of that — one press, and the menu stays up — which is what a
tile that changes a setting the menu itself prints needs.

A tile that *sets* something is **ticked** while that something is what is in
force, so a page of choices says which one you are on rather than making you
guess.

### The first menu a pad ever opens

A machine driven from a sofa is the machine nobody walks to a keyboard to set
up — so the first start offers what a first start decides, from the pad. The
first time the menu is opened it opens on a **`Start here`** tile at the top of
`Now`, and behind it is one page:

| Row | What it is |
|---|---|
| Shortcuts | [the bindings guide](#the-bindings-guide) — what every button does |
| Remap the buttons | [the mapping screen](#controller-mapping), for a pad whose buttons arrive under other names |
| Vibration · Sounds | the two ways a press answers besides the screen — the motor is on, the sound is off |
| Motion | how much the surfaces move, and at 0 whether they move at all |
| Hold time | [how long a hold takes](#holding-for-a-hand-that-cannot) |

Every row there reads the same setting its home row does — this is not a fifth
place to keep them — and each is on its own page too: `Display ▸ Motion`,
`Controller ▸ Vibration`, `Controller ▸ Sounds`, `Controller ▸ Hold time`.

**It is shown once.** Opening the menu is what answers the first start:
`first_run = false` goes into `~/.config/omapad/settings.toml` and the tile is
gone by the next opening. Delete that line — the file says so at the top — and
it comes back.

### A card, or the whole screen

The menu fills the screen and draws no panel of its own: the tiles float over
whatever is behind them. A card reads as a menu and a whole screen reads as a
page, and from a sofa the second one is what you want.

```toml
[menu]
fullscreen = true             # false gives back the centred card
```

The tiles carry their own background, so they read over a game or a wallpaper.
It covers the bars along the bottom too — it prints its own row of hints, so
there is nothing down there worth leaving room for — and that row sits in
**exactly the band the game bar's row sits in**, at the same height and the
same distance from the edge. It is the same kind of row about the same
buttons, and it wears the bar's own colours — the same text colour, the same
resting fills — so nothing moves, and nothing changes colour, when the menu
opens — and omapad's own bar is taken
down *before* the menu is drawn, so the two rows never crossfade in one place.
At the top level the line above the bar says what the group you are on
**holds** — `Sound, screen, what is playing` — rather than naming it again:
the cards are already saying where you are, and a line repeating that is the
card telling you twice. Drilled in, it names the page instead, since the bar
has dimmed on the card you came from.

Two things decide how much of the desktop you still see:

```toml
[menu]
dim = 0.6                     # how dark behind, over the theme's own scrim

[ui]
blur = true                   # ask the compositor to blur behind our surfaces
```

`blur` is a **request**. omapad asks Hyprland for a layer rule on its own
surfaces and nothing else; Hyprland blurs only where blur is on at all, so on
a desktop that has turned it off the rule does nothing and `dim` is the whole
of the contrast. Changing the Omarchy theme reloads Hyprland, which throws
that rule away — omapad notices and asks again, along with redrawing the
game-mode pointer in the new palette. Turning blur on globally is your call — it changes every
window on the machine:

```lua
-- ~/.config/hypr/looknfeel.lua
hl.config({ decoration = { blur = { enabled = true, size = 8, passes = 3 } } })
```

Set `fullscreen = false` for the card, which is the better shape at a desk.

**A tile changes shape only when it leaves the page's order.** A plain tile is
rounded and a tile you are carrying has a bite out of its corner, and that is
the whole of it — the shape is the loudest thing a tile can say with, so it is
spent on the one state where the tile is somewhere it does not belong. The tile
the pad is on is a ring, a glow round it and a light across its face; a slider
you have taken keeps every one of those and adds a second ring inside its edge,
which is this surface's one mark for *A has hold of this*. Both were cut back to
a facet once, and a page on which three tiles are three shapes reads as a page
where something has gone wrong.

**The compositor decides how hard a corner is rounded, where it has decided.**
Every radius the menu draws inside its card steps down from Hyprland's own
`decoration:rounding`, so a desktop that rounds windows at 12 gets tiles at 12
without being told. `[menu] tile_corner` is the answer where it rounds
nothing, which Omarchy ships as — that is the compositor speaking about
*windows*, and a tile is not a window: at 0 every tile is the same square, and
a tile in the hand has no corner left to take a bite out of. Raise it and the
shapes read from further away.

**How solid a tile is drawn is `[menu] tile_fill`**, and it is the fill rather
than the tile: the label and the icon are at full strength whatever it says.

```toml
[menu]
tile_fill = 1.0               # 1.0 opaque, 0 no ground at all
```

At 1.0 the page is the opaque card this surface was drawn to, which is what it
ships as — lower it and what comes through is the scrim, and under that
whatever `[ui] blur` is having the compositor blur behind the whole surface.
At 0 a plain tile has no ground and the page is its ink and its edges.

**And the tile under the thumb is always the whole of it.** Whatever the fill
is, the selected tile is drawn solid — so lowering it is also how far the page
falls back behind the thing you are on, and the selection comes *forward* as
you walk rather than only being ringed. Two grounds ignore it, because each of
them is a state rather than the absence of one: a switch that is on stays
filled, and a tile in the hand keeps its own tint.

**And the focus dims with it.** The halo and the light across a selected
tile's face are both there to lift one card out of a page of cards — so what
they have to overcome is the page, and the fill is how much page there is. At
1.0 the selected tile's ground is everyone's ground, it says nothing, and the
light is the whole of what a lit face is: the surface as drawn. Lower down,
the selection has gained a channel it never had — it is the solid card on a
page of glass — and light at full strength is saying a second time what the
ground already said, louder at every step. So both lights come down with the
fill. The **ring** does not: it is the mark rather than a glow, and it is the
one thing on a selected tile that means *here* at any fill.

**The bar follows the grid.** A group chip is one cell of the same module,
sitting an inch above the tiles it names, so a row of solid cards over a page
of glass would be the bar claiming to be a different kind of thing. The chips
you are *not* on thin with everything else; the one you are on stays filled
with the accent, and that is the second half of the same rule — its label sits
**on** that fill rather than under it, and the contrast it is set at is
measured against a solid accent. There is no thinner accent that keeps its own
label honest, so the setting reaches that card by the gap rather than by the
alpha: everything around it falls back and it does not.

`[menu] dim` does the work this gives up — once the fill is low, what a label
stands on is the scrim, so a page that reads badly over a window full of text
is asking for a darker `dim` rather than a higher fill. It is on the pad as
`Display > Tile fill`, beside `Corners`, and for the same reason: the page you
are looking at while you move the slider is the page that opens up under it.

**A switch you have turned on fills its whole tile** with the accent, rather
than drawing a little pill in the middle of it — a card has room to say one
thing with its whole face, and across a room a lit card reads where a knob
does not. Off, it looks like any other tile: *on* is the state worth seeing.

**The selected tile is lit from above** — its face carries a little more of
the accent along its top edge, falling away down the tile and gone by a little
over half, the way a leaf held up to a window is brightest at its top. Across
a room a one-pixel outline has stopped being an outline; a lit tile is still
lit.

**A press lights the tile it landed on**, for `[menu] press_ms` — a ring
drawn just inside the tile's own edge, on whatever outline that tile is cut
to. The thumb is on a button that feels the same whatever it did, and most of
these tiles leave the page exactly as it was, so without it a tile that ran
its action looks identical to a tile that was never reached. Set it to 0 to
leave the press silent.

### Arranging a page from the pad

**Press Y** on any page and its tiles become yours. Every button on the card
means something else while you are there, and the legend says which:

| | |
|---|---|
| **A** | pick a tile up, and put it down |
| **B** | done — and that is when it is written down |
| **X** | take a tile off the page, or put it back |
| **Y** | reset the page to the one that shipped |
| **LB / RB** | narrower / wider, while you are carrying one |
| **LT / RT** | shorter / taller, while you are carrying one |

Both axes, because a cell is a shape rather than a width: a card of rows with
a row too many, a reading you want to see from further away, a keyboard tile
that wants two rows rather than four. On the page the readings are drawn from,
a tile stops at the last row that page has.

A tile you take off stays on the page while you are arranging it, faded, so
putting it back is the same press that took it away — there is no second
screen to go and find it on.

**A tile goes in the cell you put it in**, including one with nothing leading
to it: carry it three across and three down on an otherwise empty page and
that is where it is. Down goes one row past the bottom each press, so a page
grows a row at a time and you can always reach what is below everything.
Everything you have *not* moved still flows around what you have, in the order
the page is written — so carrying a tile into the middle of a row still closes
the row up behind it, and a tile a new version adds still turns up at the end
rather than in the middle of your arrangement.

A tile will not walk onto another one you placed — the press does nothing and
the motor says so. One you have not placed it walks straight through, because
that one moves out of the way.

On a screen with a different `[menu] columns`, a cell off the right-hand edge
is **pulled back onto the page** rather than lost. `omapad check --layout`
prints the cells and says which ones that would happen to.

What you do lands in `~/.config/omapad/layout.toml` — the order, what is
hidden, any size you changed, and the cells you put tiles in — and it and
`config.toml` cannot break each other. A tile a new version ships appears at
the end of your page rather than being invisible; a tile that goes away is
dropped from your order rather than leaving a hole; and a tile you hid is
hidden only while it still exists. If the file is damaged the daemon says so once and uses the
shipped arrangement. `omapad check --layout` says what yours still resolves to,
and deleting the file — or resetting one page with Y — hands it back.

**Along the foot of the card is a legend** saying what the buttons do **on
the tile you are standing on**, drawn with the same buttons the guide and the
bar print — and, because it is the bar's row, in the bar's own text colour
rather than the menu's accent, so the buttons read the same whether the bar or
the menu is answering them.

It is the tile's line rather than the page's, so it changes as you walk:

| On | A says |
|---|---|
| the keyboard tile | `Keyboard` — a row that runs something says its own name |
| `Previous` | `Previous` |
| a page that opens | `Open` |
| the volume ring, or any bar | `Adjust` — A takes hold of it |
| a switch | `Turn on` or `Turn off`, whichever way it is about to go |
| what is playing | `Play` or `Pause` |
| the stopwatch | `Start`, `Stop`, `Reset` — whichever press is next |
| a row that cannot be taken back | `Hold to confirm` |
| a reading, or the clock | nothing at all, and the row is left off |

**Take hold of a control and the directions that move it appear**: ◀ `Less`
and ▶ `More`, and on the volume ring the left stick as well, because that is
the one control a thumb turns rather than steps. They are not there before you
press A, because until you do, left and right walk the page.

**B says what it is actually leaving** — `Back` inside a page, `Close` at the
top of a group, `Cancel` over a value you have pushed or a row that is
counting down. Where B closes the menu, X says nothing: it closes it too, and
one word under two badges is a row you stop reading. `[menu] keys = false`
turns the whole strip off — in game mode omapad's own bar is already saying
the same kind of thing across the screen, though only the legend can say what
a page has spent a key on, or what the tile under your thumb does.

**The menu comes back where it was.** Close it on the volume and the next
press opens on the volume — you turn it down, go back to the game, and come
back to turn it down again. The first press of a session opens on the first
tile of the first card.

A tile can override that with `open_on = true` beside its `when`: while the
condition holds, the menu opens *on* it whatever it was doing last. Nothing
ships with it — coming back where you were is the better answer for the
workspace lock too, and a tile that overrode it would take that away.

**The bar holds places, not verbs**, which is why the workspace lock is a tile
on `Now` rather than a card of its own.

### Writing the menu to suit yourself

The tree is under `[[menu.items]]`. **A top-level entry is a group** — a card
on the bar — and holds the tiles of one page. Its `detail` is what the line
above the bar prints while you are on it, so write it as what the group holds
rather than as what it is called.

**`meta` is the word under its name on the card**, and it says what that place
is *doing*: `Speakers`, `2 open`, `1200p · 60 Hz`, `151 waiting`. A bare word
prints as it is; a table runs a command and keeps the answer for its `ttl`
seconds, with `empty` for what to say when the command prints nothing.

```toml
[[menu.items]]
label = "Audio"
meta = { from = "…", ttl = 10, empty = "Nothing out" }
```

**Give it a `ttl`.** There is one of these per group, so a card without one is
a subprocess a second for a row of two-word labels. Leave `meta` out and the
card says how many tiles its page holds.

**A tile takes one too**, and it is the line a tile cannot write for itself: a
`detail` is a sentence set down in a config file, so it can say what a row does
and never what the machine is doing. A tile's `meta` stands where its written
line stands — the heading on a card of rows, the detail line on any other tile
— and only the page in front spends anything.

```toml
[[menu.items.items]]
label = "Windows"
control = "rows"
meta = { from = "hyprctl activewindow -j | jq -r .title", ttl = 2, empty = "Windows" }
```

That is what `Workspaces › Windows` ships with: the card is about the window in
front, the menu has blurred that window, and `WINDOWS` over four verbs says
only what the page is already called. With the title there, `Close window` is a
row about something you can name.

`System › Update` is the other one that ships with a `meta`, and it is the same
argument about a different fact: the tile says `12 waiting` where there is
something to install and `Up to date` where there is not, which is what the
card on the bar says about the page — and pressing it opens the update in a
terminal.

Each tile takes either an `action` (**the same grammar** as the button
bindings) or an `items` list that opens a page of its own.

```toml
[[menu.items]]
icon = ""                     # any glyph in the shell's font
icon_font = ""                # the font that glyph came from, if not the shell's
label = "Audio"                 # a group, so a noun: it is a place you go
detail = "Where the sound goes"

  [[menu.items.items]]
  label = "Screensaver"
  span = [2, 1]               # two cells across; [1, 1] unless you say
  action = "exec:omarchy-launch-screensaver force"

  [[menu.items.items]]
  control = "row_break"       # end the row here; draws nothing

  [[menu.items.items]]
  label = "Xbox labels"
  stay = true                 # keep the menu open, but fire once
  action = "pad:layout=xbox"  # and this tile is ticked while it is in force

  [[menu.items.items]]
  label = "Workspace lock"
  when = ["game", "handed_over"]   # only offered in those states, any one does
  open_on = true              # and the menu opens on it while one holds
  action = "lock:toggle"

  [[menu.items.items]]
  label = "Shutdown"
  confirm = true              # held, not pressed
  action = "exec:omarchy-system-shutdown"
```

Tiles are packed **first fit, in the order you write them**, left to right and
top to bottom — so the order is still yours, and a small tile is allowed to
backfill the hole a big one left. `[menu] columns` is how many cells across a
page is; six by default, and worth turning down for a small screen.
`[menu] cell_height` is the other half of a tile's shape — the width is
whatever the columns leave, and this is how tall one cell is. Raise it and a
tile carries its icon over its label with room to spare; lower it and the page
reads as a denser list, and below the room for both the icon steps out and the
label has the tile to itself. Below the room a *switch* and its label need,
though, nothing steps out — a tile's contents are not clipped, they hang over
the edge of it — so the default is the height the tallest control actually
comes to and not a round number. A
`row_break` tile ends the row it is in, which is the way to group tiles that
belong together. It is deliberately not a one-cell spacer: a spacer holds a
hole open at six columns and shifts everything under it at four, and the same
page has to read on a laptop panel and on a television.

`when` keeps a tile out of the menu where it could do nothing useful. The
states are `game` (game mode is on), `handed_over` (the app in front has taken
the pad), `locked` (the workspace lock is on), `kept` (the pad is being kept
from an app that opened it) and `first_run` (the menu has never been opened —
see [the first menu](#the-first-menu-a-pad-ever-opens)); a tile that says
nothing is always there. They are
read **when the menu opens** and stand until it closes, so no tile appears or
vanishes under the selection while a thumb is aiming at one.

There are **two** answers to *are you sure*, and they are for two different
presses.

`countdown` is for a row that takes the screen away. A is an ordinary press,
and then the row counts `[menu] countdown` seconds down beside its name and
runs when it reaches zero. **B stops it**, and the legend says `Cancel` while
it runs. Nothing else stops it — ten seconds is long enough to want to look at
something else on the page, and a count that died because a thumb brushed a
stick would be worse than no count at all. `countdown = 5` sets the length for
one row. `System › Power` spends it on Logout, Reboot and Shutdown: being sure
you meant to log out is not a thing to do with a thumb, and holding A for ten
seconds is not a gesture anybody makes. `Reboot` and `Shutdown` were a cell
each beside that card as well — the two anybody walks to the page for — and
are not any more: a second copy is the same two words twice a cell apart, and
a guard that has to be kept in step in two places. They are rows in the card
like the other three.

`confirm` is for a row a second press does not undo, where the answer is
wanted now. A stops being the press that runs it and becomes the press that
starts **holding** it: the tile fills
from the left, at `[confirm] hold_ms` the pad ticks and a notification says
what is coming, and `confirm_ms` later — with the fill running back out of the
tile — it runs. Letting go backs out, and so does B. It is the same gesture the
shoulders make to cross a workspace over a game, and
[`[confirm] scale`](#holding-for-a-hand-that-cannot) reaches it like every
other hold. While the tile is in front, the legend along the foot says `Hold to
confirm` rather than `Pick`, so nobody has to make the gesture to find out
about it.

The shipped tree spends the hold on one row — `Close window`, where you are
looking at the window and the answer is wanted now — and the countdown on the
three under `System › Power`. Not on `Lock` or `Suspend`: the line is what a
second press undoes, not what sounds serious. A row is held or counted, never
both, and neither goes beside `repeat`.

`open_on` is the other half of `when`, and it needs one: while the condition
holds, the menu **opens on this tile**. It is what a capability that has to be
found the moment you press PLUS asks for, now that the bar holds places rather
than verbs. The earliest one in the tree wins.

If you redefine the `items` list in your own config it replaces **the whole**
shipped tree rather than being merged group by group — your menu is your menu.

### Tiles that hold a value

A tile with a `control` reads a setting and draws what it is on, instead of
doing something:

```toml
[[menu.items.items]]
label = "Vibration"
control = "toggle"            # a switch; A flips it
reads = "pad:rumble"

[[menu.items.items]]
label = "Button style"
control = "choice"            # ‹ a value ›; A walks it forward
reads = "pad:badge_style"

[[menu.items.items]]
label = "Brightness"
control = "slider"            # a value on a line; A takes it, ‹ › move it
reads = "live:brightness"

[[menu.items.items]]
label = "Volume"
control = "knob"              # the same value as a ring, turned with the stick
reads = "live:volume"

[[menu.items.items]]
label = "Music"
empty = "Nothing playing"
control = "media"             # what is playing; A plays or pauses it
reads = "live:media"

[[menu.items.items]]
label = "Left stick"
control = "gauge"             # a dial: the setting, and where the thumb is
reads = "pad:left_deadzone"
shows = "left"

[[menu.items.items]]
label = "Time"
control = "clock"             # a face with two hands; it reads nothing

[[menu.items.items]]
label = "Stopwatch"
control = "chrono"            # the same face with a stopwatch in it
```

`reads` names either one of the settings the pad can change — the same names a
`pad:` binding takes — or one of the things the machine is doing: `volume`,
`mute`, `brightness`, `media`. The kinds have to match and `omapad check` says
so: a `toggle` reads an on/off setting, a `choice` reads one with a list of
values, a `slider` reads a number — and a `knob` reads either a number or a
list.

A control tile needs no `action`, never repeats, and always leaves the menu
up. A switch and a choice are done in one press; **a slider is taken first** —
both directions belong to the grid until it is, so A takes it, left and right
move it (faster the longer you hold one), either trigger sweeps its whole
range, and then **A keeps what it is on and B puts it back**.

**A `knob` is the same value as a ring**, and the difference is the hand
rather than the drawing. A slider is a length and a knob is an angle, and the
stick you walk the page with is already a turn — so once A has taken a knob,
**the stick turns it**, as well as the left and right that move a slider and
the triggers that sweep one. Either way it does nothing until the stick is
pushed far enough over for the angle to mean something — `[menu] aim_grip` (a
quarter of the stick) when you point at it, `[menu] turn_grip` (half) when you
wind it. Two numbers because the two gestures ask different things of the
stick: winding adds up how far your thumb has travelled, so a wobble near the
middle accumulates and the radius has to keep that sum honest; pointing keeps
nothing, so a wobble corrects itself the moment your thumb moves on. Raise
either if a dial moves when you did not mean to touch it.

And **letting go of the stick does not take the value with it.** A stick you
release does not come straight back to the middle — its two axes return at
their own rates, so the pointer would swing on the way in and leave the value
where the spring passed rather than where you aimed. omapad tells the spring
from your thumb by how fast the stick is falling inward (`[menu] turn_return`,
in stick travel a second) and stops reading the moment it is crossed, until
you push back out. Lower it if a dial still creeps as you let go; raise it if
pulling the stick back towards the middle while you turn stops the ring
answering.

`[menu] turn` says which gesture it is, and they are different controls that
share a drawing:

- **`turn = "aim"`** (the default) — **where you point is where it goes.** The
  ring has a pointer and so does your hand, so they are the same figure: take
  it, point at the number, let go. Twelve o'clock is the middle of the scale,
  half past seven is the bottom and half past four is the top. The quarter of
  the circle left open under the dial is its **two end stops** — point into it
  left of centre for the bottom of the range and right of centre for the top —
  so a ring still does not come round at the ends, and pushing against one
  ticks the way a real stop does. A number is **followed, not stepped**: it
  lands on anything it can say — whole percent for volume, whole pixels a
  second for the pointer — rather than on the steps a press moves it by, so a
  thumb moving smoothly moves it smoothly. A ladder of corners and a list of
  words keep their stops, there being nothing in between to land on.
- **`turn = "carry"`** — the value moves by **how far your thumb has
  travelled**, never by where it is pointing, so nothing jumps the moment you
  touch the stick. That is what it is for: an aimed dial grabbed at two
  o'clock puts the volume at two o'clock, and if you reach for the stick
  without looking that is a loud press. In exchange you wind rather than
  point. Its gearing is two numbers and the slower wins — `turn_degrees` (270)
  is how far round the whole range is, `turn_step_degrees` (30) is the closest
  together two steps may ever be, so volume is a five-percent detent every 30°
  and a ladder of five corners, already 67° a stop, turns as it always did.
  Neither number does anything under `aim`, which has no gearing to have.

It is two cells square, like the dial and the clock, and it is the one control
that also reads a **list**: its stops are the values, printed round the scale,
which is what a selector knob has always been. Turning it stops at the ends
rather than coming round — a press on a `choice` tile still wraps, because
that is one way through a list and this is a thing with a position.

Neither of them is the better one, which is why the shipped tree has one of
each: `Volume` on `Now` is a ring and `Brightness` on `Display` is a bar. A
length is read faster; a ring is turned better. Swap the word in either to have
two of a kind.

A choice tile shows **one** value, so it has nowhere to put the line saying how
the values differ — which is what `Button labels` and `Profile` keep their
submenus for. Where that line is what you need, reach for a
[card of rows](#a-card-of-verbs-drawn-as-rows) instead: it shows every value at
once, each with its own sentence.

**A `clock` reads nothing**, which makes it the one tile with no `reads` at
all: the time is not a setting, not something the desktop is doing and not
something the machine publishes. It is a face with an hour hand and a minute
hand, two cells square like the dial, and A on it does nothing. The menu's own
header prints the time in figures for somebody who has just opened the menu;
this is for a glance from across a room, which is the other question — and it
can be left on screen over a game, where there is no bar to glance at. It is
the one control besides a reading that [the HUD
draws](#the-readings-how-busy-how-full-how-hot).

**A `chrono` is that face with a stopwatch in it**, which is what a chronograph
is: the time of day on two hands, a sweep hand that measures, and three
registers where a three-register wristwatch has them — running seconds at nine,
the minutes measured at three, the hours at six. The figures beside its name
say the measurement to a tenth, because no hand can say *three minutes and
twelve*.

**A is the pusher**: press to start, press to stop, press to reset, round
again. One button because a tile owns one — B leaves the menu and X closes it
everywhere — and it is the cycle a monopusher chronograph has worn since before
it had two pushers. The line under the card says which of the three the next
press is, so `Reset` is read rather than discovered. What it costs is
resuming: a stopped measurement is thrown away by the next press, not
restarted.

**It strikes the minute.** A measurement that is running ticks the pad every
time the sweep hand comes back to twelve, so it can be followed without looking
at it — which is most of what a stopwatch you are holding is worth over one on
the wall. The menu can be shut and a game can have the pad; the measurement is
yours either way. It marks the turn of the hand and only that: an alarm after a
length you set is a different instrument, and this one has no number to set it
with. `[chrono] rumble = false` leaves it to be read rather than felt.

```toml
[chrono]
rumble = true                 # tick when the sweep hand comes round
```

There is **one stopwatch**, however many tiles draw one: start it here, walk to
another page, and it is the same measurement still running. It ships on `Now`,
and it is the one tile that may not be [left on
screen](#the-readings-how-busy-how-full-how-hot) — a pusher over a game is a
button you cannot reach.

A control tile draws no icon: the control is the picture, and a glyph over a
switch is the tile saying the same thing twice in the room it has for one.
A clock is the clearest case — a clock glyph beside a clock face is the tile
saying it twice.
Give it a wider `span` when its name will not sit above the control in one
cell; a bar is three cells and a media tile three by two, and neither needs
one.

### A card of verbs, drawn as rows

A tile with `control = "rows"` holds a page rather than opening one: the
entries under it are drawn **inside** it, one to a line, and the same up and
down that walks the grid walks them.

```toml
[[menu.items.items]]
label = "Power"
control = "rows"
detail = "Auto-sleep 30 min"      # the line along the foot; optional
span = [2, 3]

  [[menu.items.items.items]]
  label = "Rest mode"
  action = "exec:systemctl suspend"

  [[menu.items.items.items]]
  label = "Restart"
  action = "exec:systemctl reboot"
  confirm = true

  [[menu.items.items.items]]
  label = "Full shutdown"
  action = "exec:systemctl poweroff"
  confirm = true
```

Reach for one when the tiles you are writing are **verbs**. A verb has nothing
to show but its name, so a cell spent on one says a single word — and four of
them side by side say four words in the room one sentence needs, which is how
`Screensaver` ended up drawn as `Screensa…` — it is a row on `Display ›
Screen` for exactly that reason. Stacked, each row has the whole card to be as
long as it is, and the line under it that a one-row tile draws nowhere.

Do **not** reach for one where a tile has something to show. A card that holds
a value, what is playing, or where a stick is, is a card because the drawing
needs the room; a row is one line of text, and `omapad check` refuses a control
inside one rather than drawing a blank line.

The tile's own `label` is the heading over the rows and its `detail` the line
along the foot — the two ends of the card, both small and in capitals. A row
takes a `label`, an `icon`, an `action`, and `confirm`, `repeat` or `stay` the
way any other row does; the hold fills the row rather than the card, so the one
verb that cannot be taken back is the one that counts down. A row cannot open a
further page — the card is already the page — and a card is not a page either,
so it spends no X or Y. It carries no `icon` of its own either: a glyph at the
heading's size in front of tracked capitals reads as a bullet, and the marks on
a card of rows belong to its rows.

**A card can list its rows too.** `from` on one is a command whose output
becomes the rows — which is what `Audio` is made of, a card of outputs beside a
card of inputs. A listed card is read when the **page it stands on settles**
rather than at a press, because nobody enters a card; until the first answer
lands it draws its own `empty` words rather than nothing.

**A listing that finds one thing it has marked is drawn as a reading** — the
heading names it, the line is the answer, and A does nothing, because picking
it would set what is already set. Plug a second device in and it is a list
again. A lone row with no mark in front of it is something to run or to switch
to, so a folder with one script in it is a list of one and A runs it.

### A folder of your own scripts

`System › Scripts` is a listed card pointed at a folder rather than at a
command that knows something:

```bash
mkdir -p ~/.config/omapad/scripts
install -m755 /dev/stdin ~/.config/omapad/scripts/night-mode.sh <<'EOF'
#!/bin/sh
omarchy-theme-set ristretto
EOF
```

Every **executable** file in there is a row, read when the System page settles,
named by the file without its extension. Pressing A on it runs it in a scope of
its own, so a daemon restart does not kill what it started. Nothing else has to
be edited — no binding, no setting, no line in `config.toml` — and a file that
is not executable is left out rather than shown as a row that does nothing.

It is an ordinary card, so `config.toml` is where it is moved, renamed or
pointed at a different folder.

**A row may carry its own `detail`**, drawn small under its name, and that is
the thing a [choice tile](#tiles-that-hold-a-value) could never have: the
sentence saying how this value differs from the one under it. So a card of rows
is also the shape for a short list of *settings* — the row that is in force is
**filled**, and `stay` keeps the menu up while you watch the fill move.
**System › Start in** is the one that ships:

```toml
[[menu.items.items]]
label = "Start in"
detail = "The mode at the next start"
control = "rows"
span = [3, 2]                     # three, because a sentence needs the width

  [[menu.items.items.items]]
  label = "Game mode"
  detail = "A bigger bar; nothing else changes"
  action = "pad:start_mode=game"
  stay = true

  [[menu.items.items.items]]
  label = "Desktop"
  detail = "Omarchy's own bar, at its own size"
  action = "pad:start_mode=desktop"
  stay = true
```

**A goes into a card**, the way it takes a slider, and up and down walk the
page until it does — so a thumb pushing down always reaches the tile below,
never the second line of the one it is on. Inside, up and down walk the rows,
A runs the row in front, and **B leaves the card without leaving the page**.
The row you were on is waiting the next time you go in.

Two marks, one thing each. A line runs down the side of the list: the row **in
force** is its length of that line, lit, with a small stroke marking each end
of it, and it is there whether or not you have selected the card. The row **A would run**
has a faint ground instead, and only once you are inside. A card of verbs has
nothing lit, because nothing on one is in force.

### A card of switches, whose keys latch

The card above is a set of **alternatives** — one row is in force and picking
the next one lets the last one out, which is why what says so is a length of
the line beside the rows. Some lists are not like that. `many = true` is the
same card with its keys **latching**: any number of rows can be on at once, the
line goes, and every row gets a small key at its head with a lit core in the
middle while it is down.

```toml
[[menu.items.items]]
label = "Feedback"
detail = "What a press answers with"
control = "rows"
many = true
span = [3, 2]

  [[menu.items.items.items]]
  label = "Vibration"
  detail = "The motor, in the hands"
  action = "pad:rumble=toggle"

  [[menu.items.items.items]]
  label = "Sounds"
  detail = "A cue, in the room"
  action = "pad:sound=toggle"
```

It is an old radio, and both of its mechanisms: the band buttons are
interlocked, so pressing one lets the last one out, and the tone keys beside
them each stay down on their own. One bank, two mechanisms — and a length of
line can only ever say the first of them, because a length has one start and
one end.

Write each row as a **toggle** — `pad:<name>=toggle` or `live:<name>=toggle` —
because that is what both flips the switch and says which way it is set. A row
written as `pad:rumble=on` would light while it was on and never turn it off
again. The menu stays up on every row of one without being asked: the whole of
what a bank is for is pressing the next key while looking at the last. A
latching row carries no glyph, because the key is already at its head.

Reach for one only where the rows are **not** alternatives. The test is whether
pressing the second row should let the first one out — if it should, the card
above it is the one you want.

### Giving a page its own X or Y

A group, or any tile that opens a page, can take **X and Y** for a job of its
own while that page is in front:

```toml
[[menu.items]]
label = "Apps"

  [menu.items.keys]
  Y = { tap = "exec:omarchy-menu toggle apps", short = "All" }
```

**Not A or B.** A commits and B leaves, in every layer, every surface and every
application — a page that could take either would be the one place on the pad
where that stopped being true. And a page that takes X keeps `menu:close` on
the hold, because X is how you leave from everywhere else in here. `omapad
check` enforces both, naming the page.

`short` is the one word the legend prints; `desc` is the phrase the guide does.
And the guide agrees: open it with Y from a page that has spent a key and it
prints that page's answer, not the menu's in general.

**Nothing in the shipped tree spends one**, which is the answer rather than an
omission. A button is worth taking only when what it would do is not reachable
on screen, and a page of tiles almost always has room for one more tile — which
costs nobody a reflex. Play / pause on `Now` is the example of when not to: the
tile is right there.

### The head: the clock, and whatever else you point at it

`[[menu.head]]` is the read-only strip above the bar. Nothing on it is
selectable — a clock is not a button — and a cell prints either a time it
renders itself or the last thing a command said.

```toml
[[menu.head]]
span = [2, 3]
over = { from = "id -un", ttl = 0 }   # a line above, small and in capitals
format = "%H:%M"                      # the headline — strftime
under = "%A"                          # and a line below it

[[menu.head]]
span = [4, 1]
from = "omarchy-weather-status"
ttl = 900                     # seconds before it is asked again
empty = "Weather unavailable" # before the first answer, and after a failure
```

**A cell is up to three lines and every one of them is the same kind of
thing** — a time it renders itself, or the last thing a command said. A bare
string is a `format`, which is what `under = "%A"` is; a table is the long
form, and it is how a line becomes a command instead. Three lines in one cell
rather than three cells, because the head packs first fit — two cells could
land side by side as easily as stacked, and a name over a clock over a weekday
is one thing read at three sizes.

**A cell more than one row tall prints a headline.** The clock is `[2, 3]`
because the time is the one thing on this surface meant to be read from the far
side of the room — it is set at the very top of the scale, and it needs the
height with a name over it and a day under it. A cell with fewer rows than its
lines need clips rather than shrinking. At `[2, 1]` the same cell prints a line of text, so shortening it is how
you turn the clock down rather than a way of breaking it.

`ttl` is how fresh the answer has to be, which is not how often the menu
repaints — the card redraws every couple of seconds whatever this says, and the
weather is asked for once a quarter of an hour. **Zero never goes stale**, so
it is asked once a session: your name is not going to change under the menu.

**omapad owns nothing about the weather.** It runs the string you put in `from`
and draws what comes back; `omarchy-weather-status` owns the lookup,
`omarchy-weather-icon` owns the condition glyph — the same one Omarchy's own
bar draws — `omarchy-weather-location` owns where you are, and each prints its
own failure. The shipped cell pipes them through a `sed` that drops the place
and puts the glyph where the word `Temp` was, which is wording rather than
weather. Point the cell at something else and it says something else. A command
that answers with nothing leaves the last answer up rather than blanking the
cell.

**Apps is the couch's list, not the machine's.** Four of its rows are named
applications and the fifth is *everything installed*, because a controller menu
that tried to be a launcher would be a list nobody can walk with a thumbstick.
The four are what a sofa reaches for: Steam Big Picture, Discord, Spotify and
YouTube — the game, the people you are playing with, the music and the
television. Three of them **launch or focus**: with a pointer this slow, a
second copy of a chat client is never what was asked for, so if the window is
already open the row walks to it instead.

Discord is the row that cannot assume anything, and it is worth reading if you
are writing rows of your own — Omarchy installs Discord as a webapp as readily
as pacman installs the client, so the row asks rather than guessing:

```toml
[[menu.items.items]]
icon = "󰙯"
label = "Discord"
detail = "Voice chat"
action = 'exec:omarchy-launch-or-focus discord "$(omarchy-cmd-present discord && echo uwsm-app -- discord || echo omarchy-launch-webapp https://discord.com/channels/@me)"'
```

An `exec:` action is a **shell** command, so `$(...)`, `&&` and `||` all work
and a row can decide something at the moment it is pressed. (A TOML value in
single quotes is a literal string, which is what keeps the double quotes
inside it readable.)

### Rows that list what is plugged in

Some answers are not in a config file. Which speakers are in the room changes
when a television is plugged in, and a row that could only name what was
written down would be pointing at whatever was there when you wrote it. So a
row can **list** its submenu instead of holding one:

```toml
[[menu.items.items]]
icon = "󰓃"
label = "Output"
detail = "Speakers, headphones, the TV"
empty = "No outputs found"                            # if it prints nothing
action = "exec:omarchy-audio-output-set-default %1 %2"
from = "..."     # a command; one line per row
```

`from` is a shell command, run when the row is entered — every time, so a
television plugged in a moment ago is on the list. Each line it prints is one
row, tab separated: **the label**, then the values `action` takes as `%1` to
`%9`. A label that starts with `*` is the one **in force** and is ticked — the
mark `pactl` and `wpctl` already print beside the current device. The values
are quoted as they go in, so a device that names itself with a space or a
semicolon stays a name rather than becoming a second command.

Picking a row here keeps the menu up and moves the tick to it, because
choosing an output you cannot hear yet and being thrown back to the desktop
means opening the menu again to try the other one.

The press does not wait for the command. The page opens the moment the row is
entered and the devices appear when the answer does, which for a page entered
before means the devices it listed last until the fresh ones land. Two settings
bound it: `[menu] list_timeout_ms` is how late an answer may be before the page
is called empty, and `[menu] list_limit` is how many of its lines reach it.

The bar that ships is eight cards, in the order a thumb reaches for them:

| Group | Holds |
|---|---|
| **Now** | the keyboard, the volume, what is playing, the stopwatch — and the workspace lock and *Keep the controller* while there is anything to use them on |
| **Apps** | Steam Big Picture, Discord, Spotify, YouTube, browser, terminal, everything installed |
| **Workspaces** | fullscreen, next window, float / tile, close |
| **Audio** | which speakers, which microphone, and where dictation puts the words |
| **Display** | how bright the screen is, scale and the screensaver in one card, how much omapad's own surfaces move, how hard they round their corners |
| **Controller** | everything about the pad — see below |
| **Readings** | how busy, how full, how hot — the page [the HUD draws](#the-readings-how-busy-how-full-how-hot) |
| **System** | start in, lock, suspend, log out, restart, power off, your own scripts, whether an update is waiting, and the way out into the Omarchy menu |

What you change now, then what you open, then what is on screen, then the room,
then the pad, then the machine. `Now` is where the menu opens, which is why the
things you reach for while you are sitting in the room are on it rather than at
the top of `Audio` and `Display` — those pages keep what you set when the room
changes instead. Brightness is the line between the two, and it is on
`Display`: how bright the screen is follows the light coming in the window
rather than what you are doing, which is the same errand as the scale.

### What the machine is doing

`Volume` and `Music` on `Now`, and `Brightness` on `Display`, read the
**machine** rather than omapad: the real percentage, and the real track. They
were five stepping rows and a mute row before, none of which could say what the
number was.

omapad knows nothing about PulseAudio, backlights or MPRIS. It runs a command
and parses what comes back, and **every command is a setting**, under `[live]`:

```toml
[live]
volume_read = 'pactl get-sink-volume "$(omarchy-audio-output-sink)"'
volume_set = 'pactl set-sink-volume "$(omarchy-audio-output-sink)" %1%'
brightness_set = "omarchy-brightness-display --no-osd %1%"
media_read = "omarchy-shell media status"
```

`%1` is where the new value goes. An empty string is a reading this machine
does not have: nothing is asked for it, and its tile draws blank.

**Volume deliberately does not go through `omarchy-audio-output-volume`.** That
helper always ends in `omarchy-osd`, so every press from the menu would raise
Omarchy's own overlay *over the tile showing the same number*. It talks to the
sink instead — the same one the helper itself resolves, so a speaker tuning
chain is still respected. Put the helper in `volume_set` if you would rather
have the OSD. Brightness keeps its helper, which offers `--no-osd`: DDC, Apple
displays and backlights are three code paths omapad should not reimplement.

Nothing is asked while the menu is shut, and nothing is asked at frame rate: a
reading is read once when its tile appears, again after a press has changed it,
and otherwise only while its own tile is selected.

Any of them works from a button too — `live:volume=up`, `live:media=next` — the
same grammar as `pad:`.

**`Music` is one tile and A plays or pauses it**, because it has two states,
the way a switch does. `Previous` and `Next` are two tiles either side of it,
so left and right walk to them exactly as they walk to anything else. A
direction the player says is closed ticks the motor rather than doing nothing
quietly.

### The readings: how busy, how full, how hot

`Readings` is the page for the machine underneath — the processor, the memory,
the disk, and whatever else this one publishes a number for. Each tile says
what it is and what it says, with a bar where there is a scale to draw it
against.

**Nothing here can be pressed.** A temperature is published, not set, so A on
one of these does nothing at all rather than finding something to do.

**Where each reading comes from is a setting**, because not one of them is true
of every machine. Which chip holds a temperature, whether the graphics card
publishes a load, whether anything here knows a game's frame rate — all three
differ between two laptops of the same year.

```toml
[sysinfo]
cpu = "proc:stat"                              # ships on
memory = "proc:meminfo"                        # ships on
disk = "mount:/"                               # any path on the filesystem
temperature = "hwmon:coretemp/temp1_input"     # yours will differ
gpu = "cmd:nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader"
```

`proc:` reads the two files omapad parses, `mount:` is a filesystem, `hwmon:`
is a sensor, `file:` is any file holding one number and `cmd:` is a helper that
prints one. **An empty source is a reading this machine does not have**:
nothing is asked for it, and no tile is drawn.

Three ship with a source because three are true of every Linux. A temperature
does not, and that is deliberate — every machine has sensors and the numbers
are not interchangeable, so one picked for you would print the wrong number
under the right word. Find yours and name it:

```bash
grep . /sys/class/hwmon/*/name     # which chips this machine has
omapad check                       # what each reading says right now
```

The chip is named rather than numbered because `hwmon4` is a battery on one
boot and a network card on the next. `hwmon:*/temp1_input` takes whichever chip
has a file of that name, for anyone who does not mind which.

`omapad check` prints what every reading currently says, which is the way to
tell a source that is pointed at nothing from a reading you never asked for —
on screen the two look identical, because both draw nothing.

#### Leaving them on screen

**`Keep on screen` puts that page over everything**, at the size and in the
places you arranged it. Game mode takes Omarchy's bar away, which is the right
trade for a screen watched from a sofa and leaves one question unanswered:
what the machine is doing while it does it.

It is the same page — not a second screen with its own settings. Move a tile in
the menu and it moves here; make one wider and it is wider here.

**The grid here is the screen**, and that is the one thing that is not the
menu's. A menu page is as many rows as its tiles came to and scrolls, so
nothing on it means *the bottom*; a screen has a bottom edge, so this one is
cut into a fixed `[hud] rows` and a cell is a share of the screen rather than a
number of pixels. Put a tile in the last row and the last column and it is in
the corner of the screen.

That one number is the density as well: raise it for thinner tiles and finer
placement, lower it for fewer and bigger ones.

**Carrying a tile down this page stops on its last row**, because this is the
page with a bottom edge — every other page keeps growing a row at a time, and
the menu draws this one with the same bottom the screen has, so what you
arrange is what you get. A cell hand-edited past the end is pulled onto the
last row; `omapad check --layout` says when that happens.

`[hud] margin` is how far off the edge it starts. Set it to `0` for the corner
itself; it defaults to a hair in because a television cuts its own edges off.
The readings never come up underneath a bar either way.

Two more things are different from the menu, and both are the point:

- **A tile with something to press is not drawn.** The switch that turns this
  on stays in the menu, because there is nothing to press out here: the
  readings take no clicks, no keys and no buttons, and everything goes straight
  through them to whatever is underneath. What that leaves is a reading and a
  clock — the page ships with one, and a clock over a game is what the bar game
  mode took away was for. A stopwatch has a pusher on it, so it stays in the
  menu.
- **A reading that has never answered draws nothing at all.** A fan this
  machine publishes no number for is not a tile saying nothing, it is no tile —
  which is what makes one page correct on two machines.

It sits under anything you open on purpose, so the menu, the guide and the
keyboard all cover it, and it never comes up underneath a bar.

```toml
[hud]
show = false        # on is remembered: it is a setting, not a screen you opened
page = "hud"        # which group it draws, by id
rows = 12           # how many rows the screen is cut into
margin = 16         # 0 puts a corner tile in the corner
opacity = 0.9       # it is read while something else is watched
```

```bash
omapad ctl hud toggle
```

### The Controller submenu

Everything about the pad itself is one row, because a controller is one thing:

| Tile | What it is |
|---|---|
| Vibration | **a switch** — the motor on or off |
| Strength | **a bar** — how hard it buzzes |
| Sounds | **a switch** — whether a press answers the room as well as the hands |
| Loudness | **a bar** — how loud that answer is |
| Hold time | **a bar** — [how long every hold on this pad takes](#holding-for-a-hand-that-cannot) |
| Button labels | **a card** — [which console the badges print](#which-console-the-badges-are-printed-for): follow the pad, Nintendo, Xbox, PlayStation |
| Profile | **a card** — which codes this pad is read with: detect it, Nintendo Pro, Xbox |
| Buttons | **a card** — the [bindings guide](#the-bindings-guide), and the [mapping screen](#controller-mapping) |
| Sticks | **four bars and two dials** — pointer speed, scroll speed, how much of each stick does nothing, and where each thumb is right now |
| Hide the pointer | **a switch** — whether [a press puts the pointer away](#not-having-to-aim-the-pointer-and-snap) until something points again |
| Button style | **walked in place** — [how they are drawn](#how-the-badges-are-drawn): Filled or Stencil |

**The page is two bands, not twelve tiles.** Along the top is what a press
answers with, each switch beside the bar saying how much of it. Under it stand
the three cards — what the pad prints, what it is, and what its buttons do —
with the sticks, the pointer switch and the badge style in a column beside
them. It was a switch, a bar, a card and a door in the order they happened to
be written in, at four heights that lined up with nothing, which is a page you
read through rather than glance at.

**A switch is a switch, not two rows that both tick.** `On` and `Off` as
separate rows was always a switch written out longhand, and a tile that draws
which way it is flipped says it in the space of one. A choice with two values
is walked in place the same way: `‹ Stencil ›`, and A steps it.

**A number is a bar.** Speed, dead zone and vibration strength were ten rows
saying "faster" and "slower" across two screens, and not one of them could say
what the number was or that it had stopped at the end of its range. They are
five bars now, and `Sticks` is one page instead of two because four bars is
not the list eight stepping rows was.

`Button labels` and `Profile` are **cards of rows** on purpose. A tile that
walks a choice shows one value, so it has nowhere to put the line under each
choice saying how they differ — and those are the two where getting it wrong
scrambles the face buttons, so that line is exactly what stops you. A card is
as wide as its rows, so all four are in front of you with their sentences on.

Everything but the guide is a setting rather than a command, and they
are the ones that belong on the pad rather than in a file: which profile a pad
takes and what its badges print are exactly the questions you have while holding
the thing and getting the wrong answer, how they are drawn is one you have while
looking at them from across the room, and how hard the motor ticks — or how fast
a thumb aims — is a preference about the room you are sitting in. So those
rows leave the menu up, the one in force is ticked, and each vibration row ticks
the motor as it lands — the number says nothing and the buzz says everything.

The speeds and the dead zones have no buzz to answer with, so they say the
number instead: the row prints where it has got to (`9 notches a second`, `12%`)
and stops printing a new one at the end of its range. They all **repeat**, so
you hold the button rather than pressing it eleven times, and the pointer keeps
moving under the open menu — which is what makes a step something you feel
rather than read.

What you pick is written to `~/.config/omapad/settings.toml` at the press, not
at shutdown, and it is merged **over** `config.toml`:

```toml
# omapad settings - written by the controller menu.
layout = "xbox"
rumble = false
rumble_strength = 0.35
scroll_speed = 12.0
```

Delete a line to hand that setting back to your config file, or the file to hand
back all of them. `omapad check` prints what is in there, since it outranks
what you wrote by hand. The same settings are reachable from a button with
[`pad:`](#the-action-grammar), and each takes effect immediately: a new profile
re-reads the pad that is already open, a new layout repaints every badge on
every surface at once. **System › Start in** is the one that does
not, and that is what it is for: it names the mode the *next* start comes up
in, so nothing on screen moves when you pick it.

**Workspaces** is the window in front — fullscreen, next window, float/tile, close
— and it is in the menu rather than only on the window layer (`ZL`) because the
window layer does not reach past an app that has taken the pad, and the menu
does. That is the way out of [a game hidden behind Steam Big
Picture](#a-game-that-opens-behind-steam-big-picture).

There is the same control socket for opening the menu without a pad:

```bash
omapad ctl menu toggle
```

## The bindings guide

**Controller › Buttons › Shortcuts** in the menu opens a map of the bindings in
force right now: one page per layer, and on every row the button itself and what it does.
Read-only — this is the map, not the editor; the config is where you change
things.

The rows are grouped **by the pad's own regions** (face buttons, D-pad,
shoulders, sticks, system buttons), because while you are looking for the button
you forgot, your finger is looking there too. A button is drawn **in its own
shape** rather than as a letter: a face button is round, a shoulder is cut away
at the corner your finger comes over, a trigger is the deeper one behind it, a
stick is ringed, and the small buttons like MINUS / PLUS are the round ones a
pad prints them on - or the oblong, for the two PlayStation draws that way. Those
shapes are real drawings — `assets/shapes/`, with the label already set into
them in Fira Code, see `assets/README.md`. A D-pad direction has no letter to
set, so what is drawn into the cross is the arm that direction lights; a
PlayStation face button has a symbol rather than a letter, and an Xbox Menu
button a mark rather than a word, so those are drawn into the same shapes the
letters go into. What each badge says depends on [which console the badges are
printed for](#which-console-the-badges-are-printed-for). The colours come from the theme:
printing one console's palette would have fought every Omarchy theme there
is.

| Button | Job |
|---|---|
| L / R · D-pad left / right | Previous / next page |
| A · B · X · Y · MINUS · PLUS · Right stick click · Capture | Close |
| HOME | Tap: close · Hold: switch mode |

The guide layer sits above the other two: opening it closes the keyboard and the
menu, so one surface reads the D-pad. Along the bottom of the page, under a
rule, is which page of how many — drawn the way the bar draws your workspaces,
numbers with the one you are on turned into a square, because the pages are
something you walk between the same way. A guide only one page long prints
nothing there.

What it writes comes from two places. The action itself is usually enough
(`key:ENTER` → "Enter", `click:left` → "Left click"), but a Lua dispatcher or a
script name says nothing on its own. For those the binding says it itself:

```toml
[bindings.base]
L = { tap = "hypr:hl.dsp.focus({ workspace = 'r-1' })", desc = "Previous workspace" }
HOME = { tap = "hypr:hl.dsp.window.cycle_next()", hold = "mode:toggle",
         hold_ms = 700, desc = "Next window", hold_desc = "Switch mode" }
```

`desc` shows up in the guide only; it does not touch how the binding works — a
table carrying nothing but a `desc` behaves exactly like the plain string
binding. `short` is the same sentence for [the game bar](#game-bar), in one
word, and is worth writing whenever the first word of `desc` is not the meaning
— "New tab" would be cut to "New". `hold_desc` and `hold_short` are the pair
for the other half of a tap/hold.

The guide writes down only the buttons the connected pad **really has**: in
XInput mode the Capture row never appears, because that button is not on that
profile. If a page does not fit in two columns the layer is split, `Base 1/2`
and so on, rather than clipped.

To open it without a pad:

```bash
omapad ctl guide toggle     # open | close | next | prev
```

## The bar widget

Everything omapad draws is **summoned** — the keyboard, the menu, the guide
and the mapping screen open and close. This is the one exception: a small
indicator on the Omarchy bar, the standing answer to "is the pad mine?".

What it shows: whether the pad is connected, which mode we are in, and (in the
tooltip) which application profile is active in desktop mode. In game mode it is
drawn in **the bar's own urgent colour** — rather than a colour we made up,
because the bar already has a way of saying "look here", and game mode is
exactly the case where the button you press does nothing on the desktop.

Left click opens the menu (whatever PLUS does on the pad), right click switches
mode — the only thing you need when the pad cannot do it for you.

To place it, add it to the bar layout in `~/.config/omarchy/shell.json`:

```json
{ "id": "canerakdas.omapad" }
```

We deliberately did not build a separate bar: a separate bar would have to draw
the clock, the battery and the network a second time, and would fight Omarchy's
own for the same screen edge. If the daemon goes quiet the widget takes itself
off the bar — the icon of a service that is not running is worse than a gap.

## Controller mapping

**Controller › Buttons › Remap the buttons** in the menu (or
`omapad ctl map open`)
opens the mapping screen: it asks for each button in turn, you press it, and it
writes the evdev code that arrived next to that name. The result is saved to
`~/.config/omapad/mapping.toml` **per device identity** — since the identity
changes with the hardware mode, the KP20's NS and XInput modes do not spoil each
other.

It asks in **what the pad in your hands prints**, not in the internal name the
mapping is written under: the names are the Switch's, so on an Xbox pad the
step called `MINUS` is asked for as *View*, and it is drawn as the button it is
— the same shapes the guide badges with, from the [layout in
force](#which-console-the-badges-are-printed-for). The name in words stands
under it, naming both printings, since a pad whose profile is wrong is usually
a pad printed unlike that profile's family. The final step is printed the same
way, in the three buttons just learned.

While the screen is up the pad is read **raw**: no binding runs and the pointer
does not move. Necessarily so, because the thing being fixed is precisely the
mapping that turns a button into a name. That is why the screen has exits of its
own, and all of them stay written at every step:

| Gesture | What it does |
|---|---|
| Press the button it asks for | Binds that name to that code and moves on to the next |
| Press a button **you have already named** | Skips the step it is asking about — an Xbox pad has no Capture |
| Hold any button for **2.5 s** | Leaves without saving |
| The last step | **A** saves, **B** discards, **X** starts over (printed as your pad prints them) |

The subtlety of the last step is that A, B and X there are the buttons *just
learned*. So the act of saving is also the cheapest test of the mapping — a
mapping learned wrong cannot be saved by accident, because the button that saves
is not where you think it is.

Analog triggers are learned too: pull the trigger at the ZL/ZR step and it is
written down as an axis (on XInput pads ZL/ZR are axes, not buttons) rather than
as a button.

To drive it from the keyboard:

```bash
omapad ctl map open      # open it
omapad ctl map skip      # skip the button it asks for
omapad ctl map back      # back to the previous button
omapad ctl map restart   # start over
omapad ctl map save      # save
omapad ctl map cancel    # close without saving
```

The settings the Controller menu changes are on the same socket, in the same
grammar the bindings use:

```bash
omapad ctl pad layout=xbox        # print Xbox names on every badge
omapad ctl pad profile=auto       # work out which pad this is again
omapad ctl pad rumble=toggle      # the motor, on or off
omapad ctl pad rumble_strength=up # one step louder
```

It takes effect the moment it is saved — you do not have to restart the daemon;
the device is already open, only the name table is resolved again.

The order of precedence: **profile → the measured mapping → the
`[device.buttons]` you wrote by hand**. So what you wrote by hand always wins,
and a measurement overrides the profile's assumption. Deleting `mapping.toml`
puts every pad back on its own profile.

## Typing

The arrow keys, Enter and Esc are on the base layer already. For real text there
is the on-screen keyboard: **MINUS** opens and closes it, and so does the right
stick click while the window layer is held.

The keyboard **is not clicked with the mouse** — the pad walks from key to key,
the selected key is highlighted, and A presses it. Typing is fast because you
never have to chase a key with the pointer; the keyboard surface takes no clicks
anyway, so it does not block the window underneath it either.

The keyboard **does not overlap** windows: it reserves space for itself at the
bottom of the screen (the layer-shell exclusive zone) and Hyprland fits the
tiled windows into the height that is left. Close the keyboard and the windows
go back to their old size.

### The keyboard layer

This layer takes over while the keyboard is up. The sticks keep doing their
base-layer jobs, and the pointer goes on working.

**ZL does not open the window layer here** — while the keyboard is up it is
Shift. One button cannot do both, and the keyboard exists in order to type;
window work waits until the keyboard is down. The rule is general: an open
surface's own binding outranks a layer trigger.

| Button | Job |
|---|---|
| D-pad | Walk between the keys (hold it and it keeps walking) |
| A | Press the selected key |
| B | Close the keyboard |
| X | Backspace |
| Y | Space |
| ZL | **Shift** — on for as long as you hold it, off when you let go |
| ZR | **Enter, then put the keyboard away** (`osk:submit`) |
| L / R | Previous / next layer |
| PLUS | Enter |
| HOME | Tap: close the keyboard · Hold: switch mode |
| Left stick click | Caps Lock (as two Shifts — [why](#changing-the-keys-to-suit-yourself)) |
| Right stick click | Left click — for clicking into a field |
| MINUS | Tap: close the keyboard (the same button that opened it) · Hold: **push to talk** |

The **▼** key at the bottom right of the keyboard closes it too — from inside
the keyboard, without reaching for the pad. In the same place on every layer.

Every key that one of those buttons reaches **prints it**, small, on the
label's own line: `Bksp` carries X, the space bar Y, `Shift` the left trigger,
`Enter` the right one — `osk:submit` sends Enter and then puts the keyboard
away, and Enter is the half of that you can point at. It is read off the live
bindings rather than written down here, so a rebound `[bindings.osk]` badges
itself — and the badge is the button as it is printed on the pad in your hands,
the same drawing the [guide](#the-bindings-guide) uses. Turn it off with
`badges = false` under `[osk]`.

The badges sit against the **right edge** of the key they belong to, so they
line up down the keyboard and can be read as one list of what the pad reaches.
`badge_align = "label"` puts each one back beside its own character instead,
the two centred together as a pair.

PLUS still types Enter without closing the keyboard; it is left unbadged
because two buttons cannot share one corner, and the trigger is the one a line
is actually finished with.

Walking vertically carries the **horizontal position** rather than the row
index: above `g` is `t`, the way it is on a real keyboard. Shift/Ctrl/Alt behave
like sticky keys — applied to the next key, then let go; where a symbol key has
a shift of its own it rides on top and is not pressed twice.

### Shift does two jobs

There are three ways to reach Shift, and all three write to the same state:

| How | Behaviour |
|---|---|
| The `Shift` key on screen | **Sticky**: applied to the next key, then let go |
| **ZL** (the left trigger) | **Held**: off when your finger lifts, like a real Shift |
| Left stick click | Caps Lock — for typing in capitals, it stays locked |

While Caps is on **the letters on the keyboard are drawn in capitals** too and
the `Caps` key stays lit; it does not touch the digits and the punctuation, and
with Shift on top the letters go small again — the way a real keyboard behaves.
Caps Lock is not really a modifier we send but a state the compositor keeps;
Hyprland keeps it **per keyboard device**, and since the only thing that changes
the caps state of the device omapad types through is omapad, tracking our
own state is not a guess but the very state applied to that device. Closing the
keyboard does not drop it.

The held Shift outlives the key it applies to: hold `ZL` and press `q w e` and
you get `QWE`, where the sticky lock falls away after the first key. The two do
not spoil each other — lock it, hold it, both drive the same `mods` state.

On a character key it changes **the character**, the way a real keyboard does:
`1` → `!`, `q` → `Q`. On keys that have one, it changes **the key itself** — `←`
and `→` on the bottom row become `↑` and `↓` with Shift held. That is how the
four arrow keys fit in two cells, and because that Shift is spent on the swap it
is not sent along with the key (with a `Ctrl` lock held, a shifted `→` types
`Ctrl+↓`).

In the top right corner of every key, what Shift would turn that key into is
written small and faint — the way console keyboards do it. With Shift locked the
two swap places and the label that comes forward is drawn **fainter**, so you
can see the layout has changed without reading the row. If Shift changes
nothing, the corner stays empty.

### Layers and layout

The default layout is **grid**: its first page is **a whole keyboard**, with the
key widths a real keyboard uses. A letter is one unit, Tab/Caps/Shift/Enter/space
are wider; because the fourteen-unit budget per row is the same on every row,
the columns stay lined up. Walking vertically carries the **horizontal
position** rather than the row index, so a wide Enter costs navigation nothing.

| Layer | Contents |
|---|---|
| `main` | `` ` ``, the digits, `- =`, the letters, `' ; , . /`, Tab/Caps/Shift/Enter/Bksp/Del |
| `sym` | `!@#$%^&*()_+`, `[]{}\|<>?:"~`, Esc/Tab/Ins/Del/Home/End/PgUp/PgDn, the arrows |
| `fn` | F1–F12, Ins/Del/Home/End/PgUp/PgDn, volume, brightness, media, PrtSc/Menu |

**The page of the application in front** can be added to these: a profile lends
the keyboard a page full of commands, the page joins the cycle for as long as
that window is in front, and it leaves with the window. Below, [the keyboard
page an application lends it](#the-keyboard-page-an-application-lends-it).

The bottom row is **the same on every page** — Ctrl, Alt, space, the arrows,
the microphone, Paste and ▼ do not move; only the first cell changes, carrying
the name of the page it goes to (`&123` → `Fn` → `abc`, and in a terminal `&123` → `Fn` →
`Term` → `abc`, in a browser `Web` in the same place). L/R walk the pages in
the same order.

`Paste` on the bottom row types `Ctrl+V` — right everywhere outside a terminal.
The `Ctrl+Shift+V` a terminal wants lives on the application's own page (below),
because that is the place for a key that is something else in exactly one
application.

The cell beside it is [the microphone](#saying-it-instead-of-typing-it), which
is the one key on the keyboard that types nothing itself.

### Saying it instead of typing it

The **microphone** on the bottom row is the one key on the keyboard that types
nothing. A: dictation starts, you say the sentence, A again: it stops, and a
moment later the words arrive at the cursor — typed by whatever is doing the
dictating, into the window the keyboard is open over.

It is there because a sentence walked letter by letter with a thumb is the
slowest thing this program asks anybody to do, and it is the thing a keyboard
is for. Thirty keys of travel become one press, one sentence and one press.

The key **lights while the microphone is open**, and lights more quietly while
what was said is still being turned into text. That second half is the reason
there are two looks: nothing appears on screen until it is over, and a key that
went dark the moment it stopped listening would read as a press that did
nothing.

**omapad does not transcribe anything itself.** The key runs a command, and
that command is [voxtype](https://voxtype.io), which
Omarchy installs from its own menu → *Install* → *AI* → *Dictation*. The model,
the language and the microphone are voxtype's own settings (`voxtype
configure`) and omapad deliberately does not reach into them — which also means
**the English model it installs by default will not transcribe another
language**; change that in voxtype, not here.

**The key is only on the keyboard when there is something to dictate with.**
If the first word of the command is not a program this machine has, the
keyboard is built without the key and the space bar keeps the cell: a key that
cannot work is one you press from across a room while the screen does not
change.

```toml
[osk]
dictate = "voxtype record toggle"                 # "" takes the key away
dictate_state = "$XDG_RUNTIME_DIR/voxtype/state"  # where it says what it is doing
```

`dictate_state` is the file the tool writes `idle` / `recording` /
`transcribing` into, and it is the whole of how the key knows to be lit. A file
rather than a command, because it is read several times a second while the
keyboard is up. Point `dictate` at something else and the key runs that
instead; leave `dictate_state` empty and the key still works, it just cannot
say so.

### Push to talk, on the button that opens the keyboard

The key above is a switch: press, speak, press again. **MINUS held is the
other gesture** — the microphone is open for exactly as long as the button is
down, and the words arrive when your thumb comes off. Tap the same button and
the keyboard opens, which is what it always did.

It is the gesture the dictation tools are actually built for (`record start`
and `record stop` exist for precisely this, and Omarchy binds F9 that way),
and it is the better one from a sofa: there is nothing to remember and nothing
to leave switched on. The switch stays because a key you walk to with a D-pad
cannot be held — A is already doing the pressing.

```toml
[osk]
talk_start = "voxtype record start"
talk_stop  = "voxtype record stop"
```

Two commands rather than one, because a gesture that ends when a finger lifts
cannot ask the tool which way it is currently pointing: a toggle that fell out
of step once would stay out of step, and the next press would close a
microphone somebody had just opened.

**This is the one hold on the pad that lasts rather than fires.** Every other
`hold =` runs once when the hold lands — `hold = "key:ENTER"` means one Enter,
not a column of them — so an action only spans the hold when it says it does.
Two things follow. `confirm = true` is refused beside one (the announced hold
counts down and *then* runs, which leaves nothing to last for), and clicking
the badge on the game bar does nothing rather than opening and closing the
microphone in the same breath.

The cost is the wait: recording starts after the hold lands (`hold_ms`, 500 ms
by default), so the first half-second of a sentence started on the press is
not there. Give it its own button to lose that — a plain binding has no tap to
wait for:

```toml
[bindings.base]
CAPTURE = "osk:talk"
```

```bash
omapad ctl osk talk       # open it, with no button to hold
omapad ctl osk talk off   # and close it
```

A **button** can reach the switch too, with `osk:dictate` — in `[bindings.osk]`, where
the key then prints that button the way every other key on the keyboard does,
or on any other layer, because this is the one `osk:` action that does not wait
for the keyboard to be up: a microphone types into the window in front whether
or not there is a keyboard drawn over it. Nothing is bound to it by default:
the face buttons are spoken for, and this is a key you can see. The gesture is
a press either way rather than a hold, because the hold half of a tap/hold pair
fires its press and release together and leaves no interval to speak in.

```bash
omapad ctl osk dictate      # the same thing without a pad
```

### Where the words land

Dictation types at the cursor, which is right when there is somewhere to type.
A game, a terminal running something, a window that is not yours at all: the
sentence goes nowhere and there is nothing to paste. **Audio › Dictate to
clipboard** is the switch for that — a tile on the same page as the outputs
and the microphones, because it is the same question asked of the other end of
the microphone.

**omapad never sees the words.** voxtype types them itself and leaves no
transcript behind, so switching where they land is something omapad asks
voxtype to do: the tile runs a command, and the shipped pair edits voxtype's
own `[output] mode` and restarts its daemon.

```toml
[osk]
dictate_clipboard = false           # the switch, and what the tile reads
dictate_clipboard_on  = "…"         # what turning it on runs
dictate_clipboard_off = "…"         # and off
```

Both or neither: `omapad check` names the pair if only one is set, because a
switch that can only go one way leaves the words on the clipboard for good
with nothing on the pad saying why. The shipped commands fit the voxtype
Omarchy installs; a machine that keeps that setting somewhere else replaces
them rather than going without the tile.

### Changing the keys to suit yourself

`[osk.keys]` changes a key's **label** or **what it does**; the key of the table
is the key's default action:

```toml
[osk.keys]
BACKSPACE = ""                  # a plain string = a label
close     = { label = "" }      # the key that puts the keyboard away
DELETE    = { label = "Delete" }
ENTER     = { label = "", shifted = "" }
```

The shell draws the keyboard with the same **Nerd Font** as the rest of Omarchy,
so any glyph in that set works as a label. A key that appears on more than one
page (Tab, Enter, Bksp) changes on all of them — the only answer that does not
surprise. The label you give also comes before the XKB lookup, so whatever the
layout says, what you wrote stays. An `action` that does not parse is rejected by
`omapad check`.

**Why Caps Lock is `LEFTSHIFT+RIGHTSHIFT`** — the one override that ships.
Omarchy's own layout sets `compose:caps,shift:both_capslock_cancel`
(`/usr/share/omarchy/default/hypr/input.lua`), which turns the Caps Lock key
into Compose: sending `KEY_CAPSLOCK` toggles nothing at all. The same option
makes **both shifts together** the way to toggle caps lock, and that is what we
send. If you have changed your layout, put it back:

```toml
[osk.keys]
CAPSLOCK = { action = "CAPSLOCK" }
```

If you prefer the shape of a real desktop keyboard:

```toml
[osk]
layout = "classic"    # sliding widths, full size
```

### Localisation

The labels are read from **the compositor's active keyboard layout**. Since
omapad sends keycodes, XKB decides the character; had it printed a fixed US
QWERTY, the key labelled `;` would really produce `ş` on a `tr` layout. Instead
the layout is taken from `hyprctl devices` and resolved with `xkbcli
compile-keymap`, so what is written on the key really is what will be typed. To
turn that off:

```toml
[osk]
labels_follow_layout = false
```

The layout table is cached until it changes; every time the keyboard opens,
Hyprland is asked which layout is active, and that is cheap. If the shell
restarts while the keyboard is up (a theme change does it) the panel puts itself
back together, because the state is refreshed every 2 seconds.

### Appearance

The keyboard (and the menu) are drawn by the `canerakdas.omapad` plugin
inside the Omarchy shell, so its colours, font, corner radius and the gap it
leaves at the screen edge all come from the same source as Omarchy's own
surfaces (`Color`, `Style.gapsOut`, `Style.cornerRadius`). Change the theme and
the keyboard changes with it, with no restart. A card takes the window
rounding as it is; what is drawn inside one steps down from it, so a corner
inside the menu is in proportion to the corners around it rather than equal to
them.

**How big they draw is omapad's own, and it follows the mode.** The same
screen is read at a keyboard on the desktop and from a sofa in game mode, so
there are two numbers rather than one:

```toml
[ui]
scale = 1.0        # on the desktop: exactly what Omarchy draws
game_scale = 1.0   # in game mode: the same, and see below for why
```

It **multiplies** the shell's own scale instead of replacing it, so a theme
that runs roomy — or a font you have already made bigger — keeps its
proportions and gets them scaled. Every surface follows it: the keyboard, the
menu, the guide, the mapping screen and the game bar. What does
not is the corner radius and the gap at the screen edge — those are the
compositor's geometry, shared with every window on screen, and a surface that
rounded its corners harder than its neighbours would just look wrong.

The switch is live. Change modes with a surface up and it is redrawn at the
other scale on the same line that changes everything else about it.

**Game mode ships at 1.0, and that is not an oversight.** The menu is built to
a design drawn for a 1920 screen watched from a sofa — a 128-pixel tile, a
45-pixel title — so its numbers are already couch-sized, and multiplying them
by a couch factor counts the room twice: the page comes to more than the
screen holds. Raise it and `[menu] cell` and `columns` have to come down with
it, or the page scrolls sideways.

**How hard a corner is rounded is the desktop's answer, and yours to move.**
`decoration:rounding` is what this machine rounds every window by, and a
surface of ours that picked its own number would be the one thing on screen
not listening to it. Where the compositor rounds nothing it is saying that
about *windows* — and a tile is not a window, so `[menu] tile_corner` is the
base there. `[ui] radius` multiplies whichever of the two is in force:

```toml
[ui]
radius = 1.0       # 1.0 is exactly what the desktop rounds; 0 is square
```

**Menu ▸ Display ▸ Corners** is the same number, and it is the one setting you
can only judge by looking at the thing it sets — so it is set from the surface
it changes, with the tiles rounding under the thumb that moves the slider.

It **steps by a rung of the same ladder everything else here is on**, not by
tenths: the type, the gaps and the radii off them all climb by √2 — the silver
ratio less one, two rungs to a doubling — and a corner is a size like any of
them. 23 pixels against 25 is not a difference anybody sees from a sofa; 23
against 32 is. So there are five stops, four presses end to end, and each one
is a corner you can tell from the last. It ends **one rung above the desktop's
own answer**: two rungs past it a 128-pixel tile is a circle, which is a
different shape rather than a rounder corner — wanting corners bigger than
that is a question about the base, and the base is `[menu] tile_corner`.

**The tile says which stop rather than what percentage.** `Square · Barely ·
Slight · The desktop's · Round`, over a bar drawn in the stops themselves — one segment each, lit up to where you are. A percentage is
a number you have to divide before it says anything, and the segments have
already said how far along. A number written by hand between two stops is kept
and prints itself; the pad walks the ladder.

### The face they are set in

Every word omapad writes — a menu label, a guide line, a key on the keyboard —
is set in the desktop's own font, because these surfaces are meant to read as
part of the session they stand in. Where that is the wrong answer, it is one
line:

```toml
[ui]
font = ""   # empty is the desktop's own; name one family to take it over
```

Name it the way `fc-list : family` spells it, and name **one**: Qt takes a
single family and a comma-separated list is a font nobody has installed. The
reason to set it is that a desktop font is chosen at a desk — a face picked
for a terminal at arm's length is rarely the face for a menu read across a
room, and this changes that without touching the desktop's.

**It does not reach the buttons, and that is deliberate.** The A, the B and
the ZR on these surfaces are drawings, and their letters were punched out of
the silhouettes in the face shipped with omapad. A typed label — the word the
shell sets into a blank shape for a button nothing is drawn for — takes that
same face, so the two always match. There are two font groups here: one you
choose, and one the drawings already decided.

### How much they move

Every animation on every surface — a label fading in, the grid catching up
with a selection, a badge leaning under a thumb — runs through one number:

```toml
[ui]
motion = 1.0   # 0 turns it off, 1 is as drawn - there is no slower
motion_follows_desktop = true   # and Hyprland gets to say it first
```

At `0` nothing moves: each animation lands on its last frame at once, so a
tile that faded out has still gone. `1` is the top of the range rather than
the middle — this asks for *less*, and every duration on these surfaces was
kept under 150 ms because a menu slower than that reads as a menu that is
lagging. It is on the pad as well —
**Menu ▸ Display ▸ Motion** — because whether a moving screen is readable is
something you find out by watching one, not by editing a file.

**The desktop gets the first word.** Hyprland's own `animations:enabled` is
this machine's answer to the same question, given about every window on
screen, so with `motion_follows_desktop` on, a desktop that has turned
animations off stops omapad's too — within a couple of seconds, on an open
menu, without a restart. It is a **veto rather than a scale**: the desktop can
take motion away and never add it, so `motion = 0` stays 0 on a desktop that
animates, and turning the following off hands the number back. It is the same
standing omapad already gives `decoration:rounding` and `gaps_out`: what the
compositor has decided about every window is not ours to argue with.

Two things deliberately do **not** follow it, because neither is decoration: 
`[ripple] ms`, and the countdown an announced hold fills a badge with. Those
say how long something takes to *happen*, and asking the screen to hold still
is not asking for a shorter wait before a window closes.

### The edge a television does not draw

A television is the one screen that does not show what it is sent: the outer
few percent are behind the bezel or cropped by the set, and a row of hints
along the bottom edge is the first thing it eats. If this desktop is on one,
this is the line to write:

```toml
[ui]
safe_area = 0.05   # a twentieth of each side, game mode only
```

**It ships at `0`, and game mode is why.** It was on at a twentieth whenever
game mode was, on the argument that game mode is when a television is being
used. It is not: game mode is the couch environment, and a couch is as often a
desk monitor turned up loud. On one of those the bar came off the bottom edge
and off both ends and floated in the middle of nothing, with a centimetre of
gap on three sides that were never cropping anything. A guess that costs a
twentieth of every edge is worse than no guess, because somebody on a set
knows they are on one and can say so, and somebody on a monitor has no way of
knowing what took their margins.

**Game mode only** either way: it is the only time omapad has any reason to
assume a television at all. And it is a **floor, not an addition** — a surface
whose own margin already stands further in keeps it, so the fullscreen menu
barely moves (its 45 down and 91 across are already about a twentieth of a
1080 screen) while the readings come in off their corner and the keyboard
comes up off the bottom.

**What comes in is what has to be read, not the ground under it.** The game
bar still reaches its edge and still fills the width of the screen; a bar
that stopped short of the corners would be saying something about the shape of
the screen rather than about what a set crops. It is the row of hints inside
it that moves.

`install.sh` links the checkout into `~/.config/omarchy/plugins/` as a
**symlink**, so it stays the single source; the shell reloads itself live when
a local plugin file changes. To manage it by hand:

```bash
omarchy-plugin-list | grep omapad
omarchy-plugin-disable canerakdas.omapad
omarchy-shell shell rescanPlugins
omarchy-plugin-validate .        # manifest check, from the checkout
```

`install.sh` runs that check itself before linking: the shell rejects an invalid
manifest on a console line nobody reads, so the error is said while there is
still somebody to say it to.

### Opening it without a pad

The daemon listens on a control socket, so you can open the keyboard from a
shortcut too:

```bash
omapad ctl osk toggle
omapad ctl menu toggle
omapad ctl guide toggle
omapad ctl map open
omapad ctl surface close     # close whichever is on top
omapad ctl press A           # fire a button as if it had been tapped
omapad ctl press ZL hold     # ...or the hold half of its binding
omapad ctl ripple left       # draw the burst a click leaves, without clicking
omapad ctl mode game
omapad ctl lock toggle       # the workspace lock: the pad is the app in front's
omapad ctl keep toggle       # ...and the other way: the pad is ours over an app
omapad ctl status
```

`press` names the button the way a binding does — `R`, not the `RB` an Xbox pad
prints on it — and goes through the whole input path, so the chords, the layers
and the tap/hold timing decide it exactly as they would for a thumb. It is also
where a click on a game-bar badge lands.

To add it to `~/.config/hypr/bindings.lua`:

```lua
o.bind("SUPER + K", "On-screen keyboard", "omapad ctl osk toggle")
```

The same surfaces open from Omarchy's own plugin IPC as well; the shell passes
the request on to the daemon as `omapad ctl`, so whichever door you come in
through, the state stays in one place:

```bash
omarchy-shell shell summon canerakdas.omapad '{"surface":"osk"}'
omarchy-shell shell toggle canerakdas.omapad '{}'   # the menu, with no payload
omarchy-shell shell hide   canerakdas.omapad        # closes whichever is open
```

The valid `surface` names: `osk` (`keyboard`), `menu`, `guide`, `map`
(`mapping`). The game bar is not in the list because it is not
summoned — it follows game mode, and its door is `omapad ctl mode`.

### Closing them with a keyboard

The surfaces are drawn over everything and driven with the pad; with no pad in
your hand that is a trap — a keyboard opened from a shortcut, a menu left open
as the battery died, a guide opened from a terminal. So **while a surface is on
screen — and only for as long as it is — the keyboard on the desk can close it
too.** `Esc` by default:

| On screen | `Esc` |
|---|---|
| The keyboard, the guide,mapping | closes it |
| The menu | closes it outright,from any depth |

The menu actually needs no esc key from this table: it takes the keyboard
and the mouse itself while it is open (the Omarchy menu's own Exclusive
focus),so `Esc` is its own leave — from any depth — and the daemon's
esc agrees,via `base`. The keyboard,ther guide,and mapping stay pad-only,
so for them this table is the way out. You do not have to bind a Hyprland
shortcut of your own;ther daemon reads the keyboard nodes itself. Ther
nodes are opened when a surface opens and closed when the last one closes —
the rest of the time nothing is listening to the keyboard.

```toml
[keyboard]
enabled = true
match = "auto"                # narrowed with "VVVV:PPPP" or part of a name
ignore = []                   # nodes that look like a keyboard and are not
grab = false                  # take the key from the application underneath too

[keyboard.bindings.base]
esc = "surface:close"
```

The tables carry the surfaces' names and are resolved in the same order as
the pad's:ther table of the surface on top first, then `base`. Ther values
use the same action grammar as the pad;three of them exist for a key that
cannot know what is on screen:

| Action | What it does |
|---|---|
| `surface:close` | closes whatever is on top |
| `surface:close_all` | closes all of them |
| `surface:back` | one level back,and out if there is nowhere to go |

The menu's own keys are its own:ther D-pad and the arrows walk the rows,Enter
picks,and Backspace climbs one level,where Esc leaves. A held D-pad
direction and a held arrow key both repeat,so the two hands feel the same.

If `grab = true`,ther keyboard is omapad's entirely while a surface is up;
and the menu no longer sees a grabbed key,either — so under `grab`,bind
the menu keys in `[keyboard.bindings.menu]` (the examples are in
`config/config.toml`,as comments),and it walks with the keyboard again. Ther
price:until the surface closes you cannot type anywhere,including where
the on-screen keyboard types.

`omapad check` says which keyboards it can open; if it can open none of them
(usually the user is not in the `input` group yet) it warns — because this is
exactly the kind of fault that would otherwise surface silently, the moment a
panel gets stuck.

## Using another controller

```bash
omapad dump
```

It prints the evdev code and the detected name of every button you press.

**You do not have to name your pad.** `[device] match` is `"auto"`, and a node
counts as a pad because of what it advertises — absolute axes and buttons in the
joystick range — not because of what it is called. Plug in any controller and it
is picked up; the keyboard, mouse and consumer-control nodes a wireless Xbox pad
enumerates alongside itself never are. The profile is read off the device the
same way, so ZL/ZR arriving as analog axes is handled without being asked for.

Write something here only to **choose between** pads, or to correct a pad that
lies about itself:

```toml
[device]
match = ["Xbox", "BEITONG"]   # tried in this order; a VID:PID works too:
                              # "045E:028E". One string is fine as well.
profile = "xbox"              # "auto" reads it off the device

[device.buttons]
0x13f = "PADDLE1"             # name the buttons it does not recognise
```

If the buttons land somewhere other than where the profile says, do not fight it
by hand: the [mapping screen](#controller-mapping) asks for them one by one,
measures them and writes them to `mapping.toml`. `[device.buttons]` still
applies on top of that — leave an entry there if you want to override the
measurement for one button.

## Development

```bash
python3 -m unittest discover -s tests -v
```

The tests feed a fake controller and write to fake uinput devices; they need
neither real hardware nor permission on `/dev/uinput`.

`docs/README.md` is the index for everything else:

| Where | What it holds |
|---|---|
| `docs/components/README.md` | The map: which file belongs to which component, and one document per component — what it owns, what it may assume, what breaks it |
| `docs/conventions/` | How to write in each language the project uses, and `naming.md` for file names and folder structure |
| `docs/roadmap.md` | Planned work, with per-item confidence |

The badges are generated rather than drawn in QML. `assets/shapes/*.svg` is the
source; `python3 assets/generate.py` sets the labels into them in Fira Code and
writes both `assets/buttons/*.svg` and `shell-plugin/ButtonArt.qml`. Run it
after touching a shape, and restart the shell — `omarchy-restart-shell` — since
the plugin only re-reads a new file on a restart. `assets/README.md` has the
rest.

## Troubleshooting

**`no permission on /dev/uinput`** — run `./install.sh`, then log out and back
in (`input` group membership only takes effect in a new session).

**A button acts as if it were held down** — ask the pad rather than watching
it: `omapad check` prints `held right now: L` for anything the kernel has
down, and with nothing touching the controller that is a stuck button. Do not
read this off `omapad dump` — the daemon holds the controller exclusively and
lets go of it whenever the app in front is handed the pad, so a press that
starts inside one of those windows and ends outside prints its `down` and
never its `up`, which looks identical. `dump` says as much when it starts.

**The controller does not show up in games** — you are in desktop mode and the
pad is grabbed exclusively. Hold HOME to switch to game mode, or set
`mode.grab = false`.

**The pointer drifts into a corner untouched** — the pad is lying about where
its sticks are resting. In NS mode the Beitong KP20 rests every axis half a
range away from the centre it declares, and uses only half of that range
(X: −32767..0, Y: 0..+32767); read raw, a stick at rest means half deflection,
and pushing all the way the other way only brings it back to zero. `recenter`
(on by default) calibrates every axis at connect time against where it **really**
rests; you can see it in the log:

```
INFO: axis 0x00 rests -0.50 off centre: neutral -16498, half-range 16269
```

If you are holding the stick while it connects, that axis is skipped
(`recenter_limit`, 0.60), so no calibration goes crooked by accident — let go
of the pad and reconnect it. A skip says so in the log too:

```
INFO: axis 0x04 rests -0.84 off centre, past recenter_limit 0.60: not
calibrating, it reads as a stick held at connect
```

To take your own measurement, `omapad dump` prints the raw values.

**A page scrolls on its own, at full speed, with the pad untouched** — the same
fault one step further on. An axis calibrated onto a stick that was being held
keeps only what travel is left over — a rest 0.84 out leaves a sixth of the
range — and every reading past that, the stick's true centre included, pins to
a full deflection the stick can never be let go of. Under `right_stick =
"scroll"` that is a page running down for as long as the daemon lives. The
limit above is what stops the calibration happening; if a pad still slips past
it, lower `pointer.recenter_limit` and reconnect.

**The pointer drifts** — not enough dead zone on that stick: raise
`pointer.left_deadzone` (0.10 → 0.15), or widen it from the pad in **Controller
› Sticks**, where you can watch the pointer settle as you move the bar.

**A control in the menu climbs on its own — the volume goes up with the pad on
the table** — a trigger resting off its minimum. The sticks are not the only
axes that lie about where they rest: a Beitong KP40A in XInput mode sits `ZR`
a fifth of the way in and never comes back down. Nothing notices while a
trigger is only a button — `device.trigger_release` is above that — but in the
menu a pull is a **rate**, so a fifth of a pull crosses the tile's whole range
every seven seconds or so, for as long as the menu is open. `device.trigger_rest`
(0.25) is the floor: at or below it there is no pull at all, and what is left
is spread over the rest of the travel, so the sweep still runs from nothing to
full speed. Ask the pad where yours is sitting — a trigger at rest sends no
event, so `dump` cannot see one and `omapad check` prints it:

```
ZR rests at 0.18 of its travel
```

If that number is above the floor, `check` says so and names what to raise.

**Steam presses keys at startup** — a virtual keyboard that declares `BTN_*`
codes gets a `js*` node from the kernel, and Steam, scanning for controllers at
startup, takes that for a ghost pad and applies the desktop layout. omapad's
declares none; to check, `grep -A5 "omapad virtual keyboard"
/proc/bus/input/devices` — there must be **no `js`** on the `Handlers` line. The
remaining possibility is Steam seeing the real pad through `js0`: we take the
evdev node with `EVIOCGRAB` but `js0` stays open. Then the fix is on Steam's
side: Settings → Controller → Desktop layout.

**The keyboard does not open** — check the daemon with `omapad ctl status` and
the plugin with `omarchy-plugin-list | grep omapad`. If the plugin is not
`enabled`: `omarchy-plugin-enable canerakdas.omapad`. The socket should be
under `$XDG_RUNTIME_DIR/omapad/osk.sock`.

**`hypr:` bindings do not work** — look at `journalctl --user -u omapad`; try
the Lua expression by hand with `hyprctl dispatch "hl.dsp...."`.

## Licence

MIT — see [`LICENSE`](LICENSE).

One vendored file keeps its own: `shell-plugin/fonts/FiraCode-Medium.ttf` is
Fira Code under the SIL Open Font Licence 1.1, and
[`shell-plugin/fonts/OFL.txt`](shell-plugin/fonts/OFL.txt) is that licence. It
is vendored rather than assumed because the badges are generated with it and a
missing font would silently redraw every label.
