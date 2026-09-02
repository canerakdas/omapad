---
name: pad-bindings
description: Write or review gamepad button bindings for omapad - an application profile ([profile.<app>]), a layer, or a keyboard page. Use when asked to "bind an app to the pad", "add a profile for <app>", "which button should X be", "make the controller work in <app>", or when reviewing bindings for consistency. Enforces the face-button contract in docs/conventions/bindings.md.
---

# Binding an application to the pad

You are placing at most four things on a controller that a person already has
reflexes for. The pad has fourteen buttons and every one of them already means
something, so the work is **spending**, not filling.

Read [`docs/conventions/bindings.md`](../../../docs/conventions/bindings.md)
before writing a line. It is normative; this file is how to apply it.

## The contract, in one table

| Button | Role | The question it answers |
|---|---|---|
| **A** | Commit | confirm, enter, activate |
| **B** | Leave | back, escape, up one level |
| **X** | Do | what does this app ask you to *do*, most often? |
| **Y** | Reach | what is not on screen - a switcher, a search, a menu |

A and B are not yours. X and Y are.

## The procedure

### 1. Find the class, not the name

```bash
hyprctl activewindow | grep -E '^\s+(class|initialClass|title):'
```

`match` is a **case-insensitive substring** of the class and may be a list.
Two traps, both of which have bitten this config already:

- An Omarchy **webapp** has a class like
  `chrome-discord.com__channels_@me-Default`, which matches `"chrome"` as
  squarely as it matches `"discord"`. **The first profile that matches wins**,
  so a profile for a webapp must be declared *before* `[profile.browser]`.
- Forks do not share a substring: Discord's are `vesktop`, `webcord`,
  `legcord`, `armcord`, and each needs naming.

### 2. Ask the four questions, in this order

1. **What can a pointer on a sofa not reach?** A target in a screen corner, a
   strip of thumbnail-sized icons, anything timed. Those earn a button. A
   thing a cursor reaches in one push of a stick does not.
2. **What is the app's verb?** One thing, the most pressed. → **X**
3. **What is the reach?** A switcher, a search, another view. → **Y**
   No reach? Leave Y alone - the base layer's right click is one - or give it
   a second verb, and say so in a comment.
4. **Does the app own L or R?** Tabs, a game, a stream. Then the workspace
   moves to a `confirm = true` hold, never to a plain one.

Only if a fifth thing is genuinely needed: **L3** (`LSTICK`). It duplicates
X's middle click at the base layer, which is what makes it the cheapest button
on the pad. Then **R3**. Then stop, and write a keyboard page instead.

### 3. Check what you are taking

What a profile spends, it spends **at rest**: binding X takes that app's middle
click, binding Y its right click, binding L3 the middle click's second copy.
Write that cost in the comment. Every shipped profile does, and the comments
are the ledger of what is still free.

**It stops where the modifier starts.** `ZL` + X is float / tile and `ZL` + B
closes the window in every application, whatever the profile does with those
buttons at rest - which is what makes the guide's window page true, since the
guide knows nothing about profiles. An app that really does want one of them
names the layer, and pays for it there:

```toml
[profile.myapp.window]      # read in [bindings.window]'s place, this app only
X = { tap = "exec:my-window-thing", desc = "..." }
```

Nothing ships doing that. A key in a profile table that is neither a layer name
nor `match` / `bindings` / `osk` / `left_stick` / `right_stick` is a typo, and
`omapad check` names it.

### 4. Write it

```toml
# Ahead of [profile.browser] if the app can be a webapp.
[profile.myapp]
match = ["myapp", "fork-of-myapp"]
# Only if the app answers focus keys somewhere other than under the pointer:
# right_stick = "scroll"

[profile.myapp.bindings]
# One comment per line, saying what it does *and what it cost*.
X = { tap = "key:CTRL+N", desc = "New note", short = "Note" }
Y = { tap = "key:CTRL+P", desc = "Jump to a note" }
```

Rules the file itself enforces:

- Bindings are **inline tables on one line** - a binding is one thought.
- `desc` is a phrase, for the guide. Write one wherever the derivation would
  print a dispatcher path or a script name.
- `short` is **one word**, for the game bar, and is **required** when the
  first word of `desc` is not the meaning ("New tab" cuts to "New").
  `hold_short` likewise.
- `nop` unbinds a button in this app without giving it anything.
- Never copy the shipped defaults into `~/.config/omapad/config.toml`; the
  user's file is deep-merged over this one, and a copied default freezes.

### 5. Verify

```bash
./bin/omapad check                    # parses every binding, names a bad one
systemctl --user restart omapad       # required after ANY config change
./bin/omapad ctl guide toggle         # read the scheme back as words
```

`omapad check` catches a malformed action. It cannot catch a binding that is
merely *wrong*, so read the guide page: if a row's words do not say what you
meant, the binding needs a `desc`, not a different action.

## When it wants a keyboard page, not a button

The pad has four face buttons and an app can have forty shortcuts. Past the
budget above the answer is **not** a fifth button: a profile can lend the
on-screen keyboard **a page of its own**. It joins the cycle L/R already walk -
`abc`, `&123`, `Fn`, then this one - for as long as that window is in front,
and leaves with it.

Which one a thing wants:

