"""The third program-written file, and what it survives.

A layout that will not parse must not be able to take the settings down with
it, and a config that has moved on must not be able to break a layout - so
both halves of that are here rather than left to be discovered from a sofa.
"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad import config as config_module
from omapad.config import read_layout, render_layout


class ReadingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp(prefix="omapad-layout-")
        self.addCleanup(shutil.rmtree, self.directory, True)
        self.path = os.path.join(self.directory, "layout.toml")

    def write(self, text):
        with open(self.path, "w") as handle:
            handle.write(text)
        return read_layout(self.path)

    def test_a_file_that_is_not_there_is_no_arrangement(self):
        self.assertEqual(read_layout(self.path), {})

    def test_a_file_that_will_not_parse_is_ignored_whole(self):
        # Syntax corruption and semantic corruption are not the same failure.
        # This one costs the arrangement and nothing else - never a
        # ConfigError, because a file the daemon wrote itself must not be how
        # the daemon stops starting.
        got = self.write("this is not toml [[[ = = =\n")
        self.assertEqual(got, {})

    def test_a_page_reads_its_three_parts(self):
        got = self.write(
            '[layout.audio]\n'
            'order = ["volume", "mute"]\n'
            'hidden = ["devices"]\n'
            '[layout.audio.span]\n'
            'volume = [4, 2]\n'
        )
        self.assertEqual(got, {"audio": {
            "order": ["volume", "mute"],
            "hidden": ["devices"],
            "span": {"volume": (4, 2)},
        }})

    def test_a_duplicate_id_keeps_the_first_and_drops_the_rest(self):
        got = self.write('[layout.a]\norder = ["x", "y", "x"]\n')
        self.assertEqual(got["a"]["order"], ["x", "y"])

    def test_an_entry_that_is_not_a_name_is_dropped(self):
        got = self.write('[layout.a]\norder = ["x", 7, "", "y"]\n')
        self.assertEqual(got["a"]["order"], ["x", "y"])

    def test_one_bad_span_costs_only_itself(self):
        got = self.write(
            '[layout.a]\n'
            '[layout.a.span]\n'
            'good = [2, 1]\n'
            'short = [3]\n'
            'negative = [0, -3]\n'
            'words = ["wide", "tall"]\n'
        )
        self.assertEqual(got["a"]["span"], {"good": (2, 1)})

    def test_a_page_that_is_not_a_table_is_ignored(self):
        got = self.write('[layout]\naudio = "nonsense"\n')
        self.assertEqual(got, {})


class RoundTripTests(unittest.TestCase):
    def test_what_is_written_is_what_comes_back(self):
        directory = tempfile.mkdtemp(prefix="omapad-layout-")
        self.addCleanup(shutil.rmtree, directory, True)
        path = os.path.join(directory, "layout.toml")
        layout = {
            "audio": {"order": ["volume", "mute"], "hidden": ["devices"],
                      "span": {"volume": (4, 2)}},
            "now": {"order": ["keyboard"], "hidden": [], "span": {}},
        }
        with open(path, "w") as handle:
            handle.write(render_layout(layout))
        self.assertEqual(read_layout(path), layout)

    def test_a_page_with_nothing_in_it_is_not_written(self):
        text = render_layout({"empty": {"order": [], "hidden": [],
                                        "span": {}}})
        self.assertNotIn("[layout.empty]", text)

    def test_an_id_with_a_dot_in_it_survives_the_trip(self):
        # Ids are slugs of labels and a label is whatever somebody typed, so
        # the names go in quoted rather than bare.
        directory = tempfile.mkdtemp(prefix="omapad-layout-")
        self.addCleanup(shutil.rmtree, directory, True)
        path = os.path.join(directory, "layout.toml")
        layout = {"a": {"order": ["x.y"], "hidden": [],
                        "span": {"x.y": (2, 1)}}}
        with open(path, "w") as handle:
            handle.write(render_layout(layout))
        self.assertEqual(read_layout(path), layout)


class LoadingTests(unittest.TestCase):
    def test_the_layout_is_not_merged_into_the_config(self):
        # Structure rather than scalars, read with its own rules, and kept off
        # the deep merge every other file goes through.
        missing = os.path.join(tempfile.gettempdir(), "omapad-no-such-file")
        config = config_module.load(path=missing, mapping=missing,
                                    settings=missing, layout=missing)
        self.assertEqual(config.layout, {})
        self.assertNotIn("layout", config.data)

    def test_a_broken_layout_leaves_the_settings_standing(self):
        directory = tempfile.mkdtemp(prefix="omapad-layout-")
        self.addCleanup(shutil.rmtree, directory, True)
        settings = os.path.join(directory, "settings.toml")
        layout = os.path.join(directory, "layout.toml")
        with open(settings, "w") as handle:
            handle.write('badge_style = "stencil"\n')
        with open(layout, "w") as handle:
            handle.write("[[[ not toml\n")
        missing = os.path.join(tempfile.gettempdir(), "omapad-no-such-file")
        config = config_module.load(path=missing, mapping=missing,
                                    settings=settings, layout=layout)
        self.assertEqual(config.ui_badge_style, "stencil")
        self.assertEqual(config.layout, {})


if __name__ == "__main__":
    unittest.main()
