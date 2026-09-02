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

One command, from nothing:

```bash
curl -fsSL https://raw.githubusercontent.com/canerakdas/omapad/main/boot.sh | bash
```

`boot.sh` clones the repo straight into
`~/.config/omarchy/plugins/canerakdas.omapad` — `manifest.json` is at the root,
so the checkout **is** the plugin, with no symlink — and hands over to
`install.sh` for the parts that need permissions. It is forty lines; read it
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
2. Copies the default config to `~/.config/omapad/config.toml` if there is
   none there.
3. Links the `omapad` command into `~/.local/bin`.
4. Validates the manifest, links the checkout into `~/.config/omarchy/plugins/`
   as `canerakdas.omapad`, and enables it. If you came through `omarchy plugin
   add`, the checkout is already there and this step only enables it.
5. Installs and starts the `omapad.service` user service.

Updating it — `omarchy plugin update` only pulls, so re-run the installer when
the pull touched the service or the udev rule. It is idempotent, and re-running
it always is the simpler rule:

```bash
omarchy plugin update canerakdas.omapad
~/.config/omarchy/plugins/canerakdas.omapad/install.sh
```

Checking it:

```bash
omapad check                    # config + the connected pad
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

Switching between them: **hold HOME for 0.7 s**, or pick `Game mode` in the
controller menu. Every switch drops a notification **and ticks the motor** —
one tick each way, because the switch is the press whose result you may not be
looking at: the bar is swapping itself out across the room while the pad is on
your lap. Either answer can be turned off on its own:

```toml
[mode]
notify = true   # the desktop notification
rumble = true   # the tick under the thumb
```

(MINUS + PLUS used to be the chord for this; it opens the **menu** now, which
had no second way in — see below.)

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

```toml
[mode]
handover_depth = 3       # generations in the family tree; Steam -> reaper -> wrapper -> game
handover_siblings = true # whether siblings count too (required for Proton)
```

**What still gets through is a gesture the game does not ask for**, and there
are two of them.

First: **the MINUS + PLUS chord, which opens the controller menu.** Two buttons
at once is not an input any game binds, and this is the door — the keyboard, the
window controls, game mode, the guide and the app launcher are all rows behind
it. The moment the menu opens omapad takes the pad back (otherwise the D-pad
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

`omapad ctl status` says which it is: `pad=ours` / `pad=app`.

You can also take Omarchy's bar away when game mode starts:

```toml
[mode]
hide_bar_in_game = true
```

It does that with `omarchy toggle bar off` — the bar parks off screen and the
shell is not restarted. It comes back on the way out, **and on the way down
too**: a daemon that dies in game mode must not leave you with a barless
desktop. On a machine with no Omarchy it is skipped quietly.

The reason: every widget on that bar opens a popup you click, and in game mode
the pad is in the game — so the whole bar is out of reach. A fullscreen game
should have the screen to itself.

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
`PLUS` → **Windows** → **Fullscreen**. The menu is the only thing that reaches
past an app holding the pad, which is why those rows are in it and not only on
the `ZL` window layer.

### Game bar

Hiding the bar leaves the screen empty; this is what takes its place. Turned on
with `[gamebar] enabled`, and shown in game mode only:

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

**And only the face buttons are printed at all** (`[gamebar] kinds`). They are
the half of the pad that changes under you: a profile rewrites X and Y, a layer
rewrites all four. A shoulder or a trigger means the same thing wherever the
scheme goes — RT clicks, LB and RB walk the workspaces — so a slot spent on one
repeats what the pad told you the first time you pressed it. Nothing is lost by
leaving them off this row: the two that walk the workspaces are drawn beside the
workspaces, and the one that opens the menu stands on the left. Name the regions
you want back — `kinds = ["face", "trigger"]`, out of `face`, `bumper`,
`trigger`, `dpad`, `stick`, `system` — and they are offered in the order the
thumbs reach them.

**Every badge lights up while its button is down** — the pill on the left, the
two beside the workspaces, the hints on the right. The bar is the only thing on
screen in game mode, and on the one surface whose job is to say what the buttons
do, saying which one you just pressed is the same sentence finished. That is
what a `filled` badge does; a `stencil` one inverts instead — see [how the
badges are drawn](#how-the-badges-are-drawn).

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
| `[gamebar] kinds` | which regions of the pad the hints are about; `["face"]` — the half that changes under you |

Both waits themselves are `[confirm] hold_ms` and `[confirm] confirm_ms`, and a
binding takes them by saying `confirm = true` rather than naming its own
numbers.

At most **three actions** stand on the right, and they **do not lie**: they are
the face buttons really bound in the layer that is live right now, resolved
through exactly the path a press takes — `[gamebar] kinds` is what widens that
to the rest of the pad. Gestures that mean the same thing everywhere (confirm,
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
enabled = true
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
they are also the two the pad can change about itself — **Controller › Speed**
in the menu, or `pad:pointer_speed=up`
and `pad:scroll_speed=down` on a button. Both rows repeat while you hold them,
both print where the number has got to, and the pointer keeps moving under the
open menu, so you set them by feel. What you land on is written to
`settings.toml`.

```toml
[pointer]
speed = 1100.0      # pixels per second at full deflection
accel = 2.2         # the response curve: 1.0 linear, higher = finer near centre
deadzone = 0.10

