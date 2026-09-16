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

*(Taken back in item 50.* It was right while every row was a verb in one
column. A grid of tiles that hold values is a different thing for a thumb to
be doing, so the left stick walks the tiles and the right one keeps the
pointer - and the promise above is kept by the thumb that was aiming with it
anyway.)*

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
is taken for a stick held during connect and left alone, since calibrating
onto it would freeze that direction for the session.

The limit shipped at 0.90, and that was too generous by far: an Xbox Elite
Series 2 connected with a thumb on the right stick rested 0.84 out, calibrated,
and scrolled Discord and YouTube downwards at full speed for the rest of the
session — the leftover half-range was a sixth of the advertised one, so the
stick's real centre read as a full deflection. 0.60 is the default now, one
notch clear of the 0.50 a pad genuinely resting off centre sits at, and a
refused calibration says so in the log.

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

### 41. The pointer that kept sliding across the game · ✅ Done · S

Reported from the sofa, on the other machine: *I opened a game and it seemed to
be taking mouse input the whole time; I could not use the pad's buttons because
of it.*

**Handing the pad over was only ever half done.** `handed_over` was asked in
exactly one place - `allowed()` - and that place decides what a *press* may do.
Nothing asked it about the sticks. `drain_events` went on storing the axes,
`needs_tick` went on asking only whether a layer had given a stick a role, and
`tick` -> `emit_cursor` went on moving the virtual mouse. So the buttons stood
aside politely while the left stick drove the desktop's pointer across the game
underneath.

**The comment for `handover_siblings` had already written the symptom down** -
"a Proton game leaves the pad driving the desktop's pointer over the top of it"
- and filed it as what happens when the *detection* fails. It was also what
happened when the detection worked. It went unseen from the couch because game
mode turns both sticks off by default, and the report came from a desk.

**A stick gets no `reaches_past`.** What buys a button its way past an app
holding the pad is being a gesture the game does not ask for - a chord, an
announced hold - and a stick pushed over is the one input every game does ask
for. There is nothing to opt back in to, so `stick_roles()` returns
`("none", "none")` and that is the whole of it. `surface_open()` is now the one
question the grab, `allowed()` and the sticks all ask, so a surface takes the
pad, the presses and the pointer back together: the keyboard is pointed at with
a stick.

**What it made worse is the item that was already open.** An application that
opens the pad without being a game - Discord polls the Gamepad API for its own
keybinds - now lost the pointer as well as its bindings for as long as it was
focused. That is 42, and it went in on the same afternoon.

### 42. The application that opens a pad it is not played with · ✅ Done · S

Left open since the handover landed, and 41 made it cost the pointer rather
than a few bindings: **Discord holds the pad without being a game.** It polls
the Gamepad API so its own keybinds can answer a controller, so `/proc` sees
it holding the pad for as long as it is focused, and the profile 35 built -
the voice panel on the face buttons, the thing you aim at with the pointer the
rest of the time - stood aside in the one window it exists for.

**No amount of looking at /proc answers this**, and that is why it sat open.
The question `wants_pad` asks is *has the focused app opened the pad*; the one
worth asking is *does holding this app's pad mean driving this app*, and the
second is a fact about the application rather than about its file descriptors.
The note called for an ignore list by window class, and then a whole second
matcher would have existed beside `[profile.<name>]`, which already matches
applications by window class and is where every other thing an application
disagrees about is written down.

**So it is a profile key.** `handover = false`, one line, shipped on
`[profile.discord]` and nowhere else. `update_handover()` asks the active
profile before it asks `/proc`. The ordering fell out of it:
`seed_active_window` asked about the pad *before* swapping the profile in, so
every focus change had been answering for the window that had just left -
invisible while the answer came from a pid, wrong the moment it came from a
class.

**The dangerous direction is the other one**, and the comment in the config
says so: a game that lands here is a game the pad cannot reach. The key only
ever refuses the hand-off - there is no `handover = true` that forces one,
because being handed a pad you have not opened is not a thing to ask for.

### 43. The game that only ever saw a keyboard · ✅ Done · S

Reported from the sofa, with 41 and 42 already in: *Steam is fixed, but I open
Palworld and it is still wrong - the right stick opens menus, and inside the
game the pad reads as a keyboard and a mouse.*

**Which is exactly what a pad that was never handed over looks like.** The grab
kept the physical pad from the game's own SDL, so the only pad-shaped thing
reaching it was our virtual keyboard and mouse, and the right stick's `focus`
role was walking the game's controls with Tab. Nothing above the hand-off was
broken; the hand-off never happened.

**Steam's window handed the pad over and the game it started did not**, and the
difference is depth. `wants_pad` asks whether a holder is in the process tree
around the focused window, and that tree was bounded by a count: three, chosen
from `Steam -> reaper -> wrapper -> game`. Measured on this machine, `steam ->
srt-bwrap -> pv-adverb -> steamwebhelper` is *already* three, before a Proton
game adds the reaper and wine's own wrapper. Steam's own window worked because
Steam's window pid is Steam, which holds the pad itself.

**Raising the count was the wrong repair**, and worth writing down as such: the
same number applied to a terminal walks to the compositor, and everything under
the compositor is every window on the screen. A count cannot mean "the same
application" - it means "this far", which is a different thing in every tree.

**The cgroup already meant it.** systemd gives each launched application its
own scope, and everything Steam starts - pressure-vessel, wine, the game -
stays
inside Steam's: measured, one `run-p<pid>-i<id>.scope` holds the lot, while
two terminals sit in two scopes of their own. So the climb is bounded by scope
instead of by a number, and ends exactly where the application ends. `depth`
keeps its other job - how far *down* to look - and is the only bound left on a
machine that gives applications no scope to read.

**What it does not fix, and is not ours:** Steam reads controllers through
`hidraw`, which `EVIOCGRAB` does not cover, so Steam sees the pad whatever the
daemon holds. The overlay opening on the right stick is Steam's own desktop
layout answering a pad it thinks nothing else is using - Settings > Controller,
not a binding here.

### 44. The lock, for the game /proc argues about · ✅ Done · S

Asked from the sofa with 43 in: *give me a way to say "this is a game, leave
it alone", from inside the game, and a row in the menu to take it back.*

**The hand-off is a question about a program and it is right about the games
it can see.** What is left over is two things, and both are the same shape: a
person can see something `/proc` cannot.

A game the walk misses never gets the pad at all - and 43 was one of those,
found only because the pad read as a keyboard inside Palworld. Every fix for
that class is a better guess about process trees, and there will always be one
more launcher. And a game that *has* the pad still sees what reaches past it:
`[profile.steam]` puts a workspace on a shoulder held two seconds (`[confirm]`
1.2 s, then 0.8 s), which is deliberate at a desk and is also a thumb resting
on LB mid-fight.

**So the lock is the same question answered by hand.** `daemon.set_locked()`
pins `handed_over` on ahead of every other test - including a profile's
`handover = false`, which is a fact about an application and not about this
moment - and `allowed()` then refuses everything but a chord. Not the
announced hold, not `reaches_past`, not a single-button summon.

**And a refusal has to reach the announcement, not just the act.** Locked,
the shoulder still ticked and still said *Next workspace* two seconds in:
`allowed()` was asked when the hold fired and never when it announced itself.
An announcement is a promise, and both halves of it - the motor and the
notification - land on top of the game. `check_hold_timers()` now asks before
it warns, every tick rather than once, so a hold that outlives the lock still
announces itself.

**It is called the workspace lock**, in the row, on the guide page and in the
notification alike. *Game lock* was the first name and it says the wrong
thing: nothing about it belongs to the game, and what a person turns it on to
stop is the workspace walking away under a held shoulder.

**A chord is what is left because the menu has to stay reachable.** The lock's
own notification says "unlock it from the menu", and a lock that closed that
door would be a pad that does nothing until you find a keyboard.

**The way in is `ZL + B` or `ZR + B`, and it fires only over an app that
already has the pad.** Both triggers because which one a thumb is already
using is the game's business. The condition is not decoration: on the desktop
`ZL` + B closes the window and `ZR` is a left click held for a drag, and a
chord takes both buttons' own jobs the moment it exists - a chord member
cannot fire on the way down, since whether it is a chord is not known until
its partner has had a chance to land. So `Action.claims_chord(ctx)` was added
for it: a chord whose action can do nothing right now neither fires nor makes
its buttons wait. Over a game the same two cost nothing at all - the grab is
off there, so the game sees both whatever omapad does with them.

**Runtime state, not a setting.** A lock written to `settings.toml` is a pad
that does nothing at the next boot for a reason nobody remembers.

The menu row is at the top level rather than under Controller: it is the row
looked for while a game has the pad, and a row you have to go and find is a
row that is not there. It ticks while the lock is on, and the bar widget wears
a padlock in the same colour game mode uses - by then omapad's own bar has
gone, because the pad is the app's.

**And it is not there the rest of the time**, which the first cut got wrong:
the row sat in the desktop menu, where picking it hands the pad to a terminal
and leaves you finding the menu again to take it back. Hiding it needed
something the menu did not have - a row that is only offered in some states -
so `when` was added: `game`, `handed_over`, `locked`, any one of them enough,
read when the menu opens rather than per draw, because a row appearing under
the selection moves every row below it while a thumb is aiming at one. The
control socket asks nothing: `omapad ctl lock on` is typed on purpose, and it
is the door a script has.

### 45. Two bars along one edge · ✅ Done · S

Reported as a lock that doubled the bar: *workspace lock yapıp tekrar unlock
edince bar çiftleniyor* - both omapad's bar and Omarchy's on screen at once.

**The lock was the messenger.** `hyprctl layers` had `omarchy-bar` at y=1174
and `omapad-gamebar` at y=1134, both on screen, with `toggles/bar-off` gone
while omapad had been in game mode for four minutes. Nothing in the lock's
path touches the bar; what it does is take our bar away and give it back,
which is exactly the moment a second bar becomes visible.

**The real fault is that the desktop bar's state was said once, at the switch,
and never again.** It is a *file* - `omarchy toggle bar` creates and removes
`~/.local/state/omarchy/toggles/bar-off` - so anything may flip it, and
Omarchy's own bar carries a comment saying its watch on that directory can
stop delivering events when changes land together. A daemon that hears none of
that goes on believing what it said minutes ago.

So `set_gamebar()` says it again every time ours opens. The command names the
flag rather than toggling it, so a repeat costs one spawn and changes nothing
when nothing has changed - and it lands exactly where the doubling would be
seen. Measured on this machine: flag deleted by hand, both bars on screen,
then one lock and unlock and `omarchy-bar` is back at y=1200 with the flag
restored.

`Daemon.start()` came out of the same reading. `[mode] start = "game"` has no
switch to hang any of this off, and `run()` was already calling `apply_cursor`
for that reason and nothing else - so a session that started in game mode
opened our bar under the desktop's and stayed that way until the first switch.

### 46. The copy a terminal had no button for · ✅ Done · S

Asked for as a binding and answered as one, plus the thing that made it
invisible: *terminalde sagda gosterdigimiz tuslara copy'i de ekleyelim, cok
kullanisli oluyor kopyalamak*.

**The binding was the easy half.** `[profile.shell]` had spent X on Backspace,
Y on the paste and L3 on `Ctrl+L`, and R3 was still `click:back` - a click no
terminal answers, which makes it the last cheap button a terminal has. So
`RSTICK = { tap = "key:CTRL+SHIFT+C", desc = "Copy" }`, shifted because the
unshifted one is the interrupt already sitting on Y's hold. It closes the hole
item 37 wrote down as the price of the paste: the profile had spent both middle
clicks, so a selection dragged with ZR could be made and never put anywhere.
Now it goes to the clipboard Y pastes from.

**"Sagda" is what the item is really about.** The bar's row of hints was
`kinds = ["face"]`, and the argument for that - the face buttons are the half
of the pad that changes under you - had quietly stopped being the whole truth:
`docs/conventions/bindings.md` says a profile's budget is *four*, X, Y, L3 and
R3, and every shipped profile spends the stick clicks. So the row was printing
two of a profile's four and hiding the rest, and a copy put on R3 would have
been bound and unmentioned on the one surface whose job is to say what the pad
does. `HINTED` is `("face", "stick")` now. The shoulders and triggers stay out
for the reason they always did: they mean the same thing wherever the scheme
goes.

`MAX_ACTIONS` is still 3, so four bound buttons means one falls off in
`PREFERRED`'s order - thumbs-first, so L3 goes. That is the right one to lose:
L3 is the cheapest of the four wherever it is spent, and the guide is where the
whole scheme is read. In a terminal the row now comes to *Backspace*, *Paste*,
*Copy*, with `Ctrl+L` a page away.

### 47. The badge that had never been drawn for what it carries · ✅ Done · S

Item 46 put R3 on the game bar and the drawing was the first thing seen:
*button olarak r3 baya kotu gorunuyor, duzeltelim. border varsa outline belli
bile olmuyor yazi da sikismis halde*. Two faults, and they had been there since
the badges were drawn - R3 had simply never stood anywhere anybody looked.

**The letters.** `fit` comes down in 4% steps until a label clears
`MIN_PADDING`, which is right for a shape it is handed and wrong for a shape
that ships. `L3` came out at **12.39** units inside a 26-unit circle where
every other badge is punched at **13.44**, with **0.25** units of air - two
characters running edge to edge next to an `A` sitting in three. `stick.svg`
was a circle *smaller* than a face button carrying *twice* the characters;
every other two-character label on the pad - LB, RT, ZL, R1 - has a wide shape.
So the stick got one: a pill inside its own rim, and all four of its labels are
at the full cap with air around them.

**The rim.** It was a stroked circle outside the filled one, and a stroke's
weight is in *pixels* rather than in the shape's units. So it stayed a hairline
on a badge twice the size - and in the stencil badge style, where the surface
paints the shape solid and every surface drew the rim in the *background*
colour, it was outside the fill with nowhere left to be. Painted background on
background: the style the reporter had turned on was the one where the rim did
not exist. It is an annulus in the same fill now - three subpaths wound the
opposite way in turn, so the same shape comes out under either fill rule - two
units thick at every size and in both styles. `Shape` raises on a stroke, and
`ring`/`ringWidth` are gone from `BadgeArt` and all four surfaces.

**56 by 40, and that is not a free choice.** A badge is `unit` tall and
`round(unit * w / h)` wide, scaled by one factor taken from the width, so a
shape whose aspect the unit does not divide stands a fraction of a pixel off
its own box and every flat edge in it is painted grey. `Metrics.badgeGrid` (5)
is what makes the division come out whole. The stick was drawn 44 by 32 first,
which wants a unit divisible by *eight*, and nothing would have said so - the
symptom is a slightly soft badge. `ShapesFitTheBadgeGrid` says it now, and
`LabelsStandAtOneHeight` says the other half: a shipped shape that makes `fit`
shrink its label is the wrong shape for what it carries.

