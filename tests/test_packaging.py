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


if __name__ == "__main__":
    unittest.main()
