import pytest
import os
import socket
import re

from tempfile import TemporaryDirectory

IN_GITHUB_ACTIONS = os.getenv("GITHUB_ACTIONS") == "true"

def write_conf(path):
    conf_path = os.path.join(path, ".notmuch-config")
    with open(conf_path, "w", encoding="utf-8") as f:
        f.write(f'[database]\npath={path}\n[search]\nexclude_tags=deleted\n[new]\ntags=')
    return conf_path


def init(shell, local, remote):
    assert shell.run("cp", "-r", "test/mails", local).returncode == 0
    assert shell.run("cp", "-r", "test/mails", remote).returncode == 0
    local_conf = write_conf(local)
    remote_conf = write_conf(remote)
    assert shell.run("notmuch", "new", env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
    assert shell.run("notmuch", "new", env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0

    assert shell.run("notmuch", "count", "*", env={"NOTMUCH_CONFIG": local_conf}).data == 4
    assert shell.run("notmuch", "count", "*", env={"NOTMUCH_CONFIG": remote_conf}).data == 4
    return (local_conf, remote_conf)


def sync(shell, local_conf, remote_conf):
    res = shell.run("./src/notmuch-sync", "--host", "remote",
                    "--remote-cmd", f"bash -c 'NOTMUCH_CONFIG={remote_conf} ./src/notmuch-sync --host local'",
                    env={"NOTMUCH_CONFIG": local_conf})
    assert res.returncode == 0


def initial_sync(shell, local, local_conf, remote, remote_conf):
    sync(shell, local_conf, remote_conf)
    local_sync_file = os.path.join(local, ".notmuch", "notmuch-sync-remote")
    assert os.path.exists(local_sync_file)
    with open(local_sync_file, "r", encoding="utf-8") as f:
        assert re.match('4 [0-9a-z-]+', f.read())

    remote_sync_file = os.path.join(remote, ".notmuch", "notmuch-sync-local")
    assert os.path.exists(remote_sync_file)
    with open(remote_sync_file, "r", encoding="utf-8") as f:
        assert re.match('4 [0-9a-z-]+', f.read())


def test_sync_initial(shell):
    with TemporaryDirectory() as local:
        with TemporaryDirectory() as remote:
            (local_conf, remote_conf) = init(shell, local, remote)
            initial_sync(shell, local, local_conf, remote, remote_conf)
            initial_sync(shell, local, local_conf, remote, remote_conf)


def test_sync_tags(shell):
    with TemporaryDirectory() as local:
        with TemporaryDirectory() as remote:
            (local_conf, remote_conf) = init(shell, local, remote)
            initial_sync(shell, local, local_conf, remote, remote_conf)

            assert shell.run("notmuch", "tag", "+local", "id:874llc2bkp.fsf@curie.anarc.at",
                             env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+local", "id:20111101080303.30A10409E@asxas.net",
                             env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+unread", "id:87d1dajhgf.fsf@example.net",
                             env={"NOTMUCH_CONFIG": local_conf}).returncode == 0

            assert shell.run("notmuch", "tag", "+remote", "id:87d1dajhgf.fsf@example.net",
                             env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+remote", "id:20111101080303.30A10409E@asxas.net",
                             env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+remote", "id:1258848661-4660-2-git-send-email-stefan@datenfreihafen.org",
                             env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0

            sync(shell, local_conf, remote_conf)

            assert shell.run("notmuch", "search", "--output=tags", "--format=json", "id:874llc2bkp.fsf@curie.anarc.at",
                             env={"NOTMUCH_CONFIG": local_conf}).data == ["attachment", "local"]
            assert shell.run("notmuch", "search", "--output=tags", "--format=json", "id:874llc2bkp.fsf@curie.anarc.at",
                             env={"NOTMUCH_CONFIG": remote_conf}).data == ["attachment", "local"]
            assert shell.run("notmuch", "search", "--output=tags", "--format=json", "id:1258848661-4660-2-git-send-email-stefan@datenfreihafen.org",
                             env={"NOTMUCH_CONFIG": local_conf}).data == ["remote"]
            assert shell.run("notmuch", "search", "--output=tags", "--format=json", "id:1258848661-4660-2-git-send-email-stefan@datenfreihafen.org",
                             env={"NOTMUCH_CONFIG": remote_conf}).data == ["remote"]
            assert shell.run("notmuch", "search", "--output=tags", "--format=json", "id:20111101080303.30A10409E@asxas.net",
                             env={"NOTMUCH_CONFIG": local_conf}).data == ["attachment", "local", "remote"]
            assert shell.run("notmuch", "search", "--output=tags", "--format=json", "id:20111101080303.30A10409E@asxas.net",
                             env={"NOTMUCH_CONFIG": remote_conf}).data == ["attachment", "local", "remote"]
            assert shell.run("notmuch", "search", "--output=tags", "--format=json", "id:87d1dajhgf.fsf@example.net",
                             env={"NOTMUCH_CONFIG": local_conf}).data == ["remote", "unread"]
            assert shell.run("notmuch", "search", "--output=tags", "--format=json", "id:87d1dajhgf.fsf@example.net",
                             env={"NOTMUCH_CONFIG": remote_conf}).data == ["remote", "unread"]

            local_sync_file = os.path.join(local, ".notmuch", "notmuch-sync-remote")
            assert os.path.exists(local_sync_file)
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert re.match('10 [0-9a-z-]+', f.read())

            remote_sync_file = os.path.join(remote, ".notmuch", "notmuch-sync-local")
            assert os.path.exists(remote_sync_file)
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert re.match('10 [0-9a-z-]+', f.read())
