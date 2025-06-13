import pytest
import os
import sys
import io
from unittest.mock import MagicMock, PropertyMock, call, mock_open, patch
from tempfile import NamedTemporaryFile, gettempdir

import notmuch2

from importlib.util import spec_from_loader, module_from_spec
from importlib.machinery import SourceFileLoader 
spec = spec_from_loader("notmuch-sync", SourceFileLoader("notmuch-sync", "src/notmuch-sync"))
ns = module_from_spec(spec)
spec.loader.exec_module(ns)

def test_changes():
    mm = lambda: None
    mm.messageid = "foo"
    mm.tags = ["foo", "bar"]

    db = lambda: None
    rev = lambda: None
    rev.rev = 124
    rev.uuid = b'abc'
    db.revision = MagicMock(return_value=rev)
    db.default_path = MagicMock(return_value=gettempdir())
    db.messages = MagicMock(return_value=[mm])

    with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f:
        f.write("123 abc")
        f.flush()
        with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f1:
            f1.write("mail one")
            f1.flush()
            with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f2:
                f2.write("mail two")
                f2.flush()
                mm.filenames = MagicMock(return_value=[f1.name, f2.name])
                changes = ns.get_changes(db, f.name)
                assert changes == {"foo": {"tags": ["foo", "bar"], "files":
                                           [{"name": f1.name.removeprefix(gettempdir() + os.sep),
                                             "sha": "a983f58ef9ef755c4e5e3755f10cf3e08d9b189b388bcb59d29b56d35d7d6b9d"},
                                            {"name": f2.name.removeprefix(gettempdir() + os.sep),
                                             "sha": "17b6d790c2c6dd4c315bba65bd5d877f3a52b26756fadec0fcd6011b5cd38a1a"}]}}

    db.revision.assert_called_once()
    db.default_path.assert_called_once()
    db.messages.assert_called_once_with("lastmod:123..")


def test_changes_first_sync():
    mm = lambda: None
    mm.messageid = "foo"
    mm.tags = ["foo", "bar"]

    db = lambda: None
    rev = lambda: None
    db.default_path = MagicMock(return_value=gettempdir())
    db.messages = MagicMock(return_value=[mm])

    # this is only to get a filename that is guaranteed to be unique -- the file
    # won't exist anymore by the time it is accessed, but that's the point of
    # this test
    f = NamedTemporaryFile(mode="r", prefix="notmuch-sync-test-tmp-")
    f.close()
    with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f1:
        f1.write("mail one")
        f1.flush()
        with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f2:
            f2.write("mail two")
            f2.flush()
            mm.filenames = MagicMock(return_value=[f1.name, f2.name])
            changes = ns.get_changes(db, f.name)
            assert changes == {"foo": {"tags": ["foo", "bar"], "files":
                                       [{"name": f1.name.removeprefix(gettempdir() + os.sep),
                                         "sha": "a983f58ef9ef755c4e5e3755f10cf3e08d9b189b388bcb59d29b56d35d7d6b9d"},
                                        {"name": f2.name.removeprefix(gettempdir() + os.sep),
                                         "sha": "17b6d790c2c6dd4c315bba65bd5d877f3a52b26756fadec0fcd6011b5cd38a1a"}]}}

    db.default_path.assert_called_once()
    db.messages.assert_called_once_with("lastmod:0..")


def test_changes_changed_uuid():
    db = lambda: None
    rev = lambda: None
    rev.rev = 124
    rev.uuid = b'abd'
    db.revision = MagicMock(return_value=rev)

    with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f:
        f.write("123 abc")
        f.flush()
        with pytest.raises(SystemExit) as pwe:
            ns.get_changes(db, f.name)
        assert pwe.type == SystemExit
        assert pwe.value.code == "Last sync with UUID abc, but notmuch DB has UUID abd, aborting..."

    db.revision.assert_called_once()


