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
import QtQuick
import QtQuick.Shapes

Item {
  id: art

  // One entry out of ButtonArt: { w, h, shape, label?, ring?, ringWidth? }.
  property var drawn: null
  property color fill: "transparent"
  property color stroke: "transparent"
  property color ink: "white"
  // The ring a stick click carries is part of the drawing - the rim of the
  // stick, seen from above - and not a border around the badge, so it has a
  // colour and a weight of its own. A surface that wants no outline can drop
  // the stroke and keep the rim; left alone, both follow the stroke.
  property color ringColor: art.stroke
  property real ringWidth: art.strokeWidth
  // In badge pixels. Divided back out below, or the same outline would come
  // out twice as heavy on a bumper as on a face button. Set once and left
  // alone: the only surface that outlines a badge at all is the mapping
  // screen, and what used to animate this - an outline thickening while a
  // hold counted down - is drawn by the game bar's fill sweep now.
  property real strokeWidth: 0

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
      PathSvg { path: art.drawn ? art.drawn.shape : "" }
    }

    // The ring a stick click is drawn with: the stick, seen from above,
    // pressed in. Only that shape carries one.
    ShapePath {
      fillColor: "transparent"
      strokeColor: (art.drawn && art.drawn.ring) ? art.ringColor : "transparent"
      strokeWidth: (art.drawn && art.drawn.ring && art.factor > 0)
        ? art.ringWidth / art.factor : 0
      PathSvg { path: (art.drawn && art.drawn.ring) ? art.drawn.ring : "" }
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