| Give it a **button** | Give it a **page entry** |
|---|---|
| pressed *while doing something else* - a mute mid-sentence, an interrupt, an erase | typed at or aimed at anyway - a URL, a command, a search, a sentence |
| has to be instant | you were already going to open the keyboard |
| a pointer cannot reach it | the keyboard is where the caret already is |

```toml
[profile.shell.osk]
label = "Term"                     # what the page is called in the cycle
keys = [
  { label = "Paste", action = "CTRL+SHIFT+V" },
  "git status",
  { label = "Update", text = "sudo pacman -Syu" },
]
from = "tac ~/.bash_history | awk '!/^#/ && length > 2 && length < 60 && !seen[$0]++' | head -8"
ttl = 10
limit = 8
```

| Entry form | Does |
|---|---|
| `"git status"` | types the string; the label is the string |
| `{ label = ..., text = ... }` | types the string under its own name |
| `{ label = ..., action = "CTRL+SHIFT+V" }` | sends a **chord**, written the way `[osk.keys]` writes one |

An entry does **exactly one** of `text` and `action`, and both are parsed at
load, so `omapad check` names the profile rather than the daemon failing when
the page is drawn.

What decides whether something fits:

- **Four rows is the whole page.** A short entry shares a row, a long one
  takes it alone, and the rest do not fit - eight short entries is all of it.
  The shipped browser and Discord pages are both exactly eight, and each names
  in a comment what did *not* make it, so the next person can trade one out
  instead of guessing.
- **An entry types; it does not run.** That leaves `ZR` - Enter, then the
  keyboard away - to run it, which is what makes a command entry worth having.
- **`keys` is drawn first, then `from`.** `from` is a shell command whose
  output is one entry per line: how the commands somebody actually ran get
  onto the keyboard without omapad knowing anything about their shell. `limit`
  (default 8) caps the two together; `ttl` (default 10 s) is how long the
  output is reused before the command runs again.
- **A chord entry is for a key that is wrong in exactly one app.** The
  keyboard's bottom row has Paste as `Ctrl+V`, right everywhere except a
  terminal - so the terminal's own paste goes on its page rather than changing
  that key for everybody.

If you use `from` with bash, put this in the config's comment beside it:
**bash only writes its history file when the shell exits**, so what the
terminal in front has typed today is not in it yet. The page is worth little
without one line in `~/.bashrc`:

```bash
PROMPT_COMMAND='history -a'
```

Another history tool changes only the command, not the mechanism:

```toml
from = "atuin history list --reverse --format '{command}' | head -8"
```

## Changing a key for every app instead

If a key is wrong in *every* app rather than one, it is `[osk.keys]`, not a
page. Overrides are keyed by **what the key does by default**, either half is
optional, and a bare string is taken as the label:

```toml
[osk.keys]
BACKSPACE = ""                # relabel it
close     = { label = "" }    # the key that puts the keyboard away
CAPSLOCK  = { action = "LEFTSHIFT+RIGHTSHIFT" }
```

A key that appears on more than one page is overridden on all of them, and
`omapad check` rejects an action that does not parse. The shipped `CAPSLOCK`
row is the worked example of why this exists at all: Omarchy's own input
layout maps the Caps Lock key to Compose, so sending `KEY_CAPSLOCK` toggles
nothing - and the same option makes *both shifts together* the way to toggle
it.

## Reviewing bindings that already exist

Walk the layers - `base`, each `[layers.*]`, `osk`, `menu`, `guide`, `game` -
and each profile, and ask of each:

| Check | Fails when |
|---|---|
| A commits | A does something unrelated at a tap, with no `hold_desc` carrying Enter |
| B leaves | B is not back / escape / up / close |
| No duplicate face buttons | two of A/B/X/Y fire the same action in one layer |
| A meaning does not move | the same key sits on different buttons in two layers a user crosses (the terminal and the on-screen keyboard are the pair that matters) |
| The bar can say it | `desc` has more than one word and there is no `short` |
| The cost is written | a profile binding with no comment saying what it displaced |
| The app's button is safe | a plain binding on a button a game holds, with no `confirm = true` and no `reaches_past = false` |
| The budget was not overspent | a profile binding more than the four it has (X, Y, L3, R3) - what is left over wanted a keyboard page |
| A page entry is a page entry | a `keys` row doing what a button should do, or more than eight of them |

Report each finding as: the table, the button, the rule, and the one-line fix.
Do not rewrite a documented exception - `docs/conventions/bindings.md` ends
with the ledger of them, and a new exception belongs in that table with its
reason before it belongs in the config.

## The actions you have to spend

```
key:CTRL+SHIFT+M      a key or chord through the virtual keyboard
click:left|right|middle|back|forward
scroll:up|down
exec:<command>        spawned, survives the daemon
hypr:<lua>            hl.dsp.* - see docs/conventions/lua.md
osk:*  menu:*  guide:*  map:*  surface:*   the surfaces
mode:toggle|desktop|game
focus:*  snap:*  pad:*
nop                   bound to nothing, on purpose
```

Binding keys: `tap`, `hold`, `hold_ms`, `desc`, `short`, `hold_desc`,
`hold_short`, `on_release`, `rumble`, `confirm`, `confirm_ms`, `reaches_past`.

The full grammar, with what each one costs, is in `config/config.toml`'s own
header comment - that file is the manual as much as `README.md` is.
