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
// harder than the windows beside it would just look wrong. The radius ladder
// below takes the first of them as a *base* and does scale what it steps down
// to, which is the one place that distinction has to be made carefully: see
// the note there.
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
  // **Type climbs by sqrt(2) as well**, and it did not always. It ran on the
  // fourth root of the ratio - about 1.2465 - on the argument that the
  // difference between 10 and 12 is real and a surface needs both, a detail
  // line smaller than the label over it and still legible.
  //
  // What changed is what a cell holds. A label over a *detail* wants two
  // sizes close together; a label over a **value** wants them far apart -
  // the value is the thing the cell exists to say and the label is the word
  // that names it, and on the design this surface is built to they are two
  // sqrt(2) rungs apart with nothing in between. A finer ladder cannot put
  // them there without stopping on a rung nobody has a name for, and a
  // surface with five named sizes and four unnamed ones between them is not
  // a scale any more.
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

  // Five sizes, anchored on the shell's caption: 12, 17, 24, 34, 48 at the
  // default theme and scale - the design's own 11, 16, 23, 32, 45 hung off
  // the theme's smallest size rather than off 8. Named for the job rather than
  // numbered, because there are only five and each is a decision about what a
  // thing is: `fine` is the word that names a value, `body` is what a label
  // and a card are set in, `lead` is the value itself, and `vast` is the one
  // thing on the surface read from the far side of the room.
  //
  // They are rungs 0 to 4, consecutive: on this ladder every rung is a size
  // worth having, which is the other half of why it is this ladder. `loud` is
  // `fine` at the silver ratio less one squared, and `vast` is the largest
  // thing the design sets - a hero's title - rather than a number found by
  // looking.
  readonly property QtObject type: QtObject {
    readonly property int fine: metrics.px(Style.font.caption)
    readonly property int body: metrics.px(metrics.rung(Style.font.caption, 1))
    readonly property int lead: metrics.px(metrics.rung(Style.font.caption, 2))
    readonly property int loud: metrics.px(metrics.rung(Style.font.caption, 3))
    readonly property int vast: metrics.px(metrics.rung(Style.font.caption, 4))
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

  // -- the line ------------------------------------------------------------
  //
  // **One line, drawn at two rotations.** Down the side of a card of rows,
  // where the row in force lights its own length of it and two marks bracket
  // that length; and along the foot of a slider, a stepped slider and a
  // reading, where the value stands on one mark of its own (`Travel.qml`). They are one drawing, so the
  // measurements in it are named once here rather than twice in two surfaces
  // - two copies of a stroke weight is how two drawings of one thing quietly
  // stop matching, and this one is drawn on two surfaces at once.
  //
  // **Off the size ladder, the way every stroke weight is** (qml.md 8.2.1): a
  // line is structure rather than a gap between two things. The weight is two
  // pixels at this surface's scale, and everything else is that weight
  // stepped by `silver` - the smallest amount this tree has a name for.
  readonly property QtObject spine: QtObject {
    id: spine

    // The line itself.
    readonly property int weight: Math.max(1, metrics.space(2))
    // How far the line carries on past what it measures, at either end - a
    // line that began exactly at the first row's edge began nowhere: it read
    // as the edge of the ground behind it rather than as a thing of its own.
    // The same run of bare line goes before the first stop of a travel and
    // after its last, so both drawings start the same way.
    readonly property int arm: Math.round(spine.weight * metrics.silver)
    // **One stroke crosses the line, and it is the only mark either drawing
    // has**: the cap at each end of the line, a stop a stepped value may
    // stand on, and the place the value has got to. This is how far it
    // reaches on **each** side, so the two halves are equal and the figure is
    // a cross rather than a tick hanging off one face.
    //
    // The arm stepped a rung of the space ladder and halved, which is what
    // keeps the whole of it a little longer than the line's own run past the
    // rows: a mark on a scale has to be found from a sofa, and a corner does
    // not.
    readonly property int cross: Math.round(
      metrics.rung(spine.arm, 1) / 2)
    // And how far the two that **end** a travel reach: one rung of the space
    // ladder above a stop, which is the silver ratio less one and the step
    // everything else on these surfaces climbs by. An instrument of one
    // stroke weight has only length to tell one kind of mark from another,
    // and the two kinds here are *this is as far as it goes* and *this is a
    // place it can stand* - which is one rung's worth of difference. It was
    // the whole silver step for a pass and read as two marks of two
    // different sizes rather than one scale.
    readonly property int crossEnd: Math.round(
      metrics.rung(spine.cross, 1))
  }

  // -- the durations --------------------------------------------------------
  //
  // Everything these surfaces animate is one of three things, and each is a
  // length of attention rather than a size - so this is a list of named jobs
  // and **not** a ladder. A gap twice another gap is a proportion; a
  // fade twice another fade is just a slower fade, and the numbers here were
  // arrived at by watching a screen rather than by multiplying.
  //
  // What is scaled is time, not distance, so `factor` has no business here:
  // a surface drawn twice as large does not take twice as long to fade, and
  // a sofa is further away rather than slower.

  // How long everything on this surface takes, as a multiplier. Set from the
  // payload like `scale`, because the plugin cannot read omapad's config.
  //
  // **0 is motion off, and it is not the same as removing the animation.** A
  // `Behavior` with no duration still lands on the value it was going to, so
  // the two paths stay one path: a tile that faded out is still a tile that
  // has gone, and nothing has to be written twice to say so.
  //
  // A countdown is not motion and never comes through here: `[ripple] ms`
  // and the confirm badge's lap are how long a promise takes, and a person
  // who has asked the screen to hold still has not asked for a shorter wait
  // before something fires.
  property real motion: 1.0

  function ms(n) {
    var v = n * (metrics.motion >= 0 ? metrics.motion : 1)
    if (v <= 0) return 0
    return Math.max(1, Math.round(v))
  }

  // -- the screen's own edge ------------------------------------------------
  //
  // What a television takes off each side of the picture, as a share, from
  // the payload like everything else the plugin cannot read. It is zero
  // everywhere but game mode: the daemon answers that question, because the
  // mode lives there.
  //
  // Not scaled, and it is the one measurement here that must not be. `factor`
  // is how far away the reader is; this is how much of the picture the set
  // never draws, which is a proportion of the screen and nothing to do with
  // how big anything on it is.
  //
  // **It is a floor.** A surface passes its own margin through `edge()` and
  // gets back whichever is larger, so a surface already standing further in
  // than this is left exactly where it was.
  property real safeArea: 0

  function edge(span, own) {
    var keep = span > 0 ? Math.round(span * metrics.safeArea) : 0
    return Math.max(keep > 0 ? keep : 0, own)
  }

  readonly property QtObject time: QtObject {
    // A fade inside a tile: a label arriving, a badge dimming.
    readonly property int brisk: metrics.ms(90)
    // A view catching up with a selection that has already moved.
    readonly property int follow: metrics.ms(110)
    // A whole surface arriving, or a badge leaning under a thumb.
    readonly property int arrive: metrics.ms(140)
  }

  // -- the radius ladder ----------------------------------------------------
  //
  // One base, stepped by the same sqrt(2) as a gap. There were two unrelated
  // numbers before: the compositor's rounding drew the card and the chips and
  // `menu.tile_corner` drew the tiles - so on a setup that rounds nothing,
  // and Omarchy ships as one, a square card held a page of rounded tiles.
  //
  // **The base is the compositor's when it has one.** `decoration:rounding`
  // is this desktop's own answer to how hard a corner is rounded, and a
  // surface that picked its own would be the one thing on screen not
  // answering to it. Where it rounds nothing it is saying that about
  // *windows* - and a tile is not a window, so the surface's own setting is
  // the base there. That is the job `menu.tile_corner` now has: not a tile's
  // radius, but the base the compositor has when the compositor has none.
  //
  // Only the two rungs with call sites are named. Anything between them is
  // `metrics.rung(metrics.radius.tile, n)`, the same as every other size that
  // sits off the named ones.
  //
  // A pill is not on this ladder and never joins it: a switch knob is round
  // because it is round, which is a geometric identity rather than a decision,
  // and `height / 2` is how it is said. It used to say *and a slider track*,
  // and that trough is gone - what a value sits on is a line now, with square
  // ends and a cross at each of them (`spine` below).

  // What this surface rounds a corner by with no compositor answer, in
  // unscaled pixels. Set from the payload like `scale`, because the shell
  // cannot read omapad's config.
  property real cornerBase: 0

  // And how hard to round it, against whichever of the two is in force
  // (`[ui] radius`). 1.0 is exactly what the desktop rounds and 0 is square.
  //
  // It is a multiplier rather than a number because **the base is never
  // ours**: the compositor has already answered how hard a corner is rounded
  // on this machine, and a surface that replaced that answer would be the one
  // thing on screen not listening. What this says is how far off it somebody
  // wants these surfaces - and it walks the same sqrt(2) ladder every other
  // size here does, because a corner is a size.
  property real radiusScale: 1.0

  // Rounded like a measurement rather than through `space()`, which would put
  // the shell's spacing scale on a radius as well: a corner is a share of the
  // thing it is drawn on, not a gap between two of them. Zero survives - a
  // base of zero is somebody asking for square.
  function radiusPx(n) {
    var r = n * metrics.radiusScale
    return r > 0 ? Math.max(1, Math.round(r * metrics.factor)) : 0
  }

  readonly property QtObject radius: QtObject {
    // The compositor's geometry, shared with every window on screen, and so
    // not scaled - the rule `Style.cornerRadius` has always had. Anything
    // that reads as a window takes this, square included.
    readonly property int card: Math.max(
      0, Math.round(Style.cornerRadius * metrics.radiusScale))
    // Everything inside one: a tile, a chip. Scaled, unlike the card, because
    // a corner inside the card belongs to the thing it is drawn on - a tile
    // twice the size with the same corner reads as a tile that lost its
    // rounding.
    readonly property int tile: metrics.radiusPx(
      Style.cornerRadius > 0 ? Style.cornerRadius : metrics.cornerBase)
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
