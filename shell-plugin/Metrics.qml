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
  // Every shape is 32 units tall against 32 or 64 wide except the system
  // pill, 40 by 64, so five is the smallest step that keeps `unit * w / h`
  // whole for all of them. A geometric identity of the drawings rather than a
  // setting - it changes when a shape is redrawn on another canvas, and
  // nowhere else.
  readonly property int badgeGrid: 5

  // Snapped up, never down: every caller hands this the larger of the floors
  // it has already decided a badge must clear, and a badge losing a pixel to
  // the grid would be the one place sharpening cost legibility.
  function badge(px) {
    var n = Math.max(1, Math.round(px))
    return Math.ceil(n / metrics.badgeGrid) * metrics.badgeGrid
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
