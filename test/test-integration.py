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


def sync(shell, local_conf, remote_conf, verbose=False, delete=False):
    args = ["./src/notmuch-sync", "--remote-cmd", f"bash -c 'NOTMUCH_CONFIG={remote_conf} ./src/notmuch-sync {"--delete" if delete else ""}'"]
    if verbose:
        args.append("--verbose")
    if delete:
        args.append("--delete")
    res = shell.run(*args, env={"NOTMUCH_CONFIG": local_conf})
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
            assert lsum[2] == "5\n"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[0] == "4"
            assert rsum[2] == "5\n"

            out = sync(shell, local_conf, remote_conf).split('\n')
            assert "local:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[0]
            assert "remote:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[1]

            local_sync_file = os.path.join(local, ".notmuch", f"notmuch-sync-{rsum[1]}")
            assert os.path.exists(local_sync_file)
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"5 {lsum[1]}"

            remote_sync_file = os.path.join(remote, ".notmuch", f"notmuch-sync-{lsum[1]}")
            assert os.path.exists(remote_sync_file)
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"5 {rsum[1]}"

            out = sync(shell, local_conf, remote_conf).split('\n')
            assert "local:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[0]
            assert "remote:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[1]
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"5 {lsum[1]}"
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"5 {rsum[1]}"

            lsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": local_conf}).stdout.split('\t')
            assert lsum[2] == "5\n"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[2] == "5\n"


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
            assert lsum[2] == "5\n"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[0] == "4"
            assert rsum[2] == "5\n"

            out = sync(shell, local_conf, remote_conf).split('\n')
            assert "local:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[0]
            assert "remote:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[1]
            local_sync_file = os.path.join(local, ".notmuch", f"notmuch-sync-{rsum[1]}")
            assert os.path.exists(local_sync_file)
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"5 {lsum[1]}"
            remote_sync_file = os.path.join(remote, ".notmuch", f"notmuch-sync-{lsum[1]}")
            assert os.path.exists(remote_sync_file)
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"5 {rsum[1]}"

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

            lsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": local_conf}).stdout.split('\t')
            assert lsum[2] == "8\n"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[2] == "8\n"

            out = sync(shell, local_conf, remote_conf).split('\n')
            assert "local:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t3 messages with tag changes,\t0 messages deleted" == out[0]
            assert "remote:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t3 messages with tag changes,\t0 messages deleted" == out[1]

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
                assert f.read() == f"11 {lsum[1]}"
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"11 {rsum[1]}"

            lsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": local_conf}).stdout.split('\t')
            assert lsum[2] == "11\n"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[2] == "11\n"

            out = sync(shell, local_conf, remote_conf).split('\n')
            assert "local:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[0]
            assert "remote:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[1]


