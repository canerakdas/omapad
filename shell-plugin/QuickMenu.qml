// The quick menu for omapad: one row of tiles, what PLUS opens.
//
// A pure view like the other surfaces: omapad owns the row, which tile is in
// front, whether one is waiting for a second press, and what every tile is on.
// One JSON line per update arrives on `quick.sock` and this panel draws it.
//
// It is the menu's other shape. The menu is a place - groups, pages, a head -
// and HOME is its door; this is what a pause button is for, a handful of
// things in one row the D-pad walks end to end. The drawing is `Console
// Overlay` in the Console OS v2 mockups: the window in front named at the top
// left, the row across the middle with a band under it for the tile in front,
// and the buttons along the foot. The mockup's readings at the top right were
// left out: the row is paused over something, and a column of numbers was a
// second thing to read on a screen whose job is the one row.
// The mockup's own palette is not: every colour is a role of the theme, the
// way every other surface here takes it (qml.md 8.1), and the tile is the
// menu's cell - `cell`, `corner`, `fill` and `dim` arrive from the same
// settings - so PLUS and HOME swapping one for the other in the same place
// read as one family.
//
// Window rules are the guide's, not the menu's: overlay layer, no keyboard
// focus, an empty input region. The menu takes the desk as well because it is
// a place somebody browses; a row paused over a game is driven by the thumb
// that paused it, and a click that landed on the game behind would be worse
// than a click that did nothing.
//
// Every size is off `Metrics`' silver ladder - `metrics.type` and
// `metrics.gap` - except the cell, which is the menu's module, the stroke
// weights, which belong to the drawing rather than to the spacing, and **the
// whole of the legend along the foot**. That row is Menu.qml's fullscreen
// legend character for character, which is GameBar.qml's: the row stands in
// the bar's band - the bar steps down while this is up - so the buttons
// answering the row sit exactly where, and exactly as large as, the buttons
// the bar printed a moment before. A legend that grew when PLUS was pressed
// would read as a different row.
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons
import qs.Ui

