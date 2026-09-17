# QML style guide

Applies to every `.qml` file in `shell-plugin/` — an Omarchy shell plugin
(Quickshell). See [`README.md`](README.md) for how MUST / SHOULD / MAY are
meant here.

## 1 What the plugin is

**1.1** **The plugin is a view.** The keyboard's layout and latches, the menu's
tree and stack, the guide's pages, the wizard's step and the bar's live
bindings all live in the daemon. A panel receives line-delimited JSON and
paints it.

**1.2** A panel NEVER decides its own visibility. `Surfaces.qml`'s `open()` and
`close()` shell out to `omapad ctl`; flipping `opened` locally draws a
surface the daemon does not know it is showing, and its next heartbeat takes it
away again.

**1.3** A panel NEVER polls. No `Timer` reading state, no `Process` calling
`omapad ctl status`. If the panel needs to know something, the daemon sends
it — add a field to the payload.

## 2 Source file

**2.1** Two-space indent. Odd indent appears on 5 lines of 2 489; treat those
as mistakes, not precedent.

**2.2** NEVER end a line with `;`. Statements inside a `function` may use one
to separate two on a line, and nothing else does.

**2.3** Lines SHOULD be ≤ 80 columns, wrapping bindings at the operator.
`ButtonArt.qml` is generated and exempt.

**2.4** `var` for locals. The tree has 71 and no `let` or `const`; do not mix
the three in one file.

## 3 File layout

Every panel reads in this order:

```qml
// What this surface is for, and what shaped it: the window rules it needs,   1
// what it borrows from the desktop, why it looks the way it does.
import QtQuick                                                             // 2
import Quickshell
import qs.Commons

Item {
  id: root                                                                 // 3

  property bool opened: false          // one per payload field, defaulted  4
  property var rows: []

  Metrics { id: metrics }                                                  // 5
  ButtonArt { id: buttonArt }

  function applyState(text) { ... }                                        // 6

  SurfaceSocket { ... }                                                    // 7
  IpcHandler { ... }                                                       // 8
  PanelWindow { ... }                                                      // 9
}
```

**3.1** Every file MUST open with a `//` header comment (10 of 10 do). It says
why the surface exists and what constraint shaped it — the same job the Python
module docstring does.

**3.2** One component per file; the filename **is** the component name,
`PascalCase.qml`.

**3.3** The top-level item is `id: root`. Other ids name the thing: `card`,
`list`, `badge`, `panel`, `door`.

**3.4** Every payload field gets a declared `property` with a drawable default,
so the panel renders before anything arrives. Derived values are
`readonly property`; delegate inputs are `required property`.

## 4 The `root.` rule

**4.1** Inside `applyState` — and inside any function that writes state —
assignments to the component's own properties MUST be written **`root.x = …`**:

```qml
if (s.title !== undefined) root.title = s.title      // ✅
if (s.title !== undefined) title = s.title           // ❌
```

**4.2** Why it is a MUST and not a preference: a bare name resolves against the
whole QML scope chain and can land on something read-only. The assignment then
throws, `applyState`'s `catch` swallows it, and **every field after it silently
stops being applied**. The symptom is a panel that has its data and never comes
up, because `open` is assigned last. Nothing in the log says so.

**4.3** The same applies to reads inside a delegate, where `root.sel` and a
delegate's own `sel` are different things.

## 5 `applyState`

**5.1** The whole body is inside one `try { … } catch (e) {}`. One
`JSON.parse`, at the top.

**5.2** Every field is guarded with `!== undefined` and coerced on the way in:
`!!s.open`, `String(s.mode)`, `Number(s.scale) || 1`. The daemon may add a
field at any time; an older panel must keep drawing.

**5.3** **`scale` is assigned first, `open` last.** A scale change should land
even if a later field throws, and nothing should be shown half-applied.

