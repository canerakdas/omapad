// On-screen keyboard for controller navigation.
//
// This panel is a pure view. omapad owns the layout, the selection and the
// modifier state, and types through its own uinput keyboard, so a key press
// costs no round trip to the shell: by the time this panel repaints, the
// character has already been typed. State arrives as one JSON line per update
// over a unix socket.
//
// The surface never takes keyboard focus and carries an empty input region, so
// the application being typed into keeps focus and the keyboard never swallows
// a click meant for the window underneath.
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons
import qs.Ui

Item {
  id: root

  property bool opened: false
  property var rows: []
  property int selRow: 0
  property int selCol: 0
  property bool shift: false
  property bool ctrl: false
  property bool alt: false
  property bool caps: false
  property string hint: ""
  // Where a key's button badge sits: "right" against the key's own edge, so
  // they line up down the keyboard, or "label" beside the character.
  property string badgeAlign: "right"

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

  // The drawn controller buttons, and the font their labels are set in. The
  // guide draws these big enough to read as buttons; here they are a footnote
  // in the corner of a key, which is the whole point - the keyboard says which
  // button gets to a key without ever being read as a second row of keys.
  ButtonArt {
    id: buttonArt
  }

  readonly property int keyHeight: metrics.space(48)
  readonly property int keyGap: metrics.space(6)
  readonly property int pad: metrics.space(12)
  // Twelve columns stretched across a wide monitor gives very flat keys and a
  // lot of pointless travel between them, so the panel stops growing past this
  // and centres instead. Widened with the grid so a key keeps its old size.
  readonly property int maxWidth: metrics.space(1200)
  // A third of a key. The badge sits on the label's own line, so it only has
  // to be big enough to be recognised out of the corner of an eye - what the
  // key types is the thing actually being read, and a badge that stands as
  // tall as the character competes with it.
  readonly property int badgeUnit: metrics.badge(
    Math.max(metrics.space(12), Math.round(keyHeight * 0.34)))

  // A typed badge label is centred by its line box, and the line box is not
  // centred on the capitals inside it. Measured rather than typed in, the same
  // way the guide measures it - see Guide.qml for why. Positive moves the
  // label down; only the typed fallback needs it, since a drawn label was
  // placed by the shape it sits in.
  Text {
    id: capProbe
    visible: false
    text: "H"
    font.family: buttonArt.family
    font.pixelSize: Math.max(6, Math.round(root.badgeUnit * buttonArt.capSize))
    font.weight: Font.Medium
  }
  TextMetrics {
    id: capInk
    font: capProbe.font
    text: capProbe.text
  }
  readonly property int capNudge: Math.round(capProbe.height / 2 - capProbe.baselineOffset
    - (capInk.tightBoundingRect.y + capInk.tightBoundingRect.height / 2))

  // The pad button that reaches one key, drawn as the button it is. Same
  // machinery the guide badges a binding with, at a size that fits in a
  // corner: omapad sends the label and the kind, ButtonArt has the shape,
  // and the colours come from the key underneath so the badge inverts with it
  // when the selection lands.
  component KeyBadge: Item {
    id: badge

    property string label: ""
    property string kind: "face"
    property color ink: "white"
    property color fill: "transparent"

    // The system pill is drawn inside a box with air around it - 24 units of
    // pill in 40 of art, where a face button fills its box edge to edge - so
    // at one size for every kind it comes out half the height of the others.
    // The guide can afford that at reading size; a badge this small cannot,
    // so the system kind is given back the padding baked into its drawing.
    readonly property int unit: kind === "system"
      ? metrics.badge(root.badgeUnit * 1.4) : root.badgeUnit
    readonly property var drawn: buttonArt.find(badge.kind, badge.label)
    readonly property var bare: buttonArt.shape(badge.kind, badge.label)
    readonly property var art: badge.drawn !== null ? badge.drawn : badge.bare
    // Only for a kind ButtonArt has never heard of - the daemon sends none,
    // but a badge that is only text still needs a box to be centred in.
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
      // Stencil turns the key's two colours around: the badge is solid in
      // the ink and the label is the hole, so what shows through the letter
      // is the key itself - including the moment the selection lands and the
      // key inverts under the badge.
      fill: root.stencil ? badge.ink : badge.fill
      ink: root.stencil ? "transparent" : badge.ink
      knockout: root.stencil
      ringColor: root.stencil ? badge.fill : badge.ink
      ringWidth: Math.max(1, metrics.space(1))
    }

    // Typed only where the drawing carries no label of its own: the system
    // buttons are one pill until a word goes into it, and a remapped pad can
    // print something no shape here was generated for.
    Text {
      visible: badge.drawn === null
      // On whole pixels rather than centred by anchors: at this size a text
      // item that lands on a half pixel is the one blur antialiasing cannot
      // help.
      width: badge.width - metrics.space(4)
      height: Math.ceil(implicitHeight)
      x: Math.round((badge.width - contentWidth) / 2)
      y: Math.round((badge.height - height) / 2) + root.capNudge
      text: badge.label
      color: root.stencil ? badge.fill : badge.ink
      font.family: buttonArt.family
      font.pixelSize: Math.max(6, Math.round(badge.unit * buttonArt.capSize))
      fontSizeMode: Text.HorizontalFit
      minimumPixelSize: 6
      font.weight: Font.Medium
    }
  }

  // omapad re-sends the whole payload every VIEW_HEARTBEAT seconds, so a
  // restarted shell repaints itself with no handshake - which means most
  // lines that arrive here say nothing new. Re-applying one is not free: a
  // `var` property never compares equal to its old value, so assigning it
  // re-runs every binding that reads it, and where it is a Repeater's model
  // it destroys and rebuilds every delegate under it. A fresh component's
  // `lastLine` is empty, so a restarted shell still paints what it is given.
  property string lastLine: ""
  // The same argument one field at a time, for the grid a selection
  // move leaves alone.
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
      if (s.rows !== undefined && root.fresh("rows", s.rows))
        root.rows = s.rows
      if (s.sel !== undefined) { root.selRow = s.sel[0]; root.selCol = s.sel[1] }
      if (s.mods !== undefined) {
        root.shift = !!s.mods.shift
        root.ctrl = !!s.mods.ctrl
        root.alt = !!s.mods.alt
        root.caps = !!s.mods.caps
      }
      if (s.hint !== undefined) root.hint = s.hint
      if (s.balign !== undefined) root.badgeAlign = s.balign
      if (s.open !== undefined) root.opened = !!s.open
    } catch (e) {}
  }

  // omapad connects here and streams state; it reconnects on its own, so the
  // shell and the daemon can restart in either order.
  SocketServer {
    active: root.socketDir !== ""
    path: root.socketDir + "/osk.sock"
    handler: Socket {
      parser: SplitParser {
        splitMarker: "\n"
        onRead: line => root.applyState(line)
      }
    }
  }

  // Kept so the keyboard can also be summoned or inspected without the daemon.
  IpcHandler {
    target: "omapad-osk"
    function open(): string { root.opened = true; return "ok" }
    function close(): string { root.opened = false; return "ok" }
    function state(): string { return root.opened ? "open" : "closed" }
    function socket(): string { return root.socketDir + "/osk.sock" }
    function ping(): string { return "ok" }
  }

  PanelWindow {
    id: panel
    visible: root.opened
    anchors { bottom: true; left: true; right: true }
    // The card sizes itself; the window only needs to be tall enough to hold
    // it plus the gap it keeps from the screen edge.
    implicitHeight: card.height + Style.gapsOut * 2
    color: "transparent"
    WlrLayershell.namespace: "omapad-osk"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    // The keyboard must not cover the window being typed into, so it reserves
    // its own strip at the bottom of the screen and lets Hyprland shrink the
    // tiled windows into what is left. The zone is the card's real extent
    // (its height plus the margin it keeps from the screen edge), not the
    // window's, so the compositor's own gaps_out is not counted twice.
    exclusionMode: ExclusionMode.Normal
    exclusiveZone: card.height + Style.gapsOut
    // Navigation is on the controller, so the surface takes no pointer input
    // and never blocks the window it is typing into.
    mask: Region {}

    BorderSurface {
      id: card
      anchors.horizontalCenter: parent.horizontalCenter
      anchors.bottom: parent.bottom
      // Same distance from the screen edge that every other Omarchy surface
      // keeps: half of Hyprland's gaps_out.
      anchors.bottomMargin: Style.gapsOut
      width: Math.min(parent.width - Style.gapsOut * 2, root.maxWidth)
      height: card.borderTop + card.borderBottom + root.pad * 2 +
        rowsColumn.height
      // The bar's own ground rather than the menu's: the keyboard sits where
      // a bar would and the two should not be two different greys.
      color: Color.bar.background
      borderSpec: Border.surfaceSpec("menu", "border", Color.menu.border,
        Math.max(1, metrics.space(1)))
      radius: Style.cornerRadius
      opacity: root.opened ? 1 : 0
      Behavior on opacity { NumberAnimation { duration: 110 } }

      Column {
        id: rowsColumn
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.leftMargin: card.borderLeft + root.pad
        anchors.rightMargin: card.borderRight + root.pad
        anchors.topMargin: card.borderTop + root.pad
        spacing: root.keyGap

        Repeater {
          model: root.rows
          delegate: Item {
            id: rowItem
            required property int index
            required property var modelData
            width: rowsColumn.width
            height: root.keyHeight

            // Every row spans the full width: each key takes the share of the
            // leftover space its weight asks for, so the columns line up the
            // way they do on a real keyboard.
            readonly property real totalWeight: {
              var sum = 0
              for (var i = 0; i < modelData.length; i++)
                sum += (modelData[i].w === undefined ? 1 : modelData[i].w)
              return sum <= 0 ? 1 : sum
            }
            readonly property real unit:
              (width - root.keyGap * (modelData.length - 1)) / totalWeight

            Row {
              spacing: root.keyGap
              Repeater {
                model: rowItem.modelData
                delegate: Rectangle {
                  id: keyCell
                  required property int index
                  required property var modelData
                  readonly property bool selected:
                    rowItem.index === root.selRow && index === root.selCol
                  // A modifier key stays lit while it is latched.
                  readonly property bool latched:
                    (modelData.m === "shift" && root.shift) ||
                    (modelData.m === "ctrl" && root.ctrl) ||
                    (modelData.m === "alt" && root.alt) ||
                    (modelData.m === "caps" && root.caps)

                  width: rowItem.unit * (modelData.w === undefined ? 1 : modelData.w)
                  height: root.keyHeight
                  radius: Math.max(metrics.space(4), Style.cornerRadius)
                  color: selected ? Color.accent
                    : latched ? Util.alpha(Color.accent, 0.30)
                    : Util.alpha(Color.menu.text, modelData.s ? 0.04 : 0.13)
                  border.width: selected ? 0 : Math.max(1, metrics.space(1))
                  border.color: selected ? "transparent"
                    : latched ? Util.alpha(Color.accent, 0.55)
                    : Util.alpha(Color.menu.text, 0.10)

                  // What the key becomes on the other side of Shift. omapad
                  // sends it empty for keys Shift leaves alone, so the quiet
                  // keys stay quiet.
                  readonly property string alt:
                    modelData.x === undefined ? "" : modelData.x
                  // With Shift latched the printed character has already
                  // swapped; drawing it quieter is what makes the swap visible
                  // at a glance instead of having to read the row.
                  readonly property bool swapped: root.shift && alt !== ""

                  // What the badge costs the label: its own width and the
                  // gap before it, or nothing at all when there is no badge.
                  // The same either way - right-aligned it is the room the
                  // label may not grow into, beside the label it is what sits
                  // next to it.
                  readonly property int hintSpace:
                    hint.visible ? hint.implicitWidth + metrics.space(8) : 0

                  // The label and the badge share one line rather than a
                  // word in the middle of the key with something loose in a
                  // corner under it. The label keeps its own width until the
                  // key runs out of room, so "Space" and the button that
                  // types it stay on a key five units wide either way.
                  //
                  // Right-aligned, the badge sits against the key's own edge
                  // and the label is centred in what is left, so the badges
                  // make a column down the keyboard and read as one list of
                  // what the pad reaches. Beside the label the two are
                  // centred as a pair, which reads as belonging to that key.
                  // `osk.badge_align` picks.
                  Text {
                    id: keyLabel
                    anchors.verticalCenter: parent.verticalCenter
                    width: Math.min(implicitWidth,
                      parent.width - metrics.space(6) - parent.hintSpace)
                    x: Math.round((parent.width - parent.hintSpace - width) / 2)
                    horizontalAlignment: Text.AlignHCenter
                    elide: Text.ElideRight
                    text: modelData.l === undefined ? "" : modelData.l
                    font.family: metrics.font.family
                    font.pixelSize: (modelData.s && !modelData.g)
                      ? metrics.font.bodySmall : metrics.font.title
                    font.bold: selected
                    color: selected ? Color.menu.background
                      : latched ? Color.accent
                      : parent.swapped
                        ? Util.alpha(Color.menu.text, 0.70)
                        : (modelData.s && !modelData.g)
                          ? Util.alpha(Color.menu.text, 0.75)
                          : Color.menu.text
                  }

                  Text {
                    anchors.top: parent.top
                    anchors.right: parent.right
                    anchors.topMargin: metrics.space(3)
                    anchors.rightMargin: metrics.space(4)
                    visible: parent.alt !== "" && parent.width > metrics.space(28)
                    text: parent.alt
                    font.family: metrics.font.family
                    font.pixelSize: metrics.font.caption
                    color: selected
                      ? Util.alpha(Color.menu.background, 0.60)
                      : Util.alpha(Color.menu.text, 0.38)
                  }

                  // The pad button that reaches this key, where one does.
                  // On the label's line, at the right: the top right is
                  // already where the other half of the key is printed, and
                  // the two are different promises - one is what Shift turns
                  // this key into, the other is what to press instead of
                  // walking here.
                  KeyBadge {
                    id: hint
                    anchors.verticalCenter: parent.verticalCenter
                    x: root.badgeAlign === "right"
                      ? Math.round(parent.width - metrics.space(6) - implicitWidth)
                      : Math.round(keyLabel.x + keyLabel.width + metrics.space(8))
                    label: modelData.b === undefined ? "" : modelData.b
                    kind: modelData.k === undefined ? "face" : modelData.k
                    // Quieter than the character: the key is what is being
                    // read, and the badge is the shortcut to it.
                    ink: selected
                      ? Util.alpha(Color.menu.background, 0.75)
                      : Util.alpha(Color.menu.text, 0.55)
                    fill: selected
                      ? Util.alpha(Color.menu.background, 0.20)
                      : Util.alpha(Color.menu.text, 0.13)
                    // A badge wider than the key it sits in would read as the
                    // key, so a cell too narrow for both simply keeps the
                    // character. Nothing is lost: the guide has the same
                    // binding in full.
                    visible: label !== ""
                      && parent.width >= implicitWidth + metrics.space(34)
                  }
                }
              }
            }
          }
        }
      }
    }
  }

  // While the keyboard is up the session looks idle to the compositor:
  // navigating it moves a selection over a socket and produces no Wayland
  // input at all. Bind an idle-inhibitor to `opened` so the screensaver can't
  // start mid-typing. Omarchy's idle service runs its monitor with
  // `respectInhibitors: true`, so this is respected automatically.
  IdleInhibitor {
    window: panel
    enabled: root.opened
  }
}
