// Controller HUD for omapad: a head, a bar of groups, and a grid of tiles.
//
// A pure view, the same split the keyboard uses: omapad owns the tree, the
// selection, the drill-down stack and - because a tile that changes size
// re-packs the page under it - where every tile sits. One JSON line per update
// arrives over a unix socket and this panel draws it. What a person does with
// the desktop - arrow keys, Enter, a cursor - comes back the other way over
// the same control socket a terminal would use, so the pad and the desk drive
// the same selection.
//
// It was one column for a long time, shaped like the Omarchy menu, and that
// was right while every row was a verb: a list says every row is worth the
// same, and a D-pad walks one well. A tile that holds a value is not worth the
// same as a tile beside it, and saying so is what a grid is for. What it costs
// is the card's width - the Omarchy menu's 320 has nowhere to put six columns
// - and that is the one measurement here that no longer matches it.
//
// Unlike the keyboard and the guide, which stay pad-only, this surface takes
// the keyboard and the pointer while it is open, the way the Omarchy menu
// does: Exclusive focus so the arrows reach it rather than the window under
// the scrim, hover to select, a click to pick, a click outside to leave.
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons
import qs.Ui

Item {
  id: root

  property bool opened: false
  property var items: []
  property var groups: []
  property var head: []
  // What each face button does on this page, already worded by the daemon.
  property var keys: []
  // Where the watched thumb is, at up to `[menu] live_hz`. Its own short
  // line, carrying no `items` at all, so `applyState` never reaches `fresh()`
  // and no delegate is rebuilt - one binding re-runs instead of twenty tiles
  // being built sixty times a second.
  //
  // NOTHING HERE MAY BIND A LAYOUT WIDTH OR HEIGHT TO `root.live`. A layout
  // pass at frame rate throws away everything that buys. Only `x`, `y`,
  // `scale`, `opacity` and colours.
  property var live: ({ x: 0, y: 0 })
  // Whether the page in front is being rearranged, and which tile is being
  // carried. Both are the daemon's: the model holds the arrangement, and this
  // only draws what it is told.
  property bool editing: false
  property string picked: ""
  // Which way a badge is drawn, from the daemon: the same question the guide
  // and the bar answer, and it has to be answered the same way here or one
  // surface prints its buttons unlike the other two.
  property string badgeStyle: "filled"
  readonly property bool stencil: root.badgeStyle === "stencil"
  property string title: ""
  property string clock: ""
  // The selection is a name, not a number: a tile changing size re-packs the
  // page under it, so an index is stale the moment it is used.
  property string sel: ""
  property int group: 0
  property int depth: 0
  property int cols: 6
  property int rows: 1
  property int headRows: 0

  // $XDG_RUNTIME_DIR is per-user and 0700, and that is the only thing
  // keeping another user off this socket. Without it there is nowhere
  // private to bind, so bind nowhere: a socket under /tmp is one anybody
  // on the machine can plant first and read what this surface is sent.
  readonly property string socketDir: Quickshell.env("XDG_RUNTIME_DIR")
    ? Quickshell.env("XDG_RUNTIME_DIR") + "/omapad" : ""

  // How big this surface draws, from the daemon: the desktop is read at a
  // keyboard and game mode from a sofa, so the scale follows the mode rather
  // than the session. Every measurement below goes through `metrics`.
  property real uiScale: 1.0

  // Whether omapad's own bar is holding a strip of the screen under this.
  // The scrim dims the desktop the menu stands in front of, and the bar is
  // not that desktop: while the menu is up it prints what A, B and X do *in
  // the menu*. A legend read through a scrim is the last thing that should go
  // dark, so the window steps out of the strip rather than covering it.
  property bool overBar: false

  Metrics {
    id: metrics
    scale: root.uiScale
  }

  // The drawn buttons, and the font their labels are set in.
  ButtonArt {
    id: buttonArt
  }

  // The parts a control tile is drawn from. Only the furniture is here - what
  // follows the value is geometry, and geometry is this side's.
  ControlArt {
    id: controlArt
  }

  readonly property int badgeUnit: metrics.badge(
    Math.max(metrics.space(18), metrics.font.bodySmall + metrics.space(7)))

  // A typed badge label centred in its shape is centred by its *line box*,
  // and the line box is not centred on the capitals inside it - the letter
  // comes out about a pixel high. The correction is a font metric rather than
  // a taste, so it is measured: a probe laid out with the label's own font,
  // and the ink box of a capital inside it. Only the typed fallback needs it;
  // a drawn label was placed by the shape it sits in.
  Text {
    id: capProbe
    visible: false
    text: "H"
    textFormat: Text.PlainText
    font.family: buttonArt.family
    font.pixelSize: metrics.font.caption
    font.weight: Font.Medium
  }
  TextMetrics {
    id: capInk
    font: capProbe.font
    text: capProbe.text
  }
  readonly property int capNudge: Math.round(
    capProbe.height / 2 - capProbe.baselineOffset
    - (capInk.tightBoundingRect.y + capInk.tightBoundingRect.height / 2))

  readonly property int contentMargin: metrics.spacing.panelPadding
  readonly property int contentSpacing: metrics.spacing.md
  readonly property int headerHeight: Math.max(metrics.space(34),
    metrics.font.title + metrics.spacing.controlPaddingY * 2)
  readonly property int chipHeight: Math.max(metrics.space(38),
    metrics.font.body + metrics.spacing.controlPaddingY * 2)
  readonly property int legendHeight: root.keys.length > 0
    ? Math.max(root.badgeUnit, metrics.font.caption) + metrics.space(6) : 0
  // The gap between tiles, and the height of one cell. A cell is taller than
  // it is wide on purpose: a tile carries an icon over a label, and a square
  // one leaves the label nowhere to go on a six-column card.
  readonly property int cellGap: metrics.spacing.xs
  readonly property int cellHeight: metrics.space(68)
  readonly property var selectedBorderSpec: Border.surfaceSpec(
    "menu", "selected-border", Color.menu.selectedBorder, 0)

  readonly property int cellWidth: {
    var inner = card.width - card.borderLeft - card.borderRight
      - root.contentMargin * 2
    return Math.max(1, Math.floor(
      (inner - root.cellGap * (root.cols - 1)) / root.cols))
  }

  function cellX(x) { return x * (root.cellWidth + root.cellGap) }
  function cellY(y) { return y * (root.cellHeight + root.cellGap) }
  function cellSpan(n) {
    return n * root.cellWidth + (n - 1) * root.cellGap
  }
  function rowsHeight(n) {
    return n > 0 ? n * root.cellHeight + (n - 1) * root.cellGap : 0
  }

  // A card that swallows the screen reads as a page rather than a menu, so a
  // long group scrolls behind the fold instead of growing past this. Cut to
  // whole rows: clamping the height alone puts the fold through the middle of
  // a tile, which reads as bad padding rather than as "there is more below".
  readonly property int gridHeight: {
    var cap = Math.round(panel.height * 0.55)
    var whole = Math.max(1, Math.floor(
      (cap + root.cellGap) / (root.cellHeight + root.cellGap)))
    return root.rowsHeight(Math.max(1, Math.min(root.rows, whole)))
  }

  // omapad re-sends the whole payload every VIEW_HEARTBEAT seconds, so a
  // restarted shell repaints itself with no handshake - which means most
  // lines that arrive here say nothing new. Re-applying one is not free: a
  // `var` property never compares equal to its old value, so assigning it
  // re-runs every binding that reads it, and where it is a Repeater's model
  // it destroys and rebuilds every delegate under it. A fresh component's
  // `lastLine` is empty, so a restarted shell still paints what it is given.
  property string lastLine: ""
  property var seen: ({})

  function fresh(key, value) {
    var line = JSON.stringify(value)
    if (line === root.seen[key]) return false
    root.seen[key] = line
    return true
  }

  // What the grid was last scrolled to. Guarded because `reveal` runs on
  // every arriving line and the heartbeat brings two a second: scrolling to
  // where the selection already is costs an animation nobody asked for.
  property string revealed: ""

  function applyState(text) {
    if (text === root.lastLine) return
    root.lastLine = text
    try {
      var s = JSON.parse(text)
      // First, so a scale change lands even if a later field throws.
      if (s.scale !== undefined) root.uiScale = Number(s.scale) || 1
      if (s.bar !== undefined) root.overBar = !!s.bar
      if (s.cols !== undefined) root.cols = Number(s.cols) || 6
      if (s.rows !== undefined) root.rows = Number(s.rows) || 1
      if (s.headrows !== undefined) root.headRows = Number(s.headrows) || 0
      if (s.badge !== undefined) root.badgeStyle = String(s.badge)
      if (s.keys !== undefined && root.fresh("keys", s.keys))
        root.keys = s.keys
      if (s.items !== undefined && root.fresh("items", s.items))
        root.items = s.items
      if (s.groups !== undefined && root.fresh("groups", s.groups))
        root.groups = s.groups
      if (s.head !== undefined && root.fresh("head", s.head))
        root.head = s.head
      if (s.title !== undefined) root.title = s.title
      if (s.clock !== undefined) root.clock = s.clock
      if (s.depth !== undefined) root.depth = s.depth
      if (s.g !== undefined) root.group = Number(s.g) || 0
      if (s.sel !== undefined) root.sel = String(s.sel)
      if (s.live !== undefined) root.live = s.live
      if (s.edit !== undefined) root.editing = !!s.edit
      if (s.pick !== undefined) root.picked = String(s.pick)
      if (s.open !== undefined) root.opened = !!s.open
      Qt.callLater(root.reveal)
    } catch (e) {}
  }

  // Keep the current chip on screen once the bar is wider than the card, and
  // the selection on screen once the grid is taller than the fold.
  //
  // Both are driven from here rather than from the delegates, and both are
  // re-run when the geometry changes rather than only when the state does. A
  // delegate is laid out after it is built, so a scroll worked out at
  // construction is worked out against a width of nothing - and the answer
  // stuck, which is how a grid that fits ended up scrolled past its own last
  // row with everything above it off screen.
  function followChip() {
    if (bar.width <= 0) return
    for (var i = 0; i < chips.children.length; i++) {
      var chip = chips.children[i]
      if (chip.here === undefined || !chip.here) continue
      if (chip.x < bar.contentX)
        bar.contentX = chip.x
      else if (chip.x + chip.width > bar.contentX + bar.width)
        bar.contentX = chip.x + chip.width - bar.width
      return
    }
  }

  function settleBar() {
    var most = Math.max(0, bar.contentWidth - bar.width)
    bar.contentX = Math.max(0, Math.min(bar.contentX, most))
    root.followChip()
  }

  function settleGrid() {
    var most = Math.max(0, grid.contentHeight - grid.height)
    grid.contentY = Math.max(0, Math.min(grid.contentY, most))
  }

  onGroupChanged: Qt.callLater(root.followChip)

  function reveal() {
    if (grid.height <= 0) return
    if (root.sel === root.revealed) return
    root.revealed = root.sel
    for (var i = 0; i < root.items.length; i++) {
      if (root.items[i].id !== root.sel) continue
      var top = root.cellY(root.items[i].y)
      var bottom = top + root.rowsHeight(root.items[i].h)
      if (top < grid.contentY)
        grid.contentY = top
      else if (bottom > grid.contentY + grid.height)
        grid.contentY = bottom - grid.height
      return
    }
  }

  onOpenedChanged: {
    if (root.opened) {
      // The pad (or a summon) chose where the selection starts; a stationary
      // cursor must not take it from there, and the surface needs the key
      // focus the window rules give it.
      root.pointerArm()
      Qt.callLater(function() { keyCatcher.forceActiveFocus() })
    }
  }

  // -- the way back: what a person does with the keyboard and the mouse -----
  //
  // The pad drives the menu over its push socket below; a keyboard and a
  // cursor have no such channel, and the selection still lives in the daemon.
  // So this panel drives it instead, one short command per input over the
  // same control socket `omapad ctl` uses - `menu left`, `menu select 3`,
  // `menu group 2`. Commands are fire-and-forget: the answer to every one
  // comes back as a fresh line on menu.sock, so there is nothing to wait for.
  readonly property string controlSock:
    root.socketDir ? root.socketDir + "/control.sock" : ""
  property var commands: []
  // The shell holds one connection open and streams commands; the daemon
  // answers each line and keeps the connection, so a key never pays for a
  // fresh connect-and-hang-up, and a held arrow's auto-repeat drains in one
  // write instead of one round trip per press.
  property bool ctlDown: false

  Socket {
    id: ctl
    path: root.controlSock
    connected: false
    parser: SplitParser {
      splitMarker: "\n"
      // Replies are status lines; they tell this surface nothing it does
      // not already know. Reading them keeps the stream from growing.
      onRead: function(line) {}
    }
    onConnectionStateChanged: {
      if (ctl.connected) {
        root.ctlDown = false
        root.flushCommands()
      } else if (root.commands.length > 0 && !root.ctlDown) {
        ctl.connected = true
      }
    }
    onError: {
      // The daemon is down or the socket has gone: keep the queue and try
      // again in a moment rather than spinning on a connect that cannot
      // succeed.
      root.ctlDown = true
      ctlRetry.restart()
    }
  }

  Timer {
    id: ctlRetry
    interval: 500
    repeat: false
    onTriggered: {
      root.ctlDown = false
      if (root.commands.length > 0 && !ctl.connected)
        ctl.connected = true
    }
  }

  function flushCommands() {
    if (!ctl.connected || root.commands.length === 0) return
    // Batch: every queued command goes in one write. Auto-repeat queued this
    // turn, so one write is one wakeup for the daemon, not one per press.
    var joined = root.commands.join("\n") + "\n"
    root.commands = []
    ctl.write(joined)
  }

  function send(command) {
    root.commands.push(command)
    if (ctl.connected)
      root.flushCommands()
    else
      ctl.connected = true
  }

  // -- the pointer ----------------------------------------------------------
  //
  // A cursor names the tile it is over and the daemon makes it the selection.
  // But a menu that opens with the cursor already on a tile must not hand the
  // selection to it - the pad put it somewhere on purpose - and a cursor that
  // never moves (whose hover events are really delegates rebuilding under
  // it) must never become one. So the first sample never selects, and
  // samples count only once the cursor has actually travelled. Every keyboard
  // move re-arms it, so the two drivers cannot fight over the selection.
  property bool pointerPrimed: false
  property bool pointerInitial: false
  property real pointerX: 0
  property real pointerY: 0

  function pointerArm() {
    root.pointerPrimed = false
    root.pointerInitial = false
    root.pointerX = 0
    root.pointerY = 0
  }

  // The pointer itself moved the selection - a click - so the tile under the
  // cursor is the one the next sample may take.
  function pointerAllowSample() {
    root.pointerPrimed = false
    root.pointerInitial = true
    root.pointerX = 0
    root.pointerY = 0
  }

  function pointerMoved(item, mouse) {
    var point = item.mapToItem(card, mouse.x, mouse.y)
    var first = !root.pointerPrimed
    var moved = first
      ? root.pointerInitial
      : (Math.abs(point.x - root.pointerX) > 1
        || Math.abs(point.y - root.pointerY) > 1)
    if (first || moved) {
      root.pointerX = point.x
      root.pointerY = point.y
    }
    root.pointerPrimed = true
    return moved
  }

  function pointerSelect(index, item, mouse) {
    if (!root.pointerMoved(item, mouse)) return
    if (root.items[index] && root.items[index].id === root.sel) return
    root.send("menu select " + index)
  }

  // A click is a decision, not a sample: it lands on the tile it lands on,
  // and the daemon is told the tile and the press in one go.
  function pointerActivate(index) {
    root.send("menu select " + index)
    root.send("menu press")
    root.pointerAllowSample()
  }

  // omapad connects here and streams state; both ends keep trying, so the
  // shell and the daemon can start or restart in either order.
  SurfaceSocket {
    dir: root.socketDir
    name: "menu.sock"
    onLine: text => root.applyState(text)
  }

  IpcHandler {
    target: "omapad-menu"
    function state(): string { return root.opened ? "open" : "closed" }
    function socket(): string { return root.socketDir + "/menu.sock" }
    function ping(): string { return "ok" }
  }

  // One drawn button. The same silhouettes the guide and the bar print, from
  // the same generated art, because a face button drawn three ways on three
  // surfaces is three buttons as far as the eye is concerned.
  component Badge: Item {
    id: badge

    property string label: ""
    property string kind: "face"

    readonly property int unit: root.badgeUnit
    // `drawn` is the whole badge down to the label set into it; `bare` is the
    // shape alone, for a label no pad here prints and for the system buttons,
    // which are one pill until something is typed into them.
    readonly property var drawn: buttonArt.find(badge.kind, badge.label)
    readonly property var bare: buttonArt.shape(badge.kind, badge.label)
    readonly property var art: badge.drawn !== null ? badge.drawn : badge.bare
    readonly property bool wide: badge.kind === "bumper"
      || badge.kind === "trigger" || badge.kind === "system"

    implicitWidth: badge.art !== null
      ? Math.round(badge.unit * badge.art.w / badge.art.h)
      : (badge.wide ? Math.round(badge.unit * 1.6) : badge.unit)
    implicitHeight: badge.unit
    width: implicitWidth
    height: implicitHeight

    BadgeArt {
      anchors.fill: parent
      drawn: badge.art
      fill: root.stencil ? Color.accent : Util.alpha(Color.accent, 0.30)
      ink: root.stencil ? "transparent" : Color.menu.text
      knockout: root.stencil
    }

    // Typed only where the drawing has no label of its own - a remapped
    // button, a pad printing something new. In the same Fira Code the drawn
    // labels are outlines of, so the two read as one set.
    Text {
      id: typed
      visible: badge.drawn === null
      // Placed on whole pixels rather than centred by the anchors: a text
      // item on a half pixel is the one blur antialiasing cannot help.
      width: badge.width - metrics.space(5)
      height: Math.ceil(typed.implicitHeight)
      x: Math.round((badge.width - typed.contentWidth) / 2)
      y: Math.round((badge.height - typed.height) / 2) + root.capNudge
      text: badge.label
      textFormat: Text.PlainText
      color: root.stencil ? Color.menu.background : Color.menu.text
      font.family: buttonArt.family
      font.pixelSize: metrics.font.caption
      fontSizeMode: Text.HorizontalFit
      minimumPixelSize: Math.max(6, metrics.font.caption - metrics.space(2))
      font.weight: Font.Medium
    }
  }

  PanelWindow {
    id: panel
    visible: root.opened
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    WlrLayershell.namespace: "omapad-menu"
    WlrLayershell.layer: WlrLayer.Overlay
    // The Omarchy menu's own focus mode: while the menu is up the keyboard
    // belongs to it, and a key reaches the window under the scrim only after
    // it goes away. Arrows and Enter navigate, and the game behind gets
    // nothing until the menu leaves.
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
    // Ignore, except where our own bar is up: `Normal` with the zero
    // exclusive zone it defaults to asks for what is left once every bar has
    // taken its strip, so the scrim stops where the game bar starts instead
    // of dimming the row of hints that answers this menu.
    exclusionMode: root.overBar ? ExclusionMode.Normal : ExclusionMode.Ignore

    // This is the one omapad surface that takes the pointer: hover selects a
    // tile, a click picks one, a click on the scrim leaves. The keyboard and
    // the guide still pass clicks through - they are pad-only by design.
    Rectangle {
      anchors.fill: parent
      color: Color.menu.scrim
      opacity: root.opened ? 1 : 0
      Behavior on opacity { NumberAnimation { duration: 110 } }
    }

    MouseArea {
      anchors.fill: parent
      onClicked: root.send("menu close")
    }

    BorderSurface {
      id: card
      anchors.centerIn: parent
      // Wider than the Omarchy menu's 320, which is the one measurement the
      // grid could not keep: six columns of anything readable do not fit in
      // a column's width.
      width: Math.min(metrics.space(560), parent.width - Style.gapsOut * 2)
      height: Math.min(
        card.borderTop + card.borderBottom + root.contentMargin * 2
          + (root.headRows > 0
             ? root.rowsHeight(root.headRows) + root.contentSpacing : 0)
          + root.headerHeight + root.contentSpacing
          + root.chipHeight + root.contentSpacing + root.gridHeight
          + (root.legendHeight > 0
             ? root.contentSpacing + root.legendHeight : 0),
        parent.height - Style.gapsOut * 2)
      color: Color.menu.background
      borderSpec: Border.surfaceSpec("menu", "border", Color.menu.border,
        Math.max(1, metrics.space(2)))
      radius: Style.cornerRadius
      opacity: root.opened ? 1 : 0
      Behavior on opacity { NumberAnimation { duration: 110 } }

      // Padding is not a dismissal: only the scrim is. A click on the card,
      // or in the gap between tiles, must not send the menu away.
      MouseArea {
        anchors.fill: parent
        onClicked: {}
      }

      // Where the keyboard lands. Everything a key means goes to the daemon
      // as a menu command, the same grammar the pad uses, so whichever hand
      // is driving, the selection lives in one place. The arrows walk the
      // grid - all four of them, now that left and right are not a second way
      // to say Back and Pick - Backspace climbs a level, Escape leaves
      // outright, and Tab walks the bar.
      Item {
        id: keyCatcher
        anchors.fill: parent
        focus: true
        Keys.priority: Keys.BeforeItem
        Keys.onPressed: function(event) {
          if (event.key === Qt.Key_Escape) {
            root.send("menu close")
          } else if (event.key === Qt.Key_Backspace) {
            root.send("menu back")
            root.pointerArm()
          } else if (event.key === Qt.Key_Left) {
            root.send("menu left")
            root.pointerArm()
          } else if (event.key === Qt.Key_Right) {
            root.send("menu right")
            root.pointerArm()
          } else if (event.key === Qt.Key_Up) {
            root.send("menu up")
            root.pointerArm()
          } else if (event.key === Qt.Key_Down) {
            root.send("menu down")
            root.pointerArm()
          } else if (event.key === Qt.Key_Tab) {
            root.send("menu group_next")
            root.pointerArm()
          } else if (event.key === Qt.Key_Backtab) {
            root.send("menu group_prev")
            root.pointerArm()
          } else if (event.key === Qt.Key_Home) {
            root.send("menu select 0")
            root.pointerArm()
          } else if (event.key === Qt.Key_End) {
            root.send("menu select " + Math.max(0, root.items.length - 1))
            root.pointerArm()
          } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter
              || event.key === Qt.Key_Space) {
            root.send("menu press")
            root.pointerArm()
          } else {
            return
          }
          event.accepted = true
        }
      }

      Column {
        anchors.fill: parent
        anchors.topMargin: card.borderTop + root.contentMargin
        anchors.rightMargin: card.borderRight + root.contentMargin
        anchors.bottomMargin: card.borderBottom + root.contentMargin
        anchors.leftMargin: card.borderLeft + root.contentMargin
        spacing: root.contentSpacing

        // The head: a grid of its own, and nothing on it is selectable. A
        // clock is not a button, and a cursor that can wander into one is a
        // cursor that has to come back out again.
        Item {
          width: parent.width
          height: root.rowsHeight(root.headRows)
          visible: root.headRows > 0

          Repeater {
            model: root.head

            delegate: Item {
              id: headCell
              required property var modelData

              x: root.cellX(headCell.modelData.x)
              y: root.cellY(headCell.modelData.y)
              width: root.cellSpan(headCell.modelData.w)
              height: root.rowsHeight(headCell.modelData.h)

              Text {
                anchors.fill: parent
                anchors.leftMargin: metrics.space(4)
                anchors.rightMargin: metrics.space(4)
                text: headCell.modelData.t
                textFormat: Text.PlainText
                color: Color.menu.text
                opacity: 0.72
                font.family: metrics.font.family
                font.pixelSize: metrics.font.subtitle
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
              }
            }
          }
        }

        // Where you are, and - since game mode takes Omarchy's bar away and
        // the pad can reach no other clock - whatever the head has no room
        // for. The clock here is empty in the shipped config: it moved up.
        Item {
          width: parent.width
          height: root.headerHeight

          Text {
            anchors.left: parent.left
            anchors.right: clockLabel.left
            anchors.rightMargin: metrics.space(8)
            anchors.verticalCenter: parent.verticalCenter
            // The trailing ellipsis is the Omarchy menu's own idiom for "this
            // is where you are, pick something".
            text: root.title + "…"
            textFormat: Text.PlainText
            color: Color.menu.text
            opacity: 0.58
            font.family: metrics.font.family
            font.pixelSize: metrics.font.heading
            elide: Text.ElideRight
          }

          Text {
            id: clockLabel
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            visible: root.clock.length > 0
            text: root.clock
            textFormat: Text.PlainText
            color: Color.menu.text
            opacity: 0.42
            font.family: metrics.font.family
            font.pixelSize: metrics.font.bodySmall
          }
        }

        // The bar. It stays drawn and stays on its chip while a submenu is
        // open, dimmed: a bar that vanished would resize the card under a
        // thumb that is aiming at a tile.
        Flickable {
          id: bar
          width: parent.width
          height: root.chipHeight
          contentWidth: chips.width
          contentHeight: height
          clip: true
          // The daemon owns which chip is current, so a drag here would be a
          // second answer to where you are. It scrolls only to follow one.
          interactive: false
          boundsBehavior: Flickable.StopAtBounds
          opacity: root.depth > 0 ? 0.38 : 1
          Behavior on opacity { NumberAnimation { duration: 110 } }
          Behavior on contentX { NumberAnimation { duration: 110 } }
          onWidthChanged: root.settleBar()
          onContentWidthChanged: root.settleBar()

          Row {
            id: chips
            height: bar.height
            spacing: metrics.spacing.xs

            Repeater {
              model: root.groups

              delegate: BorderSurface {
                id: chip
                required property int index
                required property var modelData

                readonly property bool here: chip.index === root.group

                width: chipLabel.implicitWidth + metrics.space(22)
                height: root.chipHeight
                radius: Style.cornerRadius
                color: chip.here
                  ? Color.menu.selectedBackground : "transparent"
                borderSpec: chip.here
                  ? root.selectedBorderSpec : Border.none()

                Text {
                  id: chipLabel
                  anchors.centerIn: parent
                  text: (chip.modelData.i && chip.modelData.i.length > 0
                         ? chip.modelData.i + "  " : "") + chip.modelData.l
                  textFormat: Text.PlainText
                  color: chip.here
                    ? Color.menu.selectedText : Color.menu.text
                  opacity: chip.here ? 1 : 0.62
                  font.family: metrics.font.family
                  font.pixelSize: metrics.font.body
                  font.weight: chip.here ? Font.Medium : Font.Normal
                }

                MouseArea {
                  anchors.fill: parent
                  cursorShape: Qt.PointingHandCursor
                  // A chip is walked to, not pressed: the daemon enters it
                  // and the next line says which page that was.
                  onClicked: root.send("menu group " + chip.index)
                }
              }
            }
          }
        }

        // The tiles. Absolutely positioned from the cells the daemon worked
        // out, inside a Flickable that only ever scrolls because `reveal`
        // moved it: the selection lives in the daemon, so a drag here would
        // be a second answer to where you are.
        Flickable {
          id: grid
          width: parent.width
          height: root.gridHeight
          contentWidth: width
          contentHeight: root.rowsHeight(root.rows)
          clip: true
          interactive: false
          boundsBehavior: Flickable.StopAtBounds

          Behavior on contentY { NumberAnimation { duration: 110 } }
          onHeightChanged: {
            root.settleGrid()
            root.revealed = ""
            Qt.callLater(root.reveal)
          }
          onContentHeightChanged: root.settleGrid()

          Repeater {
            model: root.items

            // Inlined rather than loaded: a `Component` declared beside this
            // one cannot see the delegate's own scope, and a tile that reads
            // its data through `parent` is the sort of scope lookup this
            // plugin has a rule against. When there is more than one kind to
            // draw, each becomes a file with `required property` inputs and
            // this becomes a Loader over them.
            delegate: BorderSurface {
              id: tile
              required property int index
              required property var modelData

              readonly property bool selected: tile.modelData.id === root.sel
              readonly property bool ticked: tile.modelData.on === true
              readonly property bool hasIcon: tile.modelData.i !== undefined
                && tile.modelData.i.length > 0

              x: root.cellX(tile.modelData.x)
              y: root.cellY(tile.modelData.y)
              width: root.cellSpan(tile.modelData.w)
              height: root.rowsHeight(tile.modelData.h)

              radius: Style.cornerRadius
              // A tile that is not selected still needs a ground. A row in a
              // column is bounded by the rows above and below it; a tile has
              // air on four sides, and six of them drawn on nothing read as a
              // scatter rather than as a grid.
              color: (tile.taken || tile.carried)
                ? Util.alpha(Color.accent, 0.32)
                : (tile.selected
                   ? Util.alpha(Color.accent, 0.20)
                   : Util.alpha(Color.menu.text, 0.06))
              // A tile that has been taken off the page is drawn where it
              // sits, faded, rather than moved anywhere: there is nothing to
              // go and find, and putting it back is the same press that took
              // it away.
              opacity: tile.off ? 0.32 : 1.0
              // An outline as well as a ground: a theme whose accent is close
              // to its surface would otherwise leave the selection to the
              // label alone, and the label is the smallest thing on the tile.
              borderSpec: tile.selected
                ? Border.flat(Color.accent, Math.max(1, metrics.space(
                    (tile.taken || tile.carried) ? 4 : 2)))
                : Border.none()

              readonly property bool holds: tile.modelData.k !== undefined
                && tile.modelData.k.length > 0
              // A control with a range, being adjusted right now: both axes
              // belong to it, which is the one state of this surface a press
              // means something else in, so it is drawn as one.
              readonly property bool slider: tile.modelData.k === "slider"
              readonly property bool media: tile.modelData.k === "media"
              readonly property bool gauge: tile.modelData.k === "gauge"
              // Being carried, or on the page only so it can be put back.
              readonly property bool carried:
                tile.modelData.id === root.picked && root.editing
              readonly property bool off: tile.modelData.off === true
              readonly property bool taken: tile.modelData.hd === true

              // One column, not two anchored groups: a tile is 1 cell tall
              // more often than not, and a name anchored to the top and a
              // control anchored to the bottom collide there rather than
              // stacking. A control tile also drops its icon - the control is
              // the picture, and a glyph over a switch is the tile saying the
              // same thing twice in the room it has for one.
              Column {
                anchors.centerIn: parent
                width: parent.width - metrics.space(12)
                spacing: metrics.space(2)

                Text {
                  visible: tile.hasIcon && !tile.holds
                  width: parent.width
                  horizontalAlignment: Text.AlignHCenter
                  text: tile.hasIcon ? tile.modelData.i : ""
                  textFormat: Text.PlainText
                  color: tile.selected
                    ? Color.menu.selectedText : Color.menu.text
                  font.family: metrics.font.family
                  font.pixelSize: metrics.font.iconLarge
                }

                Text {
                  visible: !tile.slider && !tile.media && !tile.gauge
                  width: parent.width
                  horizontalAlignment: Text.AlignHCenter
                  text: tile.modelData.l
                  textFormat: Text.PlainText
                  color: tile.selected
                    ? Color.menu.selectedText : Color.menu.text
                  font.family: metrics.font.family
                  font.pixelSize: metrics.font.bodySmall
                  font.weight: Font.Medium
                  elide: Text.ElideRight
                  maximumLineCount: 2
                  wrapMode: Text.WordWrap
                }

                Text {
                  width: parent.width
                  horizontalAlignment: Text.AlignHCenter
                  visible: !tile.media && tile.modelData.d !== undefined
                    && tile.modelData.d.length > 0 && tile.modelData.h > 1
                  text: visible ? tile.modelData.d : ""
                  textFormat: Text.PlainText
                  color: Color.menu.text
                  opacity: 0.52
                  font.family: metrics.font.family
                  font.pixelSize: metrics.font.caption
                  elide: Text.ElideRight
                }

                // A switch: the pill, and the knob that slides in it. The
                // travel is a binding rather than something a signal starts,
                // so a delegate rebuilt mid-flip is born where the state
                // already is - qml.md 5.5.
                Item {
                  id: switchArt
                  visible: tile.modelData.k === "toggle"
                  readonly property int unit: metrics.space(18)
                  width: Math.round(switchArt.unit * 64 / 40)
                  height: switchArt.unit
                  anchors.horizontalCenter: parent.horizontalCenter

                  BadgeArt {
                    anchors.fill: parent
                    drawn: controlArt.find("switch", "body")
                    fill: tile.modelData.on === true
                      ? Color.accent : Util.alpha(Color.menu.text, 0.22)
                  }

                  BadgeArt {
                    width: Math.round(parent.height * 0.78)
                    height: width
                    y: Math.round((parent.height - height) / 2)
                    x: tile.modelData.on === true
                      ? parent.width - width - Math.round(parent.height * 0.11)
                      : Math.round(parent.height * 0.11)
                    drawn: controlArt.find("switch", "knob")
                    fill: Color.menu.background
                    Behavior on x { NumberAnimation { duration: 110 } }
                  }
                }

                // A choice: the value between the two chevrons it is walked
                // with, drawn rather than typed so a row of them matches the
                // buttons on the same card.
                Row {
                  visible: tile.modelData.k === "choice"
                  spacing: metrics.space(5)
                  anchors.horizontalCenter: parent.horizontalCenter

                  BadgeArt {
                    width: metrics.space(9)
                    height: width
                    anchors.verticalCenter: parent.verticalCenter
                    drawn: controlArt.find("chev", "left")
                    fill: Util.alpha(Color.menu.text, 0.5)
                  }

                  Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: tile.modelData.t !== undefined
                      ? tile.modelData.t : ""
                    textFormat: Text.PlainText
                    color: Color.accent
                    font.family: metrics.font.family
                    font.pixelSize: metrics.font.caption
                    font.weight: Font.Medium
                  }

                  BadgeArt {
                    width: metrics.space(9)
                    height: width
                    anchors.verticalCenter: parent.verticalCenter
                    drawn: controlArt.find("chev", "right")
                    fill: Util.alpha(Color.menu.text, 0.5)
                  }
                }

                // A gauge: the dead zone as a shaded disc, and a dot where
                // the thumb is right now. The whole question a dead zone asks
                // is whether the stick crosses the shading, and no number
                // could ever answer it.
                //
                // The dot moves by `x` and `y` and the zone by `scale`, both
                // of which the graphics scene can do without a layout pass -
                // which is the only reason this can arrive at frame rate. See
                // the warning on `root.live`.
                Column {
                  id: dial
                  visible: tile.gauge
                  width: parent.width
                  spacing: metrics.space(2)

                  Item {
                    id: face
                    width: Math.min(parent.width, tile.height
                                    - metrics.space(30))
                    height: face.width
                    anchors.horizontalCenter: parent.horizontalCenter
                    // How far the dot may travel from the middle: the face's
                    // inner edge is 15 of its 20 radii and the dot is 4, so
                    // a stick all the way over sits against the rim rather
                    // than half through it.
                    readonly property real reach: face.width / 2 * 0.55

                    // The shaded zone, and the one part of a dial that is
                    // not drawn art: it is a circle of *variable* radius, and
                    // a drawing cannot stretch - the same argument the
                    // slider's track carries, one shape along.
                    //
                    // `z` rides on the full push, so binding a width to it
                    // costs a layout pass when the setting changes and never
                    // at frame rate.
                    Rectangle {
                      id: zone
                      readonly property real reach: face.width / 2 * 0.75
                      width: Math.max(2, Math.round(
                        zone.reach * 2 * (tile.modelData.z !== undefined
                                          ? tile.modelData.z : 0)))
                      height: zone.width
                      radius: zone.width / 2
                      anchors.centerIn: parent
                      color: Util.alpha(Color.accent, 0.20)
                    }

                    BadgeArt {
                      anchors.fill: parent
                      drawn: controlArt.find("dial", "face")
                      fill: Util.alpha(Color.menu.text, 0.3)
                    }

                    BadgeArt {
                      anchors.fill: parent
                      drawn: controlArt.find("dial", "ticks")
                      fill: Util.alpha(Color.menu.text, 0.3)
                    }

                    // The thumb, and the whole readout. A dead zone is a
                    // tenth of the travel, so drawn to scale it is a few
                    // pixels across the middle of the dial and nothing about
                    // it is legible - which is why the dot's *colour* is what
                    // answers the question rather than its position against a
                    // ring: dim while the stick is being swallowed, accent
                    // the moment it is not. Push the stick slowly and the
                    // moment it lights is the dead zone's edge, at any value
                    // and at any size.
                    BadgeArt {
                      id: thumb
                      // Only the tile in front is told where the thumb is -
                      // it is the only thing on this surface that streams -
                      // so an unselected dial shows its zone and no dot.
                      visible: tile.selected
                      readonly property real away: Math.min(1, Math.sqrt(
                        root.live.x * root.live.x
                        + root.live.y * root.live.y))
                      readonly property bool swallowed: thumb.away
                        <= (tile.modelData.z !== undefined
                            ? tile.modelData.z : 0)
                      width: parent.width
                      height: parent.height
                      x: face.reach * Math.max(-1, Math.min(1, root.live.x))
                      y: face.reach * Math.max(-1, Math.min(1, root.live.y))
                      drawn: controlArt.find("dial", "thumb")
                      fill: thumb.swallowed
                        ? Util.alpha(Color.menu.text, 0.45) : Color.accent
                    }
                  }

                  Text {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    text: tile.modelData.l + "  " + (
                      tile.modelData.t !== undefined ? tile.modelData.t : "")
                    textFormat: Text.PlainText
                    color: tile.selected
                      ? Color.menu.selectedText : Color.menu.text
                    font.family: metrics.font.family
                    font.pixelSize: metrics.font.caption
                    elide: Text.ElideRight
                  }
                }

                // What is playing: the mark for what it is doing, then the
                // title and the artist. The two lines are somebody else's
                // words and are as long as they are, so the tile is two cells
                // tall and they elide rather than the tile growing.
                Column {
                  id: playing
                  visible: tile.media
                  width: parent.width
                  spacing: metrics.space(2)

                  BadgeArt {
                    width: metrics.space(16)
                    height: width
                    anchors.horizontalCenter: parent.horizontalCenter
                    drawn: controlArt.find(
                      "media", tile.modelData.on === true ? "pause" : "play")
                    fill: tile.selected ? Color.accent
                                        : Util.alpha(Color.menu.text, 0.55)
                  }

                  Text {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    text: tile.modelData.l
                    textFormat: Text.PlainText
                    color: tile.selected
                      ? Color.menu.selectedText : Color.menu.text
                    font.family: metrics.font.family
                    font.pixelSize: metrics.font.bodySmall
                    font.weight: Font.Medium
                    elide: Text.ElideRight
                  }

                  Text {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    visible: tile.modelData.d !== undefined
                      && tile.modelData.d.length > 0
                    text: visible ? tile.modelData.d : ""
                    textFormat: Text.PlainText
                    color: Color.menu.text
                    opacity: 0.52
                    font.family: metrics.font.family
                    font.pixelSize: metrics.font.caption
                    elide: Text.ElideRight
                  }
                }

                // A slider: the name and the number on one line, the travel
                // under both. Nothing here is drawn art, deliberately - a
                // track is as wide as the tile it is in and a shape cannot
                // stretch, so `radius: height / 2` is the honest answer and a
                // pair of fixed-aspect end caps would not be.
                //
                // It carries its own name because a slider reads left to
                // right where every other tile reads down the middle, and a
                // centred label over a full-width bar looks like a caption
                // for something else.
                Column {
                  id: slider
                  visible: tile.slider
                  width: parent.width
                  spacing: metrics.space(3)

                  Item {
                    width: parent.width
                    height: sliderName.height

                    Text {
                      id: sliderName
                      anchors.left: parent.left
                      anchors.right: sliderValue.left
                      anchors.rightMargin: metrics.space(4)
                      text: tile.modelData.l
                      textFormat: Text.PlainText
                      color: tile.selected
                        ? Color.menu.selectedText : Color.menu.text
                      font.family: metrics.font.family
                      font.pixelSize: metrics.font.bodySmall
                      font.weight: Font.Medium
                      elide: Text.ElideRight
                    }

                    Text {
                      id: sliderValue
                      anchors.right: parent.right
                      anchors.baseline: sliderName.baseline
                      text: tile.modelData.t !== undefined
                        ? tile.modelData.t : ""
                      textFormat: Text.PlainText
                      color: Color.accent
                      font.family: metrics.font.family
                      font.pixelSize: metrics.font.caption
                      font.weight: Font.Medium
                    }
                  }

                  Rectangle {
                    id: sliderTrack
                    width: parent.width
                    height: Math.max(2, metrics.space(4))
                    radius: height / 2
                    color: Util.alpha(Color.menu.text, 0.18)

                    // The travel is a binding rather than something a signal
                    // starts, so a delegate rebuilt mid-push is born where
                    // the value already is - qml.md 5.5.
                    Rectangle {
                      height: parent.height
                      radius: parent.radius
                      width: Math.round(
                        parent.width * (tile.modelData.v !== undefined
                                        ? tile.modelData.v : 0))
                      color: Color.accent
                      Behavior on width { NumberAnimation { duration: 90 } }
                    }
                  }
                }
              }

              // The same slot says two things, and they never both apply:
              // `›` where a tile drills in, and a tick where a tile sets
              // something that is already what is in force - which is what
              // turns a page of choices into one that says where you are.
              // The mark a tile wears while it is being carried, in the
              // corner the tick and the chevron share - neither of which
              // means anything while a page is being rearranged.
              BadgeArt {
                visible: tile.carried
                width: metrics.space(10)
                height: width
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.rightMargin: metrics.space(5)
                anchors.topMargin: metrics.space(5)
                drawn: controlArt.find("tile", "grip")
                fill: Color.menu.selectedText
              }

              Text {
                visible: !root.editing
                text: tile.modelData.sub
                  ? "›" : (tile.ticked && !tile.holds ? "✓" : "")
                textFormat: Text.PlainText
                color: tile.selected
                  ? Color.menu.selectedText
                  : (tile.ticked ? Color.accent : Color.menu.text)
                opacity: tile.modelData.sub
                  ? 0.36 : (tile.ticked && !tile.holds ? 0.95 : 0)
                font.family: metrics.font.family
                font.pixelSize: metrics.font.body
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.rightMargin: metrics.space(6)
                anchors.topMargin: metrics.space(4)
              }

              // Hover names the tile under the cursor, a click picks it - the
              // daemon decides both, so this MouseArea only asks. The gate
              // keeps the stationary cursor (and the cursor the menu opened
              // under) from stealing a selection the pad chose.
              MouseArea {
                id: picker
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onEntered: root.pointerSelect(tile.index, tile, {
                  x: picker.mouseX,
                  y: picker.mouseY
                })
                onPositionChanged: function(mouse) {
                  root.pointerSelect(tile.index, tile, mouse)
                }
                onClicked: root.pointerActivate(tile.index)
              }
            }
          }
        }

        // What the face buttons do here. Last in the card, and page-scoped:
        // the game bar says the same kind of thing across the whole screen,
        // and this is the only one that can say what a page has spent X or Y
        // on. `[menu] keys = false` turns it off for anyone running both.
        Item {
          width: parent.width
          height: root.legendHeight
          visible: root.legendHeight > 0

          Row {
            anchors.centerIn: parent
            spacing: metrics.space(16)

            Repeater {
              model: root.keys

              delegate: Row {
                id: hint
                required property var modelData
                spacing: metrics.space(5)

                Badge {
                  label: hint.modelData.b
                  kind: hint.modelData.k
                  anchors.verticalCenter: parent.verticalCenter
                }

                Text {
                  anchors.verticalCenter: parent.verticalCenter
                  text: hint.modelData.n
                  textFormat: Text.PlainText
                  color: Color.menu.text
                  opacity: 0.66
                  font.family: metrics.font.family
                  font.pixelSize: metrics.font.caption
                }
              }
            }
          }
        }
      }
    }
  }

  // The pad that moves the selection produces no Wayland input at all -
  // it travels over a socket - and a still pointer is no input either, so
  // the compositor would happily start the screensaver while the menu is
  // open. Same inhibitor the keyboard binds.
  IdleInhibitor {
    window: panel
    enabled: root.opened
  }
}
