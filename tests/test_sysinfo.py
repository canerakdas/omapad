"""What the machine is doing, without being on that machine.

Every reading here comes from a file the kernel fills in as it is asked, and
not one of those files is the same on two machines - a laptop has a fan and a
desktop does not, `coretemp` is `k10temp` next door, and `/proc/stat` counts
from a boot this process did not see. So the parsers are pure functions over
canned text, and the reads are pointed at a temporary directory.

The one thing a test here cannot do is read the real `/proc`: a suite that
asserts anything about the machine it runs on passes on the developer's laptop
and fails in a container.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad import config as config_module
from omapad import sysinfo
from omapad.sysinfo import Sysinfo, SysinfoError


STAT = [
    "cpu  100 0 100 800 0 0 0 0 0 0",
    "cpu0 50 0 50 400 0 0 0 0 0 0",
    "intr 12345",
]

# The same machine one interval later: 200 ticks went by and 100 of them were
# spent idle, so half a core's worth of work.
STAT_LATER = [
    "cpu  150 0 150 900 0 0 0 0 0 0",
    "cpu0 75 0 75 450 0 0 0 0 0 0",
]

MEMINFO = [
    "MemTotal:       16384000 kB",
    "MemFree:          512000 kB",
    "Buffers:          128000 kB",
    "Cached:          4096000 kB",
    "MemAvailable:    8192000 kB",
]


def shipped():
    """A config off none of this machine's files."""
    missing = os.path.join(tempfile.gettempdir(), "omapad-no-such-config")
    return config_module.load(path=missing, mapping=missing,
                              settings=missing, layout=missing)


class NothingHereRunsACommand(unittest.TestCase):
    def test_the_module_does_not_import_subprocess(self):
        # The same rule `live.py` keeps, and it matters more here: these are
        # polled twice a second while something is on screen. A file read is
        # microseconds and runs on the loop; a helper is the daemon's to
        # submit to the worker, and importing subprocess here is how that
        # stops being true without anybody noticing.
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "omapad", "sysinfo.py")
        with open(path) as handle:
            source = handle.read()
        for word in ("import subprocess", "popen", "system("):
            self.assertNotIn(word, source)


class SourcesAreCheckedWhenTheConfigIsRead(unittest.TestCase):
    """`omapad check` names a source that cannot work, not the sofa.

    The failure a bad source causes on screen is that no tile is drawn - which
    is exactly what a reading this machine does not have looks like. There is
    no way to tell the two apart by looking, so they have to be told apart
    here.
    """

    def test_empty_is_a_reading_this_machine_does_not_have(self):
        self.assertIsNone(sysinfo.source(""))
        self.assertIsNone(sysinfo.source(None))
        self.assertIsNone(sysinfo.source("   "))

    def test_a_source_is_how_and_where(self):
        self.assertEqual(sysinfo.source("proc:stat"), ("proc", "stat"))
        self.assertEqual(sysinfo.source("mount:/home"), ("mount", "/home"))
        self.assertEqual(
            sysinfo.source("hwmon:coretemp/temp1_input"),
            ("hwmon", "coretemp/temp1_input"),
        )

    def test_a_command_keeps_its_own_colons(self):
        # `partition` and not `split`: a helper is allowed to be a shell line
        # with a path in it, and cutting at the second colon would take half
        # of somebody's command away.
        self.assertEqual(
            sysinfo.source("cmd:awk -F: '{print $2}' /tmp/x"),
            ("cmd", "awk -F: '{print $2}' /tmp/x"),
        )

    def test_a_how_nobody_knows_is_named(self):
        with self.assertRaises(SysinfoError):
            sysinfo.source("magic:/tmp/x")

    def test_a_bare_word_is_not_a_source(self):
        with self.assertRaises(SysinfoError):
            sysinfo.source("/proc/stat")

    def test_a_how_with_nothing_after_it_is_named(self):
        with self.assertRaises(SysinfoError):
            sysinfo.source("file:")

    def test_proc_reads_the_two_files_it_has_a_parser_for(self):
        # Anything else under /proc is a `file:` source. Those two are parsed
        # because neither of them is one number.
        with self.assertRaises(SysinfoError):
            sysinfo.source("proc:cpuinfo")

    def test_a_hwmon_source_names_a_chip_and_a_file(self):
        with self.assertRaises(SysinfoError):
            sysinfo.source("hwmon:temp1_input")

    def test_a_path_source_takes_a_path(self):
        for spec in ("mount:home", "file:sys/class"):
            with self.assertRaises(SysinfoError):
                sysinfo.source(spec)

    def test_the_config_raises_its_own_error(self):
        # A SysinfoError reaching the daemon is a traceback; a ConfigError is
        # a line `omapad check` prints with the key in it.
        missing = os.path.join(tempfile.gettempdir(), "omapad-no-such-config")
        with tempfile.NamedTemporaryFile("w", suffix=".toml") as handle:
            handle.write('[sysinfo]\ncpu = "nonsense"\n')
            handle.flush()
            with self.assertRaises(config_module.ConfigError):
                config_module.load(path=handle.name, mapping=missing,
                                   settings=missing, layout=missing)


