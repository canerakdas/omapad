"""What a release has to look like from outside the checkout.

The plugin is submitted to the marketplace as a commit SHA, and the same SHA is
what a validation and a security baseline attest. Anything that makes the
submitted snapshot a different object from the branch tip - a version that
disagrees with itself, a commit whose only job is to move a pin - breaks that
silently: the install keeps working, and only the review fails, weeks later.
"""

import json
import os
import re
import unittest

import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import omapad

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class VersionTests(unittest.TestCase):
    def test_the_manifest_and_the_package_agree(self):
        # Two files carry the version and nothing else reads them together;
        # the shell installs one half and the daemon reports the other.
        with open(os.path.join(REPO, "manifest.json")) as handle:
            manifest = json.load(handle)
        self.assertEqual(manifest["version"], omapad.__version__)


class BootPinTests(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(REPO, "boot.sh")) as handle:
            self.boot = handle.read()

    def test_names_no_commit_of_its_own(self):
        # A SHA in here can only ever be an earlier commit than the one being
        # released, which is what put the review and the branch out of step.
        self.assertEqual(re.findall(r"\b[0-9a-f]{40}\b", self.boot), [])

    def test_the_pin_has_no_default(self):
        self.assertIn('SHA="${OMAPAD_SHA:-}"', self.boot)

    def test_refuses_an_unset_pin(self):
        self.assertIn("OMAPAD_SHA is not set", self.boot)


class UdevRuleTests(unittest.TestCase):
    """What `sudo` is handed, and where those bytes came from.

    The checkout is writable by the user running the installer, and `sudo`
    opens a source path only when it finally runs - on the far side of a
    password prompt someone stood waiting at. A rule read from the tree could
    be a different file by then, and a udev rule names things to run as root.
    """

    def setUp(self):
        with open(os.path.join(REPO, "install.sh")) as handle:
            self.install = handle.read()
        with open(os.path.join(REPO, "udev", "99-omapad-uinput.rules")) as handle:
            self.rule = handle.read()

    def test_the_rule_it_installs_is_the_rule_in_the_repository(self):
        # Two copies of one file, which is the cost of the here-document; this
        # is what stops them drifting.
        found = re.search(r"<<'RULE'\n(.*?)\nRULE\n", self.install, re.S)
        self.assertIsNotNone(found, "install.sh no longer carries the rule")
        self.assertEqual(found.group(1) + "\n", self.rule)

    def test_nothing_privileged_reads_a_path_in_the_checkout(self):
        for line in self.install.split("\n"):
            if "sudo " in line and not line.lstrip().startswith("#"):
                self.assertNotIn("$REPO", line, line.strip())

    def test_the_rule_is_read_back_before_anything_acts_on_it(self):
        # `udevadm trigger` is what makes a rule real, so what is on disk is
        # compared with what was sent before the reload gets that far.
        self.assertIn("sudo cmp -s -", self.install)
        self.assertLess(self.install.index("sudo cmp -s -"),
                        self.install.index("udevadm control"))


if __name__ == "__main__":
    unittest.main()