def test_changes_later_rev():
    db = lambda: None
    rev = lambda: None
    rev.rev = 122
    rev.uuid = b'abc'
    db.revision = MagicMock(return_value=rev)

    with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f:
        f.write("123 abc")
        f.flush()
        with pytest.raises(SystemExit) as pwe:
            ns.get_changes(db, f.name)
        assert pwe.type == SystemExit
        assert pwe.value.code == "Last sync revision 123 larger than current DB revision 122, aborting..."

    db.revision.assert_called_once()


def test_changes_corrupted_file():
    db = lambda: None
    rev = lambda: None
    rev.rev = 124
    rev.uuid = b'abd'
    db.revision = MagicMock(return_value=rev)

    with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f:
        f.write("123abc")
        f.flush()
        with pytest.raises(SystemExit) as pwe:
            ns.get_changes(db, f.name)
        assert pwe.type == SystemExit
        assert pwe.value.code == f"Sync state file '{f.name}' corrupted, delete to sync from scratch."

    db.revision.assert_called_once()


def test_initial_changes():
    args = lambda: None
    args.remote = "foo"
    db = lambda: None
    rev = lambda: None
    rev.rev = 123
    rev.uuid = b'abd'
    db.revision = MagicMock(return_value=rev)
    db.default_path = MagicMock(return_value=gettempdir())

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    fname = os.path.join(gettempdir(), ".notmuch", "notmuch-sync-foo")
    with patch("notmuch2.Database", return_value=mock_ctx):
        with patch.object(ns, "get_changes", return_value=[]) as gc:
            with patch("builtins.open", mock_open()) as o:
                with ns.initial_changes(args) as (db, changes):
                    assert [] == changes
                o.assert_called_once_with(fname, "w", encoding="utf-8")
                hdl = o()
                hdl.write.assert_called_once()
                args = hdl.write.call_args.args
                assert "123 abd" == args[0]
            gc.assert_called_once_with(db, fname)

    assert db.revision.call_count == 2
    db.default_path.assert_called_once()


def test_sync_tags_empty():
    db = lambda: None
    ns.sync_tags(db, {}, {})


def test_sync_tags_only_theirs():
    m = MagicMock()
    m.frozen = MagicMock()
    m.frozen.__enter__.return_value = None
    m.frozen.__exit__.return_value = False

    mt = MagicMock(spec=list)
    tags = ["foo", "bar"]
    mt.__iter__.return_value = iter(tags)
    mt.__len__.return_value = len(tags)
    mt.clear = MagicMock()
    mt.add = MagicMock()
    mt.to_maildir_flags = MagicMock()
    type(m).tags = PropertyMock(return_value=mt)

    db = lambda: None
    db.find = MagicMock(return_value=m)

    ns.sync_tags(db, {}, {"foo": {"tags": ["bar", "foobar"]}})

    db.find.assert_called_once_with("foo")
    m.frozen.assert_called_once()
    mt.clear.assert_called_once()
    assert mt.add.mock_calls == [
        call("bar"),
        call("foobar")
    ]
    mt.to_maildir_flags.assert_called_once()


def test_sync_tags_only_theirs_no_changes():
    m = MagicMock()

    mt = MagicMock(spec=list)
    tags = ["foo", "bar"]
    mt.__iter__.return_value = iter(tags)
    mt.__len__.return_value = len(tags)
    type(m).tags = PropertyMock(return_value=mt)

    db = lambda: None
    db.find = MagicMock(return_value=m)

    ns.sync_tags(db, {}, {"foo": {"tags": ["foo", "bar"]}})

    db.find.assert_called_once_with("foo")


def test_sync_tags_only_theirs_not_found():
    db = lambda: None
    db.find = MagicMock()
    db.find.side_effect = LookupError()

    ns.sync_tags(db, {}, {"foo": {"tags": ["bar", "foobar"]}})

    db.find.assert_called_once_with("foo")


def test_sync_tags_only_mine():
    db = lambda: None
    ns.sync_tags(db, {"foo": {"tags": ["foo", "bar"]}}, {})