[scroll]
speed = 8.0         # wheel notches per second at full deflection
accel = 2.0         # the same curve, for the wheel
ramp = 3.0          # …and how much faster a stick held one way gets
ramp_ms = 900       # after this long holding it. 1.0 = off
natural = false     # true inverts the direction
```

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
walks (first `repeat_delay_ms`, then `repeat_rate_ms`). The only thing you lose
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
| Right stick | scroll (in game mode: **walk focus**) | move the window |
| A | Enter / confirm | fullscreen |
| B | Esc / back | close the window |
| X | middle click | float/tile |
| Y | **right click** | take the window out (float+pin) |
| ZR | left click | – |
| ZL | **window layer (hold)** | – |
| L / R | previous / next workspace (the pad ticks) | move the window to the previous / next workspace |
| D-pad | arrow keys | window focus (by direction) |
| PLUS | tap: **the controller menu**, hold: the Omarchy menu | toggle split |
| MINUS | **the on-screen keyboard** | – |
| MINUS + PLUS | **the controller menu** (a chord, everywhere, and the only way in over a game) | – |
| HOME | tap: switch window, hold: **switch mode** | centre the window |
| Left stick click | middle click | pin the window |
| Right stick click | back (mouse 4) | the on-screen keyboard |
| Capture* | tap: screenshot, hold: region | screen recording |

\* The Capture button only exists in NS mode (see below).

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
face circle and system pill the letters are set into. Nothing on a badge is a
character the font happened to have.

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
bar's own text colour on the bar, the key's colour on the keyboard.

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
| `menu:toggle\|open\|close\|up\|down\|press\|back` | the controller menu |
| `guide:toggle\|open\|close` | the bindings guide |
| `guide:next\|prev` | turn the guide's page |
| `mode:toggle\|desktop\|game` | switch mode |
| `pad:profile=auto\|nintendo_pro\|xbox` | which codes this pad is read with |
| `pad:layout=auto\|nintendo\|xbox\|playstation` | which console's names the badges print |
| `pad:rumble=on\|off\|toggle` | the motor |
| `pad:rumble_strength=up\|down\|<0..1>` | how hard it ticks |
| `pad:pointer_speed=up\|down\|<200..4000>` | how fast the pointer aims |
| `pad:scroll_speed=up\|down\|<1..40>` | how fast the wheel turns |
| `snap:left\|right\|up\|down` | move the pointer to the window that way and focus it |
| `snap:centre` | put the pointer in the middle of the window in front |
| `focus:next\|prev` | walk the application's own controls (Tab / Shift+Tab) |
| `focus:up\|down\|left\|right` | the same, with the arrow keys |
| `focus:activate\|back` | press the focused control / step back out |
| `nop` | cancel an inherited binding |

Every `pad:` value also takes `next` / `prev`, which steps through what that
setting holds — so one button can walk what the menu offers as a list of rows.
What is chosen from the pad is written to `~/.config/omapad/settings.toml`
and wins over `config.toml` until you delete it; see [the Controller
menu](#the-controller-submenu).

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
| `hold_ms` | how long the hold waits — 500 ms by default, 1200 for an announced one |
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
```

A chord **takes the press outright**: neither button does its own job, and a
layer trigger inside one does not open its layer. Which button goes down first
does not matter — "at the same time" arrives as two separate events, and no
finger decides their order.

