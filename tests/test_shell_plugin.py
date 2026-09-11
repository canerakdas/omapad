"""What the plugin must be true of, read rather than run.

There is no QML runtime in the suite, so the rules whose failure is silent on
screen are checked by reading the files. A `Text` left to detect its own
format is exactly that kind of rule: it draws every string anyone has ever
typed correctly, and fetches a resource for the one a device named itself.
"""

import os
import re
import unittest

PLUGIN = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shell-plugin"
)

OPENS = re.compile(r"^(\s*)(?:\w+\s*:\s*)?Text \{\s*$")


def text_blocks(source):
    """Every `Text { … }` in one file, as (line number, body)."""
    lines = source.split("\n")
    blocks = []
    for index, line in enumerate(lines):
        if not OPENS.match(line):
            continue
        depth = 1
        body = []
        for follow in lines[index + 1:]:
            depth += follow.count("{") - follow.count("}")
            if depth <= 0:
                break
            body.append(follow)
        blocks.append((index + 1, "\n".join(body)))
    return blocks


class LiveStreamTests(unittest.TestCase):
    """The one rule whose failure costs everything the gauge phase bought."""

    # Anything that makes the scene work out where things go. `x`, `y`,
    # `scale`, `opacity` and a colour are the graphics scene's own and cost
    # nothing; a width, a height, a margin or a spacing is a layout pass, and
    # a layout pass sixty times a second throws away the whole point of a
    # push that carries no items.
    LAYOUT = re.compile(
        r"^\s*(?:width|height|implicitWidth|implicitHeight|spacing"
        r"|anchors\.\w*[Mm]argin|Layout\.\w+)\s*:.*\broot\.live\b")

    def test_nothing_binds_a_layout_to_the_live_stream(self):
        path = os.path.join(PLUGIN, "Menu.qml")
        with open(path) as handle:
            for number, line in enumerate(handle, 1):
                self.assertIsNone(
                    self.LAYOUT.match(line),
                    "Menu.qml:%d lays out from root.live, which is a layout"
                    " pass per frame" % number)

    def test_the_rule_is_written_down_where_somebody_would_break_it(self):
        # A test nobody can find the reason for is a test that gets deleted.
        path = os.path.join(PLUGIN, "Menu.qml")
        with open(path) as handle:
            source = handle.read()
        self.assertIn("property var live", source)
        self.assertIn("LAYOUT WIDTH OR HEIGHT", source)


class PlainTextTests(unittest.TestCase):
    def setUp(self):
        self.files = sorted(
            name for name in os.listdir(PLUGIN) if name.endswith(".qml")
        )

    def test_the_plugin_has_text_to_check(self):
        # A refactor that renamed the element would otherwise turn every test
        # below into a pass over nothing.
        found = 0
        for name in self.files:
            with open(os.path.join(PLUGIN, name)) as handle:
                found += len(text_blocks(handle.read()))
        self.assertGreater(found, 20)

    def test_every_text_says_what_format_it_is(self):
        for name in self.files:
            with open(os.path.join(PLUGIN, name)) as handle:
                for line, body in text_blocks(handle.read()):
                    self.assertIn(
                        "textFormat: Text.PlainText", body,
                        "%s:%d draws text with no format of its own" % (name, line))

    def test_nothing_asks_for_rich_text(self):
        for name in self.files:
            with open(os.path.join(PLUGIN, name)) as handle:
                source = handle.read()
            for wanted in ("Text.RichText", "Text.StyledText", "Text.AutoText"):
                self.assertNotIn(wanted, source, "%s: %s" % (name, wanted))


if __name__ == "__main__":
    unittest.main()