def test_sync_tags_mine_theirs_no_overlap():
    m = MagicMock()
    m.frozen = MagicMock()
    m.frozen.__enter__.return_value = None
    m.frozen.__exit__.return_value = False

    mt = MagicMock(spec=list)
    tags = ["foo", "bar"]
    mt.__iter__.return_value = iter(tags)
    mt.__len__.return_value = len(tags)
    mt.clear = MagicMock()
    mt.add = MagicMock()
    mt.to_maildir_flags = MagicMock()
    type(m).tags = PropertyMock(return_value=mt)

    db = lambda: None
    db.find = MagicMock(return_value=m)

    ns.sync_tags(db, {"bar": {"tags": ["tag1", "tag2"]}}, {"foo": {"tags": ["bar", "foobar"]}})

    db.find.assert_called_once_with("foo")
    m.frozen.assert_called_once()
    mt.clear.assert_called_once()
    assert mt.add.mock_calls == [
        call("bar"),
        call("foobar")
    ]
    mt.to_maildir_flags.assert_called_once()


def test_sync_tags_mine_theirs_overlap():
    m = MagicMock()
    m.frozen = MagicMock()
    m.frozen.__enter__.return_value = None
    m.frozen.__exit__.return_value = False

    mt = MagicMock(spec=list)
    tags = ["foo", "bar"]
    mt.__iter__.return_value = iter(tags)
    mt.__len__.return_value = len(tags)
    mt.clear = MagicMock()
    mt.add = MagicMock()
    mt.to_maildir_flags = MagicMock()
    type(m).tags = PropertyMock(return_value=mt)

    db = lambda: None
    db.find = MagicMock(return_value=m)

    ns.sync_tags(db, {"foo": {"tags": ["tag1", "tag2"]}}, {"foo": {"tags": ["bar", "foobar"]}})

    db.find.assert_called_once_with("foo")
    m.frozen.assert_called_once()
    mt.clear.assert_called_once()
    assert mt.add.mock_calls == [
        call("bar"),
        call("foobar"),
        call("tag1"),
        call("tag2")
    ]
    mt.to_maildir_flags.assert_called_once()


def test_sync_server(monkeypatch):
    args = lambda: None
    args.remote = "host"

    db = lambda: None
    rev = lambda: None
    rev.rev = 124
    rev.uuid = b'abd'
    db.revision = MagicMock(return_value=rev)
    db.default_path = MagicMock(return_value='/foo')

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    fname = "/foo/.notmuch/notmuch-sync-host"
    with patch("notmuch2.Database", return_value=mock_ctx):
        with patch.object(ns, "get_changes", return_value=[]) as gc:
            with patch("builtins.open", mock_open()) as o:
                monkeypatch.setattr(sys, "stdin", io.StringIO('{}'))
                ns.sync_server(args)
                o.assert_called_once_with(fname, "w", encoding="utf-8")
                hdl = o()
                hdl.write.assert_called_once()
                args = hdl.write.call_args.args
                assert "124 abd" == args[0]
            gc.assert_called_once_with(db, fname)

    assert db.revision.call_count == 2
    db.default_path.assert_called_once()


def test_sync_server_remote_host(monkeypatch):
    args = lambda: None
    args.remote = None
    args.host = "host"

    db = lambda: None
    rev = lambda: None
    rev.rev = 124
    rev.uuid = b'abd'
    db.revision = MagicMock(return_value=rev)
    db.default_path = MagicMock(return_value='/foo')

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    fname = "/foo/.notmuch/notmuch-sync-host"
    with patch("notmuch2.Database", return_value=mock_ctx):
        with patch.object(ns, "get_changes", return_value=[]) as gc:
            with patch("builtins.open", mock_open()) as o:
                monkeypatch.setattr(sys, "stdin", io.StringIO('{}'))
                ns.sync_server(args)
                o.assert_called_once_with(fname, "w", encoding="utf-8")
                hdl = o()
                hdl.write.assert_called_once()
                args = hdl.write.call_args.args
                assert "124 abd" == args[0]
            gc.assert_called_once_with(db, fname)

    assert db.revision.call_count == 2
    db.default_path.assert_called_once()


