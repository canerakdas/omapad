# Bindings guide - `omapad/guide.py` + `shell-plugin/Guide.qml`

What every button does, badged like the button itself. Read-only, and
deliberately so: seeing the map is most of what was wanted, and `[osk.keys]`
already lets a key be changed without touching Python.

## Descriptions are derived, not tabulated

`describe(spec)` turns an action into English, so `click:left` is a left click
whichever button carries it and no second table can drift out of date. Where
the derivation is thin - a Lua dispatcher, a script name - the binding says
what it means outright:

```toml
L = { tap = "hypr:hl.dsp.focus({ workspace = 'r-1' })", desc = "Previous workspace" }
```

`_describe_key`, `_describe_hypr`, `_describe_exec`, `_describe_pad` are the
per-verb halves; `CLICKS`, `KEY_NAMES`, `OSK_TEXT`, `MENU_TEXT`, `GUIDE_TEXT`,
`MAP_TEXT`, `SURFACE_TEXT`, `PAD_NAMES`, `MODE_TEXT`, `LOCK_TEXT`, `FOCUS_TEXT`,
`SNAP_TEXT`, `STICK_ROLES` are the words they use, and `BRIEF` is the one word
the bar gets instead.

## The bar's reading of the same row

`button_row(button, spec, layout, brief=True)` is the guide's own words cut to
one, for the game bar: `short` on the binding, else the first word of its
`desc`, else `brief_of(action)`. `BRIEF` holds only the actions `_shorten`
gets wrong - "On-screen keyboard" would cut to "On-screen", and a right click
called "Right" reads as a direction beside a badge - and it is keyed by action
rather than by the sentence, so rewriting `OSK_TEXT` cannot silently strip the
short form off. Everything else is the first word, which is the verb often
enough to be the rule.

It **must not** say something the guide does not: `short` is one meaning said
shorter. See [`../conventions/bindings.md`](../conventions/bindings.md), which
also says when a binding is obliged to carry one.

## Badges: which console is printed

This is the module that answers what a badge **prints**, which is a different
question from which physical button a name means:

- `LAYOUTS` holds one table per console (`nintendo`, `xbox`, `playstation`),
  `badge_of(button, layout)` answers it, `DEFAULT_LAYOUT` is `nintendo`.
- `KINDS` says which *shape* a button is drawn as - face, shoulder, trigger,
  D-pad arm, system pill - and the plugin draws it.
- `[device] layout` picks one; `auto` follows the profile through
  `config.PROFILE_LAYOUTS`. The daemon sets `guide.layout` and
  `gamebar.layout` in `attach()`, and **nothing else may reach for a label
  table**.
- Every label of every layout must have art or it falls back to typed text;
  `tests/test_assets.py` enforces that.

## Pages

Rows are grouped by the **region of the pad a thumb finds them in**
(`REGIONS`), not by layer order, because that is how you look for a button you
are holding. `build_pages(config, available, layout)` groups
(`_groups_for`), paginates (`_paginate`, `COLUMN_ROWS`) and balances the
columns (`_balance`). The guide's own layer is not a page and is not
printed: those bindings are how you are reading the page. `available` is which
buttons the connected pad actually has, so a pad with no Capture does not have
it printed.

## Payload - `guide.sock`

```
open, page, count, title, note, cols: [[ {b, k, d, h} ]]
```

`b` badge text, `k` badge kind, `d` what a tap does, `h` what a hold does.

## The panel

`Guide.qml`. There is nothing to press - it is read-only by design. Overlay
layer, no keyboard focus, empty input region. The badge is the point: a
binding printed as `A` in a list is a letter, but printed as a round face
button next to a shoulder cut away at one corner it is the thing under your
thumb. Colours come from the theme, never from a console's palette, which
would fight every Omarchy theme but one. The shape is filled with the accent
either way, because on a card that is nothing but badges the badge is what the
eye hunts for. What `[ui] badge_style` decides is the label: `filled` sets it
on top in the card's own text, because an accent readable as a heading is not
always readable as a letter inside a badge, and `stencil` punches it out, so
what reads the letter is the card showing through it.

Under the rule at the foot of the card, `page` of `count` is drawn as
`omarchy.workspaces` draws the desktop - numbers, the current one the same
square - so a page you can walk to reads as one. It is hidden, rule and all,
on a guide that is a single page.

Settings: `[guide] socket`, `[bindings.guide]`, `[ui] badge_style`.
