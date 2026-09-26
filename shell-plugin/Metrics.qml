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
  // Every surface is on it. The shell's own list of sizes was kept here as
  // `font.caption` and `spacing.md` and the like while the surfaces moved
  // across one at a time, and went when the last one did: a surface with one
  // size on each scale is what this is here to end, and a scale nobody reads
  // cannot be mixed in by accident.
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
  // that length; and along the foot of a slider, where it is the scale a
  // needle runs across (`Travel.qml`). The weight is named once here rather
  // than twice in two surfaces - two copies of a stroke weight is how two
  // drawings of one thing quietly stop matching. What stands on the line is
  // each drawing's own: a slider's figures are the knob's, unrolled, and a
  // card keeps its crosses and draws its row in force three weights wide.
  //
  // **Off the size ladder, the way every stroke weight is** (qml.md 8.2.1): a
  // line is structure rather than a gap between two things. The weight is two
  // pixels at this surface's scale, and the run past a card's ends is that
  // weight stepped by `silver` - the smallest amount this tree has a name
  // for. How far anything standing on the line reaches is its drawing's
  // (`travel-*.svg`, a whole number of weights on every side), because a
  // drawing owns its own proportion.
  readonly property QtObject spine: QtObject {
    id: spine

    // The line itself.
    readonly property int weight: Math.max(1, metrics.space(2))
    // How far a card's line carries on past its first row and its last - a
    // line that began exactly at the first row's edge began nowhere: it read
    // as the edge of the ground behind it rather than as a thing of its own.
    readonly property int arm: Math.round(spine.weight * metrics.silver)
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

  // **These surfaces set their words in their own family**, and the payload
  // says which (`[ui] font`). Empty is the session's own, which is what they
  // shipped reading as and what most desktops want: the group exists so a
  // face can be chosen for a menu read from a sofa without changing the one
  // the desktop is read at.
  //
  // It is the *second* of two font groups and the one that moves. The first
  // is the badges' - `ButtonArt.family`, Fira Code, shipped beside the
  // drawings - and it cannot follow this one: a label is punched out of its
  // silhouette by `assets/generate.py` in that face, so a typed label set in
  // another would not match the drawn one beside it. A surface asks
  // `buttonArt.family` for a button and this for everything else.
  property string fontFamily: ""

  readonly property QtObject font: QtObject {
    // The family, at any size: what the payload asked for, or the one the
    // desktop sets its own menus in where it asked for nothing. That is
    // `menuFamily` rather than `family` because these surfaces are menus -
    // somebody who has given Omarchy's menus a face of their own with
    // `OMARCHY_MENU_FONT` has said what a menu is set in, and ours are the
    // same kind of thing. Unset, the two are the same name.
    readonly property string family: metrics.fontFamily !== ""
      ? metrics.fontFamily : Style.font.menuFamily
  }

  // -- the weights ----------------------------------------------------------
  //
  // **A weight asked for is not a weight drawn.** Every one of these surfaces
  // asked for `Font.Medium` wherever it meant a word to stand out, and the
  // face Omarchy ships - JetBrainsMono Nerd Font - comes as a Regular and a
  // Bold and nothing between. Qt answers 500 with the nearest face at or
  // below it, so the row in force, the tab you are on and the choice that is
  // ticked were all drawn in exactly the weight of the rows beside them, and
  // said so in colour alone. Nothing warned: `fontInfo.weight` hands back the
  // number asked for. `fontInfo.styleName` is the one thing that says which
  // face was drawn, and it is what this reads.
  //
  // So a weight here is a **job**, named like the type ladder, and each job
  // says what happens when the family has no face at the weight it names:
  //
  //   body     the words a surface is read in. 400.
  //   name     a word that names something - a tile's label, a heading, a
  //            caption over a value. 500, and where the family has no 500
  //            it is drawn in whatever Qt finds: a name is already set apart
  //            by its size and its place, and climbing to Bold would put
  //            every label on a page in the weight meant for one of them.
  //   strong   the one thing in force: the row the cursor is on, the choice
  //            that is ticked, the key under the thumb. 500, **and it must
  //            not be drawn in the face `body` is**, because being different
  //            is the whole of what it says. Where the family has nothing
  //            between it climbs to the next face that is - on the shipped
  //            one that is Bold.
  //   display  the one line on a surface read from the far side of the room,
  //            set at `loud` or `vast`. 400: the size already says it is a
  //            heading, and a heavy stroke on top of it was the loudest thing
  //            on the page.
  //
  // The badges are not on this list and cannot be: their labels are Fira
  // Code Medium, punched into the drawings, and `buttonArt.weight` says so.

  // What each job starts from, before the theme and the ground have had
  // their say. Wire values rather than settings: these are the design's own
  // answer to what each job is, and the two ways to move them are below.
  readonly property var weightDefaults: ({
    "body": 400, "name": 500, "strong": 500, "display": 400
  })

  // **The theme's word first.** Omarchy reads every key of a theme's
  // `shell.toml` `[font]` table as a number and keeps the ones it has no use
  // for in `Style.fontOverrides`, so a theme can say what these surfaces are
  // set in without Omarchy knowing they exist:
  //
  //   [font]
  //   omapad-weight-strong = 700
  //
  // Prefixed, because the table is Omarchy's and a bare `weight-body` is a
  // name it could one day want for itself.
  function themeWeight(job) {
    var v = Style.fontOverrides["omapad-weight-" + job]
    return (v !== undefined && isFinite(v) && v > 0)
      ? v : metrics.weightDefaults[job]
  }

  // **Then the ground.** The design was drawn light on dark, which is also
  // what Omarchy ships, so a dark ground takes the weights as they are. Dark
  // ink on a light ground reads thinner than the same stroke reversed - the
  // eye spreads a bright stroke and swallows a dark one - and what that costs
  // is the difference between a word that is meant to stand out and the
  // words around it. So a light ground puts half a step on `name` and
  // `strong`, and leaves `body` and `display` alone: reading text is not
  // meant to stand out, and a heading already does by its size.
  //
  // Half a step, because a whole one is a different face on most families -
  // Noto answers 450 from its Medium - and a light theme is not a reason to
  // set a page of labels in the weight meant for the one row in force. On a
  // family of whole faces the probes below find the same face either side of
  // it and nothing changes; on a variable one it is the difference and no
  // more.
  //
  // Which is which is measured rather than read from the theme's name: a
  // theme is light when its text is darker than the ground it is drawn on.
  // `ground` and `ink` default to the menu's; the game bar hands its own.
  property color ground: Color.menu.background
  property color ink: Color.menu.text
  readonly property bool lightGround: tone.luminance(metrics.ground)
    > tone.luminance(metrics.ink)
  readonly property Ink tone: Ink {}

  function groundWeight(job) {
    if (!metrics.lightGround) return 0
    return (job === "name" || job === "strong") ? 50 : 0
  }

  // **And last, the person's.** Whole steps of a hundred, from the payload
  // (`[ui] weight`, `game_weight`), because the plugin cannot read omapad's
  // config. A step over every job at once: the proportions between them are
  // the design, and what somebody wants different is how heavy the whole
  // surface reads - from a sofa, usually heavier.
  property real weightStep: 0

  // On the half steps the probes below stand on, so every weight a job is
  // given is one this has asked Qt about rather than one it guessed at.
  function nominal(job) {
    var w = metrics.themeWeight(job) + metrics.groundWeight(job)
      + metrics.weightStep * 100
    return Math.max(100, Math.min(900, Math.round(w / 50) * 50))
  }

  // One probe per half step, set in the surface's own family, each saying
  // which face Qt drew it in. Half steps because that is the finest thing
  // `groundWeight` asks for, and a weight answered from the nearest whole
  // probe can be answered wrongly: Qt draws 450 from the face below and 550
  // from the face above, and rounding either to a hundred guesses which.
  //
  // A probe needs a character to set - an empty Text never resolves a face,
  // and reports Regular at every weight. `family` and `styleName` together,
  // because a family missing a face can be answered from a fallback family,
  // and that is a different face too.
  property list<Text> probes: [
    Text { text: "H"; font.family: metrics.font.family; font.weight: 100 },
    Text { text: "H"; font.family: metrics.font.family; font.weight: 150 },
    Text { text: "H"; font.family: metrics.font.family; font.weight: 200 },
    Text { text: "H"; font.family: metrics.font.family; font.weight: 250 },
    Text { text: "H"; font.family: metrics.font.family; font.weight: 300 },
    Text { text: "H"; font.family: metrics.font.family; font.weight: 350 },
    Text { text: "H"; font.family: metrics.font.family; font.weight: 400 },
    Text { text: "H"; font.family: metrics.font.family; font.weight: 450 },
    Text { text: "H"; font.family: metrics.font.family; font.weight: 500 },
    Text { text: "H"; font.family: metrics.font.family; font.weight: 550 },
    Text { text: "H"; font.family: metrics.font.family; font.weight: 600 },
    Text { text: "H"; font.family: metrics.font.family; font.weight: 650 },
    Text { text: "H"; font.family: metrics.font.family; font.weight: 700 },
    Text { text: "H"; font.family: metrics.font.family; font.weight: 750 },
    Text { text: "H"; font.family: metrics.font.family; font.weight: 800 },
    Text { text: "H"; font.family: metrics.font.family; font.weight: 850 },
    Text { text: "H"; font.family: metrics.font.family; font.weight: 900 }
  ]

  readonly property var faces: {
    var out = []
    for (var i = 0; i < metrics.probes.length; i++) {
      var info = metrics.probes[i].fontInfo
      out.push(info.family + "/" + info.styleName)
    }
    return out
  }

  function face(w) {
    var i = Math.max(0, Math.min(16, Math.round((w - 100) / 50)))
    return metrics.faces[i]
  }

  readonly property QtObject weight: QtObject {
    readonly property int body: metrics.nominal("body")
    readonly property int name: metrics.nominal("name")
    readonly property int display: metrics.nominal("display")

    // Climbs until the face changes. Where it never does - a family of one
    // face, or a variable one that names every weight alike - it asks for
    // Bold outright, which Qt draws synthetically on a face that has none:
    // an emboldened Regular is a worse letter and a better answer than a
    // difference nobody can see.
    readonly property int strong: {
      var start = metrics.nominal("strong")
      var plain = metrics.face(metrics.weight.body)
      for (var w = start; w <= 900; w += 50) {
        if (metrics.face(w) !== plain) return w
      }
      return Math.max(start, Font.Bold)
    }
  }

  // -- tracking and figures -------------------------------------------------
  //
  // Letter-spacing is a proportion of the letter it spaces, so each is a
  // function of the size rather than a number: a caption scaled up keeps the
  // same air between its capitals.
  readonly property QtObject tracking: QtObject {
    // Capitals set small. An eighth of the letter: caps set without it read
    // as a word with its letters touching.
    function caps(size) {
      return size / 8
    }

    // A masthead - a name and a time set side by side at the top of a
    // screen. Sixteen hundredths of the letter, the design's one line spaced
    // wider than a caption is.
    function masthead(size) {
      return size * 0.16
    }
  }

  // Figures that keep one width each, for a number that changes in place.
  // The shipped face is monospaced and does it anyway; a proportional one
  // chosen with `[ui] font` does not, and a clock whose colon jumps sideways
  // every second is the result.
  readonly property var figures: ({ "tnum": 1 })
}
