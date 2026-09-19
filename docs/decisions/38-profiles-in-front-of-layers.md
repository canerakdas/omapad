# 38. The modifier the apps kept taking · ✅ Done · S

Asked for from the sofa: *in Discord, `LT` + `B` should close the window - the
LT modifier can work the way it does in every other application.* It did not,
and 09 is why: a profile's bindings were resolved in front of **every** layer,
so `[profile.discord]`'s `B` - deafen - answered the window layer as well, and
`ZL` + `B` deafened instead of closing. The same held everywhere a profile
existed: `ZL` + `X` opened a browser tab rather than floating the window, `ZL`
+ `L` / `R` switched tabs rather than sending the window to a workspace, and
the browser's `right_stick = "scroll"` scrolled the page while `ZL` was down
instead of moving the window.

**Nobody had ever wanted that.** The ledger says so in its own words: every
shipped profile records the window-layer reach as a *price* - "it costs `ZL` +
`X`, float / tile", "`ZL` + left stick no longer pins the window" - and 37 went
as far as choosing which button carried an interrupt in order not to pay it.
A cost that four profiles pay and none of them wants is not a feature, and
37's lesson - *a profile's real price is what the button does in the window
layer* - was the premise being wrong rather than a rule to design around.

**The guide had already decided this.** `build_pages()` reads `[bindings.*]`
and knows nothing about profiles, so the window page has always printed
*Close the window* on `B` no matter what was in front. Under the old
resolution that page was a lie in any app with a profile; under the new one it
is true again, and there is nothing profile-shaped for it to learn.

**So a profile stops where a modifier starts.** `[bindings]` is the app's
scheme *at rest*: it answers the base layer and game mode - which is the same
desktop with a bar on it - and a held layer keeps its own table. `stick_roles`
follows the same line: while `ZL` is down both sticks belong to the window.

**And the capability is still reachable, by name.** An app that really does
want a window op of its own writes `[profile.<app>.window]`, read in
`[bindings.window]`'s place for as long as it has focus - the layer named, not
inherited by accident. Nothing ships with one. A profile key that is neither a
layer nor `match` / `bindings` / `osk` / `left_stick` / `right_stick` raises at
load, because `[profile.shell.windows]` would otherwise be a table that simply
never fires and nothing on screen would say why.

**Nothing in the daemon changed** - the fourth time in a row. It is thirty
lines of `config.py`, and what it gives back is one sentence: the left trigger
means the same thing in every application.
