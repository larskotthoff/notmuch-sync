import pytest
import os
import socket
import re
import shutil
from pathlib import Path

from tempfile import TemporaryDirectory

def write_conf(path):
    conf_path = os.path.join(path, ".notmuch-config")
    with open(conf_path, "w", encoding="utf-8") as f:
        f.write(f'[database]\npath={path}\n[search]\nexclude_tags=deleted\n[new]\ntags=')
    return conf_path


def sync(shell, local_conf, remote_conf):
    res = shell.run("./src/notmuch-sync", "--host", "remote",
                    "--remote-cmd", f"bash -c 'NOTMUCH_CONFIG={remote_conf} ./src/notmuch-sync --host local'",
                    env={"NOTMUCH_CONFIG": local_conf})
    #print(res)
    assert res.returncode == 0


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

            sync(shell, local_conf, remote_conf)

            local_sync_file = os.path.join(local, ".notmuch", "notmuch-sync-remote")
            assert os.path.exists(local_sync_file)
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert re.match('4 [0-9a-z-]+', f.read())

            remote_sync_file = os.path.join(remote, ".notmuch", "notmuch-sync-local")
            assert os.path.exists(remote_sync_file)
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert re.match('4 [0-9a-z-]+', f.read())

            sync(shell, local_conf, remote_conf)
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert re.match('4 [0-9a-z-]+', f.read())
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert re.match('4 [0-9a-z-]+', f.read())


def test_sync_tags(shell):
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

            sync(shell, local_conf, remote_conf)
            local_sync_file = os.path.join(local, ".notmuch", "notmuch-sync-remote")
            assert os.path.exists(local_sync_file)
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert re.match('4 [0-9a-z-]+', f.read())
            remote_sync_file = os.path.join(remote, ".notmuch", "notmuch-sync-local")
            assert os.path.exists(remote_sync_file)
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert re.match('4 [0-9a-z-]+', f.read())

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

            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert re.match('10 [0-9a-z-]+', f.read())

            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert re.match('10 [0-9a-z-]+', f.read())