def test_sync_tags_files_verbose(shell):
    with TemporaryDirectory() as local:
        with TemporaryDirectory() as remote:
            assert shell.run("cp", "-r", "test/mails", local).returncode == 0
            Path.unlink(os.path.join(local, "mails", "attachment.eml"))
            assert shell.run("cp", "-r", "test/mails", remote).returncode == 0
            Path.unlink(os.path.join(remote, "mails", "simple.eml"))
            local_conf = write_conf(local)
            remote_conf = write_conf(remote)
            assert shell.run("notmuch", "new", env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
            assert shell.run("notmuch", "new", env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0

            assert shell.run("notmuch", "tag", "+local", "id:87d1dajhgf.fsf@example.net",
                             env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+local", "id:1258848661-4660-2-git-send-email-stefan@datenfreihafen.org",
                             env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+local", "id:20111101080303.30A10409E@asxas.net",
                             env={"NOTMUCH_CONFIG": local_conf}).returncode == 0

            assert shell.run("notmuch", "tag", "+remote", "id:20111101080303.30A10409E@asxas.net",
                             env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+remote", "id:874llc2bkp.fsf@curie.anarc.at",
                             env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+remote", "id:87d1dajhgf.fsf@example.net",
                             env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0

            out = sync(shell, local_conf, remote_conf, verbose=True).split('\n')
            assert 'Connecting to remote...' == out[0]
            assert 'Sending UUID...' == out[1]
            assert 'Receiving UUID...' == out[2]
            assert 'UUIDs synced.' == out[3]
            assert 'Computing local changes...' == out[4]
            assert 'Sending local changes...' in out
            assert 'Receiving remote changes...' in out
            assert 'Changes synced.' == out[7]
            assert "Setting tags ['local', 'remote'] for 87d1dajhgf.fsf@example.net." in out
            assert "Setting tags ['attachment', 'local', 'remote'] for 20111101080303.30A10409E@asxas.net." in out
            assert 'Tags synced.' == out[10]
            assert 'Writing last sync revision 9.' == out[11]
            assert 'Sending file names missing on local...' in out
            assert 'Receving file names missing on remote...' in out
            assert 'Missing file names synced.' == out[14]
            assert '1/1 Sending mails/simple.eml...' in out
            assert '1/1 Receiving mails/attachment.eml...' in out
            assert f'Adding {local}/mails/attachment.eml to DB.' in out
            assert "Setting tags ['attachment', 'remote'] for 874llc2bkp.fsf@curie.anarc.at." in out
            assert 'Missing files synced.' == out[19]
            assert 'Getting change numbers from remote...' == out[20]
            assert 'local:\t1 new messages,\t1 new files,\t0 files copied/moved,\t0 files deleted,\t2 messages with tag changes,\t0 messages deleted' == out[21]
            assert 'remote:\t1 new messages,\t1 new files,\t0 files copied/moved,\t0 files deleted,\t2 messages with tag changes,\t0 messages deleted' == out[22]
            assert '9426/4616 bytes received from/sent to remote.' == out[23]


def test_sync_tags_files(shell):
    with TemporaryDirectory() as local:
        with TemporaryDirectory() as remote:
            assert shell.run("cp", "-r", "test/mails", local).returncode == 0
            Path.unlink(os.path.join(local, "mails", "attachment.eml"))
            Path.unlink(os.path.join(local, "mails", "calendar.eml"))
            assert shell.run("cp", "-r", "test/mails", remote).returncode == 0
            Path.unlink(os.path.join(remote, "mails", "html-only1.eml"))
            Path.unlink(os.path.join(remote, "mails", "html-only.eml"))
            Path.unlink(os.path.join(remote, "mails", "simple.eml"))
            local_conf = write_conf(local)
            remote_conf = write_conf(remote)
            assert shell.run("notmuch", "new", env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
            assert shell.run("notmuch", "new", env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0

            lsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": local_conf}).stdout.split('\t')
            assert lsum[0] == "2"
            assert lsum[2] == "3\n"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[0] == "2"
            assert rsum[2] == "2\n"

            assert shell.run("notmuch", "tag", "+local", "id:87d1dajhgf.fsf@example.net",
                             env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+local", "id:1258848661-4660-2-git-send-email-stefan@datenfreihafen.org",
                             env={"NOTMUCH_CONFIG": local_conf}).returncode == 0

            assert shell.run("notmuch", "tag", "+remote", "id:20111101080303.30A10409E@asxas.net",
                             env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+remote", "id:874llc2bkp.fsf@curie.anarc.at",
                             env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0

            lsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": local_conf}).stdout.split('\t')
            assert lsum[2] == "5\n"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[2] == "4\n"

            out = sync(shell, local_conf, remote_conf).split('\n')
            assert "local:\t2 new messages,\t2 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[0]
            assert "remote:\t2 new messages,\t3 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[1]

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

            local_sync_file = os.path.join(local, ".notmuch", f"notmuch-sync-{rsum[1]}")
            assert os.path.exists(local_sync_file)
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"5 {lsum[1]}"

            remote_sync_file = os.path.join(remote, ".notmuch", f"notmuch-sync-{lsum[1]}")
            assert os.path.exists(remote_sync_file)
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"4 {rsum[1]}"

            # we record the last sync before transferring files and
            # adding/tagging them, so the revision after finished sync is higher
            lsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": local_conf}).stdout.split('\t')
            assert lsum[2] == "9\n"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[2] == "9\n"

            out = sync(shell, local_conf, remote_conf).split('\n')
            assert "local:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[0]
            assert "remote:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[1]
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"9 {lsum[1]}"
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"9 {rsum[1]}"


def test_sync_tags_files_copied(shell):
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

            assert shell.run("notmuch", "tag", "+local", "id:87d1dajhgf.fsf@example.net",
                             env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+local", "id:1258848661-4660-2-git-send-email-stefan@datenfreihafen.org",
                             env={"NOTMUCH_CONFIG": local_conf}).returncode == 0

            assert shell.run("notmuch", "tag", "+remote", "id:87d1dajhgf.fsf@example.net",
                             env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+remote", "id:20111101080303.30A10409E@asxas.net",
                             env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+remote", "id:874llc2bkp.fsf@curie.anarc.at",
                             env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0

            lsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": local_conf}).stdout.split('\t')
            assert lsum[0] == "2"
            assert lsum[2] == "5\n"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[0] == "3"
            assert rsum[2] == "6\n"

            out = sync(shell, local_conf, remote_conf).split('\n')
            assert "local:\t2 new messages,\t2 new files,\t0 files copied/moved,\t0 files deleted,\t1 messages with tag changes,\t0 messages deleted" == out[0]
            assert "remote:\t1 new messages,\t1 new files,\t1 files copied/moved,\t0 files deleted,\t1 messages with tag changes,\t0 messages deleted" == out[1]

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
                             env={"NOTMUCH_CONFIG": local_conf}).data == ["local", "remote"]
            assert shell.run("notmuch", "search", "--output=tags", "--format=json", "id:87d1dajhgf.fsf@example.net",
                             env={"NOTMUCH_CONFIG": remote_conf}).data == ["local", "remote"]

            local_sync_file = os.path.join(local, ".notmuch", f"notmuch-sync-{rsum[1]}")
            assert os.path.exists(local_sync_file)
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"6 {lsum[1]}"

            remote_sync_file = os.path.join(remote, ".notmuch", f"notmuch-sync-{lsum[1]}")
            assert os.path.exists(remote_sync_file)
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"7 {rsum[1]}"

            # we record the last sync before transferring files and
            # adding/tagging them, so the revision after finished sync is higher
            lsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": local_conf}).stdout.split('\t')
            assert lsum[2] == "10\n"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[2] == "10\n"

            out = sync(shell, local_conf, remote_conf).split('\n')
            assert "local:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[0]
            assert "remote:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[1]
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"10 {lsum[1]}"
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"10 {rsum[1]}"


def test_sync_tags_files_moved(shell):
    with TemporaryDirectory() as local:
        with TemporaryDirectory() as remote:
            assert shell.run("cp", "-r", "test/mails", local).returncode == 0
            Path.unlink(os.path.join(local, "mails", "attachment.eml"))
            Path.unlink(os.path.join(local, "mails", "calendar.eml"))
            Path.unlink(os.path.join(local, "mails", "html-only1.eml"))
            assert shell.run("cp", "-r", "test/mails", remote).returncode == 0
            Path.unlink(os.path.join(remote, "mails", "simple.eml"))
            Path.unlink(os.path.join(remote, "mails", "html-only1.eml"))
            local_conf = write_conf(local)
            remote_conf = write_conf(remote)
            assert shell.run("notmuch", "new", env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
            assert shell.run("notmuch", "new", env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0

            assert shell.run("notmuch", "tag", "+local", "id:87d1dajhgf.fsf@example.net",
                             env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+local", "id:1258848661-4660-2-git-send-email-stefan@datenfreihafen.org",
                             env={"NOTMUCH_CONFIG": local_conf}).returncode == 0

            assert shell.run("notmuch", "tag", "+remote", "id:87d1dajhgf.fsf@example.net",
                             env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+remote", "id:20111101080303.30A10409E@asxas.net",
                             env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+remote", "id:874llc2bkp.fsf@curie.anarc.at",
                             env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0

            lsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": local_conf}).stdout.split('\t')
            assert lsum[0] == "2"
            assert lsum[2] == "4\n"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[0] == "3"
            assert rsum[2] == "6\n"

            out = sync(shell, local_conf, remote_conf).split('\n')
            assert "local:\t2 new messages,\t2 new files,\t0 files copied/moved,\t0 files deleted,\t1 messages with tag changes,\t0 messages deleted" == out[0]
            assert "remote:\t1 new messages,\t1 new files,\t0 files copied/moved,\t0 files deleted,\t1 messages with tag changes,\t0 messages deleted" == out[1]

            assert Path(os.path.join(local, "mails", "attachment.eml")).exists()
            assert Path(os.path.join(local, "mails", "calendar.eml")).exists()
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
                             env={"NOTMUCH_CONFIG": local_conf}).data == ["local", "remote"]
            assert shell.run("notmuch", "search", "--output=tags", "--format=json", "id:87d1dajhgf.fsf@example.net",
                             env={"NOTMUCH_CONFIG": remote_conf}).data == ["local", "remote"]

            local_sync_file = os.path.join(local, ".notmuch", f"notmuch-sync-{rsum[1]}")
            assert os.path.exists(local_sync_file)
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"5 {lsum[1]}"

            remote_sync_file = os.path.join(remote, ".notmuch", f"notmuch-sync-{lsum[1]}")
            assert os.path.exists(remote_sync_file)
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"7 {rsum[1]}"

            # we record the last sync before transferring files and
            # adding/tagging them, so the revision after finished sync is higher
            lsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": local_conf}).stdout.split('\t')
            assert lsum[2] == "9\n"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[2] == "9\n"

            shutil.move(os.path.join(local, "mails", "html-only.eml"), os.path.join(local, "mails", "html-only1.eml"))
            assert shell.run("notmuch", "new", env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
            lsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": local_conf}).stdout.split('\t')
            assert lsum[2] == "11\n"
            assert not Path(os.path.join(remote, "mails", "html-only1.eml")).exists()

            out = sync(shell, local_conf, remote_conf).split('\n')
            assert "local:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[0]
            assert "remote:\t0 new messages,\t0 new files,\t1 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[1]
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"11 {lsum[1]}"
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"9 {rsum[1]}"

            assert not Path(os.path.join(remote, "mails", "html-only.eml")).exists()
            assert Path(os.path.join(remote, "mails", "html-only1.eml")).exists()

            lsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": local_conf}).stdout.split('\t')
            assert lsum[2] == "11\n"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[2] == "11\n"

            out = sync(shell, local_conf, remote_conf).split('\n')
            assert "local:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[0]
            assert "remote:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[1]
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"11 {lsum[1]}"
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"11 {rsum[1]}"


def test_sync_tags_files_moved_twice(shell):
    with TemporaryDirectory() as local:
        with TemporaryDirectory() as remote:
            assert shell.run("cp", "-r", "test/mails", local).returncode == 0
            Path.unlink(os.path.join(local, "mails", "attachment.eml"))
            Path.unlink(os.path.join(local, "mails", "calendar.eml"))
            Path.unlink(os.path.join(local, "mails", "html-only1.eml"))
            assert shell.run("cp", "-r", "test/mails", remote).returncode == 0
            Path.unlink(os.path.join(remote, "mails", "html-only.eml"))
            Path.unlink(os.path.join(remote, "mails", "simple.eml"))
            local_conf = write_conf(local)
            remote_conf = write_conf(remote)
            assert shell.run("notmuch", "new", env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
            assert shell.run("notmuch", "new", env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0

            assert shell.run("notmuch", "tag", "+local", "id:87d1dajhgf.fsf@example.net",
                             env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+local", "id:1258848661-4660-2-git-send-email-stefan@datenfreihafen.org",
                             env={"NOTMUCH_CONFIG": local_conf}).returncode == 0

            assert shell.run("notmuch", "tag", "+remote", "id:87d1dajhgf.fsf@example.net",
                             env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+remote", "id:20111101080303.30A10409E@asxas.net",
                             env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0
            assert shell.run("notmuch", "tag", "+remote", "id:874llc2bkp.fsf@curie.anarc.at",
                             env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0

            lsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": local_conf}).stdout.split('\t')
            assert lsum[0] == "2"
            assert lsum[2] == "4\n"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[0] == "3"
            assert rsum[2] == "6\n"

            out = sync(shell, local_conf, remote_conf).split('\n')
            assert "local:\t2 new messages,\t2 new files,\t1 files copied/moved,\t0 files deleted,\t1 messages with tag changes,\t0 messages deleted" == out[0]
            assert "remote:\t1 new messages,\t1 new files,\t1 files copied/moved,\t0 files deleted,\t1 messages with tag changes,\t0 messages deleted" == out[1]

            assert Path(os.path.join(local, "mails", "attachment.eml")).exists()
            assert Path(os.path.join(local, "mails", "calendar.eml")).exists()
            assert Path(os.path.join(local, "mails", "html-only1.eml")).exists()
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
                             env={"NOTMUCH_CONFIG": local_conf}).data == ["local", "remote"]
            assert shell.run("notmuch", "search", "--output=tags", "--format=json", "id:87d1dajhgf.fsf@example.net",
                             env={"NOTMUCH_CONFIG": remote_conf}).data == ["local", "remote"]

            local_sync_file = os.path.join(local, ".notmuch", f"notmuch-sync-{rsum[1]}")
            assert os.path.exists(local_sync_file)
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"5 {lsum[1]}"

            remote_sync_file = os.path.join(remote, ".notmuch", f"notmuch-sync-{lsum[1]}")
            assert os.path.exists(remote_sync_file)
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"7 {rsum[1]}"

            # we record the last sync before transferring files and
            # adding/tagging them, so the revision after finished sync is higher
            lsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": local_conf}).stdout.split('\t')
            assert lsum[2] == "10\n"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[2] == "10\n"

            out = sync(shell, local_conf, remote_conf).split('\n')
            assert "local:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[0]
            assert "remote:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[1]
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"10 {lsum[1]}"
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"10 {rsum[1]}"


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
            assert "local:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[0]
            assert "remote:\t4 new messages,\t5 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[1]

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
                assert f.read() == f"9 {lsum[1]}"

            remote_sync_file = os.path.join(remote, ".notmuch", f"notmuch-sync-{lsum[1]}")
            assert os.path.exists(remote_sync_file)
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"0 {rsum[1]}"

            # we record the last sync before transferring files and
            # adding/tagging them, so the revision after finished sync is higher
            lsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": local_conf}).stdout.split('\t')
            assert lsum[2] == "9\n"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[2] == "9\n"

            out = sync(shell, local_conf, remote_conf).split('\n')
            assert "local:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[0]
            assert "remote:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[1]
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"9 {lsum[1]}"
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"9 {rsum[1]}"


def test_sync_files_deleted(shell):
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
            assert lsum[2] == "5\n"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[0] == "4"
            assert rsum[2] == "5\n"

            out = sync(shell, local_conf, remote_conf).split('\n')
            assert "local:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[0]
            assert "remote:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[1]

            local_sync_file = os.path.join(local, ".notmuch", f"notmuch-sync-{rsum[1]}")
            assert os.path.exists(local_sync_file)
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"5 {lsum[1]}"

            remote_sync_file = os.path.join(remote, ".notmuch", f"notmuch-sync-{lsum[1]}")
            assert os.path.exists(remote_sync_file)
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"5 {rsum[1]}"

            Path.unlink(os.path.join(remote, "mails", "html-only1.eml"))
            assert shell.run("notmuch", "new", env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0
            assert shell.run("notmuch", "search", "--output=files", "--format=json", "id:87d1dajhgf.fsf@example.net",
                             env={"NOTMUCH_CONFIG": local_conf}).data == [os.path.join(local, "mails", "html-only.eml"), os.path.join(local, "mails", "html-only1.eml")]
            assert shell.run("notmuch", "search", "--output=files", "--format=json", "id:87d1dajhgf.fsf@example.net",
                             env={"NOTMUCH_CONFIG": remote_conf}).data == [os.path.join(remote, "mails", "html-only.eml")]
            assert Path(os.path.join(local, "mails", "html-only1.eml")).exists()
            assert not Path(os.path.join(remote, "mails", "html-only1.eml")).exists()

            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[2] == "6\n"

            out = sync(shell, local_conf, remote_conf, delete=True).split('\n')
            assert "local:\t0 new messages,\t0 new files,\t0 files copied/moved,\t1 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[0]
            assert "remote:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[1]
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"5 {lsum[1]}"
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"6 {rsum[1]}"

            assert shell.run("notmuch", "search", "--output=files", "--format=json", "id:87d1dajhgf.fsf@example.net",
                             env={"NOTMUCH_CONFIG": local_conf}).data == [os.path.join(local, "mails", "html-only.eml")]
            assert shell.run("notmuch", "search", "--output=files", "--format=json", "id:87d1dajhgf.fsf@example.net",
                             env={"NOTMUCH_CONFIG": remote_conf}).data == [os.path.join(remote, "mails", "html-only.eml")]
            assert not Path(os.path.join(local, "mails", "html-only1.eml")).exists()
            assert not Path(os.path.join(remote, "mails", "html-only1.eml")).exists()

            lsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": local_conf}).stdout.split('\t')
            assert lsum[2] == "6\n"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[2] == "6\n"


def test_sync_message_deleted_local(shell):
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
            assert lsum[2] == "5\n"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[0] == "4"
            assert rsum[2] == "5\n"

            out = sync(shell, local_conf, remote_conf).split('\n')
            assert "local:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[0]
            assert "remote:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[1]

            local_sync_file = os.path.join(local, ".notmuch", f"notmuch-sync-{rsum[1]}")
            assert os.path.exists(local_sync_file)
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"5 {lsum[1]}"

            remote_sync_file = os.path.join(remote, ".notmuch", f"notmuch-sync-{lsum[1]}")
            assert os.path.exists(remote_sync_file)
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"5 {rsum[1]}"

            Path.unlink(os.path.join(local, "mails", "simple.eml"))
            assert shell.run("notmuch", "new", env={"NOTMUCH_CONFIG": local_conf}).returncode == 0
            assert shell.run("notmuch", "search", "--format=json", "id:1258848661-4660-2-git-send-email-stefan@datenfreihafen.org",
                             env={"NOTMUCH_CONFIG": local_conf}).data == []
            assert shell.run("notmuch", "search", "--output=files", "--format=json", "id:1258848661-4660-2-git-send-email-stefan@datenfreihafen.org",
                             env={"NOTMUCH_CONFIG": remote_conf}).data == [os.path.join(remote, "mails", "simple.eml")]
            assert Path(os.path.join(remote, "mails", "simple.eml")).exists()

            lsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": local_conf}).stdout.split('\t')
            assert lsum[0] == "3"
            assert lsum[2] == "5\n"

            out = sync(shell, local_conf, remote_conf, delete=True).split('\n')
            assert "local:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[0]
            assert "remote:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t1 messages deleted" == out[1]
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"5 {lsum[1]}"
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"5 {rsum[1]}"

            assert shell.run("notmuch", "search", "--format=json", "id:1258848661-4660-2-git-send-email-stefan@datenfreihafen.org",
                             env={"NOTMUCH_CONFIG": local_conf}).data == []
            assert shell.run("notmuch", "search", "--format=json", "id:1258848661-4660-2-git-send-email-stefan@datenfreihafen.org",
                             env={"NOTMUCH_CONFIG": remote_conf}).data == []
            assert not Path(os.path.join(remote, "mails", "simple.eml")).exists()

            lsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": local_conf}).stdout.split('\t')
            assert lsum[0] == "3"
            assert lsum[2] == "5\n"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[0] == "3"
            assert rsum[2] == "5\n"


def test_sync_message_deleted_remote(shell):
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
            assert lsum[2] == "5\n"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[0] == "4"
            assert rsum[2] == "5\n"

            out = sync(shell, local_conf, remote_conf).split('\n')
            assert "local:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[0]
            assert "remote:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[1]

            local_sync_file = os.path.join(local, ".notmuch", f"notmuch-sync-{rsum[1]}")
            assert os.path.exists(local_sync_file)
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"5 {lsum[1]}"

            remote_sync_file = os.path.join(remote, ".notmuch", f"notmuch-sync-{lsum[1]}")
            assert os.path.exists(remote_sync_file)
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"5 {rsum[1]}"

            Path.unlink(os.path.join(remote, "mails", "simple.eml"))
            assert shell.run("notmuch", "new", env={"NOTMUCH_CONFIG": remote_conf}).returncode == 0
            assert shell.run("notmuch", "search", "--output=files", "--format=json", "id:1258848661-4660-2-git-send-email-stefan@datenfreihafen.org",
                             env={"NOTMUCH_CONFIG": local_conf}).data == [os.path.join(local, "mails", "simple.eml")]
            assert shell.run("notmuch", "search", "--format=json", "id:1258848661-4660-2-git-send-email-stefan@datenfreihafen.org",
                             env={"NOTMUCH_CONFIG": remote_conf}).data == []
            assert Path(os.path.join(local, "mails", "simple.eml")).exists()

            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[0] == "3"
            assert rsum[2] == "5\n"

            out = sync(shell, local_conf, remote_conf, delete=True).split('\n')
            assert "local:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t1 messages deleted" == out[0]
            assert "remote:\t0 new messages,\t0 new files,\t0 files copied/moved,\t0 files deleted,\t0 messages with tag changes,\t0 messages deleted" == out[1]
            with open(local_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"5 {lsum[1]}"
            with open(remote_sync_file, "r", encoding="utf-8") as f:
                assert f.read() == f"5 {rsum[1]}"

            assert shell.run("notmuch", "search", "--format=json", "id:1258848661-4660-2-git-send-email-stefan@datenfreihafen.org",
                             env={"NOTMUCH_CONFIG": local_conf}).data == []
            assert shell.run("notmuch", "search", "--format=json", "id:1258848661-4660-2-git-send-email-stefan@datenfreihafen.org",
                             env={"NOTMUCH_CONFIG": remote_conf}).data == []
            assert not Path(os.path.join(local, "mails", "simple.eml")).exists()

            lsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": local_conf}).stdout.split('\t')
            assert lsum[0] == "3"
            assert lsum[2] == "5\n"
            rsum = shell.run("notmuch", "count", "--lastmod", env={"NOTMUCH_CONFIG": remote_conf}).stdout.split('\t')
            assert rsum[0] == "3"
            assert rsum[2] == "5\n"
