// What a press sounds like.
//
// The pad answers a press two ways already and both have a hole in them. The
// screen is answered by looking at it, which is the one thing somebody
// walking a menu by thumb is not always doing; the motor is in the hands, so
// it says nothing while the pad is resting on a knee and nothing at all on a
// pad that has none. This is the third answer, and it is the one the room
// hears.
//
// **The surface that draws nothing.** No window, no layer, no exclusion zone,
// no input region - there is nothing here to see, so there is nothing here
// for a compositor to place. It is mounted in `Surfaces.qml` like the rest
// because it is a socket the daemon streams to, and that is the whole of what
// makes it a surface.
//
// An event rather than a state, `Ripple.qml`'s shape for `Ripple.qml`'s
// reasons: the daemon sends one line per cue, `n` is assigned last and is
// what fires it, and a line carrying a number already played is a duplicate
// rather than a second press. There is no heartbeat behind this socket, so
// every line carries the volume and the directory as well - a panel that had
// missed the one line saying the volume would play at the wrong one until the
// next restart.
//
// **The bank is loaded rather than imported**, and that is the one structural
// thing in this file. Playing a sound needs QtMultimedia, which Quickshell
// does not depend on; a failed import takes its whole file down, so the
// import lives in `SoundBank.qml` behind a `Loader`. On a machine without
// `qt6-multimedia` the loader reports an error, this panel keeps parsing its
// socket, and every other surface in the plugin is untouched. A desktop
// losing its click is not a desktop losing its keyboard.
import QtQuick
import Quickshell
import Quickshell.Io

Item {
  id: root

  // The cue. `n` is a counter the daemon increments per press, never 0, so a
  // shell connecting mid-session does not announce a press that happened
  // before it came up.
  property int seq: 0
  property string cue: "move"
  // How loud, from the daemon (`[sound] volume`): the panel cannot read the
  // config, and this changes from the menu while a page is being walked.
  property real gain: 0.6
  // Where the files are (`[sound] pack`). Empty is the set that ships
  // beside the plugin.
  property string dir: ""

  // $XDG_RUNTIME_DIR is per-user and 0700, and that is the only thing
  // keeping another user off this socket. Without it there is nowhere
  // private to bind, so bind nowhere: a socket under /tmp is one anybody
  // on the machine can plant first and read what this surface is sent.
  readonly property string socketDir: Quickshell.env("XDG_RUNTIME_DIR")
    ? Quickshell.env("XDG_RUNTIME_DIR") + "/omapad" : ""

  readonly property bool ready: bank.status === Loader.Ready
    && bank.item !== null

  Loader {
    id: bank
    source: "SoundBank.qml"
    // Asynchronous so that decoding the files cannot hold up the frame the
    // shell is drawing when the plugin loads. Nothing waits on it: a cue
    // that arrives before the bank is ready is dropped, and the cue after it
    // is a fiftieth of a second later.
    asynchronous: true
    onStatusChanged: {
      if (bank.status === Loader.Error)
        console.warn("omapad: no sound - " + bank.sourceComponent)
    }
  }

  Binding {
    target: bank.item
    property: "dir"
    value: root.dir
    when: root.ready
  }

  onSeqChanged: {
    if (root.seq <= 0 || !root.ready)
      return
    bank.item.say(root.cue, root.gain)
  }

  function applyState(text) {
    try {
      var s = JSON.parse(text)
      if (s.gain !== undefined)
        root.gain = Math.max(0, Math.min(1, Number(s.gain)))
      if (s.dir !== undefined) root.dir = String(s.dir)
      if (s.c !== undefined) root.cue = String(s.c)
      // Last: it is what fires the cue, and what the cue is drawn from has
      // to be in place before it does.
      if (s.n !== undefined) root.seq = Number(s.n) || 0
    } catch (e) {}
  }

  // omapad connects here and streams cues; both ends keep trying, so the
  // shell and the daemon can start or restart in either order.
  SurfaceSocket {
    dir: root.socketDir
    name: "sound.sock"
    onLine: text => root.applyState(text)
  }

  IpcHandler {
    target: "omapad-sound"
    // The question when nothing is coming out of the speakers, and the one
    // this panel can answer that a log cannot: whether it has a bank at all.
    function state(): string {
      return root.ready ? "ready"
        : (bank.status === Loader.Error ? "no QtMultimedia" : "loading")
    }
    function cue(): string { return root.seq + " " + root.cue }
    function socket(): string { return root.socketDir + "/sound.sock" }
    function ping(): string { return "ok" }
  }
}
