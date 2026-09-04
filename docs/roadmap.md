# omapad roadmap

Scoped against this checkout: a daemon that owns the pad and types through
uinput, and an Omarchy shell plugin that draws the on-screen keyboard. Each
item says what it takes and how confident that estimate is.

Items marked **Verified** were tested against the running compositor and the
installed shell rather than estimated from documentation.

| Status | Meaning |
|---|---|
| **✅ Done** | Implemented in the working tree and covered by tests or a live check. |
| **🗑 Removed** | Was built, then taken back out. The item stays for what it measured. |
| **📦 Shelved** | Was built and worked, then taken back out to keep the shipped set small. The code is kept; the item is the design for putting it back. |
| **Ready** | The mechanism is confirmed working on this machine. What's left is writing it down. |
| **Buildable** | No unknowns in the way. The cost is the work itself, not the risk. |
| **Constrained** | Possible, but partial or unreliable in ways worth deciding on before starting. |

Effort is relative: **S** hours, **M** a day or so, **L** more than that.

---

## Phase 1 — Two things that are simply wrong

Both are small and both have a confirmed fix. One of them turned out not to be
the bug it looked like.

### 01. Cycle through empty workspaces too · ✅ Done · S

`L`/`R` use `workspace = 'r+1'`, and the *r* means **range** — it walks every
workspace in the monitor's range instead of skipping the empty ones (`e` =
existing). Shipped config and the daemon test now agree on `r+1`.

**Caveat (still open):** `r±1` follows the monitor's workspace range and does
not stop at ten. If you want a fixed 1–10 loop, omapad should hold the number
itself and dispatch the absolute id, which also makes wrap-around predictable.

### 02. The screensaver interrupting the keyboard · ✅ Done · S

This isn't a stacking problem. The keyboard already sits on the overlay layer,
above every ordinary window, and the screensaver is an ordinary window. What
actually happens is that **the idle timer runs while you use the controller**:
navigating the keyboard moves a selection over a socket and produces no Wayland
input at all, so as far as the compositor is concerned the session was
untouched.

**Done:** `Keyboard.qml` now binds a Quickshell `IdleInhibitor` (`Quickshell.Wayland`)
to the panel window's `opened` property. Omarchy's idle service runs its monitor
with `respectInhibitors: true`, so the screensaver is held off while typing.

**Worth extending past the keyboard (not done):** any pad activity in desktop
mode should hold the inhibitor with a short trailing timeout, otherwise reading
a page with the right stick still counts as idle.

---

## Phase 2 — Reworking the keyboard

Mostly data, not machinery. The layout lives in one Python file and the view
draws whatever it is handed, so page contents and labels are cheap to move.
Where a change did reach the model it stayed small: a per-key shift
alternative, a held modifier, an override table, a caps flag.

### 03. Controller buttons inside the keyboard · ✅ Done · S

Pure configuration in `[bindings.osk]`. Done:

| Button | Today | Now |
|---|---|---|
| `B` | Backspace | Close the keyboard |
| `X` | Space | Backspace |
| `Y` | Shift latch | Space |
| `L3` | Left click | Caps Lock |
| `LT` | — | Shift, held |

**The `LT` row is built, and it needed two mechanisms.** Both triggers now mean
something else while the keyboard is up:

| Trigger | While the keyboard is open |
|---|---|
| `ZL` / `LT` | **Shift, held** — down for as long as the finger is |
| `ZR` / `RT` | **`osk:submit`** — Enter, then the keyboard goes away |

- **A held modifier, not a latch.** `osk:hold:<mod>` sets the modifier on press
  and clears it on release, and `clear_latches()` now spares whatever a finger
  is holding — so `ZL` plus `q w e` types `QWE`, while the on-screen `Shift`
  still falls away after one key. The two write to the same `mods` state and do
  not fight. A hold is dropped when the keyboard closes, because the trigger's
  release is not routed to the keyboard once it is down.
- **A surface binding now outranks a layer trigger.** `ZL` holds the window
  layer everywhere else, and a layer trigger never fired its own binding. The
  keyboard and the menu are implicit layers, so they had no way to shadow one;
  `surface_override()` gives them that, checked in the same order the surfaces
  outrank each other. The cost is deliberate: **window ops are unreachable
  while the keyboard is open** — a button cannot mean two things, and typing is
  what the keyboard is for.
- `ZR` is left click at the base layer, and clicking into another field is
  worth keeping while typing, so left click moved to the **right stick click** —
  the thing already aiming the cursor. Not `CAPTURE`, which looks free but
  exists only on the `nintendo_pro` profile: a click parked there would do
  nothing in XInput mode.

### 04. Page one: a whole keyboard · ✅ Done · M

Page one is now a full keyboard, and shaped like one: `Tab`, `Caps`, `Shift`,
`Enter` and `Backspace` are back on it rather than a page turn away, the key
left of the `1` is where every keyboard puts it, and the keys are **sized the
way a real keyboard sizes them**.

```
`   1 2 3 4 5 6 7 8 9 0 - = Bksp
Tab   q w e r t y u i o p '  Del
Caps   a s d f g h j k l ;  Enter
Shift   z x c v b n m , . /  Shift
&123  Ctrl  Alt  [  Space  ]  ← →  Paste  ▼
```

**The even-column rule was dropped, and it turned out to have been paying for
nothing.** The grid insisted on uniform widths so a D-pad would walk it
predictably — but `move_vertical` carries the horizontal *position*, not the
column index, so a wide `Enter` costs nothing to walk past. What has to match
is the **width budget**: fourteen units per row, on every page, because the
three pages share a bottom row.

- **Word labels where they fit**, glyphs where they do not: `Tab`/`Caps`/
  `Shift`/`Enter`/`Space`/`Paste` are words — and they fit precisely because
  those keys are the wide ones. `Bksp` and `Del` are shortened rather than
  drawn: `⌫` and `⌦` are one pixel apart at this size and the wrong one eats a
  word. `▼` stays a glyph, since nothing it could be called is shorter.
- **Ctrl and Alt stayed.** The original write-up wanted them off page one, but
  the bottom row has the width now, and a keyboard that cannot send `Ctrl+C` is
  a worse trade than one crowded cell.
- **A second Shift on the right**, as on a real keyboard: from the right-hand
  side of the grid it halves the travel to reach one.
- **The bottom row is identical on all three pages** — only the first cell
  changes, and it names the page it goes to (`&123` → `Fn` → `abc`, the same
  order `L`/`R` walk). The keys you press without looking do not move when the
  page does.
- **The arrows cost two cells, not four**, because Shift swaps them (below).
- **Paste ships as `Ctrl+V`**, still wrong in a terminal until item 09 lands.

**The per-key shift alternative that item 04 asked for is built:** a key can
carry an `alt` action, taken instead while Shift is latched, and the shift is
spent on the swap rather than sent along with the key — a latched `Ctrl` plus a
shifted `→` types `Ctrl+↓`, not `Ctrl+Shift+→`.

### 05. Shifted characters, shown dimmer · ✅ Done · S

Two halves, both shipped:

- **The corner glyph.** Every key prints what Shift would make of it in a small,
  quiet label in its top-right corner, the way a console keyboard does. The
  payload carries it as `x`, computed from the same XKB-aware label lookup as
  the main label, so it follows the compositor's layout too. Shift latched swaps
  the two, and a key Shift does not change sends an empty string, so the quiet
  keys stay quiet.
- **The dimmer state.** While Shift is latched, a key whose label actually
  changed is drawn at a lower alpha, so the swap is visible at a glance instead
  of having to read the row.
- **The letters print no corner hint.** `Q` over every `q` is twenty-six hints
  for the one thing every keyboard already teaches, and it drowned out the ones
  worth reading. A key whose two labels differ only in case sends an empty
  corner.

**The correction from the original write-up held:** `1234567890` shifted gives
`!@#$%^&*()`, not `~!@#$%^&*()` — `~` is the shift of the backtick, which lives
on the symbol page. And because labels are read from the live XKB layout, this
row prints something different on a non-US layout, correctly so.

### 06. Three pages instead of two · ✅ Done · S

The default grid already ships three pages — `main`, `sym`, `fn` — and the
layer machinery, `L`/`R` cycling and the page keys all handle any number of
pages. Verified against the shipped `LAYOUTS` table: grid cycles
`main → sym → fn`, and the README documents all three. No code change was
needed; the "two pages" assumption in the original write-up was already ahead
of the code.

### 13. Caps Lock that works, and shows · ✅ Done · S

The `Caps` key did nothing, and the reason was not in omapad: Omarchy's own
layout ships `compose:caps,shift:both_capslock_cancel`
(`/usr/share/omarchy/default/hypr/input.lua`), which turns the Caps Lock key
into Compose. `KEY_CAPSLOCK` toggles nothing at all on a stock Omarchy. So the
shipped default sends what that layout *does* answer to — **both shifts
together** — through item 14's override table rather than hard-coded, so a
layout that was never remapped puts it back in one line. **Verified** against
`hyprctl devices`: off → on → off.

**Showing it needed a state omapad does not own**, and the obvious route is
closed:

- Declaring `EV_LED` on the virtual keyboard gets nothing back — no event on
  the uinput fd, and `EVIOCGLED` stays zero. Hyprland does not push LED state
  to it. **Verified.**
- But caps lock is held **per keyboard device**: `hyprctl devices` shows this
  device's caps `true` while the physical keyboard's stays `false`. omapad
  owns the device its keys are typed from and is the only thing that ever
  toggles that device's caps — so following its own presses is not an
  approximation, it is the state that applies to what this keyboard types.
  **Verified.**

What that buys: letters print uppercase while caps is on, digits and
punctuation do not move, Shift over Caps goes back down, the labels still come
from the live XKB layout (`tr` prints `I` on the `ı` key), and the `Caps` key
stays lit the way a latch does. Nothing changes about what is *typed* —
omapad sends keycodes and the compositor applies caps itself. It survives the
keyboard closing, the way a real Caps Lock does.

`osk:caps` is the action, so L3 and the on-screen key take one path: the key
itself decides what gets sent, and both update the printed labels.

---

## Phase 3 — How the pad should behave everywhere else

The largest change in the list is item 07, because it is the one that has to be
right before the rest are worth building on.

### 07. A console-shaped default scheme · ✅ Done · M

