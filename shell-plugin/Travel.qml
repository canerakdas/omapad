// Where along something a number is, drawn as a line.
//
// Three tiles ask that question and it is one question: a slider being
// pushed, a slider with places to stand rather than a distance to cover, and
// a reading the machine keeps answering. The menu draws all three and the HUD
// draws the last of them, and a page of readings has to read the same in both
// places it appears - so this is one file rather than two drawings that look
// alike. The menu's legend is the standing exception to that (qml.md 8.2.1)
// and it is one because the row it mirrors belongs to another surface's
// ladder; this belongs to the same ladder in both places it is drawn.
//
// **It is the row card's spine, turned on its side.** A stack of rows with a
// length of line lit beside the one in force and a mark standing on it *is* a
// vertical slider, and for as long as there were two drawings they were drawn
// to two rules: a two-pixel line with a mark on it down one card, a rounded
// eight-pixel trough along the foot of the next. The line won because a card
// that draws one kind of line is a card read once, and because the trough was
// a container drawn round a value that is not a quantity of anything.
//
// **Nothing fills, and the line behind the value is still a line.** A bar
// filled to the value draws a number as mass, which is a second answer to
// what the figure at the top of the card already says in words - and on a
// stepped control it was mass that disagreed with the word, sitting four
// pixels along from where the last press left it. What is drawn in the accent
// is where the value *is*: one stroke across the line at that place, with the
// run behind it saying how far it has come.
//
// The mark alone was not enough, though, and the screen said so: a press
// moves it by a few pixels, and a few pixels is not a change anybody sees
// from a sofa. So the line **behind** the value is drawn in too. A line with
// stops fills it in the accent and a line without them tints it at half -
// two different claims rather than two strengths of one: a stop is a place
// the value has *stood on*, and a continuous value has been at every point
// behind it and stood at none.
//
// **One stroke, and everything on the line is it**: the cap at each end, a
// stop a stepped value may stand on, and the value's own place. Equal reach
// either side of the line, so the figure is a cross and says *here* rather
// than pointing anywhere - a wedge is the row card's mark because there is a
// row beside it to point at, and along the foot of a card there is nothing.
// A stepped travel and a continuous one then differ by exactly what the two
// controls differ by, which is whether the line has places printed on it.
//
// **The line runs on past the travel at both ends**, as it runs past the
// first row and the last one of a card: the cap is out at the end of the
// line and the value's range starts an arm inside it, so there is a run of
// bare line before anything on it begins.
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

  // Where along, 0 to 1. The daemon normalises it, so no minimum or maximum
  // reaches this side of the wire.
  property real value: 0
  // How many places the value has, and which of them it is on. `0` is a
  // distance to cover rather than places to stand.
  property int stops: 0
  property int at: 0

  // The line, the part of it the value has already covered, and the mark. All
  // three are the caller's: this file names no colour, for qml.md 8.1's
  // reason. All three are also required - a travel drawn with any of them
  // missing is a card with an empty foot and nothing in any log about it,
  // which is what `tests/test_shell_plugin.py` checks the call sites for.
  property color ink: "transparent"
  property color trail: "transparent"
  property color mark: "transparent"

  // The motif's measurements, all of them the ladder's `spine` - one
  // definition for the line drawn down a card of rows and the line drawn
  // along the foot of a slider, because two copies of a stroke weight is how
  // two drawings of one thing quietly stop matching.
  readonly property int weight: travel.ladder ? travel.ladder.spine.weight : 1
  readonly property int arm: travel.ladder ? travel.ladder.spine.arm : 0
  readonly property int cross: travel.ladder ? travel.ladder.spine.cross : 0
  readonly property int crossEnd:
    travel.ladder ? travel.ladder.spine.crossEnd : 0

  // A stroke reaches the same distance either side of the line, and the two
  // that end the travel reach furthest, so the box is that twice with the
  // line between them.
  implicitHeight: travel.crossEnd * 2 + travel.weight
  readonly property int lineY: travel.crossEnd

  readonly property bool stepped: travel.stops > 1
  // **A stepped value stands on a mark, not in a gap.** Its stops are the
  // marks themselves, so five stops are five marks with four divisions
  // between them - and the bottom one is the mark that *begins* the travel,
  // with nothing covered behind it. It stood at the far edge of a segment for
  // a pass, on the argument that the first stop of a ladder is still
  // somewhere to be; what that drew was `Off` with a segment lit behind it,
  // which is a control saying it is doing something while it says `Off`.
  readonly property int divisions: travel.stepped
    ? Math.max(1, travel.stops - 1) : 1
  readonly property real share: Math.max(0, Math.min(1, travel.value))

  // **The line is exactly as long as the travel**, and it ends where the marks
  // that end the travel do - so each end of it reads as a `T`: the stroke
  // standing across, the line leaving it inwards, and nothing past it.
  //
  // It carried on an arm past both for two passes, which is what the row
  // card's spine does above a list. A line beside a list wants that, because
  // the list simply stops and the line has to say so; a line **under a value**
  // does not, because its ends are values. What the tail read as was a
  // drawing that had not been trimmed - and it also put the end marks out of
  // the value's reach, so a slider pushed the whole way stopped short of the
  // mark it was reaching for.
  readonly property int runIn: travel.arm
  readonly property int from: travel.runIn
  readonly property int to: Math.max(
    travel.from, travel.width - travel.runIn - travel.weight)

  // Where a mark stands, from the first to the last: the stops a stepped
  // value stands on **are** the marks, the first and the last of them end the
  // travel, and the value's own mark lands on one of them. Rounded off the
  // whole travel each time rather than stepped by a rounded unit, so the last
  // one lands exactly on the end however badly the width divides.
  function edge(n) {
    return travel.from
      + Math.round((travel.to - travel.from) * n / travel.divisions)
  }

  readonly property int here: travel.stepped
    ? Math.max(0, Math.min(travel.divisions, travel.at)) : 0

  // **Where the value's own stroke stands.** On a line with stops that is the
  // **far edge of the stop being stood on**, not the middle of it: a stop is
  // a length the value has reached the end of, so the mark is where the
  // reaching stopped - in the middle it read as a thing sitting inside the
  // segment rather than as the point the segment runs up to. On a line
  // without them it is the value's own place along the travel.
  //
  // It stands **on** that edge rather than inside it - the same place the
  // stop's own stroke stands, so the accent covers that stroke instead of
  // landing half a weight beside it and reading as one stroke drawn twice.
  readonly property int markAt: travel.stepped
    ? travel.edge(travel.here)
    : travel.from
      + Math.round((travel.to - travel.from) * travel.share)
  // How far the value's own mark reaches: **the reach of the mark it is
  // standing on**. At either end of the travel that is the long one, so the
  // accent covers the end mark exactly rather than sitting inside it with its
  // tips showing; anywhere else it is a stop's own.
  readonly property int markReach:
    (travel.markAt === travel.from || travel.markAt === travel.to)
      ? travel.crossEnd : travel.cross
  // What that run is drawn in, and with it every mark the value has already
  // passed: a line with stops fills in the accent and a line without them
  // tints at half - see the run below.
  readonly property color covering: travel.stepped
    ? travel.mark : travel.trail

  // Every stroke on the line that is not the value's: the two that end it,
  // out at the ends of the line itself, and one at each place a stepped value
  // may stand. A `var` recomputed from the width and the stop count only -
  // the value moving must never rebuild this, or walking a slider would
  // rebuild a Repeater per press.
  readonly property var ticks: {
    var out = []
    if (travel.width <= 0) return out
    out.push(travel.from)
    for (var i = 1; travel.stepped && i < travel.divisions; i++) {
      out.push(travel.edge(i))
    }
    out.push(travel.to)
    return out
  }

  // The line itself, **between** the marks rather than under them: every
  // stroke on this drawing owns its own pixels. Every ink here is the theme's
  // own at a share of itself, so a square painted twice is a square painted
  // brighter - and the line running under the mark that ends it lit exactly
  // that square, which read as the two of them interlocked.
  Rectangle {
    x: travel.from + travel.weight
    y: travel.lineY
    width: Math.max(0, travel.to - travel.from - travel.weight)
    height: travel.weight
    color: travel.ink
  }

  // **What the value has already covered**, which is what makes a press
  // visible: the mark moves by a few pixels and a few pixels is not a change
  // anybody sees from a sofa, but the length behind it changes by those same
  // few pixels and is read against the length ahead of it.
  //
  // **It starts where the mark that ends the travel stops**, with nothing
  // between the two - and not under it, for the line's own reason: a
  // translucent ink painted over itself is a brighter square, and the mark is
  // the thing that square would be taken from.
  //
  // **A line with stops fills it in the accent; a line without them tints
  // it.** They are two different claims. A stop is a place the value has
  // *stood on*, and every one behind the mark is a place it has been, so the
  // run is as solid as the mark that ends it. A continuous value has been at
  // every point behind it and stood at none, so the run there is the accent
  // at half - a tint rather than a fill (qml.md 8.1), which keeps the loudest
  // thing on the line the one place drawn in the full accent. The tint was
  // tried at a fifth, this surface's own for a ground, and is not there at
  // all on a two-pixel line; tried in the ink at its dim level it became the
  // brightest thing on the card, which puts the eye behind the value rather
  // than on it.
  Rectangle {
    x: travel.from + travel.weight
    y: travel.lineY
    width: Math.max(0, travel.markAt - travel.from - travel.weight)
    height: travel.weight
    color: travel.covering
    visible: travel.markAt > travel.from + travel.weight
  }

  // **The strokes, and every one of them is the same stroke**: the cap at
  // each end of the line and a stop a stepped value may stand on are one
  // drawing at one size, and so is the mark below. A cross rather than a tick
  // hanging under the line, and the same reach either side of it, so the
  // figure says *here* rather than pointing anywhere - there is nothing
  // beside a horizontal line to point at.
  //
  // **Two arms, and neither of them crosses the line.** Every ink here is the
  // theme's own at a share of itself, so a square painted twice is a square
  // painted brighter, and a bar run through the line would light the pixel
  // where they meet. The line takes the crossing; the arms start above and
  // below it.
  Repeater {
    model: travel.ticks

    delegate: Item {
      required property int index
      required property int modelData
      // **A mark the value has been past belongs to the run**, and takes its
      // colour: a stop already stood on, or the end the value started from,
      // is not a place it might go. Dim ahead of the mark, so what is left to
      // cover reads as the scale and what is behind it reads as one thing.
      readonly property bool passed: modelData <= travel.markAt
      // The two that end the travel reach furthest - the only hierarchy an
      // instrument of one weight has is length.
      readonly property int reach: (index === 0
        || index === travel.ticks.length - 1)
        ? travel.crossEnd : travel.cross
      x: modelData
      y: travel.lineY - reach
      width: travel.weight
      height: reach * 2 + travel.weight

      Rectangle {
        width: parent.width
        height: parent.height
        color: passed ? travel.covering : travel.ink
      }
    }
  }

  // **Where the value is: the same stroke again, in the accent.** One piece
  // rather than two arms, because the accent is opaque and covers the line it
  // crosses instead of tinting it twice - so the figure closes into a cross
  // where every other one is an arm either side of an unbroken line.
  Rectangle {
    x: travel.markAt
    y: travel.lineY - travel.markReach
    width: travel.weight
    height: travel.markReach * 2 + travel.weight
    color: travel.mark
    visible: travel.width > 0
  }
}
