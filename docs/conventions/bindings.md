# Button bindings

Rules here are normative in the same way the language guides are; see
[`README.md`](README.md) for how MUST / SHOULD / MAY are meant. They apply to
every binding written in `config/config.toml` - `[bindings.<layer>]`,
`[bindings.osk|menu|guide|game]`, `[profile.<app>.bindings]` - and to anything
a user is told to write in `README.md`.

A pad has fourteen buttons and a desktop has thousands of things to do, so the
question is never "is this button free?" but **"does this button already mean
something?"**. Someone who has used the pad for a week presses A without
deciding to. That reflex is the only thing this project has instead of labels,
and every binding either spends it or feeds it.

## The face buttons

Four buttons, four meanings, and they hold in every layer, every surface and
every application:

| Button | Role | Means | On the desktop | In the menu | In the keyboard |
|---|---|---|---|---|---|
| **A** | **Commit** | confirm, enter, activate, open what is selected | `key:ENTER` | `menu:press` | `osk:press` |
| **B** | **Leave** | back, escape, cancel, up one level, out | `key:ESC` | `menu:back` | `osk:close` |
| **X** | **Do** | the app's own verb - the thing you press most often *to* what is in front of you | middle click | leave outright | Backspace |
| **Y** | **Reach** | what is not on screen: a menu, a switcher, another view | right click | the bindings guide | Space* |

\* The keyboard has no Reach worth having, so Y carries a second Do. That is
allowed; see the rules below.

**Why this pairing and not the other one.** A and B are the console standard
and are not ours to move. X and Y are, and the split follows the thumb: **X is
nearer the rest position than Y**, so the button pressed more often is X. That
is also what the tree already did before the rule was written - X carried the
new tab, the paste and the Backspace, and Y carried the context menu, the
window popped out and the call answered.

### Rules

1. **A MUST commit and B MUST leave.** No layer, surface or profile may give
   them an unrelated meaning at a tap - except by rule 2.
2. A profile **MAY** take A or B when the app's most-pressed control is not
   reachable on screen at all, and then it **MUST** keep the general meaning
   on the hold with a `hold_desc` naming it. `[profile.discord]` is the whole
   of this exception in the shipped config: the mute and deafen buttons sit in
   a thumbnail-sized strip in the furthest corner of the screen, and Enter and
   Esc ride the holds.
3. **X is the app's verb and Y is the reach.** Where an app has no reach worth
   having - a terminal's right-click menu is two entries in kitty and nothing
   at all in foot - Y **MAY** carry a second Do. The reverse is not allowed:
   two reaches with no verb means the thing you actually do has no button.
4. **NEVER spend two face buttons on one meaning.** A duplicate teaches
   nothing and the pad has four of these. This is the rule the shipped
   `[bindings.menu]` was breaking when it was written down: X and Y were both
   `menu:close`, on a surface four other buttons already closed.
5. **A binding that means the same thing in two places MUST sit on the same
   button in both.** Backspace is X in `[bindings.osk]`, so Backspace is X in
   `[profile.shell.bindings]` - those are the two surfaces a command is typed
   across, and a key that moved between them would be worse than no key.
6. **Every override says what it costs.** The cost is what the button did *at
   rest* in that app - X's middle click, Y's right click - and nothing more: a
   profile stops where a modifier starts, so `ZL` + X is float / tile and
   `ZL` + B closes the window in every app. Write the cost in the comment
   beside the binding; the shipped profiles all do, and that ledger is how the
   next person knows what is still free.
7. **The modifier is the desktop's, not the app's.** A profile's `[bindings]`
   are the scheme at rest. An app that genuinely wants a window op of its own
   **MUST** say which layer it is taking - `[profile.<app>.window]`, read in
   `[bindings.window]`'s place - and nothing ships doing it. The rule is what
   makes the guide's window page true: the guide knows nothing about profiles.

## Everything that is not a face button

These carry fixed jobs. A profile may take one, under the condition in the last
column, and must say what it cost.

| Control | Job | A profile may take it |
|---|---|---|
| D-pad | the selection, or the arrow keys | rarely - it is how every surface is walked |
| **L / R** | previous / next workspace | yes, and then the workspace **MUST** move to the hold with `confirm = true` - see `[profile.browser]` |
| **ZL** | holds the window layer | **never**: a layer trigger has no binding of its own, in any layer or profile |
| **ZR** | left click | **never** without `reaches_past = false`: in a game ZR is the trigger |
| Left stick | the pointer | yes, by naming a `left_stick` role |
| Right stick | the wheel; `focus` in game mode | yes, by naming a `right_stick` role - `[profile.browser]` and `[profile.shell]` both do |
| **L3** (left stick click) | middle click, which X also carries | **the spare.** It is deliberately a duplicate, which makes it the cheapest button on the pad to spend - three shipped profiles spend it |
| **R3** (right stick click) | back (mouse 4) | yes |
| MINUS | the on-screen keyboard | no: `reaches_past = false` is what keeps it off a game's Back button |
| PLUS | the controller menu | no, same reason |
| HOME | tap: next window, hold: switch mode | no: the hold is the way back to the desktop |
| CAPTURE | screenshot / region | yes, but **NEVER as the only home for anything**: the button does not exist in XInput mode |
| MINUS + PLUS | the menu, everywhere, past a game | no: it is the only door left over a cloud session |

