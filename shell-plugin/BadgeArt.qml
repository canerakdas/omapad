// The drawn half of a badge: one controller button, in the theme's colours.
//
// The geometry comes from ButtonArt.qml, which assets/generate.py writes out
// of the hand-drawn shapes in assets/shapes and Fira Code. Paths rather than
// the SVGs beside them because every surface paints a badge differently - the
// guide fills the button faintly under a solid label, the game bar draws it as
// an outline in whatever colour the wallpaper left readable - and an SVG can
// only carry the colour it was drawn with.
//
// Nothing here decides anything: the caller picks the entry, the colours and
// the weight of the outline, and this scales the 32- or 64-unit drawing to
// whatever size the badge ended up. Set the item's width; the height follows
// the drawing's own aspect, because a squashed button stops reading as one.
//
// One factor for both axes, taken from the width, so the box the caller gives
// has to carry the drawing's aspect exactly - a height the aspect does not
// divide leaves the drawing standing a fraction of a pixel off its own box,
// and the flat edges in it are painted grey instead of drawn. `Metrics.badge`
// is what guarantees it; size a badge with that and nothing else.
import QtQuick
import QtQuick.Shapes

Item {
  id: art

  // One entry out of ButtonArt: { w, h, shape, label? }.
  property var drawn: null
  property color fill: "transparent"
  property color stroke: "transparent"
  property color ink: "white"
  // In badge pixels. Divided back out below, or the same outline would come
  // out twice as heavy on a bumper as on a face button. Set once and left
  // alone: the only surface that outlines a badge at all is the mapping
  // screen, and what used to animate this - an outline thickening while a
  // hold counted down - is drawn by the game bar's fill sweep now.
  property real strokeWidth: 0
  // Whether the label is punched out of the shape instead of set on top of
  // it. One path with an odd-even rule rather than a label painted in the
  // background's colour, because the letter has to be a *hole*: a badge sits
  // over a wallpaper, a card that fades and sometimes another badge, and a
  // letter faking the colour behind it is only right on one of those. The
  // caller can still hand it an `ink`, and then the label is drawn back over
  // its own hole - which is what the game bar inverts on a press.
  property bool knockout: false

  readonly property real factor: (drawn && drawn.w > 0) ? width / drawn.w : 1

  implicitHeight: drawn ? width * drawn.h / drawn.w : 0
  visible: drawn !== null

  Shape {
    width: art.drawn ? art.drawn.w : 0
    height: art.drawn ? art.drawn.h : 0
    preferredRendererType: Shape.CurveRenderer
    // Drawn at its own scale and then scaled up from the top left corner, so
    // the badge is exactly the box the layout gave it.
    transform: Scale { xScale: art.factor; yScale: art.factor }

    ShapePath {
      fillColor: art.fill
      strokeColor: art.stroke
      strokeWidth: art.factor > 0 ? art.strokeWidth / art.factor : 0
      // Odd-even so a second subpath subtracts rather than adding: inside the
      // shape is one crossing, inside a letter two, and inside the counter of
      // an A three - which is the counter drawn back in, for free. It is what
      // the rim of a stick is drawn with too: three subpaths, wound the
      // opposite way in turn, so the same annulus comes out under either rule
      // and the rim scales with the badge instead of staying a hairline on a
      // big one and disappearing where the shape is painted solid.
      fillRule: art.knockout ? ShapePath.OddEvenFill : ShapePath.WindingFill
      PathSvg { path: art.drawn ? art.drawn.shape : "" }
      PathSvg {
        path: (art.knockout && art.drawn && art.drawn.label)
          ? art.drawn.label : ""
      }
    }

    // The label, already set where the shape is roomiest - a shoulder is cut
    // away at one corner and its letters are not centred on the box.
    ShapePath {
      fillColor: art.ink
      strokeWidth: -1
      fillRule: ShapePath.WindingFill
      PathSvg { path: (art.drawn && art.drawn.label) ? art.drawn.label : "" }
    }
  }
}
