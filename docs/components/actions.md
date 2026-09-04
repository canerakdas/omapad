# Actions - `omapad/actions.py`

The grammar every binding, menu entry and keyboard key is written in, and the
session plumbing the ones that spawn things need.

## The grammar

A spec is `<verb>:<argument>`. `parse(spec)` returns an `Action`; `PARSERS`
maps the verb to its class. Every action is parsed **when the config is
loaded**, not when it fires, so a typo surfaces in `omapad check`.

| Verb | Class | Does |
|---|---|---|
| `click:` | `ClickAction` | a mouse button through the virtual mouse, and the burst that says so ([`ripple.md`](ripple.md)) |
| `key:` | `KeyAction` | a key or chord, through `keymap.parse_chord` |
| `scroll:` | `ScrollAction` | a wheel notch |
| `hypr:` | `HyprAction` | a Lua dispatcher over Hyprland's socket - see [`../conventions/lua.md`](../conventions/lua.md) |
| `exec:` | `ExecAction` | a command, with the session's environment |
| `osk:` | `OskAction` | a keyboard command |
| `menu:` | `MenuAction` | a menu command |
| `guide:` | `GuideAction` | a guide command |
| `map:` | `MappingAction` | a mapping-wizard command |
| `surface:` | `SurfaceAction` | close / close_all / back, whatever is in front |
| `focus:` | `FocusAction` | focus traversal inside a window |
| `snap:` | `SnapAction` | jump the pointer to the window next door |
| `pad:` | `PadAction` | change one of the settings in `config.CHOSEN` |
| `mode:` | `ModeAction` | desktop / game / toggle |
| (empty) | `NoAction` | bound to nothing, on purpose |

`ActionError` is what an unknown verb or a bad argument raises.

## `Binding`

A button is a `Binding`: a `tap`, an optional `hold`, `on_release`, and the
repeat settings. `desc` / `hold_desc` and `short` / `hold_short` ride along
untouched - `Binding` reads only `hold_desc`, for the notification an
announced hold sends, and the rest is the [guide](guide.md)'s to print. `HOLD_MS` is the default that separates the two;
`ANNOUNCED_MS` is how long a held action leans its badge on the game bar
before it fires.

`reaches_past` says whether this binding still fires while the pad has been
handed to the app in front, and it is **tri-state** on purpose. `None` is
"nobody has ruled on it", which leaves `allowed()` on its default - a summon
gets through and nothing else - and it is not the same as `False`, which keeps
even a summon back. `daemon.binding_for` promotes `None` to `True` when the
layer the binding was *found* in says so, and otherwise leaves it alone. See
`daemon.allowed()` and [handover](handover.md).

## `Session`

A systemd user service does not reliably inherit the compositor's variables,
so `Session` rediscovers them: `XDG_RUNTIME_DIR` first, then the Wayland
socket by globbing the runtime directory, then
`HYPRLAND_INSTANCE_SIGNATURE`. Everything spawned gets that environment.

`OMARCHY_BIN` is where Omarchy's own commands live; a binding that calls one
goes through there rather than assuming `PATH`.

`capture()` runs a command and hands back the non-empty lines it printed. It
blocks for as long as the command takes, so callers reach it through
`Commands` rather than from the loop.

## `Commands`

The thread the shell commands a surface asks for are run on. `submit(key,
command, timeout)` queues one, the thread runs `Session.capture`, and the
answer waits in `drain()` as `(key, lines)` - with one byte written down
`wake`, so the daemon's `poll()` returns at once instead of holding the answer
until the idle timeout. One command at a time and in order: two of them are a
menu page and a keyboard page, and a queue keeps a slow one from being outrun
by the press after it.

A command that fails, times out or raises answers with an empty list. The
thread must not die of one - that would be every later page silently never
filling.

The daemon's half is `submit_command()` / `drain_commands()`, which put a
callback behind the key; see [`daemon.md`](daemon.md).

## `Hypr`

The Hyprland IPC client: one socket per request, the reply read back for the
callers that need it (`clients` for snap, `monitors` for which workspaces are
visible, `workspaces` and `activewindow` for the bar and the profile).
Failure is a `None` and a log line - the daemon runs with no compositor.

**`query()` is how the daemon asks, never `hyprctl`.** The answer comes back
in well under a millisecond where a fork and an exec cost tens, and every
caller is on the loop.

## Rules

- A new verb is a new `Action` subclass plus a row in `PARSERS`, and it
  validates its argument **in its constructor**.
- An action that reaches a surface does not touch the surface's model: it
  hands a command word to the daemon, which routes it. That is what keeps a
  surface's state in one place.
- Anything that can take seconds does not belong in an action; see the loop
  rule in [`daemon.md`](daemon.md).
- Give the guide something to print: `guide.describe()` derives a sentence
  from the action, and where the derivation is thin the binding carries a
  `desc`. A `desc` whose first word is not the meaning needs a `short` for
  the bar - see [`../conventions/bindings.md`](../conventions/bindings.md).
- **Which button an action lands on is not a free choice.** The face buttons
  carry one meaning each, everywhere; the same file says what a layer or a
  profile may take.