class BusyIsMeasuredAcrossAnInterval(unittest.TestCase):
    """One read of `/proc/stat` says nothing, and must say nothing.

    The file counts ticks since boot, so a single read is what the machine has
    averaged since it was switched on - a number that is true, useless, and
    indistinguishable from a real one once it is on a tile.
    """

    def test_the_first_read_answers_nothing(self):
        value, sample = sysinfo.parse_stat(STAT, None)
        self.assertIsNone(value)
        self.assertIsNotNone(sample)

    def test_the_second_read_answers_the_interval(self):
        _, first = sysinfo.parse_stat(STAT, None)
        value, _ = sysinfo.parse_stat(STAT_LATER, first)
        # 200 ticks went by, 100 of them idle.
        self.assertAlmostEqual(value, 0.5)

    def test_a_sample_that_did_not_move_keeps_the_old_one(self):
        # Two reads inside one tick. Answering nothing is right; throwing the
        # sample away is not, because then the next read has no interval
        # either and the tile never fills.
        _, first = sysinfo.parse_stat(STAT, None)
        value, kept = sysinfo.parse_stat(STAT, first)
        self.assertIsNone(value)
        self.assertEqual(kept, first)

    def test_iowait_is_not_work(self):
        # The kernel counts waiting on a disk separately, and a machine
        # stalled on one is not a machine doing anything.
        _, first = sysinfo.parse_stat(["cpu 0 0 0 0 0 0 0 0"], None)
        value, _ = sysinfo.parse_stat(["cpu 0 0 0 50 50 0 0 0"], first)
        self.assertAlmostEqual(value, 0.0)

    def test_a_file_with_no_cpu_line_answers_nothing(self):
        self.assertEqual(sysinfo.parse_stat(["intr 1"], None), (None, None))

    def test_rubbish_in_the_line_answers_nothing(self):
        self.assertEqual(
            sysinfo.parse_stat(["cpu a b c d"], None), (None, None))


class MemoryIsWhatIsAvailable(unittest.TestCase):
    def test_the_cache_is_not_counted_as_used(self):
        # Against MemAvailable rather than MemFree: the cache is memory the
        # machine hands to the next program that asks, and counting it as used
        # prints a laptop at 95% for an evening in which nothing was short.
        value = sysinfo.parse_meminfo(MEMINFO)
        self.assertAlmostEqual(value, 0.5)

    def test_a_file_missing_either_number_answers_nothing(self):
        self.assertIsNone(sysinfo.parse_meminfo(["MemTotal: 100 kB"]))
        self.assertIsNone(sysinfo.parse_meminfo([]))


class OneNumberIsTheAnswer(unittest.TestCase):
    """What every `file:` and `cmd:` source comes back as."""

    def test_the_first_number_wins(self):
        self.assertEqual(sysinfo.parse_number(["42"]), 42.0)
        self.assertEqual(sysinfo.parse_number(["37 %"]), 37.0)
        self.assertEqual(sysinfo.parse_number(["74.5"]), 74.5)

    def test_a_warning_in_the_same_pipe_does_not_matter(self):
        # stderr that landed in the same pipe, which is what a helper run
        # through a shell actually looks like on a bad day.
        self.assertEqual(
            sysinfo.parse_number(["no display, using 0", "61"]), 0.0)

    def test_nothing_numeric_is_nothing(self):
        self.assertIsNone(sysinfo.parse_number(["ERROR: no device"]))
        self.assertIsNone(sysinfo.parse_number([]))


