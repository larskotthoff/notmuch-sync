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
    res = shell.run("./src/notmuch-sync", "--remote-cmd", f"bash -c 'NOTMUCH_CONFIG={remote_conf} ./src/notmuch-sync'",
                    env={"NOTMUCH_CONFIG": local_conf})
    #print(res)
    assert res.returncode == 0
    return res.stdout


def test_sync(shell):
    with TemporaryDirectory() as local:
        with TemporaryDirectory() as remote:
            assert shell.run("cp", "-r", "test/mails", local).returncode == 0
            assert shell.run("cp", "-r", "test/mails", remote).returncode == 0
            local_conf = write_conf(local)
            remote_conf = write_conf(remote)
            assert shell.run("notmuch", "new", env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
            assert shell.run("notmuch", "new", env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0

            lsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": local_conf}).stdout.split('\t')
            assert lsum[0] == "4"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[0] == "4"

            out = sync(shell, local_conf, remote_conf).split('\n')
            assert "local:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 messages with tag changes" == out[0]
            assert "remote:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 messages with tag changes" == out[1]

            local_sync_file = os.path.join(local, ".notmuch", f"notmuch-sync-{rsum[1]}")
            assert os.path.exists(local_sync_file)
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"4 {lsum[1]}"

            remote_sync_file = os.path.join(remote, ".notmuch", f"notmuch-sync-{lsum[1]}")
            assert os.path.exists(remote_sync_file)
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"4 {rsum[1]}"

            out = sync(shell, local_conf, remote_conf).split('\n')
            assert "local:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 messages with tag changes" == out[0]
            assert "remote:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 messages with tag changes" == out[1]
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"4 {lsum[1]}"
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"4 {rsum[1]}"

            lsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": local_conf}).stdout.split('\t')
            assert lsum[2] == "4\n"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[2] == "4\n"


def test_sync_tags(shell):
    with TemporaryDirectory() as local:
        with TemporaryDirectory() as remote:
            assert shell.run("cp", "-r", "test/mails", local).returncode == 0
            assert shell.run("cp", "-r", "test/mails", remote).returncode == 0
            local_conf = write_conf(local)
            remote_conf = write_conf(remote)
            assert shell.run("notmuch", "new", env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
            assert shell.run("notmuch", "new", env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0

            lsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": local_conf}).stdout.split('\t')
            assert lsum[0] == "4"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[0] == "4"

            out = sync(shell, local_conf, remote_conf).split('\n')
            assert "local:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 messages with tag changes" == out[0]
            assert "remote:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 messages with tag changes" == out[1]
            local_sync_file = os.path.join(local, ".notmuch", f"notmuch-sync-{rsum[1]}")
            assert os.path.exists(local_sync_file)
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"4 {lsum[1]}"
            remote_sync_file = os.path.join(remote, ".notmuch", f"notmuch-sync-{lsum[1]}")
            assert os.path.exists(remote_sync_file)
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"4 {rsum[1]}"

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

            out = sync(shell, local_conf, remote_conf).split('\n')
            assert "local:\t0 new messages,\t0 new files,\t0 files copied/moved,\t3 messages with tag changes" == out[0]
            assert "remote:\t0 new messages,\t0 new files,\t0 files copied/moved,\t3 messages with tag changes" == out[1]

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
                assert f.read() == f"10 {lsum[1]}"
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"10 {rsum[1]}"

            lsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": local_conf}).stdout.split('\t')
            assert lsum[2] == "10\n"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[2] == "10\n"

            out = sync(shell, local_conf, remote_conf).split('\n')
            assert "local:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 messages with tag changes" == out[0]
            assert "remote:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 messages with tag changes" == out[1]


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

            lsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": local_conf}).stdout.split('\t')
            assert lsum[0] == "2"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[0] == "2"

            assert shell.run("notmuch", "tag", "+local", "id:87d1dajhgf.fsf@example.net",
                             env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+local", "id:1258848661-4660-2-git-send-email-stefan@datenfreihafen.org",
                             env={"NOTMUCH_CONFIG": local_conf}).returncode == 0

            assert shell.run("notmuch", "tag", "+remote", "id:20111101080303.30A10409E@asxas.net",
                             env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+remote", "id:874llc2bkp.fsf@curie.anarc.at",
                             env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0

            out = sync(shell, local_conf, remote_conf).split('\n')
            assert "local:\t2 new messages,\t2 new files,\t0 files copied/moved,\t0 messages with tag changes" == out[0]
            assert "remote:\t2 new messages,\t2 new files,\t0 files copied/moved,\t0 messages with tag changes" == out[1]

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

            print(shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": local_conf}))
            print(shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}))
            local_sync_file = os.path.join(local, ".notmuch", f"notmuch-sync-{rsum[1]}")
            assert os.path.exists(local_sync_file)
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"4 {lsum[1]}"

            remote_sync_file = os.path.join(remote, ".notmuch", f"notmuch-sync-{lsum[1]}")
            assert os.path.exists(remote_sync_file)
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"4 {rsum[1]}"

            # we record the last sync before transferring files and
            # adding/tagging them, so the revision after finished sync is higher
            lsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": local_conf}).stdout.split('\t')
            assert lsum[2] == "8\n"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[2] == "8\n"

            out = sync(shell, local_conf, remote_conf).split('\n')
            assert "local:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 messages with tag changes" == out[0]
            assert "remote:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 messages with tag changes" == out[1]
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"8 {lsum[1]}"
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"8 {rsum[1]}"


def test_sync_tags_files_none_remote(shell):
    with TemporaryDirectory() as local:
        with TemporaryDirectory() as remote:
            assert shell.run("cp", "-r", "test/mails", local).returncode == 0
            local_conf = write_conf(local)
            remote_conf = write_conf(remote)
            assert shell.run("notmuch", "new", env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
            assert shell.run("notmuch", "new", env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0

            lsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": local_conf}).stdout.split('\t')
            assert lsum[0] == "4"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[0] == "0"

            assert shell.run("notmuch", "tag", "+local", "id:87d1dajhgf.fsf@example.net",
                             env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+local", "id:1258848661-4660-2-git-send-email-stefan@datenfreihafen.org",
                             env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+local", "id:20111101080303.30A10409E@asxas.net",
                             env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+local", "id:874llc2bkp.fsf@curie.anarc.at",
                             env={"NOTMUCH_CONFIG": local_conf}).returncode == 0

            out = sync(shell, local_conf, remote_conf).split('\n')
            assert "local:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 messages with tag changes" == out[0]
            assert "remote:\t4 new messages,\t4 new files,\t0 files copied/moved,\t0 messages with tag changes" == out[1]

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

            local_sync_file = os.path.join(local, ".notmuch", f"notmuch-sync-{rsum[1]}")
            assert os.path.exists(local_sync_file)
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"8 {lsum[1]}"

            remote_sync_file = os.path.join(remote, ".notmuch", f"notmuch-sync-{lsum[1]}")
            assert os.path.exists(remote_sync_file)
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"0 {rsum[1]}"

            # we record the last sync before transferring files and
            # adding/tagging them, so the revision after finished sync is higher
            lsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": local_conf}).stdout.split('\t')
            assert lsum[2] == "8\n"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[2] == "8\n"

            out = sync(shell, local_conf, remote_conf).split('\n')
            assert "local:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 messages with tag changes" == out[0]
            assert "remote:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 messages with tag changes" == out[1]
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"8 {lsum[1]}"
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"8 {rsum[1]}"
