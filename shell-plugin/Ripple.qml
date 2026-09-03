// The burst a click leaves behind.
//
// The pointer omapad draws is a ring that never changes, which is what makes
// it findable across a room and also what makes it silent: the thumb is on a
// trigger that feels the same whatever it did, and a click that landed looks
// exactly like a click that went nowhere. This is the answer - one ring
// leaving the pointer, with the half of it on the side of the button that was
// pressed drawn solid, so the two buttons differ by more than a colour.
//
// A pure view like the rest, with two differences that come from drawing an
// event rather than a state. There is no `open`: the daemon sends one payload
// per click and `n` - assigned last - is what starts the animation, so a line
// carrying a sequence number already drawn is a duplicate rather than a
// second click. And there is no heartbeat behind it, which is why nothing
// here drops a repeated line: every line that arrives is a click that
// happened.
//
// One window per monitor, because the pointer roams across all of them and
// the click's coordinates are the compositor's own - global, logical pixels -
// so each panel subtracts its own origin and only the monitor the click
// landed on maps at all. It stays mapped for a moment after the burst is
// over: a layer surface mapping and unmapping is a compositor animation each
// way, and a double click should not pay for two of them.
import QtQuick
import QtQuick.Shapes
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons

Item {
  id: root

  // The click. `n` is a counter the daemon increments per click, never 0.
  property int seq: 0
  property string button: "left"
  property real clickX: 0
  property real clickY: 0
  // How the burst is drawn, all of it from the daemon: the panel cannot read
  // the config, and these are settings rather than proportions of the drawing.
  property real burstSize: 96
  property int burstMs: 260
  property real bandFraction: 0.09
  property real uiScale: 1.0

  // $XDG_RUNTIME_DIR is per-user and 0700, and that is the only thing
  // keeping another user off this socket. Without it there is nowhere
  // private to bind, so bind nowhere: a socket under /tmp is one anybody
  // on the machine can plant first and read what this surface is sent.
  readonly property string socketDir: Quickshell.env("XDG_RUNTIME_DIR")
    ? Quickshell.env("XDG_RUNTIME_DIR") + "/omapad" : ""

  Metrics {
    id: metrics
    scale: root.uiScale
  }

  // 0 the instant the click happened, 1 once the burst is over. Everything
  // the drawing does is a function of this, so one animation drives every
  // monitor's copy rather than each of them keeping its own clock.
  //
  // It runs linearly and the two things it drives take their own curves. An
  // eased phase would have carried the fade with it: the ring reached most of
  // its size in the first third and spent the rest of the burst almost gone,
  // which is a flicker rather than a ring.
  property real phase: 1.0
  // The ring leaves fast and then eases out, the way anything thrown does.
  readonly property real grow: 1 - Math.pow(1 - root.phase, 3)
  // And holds its ink for the first half or so, so what the eye is given to
  // catch is a ring rather than the memory of one: solid until 0.55, then
  // straight down. Where the two curves are shaped is the drawing's own
  // business rather than a setting - `duration_ms` is the number anyone
  // actually wants to change, and it stretches both of them.
  readonly property real ink: root.phase < 0.55 ? 1
    : (1 - root.phase) / 0.45
  // Whether any window is mapped at all.
  property bool live: false

  // The left button gets the theme's accent and the right its foreground.
  // Which side is solid is the answer for anyone who cannot tell those two
  // apart; the colour is the second, faster answer for everyone else.
  readonly property color tint: root.button === "right" ? Color.menu.text
    : Color.accent

  NumberAnimation {
    id: sweep
    target: root
    property: "phase"
    from: 0
    to: 1
    duration: root.burstMs
  }

  // Long enough that a series of clicks costs one map, short enough that a
  // transparent overlay is not left over a fullscreen game.
  Timer {
    id: linger
    interval: root.burstMs + 2500
    onTriggered: root.live = false
  }

  onSeqChanged: {
    if (root.seq <= 0)
      return
    root.live = true
    linger.restart()
    sweep.restart()
  }

  function applyState(text) {
    try {
      var s = JSON.parse(text)
      // First, so a scale change lands even if a later field throws.
      if (s.scale !== undefined) root.uiScale = Number(s.scale) || 1
      if (s.b !== undefined) root.button = String(s.b)
      if (s.x !== undefined) root.clickX = Number(s.x) || 0
      if (s.y !== undefined) root.clickY = Number(s.y) || 0
      if (s.size !== undefined) root.burstSize = Number(s.size) || root.burstSize
      if (s.ms !== undefined) root.burstMs = Number(s.ms) || root.burstMs
      if (s.th !== undefined) root.bandFraction = Number(s.th) || root.bandFraction
      // Last: it is what starts the animation, and everything the burst is
      // drawn from has to be in place before it does.
      if (s.n !== undefined) root.seq = Number(s.n) || 0
    } catch (e) {}
  }

  // Whether a monitor is the one the click landed on.
  function hits(shellScreen) {
    if (!shellScreen)
      return false
    return root.clickX >= shellScreen.x
      && root.clickX < shellScreen.x + shellScreen.width
      && root.clickY >= shellScreen.y
      && root.clickY < shellScreen.y + shellScreen.height
  }

  // omapad connects here and streams state; it reconnects on its own, so the
  // shell and the daemon can restart in either order.
  SocketServer {
    active: root.socketDir !== ""
    path: root.socketDir + "/ripple.sock"
    handler: Socket {
      parser: SplitParser {
        splitMarker: "\n"
        onRead: line => root.applyState(line)
      }
    }
  }

  IpcHandler {
    target: "omapad-ripple"
    function state(): string { return root.live ? "live" : "idle" }
    // What the last line actually painted, which is the question when a
    // burst is drawn somewhere - or in something - it should not have been.
    function burst(): string {
      return root.seq + " " + root.button + " " + root.clickX + "," + root.clickY
    }
    function socket(): string { return root.socketDir + "/ripple.sock" }
    function ping(): string { return "ok" }
  }

  Variants {
    model: Quickshell.screens

    PanelWindow {
      id: panel
      required property var modelData

      screen: modelData
      visible: root.live && root.hits(modelData)
      anchors { top: true; bottom: true; left: true; right: true }
      color: "transparent"
      WlrLayershell.namespace: "omapad-ripple"
      WlrLayershell.layer: WlrLayer.Overlay
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
      exclusionMode: ExclusionMode.Ignore
      mask: Region {}

      Item {
        id: burst

        width: root.burstSize
        height: root.burstSize
        x: root.clickX - panel.modelData.x - width / 2
        y: root.clickY - panel.modelData.y - height / 2
        opacity: root.ink

        // The ring grows out of the pointer and thins as it goes, the way
        // anything leaving something does. The far end stops short of the
        // box by half a band, or the widest moment of the burst would be
        // drawn with four flat sides.
        readonly property real ring: root.burstSize * (0.15 + 0.27 * root.grow)
        readonly property real stroke: Math.max(
          metrics.px(2),
          root.burstSize * root.bandFraction * (1 - root.grow * 0.5))

        // The band the solid half is drawn with.
        readonly property real solid: burst.stroke * 1.55

        // No halo under any of this, unlike the pointer it leaves. The
        // cursor wears one because it is permanent and lands on every
        // wallpaper there is; a burst is gone in a quarter second, and a dark
        // band under two thin ones was measurably muddier than either of them
        // alone.
        Shape {
          anchors.fill: parent
          preferredRendererType: Shape.CurveRenderer

          // The whole ring, faint: what says a click happened here.
          ShapePath {
            strokeColor: Util.alpha(root.tint, 0.40)
            strokeWidth: burst.stroke
            fillColor: "transparent"
            capStyle: ShapePath.FlatCap

            PathAngleArc {
              centerX: burst.width / 2
              centerY: burst.height / 2
              radiusX: burst.ring
              radiusY: burst.ring
              startAngle: 0
              sweepAngle: 360
            }
          }

          // The half under the button that was pressed, solid: what says
          // which one. Qt measures from 3 o'clock and sweeps clockwise, so
          // the 180 degrees after 90 are the left of the screen.
          ShapePath {
            strokeColor: root.tint
            // Wider as well as solid: at the end of the burst the whole ring
            // is thin enough that alpha alone stopped saying which half.
            strokeWidth: burst.solid
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap

            PathAngleArc {
              centerX: burst.width / 2
              centerY: burst.height / 2
              radiusX: burst.ring
              radiusY: burst.ring
              startAngle: root.button === "right" ? -90 : 90
              sweepAngle: root.button === "middle" ? 360 : 180
            }
          }
        }
      }
    }
  }
}