class HwmonIsFoundByName(unittest.TestCase):
    """`hwmon4` is a battery on one boot and a network card on the next.

    What is stable is the name each chip publishes, so that is what a source
    names - and this is the whole reason the config does not take a path.
    """

    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self._chip("hwmon0", "BAT0", {"temp1_input": "31000"})
        self._chip("hwmon1", "coretemp", {"temp1_input": "54000"})

    def _chip(self, directory, name, files):
        path = os.path.join(self.root.name, directory)
        os.makedirs(path)
        with open(os.path.join(path, "name"), "w") as handle:
            handle.write(name + "\n")
        for filename, text in files.items():
            with open(os.path.join(path, filename), "w") as handle:
                handle.write(text + "\n")

    def test_the_named_chip_is_the_one_read(self):
        path = sysinfo.hwmon_path("coretemp/temp1_input", self.root.name)
        self.assertTrue(path.endswith("hwmon1/temp1_input"))

    def test_a_star_takes_whichever_chip_has_the_file(self):
        path = sysinfo.hwmon_path("*/temp1_input", self.root.name)
        self.assertIsNotNone(path)

    def test_a_chip_that_is_not_here_is_no_path(self):
        # Unplugged, unbound, or never on this machine. None, not an OSError
        # into the loop.
        self.assertIsNone(
            sysinfo.hwmon_path("k10temp/temp1_input", self.root.name))

    def test_a_file_the_chip_does_not_publish_is_no_path(self):
        self.assertIsNone(
            sysinfo.hwmon_path("coretemp/fan1_input", self.root.name))

    def test_a_source_with_no_file_at_all_is_no_path(self):
        self.assertIsNone(sysinfo.hwmon_path("coretemp", self.root.name))


class WordsOnATile(unittest.TestCase):
    def test_a_percentage_is_whole(self):
        self.assertEqual(sysinfo.text(0.374, "%", 100), "37%")

    def test_a_temperature_has_no_space_before_the_degree(self):
        # Which is how every thermometer on a desktop prints it.
        self.assertEqual(sysinfo.text(54.2, "°C"), "54°C")

    def test_anything_else_keeps_its_space(self):
        self.assertEqual(sysinfo.text(2200, "rpm"), "2200 rpm")
        self.assertEqual(sysinfo.text(59.94, "fps"), "59.9 fps")

    def test_nothing_says_nothing(self):
        self.assertEqual(sysinfo.text(None, "%"), "")


