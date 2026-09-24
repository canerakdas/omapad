// Where along something a number is, drawn as a ring.
//
// `Travel.qml`'s question, asked of a control that turns: a slider is a
// length and a knob is an angle, and the pad has one of each - a D-pad pushes
// a direction, and a stick *is* an angle. This is the figure a thumb can copy
// rather than translate, which is the whole argument for the control and the
// only reason there are two drawings of one value on this surface.
//
// **It is not the travel bent round.** Four things are decided differently
// here, and each of them is the circle's rather than a preference:
//
// - **A ring's ends are marks on its scale, not caps on a line.** The
//   quarter left open at the bottom already says where the scale stops; the
//   longer mark at each end is the one a Braun panel prints there, which says
//   it in the scale's own vocabulary rather than with a travel's crosses.
// - **The value's mark is a pointer, not a cross.** On a line the mark has to
//   be *on* the line because there is nowhere else for it to be. A ring has a
//   middle, and what a knob has always answered *where is it* with is a
//   pointer from that middle - one figure, and the one every hand already
//   knows how to read.
// - **The scale is printed, and a stop is one of its marks.** Hung just
//   outside the arc, standing in it: a continuous ring prints a notch every
//   five in a hundred, and a stepped one prints a detent per place it can
//   stand, so the two differ by exactly what the two controls differ by -
//   how many places the scale says there are, and that they are places.
// - **Nothing is drawn where the value started.** A line has room for a
//   second mark on it, and the gap between the two is what the press did -
//   which is why a travel leaves one. A ring would have to answer *where was
//   it* with a second figure out of the same middle, and two rectangles
//   turned out of one hub is a clock: the tile stops reading as a value and
//   starts reading as a time. The turn reports itself anyway - the run behind
//   the pointer lengthens under the thumb, which is the whole reason that run
//   is drawn.
//
// **What it keeps** is the rest of that file's argument, because the two are
// one control: nothing fills, the run behind the value says how far it has
// come, and a scale with stops fills that run in the accent where one without
// them tints it at half.
//
// **It is a Braun knob, drawn in lines.** The T 1000's bandspread control,
// taken from photographs of one: a cap with an edge and a flat top,
// an index painted on the top, and a scale printed round it on the panel - a
// hairline arc with short marks along it and a longer one at each end. The same line drawing the clock's 6139 is, so a page holding both
// reads as one instrument panel rather than two styles. The cap, the index,
// a mark and an end are drawings for the clock's hands' reason: a silhouette
// that is the same at every value is a shape, and the value only decides the
// angle it is turned to - or, for the cap, nothing, since a circle turned
// looks the same at every angle.
//
// What stays geometry is the ring itself - the scale and the run of it the
// value has covered. That run grows with the number, so it cannot be a
// drawing; and a track drawn once with a run computed against it would be two
// drawings of one figure, which is how two drawings of one thing quietly stop
// matching. `scaleRadius` and `scaleWeight` below are the arc, and they are
// also what `dial-notch.svg` was drawn to hang off: a wider scale is a
// redrawn notch. That is `assets.md`'s split, drawn where this control puts
// it.
//
// **How many marks there are is still the panel's**, which is where this
// parts company with the clock: the clock generates its track because it is
// the same on every 6139, and a knob's marks are its places - a ring reading
// a list of three has three where one reading a ladder of six has six, and a
// continuous one twenty-one, one every five in a hundred. One drawing,
// turned to as many places as the value has.
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

  // The scale, the part of it the value has covered, and the pointer. All of
  // them the caller's: this file names no colour, for qml.md 8.1's reason,
  // and a ring handed none of them draws an empty card with nothing in any
  // log about it.
  property color ink: "transparent"
  property color trail: "transparent"
  property color mark: "transparent"

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

  // Where the value is. **A stepped value stands on a stop**, not between two:
  // its places are the marks themselves, so the first of them is the start of
  // the scale with nothing covered behind it - `Travel.qml`'s own correction,
  // and the same one a ring needs.
  readonly property real here: knob.stepped
    ? Math.max(0, Math.min(knob.divisions, knob.at)) / knob.divisions
    : knob.share

  // Whether the value has got as far as a mark. Nothing is reached at
  // nought: the run behind the value is empty there, and the first mark lit
  // while the arc beside it is not would be the one place `Off` is drawn
  // doing something. The small margin is a stop's share arriving as a float.
  function reached(place) {
    return knob.here > 0 && place <= knob.here + 0.0001
  }

  function angleAt(place) {
    return knob.arcFrom + knob.arcSweep * place
  }
  // The pointer and the notch are both drawn standing at twelve o'clock,
  // which is a quarter turn before the three the scale's angles are measured
  // from - so a figure's rotation is the scale's angle with that quarter
  // added back.
  function turnAt(place) {
    return knob.angleAt(place) + 90
  }

  // The ring, out from the middle. Only these two are numbers: the pointer
  // stops short of the scale, and a mark stands on the scale's middle, and
  // both of those are in the drawings.
  //
  // The weight is the clock's hairline, a quarter of a unit - the width of
  // each of its case's two rings and of every outline on its face. **A dial
  // is drawn in the clock's weights and no others**: the first knob drew
  // its own, a hair lighter, and beside the 6139 it read as the fainter of
  // two drawings rather than one panel. `DialsShareTheClocksWeights` holds
  // the drawings to it; this one number it cannot see.
  readonly property real scaleAt: 16.6
  readonly property real scaleRadius: knob.unit * knob.scaleAt
  readonly property real scaleWeight: knob.unit * 0.25

  // Half a width, in the face's units, turned into degrees along the arc.
  function across(half) {
    return Math.asin(half / knob.scaleAt) * 180 / Math.PI
  }

  // **The arc runs on into each end mark and stops inside its outer side.**
  // An end is the clock's baton with its foot left open, and the arc is what
  // closes it, so the two read as one corner the scale turns. Stopped at the
  // baton's middle, as it first was, the arc left half the baton hanging
  // past its end and the two touched at a point - a break at nought and at a
  // hundred. It stops in the middle of that side's hairline rather than at
  // its edge, so the arc's own end is under the baton and never an edge of
  // the drawing: two figures sharing an edge each soften it on their own.
  // The baton's half-width is `dial-end.svg`'s and the clock's.
  readonly property real endHalf: 0.4536
  readonly property real overrun: knob.across(knob.endHalf - 0.125)
  readonly property real arcLow: knob.arcFrom - knob.overrun
  readonly property real arcHigh: knob.arcFrom + knob.arcSweep + knob.overrun

  // Where the scale and the run behind the value meet. At either end the
  // overrun goes with whichever of the two is there, so the corner an end
  // turns is one colour - the colour its baton is lit in. Anywhere between,
  // **half a mark past the value**: a value on a mark lights that mark, and
  // the mark's foot stands in the arc, so the run has to reach under all of
  // it or the lit foot would sit half on the unlit scale - two layers over
  // one place (see `lit` below). Half a mark is under a pixel; nothing reads
  // the run's end that closely, and the pointer is what says the value.
  readonly property real markHalf: 0.1832
  readonly property real split: knob.here <= 0 ? knob.arcLow
    : knob.here >= 1 ? knob.arcHigh
    : Math.min(knob.arcHigh,
               knob.angleAt(knob.here) + knob.across(knob.markHalf))

  // The marks a continuous scale prints: one every five in a hundred, from
  // nought to the top, which is twenty-one of them. Five is the step the
  // volume and the brightness take (`live.py`), so on the ring that ships a
  // press moves the index exactly one mark and the lit marks count the
  // presses. The T 1000 engraves thirty-one, one every nine degrees; a scale
  // in the value's own units reads better than a finer one in nobody's. Not
  // a setting: it is how the panel is engraved, and a value turned in other
  // steps still lands between two marks rather than off the scale.
  readonly property int printed: 21
  readonly property int marks: knob.stepped ? knob.stops : knob.printed

  // **A scale with stops fills its run in the accent; one without them tints
  // it.** Two different claims rather than two strengths of one: a stop is a
  // place the value has *stood on*, and a continuous value has been at every
  // point behind it and stood at none. Lifted from `Travel.qml` rather than
  // decided again, because it is the same control.
  readonly property color covering: knob.stepped ? knob.mark : knob.trail

  // **A stepped ring prints detents, and fills the ones stood on.** A
  // place to stand is a bigger claim than a graduation: three notches round
  // a list of three read as a scale somebody forgot to finish, where three
  // detents read as three places. One the value has reached is filled in,
  // and so is an end - the index is the end baton filled, and a stop is a
  // place the value has *stood on*, which a continuous value never has. The
  // same four figures stand on a stepped travel (`Travel.qml`).
  function figure(name, lit) {
    if (!knob.art) return null
    var filled = lit && knob.stepped && name !== "notch"
    return knob.art.find("dial", filled ? name + "-lit" : name)
  }

  // A colour at full strength, for drawing inside a layer that is faded
  // as a whole.
  function solid(c) {
    return Qt.rgba(c.r, c.g, c.b, 1)
  }

  Item {
    id: face
    width: knob.side
    height: knob.side
    // Whole pixels, because each of the two layers below is a texture the
    // size of the face: one centred on a half pixel is sampled half a pixel
    // off, and every hairline in it goes soft.
    x: Math.round((knob.width - knob.side) / 2)
    y: Math.round((knob.height - knob.side) / 2)

    // **Two layers, one per ink, each drawn opaque and faded once.** The
    // inks are translucent, and figures drawn one by one in a translucent
    // ink cannot meet cleanly: overlap and the place painted twice is a
    // blot, abut and the one pixel both edges share is two partial coats,
    // which come to less than one - a faint seam where the arc met an end
    // was the trace of it. The first drawing lived with the rule that
    // nothing may touch anything and still showed the seam. Inside a layer
    // the figures are opaque, so they overlap by a hair where they meet and
    // the overlap cannot show; the fade is applied to the finished drawing,
    // which is one coat everywhere.
    //
    // What the value has not reached is one layer, in the dial's ink: the
    // cap, the scale from the value on, and every mark not yet lit.
    Item {
      anchors.fill: parent
      opacity: knob.ink.a
      layer.enabled: true

      // The cap: its edge and its flat top. It does not turn - the index on
      // it does.
      BadgeArt {
        anchors.fill: parent
        drawn: knob.art ? knob.art.find("dial", "cap") : null
        fill: knob.solid(knob.ink)
      }

      Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer

        // The scale: what the value has still to cross, from the value on.
        ShapePath {
          fillColor: "transparent"
          strokeColor: knob.solid(knob.ink)
          strokeWidth: knob.scaleWeight
          capStyle: ShapePath.FlatCap

          PathAngleArc {
            centerX: face.width / 2
            centerY: face.height / 2
            radiusX: knob.scaleRadius
            radiusY: knob.scaleRadius
            startAngle: knob.split
            sweepAngle: knob.arcHigh - knob.split
          }
        }
      }

      Marks {
        dial: knob
        lit: false
        fill: knob.solid(knob.ink)
      }
    }

    // **What the value has already covered**, the second layer, which is
    // what makes a press visible: the pointer moves by a few degrees and a
    // few degrees is not a change anybody sees from a sofa, where the run
    // behind it is read against the run ahead. The two layers meet end to
    // end at `split` and nowhere else.
    Item {
      anchors.fill: parent
      opacity: knob.covering.a
      layer.enabled: true

      Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
          fillColor: "transparent"
          strokeColor: knob.solid(knob.covering)
          strokeWidth: knob.scaleWeight
          capStyle: ShapePath.FlatCap

          PathAngleArc {
            centerX: face.width / 2
            centerY: face.height / 2
            radiusX: knob.scaleRadius
            radiusY: knob.scaleRadius
            startAngle: knob.arcLow
            // Zero at the bottom of the scale, where a value that has
            // covered nothing has covered nothing: a ring lit from its own
            // start is the one place a `Off` could be drawn doing something.
            sweepAngle: knob.split - knob.arcLow
          }
        }
      }

      Marks {
        dial: knob
        lit: true
        fill: knob.solid(knob.covering)
      }
    }

    // The value: the index painted on the cap, from near its middle to near
    // its edge. The loudest thing on the drawing, because it is the one thing
    // the tile exists to say, and no hub under it - it is paint on a flat
    // top, not a hand on a pivot. Outside both layers: it touches nothing.
    BadgeArt {
      anchors.fill: parent
      rotation: knob.turnAt(knob.here)
      drawn: knob.art ? knob.art.find("dial", "pointer") : null
      fill: knob.mark
    }
  }

  // The printed scale, as one layer draws it: the marks it holds are the
  // ones the value has reached or the ones it has not, and every mark is in
  // exactly one of the two. A `Repeater` over a count the value cannot
  // change: walking a knob must never rebuild these, the way walking a
  // slider must never rebuild its ticks - only which layer shows a mark
  // follows the value.
  //
  // **Every mark but the two ends**, which are the longer drawing at the
  // same two angles: the ends take the first and last marks' places, and
  // one drawn under the other would only be the shorter one hidden.
  component Marks: Item {
    id: engraving
    // The knob, handed in: an inline component does not see the ids of the
    // file it is declared in.
    required property var dial
    property bool lit: false
    property color fill: "transparent"
    anchors.fill: parent

    Repeater {
      model: Math.max(0, engraving.dial.marks - 2)

      BadgeArt {
        required property int index
        readonly property real place: (index + 1) / Math.max(1, engraving.dial.marks - 1)
        anchors.fill: parent
        visible: engraving.dial.reached(place) === engraving.lit
        rotation: engraving.dial.turnAt(place)
        drawn: engraving.dial.figure(
          engraving.dial.stepped ? "detent" : "notch", engraving.lit)
        fill: engraving.fill
      }
    }

    Repeater {
      model: 2

      BadgeArt {
        required property int index
        anchors.fill: parent
        visible: engraving.dial.reached(index) === engraving.lit
        rotation: engraving.dial.turnAt(index)
        drawn: engraving.dial.figure("end", engraving.lit)
        fill: engraving.fill
      }
    }
  }
}
