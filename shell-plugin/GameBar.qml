// The game-mode bar for omapad.
//
// Game mode hides Omarchy's bar, because every widget on it opens a popup you
// click and in game mode there is no pointer to click with. This is what
// stands in its place: left, the clock and the menu with the button that opens
// it; centre, the workspaces, flanked by the buttons that walk them; right,
// what the rest of the buttons do.
//
// It is a readout first - every badge on it says what a button under a thumb
// does, and lights up while that button is down. Where there is a pointer on
// the desk it is a control second: clicking a badge fires exactly the binding
// the press would, through the daemon, which is the only thing that knows what
// a button means.
//
// It borrows Omarchy's bar colours - `Color.bar.*`, not the menu's - so that
// switching modes reads as the same bar changing its mind rather than a
// different program taking the screen. The workspaces are drawn the way
// `omarchy.workspaces` draws them, down to the dot the focused one becomes:
// the same information should not have two appearances on one desktop.
//
// Same split as every other surface: omapad decides all of it - which
// workspace is live, which bindings are true right now, which buttons are
// down - and pushes one JSON line per change. This file draws it, and where a
// pointer clicks a badge it says so back over `omapad ctl press` rather than
// deciding what the button means: that stays one question with one answer.
//
// Sized for the couch rather than the desktop: the whole reason Omarchy's 26px
// bar is no use here is that nobody reads 26px from a sofa. It carries an
// exclusion zone like a real bar, so windows sit under it rather than behind
// it - a game that goes full-screen covers it anyway, which is the right
// outcome and needs no special case.
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons
import qs.Ui