def test_sync_tags_files(shell):
    with TemporaryDirectory() as local:
        with TemporaryDirectory() as remote:
            assert shell.run("cp", "-r", "test/mails", local).returncode == 0
            Path.unlink(os.path.join(local, "mails", "attachment.eml"))
            Path.unlink(os.path.join(local, "mails", "calendar.eml"))
            assert shell.run("cp", "-r", "test/mails", remote).returncode == 0
            Path.unlink(os.path.join(remote, "mails", "html-only.eml"))
            Path.unlink(os.path.join(remote, "mails", "simple.eml"))
            local_conf = write_conf(local)
            remote_conf = write_conf(remote)
            assert shell.run("notmuch", "new", env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
            assert shell.run("notmuch", "new", env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0

            assert shell.run("notmuch", "count", "*", env={"NOTMUCH_CONFIG": local_conf}).data == 2
            assert shell.run("notmuch", "count", "*", env={"NOTMUCH_CONFIG": remote_conf}).data == 2

            assert shell.run("notmuch", "tag", "+local", "id:87d1dajhgf.fsf@example.net",
                             env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+local", "id:1258848661-4660-2-git-send-email-stefan@datenfreihafen.org",
                             env={"NOTMUCH_CONFIG": local_conf}).returncode == 0

            assert shell.run("notmuch", "tag", "+remote", "id:20111101080303.30A10409E@asxas.net",
                             env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+remote", "id:874llc2bkp.fsf@curie.anarc.at",
                             env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0

            sync(shell, local_conf, remote_conf)

            assert Path(os.path.join(local, "mails", "attachment.eml")).exists()
            assert Path(os.path.join(local, "mails", "calendar.eml")).exists()
            assert Path(os.path.join(remote, "mails", "html-only.eml")).exists()
            assert Path(os.path.join(remote, "mails", "simple.eml")).exists()

            assert shell.run("notmuch", "search", "--output=tags", "--format=json", "id:874llc2bkp.fsf@curie.anarc.at",
                             env={"NOTMUCH_CONFIG": local_conf}).data == ["attachment", "remote"]
            assert shell.run("notmuch", "search", "--output=tags", "--format=json", "id:874llc2bkp.fsf@curie.anarc.at",
                             env={"NOTMUCH_CONFIG": remote_conf}).data == ["attachment", "remote"]
            assert shell.run("notmuch", "search", "--output=tags", "--format=json", "id:1258848661-4660-2-git-send-email-stefan@datenfreihafen.org",
                             env={"NOTMUCH_CONFIG": local_conf}).data == ["local"]
            assert shell.run("notmuch", "search", "--output=tags", "--format=json", "id:1258848661-4660-2-git-send-email-stefan@datenfreihafen.org",
                             env={"NOTMUCH_CONFIG": remote_conf}).data == ["local"]
            assert shell.run("notmuch", "search", "--output=tags", "--format=json", "id:20111101080303.30A10409E@asxas.net",
                             env={"NOTMUCH_CONFIG": local_conf}).data == ["attachment", "remote"]
            assert shell.run("notmuch", "search", "--output=tags", "--format=json", "id:20111101080303.30A10409E@asxas.net",
                             env={"NOTMUCH_CONFIG": remote_conf}).data == ["attachment", "remote"]
            assert shell.run("notmuch", "search", "--output=tags", "--format=json", "id:87d1dajhgf.fsf@example.net",
                             env={"NOTMUCH_CONFIG": local_conf}).data == ["local"]
            assert shell.run("notmuch", "search", "--output=tags", "--format=json", "id:87d1dajhgf.fsf@example.net",
                             env={"NOTMUCH_CONFIG": remote_conf}).data == ["local"]

            local_sync_file = os.path.join(local, ".notmuch", "notmuch-sync-remote")
            assert os.path.exists(local_sync_file)
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert re.match('4 [0-9a-z-]+', f.read())

            remote_sync_file = os.path.join(remote, ".notmuch", "notmuch-sync-local")
            assert os.path.exists(remote_sync_file)
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert re.match('4 [0-9a-z-]+', f.read())


def test_sync_tags_files_none_remote(shell):
    with TemporaryDirectory() as local:
        with TemporaryDirectory() as remote:
            assert shell.run("cp", "-r", "test/mails", local).returncode == 0
            local_conf = write_conf(local)
            remote_conf = write_conf(remote)
            assert shell.run("notmuch", "new", env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
            assert shell.run("notmuch", "new", env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0

            assert shell.run("notmuch", "count", "*", env={"NOTMUCH_CONFIG": local_conf}).data == 4
            assert shell.run("notmuch", "count", "*", env={"NOTMUCH_CONFIG": remote_conf}).data == 0

            assert shell.run("notmuch", "tag", "+local", "id:87d1dajhgf.fsf@example.net",
                             env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+local", "id:1258848661-4660-2-git-send-email-stefan@datenfreihafen.org",
                             env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+local", "id:20111101080303.30A10409E@asxas.net",
                             env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+local", "id:874llc2bkp.fsf@curie.anarc.at",
                             env={"NOTMUCH_CONFIG": local_conf}).returncode == 0

            sync(shell, local_conf, remote_conf)

            assert Path(os.path.join(remote, "mails", "attachment.eml")).exists()
            assert Path(os.path.join(remote, "mails", "calendar.eml")).exists()
            assert Path(os.path.join(remote, "mails", "html-only.eml")).exists()
            assert Path(os.path.join(remote, "mails", "simple.eml")).exists()

            assert shell.run("notmuch", "search", "--output=tags", "--format=json", "id:874llc2bkp.fsf@curie.anarc.at",
                             env={"NOTMUCH_CONFIG": local_conf}).data == ["attachment", "local"]
            assert shell.run("notmuch", "search", "--output=tags", "--format=json", "id:874llc2bkp.fsf@curie.anarc.at",
                             env={"NOTMUCH_CONFIG": remote_conf}).data == ["attachment", "local"]
            assert shell.run("notmuch", "search", "--output=tags", "--format=json", "id:1258848661-4660-2-git-send-email-stefan@datenfreihafen.org",
                             env={"NOTMUCH_CONFIG": local_conf}).data == ["local"]
            assert shell.run("notmuch", "search", "--output=tags", "--format=json", "id:1258848661-4660-2-git-send-email-stefan@datenfreihafen.org",
                             env={"NOTMUCH_CONFIG": remote_conf}).data == ["local"]
            assert shell.run("notmuch", "search", "--output=tags", "--format=json", "id:20111101080303.30A10409E@asxas.net",
                             env={"NOTMUCH_CONFIG": local_conf}).data == ["attachment", "local"]
            assert shell.run("notmuch", "search", "--output=tags", "--format=json", "id:20111101080303.30A10409E@asxas.net",
                             env={"NOTMUCH_CONFIG": remote_conf}).data == ["attachment", "local"]
            assert shell.run("notmuch", "search", "--output=tags", "--format=json", "id:87d1dajhgf.fsf@example.net",
                             env={"NOTMUCH_CONFIG": local_conf}).data == ["local"]
            assert shell.run("notmuch", "search", "--output=tags", "--format=json", "id:87d1dajhgf.fsf@example.net",
                             env={"NOTMUCH_CONFIG": remote_conf}).data == ["local"]

            local_sync_file = os.path.join(local, ".notmuch", "notmuch-sync-remote")
            assert os.path.exists(local_sync_file)
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert re.match('8 [0-9a-z-]+', f.read())

            remote_sync_file = os.path.join(remote, ".notmuch", "notmuch-sync-local")
            assert os.path.exists(remote_sync_file)
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert re.match('0 [0-9a-z-]+', f.read())