### 48. The screen in front of the stream · ✅ Done · S

Reported from the sofa: *bazen oyun icin actigimiz ekranlar gamepad destekli
olmuyor ornegin geforce now oyun acarken steam big picturesiz aciliyor ve oyun
launch olmuyor, bu gibi durumlar icin menuden omapad kontrollerini toggle
edebilsek guzel olur.*

The hand-off was right and unusable. 36 established that GeForce NOW opens the
pad the moment its page loads, and 42 established that opening the pad is the
whole question `/proc` can answer - but a cloud client opens it *before there
is a game*. The launcher in front of the stream is a web page: it reads no pad
at all, and by then the pointer that could press its **Play** button has been
handed to it. Every binding stands aside for a window doing nothing with any of
them, and nothing announces itself, because from the pad's side nothing
happened.

**The lock already existed pointing the other way.** 44 built `set_locked` for
the game `/proc` argues about - the pad is the app's, whatever the walk says.
This is the same sentence with the other subject, so it is the same mechanism:
`set_keeping` pins `handed_over` **off** in the place the lock pins it on,
ahead of a profile's `handover = false` and ahead of `/proc`. The two are
exclusive; the second one asked stands.

**And the direction it points settles the rest of it.** The lock has to be
turned off through the one gesture it still allows, which is why 36's chord is
its door and why its notification names the menu. Keeping the pad makes every
gesture work again, so there is nothing to reach past and no chord to spend:
the way out is a plain press. What replaces that care is `when = ["handed_over",
"kept"]` on the row - offered while an app has the pad, *and* for as long as it
is on, so turning it on never takes away the way of turning it off.

It stays on until it is turned off, which is deliberate: the stream that starts
after **Play** does want the pad, and no timer knows when that is. The bar
widget lights up while it is on, and the tooltip names it.

### 49. The window that closed over a running command · ✅ Done · S

*game modda terminalde lt+b pencereyi kapatmak yerine ctrl+c yapsa kapatilacak
bir sey yoksa pencereyi kapatsa gibi bir ozellik ekleyebilir miyiz*.

`ZL` + B closes the window in every application, and a terminal is the one
where closing is not always what was meant. A command still running is the
thing in front of you; closing the window kills it and takes the scrollback
that said what it had done with it. Item 37 had already ruled the interrupt
onto `Y`'s hold, and this is the other half of the same question - not where
`Ctrl+C` lives, but what the close should do when there is something to
interrupt.

**Asked from /proc, not guessed at.** A pty has a foreground process group -
the one a `Ctrl+C` typed at that terminal is delivered to - and
`/proc/<pid>/stat` publishes it as `tpgid`. The shell an emulator starts is the
session leader of that pty, so the whole question is one comparison: while the
shell's own process group is the foreground one, the prompt is what is in
front. `omapad/terminal.py` walks down from the focused window's pid and asks
each session leader it finds. Measured against both terminals open on this
machine while they ran a command, before it was believed.

**It stayed in `[bindings.window]` rather than becoming the first
`[profile.shell.window]`.** `busy()` answers False for every window with no pty
under it, so a browser, a game and a file manager all take the plain close -
and the guide's window page, which knows nothing about profiles, goes on
telling the truth. The `desc` grew the second half it now has: *Close the
window, or the command in it*.

**Both halves are settings.** `[terminal] interrupt` and `idle` are parsed at
load like any other action, so a scheme that closes windows some other way
changes a setting rather than losing the interrupt with the close, and a shell
driven with something other than `Ctrl+C` says so. `depth` is how far below the
window to look for the shell; every emulator measured here starts it as a
direct child.

**Asked for in game mode, shipped in both.** Game mode is the couch
environment, not a shorter desktop: a window layer that behaved differently in
the two would be a second scheme to learn. What the item is really about is the
couch, where the window that will not close is harder to explain than anywhere
else.

**What a press pays for it, measured rather than assumed.** The walk is on the
event loop, because a button has to answer now. A terminal's whole tree is 24
/proc reads and 0.12 ms; Steam's window, ten processes under it, is 172 and
2 ms. The cost is in threads rather than processes - a child forked by any
thread is listed under that thread's own `children` file - so the bound is
counted in those reads: `READ_LIMIT`, 256, charged before each one. Without it
a browser's renderers would be 15 ms on the loop, two ticks of pointer movement
dropped for a question about a window with no terminal in it. And `busy()`
never raises: an action that throws takes the loop with it, so a nonsense pid,
an unreadable /proc and a process that ended mid-walk are all False, which is
the close.

**What it can be asked, and by whom.** Everything it reads is world-readable
and read with the daemon's own uid - no privileged step, no fd of the inspected
process opened, no symlink followed, nothing spawned, and no path built out of
anything but an integer. Two races, both bounded: a pid can be recycled and the
focus can move between the event that recorded it and the press that asks. Both
can only pick the wrong *half* - the interrupt is a key, which goes wherever the
focus is, and the close is `hl.dsp.window.close` on the active window, so
neither can act on a window that is not the one in front.

**What it cannot see, and why that direction is the safe one.** A shell inside
tmux belongs to the multiplexer's session and its server is not under the
window at all, so a busy pane reads as idle and the window closes - exactly
what this button did before. A terminal serving several windows from one
process (`foot --server`) is the other way round: any busy tty under that pid
answers for all of them, so an idle window declines to close while another is
compiling. Neither can close a window over a running command, which is the
mistake worth avoiding; the other costs one more press of the same button.

### 50. The menu that was a list of verbs · ✅ Done · L

Asked for from the sofa: *the menu and everything in it is still keyboard and
mouse shaped; make it a HUD - music, volume, brightness, all of it grouped
properly, and use the sticks and the vibration while you are at it.*

Which is right, and the shape of what was wrong is worth naming. **Every row in
the menu was a verb.** Press it, something happens, the menu closes. That is a
keyboard shortcut list drawn larger: one column, four D-pad directions and four
face buttons, and a list says every row is worth the same. What is playing is
not worth the same as the row beside it.

Three gaps, and they are separable. There was **no row that held a value** -
volume was two rows saying "up" and "down", brightness two more,
`Controller > Button labels` a submenu of four ticks, eight rows doing the work
of three controls. The daemon was **blind to the machine**: `Action.state` can
ask a setting what it holds and nothing can ask how loud the room is. And the
menu **read a quarter of the pad** - both sticks kept pointing, both triggers
and both shoulders did nothing, and the motor never ticked in it at all.

The whole of it is planned in phases; this entry is what has landed.

**Phase 1 - the head, the bar and the grid. Done.**

The top level is a bar of chips now, walked with L and R, and the tiles of the
group you are on fill the card. Above it a read-only grid carries the day, the
time and whatever command you point at it.

- **`snap.choose` decides which tile is that way**, unchanged. It already
  answered "which rectangle is that way from here?" for the windows a flick
  lands on, and a tile is a rectangle in cells - so the pad walks a page by the
  same rule it walks a desktop rather than by two that can disagree.
  `[menu] bias` is its own number and was measured on golden fixtures rather
  than inherited: windows are large and sparse, tiles small and touching.
- **Left and right stopped being a second way to say Back and Pick.** A single
  column left both free for that; a grid spends both axes on getting about, and
  A and B already said the other two things.
- **Placement is an order, not coordinates.** First fit, in the order the page
  is written, so the order stays authorial and a small tile backfills the hole
  a big one left. A `row_break` tile ends a row; deliberately not a one-cell
  spacer, which holds a hole open at six columns and shifts everything under it
  at four. *(Still how a page the author wrote is laid out, and still how
  every tile nobody has moved is laid out. **52** adds the other half: a tile
  somebody put in a cell is in that cell, and the flow runs around it.)*
- **Identity is a tile id, never an index**, in the model and on the wire. A
  tile changing size re-packs the page under it, so an index is stale the
  moment it is used - and that is due to start happening.
- **Weather, which was refused once and is not a feature now.** `roadmap.md`
  turned it down because *"putting it here means network I/O in an input
  daemon, with caching, failures and a location to own"*, and that was right.
  A head cell is a command string and a `ttl`: `omarchy-weather-status` owns
  the lookup, `omarchy-weather-location` owns the place, and the helper prints
  its own failure. omapad never learns what weather is.
- **The bar holds places, not verbs**, which cost item 48 its argument - *a row
  you have to go and find is a row that is not there* - for the workspace lock
  and *Keep the controller*. `open_on` answers it the other way round: while
  the condition holds, the menu opens **on** that tile with nothing at all to
  walk to. Nearer than a top-level row in a list of ten ever was.

  *(Answered again, and better, once the HUD was in a hand: the menu **comes
  back where it was left**. Use the lock once and it is what the next press
  opens on, at no cost to any other page - where `open_on` overrode where you
  left off every time. Nothing ships with the key now; it is still there for
  anyone who wants the other behaviour.)*
- The shipped tree gained a **`Now`** group and lost its loose top-level rows.
  What you change while sitting in the room is on the chip the menu opens on;
  `Audio` and `Display` keep what you set when the room changes.

**Found on the way:** a scroll worked out at construction is worked out against
a width of nothing. Both scrollers - the bar and the grid - computed where to
sit while their delegates were still being laid out, and the answer stuck: a
grid that fitted its card ended up scrolled past its own last row with
everything above it off screen, and every tile but the selected one was simply
off the top. Neither is driven from a delegate now, and both re-settle when the
geometry changes rather than only when the state does.

**Phase 2 - the legend, and the two keys a page may spend. Done.**

The foot of the card prints what A, B, X and Y do on the page in front, in the
contract's own order, drawn with the same generated buttons the guide and the
bar print. It is resolved through `guide.button_row(..., brief=True)` - the
guide already turns a binding into words and the bar already reads them short,
so this is that pair one surface along rather than a third opinion, read from
the same place a press reads.

A page may take **X and Y** for a job of its own, with `[menu.items.keys]`.
**Not A or B, and the parser is what says so** rather than a review: the
contract is that A commits and B leaves in every layer and every surface, and
a page that could take either would be the one place on the pad where that
stopped being true. A page taking X keeps `menu:close` on the hold, which is
rule 2 applied one surface along.

**One thing the plan asked for here could not be built, and the evidence is
why.** It wanted `omapad check` to enforce `bindings.md`'s rule that a `short`
is required where the first word of a `desc` is not the meaning. Whether it is
is a judgement no parser can make: of the fourteen shipped bindings with a
multi-word `desc` and no `short`, eleven read perfectly as their first word, so
the warning would be mostly noise. The decidable version - two bindings in one
layer printing the same word on the bar - fires on three places, and all three
are deliberate and already in that file's ledger. A check that only ever names
its own exceptions is a check nobody reads, so `bindings.md` now says out loud
that this rule is a person's and why.

**Nothing in the shipped tree spends one.** That is the answer rather than an
omission: a button is earned only when what it would do is *not reachable on
screen*, and a page of tiles almost always has room for one more tile. Play /
pause on the `Now` page is the worked example of when not to - it is a tile
already, and a tile costs nobody a reflex.

**A gap the legend opened, and closed in the same pass.** `guide.py` builds its
pages from the config and knew nothing about a page's keys, so the moment a
page took X, pressing Y opened a guide that was wrong about X - and the guide
is on Y precisely because you had forgotten what a button does. It takes the
page's table now. What made that cheap is an order that was already right:
`set_guide(True)` rebuilds before it closes the menu, so the page is still
there to be asked.

**Phase 3 - the drawn parts a control tile is made of. Done.**

Fourteen shapes in `assets/shapes/` and a fourth table, `CONTROLS_TO_DRAW`,
writing `shell-plugin/ControlArt.qml`. A dial's rim, its notches, its zone
disc, a needle and a thumb dot; a switch's pill and knob; two chevrons; four
transport marks; and the grip a tile will wear while it is being carried.

**Asked for as "a font, the way we generated one for the buttons" - and it is
not one.** The TrueType half of the generator exists to turn *letters* into
outlines so they can be punched out of a silhouette, and nothing in a dial has
a letter in it. What comes out is the same path data with that step skipped -
the right answer to what was actually wanted, and worth writing down in three
places, because "generate a font for these too" is the obvious reading of what
the buttons do.

**Only the furniture is drawn** - what does not depend on the value. The
needle's rotation, the zone's scale, where the dot sits and how far a knob has
travelled are geometry, and a shape parameterised by a number cannot be drawn
once. It is the split `BadgeArt` already makes between a button and the label
set into it, which is why `BadgeArt` paints both files without knowing there
are two.

A second generated file rather than more entries in the first: `ButtonArt`
cannot be a `pragma Singleton`, so every surface that badges anything
instantiates a copy and only the menu draws these - and `EveryBadgeIsDrawn`
says every label of every layout has art, which a map that also held dials
would turn into a coincidence.

**One rule these have that the buttons do not.** A badge is painted non-zero
normally and even-odd in the stencil style, so a ring drawn as two same-wound
circles is a disc in one of them. That is the trap `stick.svg`'s rim already
taught; the dial's rim is an outer arc wound one way and an inner wound the
other, and `AnnuliSurviveEitherFillRule` is what says so now. `MARK_CAPS` and
the centring test do not apply here at all - a needle is deliberately not
centred.

Nothing is visible on screen at the end of this phase, which is why it sits
before the tiles that use it rather than after.

**Phase 4 - the first two tiles that hold a value. Done.**

A `toggle` and a `choice`, each reading one of the settings the pad can
already change: `control` says which, `reads` says what, and `CONTROL_KINDS`
is the pair they have to make - a switch pointed at a number fails
`omapad check` rather than the sofa. `CHOSEN` is passed into `build()` rather
than imported, so `menu.py` stays the thing that holds state and geometry.

**Eight rows became four tiles.** `On` and `Off` as separate rows was always a
switch written out longhand; a tile that draws which way it is flipped says it
in the space of one. `Hide the pointer` and `Vibration` are switches now, and
`Button style` and `Start in` are walked in place.

**Where the contract's `taken` state was not spent.** A grid spends both axes
on getting about, so a control adjusted sideways has to be taken first - and a
switch has two states. Taking one in order to push it sideways is a mode
nobody needed, so **A acts**: it flips the one and walks the other forward.
What wants taking is a control with a range, and it arrives with one.

**What a choice tile cannot say, and what that decided.** It shows one value,
so the line each row of a tick submenu carried saying *how the choices differ*
has nowhere to go. `Button style` and `Start in` converted because their two
values say the difference themselves. `Button labels` and `Profile` kept their
submenus: getting either wrong scrambles the face buttons, and that line is
exactly what stops you. Seven sentences kept rather than four tiles won, and
`writing.md` carries the ledger.

