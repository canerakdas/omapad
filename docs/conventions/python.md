# Python style guide

Applies to every `.py` file in the tree: `omapad/` (the daemon), `tests/`,
`assets/` (the badge generator). See [`README.md`](README.md) for how MUST /
SHOULD / MAY are meant here.

## 1 Language

**1.1** Target **Python 3.11+**, and the **standard library only**. A
third-party import is NEVER added without raising it as a design change first
— the daemon must install with nothing but a checkout.

**1.2** Where the standard library is missing something, write the part that is
needed rather than taking a dependency: `linux_input.py` is the evdev ioctls
this project uses, `assets/truetype.py` is the five font tables the badges
need. Say in the module docstring what was left out and why that is the whole
truth for this use.

**1.3** NEVER use f-strings. Format with `%`:

```python
raise MenuError("%s[%d] must be a table" % (where, index))   # ✅
raise MenuError(f"{where}[{index}] must be a table")         # ❌
```

**1.4** NEVER use type annotations — not on parameters, returns, attributes or
variables. When a type is not obvious from the name, the docstring says it.

## 2 Source file

**2.1** Four-space indent. NEVER a tab.

**2.2** Lines MUST be **≤ 79 columns**. Up to 88 is tolerated only where
breaking would hurt the reading — a table row, a long literal. No line in the
tree is over 95 except by accident.

**2.3** No trailing whitespace; one newline at end of file.

**2.4** Strings use **double quotes**. Single quotes only *inside* a
double-quoted string — a Lua expression, a nested quote:

```python
"hypr:hl.dsp.focus({ workspace = 'r-1' })"   # ✅
```

**2.5** Two blank lines between top-level definitions, one between methods.

## 3 File layout

Every module reads in this order, and a reader may rely on it:

```python
"""Why this module exists, and what forced its shape."""   # 1  docstring

import os                                                   # 2  stdlib
import struct

from . import linux_input as li                             # 3  package

# What this number decides, and why it is not a setting.
PERPENDICULAR_WEIGHT = 2.0                                  # 4  constants


def rect(window):                                           # 5  pure functions
    ...


class GameBarModel:                                         # 6  the stateful part
    ...
```

**3.1** The pure half comes before the stateful half, so the testable part can
be read without the class.

**3.2** Helpers private to the module are prefixed `_`. Anything another
module or a test calls is not.

## 4 Imports

**4.1** Two groups, separated by a blank line: standard library first,
alphabetical; then package-relative imports.

**4.2** Package imports are `from . import x`, or `from .x import Name` for a
name used constantly. NEVER `import *`.

**4.3** An alias is used only where the name would drown the line, and then
always the same alias: `linux_input as li`, `guide as guide_module` when a
local name would shadow it.

**4.4** NEVER import at call time to break a cycle. A cycle means the two
modules are one concern that has been split in the wrong place.

## 5 Naming

| Thing | Form | Example |
|---|---|---|
| module | one lowercase word for the concern; `snake_case` only if one word will not do | `rumble.py`, `linux_input.py` |
| function, method, variable | `snake_case` | `binding_for`, `view_state` |
| module constant | `UPPER_CASE`, declared at the top | `HOLD_MS`, `VIEW_HEARTBEAT` |
| class | `CapWords` | `OskModel`, `ViewClient` |
| a surface's state class | `<Surface>Model` | `MenuModel`, `GameBarModel` |
| an area's exception | `<Area>Error` | `ConfigError`, `ActionError` |
| private helper | `_snake_case` | `_deep_merge`, `_describe_hypr` |

**5.1** Names come from the domain, not from the implementation: the pad's
printed button names, the compositor's words, the kernel's constant names.

## 6 Docstrings

**6.1** Every module MUST open with a docstring, and it MUST say **why the
module exists and what forced its shape** — not what its functions are called.
`handover.py`, `snap.py` and `cursor.py` are the models.

**6.2** A function or class gets a docstring when its name is not the whole
answer. About half of `omapad/` has one; a getter named `centre` does not
need to say it returns the centre.

**6.3** A docstring is a **noun phrase answering what this is**, not an
imperative sentence about what it does:

```python
"""The payload the shell plugin draws."""                    # ✅
"""One printed row, or None when the binding says to do nothing."""  # ✅
"""Returns a dict containing the view state."""              # ❌
```

**6.4** Multi-line form: a one-line summary, a blank line, then the
constraint, the trap or the reason — the part that would otherwise be lost.
Close with `"""` on its own line.

