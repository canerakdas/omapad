# 97. A page of words, read from a file · ✅ Done · M

Asked for from the sofa, the day after 95: *menu icerisine yazi ekledik, bir
seviye daha arttirip basit markdown goruntuleme saglayabilir miyiz, ileride ai
response'unu panelde gostermek icin kullanacagiz. icerik tiklanabilir ve
icinde scroll edilebilir olacak direkt dosyadan okuyabilir* - the menu has
words in it now; go one level up and show simple Markdown, to carry a model's
answer on a card later. The content is pressed into and scrolled inside, and
it can come straight from a file.

**A file, because the words are somebody else's.** An answer is written by a
process that is not this one, as often as it likes, and a card that reads a
path needs nothing from that process but the path. It is also the whole of the
interface [29](29-assistant.md) would need to put its answer on screen.

**What was built:** `control = "text"` with `file` on any menu tile, drawn
four cells by three. `markdown.py` reads the file into blocks - headings,
paragraphs, list items, quotes, lines of code, table rows, rules - with each
block's words cut into styled runs, and `Menu.qml` draws every piece of it in
plain text, on one proportion - the body's line over the silver ratio. The tile
is in `TAKEABLE`: A takes it, up and down move the words a line at a time
(faster held), B lets go, and a wheel over it scrolls it
without taking it. The daemon looks at the file every `[menu] text_poll_ms`,
reads it only when it has changed, and keeps the reading position when the new
words begin with the old ones. [markdown.md](../components/markdown.md) has the
mechanism.

**Rejected: `Text.MarkdownText`.** One line of QML, and the line qml.md 8.6
exists to forbid - rich text fetches what it names, and a file a model wrote is
the least trusted string this surface has drawn. The cost of refusing it is a
parser and a `Flow` of words; the cost of taking it is a shell that loads URLs
out of an answer.

**Rejected: markup the daemon writes, drawn as `Text.StyledText`.** Escaping
every character and emitting only `<b>` and `<i>` would be safe, and it would
also be the first exception to a MUST that a test enforces - on the one
surface whose words are least trusted. Words cut into runs cost a `Text` per
word on a mixed paragraph and nothing on the rest.

**Rejected: letting the `Flickable` scroll itself.** The reading position is
a cursor, and cursors live in the daemon; a panel that scrolled itself would
be scrolled back by the next heartbeat.

**Rejected, after it shipped: a block per push.** The model has no pixels, so
it counted blocks and the panel drew a share of them - and from the sofa that
was *baya kotu*: a paragraph skipped at a push, and a push that moved a
heading barely at all. A push is a line now, and the one number the model
cannot work out - how many lines the words overflow the card by - is measured
by the panel and said back (`menu lines`), the first measurement a panel has
sent rather than a gesture. The spacing went onto the silver ratio in the same
pass, measured from that same line.

**Rejected: following links.** There is no cursor inside a card to follow one
with, and a click that opened a browser would be the panel acting on its own.
A link is drawn as one and stays words.

**What it costs:** a text tile's words ride in `items`, so a page holding one
re-sends them with every push - capped at 64 KiB by `TEXT_LIMIT`, and a mixed
paragraph is a `Text` per word when the page is rebuilt.
