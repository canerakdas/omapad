# Bar widget - `daemon.status_state()` + `shell-plugin/PadStatus.qml`

The only thing omapad puts on screen that nobody summoned. Everything else it
draws is asked for and then goes away; this is the standing answer to "is the
pad mine?", which is worth a slot in the bar Omarchy already owns rather than a
second bar of ours fighting it for the same screen edge.

## Payload - `status.sock`

```
mode, connected, pad, profile, handed_over
```

Pushed on every change and re-sent on the heartbeat, so a shell restart
repaints itself and **a daemon that stops talking takes the widget off the bar
with it**.

## The widget

`PadStatus.qml`, the plugin's `barWidget` entry point (see `manifest.json`:
`displayName: "Controller"`, category `Hardware`, default section `right`).

Game mode is drawn in the bar's own urgent colour rather than a colour of ours,
because it is the state where a pressed button does nothing on the desktop and
the bar already has a way of saying "look here".

Settings: `[status] socket`.
