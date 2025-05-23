import pytest
import os
import socket
import re

from tempfile import TemporaryDirectory

def write_conf(path):
    conf_path = os.path.join(path, ".notmuch-config")
    with open(conf_path, "w", encoding="utf-8") as f:
        f.write(f'[database]\npath={path}\n[search]\nexclude_tags=deleted')
    return conf_path

def test_sync_initial(shell):
    with TemporaryDirectory() as local:
        with TemporaryDirectory() as remote:
            assert shell.run("cp", "-r", "test/mails", local).returncode == 0
            assert shell.run("cp", "-r", "test/mails", remote).returncode == 0
            local_conf = write_conf(local)
            remote_conf = write_conf(remote)
            assert shell.run("notmuch", "new", env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
            assert shell.run("notmuch", "new", env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0

            assert shell.run("notmuch", "count", "*", env={"NOTMUCH_CONFIG": local_conf}).data == 4
            assert shell.run("notmuch", "count", "*", env={"NOTMUCH_CONFIG": remote_conf}).data == 4

            def sync():
                res = shell.run("./src/notmuch-sync", "--host", "remote",
                                "--remote-cmd", f"bash -c 'NOTMUCH_CONFIG={remote_conf} ./src/notmuch-sync --host local'",
                                env={"NOTMUCH_CONFIG": local_conf})
                assert res.returncode == 0

                local_sync_file = os.path.join(local, ".notmuch", "notmuch-sync-remote")
                assert os.path.exists(local_sync_file)
                with open(local_sync_file, "r", encoding="utf-8") as f:
                    assert re.match('4 [0-9a-z-]+', f.read())

                remote_sync_file = os.path.join(remote, ".notmuch", "notmuch-sync-local")
                assert os.path.exists(remote_sync_file)
                with open(remote_sync_file, "r", encoding="utf-8") as f:
                    assert re.match('4 [0-9a-z-]+', f.read())

            sync()
            sync()