A choice prints the word it is *called* rather than the word it is stored as -
`playstation` reaches a tile as `PlayStation` - from a `words` map beside the
choices it describes, which also fixed a notification that had been saying
`Button labels: playstation` all along.

**Found on the way:** a tile is one cell tall more often than not, and a name
anchored to the top with a control anchored to the bottom collides there
rather than stacking. One column, and a control tile drops its icon: the
control is the picture.

**Phase 9 - four things the motor can say. Done, and built out of order.**

Built before the slider rather than after it, because the slider's end stop
has nowhere to fire until this exists, and shipping it first means shipping a
silent edge and coming back for it.

The pad here reports `ff=107030000`, which decodes to FF_RUMBLE, FF_PERIODIC,
FF_SQUARE, FF_TRIANGLE, FF_SINE and FF_GAIN - and only `upload_rumble` used
any of it. Now there are four effects uploaded at attach rather than one:
**tick** (a press landed), **edge** (you cannot go further), **commit** (that
took) and **texture** (it is moving, held until something lets go).
`pulse()` is `play("tick")` under its old name, so nothing that called it
changed.

- **How hard and how long are settings; the waveform is not.** A square wave
  is what makes an edge feel like an edge, and turning that into a knob is
  offering to turn a bump into a hum. The cycle count is the same argument one
  field along, so the period is computed from the length rather than named.
- **The texture ships off, and has no fallback.** Off because item 17's rule -
  *a scheme where every press buzzes says nothing* - applies hardest to the
  newest gesture. No fallback because degrading a *continuous* effect onto one
  that must be stopped is the tick that sticks on arriving through a new door,
  and a hum stuck on is not the same risk as a click stuck on. Where the pad
  has no sine wave there is simply no texture.
- **Nothing new was needed in the struct.** `FF_EFFECT_SIZE` was sized from
  `"@HHhhHHHHHIP"` on the first day there was a tick, and that format string
  *is* `ff_periodic_effect` - the union's widest member. The one thing here
  that could have been silently wrong, so a test says it out loud.
- **`EVIOCGEFFECTS` asks how many the pad holds** rather than assuming.
  Uploading past the limit fails on the effect nobody notices is missing, so
  the upload order is the priority order: a pad with three slots keeps the
  three nearest a plain press and says in `journalctl` what it could not take.
- **`omapad check` prints which words this pad can say**, from the same pure
  `plan()` the daemon uploads - one decision, not a report about a different
  pad. On the Series S|X here: all four, with sixteen slots.
- **A held effect is a finger's, the same as a held key.**
  `release_everything()` stops it, so a hum cannot survive a mode switch with
  no press left to blame.
- **None of the new levels reached the pad, deliberately.** `pad-setting.md`
  step 4 puts a setting on the pad when the question arises while holding the
  thing, and *Vibration* already answers the one that does. A switch for the
  texture belongs with the first control that scrubs - until then it would be
  a switch nothing can be felt to obey.

**Phase 5 - the first tile with a range, and the two ways to move it. Done.**

Ten rows across three pages became five bars. `Speed` and `Dead zone` were four
stepping rows each, `Strength` two, and not one of them could say what its
number was or that it had stopped at an end - which is the whole of what a
slider says.

**This is where `taken` finally gets spent.** A grid gives both axes to getting
about, so a tile the selection is only passing over cannot also own left and
right: A takes a slider, and while it is held the two axes are the tile's.
Phase 4 declined to spend it on a switch for the same reason it is right here -
a two-state control had nothing to be held for.

- **A keeps and B puts back**, which is the first place on this pad where B's
  "leave" has had something to undo. Two words rather than one said twice, so
  rule 4 holds on a surface that briefly looked like it would break it.
- **A cancel leaves no trace.** B restores the value *and* takes the setting
  back out of `chosen` where it was not there before: writing a shipped
  default into `settings.toml` freezes it, and the user stops receiving the
  default that changes later. A push nobody kept must not do that.
- **Two ways to one set of numbers.** The D-pad lands on the number you meant,
  growing to `[menu] ramp` the longer a direction is held and starting again
  on a reversal - somebody who has gone too far is not asking for the speed
  they overshot at. Either trigger crosses the whole range in `[menu]
  sweep_ms`, taken or not, because a trigger needs no mode. The sweep moves in
  whole steps of the setting's own `step`, so a value swept to is one the
  D-pad could have landed on.
- **The triggers are read as axes, not bound.** `bindings.md` says of ZL that
  a layer trigger has no binding of its own, and this gives it none: a surface
  layer falls through to nothing, so both are free while the menu is up, and
  how far one is pulled is a question no binding could have asked. The rule is
  now written down there rather than left as a thing this phase did.
- **Nothing is saved or announced until the push stops.** A slider is one
  decision made over a second, not thirty: `settings.toml` written per step is
  thirty chances to be interrupted halfway, `apply_setting` per step
  re-uploads the whole haptic vocabulary for a level nobody stopped on, and a
  notification per step is the screen saying twice what the tile says once.
  The vibration strength ticks the motor exactly once, at the level you kept.
- **Phase 9's vocabulary arrives here.** `commit` on taking and letting go,
  `edge` on the step that first finds the end - once per arrival, because a
  wall you are still pushing against is still one wall - and `texture` held
  while the value is actually moving, which is `[snap] rumble`'s written rule
  about a step repeating under a held button, obeyed rather than restated.

**Found on the way:** a push that had not yet crossed a whole step still has to
count as a push. Settling on "nothing moved this tick" wiped the accumulator
every tick, and a gently pulled trigger - which needs several ticks to earn one
step - could never move the control at all. The hold is counted down off the
same `dt` the sweep integrates over rather than against the clock, so there is
one clock and a loop running slow slows both halves together.

**And a bug the first bad config found.** `build()` recursed into a nested
page without handing down either `settings` or `columns`, so a control below
the top level was never matched against the setting it reads and a span was
never measured against the page. Every control tile in the shipped tree lives
a level down, which is to say the check added in Phase 4 had been running on
nothing at all. Found by deliberately writing a slider onto a switch and
watching `omapad check` say the configuration was fine - which is the exercise
`pad-setting.md` asks for at the end of every setting, and the reason it does.

`Speed` and `Dead zone` also merged into one page, `Sticks`. The argument for
two was that eight stepping rows on one screen is a list nobody reads from
across a room; four bars is not that list.

**Phase 6 - what the machine is doing. Done.**

`omapad/live.py`: how loud it is, how bright, and what is playing. A **source
rather than a surface** - no socket and no control verb, the same shape
`snap.py` and `handover.py` have - and `naming.md` now says that is the
difference rather than an omission.

The daemon was blind to the machine: `Action.state` could ask a setting what it
held and nothing could ask how loud the room was. `Volume` and `Brightness` are
bars showing the real percentage now, and `Music` shows the real track.

- **Nothing in `live.py` runs a command.** It returns the string, and the
  daemon submits it to the worker every other slow thing goes through - a press
  must never wait on `pactl`. A test asserts structurally that the module
  imports neither `subprocess` nor `os`, because that is the rule most easily
  broken without anybody noticing.
- **Every command is a setting.** omapad knows nothing about PulseAudio,
  backlights or MPRIS; it runs a string somebody else wrote and parses what
  comes back, and a machine that answers these questions differently answers
  them by editing `[live]`. An empty string is a reading this machine does not
  have.
- **Volume bypasses `omarchy-audio-output-volume` on purpose.** That helper
  always ends in `omarchy-osd`, so every press would raise Omarchy's own
  overlay *over the tile showing the same number* - the opposite of what
  putting volume on a tile is for. Verified on the machine: moving the bar
  raised no OSD. Brightness keeps its helper, which offers `--no-osd`, because
  DDC, Apple displays and backlights are three code paths omapad must not
  reimplement.
- **The stale-read race, closed before it could be seen.** A read started
  before a write can land after it and rewind the bar for a tenth of a second.
  Every reading carries a generation counter; a write bumps it and an older
  answer is thrown away. The one bug here that would not have looked like a
  bug.
- **A reading that times out keeps its last value.** A parser returning None
  means *no answer*, never *zero*: a tile that empties because a helper was
  slow is worse than one a second stale, and a helper that hangs must never be
  able to empty the HUD.
- **`live:` is `pad:`'s twin.** `live:volume=up` works from any button, with
  the same grammar, because a capability reachable only from the shape it first
  shipped in is a gap rather than a design.

**Where this went a different way from the plan, and why.** The plan had one
media tile with a transport inside it, and A meaning play/pause on a control
that also had to be taken to reach previous and next. Every way of writing that
ended with A meaning two things, or with pausing your music costing two
presses - and pausing is the commonest press on that page.

So the transport is **three tiles**. `Music` plays or pauses on A, the way a
switch flips on A, because it has two states and needs no mode. `Previous` and
`Next` sit either side of it, and left and right walk to them exactly as they
walk to anything else. No button learns a second meaning anywhere, and a tile
costs nobody a reflex - which is the same argument `bindings.md` already makes
about not spending a page key. `canGoNext` and `canGoPrevious` are read and not
drawn: they decide whether a press that way ticks `edge` instead of going
quiet, and a mark on screen you cannot press would say that twice.

**Phase 7 - the dial, and the menu as a surface that streams. Done.**

`Controller > Sticks` had four blind stepping rows: change a number, then go
and find out. There is a dial per stick now, with the dead zone shaded and a
dot where the thumb actually is. Push the stick slowly and the moment the dot
lights is the edge you have set.

**The rule is that the *tile's* kind decides, not the surface's.** The menu
pushes at `[menu] live_hz` only while a gauge carrying `shows` is the tile in
front, and only while the menu is open. Measured here: about 1.5% of a core
with a dial selected and a hand resting on the pad, a quarter of that on any
other tile, and nothing at all with the menu shut.

- **Two pushes, and the second one rebuilds nothing.** `push_menu_live` sends
  `{open, sel, g, live}` with **no `items` key at all**, so `applyState` gets
  past its own guard, finds nothing that is a model, and never reaches
  `fresh()`. One binding re-runs instead of twenty tiles being built. Not a
  new rule - `qml.md` §5.4 already said the panel decides a line says nothing
  new, and this is the daemon declining to send what it knows has not changed.
  `viewsock.md`'s *every push is the whole surface* gains its one exception,
  safe because the heartbeat still carries the whole thing.
- **The cost of that is one rule**, and it is checked rather than reviewed:
  nothing in `Menu.qml` may bind a layout width or height to `root.live`, or a
  layout pass per frame throws away everything it bought. The test was broken
  on purpose to confirm it fails.
- **The claim was measured rather than asserted.** A text test cannot see a
  delegate being built, so a creation counter went into the tile delegate and
  came back out: forty streamed lines rebuilt nothing, and neither did the
  selection moving or edit mode opening. Only a page that is genuinely a
  different list of tiles - another chip, or a tile hidden - rebuilds one.
  Better than the plan predicted, because `fresh()` also catches a full push
  whose items have not changed.
- **The floats are quantised in the daemon**, and not as a noise filter: it is
  what makes the guard work, so a thumb resting off the stick stops the stream
  entirely rather than pushing ADC jitter at a screen nothing is moving on.
- **`sel` rides on the stream on purpose**, so it is meaningful on its own and
  the panel never correlates two of them.
- **Analogue input arrives only here, which is the point.** The grid and the
  controls are all verifiable with a D-pad, so a stick problem can never be
  confused with a navigation or a stepping problem. A stick role of its own,
  `menu`, and the menu becomes the one implicit surface layer that does *not*
  keep the base roles - the left stick walks the tiles, held rather than
  flicked, and the right one keeps the pointer so the promise about the
  pointer staying live under the card is kept by the thumb that was aiming
  with it anyway.

**Two things drawn wrong before they were drawn right.** A dead zone is a
tenth of the travel, so drawn to scale it is four pixels across the middle of
the dial - smaller than the dot it is supposed to contain. A ring was no
better: scaled down it is its own thickness. So the dot's **colour** is what
answers the question - dim while the stick is being swallowed, accent the
moment it is not - which is legible at any value and at any size, and the
shaded disc is left as context rather than as the reading. `dial-zone.svg`
went with that change: a circle of variable radius is `radius: width / 2` and
not a drawing, which is the slider track's argument one shape along.

`dial-needle.svg` went too - drawn in Phase 3 for a rotary the gauge turned out
not to be, since a stick has a position rather than a bearing. `test_assets.py`
gained the invariant that caught it: every generated part is one some kind is
drawn from.

**Phase 8 - the tiles become the person's. Done, and the item closes with it.**

Hold Y on any page and every button on the card means something else. The
legend says which, which is the whole of how the mode is findable - and
`EDIT_KEYS` is six ordinary binding specs that `binding_for` consults before
the page's keys and before the layer's, so **what the legend prints and what a
press does come out of one table**.

The contract holds through the mode. A still commits: picking a tile up and
putting it down is what commit is saying there. B still leaves. X is this
surface's own verb one mode along - `close` becomes `hide`. Y is still the
reach, for the arrangement that is not on screen because it is the one the
config shipped.

- **L and R are the only controls taken from anything**, and only while the
  bar is not what a thumb is aiming at. Nothing is taken from ZL or ZR: a
  height is a control's own shape - a bar is a bar and a dial is round - so
  what a person overrides is how much room *across* a tile gets, which is two
  buttons rather than four.
- **Moving is a reorder, never a coordinate.** First fit always produces a
  valid packing, so a tile can only land somewhere real, and a layout written
  as names survives a different column count, a new tile and another screen.

  *(**Reversed by 52**, and for a reason this bullet does not contain: an
  order cannot express an empty cell, so a page with one tile on it had
  nowhere to put that tile. A carried tile is put in a cell now; everything
  unpinned still flows around it in this order, and `place` clamps a pin
  rather than losing it, which is how the packing property above survives the
  change.)*
- **There is no add page, and that is the better answer.** A hidden tile stays
  drawn where it sits while you are arranging, faded, so removing and
  restoring are the same press on the same tile - no second surface, and
  nothing to go and find. The plan had Y opening a page of removed tiles;
  this is one less screen and one less thing to be lost on.
- **The tree is never mutated.** The arrangement lives in `MenuModel.layout`
  and is applied when a page is shown, so a page reads the same whether it was
  just rearranged or just walked back into - and the config's own order is
  still there for Y to reset to.
- **The merge is three deterministic rules**, because this is where a saved
  arrangement and a changed config meet and that must not be something anybody
  interprets: hidden suppresses only what the config still has, anything new
  is appended, and anything gone is dropped. Editing `config.toml` cannot
  break a layout and a layout cannot hide a tile that did not exist when it
  was written.
