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
// **Every figure on this face is drawn, and the time only turns them.** The
// rim, the twelve marks, the hub, the two hands, the sweep and both halves of
// a register come out of `ControlArt.qml`, because not one of them is
// parameterised by anything: a hand is the same baton at every hour, drawn
// standing at twelve on the shapes' own canvas, and an angle is a transform
// rather than a shape. What is left as geometry is what genuinely answers to
// a number - how big the register is and where it sits. Same
// split the gauge makes one control along, and the same one `BadgeArt` makes
// between a button and the label set into it.
//
// It is why a redrawn hand is a redrawn *file*: `assets/shapes/` holds every
// line on this tile, so the whole set can be restyled without a line of QML
// moving. A drawing whose box is the face is pinned at the shapes' own 20,20,
// which is where every hand here meets the hub.
//
// **A clock has no second hand.** The daemon re-sends the page every
// `VIEW_HEARTBEAT` seconds, so a hand that moved every second would be a
// drawing that is visibly wrong most of the time - and a tile left over a game
// is the last place to put something that twitches. Two hands say what a sofa
// asks; the head's `%H:%M` is where the exact minute is.
//
// **A chronograph is the same face with one register set into it, and
// everything on it moves.** That is not the paragraph above being broken, it
// is the other side of it: this face is only ever drawn in the menu, which is
// a surface somebody opened and is looking at, and what it is drawn for is
// measuring. A stopwatch whose hands stood still between payloads would be a
// stopwatch that lies twice a second.
//
// So the daemon sends the state - how long it had measured when the line was
// written, and whether it is still going - and this file counts on from there, re-stamping itself every time a
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
// **One register, at six, counting thirty minutes - the Seiko 6139's dial.**
// A line drawing of it with no name printed on it, taken from a reference
// drawing checked against photographs of a 6139-6002: a double hairline
// case, a track in fifths inside it, slim batons in outline with the twelve as
// two bars, a small mark at six under the counter, hands in outline tapering
// to a point, and the one counter the 6139 has, large and low at six. The
// panda dial this replaced had three - running seconds at nine, measured
// minutes at three and hours at six - which at a tile's size was three discs
// crowding a face with five hands on it. What the two that went said, the
// figures under the face say better: the hours measured are printed there,
// and the sweep hand moving is what says the face is live. The 6139's
// day-date window at three stays out, as 84 left it, and a baton stands
// there instead.
//
// The register is an outline rather than a sunk disc. A disc was what made a
// counter read as one on a face drawn in solids; on a face drawn in lines,
// its own ring and its ticks do it, in the dial's own ink.
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
  property real since: 0

  onElapsedChanged: clock.stamp()
  onTickingChanged: clock.stamp()

  function stamp() {
    clock.since = Date.now()
    clock.shown = Math.max(0, clock.elapsed)
  }

  // **Twenty a second while it is measuring, and not at all while it is
  // not.** Twenty is a trade-off rather than a setting - the same kind of
  // number the generator's sampling constants are, because nobody configures
  // a repaint: the tenths digit changes every other tick and the sweep hand
  // moves a third of a degree, which is where both stop being something you
  // can watch happen in steps. Stopped, nothing on the face moves - the
  // running-seconds register that kept it at four a second went with the
  // panda dial - so there is nothing to wake for.
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
    interval: 50
    repeat: true
    running: clock.awake && clock.chrono && clock.ticking
    onTriggered: {
      // Stopped, `shown` stays exactly where the daemon left it, which is the
      // number the tile is being read for - so a stopwatch that is not
      // running has nothing to count and the timer sleeps.
      clock.shown = Math.max(0, clock.elapsed)
        + (Date.now() - clock.since) / 1000
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

  // The sweep hand, and the register under it. The register is the 6139's
  // thirty minutes, so it goes round twice an hour - twelve degrees a minute,
  // with a mark every five of them - and comes back to the top where a
  // measurement's half hour does.
  readonly property real sweepAngle: (clock.shown % 60) * 6
  readonly property real countedAngle: ((clock.shown / 60) % 30) * 12

  // How big the register is and how far below the middle it sits, read off
  // the reference drawing this face is taken from: a counter a little under
  // a third of the case's radius, its middle about half the radius down, so
  // the dial's six is only a small mark at the edge under it. Both are still
  // numbers because both are genuinely parameters - the drawing inside is
  // the same drawing wherever it is put.
  readonly property real registerOut: clock.unit * 10
  readonly property real registerSize: clock.unit * 11.5

  // The counter: a ring with its marks and a hand, drawn on the register's
  // own canvas rather than on the face's. Its 40 is this disc,
  // so a hand here is drawn against the circle it turns in and not against a
  // face six times the size - which is what keeps the register a drawing
  // somebody can open rather than two numbers that happen to look like one.
  //
  // The art is handed in for the reason the clock's own is: `ControlArt`
  // cannot be a singleton from a plugin directory, and a component reaching
  // out of its own scope for an id is what the surfaces have a rule against.
  component Register: Item {
    id: register

    property var art: null
    property real angle: 0
    property color line: "transparent"
    property color hand: "transparent"

    BadgeArt {
      anchors.fill: parent
      drawn: register.art ? register.art.find("clock", "register") : null
      fill: register.line
    }

    BadgeArt {
      anchors.fill: parent
      rotation: register.angle
      drawn: register.art ? register.art.find("clock", "register-hand") : null
      fill: register.hand
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

    // The minutes measured, at six: the 6139's one counter. Its ring and
    // marks are furniture, in the dial's ink; its hand is the measurement,
    // in the accent the sweep is drawn in.
    Register {
      x: face.width / 2 - width / 2
      y: face.height / 2 + clock.registerOut - height / 2
      width: clock.registerSize
      height: clock.registerSize
      visible: clock.chrono
      art: clock.art
      angle: clock.countedAngle
      line: clock.dim
      hand: clock.mark
    }

    // Each hand fills the face and turns about the middle of it. The drawing
    // is pinned where the hub is, so the box a hand is given is the face
    // itself and the angle is the only thing said about it here - a hand
    // positioned by its angle as well as turned by it is the arithmetic this
    // is not doing.
    BadgeArt {
      anchors.fill: parent
      rotation: clock.hourAngle
      drawn: clock.art ? clock.art.find("clock", "hour") : null
      fill: clock.ink
    }

    BadgeArt {
      anchors.fill: parent
      rotation: clock.minuteAngle
      drawn: clock.art ? clock.art.find("clock", "minute") : null
      fill: clock.ink
    }

    // The sweep hand, over the two that tell the time: it is the hand the
    // press moves, so it is the hand nothing else is allowed to stand in
    // front of.
    BadgeArt {
      anchors.fill: parent
      visible: clock.chrono
      rotation: clock.sweepAngle
      drawn: clock.art ? clock.art.find("clock", "sweep") : null
      fill: clock.mark
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
