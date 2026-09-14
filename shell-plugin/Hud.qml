// The readings omapad leaves on screen: one menu page, drawn where it was put.
//
// Game mode takes Omarchy's bar away, which is the right trade for a screen
// watched from a sofa and leaves one question unanswered - what the machine is
// actually doing while it does it. This is the answer, and it is deliberately
// not a surface of its own design.
//
// What it draws is an ordinary menu page. `hud.py` packs it with the menu's
// own packer, so the cells that arrive here are the cells `Menu.qml` would
// have drawn, and a tile carried in the menu's edit mode moves in both places
// at once - there is only one arrangement and one page.
//
// The grid those cells land in is **the screen**, and that is the one thing
// here that is not the menu's. A menu cell is a number of pixels tall on a
// page that scrolls; this one is a share of the screen, because a screen has
// a bottom edge and a tile carried into the bottom right has to arrive in the
// corner rather than a fixed distance down from the top.
//
// **Nothing here can be pressed, and that is what lets it sit over a game.**
// There is no selection, no hover, no control socket and no input region: the
// daemon never grabs for it, this panel never sends anything, and every click
// goes to the window underneath. A surface that could take a press would be
// in the way of the thing it is drawn over.
//
// It is `WlrLayer.Top` rather than Overlay, which is the other half of that:
// the menu, the guide and the keyboard are Overlay, so opening any of them
// covers the readings rather than fighting them for the same band of screen.
// `ExclusionMode.Normal` with the zero exclusive zone it defaults to asks for
// what is left once every bar has taken its strip - so the top row can never
// come up underneath the game bar, and no bar geometry has to travel here.
import QtQuick
import QtQuick.Shapes
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons
import qs.Ui

