// The time with hands on it, and the stopwatch that shares its face.
//
// The menu draws it on a tile and the HUD draws the same tile over a game -
// one page, two surfaces, so one drawing rather than two that look alike.
// `Travel.qml` is here for the same reason, one control along.
//
// **A face rather than a second `%H:%M`.** The menu's head already prints the
// time, and it prints it to somebody who has just opened the menu and is
// already reading words. A tile is glanced at from across a room and over
// something else, and what a glance gets off two hands is roughly when it is,
// which is the whole question anybody asks a clock from a sofa.
//
// **The face is generated and the hands are not.** The rim, the twelve marks
// and the hub are drawing that does not depend on the time, so they come out
// of `ControlArt.qml` like every other piece of a control tile; a hand is a
// rectangle turned to an angle the time decides, and a shape parameterised by
// a number cannot be drawn once. Same split the gauge makes between its dial
// and the dot that follows a thumb, and the same one `BadgeArt` makes between
// a button and the label set into it.
//
// **A clock has no second hand.** The daemon re-sends the page every
// `VIEW_HEARTBEAT` seconds, so a hand that moved every second would be a
// drawing that is visibly wrong most of the time - and a tile left over a game
// is the last place to put something that twitches. Two hands say what a sofa
// asks; the head's `%H:%M` is where the exact minute is.
//
// **A chronograph is the same face with three registers sunk into it, and
// every one of them moves.** That is not the paragraph above being broken, it
// is the other side of it: this face is only ever drawn in the menu, which is
// a surface somebody opened and is looking at, and what it is drawn for is
// measuring. A stopwatch whose hands stood still between payloads would be a
// stopwatch that lies twice a second.
//
// So the daemon sends the state - how long it had measured when the line was
// written, whether it is still going, and how far into the minute the clock
// was - and this file counts on from there, re-stamping itself every time a
// payload lands. It is not a `Timer` polling for state (qml.md 10): the state
// is the daemon's and arrives on the socket; what turns here is a hand on a
// measurement this already holds, which is animation. The timer sleeps
// whenever the surface is down, because a panel nobody can see has nothing to
// animate.
//
// That also means the figures are spelled on this side, which nothing else on
// these surfaces does. Same reason: a number that changes ten times a second
// cannot come off a wire that is written twice a second, and a panel drawing
// tenths it was not sent would be worse than one that spells the number it is
// counting.
//
// **The registers are three, where a panda dial's are.** Running seconds at
// nine, the chronograph's minutes at three, its hours at six - the layout a
// three-register chronograph has worn for ninety years, and the reason to
// follow it is that anybody who has seen one already knows which hand is the
// one that matters. What says a register *is* a register is the ground it is
// sunk into rather than anything drawn on it: marks inside a disc fifteen
// pixels across are two-pixel dots among the twelve already on the dial. The
// contrast is the theme's to decide - a step off the dial in whichever
// direction that theme runs - so it reads as a panda on a dark one and as a
// reverse panda on a light one, without this file naming a colour.
//
// Every measurement here is a share of the face, and none of them is on the
// ladder (qml.md 8.2.1): a hand is a fraction of the dial it turns in, which
// is the same geometric identity that keeps a pill's radius at `height / 2`.
// The face's own units are the shapes' 40, so a number below is what it would
// be in Figma.
import QtQuick

