# omapad documentation

`README.md` in the repository root is the user-facing manual: what the thing
does, how it is bound, how to configure it. Everything under `docs/` is for
whoever is changing the code.

| Path | What it is |
|---|---|
| [`roadmap.md`](roadmap.md) | Planned work, with per-item confidence. |
| [`conventions/`](conventions/) | How to write in each language this project uses, and how files and folders are named. |
| [`components/`](components/) | One document per component: what it owns, what it may assume, what breaks it. |
| [`../.claude/skills/`](../.claude/skills/) | One skill per recurring job that spans several files and fails silently: bindings, surfaces, settings, menu rows, badge art, diagnosis. |

## Conventions

| Document | Covers |
|---|---|
| [`conventions/python.md`](conventions/python.md) | The daemon, the tests and the asset generator. |
| [`conventions/qml.md`](conventions/qml.md) | The Omarchy shell plugin. |
| [`conventions/bash.md`](conventions/bash.md) | `bin/`, `install.sh`. |
| [`conventions/lua.md`](conventions/lua.md) | The Hyprland dispatcher expressions inside `hypr:` bindings. |
| [`conventions/data.md`](conventions/data.md) | The formats that carry decisions rather than code: TOML config, the socket payloads, SVG shapes, the unit and udev rule. |
| [`conventions/bindings.md`](conventions/bindings.md) | What each button on the pad means, and what a layer or an application profile may take from it. |
| [`conventions/naming.md`](conventions/naming.md) | File naming and folder structure, for every kind of file in the tree. |

## Components

Start at [`components/README.md`](components/README.md); it maps every file in
the tree to the component that owns it.

## The two rules that outrank everything here

1. **Surface state lives in the daemon.** The plugin draws what it is handed
   and never decides anything. A keypress must never wait for a round trip to
   the shell.
2. **Everything outside the daemon is optional plumbing.** No compositor, no
   plugin, no control socket, no pad: the loop keeps running and logs a line.
