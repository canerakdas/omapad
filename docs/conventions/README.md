# Style guides

One guide per language in the project. They are **normative**: a rule here is
what review asks for, and what a reader may assume when reading anything in
the tree.

| Guide | Applies to |
|---|---|
| [`python.md`](python.md) | `omapad/`, `tests/`, `assets/` — 39 files |
| [`qml.md`](qml.md) | `shell-plugin/` — 10 files |
| [`bash.md`](bash.md) | `bin/omapad`, `install.sh` |
| [`lua.md`](lua.md) | the `hypr:` expressions inside `config/config.toml` |
| [`data.md`](data.md) | TOML, the socket payloads, JSON manifest, SVG, unit and udev rule |
| [`bindings.md`](bindings.md) | what each button means, and what a profile may take |
| [`naming.md`](naming.md) | file names and folder structure, for every kind of file |
| [`writing.md`](writing.md) | the words a user reads - menu rows, `desc` and `short`, CLI output |

## How to read a rule

| Word | Means |
|---|---|
| **MUST** / **NEVER** | No exceptions. A violation is a bug in the change, not a preference. |
| **SHOULD** | Follow it unless you can say in one sentence why this case is different — and then say it in a comment. |
| **MAY** | Both are fine; match what the file already does. |

Rules are stated with the reason attached wherever the reason is not obvious.
A rule with no reason is a rule nobody will keep.

## These rules were measured, not invented

Every number in these guides came from the tree as it stands, so the guide
describes the code rather than an intention about it. The measurements, at the
time of writing:

| | |
|---|---|
| Python lines over 79 columns | 0.7% (182 of 26 000); none over 88 |
| Tabs, trailing whitespace | 0 |
| f-strings, `.format()`, type annotations | 0 |
| `%`-formatted strings | throughout |
| Double-quoted strings | 7 119, against 129 single (all inside a double-quoted string) |
| Module docstrings | 39 of 39 files |
| Function docstrings | 51% in `omapad/`, where the name is not the whole answer |
| Comment lines | 14% of `omapad/`, 8% of `tests/` and `assets/` |
| `raise` sites starting with a capital | 0 of 84 |
| British spellings in prose | 94, against 54 American - all of them API names |
| QML files opening with a `//` header comment | 10 of 10 |
| Odd indent in QML | 5 lines of 2 489 |
| Bare assignments in a QML `applyState` | 0 (37 were fixed when this guide was written) |

When a rule and the code disagree, one of them is wrong — say which in the
change that resolves it.
