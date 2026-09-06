"""The socket directory, which is the only access control the sockets have.

Nothing on these sockets is authenticated, so the daemon's whole defence
against another user on the machine is where it puts them. These tests are
about the fallback: what happens when $XDG_RUNTIME_DIR is not there to be
private for us.
"""

import os
import stat
import tempfile
import unittest

import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omapad import paths
from omapad import viewsock


class SocketDirTests(unittest.TestCase):
    def setUp(self):
        self.runtime = tempfile.mkdtemp()
        self.saved = os.environ.get("XDG_RUNTIME_DIR")
        os.environ["XDG_RUNTIME_DIR"] = self.runtime

    def tearDown(self):
        if self.saved is None:
            os.environ.pop("XDG_RUNTIME_DIR", None)
        else:
            os.environ["XDG_RUNTIME_DIR"] = self.saved

    def test_lives_under_the_runtime_directory(self):
        self.assertEqual(paths.socket_dir(),
                         os.path.join(self.runtime, "omapad"))
        self.assertEqual(paths.socket_path("osk.sock"),
                         os.path.join(self.runtime, "omapad", "osk.sock"))

    def test_created_private(self):
        created = paths.socket_dir(create=True)
        mode = os.stat(created).st_mode
        self.assertFalse(mode & (stat.S_IRWXG | stat.S_IRWXO),
                         "the socket directory must not be readable by others")

    def test_never_falls_back_to_bare_tmp(self):
        """The point of the whole module: /tmp belongs to everybody."""
        os.environ["XDG_RUNTIME_DIR"] = os.path.join(self.runtime, "gone")
        where = paths.socket_dir()
        # Under /tmp is fine; being /tmp, or a name every user would pick, is
        # not - the first one to create it owns what the daemon binds inside.
        self.assertNotIn(where, ("/tmp", "/tmp/omapad"))
        self.assertIn(str(os.getuid()), os.path.basename(where))


class EnsurePrivateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_missing_path_is_not_an_error(self):
        # Whoever binds or connects reports it better than a guess here would.
        paths.ensure_private(os.path.join(self.tmp, "nothing"))

    def test_rejects_a_directory_others_can_write_to(self):
        loose = os.path.join(self.tmp, "loose")
        os.makedirs(loose, mode=0o777)
        os.chmod(loose, 0o777)
        with self.assertRaises(paths.RuntimeDirError):
            paths.ensure_private(loose)

    def test_rejects_a_symlink(self):
        """A symlink would otherwise pass every check by describing its target."""
        real = os.path.join(self.tmp, "real")
        os.makedirs(real, mode=0o700)
        link = os.path.join(self.tmp, "link")
        os.symlink(real, link)
        with self.assertRaises(paths.RuntimeDirError):
            paths.ensure_private(link)

    def test_rejects_a_directory_owned_by_someone_else(self):
        ours = os.path.join(self.tmp, "theirs")
        os.makedirs(ours, mode=0o700)
        real_getuid = os.getuid
        os.getuid = lambda: real_getuid() + 1
        try:
            with self.assertRaises(paths.RuntimeDirError):
                paths.ensure_private(ours)
        finally:
            os.getuid = real_getuid


class PrivateDirReasonTests(unittest.TestCase):
    """The half that answers instead of refusing.

    A socket path in the config is the user's own choice, so it is taken as
    written - but nothing on these sockets is authenticated, and the control
    one reaches every `exec:` a binding can run. Saying so once, where it is
    bound, is what is left.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_a_private_directory_has_nothing_to_say(self):
        private = os.path.join(self.tmp, "private")
        os.makedirs(private, mode=0o700)
        self.assertIsNone(
            paths.private_dir_reason(os.path.join(private, "control.sock")))

    def test_a_directory_others_can_write_to_says_why(self):
        loose = os.path.join(self.tmp, "loose")
        os.makedirs(loose, mode=0o777)
        os.chmod(loose, 0o777)
        reason = paths.private_dir_reason(os.path.join(loose, "control.sock"))
        self.assertIsNotNone(reason)
        self.assertIn("writable by other users", reason)

    def test_a_directory_that_is_not_there_yet_is_not_a_complaint(self):
        # Nothing to be public about, and whoever binds says so better.
        self.assertIsNone(
            paths.private_dir_reason(os.path.join(self.tmp, "gone", "x.sock")))


class ViewClientFallbackTests(unittest.TestCase):
    """A surface that cannot be reached privately is a surface that is not drawn."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.saved = os.environ.get("XDG_RUNTIME_DIR")
        os.environ["XDG_RUNTIME_DIR"] = self.tmp
        loose = os.path.join(self.tmp, "omapad")
        os.makedirs(loose, mode=0o700)
        os.chmod(loose, 0o777)

    def tearDown(self):
        if self.saved is None:
            os.environ.pop("XDG_RUNTIME_DIR", None)
        else:
            os.environ["XDG_RUNTIME_DIR"] = self.saved

    def test_send_stays_best_effort(self):
        client = viewsock.ViewClient("osk.sock")
        self.assertIsNone(client.path)
        self.assertFalse(client.connect())
        client.send({"open": True})   # never raises, by contract


if __name__ == "__main__":
    unittest.main()