**5.4** **A line that says nothing new is dropped, and so is a list that has
not changed.** The daemon re-sends everything every `VIEW_HEARTBEAT` seconds
and on every press, so most of what arrives is what is already on screen — and
re-applying it is not free. A `var` property never compares equal to its old
value, so assigning one re-runs every binding that reads it, and where it is a
Repeater's or a ListView's model it destroys and rebuilds every delegate under
it. Twice a second, for a surface nobody is touching, that measured 0.4% of a
core and a climbing heap.

So `applyState` opens by dropping an identical line, and every field that is a
model goes through `fresh()`. A fresh component's `lastLine` is empty and its
`seen` is bare, so a restarted shell still paints the first line it is given —
the heartbeat's whole job survives.

**The daemon does the same from its end**, and that is what makes a surface
able to stream. `menu.sock` carries a second, short line — `{open, sel, g,
live}`, with **no `items` key at all** — so `applyState` gets past `lastLine`,
finds nothing that is a model, and never reaches `fresh()`: one binding
re-runs and no delegate is rebuilt. It is this rule from the other side rather
than a hole in it, and it is the only reason a 60 Hz surface is affordable
here. Its cost is one rule of its own: **nothing may bind a layout width or
height to a value that arrives at frame rate**, which is checked in
`tests/test_shell_plugin.py` rather than left to review.

```qml
property string lastLine: ""
property var seen: ({})

function fresh(key, value) {
  var line = JSON.stringify(value)
  if (line === root.seen[key]) return false
  root.seen[key] = line
  return true
}

function applyState(text) {
  if (text === root.lastLine) return
  root.lastLine = text
  try {
    var s = JSON.parse(text)
    // First, so a scale change lands even if a later field throws.
    if (s.scale !== undefined) root.uiScale = Number(s.scale) || 1
    if (s.rows !== undefined && root.fresh("rows", s.rows))
      root.rows = s.rows
    if (s.open !== undefined) root.opened = !!s.open
  } catch (e) {}
}
```

Only the models need `fresh()`. A `string`, `int` or `bool` property compares
its own value and emits nothing when it is unchanged, so guarding one buys
nothing — which is why `PadStatus.qml`, whose payload is four scalars, has
neither of these and is right not to.

**5.5** **A delegate may be built in the middle of what it is drawing.** A
model that does change rebuilds every delegate under it, so a delegate is born
wherever the state happens to be — past any transition it needed to see. A
`Behavior`, an `onXChanged` or an `Animation` started from a signal handler
must therefore be re-enterable and entered from `Component.onCompleted` too;
`GameBar.qml`'s `Badge.enterHold()` is the worked example. Left to the signal
alone, a badge rebuilt mid-hold drew a dimmed, empty countdown for the rest of
the hold.

## 6 Sockets

**6.1** One `SurfaceSocket` per surface - `dir: root.socketDir`, `name` the
daemon's own socket file, `onLine` into `applyState`. The name is the
daemon's, not the panel's: `Keyboard.qml` listens on `osk.sock`.

Never a bare `SocketServer`. The directory the sockets live in belongs to the
daemon and the shell is usually up before it, so the first bind lands in a
directory that is not there yet - and Quickshell answers a failed bind by
dropping `active` to false and never trying again. The surface would then be
dead for the whole session, with one warning in a log nobody is reading.
`SurfaceSocket` is that retry, and it is why every panel can say the shell and
the daemon start in either order.

**6.2** Each panel also exposes `IpcHandler` with `open`, `close`, `state`,
`socket` and `ping`, so a surface can be inspected without the daemon.

## 7 Window rules

A surface MUST NOT steal focus or a click from the window underneath:

```qml
WlrLayershell.namespace: "omapad-<surface>"
WlrLayershell.layer: WlrLayer.Overlay      // Top for the game bar
WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
exclusionMode: ExclusionMode.Ignore        // Normal to reserve or dodge a strip
mask: Region {}                            // empty input region
```

