"""Markdown read into the blocks a text tile draws in plain text."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad.markdown import inline, parse, pieces


class BlockTests(unittest.TestCase):
    def kinds(self, text):
        return [block["t"] for block in parse(text)]

    def test_a_paragraph_is_its_lines_joined(self):
        self.assertEqual(parse("one\ntwo\n\nthree"),
                         [{"t": "p", "x": "one two"}, {"t": "p", "x": "three"}])

    def test_headings_carry_their_level(self):
        blocks = parse("# One\n### Three ###\nSetext\n---")
        self.assertEqual([(b["t"], b["lv"], b["x"]) for b in blocks],
                         [("h", 1, "One"), ("h", 3, "Three"),
                          ("h", 2, "Setext")])

    def test_a_rule_alone_is_a_rule_not_a_heading(self):
        self.assertEqual(self.kinds("---\n\n* * *"), ["hr", "hr"])

    def test_list_items_carry_their_mark_and_depth(self):
        blocks = parse("- one\n  - nested\n3. third\n4) fourth")
        self.assertEqual([(b["lv"], b["m"], b["x"]) for b in blocks],
                         [(0, "•", "one"), (1, "•", "nested"),
                          (0, "3.", "third"), (0, "4.", "fourth")])

    def test_nesting_stops_at_the_depth_a_card_can_hold(self):
        self.assertEqual(parse("            - deep")[0]["lv"], 2)

    def test_a_lazy_line_carries_on_the_item_above_it(self):
        self.assertEqual(parse("- one\ncarried on")[0]["x"], "one carried on")

    def test_a_quote_joins_its_lines(self):
        self.assertEqual(parse("> one\n> two"), [{"t": "q", "x": "one two"}])

    def test_code_is_a_block_per_line_and_keeps_its_spaces(self):
        blocks = parse("```python\ndef f():\n    return *not* bold\n```")
        self.assertEqual(blocks, [{"t": "code", "x": "def f():"},
                                  {"t": "code", "x": "    return *not* bold"}])

    def test_an_unclosed_fence_runs_to_the_end(self):
        self.assertEqual(self.kinds("~~~\na\nb"), ["code", "code"])

    def test_a_table_is_a_header_and_its_rows(self):
        blocks = parse("| a | **b** |\n|---|:-:|\n| 1 | 2 |\n\nafter")
        self.assertEqual(blocks[:2], [{"t": "tr", "c": ["a", "b"], "th": True},
                                      {"t": "tr", "c": ["1", "2"]}])
        self.assertEqual(blocks[2]["t"], "p")

    def test_a_pipe_in_a_sentence_is_not_a_table(self):
        self.assertEqual(self.kinds("a | b\n---"), ["h"])

    def test_nothing_is_no_blocks(self):
        self.assertEqual(parse(""), [])
        self.assertEqual(parse("\n\n  \n"), [])

    def test_windows_line_ends_read_the_same(self):
        self.assertEqual(parse("# a\r\nb"), parse("# a\nb"))


class InlineTests(unittest.TestCase):
    def test_the_marks_become_styles(self):
        self.assertEqual(
            inline("a **b** *c* ***d*** ~~e~~ `f`"),
            [["a ", ""], ["b", "b"], [" ", ""], ["c", "i"], [" ", ""],
             ["d", "bi"], [" ", ""], ["e", "s"], [" ", ""], ["f", "c"]])

    def test_code_keeps_its_marks(self):
        self.assertEqual(inline("`**x**`"), [["**x**", "c"]])

    def test_a_link_is_its_words_and_an_image_is_never_fetched(self):
        self.assertEqual(inline("[docs](http://x)"), [["docs", "l"]])
        self.assertEqual(inline("![a cat](http://x/cat.png)"),
                         [["a cat", "i"]])
        self.assertEqual(inline("![](http://x/cat.png)"), [])

    def test_underscores_inside_a_word_are_the_word(self):
        self.assertEqual(inline("snake_case_name"), [["snake_case_name", ""]])
        self.assertEqual(inline("an _aside_"), [["an ", ""], ["aside", "i"]])

    def test_a_lone_star_is_a_star(self):
        self.assertEqual(inline("2 * 3 * 4"), [["2 * 3 * 4", ""]])

    def test_an_escaped_mark_is_printed(self):
        self.assertEqual(inline(r"\*not\*"), [["*not*", ""]])

    def test_raw_html_is_printed_as_it_is(self):
        # Drawn in plain text, so it is characters and nothing else - never a
        # tag a `Text` could act on.
        self.assertEqual(inline("<img src=x>"), [["<img src=x>", ""]])

    def test_a_mixed_block_arrives_as_words(self):
        block = parse("a **b**, c")[0]
        self.assertEqual(block["r"], [["a ", ""], ["b", "b"], [", ", ""],
                                      ["c", ""]])

    def test_a_word_keeps_the_space_after_it(self):
        self.assertEqual(pieces([["one two ", ""], ["three", "b"]]),
                         [["one ", ""], ["two ", ""], ["three", "b"]])

    def test_one_style_is_one_string(self):
        self.assertEqual(parse("**all of it**")[0],
                         {"t": "p", "x": "all of it", "s": "b"})


if __name__ == "__main__":
    unittest.main()
