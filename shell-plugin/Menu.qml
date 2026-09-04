// Controller menu for omapad.
//
// A pure view, the same split the keyboard uses: omapad owns the entry tree,
// the selection and the drill-down stack, and launches whatever is picked. One
// JSON line per update arrives over a unix socket and this panel draws it.
// What a person does with the desktop - arrow keys, Enter, a cursor - comes
// back the other way over the same control socket a terminal would use, so
// the pad and the desk drive the same selection.
//
// It is deliberately shaped like the Omarchy menu - centred card, a title line,
// one column of rows, `›` where a row drills in - because that is the menu the
// desktop already teaches, and a list is what a D-pad walks well.
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
  property string title: ""
  property string clock: ""
  property int sel: 0
  property int depth: 0

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

  // Same measurements the Omarchy menu uses, so the two read as one family.
  readonly property int contentMargin: metrics.spacing.panelPadding
  readonly property int contentSpacing: metrics.spacing.md
  readonly property int headerHeight: Math.max(metrics.space(34), metrics.font.title + metrics.spacing.controlPaddingY * 2)
  readonly property int baseRowHeight: Math.max(metrics.space(50), metrics.font.body + metrics.spacing.rowPaddingX * 2)
  readonly property int detailRowHeight: Math.max(metrics.space(58), metrics.font.body + metrics.font.caption + metrics.spacing.rowPaddingX * 2)
  readonly property int rowSpacing: metrics.spacing.xs
  readonly property var selectedBorderSpec: Border.surfaceSpec("menu", "selected-border", Color.menu.selectedBorder, 0)
  // How many rows PageUp and PageDown skip - the Omarchy menu's own step.
  readonly property int keyPageStep: 6

  function rowHeightFor(item) {
    return item && item.d ? detailRowHeight : baseRowHeight
  }

  // A card that swallows the screen reads as a page rather than a menu, so a
  // long submenu scrolls behind the fold instead of growing past this.
  //
  // Cut to whole rows. Clamping the height alone puts the fold through the
  // middle of a row, and since a row centres its text vertically that half
  // draws no ink at all - so the card ends in a band of empty space that reads
  // as bad padding rather than as "there is more below".
  readonly property int listHeight: {
    var cap = Math.round(panel.height * 0.6)
    var total = 0
    for (var i = 0; i < items.length; i++) {
      var step = (i > 0 ? rowSpacing : 0) + rowHeightFor(items[i])
      if (total + step > cap) break
      total += step
    }
    return Math.max(total, baseRowHeight)
  }

  // omapad re-sends the whole payload every VIEW_HEARTBEAT seconds, so a
  // restarted shell repaints itself with no handshake - which means most
  // lines that arrive here say nothing new. Re-applying one is not free: a
  // `var` property never compares equal to its old value, so assigning it
  // re-runs every binding that reads it, and where it is a Repeater's model
  // it destroys and rebuilds every delegate under it. A fresh component's
  // `lastLine` is empty, so a restarted shell still paints what it is given.
  property string lastLine: ""
  // The same argument one field at a time, for the list a moved
  // selection leaves alone.
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
      if (s.bar !== undefined) root.overBar = !!s.bar
      if (s.items !== undefined && root.fresh("items", s.items))
        root.items = s.items
      if (s.title !== undefined) root.title = s.title
      if (s.clock !== undefined) root.clock = s.clock
      if (s.depth !== undefined) root.depth = s.depth
      if (s.sel !== undefined) root.sel = s.sel
      if (s.open !== undefined) root.opened = !!s.open
      Qt.callLater(root.reveal)
    } catch (e) {}
  }

  // Keep the selection on screen once the list is taller than the fold.
  function reveal() {
    list.positionViewAtIndex(root.sel, ListView.Contain)
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
  // same control socket `omapad ctl` uses - `menu up`, `menu select 3`,
  // `menu press`. Commands are fire-and-forget: the answer to every one
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
  // A cursor names the row it is over and the daemon makes it the selection.
  // But a menu that opens with the cursor already on a row must not hand the
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

  // The pointer itself moved the selection - a click - so the row under the
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
    if (index === root.sel) return
    root.send("menu select " + index)
  }

  // A click is a decision, not a sample: it lands on the row it lands on,
  // and the daemon is told the row and the press in one go.
  function pointerActivate(index) {
    root.send("menu select " + index)
    root.send("menu press")
    root.pointerAllowSample()
  }

  // omapad connects here and streams state; it reconnects on its own, so the
  // shell and the daemon can restart in either order.
  SocketServer {
    active: root.socketDir !== ""
    path: root.socketDir + "/menu.sock"
    handler: Socket {
      parser: SplitParser {
        splitMarker: "\n"
        onRead: line => root.applyState(line)
      }
    }
  }

  IpcHandler {
    target: "omapad-menu"
    function state(): string { return root.opened ? "open" : "closed" }
    function socket(): string { return root.socketDir + "/menu.sock" }
    function ping(): string { return "ok" }
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
    // row, a click picks one, a click on the scrim leaves. The keyboard and
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
      width: Math.min(metrics.space(320), parent.width - Style.gapsOut * 2)
      height: Math.min(
        card.borderTop + card.borderBottom + root.contentMargin * 2 +
          root.headerHeight + root.contentSpacing + root.listHeight,
        parent.height - Style.gapsOut * 2)
      color: Color.menu.background
      borderSpec: Border.surfaceSpec("menu", "border", Color.menu.border,
        Math.max(1, metrics.space(2)))
      radius: Style.cornerRadius
      opacity: root.opened ? 1 : 0
      Behavior on opacity { NumberAnimation { duration: 110 } }

      // Padding is not a dismissal: only the scrim is. A click on the card,
      // or in the gap between rows, must not send the menu away.
      MouseArea {
        anchors.fill: parent
        onClicked: {}
      }

      // Where the keyboard lands. Everything a key means goes to the daemon
      // as a menu command, the same grammar the pad uses, so whichever hand
      // is driving, the selection lives in one place. Left and Backspace
      // climb one level at a time; Escape leaves outright, like the Omarchy
      // menu. A held arrow auto-repeats and the menu walks.
      Item {
        id: keyCatcher
        anchors.fill: parent
        focus: true
        Keys.priority: Keys.BeforeItem
        Keys.onPressed: function(event) {
          if (event.key === Qt.Key_Escape) {
            root.send("menu close")
            event.accepted = true
          } else if (event.key === Qt.Key_Backspace || event.key
              === Qt.Key_Left) {
            root.send("menu back")
            root.pointerArm()
            event.accepted = true
          } else if (event.key === Qt.Key_Up) {
            root.send("menu up")
            root.pointerArm()
            event.accepted = true
          } else if (event.key === Qt.Key_Down) {
            root.send("menu down")
            root.pointerArm()
            event.accepted = true
          } else if (event.key === Qt.Key_PageUp) {
            root.send("menu select "
              + Math.max(0, root.sel - root.keyPageStep))
            root.pointerArm()
            event.accepted = true
          } else if (event.key === Qt.Key_PageDown) {
            root.send("menu select " + Math.min(
              root.items.length - 1, root.sel + root.keyPageStep))
            root.pointerArm()
            event.accepted = true
          } else if (event.key === Qt.Key_Home) {
            root.send("menu select 0")
            root.pointerArm()
            event.accepted = true
          } else if (event.key === Qt.Key_End) {
            root.send("menu select " + Math.max(0, root.items.length - 1))
            root.pointerArm()
            event.accepted = true
          } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter
              || event.key === Qt.Key_Space || event.key === Qt.Key_Right) {
            root.send("menu press")
            root.pointerArm()
            event.accepted = true
          }
        }
      }

      Column {
        anchors.fill: parent
        anchors.topMargin: card.borderTop + root.contentMargin
        anchors.rightMargin: card.borderRight + root.contentMargin
        anchors.bottomMargin: card.borderBottom + root.contentMargin
        anchors.leftMargin: card.borderLeft + root.contentMargin
        spacing: root.contentSpacing

        // Where you are, and - since game mode takes Omarchy's bar away and
        // the pad can reach no other clock - the day and the time.
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
            color: Color.menu.text
            opacity: 0.42
            font.family: metrics.font.family
            font.pixelSize: metrics.font.bodySmall
          }
        }

        ListView {
          id: list
          width: parent.width
          height: root.listHeight
          model: root.items
          clip: true
          spacing: root.rowSpacing
          boundsBehavior: Flickable.StopAtBounds
          interactive: false

          delegate: BorderSurface {
            id: row
            required property int index
            required property var modelData

            readonly property bool selected: index === root.sel
            readonly property bool hasIcon: modelData.i !== undefined && modelData.i.length > 0

            width: ListView.view.width
            height: root.rowHeightFor(modelData)
            radius: Style.cornerRadius
            color: row.selected ? Color.menu.selectedBackground : "transparent"
            borderSpec: row.selected ? root.selectedBorderSpec : Border.none()

            Text {
              id: iconText
              visible: row.hasIcon
              text: row.hasIcon ? row.modelData.i : ""
              color: row.selected ? Color.menu.selectedText : Color.menu.text
              font.family: metrics.font.family
              font.pixelSize: metrics.font.iconLarge
              width: metrics.space(36)
              horizontalAlignment: Text.AlignHCenter
              anchors.left: parent.left
              anchors.leftMargin: Border.left(root.selectedBorderSpec) + metrics.space(8)
              anchors.verticalCenter: parent.verticalCenter
            }

            Column {
              anchors.left: row.hasIcon ? iconText.right : parent.left
              anchors.leftMargin: row.hasIcon
                ? metrics.space(6)
                : Border.left(root.selectedBorderSpec) + metrics.space(18)
              anchors.right: chevron.left
              anchors.rightMargin: metrics.space(6)
              anchors.verticalCenter: parent.verticalCenter
              spacing: metrics.space(3)

              Text {
                width: parent.width
                text: row.modelData.l
                color: row.selected ? Color.menu.selectedText : Color.menu.text
                font.family: metrics.font.family
                font.pixelSize: metrics.font.heading
                font.weight: Font.Medium
                elide: Text.ElideRight
              }

              Text {
                width: parent.width
                visible: row.modelData.d !== undefined && row.modelData.d.length > 0
                text: visible ? row.modelData.d : ""
                color: Color.menu.text
                opacity: 0.52
                font.family: metrics.font.family
                font.pixelSize: metrics.font.bodySmall
                elide: Text.ElideRight
              }
            }

            // The same slot says two things, and they never both apply: `›`
            // where a row drills in, and a tick where a row sets something
            // that is already what is in force - which is what turns a list
            // of choices into one that says where you are.
            Text {
              id: chevron
              readonly property bool ticked: row.modelData.on === true
              text: row.modelData.sub ? "›" : (ticked ? "✓" : "")
              color: row.selected
                ? Color.menu.selectedText
                : (ticked ? Color.accent : Color.menu.text)
              opacity: row.modelData.sub ? 0.36 : (ticked ? 0.95 : 0)
              font.family: metrics.font.family
              font.pixelSize: metrics.font.heading
              width: metrics.space(14)
              horizontalAlignment: Text.AlignHCenter
              anchors.right: parent.right
              anchors.rightMargin: Border.right(root.selectedBorderSpec) + metrics.space(8)
              anchors.verticalCenter: parent.verticalCenter
            }

            // Hover names the row under the cursor, a click picks it - the
            // daemon decides both, so this MouseArea only asks. The gate
            // keeps the stationary cursor (and the cursor the menu opened
            // under) from stealing a selection the pad chose.
            MouseArea {
              id: picker
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onEntered: root.pointerSelect(row.index, row, {
                x: picker.mouseX,
                y: picker.mouseY
              })
              onPositionChanged: function(mouse) {
                root.pointerSelect(row.index, row, mouse)
              }
              onClicked: root.pointerActivate(row.index)
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
