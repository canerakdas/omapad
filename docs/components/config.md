# Configuration - `omapad/config.py`, `config/config.toml`

Every number the daemon acts on comes from here, and every mistake in the file
is supposed to surface as a `ConfigError` from `omapad check` rather than as
nothing happening under a thumb.

## The merge

Four layers, each deep-merged over the last:

1. `config/config.toml` - the shipped defaults, in the checkout.
2. `~/.config/omapad/config.toml` - the user's file, hand-written.
3. `~/.config/omapad/mapping.toml` - what the mapping wizard measured.
4. `~/.config/omapad/settings.toml` - what was changed from the controller
   menu, last so it wins.

**Never copy the shipped defaults into the user's file.** That freezes them.

`load(path=None, mapping=None, settings=None)` does the merge and returns a
`Config`; `_deep_merge` is the merge, `_load_toml` the read.

## `Config`

A flat object of validated attributes - `pointer_speed`, `snap_bias`,
`gamebar_height`, `handover_depth`, `osk_layout`, one per setting - plus the
parsed structures: `bindings`, `layers`, `chords`, `profiles`, `menu_items`,
`keyboard_bindings`.

Lookups the daemon uses:

| Method | Answers |
|---|---|
| `binding_for(layer, button)` | what this button does in this layer |
| `binding_with_profile(profile, layer, button)` | the same, with the focused app's override in front |
| `keyboard_binding_for(surface, code)` | what a real keyboard key does while a surface is up |
| `stick_roles(layer, profile)` | what the two sticks are doing |
| `layer(name)`, `layer_for_button(button)` | the layer table, and which layer a button holds open |
| `profile_for(name, vid_pid)` | the controller profile at connect time |
| `badge_layout(profile_name)` | which console's labels the badges print |

## Application profiles

`[profile.<name>]` matches the focused window by class (case-insensitive
substring, first declared wins) and its `[bindings]` are read in front of the
**base layer and game mode**. They stop there: a held layer keeps its own
table, so `ZL` + `B` closes the window whatever the app in front does with `B`,
and the guide's window page - which never asks about profiles - stays true.

An app that wants a held layer's button says which layer, and the table is read
in that layer's place:

```toml
[profile.myapp.window]
X = { tap = "exec:my-window-thing", desc = "..." }
```

`PROFILE_KEYS` is what a profile table may hold besides a layer name
(`match`, `bindings`, `osk`, `left_stick`, `right_stick`, `handover`);
`handover = false` keeps the pad from ever being handed to this application,
which is the answer for one that opens a pad without being played through -
see [handover](handover.md). Anything else raises
`ConfigError` at load, because a mistyped layer name would otherwise be a
binding that silently never fires.

## Profiles and layouts

`PROFILES` maps a profile name to its button table (`nintendo_pro`, `xbox`);
`detect_profile(name, vid_pid)` picks one from the device identity at connect
time. `PROFILE_LAYOUTS` maps that to the console whose labels get *printed* -
a separate question, answered in `guide.LAYOUTS`. `[device] layout` overrides
it; `auto` follows the profile.

Logical button names are the pad's **own printed labels**, so `A` is a
different physical button in NS mode than in XInput mode.

## Settings changed from the pad

`CHOSEN` is the table of what the controller menu may change: for each, the
`Config` attribute, the TOML table and key it is written back to, its kind
(`bool`, `choice`, `number`) and, for a number, its step, range and unit.
`setting_request()` parses a request (`toggle`, `on`, `+`, `-`, a value),
`_clamp_setting` keeps it in range, `setting_text()` renders it for a menu
row, and `render_settings()` writes `settings.toml` back out.

`SettingError` is what an out-of-range or unknown request raises.

## Adding a setting

1. Add it to `config/config.toml` with its default **and a comment saying what
   it decides**.
2. Read it in `Config.__init__` with `.get(name, default)`, so an old user
   file still loads.
3. Validate anything that can be wrong there, raising `ConfigError` with the
   table and key named.
4. If it should be reachable from the controller menu, add it to `CHOSEN` and
   give it a `[[menu.items]]` row.
5. Document it in `README.md`.

## Traps

- `_renamed()` and `SETTING_ALIASES` carry a user's file over a rename. The
  shipped defaults always hold the current names and are merged *under* the
  user's sources, so a fallback inside `Config` would never see an old key -
  the rename has to happen to the user's data on the way in. The dead zones
  are the case: one number per role (`deadzone` under `[pointer]` and
  `[scroll]`) became one per stick.
- `APP_PAGE_TTL` / `APP_PAGE_LIMIT` bound the keyboard page an app profile can
  lend; `parse_app_page` builds it.
- `SURFACES` and `KEYBOARD_SURFACES` are the surface names in binding tables -
  `map`, `guide`, `menu`, `osk`, plus `base` for the keyboard.
- `TRAVERSE_DEFAULTS` and `TRAVERSE_STICK_DEFAULTS` are what focus traversal
  falls back to; they are defaults, not constants.