## Saying what a binding means

The guide derives its words from the action, so most bindings need no `desc`
at all: `click:left` is a left click whichever button carries it. Write one
where the derivation is thin - a Lua dispatcher, a script name, a key chord
whose meaning is the app's rather than the keyboard's.

```toml
X = { tap = "key:CTRL+T", desc = "New tab", short = "Tab", hold = "key:F5", hold_desc = "Reload" }
```

| Key | Who reads it | Rule |
|---|---|---|
| `desc` | the guide | a phrase. **SHOULD** be written wherever `describe()` would print a dispatcher path or a script name |
| `short` | the game bar | **one word**, and **MUST** be written when the first word of `desc` is not the meaning - "New tab" cuts to "New" |
| `hold_desc` / `hold_short` | the same two | the same rule for the other half |

The bar prints one word because it is glanced at over the top of a game with
three slots; the guide prints the phrase because it is a page you sit and
read. They **MUST NOT** disagree about what a button does - `short` is the
same meaning said shorter, never a different one. `[gamebar] brief = false`
puts the phrase in both places.

The bar never prints a gesture that means the same wherever you are
(`[gamebar] omit`, `key:ENTER` and `key:ESC` by default) - which is to say
**A and B are not printed at all** while they keep their meaning, and start
being printed the moment a profile takes them under rule 2. That is the rule
above enforced by what you can see.

The row is the **face buttons and nothing else** (`[gamebar] kinds`), for the
same reason: they are the half of the pad a profile rewrites, so a profile's X
and Y are exactly what the bar has to say. A shoulder means the same thing
wherever the scheme goes, and repeating it costs one of three slots.

## Writing a profile for an application

The question a profile answers is not "what are this app's shortcuts?" - it is
**"what does this app ask for that a pointer on a sofa is worst at?"**. Four
things is the whole budget, because four is what X, Y and the two stick clicks
come to.

1. **Find the controls a pointer cannot reach.** A target in a screen corner, a
   strip of icons the size of a thumbnail, anything timed. Those go on the pad
   first; anything a cursor can hit in one push of a stick does not need a
   button.
2. **Name the app's verb, and put it on X.** One verb, the one pressed most:
   a new tab, a paste, an erase, a mute.
3. **Name the reach, and put it on Y.** A switcher, a search, a context menu,
   another view. If there isn't one, leave Y alone - the base layer's right
   click is a reach - or give it a second verb.
4. **Leave A and B alone** unless rule 2 above applies, and then keep Enter
   and Esc on the holds.
5. **Spend L3 before anything else** when a fourth is needed: it duplicates X
   at the base layer, so it is the only button that costs nothing twice.
6. **Where the app owns L or R** - a browser's tabs, a game - move the
   workspace to `confirm = true`, never to a plain hold: the app sees that
   button too, and only an announced, counted-down hold is safe over one.
7. **Say what the stick does** if the app answers `focus` keys somewhere other
   than under the pointer (`right_stick = "scroll"`, as the browser and the
   terminal both do).
8. **Write the cost of every line** in the comment beside it, and check the
   result against the guide: `./bin/omapad check`, then
   `./bin/omapad ctl guide toggle`.
9. **Leave the window layer alone.** It costs nothing to keep and it is what
   `ZL` means everywhere; take a button in it only by naming the layer, and
   only with a reason written beside it.

An app whose bindings are more than a page of keys wants a **keyboard page**
(`[profile.<app>.osk]`) rather than more buttons. Four rows, eight short
entries, and the pad keeps its scheme.

## The ledger: where the shipped config bends a rule

Kept here rather than in the commit message, because a rule with an
undocumented exception is a rule nobody keeps.

| Where | Rule | Why |
|---|---|---|
| `[profile.discord]` | 1 - A and B are mute and deafen | Rule 2's exception: they are the app's most-pressed controls and its worst targets. Enter and Esc are on the holds. |
| `[bindings.osk]` | 3 - Y is Space, a second Do | A keyboard has no reach; Space is the second-most-needed key on it. |
| `[profile.youtube]` | 3 - Y is fullscreen, a second Do | The reach is the search box, which needs the on-screen keyboard anyway, so it moves to L3. Fullscreen is pressed on every video and is the pointer's worst target: a corner icon behind an overlay that hides itself. |
| `[profile.shell]` | 3 - Y is paste, a second Do | A terminal's right-click menu is two entries in kitty and ghostty and nothing at all in foot and alacritty. |
| `[bindings.guide]` | 1 and 4 - every button closes | The guide is read, not used: it has one job, turning the page, and everything else is a way out of a surface you opened by mistake. |
| `[bindings.window]` | A is fullscreen, not Enter | The layer acts on a window rather than on a selection, and fullscreen is the affirmative one. B still closes, X still acts, Y still moves it elsewhere. |