Three deliberate exceptions:ther game bar is `WlrLayer.Top` with
`ExclusionMode.Auto`, because it stands in for a real bar;ther keyboard is
`ExclusionMode.Normal` with an `exclusiveZone` of its own height, so it does
not cover what is being typed into;and the menu is the one surface someone
also drives from the desk -ther Omarchy menu's own window rules
(`WlrKeyboardFocus.Exclusive`, the whole surface as its input region,so a
hover selects,a click picks,and a scrim click leaves). The pad,ther keys
and the cursor all drive the same selection,over the same control socket.

A surface that draws a scrim - the menu, the guide, the mapping
wizard - turns `ExclusionMode.Normal` on while `bar` says omapad's own bar is
up, so the compositor hands it what is left of the screen rather than the
whole of it. The scrim dims the desktop the surface stands in front of, and
the bar is not that desktop: while one of them is up it is printing what *its*
face buttons do, and a legend read through a scrim is the last thing on screen
that should go dark. Omarchy's bar is not stood off - it is the desktop, and
dimming it is what the Omarchy menu does too.

## 8 Colour, size, glyphs

**8.1** NEVER hardcode a colour. `Color.menu.*` for the surfaces,
`Color.bar.*` for the game bar. A console's own palette would fight every
Omarchy theme but one.

**8.1.1** A colour is a *role*, and contrast between two of a theme's roles
can never be assumed - a theme whose accent sits close to its surface exists,
which is why a tile says its state in ink **and** in silhouette. The trap has
a name: `Color.menu.selectedText` defaults to `accent`, so anything filled
solid with `Color.accent` and labelled with it is a label that is not there.
Anything filled solid takes `Ink.on(ground, first, second)`, which measures;
and the candidates are only ever colours the theme is guaranteed to have
defined. Everywhere else, tint rather than fill and the question does not
arise.

**8.1.2** **A dim ink is a level, not a fade, and there are three.** The design
publishes exactly three inks over a card - primary, muted and dim - and
publishes them as *measured* colours, each at 4.5:1 or better on the ground it
is drawn on. `Menu.qml` names the lower two as `inkMuted` and `inkDim` and every
call site takes one of them. Picking a number at the call site is how that
surface ended up with 0.36, 0.42, 0.52 and 0.58 in one file, three of which are
below the floor: a second line nobody can read from a sofa is a line not doing
the job it is there for. A number of its own needs a comment saying what it is
receding *from* and why it is not one of the three.

**8.2** Every measurement goes through `Metrics`, which multiplies `Style` by
the scale the daemon stamps on the payload. `Style.cornerRadius` and
`Style.gapsOut` are NOT scaled — they are the compositor's geometry, shared
with every window on screen.

**8.2.0** A radius comes from `metrics.radius`, never from `Style.cornerRadius`
at the call site. Two rungs are named: `radius.card` is the compositor's own
rounding, unscaled, and anything that reads as a window takes it, square
included; `radius.tile` is the base scaled, and everything drawn *inside* a
card takes it. The base is `Style.cornerRadius` where the compositor has one
and the surface's own `cornerBase` where it rounds nothing — a desktop that
rounds nothing is saying so about windows, and a tile is not a window. A pill
stays `height / 2`: round because it is round, which is a geometric identity
rather than a decision.

`metrics.radiusScale` (`[ui] radius`) multiplies whichever base is in force,
and it reaches both named rungs: rounding one thing on a surface and not the
rest is the split this ladder exists to end. It is a **multiplier** because
the base is never ours to choose - what the setting says is how far off the
desktop's own answer these surfaces stand - and its stops are a √2 ladder like
every other size here, for the reason 8.2.2 gives about gaps: a corner either
reads as rounder or it does not, and the rungs in between are ones nobody can
name.

**8.2.1** A surface takes its sizes from **one** ladder. `metrics.type` (five
sizes: 10, 12, 16, 24, 47) and `metrics.gap` (nine: 3, 4, 6, 8, 11, 16, 23,
32, 45) are omapad's, both hung off the shell's smallest values; `metrics.font`
and `metrics.spacing` are the shell's own. NEVER mix the two in one file: the
whole point of the ladder is that a surface read from a sofa has few sizes and
they are far apart, and one call site left on the shell's scale puts a 13 next
to a 16 where the difference reads as a mistake. `Menu.qml` is across and says
so in its header; the rest are not.

