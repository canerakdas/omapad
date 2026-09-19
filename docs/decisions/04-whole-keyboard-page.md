# 04. Page one: a whole keyboard · ✅ Done · M

Page one is now a full keyboard, and shaped like one: `Tab`, `Caps`, `Shift`,
`Enter` and `Backspace` are back on it rather than a page turn away, the key
left of the `1` is where every keyboard puts it, and the keys are **sized the
way a real keyboard sizes them**.

```
`   1 2 3 4 5 6 7 8 9 0 - = Bksp
Tab   q w e r t y u i o p '  Del
Caps   a s d f g h j k l ;  Enter
Shift   z x c v b n m , . /  Shift
&123  Ctrl  Alt  [  Space  ]  ← →  Paste  ▼
```

**The even-column rule was dropped, and it turned out to have been paying for
nothing.** The grid insisted on uniform widths so a D-pad would walk it
predictably — but `move_vertical` carries the horizontal *position*, not the
column index, so a wide `Enter` costs nothing to walk past. What has to match
is the **width budget**: fourteen units per row, on every page, because the
three pages share a bottom row.

- **Word labels where they fit**, glyphs where they do not: `Tab`/`Caps`/
  `Shift`/`Enter`/`Space`/`Paste` are words — and they fit precisely because
  those keys are the wide ones. `Bksp` and `Del` are shortened rather than
  drawn: `⌫` and `⌦` are one pixel apart at this size and the wrong one eats a
  word. `▼` stays a glyph, since nothing it could be called is shorter.
- **Ctrl and Alt stayed.** The original write-up wanted them off page one, but
  the bottom row has the width now, and a keyboard that cannot send `Ctrl+C` is
  a worse trade than one crowded cell.
- **A second Shift on the right**, as on a real keyboard: from the right-hand
  side of the grid it halves the travel to reach one.
- **The bottom row is identical on all three pages** — only the first cell
  changes, and it names the page it goes to (`&123` → `Fn` → `abc`, the same
  order `L`/`R` walk). The keys you press without looking do not move when the
  page does.
- **The arrows cost two cells, not four**, because Shift swaps them (below).
- **Paste ships as `Ctrl+V`**, still wrong in a terminal until item 09 lands.

**The per-key shift alternative that item 04 asked for is built:** a key can
carry an `alt` action, taken instead while Shift is latched, and the shift is
spent on the swap rather than sent along with the key — a latched `Ctrl` plus a
shifted `→` types `Ctrl+↓`, not `Ctrl+Shift+→`.