class ReadingsAreKeptAndCompared(unittest.TestCase):
    def setUp(self):
        self.config = shipped()
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def _file(self, name, text):
        path = os.path.join(self.dir.name, name)
        with open(path, "w") as handle:
            handle.write(text)
        return path

    def _pointed_at(self, sources, units=None, divisors=None):
        self.config.sysinfo_sources = dict(sources)
        self.config.sysinfo_units = dict(units or {})
        self.config.sysinfo_divisors = dict(divisors or {})
        return Sysinfo(self.config)

    def test_a_file_source_is_read_and_divided(self):
        # hwmon publishes thousandths of a degree, which is the kernel's ABI
        # rather than a preference - so the divisor is in the module and not
        # in anybody's config.
        path = self._file("temp", "54321\n")
        reader = self._pointed_at({"temperature": ("file", path)})
        self.assertTrue(reader.read("temperature"))
        self.assertEqual(reader.words("temperature"), "54°C")

    def test_a_file_that_is_not_there_answers_nothing(self):
        # Optional hardware: a sensor unbound, a card gone with its driver.
        # None of it may raise into the loop.
        reader = self._pointed_at(
            {"temperature": ("file", os.path.join(self.dir.name, "gone"))})
        self.assertFalse(reader.read("temperature"))
        self.assertIsNone(reader.value("temperature"))

    def test_a_reading_that_stops_answering_keeps_its_last_value(self):
        # A sensor briefly busy, or a helper a second late, must not be able
        # to empty the HUD.
        path = self._file("temp", "54000\n")
        reader = self._pointed_at({"temperature": ("file", path)})
        reader.read("temperature")
        os.unlink(path)
        reader.read("temperature")
        self.assertEqual(reader.words("temperature"), "54°C")

    def test_a_value_that_did_not_move_is_not_a_change(self):
        # What stops the daemon repainting two surfaces twice a second for a
        # number that is the same number.
        path = self._file("temp", "54000\n")
        reader = self._pointed_at({"temperature": ("file", path)})
        self.assertTrue(reader.read("temperature"))
        self.assertFalse(reader.read("temperature"))

    def test_a_helper_is_never_read_on_the_loop(self):
        # `command()` is how the daemon tells the two apart, and `read()` has
        # to refuse the one it would have to wait for.
        reader = self._pointed_at({"fps": ("cmd", "print-fps")})
        self.assertEqual(reader.command("fps"), "print-fps")
        self.assertFalse(reader.read("fps"))

    def test_what_this_side_answers_has_no_command(self):
        reader = self._pointed_at({"memory": ("proc", "meminfo")})
        self.assertIsNone(reader.command("memory"))

    def test_a_helper_comes_back_through_the_same_door(self):
        reader = self._pointed_at(
            {"gpu": ("cmd", "ask")}, units={"gpu": "%"})
        self.assertTrue(reader.answered("gpu", ["17"]))
        # A helper's number is already the percentage, where `cpu`'s is a
        # share of one - which is what `scale` is for, and why only the
        # readings this side computes carry one.
        self.assertEqual(reader.words("gpu"), "17%")

    def test_a_helper_that_printed_nothing_is_not_an_answer(self):
        reader = self._pointed_at({"gpu": ("cmd", "ask")})
        self.assertFalse(reader.answered("gpu", ["no device"]))

    def test_a_configured_scale_is_what_the_number_is_divided_by(self):
        # The two free-form readings say what they count in, because nothing
        # else can know: a helper that prints millivolts and one that prints
        # a percentage are the same string to this module.
        reader = self._pointed_at(
            {"fps": ("cmd", "ask")}, divisors={"fps": 1000.0})
        reader.answered("fps", ["59940"])
        self.assertEqual(reader.words("fps"), "59.9 fps")

    def test_only_a_reading_with_a_source_is_named(self):
        reader = self._pointed_at({"cpu": ("proc", "stat"), "fan": None})
        self.assertEqual(reader.named(), ["cpu"])
        self.assertFalse(reader.has("fan"))


class OnlySomeReadingsHaveABarToDraw(unittest.TestCase):
    """A percentage is somewhere along a known travel; a temperature is not.

    There is no top of the scale for a thermometer that is not made up, and a
    bar drawn against a made-up maximum says a different thing on every
    machine it is read on.
    """

    def setUp(self):
        self.config = shipped()
        self.config.sysinfo_sources = {}
        self.config.sysinfo_units = {}
        self.config.sysinfo_divisors = {}
        self.reader = Sysinfo(self.config)

    def test_a_share_has_one(self):
        self.reader.took("cpu", 0.37)
        self.assertAlmostEqual(self.reader.fraction("cpu"), 0.37)

    def test_a_temperature_has_none(self):
        self.reader.took("temperature", 54.0)
        self.assertIsNone(self.reader.fraction("temperature"))

    def test_a_reading_that_has_never_answered_has_none(self):
        self.assertIsNone(self.reader.fraction("cpu"))

    def test_every_reading_with_a_full_is_a_share(self):
        # The pair that has to hold: a `full` of 1.0 is what says the value is
        # already a fraction, so anything counted in something else needs its
        # own top of scale or no bar at all.
        for name, spec in sysinfo.READINGS.items():
            if spec.get("full"):
                self.assertEqual(spec["full"], 1.0, name)
                self.assertEqual(spec.get("scale"), 100, name)


class TheShippedSourcesAreTrueOfEveryLinux(unittest.TestCase):
    def test_three_ship_with_a_source_and_the_rest_are_empty(self):
        # Three because three are true of every machine. The rest are left
        # empty deliberately: a sensor picked for somebody prints the wrong
        # number under the right word, which is worse than no tile.
        config = shipped()
        named = [name for name in sysinfo.READINGS
                 if config.sysinfo_sources.get(name)]
        self.assertEqual(sorted(named), ["cpu", "disk", "memory"])

    def test_every_reading_the_module_has_is_in_the_shipped_config(self):
        # A reading with no line in config.toml is one nobody can turn on
        # without reading the source.
        with open(os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), "config", "config.toml")) as fh:
            text = fh.read()
        for name in sysinfo.READINGS:
            self.assertIn("\n%s = " % name, text, name)


if __name__ == "__main__":
    unittest.main()