- **Syntax corruption and semantic corruption are different failures.** A file
  that will not parse costs the whole arrangement and one warning; an unknown
  id costs that id; a bad span costs that override. Never a `ConfigError` - a
  file the daemon wrote itself must not be how the daemon stops starting.
  Confirmed by hand on the machine: a layout.toml full of rubbish, and the
  daemon came up.
- `omapad check --layout` says what a saved arrangement still resolves to -
  which ids are gone, which are new since it was saved, which are hidden. A
  layout that has quietly lost half its tiles is exactly the kind of thing
  this project makes a command say out loud.
- Every gesture is a `menu:` verb, so the whole mode is drivable with
  `omapad ctl menu edit|pick|hide|restore|wider|narrower|save` and no pad -
  `pad-surface.md` step 6, which is also how it was verified.

**Found on the way.** Pushing a tile down has to take it past the *whole* of
the row below, not up against that row's near edge: taking a tile out of a row
leaves room behind it, so anything short of that packs straight back into the
row it was trying to leave. And `load()` gaining a fourth file re-opened a hole
`shipped_config()` exists to close - a suite that reads the developer's own
`~/.config` tests whichever machine it runs on. Every call site in the suite
now names a layout it does not have.

**What the hold costs.** Y acts on the way back up rather than on the way
down now, the way every tap/hold does - the same beat HOME already has in this
layer.

**Item 50 is done.** The menu that was a list of verbs is a HUD: a head, a bar
of places, a grid of tiles that hold values, a legend, four things the motor
can say, and a page you arrange yourself.

**And then it was looked at from the sofa**, which is the only place any of
this was ever going to be settled. What came back: fill the screen and draw no
panel; blur and darken what is behind; put the row of hints where the game
bar's row already is and take the bar down before the menu draws, or the two
crossfade in one band; come back where it was left; stop saying `Go…` above a
bar of chips that says it already; and **one badge treatment, not two** - every
badge on the pad is a solid silhouette with its label punched out, so the
stick's rim had to go. A ring among them reads as a different colour rather
than as a different button.

### 51. The machine, under whatever is playing · ✅ Done · M

Item 50 ends with a HUD whose every tile is something you change - how loud,
how bright, which mode, what is playing. **None of them is something you only
watch.** Game mode takes Omarchy's bar away, which is right for a screen read
from a sofa and leaves the question that bar was answering: what the machine
is actually doing while it does it.

Two things, and the second one is why this is not just a menu page.

**A source for the readings, which is `live.py` one layer down.** `live.py` is
what the *desktop* is doing and every one of its answers is a helper's;
`sysinfo.py` is what the *kernel* publishes about the hardware, so almost all
of them are a file read - and a file read is not something to spawn a shell
for twice a second. That split is the whole of why it is a second module
rather than six more entries in the first: `command()` is what tells the loop
which of the two kinds a reading is, file reads happen on the loop and `cmd:`
goes through the worker like everything slow.

- **Where each reading comes from is a setting**, in one grammar,
  `<how>:<where>`, because there is no answer here true of every machine:
  which chip holds a temperature, whether the graphics card publishes a load,
  whether anything on this desktop knows a game's frame rate. `file:` and
  `cmd:` are the two that reach anything, which is why the list of *hows* does
  not have to grow every time a driver publishes something new.
- **An empty source is a reading this machine does not have.** Nothing asks
  for it and no tile is drawn. Three ship with a source; a temperature
  deliberately does not, because every machine has hwmon chips and their
  numbers are not interchangeable - one picked for somebody prints the wrong
  number under the right word, and a wrong number is worse than no tile.
- **hwmon is found by the name a chip publishes, never by its number**:
  `hwmon4` is a battery on one boot and a network card on the next.
- **A busy share is measured across an interval**, so the first read answers
  nothing at all. `/proc/stat` counts ticks since boot, and one read of it is
  what the machine has averaged since it was switched on - a number that is
  true, useless, and indistinguishable from a real one once it is on a tile.
- **A reading that stops answering keeps its last value**; one that has never
  answered has none, and that is how a tile knows not to draw itself. A sensor
  briefly busy must not be able to empty the screen.
- **Only a share has a bar.** A thermometer's top of scale is a number
  somebody would have to invent, and a bar against an invented maximum says a
  different thing on every machine it is read on - so there is no `v` in the
  payload and no track drawn, rather than a bar that lies.

**And a surface that is deliberately not a surface of its own design.** What
the HUD draws is an ordinary `[[menu.items]]` group: `hud.py` packs it with
`menu.arrange` and `menu.place`, the same two functions the menu packs a page
with, and the panel draws those cells over the whole screen instead of inside
a card. So the tiles are written where every other tile is written, arranged
with the gesture that arranges every other page, and the arrangement lands in
the same `layout.toml` under the same page id. There is no second place to
configure this and no second packer to disagree with the first.

- **It is a setting, not a surface that is opened.** `[hud] show` is in
  `CHOSEN`, so the switch on the page, `omapad ctl hud on` and the settings
  file are three doors onto one value - and it is still on tomorrow. Every
  other surface is opened and closed; this one is decided once and left, which
  is why `set_hud()` closes nothing, takes no grab and has no layer.
- **It reads no pad input at all**, which is the whole of what lets it sit
  over a game: no `[bindings.hud]`, no `SURFACE_LAYERS` entry, no keyboard
  focus and an empty input region. The moment it could take a press it would
  be in the way of the thing it is drawn over.
- **`WlrLayer.Top`, not Overlay.** The menu, the guide and the keyboard are
  Overlay, so opening one of them covers the readings rather than fighting
  them for the same band of screen. `ExclusionMode.Normal` then asks for what
  is left once the bars have taken their strips, which is why no bar geometry
  travels in this payload and the top row can never come up under the game
  bar.
- **Two rules about what it refuses to draw**, and both are the point: a tile
  that is not a readout is not drawn - the page holds its own switch, and a
  switch is a thing to press - and a reading that has never answered draws
  nothing at all, which is what makes one page correct on two machines. The
  **whole** page is still packed, including what will not be drawn, or a
  readout would not land in the cell the menu shows it in.
- **The menu does not follow the second rule**, deliberately. A readout there
  keeps its label with the value blank, because the menu is where you go to
  find out that a reading has no source on this machine - and a row that
  vanished could not tell you that.

**Found on the way, and it is the finding of this item.** The daemon half
landed first and was complete: the model, the sources, the settings, the
validation, the control verb, the wiring, the heartbeat. It streamed to
`hud.sock` twice a second. **Nothing drew a pixel, and nothing said so** -
every test passed, `omapad check` was happy, and the only symptom was a blank
screen, which is also exactly what the surface looks like switched off.
`pad-surface.md` makes the panel step 7 of nine for this reason, and a
checklist is a thing you can get to step 6 of. So the rule is a test now:
`EverySocketIsDrawn` walks every `ViewClient` in the daemon, finds the
`SurfaceSocket` that listens on it and the entry point that mounts that panel,
and fails in both directions - a socket nobody draws, and a panel waiting on a
name the daemon never binds.

`omapad check` gained the other half of the same argument: it prints what each
reading says right now, because **a source pointed at nothing and a reading
nobody asked for look identical on screen**. Both draw no tile. The only way
to tell them apart was to read the source, and this project's habit is to make
a command say it out loud.

### 52. The cell with nothing leading to it · ✅ Done · M

Asked for from the sofa: *grid editlerken herhangi bir konuma bir item
koyabilmeliyim, hiç item yokken 3x3'e bir şey koyamam mesela şuan.*

**This reverses a decision item 50 made and wrote down**, so the reversal is
worth the same care the decision got. Phase 1 said:

> **Moving is a reorder, never a coordinate.** First fit always produces a
> valid packing, so a tile can only land somewhere real, and a layout written
> as names survives a different column count, a new tile and another screen.

Every clause of that is still true. What it does not say, and what a hand on
the pad found, is that **an order cannot express an empty cell.** With one tile
on a page there is nothing to be third in - the tile is at the top left and
there is no gesture that moves it anywhere else, because every position in a
one-item order is the same position. Item 51 is exactly the page where that
matters: a page of readings drawn over a game is one whose *whole* content is
where it sits, and the top left corner is where a game puts its own.

So a tile carried in edit mode is now put in a **cell**.

- **A pin takes a tile out of the flow; everything else still flows.** The
  order is still names, and it is still what holds every tile nobody has
  moved - so a page still absorbs a tile added to the config, and a shipped
  page still packs from the top left. Only what somebody deliberately placed
  is placed.
- **That means the new gesture still does the old one's job.** Carrying a tile
  left into the middle of a row pins it there and the rest of the row closes
  up behind it, because first fit runs *after* the pins are claimed. What was
  a special case of reordering is now a consequence of two passes.
- **The cost is real and it is paid in `place`, not given up.** A layout
  written as cells does not survive a column change on its own, which was the
  whole of item 50's argument. A pin is therefore **clamped, never lost**: off
  the edge of a narrower page it is pulled back onto it, and two pins over one
  cell leave the first where it is and hand the second to the flow. The page
  is still a packing rather than a pile - which is the property item 50
  actually wanted, and clamping keeps it without keeping the order.
- **Down goes one row past the bottom, and no further.** That is what makes a
  cell below everything reachable at all - a page grows a row at a time - and
  it is what stops a held direction flinging a tile somewhere a thumb then has
  to walk all the way back from.
- **A carried tile will not walk onto a pinned one.** It would lose the cell
  in `place` and be handed back to the flow, which is a press that goes
  somewhere nobody pointed at. It refuses instead, and the motor answers an
  edge with an edge. An *unpinned* tile is walked through rather than into,
  because that one flows out of the way - the two halves of one rule.
- `omapad check --layout` prints the cells and says which would be clamped at
  the column count the page is drawn at. Clamping is silent by design, and a
  tile quietly pulled back onto the page is the kind of thing this project
  makes a command say out loud.

**What is not in this.** No free pixels and no overlap: a cell is still a cell,
a tile still occupies whole ones, and nothing may sit on top of anything. The
grid was never the thing in the way - only the order was.

**And then the corner turned out not to be the corner** - the second half of
the same report, once a tile could be put in one: *en sağ alta koyduğum item
ekranın en sağ altına gitmiyor, window'un paddingleri vs var; ek olarak gridin
en sonu sabit olmalı, px olarak değil % olarak hesaplasak tüm grid'i.*

Right, and the diagnosis in it is the fix. **A menu page has no last row.** It
is as many rows as its tiles came to and it scrolls past the fold, which is
right for a card - and it means the HUD, drawing that same page, had no cell
that meant *the bottom*. A tile carried to the corner was drawn
`cell_height` pixels per row down from the top and stopped wherever the count
ran out.

So the HUD's grid takes a fixed `[hud] rows` and **a cell there is a share of
the screen rather than a number of pixels**. Those are not two changes: a grid
cannot end where the screen ends and also be measured in pixels from the top.
`n` cells and `n - 1` gaps add back up to the whole, on both axes, which puts
the far edge of the last one exactly on the page's.

- **One number is the density and the limit together**, and there is no
  arrangement of this in which they are two: how many rows the screen is cut
  into *is* how tall a row is. Raise it for thinner tiles, finer placement and
  more presses to cross the page; lower it for fewer, bigger ones.
  `[menu] cell_height` is the same question asked of the menu's own grid, and
  is deliberately allowed a different answer - a card that scrolls does not
  have this problem.
- **`place` gained the downward clamp to match the sideways one.** It has to:
  the menu is where a page is arranged and the menu has no last row, so a tile
  can be carried further down there than this grid has. A menu page passes
  None and is unbounded; a page that is a screen passes its count.
- **The margin is the HUD's own**, not the fullscreen menu's. That one keeps a
  television's overscan clear of a card's first tile; this is a corner
  somebody deliberately put something in, so it defaults to a hair off the edge
  and 0 is the edge. The panel's `ExclusionMode.Normal` does the rest - the
  last row stops where the bars start rather than under one, which is the same
  mechanism that stopped the *first* row coming up under the game bar.
- `omapad check --layout` names both clamps and which column and row a pin
  would be pulled to.

**Found on the way, and it cost twenty minutes:** the panel kept drawing the
old geometry after the file changed. `omarchy-shell shell rescanPlugins` does
not take on a `keepLoaded` panel entry point - which `qml.md` §9 and
`pad-surface.md` both already say, in the paragraph that is easy to read as
being about *adding* a file. It is about editing one too.

**And the bottom edge had two holes in it**, reported the moment there was a
bottom to walk to: *grid'in altına taşıyınca bir itemi bir noktadan sonra
görünmeyen bir yere gidiyor.* Two separate faults with one symptom, which is
why it read as one.

**The menu had no bottom to stop at.** `carry` refused only what was more than
one row past the *packing*, so on a page that is also drawn over a screen a
tile could be carried to row 40. What it did there was worse than nothing:
`place` clamped it back onto the last row, and where something was already
pinned there it lost the cell and fell into the flow - a press that teleports
a tile to the top left.

The coupling this needed was ducked when the clamp was written, and the note
then said so: the menu is where a page is arranged, so the menu is what has to
know the page has an end. `MenuModel` takes `page_rows` now - ids to row
counts, one entry, from `[hud] page` and `[hud] rows` - and it is applied when
the page is **placed** as well as when a tile is carried, so what the menu
draws while somebody is arranging is what the screen will draw. One answer
rather than two that can disagree about where a tile ended up. A page with no
entry keeps growing a row at a time, which is every other page.

**And what was arranged did not reach the screen at all** - reported once the
first two were out of the way: *hud için menüde koyduğum yer arayüze
yansımıyor* - the place I put it in the menu is not where it is on screen when
I leave the menu. Two faults again, one behind the other, and the second was
the real one.

**The two surfaces were not holding one arrangement.** `MenuModel` takes its
own copy of what came off `layout.toml` - deliberately, so rearranging never
writes back into the config - which means `config.layout` is *the file as it
was read* and stops being true the moment anybody carries a tile. `HudModel`
was handed that same `config.layout`, so it was reading the arrangement
somebody had before they started. It takes `self.menu.layout` now, the dict
and not a copy of it, and a test says so: this is exactly the kind of thing
that regresses silently, because both objects look right in isolation.

**And nothing was telling it to pack again.** `hud.repack()` was called from
one place, `set_hud(True)`, so even sharing the dict the cells were the ones
worked out last time the readings were switched on. `hud_rearranged()` is
called from every place the menu mutates the arrangement rather than from
where it is written down - the file is written when edit mode is left, and
what somebody is looking at must not wait for that. It returns at once while
the readings are off, since `set_hud(True)` packs on the way up.