A number that belongs to something else stays off the ladder and says in a
comment which: a stroke weight, a card's own width, a letterform's own
tracking, and above all **anything mirrored from another surface**. The menu's
legend is the whole of that last case — badge, letter, word and both spacings
are `GameBar.qml`'s expressions character for character, because on a
fullscreen HUD that row sits in the bar's band saying the same four words
about the same four buttons. Putting a mirrored measurement on the ladder is
how the two quietly stop matching.

**8.2.2** **One ladder, both questions.** Space and type both climb by √2 —
`gap` off `Style.spacing.sm`, `type` off `Style.font.caption` — so the design
this surface is built to and this surface's own scale are the same ladder hung
from two anchors, and the design's 11, 16, 23, 32, 45 land on the named rungs.
Type ran on the fourth root of the ratio once, for a menu that was a page of
labels with a detail line under each; a cell whose value is the thing it
exists to say wants that value two √2 rungs above the word naming it, and the
finer ladder cannot reach that without stopping on rungs nobody can name.

**8.2.6** **Concentric is a radius, not only a centre.** A rounded rectangle
drawn `d` pixels outside another one takes `d` more corner than it, and one
drawn inside takes that much less; give two of them the same radius and they
run parallel down the edges and part at the corners - which is exactly where
an eye checks whether two lines belong to one drawing. So a surface that draws
a figure around another one names **one** radius and every other figure asks
what its own is by how far it stands from that path: `Menu.qml` has
`tile.concentric(out)` over `metrics.radius.tile`, and the halo, the press
ring, the sheen and a hold's sweep all go through it. The bug it ends is
silent at a hairline and obvious the moment a stroke is four pixels wide,
which is how it survived a long time: the corner of a ring that changed weight
moved and nothing else did.

**8.2.5** **A margin against the edge of the *screen* goes through
`metrics.edge(span, own)`**, which answers the surface's own margin or the
share `[ui] safe_area` keeps clear, whichever stands further in. The span is
the screen's, never the window's: a bar is a strip and a keyboard is a card,
and what a television crops is a share of the picture. It is not scaled -
`factor` is how far away the reader is, and this is how much of the picture
the set never draws. A margin that is not against the screen edge stays off
it: a centred card's padding is a distance from its own border, and holding
that off to a share of the screen would blow the card's inside out to keep a
gap it is nowhere near.

**8.2.4** **A duration comes from `metrics.time`, never from a number at the
call site.** Three are named - `brisk` a fade inside a tile, `follow` a view
catching up with a selection, `arrive` a whole surface or a leaning badge -
and they are a list rather than a ladder: a fade twice another fade is just a
slower fade. There were four: `fill` was how long a bar took to answer a
number, and it went when the bars did - a mark on a line is *where the value
is* rather than a length growing towards it, so it lands on the frame the
value changes (8.2.4.1) and nothing is left to time. They all go through
`metrics.ms()`, which multiplies by `[ui] motion` off the payload, so a person
who has asked the screen to hold still is answered on every surface at once.
`tests/test_shell_plugin.py` fails on a duration that is neither.

Time is scaled by motion and **not** by `factor`: a surface drawn twice as
large does not take twice as long to fade. And a countdown is not motion -
`[ripple] ms` and the confirm badge's lap say how long a promise takes, they
are settings already, and they stay off this.

**8.2.4.1** **Three properties transition and no others**, which is the
design's own rule rather than a QML one: a ring's colour, the glow round it,
and a press brightening. Everything else about a state - a ground filling, an
ink colour inverting on it, a badge changing what it prints - switches
outright on the frame the state changes. So a `Behavior` belongs on
`strokeColor`, on a halo's or a sheen's `opacity`, and nowhere else. A nav
card whose accent fill crossfaded would read as a card being painted; walking
a bar is one card lighting up.

A colour fades with `ColorAnimation`, not `NumberAnimation`, and takes
`metrics.time.brisk` - which is the design's 90 ms linear, and linear is what
both default to.

