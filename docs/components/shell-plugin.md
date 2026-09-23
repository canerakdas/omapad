# Shell plugin - `shell-plugin/`

An Omarchy shell plugin (Quickshell, QML) that draws six surfaces and one bar
widget. What is symlinked into
`~/.config/omarchy/plugins/canerakdas.omapad` is the **checkout root**, not
this folder - `manifest.json` lives at the root so `omarchy plugin add` installs
the daemon with it - so this checkout is the live source.

Write it by [`../conventions/qml.md`](../conventions/qml.md); this document is
what is in it.

## Entry points - `../manifest.json`

Paths are relative to the manifest, which is one level up, so each carries the
`shell-plugin/` prefix.

| Kind | File | What |
|---|---|---|
| `panel` | `shell-plugin/Surfaces.qml` | every summonable surface |
| `bar-widget` | `PadStatus.qml` | "is the pad mine?" in the Omarchy bar |

`keepLoaded: true`, so the panels are alive to receive a socket line before
anybody asks for them.

## `Surfaces.qml`

A plugin gets one panel entry point and omapad draws six independent
surfaces, so they are mounted here - one hot-reloading plugin directory
instead of six.

The shell's summon/hide/toggle contract lands on `open()`, `close()` and
`opened`, so `omarchy-shell shell summon canerakdas.omapad` and an
Omarchy keybind reach the same surfaces the pad does. **Neither function opens
a panel itself**: it shells out to `omapad ctl <verb> open`, exactly the way
a terminal would, and the answer comes back over the surface's socket.
Flipping `opened` here would draw a surface the daemon does not know it is
showing, and its next heartbeat would take it away again.

`summonable` maps a payload name to a surface; `surfaceNames` accepts both the
control verb and the obvious word for it (`keyboard` → `osk`). A summon with
no payload means the menu - the door the pad's own button opens. The game bar
is deliberately not summonable: it follows game mode, and
`omapad ctl mode` is its door.
`Ripple.qml` is not summonable either, and has no `opened`: it answers a click
rather than a button. Neither is `Sound.qml`, which goes one further and has
no window at all - there is no such thing as a cue being on screen.

## The surfaces

| File | Component |
|---|---|
| `Keyboard.qml` | [`osk.md`](osk.md) |
| `Menu.qml` | [`menu.md`](menu.md) |
| `QuickMenu.qml` | [`quick.md`](quick.md) |
| `Guide.qml` | [`guide.md`](guide.md) |
| `Mapping.qml` | [`mapping.md`](mapping.md) |
| `GameBar.qml` | [`gamebar.md`](gamebar.md) |
| `Hud.qml` | [`hud.md`](hud.md) |
| `Ripple.qml` | [`ripple.md`](ripple.md) |
| `Sound.qml`, `SoundBank.qml` | [`sound.md`](sound.md) |
| `PadStatus.qml` | [`status.md`](status.md) |

**One import in this plugin is quarantined**, and it is the only one:
`SoundBank.qml` exists so that `import QtMultimedia` has a file of its own to
fail in. Quickshell does not depend on qt6-multimedia, an unresolvable QML
import takes its whole file down, and `Sound.qml` therefore reaches the bank
through a `Loader` rather than importing it. Any future import of something
outside Quickshell's own dependencies gets the same treatment for the same
reason: a plugin is installed on machines nobody here has seen, and one
missing optional package must cost one feature rather than the keyboard.

## Shared pieces

- **`SurfaceSocket.qml`** - the listening half of a surface: the
  `SocketServer` on `root.socketDir + "/<name>.sock"`, its newline
  `SplitParser`, and the retry that makes the start order stop mattering. The
  directory belongs to the daemon and the shell is up before it, so the first
  bind fails - and Quickshell answers that by dropping `active` to false and
  never trying again, which leaves every surface here dead for the session
  with one warning in a log nobody reads. It is the bug a fresh boot has and a
  `rescanPlugins` hides, because by the second bind the daemon has long since
  made the directory. The retry doubles from 250 ms to a minute, so a machine
  where omapad is not running does not fill the shell's log either. Use this,
  never a bare `SocketServer`.