The default map is now console-shaped: **A** confirms (Enter), **B** goes back
(Esc), and the triggers click. Implemented in the shipped config:

| Button | Was | Now |
|---|---|---|
| `A` | Left click | Enter / confirm |
| `B` | Right click | Esc / back |
| `X` | Enter | Middle click |
| `ZR` (RT) | Window layer | Left click |
| `ZL` (LT) | Precision cursor | Right click |

**The knock-on, decided and revised:** the window layer (was `ZR`) was first put
on the left bumper **L**, but that broke the workspace flow — the user found
"cannot change workspace without L" unacceptable. So the window layer went to
**MINUS** (Xbox Back/View, the modifier the user asked for) instead:

- **L** / **R** again walk the previous / next workspace (base).
- **MINUS** (hold) opens the window layer; MINUS is the trigger so it never fires
  its own binding, and **R** moves a window between workspaces while it is open.
- **Precision removed** (`precision_button = ""`), mechanism kept in code.
- **The window layer ended up on `ZL` after all**, not MINUS. MINUS is the small
  middle button and holding it while both thumbs work the D-pad and the face
  buttons is genuinely awkward — which is the constraint that decides this:
  the modifier has to be held by a finger that is not a thumb, so it is a
  shoulder or a trigger. The bumpers walk workspaces and that was already ruled
  untouchable, so it is the left trigger. Its right click moved to **Y**, which
  was a duplicate of B (`key:ESC`) and therefore cost nothing, and the freed
  **MINUS** made the on-screen keyboard a single button instead of a
  two-handed combination.
- **Mode switching moved onto a chord**, `MINUS + PLUS` (Back + Start), which
  needed a small chord mechanism: `[chords]` in the config, completion tested
  against everything currently held so the order two thumbs land in does not
  matter, and the press taken outright — no layer opens, no partner's pending
  tap fires late. Global rather than per-layer, because the way out of game
  mode has to work from wherever you are. The HOME long-press still works.
- The **media layer dropped off MINUS** — volume/playback/brightness are parked
  for now, to be folded into the menu (item 08) rather than overload MINUS with
  a second meaning. **Done:** they are rows in the shipped menu.

**Item 03's `LT` row is settled:** `ZL`/`LT` is right-click at the base layer,
so the keyboard leaves it unbound rather than turning a held left trigger into
Shift — that would give the trigger three meanings.

### 08. A menu instead of a keyboard shortcut · ✅ Done · M

Config-driven entries summoned by one button — **PLUS** taps it open, and
holding PLUS still reaches the real Omarchy menu, which wants a keyboard.

**Shipped as a list, not a radial.** The original write-up wanted a radial
picked by stick angle. A radial reads one flick well, but it caps out at a
handful of entries, has nowhere to put a submenu, and is a shape the desktop
teaches nowhere else. So the menu is shaped like the Omarchy menu instead:
centred card, a title line, one column of rows, `›` where a row drills in — the
same measurements and theme tokens, so the two read as one family. A D-pad
walks a list predictably, which is the same argument that shaped the keyboard's
grid (item 06).

**What shipped:**

- `omapad/menu.py` — the tree, the selection and the drill-down stack, with
  the position you left restored when you climb back out.
- `[[menu.items]]` in the config: `label`, `icon`, optional `detail`, and
  either an `action` from the ordinary binding grammar or an `items` submenu.
  Actions are parsed at build time, so a typo fails `omapad check`.
- `repeat = true` on a row you *nudge* rather than *pick* — volume, brightness.
  The menu stays put and a held button keeps firing, the way Omarchy's own
  volume keybind repeats `omarchy-audio-output-volume raise`. Every other row
  closes the menu on pick, and no ordinary row repeats under a resting thumb.
- Default tree, grouped so the root stays short and the couch-frequent rows sit
  nearest the opening selection: Apps (Steam · Browser · Terminal · All apps) ·
  Keyboard · Windows · Audio · Display · Game mode · Controller · System ·
  Omarchy menu — including the media rows item 07 parked.
- `[bindings.menu]`, an implicit layer like the keyboard's, that outranks it:
  opening the menu closes the keyboard so only one surface reads the D-pad.
- `shell-plugin/Menu.qml`, drawn from a second socket. The plugin's entry point
  is now `Panel.qml`, which mounts the keyboard and the menu together — a
  plugin gets one `panel` entry point, and two sockets do not need two plugins.
- `omapad ctl menu <toggle|open|close|up|down|press|back>`.

**Left out on purpose:** stick navigation. The sticks keep their base roles
while the menu is up, the way they do under the keyboard, so the pointer never
dies under you. Turning stick deflection into discrete row steps is a separate
mechanism and the D-pad already does the job.

**Since:** the menu also takes the keyboard and the mouse while it is open -
ther Omarchy menu's own focus rules - so the arrows,Enter and Esc drive it
over the same control socket the pad uses, and a cursor hovers, clicks and
dismisses the same way. Esc now leaves outright from any depth (strictly
closing,where it used to climb back level by level on the desk keyboard),and
clicking the scrim closes the menu,so the pointer is not handed through to
the window under it while the menu is up.

### 09. Per-application button profiles · ✅ Done · M

A profile matched on window class, layered over the defaults, so that `B` closes
the Omarchy menu, `Paste` knows it is in a terminal, and a game gets nothing at
all. Not every app needs an entry — the point is that any app can have one.

**Shipped as `[profile.<name>]`** in the config, each with a `match` (a class
string, or a list — any hit is enough — matched as a case-insensitive
substring, so `"foot"` catches `foot` and `Alacritty` catches most natural
names) and its own `[bindings]`. A profile changes only the buttons it names;
anything else resolves as `profile → layer → base`, and the implicit surfaces
(osk, menu, guide) keep outranking whatever app is underneath, the way the
original caveat wanted. A game is just an app with a profile that binds little
(or `nop`s what it does not want) — no special "game" behaviour, because a bad
default for one app is the right one for another. A profile binding that does
not parse surfaces in `omapad check`, and the active profile is logged to
`journalctl --user -u omapad`. Where two profiles match the same class the
earlier one wins.

**How:** the daemon subscribes once to Hyprland's `.socket2.sock` and swaps the
active profile on each `activewindow` event. Two practical corrections came out
of building it:

- **Connecting streams nothing on its own.** `.socket2.sock` only pushes events
  as they happen; a fresh (or reconnected) subscription does not replay the
  current focus. So the daemon seeds once with `hyprctl activewindow -j` on
  connect as well.
- **Focus changes were already happening.** The event stream gives live focus
  changes, and reading the class off the `activewindow` event (its first field)
  is cheaper than querying on every little change.

**Verified:** live against this compositor — the event socket delivers
`activewindow>>class,title`, `hyprctl activewindow` reports the class, and a
fresh subscription seeds the profile for the window actually focused.

### 10. A hint bar along the bottom · Buildable · M

What the buttons do right now, in the current context, the way a console shows
it. Only what changes is worth printing: `B` Back when a menu is open, `A`
Select — and not the D-pad, which means the same thing everywhere.

**Depends on 09, and inherits its honesty problem:** the bar can only show what
*omapad* maps, not what the focused app actually does with the keystroke it
receives. For apps with a profile that is the same thing. For apps without one it
is a guess, so the bar should stay quiet rather than print a label it cannot
stand behind.

---

## Phase 4 — Making it configurable by hand

Worth doing once the scheme underneath has settled, not before.

### 11. A place to see the bindings · ✅ Done · M

Shipped as a third surface — `omapad/guide.py`, `guide.sock`,
`shell-plugin/Guide.qml`, an implicit `[bindings.guide]` layer and
`omapad ctl guide <toggle|open|close|next|prev>` — opened from the menu's
**Shortcuts** row. Read-only, as the write-up wanted: seeing the map is most of
the value, and item 14 already made one key of it editable.

**The buttons are drawn as buttons, not as letters.** That is the whole point
of the surface. `A` in a list is a letter; a round face badge beside a
pill-shaped bumper is the thing under your thumb. So the badge carries the
*shape* — round face buttons, pill shoulders, a trigger with its bottom corners
squared off, a ringed stick, a lozenge for the small system buttons — and takes
its colours from the theme. A console's own palette (green A, red B) would read
as a controller in exactly one Omarchy theme and fight every other one.

- **Grouped by region of the pad, not by config order**: face buttons, D-pad,
  shoulders, sticks, system. That is where a hand looks for a button it has
  forgotten.
- **One page per layer**, walked with `L`/`R`, so the layered map the write-up
  said a flat list handles badly is simply four short pages. omapad packs the
  groups into columns because it is the side that knows when a layer no longer
  fits — a layer taller than two columns becomes `Base 1/2` rather than being
  clipped.
- **A layer that binds nothing gets no page**, and the sticks print their role
  (`Move the pointer`, `Resize the window`) rather than a binding, because that
  is what they carry.
- **It only prints buttons the connected pad has.** `CAPTURE` exists on the
  `nintendo_pro` profile alone, so in XInput mode the row is absent instead of
  lying. The pages are rebuilt when the guide opens, not at startup, since the
  pad can be switched between modes while the daemon runs.
- **The footer is the guide's own layer**, collapsed by what each binding does:
  half the pad closes it, and printing that eight times says nothing eight
  times.

**Descriptions come from the action, with an escape hatch.** `key:ENTER` is
"Enter" and `click:left` is "Left click" without anyone writing that down
twice, and a Lua dispatcher is read back as words. That last one is thin by
nature — `direction = 'u'` is not a sentence — so a binding can say what it
means outright, next to itself:

```toml
L = { tap = "hypr:hl.dsp.focus({ workspace = 'r-1' })", desc = "Previous workspace" }
```

**One bug fell out of that.** A table binding with no `hold` was treated as a
tap/hold pair whose hold did nothing, which waits for the release before firing
— so annotating a plain binding with `desc` would have quietly changed what it
does. A table that names no hold is now the plain binding it replaced.

**Editing it in place is still the second, larger step**, and it stays unbuilt:
a surface you drive with a pad is a poor text editor, and the config is one
file away.

### 14. Per-key labels and actions · ✅ Done · S

`[osk.keys]` overrides what a keyboard key **shows** or **does**, keyed by the
action it has by default — the one stable name a key has, since nobody wrote
down a row and a column:

