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
import subprocess
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


class UnitInstallTests(unittest.TestCase):
    """Who writes the systemd unit, now that the shell no longer does.

    The unit names the checkout in `ExecStart`, and the installer used to bake
    it in with `sed` and land it with `>`. A path is not replacement syntax,
    and a redirection writes through a symlink someone else put at the
    destination. Both halves moved to `omapad/unit.py`, where
    `tests/test_unit.py` can reach them; these are the guards against either
    half coming back as one convenient line.
    """

    def setUp(self):
        with open(os.path.join(REPO, "install.sh")) as handle:
            self.install = handle.read()
        self.lines = [line for line in self.install.split("\n")
                      if not line.lstrip().startswith("#")]

    def test_the_command_installs_it(self):
        self.assertIn('"$REPO/bin/omapad" unit', self.install)

    def test_nothing_is_redirected_into_a_unit(self):
        for line in self.lines:
            if ">" in line:
                self.assertNotIn("omapad.service", line, line.strip())

    def test_no_path_is_substituted_by_sed(self):
        for line in self.lines:
            self.assertNotIn("sed ", line, line.strip())

    def test_the_checkout_path_is_judged_before_anything_is_written(self):
        # A checkout that cannot be baked into a unit is worth saying before
        # the password prompt, not after four steps have already run.
        checked = self.install.index('"$REPO/bin/omapad" unit check')
        self.assertLess(checked, self.install.index("sudo "))
        self.assertLess(checked, self.install.index('cat >"$CONFIG_DIR'))


class PayloadTests(unittest.TestCase):
    """What the tree may contain, given that the tree is what ships.

    `omarchy plugin add` clones this checkout into
    `~/.config/omarchy/plugins/canerakdas.omapad`, and `boot.sh` clones it
    there too: every tracked file lands on the machine of someone who wanted an
    on-screen keyboard. A file a coding agent loads by itself - a skill, a
    rules file - is then instructions that arrive inside that payload and are
    read without anyone asking for them, with whatever their tools can reach.
    The jobs live in `docs/procedures/` as prose, which an agent sees only when
    its owner hands it over; the rule is `docs/conventions/procedures.md`, and
    this is what keeps one from coming back as a convenient folder.
    """

    # Formats a tool picks up on its own, by path rather than by content. A
    # name costs nothing here; the one added after the fact is the one that
    # already shipped.
    LOADED_BY_AGENTS = frozenset((
        ".claude",
        ".claude-plugin",
        ".clinerules",
        ".cursor",
        ".cursorrules",
        ".github/copilot-instructions.md",
        ".mcp.json",
        ".windsurfrules",
        "agents.md",
        "claude.md",
        "copilot-instructions.md",
        "gemini.md",
        "skill.md",
    ))

    def tracked(self):
        # Only what git carries: an untracked `.claude/` is the developer's own
        # wiring, `.gitignore` covers it, and a clone never sees it.
        try:
            found = subprocess.run(
                ["git", "-C", REPO, "ls-files", "-z"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except OSError:
            self.skipTest("git is not available")
        if found.returncode != 0:
            self.skipTest("not a git checkout")
        return [path for path in found.stdout.decode().split("\0") if path]

    def test_nothing_tracked_is_addressed_to_an_agent(self):
        for path in self.tracked():
            segments = [segment.lower() for segment in path.split("/")]
            for segment in segments:
                self.assertNotIn(
                    segment, self.LOADED_BY_AGENTS,
                    "%s ships to a user's machine and is loaded by a tool "
                    "there; see docs/conventions/procedures.md" % path)
            self.assertNotIn(path.lower(), self.LOADED_BY_AGENTS, path)

    def test_the_procedures_are_still_in_the_tree(self):
        # The rule above is satisfiable by deleting the knowledge, which is not
        # the trade this project made.
        procedures = [path for path in self.tracked()
                      if path.startswith("docs/procedures/pad-")]
        self.assertEqual(len(procedures), 7, procedures)


if __name__ == "__main__":
    unittest.main()
