"""Markdown, read into blocks a panel can draw as plain text.

What a `text` tile shows is somebody else's words - a note, and before long
what a model answered - and they arrive as Markdown because that is what
both of those are written in. Qt will render Markdown by itself
(`Text.MarkdownText`), and that is exactly what this module exists to stop:
rich text loads what it names, and qml.md 8.6 keeps every `Text` in the plugin
plain for that reason. A file a model wrote is the least trusted string this
surface has ever drawn.

So the structure is read here and the panel draws each piece with a plain
`Text` in a weight of its own. The markup never crosses the socket; what does
is a list of blocks, each a heading, a paragraph, a list item, a quote, a line
of code, a table row or a rule, with its words split into styled runs.

**What is left out is on purpose.** This is CommonMark's everyday half, the
part a note or an answer is written in: ATX and setext headings, emphasis,
code spans and fences, lists to three levels, quotes, rules, links and simple
pipe tables. Raw HTML is printed as the characters it is, an image is its alt
text, a link is its words, and an indented code block is a paragraph -
nobody writing for a card on a television indents code by four spaces
rather than fencing it, and the rule that decides one would misread every
list continuation.
"""

import re

# Where a line of code starts a fence, and what closes it: three or more of
# the same mark, up to three spaces in.
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")

HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$")

# A thematic break. Asked before a list item, because `* * *` and `- - -`
# are both.
RULE = re.compile(r"^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$")

# The line under a setext heading. Only ever asked while a paragraph is open:
# alone, `---` is a rule.
UNDERLINE = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")

QUOTE = re.compile(r"^ {0,3}>[ ]?(.*)$")

ITEM = re.compile(r"^([ \t]*)([-*+]|\d{1,9}[.)])[ \t]+(.*)$")

# The line between a table's header and its body: dashes between pipes, with
# a colon at either end where a column is aligned.
TABLE_RULE = re.compile(
    r"^[ \t]*\|?[ \t]*:?-+:?[ \t]*(\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*$")

# How far in a nested item is drawn, at most. Deeper than this is a list that
# was meant for a page, and on a card it would leave a word per line.
DEPTH = 3

# The inline marks, earliest first. Underscores only count at a word's edge,
# which is the difference between `_this_` and `snake_case_name`.
INLINE = re.compile(
    r"(?P<code>`+)(?P<code_x>.+?)(?P=code)"
    r"|!\[(?P<alt>[^\]]*)\]\([^)]*\)"
    r"|\[(?P<link>[^\]]+)\]\([^)]*\)"
    r"|<(?P<auto>(?:https?|mailto):[^>\s]+)>"
    r"|\*\*\*(?P<bi>\S(?:.*?\S)??)\*\*\*"
    r"|(?<!\w)___(?P<bi_>\S(?:.*?\S)??)___(?!\w)"
    r"|\*\*(?P<b>\S(?:.*?\S)??)\*\*"
    r"|(?<!\w)__(?P<b_>\S(?:.*?\S)??)__(?!\w)"
    r"|~~(?P<s>\S(?:.*?\S)??)~~"
    r"|\*(?P<i>[^\s*](?:.*?[^\s*])??)\*"
    r"|(?<!\w)_(?P<i_>[^\s_](?:.*?[^\s_])??)_(?!\w)"
    r"|\\(?P<esc>[\\`*_{}\[\]()#+\-.!~|>])"
)

# What each emphasis group adds to the style it is nested in.
EMPHASIS = {"bi": "bi", "bi_": "bi", "b": "b", "b_": "b", "s": "s",
            "i": "i", "i_": "i"}

WORDS = re.compile(r"\S+\s*|\s+")


def _style(outer, more):
    """Two styles as one, in a fixed order so equal runs compare equal."""
    return "".join(mark for mark in "bisl" if mark in outer or mark in more)


def inline(text, style=""):
    """One block's words as [text, style] runs.

    A style is the letters it carries - `b` bold, `i` italic, `s` struck,
    `l` a link's words - or `c` alone for code, which takes no other: a code
    span is printed as it was typed, emphasis marks and all.
    """
    runs = []
    at = 0
    for match in INLINE.finditer(text):
        if match.start() > at:
            runs.append([text[at:match.start()], style])
        at = match.end()
        group = match.lastgroup
        if group == "code_x":
            runs.append([match.group("code_x").strip() or match.group(0),
                         "c"])
        elif group == "alt":
            # The picture is never fetched, and its words are what is left.
            if match.group("alt"):
                runs.append([match.group("alt"), _style(style, "i")])
        elif group == "link":
            runs.extend(inline(match.group("link"), _style(style, "l")))
        elif group == "auto":
            runs.append([match.group("auto"), _style(style, "l")])
        elif group == "esc":
            runs.append([match.group("esc"), style])
        else:
            runs.extend(inline(match.group(group),
                               _style(style, EMPHASIS[group])))
    if at < len(text):
        runs.append([text[at:], style])
    merged = []
    for piece, kind in runs:
        if not piece:
            continue
        if merged and merged[-1][1] == kind:
            merged[-1][0] += piece
        else:
            merged.append([piece, kind])
    return merged