```toml
[osk.keys]
BACKSPACE = ""                  # a bare string is the label
close     = { label = "" }      # the key that puts the keyboard away
CAPSLOCK  = { action = "CAPSLOCK" }   # undo the shipped default
```

The shell draws with Omarchy's Nerd Font, so its glyphs work as labels. A key
that appears on more than one page is overridden on all of them — the only
answer that does not surprise. A user's label outranks the XKB lookup, which
would otherwise print the layout's character over it. Overrides apply to a copy
of the shipped layout, so they cannot leak into it, and `omapad check`
refuses an action that does not parse.

**This is item 11 arriving from the other end.** 11 wants to *see* the whole
map; this lets one key of it be changed without touching Python. The two do not
conflict — a read-only view of the map is still most of 11's value.

---

## Found while using it

Neither of these was planned, and neither is really a feature. Both were
shipped the moment they were understood.

### 15. The keyboard that looked like a controller to Steam · ✅ Done · S

Opening Steam typed `2` into whatever had focus, again and again — and it was
ours. The virtual keyboard declared the high `KEY_*` range as `0x160-0x2ff`,
and two `BTN_*` blocks sit inside it: `BTN_DPAD_*` (`0x220-0x223`) and the forty
`BTN_TRIGGER_HAPPY` (`0x2c0-0x2e7`). **One button code is enough for `joydev` to
attach a `js*` node**, so every controller scan on the machine — Steam runs one
at startup — found a phantom pad whose buttons were this keyboard's keys, and
sent whatever its desktop layout maps them to.

Fixed by skipping all three BTN blocks; nothing omapad types reaches past
`KEY_MICMUTE` (`0xf8`) anyway. **Verified:** the `js` handler is gone from
`/proc/bus/input/devices`, and a test now refuses any BTN block while requiring
every code in `keymap.KEYS`. Whether Steam still types anything is the user's
to confirm; the remaining suspect is not ours — Steam reads the real pad's
`js0`, which `EVIOCGRAB` on the evdev node does not close.

### 16. Apps launched from the pad died with the daemon · ✅ Done · S

Steam's own log lines were landing in `journalctl --user -u omapad`, which is
how this surfaced. A child of a systemd service stays in that service's cgroup,
and the default `KillMode=control-group` means `systemctl --user restart
omapad` — which every config change asks for — SIGTERMs the browser or the
game just launched from the menu.

`exec:` now runs through `systemd-run --user --scope --collect`, so the command
gets a unit of its own and outlives the daemon that started it. Gated on
`INVOCATION_ID`: run straight from a checkout there is no cgroup to escape and
nothing to pay for, and if `systemd-run` is missing it warns and spawns plainly
rather than failing to launch. `KillMode=process` was the other option and is
worse — the apps would stay in omapad's cgroup and its journal.
**Verified:** a `Started [systemd-run] …` scope in the journal for a command
the daemon spawned.

### 17. A tick when the workspace changes · ✅ Done · S

L and R walk workspaces, and from the couch the screen is often the only thing
that says the press landed — which it does not say at all when the workspace
you arrive on is empty. The pad can answer for itself: `hid-nintendo` and
`xpad` both expose `FF_RUMBLE`, so a short nudge is one uploaded effect and one
write.

`rumble = true` on a binding rather than a rule about workspaces: the flag is
where the guide's `desc` already is, and item 09's per-app profiles inherit it
for free. Off everywhere else — a scheme where every press buzzes says nothing.
`InputDevice` now opens the node `O_RDWR` and falls back to read-only, the
effect is uploaded once per connection (an `EVIOCSFF` inside a button press is
latency under the thumb), and a pad with no motors costs one log line.

**Verified by feel, and the defaults came out of it.** The Beitong in NS mode
reports `FF=107030000`, but only its low-frequency motor moves: the
high-frequency one is silent at full magnitude, which is why the first default
- 45 ms of `weak`, the obvious choice for a light tick - felt like nothing at
all. `strong = 0.20` for 60 ms is the lightest of six combinations that still
reads as a click. Duration has a floor of its own: `hid-nintendo` sends rumble
packets every 50 ms, so a shorter pulse can fall between two of them.

### 18. Shoulders that are global except where they aren't · ✅ Done (browser pilot) · M

In Chromium — and in anything else built for a pad — L and R are the app's own
tab switcher. Ours took them outright, so inside those apps the app's own
navigation was gone; but they cannot simply be given away either, because
walking workspaces is exactly what you need while a full-screen app is up.

**What landed.** The shipped `[profile.browser]` gives L and R the browser's tab
switcher on a tap and the workspace on a hold. Two seconds in, the pad ticks and
a notification says what is coming and which button stops it; two seconds later
it happens. Letting go backs out, and so does the cancel button (`[confirm]
cancel_button`, B) — which is what makes a tap that ran long harmless. A warned
hold also swallows its own tap on release: you were plainly not asking for a
tab.

Three pieces, each general rather than special-cased: `on_release` on a binding,
so the shoulders fire coming back up and the same button can carry a hold
without its tap having already gone out; `confirm_ms` beside `hold_ms`, which
turns any hold into an announced one; and 17's tick, which is the half of the
announcement that survives a full-screen window or a dark screen — the case the
whole thing exists for.

**Still open.** Steam Big Picture is next and wants the same table with its own
match and its own tap. Two seconds and two seconds were guesses; they are now
`[confirm] hold_ms` and `confirm_ms` (1.2 s and 0.8 s), shorter because the game
bar draws the countdown - the badge fills in from the left over each wait - and
a wait you can watch does not have to be as long as one you cannot. The guide (item 11) knows nothing about profile bindings, so inside the
browser it still prints the base map — that is 10's territory as much as 11's.
And the cheaper alternative is worth remembering: ask once, on screen, the first
time a claiming app takes focus — *this app uses L/R; hand them over?* — a
decision made once per app rather than a gesture repeated. If the hold turns out
to feel like a chore, that is the fallback.

### 19. The stick that rested half a range off centre · ✅ Done · S

The cursor walked into the bottom-left corner the moment the pad connected, and
a full push the other way only held it still. Measured rather than guessed:
every axis on the Beitong KP20 in NS mode rests at half the advertised range
and then uses only that half — X and RX span `-32767..0`, Y and RY span
`0..32767`, each resting at its own midpoint. Against the advertised centre of
0 that reads as a permanent half deflection, and the far end of the stick is
exactly the centre the daemon thought it had.

Two things had to change together. The neutral comes from the value the axis
actually rests at, read with one `EVIOCGABS` at connect — an earlier attempt
sampled `EV_ABS` events over a window instead and never fired once, because
this pad sends nothing at all while it sits still. And the half-range becomes
the distance to the *nearer* advertised end, so both directions still reach
full speed on a half-range axis; a pad that rests where it claims to is
unaffected, its two ends being equidistant. A rest beyond `recenter_limit`
(0.90) is taken for a stick held during connect and left alone, since
calibrating onto it would freeze that direction for the session.

**Verified:** `axis 0x00 rests -0.50 off centre` for all four axes on connect,
and the measured travel — rest `-16379`, ends `-32542` and `0` — reproduced
across two runs.

### 20. Left click in a browser the pad had been handed to · ✅ Done · S

Reported as a bug — *left click doesn't work in the browser in gaming mode* —
and it was not one: `mode=game` had been on since the last mode switch, and in
game mode nothing but a `mode:` action ran. Right, whenever the game really is
the whole screen. It is wrong for the case that keeps coming up: a cloud
session in a browser, an emulator's own menu, a launcher. There the pad has to
reach the game *and* the page around it, and the desktop mode that could click
is the one that stops the page from seeing the pad at all.

`[bindings.game]` is the answer, and it is empty by default: game mode still
means the game gets the pad, and every button named here is one it stops
getting. Three things fall out of it being a layer rather than a special case.
It is **flat** — no layer opens inside it and no surface shows — so ZL is an
ordinary bindable button there rather than the window trigger. It **falls back
to base for the way out only**: a base binding is resolved but tagged with
where it came from, and `allowed()` lets a `mode:` action out of it and nothing
else, so HOME's hold and the chord keep working without the layer repeating
them — and a button the layer does name takes the base one's place, holds
included. And the guide grows a page for it the moment it is non-empty, which
is the one thing about game mode you cannot work out by pressing buttons.

The sticks needed their own answer. A click with a frozen cursor is worth
little, and the tick was gated on `mode == "desktop"`; it now follows the
stick's role instead, with `[mode] game_left_stick` / `game_right_stick`
defaulting to `none`. Off is still off, and the loop still sleeps: `needs_tick`
asks whether any stick has a role before it asks whether one is deflected.

**Still open.** Nothing says which buttons a game already uses, so a config
that names too many is a config that eats the game's own controls; the guide
page is the only warning. Suspicion, not measurement: the sticks are the part
worth being careful with, since a game reading the pad directly sees them too.

### 21. The pad that answered to its neighbour's name · ✅ Done (screen; profile still assumed) · M

`X` produced a right click. Not a binding problem: omapad names buttons by
what is *printed on the pad* and picks a profile from what the *driver
reports*, and those are two independent facts. The Beitong KP20 in NS mode
sends Switch Pro codes out of a shell printed with Xbox letters, so `0x134` -
`BTN_WEST`, the left face button, which the `nintendo_pro` profile calls `Y`
because on a Switch that is where Y is - arrives under the finger the case
labels `X`. Every face button answers to a neighbour. No profile can know
this: nothing in the protocol says what is silkscreened on the plastic.

Measured rather than argued about. The pad advertises exactly the 14 codes the
profile expects, so the code set was never wrong - only which physical button
each one sits under.

**What landed** is a fourth surface rather than another profile, because the
same gap opens for every pad nobody has written a profile for: `mapping.py`,
`mapping.sock`, `Mapping.qml`, a `Map controller` menu row and
`omapad ctl map <toggle|open|close|skip|back|restart|save|cancel>`. It asks
for each printed name in turn and writes down the code that answers, into
`~/.config/omapad/mapping.toml` - keyed by device identity, because the KP20
has one per hardware mode and different codes in each. Resolution runs
profile → measured → hand-written `[device.buttons]`, so a measurement beats an
assumption and a person still beats both. Saving re-resolves the live device,
so it takes effect without a restart.

