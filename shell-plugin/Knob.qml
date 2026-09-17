// Where along something a number is, drawn as a ring.
//
// `Travel.qml`'s question, asked of a control that turns: a slider is a
// length and a knob is an angle, and the pad has one of each - a D-pad pushes
// a direction, and a stick *is* an angle. This is the figure a thumb can copy
// rather than translate, which is the whole argument for the control and the
// only reason there are two drawings of one value on this surface.
//
// **It is not the travel bent round.** Three things are decided differently
// here, and each of them is the circle's rather than a preference:
//
// - **A ring needs no caps.** A line has to say where it stops, because a
//   line that simply ended would read as a drawing that had not been trimmed;
//   that is what the crosses at the ends of a travel are for. A ring says it
//   by not closing - the quarter left open at the bottom is the end of the
//   scale and the start of it, and no mark has to stand there to be read.
// - **The value's mark is a pointer, not a cross.** On a line the mark has to
//   be *on* the line because there is nowhere else for it to be. A ring has a
//   middle, and what a knob has always answered *where is it* with is a
//   pointer from that middle - one figure, and the one every hand already
//   knows how to read.
// - **A stop is a notch on the scale.** Hung just outside it, touching, so a
//   stepped ring and a continuous one differ by exactly what the two controls
//   differ by - whether the scale has places printed on it - which is
//   `Travel.qml`'s own rule about `stops` and is the whole difference between
//   the drawings there too.
//
// **What it keeps** is the rest of that file's argument, because the two are
// one control: nothing fills, the run behind the value says how far it has
// come, a scale with stops fills that run in the accent and one without them
// tints it at half, and the mark left where a press began is one faint figure
// with nothing drawn between it and the value.
//
// **The rim is generated and nothing else is.** It is the gauge's own
// `dial-face.svg`, because a knob is the same circle as the dial beside it
// and the clock under it, and a page holding three circles drawn to three
// weights reads as a fault rather than as three tiles. Everything else here
// answers to a number - an arc from one angle to another, a notch per stop, a
// rectangle turned to where the value is - and a shape parameterised by a
// number cannot be drawn once. That is `assets.md`'s split, and the reason a
// knob adds nothing at all to `shapes/`.
//
// The scale's own marks are the one place this parts company with the clock,
// which *does* generate its twelve. Those twelve are the same twelve on every
// clock ever drawn; a knob's marks are its stops, and a ring reading a list
// of three has three where one reading a ladder of six has six. A family of
// marks drawn at its ends and computed in its middle is two drawings of one
// figure, which is how two drawings of one thing quietly stop matching.
//
// Every measurement below is a share of the face and none of them is on the
// ladder (qml.md 8.2.1), for `Clock.qml`'s reason: a hand is a fraction of
// the dial it turns in. The face's own units are the shapes' 40, so a number
// here is what it would be in Figma.
import QtQuick
import QtQuick.Shapes