Item {
  id: root

  property bool opened: false
  property var menu: null
  property var wsprev: null
  property var wsnext: null
  // {b, ms} while a confirming hold counts down, so the badge it names can
  // walk back to full exactly as the hold completes.
  property var holding: null
  property var workspaces: []
  property int active: -1
  property var actions: []
  // The buttons that are down right now, in omapad's own logical names, so
  // a badge answers the thumb on it. Every press is sent, not only the ones
  // the bar has a badge for: which of them is drawn is this file's question.
  property var pressed: []
  // Whether a pointer may fire what a badge names (`[gamebar] click`). The bar
  // stands in for a desktop bar because game mode has no pointer to click one
  // with - but game mode is the couch environment rather than a hand-off, so
  // the desktop is still under this bar and a mouse may still be on the desk.
  property bool clickable: true
  property string note: ""

  function isDown(name) {
    return name.length > 0 && root.pressed.indexOf(name) !== -1
  }

  // A click on a badge, sent the way the shell's summon is sent: the daemon
  // owns what a button does, and the bar has no business resolving a binding
  // it only prints. `hold` for a hint that only has a hold half - one reading
  // "hold - Fullscreen" that did nothing when clicked would be worse than not
  // being clickable at all.
  function fire(name, holdOnly) {
    if (!root.clickable || !name || name.length === 0) return
    Quickshell.execDetached(
      ["omapad", "ctl", "press", name, holdOnly ? "hold" : "tap"])
  }

  readonly property string socketDir: (Quickshell.env("XDG_RUNTIME_DIR") || "/tmp") + "/omapad"

  // How big this surface draws, from the daemon: the desktop is read at a
  // keyboard and game mode from a sofa, so the scale follows the mode rather
  // than the session. Every measurement below goes through `metrics`.
  property real uiScale: 1.0

  Metrics {
    id: metrics
    scale: root.uiScale
  }

  // The drawn buttons, and the font their labels are set in.
  ButtonArt {
    id: buttonArt
  }

  // What omapad's `[gamebar] height` asks for, before the shell's spacing
  // scale and omapad's own `[ui]` scale. Floored at the badge row plus a hairline of air, so a number typed
  // too small yields the tightest legible bar rather than a cropped one - the
  // bar is a readout, and half a badge reads as a glitch.
  property int wantedHeight: 32
  // How far an armed badge leans, and how long one lean-and-back takes. Both
  // come from the daemon rather than being picked here: how big a tremble has
  // to be before it is seen is a function of how far away the sofa is, which
  // is the same thing the bar's height answers.
  property int wantedTremble: 2
  property int trembleMs: 90
  // How long a badge sits dimmed before it begins to fill. Same reason as the
  // two above: what counts as "longer than a tap" is the user's, not ours.
  property int fillDelayMs: 60
  readonly property int sideMargin: metrics.space(18)
  readonly property int badgeUnit: Math.max(metrics.space(20), metrics.font.bodySmall + metrics.space(7))
  readonly property int barHeight: Math.max(metrics.space(wantedHeight),
    badgeUnit + metrics.space(3) * 2)
  // Zero means the badge only stays full while it counts down; `space` never
  // rounds a positive number down to nothing, so anything else is at least a
  // pixel of lean.
  readonly property int trembleReach: wantedTremble > 0 ? metrics.space(wantedTremble) : 0

  // A typed badge label centred in its shape is centred by its *line box*,
  // and the line box is not centred on the capitals inside it - the letter
  // came out about a pixel high, with the gap under the glyph wider than the
  // gap over it. The correction is a font metric rather than a taste, so it
  // is measured instead of typed in: a probe laid out with the label's own
  // font, and the ink box of a capital inside it. Positive moves the label
  // down. Only the typed fallback needs it; a drawn label was placed by the
  // shape it sits in, not by a line box.
  Text {
    id: capProbe
    visible: false
    text: "H"
    font.family: buttonArt.family
    font.pixelSize: Math.round(root.badgeUnit * 0.44)
    font.weight: Font.Medium
  }
  TextMetrics {
    id: capInk
    font: capProbe.font
    text: capProbe.text
  }
  readonly property int capNudge: Math.round(capProbe.height / 2 - capProbe.baselineOffset
    - (capInk.tightBoundingRect.y + capInk.tightBoundingRect.height / 2))

  // The dot `omarchy.workspaces` puts where the focused number would be.
  readonly property string focusedGlyph: "󱓻"

  // Omarchy's bar can be transparent, and on this desktop it is - so its
  // background is the wallpaper, not `Color.bar.background`. Matching it means
  // following that setting rather than the token, which is why the shell's own
  // config is read here. It is watched, so toggling the bar's transparency
  // (double-click its centre) carries over to this one.
  property bool barTransparent: false

  // Transparent means the wallpaper is the background, and the theme's bar
  // text is not guaranteed to be legible on it. Omarchy solves this by asking
  // `omarchy-bar-text-color` which of two colours survives the pixels behind
  // the bar; asking the same question with this bar's own height is the only
  // way to end up with the same answer.
  property color transparentForeground: Color.bar.text
  readonly property color foreground: barTransparent ? transparentForeground : Color.bar.text

  // Omarchy's own bar edge, read from the same watched file as transparency,
  // and what omapad's `[gamebar] position` asks for. "auto" follows the
  // desktop bar so the couch bar is where the desktop bar taught you to look;
  // anything else pins it.
  //
  // Only the two horizontal edges: Omarchy's bar can stand on the left or the
  // right, but this one is a horizontal readout and turning it on its side is
  // a different bar, not this one rotated. A vertical bar leaves both
  // horizontal edges free anyway, so following it lands on the top.
  property string barPosition: "top"
  property string wantedPosition: "auto"
  readonly property string edge: (wantedPosition === "top" || wantedPosition === "bottom")
    ? wantedPosition
    : (barPosition === "bottom" ? "bottom" : "top")

  function colorHex(colorValue) {
    var c = colorValue
    if (typeof c === "string") c = Qt.color(c)
    function channel(value) {
      var text = Math.round(Math.max(0, Math.min(1, value)) * 255).toString(16)
      return text.length < 2 ? "0" + text : text
    }
    return "#" + channel(c.r) + channel(c.g) + channel(c.b)
  }

  function refreshForeground() {
    if (!barTransparent || textColorProc.running) return
    // The edge is what the helper samples the wallpaper behind, so it has to
    // be this bar's edge and not the desktop bar's.
    textColorProc.command = [
      "omarchy-bar-text-color", root.edge, String(root.barHeight),
      root.colorHex(Color.bar.text), root.colorHex(Color.background)
    ]
    textColorProc.running = true
  }

  onBarTransparentChanged: refreshForeground()
  onEdgeChanged: refreshForeground()
  onOpenedChanged: if (opened) refreshForeground()

  Process {
    id: textColorProc
    stdout: SplitParser {
      onRead: function (line) {
        var value = String(line || "").trim()
        if (/^#[0-9A-Fa-f]{6}$/.test(value)) root.transparentForeground = value
      }
    }
  }

  FileView {
    path: (Quickshell.env("HOME") || "") + "/.config/omarchy/shell.json"
    watchChanges: true
    printErrors: false
    onLoaded: {
      try {
        var config = JSON.parse(text())
        root.barTransparent = !!(config.bar && config.bar.transparent)
        var position = config.bar && config.bar.position
        root.barPosition = (position === "bottom") ? "bottom" : "top"
      } catch (e) {}
    }
    onFileChanged: reload()
  }

  // omapad re-sends the whole payload every VIEW_HEARTBEAT seconds, so a
  // restarted shell repaints itself with no handshake - which means most
  // lines that arrive here say nothing new. Re-applying one is not free: a
  // `var` property never compares equal to its old value, so assigning it
  // re-runs every binding that reads it, and where it is a Repeater's model
  // it destroys and rebuilds every delegate under it. A fresh component's
  // `lastLine` is empty, so a restarted shell still paints what it is given.
  property string lastLine: ""
  // The same argument one field at a time, for the lists a press leaves
  // alone:
  // every button event repaints the bar, but what the buttons do and which
  // workspaces exist are not what changed - and a rebuilt badge loses the
  // countdown it was drawing.
  // The daemon sends the whole surface on every change, and most of it is
  // the same surface.
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
      if (s.pos !== undefined) root.wantedPosition = String(s.pos)
      if (s.h !== undefined) root.wantedHeight = Number(s.h)
      if (s.tremble !== undefined) root.wantedTremble = Number(s.tremble)
      if (s.tremble_ms !== undefined) root.trembleMs = Number(s.tremble_ms)
      if (s.fill_delay_ms !== undefined) root.fillDelayMs = Number(s.fill_delay_ms)
      if (s.menu !== undefined) root.menu = s.menu
      if (s.wsprev !== undefined) root.wsprev = s.wsprev
      if (s.wsnext !== undefined) root.wsnext = s.wsnext
      if (s.holding !== undefined) root.holding = s.holding
      if (s.workspaces !== undefined
          && root.fresh("workspaces", s.workspaces))
        root.workspaces = s.workspaces
      if (s.active !== undefined) root.active = s.active === null ? -1 : Number(s.active)
      if (s.actions !== undefined && root.fresh("actions", s.actions))
        root.actions = s.actions
      if (s.pressed !== undefined) root.pressed = s.pressed
      if (s.click !== undefined) root.clickable = !!s.click
      if (s.note !== undefined) root.note = s.note
      if (s.open !== undefined) root.opened = !!s.open
    } catch (e) {}
  }

  // 1 to 5 always, plus anything else that exists, exactly as the Omarchy
  // widget decides its own row: a workspace strip that changes length as you
  // move through it is a strip you cannot aim at.
  //
  // A property rather than the function it was, because it is a Repeater's
  // model: a function called from a binding hands back a new array every time
  // it is evaluated, and a new array is a model reset. As a property it is
  // one array that is rebuilt only when the workspaces themselves change.
  readonly property var workspaceIds: {
    var ids = [1, 2, 3, 4, 5]
    for (var i = 0; i < root.workspaces.length; i++) {
      var id = Number(root.workspaces[i].id)
      if (id > 0 && id <= 10 && ids.indexOf(id) === -1) ids.push(id)
    }
    ids.sort(function (left, right) { return left - right })
    return ids
  }

  function occupied(id) {
    for (var i = 0; i < workspaces.length; i++) {
      if (Number(workspaces[i].id) === id) return (workspaces[i].windows || 0) > 0
    }
    return false
  }

  SocketServer {
    active: true
    path: root.socketDir + "/gamebar.sock"
    handler: Socket {
      parser: SplitParser {
        splitMarker: "\n"
        onRead: line => root.applyState(line)
      }
    }
  }

  IpcHandler {
    target: "omapad-gamebar"
    function state(): string { return root.opened ? "open" : "closed" }
    function socket(): string { return root.socketDir + "/gamebar.sock" }
    function ping(): string { return "ok" }
  }

  // How lit something pressable on the bar is: at rest, under a pointer that
  // could fire it, and while it is down - from a thumb or from that pointer,
  // which are one statement about one button and so look like one. It is the
  // fill that carries it rather than an outline, because what survives being
  // read across a room is the shape's area and not a line around it.
  readonly property real restLit: 0.20
  readonly property real hoverLit: 0.32
  readonly property real downLit: 0.50

  // A pointer's way in, and the whole of it: laid over the thing it fires,
  // badge and words together, because a target picked out from a sofa wants to
  // be the size of the thing you are reading. Everywhere else on the strip a
  // click lands on nothing, the way it does on a desktop bar's background.
  component Click: MouseArea {
    property string button: ""
    // A binding whose tap half is empty is fired by its hold half instead.
    property bool holdOnly: false
    // What the daemon says this one may be fired by: a binding that clicks or
    // scrolls the pointer does it wherever the pointer is, which is on this
    // badge, so the answer would land back here and ask for another. Such a
    // badge is still drawn and still lights up under its own button - it just
    // is not a thing a mouse can ask for.
    property bool offered: true

    anchors.fill: parent
    enabled: root.clickable && offered && button.length > 0
    // Only while it can act: a hand-shaped cursor over a badge that does
    // nothing is the same lie as a badge printing a binding it does not have.
    hoverEnabled: enabled
    cursorShape: Qt.PointingHandCursor
    onClicked: root.fire(button, holdOnly)
  }

  // The same badge the guide draws, at the same proportions, because a button
  // named here and named there has to look like the same button. Its colours
  // come from the bar, so it sits on this ground rather than the guide's.
  component Badge: Item {
    id: badge

    property string label: ""
    property string kind: "face"
    // omapad's own name for this button, under the name the pad prints:
    // what a press arrives as and what a click is sent back as. The printed
    // label is for the eye and cannot be either.
    property string name: ""
    // A pointer over this badge, and a pointer holding it down. The thumb's
    // own press comes the other way round, out of `root.pressed`, and lights
    // the badge identically: one button pressed is one thing, however.
    property bool hovered: false
    property bool held: false
    // The app in front has this button's plain press; the desktop is behind
    // an announced hold. Said with less of the same colour rather than with a
    // colour of its own: "not at a tap" is contrast, not hue - and a hue would
    // fight a bar whose foreground is picked per wallpaper.
    property bool locked: false
    // Which way the press this badge is counting down to will move things:
    // -1 leans left, +1 right, 0 trembles both ways because nothing on the
    // bar says where this one would go. A drawing fact rather than a daemon
    // one - it is the side of the strip the badge stands on.
    property int lean: 0
    // How far it is leaning right now, in pixels. Left unrounded: the badge
    // is vector art and this only moves while it is moving, so whole pixels
    // would buy no sharpness and cost the tremble its smoothness.
    property real leaned: 0

    readonly property bool down: badge.held || root.isDown(badge.name)

    readonly property int unit: root.badgeUnit
    // The button as drawn in assets/shapes: `drawn` is the whole badge, down
    // to the label or the D-pad arm set into it, and `bare` is the shape
    // alone, for a label no pad here prints and for the system buttons, which
    // are one pill until the shell types START or SELECT into it.
    readonly property var drawn: buttonArt.find(badge.kind, badge.label)
    readonly property var bare: buttonArt.shape(badge.kind, badge.label)
    readonly property var art: badge.drawn !== null ? badge.drawn : badge.bare
    // Only for a kind ButtonArt has never heard of - the daemon sends none,
    // but a badge that is only text still needs a box to be centred in.
    readonly property bool wide: kind === "bumper" || kind === "trigger" || kind === "system"
    // Counting down right now, so the dimming walks off over exactly as long
    // as the hold takes: the badge is full at the moment it fires.
    readonly property bool arming: root.holding !== null && root.holding !== undefined
      && root.holding.b === label
    // Past the tick: the hold has announced itself and is counting down to
    // firing.
    readonly property bool armed: arming && !!root.holding.armed
    // The countdown, split into the part that is waited out and the part that
    // is drawn. A fill that started on contact flickered under a shoulder
    // tapped to walk browser tabs, so it sits still for `fillDelayMs` first -
    // and the wait comes out of the ramp rather than off the end, so the badge
    // is still exactly full at the moment the hold fires. Capped at the hold
    // itself: a delay longer than the wait it announces would draw nothing.
    readonly property int lapMs: root.holding ? root.holding.ms : 0
    readonly property int lapWaitMs: Math.max(0, Math.min(root.fillDelayMs, badge.lapMs))
    readonly property int lapRampMs: Math.max(0, badge.lapMs - badge.lapWaitMs)

    // Left alone while a hold counts down: the fill is saying how much longer
    // then, and a press brightening the same fill would erase the sweep that
    // is the whole point of announcing the hold.
    readonly property real lit: badge.arming
      ? root.restLit
      : (badge.down ? root.downLit
                    : (badge.hovered ? root.hoverLit : root.restLit))

    implicitWidth: badge.art !== null
      ? Math.round(unit * badge.art.w / badge.art.h)
      : (wide ? Math.round(unit * 1.6) : unit)
    implicitHeight: unit
    opacity: (badge.locked && !badge.arming) ? 0.45 : 1
    // A button gives under a thumb, so the badge does. Not while it is
    // counting down: the tremble owns the badge's movement then, and two
    // reasons to move at once read as neither.
    scale: (badge.down && !badge.arming) ? 0.92 : 1
    // Leaning rather than moving: a transform, not `x`, because the badge is
    // laid out by a Row and an assigned x would fight it.
    transform: Translate { x: badge.leaned }

    Behavior on scale { NumberAnimation { duration: 90; easing.type: Easing.OutCubic } }

    // Where the countdown has got to, entered from wherever the badge
    // currently is rather than from the step it just took. A signal handler
    // alone could not do it: this row is a Repeater, every button event
    // repaints the bar, and a badge rebuilt mid-hold is born past the
    // transition it needed to see - so it drew a dimmed, empty badge for the
    // rest of the hold. Called on completion as well as on each change, so a
    // badge that arrives already counting down picks the hold up.
    function enterHold() {
      if (badge.armed) {
        // The tick: the ramp has just reached full and stays there. Filling a
        // second time said "again" where the gesture says "still" - it read
        // as a second, separate wait rather than as the same one about to
        // end. What the confirm window gets instead is the badge straining in
        // the direction the press is about to move things, which is what
        // something about to happen looks like and says which way in the same
        // breath.
        lap.stop()
        filling.swept = 1
        if (root.trembleReach > 0 && root.trembleMs > 0) tremble.restart()
      } else if (badge.arming) {
        lapWait.duration = badge.lapWaitMs
        lapRamp.duration = badge.lapRampMs
        // Explicitly, before the pause rather than by the ramp's `from`: the
        // badge holds whatever it last swept to for as long as the pause
        // lasts, and a second hold would spend that wait looking full.
        filling.swept = 0
        lap.restart()
      } else {
        lap.stop()
        tremble.stop()
        filling.swept = 0
        badge.leaned = 0
      }
    }

    Component.onCompleted: badge.enterHold()
    onArmingChanged: badge.enterHold()
    onArmedChanged: badge.enterHold()

    SequentialAnimation {
      id: tremble
      loops: Animation.Infinite

      NumberAnimation {
        target: badge
        property: "leaned"
        to: root.trembleReach * (badge.lean !== 0 ? badge.lean : 1)
        duration: Math.max(1, Math.round(root.trembleMs / 2))
        easing.type: Easing.InOutSine
      }
      NumberAnimation {
        target: badge
        property: "leaned"
        // A badge that points somewhere only ever leans that way and comes
        // back; one that points nowhere swings through centre to the other
        // side, so it still reads as a tremble rather than as a nudge.
        to: badge.lean !== 0 ? 0 : -root.trembleReach
        duration: Math.max(1, Math.round(root.trembleMs / 2))
        easing.type: Easing.InOutSine
      }
    }

    // The dimming waits with the fill and then walks off over what is left of
    // the hold: brightness and fill are one statement about the same wait, and
    // one of them moving while the other sits still read as a stutter.
    Behavior on opacity {
      SequentialAnimation {
        PauseAnimation { duration: badge.arming ? badge.lapWaitMs : 0 }

        NumberAnimation {
          duration: badge.arming ? badge.lapRampMs : 140
          easing.type: Easing.Linear
        }
      }
    }

    // Filled in the text's own colour, at the weight the guide gives it: the
    // silhouette is what says which button this is, and a line around it read
    // as a frame rather than as part of the drawing. The stick's rim is not
    // that line - it is the drawing - so it keeps its own colour.
    BadgeArt {
      anchors.fill: parent
      drawn: badge.art
      fill: Util.alpha(root.foreground, badge.lit)
      ink: root.foreground
      ringColor: root.foreground
      ringWidth: Math.max(1, metrics.space(1))

      // Long enough to be seen as a change, short enough that a tap still
      // reads as a tap rather than as a glow that arrives after the press.
      Behavior on fill { ColorAnimation { duration: 90 } }
    }

    // A counted-down hold fills the badge in from the left, the way anything
    // that takes a moment fills. It replaces an outline that used to thicken:
    // a line growing heavier says something is happening, a bar filling says
    // how much longer - and how much longer is the whole point of announcing
    // a hold. The same badge drawn a second time, brighter, behind a window
    // that widens: no mask, no second shape to keep in step, and the label is
    // painted again in the same ink so the sweep crosses it without a seam.
    //
    // It fills once and once only, over what is left of `hold_ms` once the
    // opening wait is out of the way (`lapWaitMs`). The confirm window that
    // follows is the same wait continuing, so the badge stays full through it
    // and trembles instead; see `onArmedChanged`.
    Item {
      id: filling

      property real swept: 0

      anchors.left: parent.left
      anchors.top: parent.top
      width: Math.round(badge.width * filling.swept)
      height: badge.height
      clip: true
      visible: badge.arming

      SequentialAnimation {
        id: lap

        PauseAnimation { id: lapWait }

        NumberAnimation {
          id: lapRamp
          target: filling
          property: "swept"
          from: 0
          to: 1
          easing.type: Easing.Linear
        }
      }

      BadgeArt {
        width: badge.width
        drawn: badge.art
        // Over the badge's own fill, not instead of it: enough to read as
        // filled, not so much that the label sinks into it.
        fill: Util.alpha(root.foreground, 0.45)
        ink: root.foreground
        ringColor: root.foreground
        ringWidth: Math.max(1, metrics.space(1))
      }
    }

    Text {
      id: typed
      visible: badge.drawn === null
      // On whole pixels rather than centred by the anchors: a label that
      // lands on a half pixel is blurred, and on a bar read from a sofa that
      // is the first thing to go.
      width: badge.width - Math.round(badge.unit * 0.24)
      height: Math.ceil(typed.implicitHeight)
      x: Math.round((badge.width - typed.contentWidth) / 2)
      y: Math.round((badge.implicitHeight - typed.height) / 2) + root.capNudge
      // Sized off the badge rather than off the type scale, so a three
      // character label still fits the shape one letter does - by being
      // squeezed to the width at one shared size, not by stepping down a
      // size, which made a row of badges read as two type sizes.
      text: badge.label
      color: root.foreground
      font.family: buttonArt.family
      font.pixelSize: Math.round(badge.unit * 0.44)
      fontSizeMode: Text.HorizontalFit
      minimumPixelSize: Math.max(6, Math.round(badge.unit * 0.26))
      font.weight: Font.Medium
    }
  }

  PanelWindow {
    id: panel
    visible: root.opened
    anchors {
      top: root.edge === "top"
      bottom: root.edge === "bottom"
      left: true
      right: true
    }
    implicitHeight: root.barHeight
    color: "transparent"
    WlrLayershell.namespace: "omapad-gamebar"
    WlrLayershell.layer: WlrLayer.Top
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    exclusionMode: ExclusionMode.Auto
    // The strip takes the pointer while its badges can answer one, and
    // nothing at all when they cannot - `[gamebar] click = false` gives back
    // the bar this was before it was clickable, a readout a click goes
    // straight through. It is the whole strip rather than the badges alone
    // because a mask is one region here: nested `Region`s do not union in this
    // Quickshell, and the bar reserves its own strip anyway (`ExclusionMode`),
    // so what a click on the empty half of it would otherwise have reached is
    // the wallpaper.
    mask: Region { item: root.clickable ? bar : null }

    Rectangle {
      id: bar

      anchors.fill: parent
      color: root.barTransparent ? "transparent" : Color.bar.background

      // Left: the door, and which button walks through it. Drawn only when
      // omapad says a button really opens it. The clock is inside the menu
      // rather than beside it: two things at this end read as clutter.
      Row {
        id: left
        anchors.left: parent.left
        anchors.leftMargin: root.sideMargin
        anchors.verticalCenter: parent.verticalCenter
        spacing: metrics.space(16)

        // One button, not a button and a caption: the pad's own mark and the
        // word for what it opens sit inside a single system pill, stretched
        // to hold both. A badge with a label beside it read as two things at
        // the one end of the bar where there is only ever one.
        Rectangle {
          id: door

          readonly property var drawn:
            root.menu ? buttonArt.find("system", root.menu.b) : null
          // The button under the mark: the door is a badge like any other
          // here, so it answers a thumb and a pointer the same way.
          readonly property string name: root.menu ? String(root.menu.n || "") : ""
          readonly property bool down: doorClick.pressed || root.isDown(door.name)

          // How much of a pixel one drawn unit is worth here. Rounded to a
          // half, and never below one: the mark is the only drawing on the
          // bar painted on its own rather than inside its badge, and a menu
          // mark is three parallel bars - at 2.7 pixels each, two of them
          // land one side of the pixel grid and the third the other, and the
          // icon reads as broken rather than as soft. On a half the drawing's
          // own whole units stay whole.
          readonly property real markScale: door.drawn
            ? Math.max(0.5, Math.round(root.badgeUnit * buttonArt.capRatio
                                       / door.drawn.mh * 2) / 2)
            : 1

          anchors.verticalCenter: parent.verticalCenter
          visible: root.menu !== null && root.menu !== undefined
          // As tall as a face button, not as tall as the little pill the mark
          // is drawn on: this is the one thing at this end of the bar, and at
          // the system pill's own height it read as an afterthought beside
          // the badges across from it.
          height: root.badgeUnit
          // Room enough that the mark and the word clear the round ends: at
          // half the height the content starts exactly where the cap stops
          // curving, which reads as touching it, so there is a little past
          // that on each side.
          width: Math.round(inside.width + height * 1.15)
          radius: height / 2
          color: Util.alpha(root.foreground, door.down
            ? root.downLit
            : (doorClick.containsMouse ? root.hoverLit : root.restLit))
          // Less than a badge gives, for the same travel in pixels: this pill
          // is several badges wide, and the same factor would swing it.
          scale: door.down ? 0.96 : 1

          Behavior on color { ColorAnimation { duration: 90 } }
          Behavior on scale { NumberAnimation { duration: 90; easing.type: Easing.OutCubic } }

          Click {
            id: doorClick
            button: door.name
          }

          Row {
            id: inside
            anchors.centerIn: parent
            spacing: metrics.space(6)

            // The mark alone. It is drawn on the pill's own grid and centred
            // in it, so the whole badge is painted with its shape left out
            // and cropped to the middle - the pill around it is this
            // rectangle, and two pills would be a button inside a button.
            Item {
              id: mark

              anchors.verticalCenter: parent.verticalCenter
              // The mark's own ink and nothing else: the generator says how
              // wide it is, so the word sits beside the mark rather than
              // beside the empty half of the pill it is drawn on.
              width: door.drawn ? Math.round(door.drawn.mw * door.markScale) : 0
              height: door.height
              clip: true
              visible: door.drawn !== null

              BadgeArt {
                // The whole badge, painted with its shape left out and its
                // mark placed on whole pixels over this window.
                width: door.drawn ? door.drawn.w * door.markScale : 0
                x: door.drawn
                  ? Math.round(-door.drawn.mx * door.markScale) : 0
                y: door.drawn
                  ? Math.round((mark.height - door.drawn.mh * door.markScale)
                               / 2 - door.drawn.my * door.markScale)
                  : 0
                drawn: door.drawn
                ink: root.foreground
              }
            }

            // Fira Code, upper case, and exactly as tall as the mark beside
            // it: the word is inside the button, so it is legend and not
            // prose, and a legend a pixel taller than the mark it is next to
            // reads as two things that were sized separately.
            //
            // Sized off the mark rather than off the badge, because the mark
            // is snapped to whole pixels and the badge is not: matching the
            // badge would put the two a pixel apart at most sizes. `capSize`
            // over `capRatio` turns a cap height into a font size, both
            // generated from what the drawn labels are punched at.
            Text {
              anchors.verticalCenter: parent.verticalCenter
              text: "MENU"
              color: root.foreground
              font.family: buttonArt.family
              font.pixelSize: Math.round(
                (door.drawn ? door.drawn.mh * door.markScale
                            : root.badgeUnit * buttonArt.capRatio)
                * buttonArt.capSize / buttonArt.capRatio)
              font.weight: Font.Medium
            }
          }
        }
      }

      // Centre: the workspaces, drawn as Omarchy draws them - the focused one
      // becomes a dot, an empty one is dimmed - with the buttons that step
      // between them at either end. A button next to what it moves needs no
      // words.
      Row {
        anchors.centerIn: parent
        spacing: metrics.space(10)

        Badge {
          anchors.verticalCenter: parent.verticalCenter
          visible: root.wsprev !== null && root.wsprev !== undefined
          label: root.wsprev ? root.wsprev.b : ""
          kind: root.wsprev ? root.wsprev.k : "trigger"
          name: root.wsprev ? String(root.wsprev.n || "") : ""
          locked: root.wsprev ? !!root.wsprev.locked : false
          hovered: prevClick.containsMouse
          held: prevClick.pressed
          // Towards the workspace it walks to, which is the one on its side
          // of the strip.
          lean: -1

          // Locked means the app in front has the plain press and the
          // workspace is behind the announced hold - which is a fact about
          // the pad, not about the pointer: a click is aimed, so it walks the
          // workspace the badge is pointing at either way.
          Click {
            id: prevClick
            button: root.wsprev ? String(root.wsprev.n || "") : ""
            holdOnly: root.wsprev ? !!root.wsprev.locked : false
          }
        }

        Row {
          anchors.verticalCenter: parent.verticalCenter
          spacing: metrics.space(2)

          Repeater {
            model: root.workspaceIds
            delegate: Item {
              required property int modelData

              readonly property bool focused: modelData === root.active

              width: metrics.space(24)
              height: root.badgeUnit

              Text {
                anchors.centerIn: parent
                text: parent.focused
                  ? root.focusedGlyph
                  : (parent.modelData === 10 ? "0" : String(parent.modelData))
                color: root.foreground
                opacity: parent.focused || root.occupied(parent.modelData) ? 1 : 0.5
                font.family: metrics.font.family
                font.pixelSize: metrics.font.body
              }
            }
          }
        }

        Badge {
          anchors.verticalCenter: parent.verticalCenter
          visible: root.wsnext !== null && root.wsnext !== undefined
          label: root.wsnext ? root.wsnext.b : ""
          kind: root.wsnext ? root.wsnext.k : "trigger"
          name: root.wsnext ? String(root.wsnext.n || "") : ""
          locked: root.wsnext ? !!root.wsnext.locked : false
          hovered: nextClick.containsMouse
          held: nextClick.pressed
          lean: 1

          Click {
            id: nextClick
            button: root.wsnext ? String(root.wsnext.n || "") : ""
            holdOnly: root.wsnext ? !!root.wsnext.locked : false
          }
        }
      }

      // Right: what the thumbs can do, in the order the thumbs find them.
      Row {
        anchors.right: parent.right
        anchors.rightMargin: root.sideMargin
        anchors.verticalCenter: parent.verticalCenter
        spacing: metrics.space(16)

        Text {
          visible: root.note.length > 0
          anchors.verticalCenter: parent.verticalCenter
          text: visible ? root.note : ""
          color: root.foreground
          opacity: 0.45
          font.family: metrics.font.family
          font.pixelSize: metrics.font.bodySmall
        }

        Repeater {
          model: root.actions
          // An Item around the row rather than the row itself: the click
          // surface has to lie over the badge *and* its words, and a
          // MouseArea inside a Row would be laid out as another column of
          // it.
          delegate: Item {
            id: hint
            required property var modelData

            readonly property bool holdOnly: (!modelData.d || modelData.d.length === 0)
              && modelData.h && modelData.h.length > 0

            implicitWidth: hintRow.implicitWidth
            implicitHeight: hintRow.implicitHeight

            Row {
              id: hintRow
              anchors.fill: parent
              spacing: metrics.space(7)

              Badge {
                anchors.verticalCenter: parent.verticalCenter
                label: hint.modelData.b
                kind: hint.modelData.k
                name: String(hint.modelData.n || "")
                hovered: hintClick.containsMouse
                held: hintClick.pressed
              }

              Text {
                anchors.verticalCenter: parent.verticalCenter
                // A binding game mode only honours as a hold says so, rather
                // than reading as something a tap would do.
                text: hint.holdOnly ? "hold · " + hint.modelData.h : hint.modelData.d
                color: root.foreground
                opacity: 0.85
                font.family: metrics.font.family
                font.pixelSize: metrics.font.bodySmall
              }
            }

            // The whole hint, badge and words together: the words are what
            // says which one this is, and a target picked out from a sofa
            // wants to be the size of the thing you are reading.
            Click {
              id: hintClick
              button: String(hint.modelData.n || "")
              holdOnly: hint.holdOnly
              offered: hint.modelData.c !== false
            }
          }
        }
      }
    }
  }

  // Game mode is on, so the screen is being watched from across the room:
  // nothing on the bar produces input of its own, and a click on a badge is
  // the desk's pointer rather than a sign of anyone in front of the screen.
  IdleInhibitor {
    window: panel
    enabled: root.opened
  }
}