- **`Ink.qml`** - which of the theme's two inks reads on a given ground.
  `Color.menu.selectedText` looks like the ink for anything filled with the
  accent and is not: Omarchy defaults that key to the **accent itself**, so a
  solid accent fill labelled with it would be a label that is not there. Every
  other state on these surfaces tints rather than fills and keeps the theme's
  own text colour; the bar's current nav card is the one place that dodge runs
  out. So it is measured - WCAG relative luminance - and only ever one of
  `menu.background` and `menu.text`, the two colours every theme is guaranteed
  to define. A third would be a console's own palette arriving through the
  back door.
- **`Travel.qml`** - where along something a number is, drawn as a line: a
  slider being pushed, a slider with places to stand rather than a distance to
  cover, and a reading the machine keeps answering. One file because it is one
  question, and because a page of readings has to read the same in the menu and
  on the HUD. It is the row card's spine turned on its side, down to the
  stroke: **one figure crosses the line and it is the only mark either drawing
  has** - the cap at each end, a stop a stepped value may stand on, and the
  place the value has got to, which is that same cross in the accent. Nothing
  fills; what the value has covered is the line behind it - solid where it has
  stops, a tint at half where it has none - because a mark that moves a few
  pixels is not a press anybody sees from a sofa and a length changing is. The
  line runs on past the travel at both ends, as the spine runs past the first
  row and the last. The caller hands it `ladder` (the surface's `Metrics`), the
  value, the stops and the three colours; it decides nothing.
- **`Knob.qml`** - the same question drawn as a ring, for the one control a
  thumb can copy rather than translate. It keeps the travel's whole argument -
  nothing fills, the run behind the value says how far it has come, solid
  where the value has stops and a tint where it has none - and parts company
  with it four times, each time because a circle is not a line: **a ring
  needs no caps**, since the quarter left open at the bottom is where the
  scale starts and stops; **the value's mark is a pointer**, because a ring
  has a middle and that is what a knob has always answered *where is it* with;
  **a stop is a notch hung just outside the scale**, the same claim the
  travel makes with a cross; and **nothing is drawn where the value started**,
  because a second pointer out of that same middle is a clock rather than a
  value and its ghost - so the ring takes no `ghost` and reads no `b`, and
  what the turn has done is the run lengthening behind the pointer. The rim is the gauge's own `dial-face.svg` - a
  page holding a knob, a dial and a clock holds one circle drawn three times -
  and so are the two figures it turns, the pointer and the notch under a stop.
  What is not generated is the scale: the run of it the value has covered
  grows with the number, and a track drawn once with that run computed against
  it would be two drawings of one ring. How many notches there are is the
  panel's too. The caller hands it `art` (the surface's `ControlArt`), the
  value, the stops and three colours.