The panel never asks whether motion is wanted - it is handed a number, and the
daemon has already folded the compositor's own `animations:enabled` into it
(`daemon.view_motion`). A panel that read a system preference for itself would
be the second place that answer lives.


**8.2.3** Sizes between the named ones come from `metrics.rung(base, n)`,
never from arithmetic on a rung.
`metrics.type.fine - metrics.gap.xxs` happens to be the right number and says
nothing; `metrics.rung(metrics.type.fine, -1)` says it is a step down the same
ladder. `metrics.silver` (1 + √2) is the proportion for one line set over
another.

**8.3** Controller glyphs come from `ButtonArt.qml`, and the parts a menu
control tile is drawn from come from `ControlArt.qml`. Both are painted by
`BadgeArt.qml`. NEVER draw a button shape by hand, and never inline an SVG from
`assets/buttons/`: a badge takes the theme's colours, an SVG carries only the
colour it was drawn with.

**8.4** Both are **generated**. Edit `assets/shapes/` or a table in
`assets/generate.py` and re-run it. `ControlArt.qml` holds only the furniture
of a control - what does not depend on its value; an arc that follows a number
is geometry, and geometry is the panel's.

**8.5** **Text set inside a button is centred on its capitals, never by
`anchors.verticalCenter`.** That anchor centres the *line box*, and Fira Code's
line box carries a descender's worth of room under the word — 0.046 em more
below the capitals than above them — so an all-caps label sits high and the
gap under it comes out about twice the gap over it. Measure instead: a
`TextMetrics` on an **H** (flat on the baseline, so its ink box is the cap
box) plus the item's `baselineOffset` say where the capitals are.
`Guide.qml`, `Keyboard.qml` and `GameBar.qml` each carry a `capNudge` for
their badge labels; `GameBar.qml`'s menu door measures its own because the
mark beside its word is drawn to the word's capitals. Round the result: a
letter on a half pixel is the blur antialiasing cannot help.

**8.6** **Every `Text` MUST say `textFormat: Text.PlainText`.** Left alone, a
`Text` guesses: a string that looks like markup is drawn as rich text, and
rich text loads what it names. Some of what a panel draws is not typed by
anyone - a pad's name comes from its own USB descriptor, an audio row's label
from whatever a sink calls itself - so `<img src=…>` in a device name is a
persistent shell fetching a stranger's URL. The property is on every `Text`
rather than only the ones drawing a payload today, because which string a
`Text` draws changes and the failure is silent when it does.
`tests/test_shell_plugin.py` reads the files and fails on a `Text` without it.

The daemon does the other half: `viewsock.drawable()` cuts a device-derived
string to a length a row can hold and strips the characters that make Qt guess
at all, for the sinks this project does not own - the bar tooltip is Omarchy's
`Text`, not ours to set.

## 9 Reloading

```bash
omarchy-shell shell rescanPlugins   # after editing an existing .qml
omarchy-restart-shell               # after ADDING one, and when an edit does not take
qs -p /usr/share/omarchy/shell log  # the only place the real error appears
/usr/lib/qt6/bin/qmllint <file>.qml # syntax and scope, before any of that
```

Qt caches the directory listing per process, so a brand-new file fails with a
misleading `File name case mismatch` and the panel silently stays down. Panel
entry points (`keepLoaded: true`) have been seen to resist `rescanPlugins`
even on an edit; the bar widget never does.

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

`shell-plugin/` is symlinked into `~/.config/omarchy/plugins/`, so the checkout
is the live source. `omarchy-plugin-validate` rejects a symlink *inside* a
plugin folder — which is why `fonts/` holds a real copy of the font.

## 10 Quick list of what is never in this plugin

state the daemon should own · a `Timer` polling for it · a hardcoded colour ·
a hand-drawn button shape · an edit to `ButtonArt.qml` · a `Text` with no
`textFormat` · a bare assignment in `applyState` · a model re-assigned from an unchanged payload · an animation
only a signal handler can start · a panel that opens itself.