Three things fall out of the screen reading the pad **raw** - it must, since
the map that would turn a code into a name is the thing being fixed - and each
needed its own answer, none of which can be inferred from a pad whose map is in
doubt: a code that already has a name **skips** the step being asked (an Xbox
pad has no Capture, and it doubles as the answer to pressing one twice);
holding anything for 2.5s leaves without saving; and the last step asks for
**A** to save and **B** to discard *in the names just learned*, which makes the
act of saving the cheapest possible test of what was learned. An axis pulled
past 0.6 of its travel is recorded as a trigger rather than a button, so the
XInput pads that report ZL/ZR as axes map the two the console scheme clicks
with.

**Found on the way:** the test suite called `config_module.load()`, which
merges `~/.config/omapad` over the defaults - so it tested whichever machine
it ran on, and started failing the moment this session wrote a binding into the
developer's own config. Pinned to the shipped defaults.

**Still open.** The shipped `nintendo_pro` profile still names the KP20's face
buttons by Nintendo printing, so a fresh install of this pad is still wrong
until someone runs the screen. Splitting a profile into *protocol* (codes,
whether the triggers are analog) and *printing* (which letter sits at which
position), with `[device] labels = "xbox" | "nintendo"`, is the fix that would
make the screen unnecessary for pads we already know. The screen also cannot
map the D-pad - it is a hat, not a button, on every pad seen so far - and it
takes the sticks on faith.

### 22. A bar that knows about the pad · ✅ Done (unverified on screen) · S

Everything omapad draws is summoned and then goes away, which leaves no
standing answer to *is the pad mine?* — the question you ask before pressing
anything. The obvious shapes were a widget in Omarchy's bar or a bar of our
own, and the second is wrong twice over: it would redraw the clock, the
battery and the network to be a bar at all, and it would fight Omarchy's for
the same screen edge.

So: one widget, in the bar that already exists. Omarchy takes third-party
`bar-widget` plugins (`shell.qml:672`), and a plugin already declaring `panel`
can carry one — the exclusion at `shell.qml:429` only decides which loader
answers `summon/hide/toggle`, which omapad does not use. `PadStatus.qml`
extends the host's own `BarWidget` and draws game mode in the bar's urgent
colour rather than one of ours, since the bar has a way of saying *look here*
already. It hides itself when the daemon stops talking: an icon for a service
that is not running is worse than a gap.

The daemon side is a fifth view socket, `status.sock`, carrying mode, whether
a pad is attached, its name and the active profile — pushed on every change
and on the same heartbeat as the rest, so a shell restart repaints it.

**What was rejected:** a per-mode bar *layout*. `shell.json` has no notion of
modes and Omarchy is explicit that the user's file is canonical with no
deep-merge, so switching layouts would mean a program rewriting a hand-edited
config on every mode toggle. Hiding the bar wholesale needs none of that —
`omarchy toggle bar off` parks it off-screen through a flag file the bar
watches, and `[mode] hide_bar_in_game` uses it. It is put back on the way out
*and at shutdown*, because a daemon that dies in game mode would otherwise
leave a desktop with no bar and no clue why.

**Found on the way:** `hide_bar_in_game = true` appended one table too low
landed under `[bindings.game]`, and `omapad check` answered a bool binding
with an `AttributeError` traceback instead of naming the row — the one job it
has. `parse()` now rejects a non-string spec as an `ActionError`.

**And the direction was backwards.** `omarchy toggle bar <action>` is a wrapper
around `omarchy-toggle bar-off <action>`, and the action names the *flag*, not
the bar: `on` creates `bar-off` and hides it, `off` removes it and brings it
back. Written the way it reads, entering game mode showed the bar and returning
to the desktop hid it. The test did not catch it because it asserted the string
the code sent — it pinned the assumption rather than the behaviour — so it now
pins the direction with the reason next to it, and the fix was verified against
the live layer geometry (`0 -26` in game mode, `0 0` on the desktop) rather
than against the test alone.

**Verified on screen** once the session unlocked: the widget sits between
`omarchy.agents` and `omarchy.bluetooth`, and game mode parks the whole bar
off-screen and gives the space back to the windows.

**Still open.** In desktop mode the widget is one icon and nothing else, which
is either exactly right or too quiet to be worth a slot — the payload already
carries the mode, the pad's name and the active profile, so a label costs
nothing but bar width. The mapping screen has still not been *driven*, only
loaded.

### 23. A bar for game mode, and item 10 arriving through the side door · ✅ Done · M

Hiding Omarchy's bar (22) left game mode with nothing on screen at all — no
clock, no workspaces, and no reminder of how to get back out. A second
general-purpose bar was the wrong answer for the reason 22 gives, but the
*gap* was real, and what fills it is not a bar in the desktop sense: every
widget on Omarchy's opens a popup you click, and in game mode there is no
pointer to click with. So this one is a readout. Left: the menu and the button
that opens it. Centre: the workspaces. Right: what the buttons under your
thumbs do.

That right-hand strip is **item 10** — the hint bar — arriving from a
direction the roadmap did not expect. 10 was blocked on per-app profiles (09)
so it could stop guessing what a keystroke would do; the honest version turned
out to be narrower and better: print what is *actually bound in the layer that
is live*, resolved through exactly the path a press takes, including game
mode's rule that an unbound button reaches the base layer for its `mode:`
action and nothing else. So HOME still says how to leave, and a game layer
that binds nothing says "The pad is the game's" rather than printing a row of
buttons that do nothing. Same for the menu: it appears only once some button
really opens it. `guide._row` became `guide.button_row` so the bar and the
guide cannot describe the same binding differently.

Sized for the couch — 44px against the desktop bar's 26 — and it carries an
exclusion zone like a real bar, so windows sit under it; a full-screen game
covers it, which is the right outcome and needed no special case. Workspaces
come from Hyprland, queried when the bar opens and on create/destroy only: a
plain switch carries the name it switched to, so the common case spawns
nothing, and none of it runs while the bar is down.

The clock lives at the left end of the bar (`[gamebar] clock`, strftime). It
was briefly at the head of the controller menu instead, which was wrong for a
reason worth keeping: a clock is a thing you glance at, and a menu you have to
open first is not a glance.

**Looking like Omarchy took three separate answers, not one.** Colours come
from `Color.bar.*` rather than the menu's tokens. Transparency follows
`bar.transparent` out of `shell.json`, watched live — on this desktop the bar
*is* transparent, so its real background is the wallpaper and matching the
token would have matched nothing. And a transparent bar cannot use the theme's
bar text: Omarchy runs `omarchy-bar-text-color`, which samples the pixels under
the bar and returns whichever of two colours survives them. Asking the same
question, with this bar's own height, is the only way to get the same answer —
the first attempt used the token and produced pale blue on a cream wallpaper.
The workspaces are drawn the way `omarchy.workspaces` draws them, down to the
dot the focused one becomes, and the buttons that step between them sit either
end of the strip rather than in the row of hints: a button drawn beside what it
moves needs no words. A button is never drawn twice.

**Not built, deliberately.** Wi-Fi and weather were asked for in the same
breath and neither is a bar problem. Weather has no source in the daemon —
Omarchy's widget fetches it from wttr.in in the shell — so putting it here
means network I/O in an input daemon, with caching, failures and a location to
own. Wi-Fi needs the menu to hold *dynamic* rows (a scan is not a config file)
and a password path through the on-screen keyboard; that is a feature of its
own, not a row. Both are worth doing and neither should be smuggled in as part
of a bar. **Half of that landed in 40**, which the audio devices asked for: the
menu holds listed rows now, and what Wi-Fi still wants is the password path.

**Found on the way:** the suite swapped only three of the daemon's view
clients for fakes, so the two new ones pushed test payloads into whichever
shell was running on the developer's machine. All of them are swapped in the
base case now.

**And two more, both reported as "game mode is broken":**

Picking a row from the menu closed it and then did nothing. `allowed()` blocked
any action that carried no layer, and a menu row carries none - which was right
while the menu could not be opened in game mode at all, and became wrong the
moment it could. Rows are tagged with the menu now. A menu that closes on a
press and does nothing is indistinguishable from a menu that ignored the press,
which is exactly how it was reported.

The measurement that found it is worth keeping: reading the pad's raw codes in
parallel while the daemon ran (game mode leaves it ungrabbed, so nothing had to
be stopped) and lining the timestamps up against the daemon's own journal.
`0x13b -> PLUS` opened the menu, the D-pad moved, `0x131 -> A` closed it. Every
code was the one the profile expected - so the pad was not the problem, and
three earlier rounds of theorising about a shifted button map had been aimed at
the wrong thing.

**And the first of the two:** item 20 made
`current_layer` return `game` ahead of everything, so a surface opened *from*
the game layer could not be driven - the menu came up on `PLUS` and then
ignored its own D-pad. Three opens and closes in the journal inside twelve
seconds is what that looks like from the outside. Surfaces now outrank game
mode (a held layer still outranks both, as it always did) and `allowed()` lets
their bindings through, because opening one is a decision to look at it rather
than at the game. The first fix put surfaces above held layers too and broke
two older tests that had pinned exactly that order - they were right and it
was wrong.

### 24. Game mode was the wrong shape · ✅ Done · L

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

### 25. The band of nothing under the menu · ✅ Done · S

Noticed by eye, against Omarchy's own menu: ours ended in more empty space
than it began with. Measured off screenshots at the same crop and scale,
Omarchy's card is even - about 45px at either end - and ours had 43 above and
74 below.

Not padding. The list is capped at 60% of the screen so a long submenu cannot
swallow it, and the cap was cutting *through a row*. A row centres its text
vertically, so the visible half of the cut row carries no ink at all: the card
appeared to end in bad padding rather than in "there is more below". Cut to
whole rows instead - the cap does the same job and the fold now lands between
two of them. 45 and 48.

The clock moved back into the menu's header with the day name, after a spell at
the left end of the bar next to the menu's own badge, where two things at one
end read as clutter.

### 26. A badge that was promising something a press would not do · ✅ Done · S

The workspace badges sit either side of the strip, which says "these walk the
workspaces". Under `[profile.browser]` or `[profile.steam]` a plain press does
not: the app has it, and the workspace is behind the announced hold. Same
badge, different behaviour - a small lie, and the thing that made the confirm
gesture undiscoverable.

Locked badges are drawn at 45% instead. **Dimmed rather than coloured**, for
three reasons worth keeping: the bar's foreground is chosen per wallpaper by
`omarchy-bar-text-color`, so a fixed hue would be illegible on some of them;
"not available at a tap" is conventionally contrast rather than colour; and it
leaves the theme's urgent colour free for the louder event.