- **`Clock.qml`** - the time with hands on it, and the stopwatch that shares
  its face, for the two surfaces that draw a clock tile. One file for `Travel.qml`'s reason: the menu is where the tile
  is put on the page and the HUD is where it is looked at, and a face that
  differed between them would be the arrangement saying something it does not
  mean. Every figure on it comes out of `ControlArt.qml` - the rim, the twelve
  marks, the hub, both hands, the sweep and the register's ring and hand - and
  the time only turns them: a hand is drawn standing at twelve, pinned where
  the hub is, and the panel gives it the whole face to fill and a rotation.
  What is left as geometry is where the register sits and how big it is. **A clock has no second hand**:
  the page arrives every `VIEW_HEARTBEAT` seconds, so one would be visibly
  wrong most of the time on a surface whose whole argument is that nothing on
  it twitches. The caller hands it `art` (the surface's `ControlArt`), the
  minute of the day and three colours; every measurement in it is a share of
  the face, which is why none of them is on the ladder.

  **A chronograph is the same file with `elapsed` handed in**, and it is the
  one drawing on these surfaces that animates itself: the daemon sends how
  long it had measured and whether it is still going - **on the surface rather
  than on the tile**, or `fresh()` would rebuild the page twice a second to
  move one hand (qml.md 5.4) - and this stamps `Date.now()` when that lands
  and counts on from there, re-syncing on every push. Not a
  `Timer` polling for state - the state arrived on the socket; what turns here
  is a hand on a measurement it already holds - and it sleeps while the
  surface is down. The face is the Seiko 6139's in line: one register, the
  thirty minutes measured at six, large and low as the 6139's is, with a hand
  in the accent. `ShapesSitOnTheGrid` holds the dial's furniture to nothing,
  because nothing snaps the square a clock is drawn in - the running seconds and the hours the panda dial had
  went, and the figures beside the name say the hours. The figures
  beside the tile's name are spelled here too, which nothing else on these
  surfaces does: a number that changes ten times a second cannot come off a
  wire written twice a second.
- **`Metrics.qml`** - the shell's measurements at omapad's own scale. Every
  surface here is read from twice the distance an Omarchy menu is, and the
  shell has one scale for the whole session, so this multiplies it per surface
  from the number the daemon stamps on every payload (`[ui] scale`,
  `game_scale`). A multiplier rather than a replacement, so a roomy theme
  stays roomy. `Style.gapsOut` is **not** scaled: it is the compositor's own
  geometry, and a surface that kept a different gap from the windows beside it
  just looks wrong.

  **`metrics.font` is the same idea about type**, and it is the second of two
  font groups. The family comes off the payload (`[ui] font`) and falls back
  to the session's where that is empty, so a face can be chosen for surfaces
  read from a sofa without changing the one the desktop is read at. The first
  group is the badges' - `ButtonArt.family`, the face `assets/generate.py`
  punched the drawn labels out of - and it does not follow this one, because a
  typed label in another family would stand beside a drawn one that did not
  match. A surface asks `buttonArt.family` for a button and `metrics.font` for
  every other word; reaching past the group for `Style.font.family` is what
  `FontTests` in `tests/test_shell_plugin.py` fails on.

  **`metrics.time` is the same idea about time.** Three named durations, all
  multiplied by `[ui] motion` from the payload, so turning motion off is one
  answer given to every surface rather than seven. There were four: `fill` was
  how long a bar took to answer a number, and it went out with the bars - a
  mark on a line is *where the value is* rather than a length growing towards
  it, so it lands on the frame the value changes and there is nothing left to
  time. 0 does not remove an
  animation, it gives it no duration - a `Behavior` still lands on the value
  it was going to, which is what keeps the still path and the moving path one
  path. The two countdowns stay off it: how long a promise takes is not how
  long a thing takes to move.

  **`metrics.radius` is one ladder off the compositor's own rounding.**
  `radius.card` is `Style.cornerRadius` raw and unscaled - anything that reads
  as a window takes it, square included. `radius.tile` is the base scaled, and
  everything drawn *inside* a card takes it. The base is `decoration:rounding`
  where the compositor has one and the surface's `cornerBase` where it rounds
  nothing, because a desktop that rounds nothing is saying so about windows
  and a tile is not a window. Anything between the two named rungs comes from
  `metrics.rung`; a pill stays `height / 2`.

  **`metrics.type` and `metrics.gap` are the silver ladder**, and a surface
  uses them or it uses `metrics.font` and `metrics.spacing` - never a mixture,
  because half a surface on one scale and half on another is what the ladder
  is here to end. The shell's own sizes are a list of near neighbours (10, 11,
  12, 13, 14, 16) and five of the six landed on one card here: five sizes at a
  keyboard and one size from a sofa, because a pixel of difference is not a
  difference across a room.

  **The ratio answers the question twice**, because a gap and a letter are not
  asked the same one. `gap` is nine gaps off `Style.spacing.sm` climbing by √2
  - the ratio less one - which is 3, 4, 6, 8, 11, 16, 23, 32, 45: a gap either
  separates two things or it does not, nobody reads the difference between 14
  and 16 pixels of air, and √2 doubles in two rungs so the ladder keeps
  landing on 4, 8, 16, 32. `type` climbs by √2 **as well**, off
  `Style.font.caption`: rungs 0 to 4, which is 12, 17, 24, 34, 48 at the
  default theme - the design's own 11, 16, 23, 32, 45 hung from the theme's
  smallest size rather than from 8. It ran on the fourth root of the ratio
  once, for a menu that was a page of labels with a detail line under each; a
  cell whose *value* is the thing it exists to say wants that value two √2
  rungs above the word naming it, and a finer ladder cannot reach that without
  stopping on rungs nobody can name.

  **The ladder decides the steps and the screen decides which one to stop on.**
  `vast` is not a whole ratio above anything: it is three rungs over `loud`
  because four was too much from a sofa and two was not enough, and both of
  those were found by looking. A scale is what stops the sizes drifting between
  the rungs; it was never going to say which rung a clock wants.

  `metrics.rung(base, n)` walks the space ladder and `metrics.step(base, n)`
  the type one, for the places that need a size between the named ones - a
  shrink-to-fit floor. `metrics.silver` is 1 + √2, the proportion to split one
  line over another by. Everything goes through the surface's own scale like
  the rest of this file. `Menu.qml` is across; the other surfaces are not yet.

  **`metrics.spine` is the line motif's measurements**, named here because the
  same line is drawn on two surfaces: down the side of a card of rows in the
  menu, and along the foot of a slider, a stepped slider and a reading in the
  menu and on the HUD (`Travel.qml`). A stroke weight is off the size ladder
  like every stroke weight is, and everything else in it is that weight stepped
  by `silver` - how far the line carries past the thing it measures (`arm`),
  how far the stroke that crosses it reaches on each side (`cross`), and the
  two numbers of the wedge the row card marks its own rows with. Two copies of
  those is how one drawing quietly becomes two.

  `metrics.badge(px)` is the other exception: a badge box has to be whole
  pixels on **both** sides, because BadgeArt scales the drawing by one factor
  taken from the width. Every shape is 32 units tall but a system button is 40
  by 48, so the height is snapped up to a multiple of five - the smallest step
  that keeps `unit * w / h` whole for all of them. Off the grid the pill's rim
  lands mid-pixel and is painted grey instead of drawn. Size a badge with this
  and nothing else.
