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
//
// Every size on it comes off `Metrics`' silver ladder - `metrics.type` and
// `metrics.gap`, never `metrics.font` or `metrics.spacing` - except where a
// measurement belongs to something else. Those are the card's own width, two
// stroke weights, and **the whole of the legend along the foot**: badge,
// letter, word and both spacings are GameBar.qml's expressions mirrored
// character for character, because on a fullscreen HUD that row sits in the
// bar's band saying the same kind of thing about the same buttons. A badge
// that grew when the menu opened would read as a different row.
import QtQuick
import QtQuick.Shapes
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons
import qs.Ui

Item {
  id: root

  property bool opened: false
  // **The stopwatch, and it is the surface's rather than the tile's.** What
  // it holds changes between one payload and the next, and `fresh` decides
  // whether to rebuild the page by comparing the tiles it was sent with the
  // tiles it has - so a measurement carried on its own tile is every delegate
  // on this page rebuilt twice a second to move one hand (qml.md 5.4, and
  // `menu_gauge`'s own warning one control along). Off the wire entirely for
  // a page with no chronograph on it.
  property var chronoState: ({})
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
  // Whether the card fills the screen and draws no panel of its own. A
  // setting, from the daemon: a card reads as a menu and a whole screen reads
  // as a page, and across a room the second one is what a HUD is for.
  property bool full: false
  // How dark the screen behind goes, over whatever the theme's own scrim
  // already does. With the compositor blurring as well this is the tint over
  // the blur; with blur off it is the whole of the contrast, which is why it
  // is a setting rather than a number picked here.
  property real dim: 0.6
  // What a corner is rounded by where the compositor rounds nothing, before
  // this surface's own scale. `menu.tile_corner`, and it is the *base* of
  // `metrics.radius` rather than a tile's radius: `Style.cornerRadius` is the
  // first answer and is 0 on plenty of setups - which would leave every state
  // of a tile drawn as the same square.
  property real corner: 23
  // How solid a plain tile's ground is drawn - `menu.tile_fill`. 1.0 is the
  // opaque card this surface was drawn to; below it the scrim shows through,
  // and under that whatever the compositor is blurring behind the surface.
  // **The fill, not the tile**: every label and icon is drawn at full strength
  // whatever this is, because a page you can see through is not the same thing
  // as a page you cannot read.
  property real tileFill: 1.0
  // One cell, square, before this surface's own scale. `menu.cell`: the module
  // the whole page is built from, and the shell cannot read the config.
  property int cellUnit: 128
  // The game bar's own height and edge padding, so a fullscreen HUD can put
  // its row of hints in the band the bar's row sits in. Mirrored from
  // GameBar.qml rather than shared, because the two surfaces are separate
  // components - if one of these changes there, it changes here.
  property int barh: 32
  readonly property int barSideMargin: metrics.space(18)
  readonly property int barBand: Math.max(metrics.space(root.barh),
    root.badgeUnit + metrics.space(3) * 2)
  // The last press, which is the one thing on this surface that is an event
  // rather than a state - `Ripple.qml`'s argument about a click, for the
  // button that answers it. `seq` is the daemon's count for the session and
  // `hit` the tile it landed on; `flashed` is the tile lit right now, which
  // the timer below puts out.
  //
  // `joined` is what keeps a restarted shell quiet. The page is re-sent every
  // `VIEW_HEARTBEAT` seconds, so a serial that has not moved says nothing -
  // but the first line a fresh panel is handed carries whatever the count had
  // reached before it existed, and that press is not one to draw.
  property int pressSeq: 0
  property string pressHit: ""

  // Which page turn the panel has drawn, and how far the page in front still
  // has to travel. A page reached by going *in* - a level down, the next chip
  // along - arrives from the right and settles leftwards; going back out is
  // the same movement mirrored. Content moving the way the press did is what
  // says which direction the page you are now on was reached from, and it is
  // the one thing a fade cannot say.
  property int turn: 0
  property real shift: 0

  // Which row is being held down towards running, and how far it has got:
  // `{ id, ms, armed }`, or null while nobody is holding anything. The game
  // bar's `holding` one surface along, and the same gesture - a tile that
  // cannot be taken back is held rather than pressed, and the tile is the
  // thing being looked at, so the tile is what says how much longer.
  property var holding: null
  // And which row is counting down to running, as `{ id, left }` - the other
  // answer to *are you sure*, and the one that asks nothing of the hand. Null
  // while nothing is counting.
  property var counting: null
  property string flashed: ""
  property bool joined: false
  // How long a tile stays lit, from the daemon: `menu.press_ms`, and 0 there
  // means somebody wants the press silent.
  property int pressMs: 160
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
  // And which row of it, where the tile in front is a card of rows. Its own
  // field rather than a second meaning for `sel`, because the ring, the
  // scroll and the press each want a different one of the two: the grid
  // scrolls to a tile and rings a tile, and only the press reaches the row.
  property string selRow: ""
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

  // The family this surface's words are set in, from the daemon
  // (`[ui] font`); empty is the desktop's own. Not the badges' - those are
  // lettered in the face their drawings were punched with, which is
  // `buttonArt.family`. See `Metrics.fontFamily`.
  property string fontFamily: ""

  // Whether omapad's own bar is holding a strip of the screen under this.
  // The scrim dims the desktop the menu stands in front of, and the bar is
  // not that desktop: while the menu is up it prints what A, B and X do *in
  // the menu*. A legend read through a scrim is the last thing that should go
  // dark, so the window steps out of the strip rather than covering it.
  property bool overBar: false

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

  // What the legend's own band gives up to a cropped edge. It has to be the
  // number `GameBar.qml` uses, arrived at the same way from the same screen:
  // the fullscreen legend sits in the bar's band saying the same kind of
  // thing about the same buttons, and a row that came in off the edge by a
  // different amount than the bar did would be the drift that band exists to
  // avoid.
  readonly property int safeGap: metrics.edge(root.screenH, 0)
  readonly property int safeSide: metrics.edge(root.screenW, 0)

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

  // The drawn buttons, and the font their labels are set in.
  ButtonArt {
    id: buttonArt
  }

  // The parts a control tile is drawn from. Only the furniture is here - what
  // follows the value is geometry, and geometry is this side's.
  ControlArt {
    id: controlArt
  }

  // The ground a tile is drawn on. A function rather than path data: a tile
  // is as wide as the cells it spans, and what is drawn once is the corner.
  TileArt {
    id: tileArt
  }

  // Which of the theme's two inks reads on a given ground.
  Ink {
    id: ink
  }

  // The ink for the one thing here that is filled solid rather than tinted:
  // the nav card you are on. `Color.menu.selectedText` is not it - Omarchy
  // defaults that key to the accent itself, so on nearly every theme the
  // label would be accent on accent and simply not there. Measured instead,
  // and only ever one of the two colours a theme is guaranteed to define.
  readonly property color onAccent:
    ink.on(Color.accent, Color.menu.background, Color.menu.text)

  // The badge the legend is drawn at, and the one thing on this surface that
  // is **not** off the ladder. It is GameBar.qml's own expression, character
  // for character: on a fullscreen HUD this row sits in the bar's band saying
  // the same kind of thing about the same buttons, so a badge that grew
  // when the menu opened would read as a different row. Mirrored rather than
  // shared, the same as `barh` and `barSideMargin` above - if it changes
  // there it changes here.
  readonly property int badgeUnit: metrics.badge(
    Math.max(metrics.space(20), metrics.font.bodySmall + metrics.space(7)))

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

  // A fullscreen card needs more than a card's padding: with none, the first
  // tile sits against the edge of the screen, which on a television is the
  // part of it that is not there.
  //
  // **And it is not the same on both axes.** The design sets a screen's
  // padding at 45 down and 91 across - two rungs apart, because a screen is
  // wider than it is tall and equal padding on both axes reads as too little
  // at the sides. 91 is off the named end of this ladder, so it comes from
  // `rung` like every other size between the names. A card keeps one number:
  // it is only as wide as the page it holds, so there is no width to hold the
  // page off from.
  //
  // **Only the fullscreen one goes through `metrics.edge`.** It is the only
  // one whose padding is a distance from the screen edge; a centred card's
  // is the distance from its own border, and holding that off to a share of
  // the screen would blow a card's inside out to keep a gap the card is
  // nowhere near. The set crops the card's corner there, not the page's, and
  // that is a question about how wide the card may be rather than about its
  // padding. The fullscreen numbers barely move either way: 45 down and 91
  // across are already about a twentieth of a 1080 screen, which is what a
  // safe area asks for - this is what makes that a promise rather than a
  // coincidence at one resolution.
  readonly property int contentMargin: root.full
    ? metrics.edge(root.screenH, metrics.gap.huge) : metrics.gap.xxl
  readonly property int contentMarginX: root.full
    ? metrics.edge(root.screenW, metrics.space(metrics.rung(45, 2)))
    : root.contentMargin
  // The gap between the bands of the card - the head, the title line, the bar
  // of chips, the grid. Five rungs above `cellGap`, because that is the whole
  // of what says the head is not the first row of the grid: a band reads as a
  // band at that distance rather than as a row that has drifted. It is the
  // distance that matters and not the number, so both ends of it moved up a
  // rung together when the head gained a headline worth standing back from.
  readonly property int contentSpacing: metrics.gap.xxl
  // And what the bar stands off the grid, over and above that. A nav card is
  // one cell of the grid, landing on the same columns as the tiles under it -
  // which is the whole argument for the bar being a row of cards, and is also
  // what leaves it reading as the grid's first row at a band's distance. So
  // that seam is `huge`, **the rung two above a band's gap** rather than two
  // of them added up: 45 is on the ladder and 46 is not, and at a scale where
  // the two answers differ by more than a pixel it is the rung that is right.
  // This is only what the `Column`'s own spacing does not already cover, and
  // the bar carries it as trailing air inside its own clip, where nothing is
  // drawn: a `Column` spaces every band of the page the same.
  readonly property int navGap:
    Math.max(0, metrics.gap.huge - root.contentSpacing)
  readonly property int headerHeight: Math.max(metrics.gap.xxxl,
    metrics.type.lead + metrics.gap.sm * 2)
  // How tall the bar is, and it is **one row of the grid**. A nav card is a
  // tile that happens to be a place: the same cell, the same ground, the same
  // corner art, landing on the same columns as the tiles under it. It cost
  // the bar a line of type's height and bought the surface one module instead
  // of two - which is the whole argument for a grid, applied to the row that
  // was still a list of words.
  readonly property int navHeight: root.cellHeight
  // What the title line says, and it is not the same sentence at both levels.
  // Drilled in, it is the page you are on, with the Omarchy menu's trailing
  // ellipsis for "this is where you are, pick something" - the bar is dimmed
  // on the chip you came from and nothing else names the page.
  //
  // At the top level it is nothing, and a group's `detail` was tried here and
  // taken back out. The bar of cards is already saying where you are an inch
  // below; a sentence above it describing the same place is a third band of
  // words over a page whose whole argument is that a grid says more than a
  // list does. The detail is still what a group is written with - it is what
  // `omapad check` prints and what the config is read by - it is just not a
  // thing this surface draws.
  readonly property string lede: root.depth > 0 ? root.title + "…" : ""
  // What the title line costs, which is nothing when it has nothing to say.
  readonly property bool titled:
    root.lede.length > 0 || root.clock.length > 0
  readonly property int headerSpace: root.titled
    ? root.headerHeight + root.contentSpacing : 0
  readonly property int legendHeight: root.keys.length > 0
    ? Math.max(root.badgeUnit, metrics.font.bodySmall) + metrics.space(6) : 0
  // What the legend takes off the bottom. On a card it is its own height and
  // the gap above it; on the whole screen it is the game bar's band, because
  // that is where the row it replaces was.
  readonly property int legendBand: root.legendHeight <= 0 ? 0
    : (root.full ? root.barBand : root.legendHeight + root.contentSpacing)
  // **One module, square, and it does not stretch.** A cell used to be
  // `cell_height` tall and whatever `cols` left of the card wide, which meant
  // the shape of a tile was decided by the width of the screen it landed on -
  // and on a wide one that is a cell six times wider than it is tall. A tile
  // that shape cannot stand an icon over a label, so every tile was a word on
  // a strip, and the bar of nav cards above them was the same strip again.
  //
  // So the cell is a number now, on both axes, and what does not fit scrolls.
  // That is the whole of why the page reads as a grid: a module is a module
  // at any width, and a page wider than the card is what the `Flickable` has
  // always been for vertically.
  //
  // The gap is `gap.xl`, and that is not a coincidence worth deriving. This
  // surface's ladder and the design this grid comes from are **the same
  // ladder**: both climb by sqrt(2), one anchored on the shell's smallest gap
  // and one on 8, and they meet on 16, 23, 32, 45. So the grid's gap is not a
  // fraction of the module - it is the rung the design names, which happens
  // to be an eighth of 128 because that is what a ladder does.
  // **A cell is one step lighter than the page**, and opaque. Two answers
  // before: six percent of the ink over an opaque card, and the page's own
  // colour at 88 percent over whatever the screen was showing - which reads
  // as a *darker* card on a bright desktop and as no card at all on a dark
  // one. The design has one ground for a cell and it is a step up from the
  // shell it sits on, so that is what this is: the page's colour tinted
  // towards the ink, resolved to a solid rather than left translucent.
  //
  // Which also settles what is behind it. A tile drawn on the desktop needs
  // the desktop dimmed to nothing for the step to read at all - `[menu] dim`
  // at 1 is the design's flat ground, and lower is somebody choosing to see
  // what they are standing in front of.
  readonly property color cellGround:
    Qt.tint(Color.menu.background, Util.alpha(Color.menu.text, 0.08))
  // And the line round it, which is a step off the **card** rather than off
  // the page: in the design a card's edge is barely there - seven percent of
  // the ink over the card it bounds - because what makes a card a card is the
  // fill. An edge measured against the page instead comes out as bright as
  // the label, and then the grid reads as a sheet of outlined boxes with
  // nothing in them. Measured off both files: the shell to the card is eight
  // percent of the ink, the card to its line another seven.
  readonly property color cellEdge:
    Qt.tint(root.cellGround, Util.alpha(Color.menu.text, 0.07))
  // And the ground a tile takes when the control on it is **on**: a fifth of
  // the accent over the cell's own colour, resolved to a solid the way
  // `cellGround` is. Left translucent it would be the desktop showing through
  // the one tile on the page with something to say - on a fullscreen page
  // there is nothing behind a tile but the desktop.
  //
  // A fifth, and not the fill it used to be. A solid accent ground is the
  // bar's word for the place you are standing in, and a second one down in
  // the grid outranked it: the tile's own `lit` is the whole argument.
  readonly property color cellLit:
    Qt.tint(root.cellGround, Util.alpha(Color.accent, 0.20))
  // **The three inks, and they are contrast ratios rather than fades.** The
  // design publishes exactly three levels over a card - primary, muted and
  // dim - and publishes them as *measured* colours, each at least 4.5:1 on
  // the ground it is drawn on. Read back as a share of this theme's ink over
  // `cellGround`, `#A3B3AE` and `#99A8A3` on `#2E3A36` come to these two.
  //
  // They replace a scatter of numbers between 0.36 and 0.58 that were each
  // picked at their own call site, and the lowest of them were simply not
  // legible from a sofa. A dim ink is not a decoration: it is the level a
  // second line is read at, so it has a floor.
  readonly property real inkMuted: 0.63
  readonly property real inkDim: 0.58

  // And the ground a *row* inside a card sits on, which is the same step
  // again one level in: the page is a step under the card, the card a step
  // under the row the cursor is on. The design calls it the track colour and
  // uses it for exactly this - the one row of a list that is in front.
  // The line down the side of a card's rows, and the corner at the top of it.
  // Structure rather than state, so it is under every ink this surface reads
  // at: what is *on* the line - the pointer, and the lit length behind it -
  // is the part that says something.
  readonly property color spineInk:
    Util.alpha(Color.menu.text, root.inkDim * 0.35)

  // The line behind the value, on a travel. The accent at half: a tint rather
  // than a fill (qml.md 8.1), and half rather than the fifth a lit ground
  // takes, because a two-pixel line has no area to carry a tint that faint.
  // It is what makes a press visible - the mark moves a few pixels and the
  // length behind it changes by the same few - and it stays under the full
  // accent, so the loudest thing on the line is still where the value is.
  readonly property color trailInk: Util.alpha(Color.accent, 0.5)

  // What a press that has not settled is drawn in: the accent at the share a
  // line behind the value takes, which is the same tint - what tells the two
  // apart is that this one is dashed and sits between where the value was
  // taken from and where it is now. Loud enough to find, quiet enough that
  // what the value has *settled* on stays the thing being read.
  readonly property color ghostInk: Util.alpha(Color.accent, 0.5)

  // **Which font a glyph is set in.** The surface's own, unless the row that
  // carries it named another: a glyph only exists in the font that drew it,
  // and Omarchy's own mark is at U+E900 in `omarchy.ttf` and nowhere in a
  // Nerd Font. The daemon leaves `f` off every row that has nothing to say
  // about it, so this is one `undefined` test and no cost anywhere else.
  function glyphFont(item) {
    return (item && item.f !== undefined && item.f.length > 0)
      ? item.f : metrics.font.family
  }

  readonly property color rowGround:
    Qt.tint(root.cellGround, Util.alpha(Color.menu.text, 0.10))
  readonly property int cellHeight: metrics.space(root.cellUnit)
  readonly property int cellWidth: root.cellHeight
  readonly property int cellGap: metrics.gap.xl

  // **The head's row is not the grid's.** The head is a strip - a name, a
  // time, a line of weather - and the grid's module is a tile's module: a cell
  // the size of a nav card holding one line of type is a band of air with a
  // word in it, and three of them is the head taking a third of the screen
  // before the page has said anything. So the head keeps the title line's own
  // height and the cells stay on the grid's *columns*, which is the half of
  // the module that matters here - the first head line starts where the first
  // nav card and the first tile start.
  readonly property int headRow: metrics.gap.xxxl
  function headHeight(n) {
    return n > 0 ? n * root.headRow + (n - 1) * root.cellGap : 0
  }
  function headY(y) { return y * (root.headRow + root.cellGap) }

  // What the page comes to, edge to edge. The card is sized to it and the
  // grid scrolls inside it when the screen is narrower.
  readonly property int gridWidth: root.cols > 0
    ? root.cols * root.cellWidth + (root.cols - 1) * root.cellGap : 0

  // How far a focused tile draws **outside** its own cell: the ring, and the
  // halo round it. The grid scrolls, so it clips - and a glow drawn past the
  // clip is a glow with a straight edge along the top of the first row and
  // down the left of the first column, which is the one place a focus ring
  // has to look like a ring. So the page is inset by it and the `Flickable`
  // is grown by the same, which moves the clip out without moving a tile: the
  // reach is added here, once, where every cell is placed from.
  readonly property int haloReach: metrics.gap.hairline + metrics.gap.xs

  function cellX(x) {
    return root.haloReach + x * (root.cellWidth + root.cellGap)
  }
  function cellY(y) {
    return root.haloReach + y * (root.cellHeight + root.cellGap)
  }
  function cellSpan(n) {
    return n * root.cellWidth + (n - 1) * root.cellGap
  }
  function rowsHeight(n) {
    return n > 0 ? n * root.cellHeight + (n - 1) * root.cellGap : 0
  }

  // **The fold falls between two cells, never through one.** A tile centres
  // its ink, so the visible part of a cut one carries none at all: a page
  // cropped mid-tile ends in a band of nothing and reads as bad padding
  // rather than as "there is more below". That was measured once against
  // Omarchy's own menu and fixed for the card's rows; it is the same
  // measurement on the fullscreen page and on the columns, and it is one rule
  // now rather than an arithmetic in the one place it first went wrong.
  //
  // `room` is what the band was given; what comes back is what may be
  // *shown* in it, which is a whole number of cells and never more of them
  // than the page has. One cell at least: a screen too small for a module is
  // a tile hanging over the edge rather than a page with nothing on it.
  function wholeCells(room, cell) {
    return Math.max(1, Math.floor(
      (room + root.cellGap) / (cell + root.cellGap)))
  }
  function shownRows(room) {
    return root.rowsHeight(
      Math.min(root.rows, root.wholeCells(room, root.cellHeight)))
  }
  function shownCols(room) {
    return root.cellSpan(
      Math.min(root.cols, root.wholeCells(room, root.cellWidth)))
  }

  // How much of the screen the grid may have before a long group scrolls
  // behind the fold. A card stops at a little over half, because a card that
  // swallowed the screen would read as a page rather than as a menu - which
  // is exactly what `full` asks for, so there it takes whatever the head, the
  // bar and the legend leave.
  //
  // **What the band is given and what it may show are two numbers**, and only
  // here do they come apart. A card is sized to its page, so the cut belongs
  // in the height itself - that is what keeps the card's foot off the floor
  // of the screen. The fullscreen page is given the room whether or not it
  // fills it, because what sits under it is the legend and a legend that
  // floated up under a short page would not be at the foot of anything; there
  // the clip stops short inside the room it was given and the remainder is
  // air under the last row, where nothing is drawn.
  readonly property int gridHeight: {
    var cap = root.full
      ? panel.height - root.contentMargin * 2
        - (root.headRows > 0
           ? root.headHeight(root.headRows) + root.contentSpacing : 0)
        - root.headerSpace
        - root.navHeight - root.navGap - root.contentSpacing
        - root.legendBand
      // **The silver split of the screen**, not a decimal somebody liked: a
      // card that swallowed the screen would read as a page rather than as a
      // menu, and the proportion for "the larger part of this, but a part" is
      // the one the whole surface is set on. 1 - 1/delta is a little under
      // three fifths.
      : Math.round(panel.height * (1 - 1 / metrics.silver))
    if (root.full) return Math.max(root.cellHeight, cap)
    return root.shownRows(cap)
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

  // What the grid was last scrolled to: the tile **and the cell it was in**.
  // Guarded at all because `reveal` runs on every arriving line and the
  // heartbeat brings two a second - scrolling to where the selection already
  // is costs an animation nobody asked for. Keyed on the cell as well as the
  // id because while a tile is being carried the selection does not change
  // and its row does: on the id alone the guard fires, the view stands still,
  // and the tile walks off the bottom of the grid while the button is still
  // being pressed.
  property string revealed: ""

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
      if (s.bar !== undefined) root.overBar = !!s.bar
      // **Only the whole surface may say that something has ended.** Three
      // fields below mean *gone* by being absent - the chronograph, the row
      // being held towards running, the row counting down - and the short
      // push carries none of them, because it carries almost nothing
      // (menu.md: "no `items` key at all", which is what marks it). Read as
      // authoritative, a stream that never mentions the clock wiped its three
      // sub-dials every frame. It went unnoticed while the short push only
      // flew for a gauge; a held ring streams on any page, clocks included.
      var whole = s.items !== undefined
      if (s.cols !== undefined) root.cols = Number(s.cols) || 6
      if (s.rows !== undefined) root.rows = Number(s.rows) || 1
      if (s.headrows !== undefined) root.headRows = Number(s.headrows) || 0
      if (s.badge !== undefined) root.badgeStyle = String(s.badge)
      if (s.radius !== undefined)
        root.radiusScale = Math.max(0, Number(s.radius))
      if (s.keys !== undefined && root.fresh("keys", s.keys))
        root.keys = s.keys
      if (s.items !== undefined && root.fresh("items", s.items))
        root.items = s.items
      // Not through `fresh`: this one is *meant* to differ every time, and
      // what it costs is three properties on one tile rather than a page of
      // delegates. Cleared where the payload has none, so a page without a
      // chronograph draws none - but only where the payload is the *whole*
      // surface. See `whole` above.
      if (whole)
        root.chronoState = s.chrono !== undefined ? s.chrono : ({})
      if (s.groups !== undefined && root.fresh("groups", s.groups))
        root.groups = s.groups
      if (s.head !== undefined && root.fresh("head", s.head))
        root.head = s.head
      if (s.title !== undefined) root.title = s.title
      if (s.clock !== undefined) root.clock = s.clock
      if (s.depth !== undefined) root.depth = s.depth
      if (s.g !== undefined) root.group = Number(s.g) || 0
      if (s.sel !== undefined) root.sel = String(s.sel)
      if (s.row !== undefined) root.selRow = String(s.row)
      if (s.live !== undefined) root.live = s.live
      if (s.full !== undefined) root.full = !!s.full
      if (s.dim !== undefined) root.dim = Number(s.dim)
      if (s.barh !== undefined) root.barh = Number(s.barh) || 32
      if (s.corner !== undefined) root.corner = Number(s.corner) || 0
      // `|| 1` would be wrong here: 0 is a fill somebody asked for - it is
      // the page with no grounds at all - and the fallback is for a field
      // that did not arrive rather than for one that arrived as zero.
      if (s.fill !== undefined)
        root.tileFill = Math.max(0, Math.min(1, Number(s.fill)))
      // After the model above and before the press below: what arrives is a
      // new page, and the slide is that page arriving rather than anything
      // about the press that asked for it.
      if (s.turn !== undefined && Number(s.turn) !== root.turn) {
        root.turn = Number(s.turn)
        root.enterPage(Number(s.way) || 0)
      }
      if (s.press_ms !== undefined) root.pressMs = Number(s.press_ms) || 0
      // Absent while nothing is held, so the line says nothing about a
      // gesture nobody is making - and absent is what ends one. On the whole
      // surface only, for `chronoState`'s reason.
      if (whole)
        root.holding = (s.confirm !== undefined) ? s.confirm : null
      // And which row is counting down, with the whole seconds left on it.
      // Absent while nothing is counting, the same way `confirm` is - so a
      // line that says nothing about one is what ends it here.
      if (whole)
        root.counting = (s.count !== undefined) ? s.count : null
      if (s.hit !== undefined) root.pressHit = String(s.hit)
      if (s.cell !== undefined) root.cellUnit = Number(s.cell) || 34
      if (s.edit !== undefined) root.editing = !!s.edit
      if (s.pick !== undefined) root.picked = String(s.pick)
      if (s.open !== undefined) root.opened = !!s.open
      // Last of all: it is what lights a tile, and the tile it names has to
      // be on the page before it does.
      if (s.n !== undefined) root.pressSeq = Number(s.n) || 0
      root.joined = true
      Qt.callLater(root.reveal)
    } catch (e) {}
  }

  onPressSeqChanged: {
    if (!root.joined || root.pressSeq <= 0 || root.pressMs <= 0) return
    root.flashed = root.pressHit
    flash.restart()
  }

  Timer {
    id: flash
    interval: root.pressMs
    onTriggered: root.flashed = ""
  }

  // The page's own arrival. `slide` runs the offset home rather than a
  // position, so a turn that lands while the last one is still moving
  // continues from wherever it is instead of jumping back to the edge.
  //
  // **A page reached sideways is not a page that faded.** The tiles are the
  // same delegates either way - this is a Repeater over one model, not two
  // pages on screen at once - so what says a page was replaced is the
  // direction the new one came from. One rung of the space ladder is the
  // whole distance: enough to read from a sofa, and short enough that the
  // page is where it belongs before a thumb has moved again.
  function enterPage(way) {
    slide.stop()
    if (way === 0 || metrics.time.follow <= 0) {
      // Motion off, or a turn with no direction to it - the menu opening on
      // a page rather than walking onto one. It is simply there.
      root.shift = 0
      return
    }
    root.shift = way * metrics.gap.huge
    slide.start()
  }

  NumberAnimation {
    id: slide
    target: root
    property: "shift"
    to: 0
    duration: metrics.time.follow
    easing.type: Easing.OutCubic
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
  function followNav() {
    if (bar.width <= 0) return
    for (var i = 0; i < navs.children.length; i++) {
      var card = navs.children[i]
      if (card.here === undefined || !card.here) continue
      if (card.x < bar.contentX)
        bar.contentX = card.x
      else if (card.x + card.width > bar.contentX + bar.width)
        bar.contentX = card.x + card.width - bar.width
      return
    }
  }

  function settleBar() {
    var most = Math.max(0, bar.contentWidth - bar.width)
    bar.contentX = Math.max(0, Math.min(bar.contentX, most))
    root.followNav()
  }

  function settleGrid() {
    var down = Math.max(0, grid.contentHeight - grid.height)
    grid.contentY = Math.max(0, Math.min(grid.contentY, down))
    var across = Math.max(0, grid.contentWidth - grid.width)
    grid.contentX = Math.max(0, Math.min(grid.contentX, across))
  }

  onGroupChanged: Qt.callLater(root.followNav)

  function reveal() {
    if (grid.height <= 0) return
    for (var i = 0; i < root.items.length; i++) {
      if (root.items[i].id !== root.sel) continue
      // The cell is part of the key, not just the id - see `revealed`.
      var key = root.sel + "@" + root.items[i].x + "," + root.items[i].y
        + ":" + root.items[i].w + "x" + root.items[i].h
      if (key === root.revealed) return
      root.revealed = key
      // **What is brought into view is the tile *and its halo*.** The glow is
      // drawn `haloReach` outside the tile's own box and the Flickable clips,
      // so scrolling a box flush with an edge scrolls the ring on that side
      // off with it: the tile arrives selected and looks unmarked down one
      // side. The reach is already in the content on every side - the first
      // column sits at `haloReach` and the content is that much wider - so
      // the resting page is the same page these sums ask for, `contentX` 0
      // for column 0 and the full `contentWidth` for the last.
      var top = root.cellY(root.items[i].y) - root.haloReach
      var bottom = root.cellY(root.items[i].y)
        + root.rowsHeight(root.items[i].h) + root.haloReach
      if (top < grid.contentY)
        grid.contentY = top
      else if (bottom > grid.contentY + grid.height)
        grid.contentY = bottom - grid.height
      // And the same across, now that a page can be wider than the card. The
      // selection lives in the daemon and walks cells it cannot see; this is
      // the only thing that brings the card to it.
      var left = root.cellX(root.items[i].x) - root.haloReach
      var right = root.cellX(root.items[i].x)
        + root.cellSpan(root.items[i].w) + root.haloReach
      if (left < grid.contentX)
        grid.contentX = left
      else if (right > grid.contentX + grid.width)
        grid.contentX = right - grid.width
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

  // A row inside a card is **two** things a cursor names - the card, then the
  // row - and they are sent as two lines in that order. One verb taking both
  // would have to decide what a cursor crossing from one card into another
  // meant, and it means the card first: the row cursor only exists inside the
  // card in front.
  function pointerSelectRow(index, id, item, mouse) {
    if (!root.pointerMoved(item, mouse)) return
    if (root.items[index] && root.items[index].id === root.sel
        && root.selRow === id) return
    root.send("menu select " + index)
    root.send("menu row " + id)
  }

  function pointerActivateRow(index, id) {
    root.send("menu select " + index)
    root.send("menu row " + id)
    root.send("menu press")
    root.pointerAllowSample()
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
  //
  // Only the legend uses this Badge, and the legend is the game bar's row:
  // the same kind of words about the same buttons, printed in the exact
  // band the bar's row sat in. So it is drawn in the bar's own text colour
  // rather than the menu's accent - the menu has taken the bar's place, and
  // buttons that changed colour as the menu opened would read as a different
  // row. The bar's resting levels, not the menu's brighter wash: at rest a
  // filled badge is 0.20 of the foreground, a stencil one keeps 0.88.
  component LegendBadge: Item {
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
      fill: root.stencil
        ? Util.alpha(Color.bar.text, 0.88)
        : Util.alpha(Color.bar.text, 0.20)
      ink: root.stencil ? "transparent" : Color.bar.text
      knockout: root.stencil
    }

    // Typed only where the drawing has no label of its own - a remapped
    // button, a pad printing something new. In the same Fira Code the drawn
    // labels are outlines of, so the two read as one set. On a stencil badge
    // the letter is a hole, so it is the colour of what is behind it here -
    // the menu's own surface - just as the bar's typed letters show the bar's.
    Text {
      id: typed
      visible: badge.drawn === null
      // Placed on whole pixels rather than centred by the anchors: a text
      // item on a half pixel is the one blur antialiasing cannot help.
      width: badge.width - Math.round(badge.unit * 0.24)
      height: Math.ceil(typed.implicitHeight)
      x: Math.round((badge.width - typed.contentWidth) / 2)
      y: Math.round((badge.height - typed.height) / 2) + root.capNudge
      text: badge.label
      textFormat: Text.PlainText
      color: root.stencil ? Color.menu.background : Color.bar.text
      font.family: buttonArt.family
      // Off the badge rather than off the ladder, the bar's own numbers: a
      // three character label has to fit the shape one letter does, and it
      // does that by being squeezed to the width at one shared size rather
      // than by stepping down one - which made a row of badges read as two
      // type sizes.
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
    // `Normal` asks for what is left once every bar has taken its strip, so
    // a card's scrim stops where the game bar starts instead of dimming the
    // row of hints that answers this menu. A fullscreen HUD prints that row
    // itself, so there is nothing down there worth leaving room for - it
    // takes the whole screen and covers both bars, which is what "fullscreen"
    // has to mean or the thing is a screen with a strip cut off it.
    exclusionMode: (root.overBar && !root.full)
      ? ExclusionMode.Normal : ExclusionMode.Ignore

    // This is the one omapad surface that takes the pointer: hover selects a
    // tile, a click picks one, a click on the scrim leaves. The keyboard and
    // the guide still pass clicks through - they are pad-only by design.
    Rectangle {
      anchors.fill: parent
      color: Color.menu.scrim
      opacity: root.opened ? 1 : 0
      Behavior on opacity { NumberAnimation { duration: metrics.time.follow } }
    }

    // And then as much again as `[menu] dim` asks for, in the theme's own
    // background rather than in black: darkening a themed surface towards
    // something that is not in the theme is how a warm palette goes grey.
    Rectangle {
      anchors.fill: parent
      color: Util.alpha(Color.menu.background, root.dim)
      opacity: root.opened ? 1 : 0
      Behavior on opacity { NumberAnimation { duration: metrics.time.follow } }
    }

    MouseArea {
      anchors.fill: parent
      onClicked: root.send("menu close")
    }

    BorderSurface {
      id: card
      anchors.centerIn: parent
      // As wide as the page it holds, and no wider. The cell is a module
      // now, so the card is not a width the grid is fitted into - it is what
      // `cols` modules come to, plus its own padding. The Omarchy menu's 320
      // was the measurement this surface could never keep, and now there is
      // no width of its own here at all.
      //
      // Capped at the screen, where a page too wide for it scrolls sideways
      // the way a page too tall scrolls down - and the cap is cut to whole
      // columns, which is the fold's own rule turned on its side. A card
      // whose last column is a sliver of a tile ends in the same band of
      // nothing the cut row ended in, and what the cut leaves over is a
      // narrower card, which is centred.
      readonly property int roomAcross: parent.width - Style.gapsOut * 2
        - card.borderLeft - card.borderRight - root.contentMarginX * 2
      width: root.full ? parent.width
        : card.borderLeft + card.borderRight + root.contentMarginX * 2
          + root.shownCols(card.roomAcross)
      height: root.full ? parent.height : Math.min(
        card.borderTop + card.borderBottom + root.contentMargin * 2
          + (root.headRows > 0
             ? root.headHeight(root.headRows) + root.contentSpacing : 0)
          + root.headerSpace
          + root.navHeight + root.navGap + root.contentSpacing
          + root.gridHeight
          + root.legendBand,
        parent.height - Style.gapsOut * 2)
      // Nothing of its own when it is the screen: the scrim behind is what
      // the tiles are read against, and a panel drawn over it would be the
      // same rectangle painted twice.
      color: root.full ? "transparent" : Color.menu.background
      borderSpec: root.full ? Border.none()
        : Border.surfaceSpec("menu", "border", Color.menu.border,
                             Math.max(1, metrics.space(2)))
      radius: root.full ? 0 : metrics.radius.card
      opacity: root.opened ? 1 : 0
      Behavior on opacity { NumberAnimation { duration: metrics.time.follow } }

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
        anchors.rightMargin: card.borderRight + root.contentMarginX
        anchors.bottomMargin: card.borderBottom + root.contentMargin
          + root.legendBand
        anchors.leftMargin: card.borderLeft + root.contentMarginX
        spacing: root.contentSpacing

        // The head: **a strip, not a grid**. One row across the top - who
        // this is, what the machine is, and the time at the far end - and
        // nothing on it is selectable. A clock is not a button, and a cursor
        // that can wander into one is a cursor that has to come back out.
        //
        // It was a grid of stacked cells with the clock set at `vast`, which
        // is the one thing the design this surface is built to does not have:
        // a home screen opens on what you came for, and a clock three inches
        // tall is the screen opening on the time. So the lines that were
        // stacked now run along one line, and the cell that reaches the last
        // column hangs off the right edge.
        //
        // **The first line a cell has is the one it says loudly; the rest are
        // facts beside it.** That is one rule for two shapes - a cell with a
        // name over it says the name and murmurs the weather; a cell with
        // only a time says the time - and it is why neither the config nor
        // this delegate needs to know which cell is the clock.
        Item {
          id: strip
          width: parent.width
          height: root.headHeight(root.headRows)
          visible: root.headRows > 0

          // **The strip is measured against the screen, not the module.** The
          // grid below is `cols` fixed cells and scrolls when the screen is
          // narrower than that; the head does not scroll and must not, so a
          // cell placed on the grid's columns would run off the edge and be
          // clipped - which is exactly where the clock went. The config still
          // says `span` in columns, because that is the one vocabulary this
          // surface has for "how much of the width", and here it is read as a
          // share of what there is rather than as a number of modules.
          function at(n) {
            return root.cols > 0
              ? Math.round(strip.width * n / root.cols) : 0
          }

          Repeater {
            model: root.head

            delegate: Item {
              id: headCell
              required property var modelData

              x: strip.at(headCell.modelData.x)
              y: root.headY(headCell.modelData.y)
              width: strip.at(headCell.modelData.x + headCell.modelData.w)
                - strip.at(headCell.modelData.x)
              height: root.headHeight(headCell.modelData.h)

              readonly property string over:
                headCell.modelData.o !== undefined ? headCell.modelData.o : ""
              readonly property string under:
                headCell.modelData.u !== undefined ? headCell.modelData.u : ""
              // The loud line, and everything else joined behind it. A middle
              // dot between facts, which is how this project separates two of
              // them everywhere else it prints a row of them.
              readonly property string loud: headCell.over.length > 0
                ? headCell.over : headCell.modelData.t
              readonly property string facts: {
                var rest = []
                if (headCell.over.length > 0 && headCell.modelData.t.length > 0)
                  rest.push(headCell.modelData.t)
                if (headCell.under.length > 0) rest.push(headCell.under)
                return rest.join("  \u00b7  ")
              }
              // A cell that reaches the last column is the end of the strip,
              // so it hangs off the right edge rather than starting at its
              // own. Positional rather than an index, because where a cell
              // sits is what the config actually says.
              readonly property bool trailing:
                headCell.modelData.x + headCell.modelData.w >= root.cols

              // An `Item` rather than a `Row`, because the two lines are set
              // at two sizes and have to sit on **one baseline** - and a
              // child of a `Row` cannot be anchored to anything, which is the
              // only way to say that.
              Item {
                id: headText
                anchors.verticalCenter: parent.verticalCenter
                height: headLoud.height
                width: headLoud.width + (headFacts.visible
                  ? metrics.gap.xl + headFacts.width : 0)
                // Placed rather than anchored, because an anchor chosen by a
                // ternary leaves both sides unset and the row lands nowhere.
                // Flush with the cell's own edge, unlike a tile: a tile's
                // label is centred inside a ground already inset from its
                // cell, and this prints on nothing at all - so the first
                // head line, the first nav card and the first tile all start
                // on one column.
                x: headCell.trailing
                  ? Math.max(0, headCell.width - headText.width) : 0

                Text {
                  id: headLoud
                  anchors.left: parent.left
                  anchors.top: parent.top
                  text: headCell.loud
                  textFormat: Text.PlainText
                  color: Color.menu.text
                  font.family: metrics.font.family
                  font.pixelSize: metrics.type.body
                  font.weight: Font.Medium
                  // Tracked far out, and only here. A name and a time set
                  // side by side at the top of a screen are a masthead, and
                  // a masthead is spaced: the design sets this one line at
                  // sixteen hundredths of its own letter, which is four
                  // times what a tracked caption takes.
                  font.capitalization: Font.AllUppercase
                  font.letterSpacing: metrics.type.body * 0.16
                  // Time set here is read as a shape rather than spelled
                  // out, and the shape has to hold still: with proportional
                  // figures the line re-lays itself every minute as a 1
                  // replaces an 8.
                  font.features: ({ "tnum": 1 })
                  elide: Text.ElideRight
                }

                Text {
                  id: headFacts
                  visible: headCell.facts.length > 0
                  anchors.left: headLoud.right
                  anchors.leftMargin: metrics.gap.xl
                  anchors.baseline: headLoud.baseline
                  text: headCell.facts
                  textFormat: Text.PlainText
                  color: Color.menu.text
                  opacity: root.inkDim
                  font.family: metrics.font.family
                  font.pixelSize: metrics.type.fine
                  // The one place this surface sets capitals on somebody
                  // else's words, and a typographic decision rather than a
                  // worded one: the config says `%A` and `id -un`, and every
                  // locale's weekday and every machine's name comes back as
                  // it is. Tracked, because caps set without it read as a
                  // word with its letters touching.
                  font.capitalization: Font.AllUppercase
                  font.letterSpacing: metrics.type.fine / 8
                  font.features: ({ "tnum": 1 })
                  elide: Text.ElideRight
                }
              }
            }
          }
        }

        // Where you are, and - since game mode takes Omarchy's bar away and
        // the pad can reach no other clock - whatever the head has no room
        // for. The clock here is empty in the shipped config: it moved up.
        //
        // **Only once you have gone somewhere.** At the top level the bar of
        // chips is already saying where you are, in the same words and an
        // inch below; a line above it saying "Go…" is the card telling you
        // twice. Drilled in, the bar is dimmed on the chip you came from and
        // this is the only thing that names the page you are on.
        Item {
          width: parent.width
          height: visible ? root.headerHeight : 0
          visible: root.titled

          Text {
            anchors.left: parent.left
            anchors.right: clockLabel.left
            anchors.rightMargin: metrics.gap.md
            anchors.verticalCenter: parent.verticalCenter
            text: root.lede
            textFormat: Text.PlainText
            color: Color.menu.text
            opacity: root.inkDim
            font.family: metrics.font.family
            font.pixelSize: metrics.type.lead
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
            font.pixelSize: metrics.type.body
          }
        }

        // The bar. It stays drawn and stays on the card you came from while a
        // submenu is open, dimmed: a bar that vanished would resize the card
        // under a thumb that is aiming at a tile.
        //
        // It was a row of words for a long time, sized to the words. A row of
        // words says every place is worth the same, which is the argument the
        // grid below already won - so it is a row of **cards** now, each one
        // cell of the grid it sits over, landing on the same columns. More of
        // them than fit is what the Flickable is for, and always was.
        Flickable {
          id: bar
          // Cut to whole cards, and a nav card is a cell: the bar sits on the
          // grid's own columns an inch above it, so a half card at the right
          // edge is the one place the two bands would disagree about where
          // the page ends.
          width: root.shownCols(parent.width)
          // The row, and then the air it keeps under itself - see `navGap`.
          height: root.navHeight + root.navGap
          contentWidth: navs.width
          contentHeight: height
          clip: true
          // The daemon owns which card is current, so a drag here would be a
          // second answer to where you are. It scrolls only to follow one.
          interactive: false
          boundsBehavior: Flickable.StopAtBounds
          opacity: root.depth > 0 ? 0.38 : 1
          Behavior on opacity { NumberAnimation { duration: metrics.time.follow } }
          Behavior on contentX { NumberAnimation { duration: metrics.time.follow } }
          onWidthChanged: root.settleBar()
          onContentWidthChanged: root.settleBar()

          Row {
            id: navs
            height: bar.height
            // **The grid's own gap, and this is the one measurement the
            // design does not hand over.** It sets a nav row a rung wider
            // than the grid - 23 against 16 - and gets away with it because
            // its grid is *centred* in the shell while the nav row is flush
            // left, and because nine cards over twelve columns never invites
            // the comparison. Here both bands start on the card's own padding
            // and a nav card is the module exactly, so a wider gap is not a
            // band standing apart - it is eight cards drifting six pixels a
            // column off the tiles beneath them, forty by the end of the row.
            //
            // A card is a cell. The gap between two of them is the gap
            // between two cells.
            spacing: root.cellGap

            Repeater {
              model: root.groups

              delegate: Item {
                id: nav
                required property int index
                required property var modelData

                readonly property bool here: nav.index === root.group
                readonly property bool hasIcon: nav.modelData.i !== undefined
                  && nav.modelData.i.length > 0
                readonly property string meta: nav.modelData.m !== undefined
                  ? nav.modelData.m : ""

                width: root.cellWidth
                height: root.navHeight

                // **A nav card keeps its shape.** A tile is cut back to a
                // facet when it is selected, because a tinted ground is all
                // it has and a theme whose accent sits near its surface would
                // leave the selection to the border alone. A nav card is
                // filled outright - there is no reading in which that is
                // missed - and a row of eight squares where one is a
                // different shape reads as a card that has gone wrong rather
                // than as the one you are on.
                readonly property string outline: "plain"

                Shape {
                  id: navGround
                  anchors.fill: parent
                  preferredRendererType: Shape.CurveRenderer

                  // A hairline whichever card this is. The one you are on
                  // is filled outright, and a heavier line round a filled
                  // card is the state said a second time in the one way that
                  // only makes that card look thicker than its neighbours.
                  readonly property real weight: metrics.gap.hairline

                  ShapePath {
                    // **Solid, not a tint** - the one fill on this surface
                    // that has to carry a label rather than sit under one.
                    // Everywhere else a state is a fifth of the accent and
                    // the theme's own ink still stands on it; here the card
                    // is the accent, so the ink is measured against it.
                    //
                    // **A card you are not on thins with the grid** - the bar
                    // is a row of cells over a grid of them, and a page of
                    // glass under a row of solid cards would be the bar
                    // saying it is a different kind of thing from the tiles
                    // it names. `menu.tile_fill` is one answer about this
                    // surface's cards, and these are cards.
                    //
                    // **The one you are on does not**, and that is not the
                    // selected tile's reason twice over. A tile's label sits
                    // *under* its ground, so thinning the ground costs the
                    // label nothing; this label sits **on** the fill, and
                    // `root.onAccent` is measured against a solid accent - so
                    // an accent at four tenths is a contrast ratio that was
                    // worked out against a colour no longer on the screen,
                    // over whatever the desktop happens to be showing. There
                    // is no fill for it that keeps its own label honest.
                    //
                    // So the setting reaches this card the way it reaches the
                    // selected tile: **by the gap rather than by the alpha.**
                    // Everything around it thins and it does not, which is
                    // the page falling back behind the place you are standing
                    // in - the same sentence the grid tells, told once on the
                    // bar.
                    fillColor: nav.here
                      ? Color.accent
                      : Util.alpha(root.cellGround, root.tileFill)
                    strokeColor: nav.here ? Color.accent : root.cellEdge
                    strokeWidth: navGround.weight > 0 ? navGround.weight : -1

                    // The line fades and **the fill does not**, which is the
                    // design's own asymmetry rather than an omission here:
                    // its nav card transitions box-shadow and border-color
                    // and lets the ground and the ink switch outright. A
                    // filled card crossfading would read as a card being
                    // painted; walking a bar is one card lighting up.
                    Behavior on strokeColor {
                      ColorAnimation { duration: metrics.time.brisk }
                    }

                    PathSvg {
                      path: tileArt.ground(nav.outline,
                                           nav.width - navGround.weight,
                                           nav.height - navGround.weight,
                                           metrics.radius.tile)
                    }
                  }

                  transform: Translate {
                    x: navGround.weight / 2
                    y: navGround.weight / 2
                  }
                }

                readonly property color navInk: nav.here
                  ? root.onAccent : Color.menu.text

                // Whether the card is tall enough to stand the icon over the
                // label. `menu.cell_height` is a setting, so it can be
                // shorter than the two of them - and the label is what
                // survives, because it is the half that names the place.
                readonly property bool roomForIcon: nav.hasIcon
                  && nav.height - nav.inset * 2
                     >= nav.iconSize + navLabel.implicitHeight
                        + (nav.meta.length > 0
                           ? navMeta.implicitHeight + metrics.gap.xxs : 0)
                        + metrics.gap.xxs

                // The card's own inset - `gap.xl`, the rung the design sets
                // a nav card's padding on. It was `gap.sm` before, which on a
                // 128 module is seven pixels: an inset that small reads as
                // text that has slipped off the edge of its card.
                readonly property int inset: metrics.gap.xl

                // **The icon is on the gap ladder, not the type ladder.** A
                // nav card's mark is a picture on a module, the way the inset
                // and the corner are, and a glyph set at a text size inside a
                // cell this big is a word's worth of ink floating in a card's
                // worth of air. `gap.xxxl` is the box the design gives it -
                // 32 against a 128 module - and a glyph set at 32 draws about
                // 26 of ink, which is the drawing inside that box.
                readonly property int iconSize: metrics.gap.xxxl

                // **What is inset is the ink, not the box it is laid out
                // in.** A `Text` reserves a full ascent and descent and a
                // side bearing whether the glyph reaches them or not, so a
                // mark held off the edges by its layout box sits low and
                // right of a label held off the bottom edge by its baseline -
                // the two insets of one card disagreeing by whatever that
                // face leaves spare, which on the shipped icons is six or
                // seven pixels and is exactly the thing the eye picks up.
                //
                // The font's ascent is the wrong correction - the box a glyph
                // is laid out in and the ink it draws are two different
                // questions for an icon face, and using one for the other
                // lands a few pixels the other way. `tightBoundingRect` is
                // the ink itself, so the glyph is centred in a square box and
                // the box is then shifted by however far the ink sits inside
                // it. Every card in the row agrees whatever each one draws.
                TextMetrics {
                  id: navIconInk
                  font: navIconText.font
                  text: navIconText.text
                }

                Item {
                  id: navIcon
                  visible: nav.roomForIcon
                  anchors.left: parent.left
                  anchors.top: parent.top
                  anchors.leftMargin: nav.inset - Math.round(
                    (nav.iconSize - navIconInk.tightBoundingRect.width) / 2)
                  anchors.topMargin: nav.inset - Math.round(
                    (nav.iconSize - navIconInk.tightBoundingRect.height) / 2)
                  width: nav.iconSize
                  height: nav.iconSize

                  Text {
                    id: navIconText
                    anchors.fill: parent
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    // Not keyed on `visible`: that is what decides whether
                    // there is room, and a height that depended on it would
                    // be a binding asking itself a question.
                    text: nav.hasIcon ? nav.modelData.i : ""
                    textFormat: Text.PlainText
                    color: nav.navInk
                    font.family: root.glyphFont(nav.modelData)
                    font.pixelSize: nav.iconSize
                  }
                }

                Text {
                  id: navLabel
                  anchors.left: parent.left
                  anchors.right: parent.right
                  anchors.leftMargin: nav.inset
                  anchors.rightMargin: nav.inset
                  // Placed rather than anchored, because an anchor chosen by
                  // a ternary leaves both sides unset and the text lands
                  // nowhere - the head cell's own trap. The label sits at the
                  // foot of the card under its icon, and in the middle of one
                  // that had no room for one.
                  //
                  // **The baseline is what is inset, not the line box.** A
                  // `Text` carries a descender's worth of room under the
                  // letters whether the word has a descender or not, so a
                  // label held off the bottom edge by its own height sits
                  // visibly lower than the icon sits high - qml.md 8.5's
                  // argument, in the one place on this surface where a word
                  // is measured against an edge rather than centred.
                  y: navMeta.visible
                    ? navMeta.y - navLabel.height - metrics.gap.xxs
                    : (nav.roomForIcon
                       ? nav.height - nav.inset - navLabel.baselineOffset
                       : Math.round((nav.height - navLabel.height) / 2))
                  text: nav.modelData.l
                  textFormat: Text.PlainText
                  color: nav.navInk
                  // Full strength on every card. The one you are on is a
                  // solid fill and needs no help from the others being faint;
                  // a bar of dimmed words is a bar that has to be squinted at
                  // to be walked.
                  font.family: metrics.font.family
                  font.pixelSize: metrics.type.body
                  font.weight: nav.here ? Font.Medium : Font.Normal
                  elide: Text.ElideRight
                }

                // What this place has in it, under its name: a count, a
                // state, a device. It is the half of a nav card that makes
                // the bar worth looking at rather than reading - a row of
                // eight words says only that there are eight places, and a
                // row that also says `7`, `HEADSET`, `82%` has answered a
                // question before anybody walked there to ask it.
                //
                // Set in capitals at the smallest size the surface has and
                // dimmed, so it is a line beside the name rather than a
                // second name. On the filled card it dims against the accent
                // instead, which is the one place `navInk` is not enough on
                // its own - a fill is not a ground the ink can simply be
                // faded over twice.
                Text {
                  id: navMeta
                  visible: nav.meta.length > 0 && nav.roomForIcon
                  anchors.left: parent.left
                  anchors.right: parent.right
                  anchors.leftMargin: nav.inset
                  anchors.rightMargin: nav.inset
                  y: nav.height - nav.inset - navMeta.baselineOffset
                  text: nav.meta
                  textFormat: Text.PlainText
                  color: nav.navInk
                  opacity: root.inkDim
                  font.family: metrics.font.family
                  font.pixelSize: metrics.type.fine
                  font.capitalization: Font.AllUppercase
                  font.letterSpacing: metrics.type.fine / 8
                  font.features: ({ "tnum": 1 })
                  elide: Text.ElideRight
                }

                MouseArea {
                  anchors.fill: parent
                  cursorShape: Qt.PointingHandCursor
                  // A card is walked to, not pressed: the daemon enters it
                  // and the next line says which page that was.
                  onClicked: root.send("menu group " + nav.index)
                }
              }
            }
          }
        }

        // The tiles. Absolutely positioned from the cells the daemon worked
        // out, inside a Flickable that only ever scrolls because `reveal`
        // moved it: the selection lives in the daemon, so a drag here would
        // be a second answer to where you are.
        // The grid sits in a box the Column measures, and the `Flickable`
        // inside it reaches `haloReach` past that box on every side - far
        // enough that a focused tile in the first row keeps its glow, near
        // enough that it stays inside the card's own padding.
        Item {
          id: gridBox
          width: parent.width
          height: root.gridHeight

          Flickable {
            id: grid
            // The box is what the `Column` measured; the clip is what may be
            // shown in it, cut to whole cells on both axes - see
            // `wholeCells`. On a card the two are the same number and this is
            // the box; on the fullscreen page the remainder is air under the
            // last row and outside the last column, where nothing is drawn.
            x: -root.haloReach
            y: -root.haloReach
            width: root.shownCols(gridBox.width) + root.haloReach * 2
            height: root.shownRows(gridBox.height) + root.haloReach * 2
            // The page's own width, which is `cols` modules whatever the screen
            // is. A screen narrower than that scrolls sideways, exactly as one
            // shorter than the page scrolls down - a module that shrank to fit
            // would be the stretched cell this surface just stopped having.
            contentWidth: root.gridWidth + root.haloReach * 2
            contentHeight: root.rowsHeight(root.rows) + root.haloReach * 2
            clip: true
            interactive: false
            boundsBehavior: Flickable.StopAtBounds

            Behavior on contentY { NumberAnimation { duration: metrics.time.follow } }
            Behavior on contentX { NumberAnimation { duration: metrics.time.follow } }
            onHeightChanged: {
              root.settleGrid()
              root.revealed = ""
              Qt.callLater(root.reveal)
            }
            onWidthChanged: {
              root.settleGrid()
              root.revealed = ""
              Qt.callLater(root.reveal)
            }
            onContentHeightChanged: root.settleGrid()
            onContentWidthChanged: root.settleGrid()

            Repeater {
              model: root.items

              // Inlined rather than loaded: a `Component` declared beside this
              // one cannot see the delegate's own scope, and a tile that reads
              // its data through `parent` is the sort of scope lookup this
              // plugin has a rule against. When there is more than one kind to
              // draw, each becomes a file with `required property` inputs and
              // this becomes a Loader over them.
              delegate: Item {
                id: tile
                required property int index
                required property var modelData

                readonly property bool selected: tile.modelData.id === root.sel
                readonly property bool ticked: tile.modelData.on === true

                // **What the tile says about itself that a config file could
                // not.** `m` is a command's last answer, or the word the row
                // said to use until there is one - and off the wire for every
                // tile that has neither, so a page draws what it was written
                // with and never a blank line while a command is thinking. It
                // stands where the written line stands: the heading of a card
                // of rows, the detail of any other tile.
                readonly property string says:
                  (tile.modelData.m !== undefined && tile.modelData.m.length > 0)
                    ? tile.modelData.m : ""

                // **Concentric is a radius, not only a centre.** A rounded
                // rectangle drawn `out` pixels outside another one has to
                // take `out` more corner than it, or the two run parallel
                // down the edges and part at the corners - which is exactly
                // where an eye checks whether two lines belong to one
                // drawing. `metrics.radius.tile` is measured on the ground's
                // own path, so every other figure on this tile - the halo
                // outside it, the press ring inside it, the sheen on its
                // face, the sweep of a hold - asks for its radius by how far
                // it stands from that path, out positive and in negative.
                //
                // It is geometry rather than a ladder rung, for the reason
                // the travel's marks are: the numbers in it are the ring's,
                // so a corner follows the ring at any scale, at any
                // `[ui] radius`, and on a desktop that rounds nothing.
                function concentric(out) {
                  return Math.max(0, metrics.radius.tile + out)
                }
                // **A toggle that is on is a lit card, not a filled one.**
                // It drew a pill with a knob in it once, which is how a switch
                // looks in a *row* of settings; a cell has a whole card's worth
                // of room to say one bit with, so the card became the switch
                // and filled with the accent outright. The card is still the
                // switch. What the fill cost is the two things a state has to
                // leave alone.
                //
                // **A solid accent ground already means something here**, and
                // it is the nav card you are standing on. A page with a lit
                // toggle had two of them, the larger one down in the grid, and
                // a bar that is outshouted by a tile has stopped saying which
                // place you are in.
                //
                // **And a filled tile had nothing left to be selected with.**
                // The ring, the halo and the light are all drawn in the accent,
                // so on an accent ground they came out in `onAccent` - a
                // border, a glow and a face within one step of each other, and
                // no way to tell which tile the selection was on.
                //
                // So a toggle says on the way every other state on this surface
                // says one - a fifth of the accent, with the theme's own ink
                // standing on it (qml.md 8.1.1) - and lights its mark rather
                // than its ground. The fill is the bar's word and the grid does
                // not spend it. What it costs is the same thing it always cost:
                // an off toggle looks like a tile that merely does something.
                // **A tile that knows a bool about itself is a switch**,
                // however the config happened to say so. `control = "toggle"`
                // is one way; an action the daemon can ask a question about is
                // the other - `lock:toggle`, `keep:toggle`, a listed device
                // that knows it is the current one - and from a sofa they are
                // the same tile: a thing that is on or off. They were drawn
                // two different ways for exactly as long as it took to put
                // both on one page, where a lit card and a tick in a corner
                // read as two unrelated facts.
                //
                // A control that draws its own picture is not one of these:
                // `media` carries `on` for *playing* and says so with the
                // play and pause mark it already draws.
                readonly property bool switchable: tile.modelData.k === "toggle"
                  || (!tile.holds && tile.modelData.on !== undefined)
                readonly property bool lit: tile.switchable && tile.ticked
                // Everything drawn on this tile, and it is the theme's own ink
                // whatever the tile is doing: nothing in this grid is filled
                // any more, so every string stands on the cell's own ground and
                // `Ink.on` has nothing left to measure down here. The nav card
                // is where that question lives.
                readonly property color ink: Color.menu.text
                // And everything drawn *in* the accent - the focus ring, its
                // halo, the light on the face, the press. Full strength on a
                // lit tile too: a fifth of the accent is what the ring is read
                // against, which is two states saying two things rather than
                // one colour said twice.
                readonly property color mark: Color.accent
                readonly property bool hasIcon: tile.modelData.i !== undefined
                  && tile.modelData.i.length > 0
                // Whether this tile is tall enough to stack the icon over the
                // label. `menu.cell_height` is a setting, so a tile can be
                // shorter than the two of them together - and a glyph that
                // pushed the label out past the ground it is drawn on would be
                // the page looking broken rather than dense. The label is what
                // survives: it is the half that says which tile this is.
                // Whether the tile is tall enough to stand the mark over the
                // name. `[menu] cell` is a setting, so a tile can be shorter
                // than the two of them together - and a mark that pushed the
                // name out past the ground it is drawn on would be the page
                // looking broken rather than dense. The name is what survives:
                // it is the half that says which tile this is.
                readonly property bool roomForIcon:
                  tile.height - tile.pad * 2 >= tile.iconSize
                    + labelText.implicitHeight + metrics.gap.xs

                // `shift` is the page's own arrival, and it is added here
                // rather than to a container around the grid: a wrapper would
                // be one more Item between the Flickable and every tile for
                // the sake of an offset that is only ever on its way back to
                // zero. It is one number shared by all of them, so a turn
                // moves the page rather than the tiles moving one by one.
                x: root.cellX(tile.modelData.x) + root.shift
                y: root.cellY(tile.modelData.y)
                width: root.cellSpan(tile.modelData.w)
                height: root.rowsHeight(tile.modelData.h)

                // A tile that has been taken off the page is drawn where it
                // sits, faded, rather than moved anywhere: there is nothing to
                // go and find, and putting it back is the same press that took
                // it away.
                opacity: tile.off ? 0.32 : 1.0

                // Which outline this tile is drawn with. The same three cases
                // the colour below splits on, deliberately: the state is said
                // twice, once in ink and once in the silhouette, and a theme
                // whose accent sits close to its surface only has the second
                // one left. TileArt is what turns a name into a path.
                // **Selection does not change a tile's shape.** It did - cut
                // back to a facet - on the argument that a theme whose accent
                // sits close to its surface leaves the selection to the border
                // alone. It has three other answers now: the ground is tinted,
                // the edge is the accent, and the face is lit from above. A
                // fourth, and the only one that changes the silhouette, reads
                // as a tile that has gone wrong beside seven that have not.
                //
                // Being *carried* still does, and that is the difference: a
                // tile in the hand is out of the page's order for as long as it
                // is held, which is a thing about the tile and not about where
                // the selection happens to be.
                readonly property string outline: tile.lifted
                  ? "carried" : "plain"

                // **How much light the focus is worth, which is what the page
                // is worth.** The halo and the sheen are the two lit channels
                // of a selection - a glow outside the ring and a light across
                // the face - and both of them exist to lift one card out of a
                // page of cards. So what they have to overcome is the page,
                // and how much page there is is `menu.tile_fill`.
                //
                // At 1.0 the selected tile's ground is the same ground every
                // other tile has, so the ground says nothing and the light is
                // the whole of what a lit face is: the design as drawn, and
                // this multiplies by one. Below it the selection has gained a
                // channel it did not have - it is the solid card on a page of
                // glass, which at 0.2 is the loudest thing on the screen
                // before a single lumen is spent - and light at full strength
                // is then saying a second time what the ground has already
                // said, louder each step the fill comes down.
                //
                // So the two fall together and by the same number, because
                // they are answering the same question. **The ring does not**:
                // it is not light, it is the mark, and it is the one thing on
                // a selected tile that means *here* at every fill.
                readonly property real focusLight:
                  tile.selected ? root.tileFill : 0

                // A tile that is not selected still needs a ground. A row in a
                // column is bounded by the rows above and below it; a tile has
                // air on four sides, and six of them drawn on nothing read as a
                // scatter rather than as a grid.
                // A tile that is not selected still needs a ground, and on a
                // fullscreen card it needs a solid one: the six percent that
                // reads as a tile against an opaque panel reads as nothing at
                // all against a desktop. With no page behind them the tiles are
                // the only thing there is, so they carry their own.
                Shape {
                  id: ground
                  anchors.fill: parent
                  preferredRendererType: Shape.CurveRenderer

                  // An outline as well as a ground, on every tile and not
                  // only the selected one. A fill at eight percent of the ink
                  // is a tile on a dark theme and nothing at all on a light
                  // one, and six tiles that cannot be found read as a scatter
                  // of labels rather than as a grid.
                  //
                  // **One pixel when it is the accent, too.** It was two,
                  // which is the weight of a thing that has to be seen on its
                  // own - and a focused cell is not outlined on its own here,
                  // it is ringed, haloed and lit.
                  //
                  // **And one weight everywhere, which is the whole of what a
                  // focus ring is.** It went to four for a tile in the hand
                  // and for a card you are standing inside: the same figure
                  // drawn at two sizes, which is two focus marks rather than
                  // one, and the reader has to know the difference between a
                  // thin ring and a thick one to read either. What the thick
                  // one was saying is not *where the cursor is* but *what A is
                  // doing to this* - and the design has a mark for that
                  // already, and it is not a heavier border: a press is a
                  // two-pixel ring drawn **inside** the edge. So `hit` below
                  // is drawn for as long as the press lasts, the ring says
                  // which tile and nothing else, and neither has to be
                  // measured against the other to be read.
                  //
                  // It holds the page's geometry still as well. Every other
                  // figure on a tile is concentric with this ring
                  // (`tile.concentric`), so a ring that changed weight moved
                  // the halo's corner, the sheen's and the press ring's with
                  // it - which is what a corner that did not fit its ring
                  // was.
                  readonly property real weight: metrics.gap.hairline

                  // **Nor does its ink.** `Color.menu.selectedText` was on every
                // string a tile draws, and Omarchy defaults that key to the
                // accent - so a focused cell turned its own label and its own
                // value the colour of the bar underneath them. It is the ink
                // for a ground that has been *filled*, and nothing in this grid
                // is filled: the nav card is, and it measures its own with
                // `Ink.on`.
                //
                // **The face of a focused tile does not change colour.** It
                  // used to take a fifth of the accent, then two fifths on a
                  // screen, which is a filled tile - and a filled tile is what
                  // the bar's nav cards are. Reading a page then meant looking
                  // for the second filled thing on it. The design puts nothing
                  // on the face at all: the card stays the colour every other
                  // card is, and the focus is entirely edge and light.
                  //
                  // A tile in the hand is the exception and keeps its tint,
                  // because being carried is not a selection - it is a tile out
                  // of the page's order for as long as it is held.
                  //
                  // **And how solid that card is drawn is `menu.tile_fill`,
                  // except on the tile you are on.** A selected tile is
                  // always the whole of it: lowering the fill is then how far
                  // the page falls back behind the thing under the thumb, and
                  // the selection comes forward as you walk rather than only
                  // being ringed. At 1.0 there is nothing to come forward
                  // from and the page is exactly what it always was, which is
                  // what makes this safe to ship at 1.0.
                  //
                  // The other two grounds ignore it, because each of them
                  // *is* a state rather than the absence of one: a switch
                  // that is on stays filled, and a tile in the hand keeps its
                  // own tint - which is already translucent, and already
                  // showing what it is being carried over.
                  readonly property real fill:
                    tile.selected ? 1.0 : root.tileFill

                  readonly property color face: tile.lifted
                    ? Util.alpha(Color.accent, root.full ? 0.55 : 0.32)
                    : (tile.lit ? root.cellLit
                                : Util.alpha(root.cellGround, ground.fill))

                  ShapePath {
                    fillColor: ground.face

                    // **A fourth transitioned property, and it is the same
                    // one.** The design fades a ring between two tiles and
                    // switches everything else outright - which was right
                    // while the fill said nothing about the selection. Below
                    // 1.0 it says exactly what the ring says, so a fill that
                    // snapped while the ring faded would be the selection
                    // arriving twice, a tenth of a second apart. At 1.0 the
                    // two colours are equal and this costs nothing.
                    Behavior on fillColor {
                      ColorAnimation { duration: metrics.time.brisk }
                    }
                    // **The edge belongs to the selection alone.** A lit tile
                    // is a ground and a mark and stops there: an accent border
                    // on it would put the state back on the one channel the
                    // focus has nothing else to use, and a tile that is *on*
                    // would be drawn with the line that says which tile you are
                    // *at*. A ring that is already round everything switched on
                    // has stopped being a ring that moves as you walk.
                    strokeColor: tile.selected ? tile.mark : root.cellEdge
                    strokeWidth: ground.weight > 0 ? ground.weight : -1

                    // The design transitions three properties and no others -
                    // box-shadow, border-color and filter - so the ring
                    // *fades* between two tiles while everything else about
                    // them switches outright. The sheen and the halo were
                    // already doing their half of that; this line is the
                    // border-color half, and without it a selection landing
                    // on a tile drew a ring that was suddenly there against a
                    // glow that arrived over 90 ms.
                    Behavior on strokeColor {
                      ColorAnimation { duration: metrics.time.brisk }
                    }

                    // Drawn a border in from the tile's own box, and shifted
                    // back out by half of it below: a stroke straddles the path
                    // it follows, and a selected tile whose outline hung over
                    // the gap would be the one tile on the page that is bigger
                    // than a cell.
                    PathSvg {
                      path: tileArt.ground(tile.outline,
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

                // **The halo.** Four pixels of the accent at a fifth, outside
                // the one-pixel ring and not touching it - the design's focus
                // is a ring with a glow round it rather than a thicker ring,
                // and the difference is what lets a one-pixel line be enough at
                // the distance this is read from. It is drawn outside the
                // tile's own box, in the gap between cells, which is what that
                // gap is for.
                Shape {
                  id: halo
                  anchors.fill: parent
                  preferredRendererType: Shape.CurveRenderer
                  visible: halo.opacity > 0
                  opacity: tile.focusLight
                  Behavior on opacity { NumberAnimation { duration: metrics.time.brisk } }

                  // Four pixels, which is the design's own and a rung of
                  // this ladder as well - `gap.xs`. A stroke weight is off
                  // the ladder by rule (qml.md 8.2.1) because it belongs to
                  // the drawing rather than to the spacing between things;
                  // this one is a *glow* measured in the gap it lives in, so
                  // it is on it.
                  readonly property real weight: metrics.gap.xs
                  // Where the middle of the halo's stroke sits, measured out
                  // from the tile's edge: one pixel clear of it, then half its
                  // own weight further.
                  //
                  // **A hairline clear of the tile's box, not of the ring.**
                  // It was `ground.weight + …`, which reads right and is not:
                  // the ring is drawn *inward*, straddling a path inset by
                  // half its weight, so it occupies the first `weight` pixels
                  // **inside** the tile and the halo has only the box itself
                  // to clear. The sum was a one-pixel error while every ring
                  // was a hairline, and a four-pixel one the moment a ring was
                  // not: the halo went past the gap between cells, the grid
                  // clipped it on the leftmost tile of a page, and the border
                  // came out as two broken lines with a hole between them.
                  readonly property real out:
                    metrics.gap.hairline + halo.weight / 2

                  ShapePath {
                    fillColor: "transparent"
                    strokeColor: Util.alpha(tile.mark, 0.22)
                    strokeWidth: halo.weight

                    PathSvg {
                      // Concentric with the ring, which is a radius as much as
                      // a centre: `tile.concentric` takes the distance from
                      // the path the tile's own radius is measured on, so the
                      // hairline between the two is a hairline at the corners
                      // as well as down the edges.
                      path: tileArt.ground(tile.outline,
                                           tile.width + halo.out * 2,
                                           tile.height + halo.out * 2,
                                           tile.concentric(ground.weight / 2
                                                           + halo.out))
                    }
                  }

                  transform: Translate {
                    x: -halo.out
                    y: -halo.out
                  }
                }

                // **The sheen**, and it is a veil over the card rather than a
                // colour in it: one source above the tile, brightest along the
                // top edge, a third of that a quarter of the way down, gone by
                // a little over half. A leaf held against a window.
                //
                // The first stop is the light itself - a hairline of it, which
                // is what `0.012` of a tile's height comes to - and the rest is
                // the spill off it. Neither is on the ladder and neither is a
                // setting: this is the falloff of a drawn light, so it changes
                // when the light is redrawn and nowhere else. The numbers are
                // the design's own.
                Shape {
                  id: sheen
                  anchors.fill: parent
                  preferredRendererType: Shape.CurveRenderer
                  visible: sheen.opacity > 0
                  opacity: tile.focusLight
                  Behavior on opacity { NumberAnimation { duration: metrics.time.brisk } }

                  readonly property real weight: metrics.gap.hairline
                  // The light that lands on the top edge: the accent's own
                  // hue, lifted. A light source is brighter than the thing it
                  // lights, and the only lighter thing a theme is guaranteed to
                  // have is its own accent taken up.
                  readonly property color lit: Qt.lighter(tile.mark, 1.25)

                  ShapePath {
                    strokeColor: Util.alpha(tile.mark, 0.16)
                    strokeWidth: sheen.weight > 0 ? sheen.weight : -1

                    fillGradient: LinearGradient {
                      x1: 0
                      y1: 0
                      x2: 0
                      y2: sheen.height
                      GradientStop {
                        position: 0.0
                        color: Util.alpha(sheen.lit, 0.5)
                      }
                      GradientStop {
                        position: 0.012
                        color: Util.alpha(tile.mark, 0.08)
                      }
                      GradientStop {
                        position: 0.24
                        color: Util.alpha(tile.mark, 0.03)
                      }
                      GradientStop {
                        position: 0.56
                        color: Util.alpha(tile.mark, 0)
                      }
                      // And the bounce off the floor of the card, which is the
                      // half of a rim light that says the thing has a bottom.
                      GradientStop {
                        position: 0.9
                        color: Util.alpha(tile.mark, 0)
                      }
                      GradientStop {
                        position: 1.0
                        color: Util.alpha(tile.mark, 0.10)
                      }
                    }

                    PathSvg {
                      path: tileArt.ground(tile.outline,
                                           tile.width - sheen.weight,
                                           tile.height - sheen.weight,
                                           tile.concentric(
                                             (ground.weight - sheen.weight)
                                             / 2))
                    }
                  }

                  transform: Translate {
                    x: sheen.weight / 2
                    y: sheen.weight / 2
                  }
                }

                // What a press leaves behind, for `press_ms`. A thumb is on a
                // button that feels the same whatever it did, and most of these
                // tiles leave the page exactly as it was - so a tile that ran
                // its action looks identical to a tile that was never reached.
                // The same silence `Ripple.qml` answers for a click.
                //
                // A ring inside the ground's own edge rather than over it: a
                // press is the tile being pushed, and anything drawn outside
                // would read as a second selection. It follows the same outline
                // the tile is already cut to, so a facet stays a facet.
                readonly property bool flashing:
                  tile.modelData.id === root.flashed

                // **And it is this surface's one mark for *A is on this*.**
                // A flash is a press that is over. A control taken with both
                // axes, a card you have gone into and a tile in the hand are
                // presses that have not been let go of - the same gesture,
                // still happening - so they draw the same ring for as long as
                // they last rather than each inventing a focus of its own. It
                // is the design's own pair and the whole vocabulary of this
                // grid: a hairline ring outside says *here*, a two-pixel ring
                // inside says *and A has hold of it*.
                readonly property bool acting:
                  tile.flashing || tile.taken || tile.carried

                Shape {
                  id: hit
                  anchors.fill: parent
                  preferredRendererType: Shape.CurveRenderer
                  visible: hit.opacity > 0
                  // A binding, not something the timer starts: a delegate
                  // rebuilt mid-flash is born where the state already is -
                  // qml.md 5.5. It is `acting` rather than `flashing`, so a
                  // press that is still being made keeps the ring up.
                  opacity: tile.acting ? 1 : 0
                  Behavior on opacity { NumberAnimation { duration: metrics.time.brisk } }

                  // Two pixels, and **off the ladder on purpose** - qml.md
                  // 8.2.1: a stroke weight belongs to the drawing it outlines
                  // rather than to the spacing between things, and this one
                  // is the design's own `inset 0 0 0 2px`. The nearest rungs
                  // are one and three, and a press held for a sixth of a
                  // second at either reads as a different gesture.
                  readonly property real weight: Math.max(1, metrics.space(2))
                  // Clear of whatever outline the tile already carries, **and
                  // a hairline clear of it** - the two touching is a three
                  // pixel edge, which is the thick ring this pair replaced
                  // rather than the two marks it is meant to be. A line of
                  // the card's own face between them is what makes a press
                  // read as a second figure inside the first.
                  readonly property real inset:
                    ground.weight + metrics.gap.hairline + hit.weight / 2

                  ShapePath {
                    fillColor: "transparent"
                    strokeColor: tile.mark
                    strokeWidth: hit.weight

                    PathSvg {
                      path: tileArt.ground(tile.outline,
                                           tile.width - hit.inset * 2,
                                           tile.height - hit.inset * 2,
                                           tile.concentric(ground.weight / 2
                                                           - hit.inset))
                    }
                  }

                  transform: Translate {
                    x: hit.inset
                    y: hit.inset
                  }
                }

                // **The countdown on a row that has to be held.** A is not
                // a press on these: it starts an announced hold, and a tile
                // that sat there doing nothing for a second while somebody
                // held A would read as a tile that had stopped working. So
                // the tile fills, the way the game bar's badge fills over
                // exactly the same gesture - the bar says which button is
                // counting, and here the page says which row is.
                //
                // Clipped rather than stretched, for the reason the badge's
                // sweep is clipped: the ground is a drawing with corners of
                // its own, and a rectangle laid over it would fill corners
                // the tile does not have.
                readonly property bool holding: root.holding !== null
                  && root.holding !== undefined
                  && root.holding.id === tile.modelData.id
                // Past the tick: it has announced itself and is counting down
                // to running.
                readonly property bool armed:
                  tile.holding && !!root.holding.armed
                // How long the phase it is in lasts. **Never through
                // `metrics.ms`**: a countdown is not motion, and somebody who
                // asked the screen to hold still has not asked for a shorter
                // wait before something irreversible happens.
                readonly property int lapMs:
                  tile.holding ? (Number(root.holding.ms) || 0) : 0

                // Entered from wherever the fill has got to rather than from
                // the step it just took, and called on completion as well as
                // on each change: this grid is a Repeater, every push
                // repaints it, and a delegate rebuilt mid-hold is otherwise
                // born past the transition it needed to see - qml.md 5.5.
                function enterHold() {
                  lap.stop()
                  if (!tile.holding) {
                    lapping.swept = 0
                    return
                  }
                  if (tile.armed) {
                    // The tick has gone. The fill runs back *out* over the
                    // confirm window, so the tile is empty at the moment the
                    // row runs - filling a second time would say "again"
                    // where the gesture says "still".
                    lapping.swept = 1
                    lap.from = 1
                    lap.to = 0
                  } else {
                    lap.from = lapping.swept
                    lap.to = 1
                  }
                  lap.duration = tile.lapMs
                  if (lap.duration > 0) lap.start()
                  else lapping.swept = lap.to
                }

                onHoldingChanged: tile.enterHold()
                onArmedChanged: tile.enterHold()
                Component.onCompleted: tile.enterHold()

                Item {
                  id: lapping
                  property real swept: 0
                  anchors.left: parent.left
                  anchors.top: parent.top
                  width: Math.round(tile.width * lapping.swept)
                  height: tile.height
                  clip: true
                  visible: tile.holding

                  Shape {
                    width: tile.width
                    height: tile.height
                    preferredRendererType: Shape.CurveRenderer

                    ShapePath {
                      // Over the tile's own ground rather than instead of it,
                      // and in the same ink the selection is drawn in: this
                      // is the tile being pressed for a long time, not a
                      // fourth kind of tile.
                      fillColor: Util.alpha(tile.mark, 0.35)
                      strokeColor: "transparent"
                      strokeWidth: -1

                      PathSvg {
                        path: tileArt.ground(tile.outline, tile.width,
                                             tile.height,
                                             tile.concentric(ground.weight / 2))
                      }
                    }
                  }
                }

                NumberAnimation {
                  id: lap
                  target: lapping
                  property: "swept"
                  easing.type: Easing.Linear
                }

                readonly property bool holds: tile.modelData.k !== undefined
                  && tile.modelData.k.length > 0
                // A control with a range, being adjusted right now: both axes
                // belong to it, which is the one state of this surface a press
                // means something else in, so it is drawn as one.
                readonly property bool slider: tile.modelData.k === "slider"
                // The same value, turned. A slider is a length and a knob is
                // an angle, and the stick this surface walks with is the one
                // gesture on the pad that is already a turn - so a held knob
                // is the one tile where the stick stops walking the page.
                // What it draws is `Knob.qml`, which is `Travel.qml`'s
                // question asked round a ring.
                readonly property bool knob: tile.modelData.k === "knob"
                readonly property bool media: tile.modelData.k === "media"
                readonly property bool gauge: tile.modelData.k === "gauge"
                // The one tile with no control on it. It is drawn here as well
                // as on the HUD because a page of readings has to read the same
                // in both places it appears - this is where you turn them on,
                // and a page that looked different once it was on screen would
                // be a page you had to learn twice.
                readonly property bool readout: tile.modelData.k === "readout"
                // The other tile with nothing to press, and the only one that
                // reads nothing at all. It is drawn here as well as on the
                // HUD for the readout's reason: this is the page a clock is
                // put on, and a page that looked different once it was on
                // screen would be a page you had to learn twice.
                readonly property bool clock: tile.modelData.k === "clock"
                // The same face with a stopwatch in it, which is what a
                // chronograph is - and the one tile with nothing to press
                // that has something to press. A is a pusher on it: start,
                // stop, reset, and the legend under the card says which of
                // the three the next press is.
                readonly property bool chrono: tile.modelData.k === "chrono"
                // **A card of verbs, drawn as rows.** It is the one control
                // that holds no value at all: what it holds is the page that
                // would otherwise be a level down, and the argument for it is
                // width. A verb has nothing to show but its name, so a cell
                // spent on one says a single word - and four of them side by
                // side say four words in the room one sentence needs, which
                // is how `Screensaver` ended up drawn as `Screensa…`. Stacked,
                // each row has the whole card to be as long as it is.
                //
                // The rows are the daemon's, like everything else here, and
                // so is which of them the cursor is on: `root.selRow`.
                readonly property bool column: tile.modelData.k === "rows"
                // A card that lists and found one thing. It is not a list
                // then - there is nothing to choose between, and A does
                // nothing on it - so what it holds is drawn as a reading:
                // the heading names it, the one line *is* the answer, and
                // none of the furniture a column needs applies.
                readonly property bool lone: tile.modelData.one === true
                readonly property var lines: tile.modelData.rs !== undefined
                  ? tile.modelData.rs : []
                // **The line's own measurements, and they are not this
                // card's.** The same drawing runs along the foot of a slider,
                // a stepped slider and a reading (`Travel.qml`), so the five
                // of them live on the ladder - `Metrics.qml`'s `spine` - and
                // the arguments for each are written down there. What a row
                // uses them for is here: a segment of the line per row, a
                // cross capping the line at both ends, and the wedge that
                // leaves it beside the row in force.
                readonly property int spineWeight: metrics.spine.weight
                readonly property int spineArm: metrics.spine.arm
                // The stroke that crosses the line at each end of it. **The
                // same size as the marks that end a travel** - `crossEnd`,
                // not the `cross` a stop takes - because the ends of the two
                // drawings are the same claim: *this is as far as it goes*.
                // A card's ends were a stop's size for a pass, which made the
                // list end more quietly than a slider does at exactly the
                // moment the two sit on one page.
                readonly property int spineCap: metrics.spine.crossEnd
                // How far the two marks on the row in force reach out of
                // the line: a stop's own reach, so a card's marks and a
                // travel's are one size.
                readonly property int markReach: metrics.spine.cross

                // **Whether any row on this card can be *in force*.** A card
                // of verbs cannot: `Lock`, `Suspend`, `Logout` are things
                // that happen, and none of them is a thing the machine is
                // currently on. The spine and its caps exist to carry that
                // state - the row in force lights its own length of the line
                // - so on a card with no state they are a line drawn down a
                // list for the sake of drawing one, and the row gets its own
                // left corner back instead.
                //
                // `on` is the question, and a row that has one carries it
                // even when the answer is no: what says a card is stateless
                // is that nothing on it was asked.
                readonly property bool stated: {
                  for (var s = 0; s < tile.lines.length; s++) {
                    if (tile.lines[s].on !== undefined) return true
                  }
                  return false
                }

                // **A card whose rows latch rather than interlock**, which
                // the daemon says and nothing here works out: two rows on at
                // once is what a bank of switches looks like, and it is also
                // what a card of alternatives looks like for the instant a
                // setting is being written.
                //
                // What it changes is which drawing carries the state. A row
                // in force on an ordinary card is a *length* of the line
                // beside it, and a length has one start and one end - so on
                // a card where three rows may be on there is no length to
                // light, and the line would be left saying nothing while
                // three rows said something. The key on each row says it
                // instead, and the line goes.
                readonly property bool many: tile.modelData.many === true
                // Whether the line is drawn at all: a card whose state is a
                // length of it, and no other. A card of verbs has no state
                // to carry and a latching card carries its own on the rows,
                // and both then take their left corner back - see `stated`.
                readonly property bool railed: tile.stated && !tile.many

                // Whether **any** row carries a glyph, or the card spends the
                // slot on keys - one head slot either way, because a name
                // that started in a different place depending on what was
                // beside it would make one list of four read as two lists of
                // two.
                readonly property bool slotted: {
                  if (tile.many) return true
                  for (var i = 0; i < tile.lines.length; i++) {
                    var row = tile.lines[i]
                    if (row.i !== undefined && row.i.length > 0) return true
                  }
                  return false
                }
                // Being carried, or on the page only so it can be put back.
                readonly property bool carried:
                  tile.modelData.id === root.picked && root.editing
                readonly property bool off: tile.modelData.off === true
                readonly property bool taken: tile.modelData.hd === true
                // Whether the short push's held-value fields are *this*
                // tile's. Matched by id rather than by `taken`, because the
                // stream falls silent when nothing is being turned and the
                // last line it sent stands: read as "whatever is held", a
                // ring's number followed the next tile that was taken onto
                // the screen. `hid` is the daemon saying which tile it means.
                readonly property bool streaming:
                  root.live.hid !== undefined
                  && root.live.hid === tile.modelData.id
                // Counting down to running, where the press landed on the
                // tile itself rather than on a row inside one. `Reboot` and
                // `Shutdown` were written both ways on the System page for a
                // while, and a countdown may still land on either, so the
                // number is drawable both ways - a press guarded in one place
                // and silent in the other is worse than not guarding it at
                // all.
                readonly property bool counting: root.counting !== null
                  && root.counting !== undefined
                  && root.counting.id === tile.modelData.id
                readonly property int remaining: tile.counting
                  ? (Number(root.counting.left) || 0) : 0
                // **Out of the page's order**, and a tile in the hand is the
                // only thing that is: it fills with the accent and cuts its
                // corners for as long as it is held, because it has left its
                // cell and is waiting to be put down in another one.
                //
                // **A control being adjusted has not gone anywhere.** A
                // slider, a knob and a gauge were lifted too, on the argument
                // that both axes belong to one while A is down - and a card of
                // rows was excepted for the reason that turns out to be all
                // three's: filled and cut back, the tile is the loudest thing
                // on the page at exactly the moment its number and its travel
                // are what you are trying to read, and the shape it changes to
                // reads as a tile that has gone wrong beside seven that have
                // not. It is still the cell it was. It is being pushed.
                //
                // What a taken tile takes instead is the **press ring** - see
                // `hit`, and `ground.weight` for why it is not a heavier
                // border - over a selection that stays exactly where it was:
                // the hairline outside says which tile, the two-pixel ring
                // inside says A has hold of it, and the ghost on the travel
                // says what this press has done to it.
                readonly property bool lifted: tile.carried

                // One column, not two anchored groups: a tile is 1 cell tall
                // more often than not, and a name anchored to the top and a
                // control anchored to the bottom collide there rather than
                // stacking. A control tile also drops its icon - the control is
                // the picture, and a glyph over a switch is the tile saying the
                // same thing twice in the room it has for one.
                // The design's cell padding, and the one measurement inside a
                // tile that is not a gap between two things: it is the air a
                // card keeps round everything it holds.
                readonly property int pad: metrics.gap.xxl
                readonly property int iconSize: metrics.gap.xxxl

                // **The mark at the top corner, the name at the foot**, both
                // flush with the tile's own edge - a nav card's shape, because
                // a nav card is a tile that happens to be a place and the two
                // must not be drawn to two different rules. It was an icon
                // centred over a label in the middle of the cell, which is what
                // a tile the height of a row of text wants; a module-tall cell
                // holding a centred word is a card with a caption floating in
                // it. The design puts both in corners for the same reason it
                // puts the value at the top of a slider: a card is read from
                // its edges in.
                readonly property bool named: !tile.slider && !tile.knob
                  && !tile.gauge && !tile.readout && !tile.column
                  && !tile.clock && !tile.chrono

                // **A figure sits at the top of the card and its travel
                // along the bottom.** Slider, reading and dead zone all
                // answer the same question - where along something a number
                // is - so they are one head and one track here rather than
                // three stacks, and they are anchored to the two ends of the
                // card the way the design's cell is: the caption and the
                // figure where a card is read first, the bar where it has a
                // floor to sit on. Stacked together and centred they were a
                // block of content floating in a module-tall cell.
                Item {
                  id: figureHead
                  visible: tile.slider || tile.knob || tile.readout
                    || tile.gauge || tile.clock || tile.chrono
                  anchors.left: parent.left
                  anchors.right: parent.right
                  anchors.top: parent.top
                  anchors.leftMargin: tile.pad
                  anchors.rightMargin: tile.pad
                  anchors.topMargin: tile.pad
                  height: figureValue.height

                  Text {
                    anchors.left: parent.left
                    anchors.right: figureValue.left
                    anchors.rightMargin: metrics.gap.sm
                    anchors.baseline: figureValue.baseline
                    text: tile.modelData.l
                    textFormat: Text.PlainText
                    color: tile.ink
                    // **The word that names a value is smaller than the
                    // value.** It was the other way round - a label at the
                    // surface's reading size and the number in fine print
                    // beside it - which says the tile is called Volume and
                    // mentions that it is at 35. A cell exists to say the
                    // number; the word is the caption. Two rungs apart,
                    // tracked capitals and dimmed, so the eye lands on the
                    // figure and finds the name without looking for it.
                    opacity: root.inkMuted
                    font.family: metrics.font.family
                    font.pixelSize: metrics.type.fine
                    font.capitalization: Font.AllUppercase
                    font.letterSpacing: metrics.type.fine / 8
                    elide: Text.ElideRight
                  }

                  Text {
                    id: figureValue
                    anchors.right: parent.right
                    anchors.top: parent.top
                    // Empty until something has answered. On the HUD such a
                    // tile is not drawn at all; here it stays, because this
                    // is the page you come to in order to find out that a
                    // reading has no source on this machine.
                    // The one value on this surface the panel spells
                    // rather than receives, and `Clock.qml`'s header says
                    // why: a number that changes ten times a second cannot
                    // come off a wire written twice a second.
                    // And the ring being turned is the other: a value
                    // followed rather than stepped changes on every frame a
                    // thumb moves, so it rides the short push beside the
                    // thumb (`ht`) rather than rebuilding twenty tiles to
                    // print one number. The words are still the daemon's -
                    // unlike the clock, a level has a unit the panel does
                    // not hold.
                    text: tile.chrono ? clockFace.words
                      : (tile.streaming && root.live.ht !== undefined
                         ? String(root.live.ht)
                         : (tile.modelData.t !== undefined
                            ? tile.modelData.t : ""))
                    textFormat: Text.PlainText
                    // Ink, not the accent. The accent on this cell is the
                    // travel along the bottom - that is the thing that is
                    // *on* - and a number painted the same colour is the
                    // cell saying "on" twice and "how much" nowhere.
                    color: tile.ink
                    font.family: metrics.font.family
                    font.pixelSize: metrics.type.lead
                    // A value is what the machine reports, and most of them
                    // are a number that keeps arriving: a reading is asked
                    // again every second and a slider is redrawn under the
                    // thumb pushing it. With proportional figures the line
                    // re-lays itself every time a 1 replaces an 8, which from
                    // across a room reads as the number twitching rather than
                    // as the number changing. The clock in the head strip is
                    // set this way for the same reason.
                    font.features: ({ "tnum": 1 })
                  }
                }

                // **The travel, and it is one drawing for both kinds of
                // slider and for a reading.** A line with the value marked on
                // it, drawn by `Travel.qml` - which is the spine off a card of
                // rows turned on its side, because a list with the row in
                // force lit and a wedge leaving it *is* a vertical slider.
                // The argument for the line, and for nothing filling up to
                // it, is written there and in menu.md.
                //
                // Which of the two it is, is `seg`: a value with places to
                // stand has them printed on the line as crosses, and a value
                // with a distance to cover has a bare line between its two
                // ends. That is the whole difference between the controls, so
                // it is the whole difference between the drawings.
                //
                // **Only a share has one.** A thermometer's top of scale is a
                // number somebody would have to invent, and a line drawn
                // against an invented maximum says a different thing on every
                // machine it is read on - so the daemon sends no `v` and there
                // is no travel, rather than one that lies.
                Travel {
                  id: figureTravel
                  visible: (tile.slider || tile.readout)
                    && tile.modelData.v !== undefined
                  anchors.left: parent.left
                  anchors.right: parent.right
                  anchors.bottom: parent.bottom
                  anchors.leftMargin: tile.pad
                  anchors.rightMargin: tile.pad
                  anchors.bottomMargin: tile.pad
                  height: figureTravel.implicitHeight
                  ladder: metrics
                  // The page's own, not one per slider: a `ControlArt` cannot
                  // be a singleton, so a component that built its own would
                  // build one per tile on the page.
                  art: controlArt
                  // Bindings rather than anything a signal starts, so a
                  // delegate rebuilt mid-push is born where the value already
                  // is - qml.md 5.5.
                  value: tile.modelData.v !== undefined
                    ? tile.modelData.v : 0
                  stops: tile.modelData.seg !== undefined
                    ? Number(tile.modelData.seg) : 0
                  at: tile.modelData.at !== undefined
                    ? Number(tile.modelData.at) : 0
                  // Where the value stood when A took it, so the line can
                  // show what this press has done to it. Only while it is
                  // held: the daemon leaves the field off a control nobody
                  // is holding, and a negative here is that absence.
                  was: tile.modelData.b !== undefined
                    ? Number(tile.modelData.b) : -1
                  // The line is the card's structure, the trail is how far
                  // along the value has got, the ghost is what this press
                  // changed, and the mark is where it is.
                  ink: root.spineInk
                  trail: root.trailInk
                  ghost: root.ghostInk
                  mark: Color.accent
                }

                // **What is playing is a named tile, not a shape of its
                // own.** It was a mark over a title over an artist, all three
                // centred in the middle of the cell - a fourth way of laying
                // out a card on a surface that now has one. The mark goes
                // where every mark goes, the title where every name goes, and
                // the artist where the line under a name goes.
                //
                // Both lines are somebody else's words and are as long as
                // they are, so they elide rather than the tile growing.
                BadgeArt {
                  id: mediaMark
                  visible: tile.media && tile.roomForIcon
                  anchors.left: parent.left
                  anchors.top: parent.top
                  anchors.leftMargin: tile.pad
                  anchors.topMargin: tile.pad
                  width: tile.iconSize
                  height: width
                  drawn: controlArt.find(
                    "media", tile.modelData.on === true ? "pause" : "play")
                  fill: tile.modelData.on === true
                    ? Color.accent : Util.alpha(Color.menu.text, 0.55)
                }

                Item {
                  id: iconBox
                  // A toggle keeps its mark, where `holds` drops it for every
                  // other control: elsewhere the control *is* the picture and
                  // a glyph over it would be the tile saying the same thing
                  // twice. A toggle has no picture of its own - the mark is
                  // the thing it switches on, and the one glyph on this
                  // surface drawn in a colour of its own, because it is the
                  // one that is also a state.
                  visible: tile.hasIcon && tile.roomForIcon
                    && (!tile.holds || tile.switchable)
                  anchors.left: parent.left
                  anchors.top: parent.top
                  anchors.leftMargin: tile.pad
                  anchors.topMargin: tile.pad
                  width: tile.iconSize
                  height: tile.iconSize

                  Text {
                    id: iconText
                    anchors.fill: parent
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    text: tile.hasIcon ? tile.modelData.i : ""
                    textFormat: Text.PlainText
                    color: tile.lit ? Color.accent : tile.ink
                    font.family: root.glyphFont(tile.modelData)
                    font.pixelSize: tile.iconSize
                  }
                }

                // **A toggle says it is on with its ground and its mark, and
                // that is all it says it with.** A disc sat at the foot beside
                // the name - a third channel, for a theme whose accent sits
                // close to its surface and leaves the other two saying little.
                // Against every theme that does not, it was a full stop nobody
                // had asked a question in front of: the tile was already lit,
                // and the dot repeated it in the corner the name had to be
                // held clear of. A state drawn twice is not a state said
                // twice as well.
                Text {
                  id: detailText
                  // A media tile's second line is the artist and is worth a
                  // one-row tile's room; everything else earns one by being
                  // two rows tall.
                  // The live line where there is one, the written one where
                  // there is not - the same order the card's heading takes.
                  readonly property string line: tile.says.length > 0
                    ? tile.says
                    : (tile.modelData.d !== undefined ? tile.modelData.d : "")
                  visible: tile.named && detailText.line.length > 0
                    && (tile.media || tile.modelData.h > 1)
                  anchors.left: parent.left
                  anchors.right: parent.right
                  anchors.leftMargin: tile.pad
                  anchors.rightMargin: tile.pad
                  y: labelText.y - detailText.height - metrics.gap.xxs
                  text: detailText.visible ? detailText.line : ""
                  textFormat: Text.PlainText
                  color: tile.ink
                  opacity: root.inkDim
                  font.family: metrics.font.family
                  font.pixelSize: metrics.type.fine
                  elide: Text.ElideRight
                }

                Text {
                  id: labelText
                  visible: tile.named
                  anchors.left: parent.left
                  anchors.right: parent.right
                  anchors.leftMargin: tile.pad
                  anchors.rightMargin: tile.pad
                  // The baseline is what is inset, not the line box - a `Text`
                  // keeps a descender's room under the letters whether the word
                  // has one or not, and a name held off the bottom edge by its
                  // own height sits visibly lower than the mark sits high.
                  y: tile.height - tile.pad - labelText.baselineOffset
                  text: tile.modelData.l
                  textFormat: Text.PlainText
                  color: tile.ink
                  font.family: metrics.font.family
                  font.pixelSize: metrics.type.body
                  font.weight: Font.Medium
                  elide: Text.ElideRight
                }

                // **A card of rows**: a heading, the verbs under it, and
                // whatever the card has to say along its foot. The three sit
                // where a card's three things sit everywhere else on this
                // surface - the caption at the top, the line along the
                // bottom, the content between them - so a card that happens
                // to hold a list is still read from its edges in.
                //
                // The heading is the tile's own `l`, set the way the word
                // that names a value is set: two rungs down, tracked
                // capitals, dimmed. It names the card rather than being one
                // of its rows, and a name at the rows' own size would be a
                // fourth row that did nothing when it was pressed.
                //
                // **And a word, with no mark before it.** It carried the
                // tile's glyph for a while and a glyph is not what that slot
                // is: everywhere else on this surface an icon is the big mark
                // in a card's top corner, the thing that says which tile this
                // is from across a room. Set at the caption's size in front of
                // tracked capitals it is none of that - it reads as a bullet,
                // or as a stray chevron somebody left in. A card of rows has
                // marks; they are on its rows, where a row that needs one
                // says so. `build()` refuses the card its own.
                Text {
                  id: columnHead
                  visible: tile.column
                  anchors.left: parent.left
                  // **Held off the right edge as well**, which it was not
                  // while the only thing it could print was a label somebody
                  // had written to fit. A heading that names the window in
                  // front is as long as that window's own title, and a card
                  // is the width it is.
                  anchors.right: parent.right
                  anchors.top: parent.top
                  anchors.leftMargin: tile.pad
                  anchors.rightMargin: tile.pad
                  anchors.topMargin: tile.pad
                  elide: Text.ElideRight
                  text: tile.column
                    ? (tile.says.length > 0 ? tile.says : tile.modelData.l)
                    : ""
                  textFormat: Text.PlainText
                  color: tile.ink
                  opacity: root.inkMuted
                  font.family: metrics.font.family
                  font.pixelSize: metrics.type.fine
                  font.capitalization: Font.AllUppercase
                  font.letterSpacing: metrics.type.fine / 8
                }

                // **The ends of the spine**: the line carries on a little
                // past the first row and the last one, and crosses at both. A
                // line that began exactly at the first row's top edge began
                // nowhere - it read as the edge of the ground behind it
                // rather than as a thing of its own - and an end cap is what
                // says *this is where the list starts* without saying
                // anything else.
                //
                // **A cross, not a corner.** Both turned right at first, which
                // made the two of them a bracket round the rows - and a
                // bracket is a thing that *holds* what is inside it, which is
                // a claim about the rows. A cross is a stop: it says the line
                // ends here and nothing about what the line is next to. The
                // two arms are the same length, so the cap is centred on the
                // line rather than hanging off one face.
                //
                // Siblings of the stack rather than children of it: a
                // `Column` lays its children out, so a child that wanted to
                // sit above the first row would be the first row.
                //
                // **The arms do not cross the line**, and that is not
                // tidiness: every ink on this surface is the theme's own at a
                // share of itself, so a square painted twice is a square
                // painted brighter. The line takes the crossing and the arms
                // start either side of it - the rule a travel's stops keep
                // as well.
                Repeater {
                  model: rowStack.visible && rowStack.height > 0
                    && tile.railed ? 2 : 0

                  delegate: Item {
                    id: cap
                    required property int index
                    // The head, then the foot.
                    readonly property bool head: cap.index === 0
                    // Where the cap's own edge sits.
                    readonly property real edge: cap.head
                      ? rowStack.y - tile.spineArm
                      : rowStack.y + rowStack.height + tile.spineArm
                        - tile.spineWeight

                    // **The cap itself: the travel's own drawing, turned a
                    // quarter.** A card of rows is that line stood up, so the
                    // stroke that ends it is the stroke that ends a slider -
                    // `travel-end-open.svg`, the long one with the line's own
                    // weight of air through the middle, because here the line
                    // carries on past the crossing and a stroke drawn whole
                    // over it would paint the same ink twice.
                    //
                    // Drawn along its own axis and rotated about its middle,
                    // which is why the box is the figure lying down and the
                    // placement is its centre: a drawing positioned by its
                    // rotation as well as turned by it is arithmetic in two
                    // places, and it is the rule the clock's hands are drawn
                    // under.
                    BadgeArt {
                      id: capCross
                      // The middle of the line, which is what the figure is
                      // centred on at both ends.
                      readonly property real mid: rowStack.x
                        + tile.spineWeight / 2
                      // Standing, like the drawing: the width is the line's
                      // own weight and the height follows the figure's aspect
                      // - seven of them. The quarter turn then lays that
                      // across the line, centred on the same point.
                      width: tile.spineWeight
                      height: capCross.implicitHeight
                      x: capCross.mid - capCross.width / 2
                      y: cap.edge + tile.spineWeight / 2
                        - capCross.height / 2
                      rotation: 90
                      drawn: controlArt.find("travel", "end-open")
                      fill: root.spineInk
                    }

                    // And the line's own run past the rows, which is what
                    // the cap caps: the arms take the crossing at the far
                    // end of it, so nothing here is painted twice.
                    Rectangle {
                      x: rowStack.x
                      y: cap.head
                        ? cap.edge
                        : rowStack.y + rowStack.height
                      width: tile.spineWeight
                      height: tile.spineArm
                      color: root.spineInk
                    }
                  }
                }

                // What the card has to say that is not one of its rows -
                // `AUTO-SLEEP 30 MIN` in the design, which is a fact about
                // the whole card rather than about any one verb in it. It is
                // the tile's own `detail`, and it is set as the heading is:
                // the two are the same kind of thing at the two ends of the
                // card.
                Text {
                  id: columnFoot
                  visible: tile.column && tile.modelData.d !== undefined
                    && tile.modelData.d.length > 0
                  anchors.left: parent.left
                  anchors.right: parent.right
                  anchors.bottom: parent.bottom
                  anchors.leftMargin: tile.pad
                  anchors.rightMargin: tile.pad
                  anchors.bottomMargin: tile.pad
                  text: columnFoot.visible ? tile.modelData.d : ""
                  textFormat: Text.PlainText
                  color: tile.ink
                  opacity: root.inkDim
                  font.family: metrics.font.family
                  font.pixelSize: metrics.type.fine
                  font.capitalization: Font.AllUppercase
                  font.letterSpacing: metrics.type.fine / 8
                  elide: Text.ElideRight
                }

                // The rows. Above the tile's own `picker`, which fills the
                // whole card: a cursor inside one of these names the row it
                // is over, and the card underneath would otherwise take the
                // hover and answer with the card.
                // The one line a listing found, set as the value it is. The
                // size every value on this surface is set in, in the middle
                // of the card between the heading and the foot - which is the
                // shape a `readout` tile already has, because this is one.
                Text {
                  visible: tile.lone
                  anchors.left: parent.left
                  anchors.right: parent.right
                  anchors.leftMargin: tile.pad
                  anchors.rightMargin: tile.pad
                  anchors.verticalCenter: parent.verticalCenter
                  text: (tile.lone && tile.lines.length > 0)
                    ? tile.lines[0].l : ""
                  textFormat: Text.PlainText
                  color: tile.ink
                  font.family: metrics.font.family
                  font.pixelSize: metrics.type.lead
                  wrapMode: Text.WordWrap
                  maximumLineCount: 2
                  elide: Text.ElideRight
                }

                Column {
                  id: rowStack
                  z: 1
                  visible: tile.column && !tile.lone
                  anchors.left: parent.left
                  anchors.right: parent.right
                  anchors.leftMargin: tile.pad
                  anchors.rightMargin: tile.pad
                  // Between the heading and the foot rather than under one of
                  // them: the card is as tall as its `span` says and the rows
                  // are as many as there are, so what is left over is air at
                  // both ends. A stack pinned under the heading would leave
                  // all of it at the bottom, which reads as a card that has
                  // been cut short.
                  anchors.verticalCenter: parent.verticalCenter
                  // **Nothing between the rows**, and that is what makes the
                  // spine one line rather than a dashed one: each row draws
                  // its own full-height segment of it, so the segments meet.
                  // A Column child cannot be the whole spine - a Column lays
                  // its children out, so a child asking for the Column's
                  // height is a binding loop, and the one that happened drew
                  // a line down the whole card with no rows on it.
                  //
                  // The rows do not run into each other for it: each already
                  // holds its name off its own top and bottom by a rung, so
                  // what was between them was air twice over.
                  spacing: 0

                  Repeater {
                    model: tile.lines

                    delegate: Rectangle {
                      id: line
                      required property var modelData

                      // A row is in front only while somebody is **inside**
                      // the card. Selected is not enough: until A is pressed
                      // up and down belong to the page, and a row drawn as
                      // the one in front would be promising a walk that press
                      // does not make. So a card standing in the grid shows
                      // its rows and which of them is in force, and no cursor
                      // at all.
                      // **Two marks, and they answer two questions that are
                      // often two different rows.**
                      //
                      // `ticked` is the row in force, and it is a *state*: it
                      // is true whether or not this card is the one selected,
                      // let alone the one somebody is inside. So the mark for
                      // it is drawn always - the pointer, and the row's length
                      // of the spine lit behind it.
                      //
                      // `here` is the row A would run, which only exists once
                      // A has gone in: up and down belong to the page until
                      // then, so a mark for it outside the card would be
                      // promising a walk that press does not make.
                      readonly property bool here: tile.selected && tile.taken
                        && root.selRow === line.modelData.id
                      readonly property bool ticked: line.modelData.on === true
                      // **Whether the row was asked**, which is not whether
                      // the answer was yes: a key is drawn for every row on
                      // a latching card that has an answer at all, because a
                      // bank with a gap in it is a bank whose gap means
                      // something. A row nothing could answer for - a verb
                      // among switches, a reading the mixer has not sent yet
                      // - leaves the slot empty rather than drawing a key
                      // that can never go down.
                      readonly property bool asked:
                        line.modelData.on !== undefined
                      readonly property bool marked:
                        line.modelData.i !== undefined
                        && line.modelData.i.length > 0
                      readonly property bool flashing:
                        tile.selected && root.flashed === line.modelData.id
                      // The hold on a row that cannot be taken back. The
                      // daemon names the row rather than the card, so Logout
                      // fills and the three verbs beside it do not.
                      readonly property bool holding: root.holding !== null
                        && root.holding !== undefined
                        && root.holding.id === line.modelData.id
                      readonly property bool armed:
                        line.holding && !!root.holding.armed
                      // Counting down to running, and how long is left. The
                      // daemon names the row rather than the card, so one row
                      // counts and the verbs beside it do not.
                      readonly property bool counting: root.counting !== null
                        && root.counting !== undefined
                        && root.counting.id === line.modelData.id
                      // **Not `left`.** An `Item` has one and it is FINAL,
                      // so declaring it here fails the whole component - and
                      // the way that fails is the panel never coming up at
                      // all, with one line about it in the shell's log.
                      readonly property int remaining: line.counting
                        ? (Number(root.counting.left) || 0) : 0
                      // Never through `metrics.ms` - a countdown is not
                      // motion, and somebody who asked the screen to hold
                      // still has not asked for a shorter wait in front of
                      // something irreversible. The tile's rule, one level in.
                      readonly property int lapMs:
                        line.holding ? (Number(root.holding.ms) || 0) : 0

                      readonly property bool explained:
                        line.modelData.d !== undefined
                        && line.modelData.d.length > 0

                      width: rowStack.width
                      height: lineName.implicitHeight
                        + (line.explained
                           ? lineWhy.implicitHeight + metrics.gap.xxs : 0)
                        + metrics.gap.lg * 2
                      // The row itself draws nothing: it is the box the rest
                      // is laid out in, and what fills it starts a spine's
                      // width along - see `lineGround`.
                      color: "transparent"

                      // Two rungs under the card's own corner - the design's
                      // radius for a row against its radius for the card that
                      // holds it - and **square down the left** where there is
                      // a spine, so whatever is filled meets it instead of
                      // curving away and leaving a sliver of card between the
                      // two. A card with no state has no spine, and the row
                      // takes its corner on all four.
                      readonly property real corner:
                        metrics.rung(metrics.radius.tile, -2)
                      // How far in everything the row fills starts: the
                      // spine's own width where there is one, and the row's
                      // own edge where there is not.
                      readonly property int inset:
                        tile.railed ? tile.spineWeight : 0

                      // **The ground is the cursor**, and only while the card
                      // has been entered. It said which row was in force for
                      // a while, and then the pointer said that too - which
                      // is one thing drawn twice, and the ground was the half
                      // that could not also say where A would land.
                      //
                      // It starts where the spine ends rather than under it.
                      // Every ink here is the theme's own at a share of
                      // itself, so a line drawn over a ground is a different
                      // line from the one drawn over the card beside it - and
                      // a spine that changed colour for the length of one row
                      // read as the two of them overlapping, which is exactly
                      // what it was.
                      Rectangle {
                        id: lineGround
                        anchors.fill: parent
                        anchors.leftMargin: tile.railed ? tile.spineWeight : 0
                        color: line.here ? root.rowGround : "transparent"
                        topRightRadius: line.corner
                        bottomRightRadius: line.corner
                        // Square down the left only where there is a spine
                        // for it to meet. With none, the row is a shape of
                        // its own and takes its corner on all four.
                        topLeftRadius: tile.railed ? 0 : line.corner
                        bottomLeftRadius: tile.railed ? 0 : line.corner
                      }

                      // The countdown, swept across the row the way it is
                      // swept across a tile - clipped rather than stretched,
                      // and entered from wherever it has got to, because this
                      // grid is a Repeater and a delegate rebuilt mid-hold is
                      // born past the transition it needed to see (qml.md
                      // 5.5).
                      function enterHold() {
                        lineLap.stop()
                        if (!line.holding) {
                          lineFill.swept = 0
                          return
                        }
                        if (line.armed) {
                          // The fill runs back out over the confirm window,
                          // so the row is empty at the moment it runs.
                          lineFill.swept = 1
                          lineLap.from = 1
                          lineLap.to = 0
                        } else {
                          lineLap.from = lineFill.swept
                          lineLap.to = 1
                        }
                        lineLap.duration = line.lapMs
                        if (lineLap.duration > 0) lineLap.start()
                        else lineFill.swept = lineLap.to
                      }

                      onHoldingChanged: line.enterHold()
                      onArmedChanged: line.enterHold()
                      Component.onCompleted: line.enterHold()

                      // Clipped rather than stretched, the way the tile's
                      // own sweep is: the ground has corners and a rectangle
                      // laid over it would fill corners the row does not
                      // have. The clip is square and the fill inside it
                      // carries the row's radius, so the trailing edge is
                      // rounded and the leading edge is not - which is what a
                      // sweep looks like.
                      Item {
                        id: lineFill
                        property real swept: 0
                        anchors.left: parent.left
                        anchors.leftMargin: line.inset
                        anchors.top: parent.top
                        width: Math.round(
                          (line.width - line.inset) * lineFill.swept)
                        height: line.height
                        clip: true
                        visible: line.holding

                        Rectangle {
                          width: line.width - line.inset
                          height: line.height
                          // The row's own corners: square where it meets the
                          // spine, rounded where it leaves the card - and
                          // rounded at both ends where there is no spine.
                          topRightRadius: line.corner
                          bottomRightRadius: line.corner
                          topLeftRadius: tile.railed ? 0 : line.corner
                          bottomLeftRadius: tile.railed ? 0 : line.corner
                          color: Util.alpha(tile.mark, 0.35)
                        }
                      }

                      NumberAnimation {
                        id: lineLap
                        target: lineFill
                        property: "swept"
                        easing.type: Easing.Linear
                      }

                      // The press, as the tile answers one: a ring inside the
                      // row's own edge, clear of it, so a row being pressed
                      // reads as two lines rather than one thick one.
                      Rectangle {
                        anchors.fill: parent
                        anchors.leftMargin: line.inset
                        // The row's own corners: square where it meets the
                        // spine, rounded where it leaves the card - and
                        // rounded at both ends where there is no spine.
                        topRightRadius: line.corner
                        bottomRightRadius: line.corner
                        topLeftRadius: tile.railed ? 0 : line.corner
                        bottomLeftRadius: tile.railed ? 0 : line.corner
                        color: "transparent"
                        border.color: tile.mark
                        // The design's `inset 0 0 0 2px`, off the ladder for
                        // the reason every stroke weight is - qml.md 8.2.1.
                        border.width: Math.max(1, metrics.space(2))
                        // A binding rather than something the timer starts:
                        // a delegate rebuilt mid-flash is born where the
                        // state already is.
                        opacity: line.flashing ? 1 : 0
                        visible: opacity > 0
                        Behavior on opacity {
                          NumberAnimation { duration: metrics.time.brisk }
                        }
                      }

                      // **The lit segment of the spine, and the mark on
                      // it.** Together they say one thing: *this is the row A
                      // would act on*. The ground says which row is in force,
                      // which is a different question and often a different
                      // row - `Start in` shows both at once.
                      //
                      // **The spine**, one row's worth of it. Every row draws
                      // it, so a stack of words reads as a list rather than
                      // as four labels that happen to be under one another -
                      // and the row in force lights its own length of it.
                      // Full height and no gap between rows, so the segments
                      // meet and the line is one line.
                      Rectangle {
                        visible: tile.railed
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        width: tile.spineWeight
                        color: line.ticked ? Color.accent : root.spineInk
                      }

                      // **The mark on the line: two strokes, at the row's
                      // own ends.** They bracket the lit length rather than
                      // pointing at the middle of it, which is the truer
                      // thing to say - what is in force on a card is a
                      // *length* of line, and these are where it starts and
                      // stops. The line's own weight and a stop's own reach,
                      // to the right of the line and never across it, so the
                      // card has one figure on it and no exceptions.
                      //
                      // It was a wedge in the middle for four passes, and
                      // before that a tick at the far end of the row, a radio
                      // ring at its head, and a pointer. A wedge points, and
                      // pointing is right when the thing pointed at is beside
                      // the mark - but the row is not beside it, it is the
                      // length behind it.
                      //
                      // Drawn whether or not the card has been entered: what
                      // they mark is a *state*, and opaque over whatever the
                      // row is filled with.
                      Repeater {
                        // With the line gone they have nothing to bracket:
                        // a latching card says which rows are on with the
                        // key at the head of each, and two marks against the
                        // card's own edge would be a length measured on a
                        // line that is not there.
                        model: line.ticked && tile.railed ? 2 : 0

                        delegate: BadgeArt {
                          required property int index
                          x: tile.spineWeight
                          y: index === 0
                            ? 0 : line.height - tile.spineWeight
                          width: tile.markReach
                          height: implicitHeight
                          // The one stroke on either drawing that is not a
                          // cross, so the one with a drawing of its own: two
                          // units of reach by one of weight, out of one face
                          // of the line.
                          drawn: controlArt.find("travel", "side")
                          fill: Color.accent
                        }
                      }

                      // **The slot at the head of the row**: the row's
                      // glyph where it carries one, and the card's key where
                      // the card latches. A fixed slot rather than a mark
                      // measured at the call site, so every row's name starts
                      // in the same place whatever is beside it - and one
                      // slot rather than two, because a row that carried
                      // both would be asking a reader to learn which of two
                      // marks at its head means which.
                      Item {
                        id: lineMark
                        // The slot is the card's and what is in it is the
                        // row's, so an unmarked row among marked ones is a
                        // gap in the column rather than a name out of line.
                        // It clears the rail: the rail is two pixels at the
                        // row's own edge and this is a rung further in. A card
                        // with no state has no rail to clear, so the words sit
                        // a rung nearer their own ground - the column moved
                        // left with the line that was holding it out.
                        width: tile.slotted ? metrics.gap.xl : 0
                        height: metrics.gap.xl
                        anchors.left: parent.left
                        anchors.leftMargin: tile.railed
                          ? metrics.gap.xxl : metrics.gap.lg
                        anchors.verticalCenter: lineName.verticalCenter

                        Text {
                          visible: line.marked
                          anchors.fill: parent
                          horizontalAlignment: Text.AlignHCenter
                          verticalAlignment: Text.AlignVCenter
                          text: line.marked ? line.modelData.i : ""
                          textFormat: Text.PlainText
                          color: line.here ? Color.accent : tile.ink
                          opacity: line.here ? 1 : root.inkMuted
                          font.family: root.glyphFont(line.modelData)
                          font.pixelSize: metrics.type.body
                        }

                        // **The key, on a card whose rows latch.** It is the
                        // one drawing this card was right to refuse while
                        // its state was a length of line - a ring at the
                        // head of every row was tried and dropped, because
                        // the line already changed colour at the row it
                        // meant and a second mark saying the same thing is a
                        // mark to learn for nothing. A bank of switches has
                        // no such line: there is no *one* row to point at,
                        // so what says a row is on has to be on the row.
                        //
                        // A key rather than a tick. A tick is a mark made in
                        // a box by somebody filling a form in; a key is a
                        // thing on the front of a radio that is down or up,
                        // and this is a bank of them - the state is the
                        // key's own, and reading it is reading whether
                        // anything is lit in the window rather than reading
                        // a glyph. It also keeps the card to the two figures
                        // it already has: a rectangle and a stroke.
                        //
                        // **The slot and what is in it are two drawings**
                        // (`key-ring.svg`, `key-lit.svg`), on one canvas and
                        // one box, the way a button and the label punched
                        // through it are. Two because they are painted in two
                        // colours: the ring takes the card's own line ink and
                        // does not light with the row, and the window does.
                        //
                        // The key's corner is **the drawing's** rather than
                        // the ladder's, which is the one thing it gave up by
                        // becoming art. It had already stopped following the
                        // ladder in the place that mattered: a rung under the
                        // row's corner, then capped at a quarter of its own
                        // side, because past that a 16-pixel square is not a
                        // rounder key, it is a pill - a different shape, and
                        // the shape of the switch on a tile rather than of a
                        // key on a bank. What is drawn is that cap. A theme
                        // that rounds nothing at all now keeps a rounded key,
                        // which is the trade: the figure is one a hand reads
                        // at 16 pixels, and it is redrawn in `shapes/` rather
                        // than computed here.
                        Item {
                          id: lineKey
                          visible: tile.many && line.asked
                          anchors.centerIn: parent
                          width: metrics.gap.xl
                          height: metrics.gap.xl

                          // The card's own line, at the card's own weight:
                          // the keys are what makes this stack a list, which
                          // is the job the line has on every other card.
                          BadgeArt {
                            anchors.fill: parent
                            drawn: controlArt.find("key", "ring")
                            fill: root.spineInk
                          }

                          // **What is in the window when the key is down.**
                          // The state is a thing that is *there* rather than
                          // a colour the key turns, which is qml.md 8.1.1
                          // read at a key's size: a theme whose accent sits
                          // close to its card exists, and on one of those the
                          // difference between an empty window and a full one
                          // is still a difference.
                          //
                          // One stroke of air inside the ring, and square
                          // where the ring is round - a shape drawn that far
                          // inside another takes that much less corner
                          // (qml.md 8.2.6), and at this size two equal radii
                          // read as the inner one bulging. Both of those are
                          // in the drawing now.
                          BadgeArt {
                            visible: line.ticked
                            anchors.fill: parent
                            drawn: controlArt.find("key", "lit")
                            fill: Color.accent
                          }
                        }
                      }

                      Text {
                        id: lineName
                        anchors.left: lineMark.right
                        anchors.right: parent.right
                        // Nothing where the card has no slot: an empty
                        // `Item` is still anchored, so its right edge is
                        // already the inset the row is written to and a
                        // second one would indent every row twice.
                        anchors.leftMargin: tile.slotted
                          ? metrics.gap.sm : 0
                        // The mark slot starts clear of the pointer, so this
                        // needs nothing of its own - see `lineMark`.
                        // Out of the number's way while one is counting: a
                        // name running under the seconds left is the one
                        // row on the page where both matter at once.
                        anchors.rightMargin: line.counting
                          ? metrics.gap.huge : metrics.gap.lg
                        // Placed from the top rather than centred: a row with
                        // a line under it is two lines centred *together*,
                        // and an anchor switched by a ternary leaves both
                        // unset - which is a thing that happens silently.
                        y: metrics.gap.lg
                        text: line.modelData.l
                        textFormat: Text.PlainText
                        color: tile.ink
                        // **Full ink for the row in front and for the row
                        // in force**, muted for the rest - the design's own
                        // two levels, saying two different things at once.
                        // The cursor is already a ground and a ring, so what
                        // the ink adds is the second half of the radio's
                        // answer: the chosen row reads as chosen from across
                        // a room whether or not anybody is standing on it.
                        opacity: (line.here || line.ticked) ? 1 : root.inkMuted
                        font.family: metrics.font.family
                        font.pixelSize: metrics.type.body
                        font.weight: (line.here || line.ticked)
                          ? Font.Medium : Font.Normal
                        elide: Text.ElideRight
                      }

                      // **The line a choice tile had nowhere to put.** A
                      // choice shows one value, so the sentence saying *how*
                      // the values differ was the price of converting a tick
                      // submenu into one - and it is why `Button labels` and
                      // `Profile` kept their submenus. A row has the width
                      // for it, so a card of rows is the shape those wanted:
                      // the values in front of you, each with its own line.
                      //
                      // Optional, and most rows have none: a verb whose name
                      // says what it does does not need a sentence under it.
                      Text {
                        id: lineWhy
                        visible: line.explained
                        anchors.left: lineName.left
                        anchors.right: lineName.right
                        anchors.top: lineName.bottom
                        anchors.topMargin: metrics.gap.xxs
                        text: line.explained ? line.modelData.d : ""
                        textFormat: Text.PlainText
                        color: tile.ink
                        // One level, not two. It was 0.36 while the row was
                        // not in front, which is a sentence nobody can read
                        // from a sofa - and a line you have to walk onto in
                        // order to read is a line not doing the job it is
                        // there for, which is saying what walking onto it
                        // would mean.
                        opacity: root.inkDim
                        font.family: metrics.font.family
                        font.pixelSize: metrics.type.fine
                        elide: Text.ElideRight
                      }

                      // **The number, and it is the whole of the count.** A
                      // row about to take the screen away says how long is
                      // left, at the end of the row where a value goes on
                      // every other tile here. No bar drains beside it: a bar and a
                      // number are one answer drawn twice, and the number is
                      // the one somebody can act on - it says how long they
                      // have rather than merely that they are running out.
                      //
                      // Held still with `tnum`, for the clock's reason: with
                      // proportional figures the line re-lays itself when a 1
                      // replaces an 8, which from across a room reads as the
                      // number twitching rather than as it changing.
                      Text {
                        visible: line.counting
                        anchors.right: parent.right
                        anchors.rightMargin: metrics.gap.lg
                        anchors.verticalCenter: parent.verticalCenter
                        text: line.counting ? String(line.remaining) : ""
                        textFormat: Text.PlainText
                        color: Color.accent
                        font.family: metrics.font.family
                        // **The name's size, not the value size the rest of
                        // this surface answers in.** A value is read against
                        // the words beside it and is sized to be picked out
                        // from among them; a countdown has nothing to be
                        // picked out from, and a rung above the row it
                        // belongs to read as the row shouting seconds at
                        // somebody who is already watching them.
                        font.pixelSize: metrics.type.body
                        font.features: ({ "tnum": 1 })
                      }

                      MouseArea {
                        id: linePicker
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onEntered: root.pointerSelectRow(
                          tile.index, line.modelData.id, line,
                          { x: linePicker.mouseX, y: linePicker.mouseY })
                        onPositionChanged: function(mouse) {
                          root.pointerSelectRow(tile.index,
                                                line.modelData.id, line, mouse)
                        }
                        onClicked: root.pointerActivateRow(
                          tile.index, line.modelData.id)
                      }
                    }
                  }
                }

                Column {
                  id: body
                  // What is left in here is what belongs in the middle of a
                  // card: a choice between its chevrons, and the dead zone's
                  // ring. Everything else is anchored to an edge - the mark
                  // and the name to the corners, a figure and its travel to
                  // the top and the foot.
                  anchors.horizontalCenter: parent.horizontalCenter
                  anchors.verticalCenter: parent.verticalCenter
                  width: parent.width - tile.pad * 2
                  spacing: metrics.gap.xs
                  // The name is drawn on the tile's own foot, so a tile that
                  // has one needs what is in the middle to stop short of it.
                  bottomPadding: tile.named
                    ? labelText.height + metrics.gap.xs : 0

                  // A choice: the value between the two chevrons it is walked
                  // with, drawn rather than typed so a row of them matches the
                  // buttons on the same card.
                  Row {
                    visible: tile.modelData.k === "choice"
                    spacing: metrics.gap.md
                    anchors.horizontalCenter: parent.horizontalCenter

                    BadgeArt {
                      width: metrics.gap.xl
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
                      // The size every value on this surface is set in. It
                      // was two rungs below, which made a choice the one kind
                      // of tile whose answer was smaller than its question -
                      // and a choice is picked *by* its answer, so that is
                      // the one it could least afford. The chevrons went up
                      // with it: a mark beside a word is sized to the word.
                      font.pixelSize: metrics.type.lead
                      // Held still between the chevrons - see the slider's
                      // value below. A choice walks through words more often
                      // than numbers, and a word is not hurt by it.
                      font.features: ({ "tnum": 1 })
                      elide: Text.ElideRight
                    }

                    BadgeArt {
                      width: metrics.gap.xl
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
                    spacing: metrics.gap.xs

                    Item {
                      id: face
                      width: Math.min(parent.width, tile.height
                                      - metrics.gap.huge)
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
                      // slider's travel carries, one shape along.
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
                  }

                  // The same number the travel draws, turned. Sized off the
                  // dial and the clock to the pixel, for their own reason:
                  // three circles on one page drawn to three sizes read as a
                  // fault rather than as three tiles.
                  Knob {
                    id: knobFace
                    visible: tile.knob
                    width: Math.min(parent.width,
                                    tile.height - metrics.gap.huge)
                    height: knobFace.width
                    anchors.horizontalCenter: parent.horizontalCenter
                    art: controlArt
                    // Bindings rather than anything a signal starts, so a
                    // delegate rebuilt mid-turn is born where the value
                    // already is - qml.md 5.5.
                    // While this is the ring being turned, where round it
                    // the value has got comes off the short push (`hv`): the
                    // full one rebuilds every tile on the page, which at the
                    // rate a followed dial moves is the cost `menu_gauge`
                    // warns about, paid to move one pointer. The daemon
                    // sends it only for a ring whose value is continuous;
                    // a ladder and a list step rarely enough to ride the
                    // surface, and their `seg` and `at` are only on it.
                    value: tile.streaming && root.live.hv !== undefined
                      ? Number(root.live.hv)
                      : (tile.modelData.v !== undefined
                         ? tile.modelData.v : 0)
                    stops: tile.modelData.seg !== undefined
                      ? Number(tile.modelData.seg) : 0
                    at: tile.modelData.at !== undefined
                      ? Number(tile.modelData.at) : 0
                    // `b` - where it stood when A took it - is the travel's
                    // and not read here: a ring draws no ghost, because a
                    // second figure out of the same middle is a clock rather
                    // than a value and its history. `Knob.qml` argues it.
                    //
                    // The rim and the scale are the card's structure, the
                    // trail is how far round the value has got, and the mark
                    // is where it is.
                    // The first of them is the dial's own number rather than
                    // one of the three inks (qml.md 8.1.2): a ring beside a
                    // dial at a different strength is two circles rather than
                    // two tiles.
                    ink: Util.alpha(Color.menu.text, 0.3)
                    trail: root.trailInk
                    mark: tile.mark
                  }

                  // The time, with hands on it. `Clock.qml` rather than a
                  // drawing of this surface's own, because the HUD holds the
                  // same tile over a game and a page has to read the same in
                  // both places it appears - `Travel.qml`'s argument, one
                  // control along.
                  //
                  // Sized off the dial above it, to the pixel: two circles on
                  // one page drawn to two sizes read as a fault rather than
                  // as two tiles.
                  Clock {
                    id: clockFace
                    visible: tile.clock || tile.chrono
                    width: Math.min(parent.width,
                                    tile.height - metrics.gap.huge)
                    height: clockFace.width
                    anchors.horizontalCenter: parent.horizontalCenter
                    art: controlArt
                    minutes: tile.modelData.mn !== undefined
                      ? tile.modelData.mn : 0
                    seconds: root.chronoState.sc !== undefined
                      ? root.chronoState.sc : 0
                    // Nothing turns while the card is down: the delegates
                    // outlive the window being closed, and a hand animating
                    // behind one nobody can see is twenty wake-ups a second
                    // spent on a drawing that is not on screen.
                    awake: root.opened
                    // Negative is a clock and nothing else, so a plain face
                    // draws no complication - and a chronograph that has
                    // never been started still draws one, standing at zero,
                    // which is what says the tile has a stopwatch in it
                    // before anybody presses anything.
                    elapsed: (tile.chrono
                              && root.chronoState.el !== undefined)
                      ? root.chronoState.el : -1
                    ticking: root.chronoState.run === true
                    ink: tile.ink
                    // The dial's own number rather than one of the three inks
                    // (qml.md 8.1.2): what recedes here is furniture under a
                    // drawing, not a line of type, and the gauge's face is
                    // the thing it has to match - a clock beside a dial at a
                    // different strength is two circles rather than two
                    // tiles.
                    dim: Util.alpha(Color.menu.text, 0.3)
                    // A ground rather than an ink, and the same kind of
                    // number the tile's own ground is: one step off what it
                    // is drawn on, which is all a recess has to be.
                    wash: Util.alpha(Color.menu.text, 0.13)
                    mark: tile.mark
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
                  width: metrics.gap.xl
                  height: width
                  anchors.right: parent.right
                  anchors.top: parent.top
                  anchors.rightMargin: metrics.gap.md
                  anchors.topMargin: metrics.gap.md
                  drawn: controlArt.find("tile", "grip")
                  fill: Color.menu.text
                }

                // The seconds left, in the corner a tile says what it is on
                // in - where the tick and the chevron sit, neither of which
                // can be true of a tile that is about to run. The row
                // countdown's size, so one count is one size wherever it is
                // drawn, held still with `tnum` for the clock's reason.
                Text {
                  visible: tile.counting
                  text: tile.counting ? String(tile.remaining) : ""
                  textFormat: Text.PlainText
                  color: Color.accent
                  font.family: metrics.font.family
                  font.pixelSize: metrics.type.body
                  font.features: ({ "tnum": 1 })
                  anchors.right: parent.right
                  anchors.top: parent.top
                  anchors.rightMargin: metrics.gap.md
                  anchors.topMargin: metrics.gap.sm
                }

                // **The chevron, and nothing else in this corner.** A tick
                // sat here for anything that was on, which is the half of a
                // switch the lit ground says better and said it at the
                // opposite end of the tile from the name it was about. This
                // corner is left to say *there is a page behind this tile*.
                Text {
                  visible: !root.editing && !tile.counting
                  text: tile.modelData.sub ? "›" : ""
                  textFormat: Text.PlainText
                  color: Color.menu.text
                  opacity: tile.modelData.sub ? 0.36 : 0
                  font.family: metrics.font.family
                  font.pixelSize: metrics.type.body
                  anchors.right: parent.right
                  anchors.top: parent.top
                  anchors.rightMargin: metrics.gap.md
                  anchors.topMargin: metrics.gap.sm
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
        }

      }

      // What the face buttons do here, page-scoped: the game bar says the
      // same kind of thing across the whole screen, and this is the only one
      // that can say what a page has spent X or Y on. `[menu] keys = false`
      // turns it off for anyone running both.
      //
      // Anchored to the foot rather than flowing after the tiles, and on a
      // fullscreen HUD it sits in the **game bar's own band**: it is the same
      // four words about the same four buttons, so it must not move when the
      // menu opens. A row that jumped an inch up the screen would read as a
      // different row - and neither may its colours change, which is why the
      // badges and the words are drawn in the bar's own text colour (see the
      // LegendBadge component): the row that answers the menu is the row the
      // bar answered before it.
      Item {
        id: legend
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.bottomMargin: root.full
          ? root.safeGap : card.borderBottom + root.contentMargin
        anchors.leftMargin: root.full
          ? 0 : card.borderLeft + root.contentMarginX
        anchors.rightMargin: root.full
          ? 0 : card.borderRight + root.contentMarginX
        height: root.legendBand
        visible: root.legendHeight > 0

        // Centred under a card, because a card is a thing you are looking at
        // and its foot is the middle. On the screen it takes the bar's own
        // edge padding, so the row lands where the bar's row was.
        Row {
          id: legendRow
          anchors.verticalCenter: parent.verticalCenter
          // Placed rather than anchored: an anchor switched between two sides
          // by a ternary leaves both unset and the row lands nowhere, which
          // is a thing that happens silently.
          x: root.full
            ? parent.width - legendRow.width - root.barSideMargin
              - root.safeSide
            : Math.round((parent.width - legendRow.width) / 2)
          // The bar's spacings, like everything else in this row.
          spacing: metrics.space(16)

          Repeater {
            model: root.keys

            delegate: Row {
              id: hint
              required property var modelData
              spacing: metrics.space(7)

              LegendBadge {
                label: hint.modelData.b
                kind: hint.modelData.k
                anchors.verticalCenter: parent.verticalCenter
              }

              Text {
                anchors.verticalCenter: parent.verticalCenter
                text: hint.modelData.n
                textFormat: Text.PlainText
                // The bar's word, at the bar's weight: the bar prints its
                // hint words at 0.85 of its foreground, and this row is that
                // row.
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