Item {
  id: root

  property bool opened: false
  property int sel: -1
  property var tiles: []
  // The tile in front, worded: its name, what it is on, the line under it,
  // and where along its travel it is where it has one. A field of its own so
  // a step along the row re-runs these bindings and rebuilds no tile.
  property var band: ({})
  property var head: ({})
  property var keys: []

  // $XDG_RUNTIME_DIR is per-user and 0700, and that is the only thing
  // keeping another user off this socket. Without it there is nowhere
  // private to bind, so bind nowhere.
  readonly property string socketDir: Quickshell.env("XDG_RUNTIME_DIR")
    ? Quickshell.env("XDG_RUNTIME_DIR") + "/omapad" : ""

  // How big this surface draws, from the daemon: the scale follows the mode.
  property real uiScale: 1.0
  // The family its words are set in (`[ui] font`), empty for the desktop's.
  property string fontFamily: ""
  // How long everything on it takes to move (`[ui] motion`). 0 is none.
  property real motion: 1.0
  // What share of each screen edge a television crops (`[ui] safe_area`).
  // The head and the foot stand against the edge, so both go through it.
  property real safeArea: 0
  // How hard a corner is rounded, against the desktop's (`[ui] radius`).
  property real radiusScale: 1.0
  // Which of the two ways a badge is drawn (`[ui] badge_style`).
  property string badgeStyle: "filled"
  // The game bar's height (`[gamebar] height`), so the legend can stand in
  // the band the bar's own row stood in. Mirrored from GameBar.qml the way
  // Menu.qml mirrors it - if one of these changes there, it changes here.
  property int barh: 32
  readonly property int barSideMargin: metrics.space(18)
  readonly property int barBand: Math.max(metrics.space(root.barh),
    root.badgeUnit + metrics.space(3) * 2)
  // Whether the pad has been touched lately enough to hold the screen awake.
  property bool awake: true
  // The menu's module, rounding, fill and dimming - `[menu] cell`,
  // `tile_corner`, `tile_fill` and `dim` - for the reason the header gives.
  property int cellUnit: 128
  property real corner: 23
  // Menu.qml's `tileFill`, read the way Menu.qml reads it: a plain tile's
  // ground at this alpha, the one under the thumb solid. Drawn solid here
  // while the menu honoured it, the same theme gave the two surfaces two
  // different greys.
  property real tileFill: 1.0
  property real dim: 0.75

  readonly property bool stencil: root.badgeStyle === "stencil"
  readonly property int screenH: panel.screen ? panel.screen.height : 0
  readonly property int screenW: panel.screen ? panel.screen.width : 0
  // What the legend's band gives up to a cropped edge: GameBar.qml's number,
  // arrived at the same way, so the row lands where the bar's did.
  readonly property int safeGap: metrics.edge(root.screenH, 0)
  readonly property int safeSide: metrics.edge(root.screenW, 0)

  Metrics {
    id: metrics
    radiusScale: root.radiusScale
    scale: root.uiScale
    fontFamily: root.fontFamily
    motion: root.motion
    safeArea: root.safeArea
    cornerBase: root.corner
  }

  // The drawn buttons, and the font their labels are set in.
  ButtonArt {
    id: buttonArt
  }

  // The figures a value's scale is drawn with - the menu's own, because the
  // scale here is the menu's slider (`Travel.qml`). One per surface: it
  // cannot be a singleton.
  ControlArt {
    id: controlArt
  }

  // The three inks over a card, as Menu.qml measures them (qml.md 8.1.2):
  // the grounds are the menu's, so the levels that read on them are too.
  readonly property real inkMuted: 0.63
  readonly property real inkDim: 0.58
  readonly property color cellGround:
    Qt.tint(Color.menu.background, Util.alpha(Color.menu.text, 0.08))
  readonly property color cellEdge:
    Qt.tint(root.cellGround, Util.alpha(Color.menu.text, 0.07))
  // The scale a value is read against, and the run of it the value has
  // covered: `Menu.qml`'s `spineInk` and `trailInk` written out. The value
  // here is drawn by the menu's slider, so its inks are a mirrored
  // measurement (qml.md 8.2.1) and stay off this surface's own numbers.
  readonly property color spineInk:
    Util.alpha(Color.menu.text, root.inkDim * 0.35)
  readonly property color trailInk: Util.alpha(Color.accent, 0.5)

  // Stroke weights, which belong to the drawing: the ring is a hairline and
  // the halo round it is the design's four pixels, a rung of the gap ladder.
  readonly property int ringWeight: Math.max(1, metrics.gap.hairline)
  readonly property int haloWeight: metrics.gap.xs
  readonly property int haloReach: metrics.gap.hairline + metrics.gap.xs

  // The row is a run of cells, and a run that does not fit the screen is
  // shrunk to fit rather than scrolled: eight tiles are all of it, and a row
  // you can only see part of is a row that hides the tile you paused for.
  readonly property int cellGap: metrics.gap.xxl
  readonly property int count: Math.max(1, root.tiles.length)
  readonly property int sideRoom: metrics.edge(root.screenW, metrics.gap.huge)
  readonly property int cell: Math.max(metrics.gap.huge, Math.min(
    metrics.space(root.cellUnit),
    Math.floor((panel.width - root.sideRoom * 2
                - root.cellGap * (root.count - 1)) / root.count)))
  readonly property int rowWidth:
    root.cell * root.count + root.cellGap * (root.count - 1)

  // The legend's badge: GameBar.qml's own expression, off the shell's scale
  // rather than this surface's ladder, for the reason the header gives.
  readonly property int badgeUnit: metrics.badge(
    Math.max(metrics.space(20), metrics.font.bodySmall + metrics.space(7)))

  // A typed badge label is centred on its capitals, not on its line box
  // (qml.md 8.5): measured with the label's own font rather than typed in.
  Text {
    id: capProbe
    visible: false
    text: "H"
    textFormat: Text.PlainText
    font.family: buttonArt.family
    font.pixelSize: Math.round(root.badgeUnit * 0.44)
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

  // The daemon re-sends everything every heartbeat, so most lines say
  // nothing new, and a model re-assigned from one rebuilds every delegate
  // under it (qml.md 5.4).
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
      if (s.motion !== undefined)
        root.motion = Math.max(0, Number(s.motion))
      if (s.safe !== undefined)
        root.safeArea = Math.max(0, Number(s.safe))
      if (s.radius !== undefined)
        root.radiusScale = Math.max(0, Number(s.radius))
      if (s.badge !== undefined) root.badgeStyle = String(s.badge)
      if (s.barh !== undefined) root.barh = Number(s.barh) || 32
      if (s.awake !== undefined) root.awake = !!s.awake
      if (s.cell !== undefined) root.cellUnit = Number(s.cell) || 128
      if (s.corner !== undefined) root.corner = Number(s.corner) || 0
      if (s.dim !== undefined) root.dim = Number(s.dim)
      if (s.fill !== undefined)
        root.tileFill = Math.max(0, Math.min(1, Number(s.fill)))
      if (s.tiles !== undefined && root.fresh("tiles", s.tiles))
        root.tiles = s.tiles
      if (s.band !== undefined && root.fresh("band", s.band))
        root.band = s.band
      if (s.head !== undefined && root.fresh("head", s.head))
        root.head = s.head
      if (s.keys !== undefined && root.fresh("keys", s.keys))
        root.keys = s.keys
      if (s.sel !== undefined) root.sel = Number(s.sel)
      if (s.open !== undefined) root.opened = !!s.open
    } catch (e) {}
  }

  // omapad connects here and streams state; both ends keep trying, so the
  // shell and the daemon can start in either order.
  SurfaceSocket {
    dir: root.socketDir
    name: "quick.sock"
    onLine: text => root.applyState(text)
  }

  IpcHandler {
    target: "omapad-quick"
    function state(): string { return root.opened ? "open" : "closed" }
    function socket(): string { return root.socketDir + "/quick.sock" }
    function ping(): string { return "ok" }
  }

  // One button of the legend, drawn as the button it is.
  component Badge: Item {
    id: badge

    property string label: ""
    property string kind: "face"

    readonly property int unit: root.badgeUnit
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

    // The bar's badge at the bar's resting levels, drawn in the bar's own
    // text colour: this row is the bar's row while the bar is stood down.
    BadgeArt {
      anchors.fill: parent
      drawn: badge.art
      fill: root.stencil
        ? Util.alpha(Color.bar.text, 0.88)
        : Util.alpha(Color.bar.text, 0.20)
      ink: root.stencil ? "transparent" : Color.bar.text
      knockout: root.stencil
    }

    Text {
      id: typed
      visible: badge.drawn === null
      width: badge.width - Math.round(badge.unit * 0.24)
      height: Math.ceil(typed.implicitHeight)
      x: Math.round((badge.width - typed.contentWidth) / 2)
      y: Math.round((badge.height - typed.height) / 2) + root.capNudge
      text: badge.label
      textFormat: Text.PlainText
      color: root.stencil ? Color.menu.background : Color.bar.text
      font.family: buttonArt.family
      // Off the badge rather than off the ladder, the bar's own proportions:
      // a three-letter label is squeezed to the shape rather than stepped
      // down a size.
      font.pixelSize: Math.round(badge.unit * 0.44)
      fontSizeMode: Text.HorizontalFit
      minimumPixelSize: Math.max(6, Math.round(badge.unit * 0.26))
      font.weight: Font.Medium
    }
  }

  PanelWindow {
    id: panel
    visible: root.opened
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    WlrLayershell.namespace: "omapad-quick"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    // The whole screen, the bar's strip included: the bar is stood down
    // while the row is up and its row of buttons is printed here instead.
    exclusionMode: ExclusionMode.Ignore
    mask: Region {}

    Rectangle {
      anchors.fill: parent
      color: Color.menu.scrim
      opacity: root.opened ? 1 : 0
      Behavior on opacity { NumberAnimation { duration: metrics.time.follow } }
    }

    // And as much again as `[menu] dim` asks for, in the theme's own
    // background: the row is read over a game, and the game is what has to
    // recede.
    Rectangle {
      anchors.fill: parent
      color: Util.alpha(Color.menu.background, root.dim)
      opacity: root.opened ? 1 : 0
      Behavior on opacity { NumberAnimation { duration: metrics.time.follow } }
    }

    // -- the head: what is in front, and what the machine is doing -------

    Column {
      id: heading
      anchors.left: parent.left
      anchors.top: parent.top
      anchors.leftMargin: root.sideRoom
      anchors.topMargin: metrics.edge(root.screenH, metrics.gap.huge)
      width: Math.max(0, parent.width / 2 - root.sideRoom)
      spacing: metrics.gap.lg

      Text {
        width: parent.width
        visible: text.length > 0
        text: root.head.k !== undefined ? String(root.head.k) : ""
        textFormat: Text.PlainText
        color: Color.accent
        font.family: metrics.font.family
        font.pixelSize: metrics.type.fine
        font.weight: Font.Medium
        font.capitalization: Font.AllUppercase
        font.letterSpacing: Math.round(metrics.type.fine * 0.09)
        elide: Text.ElideRight
      }

      Text {
        width: parent.width
        visible: text.length > 0
        text: root.head.t !== undefined ? String(root.head.t) : ""
        textFormat: Text.PlainText
        color: Color.menu.text
        font.family: metrics.font.family
        // A heading over the row rather than a title for the screen: the row
        // is the thing being read, and a window's name set at the largest
        // rung outweighed it.
        font.pixelSize: metrics.type.lead
        font.weight: Font.Medium
        elide: Text.ElideRight
      }
    }

    // -- the row and the band under it -----------------------------------

    Column {
      anchors.centerIn: parent
      spacing: root.cellGap

      Row {
        id: row
        spacing: root.cellGap

        Repeater {
          model: root.tiles
          delegate: Item {
            id: tile
            required property var modelData
            required property int index

            readonly property bool selected: tile.index === root.sel
            readonly property bool lit: tile.modelData.on === true
            // How far a tile that is on has sunk into its slot - Menu.qml's
            // `tile.sunk`, for its reason: a switch that is on is a key that
            // has gone down, and a coloured ground was the nav card's word.
            // No plate here: every tile on this row carries `on`, verbs
            // included, and a tile that has a word to say already says it
            // on its own foot.
            property real sunk: tile.lit ? metrics.gap.md : 0
            Behavior on sunk {
              NumberAnimation {
                duration: metrics.time.brisk
                easing.type: Easing.OutCubic
              }
            }
            readonly property bool danger: tile.modelData.x === true
            // The ring, the halo and the mark: the accent, or the theme's
            // urgent colour on the one tile nobody can take back.
            readonly property color mark: tile.danger
              ? Color.urgent : Color.accent
            readonly property int pad: metrics.gap.xl

            width: root.cell
            height: root.cell

            // The halo: four pixels of the mark at a fifth, outside the ring
            // and clear of it, in the gap between cells - the design's focus
            // is a ring with a glow round it rather than a thicker ring.
            Rectangle {
              anchors.fill: parent
              anchors.margins: -root.haloReach
              radius: metrics.radius.tile + root.haloReach
              color: "transparent"
              border.width: root.haloWeight
              border.color: Util.alpha(tile.mark, 0.2)
              opacity: tile.selected ? 1 : 0
              visible: opacity > 0
              Behavior on opacity {
                NumberAnimation { duration: metrics.time.brisk }
              }
            }

            // The face, flush with the slot until the tile is on and `sunk`
            // inside it after, with its own hairline so the rim reads as a
            // gap. Its corner is the slot's less the inset: concentric, or it
            // bulges at the corners.
            Rectangle {
              anchors.fill: parent
              anchors.margins: tile.sunk
              radius: Math.max(0, metrics.radius.tile - tile.sunk)
              color: Util.alpha(root.cellGround,
                                tile.selected ? 1.0 : root.tileFill)
              Behavior on color {
                ColorAnimation { duration: metrics.time.brisk }
              }
              border.width: tile.sunk > 0 ? root.ringWeight : 0
              border.color: root.cellEdge
            }

            // The slot, which is the ring as well: it stays where the cell is.
            Rectangle {
              anchors.fill: parent
              radius: metrics.radius.tile
              color: "transparent"
              border.width: root.ringWeight
              border.color: tile.selected ? tile.mark : root.cellEdge
              Behavior on border.color {
                ColorAnimation { duration: metrics.time.brisk }
              }
            }

            Text {
              id: glyph
              anchors.left: parent.left
              anchors.top: parent.top
              anchors.leftMargin: tile.pad
              anchors.topMargin: tile.pad
              width: metrics.gap.xxxl
              height: metrics.gap.xxxl
              visible: text.length > 0
              horizontalAlignment: Text.AlignHCenter
              verticalAlignment: Text.AlignVCenter
              text: tile.modelData.i !== undefined ? tile.modelData.i : ""
              textFormat: Text.PlainText
              color: tile.mark
              font.family: (tile.modelData.f !== undefined
                            && tile.modelData.f.length > 0)
                ? tile.modelData.f : metrics.font.family
              font.pixelSize: metrics.gap.xxxl
            }

            Text {
              id: tileMeta
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.leftMargin: tile.pad
              anchors.rightMargin: tile.pad
              y: tile.height - tile.pad - tileMeta.height
              visible: text.length > 0
              text: tile.modelData.m !== undefined ? String(tile.modelData.m) : ""
              textFormat: Text.PlainText
              color: Color.menu.text
              opacity: root.inkDim
              font.family: metrics.font.family
              font.pixelSize: metrics.type.fine
              font.capitalization: Font.AllUppercase
              elide: Text.ElideRight
            }

            Text {
              id: tileName
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.leftMargin: tile.pad
              anchors.rightMargin: tile.pad
              y: (tileMeta.visible ? tileMeta.y - metrics.gap.xxs : tile.height - tile.pad)
                - tileName.height
              text: String(tile.modelData.l)
              textFormat: Text.PlainText
              color: Color.menu.text
              font.family: metrics.font.family
              font.pixelSize: metrics.type.body
              font.weight: Font.Medium
              // Two lines before an ellipsis: three words is the label
              // budget, and a cell is narrower than three words at this size.
              wrapMode: Text.WordWrap
              maximumLineCount: 2
              elide: Text.ElideRight
            }
          }
        }
      }

      // The band: the tile in front, worded. Its name and what it is on at
      // the left, and to the right either the bar of its value or the line
      // saying what A does to it.
      Rectangle {
        id: bandCard
        width: root.rowWidth
        height: root.cell
        visible: root.band.l !== undefined
        radius: metrics.radius.tile
        // A plain card, so a plain tile's fill: the menu's nav card takes it
        // the same way.
        color: Util.alpha(root.cellGround, root.tileFill)
        border.width: root.ringWeight
        border.color: root.cellEdge

        readonly property string said: root.band.w !== undefined
          ? String(root.band.w) : ""
        readonly property bool hasBar: root.band.v !== undefined
        readonly property bool armed: root.band.arm === true
        readonly property int inset: metrics.gap.xxxl

        Column {
          id: bandName
          anchors.left: parent.left
          anchors.leftMargin: bandCard.inset
          anchors.verticalCenter: parent.verticalCenter
          width: Math.round(root.cell * metrics.silver * 0.75)
          spacing: metrics.gap.md

          Text {
            width: parent.width
            // The name is the caption over what the tile is on; where it is
            // on nothing, the name is what is printed large instead.
            visible: bandCard.said.length > 0
            text: root.band.l !== undefined ? String(root.band.l) : ""
            textFormat: Text.PlainText
            color: Color.menu.text
            opacity: root.inkMuted
            font.family: metrics.font.family
            font.pixelSize: metrics.type.fine
            font.weight: Font.Medium
            font.capitalization: Font.AllUppercase
            font.letterSpacing: Math.round(metrics.type.fine * 0.09)
            elide: Text.ElideRight
          }

          Text {
            width: parent.width
            text: bandCard.said.length > 0 ? bandCard.said
              : (root.band.l !== undefined ? String(root.band.l) : "")
            textFormat: Text.PlainText
            color: root.band.x === true ? Color.urgent : Color.menu.text
            font.family: metrics.font.family
            font.pixelSize: metrics.type.loud
            elide: Text.ElideRight
          }
        }

        // One column rather than anchors that swap with the tile: a bar and
        // the line under it, or the line alone, centred either way. An
        // anchor switched between two targets by a binding leaves the item
        // anchored to both for a frame, and the line was lost for good.
        Column {
          anchors.left: bandName.right
          anchors.right: parent.right
          anchors.leftMargin: bandCard.inset
          anchors.rightMargin: bandCard.inset
          anchors.verticalCenter: parent.verticalCenter
          spacing: metrics.gap.lg

          // A value's scale: where along its travel it is, drawn by the
          // menu's own slider. It was a rounded trough filling with the
          // accent - the drawing the menu retired twice over (decisions 65
          // and 92) - and beside the menu's scale it read as a different
          // product. The needle lands on the frame the value changes rather
          // than growing towards it (qml.md 8.2.4), so nothing here is
          // animated.
          //
          // Continuous, and never taken: a `live:` number is all that draws
          // one here (a `pad:` setting names its own scale in words), and a
          // nudge on the row writes straight through - there is no press in
          // progress, so nothing for the ghost to mark.
          Travel {
            id: bandTravel
            visible: bandCard.hasBar
            width: parent.width
            height: bandTravel.implicitHeight
            ladder: metrics
            art: controlArt
            value: Math.max(0, Math.min(1, Number(root.band.v) || 0))
            ink: root.spineInk
            trail: root.trailInk
            ghost: root.trailInk
            mark: Color.accent
          }

          Text {
            width: parent.width
            visible: text.length > 0
            text: root.band.t !== undefined ? String(root.band.t) : ""
            textFormat: Text.PlainText
            color: bandCard.armed ? Color.urgent : Color.menu.text
            opacity: bandCard.armed ? 1 : root.inkMuted
            font.family: metrics.font.family
            font.pixelSize: bandCard.hasBar ? metrics.type.fine : metrics.type.body
            wrapMode: Text.WordWrap
            maximumLineCount: 2
            elide: Text.ElideRight
          }
        }
      }
    }

    // -- the foot: what the buttons do -------------------------------------
    //
    // In the game bar's band, at the bar's edge padding and in its sizes -
    // Menu.qml's fullscreen legend, which is the bar's row.
    Item {
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.bottom: parent.bottom
      anchors.bottomMargin: root.safeGap
      height: root.barBand
      visible: root.keys.length > 0

      Row {
        id: legendRow
        anchors.verticalCenter: parent.verticalCenter
        x: parent.width - legendRow.width - root.barSideMargin - root.safeSide
        // The bar's spacings, like everything else in this row.
        spacing: metrics.space(16)

        Repeater {
          model: root.keys
          delegate: Row {
            id: key
            required property var modelData
            spacing: metrics.space(7)

            Badge {
              anchors.verticalCenter: parent.verticalCenter
              label: String(key.modelData.b)
              kind: String(key.modelData.k)
            }

            Text {
              anchors.verticalCenter: parent.verticalCenter
              text: String(key.modelData.n)
              textFormat: Text.PlainText
              // The bar's word at the bar's weight.
              color: Color.bar.text
              opacity: 0.85
              font.family: metrics.font.family
              font.pixelSize: metrics.font.bodySmall
            }
          }
        }
      }
    }
  }

  // Walking a row produces no Wayland input, so the compositor would start
  // the screensaver under it. The same inhibitor every surface binds, and
  // let go of once the pad has been left alone (`[idle] awake_ms`).
  IdleInhibitor {
    window: panel
    enabled: root.opened && root.awake
  }
}
