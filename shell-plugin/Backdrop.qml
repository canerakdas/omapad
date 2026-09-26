// The dimmed screen the menu and the quick menu trade between them.
//
// HOME and PLUS swap the two in one place, and they are separate layer-shell
// windows dimming the screen by the same amount. Shut one and open the other
// and there are frames with neither scrim up - the desktop shows through
// between two dark screens (decision 98). So:
//
// - arriving, the scrim is up at once and does not fade in - there is a
//   backdrop on screen already, and this is taking it over;
// - leaving, the scrim stays up until the other window is on screen and a
//   fade longer, then fades out, and the window stays until it has.
//
// **Neither end of the hold can be read off the other window.** A window
// reported visible has been shown, not drawn: its first buffer reaches the
// glass a few frames later, and a leaving scrim that let go two frames after
// the report still left the desktop showing between the two. So the hold
// runs a whole fade past the report, and ends in a fade rather than a snap:
// where the compositor stacks the leaving window on top, what arrives is
// under its scrim for that while, and a scrim lifting slowly off the page
// reads as the page arriving, where one snapping off reads as a flash. The
// overlap is two scrims deep, a shade darker, and nobody sees it.
//
// A panel binds `opened` and `partner`, calls `turn(open, swap)` on every
// line **before** it assigns `open`, draws its scrim from `up` and its window
// from `mapped`, and fades the scrim except while it is arriving on a swap.
// Both ordering rules were learned on the glass: a binding on `opened`
// re-runs before any handler of the same change does, so a hold set in
// `onOpenedChanged` came after the window had been told to go - Quickshell
// tears the surface down on the spot, and the menu vanished whole before the
// row was there - and a fade flag set in that handler came a change too late,
// so the arriving scrim faded in from nothing.
import QtQuick

Item {
  id: root

  property bool opened: false
  // Whether the other surface's window is on screen, wired in Surfaces.qml.
  property bool partner: false
  // The panel's own fade, which is also how long the hold outlasts the
  // other window showing.
  property int fade: 0

  property bool holding: false
  property bool lingering: false

  readonly property bool up: root.opened || root.holding
  readonly property bool mapped: root.opened || root.holding || root.lingering

  // Called with the line's `open` and `swap` before the panel assigns
  // `open`, so a window that is handing over never sees `mapped` go false.
  function turn(open, swap) {
    if (open === root.opened) return
    var leaving = !open && swap
    root.holding = leaving
    root.lingering = leaving
    release.stop()
    linger.stop()
    cap.stop()
    if (leaving) {
      cap.restart()
      if (root.partner) release.restart()
    }
  }

  function letGo() {
    if (!root.holding) return
    release.stop()
    cap.stop()
    root.holding = false
    linger.restart()
  }

  onPartnerChanged: {
    if (root.holding && root.partner) release.restart()
  }

  // A fade past the other window showing, and never less than three frames:
  // with `[ui] motion` at 0 there is no fade, and the gap between a window
  // shown and a window drawn is still there. Not a setting - it is the
  // Wayland hazard rather than a taste.
  Timer {
    id: release
    interval: Math.max(root.fade, 50)
    onTriggered: root.letGo()
  }

  // The scrim's fade out, and a frame over, before the window goes.
  Timer {
    id: linger
    interval: root.fade + 17
    onTriggered: root.lingering = false
  }

  // And a ceiling, for the hand-over whose other half never draws - a panel
  // that failed to load, a shell half restarted. Not a setting either.
  Timer {
    id: cap
    interval: 600
    onTriggered: root.letGo()
  }
}
