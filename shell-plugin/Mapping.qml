// Controller mapping for omapad.
//
// A pure view, like the other three: omapad walks the printed button names,
// reads the pad raw and decides what has been learned, skipped or is still
// being asked for. One JSON line per update arrives over a unix socket and
// this panel draws it.
//
// The surface is shaped around the one thing it has to say - *press this
// button now* - so the asked-for name is the largest thing on screen and the
// list underneath is a progress report you glance at rather than read. That
// order matters here more than on the other surfaces: eyes are on the pad, not
// the screen, and what the screen has to survive is being seen in the corner
// of one.
//
// The escapes are printed on every step because none of them can be inferred
// from a pad whose map is exactly what is in doubt.
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons
import qs.Ui

Item {
  id: root

  property bool opened: false
  property string step: ""
  // What the pad in hand prints on that step, and the shape it is printed on.
  // The daemon answers both, out of the layout in force: `step` is the name
  // the mapping is written under, `label` is the one on the plastic.
  property string label: ""
  property string kind: "face"
  // The three names the confirmation is answered in, learned a moment ago.
  property var keys: ({})
  property string prompt: ""
  property bool optional: false
  property bool confirm: false
  property string note: ""
  property string pad: ""
  property int index: 0
  property int count: 0
  property var rows: []

  // $XDG_RUNTIME_DIR is per-user and 0700, and that is the only thing
  // keeping another user off this socket. Without it there is nowhere
  // private to bind, so bind nowhere: a socket under /tmp is one anybody
  // on the machine can plant first and read what this surface is sent.
  readonly property string socketDir: Quickshell.env("XDG_RUNTIME_DIR")
    ? Quickshell.env("XDG_RUNTIME_DIR") + "/omapad" : ""

  // How big this surface draws, from the daemon: the desktop is read at a
  // keyboard and game mode from a sofa, so the scale follows the mode rather
  // than the session. Every measurement below goes through `metrics`.
  property real uiScale: 1.0
  // Which of the two ways a badge is drawn (`[ui] badge_style`). A payload
  // field rather than a shell constant: the panel cannot read the config, and
  // the answer changes from the menu while the surface is up.
  property string badgeStyle: "filled"
  readonly property bool stencil: root.badgeStyle === "stencil"

  Metrics {
    id: metrics
    scale: root.uiScale
  }

  // Same measurements as the menu and the guide, so all four read as one.
  readonly property int contentMargin: metrics.spacing.panelPadding
  readonly property int contentSpacing: metrics.spacing.md
  readonly property int chipUnit: metrics.badge(
    Math.max(metrics.space(26), metrics.font.body + metrics.space(10)))

  // What the pad prints on one of the three buttons the confirmation takes,
  // falling back to the logical name until the daemon has said.
  function keyName(which, fallback) {
    return (root.keys && root.keys[which]) ? root.keys[which] : fallback
  }

  // omapad re-sends the whole payload every VIEW_HEARTBEAT seconds, so a
  // restarted shell repaints itself with no handshake - which means most
  // lines that arrive here say nothing new. Re-applying one is not free: a
  // `var` property never compares equal to its old value, so assigning it
  // re-runs every binding that reads it, and where it is a Repeater's model
  // it destroys and rebuilds every delegate under it. A fresh component's
  // `lastLine` is empty, so a restarted shell still paints what it is given.
  property string lastLine: ""
  // The same argument one field at a time, for the strip a finished
  // step leaves alone.
  // The daemon sends the whole surface on every change, and most of it is
  // the same surface.
  property var seen: ({})

  function fresh(key, value) {
    var line = JSON.stringify(value)
    if (line === root.seen[key]) return false
    root.seen[key] = line
    return true
  }

  function applyState(text) {
    if (text === root.lastLine) return
    root.lastLine = text
    try {
      var s = JSON.parse(text)
      // First, so a scale change lands even if a later field throws.
      if (s.scale !== undefined) root.uiScale = Number(s.scale) || 1
      if (s.badge !== undefined) root.badgeStyle = String(s.badge)
      // `root.` on every one of these: a bare name resolves against the whole
      // QML scope chain and can land on something read-only, and the throw
      // that follows takes every assignment after it with it.
      if (s.step !== undefined) root.step = s.step
      if (s.label !== undefined) root.label = s.label
      if (s.kind !== undefined) root.kind = s.kind
      if (s.keys !== undefined) root.keys = s.keys
      if (s.prompt !== undefined) root.prompt = s.prompt
      if (s.optional !== undefined) root.optional = !!s.optional
      if (s.confirm !== undefined) root.confirm = !!s.confirm
      if (s.note !== undefined) root.note = s.note
      if (s.pad !== undefined) root.pad = s.pad
      if (s.index !== undefined) root.index = s.index
      if (s.count !== undefined) root.count = s.count
      if (s.rows !== undefined && root.fresh("rows", s.rows))
        root.rows = s.rows
      if (s.open !== undefined) root.opened = !!s.open
    } catch (e) {}
  }

  // omapad connects here and streams state; it reconnects on its own, so the
  // shell and the daemon can restart in either order.
  SocketServer {
    active: root.socketDir !== ""
    path: root.socketDir + "/mapping.sock"
    handler: Socket {
      parser: SplitParser {
        splitMarker: "\n"
        onRead: line => root.applyState(line)
      }
    }
  }

  IpcHandler {
    target: "omapad-mapping"
    function state(): string { return root.opened ? "open" : "closed" }
    function socket(): string { return root.socketDir + "/mapping.sock" }
    function ping(): string { return "ok" }
  }

  ButtonArt {
    id: buttonArt
  }

  // The button being asked for, drawn as the button it is. A name is what a
  // mapping is written under, but a shape is what you find under a thumb
  // without looking - and looking is what this screen cannot ask for, because
  // the eyes are on the pad.
  component Badge: Item {
    id: badge

    property string label: ""
    property string kind: "face"
    property int unit: root.chipUnit

    readonly property var drawn: buttonArt.find(badge.kind, badge.label)
    readonly property var bare: buttonArt.shape(badge.kind, badge.label)
    readonly property var art: badge.drawn !== null ? badge.drawn : badge.bare
    readonly property bool wide: kind === "bumper" || kind === "trigger" || kind === "system"

    implicitWidth: badge.art !== null
      ? Math.round(unit * badge.art.w / badge.art.h)
      : (wide ? Math.round(unit * 1.6) : unit)
    implicitHeight: unit
    width: implicitWidth
    height: implicitHeight

    BadgeArt {
      anchors.fill: parent
      drawn: badge.art
      // The accent, not the text colour the guide fills a badge with: this
      // one is an instruction rather than a legend, and it is the only thing
      // on the screen worth looking up for.
      // Stencil says the same thing louder: the accent solid with the
      // button punched out of it. The outline goes with it - a line around a
      // shape already at full strength draws nothing but a seam.
      fill: root.stencil ? Color.accent : Util.alpha(Color.accent, 0.22)
      stroke: root.stencil ? "transparent" : Util.alpha(Color.accent, 0.55)
      strokeWidth: Math.max(1, metrics.space(2))
      ink: root.stencil ? "transparent" : Color.accent
      knockout: root.stencil
      ringColor: root.stencil
        ? Color.menu.background : Util.alpha(Color.accent, 0.65)
      ringWidth: Math.max(1, metrics.space(2))
    }

    // Only where the drawing carries no label of its own - the system pill,
    // and any name no pad here prints.
    Text {
      visible: badge.drawn === null
      width: badge.width - metrics.space(10)
      height: Math.ceil(implicitHeight)
      x: Math.round((badge.width - contentWidth) / 2)
      y: Math.round((badge.height - height) / 2)
      text: badge.label
      color: Color.accent
      font.family: buttonArt.family
      font.pixelSize: Math.round(badge.unit * 0.4)
      fontSizeMode: Text.HorizontalFit
      minimumPixelSize: Math.max(8, metrics.font.caption)
      font.weight: Font.Medium
      horizontalAlignment: Text.AlignHCenter
    }
  }

  // One button in the progress strip: its printed name, and how far it has
  // got. Filled is learned, outlined is being asked for now, faint is still to
  // come, struck through is one this pad does not have.
  component Chip: Rectangle {
    id: chip

    property string name: ""
    property string state: "waiting"

    readonly property bool asking: state === "asking"
    readonly property bool done: state === "done"
    readonly property bool skipped: state === "skipped"

    implicitWidth: Math.ceil(Math.max(root.chipUnit,
                                      label.implicitWidth + metrics.space(14)))
    implicitHeight: root.chipUnit
    radius: height / 2
    color: chip.done ? Util.alpha(Color.accent, 0.18) : "transparent"
    border.width: chip.asking ? Math.max(1, metrics.space(2)) : Math.max(1, metrics.space(1))
    border.color: chip.asking
      ? Color.accent
      : Util.alpha(Color.menu.text, chip.done ? 0.22 : 0.12)

    Text {
      id: label
      anchors.centerIn: parent
      text: chip.name
      color: chip.asking ? Color.accent : Color.menu.text
      opacity: chip.skipped ? 0.3 : (chip.done ? 0.85 : 0.45)
      font.family: metrics.font.family
      font.pixelSize: metrics.font.caption
      font.weight: chip.asking ? Font.Medium : Font.Normal
      font.strikeout: chip.skipped
    }
  }

  PanelWindow {
    id: panel
    visible: root.opened
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    WlrLayershell.namespace: "omapad-mapping"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    exclusionMode: ExclusionMode.Ignore
    mask: Region {}

    Rectangle {
      anchors.fill: parent
      color: Color.menu.scrim
      opacity: root.opened ? 1 : 0
      Behavior on opacity { NumberAnimation { duration: 110 } }
    }

    BorderSurface {
      id: card
      anchors.centerIn: parent
      width: Math.min(metrics.space(560), parent.width - Style.gapsOut * 2)
      height: Math.min(
        card.borderTop + card.borderBottom + root.contentMargin * 2 + content.height,
        parent.height - Style.gapsOut * 2)
      color: Color.menu.background
      borderSpec: Border.surfaceSpec("menu", "border", Color.menu.border,
        Math.max(1, metrics.space(2)))
      radius: Style.cornerRadius
      opacity: root.opened ? 1 : 0
      Behavior on opacity { NumberAnimation { duration: 110 } }
      clip: true

      Column {
        id: content
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.topMargin: card.borderTop + root.contentMargin
        anchors.leftMargin: card.borderLeft + root.contentMargin
        anchors.rightMargin: card.borderRight + root.contentMargin
        spacing: root.contentSpacing

        Item {
          width: parent.width
          height: Math.ceil(Math.max(heading.implicitHeight, progress.implicitHeight))

          Text {
            id: heading
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            text: "Map the controller"
            color: Color.menu.text
            font.family: metrics.font.family
            font.pixelSize: metrics.font.heading
            font.weight: Font.Medium
          }

          Text {
            id: progress
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            text: root.confirm ? "done" : (root.index + 1) + " / " + root.count
            color: Color.menu.text
            opacity: 0.5
            font.family: metrics.font.family
            font.pixelSize: metrics.font.bodySmall
          }
        }

        Text {
          width: parent.width
          visible: root.pad.length > 0
          text: visible ? root.pad : ""
          color: Color.menu.text
          opacity: 0.45
          font.family: metrics.font.family
          font.pixelSize: metrics.font.caption
          elide: Text.ElideRight
        }

        Item { width: 1; height: metrics.space(6) }

        // The whole point of the screen, and sized like it.
        Column {
          width: parent.width
          spacing: metrics.space(6)

          Text {
            width: parent.width
            text: root.confirm ? "Save this mapping?" : "Press"
            color: Color.menu.text
            opacity: 0.55
            font.family: metrics.font.family
            font.pixelSize: metrics.font.body
            horizontalAlignment: Text.AlignHCenter
          }

          Item {
            width: parent.width
            height: asked.visible ? asked.height : 0

            Badge {
              id: asked
              visible: !root.confirm && root.label.length > 0
              label: root.label
              kind: root.kind
              // As big as the card can carry: this is the whole message, and
              // it is read out of the corner of an eye that is on the pad. A
              // face button is the narrowest shape here, so the height is
              // what it is sized by and a shoulder simply comes out wider.
              unit: metrics.badge(metrics.font.title * 4)
              x: Math.round((parent.width - width) / 2)
            }
          }

          Text {
            width: parent.width
            visible: !root.confirm && root.prompt.length > 0 && root.prompt !== root.label
            text: visible ? root.prompt : ""
            color: Color.menu.text
            opacity: 0.6
            font.family: metrics.font.family
            font.pixelSize: metrics.font.bodySmall
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
          }

          Text {
            width: parent.width
            visible: root.confirm
            // In the names just learned, and printed as them: on a pad whose
            // face buttons are shapes, "A saves it" names nothing you are
            // holding.
            text: visible
              ? (root.keyName("save", "A") + " saves it · "
                 + root.keyName("discard", "B") + " discards it · "
                 + root.keyName("restart", "X") + " starts over — "
                 + "in the names just learned")
              : ""
            color: Color.menu.text
            opacity: 0.7
            font.family: metrics.font.family
            font.pixelSize: metrics.font.body
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
          }
        }

        Text {
          width: parent.width
          visible: root.note.length > 0
          text: visible ? root.note : ""
          color: Color.accent
          opacity: 0.8
          font.family: metrics.font.family
          font.pixelSize: metrics.font.caption
          horizontalAlignment: Text.AlignHCenter
          elide: Text.ElideRight
        }

        Item { width: 1; height: metrics.space(4) }

        Flow {
          width: parent.width
          spacing: metrics.space(6)

          Repeater {
            model: root.rows
            delegate: Chip {
              required property var modelData
              // Printed, not logical: the strip is a picture of the pad.
              name: modelData.b ? modelData.b : modelData.n
              state: modelData.s
            }
          }
        }

        Item { width: 1; height: metrics.space(6) }

        Rectangle {
          width: parent.width
          height: Math.max(1, metrics.space(1))
          color: Util.alpha(Color.menu.text, 0.12)
        }

        // Printed on every step on purpose: none of these can be worked out by
        // pressing buttons on a pad whose map is the thing being fixed.
        Text {
          width: parent.width
          text: root.optional
            ? "This pad may not have one — press a button you have already named to skip it. Hold anything for 2.5s to leave."
            : "A button you have already named skips this one. Hold anything for 2.5s to leave without saving."
          color: Color.menu.text
          opacity: 0.5
          font.family: metrics.font.family
          font.pixelSize: metrics.font.caption
          wrapMode: Text.WordWrap
        }
      }
    }
  }

  // Pressing pad buttons at a screen that reads them raw produces no Wayland
  // input at all, so the compositor would happily lock underneath it. Same
  // inhibitor the other three bind.
  IdleInhibitor {
    window: panel
    enabled: root.opened
  }
}
