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

  SocketServer { ... }                                                     // 7
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

**6.1** One `SocketServer` per surface, on `root.socketDir + "/<name>.sock"`,
with `SplitParser { splitMarker: "\n" }`. The name is the daemon's, not the
panel's: `Keyboard.qml` listens on `osk.sock`.

**6.2** Each panel also exposes `IpcHandler` with `open`, `close`, `state`,
`socket` and `ping`, so a surface can be inspected without the daemon.

## 7 Window rules

A surface MUST NOT steal focus or a click from the window underneath:

```qml
WlrLayershell.namespace: "omapad-<surface>"
WlrLayershell.layer: WlrLayer.Overlay      // Top for the game bar
WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
exclusionMode: ExclusionMode.Ignore        // Normal only if it reserves space
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

## 8 Colour, size, glyphs

**8.1** NEVER hardcode a colour. `Color.menu.*` for the surfaces,
`Color.bar.*` for the game bar. A console's own palette would fight every
Omarchy theme but one.

**8.2** Every measurement goes through `Metrics`, which multiplies `Style` by
the scale the daemon stamps on the payload. `Style.cornerRadius` and
`Style.gapsOut` are NOT scaled — they are the compositor's geometry, shared
with every window on screen.

**8.3** Controller glyphs come from `ButtonArt.qml` painted by `BadgeArt.qml`.
NEVER draw a button shape by hand, and never inline an SVG from
`assets/buttons/`: a badge takes the theme's colours, an SVG carries only the
colour it was drawn with.

**8.4** `ButtonArt.qml` is **generated**. Edit `assets/shapes/` or a table in
`assets/generate.py` and re-run it.

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

`shell-plugin/` is symlinked into `~/.config/omarchy/plugins/`, so the checkout
is the live source. `omarchy-plugin-validate` rejects a symlink *inside* a
plugin folder — which is why `fonts/` holds a real copy of the font.

## 10 Quick list of what is never in this plugin

state the daemon should own · a `Timer` polling for it · a hardcoded colour ·
a hand-drawn button shape · an edit to `ButtonArt.qml` · a bare assignment in
`applyState` · a model re-assigned from an unchanged payload · an animation
only a signal handler can start · a panel that opens itself.
