# Bar widget - `daemon.status_state()` + `shell-plugin/PadStatus.qml`

The only thing omapad puts on screen that nobody summoned. Everything else it
draws is asked for and then goes away; this is the standing answer to "is the
pad mine?", which is worth a slot in the bar Omarchy already owns rather than a
second bar of ours fighting it for the same screen edge.

## Payload - `status.sock`

```
mode, connected, pad, profile, handed_over, locked, kept
```

Pushed on every change and re-sent on the heartbeat, so a shell restart
repaints itself and **a daemon that stops talking takes the widget off the bar
with it**.

## The widget

`PadStatus.qml`, the plugin's `barWidget` entry point (see `manifest.json`:
`displayName: "Controller"`, category `Hardware`, default section `right`).

Game mode is drawn in the bar's own urgent colour rather than a colour of ours,
because it is the state where a pressed button does nothing on the desktop and
the bar already has a way of saying "look here". The workspace lock
([`handover.md`](handover.md)) wears the same colour and a padlock: it is the
same statement, said harder, and nothing else on the desktop says it - the
game bar has gone by then, because the pad is the app's.

A **kept** pad keeps the plain gamepad glyph and is lit instead. It is the
ordinary state - the pad is ours - held on to over a window that wanted it, and
a glyph of its own would say something had changed about the pad when what
changed is who was refused it. The tooltip names it.

Settings: `[status] socket`.
