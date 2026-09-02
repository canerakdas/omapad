// Controller menu for omapad.
//
// A pure view, the same split the keyboard uses: omapad owns the entry tree,
// the selection and the drill-down stack, and launches whatever is picked. One
// JSON line per update arrives over a unix socket and this panel draws it.
//
// It is deliberately shaped like the Omarchy menu - centred card, a title line,
// one column of rows, `›` where a row drills in - because that is the menu the
// desktop already teaches, and a list is what a D-pad walks well.
//
// The surface takes no keyboard focus and carries an empty input region: the
// pad drives it, so it must never swallow a click meant for the window under
// the scrim.
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

  readonly property string socketDir: (Quickshell.env("XDG_RUNTIME_DIR") || "/tmp") + "/omapad"

  // How big this surface draws, from the daemon: the desktop is read at a
  // keyboard and game mode from a sofa, so the scale follows the mode rather
  // than the session. Every measurement below goes through `metrics`.
  property real uiScale: 1.0

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

  // omapad connects here and streams state; it reconnects on its own, so the
  // shell and the daemon can restart in either order.
  SocketServer {
    active: true
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
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    exclusionMode: ExclusionMode.Ignore
    mask: Region {}

    Rectangle {
      anchors.fill: parent
      color: Color.menu.scrim
      opacity: root.opened ? 1 : 0
      Behavior on opacity { NumberAnimation { duration: 110 } }
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
          }
        }
      }
    }
  }

  // Pointing at menu rows produces no Wayland input at all - the selection
  // moves over a socket - so the compositor would happily start the
  // screensaver while the menu is open. Same inhibitor the keyboard binds.
  IdleInhibitor {
    window: panel
    enabled: root.opened
  }
}