Holding walks the dimming off over exactly `hold_ms + confirm_ms`, so the badge
is full at the moment the action fires. That makes the countdown visible - it
was a tick and a notification, both of which happen away from the thing you are
looking at - and it answers "why is this one dim?" the first time you hold it.
The daemon says a countdown has started (`holding: {b, ms}`) rather than the
bar guessing, because only the daemon knows when the press landed.

The tick got its own mark too. The gesture has two phases and the ramp only
showed one, so the badge now **arms** at `hold_ms`: thicker, and in the bar's
own urgent colour, for the confirm window. Thicker *as well as* coloured
because the theme's urgent hue is darker than the foreground on a dark bar -
hue alone read as the badge fading at the exact moment it should escalate,
which the first capture showed plainly.

**Measured** off screenshots, since opacity is not a thing to take on trust:
the badge region reads 62 at rest while locked, 66 at 1.4s into a four second
hold, and 75 unlocked.

**Found while testing:** `hyprctl dispatch focuswindow class:chromium` does
nothing on this Hyprland - dispatch goes through Lua - so the first comparison
was two screenshots of the same unfocused state. `hl.dsp.focus({ window =
'address:0x...' })` works. A reminder that a test that cannot fail is worse
than no test.

### 27. A keyboard page the app in front lends it · ✅ Done · M

Typing a command letter by letter with a thumbstick is the worst thing the
keyboard asks of anybody — and in a terminal it is also the most predictable
thing it is asked for, because the command you want is nearly always one you
have already run. So a profile can now hand the keyboard **a page of its own**:
it joins the cycle `L`/`R` already walk (`abc` → `&123` → `Fn` → `Term`) for as
long as its window is in front, and leaves the cycle with it.

```toml
[profile.shell.osk]
label = "Term"
keys = ["git status", "sudo pacman -Syu"]
from = "tac ~/.bash_history | awk '!/^#/ && length > 2 && length < 60 && !seen[$0]++' | head -8"
```

**`from` is what keeps the daemon out of the shell business.** Its output is
one entry per line, so which history file, and whether bash or atuin or zsh is
answering, is a line of config rather than a branch in Python — the same reason
`hypr:` bindings are Lua expressions rather than a dispatcher table.

Four things had to move to make the page possible, and each is small:

- **The page-turn cell stopped naming a layer.** It said `layer:sym`, which
  cannot be right when how many pages exist depends on what is focused. It now
  says `layer:next` and the *model* prints where that goes, because the running
  order is the only thing that knows.
- **A key can type a string** (`text:`), and a character is not a keycode: the
  same XKB table the printed labels are read out of is inverted into
  character → chord, so an entry types the same thing the keys say. A character
  the layout cannot make is dropped rather than typed wrong.
- **The page is laid out the way text is read**, not the way a grid is walked:
  a short entry shares its row, a long one takes it alone, and it stops at four
  rows so the keyboard keeps the height it has on every other page. The width
  budget comes from the bottom row it shares, so the columns still line up when
  the page turns.
- **The command runs when the keyboard opens**, not when focus moves, and its
  output is kept for `ttl` seconds. A window change is not worth spawning a
  shell for, and the page cannot be read while the keyboard is down.

**Caveat, and it is bash's:** the history file is only written when the shell
exits, so what the terminal in front has typed today is not in it. One line —
`PROMPT_COMMAND='history -a'` — fixes it, and the README says so where the
page is documented.

**An entry can also carry a chord** (`action`, the same grammar `[osk.keys]`
uses) rather than a string, and that closes the `Paste` key's oldest wrong
answer: the bottom row sends `Ctrl+V`, which is right everywhere except a
terminal, and a terminal's `Ctrl+Shift+V` now sits on the terminal's own page.
That is the shape the problem always wanted — not a key that means two things
depending on where it is, but the app's page carrying the key that is only
right there. The chord is parsed at config load, so `omapad check` names the
profile instead of the daemon failing when the page is drawn.

---

## Needs a decision — the one that doesn't work as asked

### 28. Not having to aim: the ring cursor, snap and traversal · ✅ Done · M

The one thing a thumbstick is definitively worse at than a mouse is aiming.
From the couch that is two separate problems: **finding** the pointer and
**taking it somewhere**.

**The pointer.** Game mode switches to an XCursor theme it draws itself — a ring
with a dot in the middle and a dark halo underneath (`cursor.py`). The format is
small enough to be worth writing (a header, a table of contents, premultiplied
ARGB per size), and it needs no xcursorgen dependency. The theme is written
under `~/.local/share/icons` **at daemon startup** rather than at the mode
switch: drawing takes 0.26 s, which would be felt in a mode switch and is not
felt at startup — a config change wants a restart anyway. The switch itself is
one line to the compositor's socket.
Every cursor name in the theme points at the same ring: from the couch an I-beam
is an unreadable smudge too, and one shape that never changes is easier to
follow than the correct shape that keeps changing.

The way back is the desktop's own theme, read **at the moment of the swap**
(`gsettings get org.gnome.desktop.interface cursor-theme`, with `XCURSOR_THEME`
behind it) — not at startup, so that a theme changed while the daemon runs comes
back too. It is done at shutdown as well, so a daemon that dies in game mode
does not leave the desktop with the ring.

**Snap.** `snap:left|right|up|down` teleports the pointer to the middle of the
window that way and focuses it. Measured: `cursorpos` over the socket is
**0.03 ms**, `j/clients` **0.32 ms** — so asking on every press is both cheaper
and more correct than keeping state. `hl.dsp.cursor.move({ x = , y = })` and
`hl.dsp.focus({ window = 'address:0x…' })` were verified live. The choice is
edge-based: the window's *near edge* has to be ahead of the pointer. The first,
centre-based version gave the wrong answer for two windows in the same column —
the lower window's centre sat a few pixels to the right of the pointer, so it
counted as "the window on the right".

**What could not be done: the widget level.** AT-SPI was tested live. Part of it
works — zenity's tree arrived with its roles and the right rectangles, and
`GetAccessibleAtPoint` answered correctly. Three obstacles:

1. `GetExtents(coordType=0 /*screen*/)` returns `x=0, y=0` for every node —
   under Wayland an application does not know its own window position. The
   window-relative coordinate is right, and could be added to `at` from
   `hyprctl clients`.
2. `org.a11y.Status.IsEnabled` and `ScreenReaderEnabled` are both `false`, and
   Chromium/Electron never register on the bus without that flag (GTK ones do —
   zenity did). Games, Steam and terminals under no circumstances.
3. There is no D-Bus in the stdlib. Shelling out to `busctl` (~7 ms per call) or
   ~400 lines of raw D-Bus client — either is a design decision under the "no
   third party" rule.

It was not built because its coverage stops exactly short of what game mode uses
most. If it is reopened: point probing (`GetAccessibleAtPoint`) is far cheaper
than walking the tree, and that is where to start.

**Traversal.** The only thing that knows where a widget is is the application
itself, and every toolkit already answers Tab and the arrow keys correctly.
`focus:next|prev|…` sends the configured key (`[traverse]`) and the application
moves the focus. A stick can be given the `focus` role: not one shot but a
direction that walks while held — the repeat ours rather than the compositor's,
because an application that saw a key held down would run far past where the
finger stopped.

**Where it ended up bound.** A layer was tried first (`[layers.traverse]`,
trigger X) and taken back out: because `layer_for_button` is checked before
every binding, the button that opens the layer has no job of its own in any
layer or any profile. X's cost was not just the duplicate middle click on the
base layer — float/tile in the window layer and `Ctrl+T`/`F5` in
`[profile.browser]` went with it, and neither had a free button to move to.

**A stick instead**: `[mode] right_stick = "focus"`, on by default in game mode.
It spends no button, the wheel on the desktop stays, and the game-mode scrolling
it loses comes back anyway because focus scrolls itself into view. That required
game mode to be able to name its own stick roles; under `[mode]` rather than
`[layers.game]`, because game mode is not held by a button, and a layer without
a button would make the layer's `button` requirement meaningless.

### 12. Disabling the keyboard in password fields · Constrained · L

Wayland gives no general way to ask what kind of field has focus. The only signal
is the content purpose an app volunteers through the text-input protocol, and
reading it means binding `zwp_input_method_v2` as a client.

**And that seat is taken** — measured in 30: Hyprland answers a second input
method with `unavailable`, and fcitx5 holds the first one on every Omarchy
install. So the signal is not merely partial here, it is unreachable; what
30 shipped instead is per-app, by name.

**Why it would only half work:** Quickshell exposes no input-method or text-input
type, so this cannot live in the existing plugin — it needs a separate small
Wayland client. And it only sees apps that use text-input: GTK and Qt do,
Chromium and Electron generally do not. Most password fields you meet in a
browser would go undetected, which is the worst outcome — a protection that is on
often enough to be trusted and off exactly where it matters.

**Verified:** checked against the installed Quickshell type registry.

**The premise is also worth questioning.** The on-screen keyboard doesn't add a
meaningful attack surface. It types through the same uinput device as everything
else omapad does, the daemon runs as your user rather than root, and anything
able to read that device can already read your physical keyboard. What is
genuinely different is **shoulder surfing**: an on-screen keyboard shows the
character you are about to press.

So the honest shape is a convenience, not a control — hide on detected password
fields where the signal exists, and never claim the coverage is complete. If
shoulder surfing is the real concern, suppressing the pressed-key highlight is
cheaper and works everywhere.

---

### 29. Showing the screen and asking: the assistant · 📦 Shelved · L

**Built, then taken back out (2026-08-31)** to ship a smaller feature set
first: it was the one thing here that spawned a model, a recorder and a
transcriber, and the four programs behind it are four ways for the pad to
stop working for reasons that have nothing to do with the pad. Everything
below is what it was, and stands as the design for putting it back.
`assist.py`, `ai.py`, `history.py`, `Assist.qml` and `tests/test_assist.py`
are kept verbatim in `../../tries/omapad-assist-removed-2026-08-31/`,
along with the config and the callers as they were before the removal.

From the couch, the shortest way to explain where you are stuck is to show the
screen. One button photographs it, listens to what you are asking, and prints
the answer on a panel sized to be read. Working in game mode was the point; it
works exactly the same on the desktop.

