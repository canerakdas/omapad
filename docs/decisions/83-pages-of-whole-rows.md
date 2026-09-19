# 83. Pages that came to whole rows · ✅ Done · S

Asked for from the sofa: *default settings icin mevcut navigasyon altindaki
kartlari daha iyi bir sekilde gruplandirip boyutlandir.*

The card is `[menu] columns` wide whatever is on it, and most of the shipped
pages were not. `Workspaces` was one card three cells square on a page twelve
wide. `Display` was the same card with nine columns of white beside it and
three bars in a band underneath. `Now` was two whole rows and then a bar, three
small squares and a stopwatch reaching column eight in one row and column two
in the next. `Apps` filled its first band and put two small squares under it
with two thirds of the band empty. Every one of those reads as a drawing fault
rather than as air, and none of it is what the grid was for.

**The arithmetic is the design, not a tidy-up after it.** A page is bands and a
band comes to twelve, so the spans are what gets adjusted until it does. Two
things would not bend for it and did not: a circle is two cells square -
knob, dial, clock and stopwatch are one drawing at one size - and nothing
takes a span wider than six, because `build` refuses a span wider than the
columns there are and `[menu] columns` is a setting somebody may turn down.
`pad-menu.md` carries both rules now.

- **`Now` is four squares and a transport.** The keyboard gave up two cells
  and the stopwatch came up out of the tail: four and four and two and two is
  the one tiling of twelve that holds a keyboard, a title, a ring and a dial
  at the heights each is drawn at, and `Previous`, `Next` and `Mute` take four
  cells each in the row under them. Three rows, nothing left over. The
  keyboard is still the first tile and still twice the ring; the eight equal
  squares its comment was written against are not what it stands among.
- **`Brightness` went to `Display`, which is where 78 said it was.** The item
  is marked done, the README says so and three tests said so, and the config
  never got the change - which is why those three tests were failing on this
  branch before any of this was written. The page's own rule decides it: how
  bright the screen is follows the light coming in the window, how loud moves
  with the film.
- **`Display` is two halves.** The `Screen` card is six by two - three verbs
  and a heading fit a card that tall, the way `Power` holds five rows in three
  - with the brightness bar beside it and the three omapad draws over the
  desktop under them. Six-cell bars, the longest travel on the surface, for
  the three numbers you set by looking at what they did.
- **`Apps` is one tile that says what the machine is for.** Steam at six by
  two and six tiles of three by two under and beside it, where it was one of
  four and two stragglers. Three cells is also where a name stops being cut in
  half and where the line under it has somewhere to go.
- **`Audio` is two lists the width of the names in them.** `Built-in Audio
  Analog Stereo` was three cells of elision on both cards; they are six each
  now, and the dictation switch takes half the row under them.
- **`System` lost its row break and gained its corner.** `Update` is three by
  two and `Omarchy menu` stands in the strip under it - which the break used
  to hold open and nothing could reach. Four cards and a door in three rows.
- **`Controller` ends flush.** `Hold time` is four cells, which is the one
  that took its feedback band from eleven to twelve. Nothing else on that page
  moved; it was already the page the others are now.
- **The sticks page is two rows with a dial at each end**, one under each
  thumb: four bars of four between them, twenty-four cells, no break. It was
  three rows with the two dials in the corner of one that was two thirds
  empty. A break would not have done it - a break counts from the foot of
  everything flowed before it, and a dial two rows tall pushes the line under
  it past its own second row.
- **The first-run tile is half a row and has a neighbour.** Six cells with the
  keyboard beside it rather than three with a hole, and deliberately **no**
  break under it: the first press anybody makes on this page is a direction,
  and a tile alone in its row answers only one of the four. Its page is two
  rows of twelve as well.

**`Workspaces` is the one page this could not fix, and the reason is content.**
It holds one card - four window verbs - and the card is six cells now rather
than three, which is as far as sizing gets you: a page with one thing on it is
half empty at any width. What it wants is a second card, and the page is named
for what it has not got. The vocabulary is already in the shipped bindings -
`hl.dsp.window.move({ workspace = 'r+1' })` and its pair send the window in
front to the next workspace and the one before - so a `Workspace` card of two
or three rows beside `Windows` costs no new capability, only the wording and
the decision that those rows belong on a sofa. That is an item, not this one.

**`Readings` was left alone on purpose.** Its tiles are the HUD's layout -
where one sits in that grid is where it sits on the screen - so re-spanning
them moves what is drawn over a game, and the surface is being replaced.
