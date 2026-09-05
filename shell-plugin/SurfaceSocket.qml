// One surface's socket, and the retry that makes the start order stop
// mattering.
//
// The plugin listens and the daemon connects, so the directory the sockets
// live in - $XDG_RUNTIME_DIR/omapad - is the daemon's to create, and at login
// the shell is usually up first: Hyprland execs it the moment the compositor
// is there, while omapad.service is still starting Python. Binding into a
// directory that is not there yet fails once and quietly: Quickshell drops
// `active` to false and never tries again, so every surface in the plugin
// would sit dead for the whole session, with one warning in a log nobody is
// reading. It is the bug a fresh boot has and a rescanPlugins hides, because
// by the second bind the daemon has long since made the directory.
//
// The daemon reconnects on its own heartbeat. This is the same promise from
// the listening side, and it is what lets every panel say that the shell and
// the daemon can start in either order.
import QtQuick
import Quickshell.Io

Item {
  id: root

  // The daemon's socket name, not the panel's: Keyboard.qml listens on
  // osk.sock. Empty until there is a private directory to bind in.
  property string dir: ""
  property string name: ""

  // One line of JSON off the socket, for the panel's applyState.
  signal line(string text)

  readonly property bool listening: server.active

  // Doubling, from a wait short enough to catch a daemon a second behind up
  // to one that costs the shell's log a line a minute on a machine where
  // omapad is not running at all.
  readonly property int firstWait: 250
  readonly property int lastWait: 60000
  property int wait: firstWait

  SocketServer {
    id: server
    active: root.dir !== "" && root.name !== ""
    path: root.dir + "/" + root.name
    handler: Socket {
      parser: SplitParser {
        splitMarker: "\n"
        onRead: text => root.line(text)
      }
    }
    onActiveStatusChanged: {
      if (server.active) root.wait = root.firstWait
      else if (root.dir !== "") retry.restart()
    }
  }

  Timer {
    id: retry
    interval: root.wait
    repeat: false
    onTriggered: {
      if (server.active || root.dir === "") return
      root.wait = Math.min(root.wait * 2, root.lastWait)
      // A directory that is still not there fails the same way, which is
      // what re-arms this timer.
      server.active = true
    }
  }
}
