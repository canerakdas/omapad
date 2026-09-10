# Lua style guide

There is no `.lua` file in this repository. Lua appears in exactly one place:
the value of a `hypr:` binding in `config/config.toml`, which this Hyprland
evaluates as a Lua expression. See [`README.md`](README.md) for how MUST /
SHOULD / MAY are meant here.

```toml
L = { tap = "hypr:hl.dsp.focus({ workspace = 'r-1' })", desc = "Previous workspace" }
```

## 1 Rules

- **The old string form is dead.** `workspace e+1` and every other
  `/dispatch`-style string does nothing on this Hyprland; it routes
  `/dispatch` through Lua. Always `hl.dsp.<dispatcher>({ ... })`.
- The valid dispatchers and their arguments are in
  `/usr/share/hypr/stubs/hl.meta.lua`. Read it rather than guessing at a name:
  a wrong dispatcher fails silently at the press, and `omapad check` cannot
  catch it - the expression is not evaluated until it is fired.
- **Single quotes inside the expression.** The whole thing lives in a
  double-quoted TOML string, so `'e+1'` costs nothing and `\"e+1\"` is
  unreadable.
- One expression per binding. If two things have to happen, that is two
  bindings or an `exec:` to a script - not a `;`-joined line nobody can read
  back.
- **Write `desc =` next to it.** `guide.py` derives an English description from
  the action so the bindings guide has something to print, and its derivation
  for a Lua dispatcher is thin: `_DISPATCH` and `_ARGUMENT` in `guide.py`
  recognise a handful of shapes (`focus`, `workspace`, `movetoworkspace`, a
  quoted argument) and anything else prints as the raw expression. A `desc`
  is how you stop the guide printing Lua at the user.
- Keep the expression short enough to read in a config file. Anything with
  logic in it is a script called through `exec:`, where it can be tested and
  where a failure has somewhere to go.

## 2 Where it is parsed on this side

`guide._describe_hypr()` reads the dispatcher name and the quoted arguments
out of the string with two regexes, purely to write a sentence. Nothing else
in the daemon inspects it: `actions.HyprAction` hands the expression to
Hyprland's socket as written.

## 3 The config is Lua too, and `keyword` is dead with it

`hyprctl keyword <option> <value>` does not work on this Hyprland. It answers
*"keyword can't work with non-legacy parsers. Use eval."* and changes nothing -
silently, if the caller sent its output to `/dev/null`, which is how a probe
that seems to prove an option has no effect at runtime is really only proving
that nothing was set. The runtime form is a Lua call:

```bash
hyprctl eval 'hl.config({ cursor = { invisible = true } })'
```

Nothing in omapad sets a compositor option, and this is one reason not to
start: an option is the desktop's, borrowing one means putting it back, and
`omarchy-screensaver` is already the second writer of the one a pointer would
want. Where the daemon needs the compositor to do something it asks for the
behaviour instead - see [`cursor.md`](../components/cursor.md), where a press
that hides the pointer sends a keystroke rather than setting `cursor:invisible`.
