# Markdown

| | |
|---|---|
| **Daemon** | `omapad/markdown.py` (the reading), `omapad/menu.py` (the tile), `omapad/daemon.py` (the file) |
| **Panel** | `shell-plugin/Menu.qml`, the tile's `reader` |
| **Socket** | `menu.sock` - it is a menu tile, not a surface |
| **Config** | `control = "text"` and `file` on any `[[menu.items]]` tile; `[menu] text_poll_ms` |
| **Verb** | A takes it, up and down scroll it, B lets go; `omapad ctl menu scroll ID N` |

A card of somebody else's words. It is the heading one level up
([95](../decisions/95-words-over-a-run.md)) - words that say something rather
than name a run of tiles - and it is what a model's answer will be drawn on,
which is why it reads a **file**: what writes the words is something else, as
often as it likes, and the card only has to look. [97](../decisions/97-a-page-of-words.md)
is the decision.

## Why the panel is not allowed to render it

Qt renders Markdown itself (`Text.MarkdownText`), in a line of QML. That line
is what qml.md 8.6 forbids, and `tests/test_shell_plugin.py` fails on it: rich
text loads what it names, so `![](http://…)` in a file is a shell that stays up
all session fetching a stranger's URL. A file a model wrote is the least
trusted string this surface has ever drawn - the rule was written for a
device's own name, and an answer is worse.

So `markdown.parse()` reads the structure on the daemon's side and the panel
draws every piece of it with a plain `Text`. **The markup never crosses the
socket.** What does is a list of blocks:

```
{t: "h",    lv: 1..6, ...words}      a heading
{t: "p",    ...words}                a paragraph
{t: "li",   lv: 0..2, m, ...words}   a list item, after its mark: "•" or "3."
{t: "q",    ...words}                a quote
{t: "code", x}                       one line of a fence, spaces kept
{t: "tr",   c: [cell], th?}          a row of a pipe table; th on the header
{t: "hr"}                            a rule
```

`...words` is `x` (with `s`, its style, where it has one) when the block is
one style throughout, and `r` - `[[word, style], ...]` - when it mixes them. A
style is the letters it carries: `b` bold, `i` italic, `s` struck, `l` a
link's words, or `c` alone for code.

**One style is one `Text`, and a mix is a `Text` per word.** A `Text` wraps
itself but draws one weight, and a `Flow` of them wraps between its items and
never inside one - so a paragraph with a bold word in it arrives already cut
into words (`pieces()`), each carrying the space after it, so that a comma
after a bold word stays against it. Nearly every paragraph anybody writes is
one style, and costs one item.

**Code is a block per line** rather than one block, so each line of a fence
draws on its own ground and a long line wraps inside it rather than off the
card.

## What it reads, and what it leaves

CommonMark's everyday half - the part a note or an answer is written in: ATX
and setext headings, emphasis, code spans and fences, lists to three levels,
quotes, rules, links and simple pipe tables. Left out on purpose:

- **Raw HTML** is printed as the characters it is. Drawn plain, it is text.
- **An image** is its alt text, in italic, and is never fetched.
- **A link** is its words, drawn as a link, and cannot be followed: there is
  no cursor inside a card for A to follow it with, and a click that opened a
  browser from inside the menu would be the panel acting on its own, which
  `pad-surface.md` calls a bug.
- **An indented code block** is a paragraph. Nobody writing for a card fences
  code with four spaces, and the rule that recognises one misreads every
  list continuation.
- **Nesting past three levels** is drawn at the third: deeper is a list meant
  for a page, and on a card it leaves a word per line.

## Where the words come from

`daemon.menu_text_refresh()` looks at the file behind every text tile on the
**page in front** every `[menu] text_poll_ms`, and at once for a tile nothing
has been read for yet, so a page arriving does not draw an empty card first.
A look is a `stat`; the file is read again only when its change time or its
size has moved, and the cache is by tile rather than by path so two tiles on
one file both hear about it.

**It is read on the loop**, where every other thing the menu reads goes to
the worker, and it may be: a `stat` and a read capped at `TEXT_LIMIT` (64 KiB)
of a local file are over in microseconds, and what makes a read hang is
refused before the open - only a regular file is read at all, because a FIFO
is the file a writer can hold open forever. A file that is not there is a card
with nothing on it rather than an error: what writes it may simply not have
run yet. `~` is expanded here rather than in `menu.py`, which reads nothing
from the machine.

## Where it is read to

`MenuModel.scrolled` is a **line** per tile: a push down moves the words one
line of body text, and a direction held moves more the longer it is held. It
was a block per push first, and a push that moved a whole paragraph was a push
that skipped half of it.

**How many lines there are is the panel's to know**, because what a paragraph
wraps to is a font and a width, and the model has neither. So the panel
measures how many lines the words overflow the card by and says so over the
control socket - `menu lines <id> <n>`, the one thing a panel sends that is a
measurement rather than a gesture - and `set_overflow()` makes that the end of
the travel, pulling the place back inside it where the words got shorter.
Until it has said, the blocks are the end: the words are at least that many
lines long. The panel says it again whenever the number changes and whenever
the card is built, so a restarted shell tells a daemon that never heard.

The payload carries the line as `scr: {id: n}`, on the **surface** rather than
the tile, for `chrono`'s reason: a value that changed at every push would
change `items`, and `fresh()` would rebuild every delegate on the page to move
one card's words - and the card being read would lose its place in the
rebuild.

**Words that grow keep their place.** `set_text()` resets the position only
when the new words do not begin with the old ones: an answer arriving a few
words at a time is read from wherever the reader is, and a file that says
something else entirely is a new page, read from its first line. Letting go
keeps the place too; coming back to a page you were half way down is coming
back to where you were.

## The page, on one proportion

One line of body text is the unit everything on the card is measured in, and
the silver ratio is the only number: the air between two blocks is that line
over the ratio, a heading takes a whole line above it, and what follows a
heading - or one list item after another - takes a step less than a paragraph,
so a list and its heading read as one thing. A first-level heading is the body
one `sqrt(2)` rung up (the ratio less one, the ladder's own step), a second is
half a rung up, and past that a heading is the body's size in the strong weight
and the muted ink.

## The pad

It is in `TAKEABLE`, and taken the way a card of rows is entered:
`MenuModel.reading` is `entered`'s twin. While it is true, up and down move the
words by `menu_ramp()` lines - one to start, more the longer a direction is
held - left and right do nothing, **A does nothing**, and B lets go without
putting anything back, because reading moved nothing. A letting go as well
would be one press said by two buttons (`bindings.md` rule 4). The legend says
`Scroll` over the card, then `Back` and the two directions once inside.

A wheel over the card scrolls it without taking it - what a wheel over words
does on every desktop - by sending `menu scroll <id> <±1>` over the control
socket - three lines a notch, which is what a wheel moves words by everywhere
else on the desktop.

The HUD does not draw one: it has a press, and a press over a game is a
control with no way to reach it ([hud](hud.md)).
