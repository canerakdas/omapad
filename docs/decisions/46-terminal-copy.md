# 46. The copy a terminal had no button for · ✅ Done · S

Asked for as a binding and answered as one, plus the thing that made it
invisible: *terminalde sagda gosterdigimiz tuslara copy'i de ekleyelim, cok
kullanisli oluyor kopyalamak*.

**The binding was the easy half.** `[profile.shell]` had spent X on Backspace,
Y on the paste and L3 on `Ctrl+L`, and R3 was still `click:back` - a click no
terminal answers, which makes it the last cheap button a terminal has. So
`RSTICK = { tap = "key:CTRL+SHIFT+C", desc = "Copy" }`, shifted because the
unshifted one is the interrupt already sitting on Y's hold. It closes the hole
item 37 wrote down as the price of the paste: the profile had spent both middle
clicks, so a selection dragged with ZR could be made and never put anywhere.
Now it goes to the clipboard Y pastes from.

**"Sagda" is what the item is really about.** The bar's row of hints was
`kinds = ["face"]`, and the argument for that - the face buttons are the half
of the pad that changes under you - had quietly stopped being the whole truth:
`docs/conventions/bindings.md` says a profile's budget is *four*, X, Y, L3 and
R3, and every shipped profile spends the stick clicks. So the row was printing
two of a profile's four and hiding the rest, and a copy put on R3 would have
been bound and unmentioned on the one surface whose job is to say what the pad
does. `HINTED` is `("face", "stick")` now. The shoulders and triggers stay out
for the reason they always did: they mean the same thing wherever the scheme
goes.

`MAX_ACTIONS` is still 3, so four bound buttons means one falls off in
`PREFERRED`'s order - thumbs-first, so L3 goes. That is the right one to lose:
L3 is the cheapest of the four wherever it is spent, and the guide is where the
whole scheme is read. In a terminal the row now comes to *Backspace*, *Paste*,
*Copy*, with `Ctrl+L` a page away.
