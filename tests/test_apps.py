"""What is installed, read the way Omarchy's launcher reads it."""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad import apps


class InstalledTests(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="omapad-apps-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.near = os.path.join(self.root, "near")
        self.far = os.path.join(self.root, "far")

    def entry(self, folder, name, **fields):
        path = os.path.join(folder, name + ".desktop")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        lines = ["[Desktop Entry]", "Type=Application"]
        lines += ["%s=%s" % pair for pair in sorted(fields.items())]
        with open(path, "w") as handle:
            handle.write("\n".join(lines) + "\n")

    def installed(self, hidden=()):
        return apps.installed([self.near, self.far], hidden)

    def test_an_entry_is_named_by_its_file(self):
        self.entry(self.far, "steam", Name="Steam", Icon="steam",
                   StartupWMClass="steam", Categories="Game;")
        self.assertEqual(self.installed(), {"steam": {
            "id": "steam", "name": "Steam", "icon": "steam",
            "wmclass": "steam", "kind": "games"}})

    def test_the_nearest_one_decides_even_by_being_hidden(self):
        # The user's own directory shadows the system's, which is how a
        # person hides one the system shipped.
        self.entry(self.far, "zoom", Name="Zoom")
        self.entry(self.near, "zoom", Name="Zoom", Hidden="true")
        self.assertEqual(self.installed(), {})

    def test_what_every_launcher_leaves_out_is_left_out(self):
        self.entry(self.far, "helper", Name="Helper", NoDisplay="true")
        self.entry(self.far, "link", Name="Link", Type="Link")
        self.entry(self.far, "nameless")
        self.assertEqual(self.installed(), {})

    def test_what_omarchy_hides_is_hidden(self):
        self.entry(self.far, "cmake-gui", Name="CMake")
        self.assertEqual(self.installed(hidden=["cmake-gui"]), {})

    def test_an_id_in_a_folder_is_joined_with_a_dash(self):
        # The freedesktop rule, and the one Omarchy's hiding script applies.
        self.entry(self.far, os.path.join("kde", "dolphin"), Name="Dolphin")
        self.assertEqual(list(self.installed()), ["kde-dolphin"])

    def test_a_field_code_is_not_an_interpolation(self):
        self.entry(self.far, "files", Name="Files", Exec="nautilus %U")
        self.assertEqual(self.installed()["files"]["name"], "Files")

    def test_a_webapp_is_the_internet(self):
        self.entry(self.far, "youtube", Name="YouTube",
                   Exec="omarchy-launch-webapp https://youtube.com")
        self.assertEqual(self.installed()["youtube"]["kind"], "internet")

    def test_the_first_kind_named_wins_and_the_rest_is_other(self):
        self.entry(self.far, "a", Name="A", Categories="Utility;Game;")
        self.entry(self.far, "b", Name="B", Categories="Utility;")
        found = self.installed()
        self.assertEqual(found["a"]["kind"], "games")
        self.assertEqual(found["b"]["kind"], "other")


class WireTests(unittest.TestCase):

    def test_the_index_survives_the_trip(self):
        index = {"org.telegram.desktop": {
            "id": "org.telegram.desktop", "kind": "internet",
            "name": "Telegram\tDesktop", "icon": "telegram", "wmclass": ""}}
        back = apps.parse(apps.lines(index))
        self.assertEqual(back["org.telegram.desktop"]["name"],
                         "Telegram Desktop")
        self.assertEqual(back["org.telegram.desktop"]["wmclass"], "")

    def test_a_line_stripped_of_its_empty_fields_is_still_read(self):
        # The command worker strips what it reads, and an entry with no
        # window class ends in the tab that goes with it.
        index = {"files": {"id": "files", "kind": "system", "name": "Files",
                           "icon": "", "wmclass": ""}}
        sent = [line.strip() for line in apps.lines(index)]
        self.assertEqual(apps.parse(sent), index)

    def test_a_bad_line_is_skipped(self):
        self.assertEqual(apps.parse(["nonsense", "\tgames\t\t\t"]), {})

    def test_kinds_with_nothing_in_them_are_not_offered(self):
        index = {"b": {"id": "b", "name": "beta", "kind": "games"},
                 "a": {"id": "a", "name": "Alpha", "kind": "games"}}
        found = apps.by_kind(index)
        self.assertEqual([(name, [entry["id"] for entry in entries])
                          for name, _, entries in found],
                         [("games", ["a", "b"])])

    def test_it_launches_the_way_omarchy_launches_it(self):
        self.assertEqual(apps.launch("org.telegram.desktop"),
                         "uwsm-app -- gtk-launch org.telegram.desktop.desktop")
        self.assertEqual(apps.launch("Disk Usage"),
                         "uwsm-app -- gtk-launch 'Disk Usage.desktop'")


class OmarchyHiddenTests(unittest.TestCase):

    def test_the_hides_file_is_read_with_or_without_the_suffix(self):
        root = tempfile.mkdtemp(prefix="omapad-omarchy-")
        self.addCleanup(shutil.rmtree, root, True)
        path = os.path.join(root, apps.HIDES_FILE)
        os.makedirs(os.path.dirname(path))
        with open(path, "w") as handle:
            handle.write("btop\ncmake-gui.desktop\n\n")
        self.assertEqual(apps.omarchy_hidden(root), {"btop", "cmake-gui"})

    def test_no_omarchy_hides_nothing(self):
        self.assertEqual(apps.omarchy_hidden(""), set())


if __name__ == "__main__":
    unittest.main()