*The same arrangement is not the same packing*, and *the same file is not the
same arrangement*. Neither is obvious from either module on its own, which is
what the two tests are for.

**Found while writing those tests**, and it had been true since the surface
landed: `hud_client` was never swapped for a `FakeViewClient` in the daemon
suite. The comment two lines above the list says what that costs - *a suite
that left them in place would push test payloads at whatever is running on the
machine* - and for the whole of this item's life the suite had been doing
exactly that to the live shell's HUD.

**And the grid did not follow a tile it was carrying.** `reveal` is guarded so
it does not scroll on every arriving line - the heartbeat brings two a second
- but the guard was the selection's **id**, and the one gesture in the whole
surface that moves a tile without changing the selection is carrying one. So
the guard fired, the view stood still, and the tile walked off the bottom of
the visible grid while the button was still being pressed. The key carries the
cell now. A guard on identity where the question is position: the same shape
of mistake as an index for a tile id, one surface along.

### 53. Six sizes that are all the same size · ✅ Done · M

Asked for from the sofa: *menünün stilini toplayacağız, öncelikle spacingler
ve tipografi için silver ratio kullanacağız. sol köşede sade saat yazsın, gün
bilgisi saat altında.*

**The menu had no scale of its own.** It took Omarchy's - `caption` 10,
`bodySmall` 11, `body` 12, `subtitle` 13, `title` 14, `heading` 16 - and used
five of the six on one card, plus fifteen loose `metrics.space(N)` calls
between 2 and 40. That is a scale designed to be read at a keyboard, where a
pixel of difference *is* a difference. Across a room it is one size printed
six ways, and the card had no hierarchy at all: the clock, a tile's label and
a tile's detail line were within three pixels of each other.

So `Metrics` gained a ladder of its own, and the silver ratio sets the rung.
Nine gaps (3, 4, 6, 8, 11, 16, 23, 32, 45) and five type sizes (10, 12, 16,
24, 47), both anchored at the *small* end - the smallest thing a surface
prints is the one that must not shrink, and a ladder hung from body text has
nowhere legible to put a detail line.

**The ratio answers it twice, at two rates, and the first attempt did not.**
Space climbs by √2, the ratio less one: a gap either separates two things or
it does not, nobody reads the difference between 14 and 16 pixels of air, so
it wants few rungs far apart - and √2 doubles in exactly two of them, which
keeps the ladder landing on 4, 8, 16, 32 rather than drifting off the familiar
numbers and taking every rounding decision with it.

Type was √2 as well for about an hour, and the sofa said so at once:
*yazılar fazla büyüdü, tabler vs onlar standart kalsın.* One rung of √2 above
a 10px mark is 14, so every label, chip and slider name on the card went up
two or three pixels at once - and the reason is structural rather than a bad
anchor. **A √2 ladder cannot hold both 10 and 12, and a surface needs both:**
a detail line has to be smaller than the label over it and still legible from
the same distance, which is a 20% difference, not a 41% one.

So type climbs by the **fourth root** of the ratio, ≈1.2465, and the named
sizes are rungs 0, 1, 2, 4 and 7 - not consecutive, because the ladder is
finer than the set of jobs a surface has. The first three land on 10, 12 and
16, which is exactly where the shell's `caption`, `body` and `heading` already
were. Those three were never the problem; using five sizes within six pixels
of each other was. And four rungs is the silver ratio itself, which is what
makes it that root and not any other: `loud` is `fine` at 1 + √2, and
`metrics.silver` is there for the split a headline over its second line is.

The rest of the value is that this is a *decision*, written in one place,
rather than sixteen call sites each having had one. `metrics.rung` and
`metrics.step` make a size between the named ones say it is a step down the
same ladder instead of being arithmetic that happens to come out right.

**A surface is on one ladder or the other, never both.** `Menu.qml` is across
and says so in its header; the guide, the keyboard, the mapping screen and the
game bar are not yet.

**And what is mirrored from another surface is not on either ladder** - which
the sofa found before the argument did: *menünün sağ altındaki butonların
boyutu da büyümüş, desktop modu ile aynı olmalı.* The legend along the foot of
a fullscreen HUD sits in the game bar's own band, saying the same four words
about the same four buttons, and its badge had gone from 25 to 30 while the
bar's stayed at 25 - so opening the menu resized a row that must not move.
The whole row is `GameBar.qml`'s expressions character for character now:
badge, typed letter, hint word and both spacings. The badge's letter in
particular is sized off the *badge* (0.44 of it) rather than off any type
scale, which is a rule the bar already carries for its own reason - a three
character label has to fit the shape one letter does by being squeezed at one
shared size, not by stepping down one.

Two other numbers stayed off as well: the card's own width, and two stroke
weights.

**And then the ladder was climbed rather than rebuilt**, which is the point of
having one: *saat daha büyük olsun, spacingler artsın silver ratioya göre.*
`vast` moved off rung 6, and the card's rhythm went up a rung with it: the gap
between bands `xl` → `xxl`, the gap between tiles `xxs` → `xs`, a card's own
padding `xl` → `xxl`, and the leading inside a stacked head cell `xxs` → `sm`,
which is two rungs because what it separates is three sizes of one block rather
than two things side by side.

**It went to rung 8 first, and that was a rung too far** - *saati biraz
küçültelim çok büyümüş* - so it sits on 7. Which is the useful thing this item
learned about its own ladder: **the scale decides the steps and the screen
decides which one to stop on.** Rung 8 was tidier on paper, because it made the
top of the ladder the silver ratio twice over, and it was wrong on the wall. A
scale is what stops sizes drifting to whatever looked right that afternoon; it
was never going to say which rung a clock wants, and reaching for the tidy
answer over the legible one is the failure mode of having a system at all.

The fullscreen margin did **not** move, and for a reason worth keeping: it is
a television's overscan, a fact about the screen rather than a proportion of
the layout, so it has no business travelling with a rhythm.

**A tile's insides did not move either, and that turned out to be the wrong
call** - *şimdi menüdeki tile'lara da aynı spacing'leri uygula.* The reason
they were held back was real: a cell is `[menu] cell_height` tall whatever the
ladder does, and a switch grown a rung came to more than a cell at `[ui] scale
= 1`. But the conclusion drawn from it - leave the tiles behind - was the
wrong half of the problem to give way. **A cell shorter than its own contents
does not make them smaller.** `Column` has no clip, so they hang over the edge
of the ground the tile is drawn on, and the old 34 was already a pixel under
what a switch and its label came to; nobody had noticed because a pixel is not
a thing you see.

So the tile's insides went up a rung with everything else - the gap under a
label, the switch, the chevrons either side of a value, the slider's track,
the dial's face, the mark in a carried tile's corner - and `cell_height`'s
default went with them, to 45, which is a rung of the same ladder. **It is the
one setting whose default is derived rather than chosen**, because it is the
room the ladder needs rather than a preference about density, and the comment
beside it now says so. Type was left alone: the ask was the spacing, and the
sizes had already been settled two items ago.

**And the clock became the thing the head is for.** It was `format = "%A %H:%M"`
in a cell one row tall - the day and the time on one line at 13px, in the
corner, saying both at the strength of neither. A `[[menu.head]]` cell now
takes `under`, a second strftime format set beneath the first, and **the
cell's height decides its treatment**: two rows and the first line is set at
the top of the ladder with `under` small and in capitals beneath it, one row
and it is a line of text. So the shipped clock is `[2, 2]`, `%H:%M` over `%A`,
and turning it down is giving it fewer rows rather than a new key.

One cell holding two lines rather than two cells, because the head packs first
fit like everything else here - two cells could land side by side as easily as
stacked. `under` goes with a `format` and is refused under a `from`: a second
line under a command's answer would be a second command, with its own `ttl`
and its own failure to word. The capitals are the panel's and not the
config's - `%A` returns whatever the locale's own weekday is, and casing it is
typography.

**Two things the screen said that the code did not.** The bands of the card
were `md` apart - six pixels, against three between tiles - so the head read
as the grid's first row rather than as a band of its own; they are `xl` now,
five rungs clear of the cell gap. And the head's text carried a tile's inset
without a tile's ground behind it, which put the clock four pixels right of
the first chip and the first tile. A head cell prints on nothing, so it lines
up with the cell's own edge; only the far side is held off, far enough that a
line elides before it reaches the cell beside it.

### 54. A head cell that could say the time and not who you are · ✅ Done · M

Asked for from the sofa: *konumu kaldıralım, derece yerine ikon kullansak olur
mu, ek olarak saatin üstüne de kullanıcı adını yazabilir miyiz.*

Three asks, and the third one found the fault. Item 53 gave a head cell a
second line, `under`, and made it a strftime format - which was right for a
weekday and useless for a name. **A cell could print what a command said while
the line under it could only print a time**: two grammars wearing one name, and
the first thing anybody wanted there was the one it did not have.

So every line of a cell is the same kind of thing now. `over` above, the cell's
own line in the middle, `under` below, and each is a `format` or a `from`:

```toml
[[menu.head]]
span = [2, 3]
over = { from = "id -un", ttl = 0 }
format = "%H:%M"
under = "%A"
```

A bare string is still a format - `under = "%A"` is the whole of what a weekday
costs - and a table is the long form. It is a *simplification*: the old rule
that refused `under` beside a `from` is gone, because there is nothing left to
refuse.

- **Three lines in one cell, not three cells.** The head packs first fit, so
  nothing could promise that the cell holding the day landed under the one
  holding the time rather than beside it. Tried as three cells first, and the
  screen said so at once: a cell is a sixth of the card wide and its text is
  flush left, so an icon in its own cell sat a cell's width from the reading it
  belonged to.
- **`head_sources(cell)` is the one thing that knows a cell has three lines**,
  so the daemon asks for what has gone stale without learning the shape of a
  cell, and each line files its answer under a name derived from the cell's.
- **`ttl = 0` now means what `build_head` always said it meant.** The docstring
  read *zero asks once* and the code asked again every second, which nothing
  had noticed because nothing shipped with one. A name is exactly that case, so
  a zero-ttl line that answers is kept for the session - and the *never again*
  is written when the answer lands rather than when it is asked for, so a
  command that failed is tried again instead of leaving the cell empty until
  the daemon restarts.

**And the weather cell says less, in Omarchy's own glyph.** The place goes -
you know where you are - and so do the words `Temp` and `Wind`, the first
replaced by `omarchy-weather-icon` and the second by the arrow that was already
after it:

```
Istanbul  ·  Temp 20°C  ·  Wind ↓15km/h    →     20°C  ·  ↓15km/h
```

**`omarchy-weather-icon` is the whole reason this stays inside the rule.** A
live condition icon means knowing the condition, and `omarchy-weather-status`
never prints it - so the honest options looked like omapad querying wttr.in
itself, which is the network, the location and the cache that roadmap item 2170
refused. The helper already owns all three, and it is day/night aware on top.
Nothing was taken on; a second command was added to a string in the config.

The two run as a **pipeline** rather than one after the other, so their network
calls overlap: half a second against `list_timeout_ms`'s one, where sequentially
they came to eight tenths. `omarchy-weather-status | { i=$(omarchy-weather-icon);
sed ...; }` - both sides of a pipe start at once, which is the whole trick. What
the `sed` does is wording, which *is* omapad's business where the lookup is not,
and a failure has no place, no `Temp` and no `Wind` in it, so the sentence the
helper wrote passes straight through.

### 55. A hold some hands cannot make · ✅ Done · S

From the September 2026 console-launcher survey in
[`research/console-launcher-ux.md`](research/console-launcher-ux.md), §4.10:
*button remapping system-wide; hold-to-press → toggle alternative for
hold-confirm actions.* Everything else in that paragraph this project already
had - remapping is a screen, reduce-motion is a slider, no menu is on a timer -
and this one it did not: **every hold on the pad was a hold, at a length
written into the binding.** Two seconds of keeping a shoulder down is a gesture
some hands cannot make at all, and others make by accident.

The literal XAG answer - a press that latches the button down - does not fit
here, and finding out why is most of what this item is. Every announced hold in
the shipped tree is **half of a tap/hold pair**: `L` walks a browser tab and,
held, walks a workspace. A gesture that replaced the hold with a press has to
take the press from somewhere, and the only place to take it from is the tap.
So the answer is two numbers rather than a new gesture, and each of them
removes a different part of the difficulty:

| `[confirm]` | What it takes away |
|---|---|
| `scale` | the length. One multiplier over **every** wait on the pad - the announced pair, a binding's own `hold_ms`, the half-second a plain hold takes - bounded to 0.5–2.0, because under a half a tap and a hold stop being different gestures and over a double nobody reaches the end of one |
| `slack_ms` | the *continuity*. How long the finger may come off a hold that has **already announced itself**. Set it to `confirm_ms` and letting go after the tick stops cancelling at all: hold until the pad ticks, take the thumb off, and it still fires |

- **The scale is applied in `Binding`, not where the timers are read.** The
  game bar fills a badge over `hold_ms` and empties it over `confirm_ms`; a
  scale that reached the loop and not the payload would be a promise counting
  down over a bar that had already finished. The cost is a cache to clear -
  `apply_setting` drops `bindings` and `page_keys`.
- **The slack starts at the announcement and never before it.** Before it,
  letting go is how a tap is made, and a browser tab that waited out a slack
  nobody turned on for tabs would be the bill for a setting about something
  else.
- `hold_scale` is on the pad as `Controller ▸ Hold time`, which is the whole
  point: the person who cannot make the gesture is the last person who should
  have to find a text editor to say so.

Both ship neutral - `scale = 1.0`, `slack_ms = 0` - so the gesture is exactly
what it was until somebody says otherwise.

### 56. The first start nobody walks to a keyboard for · ✅ Done · S

The same survey, §4.10 again: *accessibility settings reachable from the
first-run flow and from the overlay.* The second half was true - motion is on
`Display`, vibration and sound on `Controller` - and the first half could not
be, because **this program had no first run at all.** It starts, it works, and
what it can do about a screen somebody reads badly or a motor somebody cannot
feel is four pages away from a person who does not yet know there is a menu.

A machine driven from a sofa is the machine nobody walks to a keyboard to set
up, so the first start has to offer what a first start decides, from the pad.
It is one tile, `Start here`, at the top of `Now`, and behind it one page: the
bindings guide, the mapping screen, vibration, sounds, motion and item 55's
hold time. Every row reads the same `pad:` setting its home row does, so this
is not a fifth place to keep them and the two cannot drift.

- **`when = ["first_run"]` is how it goes away**, which makes it the first
  state in `menu.WHEN` that nobody can point at twice. That is the rule the
  list is kept short by, and this is the one thing it is worth breaking for: a
  row true exactly once is what a first start *is*.
