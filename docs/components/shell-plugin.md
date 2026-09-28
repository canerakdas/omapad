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
control verb and the obvious word for it (`keyboard` → `osk`), and
`surfacePages` the one name that opens a surface on a page: `quick` is the
menu's quick page ([102](../decisions/102-a-page-not-a-second-menu.md)). A summon with
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
- **`Travel.qml`** - where along something a number is, drawn as the
  knob's scale unrolled: a slider being pushed, and a slider with places to
  stand rather than a distance to cover. Every figure is one the ring has, at
  whole line weights - a graduation every five in a hundred on a continuous
  scale, a detent per stop on a stepped one, open-footed ends, and a needle
  across the line that is taller than an end, so a value at either end is
  still drawn. Nothing fills; what the value has covered is the line behind
  the needle - solid, with its detents filled, where it has stops, a tint at
  half where it has none. Two opaque layers faded once, `Knob.qml`'s way. A
  reading is not drawn here: it is words, on both surfaces
  ([92](../decisions/92-a-tuning-scale.md)). The caller hands it `ladder`
  (the surface's `Metrics`), the value, the stops and the four colours; it
  decides nothing.
- **`Knob.qml`** - the same question drawn as a ring, for the one control a
  thumb can copy rather than translate. It keeps the travel's whole argument -
  nothing fills, the run behind the value says how far it has come, solid
  where the value has stops and a tint where it has none - and parts company
  with it four times, each time because a circle is not a line: **a ring's
  ends are marks on its scale**, the longer ones a Braun panel prints there;
  **the value's mark is a pointer**, the index painted on the cap; **a stop is
  one of the scale's printed marks**, a continuous ring printing one every
  five in a hundred;
  and **nothing is drawn where the value started**, because a second pointer
  out of that same middle is a clock rather than a value and its ghost - so
  the ring takes no `ghost` and reads no `b`, and what the turn has done is
  the run lengthening behind the pointer and the marks it has reached
  lighting. It is a Braun T 1000 control drawn in one hairline weight: a
  cap whose edge is a double ring and never turns, the index on its top, and
  the scale round it - `dial-cap`, `dial-pointer`, `dial-notch` and
  `dial-end` - and the arc's `scaleWeight` is the same quarter-unit
  hairline.
  What is not generated is the scale's arc: the run of it the value has
  covered grows with the number, and a track drawn once with that run computed
  against it would be two drawings of one ring. How many marks there are is
  the panel's too. **It is drawn in two layers, one per ink**, each painted
  opaque and faded once: translucent figures drawn one by one either blot
  where they overlap or leave a faint seam where they abut, and the seam was
  visible where the arc met an end. Inside a layer the marks stand in the
  arc and the arc runs into each end, and nothing shows. The two layers meet
  only at the value, where the run reaches half a mark past it so a lit
  mark's foot is never on the unlit scale. The caller hands it `art` (the
  surface's `ControlArt`), the value, the stops and three colours.
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
  to Omarchy's menu face (`OMARCHY_MENU_FONT`, the session's where that is
  unset) where it is empty, so a face can be chosen for surfaces
  read from a sofa without changing the one the desktop is read at. The first
  group is the badges' - `ButtonArt.family`, the face `assets/generate.py`
  punched the drawn labels out of - and it does not follow this one, because a
  typed label in another family would stand beside a drawn one that did not
  match. A surface asks `buttonArt.family` for a button and `metrics.font` for
  every other word; reaching past the group for `Style.font.family` is what
  `FontTests` in `tests/test_shell_plugin.py` fails on. The family is all
  `metrics.font` holds now: the shell's list of sizes went when the last
  surface crossed to the ladder below.

  **`metrics.weight` is four jobs, and each is checked against the faces the
  family has.** `body`, `name`, `strong` and `display` - the words read, a
  word that names something, the one thing in force, the line read from
  across the room. A weight asked for is not a weight drawn: the shipped face
  is a Regular and a Bold, Qt draws 500 from the Regular, and for as long as
  the surfaces asked for `Font.Medium` the row in force was drawn exactly like
  the rows beside it. Seventeen probe `Text`s - one per half step, in the
  surface's family - report `fontInfo.styleName`, which is the only thing Qt
  hands back that names the face it drew; `strong` climbs until that
  changes. Each job's number is the design's, overridden by the theme's
  `shell.toml` (`[font] omapad-weight-<job>`, read through
  `Style.fontOverrides`), moved half a step on `name` and `strong` when the
  theme's text is darker than its ground, then moved in whole steps by `[ui]
  weight` / `game_weight` off the payload (`weightStep`). A badge's label is
  not on it - `buttonArt.weight`, the one face `ButtonArt` loads.
  `metrics.tracking` (`caps`, `masthead`) and `metrics.figures` are the same
  rule for letter-spacing and held figures. `WeightTests` fails on a weight,
  a tracking or a `font.bold` written at the call site.

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

  **`metrics.type` and `metrics.gap` are the silver ladder**, and every
  surface is on it. The shell's own `font.caption`, `spacing.md` and the rest
  were kept beside it while the surfaces crossed one at a time and went when
  the last one did, because half a surface on one scale and half on another
  is what the ladder is here to end. The shell's own sizes are a list of near neighbours (10, 11,
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
  the rest of this file. Every surface is across: the menu first, the guide,
  the mapping screen, the keyboard, the bar and the HUD after it, each at the
  nearest rung - `caption` and `bodySmall` both `fine`, `body` and `title`
  both `body`, `heading` `lead`.

  **`metrics.spine` is the line motif's measurements**, named here because the
  same weight is drawn twice: down the side of a card of rows, and along the
  foot of a slider (`Travel.qml`). A stroke weight is off the size ladder like
  every stroke weight is; the rest is the card's - how far its line carries
  past its first and last rows (`arm`, that weight stepped by `silver`). Two copies of the weight is how one drawing quietly
  becomes two.

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
