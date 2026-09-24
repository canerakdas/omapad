// Where along something a number is, drawn as a scale with a needle on it.
//
// Two tiles ask that question and it is one question: a slider being pushed,
// and a slider with places to stand rather than a distance to cover. A
// reading asked it too, once, and was drawn here for as long as it did: a
// number the machine keeps answering drew a control's line under itself, on
// a page where nothing could push it, and read as a slider that had lost its
// thumb. A reading is words now, on both surfaces that draw one.
//
// **It is the knob's scale, unrolled** - `Knob.qml` is the T 1000's
// bandspread control, and this is the same radio's tuning scale: a printed
// scale along a hairline and a needle that runs across it. The first drawing
// here was the row card's spine turned on its side, a line with crosses on
// it, and beside a knob on one page it was the plainer of two drawings of one
// value: no scale where the ring printed one, the value's cross hidden inside
// the end's at nought and at a hundred, and one weight for every stroke where
// the ring's index is plainly the heaviest thing on it. So every figure on
// this line is now one the ring already has, and what is left of the spine
// is its weight.
//
// **What it takes from the ring**, and why the line agrees with it:
//
// - **Its scale is printed.** A continuous line prints a graduation every
//   five in a hundred, the ring's twenty-one; a stepped one prints one
//   detent per place it can stand and nothing between them. The two differ
//   by exactly what the two controls differ by.
// - **An end is a baton in outline with its foot open**, and the line closes
//   it, the way the ring's arc closes `dial-end`.
// - **A place stood on is filled in.** A detent the value has reached, and
//   an end, are drawn solid in the accent - a stop is a place the value has
//   *stood on*. A continuous value has been at every point behind it and
//   stood at none, so its run and its graduations are tinted at half.
// - **Nothing fills; the run behind the value is still a line.** A bar filled
//   to the value is a second answer to what the figure at the top of the
//   card already says in words. What makes a press visible is the length of
//   line behind the needle changing under the thumb.
//
// **What it does not take**, because a line is not a ring:
//
// - **The needle crosses the line** rather than pointing from a middle it
//   does not have, and it is taller than an end, so a value at nought or at
//   a hundred is drawn rather than hidden inside the end's outline.
// - **Where the value was taken is drawn.** A ring would need a second
//   figure out of the same middle, and two of those are a clock; a line has
//   room under it, where nothing else is printed, for a stub the size of the
//   needle's tail - and the gap between the two is what the press did.
//
// Nothing here decides anything: the caller hands it the ladder, the value,
// and how many places the value has.
import QtQuick