The price is this: a button named in a chord fires **on the way up, not on the
way down**. Whether it is a chord or a press of its own cannot be known until
its partner has had its chance to go down. An imperceptible delay, but a chord
button is a bad place for dragging (a click held down).

Chords are bound **everywhere**, not to a layer. The reason is the one chord
that ships: over an app that has taken the pad it is the only way in, and that
has to work wherever you are. A chord is also the one gesture that **always
reaches past** an app holding the pad, whatever it runs — two buttons at once
is not an input any game asks you for.

### Adding a layer

```toml
[layers.apps]
button = "PLUS"
left_stick = "none"       # cursor | scroll | resize | move | none
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

A profile may also say what a **stick** is for, with the same `left_stick` /
`right_stick` roles a layer takes (`cursor`, `scroll`, `resize`, `move`, `snap`,
`focus`, `none`). It has the last word at rest and in game mode, on the same
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
```

| Button | In a terminal | Otherwise |
|---|---|---|
| X | **Backspace** — repeats while held | middle click |
| Y | **paste** (`Ctrl+Shift+V`) | right click |
| Y **held** | **`Ctrl+C`** — interrupt | – |
| Left stick click | **clear the screen** (`Ctrl+L`) | middle click |
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

What is **left alone**: `A` is Enter, `B` is Esc, `ZR` is the left click, and
the D-pad is the arrows the line editor and the history are walked with.

What the profile **spends**: `X` and the left stick were the pad's two middle
clicks, so a terminal now has none — text selected with a mouse but never
copied is no longer reachable from the pad. That is the price of a paste that
works with the clipboard everything else on this desktop uses. `Y` was the
right click, which is the one this profile is happiest to lose.

### Rumble

Write `rumble = true` on a binding and the pad gives a short tick when that
binding fires:

```toml
[bindings.base]
Y = { tap = "hypr:hl.dsp.window.center()", rumble = true }
```

In the shipped scheme this flag is not on anywhere. The rumble's two standing
jobs are elsewhere. One is the **confirmation countdown**: the pad ticks when
the `confirm_ms` above runs out. With the screen off or a window fullscreen you
do not see the notification but you do feel the rumble — and that situation is
the whole reason the countdown exists. The other is the **mode switch**
(`[mode] rumble`), which is the same problem: what changes is across the room,
so one tick goes in and one comes back out.

**Controller › Vibration** in the menu turns it on and off and steps the
strength, ticking the motor at each step so you set it by feel rather than by
number; what you pick lands in `settings.toml`. The defaults, and the two knobs
the menu does not reach, are under `[rumble]`:

```toml
[rumble]
enabled = true
strong = 0.20         # 0..1, the low-frequency motor - this is the real "tick"
weak = 0.0            # 0..1, the high-frequency motor, on pads that have one
duration_ms = 60      # short enough to read as a tick rather than a buzz
```

The defaults were picked **by hand on a Beitong KP20 in NS mode**: this pad has
only wired up the low-frequency motor, and you cannot feel the high-frequency
one even at full power. On pads that wire up both, the really clean tick is
usually on `weak`, so the knob stays.

There is a timing floor too: `hid-nintendo` sends rumble packets **on a 50 ms
period**, so a pulse shorter than 50 ms can be swallowed entirely. If you feel
nothing, lengthen `duration_ms` first, then try the motors one at a time. On a
pad with no motor, or one opened read-only, rumble turns itself off quietly —
one line lands in `journalctl --user -u omapad` and nothing else changes.

The rumble fires when the action **really runs**: in game mode a binding outside
`[bindings.game]` does not run, so the pad does not tick either.

## The menu

To the right of the title stand **the day and the time** (`[menu] clock`,
strftime; leave it empty for none). The reason: game mode takes Omarchy's bar
away, and there is no other clock the pad can reach.

Press **PLUS**: a menu shaped like Omarchy's own opens in the middle of the
screen — a single column of rows, a header at the top saying where you are, and
a `›` to the right of the rows that lead into a submenu. **Hold** PLUS and the
real Omarchy menu opens; that menu wants a keyboard, this one is driven with the
pad.

Being a list rather than a radial is deliberate: a radial reads a stick angle in
one flick but takes no more than a handful of entries, and has nowhere to put a
submenu. The D-pad already walks a list well, and that is the shape the rest of
the desktop teaches anyway.