- **`BadgeArt.qml`** - paints one controller button in given colours. Decides
  nothing: the caller picks the entry, the colours and the stroke weight, and
  this scales the drawing. Set the width; the height follows the drawing's
  aspect, because a squashed button stops reading as one - and the box the
  caller gives has to carry that aspect exactly, which is what
  `Metrics.badge` is for. `strokeWidth` is set
  once and not animated - the mapping screen is the only surface that outlines
  a badge at all, and the countdown that used to thicken an outline is drawn
  by the game bar's fill sweep now.

  Two things that look like savings here were measured and are not:

  - **Building the `Shape` behind a `Loader`** so a badge with no drawing
    skips it. The keyboard carries one `BadgeArt` per key and only about a
    quarter of them draw anything, so this looked free. It cost 2.30 → 2.40 ms
    of shell CPU per keystroke and about 3 MB: a `Loader` and its `Component`
    per badge is more than the empty `Shape` they were meant to save.
  - **Making `ButtonArt.qml` a `pragma Singleton`** so the four surfaces share
    one table instead of four. The table really is about 180 kB an instance,
    so this is roughly 540 kB on the floor - but the singleton does not
    register from a plugin directory. The name resolves and the properties do
    not: `TypeError: Property 'find' of object ButtonArt is not a function`,
    and all four surfaces stop drawing badges. Quickshell's own `Commons/`
    singletons work because they are part of the shell, not a plugin.
- **`ButtonArt.qml`** - **GENERATED** by `assets/generate.py`. Every drawn
  button as path data, plus the `FontLoader` for Fira Code. Do not edit; see
  [`assets.md`](assets.md).
- **`fonts/`** - Fira Code Medium and its OFL licence. Here rather than beside
  the shapes because `omarchy-plugin-validate` rejects a symlink inside a
  plugin folder, so the one copy has to be the one the plugin can reach.

## Reloading

```bash
omarchy-shell shell rescanPlugins   # after editing an existing .qml
omarchy-restart-shell               # after ADDING a .qml, and when an edit does not take
qs -p /usr/share/omarchy/shell log  # the only place the real error appears
```

Qt caches the directory listing per process, so a brand-new file fails to load
with a misleading `File name case mismatch` and the panel silently stays down.
Panel entry points have been seen to resist `rescanPlugins` even on an edit;
the bar widget never does.

**A shared component is worse than an entry point**, and this is the one that
costs an afternoon: `Metrics.qml`, `TileArt.qml`, `ButtonArt.qml` and the rest
are not scanned at all - `rescanPlugins` walks the *plugin's* entry points, and
a component is only re-read when whatever imports it is. A change to a ladder
or a shape therefore takes on the next restart and not before, while every
panel carries on drawing the old numbers and the log says nothing, because
nothing is wrong. Edit one of those and go straight to `omarchy-restart-shell`.

The way to be sure is to look rather than to reason: the surface is on screen,
so `grim` it before and after, and compare the **same** page at both ends of
whatever was changed. Two different pages at two different settings is not a
comparison, and it reads as a difference that is not there.