- **Opening the menu is what answers it**, not pressing the tile. Somebody who
  opens the menu, reads the tile and walks off has been offered the page; a
  greeting waiting to be pressed would be on the first page for ever.
- **The mark is a setting because settings.toml is the only thing the pad can
  write.** `[menu] first_run`, written false by `set_menu` rather than through
  `set_setting` - nothing to apply, nothing to repaint, and a notification
  saying a mark had been written is the machine talking about itself. Deleting
  the line brings the tile back, which the file's own header already explains.
- **It cost the suite a rule.** Opening a menu now writes a file, and
  `tests/test_kbd.py` built a real daemon without redirecting the path - so a
  test run replaced the settings this pad had chosen from the sofa. Both
  harnesses redirect it now and `test_packaging.py` fails if a third one
  forgets.

### 57. A walk that never got any faster · ✅ Done · S

[`research/console-launcher-ux.md`](research/console-launcher-ux.md) §4.2:
*analog stick + D-pad both navigate, with stick auto-repeat and **acceleration**
on hold*, and §3's tvOS note that inertia is what makes a long row navigable at
all. Ours had the repeat and not the acceleration: a held direction stepped
every `repeat_rate_ms` from the first step to the last.

The same survey asks for edge-to-edge in six presses or a jump control, and the
keyboard's first page is fourteen keys wide. **The steps closing up is that
jump control** - the distance is the same and the journey stops being a count.

`ramped(rate, ramp, ramp_time, held)` is the whole of it, and it is linear in
*speed* rather than in the gap: ramping the gap spends most of the acceleration
in the first tenth of the walk and then crawls, and what a thumb is doing is
covering distance. It reaches both places a walk is timed - `fire_repeats`,
where a held button's repeat lives, and the two stick walkers, which count down
off the tick's own `dt` - so `[menu]`, `[osk]` and `[traverse]` each carry the
pair. A reversal starts it again: somebody pushing the other way has gone too
far, not further.

2.5 over a second ships everywhere, and 1.0 is the walk exactly as it was.

### 58. A machine that shut down under a resting thumb · ✅ Done · S

§4.3: *hold A to confirm destructive or irreversible actions*. The pad had the
gesture already - an announced hold, with a tick, a notification, a filling
badge and a cancel button - and it was reachable **only from a binding**.
`System ▸ Shutdown` was one press of A, the same press as `Volume`.

So `confirm = true` on a menu row, and deliberately the same gesture rather
than a second one: the two waits are `[confirm]`'s, item 55's scale reaches
them, letting go and the cancel button both back out, and somebody who has held
a shoulder to cross a workspace over a game already knows what a filling shape
means.

- **The tile fills, not a badge.** The bar says which *button* is counting
  down; the tile is the thing being looked at, so the page says which *row* is.
  Clipped to the tile's own ground the way the badge's sweep is clipped to the
  badge's drawing, in over `hold_ms` and back out over `confirm_ms` - empty at
  the moment it runs.
- **The legend says it before anybody presses anything.** While the tile is in
  front, A's word on the foot of the card is `Hold to confirm`. A gesture you
  find out about by making it is a gesture nobody makes on purpose.
- **What earns it is what a second press does not undo**, not what sounds
  serious. Logout, Reboot, Shutdown and Close window; Lock and Suspend stay a
  press, because both are one button away from where you were.
- `build()` refuses it on a page (opening one is not a thing to be sure about),
  on a control (nothing a switch or a slider does is one-way) and beside
  `repeat` (one says *this again*, the other *this at last*).

### 59. The screen that never went dark · ✅ Done · S

§4.5's last row: *after N minutes idle, dim the chrome and show art - it
protects OLEDs and looks intentional.* This program had the opposite: item 02
bound an idle inhibitor under the keyboard, the guide, the mapping screen and
the game bar, and game mode asks the desktop for `stay-awake` outright. A menu
left open on a television held the screensaver off all night.

The launcher half of that row is not ours to build - the desktop already has a
screensaver, and this is not a shell. **The fault was only that we were holding
it off with nobody at the other end of the hold.** So the hold follows the
thumb rather than the surface: a press, a D-pad step, a stick past its dead
zone, and `[idle] awake_ms` later omapad lets go and the desktop decides. The
next press takes it back.

- **`handle_button` is the one place every button, trigger and D-pad direction
  passes through**, so that is where somebody being there is recorded. A stick
  says so only past its dead zone - a pad with drift would otherwise hold the
  screen awake for ever on its own, which is the one failure this must not
  have.
- **`awake` rides on every surface's payload** through `scaled()`, because what
  it answers is true of all of them at once, and each panel binds its inhibitor
  to `opened && awake` rather than to `opened`.
- It closes item 02's open caveat from the other side as well: what holds the
  screen awake is now pad *activity* rather than a surface being open, which is
  what that caveat asked for.

### 60. A vocabulary with no word for going back · ✅ Done · S

[`research/console-launcher-ux.md`](research/console-launcher-ux.md) §4.6:
*every focus move gets an audible tick; every confirm gets a distinct sound;
**cancels and back get a lower, softer one***. We had the first two and not the
third: `VOICES` was four words, and B either sounded like A or said nothing at
all.

`back` is the fifth, and the arithmetic in `assets/sounds.py` is the argument:
it is the **commit's own note and the commit's own interval inverted** - that
one bends up a fourth over its length, this one bends down the same fourth
from the same place - softer and shorter besides, because leaving is the
smaller event. A pair that shares a note and mirrors an interval is how a room
tells two presses apart without anybody having been taught which is which.

- **It ticks the motor, unlike `move`.** A press is a press, and the hands
  have no business finding out that something was cancelled by feeling
  nothing. What a motor cannot be is *lower*: it can be shorter or weaker,
  which says less happened, and only a falling pitch says *this went the other
  way*. So `say()` maps both of the words `rumble.VOCABULARY` does not hold
  onto its `tick`.
- **It follows the verb, never the surface going away.** `menu:back`,
  `menu:close`, `osk:close` and `osk:toggle` on the way out, `guide:close`, a
  control put back with B, and either kind of countdown backed out of. A row
  that ran and took the menu with it has an answer of its own, and two sounds
  for one press is one of them arguing with the other.
- It found one thing already wrong: `menu_untake` said `commit` for **both**
  ways off a control, so putting a slider back sounded exactly like keeping
  it. A is `commit` and B is `back` now, which is what those two words are.
- The fifth place a voice has to be named is `SoundBank.qml`, and it is the
  one no Python import would ever notice. `tests/test_sound.py` reads that
  list out of the QML now: a cue the bank does not load is a press that ticks
  the hands and says nothing to the room.

### 61. A page that was swapped where it stood · ✅ Done · S

§4.6 again: *transitions are rapid and **directional** - content moves in the
direction of the input*. Ours were rapid and had no direction at all: a
submenu, the next chip along and the next page of the guide all replaced what
was there without anything saying where it had come from.

So a page now **arrives from the side it was reached from** - in from the
right going deeper or forward, in from the left coming back - over the same
110 ms everything else on these surfaces takes.

- **The model is what knows a page changed**, so `turn_seq` / `turn_way` are
  the model's, in `press_seq`'s shape and for `press_seq`'s reason: the page
  is re-sent twice a second, and a turn already drawn must not be drawn
  again. What the panel does with it is a drawing and stays the panel's.
- **The bar had to say the direction rather than have it worked out.** It
  wraps, so the last chip to the first is a step right that looks like a jump
  left to anything comparing indexes. `group_move` leaves the way behind for
  `enter_group`; the guide's `move(step)` does the same.
- **Opening a surface is not a turn.** A surface arriving already has a way of
  arriving, and a page that also slid in from somewhere would be two
  entrances for one press.
- In the menu the offset is added to `cellX` and shared by every tile rather
  than wrapped in a container: it is only ever on its way back to zero, and a
  wrapper would be one more Item between the Flickable and every tile for the
  sake of that. In the guide it is a `Translate`, because that Row is laid out
  by a Column and an assigned `x` would fight the layout.
- It is motion like any other, so `[ui] motion = 0` lands every page where it
  belongs at once - and the countdown on a held row deliberately still does
  not come through there.

### 62. A bar that came off its own edge · ✅ Done · S

Asked for from the sofa: *alttaki bar çok altta kalmış ve sağında solunda çok
boşluk var, onu eski haline çevirelim.*

`[ui] safe_area` was a twentieth of each side and it was applied whenever game
mode was on, on the argument that game mode is when a television is being
used. The screen it was being read on was a 1920×1200 monitor, which crops
nothing: 96 pixels off each end of the bar and 60 off the bottom, for a set
that was not there. A bar standing a centimetre clear of three edges says
something about the shape of the screen, which is not what a safe area is for.

Two things were wrong and they are separate:

- **The default.** Game mode is the *couch environment*, not proof of a
  television - the README has said so since item 24 - and a couch is as often
  a desk monitor turned up loud. So it ships at **0**. A guess that costs a
  twentieth of every edge is worse than no guess: the person on a set knows
  they are on one and can write the line, and the person on a monitor has no
  way of knowing what took their margins away.
- **What the share moved.** The bar's ground was being inset bodily. The rule
  it is borrowed from says the opposite - backgrounds bleed to the edge, and
  what has to be *read* comes in - so the ground fills the window again at any
  safe share and the row of hints inside it is what moves. That is what makes
  the setting worth turning on rather than something that looks broken when
  you do.

It also caught two tests reading the developer's own `~/.config/omapad`:
`config_module.load(path)` merges settings.toml over whatever a test wrote, so
three validation tests had been passing on this machine's answers rather than
on the file they wrote - and started failing the day somebody turned the sound
on from the menu. `only()` in `test_daemon.py` is the fix, and
`test_packaging.py` now fails any test that loads a config without naming the
layers under it.

### 63. A corner nobody could argue with · ✅ Done · S

Asked for from the sofa: *radius'u OS'e göre yap ama menüden arttırılıp
azaltılabilsin, silver ratio'ya göre bir bak.*

The first half was already true and worth saying out loud: the base is
`decoration:rounding`, the compositor's own answer about every window on this
machine, and `[menu] tile_corner` only where it rounds nothing - a desktop
that rounds nothing is saying that about *windows*, and a tile is not a
window. What was missing is the second half: nothing could move it from the
pad, and it is the one measurement you can only judge by looking at the thing
it sets.

`[ui] radius` is a **multiplier** over whichever base is in force, and it is a
multiplier rather than a number precisely because the base is never ours to
choose. 1.0 is exactly what the desktop rounds; 0 is square. `Display ▸
Corners` is the same number, set from the surface it changes - the tiles round
under the thumb moving the slider, which is why `apply_setting` pushes every
open view rather than waiting out the heartbeat.

**The silver ratio is where the third part of the ask landed.** The ladder
itself was already sound - `radius.card` and `radius.tile` are one base, one
scaled and one not, with `rung()` for anything off them - so what wanted
answering was the *stepping*. A corner is a size, every size on these surfaces
climbs by √2, and 23 pixels against 25 is not a difference anybody sees from a
sofa. So the setting walks stops rather than an amount: `0, 0.5, 0.71, 1,
1.414` - four presses end to end, each a corner you can tell from the last,
and it stops one rung above the desktop's own answer: two rungs past that a
128-pixel tile is a circle, which is a different shape rather than a rounder
corner.

- `stops` in a `CHOSEN` spec is the general shape of that, and three things
  had to learn it: `set_setting` walks the list, `setting_share` draws the bar
  by its stops (spacing them by their arithmetic bunches the bottom half of a
  ladder into the first third of the track), and the trigger sweep crosses it
  in stops rather than in the value's own range.
- **No ramp on a ladder.** The ramp exists because a pointer speed is
  thirty-eight presses end to end; six is not, and a held direction would
  cross the whole thing in the first push.
- Zero is the stop *under* the bottom rung rather than a rung: no amount of
  dividing reaches it, and square is a thing somebody may want.
- **The tile is a different tile, and the design already had it.** Asked from
  the sofa with a picture: *bunu yüzdeli değil de şöyle yapsak nasıl olur. bu
  tasarım tasarım klasöründe vardı ama hiç kullanmadın.* `Console OS
  v2.dc.html`'s Haptics cell is a caption, a word at the top of the type
  ladder, and four equal segments - and it is what a stopped control wants:
  the segments say how far along without arithmetic, which frees the line
  above them to say *which* stop. `141%` is a number you have to divide
  before it means anything, and against what? So `words` name the five
  (`Square · Barely · Slight · The desktop's · Round`) and `seg`/`at` draw the
  bar. A
  continuous number keeps its percentage and its unbroken bar.
- **And then everything else shaped like it**, asked for in the same breath:
  *benzer olanlarda da bu componenti kullan.* Which turned out to be two
  questions rather than one. **Few stops** decides the segments - `motion`
  (five) and `hold_scale` (seven) joined `radius`, while a pointer speed's
  thirty-nine places and the motor's twenty-one keep the unbroken bar, because
  a control drawn in segments has to have few enough of them to count from a
  sofa. **A place rather than an amount** decides the word: `motion` is worded
  because `Off` is the stop it exists to be able to say, and `hold_scale` is
  not, because 150% of the length a binding was written at is a quantity and
  `Slower` would say less than it does.

**What it cost to find out it worked.** `rescanPlugins` does not reach a
shared component: it walks the plugin's entry points, and `Metrics.qml` is
imported by them rather than being one. So the panels went on drawing the old
ladder with nothing in the log - nothing was wrong - and the first check said
the setting did nothing. The second said it did, on the strength of two
screenshots of two *different* pages. Both are written down in
[`conventions/qml.md`](conventions/qml.md) §9 now: restart the shell for a
component, and compare the same page at both ends or do not claim a
difference.

### 64. Four verbs drawn as four squares · ✅ Done · M

Asked for from the sofa with a picture: *menüde örneğin button style için şu
component kullanılmalı, work altında tasarımı da var, bu hali anlaşılmaz duruyor.*
The picture is `Console OS v2 UI mockups`' Power cell: a heading, three verbs
one to a line, the one in front on a ground, and a line along the foot.

The shape of what was wrong is a width. Item 50 made the menu a grid because
**a list says every row is worth the same** and what is playing is not worth
the same as the row beside it - which is true, and it cut the other way for
the rows that have nothing to be worth. A verb has no value to show, so a cell
spent on one says a single word, and the two pages where that lands hardest
say it plainly: `System` draws `Lock`, `Suspend`, `Logout` and `Reboot` as four
identical squares, and `Display` draws `Scale down` as `Scale do…` and
`Screensaver` as `Screensa…`. Four cells, four words, and an elision in two of
them.

