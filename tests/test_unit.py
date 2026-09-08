"""Installing the systemd unit: what the path may be, and where it lands.

Two failures are being kept closed here. The path is baked into `ExecStart`,
and it used to be baked in as `sed` replacement syntax, where `&` means the
whole match and the delimiter and a newline end the command. And the unit was
written with a plain redirection, which opens whatever name is already there:
a symlink at `omapad.service` made the installer truncate its target, and an
interruption left half a unit where systemd reads it.

So the tests are about the failing paths, not the happy one: a destination
somebody else put there, a path that used to be syntax, and a write that stops
half way.
"""

import contextlib
import io
import os
import shutil
import stat
import tempfile
import unittest
from unittest import mock

import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad import unit
from omapad.__main__ import main

TEMPLATE = "[Service]\nExecStart=__REPO__/bin/omapad run\nEnvironment=X=%t\n"


class TempDirTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.dest = os.path.join(self.dir, unit.NAME)

    def leftovers(self):
        """Everything in the destination's directory but the unit itself."""
        return [name for name in os.listdir(self.dir) if name != unit.NAME]


class PathTests(unittest.TestCase):
    """Which checkout paths can be written into a unit at all."""

    def test_takes_an_ordinary_checkout(self):
        for path in ("/home/me/gamepadd",
                     "/home/me/.config/omarchy/plugins/canerakdas.omapad",
                     "/srv/build-2.0/pad_files/a+b/c.d:e=f,g@h/"):
            self.assertEqual(unit.check_repo(path), path)

    def test_refuses_what_used_to_be_syntax(self):
        # `&` is the whole match in a sed replacement, `|` was the delimiter,
        # `\\` escapes, and a newline ends the command - the four ways the old
        # one-liner could be made to write a unit nobody wrote.
        for path in ("/home/me/a&b", "/home/me/a|b", "/home/me/a\\b",
                     "/home/me/a\nb", "/home/me/a\nExecStart=/bin/sh"):
            with self.assertRaises(unit.UnitError):
                unit.check_repo(path)

    def test_refuses_what_systemd_would_read(self):
        # A space splits ExecStart into two words and `%` is a specifier;
        # neither can be quoted or escaped into meaning the path.
        for path in ("/home/me/my pad", "/home/me/100%", "/home/me/a\tb"):
            with self.assertRaises(unit.UnitError):
                unit.check_repo(path)

    def test_refuses_a_path_that_is_not_one(self):
        for path in ("", None, "gamepadd", "../gamepadd", "/home/me/a\0b"):
            with self.assertRaises(unit.UnitError):
                unit.check_repo(path)

    def test_says_which_path_it_refused(self):
        # The message is the whole fix - the user moves the checkout - so it
        # has to name what was wrong with the one they have.
        with self.assertRaises(unit.UnitError) as caught:
            unit.check_repo("/home/me/my pad")
        self.assertIn("my pad", str(caught.exception))


class RenderTests(unittest.TestCase):
    def test_bakes_the_path_in_as_data(self):
        text = unit.render(TEMPLATE, "/srv/a+b/c.d:e=f")
        self.assertEqual(
            text, "[Service]\nExecStart=/srv/a+b/c.d:e=f/bin/omapad run\n"
                  "Environment=X=%t\n")

    def test_leaves_the_units_own_specifiers_alone(self):
        # `%t` is systemd's runtime directory and the reason the unit works
        # under a user session; a substitution that touched it would be worse
        # than the one it replaced.
        self.assertIn("Environment=X=%t\n", unit.render(TEMPLATE, "/srv/pad"))

    def test_a_refused_path_never_reaches_the_template(self):
        with self.assertRaises(unit.UnitError):
            unit.render(TEMPLATE, "/srv/a&b")

    def test_refuses_a_template_with_nothing_to_replace(self):
        with self.assertRaises(unit.UnitError):
            unit.render("[Service]\nExecStart=/bin/true\n", "/srv/pad")


class TemplateTests(TempDirTest):
    def test_reads_the_template(self):
        path = os.path.join(self.dir, "omapad.service.in")
        with open(path, "w") as handle:
            handle.write(TEMPLATE)
        self.assertEqual(unit.read_template(path), TEMPLATE)

    def test_refuses_a_file_that_is_not_a_unit(self):
        # Bounded: a page of text is a unit, a megabyte of anything is not,
        # and what is rendered has to be bytes that were looked at.
        path = os.path.join(self.dir, "omapad.service.in")
        with open(path, "w") as handle:
            handle.write("x" * (unit.MAX_TEMPLATE + 1))
        with self.assertRaises(unit.UnitError):
            unit.read_template(path)


class InstallTests(TempDirTest):
    def test_writes_the_unit_readable(self):
        unit.install("[Unit]\n", self.dest)
        with open(self.dest) as handle:
            self.assertEqual(handle.read(), "[Unit]\n")
        self.assertEqual(stat.S_IMODE(os.stat(self.dest).st_mode), 0o644)
        self.assertEqual(self.leftovers(), [])

    def test_replaces_a_unit_that_is_already_there(self):
        with open(self.dest, "w") as handle:
            handle.write("[Unit]\nold\n")
        unit.install("[Unit]\nnew\n", self.dest)
        with open(self.dest) as handle:
            self.assertEqual(handle.read(), "[Unit]\nnew\n")

    def test_makes_the_unit_directory(self):
        dest = os.path.join(self.dir, "systemd", "user", unit.NAME)
        unit.install("[Unit]\n", dest)
        self.assertTrue(os.path.isfile(dest))

    def test_reads_the_unit_back(self):
        unit.install("[Unit]\n", self.dest)
        unit.verify("[Unit]\n", self.dest)
        with self.assertRaises(unit.UnitError):
            unit.verify("[Unit]\nsomething else\n", self.dest)


