// The shell's measurements, at omapad's own scale.
//
// Every surface here is drawn twice as far away as an Omarchy menu is: the
// desktop reads them at a keyboard, game mode reads them from a sofa. The
// shell has one scale for the whole session, so a couch-sized menu cannot be
// asked for through `Style` - this multiplies it per surface instead, from the
// number the daemon stamps on every payload.
//
// A multiplier rather than a replacement, deliberately: a theme that runs
// roomy, or a user who has raised the shell's own font, keeps those
// proportions and gets them scaled, so the surfaces still read as the same
// family as the desktop they sit on.
//
// Only what depends on the reading distance is scaled. `Style.cornerRadius`
// and `Style.gapsOut` are the compositor's own geometry - the radius of every
// window on screen, the gap it keeps - and a surface that rounded its corners
// harder than the windows beside it would just look wrong.
import QtQuick
import qs.Commons

QtObject {
  id: metrics

  property real scale: 1.0
  // A payload can carry anything; a zero or a negative here would collapse
  // every measurement on the surface to nothing.
  readonly property real factor: scale > 0 ? scale : 1.0

  function spaceReal(px) {
    return Style.spaceReal(px) * metrics.factor
  }

  function space(px) {
    var n = metrics.spaceReal(px)
    if (n <= 0) return 0
    return Math.max(1, Math.round(n))
  }

  function px(n) {
    return Math.max(1, Math.round(n * metrics.factor))
  }

  // A badge is one of `assets/shapes` scaled into the box a surface reserves
  // for it, and that box has to be whole pixels on *both* sides. BadgeArt
  // scales the drawing by one factor taken from the width, so a height the
  // shape's own aspect does not divide leaves the drawing standing a fraction
  // of a pixel off its box - and the flat edges inside it, the system pill's
  // rim above all, land mid-pixel and come out grey rather than drawn.
  //
  // Every shape is 32 units tall against 32 or 64 wide, except the system
  // buttons at 40 by 48 - the round one and the oblong share a box - and the
  // stick at 40 by 56, so five is the smallest step that keeps `unit * w / h`
  // whole for all of them. A geometric identity of the drawings rather than a
  // setting - it changes when a shape is redrawn on another canvas, and
  // nowhere else. It is also what a new canvas has to answer to: the stick
  // was drawn 44 by 32 first, and 44/32 needs a unit divisible by eight.
  readonly property int badgeGrid: 5

  // Snapped up, never down: every caller hands this the larger of the floors
  // it has already decided a badge must clear, and a badge losing a pixel to
  // the grid would be the one place sharpening cost legibility.
  function badge(px) {
    var n = Math.max(1, Math.round(px))
    return Math.ceil(n / metrics.badgeGrid) * metrics.badgeGrid
  }

  // -- the silver ladder ----------------------------------------------------
  //
  // Type and space on one proportion, so a surface has a scale of its own
  // rather than a list of numbers somebody once liked.
  //
  // The shell's scale is a list of near neighbours - 10, 11, 12, 13, 14, 16 -
  // and five of the six landed on one card here. That is five sizes at a
  // keyboard and one size from a sofa: a pixel of difference is not a
  // difference across a room. So the question is how far apart, and the
  // silver ratio answers it twice, because a gap and a letter are not asked
  // the same question.
  //
  // **Space climbs by sqrt(2)**, the silver ratio less one. A gap either
  // separates two things or it does not - nobody reads the difference between
  // 14 and 16 pixels of air - so it wants few rungs far apart, and sqrt(2)
  // doubles in exactly two of them, which keeps the ladder landing on 4, 8,
  // 16, 32 rather than drifting off the familiar numbers.
  //
  // **Type climbs by the fourth root of the ratio**, about 1.2465, because
  // there the difference between 10 and 12 is real and a surface needs both:
  // a detail line under a label has to be smaller than it and still legible,
  // and one rung of sqrt(2) puts those two five pixels apart. Four rungs is
  // the silver ratio itself, which is what makes it that root rather than any
  // other: `loud` is `fine` at 1 + sqrt(2). The clock set over its weekday is
  // that split, drawn.
  //
  // Both are anchored on the shell's own smallest value rather than its body
  // text and its middle gap. The smallest thing a surface prints is the one
  // that must not shrink, and a ladder hung from the middle has nowhere
  // legible to put a detail line.
  //
  // A surface uses this ladder **or** `font` and `spacing` above, never a
  // mixture: half a surface on one scale and half on another is what this is
  // here to end. The menu is the first surface across.
  readonly property real silver: 1 + Math.sqrt(2)

  // `base` scaled by `n` space rungs, before rounding. Negative goes down.
  function rung(base, n) {
    return base * Math.pow(Math.SQRT2, n)
  }

  // The same, on the type ladder's finer rung. Four of these is `silver`.
  function step(base, n) {
    return base * Math.pow(metrics.silver, n / 4)
  }

  // Five sizes, anchored on the shell's caption: 10, 12, 16, 24, 47 at the
  // default theme and scale. The first three are where the shell's own
  // caption, body and heading already were, because those three were the ones
  // that were right. Named for the job rather than numbered, because there are
  // only five and each is a decision about what a thing is: `fine` is a mark
  // beside something, `body` is what a label and a chip are set in, `vast` is
  // the one thing on the surface read from the far side of the room.
  //
  // They are rungs 0, 1, 2, 4 and 7 - not consecutive, because the ladder is
  // finer than the set of jobs a surface has, and the gaps are where a size
  // would have been too close to its neighbour to mean anything different.
  //
  // **The ladder decides the steps and the screen decides which one to stop
  // on.** `loud` at rung 4 is `fine` at the silver ratio exactly, and `vast`
  // is not a whole ratio above anything - it is three rungs over `loud`
  // because four was too much from a sofa and two was not enough, and both of
  // those were found by looking rather than by arithmetic. A scale is what
  // stops the sizes drifting between the rungs; it was never going to say
  // which rung a clock wants.
  readonly property QtObject type: QtObject {
    readonly property int fine: metrics.px(Style.font.caption)
    readonly property int body: metrics.px(metrics.step(Style.font.caption, 1))
    readonly property int lead: metrics.px(metrics.step(Style.font.caption, 2))
    readonly property int loud: metrics.px(metrics.step(Style.font.caption, 4))
    readonly property int vast: metrics.px(metrics.step(Style.font.caption, 7))
  }

  // Nine gaps, anchored on the shell's `sm`: 3, 4, 6, 8, 11, 16, 23, 32, 45.
  // Sized names rather than job names, and the shell's own vocabulary for
  // them, because nine of anything is only readable at the call site if the
  // name says which way is bigger.
  readonly property QtObject gap: QtObject {
    // A hairline is one device pixel by definition, the same as above: it is
    // not on the ladder and scaling it would make it a rule.
    readonly property int hairline: Style.spacing.hairline
    readonly property int xxs: metrics.space(metrics.rung(4, -1))
    readonly property int xs: metrics.space(4)
    readonly property int sm: metrics.space(metrics.rung(4, 1))
    readonly property int md: metrics.space(8)
    readonly property int lg: metrics.space(metrics.rung(4, 3))
    readonly property int xl: metrics.space(16)
    readonly property int xxl: metrics.space(metrics.rung(4, 5))
    readonly property int xxxl: metrics.space(32)
    readonly property int huge: metrics.space(metrics.rung(4, 7))
  }

  readonly property QtObject font: QtObject {
    // The family is the session's, at any size.
    readonly property string family: Style.font.family
    readonly property string resolvedFamily: Style.font.resolvedFamily
    readonly property string menuFamily: Style.font.menuFamily
    readonly property int baseSize: metrics.px(Style.font.baseSize)

    readonly property int caption: metrics.px(Style.font.caption)
    readonly property int bodySmall: metrics.px(Style.font.bodySmall)
    readonly property int body: metrics.px(Style.font.body)
    readonly property int subtitle: metrics.px(Style.font.subtitle)
    readonly property int title: metrics.px(Style.font.title)
    readonly property int heading: metrics.px(Style.font.heading)
    readonly property int display: metrics.px(Style.font.display)
    readonly property int displayLarge: metrics.px(Style.font.displayLarge)

    readonly property int iconSmall: metrics.px(Style.font.iconSmall)
    readonly property int icon: metrics.px(Style.font.icon)
    readonly property int iconLarge: metrics.px(Style.font.iconLarge)
  }

  readonly property QtObject spacing: QtObject {
    readonly property real scale: Style.spacing.scale * metrics.factor

    // A hairline is one device pixel by definition; scaling it would make
    // it a rule.
    readonly property int hairline: Style.spacing.hairline
    readonly property int xxs: metrics.px(Style.spacing.xxs)
    readonly property int xs: metrics.px(Style.spacing.xs)
    readonly property int sm: metrics.px(Style.spacing.sm)
    readonly property int md: metrics.px(Style.spacing.md)
    readonly property int lg: metrics.px(Style.spacing.lg)
    readonly property int xl: metrics.px(Style.spacing.xl)
    readonly property int xxl: metrics.px(Style.spacing.xxl)
    readonly property int xxxl: metrics.px(Style.spacing.xxxl)
    readonly property int huge: metrics.px(Style.spacing.huge)

    readonly property int controlGap: metrics.px(Style.spacing.controlGap)
    readonly property int controlPaddingX: metrics.px(Style.spacing.controlPaddingX)
    readonly property int controlPaddingY: metrics.px(Style.spacing.controlPaddingY)
    readonly property int inputPaddingY: metrics.px(Style.spacing.inputPaddingY)
    readonly property int controlHeight: metrics.px(Style.spacing.controlHeight)
    readonly property int rowGap: metrics.px(Style.spacing.rowGap)
    readonly property int rowPaddingX: metrics.px(Style.spacing.rowPaddingX)
    readonly property int labelGap: metrics.px(Style.spacing.labelGap)
    readonly property int panelGap: metrics.px(Style.spacing.panelGap)
    readonly property int panelPadding: metrics.px(Style.spacing.panelPadding)
    readonly property int popupPadding: metrics.px(Style.spacing.popupPadding)
  }
}
