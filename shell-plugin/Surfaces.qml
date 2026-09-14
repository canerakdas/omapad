// The plugin's panel entry point.
//
// A plugin gets one panel entry point, and omapad draws seven independent
// surfaces - the on-screen keyboard, the controller menu, the bindings guide,
// the mapping screen, the game-mode bar, the readings it leaves on screen and
// the burst a click leaves at the pointer - each fed by its own socket.
// Mounting them here keeps them in one hot-reloading plugin directory instead
// of seven.
//
// The shell's summon/hide/toggle contract lands on `open()`, `close()` and
// `opened` below, so `omarchy-shell shell summon <id>` and an Omarchy keybind
// reach the same surfaces the pad does. Neither function opens a panel itself:
// surface state lives in the daemon, so the shell asks omapad exactly the
// way a terminal would and the answer comes back over the surface's socket.
// Flipping `opened` here instead would draw a keyboard the daemon does not
// know it is showing, and its next heartbeat would take it away again.
import QtQuick
import Quickshell

Item {
  id: root

  Keyboard { id: keyboard }
  Menu { id: menu }
  Guide { id: guide }
  Mapping { id: mapping }
  GameBar {}
  // Neither summonable nor part of `opened`, and for a different reason from
  // the bar's: the readings are a *setting* rather than a surface. There is
  // no `omapad ctl hud open` to summon them with - the verb takes on, off or
  // toggle - and a shell "hide" that took them down would be undoing
  // something somebody chose and wrote down, not closing a screen they
  // opened.
  Hud {}
  // Not summonable and never opened: it answers a click rather than a
  // button, and the daemon speaks to it one burst at a time.
  Ripple {}

  // The surfaces a summon can name, keyed by omapad's own control verb. The
  // game bar is deliberately absent: it follows game mode rather than being
  // summoned, so `omapad ctl mode` is its door. So are the readings, whose
  // door is `omapad ctl hud`.
  readonly property var summonable: ({
    "osk": keyboard,
    "menu": menu,
    "guide": guide,
    "map": mapping
  })

  // What a caller may write in the payload. The verbs are accepted as-is and
  // the longer words alongside them, because a keybind is written by hand and
  // "keyboard" is the obvious name for what the shell calls osk.
  readonly property var surfaceNames: ({
    "osk": "osk",
    "keyboard": "osk",
    "menu": "menu",
    "guide": "guide",
    "map": "map",
    "mapping": "map"
  })

  // A summon with no payload means the menu: it is the door the pad's own
  // button opens, and the one surface that leads to all the others.
  readonly property string defaultSurface: "menu"

  // The shell reads this to decide whether a toggle should summon or hide.
  readonly property bool opened: keyboard.opened || menu.opened || guide.opened
    || mapping.opened

  function ask(verb, command) {
    Quickshell.execDetached(["omapad", "ctl", verb, command])
  }

  function open(payloadJson) {
    var name = root.defaultSurface
    try {
      var payload = JSON.parse(payloadJson || "{}")
      if (payload && payload.surface !== undefined) name = String(payload.surface)
    } catch (e) {}
    var verb = root.surfaceNames[name]
    if (!verb) {
      console.warn("omapad: summon names no surface: " + name)
      return
    }
    root.ask(verb, "open")
  }

  function close() {
    // Only what is actually up: a close for a surface the daemon already has
    // shut is harmless, but it would also be a spawned process per surface
    // every time the shell tears its panels down.
    for (var verb in root.summonable)
      if (root.summonable[verb].opened) root.ask(verb, "close")
  }
}