**Three new modules, without bending any of the existing limits.** `assist.py`
is the surface itself (pure, it runs no commands), `ai.py` the providers and the
thread that does the work, `history.py` the per-game transcript. The panel is
`shell-plugin/Assist.qml`, the sixth surface.

**No third-party package, and no HTTP.** Every assistant worth pointing at
already ships a CLI that takes prose on stdin and prints prose on stdout, and
each carries its own login. A provider became a **command template**: `claude`
ships, and `codex` / `gemini` / `grok` stand there as starting points. An HTTP
client would have reached exactly one provider, and would have wanted the API
key the CLIs already have.

**The audio never goes to the model.** No provider accepts audio, so speech is
transcribed on this machine (voxtype / whisper.cpp). Two side benefits: you can
read what you asked before it is sent — the only way you notice the microphone
misheard you — and the history stays `grep`-able.

**Memory is per game, not per session.** A question asked over a game is almost
never the first question, so the transcript is filed under the window class
(`~/.local/state/omapad/assist/<class>.jsonl`) and a new conversation opens
with the tail of it. A provider that can resume its own session is better than
repeating lines — it has kept the screenshots as well — so `mode = "auto"` tries
resuming first, `lines` stands there as the portable answer, and `off` writes
nothing.

**Every phase says its own name.** There is a dead moment of a few seconds in
the middle of a question sent to a model, and over a fullscreen game that is
indistinguishable from a button that did not work. So the panel walks through
photographing / listening / understanding / thinking; the listening phase is the
only movement and the only counter, because just then the user is the side that
has to do something.

**The shutter before the panel.** Our own surfaces are on the overlay layer, so
if they were open `grim` would photograph them too. The panel opens *after* the
photo, and in the ~90 ms in between the thing that says the press arrived is the
rumble.

Verified end to end: photo → answer ~9 s, a follow-up question ~3 s, the
transcript and the session id written to disk, the panel drawn on screen.

**Two traps, both hit and both fixed:**

- The `resume` template did not carry the first turn's permissions
  (`--allowedTools Read --add-dir`), so reading the new screenshot was refused
  on a follow-up question. Because the provider returned that as an *answer*, no
  error appeared anywhere — only the answer itself said "I could not read it".
- On the QML side the socket data was assigned with bare names; when one of them
  landed on something read-only and threw, the `catch` swallowed it and **every
  field after it** silently stopped being applied. `open` was last, so the
  symptom was "a panel that has its data and never comes up". All of them are
  now written explicitly with `root.`, and the `catch` logs instead of staying
  quiet.

**Left open when it was shelved:** asking a question by typing on the panel
(through the OSK) was never wired up — every question was either spoken or the
ready-made one in `[assist] prompt`. And `assist:talk` could not be used as the
hold half of a tap/hold pair: the hold half fires press and release together,
leaving no interval to speak in. Putting it behind a confirmed hold would need
a mechanism of its own.

### 30. The keyboard opening by itself · 🗑 Removed · S

Not having to reach for MINUS when a box that says "type here" comes up on the
couch. What was asked for was field-level: the keyboard opens **when focus
lands in a text field**.

**Field level was measured, and it is closed.** The only thing on Wayland that
says so is what an app volunteers through text-input, and reading that means
binding the seat's `zwp_input_method_v2`. A raw Wayland client was written and
run (registry → `wl_seat` + `zwp_input_method_manager_v2` →
`get_input_method`): Hyprland 0.56.2 answers with **`unavailable`** at once,
because the seat is already fcitx5's — and fcitx5 is part of Omarchy itself
(`omarchy-fcitx5.service`, for XCompose), so this is every Omarchy install.
The ways around it were eliminated one by one too: the `fcitx5-remote` state
(the same `1` with and without a text field focused), Hyprland's IPC event
stream and its Lua event list (nothing about IME or text-input), `hyprctl`
(likewise). AT-SPI was already ruled out in 28 (no D-Bus in the stdlib,
Chromium and Electron never register).

**What was built, and why it is gone.** Window level, seeing layer surfaces
too: `[osk] auto` (`never|game|always`) with `auto_match` and `auto_close`,
matching the focused window's class and title and the namespace of every layer
that was up. It was removed in use. A name is not a text field: matching an app
says nothing about whether the box in front of you wants typing, so the
keyboard came up over things that were not asking for it and stayed down for
things that were. Every guard against fighting the user — acting only on a
*change* of what is in front, never taking away a keyboard it did not open —
made it less wrong without making it right. Opening it costs one button.

Reopening this needs a signal about the *field*, not about the app. That means
either the input-method seat becoming reachable (Hyprland allowing a second
`zwp_input_method_v2`, or Omarchy dropping fcitx5) or something equivalent from
the toolkits. Until then it is closed, and the removal is the answer.

### 31. Buttons drawn as drawings, not as rounded rectangles · ✅ Done · M

Item 11 got the shapes right in principle and wrong in fact. Every surface drew
its own badge out of a `Rectangle` with a radius per kind, a second rectangle
inset for a stick's ring, and a `Text` on top - three copies of it, in
`Guide.qml`, `Assist.qml` and `GameBar.qml`, drifting apart a little each time
one of them was touched. A bumper was a lozenge, a trigger was the same lozenge
with two corners squared, and neither looked like the thing under a thumb.

The shapes are now **drawn**, once, and everything else is generated from them.
`assets/shapes/*.svg` holds one unlabelled SVG per control; `assets/generate.py`
sets the label into it in **Fira Code** and writes two things from the same
numbers - `assets/buttons/*.svg`, the button with its label punched through it,
and `shell-plugin/ButtonArt.qml`, the same geometry as path data with the shape
and the label kept apart so a surface can paint them in its own colours. The
guide fills the button faintly under a solid label; the game bar draws it as an
outline over the wallpaper. `BadgeArt.qml` is the one thing that paints either,
so the three surfaces cannot drift again.

**Nobody types a nudge per shape.** A shoulder is cut away at one corner, so a
label centred on its bounding box crowds the cut. `assets/place.py` rasterises
the filled shape, measures how far every point inside it is from the outside,
slides the label's box over that field and puts the label where the box sits
deepest, preferring the middle when several positions tie. On a circle that is
the centre; on a shoulder it lands within a unit of where the hand-drawn
examples put it. It also decides the size: the label starts at the cap height
those examples used and shrinks only where the shape makes it, which is `L3`
inside a stick click and nothing else.

The font parsing is 200 lines of `truetype.py` rather than a dependency -
`cmap`, `loca`, `glyf`, `hmtx`, `OS/2` - because this project takes no
third-party packages and the job is capitals and digits out of a monospaced
face, which is the one case where an outline dump is the whole truth.

Everything the daemon names is drawn: the D-pad as a cross with the arm its
direction lights set into it the way a letter is set into a face button, and
the system buttons as a pill the shell types the word into, since what tells
MINUS from HOME is the word and not the shape. A new drawing plugs in the same
way - add the SVG, add a line to `BUTTONS_TO_DRAW` (or to `ICONS_TO_DRAW` for
a badge whose label is drawn, `BLANKS_TO_DRAW` for a shape the shell types
into), re-run. `tests/test_assets.py` rebuilds everything in memory
and fails if what is checked in no longer matches, because forgetting to re-run
the generator is the one mistake nothing else would catch.

### 32. The browser's own keyboard page · ✅ Done · S

Item 27 built the mechanism and the terminal was the only thing using it, which
made it look like a history feature. It is not: it is the page an app lends the
keyboard, and the browser wants a different one, because what a browser asks you
to type is not a command you have run before — it is **a URL**, the one string
here that has to be exact, and the one a thumbstick is worst at.

So `[profile.browser.osk]` ships as `Web`, and it is built around the address
bar rather than around the browser's menus:

- **`Address bar` (`Ctrl+L`)** puts the caret where you are about to type
  without aiming the pointer at a text field that is four pixels tall from a
  sofa. It is first because it is what the keyboard was opened for.
- **`https://`** types the prefix the omnibox will not guess once what follows
  is not a plain domain, which is the thing that was asked for and the reason
  this item exists.
- **`Go .com` (`Ctrl+Enter`)** wraps what has been typed in `www.`/`.com` and
  opens it. It is the largest saving on the page: a domain becomes the few
  letters in the middle of it, typed one thumb-walk each.
- **`Find` (`Ctrl+F`)** and **`Search tabs` (`Ctrl+Shift+A`)** are the two
  places a browser expects you to type that are not the address bar. Tab search
  matches a title or URL across the window's open and recently closed tabs,
  which from a couch beats walking `L`/`R` past twenty of them.
- **`Reopen tab` (`Ctrl+Shift+T`)** is the one-key undo of a mis-click, and a
  mis-click is what a stick-driven pointer produces.
- **`Zoom −` / `Zoom +`** are the couch's own complaint — a page written for a
  desk, read from a sofa — and they take two entries rather than one because
  zoom is pressed more than once.

**Nothing in the daemon changed.** Every one of those is an `action` entry, the
chord form item 27 added for the terminal's paste, so the page is config: eight
lines in `config/config.toml` and the two tests that assert the shipped page is
what the browser gets. That is the check on 27's shape — a second app wanted a
page of an entirely different kind and needed no code.

**The page is four rows**, so eight short entries is the whole of it, and what
did not fit is written down beside it as a comment: bookmark, history,
downloads, close the tab, full screen, reset the zoom, a private window. The
shortcuts are **Chromium's**, which is what the profile's `match` names —
Firefox reads `Ctrl+Shift+A` as its add-on manager, so a Firefox profile wants
its own page rather than this one stretched over it.

### 33. The game behind Big Picture, and the menu rows that died with it · ✅ Done · S

Reported from the sofa: *launch a game from Steam Big Picture and Steam stays in
front of it; I have to close Steam, and I cannot close Steam with the
controller either.* Two separate faults, and the second one turned out to be
ours.

**The stacking is Hyprland's, and no dispatcher fixes it.** Omarchy floats every
Steam window and the rule matches the class exactly, so Big Picture (class
`steam`) floats while a game launched from it (class `steam_app_<id>`) tiles.
A floating window is **always** drawn above a tiled one - a layering rule, not a
z-order - which is why the obvious answers do nothing.

**Measured**, with two terminals standing in for the pair (`--app-id=steam` and
`--app-id=steam_app_888`, so the real rules applied to them):