Item {
  id: clock

  // The generated furniture, handed in rather than built here. `ControlArt`
  // cannot be a `pragma Singleton` - it does not register from a plugin
  // directory - so a copy built in this file would be a copy per clock on the
  // page, and the surface already has one to lend.
  property var art: null

  // Minutes since midnight: both of the big hands, in one number. The daemon
  // works it out (`menu.minute_of_day`), because an hour hand stands between
  // two hours by exactly how far round the minute hand has got, and two
  // fields could arrive disagreeing about that.
  property int minutes: 0
  // And how far into the minute it was when that was written, for the one
  // register that is not part of the stopwatch.
  property real seconds: 0

  // Whether the surface this is on is up. Nothing here animates while it is
  // not: a menu that has been closed for an hour must not be turning a hand
  // twenty times a second behind a window nobody can see.
  property bool awake: true

  // The hands, the face they turn in, and the hub they meet under. All three
  // are the caller's: this file names no colour, for qml.md 8.1's reason.
  // `mark` carries the chronograph as well - the hands that measure are the
  // accent and the hands that tell the time are not, which is what keeps five
  // hands on one face readable as two sets.
  property color ink: "transparent"
  property color dim: "transparent"
  property color mark: "transparent"
  // And the ground a register is sunk into. It is a **ground rather than an
  // ink** (qml.md 8.1.2 is about the three inks and this is none of them):
  // what makes a counter read as a counter at this size is a change of
  // ground, which is the same kind of number the tile under it is drawn with.
  property color wash: "transparent"

  // **The chronograph, or nothing.** Seconds measured when the payload was
  // written, and whether it was still running then; negative is a plain clock
  // and draws no complication at all, which is what a tile that is only a
  // clock passes.
  property real elapsed: -1
  property bool ticking: false
  readonly property bool chrono: clock.elapsed >= 0

  // What the face is drawing *now*: the payload's numbers plus however long
  // ago they landed. Re-stamped on every payload, so the drift between two of
  // them is never more than a heartbeat of two clocks disagreeing - and the
  // moment the stopwatch stops, the number is the daemon's exactly.
  property real shown: 0
  property real shownSeconds: 0
  property real since: 0

  onElapsedChanged: clock.stamp()
  onSecondsChanged: clock.stamp()
  onTickingChanged: clock.stamp()

  function stamp() {
    clock.since = Date.now()
    clock.shown = Math.max(0, clock.elapsed)
    clock.shownSeconds = clock.seconds
  }

  // **Twenty a second while it is measuring, four while it is not**, and both
  // are trade-offs rather than settings - the same kind of number the
  // generator's sampling constants are, because nobody configures a repaint.
  //
  // Measuring, the tenths digit changes every other tick and the sweep hand
  // moves a third of a degree, which is where both stop being something you
  // can watch happen in steps. Idle, the only thing moving is the seconds
  // hand of a register fifteen pixels across, and four a second is already
  // finer than a pixel of it.
  //
  // What it costs was measured rather than guessed, with the menu up on this
  // machine: about a point of a core, against one point one for the same page
  // with no clock on it at all. It was **thirteen** points before the
  // stopwatch came off the tile and onto the surface - and that was never
  // this timer, it was a number that differed on every payload rebuilding
  // every delegate on the page. That is the expensive mistake here and it is
  // not one this file can make again: what turns below is a property, and
  // where it came from is the surface's business.
  Timer {
    interval: clock.ticking ? 50 : 250
    repeat: true
    running: clock.awake && clock.chrono
    onTriggered: {
      var gone = (Date.now() - clock.since) / 1000
      // The stopwatch counts on only while it is running; the clock's own
      // seconds always do. Stopped, `shown` stays exactly where the daemon
      // left it, which is the number the tile is being read for.
      clock.shown = Math.max(0, clock.elapsed) + (clock.ticking ? gone : 0)
      clock.shownSeconds = clock.seconds + gone
    }
  }

  // The measurement in figures, because no hand can say *three minutes and
  // twelve*. Tenths under the hour and seconds over it: a stopwatch is read
  // for its tenths in the first minute and for its minutes after that, and a
  // tenth still turning under an hour's worth of figures is a digit nobody is
  // reading and everybody can see.
  readonly property string words: clock.chrono ? clock.spell(clock.shown) : ""

  function spell(seconds) {
    var whole = Math.floor(Math.max(0, seconds))
    var hours = Math.floor(whole / 3600)
    var minutes = Math.floor(whole / 60) % 60
    var pad = function (n) { return n < 10 ? "0" + n : "" + n }
    if (hours > 0)
      return hours + ":" + pad(minutes) + ":" + pad(whole % 60)
    var tenths = Math.floor((Math.max(0, seconds) - whole) * 10)
    return minutes + ":" + pad(whole % 60) + "." + tenths
  }

  // Round in whatever box it was given, rather than oval in a box that is not
  // square: a clock is the one drawing on a page whose aspect is not the
  // cell's to decide.
  readonly property real side: Math.min(clock.width, clock.height)
  // The shapes' own canvas, so the lengths below read as the drawing does.
  readonly property real unit: clock.side / 40

  // Where the two big hands stand. The hour goes round twice a day - half a
  // degree a minute - and it is `% 720` rather than an hour of its own so it
  // carries the minutes with it: an hour hand standing dead on the twelve at
  // half past is the one fault a face can have that nobody misreads as
  // anything else.
  readonly property real hourAngle: (clock.minutes % 720) * 0.5
  readonly property real minuteAngle: (clock.minutes % 60) * 6

  // The sweep hand, and the three registers under it. Seconds, measured
  // seconds and measured minutes all turn at the big minute hand's own six
  // degrees a step, which is why none of them needs a scale printed in it:
  // each is the dial's own hand, one ring down. The hours register goes round
  // twelve times slower, like the hand above it.
  readonly property real sweepAngle: (clock.shown % 60) * 6
  readonly property real secondsAngle: (clock.shownSeconds % 60) * 6
  readonly property real countedAngle: ((clock.shown / 60) % 60) * 6
  readonly property real hoursAngle: ((clock.shown / 3600) % 12) * 30

  // Long, thin, up to the marks; short, thick, well inside them. The pair has
  // to differ in both at once - at a tile's size two hands of one weight are
  // one hand and a shadow, and two of one length are a cross.
  //
  // The minute hand stops **at** the marks rather than on them: the marks run
  // from 10 to 14 of the face's 20, and a hand drawn into that band crosses
  // whichever one it is nearest and takes a bite out of the only ring on the
  // drawing that says what o'clock means.
  readonly property real minuteLength: clock.unit * 10
  readonly property real minuteWeight: clock.unit * 2
  readonly property real hourLength: clock.unit * 7
  readonly property real hourWeight: clock.unit * 3

  // The sweep hand is the longest and the thinnest thing on the face, and it
  // is the one hand drawn *into* the marks: it is read against them one
  // second at a time, where the time of day is read off two hands nowhere
  // near each other. The tail past the pivot is a counterweight, which is
  // what a real one is for and what says at a glance which hand this is even
  // when it is standing under another.
  readonly property real sweepLength: clock.unit * 13
  readonly property real sweepTail: clock.unit * 1.8
  readonly property real sweepWeight: clock.unit * 1.5

  // A register, and how far out its middle sits. 6.4 and 3.3 are one
  // decision: the hour marks begin at 10, so this is the whole of the room
  // between the hub and them, and a register drawn any larger lands its own
  // edge among those marks.
  readonly property real registerOut: clock.unit * 6.4
  readonly property real registerSize: clock.unit * 6.6
  readonly property real registerReach: clock.unit * 2.4
  readonly property real registerWeight: clock.unit * 0.8

  // One counter, sunk into the dial. Everything about it answers to a number,
  // so none of it is drawn art: the disc is `radius: width / 2`, which is
  // what a circle of any size is, and the hand is the rectangle every other
  // hand on this face is.
  component Register: Item {
    id: register

    property real angle: 0
    property real reach: 0
    property real weight: 0
    property color ground: "transparent"
    property color hand: "transparent"

    Rectangle {
      anchors.fill: parent
      radius: width / 2
      color: register.ground
    }

    Item {
      x: register.width / 2
      y: register.height / 2
      width: 0
      height: 0
      rotation: register.angle

      Rectangle {
        x: -register.weight / 2
        y: -register.reach
        width: register.weight
        height: register.reach
        radius: width / 2
        color: register.hand
      }
    }
  }

  Item {
    id: face
    width: clock.side
    height: clock.side
    anchors.centerIn: parent

    BadgeArt {
      anchors.fill: parent
      drawn: clock.art ? clock.art.find("clock", "face") : null
      fill: clock.dim
    }

    BadgeArt {
      anchors.fill: parent
      drawn: clock.art ? clock.art.find("clock", "ticks") : null
      fill: clock.dim
    }

    // Running seconds at nine o'clock, which is the one register that is not
    // the stopwatch's: what it says is that the face is live rather than
    // stopped, which is the whole job it does on a wrist too. Its hand is
    // drawn in the ink the big hands are, because that is what it is - the
    // time, not a measurement.
    Register {
      x: face.width / 2 - clock.registerOut - width / 2
      y: face.height / 2 - height / 2
      width: clock.registerSize
      height: clock.registerSize
      visible: clock.chrono
      angle: clock.secondsAngle
      reach: clock.registerReach
      weight: clock.registerWeight
      ground: clock.wash
      hand: clock.ink
    }

    // The minutes measured, at three. Sixty of them, so its hand is the
    // minute hand's twin and comes back to the top of the register once an
    // hour.
    Register {
      x: face.width / 2 + clock.registerOut - width / 2
      y: face.height / 2 - height / 2
      width: clock.registerSize
      height: clock.registerSize
      visible: clock.chrono
      angle: clock.countedAngle
      reach: clock.registerReach
      weight: clock.registerWeight
      ground: clock.wash
      hand: clock.mark
    }

    // The hours measured, at six. It moves rarely and is drawn anyway: a
    // chronograph with two registers and a gap where the third goes is a
    // chronograph missing a part, and the whole reason to keep the layout a
    // wrist has is that somebody who has seen one knows where to look.
    Register {
      x: face.width / 2 - width / 2
      y: face.height / 2 + clock.registerOut - height / 2
      width: clock.registerSize
      height: clock.registerSize
      visible: clock.chrono
      angle: clock.hoursAngle
      reach: clock.registerReach
      weight: clock.registerWeight
      ground: clock.wash
      hand: clock.mark
    }

    // Each hand hangs off a point rather than off a box. A rectangle rotated
    // about its own centre would have to be positioned by the angle as well
    // as turned by it; a zero-sized item at the middle of the face turns
    // about the one place a hand is pinned, and the rectangle under it is
    // then written as what it is - so wide, so long, and standing up.
    Item {
      x: face.width / 2
      y: face.height / 2
      width: 0
      height: 0
      rotation: clock.hourAngle

      Rectangle {
        x: -clock.hourWeight / 2
        y: -clock.hourLength
        width: clock.hourWeight
        height: clock.hourLength
        // Round because it is round: a hand with square ends reads as a
        // pointer at one size and as a plank at the next.
        radius: width / 2
        color: clock.ink
      }
    }

    Item {
      x: face.width / 2
      y: face.height / 2
      width: 0
      height: 0
      rotation: clock.minuteAngle

      Rectangle {
        x: -clock.minuteWeight / 2
        y: -clock.minuteLength
        width: clock.minuteWeight
        height: clock.minuteLength
        radius: width / 2
        color: clock.ink
      }
    }

    // The sweep hand, over the two that tell the time: it is the hand the
    // press moves, so it is the hand nothing else is allowed to stand in
    // front of.
    Item {
      x: face.width / 2
      y: face.height / 2
      width: 0
      height: 0
      visible: clock.chrono
      rotation: clock.sweepAngle

      Rectangle {
        x: -clock.sweepWeight / 2
        y: -clock.sweepLength
        width: clock.sweepWeight
        height: clock.sweepLength + clock.sweepTail
        radius: width / 2
        color: clock.mark
      }
    }

    // Over all of them, because what it is there for is the corner each one
    // turns at the middle: rounded rectangles crossing at a point leave a
    // notch, and the hub is the drawing that covers it.
    BadgeArt {
      anchors.fill: parent
      drawn: clock.art ? clock.art.find("clock", "hub") : null
      fill: clock.mark
    }
  }
}
