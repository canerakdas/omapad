---
name: pad-setting
description: Add, change or audit an omapad configuration setting so it is reachable from config.toml, validated, documented, and reachable from the pad where it should be. Use when adding a number/threshold/timeout to the daemon, when asked to "make X configurable", when a hardcoded value needs turning into a setting, or when omapad check should be catching a bad value and is not.
---

# Adding a setting

The rule this skill exists to enforce:

> **A number in the code is a decision made on the user's behalf.** Anything
> someone could reasonably want different is a setting, and the value in the
> code is its default.

What legitimately stays hardcoded is **a wire format, a geometric identity, or
an implementation trade-off** - and it says in a comment why it is not a
setting. `guide.COLUMN_ROWS` and `gamebar.MAX_ACTIONS` are the shape of a card
and where a hint stops reading as a hint; both carry that sentence. If you
cannot write that sentence, it is a setting.

Read [`docs/components/config.md`](../../../docs/components/config.md) and
[`docs/conventions/data.md`](../../../docs/conventions/data.md) first.

## Where the value comes from

Four files, each deep-merged over the last:

| Layer | File | Written by |
|---|---|---|
| 1 | `config/config.toml` | the checkout - the shipped defaults |
| 2 | `~/.config/omapad/config.toml` | the user, by hand |
| 3 | `~/.config/omapad/mapping.toml` | the mapping wizard |
| 4 | `~/.config/omapad/settings.toml` | the controller menu, last so it wins |

**Never copy the shipped defaults into the user's file.** That freezes them:
the user stops receiving any default that changes later. This is why every
read is `.get(key, default)` and never `data["key"]` - an old user file has to
keep loading when a new setting appears.

## The five steps

### 1. `config/config.toml`

In the right `[section]`, with its default **and a comment saying what it
decides** - not what it is. The comments in that file are the user's manual as
much as `README.md` is; write for someone editing at a keyboard.

```toml
# How long a badge sits dimmed before it starts filling. A fill that begins on
# contact flickers under a shoulder tapped to walk browser tabs - the commonest
# press these buttons take - so it sits still for a moment first. Raise it if a
# flick still flashes, lower it towards 0 to fill from the moment the button
# goes down.
confirm_fill_delay_ms = 60
```

Say what raising it and lowering it *feel* like. A comment that only restates
the name is not worth the line.

### 2. `omapad/config.py`

Read it in `Config.__init__`, in the block for its section, with the default
repeated:

```python
self.gamebar_fill_delay_ms = int(gamebar.get("confirm_fill_delay_ms", 60))
if self.gamebar_fill_delay_ms < 0:
    raise ConfigError("gamebar.confirm_fill_delay_ms must be 0 or more")
```

The attribute name is `<section>_<key>` where that reads well
(`gamebar_height`, `handover_depth`, `osk_layout`). Underscores stay
underscores here.

### 3. Validate anything that can be wrong

**Every value that can be wrong raises `ConfigError`, naming the table and the
key**, so `omapad check` reports it instead of the daemon failing under a
thumb. Ranges, enums, unknown key names, a mode that is not one of two. A
`raise` message starts lowercase - 0 of 84 in the tree start with a capital.

### 4. Reachable from the pad, if it belongs there

A setting belongs on the pad when the question arises **while holding the
thing**: which profile, what the badges print, how hard the motor ticks, how
fast a thumb aims. A setting you decide once at a keyboard does not.

If it does belong there, add it to `CHOSEN` in `config.py`:

```python
"rumble_strength": {
    "attr": "rumble_strong", "table": "rumble", "key": "strong",
    # A twentieth of the motor's range per step: fine enough to stop on the
    # level you meant, coarse enough that reaching it is a few presses.
    "kind": "number", "step": 0.05, "min": 0.0, "max": 1.0,
    "unit": "%", "scale": 100,
},
```

`kind` is `bool`, `choice` or `number`; a number needs `step`, `min`, `max`
and a `unit` that reads in a sentence. **The step size is itself a decision** -
comment it. Then give it a `[[menu.items]]` row, and it becomes reachable from
a binding as `pad:<name>=...` for free. A row that changes a setting the menu
itself prints wants `stay = true`; one you nudge rather than pick wants
`repeat = true`.

### 5. Document it

- `README.md` - authoritative, and updated in the same pass. Find the section
  a user would look in, not a table at the end.
- `docs/components/<component>.md` - the settings line at the foot of the doc.
- If the **plugin** needs the value: put it in the payload. The shell cannot
  read the config, so a height, a lean, a delay all travel over the socket
  even though they look like shell constants. See the `pad-surface` skill.

## Verifying

```bash
./bin/omapad check                  # parses, and names a bad value
python3 -m unittest discover -s tests
systemctl --user restart omapad     # required after ANY config change
```

Then prove the validation works by breaking it on purpose: put an
out-of-range value in `~/.config/omapad/config.toml`, run `omapad check`, and
confirm it names the table and the key. A setting whose error message does not
say where the mistake is has not been validated, only read.

## Auditing for settings that should exist

When reviewing, a literal in the daemon is suspect if it is any of:

- a duration, a delay, a timeout, a poll interval
- a speed, a step, a threshold, a deadzone
- a size, a height, a count of rows or slots
- how far something moves, or how long an animation runs

and it is **not** a wire format, a geometric identity or a commented
trade-off. The other half of the rule is worth checking too: *every capability
should be reachable from config, not only from the shape it first shipped in*.
A role that cannot carry the option its equivalent binding carries is a gap,
not a design.