Item {
  id: knob

  // The generated furniture, handed in rather than built here. `ControlArt`
  // cannot be a `pragma Singleton` - it does not register from a plugin
  // directory - so a copy built in this file would be a copy per knob on the
  // page, and the surface already has one to lend.
  property var art: null

  // Where round, 0 to 1. The daemon normalises it - a list's places as
  // readily as a number's range - so no minimum, maximum or set of words
  // reaches this side of the wire.
  property real value: 0
  // How many places the value has, and which of them it is on. `0` is a
  // distance to cover rather than places to stand.
  property int stops: 0
  property int at: 0
  // **Where the value stood when it was taken**, 0 to 1, or negative for a
  // control nobody is holding. Same field and same argument as the travel's:
  // a press moves a knob by a step, and the one question a hand asks while it
  // turns - *what have I done to this* - is answered by where it started.
  property real was: -1

  // The scale, the part of it the value has covered, the pointer and the
  // ghost it leaves. All of them the caller's: this file names no colour, for
  // qml.md 8.1's reason, and a ring handed none of them draws an empty card
  // with nothing in any log about it.
  property color ink: "transparent"
  property color trail: "transparent"
  property color mark: "transparent"
  property color ghost: "transparent"

  // Square, because it is round, and the smaller side because a ring in a
  // wide box is a ring with air either side of it.
  readonly property real side: Math.min(knob.width, knob.height)
  readonly property real unit: knob.side / 40

  // **A quarter of the circle, left open at the bottom.** Three quarters is
  // as much scale as a ring can carry and still say which end is which: a
  // gap any narrower stops reading as a gap from a sofa and the drawing
  // becomes a clock, and one wider spends travel that the value has to cross.
  // The ends land at half past seven and half past four, where no clock has a
  // hand and where the eye already expects a knob to start.
  //
  // Degrees clockwise from three o'clock, which is what `PathAngleArc`
  // measures in: 135 is the foot of the left side, 405 the foot of the right.
  readonly property real arcFrom: 135
  readonly property real arcSweep: 270
  readonly property real share: Math.max(0, Math.min(1, knob.value))
  readonly property bool stepped: knob.stops > 1
  readonly property int divisions: knob.stepped
    ? Math.max(1, knob.stops - 1) : 1

  // Where the value is, and where it was found. **A stepped value stands on a
  // stop**, not between two: its places are the marks themselves, so the
  // first of them is the start of the scale with nothing covered behind it -
  // `Travel.qml`'s own correction, and the same one a ring needs.
  readonly property real here: knob.stepped
    ? Math.max(0, Math.min(knob.divisions, knob.at)) / knob.divisions
    : knob.share
  readonly property bool changed: knob.was >= 0
    && Math.abs(knob.was - knob.here) > 0.0005

  function angleAt(place) {
    return knob.arcFrom + knob.arcSweep * place
  }
  // A rectangle drawn up out of the pivot points at twelve o'clock, which is
  // a quarter turn before three - so the pointer's rotation is the scale's
  // angle with that quarter added back.
  function turnAt(place) {
    return knob.angleAt(place) + 90
  }

  // The four radii, out from the middle. Each figure owns its own band: the
  // pointer stops short of the scale, the notches begin where the scale ends
  // and reach the rim's inner edge, and nothing is painted over anything -
  // which is the travel's rule about translucent ink painted twice, one
  // drawing along.
  readonly property real scaleRadius: knob.unit * 12.5
  readonly property real scaleWeight: knob.unit * 1.6
  readonly property real notchFrom: knob.unit * 13.3
  readonly property real notchTo: knob.unit * 15
  readonly property real notchWeight: knob.unit * 1.2
  readonly property real pointerFrom: knob.unit * 1.5
  readonly property real pointerTo: knob.unit * 10.5
  readonly property real pointerWeight: knob.unit * 2

  // **A scale with stops fills its run in the accent; one without them tints
  // it.** Two different claims rather than two strengths of one: a stop is a
  // place the value has *stood on*, and a continuous value has been at every
  // point behind it and stood at none. Lifted from `Travel.qml` rather than
  // decided again, because it is the same control.
  readonly property color covering: knob.stepped ? knob.mark : knob.trail

  Item {
    id: face
    width: knob.side
    height: knob.side
    anchors.centerIn: parent

    // The body. The gauge's rim, at the gauge's weight, on the gauge's
    // canvas.
    BadgeArt {
      anchors.fill: parent
      drawn: knob.art ? knob.art.find("dial", "face") : null
      fill: knob.ink
    }

    Shape {
      anchors.fill: parent
      preferredRendererType: Shape.CurveRenderer

      // The scale: the whole of what the value may cross, drawn once and
      // not answering to anything but the size of the tile.
      ShapePath {
        fillColor: "transparent"
        strokeColor: knob.ink
        strokeWidth: knob.scaleWeight
        capStyle: ShapePath.FlatCap

        PathAngleArc {
          centerX: face.width / 2
          centerY: face.height / 2
          radiusX: knob.scaleRadius
          radiusY: knob.scaleRadius
          startAngle: knob.arcFrom
          sweepAngle: knob.arcSweep
        }
      }

      // **What the value has already covered**, which is what makes a press
      // visible: the pointer moves by a few degrees and a few degrees is not
      // a change anybody sees from a sofa, where the run behind it is read
      // against the run ahead.
      ShapePath {
        fillColor: "transparent"
        strokeColor: knob.covering
        strokeWidth: knob.scaleWeight
        capStyle: ShapePath.FlatCap

        PathAngleArc {
          centerX: face.width / 2
          centerY: face.height / 2
          radiusX: knob.scaleRadius
          radiusY: knob.scaleRadius
          startAngle: knob.arcFrom
          // Zero at the bottom of the scale, where a value that has covered
          // nothing has covered nothing: a ring lit from its own start is
          // the one place a `Off` could be drawn doing something.
          sweepAngle: knob.arcSweep * knob.here
        }
      }
    }

    // The stops, where the value has any. A `Repeater` over a count that the
    // value cannot change: walking a knob must never rebuild these, the way
    // walking a slider must never rebuild its ticks.
    Repeater {
      model: knob.stepped ? knob.stops : 0

      Item {
        required property int index
        x: face.width / 2
        y: face.height / 2
        width: 0
        height: 0
        rotation: knob.turnAt(index / knob.divisions)

        Rectangle {
          x: -knob.notchWeight / 2
          y: -knob.notchTo
          width: knob.notchWeight
          height: knob.notchTo - knob.notchFrom
          color: knob.ink
        }
      }
    }

    // **Where the value was found**, if it has been taken and has moved
    // since. One faint pointer, and nothing drawn between it and the value:
    // what a hand is asking is *where was it*, and the distance is then read
    // the way every other distance on this drawing is, by looking.
    Item {
      visible: knob.changed
      x: face.width / 2
      y: face.height / 2
      width: 0
      height: 0
      rotation: knob.turnAt(Math.max(0, Math.min(1, knob.was)))

      Rectangle {
        x: -knob.pointerWeight / 2
        y: -knob.pointerTo
        width: knob.pointerWeight
        height: knob.pointerTo - knob.pointerFrom
        radius: width / 2
        color: knob.ghost
      }
    }

    // And the value itself. The loudest thing on the drawing, because it is
    // the one thing the tile exists to say.
    Item {
      x: face.width / 2
      y: face.height / 2
      width: 0
      height: 0
      rotation: knob.turnAt(knob.here)

      Rectangle {
        x: -knob.pointerWeight / 2
        y: -knob.pointerTo
        width: knob.pointerWeight
        height: knob.pointerTo - knob.pointerFrom
        radius: width / 2
        color: knob.mark
      }
    }

    // What the pointers meet under. The clock's own, for the clock's reason:
    // the join at the middle of a turning rectangle is not parameterised by
    // anything, and two of them crossing is the one place their corners show.
    BadgeArt {
      anchors.fill: parent
      drawn: knob.art ? knob.art.find("clock", "hub") : null
      fill: knob.mark
    }
  }
}
