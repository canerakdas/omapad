# Data formats

Rules here are normative in the same way the language guides are; see
[`README.md`](README.md) for how MUST / SHOULD / MAY are meant.

The formats that carry decisions rather than code. Each has one owner and one
rule that matters more than the rest.

## TOML - `config/config.toml`

The shipped defaults. The user's file at
`~/.config/omapad/config.toml` is **deep-merged over** it, so:

- **Never copy the shipped defaults into the user's file.** That freezes them:
  the user stops receiving any default that changes later.
- A new setting goes in `config/config.toml` with its default **and a comment
  saying what it decides**, and is read in `config.py` with
  `.get(name, default)` so an older user file still loads.
- A value that can be wrong - an unknown key name, a mode that is not one of
  two - is validated in `config.py` and raises `ConfigError`, naming the table
  and key, so `omapad check` reports it.
- Sections are `[area]` and `[area.sub]`, keys are `snake_case`. Bindings are
  inline tables on one line (`A = { tap = "...", desc = "..." }`) because a
  binding is one thought.
- Comments in this file are the user's manual as much as `README.md` is;
  write them for someone editing at a keyboard, not for a reviewer.

Two files are written *by* the program and are merged after the user's:

| File | Written by | Why it is not in `config.toml` |
|---|---|---|
| `~/.config/omapad/mapping.toml` | the mapping wizard | `config.toml` is hand-written and full of comments a program would trample; a mapping is undone by deleting a file |
| `~/.config/omapad/settings.toml` | the controller menu | same reason; it is merged last so what was just changed from the pad wins |

## The socket payloads - line-delimited JSON

One JSON object per line, one line per state change, pushed daemon → plugin
over `$XDG_RUNTIME_DIR/omapad/<surface>.sock`. See
[`../components/viewsock.md`](../components/viewsock.md).

- **Field names are short and stable**: `open`, `sel`, `rows`, `l`, `d`, `b`,
  `k`. They are read in exactly one `applyState` each, and renaming one is a
  breaking change against a shell that has not restarted.
- **Fields are additive and optional.** The plugin guards every field with
  `!== undefined`, so a daemon that sends a new one talks to an old plugin
  fine. Never repurpose an existing name for a different meaning.
- Everything the plugin needs to draw is in the payload, including the things
  that look like shell constants - the surface scale, the bar's height, how
  far a badge leans. They are settings, and the shell has no access to the
  config.
- `open` is meaningful on its own: it is what opens and closes the surface,
  and it is assigned last on the QML side.

## SVG - `assets/shapes/`

Hand-drawn, unlabelled, one file per control, and **the source**. Everything
in `assets/buttons/` and all of `shell-plugin/ButtonArt.qml` is generated from
them by `python3 assets/generate.py`. Figma's output dialect (`M C H V L Z`
plus `A` for a circle, absolute or relative) is what `assets/svgpath.py`
parses. See [`../components/assets.md`](../components/assets.md).

## JSON - `manifest.json`

What the Omarchy shell reads before it loads anything: the plugin's id, its
`kinds`, and the `entryPoints` that name the QML files for the panel and the
bar widget. `keepLoaded: true` is why the panels are alive to receive a socket
line before anybody summons them.

- **It sits at the repo root, not beside the QML.** `omarchy plugin add`
  clones a repo and reads the manifest at its top, so a root manifest is what
  puts the daemon and the surfaces one command away instead of two. The price
  is the `shell-plugin/` prefix on every entry point: the shell resolves them
  against the manifest's own directory and rejects one that climbs out of it.
- The id `canerakdas.omapad` is the plugin's address everywhere -
  the symlink under `~/.config/omarchy/plugins/`, `omarchy-shell shell summon`,
  the bar layout in `shell.json`. Renaming it breaks all three at once.
- `omarchy-plugin-validate .` checks it, and `install.sh` runs that
  before linking: the shell rejects an invalid manifest on a console line
  nobody reads.
- It is the shell's schema, not ours. Add a field only because the shell reads
  it; anything omapad needs to say goes over a socket instead.

## The systemd unit and the udev rule

- `systemd/omapad.service` is a template: `__REPO__` is substituted by
  `install.sh`. It is a user unit, `PartOf=graphical-session.target`, and it
  carries `Environment=XDG_RUNTIME_DIR=%t` because that one variable is what
  makes rediscovering the rest possible.
- `udev/99-omapad-uinput.rules` exists so the daemon never runs as root. It
  gives the `input` group `/dev/uinput`, with `static_node=uinput` so the mode
  applies before the module is loaded on demand.
