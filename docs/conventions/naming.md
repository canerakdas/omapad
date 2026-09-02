# File naming and folder structure

Rules here are normative in the same way the language guides are; see
[`README.md`](README.md) for how MUST / SHOULD / MAY are meant.

The standard, derived from what the tree already does. When adding a file, the
question is not "where does this fit?" but "which of these kinds is it?" -
each kind has exactly one home and one naming rule.

## The tree

```
omapad/
  bin/              executable entry points (bash wrappers, no extension)
  omapad/           the daemon: one Python module per concern
  shell-plugin/     the Omarchy shell plugin (QML), one file per component
    fonts/          the one vendored font, and its licence file
  assets/           the drawn buttons: sources, generator, generated SVGs
    shapes/         hand-drawn sources - edit these
    buttons/        generated, do not edit
  config/           the shipped defaults (config.toml)
  systemd/          the user unit
  udev/             the uinput rule
  tests/            one test module per daemon module
  docs/             this folder
    conventions/    how to write in each language
    components/     one document per component
  .claude/skills/   one folder per skill, each holding a SKILL.md
  manifest.json     the Omarchy plugin manifest - at the root, not in
                    shell-plugin/, so `omarchy plugin add` finds it
  README.md         the user-facing manual, authoritative
  LICENSE           MIT; the vendored font keeps its own OFL beside it
  boot.sh           the one-command bootstrap: clone, then hand over
  install.sh        the only script that uses sudo
```

## Naming, by kind of file

| Kind | Where | Name | Example |
|---|---|---|---|
| Daemon module | `omapad/` | one lowercase word for the concern; `snake_case` only when one word will not do | `rumble.py`, `linux_input.py` |
| Test module | `tests/` | `test_<module>.py`, mirroring the module it covers | `tests/test_osk.py` |
| Asset tool | `assets/` | lowercase word naming the job | `generate.py`, `place.py` |
| QML component | `shell-plugin/` | `PascalCase.qml`; the filename **is** the component name | `GameBar.qml` |
| Generated QML | `shell-plugin/` | `<Thing>Art.qml`, with `GENERATED` in the first comment line | `ButtonArt.qml` |
| Shape source | `assets/shapes/` | `<family>-<name>.svg`, family first | `bumper-left.svg`, `sys-plus.svg`, `dpad-up.svg` |
| Generated button | `assets/buttons/` | `<kind>-<side>-<label>.svg`, or `<kind>-<label>.svg` where there is no side | `bumper-l-lb.svg`, `face-a.svg`, `system-menu.svg` |
| Executable | `bin/` | `omapad` or `omapad-<thing>`, no extension, `chmod +x` | `bin/omapad` |
| Unit / rule | `systemd/`, `udev/` | what the packaging convention demands: `omapad.service`, `99-omapad-<thing>.rules` | |
| Vendored asset | beside what loads it | the upstream filename, unchanged, with its licence file next to it | `shell-plugin/fonts/FiraCode-Medium.ttf`, `OFL.txt` |
| Manifest / unit / rule | where the tool that reads it demands | the name that tool demands, never a name of ours | `manifest.json`, `omapad.service` |
| Documentation | `docs/` | `kebab-case.md`, one component per file | `docs/components/linux-input.md` |
| Skill | `.claude/skills/<name>/` | `kebab-case` folder naming the job, always `SKILL.md` inside it | `.claude/skills/pad-bindings/SKILL.md` |

## Names that have to agree across the tree

A component is usually four names, and they must line up:

| | Example |
|---|---|
| daemon module | `omapad/guide.py` |
| test module | `tests/test_guide.py` |
| socket | `$XDG_RUNTIME_DIR/omapad/guide.sock` |
| config key | `[guide]`, `guide_socket` on `Config` |
| control verb | `omapad ctl guide ...` |
| doc | `docs/components/guide.md` |

The QML panel is the exception: it is named for what the user sees
(`Keyboard.qml` for `osk.py`, `Mapping.qml` for `mapping.py`), because the
plugin is the user's side of the boundary. Its socket keeps the daemon's name
(`osk.sock`, `mapping.sock`).

Underscores in a Python module become hyphens in its doc
(`linux_input.py` → `docs/components/linux-input.md`) and stay underscores in
a `Config` attribute (`handover_depth`).

## Naming inside a file

- **Python**: `snake_case` functions, `UPPER_CASE` module constants at the
  top, `_leading_underscore` for anything private. A surface's state class is
  `<Surface>Model`; its exception is `<Area>Error`. `omapad/__init__.py`
  holds the package docstring and `__version__` (what `omapad --version`
  prints) and nothing else - no imports, so importing the package costs
  nothing.
- **QML**: `id: root` for the top-level item, ids elsewhere name the thing
  (`card`, `list`, `badge`, `panel`); `camelCase` properties matching the
  payload field where they differ only in length (`uiScale` for `scale`).
- **TOML**: `snake_case` keys, `[area.sub]` sections, logical button names in
  the pad's own printed capitals (`A`, `ZL`, `MINUS`).
- **Payload JSON**: short and stable; see
  [`data.md`](data.md).

## Adding a component

1. `omapad/<name>.py` with a docstring saying why it exists.
2. `tests/test_<name>.py`.
3. Its settings in `config/config.toml`, read in `config.py` with a default.
4. If it draws: a socket named `<name>.sock`, a `view_state()` on its model,
   a panel in `shell-plugin/` mounted in `Surfaces.qml`, and a control verb in
   `__main__.py` and `daemon.handle_control`.
5. `docs/components/<name>.md`, and a row in
   [`../components/README.md`](../components/README.md).
6. If it added a file to `shell-plugin/`: `omarchy-restart-shell`, not
   `rescanPlugins`.

## What is not tracked

`.gitignore` covers `__pycache__/` and `*.pyc` - the only generated files that
land in the tree. Everything else in it is source, including the generated
`assets/buttons/*.svg` and `shell-plugin/ButtonArt.qml`: they are checked in on
purpose, so a change to a shape shows up as a diff and `tests/test_assets.py`
can fail when the output and the generator disagree.
