// The bindings guide for omapad.
//
// A pure view, like the other two surfaces: omapad owns the pages, decides
// which buttons the connected pad actually has and how the rows are grouped,
// and pushes one JSON line per update over a unix socket. This panel draws a
// page and nothing else - there is nothing here to press, because the guide is
// read-only by design.
//
// The point of the whole surface is the badge: a binding printed as `A` in a
// list is a letter, but printed as a round face button next to a shoulder cut
// away at one corner it is the thing under your thumb. So the badge draws the
// *shape* of the control, from assets/shapes through ButtonArt.qml, with the
// label already set into it in Fira Code - and takes its colours from the
// theme rather than from any one console's palette, which would fight every
// Omarchy theme but one. Every control the daemon names is drawn now, the
// D-pad by the arm its direction lights and the system buttons by a pill the
// text goes into, so nothing here falls back to a rectangle with a border.
//
// Same window rules as the menu: overlay layer, no keyboard focus, empty input
// region, so nothing underneath loses focus or a click.
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons
import qs.Ui

Item {
  id: root

  property bool opened: false
  property string title: ""
  property string note: ""
  property int page: 0
  property int count: 0
  property var cols: []

  readonly property string socketDir: (Quickshell.env("XDG_RUNTIME_DIR") || "/tmp") + "/omapad"

  // How big this surface draws, from the daemon: the desktop is read at a
  // keyboard and game mode from a sofa, so the scale follows the mode rather
  // than the session. Every measurement below goes through `metrics`.
  property real uiScale: 1.0
  // Which of the two ways a badge is drawn (`[ui] badge_style`). A payload
  // field rather than a shell constant: the panel cannot read the config, and
  // the answer changes from the menu while the surface is up.
  property string badgeStyle: "filled"
  readonly property bool stencil: root.badgeStyle === "stencil"

  Metrics {
    id: metrics
    scale: root.uiScale
  }

  // The square `omarchy.workspaces` puts where the focused number would be,
  // and the pager under the rule borrows for the page you are reading.
  readonly property string focusedGlyph: "󱓻"

  // The drawn buttons, and the font their labels are set in.
  ButtonArt {
    id: buttonArt
  }

  // Same measurements as the menu, so the two read as one family.
  readonly property int contentMargin: metrics.spacing.panelPadding
  readonly property int columnGap: metrics.space(28)
  readonly property int groupGap: metrics.space(14)
  readonly property int rowGap: metrics.space(5)
  readonly property int badgeUnit: metrics.badge(
    Math.max(metrics.space(22), metrics.font.body + metrics.space(8)))
  // A shoulder is drawn twice as wide as it is tall; every row indents past
  // that, so a column of badges lines its descriptions up whatever is in it.
  readonly property int badgeWide: Math.round(badgeUnit * 2)

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
    font.pixelSize: metrics.font.bodySmall
    font.weight: Font.Medium
  }
  TextMetrics {
    id: capInk
    font: capProbe.font
    text: capProbe.text
  }
  readonly property int capNudge: Math.round(capProbe.height / 2 - capProbe.baselineOffset
    - (capInk.tightBoundingRect.y + capInk.tightBoundingRect.height / 2))

  // omapad re-sends the whole payload every VIEW_HEARTBEAT seconds, so a
  // restarted shell repaints itself with no handshake - which means most
  // lines that arrive here say nothing new. Re-applying one is not free: a
  // `var` property never compares equal to its old value, so assigning it
  // re-runs every binding that reads it, and where it is a Repeater's model
  // it destroys and rebuilds every delegate under it. A fresh component's
  // `lastLine` is empty, so a restarted shell still paints what it is given.
  property string lastLine: ""
  // The same argument one field at a time, for the page a turned page
  // leaves alone.
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
      if (s.badge !== undefined) root.badgeStyle = String(s.badge)
      if (s.title !== undefined) root.title = s.title
      if (s.note !== undefined) root.note = s.note
      if (s.page !== undefined) root.page = s.page
      if (s.count !== undefined) root.count = s.count
      if (s.cols !== undefined && root.fresh("cols", s.cols))
        root.cols = s.cols
      if (s.open !== undefined) root.opened = !!s.open
    } catch (e) {}
  }

  // omapad connects here and streams state; it reconnects on its own, so the
  // shell and the daemon can restart in either order.
  SocketServer {
    active: true
    path: root.socketDir + "/guide.sock"
    handler: Socket {
      parser: SplitParser {
        splitMarker: "\n"
        onRead: line => root.applyState(line)
      }
    }
  }

  IpcHandler {
    target: "omapad-guide"
    function state(): string { return root.opened ? "open" : "closed" }
    function socket(): string { return root.socketDir + "/guide.sock" }
    function ping(): string { return "ok" }
  }

  // One control, drawn as the control it is. The shape carries the identity,
  // so the text inside can stay as short as what the pad itself prints.
  component Badge: Item {
    id: badge

    property string label: ""
    property string kind: "face"

    readonly property int unit: root.badgeUnit
    // The button as drawn in assets/shapes: `drawn` is the whole badge, down
    // to the label or the arrow set into it, and `bare` is the shape alone,
    // for a label no pad here prints and for the system buttons, which are
    // one pill until the shell types START or SELECT into it.
    readonly property var drawn: buttonArt.find(badge.kind, badge.label)
    readonly property var bare: buttonArt.shape(badge.kind, badge.label)
    readonly property var art: badge.drawn !== null ? badge.drawn : badge.bare
    // Only for a kind ButtonArt has never heard of - the daemon sends none,
    // but a badge that is only text still needs a box to be centred in.
    readonly property bool wide: kind === "bumper" || kind === "trigger" || kind === "system"

    implicitWidth: badge.art !== null
      ? Math.round(unit * badge.art.w / badge.art.h)
      : (wide ? Math.round(unit * 1.6) : unit)
    implicitHeight: unit
    width: implicitWidth
    height: implicitHeight

    BadgeArt {
      anchors.fill: parent
      drawn: badge.art
      // No outline: a drawn button is read by its silhouette, and a line
      // around it read as a frame someone had put the button in. The fill
      // carries the shape on its own, which is why it is heavier than the
      // tenth an outlined badge needed - and it is the accent, because the
      // badge is the one thing on the card the eye is hunting for. The label
      // stays the card's own text: an accent readable as a heading is not
      // always readable as a letter inside a badge.
      // Filled washes the shape in the accent and sets the label on it in
      // the card's own text. Stencil takes the accent to full strength and
      // makes the label the hole in it, so the card shows through the letter
      // and the badge carries from across a room.
      fill: root.stencil ? Color.accent : Util.alpha(Color.accent, 0.30)
      ink: root.stencil ? "transparent" : Color.menu.text
      knockout: root.stencil
      // The stick's rim is part of the drawing, not a border, so it is
      // punched along with the label rather than left as a line on a solid
      // badge.
      ringColor: root.stencil
        ? Color.menu.background : Util.alpha(Color.accent, 0.55)
      ringWidth: Math.max(1, metrics.space(1))
    }

    // Typed only where the drawing has no label of its own - a remapped
    // button, a profile someone added, the shapes above. In the same Fira
    // Code the drawn labels are outlines of, so the two read as one set.
    Text {
      id: typed
      visible: badge.drawn === null
      // Placed on whole pixels rather than centred by the anchors. A text
      // item that lands on a half pixel is the one blur antialiasing cannot
      // help, and centring an odd painted width in an even box - or a
      // fractional line height in either - does exactly that. The box the
      // size is fitted to is still the badge's; only where it is painted is
      // rounded.
      width: badge.width - metrics.space(6)
      height: Math.ceil(typed.implicitHeight)
      x: Math.round((badge.width - typed.contentWidth) / 2)
      y: Math.round((badge.height - typed.height) / 2) + root.capNudge
      // Three characters (CAP, L3 on a narrow badge) have to fit the same
      // shape a single letter does. Stepping the size by label length made
      // a row of badges read as two type sizes, so every badge is set at
      // one size and only the labels that overrun are squeezed to the width.
      text: badge.label
      // A label with no drawing behind it is typed into the same shape, so it
      // is punched the same way: on a solid badge it is the card showing
      // through, and on a washed one it is the card's text.
      color: root.stencil ? Color.menu.background : Color.menu.text
      font.family: buttonArt.family
      font.pixelSize: metrics.font.bodySmall
      fontSizeMode: Text.HorizontalFit
      minimumPixelSize: Math.max(6, metrics.font.caption - metrics.space(2))
      font.weight: Font.Medium
    }
  }

  // One binding: the control, then what it does, with a press-and-hold on a
  // quieter second line - the same shape the menu gives a row's detail.
  component BindingRow: Item {
    id: line

    property var row
    readonly property bool hasHold: line.row.h !== undefined && line.row.h.length > 0

    // Whole pixels all the way down: a row half a pixel tall pushes every
    // row under it off the grid, and then no text on the page is crisp.
    height: Math.max(root.badgeUnit, label.height + (hasHold ? hold.height : 0))

    Badge {
      id: badge
      label: line.row.b
      kind: line.row.k
      anchors.left: parent.left
      y: Math.round((line.height - badge.height) / 2)
    }

    Text {
      id: label
      anchors.left: parent.left
      anchors.leftMargin: root.badgeWide + metrics.space(10)
      anchors.right: parent.right
      height: Math.ceil(label.implicitHeight)
      y: line.hasHold ? 0 : Math.round((line.height - label.height) / 2)
      text: line.row.d
      color: Color.menu.text
      font.family: metrics.font.family
      font.pixelSize: metrics.font.body
      elide: Text.ElideRight
    }

    Text {
      id: hold
      visible: line.hasHold
      anchors.left: label.left
      anchors.right: parent.right
      height: Math.ceil(hold.implicitHeight)
      y: label.y + label.height
      text: visible ? "hold · " + line.row.h : ""
      color: Color.menu.text
      opacity: 0.52
      font.family: metrics.font.family
      font.pixelSize: metrics.font.caption
      elide: Text.ElideRight
    }
  }

  PanelWindow {
    id: panel
    visible: root.opened
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    WlrLayershell.namespace: "omapad-guide"
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
      width: Math.min(metrics.space(920), parent.width - Style.gapsOut * 2)
      height: Math.min(
        card.borderTop + card.borderBottom + root.contentMargin * 2 + content.height,
        parent.height - Style.gapsOut * 2)
      color: Color.menu.background
      borderSpec: Border.surfaceSpec("menu", "border", Color.menu.border,
        Math.max(1, metrics.space(2)))
      radius: Style.cornerRadius
      opacity: root.opened ? 1 : 0
      Behavior on opacity { NumberAnimation { duration: 110 } }
      clip: true

      Column {
        id: content
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.topMargin: card.borderTop + root.contentMargin
        anchors.leftMargin: card.borderLeft + root.contentMargin
        anchors.rightMargin: card.borderRight + root.contentMargin
        spacing: metrics.spacing.md

        Text {
          id: heading
          width: parent.width
          height: Math.ceil(heading.implicitHeight)
          text: root.title
          color: Color.menu.text
          font.family: metrics.font.family
          font.pixelSize: metrics.font.heading
          font.weight: Font.Medium
          elide: Text.ElideRight
        }

        Text {
          width: parent.width
          visible: root.note.length > 0
          text: root.note
          color: Color.menu.text
          opacity: 0.55
          font.family: metrics.font.family
          font.pixelSize: metrics.font.bodySmall
          elide: Text.ElideRight
        }

        Item { width: 1; height: metrics.space(4) }

        // The page itself: omapad has already packed the groups into
        // columns, because it is the side that knows how many rows a page can
        // hold before it has to become two pages.
        Row {
          id: columns
          width: parent.width
          spacing: root.columnGap

          Repeater {
            model: root.cols
            delegate: Column {
              id: columnItem
              required property var modelData
              width: (columns.width - root.columnGap * (root.cols.length - 1))
                / Math.max(1, root.cols.length)
              spacing: root.groupGap

              Repeater {
                model: columnItem.modelData
                delegate: Column {
                  id: groupItem
                  required property var modelData
                  width: columnItem.width
                  spacing: root.rowGap

                  Text {
                    width: groupItem.width
                    text: groupItem.modelData.t
                    color: Color.accent
                    font.family: metrics.font.family
                    font.pixelSize: metrics.font.caption
                    font.weight: Font.Medium
                    elide: Text.ElideRight
                  }

                  Repeater {
                    model: groupItem.modelData.rows
                    delegate: BindingRow {
                      required property var modelData
                      width: groupItem.width
                      row: modelData
                    }
                  }
                }
              }
            }
          }
        }

        Item {
          width: 1
          height: metrics.space(6)
          visible: root.count > 1
        }

        Rectangle {
          width: parent.width
          height: Math.max(1, metrics.space(1))
          color: Util.alpha(Color.menu.text, 0.12)
          visible: root.count > 1
        }

        // Which page of how many, drawn the way `omarchy.workspaces` draws
        // the desktop you are sitting on - numbers, and the one you are on a
        // square. A row of dots only says there is more of this; a workspace
        // strip says you can walk to it, which is the question the surface
        // raises the moment it is more than one page long. One page has
        // nowhere to walk, so nothing is printed and the rule goes with it.
        Row {
          id: pager
          anchors.horizontalCenter: parent.horizontalCenter
          spacing: metrics.space(2)
          visible: root.count > 1

          Repeater {
            model: root.count
            delegate: Item {
              id: pip
              required property int index
              readonly property bool current: pip.index === root.page

              // The same slot Omarchy gives a workspace, so a two-digit page
              // and the square that replaces it sit on the same centre.
              width: metrics.space(24)
              height: root.badgeUnit

              Text {
                anchors.centerIn: parent
                text: pip.current ? root.focusedGlyph : String(pip.index + 1)
                color: pip.current ? Color.accent : Color.menu.text
                opacity: pip.current ? 1 : 0.5
                font.family: metrics.font.family
                font.pixelSize: metrics.font.body
              }
            }
          }
        }
      }
    }
  }

  // Reading a page produces no Wayland input at all, so the compositor would
  // happily start the screensaver underneath it. Same inhibitor the keyboard
  // and the menu bind.
  IdleInhibitor {
    window: panel
    enabled: root.opened
  }
}