def pieces(runs):
    """Runs cut at the spaces, each word keeping the space after it.

    What a panel wraps with: a `Flow` of plain `Text`s breaks between items
    and never inside one, so a paragraph with a bold word in it has to arrive
    as words. The space rides on the word before it rather than standing
    alone, so a comma after a bold word stays against it.
    """
    out = []
    for text, kind in runs:
        for word in WORDS.findall(text):
            out.append([word, kind])
    return out


def _words(block, text):
    """`block` with its words: one `x` where they are all one style, or `r`.

    One style is nearly every paragraph a person writes, and it is one `Text`
    that wraps itself; only a block that mixes them costs a `Text` per word.
    """
    text = " ".join(text.split())
    runs = inline(text)
    if len(runs) <= 1:
        block["x"] = runs[0][0] if runs else ""
        if runs and runs[0][1]:
            block["s"] = runs[0][1]
    else:
        block["r"] = pieces(runs)
    return block


def _cells(line):
    """A table row's cells as plain words. A cell is too narrow for styles."""
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    cells = re.split(r"(?<!\\)\|", line)
    return ["".join(piece for piece, _ in inline(" ".join(cell.split())))
            for cell in cells]


def parse(text):
    """The blocks a text tile draws, top to bottom.

    Each is a dict with `t` saying what it is - `h` (with `lv`, 1 to 6), `p`,
    `li` (with `lv` from 0 and `m`, the mark it is drawn after), `q`, `code`
    (one per line, so a long block scrolls a line at a time), `tr` (with `c`,
    its cells, and `th` on a header) or `hr` - and its words as `_words`
    leaves them.
    """
    lines = str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks = []
    open_ = None        # the block whose words are still arriving
    words = []
    fence = None
    index = 0

    def flush():
        if open_ is not None:
            blocks.append(_words(open_, " ".join(words)))

    while index < len(lines):
        line = lines[index].expandtabs(4)
        index += 1
        if fence is not None:
            if line.strip().startswith(fence) and not line.strip().strip(
                    fence[0]):
                fence = None
            else:
                blocks.append({"t": "code", "x": line.rstrip()})
            continue
        found = FENCE.match(line)
        if found:
            flush()
            open_, words = None, []
            fence = found.group(1)
            continue
        if not line.strip():
            flush()
            open_, words = None, []
            continue
        if open_ is not None and open_["t"] == "p" and UNDERLINE.match(line):
            open_ = {"t": "h", "lv": 1 if line.strip()[0] == "=" else 2}
            flush()
            open_, words = None, []
            continue
        if RULE.match(line):
            flush()
            open_, words = None, []
            blocks.append({"t": "hr"})
            continue
        found = HEADING.match(line)
        if found:
            flush()
            open_, words = None, []
            blocks.append(_words({"t": "h", "lv": len(found.group(1))},
                                 found.group(2) or ""))
            continue
        found = QUOTE.match(line)
        if found:
            if open_ is None or open_["t"] != "q":
                flush()
                open_, words = {"t": "q"}, []
            words.append(found.group(1))
            continue
        found = ITEM.match(line)
        if found:
            flush()
            mark = found.group(2)
            depth = min(DEPTH - 1, len(found.group(1)) // 2)
            open_ = {"t": "li", "lv": depth,
                     "m": "•" if mark in "-*+" else mark[:-1] + "."}
            words = [found.group(3)]
            continue
        if ("|" in line and index < len(lines)
                and "|" in lines[index] and TABLE_RULE.match(lines[index])):
            flush()
            open_, words = None, []
            blocks.append({"t": "tr", "c": _cells(line), "th": True})
            index += 1
            while index < len(lines) and "|" in lines[index] \
                    and lines[index].strip():
                blocks.append({"t": "tr", "c": _cells(lines[index])})
                index += 1
            continue
        if open_ is None:
            open_, words = {"t": "p"}, []
        # A line that is none of the above carries on whatever is open - a
        # paragraph, and a list item or a quote written lazily across lines.
        words.append(line.strip())
    flush()
    return blocks