`control = "rows"` is the answer, and it is a **card that holds a page rather
than opening one**: the `items` under it are drawn inside it, and each row has
the card's whole width to be as long as it is. It is not a submenu with the
drilling taken out - a submenu is a page you go to and come back from, and its
rows get a card each. These are already in front of you.

**It was built without a `taken` and that was wrong**, which the sofa found in
one press: *a'ya basmadan yukarı aşağı seçememem lazım, altta bir kart olsa ona
gitmesi beklenir, kendi içinde bir alttaki seçeneğe değil.* Walking the rows
with the page's own up and down is cheaper and reads fine on a card with
nothing under it. Put a tile below one and **down means two different things a
cell apart**: the next row here, the next card there, and the tile a thumb was
actually reaching for two presses further on. No page can be walked that way.

So a card is entered, and `TAKEABLE` already had the shape: `entered` is
`taken` narrowed to one axis. A slider took both and answers left and right; a
card took the one that runs down it and answers up and down. A goes in, A runs
the row, B comes out of the card without coming out of the page, and the row
you were on is waiting the next time. The walk does not wrap, for the reason
the grid does not.

**And the marks settled on a spine and a pointer**, asked for with a picture:
*bu itemlarin solunda bir cizgi olsa ve aktif olana dogru bir ok olsa ici dolu
cizgi ile birlesik nasil durur?* - and then *a'ya basili degilken de aktif
olani gostersin.*

The line is structure: it is what makes a stack of words read as a list rather
than as four labels that happen to be under one another, so it is there
whether or not anybody is inside the card. Every row draws its own segment and
the spacing between rows is 0, because a single `Column` child asking for the
`Column`'s own height is a binding loop - the one that happened drew a line
down the whole card with no rows on it.

The **pointer** marked the cursor at first - drawn either way, dim outside the
card and accent in - and that lasted one pass. From the sofa: *cizgi gibi ok da
surekli cizilsin aktif secili bir item varsa, arka plana da gerek kalmayacak
boylelikle. a'ya basinca aktif olana soluk bir arka plan ver.*

Which is the jobs the right way round. The card had **one line with a mark on
it** saying where A would land, and **a ground two pixels away** saying which
row was in force: two answers to *which row matters*, drawn at the same place
in the same row. Give the persistent mark the persistent state and the
transient mark the transient one and both become readable at a glance - the
pointer is the row in force, drawn always and on a card nobody has selected,
and the ground is the cursor, faint and only once A has gone in. A card of
verbs has no pointer at all, because nothing on it is in force.

The ground's left corners are square, so it meets the spine rather than
curving away and leaving a sliver of card between the two.

Two last measurements, both `Metrics.silver` and both asked for by eye from the
sofa. **The pointer's sides**: it was near enough equilateral and read as a
squat blob on the line, because a mark whose flat edge is the line it stands on
wants that edge to be the long one - base over length is the ratio now. And
**the ends of the spine**: the line carries on past the first row and the last
one and is capped at both, every arm the stroke weight set against itself at
the same ratio. A line that began exactly at the first row's top edge began
nowhere; it read as the edge of the ground behind it rather than as a thing of
its own.

The caps turned **right** at first and that was one shape too many: two of them
facing the same way are a bracket, and a bracket *holds* what is inside it,
which is a claim about the rows. A `T` at the head and its mirror at the foot
is a stop instead - it says the line ends here and nothing about what the line
is next to.

**And then the mark on the line stopped being a drawing.** A pointer beside a
line that already changes colour at that row is the same thing said twice - one
of them a whole shape, on a card whose entire argument is that a row has
nothing to show but its name.

What replaced it first was **weight**: the lit length a hairline wider. That
was the wrong silhouette and the sofa found the second half of it before the
first - *bence 1px daha artsin ortali durmuyor*, because growing on one side
alone moves the line off its own centre. Centred it was honest and still wrong,
for a reason the fix makes plain: a line that changes *weight* for one row
reads as the line, not as the row. Something **leaving** the line reads as the
row.

So the mark leaves the line at that row, reaching as far sideways as the caps
reach along - one distance on the card rather than two that are nearly the
same - and centred on the row so it marks the row rather than a place in it.

It was a flat **stub** first, and a stub is a line crossing a line: two strokes
of the same weight meeting at a right angle, which is what the caps at the ends
of the spine already are. It is a **wedge** now, wider where it leaves and
flat at the line's own weight where it arrives. A taper is not a second cap: it
says the mark comes *out of* the line rather than across it, and keeping the
tip flat keeps what it reaches a measurement rather than a point. The rise
where it leaves is the reach at `Metrics.silver`, which is the proportion a
mark whose flat edge is the line it stands on wants.

Which is a triangle again, four marks later - but computed from the spine's own
numbers rather than drawn, so it follows the line at any scale. The drawing was
never the part that was wrong.

`rows:point` left `assets/shapes/` on the way. Three drawn marks were tried
here and none survived - a tick at the far end of the row, a radio ring at the
head of it, and the pointer - which is worth writing down next to the rule
about never hand-drawing a badge: that rule is about *what* a drawing is made
of, and says nothing about whether a drawing was the right answer at all.

And the `T` found the ratio in the wrong place, spotted by eye and confirmed
with a pixel scan: *solu ve sagi uzun gibi, silver ratio olduguna emin misin.*
It was, and on one **arm** - which is half a crossbar, so doubling it for the
cross left the cap 12 across against 5 along. The quantity is spent once now:
the line carries on past the rows by the stroke at silver, and the cap is as
wide as that, half either side.

**Two overlaps, and both are the same fault.** A corner's two bars start from
one origin if you write them the obvious way, and the cursor's ground fills the
row from its left edge, which is where the spine is. Every ink here is the
theme's own at a share of itself, so a thing painted twice is a thing painted
darker: the pixel where the corner's bars crossed was the brightest on the
card, and the spine changed colour for the length of whichever row the cursor
was on. Neither was a drawing decision - both were two things asked to occupy
one place. The horizontal bar takes the outermost weight and the vertical
starts under it; the ground starts where the spine ends, and so do the sweep
and the press ring.