def test_sync_files_empty():
    db = lambda: None
    db.default_path = MagicMock(return_value='/foo')

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    with patch("notmuch2.Database", return_value=mock_ctx):
        assert {} == ns.get_missing_files({})

    db.default_path.assert_called_once()


def test_sync_files_new():
    m = MagicMock()
    m.filenames = MagicMock(return_value=['/foo/bar'])
    db = lambda: None
    db.default_path = MagicMock(return_value='/foo')

    def effect(*args, **kwargs):
        yield m
        while True:
            yield LookupError
    db.find = MagicMock()
    db.find.side_effect = effect()

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    changes = {"foo": {"tags": ["foo"], "files": [{"name": "bar", "sha": "abc"}]},
               "bar": {"tags": ["bar"], "files": [{"name": "foo", "sha": "def"}]}}

    with patch("notmuch2.Database", return_value=mock_ctx):
        exp = {"bar": {"type": "new",
                       "tags": ["bar"],
                       "files": [{"name": "foo", "sha": "def"}]}}
        assert exp == ns.get_missing_files(changes)

    db.default_path.assert_called_once()
    m.filenames.assert_called_once()
    assert db.find.mock_calls == [call('foo'), call('bar')]


def test_sync_files_moved():
    m = MagicMock()
    db = lambda: None
    db.default_path = MagicMock(return_value=gettempdir())

    db.find = MagicMock(return_value=m)
    db.add = MagicMock()
    db.remove = MagicMock()

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    with patch("notmuch2.Database", return_value=mock_ctx):
        with patch("shutil.move") as sm:
            with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f1:
                with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f2:
                    m.filenames = MagicMock(return_value=[f1.name])
                    f1.write("mail one")
                    f1.flush()
                    changes = {"foo": {"tags": ["foo"],
                                       "files": [{"name": f2.name.removeprefix(gettempdir() + os.sep),
                                                  "sha": "a983f58ef9ef755c4e5e3755f10cf3e08d9b189b388bcb59d29b56d35d7d6b9d"}]}}
                    assert {} == ns.get_missing_files(changes)

                    sm.assert_called_once_with(f1.name, f2.name)
                    db.add.assert_called_once_with(f2.name)
                    db.remove.assert_called_once_with(f1.name)

    db.default_path.assert_called_once()
    db.find.assert_called_once_with("foo")
    assert m.filenames.call_count == 2


def test_sync_files_copied():
    m = MagicMock()
    db = lambda: None
    db.default_path = MagicMock(return_value=gettempdir())

    db.find = MagicMock(return_value=m)
    db.add = MagicMock()

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    # this is only to get a filename that is guaranteed to be unique
    f = NamedTemporaryFile(mode="r", prefix="notmuch-sync-test-tmp-")
    f.close()
    with patch("notmuch2.Database", return_value=mock_ctx):
        with patch("shutil.copy") as sc:
            with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f1:
                m.filenames = MagicMock(return_value=[f1.name])
                f1.write("mail one")
                f1.flush()
                changes = {"foo": {"tags": ["foo"],
                                   "files": [{"name": f1.name.removeprefix(gettempdir() + os.sep),
                                              "sha": "a983f58ef9ef755c4e5e3755f10cf3e08d9b189b388bcb59d29b56d35d7d6b9d"},
                                             {"name": f.name.removeprefix(gettempdir() + os.sep),
                                              "sha": "a983f58ef9ef755c4e5e3755f10cf3e08d9b189b388bcb59d29b56d35d7d6b9d"}]}}
                assert {} == ns.get_missing_files(changes)

                sc.assert_called_once_with(f1.name, f.name)

    db.default_path.assert_called_once()
    db.find.assert_called_once_with("foo")
    db.add.assert_called_once_with(f.name)
    assert m.filenames.call_count == 2


