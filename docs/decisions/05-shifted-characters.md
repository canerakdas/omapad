# 05. Shifted characters, shown dimmer · ✅ Done · S

Two halves, both shipped:

- **The corner glyph.** Every key prints what Shift would make of it in a small,
  quiet label in its top-right corner, the way a console keyboard does. The
  payload carries it as `x`, computed from the same XKB-aware label lookup as
  the main label, so it follows the compositor's layout too. Shift latched swaps
  the two, and a key Shift does not change sends an empty string, so the quiet
  keys stay quiet.
- **The dimmer state.** While Shift is latched, a key whose label actually
  changed is drawn at a lower alpha, so the swap is visible at a glance instead
  of having to read the row.
- **The letters print no corner hint.** `Q` over every `q` is twenty-six hints
  for the one thing every keyboard already teaches, and it drowned out the ones
  worth reading. A key whose two labels differ only in case sends an empty
  corner.

**The correction from the original write-up held:** `1234567890` shifted gives
`!@#$%^&*()`, not `~!@#$%^&*()` — `~` is the shift of the backtick, which lives
on the symbol page. And because labels are read from the live XKB layout, this
row prints something different on a non-US layout, correctly so.
