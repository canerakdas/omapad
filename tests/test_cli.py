"""The commands `bin/omapad` answers with, and what they report.

`budget` is what is covered here: it prices what the daemon costs while
nothing is happening, and a budget that quietly stops counting a row is worse
than no budget at all. `budget stress` drives the daemon on the desktop in
front of you, so what it is allowed to send is held here too.
"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad import __main__ as cli
from omapad import config as config_module


class ProcReadingTests(unittest.TestCase):
    """The two files every figure in `budget` comes out of."""

    def test_a_process_reports_its_own_memory(self):
        size = cli._proc_kb(os.getpid(), "VmRSS")
        self.assertIsNotNone(size)
        self.assertGreater(size, 0)

    def test_and_its_own_cpu(self):
        ticks = cli._cpu_ticks(os.getpid())
        self.assertIsNotNone(ticks)
        self.assertGreaterEqual(ticks, 0)

    def test_a_process_that_is_gone_reports_nothing(self):
        # /proc disappears under you - the same posture `handover.py` takes,
        # because it is the same filesystem.
        gone = 2 ** 22
        self.assertIsNone(cli._proc_kb(gone, "VmRSS"))
        self.assertIsNone(cli._cpu_ticks(gone))

    def test_a_line_that_is_not_there_reports_nothing(self):
        self.assertIsNone(cli._proc_kb(os.getpid(), "VmNoSuchThing"))


class MenuCommandBudgetTests(unittest.TestCase):
    """How many shells an open menu runs a minute, read off the config."""

    def setUp(self):
        # The shipped defaults alone: the three layers over them are the
        # machine's, and a budget test that reads them prices whatever this
        # developer's sofa chose last week.
        nowhere = os.path.join(os.path.dirname(__file__), "no-such-file.toml")
        self.config = config_module.load(path=nowhere, mapping=nowhere,
                                         settings=nowhere, layout=nowhere)

    def rows(self, config=None):
        return cli._menu_command_rows(config or self.config)

    def test_the_shipped_menu_prices_every_command_it_runs(self):
        rows = self.rows()
        self.assertIsNotNone(rows, "the shipped menu should parse")
        self.assertTrue(rows, "the shipped menu runs commands for its lines")
        for source, ttl in rows:
            self.assertTrue(source.strip())
            self.assertIsInstance(ttl, float)

    def test_a_row_that_never_goes_stale_costs_nothing_a_minute(self):
        self.config.menu_items = [
            {"label": "Windows", "meta": {"from": "id -un", "ttl": 0},
             "items": [{"label": "Close", "action": "exec:true"}]},
        ]
        self.config.menu_head = []
        self.assertEqual(self.rows(), [("id -un", 0.0)])

    def test_and_one_that_does_costs_what_its_ttl_says(self):
        self.config.menu_items = [
            {"label": "Windows", "meta": {"from": "count", "ttl": 5},
             "items": [{"label": "Close", "action": "exec:true"}]},
        ]
        self.config.menu_head = [{"from": "weather", "ttl": 30}]
        rows = dict(self.rows())
        self.assertEqual(rows["count"], 5.0)
        self.assertEqual(rows["weather"], 30.0)
        # Twelve a minute for the card, two for the head line.
        self.assertEqual(sum(60.0 / ttl for ttl in rows.values() if ttl > 0),
                         14.0)

    def test_a_head_line_is_counted_as_well_as_a_card(self):
        # Both are a subprocess with a clock on it, and a budget that counted
        # one of them would be wrong by however many the other holds.
        self.config.menu_items = []
        self.config.menu_head = [
            {"format": "%H:%M", "over": {"from": "id -un", "ttl": 60}},
        ]
        self.assertEqual(self.rows(), [("id -un", 60.0)])

    def test_a_menu_that_will_not_parse_is_not_priced(self):
        # `check` is the command that names a broken menu; this one declines
        # to put a number on a tree it could not build.
        self.config.menu_items = [{"label": "Broken", "meta": {}}]
        self.assertIsNone(self.rows())


class StressCycleTests(unittest.TestCase):
    """What `budget stress` sends to the daemon on the desktop in front of you."""

    # Selection and open/close only. A verb here is safe because of what it
    # does on every row, not on the rows the shipped menu happens to have.
    SAFE = {
        "menu": {"open", "close", "select", "group"},
        "quick": {"open", "close", "select"},
        "guide": {"open", "close", "next", "prev"},
        "osk": {"open", "close"},
    }

    def test_nothing_it_sends_runs_a_row_or_moves_a_value(self):
        # The first run pressed A through All apps and started a browser, and
        # walked the quick menu's volume to nothing. Neither is a leak test.
        for command in cli.STRESS_CYCLE:
            surface, verb = command.split()[:2]
            self.assertIn(verb, self.SAFE.get(surface, ()), command)

    def test_every_surface_is_opened_and_closed_in_a_cycle(self):
        # One left open would be closed by the next cycle's open of another,
        # and the drift would be the cost of a surface up, not of a leak.
        for surface in self.SAFE:
            self.assertEqual(
                cli.STRESS_CYCLE.count("%s open" % surface),
                cli.STRESS_CYCLE.count("%s close" % surface), surface)
            self.assertIn("%s open" % surface, cli.STRESS_CYCLE)


class StressReadingTests(unittest.TestCase):
    """The shell it finds and the lines it prints."""

    def fake_proc(self, names):
        root = tempfile.mkdtemp(prefix="omapad-proc-")
        self.addCleanup(shutil.rmtree, root, True)
        for pid, name in names.items():
            os.makedirs(os.path.join(root, str(pid)))
            with open(os.path.join(root, str(pid), "comm"), "w") as handle:
                handle.write(name + "\n")
        os.makedirs(os.path.join(root, "self"))
        return root

    def test_the_oldest_shell_is_the_one_read(self):
        # A restarted shell leaves the old one exiting beside it for a moment.
        proc = self.fake_proc({900: "quickshell", 400: "quickshell", 5: "bash"})
        self.assertEqual(cli._pid_named("quickshell", proc), 400)

    def test_no_shell_is_none(self):
        proc = self.fake_proc({5: "bash"})
        self.assertIsNone(cli._pid_named("quickshell", proc))

    def test_a_process_reports_its_own_footprint(self):
        size, fds, threads = cli._footprint(os.getpid())
        self.assertGreater(size, 0)
        self.assertGreater(fds, 0)
        self.assertGreaterEqual(threads, 1)

    def test_drift_is_signed(self):
        line = cli._drift("daemon", (2048, 18, 2), (2148, 17, 2))
        self.assertEqual(
            line, "daemon: 2.1 MB (+100 kB), 17 descriptors (-1), "
            "2 threads (+0)")

    def test_a_process_gone_is_said(self):
        self.assertIn("went away",
                      cli._drift("shell", (1, 1, 1), (None, None, None)))


if __name__ == "__main__":
    unittest.main()