| Dispatcher | What the screenshot showed |
|---|---|
| `hl.dsp.window.cycle_next()` | focus moved to the "game" - its border lit - and it stayed covered |
| `hl.dsp.window.bring_to_top()` | no change at all; a tiled window cannot be raised over a floating one |
| `hl.dsp.window.fullscreen({ mode = 'fullscreen' })` | the "game" covered the screen, Big Picture gone |

So the fix is a window rule, and it belongs in the user's Hyprland config rather
than in this repo - the README says which line, next to the hand-off it belongs
to. It is the same answer Omarchy already gives RetroArch and Moonlight:
`o.window("steam_app_.*", { fullscreen = true, idle_inhibit = "fullscreen" })`.

**The pad-side half is a `Windows` row in the menu** - fullscreen, next window,
float/tile, close - because the window layer (`ZL`) already has all of it and
none of it reaches past an app holding the pad. A summon does, and the menu is
the summon. `Fullscreen` is first in the submenu because it is the row that
actually clears the case above.

**And that is where the real bug was.** A picked row fires *after* the menu is
put away - deliberately, so what it opens does not come up behind a scrim - and
`allowed()` was reading `menu_open` at that moment, which is now False. With the
pad handed to a game, every row that was not itself a summon was **silently
dead**: `Terminal`, `Ask about this screen`, the whole Audio and Screen
submenus. Only `Keyboard`, `Bindings` and `Game mode` worked, because those are
summons and summons are allowed by kind. In other words the menu was at its most
useless exactly where it is the only thing you have.

`allowed()` now takes the surface layer a row was tagged with as its own answer:
the button that chose the row was ours, on a surface the pad was driving, and
closing the surface first is an implementation detail of how it is drawn.
`fire_once(action, "menu")` had been passing that tag since the menu was
written; nothing read it.

### 34. Asking for a button the pad does not print, and a menu for the pad · ✅ Done · M

The mapping screen shouted `MINUS` at an Xbox pad. The logical names are the
Switch's - that is what a binding is written against and what the mapping file
is keyed by - but nothing on an Xbox pad says *minus*, and the one screen where
the eyes are on the plastic rather than on the display is the worst place to
name a button after a different console. `guide.badge_of` had answered this
question everywhere else since **31**; the fourth surface had never been given
the answer.

**What landed:** `MappingModel` carries a `layout` like the guide and the bar
do, the daemon sets all three in one place (`apply_layout`), and the step is
drawn as the button it is - the same shapes, through `ButtonArt`, in the accent
colour - with the words underneath naming both printings, because a pad whose
profile is wrong is usually a pad printed unlike that profile's family. The
progress strip and the final confirmation moved with it: `A saves it` is
printed `✕ saves it` on a pad whose face buttons are shapes. Four face buttons
whose printing *is* a shape get words of their own (`Cross`, not `✕`), since
"press ✕" reads as a step that was crossed out.

**And the settings themselves became reachable.** Which profile a pad takes and
what its badges print are exactly the questions you have while holding the
thing and getting the wrong answer, and until now both were a file edit and a
`systemctl --user restart`. `pad:<setting>=<value>` is the action grammar's way
in - `pad:layout=xbox`, `pad:profile=auto`, `pad:rumble=toggle`,
`pad:rumble_strength=up`, and `next`/`prev` on any of them so one button can
walk what the menu offers as rows. What is chosen is applied to the running
daemon (a new profile re-reads the pad already open; a new layout repaints
every surface) and written to `~/.config/omapad/settings.toml`, merged last
so it wins over `config.toml` - the same shape `mapping.toml` already had, and
for the same reason: a hand-written file full of comments is not something a
program should rewrite.

The menu grew the two things a settings row needs and did not have: `stay =
true`, one press that leaves the menu up (a choice you cannot see the result of
without being thrown back to the desktop is a choice you make twice), and a
**tick** on the row that is already in force, which is the difference between a
list of choices and a list of guesses. The tick is `Action.state(ctx)` -
`None` for everything that is not a setting, since launching a browser is
neither on nor off - so the menu asks the daemon rather than knowing anything
itself.

`Controller` in the root menu now holds all five: Shortcuts, Remap the buttons,
Profile, Button labels, Vibration. The first two were loose rows in the root
menu before; a controller is one thing and reads as one row.

**What this does not fix:** item **21**'s open caveat, one layer down. The
`nintendo_pro` profile still names a KP20's face buttons by Nintendo printing,
so a fresh install of that pad is still wrong until someone opens the screen or
picks a profile - the difference is that picking one is now four button presses
rather than a file edit. Splitting a profile into *protocol* and *printing*
remains the fix that would make neither necessary.

### 35. Discord: the face buttons as a voice panel · ✅ Done · S

Asked for from the sofa: *let the face buttons run Discord's shortcuts — mute
the mic, mute the mic and the sound, and two more.* The third app to want a
profile, and the first to want the **face** buttons: 09 gave the browser the
shoulders and the file manager a single key, and both left `A` and `B` alone
because a console scheme is what everything else expects of them.

Discord is where leaving them alone is the wrong answer. Its most-pressed
controls are not on screen where a pointer can reach them — mute and deafen sit
in a strip the size of a thumbnail, in the corner furthest from wherever you
are aiming, and you have to hit one of them *mid-sentence*. Meanwhile `A` is
Enter in an app whose messages are sent by the keyboard's own `ZR`, so what the
console scheme was protecting there was worth very little.

So `[profile.discord]` puts the voice panel on the four face buttons: `A` mutes
the microphone (`Ctrl+Shift+M`), `B` deafens (`Ctrl+Shift+D`) — the pair, next
to each other on the pad the way they are in the app — `X` is the quick
switcher (`Ctrl+K`), and `Y` answers an incoming call (`Ctrl+Enter`), which is
the one thing here that is *timed*. Enter and Esc survive as holds, which is
also how Esc keeps declining a call.

**The right click was the interesting cost.** Taking `Y` takes the context
menu, and in Discord that menu is how a message is replied to and reacted to —
more than the binding was worth. It moves to the left stick click, whose middle
click was `X`'s twice over, so nothing that mattered paid for it. That is the
same displacement `[profile.browser]` makes, and it reached into the window
layer the same way: `ZL` + left stick no longer pinned the window while Discord
was focused. **38 ended that** — the pin is back, in Discord as everywhere.

The keyboard gets a `Chat` page over 27's mechanism, and it is a third kind of
page again: a terminal's is what you have already run, a browser's is the
address bar, and a chat app's is **the sentences you send without meaning
anything by them** — `brb`, `omw`, `gg`, three keys instead of nine aimed
letters. The other half is the pickers, all of which open something that is
then typed into: search, emoji, GIF, mark the server read, pins.

**Nothing in the daemon changed here either**, which is the second check on
27's and 09's shape: the pad's most app-specific scheme so far is config.

**What the order of the profiles turned out to be worth.** Omarchy installs
Discord as a webapp as readily as pacman installs the client, and a webapp is a
Chromium window: class `chrome-discord.com__channels_@me-Default`, which
matches `chrome` as squarely as it matches `discord`. 09 resolves the first
profile declared, so written where the other app profiles are this would have
lost to `[profile.browser]` on exactly the install that needs it most - the
buttons would have been the browser's tab switcher over a chat client. It is
declared first, with the reason written beside it. That is the first time the
declaration order has decided anything, and it is the shape of the next
question rather than a fault: a webapp is two applications wearing one class.

**And the menu grew the couch's short list.** `Apps` had Steam, a browser, a
terminal and *everything installed*; it now leads with the four a sofa actually
reaches for - Steam Big Picture, Discord, Spotify, YouTube: the game, the people
you are playing with, the music and the television. Three of them launch **or
focus**, because with a pointer this slow a second copy of a chat client is
never what was asked for. Discord's row is the one worth reading: an `exec:`
action is a shell command, so the row asks `omarchy-cmd-present` which of the
two Discords is installed at the moment it is pressed rather than the config
guessing at install time.

### 36. The cloud session, and the menu that opened on top of it · ✅ Done · M

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

### 37. The terminal: Tab, the interrupt and the scrollback · ✅ Done · S

Asked for from the sofa: *make the buttons mean something in a terminal.* The
fourth app to want a profile, and the first whose gap was visible in the config
itself - `[profile.shell]` had shipped since 27 with a keyboard page and **no
bindings at all**, while the browser, the file manager and Discord each had
theirs. A terminal was the app the pad understood least and the one 27 had
already decided was worth a page.

What it needed was not on the pad. A shell is *used* with Tab - the command,
the path and the flag are completed rather than typed - and `Ctrl+C` is the way
out of something that is not coming back. Neither is a key any button sends,
and neither is a thing a pointer can reach. So `Y`, whose right click opens a
menu of two entries in kitty and ghostty and nothing at all in foot and
alacritty, carries both: Tab on the tap, the interrupt on the hold. `Ctrl+L` -
the screen having scrolled past reading - goes on the left stick click, the
middle click's second copy, which is where 35 put Discord's context menu for
the same reason.

**Why the interrupt is not on `B`.** Next to Esc is where it looks like it
belongs, and that was the first draft. But 09's resolution reaches into the
held layers, so a profile's `B` is `ZL` + `B` as well - and that is *close the
window*, which a terminal needs more than any other app on the desktop. `Y`
costs popping the window out instead. The lesson generalised as far as
**38**, which decided the premise was the fault: a profile now stops at the
held layers and pays only at rest. `Ctrl+C` stayed on `Y` anyway — `B` is the
Esc that vim and less want, and an interrupt belongs on a hold.

**And the stick was the actual bug.** 24 gives the right stick to `focus` in
game mode, which sends `[traverse]`'s keys - `next` is Tab and `up` / `down`
are the arrows. At a prompt that is not a poor fit, it is destructive: a thumb
resting on the stick sprays completions across the line and then walks the
shell's history over the top of it. A terminal answers the wheel with its
scrollback, which is what the stick is being pushed for anyway, so
`right_stick = "scroll"` takes it back the way `[profile.browser]` does - the
same exception for the opposite reason, since a browser's focus keys go
somewhere real and just not where the pointer is.