def test_sync_files_added():
    m = MagicMock()
    db = lambda: None
    db.default_path = MagicMock(return_value=gettempdir())

    db.find = MagicMock(return_value=m)

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    with patch("notmuch2.Database", return_value=mock_ctx):
        with patch("shutil.copy") as sc:
            with patch("shutil.move") as sm:
                with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f1:
                    m.filenames = MagicMock(return_value=[f1.name])
                    f1.write("mail one")
                    f1.flush()
                    changes = {"foo": {"tags": ["foo"],
                                       "files": [{"name": f1.name.removeprefix(gettempdir() + os.sep),
                                                  "sha": "a983f58ef9ef755c4e5e3755f10cf3e08d9b189b388bcb59d29b56d35d7d6b9d"},
                                                 {"name": "bar", "sha": "abc"}]}}
                    exp = {"foo": {"type": "add",
                                   "files": [{"name": "bar", "sha": "abc"}]}}
                    assert exp == ns.get_missing_files(changes)
                assert sm.call_count == 0
                assert sc.call_count == 0

    db.default_path.assert_called_once()
    db.find.assert_called_once_with("foo")
    assert m.filenames.call_count == 2


def test_send_file():
    with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-", delete_on_close=False) as f1:
        f1.write("mail one\n")
        f1.write("mail\n")
        f1.close()
        stream = io.StringIO()
        ns.send_file(f1.name, stream)
        out = stream.getvalue()
        assert "2\nmail one\nmail\n" == out


def test_send_files():
    with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-", delete_on_close=False) as f1:
        with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-", delete_on_close=False) as f2:
            f1.write("mail one\n")
            f1.close()
            f2.write("mail two\n")
            f2.close()
            istream = io.StringIO(f"SEND {f1.name.removeprefix(gettempdir() + os.sep)}\nSEND {f2.name.removeprefix(gettempdir() + os.sep)}\nSEND_END")
            ostream = io.StringIO()
            ns.send_files(gettempdir(), istream, ostream)
            out = ostream.getvalue()
            assert "1\nmail one\n1\nmail two\n" == out


def test_send_files_nothing():
    istream = io.StringIO(f"SEND_END")
    ostream = io.StringIO()
    ns.send_files(gettempdir(), istream, ostream)
    out = ostream.getvalue()
    assert "" == out


def test_send_files_garbage():
    istream = io.StringIO(f"LKSHDF")
    ostream = io.StringIO()
    with pytest.raises(ValueError) as pwe:
        ns.send_files(gettempdir(), istream, ostream)
    assert pwe.type == ValueError
    assert str(pwe.value) == "Expected SEND, got 'LKSHDF'!"
    out = ostream.getvalue()
    assert "" == out


def test_recv_file():
    fname = "foo"
    with patch("builtins.open", mock_open()) as o:
        stream = io.StringIO("2\nmail one\nmail\n")
        ns.recv_file("foo", stream, "3d0ea99df44f734ef462d85bfeb1352edcb7af528f3386cdaa0939ac27cd8cb3")
        o.assert_called_once_with("foo", "w", encoding="utf-8")
        hdl = o()
        hdl.write.assert_called_once()
        args = hdl.write.call_args.args
        assert "mail one\nmail\n" == args[0]


def test_recv_file_checksum():
    fname = "foo"
    with patch("builtins.open", mock_open()) as o:
        stream = io.StringIO("2\nmail one\nmail\n")
        with pytest.raises(ValueError) as pwe:
            ns.recv_file("foo", stream, "abc")
        assert pwe.type == ValueError
        assert str(pwe.value) == "Checksum of received file 'foo' (3d0ea99df44f734ef462d85bfeb1352edcb7af528f3386cdaa0939ac27cd8cb3) does not match expected (abc)!"
        assert o.call_count == 0


def test_recv_files_nothing():
    istream = io.StringIO()
    ostream = io.StringIO()
    ns.recv_files(gettempdir(), {}, istream, ostream)
    out = ostream.getvalue()
    assert "SEND_END\n" == out