| Button | Job |
|---|---|
| D-pad up / down | Walk the rows (hold it and it keeps walking) |
| A · D-pad right | Pick — and go in, if it is a submenu |
| B · D-pad left | Back to the menu above; at the top it closes the menu |
| X · PLUS · Capture · Right stick click | Close the menu outright, from any depth |
| Y | Open [the bindings guide](#the-bindings-guide) |
| HOME | Tap: close the menu · Hold: switch mode |

`X` and `B` are not the same button twice: `B` walks back up **one** submenu at
a time, and from inside `Controller › Speeds` that is two presses, while `X`
leaves outright. `Y` is the pad's reach for something not on screen — the menu
has a `Controller › Shortcuts` row that opens the same guide, and `Y` is that
row without walking to it. It is the button for when you opened the menu
*because* you had forgotten which button does what.

The menu layer sits above the keyboard layer: opening the menu closes the
on-screen keyboard, so that exactly one surface reads the D-pad. Holding MINUS
still wins.

When a row is picked the menu **closes first and the command runs after** — so
the window you opened is not left behind the dimming. There are two exceptions.
Rows with `repeat = true` are things you *nudge* rather than *pick*, like volume
and brightness: they leave the menu where it is, hold A and it repeats like a
held keyboard key, and B is the way out. Rows with `stay = true` are the quieter
half of that — one press, and the menu stays up — which is what a row that
changes a setting the menu itself prints needs.

A row that *sets* something is **ticked** while that something is what is in
force, so a list of choices says which one you are on rather than making you
guess.

### Writing the menu to suit yourself

The rows are under `[[menu.items]]`; each row takes either an `action` (**the
same grammar** as the button bindings) or an `items` list that opens a submenu.

```toml
[[menu.items]]
icon = ""                    # any glyph in the shell's font
label = "Terminal"
action = "exec:omarchy-launch-terminal"

[[menu.items]]
icon = ""
label = "Audio"
detail = "Drive volume and playback from here"   # a quieter second line under the label

  [[menu.items.items]]
  label = "Volume up"
  repeat = true              # keep the menu open, and repeat while held
  action = "exec:omarchy-audio-output-volume raise"

[[menu.items]]
label = "Xbox labels"
stay = true                  # keep the menu open, but fire once
action = "pad:layout=xbox"   # and this row is ticked while it is in force
```

If you redefine the `items` list in your own config it replaces **the whole**
shipped tree rather than being merged row by row — your menu is your menu.

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

The tree that ships is nine rows deep at the top, grouped so that the ones you
reach for from a sofa are the ones nearest the opening selection: **Apps** (Steam
Big Picture, Discord, Spotify, YouTube, browser, terminal, everything
installed) · Keyboard · **Windows** ·
**Audio** (volume, playback) · **Display** (brightness, scale, screensaver) · Game
mode · **Controller** · **System** (lock, suspend, log out, restart, power off) ·
Omarchy menu. What you open, then what is on screen, then the room, then the pad,
then the machine — and last, on its own, the way out into the Omarchy menu, which
has everything else and wants a keyboard. The volume and brightness rows are
`repeat = true`.

### The Controller submenu

Everything about the pad itself is one row, because a controller is one thing:

| Row | What it is |
|---|---|
| Shortcuts | the [bindings guide](#the-bindings-guide) — what every button does |
| Speed | how fast the two thumbs are: pointer faster/slower, scroll faster/slower |
| Vibration | the motor: on, off, stronger, weaker |
| Button labels | [which console the badges print](#which-console-the-badges-are-printed-for): follow the pad, Nintendo, Xbox, PlayStation |
| Button style | [how they are drawn](#how-the-badges-are-drawn): filled, or the label punched out of a solid shape |
| Profile | which codes this pad is read with: detect it, Nintendo Pro, Xbox |
| Remap the buttons | the [mapping screen](#controller-mapping) |

What you look up is first, then what you feel, then what you set once and forget.
The two speeds share one screen because they are the same decision made twice —
and a submenu of two rows is not a place.

Everything but the guide is a setting rather than a command, and they
are the ones that belong on the pad rather than in a file: which profile a pad
takes and what its badges print are exactly the questions you have while holding
the thing and getting the wrong answer, how they are drawn is one you have while
looking at them from across the room, and how hard the motor ticks — or how fast
a thumb aims — is a preference about the room you are sitting in. So those
rows leave the menu up, the one in force is ticked, and each vibration row ticks
the motor as it lands — the number says nothing and the buzz says everything.

The two speeds have no buzz to answer with, so they say the number instead: the
row prints where it has got to (`9 notches a second`) and stops printing a new
one at the end of its range. Both **repeat**, so you hold the button rather than
pressing it eleven times, and the pointer keeps moving under the open menu —
which is what makes a step something you feel rather than read.

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
every surface at once.

**Windows** is the window in front — fullscreen, next window, float/tile, close
— and it is in the menu rather than only on the window layer (`ZL`) because the
window layer does not reach past an app that has taken the pad, and the menu
does. That is the way out of [a game hidden behind Steam Big
Picture](#a-game-that-opens-behind-steam-big-picture).

There is the same control socket for opening the menu without a pad:

```bash
omapad ctl menu toggle
```

## The bindings guide

**Controller › Shortcuts** in the menu opens a map of the bindings in force right
now: one page per layer, and on every row the button itself and what it does.
Read-only — this is the map, not the editor; the config is where you change
things.

The rows are grouped **by the pad's own regions** (face buttons, D-pad,
shoulders, sticks, system buttons), because while you are looking for the button
you forgot, your finger is looking there too. A button is drawn **in its own
shape** rather than as a letter: a face button is round, a shoulder is cut away
at the corner your finger comes over, a trigger is the deeper one behind it, a
stick is ringed, and the small buttons like MINUS / PLUS are lentils. Those
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

**Controller › Remap the buttons** in the menu (or `omapad ctl map open`)
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
| MINUS | Close the keyboard (the same button that opened it) |

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
Paste and ▼ do not move; only the first cell changes, carrying the name of the
page it goes to (`&123` → `Fn` → `abc`, and in a terminal `&123` → `Fn` →
`Term` → `abc`, in a browser `Web` in the same place). L/R walk the pages in
the same order.

`Paste` on the bottom row types `Ctrl+V` — right everywhere outside a terminal.
The `Ctrl+Shift+V` a terminal wants lives on the application's own page (below),
because that is the place for a key that is something else in exactly one
application.

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
the keyboard changes with it, with no restart.

**How big they draw is omapad's own, and it follows the mode.** The same
screen is read at a keyboard on the desktop and from a sofa in game mode, so
there are two numbers rather than one:

```toml
[ui]
scale = 1.0        # on the desktop: exactly what Omarchy draws
game_scale = 1.25  # in game mode: a quarter bigger, for the couch
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
omapad ctl mode game
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
| The keyboard, the guide, mapping | closes it |
| The menu | goes up one level, and closes the menu at the root |

You do not have to bind a Hyprland shortcut of your own; the daemon reads the
keyboard nodes itself. The nodes are opened when a surface opens and closed when
the last one closes — the rest of the time nothing is listening to the keyboard.

```toml
[keyboard]
enabled = true
match = "auto"                # narrowed with "VVVV:PPPP" or part of a name
ignore = []                   # nodes that look like a keyboard and are not
grab = false                  # take the key from the application underneath too

[keyboard.bindings.base]
esc = "surface:close"

[keyboard.bindings.menu]
esc = "surface:back"
```

The tables carry the surfaces' names and are resolved in the same order as the
pad's: the table of the surface on top first, then `base`. The values use the
same action grammar as the pad; three of them exist for a key that cannot know
what is on screen:

| Action | What it does |
|---|---|
| `surface:close` | closes whatever is on top |
| `surface:close_all` | closes all of them |
| `surface:back` | one level back, and out if there is nowhere to go |

The arrow keys are deliberately not bound: with `grab = false` the key also
reaches the window underneath, so an arrow walking the menu would play the game
behind it too. Say `grab = true` and the keyboard is omapad's entirely while a
surface is up — and then walking the menu with the arrow keys makes sense as
well (the examples are in `config/config.toml`, as comments). The price: until
the surface closes you cannot type anywhere, including where the on-screen
keyboard types.

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
(`recenter_limit`), so no calibration goes crooked by accident — let go of the
pad and reconnect it. To take your own measurement, `omapad dump` prints the
raw values.

**The pointer drifts** — not enough dead zone on the sticks: raise
`pointer.deadzone` (0.10 → 0.15).

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
