// The files, loaded and ready to fire.
//
// Kept apart from `Sound.qml` for one reason: the `import QtMultimedia` below.
// Quickshell does not depend on qt6-multimedia, a QML import that cannot be
// resolved takes its entire file down with it, and this program is installed
// as a plugin on machines nobody here has seen. So the import is quarantined
// in the smallest file that can hold it, and `Sound.qml` reaches it through a
// `Loader`: without the package this file fails to load and every other
// surface in the plugin carries on.
//
// `SoundEffect` rather than `MediaPlayer`, which is the whole reason a cue
// can be answered at all: it decodes the file once when the source is set and
// keeps the samples, so firing it is a memory read rather than a decode. A
// `MediaPlayer` opens a pipeline per play and arrives tens of milliseconds
// after the button - by which time the thumb has moved on and the sound is
// answering the wrong press.
import QtQuick
import QtMultimedia

Item {
  id: root

  // Where the files come from (`[sound] pack`). Empty is the set beside the
  // plugin, written by `assets/sounds.py`.
  property string dir: ""

  // The closed list, and it is the daemon's `sound.VOICES` in the same order.
  // A new word is four things rather than one: a file here, a name there,
  // a `say()` at the moment it happens, and a test.
  readonly property var voices: ["move", "prev", "next", "show", "back", "tick", "edge", "commit"]

  // A pack is a directory of files; the shipped set is beside this file. Both
  // end up as URLs, which is what a `SoundEffect` takes.
  function urlFor(name) {
    if (root.dir.length > 0)
      return "file://" + root.dir + "/" + name + ".wav"
    return Qt.resolvedUrl("../assets/sounds/" + name + ".wav")
  }

  function shippedFor(name) {
    return Qt.resolvedUrl("../assets/sounds/" + name + ".wav")
  }

  function say(name, gain) {
    var effect = root.effects[name]
    if (effect === undefined || effect.status !== SoundEffect.Ready)
      return
    // Set per cue rather than bound: the volume arrives on the same line the
    // cue does, and a binding would set it on all of them for a press that
    // sounds one.
    effect.volume = gain
    // `play()` rather than `restart()`: two presses a frame apart should
    // overlap the way two keys on an instrument do, not cut each other off.
    effect.play()
  }

  // Built rather than written out once per voice, because every one of them
  // is the same four lines and the list above is already the authority on
  // what they are called. The fallback is what makes a pack of one file worth
  // writing: a name the pack does not hold fails to load and is replaced by
  // the shipped one, so the rest of the cues are still the pack's.
  readonly property var effects: ({})

  Instantiator {
    model: root.voices
    delegate: SoundEffect {
      required property string modelData
      source: root.urlFor(modelData)
      onStatusChanged: {
        if (status === SoundEffect.Error
            && source != root.shippedFor(modelData))
          source = root.shippedFor(modelData)
      }
    }
    onObjectAdded: (index, object) => {
      root.effects[root.voices[index]] = object
    }
    onObjectRemoved: (index, object) => {
      delete root.effects[root.voices[index]]
    }
  }
}