Item {
  id: root

  // A setting rather than a surface that is opened, which is why it can be on
  // when the daemon starts: `[hud] show`, and the switch on the page.
  property bool opened: false
  property var items: []
  // How many cells across and down the screen is cut into. Both from the
  // daemon, and `rows` is the HUD's own setting rather than how tall the page
  // came out - the grid below divides by it.
  property int cols: 6
  property int rows: 12

  // $XDG_RUNTIME_DIR is per-user and 0700, and that is the only thing keeping
  // another user off this socket. Without it there is nowhere private to
  // bind, so bind nowhere - see Guide.qml.
  readonly property string socketDir: Quickshell.env("XDG_RUNTIME_DIR")
    ? Quickshell.env("XDG_RUNTIME_DIR") + "/omapad" : ""

  // How big this surface draws, from the daemon: the desktop is read at a
  // keyboard and game mode from a sofa, so the scale follows the mode rather
  // than the session. Every measurement below goes through `metrics`.
  property real uiScale: 1.0
  // How solid the readings are over what is behind them (`[hud] opacity`). A
  // HUD is read while something else is being watched, so the thing it is
  // over has to stay watchable - and how much is not this panel's to decide.
  property real fade: 0.9
  // How far the drawn corner of a tile reaches in - the menu's own setting,
  // so a tile is the same shape in both places. Its *height* is not a setting
  // here at all; see the grid below.
  property real corner: 10
  // How far off the edge of the screen the grid starts. `[hud] margin`, and
  // deliberately not the menu's own: a fullscreen card keeps a television's
  // overscan clear of its first tile, and this is a corner somebody put
  // something in on purpose. 0 is the corner itself.
  property int margin: 16

  Metrics {
    id: metrics
    scale: root.uiScale
  }

  // The ground a tile is drawn on. Only ever "plain" here: the other two
  // outlines say "selected" and "being carried", and this surface has no
  // selection and nothing to carry.
  TileArt {
    id: tileArt
  }

  // -- the grid, which is the screen ----------------------------------------
  //
  // The same four functions Menu.qml lays a page out with, with one thing
  // changed and it is the thing that makes this a HUD: **a cell is a share of
  // the screen, not a number of pixels.** The menu's cell is `cell_height`
  // pixels tall and its page is as many rows as its tiles came to, which
  // scrolls - right for a card, and it leaves no cell that means "the
  // bottom". A screen has a bottom edge, so this grid takes a fixed `rows`
  // and divides by it. A tile carried into the last row and the last column
  // is then in the corner of the screen, which is what a corner is for.
  //
  // Both axes are worked out the same way, and the arithmetic is what puts
  // the far edge of the last one exactly on the page's: `n` cells and `n - 1`
  // gaps add back up to the whole.
  readonly property int contentMargin: metrics.space(root.margin)
  readonly property int cellGap: metrics.spacing.xs
  readonly property int cellWidth: {
    var inner = panel.width - root.contentMargin * 2
    return Math.max(1, Math.floor(
      (inner - root.cellGap * (root.cols - 1)) / root.cols))
  }
  readonly property int cellHeight: {
    var inner = panel.height - root.contentMargin * 2
    return Math.max(1, Math.floor(
      (inner - root.cellGap * (root.rows - 1)) / root.rows))
  }

  function cellX(x) { return x * (root.cellWidth + root.cellGap) }
  function cellY(y) { return y * (root.cellHeight + root.cellGap) }
  function cellSpan(n) {
    return n * root.cellWidth + (n - 1) * root.cellGap
  }
  function rowsHeight(n) {
    return n > 0 ? n * root.cellHeight + (n - 1) * root.cellGap : 0
  }

  // -- the payload ----------------------------------------------------------

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
      if (s.opacity !== undefined) root.fade = Number(s.opacity) || 1
      if (s.corner !== undefined) root.corner = Number(s.corner) || 0
      if (s.margin !== undefined) root.margin = Math.max(0, Number(s.margin))
      if (s.cols !== undefined) root.cols = Number(s.cols) || 6
      // Not how tall the page came out - how many rows the screen is cut
      // into. Every measurement above divides by it.
      if (s.rows !== undefined) root.rows = Number(s.rows) || 1
      // The one model on this surface, so the one field that needs `fresh`:
      // a reading that has not moved arrives twice a second, and rebuilding
      // every delegate for it is what qml.md 5.4 measured.
      if (s.items !== undefined && root.fresh("items", s.items))
        root.items = s.items
      if (s.open !== undefined) root.opened = !!s.open
    } catch (e) {}
  }

  // omapad connects here and streams state; both ends keep trying, so the
  // shell and the daemon can start or restart in either order.
  SurfaceSocket {
    dir: root.socketDir
    name: "hud.sock"
    onLine: text => root.applyState(text)
  }

  IpcHandler {
    target: "omapad-hud"
    function state(): string { return root.opened ? "on" : "off" }
    function socket(): string { return root.socketDir + "/hud.sock" }
    function ping(): string { return "ok" }
  }

  PanelWindow {
    id: panel
    visible: root.opened
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    WlrLayershell.namespace: "omapad-hud"
    // Under the surfaces that are opened on purpose, over the desktop. See
    // the header: the menu covering the readings is the right way round.
    WlrLayershell.layer: WlrLayer.Top
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    // What is left once the bars have taken their strips, with no strip of
    // its own: the readings never sit under the game bar and never push
    // anything about.
    exclusionMode: ExclusionMode.Normal
    // Empty, so every click goes to the window underneath. There is nothing
    // here to press.
    mask: Region {}

    // The page is the screen less its margin, and the grid is that divided
    // up - so the last row ends where the page ends, whatever is on it.
    Item {
      id: page
      x: root.contentMargin
      y: root.contentMargin
      width: parent.width - root.contentMargin * 2
      height: parent.height - root.contentMargin * 2
      opacity: root.opened ? root.fade : 0
      Behavior on opacity { NumberAnimation { duration: 140 } }

      Repeater {
        model: root.items

        // Inlined for Menu.qml's reason: a Component declared beside this one
        // cannot see the delegate's own scope, and reading the data through
        // `parent` is the scope lookup this plugin has a rule against.
        delegate: Item {
          id: tile
          required property var modelData

          readonly property bool hasIcon: tile.modelData.i !== undefined
            && tile.modelData.i.length > 0
          // Only where there is a travel to draw it against. A thermometer's
          // top of scale is a number somebody would have to invent, so the
          // daemon sends no `v` and there is no bar - rather than a bar that
          // says a different thing on every machine it is read on.
          readonly property bool hasBar: tile.modelData.v !== undefined

          x: root.cellX(tile.modelData.x)
          y: root.cellY(tile.modelData.y)
          width: root.cellSpan(tile.modelData.w)
          height: root.rowsHeight(tile.modelData.h)

          // A ground, and a solid one. Over a game there is no panel behind
          // these at all, so the six percent that reads as a tile against an
          // opaque card reads as nothing whatever - the tiles are the only
          // thing there is, and they carry their own.
          Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer

            ShapePath {
              fillColor: Util.alpha(Color.menu.background, 0.88)
              strokeColor: "transparent"
              strokeWidth: -1

              PathSvg {
                path: tileArt.ground("plain", tile.width, tile.height,
                                     metrics.px(root.corner))
              }
            }
          }

          // The name and what it says on one line, the bar under both - the
          // slider's shape, and the readout's shape in the menu. A page of
          // readings has to read the same in both places it appears, or it is
          // a page you have to learn twice.
          Column {
            anchors.centerIn: parent
            width: parent.width - metrics.space(12)
            spacing: metrics.space(3)

            Item {
              width: parent.width
              height: readingName.height

              Text {
                id: readingName
                anchors.left: parent.left
                anchors.right: readingValue.left
                anchors.rightMargin: metrics.space(4)
                text: (tile.hasIcon ? tile.modelData.i + "  " : "")
                  + tile.modelData.l
                textFormat: Text.PlainText
                color: Color.menu.text
                font.family: metrics.font.family
                font.pixelSize: metrics.font.bodySmall
                font.weight: Font.Medium
                elide: Text.ElideRight
              }

              Text {
                id: readingValue
                anchors.right: parent.right
                anchors.baseline: readingName.baseline
                text: tile.modelData.t !== undefined ? tile.modelData.t : ""
                textFormat: Text.PlainText
                color: Color.accent
                font.family: metrics.font.family
                font.pixelSize: metrics.font.caption
                font.weight: Font.Medium
              }
            }

            Rectangle {
              visible: tile.hasBar
              width: parent.width
              height: Math.max(2, metrics.space(4))
              radius: height / 2
              color: Util.alpha(Color.menu.text, 0.18)

              // The travel is a binding rather than something a signal
              // starts, so a delegate rebuilt between two readings is born
              // where the value already is - qml.md 5.5.
              Rectangle {
                height: parent.height
                radius: parent.radius
                width: Math.round(
                  parent.width * (tile.modelData.v !== undefined
                                  ? tile.modelData.v : 0))
                color: Color.accent
                Behavior on width { NumberAnimation { duration: 200 } }
              }
            }
          }
        }
      }
    }
  }
}
