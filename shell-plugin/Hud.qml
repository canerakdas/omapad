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

  // The family this surface's words are set in, from the daemon
  // (`[ui] font`); empty is the desktop's own. Not the badges' - those are
  // lettered in the face their drawings were punched with, which is
  // `buttonArt.family`. See `Metrics.fontFamily`.
  property string fontFamily: ""
  // How solid the readings are over what is behind them (`[hud] opacity`). A
  // HUD is read while something else is being watched, so the thing it is
  // over has to stay watchable - and how much is not this panel's to decide.
  property real fade: 0.9
  // What a corner is rounded by where the compositor rounds nothing - the
  // menu's own setting, so a tile is the same shape in both places. It is the
  // base of `metrics.radius` rather than a radius; the compositor answers
  // first. A tile's *height* is not a setting here at all; see the grid below.
  property real corner: 23
  // How far off the edge of the screen the grid starts. `[hud] margin`, and
  // deliberately not the menu's own: a fullscreen card keeps a television's
  // overscan clear of its first tile, and this is a corner somebody put
  // something in on purpose. 0 is the corner itself.
  property int margin: 16

  // What share of each screen edge is kept clear of anything that has to be
  // read (`[ui] safe_area`, game mode only). A television crops its own
  // edges; every margin below goes through `metrics.edge`, which takes this
  // or the surface's own, whichever is further in.
  property real safeArea: 0

  // The screen's own measurements, which are not the window's: a bar is a
  // strip and a keyboard is a card, and the share a television crops is a
  // share of the picture rather than of whatever surface is standing in it.
  // A window with no screen yet answers nothing rather than a share of zero.
  readonly property int screenH: panel.screen ? panel.screen.height : 0
  readonly property int screenW: panel.screen ? panel.screen.width : 0

  // How long everything on this surface takes to move, as a multiplier over
  // the durations in `Metrics` (`[ui] motion`). 0 is motion off.
  property real motion: 1.0

  // How hard these surfaces round a corner, against the desktop's own answer
  // (`[ui] radius`). From the payload like the scale, and for the same
  // reason: the shell cannot read omapad's config, and a person who has
  // rounded one surface has rounded all of them.
  property real radiusScale: 1.0

  Metrics {
    id: metrics
    radiusScale: root.radiusScale
    scale: root.uiScale
    fontFamily: root.fontFamily
    motion: root.motion
    safeArea: root.safeArea
    cornerBase: root.corner
  }

  // The ground a tile is drawn on. Only ever "plain" here: the other two
  // outlines say "selected" and "being carried", and this surface has no
  // selection and nothing to carry.
  TileArt {
    id: tileArt
  }

  // The furniture a clock's face is drawn from. Lent to every clock on the
  // page rather than built per tile: `ControlArt` cannot be a singleton - it
  // does not register from a plugin directory - so one instance per surface
  // is what there is.
  ControlArt {
    id: controlArt
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
  // The grid's own inset, held off to the safe area where a television is
  // cropping one. Two of them, because a share of the height and a share of
  // the width are two different numbers on a screen that is not square - and
  // `[hud] margin` is one number because it was a corner somebody put
  // something in, which is the same corner either way.
  readonly property int contentMargin: metrics.edge(
    root.screenH, metrics.space(root.margin))
  readonly property int contentMarginX: metrics.edge(
    root.screenW, metrics.space(root.margin))
  readonly property int cellGap: metrics.spacing.xs
  readonly property int cellWidth: {
    var inner = panel.width - root.contentMarginX * 2
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
      if (s.font !== undefined) root.fontFamily = String(s.font)
      if (s.radius !== undefined)
        root.radiusScale = Math.max(0, Number(s.radius))
      if (s.motion !== undefined)
        root.motion = Math.max(0, Number(s.motion))
      if (s.safe !== undefined)
        root.safeArea = Math.max(0, Number(s.safe))
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
      x: root.contentMarginX
      y: root.contentMargin
      width: parent.width - root.contentMarginX * 2
      height: parent.height - root.contentMargin * 2
      opacity: root.opened ? root.fade : 0
      Behavior on opacity { NumberAnimation { duration: metrics.time.arrive } }

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
          // The other tile this surface draws, and the only one that is not a
          // reading: it has nothing to press, which is the whole of what a
          // tile needs to be allowed over a game. Game mode takes Omarchy's
          // bar away and the bar is where the time was - see hud.py.
          readonly property bool clock: tile.modelData.k === "clock"

          x: root.cellX(tile.modelData.x)
          y: root.cellY(tile.modelData.y)
          width: root.cellSpan(tile.modelData.w)
          height: root.rowsHeight(tile.modelData.h)

          // A ground, and a solid one. Over a game there is no panel behind
          // these at all, so the six percent that reads as a tile against an
          // opaque card reads as nothing whatever - the tiles are the only
          // thing there is, and they carry their own.
          Shape {
            id: ground
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer

            // An edge as well as a ground, for the same reason the menu's
            // tiles have one: a fill alone is a shade, and a shade is what a
            // theme is free to move. Drawn a hairline in from the tile's own
            // box and shifted back out by half of it below, because a stroke
            // straddles the path it follows.
            readonly property real weight: metrics.spacing.hairline

            ShapePath {
              // One step lighter than the page, the same ground the menu's
              // tiles carry - there is one arrangement and one page, so there
              // is one thing a cell is drawn on.
              fillColor: Qt.tint(Color.menu.background,
                                 Util.alpha(Color.menu.text, 0.08))
              // A step off the card, not off the page - see menu.md.
              strokeColor: Qt.tint(
                Qt.tint(Color.menu.background,
                        Util.alpha(Color.menu.text, 0.08)),
                Util.alpha(Color.menu.text, 0.07))
              strokeWidth: ground.weight > 0 ? ground.weight : -1

              PathSvg {
                path: tileArt.ground("plain",
                                     tile.width - ground.weight,
                                     tile.height - ground.weight,
                                     metrics.radius.tile)
              }
            }

            transform: Translate {
              x: ground.weight / 2
              y: ground.weight / 2
            }
          }

          // The name and what it says, on one line and nothing under them.
          // A reading drew the menu's slider line under itself once, and on
          // a surface nothing can push it read as a control that had lost its
          // thumb - so it is words here and on the menu's readout tile, which
          // is what keeps a page of readings the same in both places it
          // appears.
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

            // And the one tile whose value is a drawing rather than a number.
            // It hangs under the same name line every reading here has, so a
            // page of tiles is a page of one shape - and it is `Clock.qml`,
            // the menu's own, because the menu is where this tile was put on
            // the page and a face that differed between the two would be the
            // arrangement saying something it does not mean.
            //
            // The name stays: a reading's word says what its number is about,
            // and what this one says is which of the corners somebody put a
            // clock in. `t` is off the wire for it, so the value beside the
            // name draws nothing without being told not to.
            Clock {
              id: readingClock
              visible: tile.clock
              width: Math.max(0, Math.min(
                parent.width,
                tile.height - readingName.height - metrics.space(12)))
              height: readingClock.width
              anchors.horizontalCenter: parent.horizontalCenter
              art: controlArt
              family: metrics.font.family
              figures: metrics.type.loud
              minutes: tile.modelData.mn !== undefined
                ? tile.modelData.mn : 0
              ink: Color.menu.text
              // The menu's own strength for this drawing, mirrored rather
              // than picked again here: the same face is drawn on both
              // surfaces, so its furniture recedes by the same amount on
              // both (qml.md 8.2.1 on a mirrored measurement).
              dim: Util.alpha(Color.menu.text, 0.3)
              mark: Color.accent
            }
          }
        }
      }
    }
  }
}
