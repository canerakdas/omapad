# 95. Words over a run of tiles · ✅ Done · M

Asked for from the sofa: *menuye baslik ekleme ozelligi ekleyelim, yazi
yazilabilsin. menu altindaki ogeleri basliklara ayirmada kullanacagim. font
size silver ratio'ya gore kendi icinde ayarlansin ve arka plani olmasin bu
alanin. sadece edit modunda ustune gelinebilsin ve istenilen yere eklenip
cikarilabilsin* - a heading on a menu page, with words somebody types, to
split the tiles under it into sections; its size set from itself by the silver
ratio, no ground behind it, reachable only while the page is being arranged,
and put down and taken off wherever it is wanted.

**What a page had for a section was a `row_break`**, which ends a row and says
nothing about why. A group of tiles that belong together was a group only to
whoever wrote the config: from the sofa it was a gap. A heading is the break
with the reason printed on it, and it is built as exactly that - `place` starts
one on a row of its own and raises the floor under it, so nothing after it
backfills a hole above it.

**What was built:** `control = "heading"` in `menu.py`; RT with an empty hand
while arranging puts one over the tile in front and brings the keyboard up
over the menu to type it; on a heading X deletes it and LT types it again;
carried, it moves through the order rather than into a cell; outside the mode
the selection, the stick and the pointer walk past it. The words live in
`layout.toml` beside the page's order. `Menu.qml` draws it with a Repeater of
its own - words only, `height / silver²` pixels tall, at the book weight - and an outline only
while arranging. [`menu.md`](../components/menu.md) has the mechanism.

**The words are typed on the keyboard omapad already has.** It is the one
text entry the pad knows, walked the same way whether it types into a window
or not, so there is nothing new to learn to write a heading. What it types is
taken before it reaches uinput (`HeadingKeys`) and turned back into characters
with the same table that turns a string into chords, which keeps the active
layout's `ş` a `ş`.

**Rejected:** a heading as a tile pinned to a cell, the way every other tile
is moved since 52. A pin is out of the flow, so the tiles meant to be under it
flow around it - and up past it, into whatever hole is above. The order is the
one thing that can say "these come after this", so a heading moves through it.

**Rejected:** a heading in the strip when it is taken off. The strip holds
what the config has so it can be put on another page; a heading made from the
pad is words and a place, and there is nothing of it to put back.

**Rejected:** a type size from the ladder. The ladder is for type beside type,
and a heading is read against the box it stands in, so the box decides: one
part in `silver` squared of its height is the words, and making it taller is how it is
made louder. It was one part in `silver` at first, at a semi-bold weight, and
from the sofa that was *cok buyuk ve kalin* - too big and too heavy: a one-row
heading twice the size of anything else on the card reads as the page's title.
The ratio squared, at the book weight, puts it a rung over a tile's name.

**Rejected:** a separate text field drawn in the menu, with its own caret and
its own keys. That would be a second keyboard to walk, and one that could only
ever type here.

**What it costs:** the keyboard and the menu are up together for the first
time, and the menu has to stand down under it in three places that ask which
surface is on top. `menu.typing` is what they ask.