- **The drawing had to say it twice.** A card nobody is inside draws **no
  cursor** - a cursor would promise a walk that press does not make. And an
  entered card is not *lifted*: filling with the accent and cutting its corners
  is what a tile out of the page's order does, and it made the card the loudest
  thing on the page with the least readable rows on it.

  It takes a **heavier ring** instead - and that found a real fault two moves
  later. Four pixels cut the border (*a'ya basinca border kesiliyor*): the halo
  sat `ring + its own half` outside the tile, in the gap between cells, so at
  four it went past the gap and the grid clipped it on the leftmost tile of a
  page. **The sum was wrong rather than the ring.** The ring is drawn *inward*,
  straddling a path inset by half its weight, so it occupies the first `weight`
  pixels inside the tile and the halo has only the box to clear - a one-pixel
  error while every ring was a hairline, and a four-pixel one the moment one
  was not. `halo.out` is a hairline clear of the tile now and a ring may be any
  weight without moving it.

  Taking the ring away instead was the wrong repair, and it said so at once
  (*kartin secildigi anlasilmiyor*): the rail says which **row**, and a
  two-pixel mark on one row is no answer at all to which **card**.

**And then the two marks on a row, which took three passes.** Asked for from
the sofa twice: *yandaki tik bir sey anlatmiyor ve fontlar cok soluk*, and then
*soldaki tick de kotu sadece arka plan olsun, a'ya basinca solda 2px genislikli
bir cizgi olsun aktif olani gosteren.* Both were right and the second one is
the better design.

- **A tick at the far end of the row** was the grid's own mark, and out there
  it says nothing: a tick has no second state, so a reader sees one row
  carrying something and three carrying a gap, at the opposite end of the card
  from the words it is about.
- **A radio ring at the head of each row** was the design's, and it says more -
  an empty ring beside every row says *these are alternatives* before it says
  which one. But it is a second drawing for something the row can simply
  **be**, and it took the slot a row's own glyph wants.
- **The ground says it now**, and the cursor is **two pixels of rule** down the
  row's left edge, drawn only inside the card. One mark each, and the card's
  own ring and ground go back to meaning the card is selected rather than
  saying the same sentence twice at two sizes.

**The inks were the other half of it, and they were a real fault.** The surface
had picked a number at each call site - 0.36, 0.42, 0.52, 0.58 - and the design
publishes exactly three levels, each *measured* at 4.5:1 or better on the
ground it sits on. A second line at 0.36 is a sentence you have to walk onto in
order to read, which is a line not doing the job it exists for. `inkMuted` and
`inkDim` are those two levels named once, and the call sites take them.

- **The row cursor is a second cursor, not a second kind of `selected`.**
  Everything the page does to a tile - carry it, hide it, resize it, scroll to
  it, ring it - is still done to the tile; only a press reaches further in.
  `acting` is that one question, and it is what makes `confirm`, `stay` and
  `repeat` the row's answers. The legend asks it too, so `A` reads `Hold to
  confirm` over `Full shutdown` and `Pick` over `Rest mode` beside it, and the
  hold fills the row rather than the card.
- **What a row may be is a short list, and the parser holds it**: a verb, with
  no page under it, no control on it, and no `from` listing to fill it. Each
  of those is a tile that could never draw itself, and `omapad check` is where
  that gets said. A card spends no X or Y either - a key is spent while a page
  is in front, and nothing is ever in front of a card of rows.
- **Found on the way**, and it took the daemon down twice a second rather
  than quietly: `view_state` asked the daemon what every tile with a `control`
  was *on*, and the daemon's answer starts by unpacking the pair a tile reads
  from. A card of rows is a control that reads nothing. The condition is
  whether a tile **reads** something, not whether it is a control, and it has
  a test now.

**And then the first page that asked for one**, from the sofa: *system altında
game mode kartı var ve bu kartta yeni yaptığımız tasarımı kullanmak
istiyorum.* `System › Start in` was a `choice` - a card reading `Game mode`
with a chevron either side, which is a card you have to press to find out what
else there is. It is a card of two rows now, and converting it settled the one
thing the control was still missing.

**A row carries its own line.** Item 50 named the price of a choice tile: it
shows one value, so *the sentence saying how the choices differ has nowhere to
go*, and `Button labels` and `Profile` kept their submenus for exactly that. A
row is as wide as the card it sits in, so it has somewhere to put one - which
makes a card of rows the third shape, and the only one that pays nothing. The
three answer three questions now: a **submenu** is for choices that are a place
of their own, a **choice** for two values whose names are the whole difference
in one cell, and a **card of rows** for a short list you want to *read* rather
than press.

- **Three cells, not two.** Forty characters do not fit in two beside a tick,
  and `pad-menu.md` says so where somebody would write the next one.
- **A row that sets something ticks**, by the same `state(action)` a tile is
  asked, so a card of them is a list of choices rather than a list of guesses -
  and `stay` is what keeps the menu up while the tick moves.
- `Button labels` and `Profile` are the two this now unblocks, and they are
  deliberately not converted here: that is a face-button question and it gets
  its own pass.

`README.md` and `pad-menu.md` carry the worked example both ways round - the
verbs, and the settings. The test for *when* to reach for one is the elision: a
run of tiles whose labels do not fit a cell and none of which has a value to
show is a card of rows.

**Then the rest of the tree, from a list the sofa picked off.** Four pages
converted, and each was a different argument for the same shape:

- **`Windows`** was four cells reading `Fullscre…`, `Next win…`, `Float / …`
  and `Close wi…` - four words cut in half on a page two thirds empty. The
  whole group is one card now.
- **`Controller › Button labels`** and **`Profile`** were submenus, and item
  50 said why they had to stay ones: a `choice` tile shows one value, so the
  sentence saying how the choices differ had nowhere to go, and getting either
  wrong scrambles the face buttons. A row is as wide as the card, so it keeps
  the sentence - and all of them are in front of you rather than a level down.
- **`System`** was five power verbs as five squares, which is the scatter the
  control exists to end. `Omarchy menu` stayed a tile: it is a door out of this
  menu rather than something the machine does.

**And the three under Power stopped being a hold**, asked for from the sofa:
*basili tutmasin 10 9 8 diye geri sayim yapsin b ile cancel edilebilsin.*
Which is right, and it splits one question into two.

A **hold** is the right gesture where it is already in the hand and is over in
a second - `Close window`, with the window in front of you, wanting an answer
now. It is the wrong one for logging out. What those three do is take the
screen away, and being sure about that is not something to do with a thumb: it
is something to be given long enough to change your mind about. Holding A for
ten seconds is not a gesture anybody makes.

So `countdown` is a second answer rather than a replacement. A is an ordinary
press, the row prints `[menu] countdown` seconds beside its name, and B stops
it - the legend says `Cancel` while it runs. Three things it does not do: no
tick per second (a pad buzzing ten times through a decision is the opposite of
what the wait is for), no `[confirm] scale` (that is for a hand that cannot
keep a button down, and this asks nobody to keep anything down), and no
stopping on a cursor move - ten seconds is long enough to want to look at
something else, and a count that died because a thumb brushed a stick would be
worse than no count at all.

**Reboot and Shutdown are written twice, and that is the point**, asked for
from the sofa: *reboot ve shutdown bu grup disinda ayri 1x1 tile olarak da
dursun.* They are rows in the card like the other three, and they are also the
two anybody walks to that page for - so they are a cell each as well, where a
thumb reaches them without going into a card first. Item 48's argument about a
row you have to go and find, spent on the two rows it is true of.

Two things that had to follow. **Both copies count down** - a press guarded in
one place and cheap in the other is worse than not guarding it - which meant
the number had to be drawable on a *tile* as well as on a row, in the corner
the tick and the chevron share. And **each copy needs its own id**: the flash,
the countdown and the fill all name a tile by id, and two things answering to
one name is two things lighting up for one press.

**And a card can list**, which the first pass refused. `Audio` was `Devices`
opening on `Output` opening on the outputs: two presses in before a name you
could pick, and each of those pages held exactly one thing. It is two cards on
one page now. The refusal had a real reason - a listing is read at the press
that enters the page it fills, and nobody enters a card - and the answer was a
second lifetime rather than a special case: `menu_cards_settled` reads the
listing cards on the page in front once the page stops changing, on the bar's
own `group_settle_ms` and for the bar's own reason. A card is seeded with its
`empty` words so it is never blank while the command runs.

**And a listing that finds one thing is not a list**, said from the sofa the
moment it was on screen: *tek secenek varsa boyle gorunmesin, output ve
microphone kotu gorunuyor, kullanici da secim yapamaz zaten.* One pair of
speakers in the room is one row - picking it sets what is already set - and a
column of alternatives with a single alternative in it is a card of furniture
round a fact. It is a **reading** then, and drawn as one: the heading names it,
the line is the answer, and `takeable()` refuses the card, which is the
`readout` tile's own argument one control along. Plug a television in and the
second row makes it a list again. Only a card that *lists*: a card somebody
wrote one row into meant that row.

**Found on the way**, and both were the same shape of fault - a field asked of
the wrong thing:

- `_row_state` did not carry a **listed** row's own `on`, so the card of
  outputs drew every device unfilled. A listed row knows its own answer; the
  daemon can ask a setting what it holds but not a device whether the sound is
  going to it, and the tile payload had said so for a year.
- `choose()` moved the fill among the page's tiles and not among a card's
  rows, and then among *every* card's rows when it was taught to - picking a
  speaker said something about which microphone was in use.

**And one that cost an afternoon of drawing**: a `readonly property int left`
on the row delegate. `Item` has a FINAL `left`, so the whole component failed
to compile - and the way that fails is the panel never coming up at all, with
one line about it in `qs -p /usr/share/omarchy/shell log` and nothing anywhere
else. The rule in `qml.md` about reading that log first is what found it.

### 65. One line, and three drawings of it · ✅ Done · S

Said from the sofa, reading item 64's card back: *button labels için yaptığımız
tasarım aslında dikey slider gibi, mevcut kademeli slider ve slider'ı da benzer
bir tasarıma geçirebilir miyiz.* It is the right reading of the drawing. A card
of rows is a two-pixel line with the row in force lit along its own length and
a wedge leaving it - which is a vertical slider, and the card next to it drew
its actual slider as a rounded eight-pixel trough with a fill running along it.

So there were three drawings of *where along something a number is*: the
trough, the trough cut into segments for a stepped value (63), and the spine.
There is one now. `shell-plugin/Travel.qml` is the line, drawn along the foot
of a slider, a stepped slider and a reading in the menu, and under a reading on
the HUD - which had its own copy of the trough, for the rule that a page of
readings must read the same in both places it appears.

- **The measurements moved to the ladder.** `metrics.spine` holds the five -
  the weight, how far the line carries past what it measures, the cross's reach
  either side, and the mark's reach out of the line and its base on it - and
  both the row card and the travel read them from there. Two copies of a stroke
  weight is how one drawing quietly becomes two.
- **Nothing fills**, which was the question asked back with three pictures and
  answered by picking the quietest: a bar filled to the value draws a number as
  mass, and the figure at the top of the card has already said it in words.
  What is drawn is where the value *is* - the line's own length there, in the
  accent, with the wedge over it. A stop is a length of line, so standing on
  one lights the whole of it; a continuous value lights the mark's own base.
- **It reverses half of 63.** The segments were chosen so *how far along* could
  be read without arithmetic; it is read off the mark's place between the
  crosses now, which is quieter. The trade was made with the picture in front
  of us and it buys one drawing where there were three. `seg` and `at` on the
  payload are untouched - how a value is drawn was always the panel's.
- **The stops are the cap repeated.** A cross at the end of a line says the
  line ends here; a cross partway along says it about a place the value may
  stand. The two controls then differ by exactly what the two controls differ
  by, and the ends of the line are values - a slider at its minimum stands on
  the cross, where a spine would have carried on past the last row.
- **`metrics.time.fill` went with the troughs**, and `qml.md` is down to three
  durations. A mark is where the value is rather than a length growing towards
  it, so it lands on the frame the value changes - which is 8.2.4.1, the rule
  the filling bar was the exception to.

**The crossings were wrong on the first pass**, and the sofa said so at a
glance: *dikey ve yatay çizgiler iç içe geçmiş görünüyor.* Each cross was one
bar run through the line, so the pixel where the two met was painted twice -
and every ink here is the theme's own at a share of itself, which makes a
square painted twice a square painted brighter. Seven of those along a stepped
control and the drawing reads as two strokes laid over one another. It is the
rule the row card's caps have carried since they were drawn; the travel now
carries it too, with the line taking the crossing and the arms starting above
and below it.

**And the plain line did not show a press**, said as soon as the crossings
were fixed: *kullanıcı düz çizgi olan versiyonda değişimi görebilmeli.* True,
and it is the cost of the quietest of the three treatments - a press moves the
mark a few pixels, and on a continuous slider there was nothing else on the
line to see move. The stepped one never had the problem: a whole stop lights.

So the line **behind** the value is drawn in the accent at half. It is the old
bar's length at one twentieth of its ink - a tint rather than a fill, which is
what qml.md 8.1 asks for everywhere the accent is not carrying a solid - and
the full accent still marks one place. Three strengths were rendered side by
side to pick it: a fifth (this surface's tint for a lit ground) is not there at
all on a two-pixel line, and the ink at its dim level makes the trail the
brightest thing on the card, which puts the eye behind the value instead of on
it.

What that buys back is item 63's own argument, which the first pass had spent:
the segments were chosen so *how far along* could be read without arithmetic,
and a trail running to the stop you are on reads exactly that - on both kinds
of slider and on a reading, in one drawing.

**And then the lit line crossed them too**, which is the same fault one layer
up: *düz sliderda aktif olan sol yatay çizgi ile dikey çizgi yine iç içe
geçti.* Splitting each cross into two arms had fixed the ink and not the
figure - whatever the value lights runs through every stop it has passed, so a
blue line and a grey bar still read as two strokes laid over one another. The
stops **hang under the line** now, one tick each, as long as the spine carries
past the last row of the card next door. Nothing on the drawing overlaps
anything: wedge above, ticks below, and one unbroken line between them.

**And the mark stopped being a wedge**, which is the third thing the screen
said and the clearest of them: *yatay sliderlarda ok gibi olmasın, kalın çizgi
gibi olsun, sol ve sağındaki üçgenleri kaldır.* The wedge is the row card's own
mark, and turned a quarter it is an arrow lying on the line - an arrow points
somewhere, and beside a horizontal line there is nothing to point at. The mark
is the line **thickened** now: as tall as the wedge reached, half again as long
as that, its foot on the line. At the wedge's own width it was as wide as it
was tall, and a square standing on a line is a knob rather than a length of it.

**And the two drawings settled on one stroke**, which is where the passes
above were heading: *yatay ve dikey için tüm çizgileri aynı yapalım, --+-- gibi
olsun, üstte ve altta aynı; kalınlık bardaki en sol ve en sağdaki çizginin
kalınlığı olsun; dikeyde en üstte ve en altta bir boşluk var sonrasında
başlıyor, yatayda da bunu ekle.* So:

- **One figure, three jobs.** The cap at each end of a line, a stop a stepped
  value may stand on, and the place the value has got to are the same cross at
  the same size - `metrics.spine.cross`, the arm stepped a rung and halved -
  with equal reach either side. The row card's caps took it too: the `T` with
  a quantity of its own is gone, and `reach` with it.
- **The value's mark is that cross in the accent**, which is the end of the
  wedge here. A wedge points at something, which is right beside a row and
  wrong along the foot of a card; the thickened line that replaced it for a
  pass was a block sitting on a stroke.
- **The line runs on past the travel at both ends**, so a slider at its
  minimum stands an arm inside the cross that ends its line - the run of bare
  line a spine already had above its first row and below its last.
- **And nothing is painted twice.** The dim strokes are two arms with the line
  taking the crossing; the accent one is a single piece, because an opaque
  colour covers the line rather than tinting it. That is what the two earlier
  passes were reaching for by splitting the cross and then by hanging it under
  the line.

**The stepped one then wanted its run solid**, which is the last thing the
screen said: *yatay parçalı olanın solundaki hafif soluk turuncu da düz turuncu
olsun, en sağda ortadaki turuncu bar da aktif olduğu alanın en sağında
görünsün.* Both halves are the same correction. A stop is a place the value has
**stood on**, so the stops behind the mark are places it has been and the run
over them is as solid as the mark itself - the tint is for a continuous value,
which has been at every point behind it and stood at none. And the mark belongs
at the **far edge** of the stop it is on rather than the middle: a stop is a
length the value has reached the end of. It stands on that stop's own stroke,
so the accent covers it instead of landing half a weight beside it.

Checked by rendering `Travel.qml` on its own against a fake ladder - at both
kinds and at 0, mid and full - and then headless through `grabToImage`, which
is the cheaper loop: it costs no shell restart and no screen, so the crossings
were compared at four times life size and the three trail strengths on one
sheet, instead of squinted at.

### 66. A hum that said nothing about the value under it · ✅ Done · S

Asked for in the same sitting as the line above it, and it is the same ask one
sense along: *yatay çizgiyi hareket ettirirken A'ya basmadan önceki hâline göre
ne kadar soldan sağa giderse sağda titreşim artsın, yukarı aşağıda da sabit,
solda titreşim artsın veya azalsın - tabi bunları yaparken mevcut titreşimin
strengthine göre yapsın.*

The `texture` said *it is moving*, which is the least interesting thing about a
value being changed: the thumb already knows it is moving, because it is the
thing doing it. What it says now is **which way, and how far from where it
stood** - the same sentence the line on screen says, told to the hand.

- **Two motors, which is why it stopped being a sine.** A pad wires its
  low-frequency motor on the left and its high-frequency one on the right, so a
  value pushed right is felt on the right - and a periodic effect carries one
  magnitude, which cannot say a direction. `texture` is plain `FF_RUMBLE` now.
  It loses a waveform a pad might not have, so it also stops being the one word
  some pads simply cannot say.
- **The mark is where A found the value.** `_menu_from` is set by `menu_take()`
  - the same point B puts the value back to - and the level is the distance
  from it. Push back to the mark and the motor goes quiet; a pause in the
  middle of pushing is not letting go of the mark, because A has not been let
  go of. A control moved with no mode at all - a trigger sweeps one without
  taking it - marks where the push began and lets that go when it settles.
- **Up and down were already still**, which is the third clause of the ask and
  cost nothing: a taken control answers one axis because a range is one
  dimension, so there was nothing to keep the motor from following.
- **The strength is the one already chosen.** The floor is `texture_strength`,
  so the first step away is felt at all; the ceiling is the **tick's** own
  `strong` - the `Strength` tile on the Controller page - so a value pushed the
  whole way is exactly as strong as a press, and turning the vibration down
  turns this down with it. No new setting: both ends were numbers somebody had
  already set.
- **`aim()` re-uploads the effect in place.** `EVIOCSFF` with an effect's own
  id replaces what the slot holds, and a running effect picks the new level up
  without a gap. One round trip per step is the thing `rumble.py` otherwise
  refuses - allowed because it *is* the press's own work rather than something
  happening underneath one - and it is skipped where the magnitudes have not
  changed, which is most steps of a held repeat.
- **And it ships on**, where it shipped off. Roadmap 17's rule is that a scheme
  where every press buzzes says nothing; a buzz that says *which way you just
  pushed* is not that scheme.

**The scale came back out a day later**, from the same chair: *titreşimleri de
artan azalan değil sabit bir hâle getirelim, hamlenin yapıldığı yönde titreşim
verebilirsek daha iyi olur geri bildirim için; dikeyde dpad olduğu için sola
titreşim versek daha iyi.* Right on all three counts. A level that rose with
the distance from where a push began is a second reading of the number the
tile is already printing, and what a hand on a control is asking is whether
the push landed - so it is one flat level, `texture_strength`, re-derived at
0.25 because a level that used to climb to a ceiling could afford to start
low. The side is the whole message: `aim(name, side)` takes "left", "right" or
"both". And **up and down are the left motor**, both of them, because a list
is walked with the D-pad and the D-pad is under that thumb - which is also the
first time the vertical instrument is felt at all, on the same
`MENU_SCRUB_HOLD` a scrubbed slider uses. `_menu_from` and `menu_share()` went
with the scale.

### 67. The instrument, read off a Braun meter · 🗑 Removed · M

Five passes had gone into the line at the foot of a slider, and the sixth ask
was the honest one: *bu barlar bir türlü olmadı, yatayda ve dikeyde Dieter
Rams'in oluşturduğu barlardan ilham alarak bir şeyler dener misin* - and then,
when sketches came back without a source: *örnek görseller lazım yoksa olmaz.*

So the reference came first: a Braun **T1000**'s tuning meter, photographed
close (Wikimedia Commons). Four things are in it, and the fourth is what every
pass here had been missing.

- A **rule** with its **ticks hanging under it**, never across it.
- The ticks all **one weight**, told apart by **length**: the ends of the
  scale and the places that matter are long, a printed division is half.
- A **needle** at the value, crossing the whole instrument.
- And the only solid colour on it sits in a **channel of its own, under the
  ticks**.

That last one is the answer to three passes of the same fault. The marks and
the filled run were being drawn on **one line**, so a lit run always crossed a
dim mark: splitting each mark into two arms fixed the doubled ink and not the
figure, hanging the marks under the line moved the crossing rather than ending
it, and a cross in the accent only hid it. The registers are what make the
drawing hold: **the fill is not on the scale.**

`Travel.qml` is that instrument now - scale, channel, needle - and the row
card's spine is the same instrument turned. `metrics.spine` carries its five
measurements: the stroke `weight`, the `arm` a rule runs past what it
measures, a major `tick` (the arm a rung up, because an arm reads as a corner
and a mark has to be found from a sofa), a `minor` at half of that, the
`gutter` between the registers, and the `lead` the needle stands above the
rule.

A stepped value's places are the tick **ends** rather than the segments
between them - five stops are five ticks and four divisions - and a continuous
one prints tenths, which is a division somebody can count and the same on
every tile.

**And it was taken back out**, the same evening, from the same chair: *kötü
oldu, eski hâline geri alabilir misin ondan ilerleyelim.* Built, looked at,
dropped - so the surfaces are back on the single line of item 65, with its
crosses at the ends and at the stops, its solid run on a stepped control and
its tint on a continuous one, and the row card back on its spine and wedge.

What the item measured is worth keeping, because it is the only thing here
that was read off an instrument rather than argued into being:

- **Two registers is a real answer to a real fault.** Five passes of one-line
  drawing had the marks and the fill on the same stroke, and every one of them
  read as two strokes laid over one another. Braun's meter does not have that
  problem because the fill is not on the scale.
- **A scale can be printed on a control that has no places.** Tenths under a
  continuous slider are honest - a printed division rather than a claim about
  how the value moves - and nothing before this had tried it.
- **And it is too much furniture for a tile.** Three registers plus a needle
  is an instrument panel's worth of drawing at the foot of a cell that is
  mostly a word and a number, which is what the sofa said in three words.

`metrics.spine` kept `cross`, `markOut` and `markBase`; `tick`, `minor`,
`gutter` and `lead` went out with the drawing. The rumble work that landed in
the same sitting (66) is **not** part of this and stayed.

## Suggested order

Done: **01–09**, **11**, **13–66**. The button scheme (07) settled first because it
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