Every key here is the **shell's own** rather than an emulator's, which is what
lets one profile cover all five names in `match`: foot and alacritty have
neither tabs nor a context menu, and the obvious scheme - `Ctrl+Shift+T`,
`Ctrl+Shift+←/→` - would have been dead in two of the five while still
spending `X`. `X` keeps `click:middle`, which in all five pastes the PRIMARY
selection, so select-in-the-browser / click-in-the-terminal already worked and
the clipboard's own `Ctrl+Shift+V` stays on the `Term` page 27 built.

**Nothing in the daemon changed**, the third time in a row: 09's and 27's shape
has now absorbed a browser, a file manager, a chat client and a shell without a
line of Python.

**Revised in use: Tab was the wrong key to spend a button on.** From the sofa a
command is not typed at a prompt, it is aimed at on the on-screen keyboard - and
completing one meant putting the keyboard away, pressing `Y`, and summoning it
again, once per completion. Meanwhile the keyboard's own first page has had a
`Tab` key all along, sitting right where the line being completed is. What that
line actually wants from a button is **Backspace**: the letter aimed at is
regularly not the letter that lands, and there was no way to take one back
without opening the keyboard either. So `Y` is now a plain `key:BACKSPACE`.

**Plain, and that is the second lesson.** A tap/hold binding waits for the
release before its key goes down (`waits_for_release`), which costs the
autorepeat - and Backspace is the one key that is held rather than pressed. A
button that must repeat cannot carry a hold, so the interrupt had to move, and
it went to `X` with `Ctrl+Shift+V` on the tap: `X`'s middle click pastes the
PRIMARY selection, which wants a mouse to have made a selection and a pointer
parked on the prompt - from the couch, the deadest button in a terminal. The
price is the one this item already named, and after **38** it is the whole of
it: what a profile spends, it spends at rest, and the window layer is untouched
either way. A terminal now has no middle click at all, which is what a paste
that works with the clipboard everything else fills is worth.

### 38. The modifier the apps kept taking · ✅ Done · S

Asked for from the sofa: *in Discord, `LT` + `B` should close the window - the
LT modifier can work the way it does in every other application.* It did not,
and 09 is why: a profile's bindings were resolved in front of **every** layer,
so `[profile.discord]`'s `B` - deafen - answered the window layer as well, and
`ZL` + `B` deafened instead of closing. The same held everywhere a profile
existed: `ZL` + `X` opened a browser tab rather than floating the window, `ZL`
+ `L` / `R` switched tabs rather than sending the window to a workspace, and
the browser's `right_stick = "scroll"` scrolled the page while `ZL` was down
instead of moving the window.

**Nobody had ever wanted that.** The ledger says so in its own words: every
shipped profile records the window-layer reach as a *price* - "it costs `ZL` +
`X`, float / tile", "`ZL` + left stick no longer pins the window" - and 37 went
as far as choosing which button carried an interrupt in order not to pay it.
A cost that four profiles pay and none of them wants is not a feature, and
37's lesson - *a profile's real price is what the button does in the window
layer* - was the premise being wrong rather than a rule to design around.

**The guide had already decided this.** `build_pages()` reads `[bindings.*]`
and knows nothing about profiles, so the window page has always printed
*Close the window* on `B` no matter what was in front. Under the old
resolution that page was a lie in any app with a profile; under the new one it
is true again, and there is nothing profile-shaped for it to learn.

**So a profile stops where a modifier starts.** `[bindings]` is the app's
scheme *at rest*: it answers the base layer and game mode - which is the same
desktop with a bar on it - and a held layer keeps its own table. `stick_roles`
follows the same line: while `ZL` is down both sticks belong to the window.

**And the capability is still reachable, by name.** An app that really does
want a window op of its own writes `[profile.<app>.window]`, read in
`[bindings.window]`'s place for as long as it has focus - the layer named, not
inherited by accident. Nothing ships with one. A profile key that is neither a
layer nor `match` / `bindings` / `osk` / `left_stick` / `right_stick` raises at
load, because `[profile.shell.windows]` would otherwise be a table that simply
never fires and nothing on screen would say why.

**Nothing in the daemon changed** - the fourth time in a row. It is thirty
lines of `config.py`, and what it gives back is one sentence: the left trigger
means the same thing in every application.

### 39. YouTube: the television's two controls · ✅ Done · S

Asked for from the sofa: *give the YouTube webapp its own shortcuts - play /
pause and fullscreen on the face buttons.* The fifth app to want a profile, and
the first that is a **television** rather than a tool: 35 put a row in the menu
for it because a console has one of these and a desktop does not, and what
that row launches is a webapp window the pad can walk to.

**Two controls, and both are the same kind of target.** Whether it is playing
and whether it fills the screen are the player's own buttons, they sit along
the bottom edge of the video behind an overlay that hides itself, and hitting
one from a sofa means waking the overlay first and then aiming inside it. So
`X` is `k` and `Y` is `f`.

**`k`, not Space.** Space scrolls the page whenever the player is not the
focused element, which after any click is most of the time; `k` is answered by
YouTube's own document handler wherever the focus is, as long as it is not in
a text box.

**`Y` is a second Do, and the ledger says so.** The pattern wants the reach on
`Y`, and here the reach is the search box - but searching cannot happen without
the on-screen keyboard anyway, so `/` costs nothing by moving one button along
to `L3`, and the button a thumb finds first carries the control every video
needs. `R3` hands mouse button 4 back as `Alt+Left`, the displacement
`[profile.browser]` already makes.

**A and B were free, which is the part worth recording.** Nothing had to bend:
`A` is Enter, which opens the thumbnail 22's traversal walked to, and `B` is
Esc, which is how a browser leaves fullscreen - "B goes back" in the player's
own words. The D-pad was free too: YouTube reads the arrows as seek and volume
while the player has the focus. Four buttons of the budget bought two controls,
because the scheme already answered for the other two.

**`match` is the host with its leading dash**, and that is new. Every profile
so far matched a word - `discord`, `foot`, `chromium` - but `youtube` on its
own takes **YouTube Music** (`chrome-music.youtube.com__...`) with it, where
none of these keys exist. `-www.youtube.com` and `-youtube.com` match any
browser's webapp class and neither matches Music's. Declared before
`[profile.browser]` for 35's reason.

**Nothing in the daemon changed**, the fifth time in a row.

### 40. The television's two devices, and the rows nobody could write down · ✅ Done · M

Asked for from the sofa: *when I plug the television in I should be able to
pick the sound and the microphone, or it is back to a keyboard and a mouse.*
Which is exactly right, and the reason it had never been a row is that **the
answer is not in a config file**. A menu built at load can only name what was
written down; plugging a television in adds an output that was not there when
anybody wrote anything.

**So a row can list its own submenu.** `from` is a command, `action` is the
template each of its lines runs, and the line carries the values as `%1` and
`%2` - a node id and a device name, because the command that moves the sound
wants both. Read when the row is entered rather than cached, since the whole
point is that the answer moves; the OSK page a profile lends an app (32) had
already established that a command's output can be a surface's content, and
this is the same idea one surface along.

**The tick is the feature.** `state(action)` can ask a setting what it holds,
but nothing can ask a device whether the sound is going to it - so the listing
says. A label that arrives with a `*` is the one in force, which is the mark
`pactl` and `wpctl` already print beside the current device, and the mark is
not drawn. Without it the page would be three names and a guess. Picking a row
moves the tick locally and keeps the menu up: the command is let go of rather
than waited for, so re-reading the listing at that moment would race the thing
the press has only just started, and the answer settles at the next entry.

**Every value is quoted as it goes in**, and that is not tidiness. A device
names itself from its own USB descriptor - from outside this machine - and the
name lands in `/bin/sh -c`. A speaker called `x; rm -rf ~` is a plausible
thing to hand a daemon that runs as the user.

**The two listings are not symmetric, and the second one was wrong first.**
The outputs are the ones Omarchy's own switcher offers: a sink whose only ports
are unplugged is left out, and so is the physical sink a speaker tuning fronts.
Copying that filter onto the inputs listed *nothing at all* - a built-in
microphone reports its jack as unplugged and is still the microphone in use, so
the filter hid the row that was ticked. The inputs are every source that is not
a monitor instead, a monitor being what the speakers are already playing rather
than anything anybody speaks into.

**A press no longer waits for the command.** It did at first, which was the one
thing here that broke the loop's own rule, and `[menu] list_timeout_ms` was all
that stood between a wedged listing and a pad that had stopped answering. The
honest version was written afterwards: `actions.Commands` runs the command on a
thread, the press enters the page at once, and the rows land in it when the
answer does. The timeout is still there, now as the floor under the thread.

**They are a page of their own, and that was the second thing asked for.**
Beside `Mute` and `Play / pause` the two rows read as an odd third thing, and
the complaint named it exactly: the Audio submenu was answering *how loud*,
*where the sound goes* and *what is playing* in one column. Only the middle one
is set when the room changes rather than while you are sitting in it, so it
goes a level down under `Devices` - the rule the menu already follows, that
what a thumb reaches for often keeps the top of the page.

**Found on the way:** the menu card is a fixed width, so a long device
description elides. Left alone. It elides from the right, which is where the
part that distinguishes one device from another is not, and widening the card
for this would be the menu no longer measuring the same as the Omarchy one.

## Suggested order

Done: **01–09**, **11**, **13–40**. The button scheme (07) settled first because it
decided what the keyboard's own map (03) should be; the keyboard itself (03–06)
followed, then the menu (08), and 13–17 and 19–22 came out of using the thing, and 09
(per-app profiles) landed once the map underneath had a shape to layer over.

**10 landed sideways** as the right-hand end of 23's game bar — see there for
what it turned out to be, and why it prints only what is live. What remains of
the original idea is the desktop half: the same strip has never been shown
outside game mode, where a profile's bindings change under you as focus moves
and the countdown 18 put behind a hold would have somewhere to draw itself.

The original note read: a hint bar along the bottom. It is the one item still waiting
on profile support: without 09 it could only guess what a focused app would do
with a keystroke, and now the bar can be honest wherever a profile exists, which
is exactly the boundary it wants. It has a second job now too: **18** put a
countdown behind a hold, and the bar is where a countdown belongs once there is
one to draw.

**12** still needs a decision rather than an implementation, and the open
caveats are small: 01's `r±1` walks the monitor's
whole workspace range rather than stopping at ten, and 02's idle inhibitor only
holds while the keyboard is up — pad activity in desktop mode should hold it
too.