class PlantedDestinationTests(TempDirTest):
    """A name at the destination that this installer did not put there."""

    def setUp(self):
        super().setUp()
        self.victim = os.path.join(self.dir, "someone-elses-file")
        with open(self.victim, "w") as handle:
            handle.write("mine\n")

    def test_refuses_a_symlink_and_leaves_its_target_alone(self):
        os.symlink(self.victim, self.dest)
        with self.assertRaises(unit.UnitError):
            unit.install("[Unit]\n", self.dest)
        with open(self.victim) as handle:
            self.assertEqual(handle.read(), "mine\n")
        self.assertTrue(os.path.islink(self.dest))
        self.assertEqual(sorted(self.leftovers()), ["someone-elses-file"])

    def test_refuses_a_dangling_symlink(self):
        # The dangerous half of the old redirection: `-f` is false here, so
        # nothing was kept, and `>` created the target the link named.
        planted = os.path.join(self.dir, "not-yet")
        os.symlink(planted, self.dest)
        with self.assertRaises(unit.UnitError):
            unit.install("[Unit]\n", self.dest)
        self.assertFalse(os.path.exists(planted))

    def test_refuses_anything_that_is_not_a_regular_file(self):
        os.mkdir(self.dest)
        with self.assertRaises(unit.UnitError):
            unit.install("[Unit]\n", self.dest)
        self.assertTrue(os.path.isdir(self.dest))

    def test_says_what_it_found(self):
        os.symlink(self.victim, self.dest)
        with self.assertRaises(unit.UnitError) as caught:
            unit.install("[Unit]\n", self.dest)
        self.assertIn("symlink", str(caught.exception))


class InterruptedTests(TempDirTest):
    """A write that stops half way leaves the unit that was already there."""

    def setUp(self):
        super().setUp()
        with open(self.dest, "w") as handle:
            handle.write("[Unit]\nold\n")

    def assert_untouched(self):
        with open(self.dest) as handle:
            self.assertEqual(handle.read(), "[Unit]\nold\n")
        self.assertEqual(self.leftovers(), [])

    def test_an_interruption_before_the_rename(self):
        with mock.patch("os.rename", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                unit.install("[Unit]\nnew\n", self.dest)
        self.assert_untouched()

    def test_an_interruption_while_writing(self):
        with mock.patch("os.fsync", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                unit.install("[Unit]\nnew\n", self.dest)
        self.assert_untouched()

    def test_a_full_disk(self):
        with mock.patch("os.rename", side_effect=OSError(28, "No space left")):
            with self.assertRaises(OSError):
                unit.install("[Unit]\nnew\n", self.dest)
        self.assert_untouched()

    def test_nothing_is_left_where_there_was_no_unit(self):
        os.unlink(self.dest)
        with mock.patch("os.rename", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                unit.install("[Unit]\nnew\n", self.dest)
        self.assertFalse(os.path.exists(self.dest))
        self.assertEqual(self.leftovers(), [])


class ServiceTests(TempDirTest):
    """The whole job: a checkout in, a unit at the destination."""

    def repo_at(self, name):
        repo = os.path.join(self.dir, name)
        os.makedirs(os.path.join(repo, "systemd"))
        with open(os.path.join(repo, "systemd", unit.NAME), "w") as handle:
            handle.write(TEMPLATE)
        return repo

    def test_installs_the_unit_for_a_checkout(self):
        repo = self.repo_at("gamepadd")
        dest = os.path.join(self.dir, "user", unit.NAME)
        self.assertEqual(unit.install_service(repo=repo, dest=dest), dest)
        with open(dest) as handle:
            self.assertIn("ExecStart=%s/bin/omapad run\n" % repo, handle.read())

    def test_a_checkout_that_cannot_be_baked_in_writes_nothing(self):
        repo = self.repo_at("game&padd")
        dest = os.path.join(self.dir, "user", unit.NAME)
        with self.assertRaises(unit.UnitError):
            unit.install_service(repo=repo, dest=dest)
        self.assertFalse(os.path.exists(dest))


class CommandTests(TempDirTest):
    """`omapad unit`, which is the half of `install.sh` that decides."""

    def setUp(self):
        super().setUp()
        self.saved = os.environ.get("OMAPAD_UNIT_DIR")
        os.environ["OMAPAD_UNIT_DIR"] = self.dir
        self.addCleanup(self.restore)

    def restore(self):
        if self.saved is None:
            os.environ.pop("OMAPAD_UNIT_DIR", None)
        else:
            os.environ["OMAPAD_UNIT_DIR"] = self.saved

    def test_the_destination_follows_the_environment(self):
        self.assertEqual(unit.unit_dir(), self.dir)

    def run_main(self, words):
        """The path it printed, with stdout kept out of the test report."""
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            status = main(words)
        return status, printed.getvalue().strip()

    def test_installs_this_checkout(self):
        if not unit.SAFE.match(unit.checkout()):
            self.skipTest("this checkout's own path cannot be baked into a unit")
        status, printed = self.run_main(["unit"])
        self.assertEqual(status, 0)
        self.assertEqual(printed, self.dest)
        with open(self.dest) as handle:
            self.assertIn("ExecStart=%s/bin/omapad run" % unit.checkout(),
                          handle.read())

    def test_check_writes_nothing(self):
        if not unit.SAFE.match(unit.checkout()):
            self.skipTest("this checkout's own path cannot be baked into a unit")
        status, printed = self.run_main(["unit", "check"])
        self.assertEqual(status, 0)
        self.assertEqual(printed, unit.checkout())
        self.assertFalse(os.path.exists(self.dest))

    def test_refuses_a_verb_it_does_not_have(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["unit", "install"]), 2)


if __name__ == "__main__":
    unittest.main()