def test_recv_files_add():
    istream = io.StringIO("1\nmail one\n1\nmail two\n")
    ostream = io.StringIO()

    # this is only to get filenames that are guaranteed to be unique
    f1 = NamedTemporaryFile(mode="r", prefix="notmuch-sync-test-tmp-")
    f1.close()
    f1name = f1.name.removeprefix(gettempdir() + os.sep)
    f2 = NamedTemporaryFile(mode="r", prefix="notmuch-sync-test-tmp-")
    f2.close()
    f2name = f2.name.removeprefix(gettempdir() + os.sep)
    missing = {"foo": {"type": "add",
                       "files": [{"name": f1name,
                                  "sha": "2db89bdd696cbf030ed6b4908ebe0fb59a06d9c038c122ae75467e812be8102c"},
                                 {"name": f2name,
                                  "sha": "0e131e4c8a24e636c44e8f6ae155df8bec777e63a4830b1770e9f9f1e1c26667"}]}}

    db = lambda: None
    db.add = MagicMock()

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    with patch("builtins.open", mock_open()) as o:
        with patch("notmuch2.Database", return_value=mock_ctx):
            ns.recv_files(gettempdir(), missing, istream, ostream)
            assert call(f1.name, "w", encoding="utf-8") in o.mock_calls
            assert call().write('mail one\n') in o.mock_calls
            assert call(f2.name, "w", encoding="utf-8") in o.mock_calls
            assert call().write('mail two\n') in o.mock_calls
            hdl = o()
            assert hdl.write.call_count == 2

    assert db.add.mock_calls == [
        call(f1.name),
        call(f2.name)
    ]
    out = ostream.getvalue()
    assert f"SEND {f1name}\nSEND {f2name}\nSEND_END\n" == out


def test_recv_files_new():
    istream = io.StringIO("1\nmail one\n1\nmail two\n")
    ostream = io.StringIO()

    # this is only to get filenames that are guaranteed to be unique
    f1 = NamedTemporaryFile(mode="r", prefix="notmuch-sync-test-tmp-")
    f1.close()
    f1name = f1.name.removeprefix(gettempdir() + os.sep)
    f2 = NamedTemporaryFile(mode="r", prefix="notmuch-sync-test-tmp-")
    f2.close()
    f2name = f2.name.removeprefix(gettempdir() + os.sep)
    missing = {"foo": {"type": "new",
                       "tags": ["foo", "bar"],
                       "files": [{"name": f1name,
                                  "sha": "2db89bdd696cbf030ed6b4908ebe0fb59a06d9c038c122ae75467e812be8102c"},
                                 {"name": f2name,
                                  "sha": "0e131e4c8a24e636c44e8f6ae155df8bec777e63a4830b1770e9f9f1e1c26667"}]}}

    m = MagicMock()
    m.frozen = MagicMock()
    m.frozen.__enter__.return_value = None
    m.frozen.__exit__.return_value = False

    mt = MagicMock(spec=list)
    mt.__iter__.return_value = iter([])
    mt.__len__.return_value = 0
    mt.clear = MagicMock()
    mt.add = MagicMock()
    type(m).tags = PropertyMock(return_value=mt)

    db = lambda: None
    db.add = MagicMock()
    db.find = MagicMock(return_value=m)

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    with patch("builtins.open", mock_open()) as o:
        with patch("notmuch2.Database", return_value=mock_ctx):
            ns.recv_files(gettempdir(), missing, istream, ostream)
            assert call(f1.name, "w", encoding="utf-8") in o.mock_calls
            assert call().write('mail one\n') in o.mock_calls
            assert call(f2.name, "w", encoding="utf-8") in o.mock_calls
            assert call().write('mail two\n') in o.mock_calls
            hdl = o()
            assert hdl.write.call_count == 2

    assert db.add.mock_calls == [
        call(f1.name),
        call(f2.name)
    ]
    db.find.assert_called_once_with("foo")
    m.frozen.assert_called_once()
    mt.clear.assert_called_once()
    assert mt.add.mock_calls == [
        call("foo"),
        call("bar")
    ]

    out = ostream.getvalue()
    assert f"SEND {f1name}\nSEND {f2name}\nSEND_END\n" == out