Item {
  id: travel

  // The surface's `Metrics`, handed in rather than built here: the scale on
  // the payload is the card's, and a component that built its own would be
  // drawing to a different one. Named `ladder` because a property called
  // `metrics` shadows the caller's `metrics` id in its own binding, and `var`
  // rather than `QtObject` because the ladder is a bag of measurements this
  // reads through rather than a type it has anything to say about.
  property var ladder: null

  // The generated figures, handed in rather than built here. `ControlArt`
  // cannot be a `pragma Singleton` - it does not register from a plugin
  // directory - so a copy built in this file would be a copy per slider on
  // the page, and the surface that draws one already has one to lend. A
  // travel handed none draws its line and nothing on it.
  property var art: null

  // Where along, 0 to 1. The daemon normalises it, so no minimum or maximum
  // reaches this side of the wire.
  property real value: 0
  // How many places the value has, and which of them it is on. `0` is a
  // distance to cover rather than places to stand.
  property int stops: 0
  property int at: 0

  // **Where the value stood when it was taken**, 0 to 1, or negative for a
  // control nobody is holding. A press moves a slider by a step and a step is
  // a few pixels, so the one question a hand asks while it pushes - *what
  // have I done to this* - is answered by a faint stub under the line, left
  // where the value was found.
  property real was: -1

  // The scale, the part of it the value has already covered, and the needle.
  // All of them the caller's: this file names no colour, for qml.md 8.1's
  // reason. All of them are also required - a travel drawn with any of them
  // missing is a card with an empty foot and nothing in any log about it,
  // which is what `tests/test_shell_plugin.py` checks the call sites for.
  property color ink: "transparent"
  property color trail: "transparent"
  property color mark: "transparent"
  // And what the needle a press left behind is drawn in - see `was`.
  property color ghost: "transparent"

  // The line's weight is the ladder's `spine`, the one number the row
  // card's line and this one still share. Every figure is a whole number of
  // it on both sides (`travel-*.svg`), so a figure handed a box `weight`
  // wide times its own count lands on whole pixels at every scale.
  readonly property int weight: travel.ladder ? travel.ladder.spine.weight : 1
  // The figures that stand on the line are three weights across - an end,
  // a detent and the needle - and a graduation is one. A wide figure is
  // hung by its middle column, which is the column a graduation at the same
  // place would take, so the needle lands *on* a mark rather than beside it.
  readonly property int wide: travel.weight * 3

  // **How far the needle hangs below the line.** The one proportion here
  // that is not a drawing's, because it is where the needle is hung rather
  // than what it is: the needle is twenty-one weights, fifteen of them
  // above the line, which clears an end's twelve by three - enough that the
  // needle standing on an end reads as the needle and not as a heavier end.
  readonly property int below: travel.weight * 5

  readonly property var needle: travel.art
    ? travel.art.find("travel", "needle") : null
  readonly property int needleHeight: travel.needle
    ? Math.round(travel.wide * travel.needle.h / travel.needle.w) : 0

  // The needle is the tallest thing here, so it is the box; the line sits
  // where the needle crosses it.
  implicitHeight: travel.needle
    ? travel.needleHeight : travel.weight
  readonly property int lineY: travel.needle
    ? travel.needleHeight - travel.below - travel.weight : 0

  readonly property bool stepped: travel.stops > 1
  // **A stepped value stands on a detent, not in a gap.** Its stops are the
  // detents themselves, so five stops are five with four divisions between
  // them - and the first one begins the travel, with nothing covered behind
  // it. A value on the first stop of a ladder that drew a length lit behind
  // it was a control saying it is doing something while it says `Off`.
  readonly property int divisions: travel.stepped
    ? Math.max(1, travel.stops - 1) : 1
  readonly property real share: Math.max(0, Math.min(1, travel.value))
  readonly property real place: travel.stepped
    ? Math.max(0, Math.min(travel.divisions, travel.at)) / travel.divisions
    : travel.share

  // **The travel runs between the two ends' middle columns**, and the line
  // runs on under each end to its outer wall, which is where the end's
  // outline closes. The outer walls are flush with the box, so the scale
  // lines up with the words above it on the card.
  readonly property int from: travel.weight
  readonly property int to: Math.max(
    travel.from, travel.width - travel.weight * 2)

  // Where a figure at `p` stands. Rounded off the whole travel each time
  // rather than stepped by a rounded unit, so the last detent lands exactly
  // on the end however badly the width divides.
  function xAt(p) {
    return travel.from + Math.round((travel.to - travel.from) * p)
  }
  readonly property int needleAt: travel.xAt(travel.place)

  // Whether the value has got as far as `p`. Nothing is reached at nought,
  // `Knob.qml`'s own rule: the run behind the value is empty there, and an
  // end lit while the line beside it is not would be the one place `Off` is
  // drawn doing something. The margin is a stop's share arriving as a float.
  function reached(p) {
    return travel.place > 0 && p <= travel.place + 0.0001
  }

  // Where the two layers meet. At either end the whole line goes with
  // whichever of them is there, so an end and the line under it are one
  // colour; anywhere else it is under the needle, which hides the join.
  readonly property int split: travel.place <= 0 ? 0
    : travel.place >= 1 ? travel.width
    : travel.needleAt

  // The printed scale: every place a figure stands, as a share of the
  // travel. A continuous line prints one every five in a hundred - the
  // ring's twenty-one, and five is the step the volume and the brightness
  // take (`live.py`), so a press moves the needle exactly one graduation. A
  // stepped one prints its stops and nothing else. Not a setting, for the
  // ring's reason: it is how the scale is engraved.
  readonly property int printed: 21
  readonly property var places: {
    var count = travel.stepped ? travel.stops : travel.printed
    var out = []
    for (var i = 0; i < count; i++) out.push(i / (count - 1))
    return out
  }

  readonly property color covering: travel.stepped
    ? travel.mark : travel.trail

  // Which figure stands at `p`, and whether it is the filled one. An end at
  // either end of the scale; a detent between the stops of a stepped one; a
  // graduation between the ends of a continuous one. Filled only on a
  // stepped scale, and only where the value has stood.
  function figureAt(p, lit) {
    var name = travel.heavy(p) ? (p > 0 && p < 1 ? "detent" : "end")
                               : "notch"
    if (lit && travel.stepped && name !== "notch") name += "-lit"
    return travel.art ? travel.art.find("travel", name) : null
  }
  // Whether the figure at `p` is one of the three-weight ones: an end, or a
  // detent. Everything else printed on the scale - and anywhere a continuous
  // value can be between two graduations - is one weight.
  function heavy(p) {
    return p <= 0 || p >= 1 || travel.stepped
  }

  // A colour at full strength, for drawing inside a layer that is faded as a
  // whole.
  function solid(c) {
    return Qt.rgba(c.r, c.g, c.b, 1)
  }

  // **Two layers, one per ink, each drawn opaque and faded once** -
  // `Knob.qml`'s answer, for its reason. The inks are translucent, and
  // figures drawn one by one in a translucent ink cannot meet cleanly: an end
  // standing on the line paints the pixel they share twice, and that pixel
  // is brighter than either. Inside a layer the figures are opaque and
  // overlap where they meet; the fade is applied to the finished drawing,
  // which is one coat everywhere.
  //
  // What the value has not reached is the first, in the scale's ink.
  Item {
    anchors.fill: parent
    opacity: travel.ink.a
    layer.enabled: true

    Rectangle {
      x: travel.split
      y: travel.lineY
      width: Math.max(0, travel.width - travel.split)
      height: travel.weight
      color: travel.solid(travel.ink)
    }

    Engraving {
      line: travel
      lit: false
      fill: travel.solid(travel.ink)
    }
  }

  // **What the value has already covered**, the second layer, which is
  // what makes a press visible: the needle moves a few pixels, and the run
  // behind it is read against the run ahead.
  Item {
    anchors.fill: parent
    opacity: travel.covering.a
    layer.enabled: true

    Rectangle {
      y: travel.lineY
      width: travel.split
      height: travel.weight
      color: travel.solid(travel.covering)
    }

    Engraving {
      line: travel
      lit: true
      fill: travel.solid(travel.covering)
    }
  }

  // Where the value was found, while a press has it: **the needle's tail,
  // and only that**, under the line. It was the whole needle in outline
  // first, and a second needle crosses everything the first one does - the
  // graduations, and an end's outline, where two outlines laid over each
  // other read as a smudge rather than as a mark. Below the line nothing is
  // printed, so the stub has that band to itself and the scale above it
  // stays one drawing. Outside both layers, under the needle: the two only
  // meet when the press has not moved the value, and then this is not
  // drawn.
  //
  // **As wide as the figure it was found on.** Taken from an end or a
  // detent, the stub is three weights, the end's own; taken from a
  // graduation it is one, the graduation's. A stub one width everywhere
  // said *somewhere around here*; this one hangs under the very figure the
  // value left, so the two read as one mark with its foot showing.
  BadgeArt {
    readonly property real wasPlace: Math.max(0, Math.min(1, travel.was))
    readonly property int wasAt: travel.xAt(wasPlace)
    readonly property bool heavy: travel.heavy(wasPlace)
    visible: travel.was >= 0 && wasAt !== travel.needleAt
    x: wasAt - (heavy ? travel.weight : 0)
    y: travel.lineY + travel.weight
    width: heavy ? travel.wide : travel.weight
    height: implicitHeight
    drawn: travel.art ? travel.art.find(
      "travel", heavy ? "ghost" : "ghost-thin") : null
    fill: travel.ghost
  }

  // The value. The loudest thing on the drawing, because it is the one
  // thing the tile exists to say.
  BadgeArt {
    visible: travel.width > 0
    x: travel.needleAt - travel.weight
    y: 0
    width: travel.wide
    height: implicitHeight
    drawn: travel.needle
    fill: travel.mark
  }

  // The printed scale, as one layer draws it: the figures it holds are the
  // ones the value has reached or the ones it has not, and every figure is
  // in exactly one of the two. A `Repeater` over a list the value cannot
  // change, so pushing a slider never rebuilds its scale - only which layer
  // shows a figure follows the value.
  //
  // **The travel is handed in**: an inline component does not see the ids of
  // the file it is declared in.
  component Engraving: Repeater {
    id: engraving
    required property var line
    property bool lit: false
    property color fill: "transparent"
    model: engraving.line.places

    BadgeArt {
      required property real modelData
      readonly property var line: engraving.line
      readonly property bool slim: !line.heavy(modelData)
      visible: line.reached(modelData) === engraving.lit
      x: line.xAt(modelData) - (slim ? 0 : line.weight)
      y: line.lineY - implicitHeight
      width: slim ? line.weight : line.wide
      height: implicitHeight
      drawn: line.figureAt(modelData, engraving.lit)
      fill: engraving.fill
    }
  }
}
