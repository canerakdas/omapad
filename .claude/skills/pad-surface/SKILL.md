---
name: pad-surface
description: Add or change an omapad surface - a daemon-side model plus the QML panel that draws it and the socket between them. Use when asked to "add a new screen/overlay/panel", "make the daemon show X", "add a field to the keyboard/menu/guide/bar payload", or when a panel is not drawing, not opening, or silently ignoring half its data. Covers the wiring checklist and the three silent failure modes.
---

# Adding or changing a surface

A surface is **three things that must agree**: a model in the daemon, a socket,
and a panel that only draws. Getting one of them wrong is usually silent -
this file exists for the silent parts.

Read [`docs/conventions/qml.md`](../../../docs/conventions/qml.md) before
touching a `.qml`, [`docs/components/viewsock.md`](../../../docs/components/viewsock.md)
for the boundary, and the target surface's own doc under `docs/components/`.

## The two rules that decide every question

1. **Surface state lives in the daemon.** The layout, the latches, the tree,
   the stack, the page, the step - all of it. The panel receives
   line-delimited JSON and paints it. A keypress must never wait for a round
   trip to the shell.
2. **The view is best-effort.** `ViewClient.send` never raises and every state
   is re-sent every `VIEW_HEARTBEAT` (2.0 s), so a restarted shell repaints
   itself. Nothing in the loop may depend on the plugin being up.

If a change needs the panel to decide something, ask what field the daemon
should send instead. There is **no channel back**: a panel asks for things by
spawning `omapad ctl`, which is a different socket and a different process, so
that a drawing problem can never stall an input one.

## The three silent failures

Learn these before writing anything; each one costs an hour if you meet it
without knowing it.

### 1. A bare assignment in `applyState`

```qml
if (s.title !== undefined) root.title = s.title      // ✅
if (s.title !== undefined) title = s.title           // ❌
```

A bare name resolves against the whole QML scope chain and can land on
something read-only. The assignment throws, `applyState`'s `catch` swallows
it, and **every field after it silently stops being applied**. Because `open`
is assigned last, the symptom is a panel that has all its data and never comes
up. Nothing in any log says so.

### 2. A brand-new `.qml` does not hot-reload

Qt caches the directory listing per process. A new file fails with a
misleading `File name case mismatch` and the panel stays down.

```bash
/usr/lib/qt6/bin/qmllint shell-plugin/Thing.qml   # syntax and scope, first
omarchy-shell shell rescanPlugins                 # editing an existing file
omarchy-restart-shell                             # ADDING one, or an edit that will not take
qs -p /usr/share/omarchy/shell log                # the only place the real error appears
```

Panel entry points (`keepLoaded: true`) have been seen to resist
`rescanPlugins` even on an edit; the bar widget never does.

### 3. A model re-assigned from an unchanged payload

The daemon re-sends everything twice a second and on every press, so most of
what arrives is already on screen. A `var` property never compares equal to
its old value, so re-assigning one rebuilds every delegate under it - measured
at 0.4% of a core and a climbing heap for a surface nobody is touching.

Every field that is a **model** goes through `fresh()`; scalars do not need it
(`PadStatus.qml` has neither and is right not to). And because a rebuilt
delegate is born wherever the state happens to be, any `Behavior` or animation
it needs must also be entered from `Component.onCompleted` - see
`GameBar.qml`'s `Badge.enterHold()`.

## Adding a whole surface

Nine steps. Follow `menu.py` / `Menu.qml` as the smallest complete example.

1. **`omapad/<name>.py`** - a module docstring saying *why it exists*, and a
   `<Name>Model` class holding the state with a `view_state(opened)` that
   returns the payload dict. No I/O, no compositor calls: it is a model.
2. **`tests/test_<name>.py`** - synthetic input into the model. No hardware,
   no `/dev/uinput`.
3. **`config/config.toml`** - a `[<name>]` section with its settings, each
   with a comment saying what it decides, and the commented-out `socket` line
   the others carry. Read it in `config.py` with `.get(key, default)`; see
   the `pad-setting` skill.
4. **Daemon wiring**, four places in `omapad/daemon.py` - grep `menu_client`
   to see all of them at once:
   - `__init__`: `self.<name> = <Name>Model(...)`,
     `self.<name>_client = ViewClient("<name>.sock", config.<name>_socket)`,
     `self.<name>_open = False`, `self._<name>_next_heartbeat = 0.0`
   - `push_<name>_view()`: set the next heartbeat, then
     `self.<name>_client.send(self.scaled(self.<name>.view_state(...)))`.
     `scaled()` stamps the payload with `[ui] scale` - never let the panel
     guess it.
   - `set_<name>(opened)`: close the surfaces this one outranks, push, then
     `self.apply_grab()` and one `log.info`
   - the poll loop's heartbeat block and `close()` at shutdown
5. **The layer**, if the surface reads the pad: a `[bindings.<name>]` table,
   the name in `daemon.SURFACE_LAYERS`, and a branch in `current_layer`. The
   order in that property **is** the precedence - guide over menu over
   keyboard. Bindings for it follow
   [`../../../docs/conventions/bindings.md`](../../../docs/conventions/bindings.md):
   A commits, B leaves.
6. **The control verb** - `handle_control` in `daemon.py`, the usage string
   beside it, and the `--help` text in `__main__.py`. Everything a binding can
   do to the surface must be reachable here, so it can be driven without a pad.
7. **`shell-plugin/<Panel>.qml`** - named for what the user sees
   (`Keyboard.qml` draws `osk.py`), but listening on the **daemon's** socket
   name (`osk.sock`), through `SurfaceSocket` and never a bare `SocketServer`
   - qml.md §6.1 says why. Follow qml.md §3's file order, §7's window rules,
   and never hardcode a colour or hand-draw a button.
8. **Mount it in `Surfaces.qml`** - the child item, plus `summonable`,
   `surfaceNames` and `opened` if it can be summoned. `open()`/`close()` shell
   out to `omapad ctl`; a panel that opens itself is a bug.
9. **Docs** - `docs/components/<name>.md`, a row in
   `docs/components/README.md`, and whatever section of `README.md` a user
   would look in. `README.md` is authoritative and is updated in the same pass.

## Adding one field to an existing payload

Cheaper, and mostly a matter of not breaking the old plugin:

- Field names are **short and stable** (`open`, `sel`, `rows`, `b`, `k`, `d`).
  Renaming one is a breaking change against a shell that has not restarted.
- Fields are **additive and optional**. Never repurpose an existing name for a
  different meaning.
- Add it to `view_state()`, declare a `property` with a **drawable default**
  in the panel, guard it `!== undefined` and coerce it (`!!s.open`,
  `String(s.mode)`, `Number(s.scale) || 1`), and put it through `fresh()` if
  it is a model.
- `scale` is assigned first and `open` **last**, always.
- Anything that looks like a shell constant but is really a setting - a
  height, how far a badge leans - goes in the payload. The plugin cannot read
  the config.
- Update the payload line in `docs/components/<name>.md`.

## Verifying

```bash
python3 -m unittest discover -s tests -v      # the model, without a shell
./bin/omapad check                            # the config parses
systemctl --user restart omapad               # required after ANY code change
omapad ctl <verb> toggle                      # drive it with no pad
journalctl --user -u omapad -f                # the daemon's side
qs -p /usr/share/omarchy/shell log            # the panel's side
```

If the panel does not come up: check the shell log first, then walk the three
silent failures above in order. If it comes up empty, the payload arrived and
a field name disagrees - compare `view_state()` against the panel's
`applyState` line by line.