**6.5** Docstring lines obey the 79-column rule like any other line.

## 7 Comments

**7.1** A comment states **the constraint that forced the code**, never what
the line does:

```python
# A pad in XInput mode carries EV_KEY too; absolute axes are what tell the
# two apart, the same test find_device() makes from the other side.          # ✅
# Check whether ABS_X is in the capabilities.                                # ❌
```

**7.2** Density is about **14%** of `omapad/` and 8% of `tests/`. Do not add
narration to reach it, and do not delete a long rationale to tidy a file.

**7.3** Every module constant carries a comment saying what decision it
encodes — see §8.

## 8 Numbers are decisions

**8.1** A number in the code is a decision made on the user's behalf. Anything
someone could reasonably want different — a threshold, a timing, a proportion,
which button means what, whether a thing is on at all — MUST be a setting, and
the value in the code becomes its default.

**8.2** What legitimately stays hardcoded:

- a wire format or a kernel constant (`EVENT_FORMAT`, `SYN_REPORT`);
- a geometric identity;
- an implementation trade-off rather than a preference (`CURVE_STEPS`,
  `SUPERSAMPLE`, a buffer size).

**8.3** When you leave one in, the comment MUST say **why it is not a
setting**:

```python
# Segments per curve when flattening. The shapes are 64 units across at most
# and the mask is sampled a few times per unit, so this is far finer than the
# grid it lands on - an implementation detail, not a knob.
CURVE_STEPS = 24
```

**8.4** Every capability SHOULD be reachable from config, not only from the
shape it first shipped in: a role that cannot carry the option its equivalent
binding carries is a gap, not a design.

## 9 Settings

**9.1** A new setting goes in `config/config.toml` with its default **and a
comment**, and is read in `config.py` with `.get(name, default)` so an older
user file still loads.

**9.2** Anything that can be wrong is validated **where it is read**, not
where it is used, and raises `ConfigError` naming the table and key — so
`omapad check` reports it instead of the daemon failing under a thumb.

## 10 Errors

**10.1** One exception class per area, subclassing `ValueError` or
`RuntimeError`: `ConfigError`, `SettingError`, `ActionError`, `MenuError`,
`OverrideError`, `KeyParseError`, `UinputError`.

**10.2** Messages MUST start lowercase, name the offending value with `%r`,
and name the path in the config where there is one. All 84 `raise` sites in
`omapad/` follow this:

```python
raise ActionError("unknown mouse button: %r" % name)          # ✅
raise MenuError("%s needs a label" % path)                    # ✅
raise ActionError("Unknown mouse button.")                    # ❌
```

**10.3** Optional plumbing NEVER raises out. The compositor, the shell, the
pad's motors and the control socket are each wrapped: catch `OSError`, log one
line, carry on. `ViewClient.send` is the model — it cannot raise by
construction.

## 11 The loop may not block

**11.1** Everything reached from `daemon.run()` MUST return in microseconds.

**11.2** Anything that shells out, waits on a socket, or reads a file that
might not answer is either best-effort and wrapped, or it runs in a thread and
posts back through a queue the loop learns about by reading one byte off a
self-pipe registered with `poll()`.

**11.3** A missing optional thing is a `None`, never an exception path.

## 12 Models and views

**12.1** A surface's state lives in a model class in the daemon, which exposes
`view_state(opened, ...)` returning a plain dict of JSON-safe values.

**12.2** A model NEVER touches a socket, a subprocess or the config directly —
what it needs is passed in (`GameBarModel.view_state` takes a `resolve`
callback). That is what makes every surface testable without a shell.

## 13 Tests

**13.1** One test module per daemon module: `tests/test_<module>.py`,
`unittest`, run with `python3 -m unittest discover -s tests -v`.

**13.2** A test MUST NOT need hardware, `/dev/uinput`, a compositor or the
shell. Synthetic evdev events go in, fake uinput recorders come out.

**13.3** New code is **written so that is possible**: take the outside as an
argument (`proc=PROC`, a canned window list, a `resolve` callback) rather than
reaching for it.

**13.4** Test methods are named for the behaviour they pin, and usually carry
no docstring — the name is the sentence.

## 14 Quick list of what is never in this codebase

f-strings · type annotations · third-party imports · `import *` · tabs ·
`.format()` · a bare `except:` that swallows without logging · a number that
should have been a setting · a comment that restates the line below it.
