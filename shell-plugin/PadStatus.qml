// omapad's widget in the Omarchy bar.
//
// The only thing omapad puts on screen that nobody summoned. Everything else
// it draws - the keyboard, the menu, the guide, the mapping screen - is asked
// for and then goes away; this is the one standing answer to "is the pad
// mine?", which is worth a slot in the bar Omarchy already owns rather than a
// second bar of ours fighting it for the same screen edge.
//
// A pure view like the rest: the daemon pushes one JSON line per change over
// status.sock and re-sends on a heartbeat, so a shell restart repaints itself
// and a daemon that stops talking takes the widget off the bar with it. Game
// mode is drawn in the bar's own urgent colour rather than a colour of ours,
// because it is the state where a pressed button does nothing on the desktop
// and the bar already has a way of saying "look here".
import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "canerakdas.omapad"

  property bool connected: false
  property string mode: "desktop"
  property string pad: ""
  property string profile: ""
  // Nothing has been heard from the daemon yet. An icon for a service that is
  // not running is worse than a gap, so the widget waits to be told.
  property bool live: false

  readonly property bool game: mode === "game"
  // $XDG_RUNTIME_DIR is per-user and 0700, and that is the only thing
  // keeping another user off this socket. Without it there is nowhere
  // private to bind, so bind nowhere: a socket under /tmp is one anybody
  // on the machine can plant first and read what this surface is sent.
  readonly property string socketDir: Quickshell.env("XDG_RUNTIME_DIR")
    ? Quickshell.env("XDG_RUNTIME_DIR") + "/omapad" : ""

  function applyState(text) {
    try {
      var s = JSON.parse(text)
      if (s.mode !== undefined) root.mode = String(s.mode)
      if (s.connected !== undefined) root.connected = !!s.connected
      if (s.pad !== undefined) root.pad = String(s.pad)
      if (s.profile !== undefined) root.profile = String(s.profile)
      root.live = true
      silence.restart()
    } catch (e) {}
  }

  function summary() {
    var text = pad !== "" ? pad : "No controller"
    text += game ? " · game mode, the pad is the game's" : " · desktop mode"
    if (!game && profile !== "") text += " · " + profile + " profile"
    return text + "\nLeft: menu · Right: switch mode"
  }

  // omapad re-sends its state every couple of seconds, so a longer silence
  // is a daemon that has stopped rather than one with nothing to say.
  Timer {
    id: silence
    interval: 7000
    onTriggered: root.live = false
  }

  SocketServer {
    active: root.socketDir !== ""
    path: root.socketDir + "/status.sock"
    handler: Socket {
      parser: SplitParser {
        splitMarker: "\n"
        onRead: line => root.applyState(line)
      }
    }
  }

  visible: live && connected
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    // A gamepad, and a gamepad handed over.
    text: root.game ? "󰒗" : ""
    active: root.game
    slotSize: Style.bar.statusSlot
    tooltipText: root.summary()
    onPressed: function (which) {
      // The menu is what the pad's own PLUS opens, so the mouse gets the same
      // door; the right button switches modes, which is the one thing you may
      // need precisely when the pad cannot do it for you.
      if (!root.bar) return
      if (which === Qt.RightButton) root.bar.run("omapad ctl mode toggle")
      else root.bar.run("omapad ctl menu toggle")
    }
  }
}
