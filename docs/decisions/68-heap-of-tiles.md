# 68. Three pages that were a heap of tiles · ✅ Done · M

Asked for from the sofa, about the whole surface rather than one drawing:
*menuleri tasarima benzer sekilde duzenle ve grupla suan cok karmasik
duruyor.* The design is `Console OS v2 UI mockups`, the same one items 63 and
64 were read off, and what it does with a panel is the answer: a page there is
a handful of **cards**, each one job, standing in bands of a single height -
a mixer of four sliders in one card, three switches in another, power as a
list of rows. What the menu had instead was pages that had grown a tile at a
time, in the order the tiles were written.

`Controller` was the evidence. Twelve tiles at four heights: a switch, a bar,
a card, a door, another switch, in whatever order each had been added in, with
`Button labels` three rows tall next to `Profile` at two and a one-cell
`Shortcuts` beside them. Nothing lined up with anything, so there was no shape
to glance at - which is the whole of what a grid is for.

**Three pages, with today's shapes.** No new control: the point of the pass is
that a page is an arrangement, and the arrangement was what was wrong.

- **Controller is two bands.** Along the top, what a press answers with -
  `Vibration` beside `Strength`, `Sounds` beside `Loudness`, `Hold time`
  closing the row, each switch next to the bar that says how much of it. Under
  it, three cards at one height: what the pad prints, what it is, and what its
  buttons do. `Profile` went to three rows tall to stand level with the card
  beside it - a measurement about the band rather than about the card. The
  page's leftovers - `Sticks`, `Hide the pointer`, `Button style` - are a
  three-cell column down the right, all the same width, because a column with
  a step in it is not a column.
- **`Shortcuts` and `Remap the buttons` became a card**, `Buttons`. They were
  the test the procedure already states, sitting unread on the page it was
  written about: two verbs at a cell each, drawn `Shortcut…` and `Remap th…`,
  each with a sentence that a tile one row tall draws **nowhere at all** -
  `detail` needs two rows. A card gives both back. It costs a press: A into
  the card, then the row. The guide is on `Y` from anywhere, so the one that
  is opened in a hurry is not the one that got longer.
- **Display is a card and two bars.** `Scale up`, `Scale down` and
  `Screensaver` are the same three verbs one level along - and `Screensaver`
  drawn as `Screensa…` is the example both `menu.md` and `pad-menu.md` reach
  for when they explain what a card is for. They are `Screen` now, with the
  lines saying which way each one goes, and the two sliders sit under them
  after a break: the card is what the **desktop** is drawn at, the bars are
  what **omapad** draws over it.
- **System lost the second copy of `Reboot` and `Shutdown`.** They were rows
  in `Power` *and* tiles beside it, on item 48's argument about a row you have
  to go and find. What that bought was one press. What it cost was a page
  saying the same two words twice a cell apart, and a guard that has to be
  kept in step in two places - the comment defending it said so itself. The
  card is the page's answer to power; `Start in` stands level with it at three
  rows, and `Omarchy menu` takes its own row underneath, three cells wide,
  because `Omarchy m…` is what one cell had room for.

**What the design has and this surface still cannot draw**, and it is the
reason the pass stopped where it did: a card that holds **controls**. The
mixer with four sliders in it, the three switches under one heading - those
are one card each there, and here `_rows()` refuses a control inside a card
because every control this surface has is a card's worth of drawing. So the
loose switches and bars stay loose, arranged into a band rather than grouped
under a heading. That is the next item, not this one, and it is a real one: it
would collapse the Controller page's top band into a single `Feedback` card.

**And the door lost its mark on the way.** The same pass had given
`Omarchy menu` Omarchy's own glyph rather than a hamburger, on the argument
that the thing on the other side of a door is what a door should be labelled
with - and nothing appeared on the tile. The glyph is U+E900, a private-use
codepoint, and what reached `config.toml` was an empty string: it did not
survive being written into the file. Asked from the sofa (*menuye omarchy
logosu gelmedi, kaldiralim*), the mark went back to the hamburger.
`icon_font` stays - it is how a row names the family its glyph came from, and
it is one character away from working for whoever puts it back.

The tests that moved say what changed: the Controller page's first tiles, the
guide's route in (`Controller ▸ Buttons ▸ Shortcuts`), the count of shipped
countdowns, and the edit-mode carry - which used to step a one-cell tile over
another one-cell tile and now steps it over a three-cell bar, so the bar takes
the first hole that holds it rather than the cell left behind.
