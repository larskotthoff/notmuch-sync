import pytest
import os
import sys
import io
import struct
from unittest.mock import MagicMock, PropertyMock, call, mock_open, patch
from tempfile import NamedTemporaryFile, TemporaryDirectory, gettempdir

import notmuch2

from importlib.util import spec_from_loader, module_from_spec
from importlib.machinery import SourceFileLoader 
spec = spec_from_loader("notmuch-sync", SourceFileLoader("notmuch-sync", "src/notmuch-sync"))
ns = module_from_spec(spec)
spec.loader.exec_module(ns)

prefix = gettempdir() + os.sep

def test_changes():
    mm = lambda: None
    mm.messageid = "foo"
    mm.tags = ["foo", "bar"]

    db = lambda: None
    rev = lambda: None
    rev.rev = 124
    rev.uuid = b'00000000-0000-0000-0000-000000000000'
    db.messages = MagicMock(return_value=[mm])

    with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f:
        f.write("123 00000000-0000-0000-0000-000000000000")
        f.flush()
        with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f1:
            f1.write("mail one")
            f1.flush()
            with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f2:
                f2.write("mail two")
                f2.flush()
                mm.filenames = MagicMock(return_value=[f1.name, f2.name])
                changes = ns.get_changes(db, rev, prefix, f.name)
                assert changes == {"foo": {"tags": ["foo", "bar"], "files":
                                           [f1.name.removeprefix(prefix), f2.name.removeprefix(prefix)]}}

    # expect call for new changes, since next rev number
    db.messages.assert_called_once_with("lastmod:124..")


def test_changes_first_sync():
    mm = lambda: None
    mm.messageid = "foo"
    mm.tags = ["foo", "bar"]

    db = lambda: None
    rev = lambda: None
    rev.rev = 123
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
            changes = ns.get_changes(db, rev, prefix, f.name)
            assert changes == {"foo": {"tags": ["foo", "bar"], "files":
                                       [f1.name.removeprefix(prefix), f2.name.removeprefix(prefix)]}}

    db.messages.assert_called_once_with("lastmod:0..")


def test_changes_changed_uuid():
    db = lambda: None
    rev = lambda: None
    rev.rev = 124
    rev.uuid = b'00000000-0000-0000-0000-000000000000'

    with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f:
        f.write("123 abc")
        f.flush()
        with pytest.raises(SystemExit) as pwe:
            ns.get_changes(db, rev, prefix, f.name)
        assert pwe.type == SystemExit
        assert pwe.value.code == "Last sync with UUID abc, but notmuch DB has UUID 00000000-0000-0000-0000-000000000000, aborting..."


def test_changes_later_rev():
    db = lambda: None
    rev = lambda: None
    rev.rev = 122
    rev.uuid = b'00000000-0000-0000-0000-000000000000'

    with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f:
        f.write("123 00000000-0000-0000-0000-000000000000")
        f.flush()
        with pytest.raises(SystemExit) as pwe:
            ns.get_changes(db, rev, prefix, f.name)
        assert pwe.type == SystemExit
        assert pwe.value.code == "Last sync revision 123 larger than current DB revision 122, aborting..."


def test_changes_corrupted_file():
    db = lambda: None
    rev = lambda: None
    rev.rev = 124
    rev.uuid = b'00000000-0000-0000-0000-000000000000'

    with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f:
        f.write("123abc")
        f.flush()
        with pytest.raises(SystemExit) as pwe:
            ns.get_changes(db, rev, prefix, f.name)
        assert pwe.type == SystemExit
        assert pwe.value.code == f"Sync state file '{f.name}' corrupted, delete to sync from scratch."


def test_initial_sync():
    db = lambda: None
    rev = lambda: None
    rev.rev = 123
    rev.uuid = b'00000000-0000-0000-0000-000000000000'
    db.revision = MagicMock(return_value=rev)
    db.default_path = MagicMock(return_value=gettempdir())

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    fname = os.path.join(gettempdir(), ".notmuch", "notmuch-sync-00000000-0000-0000-0000-000000000001")
    with patch("notmuch2.Database", return_value=mock_ctx):
        with patch.object(ns, "get_changes", return_value=[]) as gc:
            istream = io.BytesIO(b"00000000-0000-0000-0000-000000000001\x00\x00\x00\x02[]")
            ostream = io.BytesIO()
            prefix, mine, theirs, nchanges, syncname, rev = ns.initial_sync(istream, ostream)
            assert mine == []
            assert theirs == []
            assert nchanges == 0
            assert syncname == fname
            assert rev.rev == 123
            assert rev.uuid == b"00000000-0000-0000-0000-000000000000"
            assert b"00000000-0000-0000-0000-000000000000\x00\x00\x00\x02[]" == ostream.getvalue()

            gc.assert_called_once_with(db, rev, prefix, fname)

    assert db.revision.call_count == 2
    db.default_path.assert_called_once()


def test_record_sync():
    rev = lambda: None
    rev.rev = 123
    rev.uuid = b'00000000-0000-0000-0000-000000000000'

    fname = os.path.join(gettempdir(), ".notmuch", "notmuch-sync-00000000-0000-0000-0000-000000000001")
    with patch("builtins.open", mock_open()) as o:
        ns.record_sync(fname, rev)
        o.assert_called_once_with(fname, "w", encoding="utf-8")
        hdl = o()
        hdl.write.assert_called_once()
        args = hdl.write.call_args.args
        assert "123 00000000-0000-0000-0000-000000000000" == args[0]


def test_sync_tags_empty():
    db = lambda: None
    changes = ns.sync_tags(db, {}, {})
    assert changes == 0


def test_sync_tags_only_theirs():
    m = MagicMock()
    m.frozen = MagicMock()
    m.frozen.__enter__.return_value = None
    m.frozen.__exit__.return_value = False
    m.ghost = False

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

    changes = ns.sync_tags(db, {}, {"foo": {"tags": ["bar", "foobar"]}})
    assert changes == 1

    db.find.assert_called_once_with("foo")
    m.frozen.assert_called_once()
    mt.clear.assert_called_once()
    assert mt.add.mock_calls == [
        call("bar"),
        call("foobar")
    ]
    mt.to_maildir_flags.assert_called_once()


def test_sync_tags_only_theirs_ghost():
    m = MagicMock()
    m.ghost = True

    db = lambda: None
    db.find = MagicMock(return_value=m)

    changes = ns.sync_tags(db, {}, {"foo": {"tags": ["bar", "foobar"]}})
    assert changes == 0

    db.find.assert_called_once_with("foo")


def test_sync_tags_only_theirs_no_changes():
    m = MagicMock()

    mt = MagicMock(spec=list)
    tags = ["foo", "bar"]
    mt.__iter__.return_value = iter(tags)
    mt.__len__.return_value = len(tags)
    type(m).tags = PropertyMock(return_value=mt)

    db = lambda: None
    db.find = MagicMock(return_value=m)

    changes = ns.sync_tags(db, {}, {"foo": {"tags": ["foo", "bar"]}})
    assert changes == 0

    db.find.assert_called_once_with("foo")


def test_sync_tags_only_theirs_not_found():
    db = lambda: None
    db.find = MagicMock()
    db.find.side_effect = LookupError()

    changes = ns.sync_tags(db, {}, {"foo": {"tags": ["bar", "foobar"]}})
    assert changes == 0

    db.find.assert_called_once_with("foo")


def test_sync_tags_only_mine():
    db = lambda: None
    changes = ns.sync_tags(db, {"foo": {"tags": ["foo", "bar"]}}, {})
    assert changes == 0


def test_sync_tags_mine_theirs_no_overlap():
    m = MagicMock()
    m.frozen = MagicMock()
    m.frozen.__enter__.return_value = None
    m.frozen.__exit__.return_value = False
    m.ghost = False

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

    changes = ns.sync_tags(db, {"bar": {"tags": ["tag1", "tag2"]}}, {"foo": {"tags": ["bar", "foobar"]}})
    assert changes == 1

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
    m.ghost = False

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

    changes = ns.sync_tags(db, {"foo": {"tags": ["tag1", "tag2"]}}, {"foo": {"tags": ["bar", "foobar"]}})
    assert changes == 1

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
    args.delete = False
    args.mbsync = False

    db = lambda: None
    rev = lambda: None
    rev.rev = 124
    rev.uuid = b'00000000-0000-0000-0000-000000000000'
    db.revision = MagicMock(return_value=rev)
    db.default_path = MagicMock(return_value=gettempdir())

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    fname = os.path.join(gettempdir(), ".notmuch", "notmuch-sync-00000000-0000-0000-0000-000000000001")
    with patch("notmuch2.Database", return_value=mock_ctx):
        with patch.object(ns, "get_changes", return_value=[]) as gc:
            with patch("builtins.open", mock_open()) as o:
                mockio = io.BytesIO(b'00000000-0000-0000-0000-000000000001\x00\x00\x00\x02{}\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
                mockio.buffer = mockio
                monkeypatch.setattr(sys, "stdin", mockio)
                ns.sync_remote(args)
                o.assert_called_once_with(fname, "w", encoding="utf-8")
                hdl = o()
                hdl.write.assert_called_once()
                args = hdl.write.call_args.args
                assert "124 00000000-0000-0000-0000-000000000000" == args[0]
            gc.assert_called_once_with(db, rev, prefix, fname)

    assert db.revision.call_count == 2
    db.default_path.assert_called_once()


def test_missing_files_empty():
    db = lambda: None

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    with patch("notmuch2.Database", return_value=mock_ctx):
        istream = io.BytesIO(b"\x00\x00\x00\x00\x00\x00\x00\x00")
        ostream = io.BytesIO()
        assert ({}, 0, 0) == ns.get_missing_files({}, {}, prefix, istream, ostream)
        assert b"\x00\x00\x00\x00\x00\x00\x00\x00" == ostream.getvalue()


def test_missing_files_new():
    m = MagicMock()
    m.filenames = MagicMock(return_value=[os.path.join(gettempdir(), "foofile")])
    m.ghost = False
    db = lambda: None

    def effect(*args, **kwargs):
        yield m
        yield LookupError
        yield m
        while True:
            yield LookupError
    db.find = MagicMock()
    db.find.side_effect = effect()

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    changes = {"foo": {"tags": ["foo"], "files": ["foofile"]},
               "bar": {"tags": ["bar"], "files": ["barfile"]}}

    with patch("notmuch2.Database", return_value=mock_ctx):
        istream = io.BytesIO(b"\x00\x00\x00\x00\x00\x00\x00\x00")
        ostream = io.BytesIO()
        exp = {"bar": {"tags": ["bar"], "files": ["barfile"]}}
        assert (exp, 0, 0) == ns.get_missing_files({}, changes, prefix, istream, ostream)
        assert b"\x00\x00\x00\x00\x00\x00\x00\x00" == ostream.getvalue()

    assert m.filenames.call_count == 2
    assert db.find.mock_calls == [call('foo'), call('bar'), call('foo'), call('bar')]


def test_missing_files_ghost():
    m = MagicMock()
    m.ghost = True
    db = lambda: None

    db.find = MagicMock(return_value=m)

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    changes = {"bar": {"tags": ["bar"], "files": ["foo"]}}

    with patch("notmuch2.Database", return_value=mock_ctx):
        istream = io.BytesIO(b"\x00\x00\x00\x00\x00\x00\x00\x00")
        ostream = io.BytesIO()
        exp = {"bar": {"tags": ["bar"], "files": ["foo"]}}
        assert (exp, 0, 0) == ns.get_missing_files({}, changes, prefix, istream, ostream)
        assert b"\x00\x00\x00\x00\x00\x00\x00\x00" == ostream.getvalue()

    assert db.find.mock_calls == [ call("bar"), call("bar") ]


def test_missing_files_inconsistent_no_move():
    m = MagicMock()
    m.ghost = False
    db = lambda: None

    db.find = MagicMock(return_value=m)
    db.add = MagicMock(return_value=(m, True))
    db.remove = MagicMock()

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    with patch("notmuch2.Database", return_value=mock_ctx):
        with patch("shutil.move") as sm:
            with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f1:
                with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f2:
                    istream = io.BytesIO(b"\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x40a983f58ef9ef755c4e5e3755f10cf3e08d9b189b388bcb59d29b56d35d7d6b9d")
                    ostream = io.BytesIO()
                    m.filenames = MagicMock(return_value=[f1.name])
                    f1.write("mail one")
                    f1.flush()
                    f2.write("mail one")
                    f2.flush()
                    f2name = f2.name.removeprefix(prefix)
                    changes_mine = {"foo": {"tags": ["foo"], "files": [f1.name.removeprefix(prefix)]}}
                    changes_theirs = {"foo": {"tags": ["foo"], "files": [f2name]}}
                    assert ({}, 0, 0) == ns.get_missing_files(changes_mine, changes_theirs, prefix, istream, ostream, move_on_change=False)
                    assert b"\x00\x00\x00\x01" + struct.pack("!I", len(f2name)) + f2name.encode("utf-8") + b"\x00\x00\x00\x00" == ostream.getvalue()

                    assert sm.call_count == 0
                    assert db.add.call_count == 0
                    assert db.remove.call_count == 0
                    assert db.find.mock_calls == [ call("foo"), call("foo") ]

    assert m.filenames.call_count == 3


def test_missing_files_inconsistent_move():
    m = MagicMock()
    m.ghost = False
    db = lambda: None

    db.find = MagicMock(return_value=m)
    db.add = MagicMock(return_value=(m, True))
    db.remove = MagicMock()

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    with patch("notmuch2.Database", return_value=mock_ctx):
        with patch("shutil.move") as sm:
            with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f1:
                with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f2:
                    istream = io.BytesIO(b"\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x40a983f58ef9ef755c4e5e3755f10cf3e08d9b189b388bcb59d29b56d35d7d6b9d")
                    ostream = io.BytesIO()
                    m.filenames = MagicMock(return_value=[f1.name])
                    f1.write("mail one")
                    f1.flush()
                    f2.write("mail one")
                    f2.flush()
                    f2name = f2.name.removeprefix(prefix)
                    changes_mine = {"foo": {"tags": ["foo"], "files": [f1.name.removeprefix(prefix)]}}
                    changes_theirs = {"foo": {"tags": ["foo"], "files": [f2name]}}
                    assert ({}, 1, 0) == ns.get_missing_files(changes_mine, changes_theirs, prefix, istream, ostream, move_on_change=True)
                    assert b"\x00\x00\x00\x01" + struct.pack("!I", len(f2name)) + f2name.encode("utf-8") + b"\x00\x00\x00\x00" == ostream.getvalue()

                    sm.assert_called_once_with(f1.name, f2.name)
                    db.add.assert_called_once_with(f2.name)
                    db.remove.assert_called_once_with(f1.name)
                    assert m.filenames.call_count == 3

    assert db.find.mock_calls == [ call("foo"), call("foo") ]


def test_missing_files_moved():
    m = MagicMock()
    m.ghost = False
    db = lambda: None

    db.find = MagicMock(return_value=m)
    db.add = MagicMock(return_value=(m, True))
    db.remove = MagicMock()

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    with patch("notmuch2.Database", return_value=mock_ctx):
        with patch("shutil.move") as sm:
            with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f1:
                with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f2:
                    istream = io.BytesIO(b"\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x40a983f58ef9ef755c4e5e3755f10cf3e08d9b189b388bcb59d29b56d35d7d6b9d")
                    ostream = io.BytesIO()
                    m.filenames = MagicMock(return_value=[f1.name])
                    f1.write("mail one")
                    f1.flush()
                    f2name = f2.name.removeprefix(prefix)
                    changes = {"foo": {"tags": ["foo"], "files": [f2name]}}
                    assert ({}, 1, 0) == ns.get_missing_files({}, changes, prefix, istream, ostream)
                    assert b"\x00\x00\x00\x01" + struct.pack("!I", len(f2name)) + f2name.encode("utf-8") + b"\x00\x00\x00\x00" == ostream.getvalue()

                    sm.assert_called_once_with(f1.name, f2.name)
                    db.add.assert_called_once_with(f2.name)
                    db.remove.assert_called_once_with(f1.name)
                    assert m.filenames.call_count == 3

    assert db.find.mock_calls == [ call("foo"), call("foo") ]


def test_missing_files_copied():
    m = MagicMock()
    m.ghost = False
    db = lambda: None

    db.find = MagicMock(return_value=m)
    db.add = MagicMock(return_value=(m, True))

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    # this is only to get a filename that is guaranteed to be unique
    f = NamedTemporaryFile(mode="r", prefix="notmuch-sync-test-tmp-")
    f.close()
    with patch("notmuch2.Database", return_value=mock_ctx):
        with patch("shutil.copy") as sc:
            with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f1:
                istream = io.BytesIO(b"\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x40a983f58ef9ef755c4e5e3755f10cf3e08d9b189b388bcb59d29b56d35d7d6b9d\x00\x00\x00\x40a983f58ef9ef755c4e5e3755f10cf3e08d9b189b388bcb59d29b56d35d7d6b9d")
                ostream = io.BytesIO()
                m.filenames = MagicMock(return_value=[f1.name])
                f1.write("mail one")
                f1.flush()
                fname = f.name.removeprefix(prefix)
                f1name = f1.name.removeprefix(prefix)
                changes = {"foo": {"tags": ["foo"], "files": [f1name, fname]}}
                assert ({}, 1, 0) == ns.get_missing_files({}, changes, prefix, istream, ostream)
                assert b"\x00\x00\x00\x02" + struct.pack("!I", len(f1name)) + f1name.encode("utf-8") + struct.pack("!I", len(fname)) + fname.encode("utf-8") + b"\x00\x00\x00\x00" == ostream.getvalue()

                sc.assert_called_once_with(f1.name, f.name)

    assert m.filenames.call_count == 3
    assert db.find.mock_calls == [ call("foo"), call("foo") ]
    db.add.assert_called_once_with(f.name)


def test_missing_files_added():
    m = MagicMock()
    m.ghost = False
    db = lambda: None

    db.find = MagicMock(return_value=m)

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    with patch("notmuch2.Database", return_value=mock_ctx):
        with patch("shutil.copy") as sc:
            with patch("shutil.move") as sm:
                with patch("pathlib.Path.unlink") as pu:
                    with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f1:
                        istream = io.BytesIO(b"\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x40a983f58ef9ef755c4e5e3755f10cf3e08d9b189b388bcb59d29b56d35d7d6b9d\x00\x00\x00\x03abc")
                        ostream = io.BytesIO()
                        m.filenames = MagicMock(return_value=[f1.name])
                        f1.write("mail one")
                        f1.flush()
                        f1name = f1.name.removeprefix(prefix)
                        changes = {"foo": {"tags": ["foo"], "files": [f1name, "bar"]}}
                        exp = {"foo": {"files": ["bar"]}}
                        assert (exp, 0, 0) == ns.get_missing_files({}, changes, prefix, istream, ostream)
                        assert b"\x00\x00\x00\x02" + struct.pack("!I", len(f1name)) + f1name.encode("utf-8") + b"\x00\x00\x00\x03bar\x00\x00\x00\x00" == ostream.getvalue()
                        assert pu.call_count == 0

                assert sm.call_count == 0
                assert sc.call_count == 0

    assert db.find.mock_calls == [ call("foo"), call("foo") ]
    assert m.filenames.call_count == 3


def test_missing_files_delete():
    m = MagicMock()
    m.ghost = False
    db = lambda: None

    db.find = MagicMock(return_value=m)
    db.remove = MagicMock()

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    with patch("notmuch2.Database", return_value=mock_ctx):
        with patch("shutil.copy") as sc:
            with patch("shutil.move") as sm:
                with patch("pathlib.Path.unlink") as pu:
                    with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f1:
                        with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f2:
                            istream = io.BytesIO(b"\x00\x00\x00\x00\x00\x00\x00\x00")
                            ostream = io.BytesIO()
                            m.filenames = MagicMock(return_value=[f1.name, f2.name])
                            f1.write("mail one")
                            f1.flush()
                            f2.write("mail one")
                            f2.flush()
                            changes = {"foo": {"tags": ["foo"], "files": [f1.name.removeprefix(prefix)]}}
                            assert ({}, 0, 1) == ns.get_missing_files({}, changes, prefix, istream, ostream)
                            assert b"\x00\x00\x00\x00\x00\x00\x00\x00"
                            db.remove.assert_called_once_with(f2.name)
                            pu.assert_called_once()
                assert sm.call_count == 0
                assert sc.call_count == 0

    assert db.find.mock_calls == [ call("foo"), call("foo") ]
    assert m.filenames.call_count == 2


def test_missing_files_delete_changed():
    m = MagicMock()
    m.ghost = False
    db = lambda: None

    db.find = MagicMock(return_value=m)
    db.remove = MagicMock()

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    with patch("notmuch2.Database", return_value=mock_ctx):
        with patch("shutil.copy") as sc:
            with patch("shutil.move") as sm:
                with patch("pathlib.Path.unlink") as pu:
                    with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f1:
                        with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f2:
                            istream = io.BytesIO(b"\x00\x00\x00\x00\x00\x00\x00\x00")
                            ostream = io.BytesIO()
                            m.filenames = MagicMock(return_value=[f1.name, f2.name])
                            f1.write("mail one")
                            f1.flush()
                            f2.write("mail one")
                            f2.flush()
                            changes_theirs = {"foo": {"tags": ["foo"], "files": [f1.name.removeprefix(prefix)]}}
                            changes_mine = {"foo": {"tags": ["foo"], "files": [f2.name.removeprefix(prefix)]}}
                            assert ({}, 0, 0) == ns.get_missing_files(changes_mine, changes_theirs, prefix, istream, ostream)
                            assert b"\x00\x00\x00\x00\x00\x00\x00\x00"
                            assert pu.call_count == 0
                assert sm.call_count == 0
                assert sc.call_count == 0

    assert db.remove.call_count == 0
    assert db.find.mock_calls == [ call("foo"), call("foo") ]
    assert m.filenames.call_count == 2


def test_missing_files_copy_delete():
    m = MagicMock()
    m.ghost = False
    db = lambda: None

    db.find = MagicMock(return_value=m)
    db.add = MagicMock()
    db.remove = MagicMock()

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    with patch("notmuch2.Database", return_value=mock_ctx):
        with patch("shutil.move") as sm:
            with patch("pathlib.Path.unlink") as pu:
                with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f1:
                    with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f2:
                        with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f3:
                            istream = io.BytesIO(b"\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x40a983f58ef9ef755c4e5e3755f10cf3e08d9b189b388bcb59d29b56d35d7d6b9d")
                            ostream = io.BytesIO()
                            m.filenames = MagicMock(return_value=[f1.name, f3.name])
                            f1.write("mail one")
                            f1.flush()
                            f2.write("mail one")
                            f2.flush()
                            f3.write("not mail one")
                            f3.flush()
                            f2name = f2.name.removeprefix(prefix)
                            changes_theirs = {"foo": {"tags": ["foo"], "files": [f2name]}}
                            assert ({}, 1, 1) == ns.get_missing_files({}, changes_theirs, prefix, istream, ostream)
                            assert b"\x00\x00\x00\x01" + struct.pack("!I", len(f2name)) + f2name.encode("utf-8") + b"\x00\x00\x00\x00" == ostream.getvalue()

                            sm.assert_called_once_with(f1.name, f2.name)
                            db.add.assert_called_once_with(f2.name)
                            assert db.remove.mock_calls == [
                                call(f1.name),
                                call(f3.name)
                            ]
                            pu.assert_called_once()

    assert db.find.mock_calls == [ call("foo"), call("foo") ]
    assert m.filenames.call_count == 3


def test_missing_files_delete_mismatch():
    m = MagicMock()
    m.ghost = False
    db = lambda: None

    db.find = MagicMock(return_value=m)
    db.add = MagicMock(return_value=(m, True))
    db.remove = MagicMock()

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    with patch("notmuch2.Database", return_value=mock_ctx):
        with patch("pathlib.Path.unlink") as pu:
            with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f1:
                with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f2:
                    istream = io.BytesIO(b"\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x40a983f58ef9ef755c4e5e3755f10cf3e08d9b189b388bcb59d29b56d35d7d6b9d")
                    ostream = io.BytesIO()
                    m.filenames = MagicMock(return_value=[f1.name])
                    f1.write("mail two")
                    f1.flush()
                    f2.write("mail one")
                    f2.flush()
                    f2name = f2.name.removeprefix(prefix)
                    changes_theirs = {"foo": {"tags": ["foo"], "files": [f2name]}}
                    with pytest.raises(ValueError) as pwe:
                        ns.get_missing_files({}, changes_theirs, prefix, istream, ostream)
                    assert b"\x00\x00\x00\x01" + struct.pack("!I", len(f2name)) + f2name.encode("utf-8") + b"\x00\x00\x00\x00" == ostream.getvalue()
                    assert pwe.type == ValueError
                    assert str(pwe.value) == f"Message 'foo' has ['{f2name}'] on remote and different ['{f1.name.removeprefix(prefix)}'] locally!"

                    assert db.add.call_count == 0
                    assert pu.call_count == 0

    assert db.find.mock_calls == [ call("foo"), call("foo") ]
    assert m.filenames.call_count == 3


def test_send_file():
    with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-", delete_on_close=False) as f1:
        f1.write("mail one\n")
        f1.write("mail\n")
        f1.close()
        stream = io.BytesIO()
        ns.send_file(f1.name, stream)
        out = stream.getvalue()
        assert b"\x00\x00\x00\x0email one\nmail\n" == out



def test_recv_file():
    fname = "foo"
    with patch("builtins.open", mock_open()) as o:
        stream = io.BytesIO(b"\x00\x00\x00\x0email one\nmail\n")
        ns.recv_file("foo", stream, "3d0ea99df44f734ef462d85bfeb1352edcb7af528f3386cdaa0939ac27cd8cb3")
        o.assert_called_once_with("foo", "wb")
        hdl = o()
        hdl.write.assert_called_once()
        args = hdl.write.call_args.args
        assert b"mail one\nmail\n" == args[0]


def test_recv_file_exists():
    fname = "foo"
    with patch("builtins.open", mock_open()) as o:
        with patch("pathlib.Path.exists") as pe:
            with patch("pathlib.Path.read_bytes") as prb:
                pe.return_value = True
                prb.return_value = b"mail one"
                stream = io.BytesIO(b"\x00\x00\x00\x0email one\nmail\n")
                with pytest.raises(ValueError) as pwe:
                    ns.recv_file("foo", stream, "3d0ea99df44f734ef462d85bfeb1352edcb7af528f3386cdaa0939ac27cd8cb3")
                assert pwe.type == ValueError
                assert str(pwe.value) == "Set to receive 'foo', but already exists with different content!"
                assert pe.call_count == 1
                assert o.call_count == 0


def test_sync_files_nothing():
    istream = io.BytesIO(b"\x00\x00\x00\x00")
    ostream = io.BytesIO()
    assert (0, 0) == ns.sync_files(prefix, {}, istream, ostream)
    out = ostream.getvalue()
    assert b"\x00\x00\x00\x00" == out


def test_sync_files_recv_add():
    istream = io.BytesIO(b"\x00\x00\x00\x00\x00\x00\x00\x09mail one\n\x00\x00\x00\x09mail two\n")
    ostream = io.BytesIO()

    # this is only to get filenames that are guaranteed to be unique
    f1 = NamedTemporaryFile(mode="r", prefix="notmuch-sync-test-tmp-")
    f1.close()
    f1name = f1.name.removeprefix(prefix)
    f2 = NamedTemporaryFile(mode="r", prefix="notmuch-sync-test-tmp-")
    f2.close()
    f2name = f2.name.removeprefix(prefix)
    missing = {"foo": {"files": [f1name, f2name]}}

    db = lambda: None
    db.add = MagicMock(return_value=(lambda: None, True))

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    with patch("builtins.open", mock_open()) as o:
        with patch("notmuch2.Database", return_value=mock_ctx):
            assert (0, 2) == ns.sync_files(prefix, missing, istream, ostream)
            assert call(f1.name, "wb") in o.mock_calls
            assert call().write(b'mail one\n') in o.mock_calls
            assert call(f2.name, "wb") in o.mock_calls
            assert call().write(b'mail two\n') in o.mock_calls
            hdl = o()
            assert hdl.write.call_count == 2

    assert db.add.mock_calls == [
        call(f1.name),
        call(f2.name)
    ]
    out = ostream.getvalue()
    assert b"\x00\x00\x00\x02" + struct.pack("!I", len(f1name)) + f1name.encode("utf-8") + struct.pack("!I", len(f2name)) + f2name.encode("utf-8") == out


def test_sync_files_recv_new():
    istream = io.BytesIO(b"\x00\x00\x00\x00\x00\x00\x00\x09mail one\n\x00\x00\x00\x09mail two\n")
    ostream = io.BytesIO()

    # this is only to get filenames that are guaranteed to be unique
    f1 = NamedTemporaryFile(mode="r", prefix="notmuch-sync-test-tmp-")
    f1.close()
    f1name = f1.name.removeprefix(prefix)
    f2 = NamedTemporaryFile(mode="r", prefix="notmuch-sync-test-tmp-")
    f2.close()
    f2name = f2.name.removeprefix(prefix)
    missing = {"foo": {"tags": ["foo", "bar"], "files": [f1name, f2name]}}

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
    db.add.side_effect = [(m, False), (m, True)]

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    with patch("builtins.open", mock_open()) as o:
        with patch("notmuch2.Database", return_value=mock_ctx):
            assert (1, 2) == ns.sync_files(prefix, missing, istream, ostream)
            assert call(f1.name, "wb") in o.mock_calls
            assert call().write(b'mail one\n') in o.mock_calls
            assert call(f2.name, "wb") in o.mock_calls
            assert call().write(b'mail two\n') in o.mock_calls
            hdl = o()
            assert hdl.write.call_count == 2

    assert db.add.mock_calls == [
        call(f1.name),
        call(f2.name)
    ]
    m.frozen.assert_called_once()
    mt.clear.assert_called_once()
    assert mt.add.mock_calls == [
        call("foo"),
        call("bar")
    ]

    out = ostream.getvalue()
    assert b"\x00\x00\x00\x02" + struct.pack("!I", len(f1name)) + f1name.encode("utf-8") + struct.pack("!I", len(f2name)) + f2name.encode("utf-8") == out


def test_sync_files_send():
    missing = {}
    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = lambda: None
    mock_ctx.__exit__.return_value = False
    with patch("notmuch2.Database", return_value=mock_ctx):
        with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f1:
            f1.write("mail one\n")
            f1.flush()
            with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f2:
                f2.write("mail two\n")
                f2.flush()
                istream = io.BytesIO(b"\x00\x00\x00\x02" + struct.pack("!I", len(f1.name)) + f1.name.encode("utf-8") + struct.pack("!I", len(f2.name)) + f2.name.encode("utf-8"))
                ostream = io.BytesIO()
                assert (0, 0) == ns.sync_files(prefix, missing, istream, ostream)
                out = ostream.getvalue()
                assert b"\x00\x00\x00\x00\x00\x00\x00\x09mail one\n\x00\x00\x00\x09mail two\n" == out


def test_sync_files_send_recv_add():
    # this is only to get filenames that are guaranteed to be unique
    f1 = NamedTemporaryFile(mode="r", prefix="notmuch-sync-test-tmp-")
    f1.close()
    f1name = f1.name.removeprefix(prefix)
    f2 = NamedTemporaryFile(mode="r", prefix="notmuch-sync-test-tmp-")
    f2.close()
    f2name = f2.name.removeprefix(prefix)
    missing = {"foo": {"files": [f1name, f2name]}}

    db = lambda: None
    db.add = MagicMock(return_value=(lambda: None, True))

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    with patch("builtins.open", mock_open(read_data=b"mail three\n")) as o:
        with patch("notmuch2.Database", return_value=mock_ctx):
            istream = io.BytesIO(b"\x00\x00\x00\x01" + struct.pack("!I", len(f1.name)) + f1.name.encode("utf-8") + b"\x00\x00\x00\x09mail one\n\x00\x00\x00\x09mail two\n")
            ostream = io.BytesIO()
            assert (0, 2) == ns.sync_files(prefix, missing, istream, ostream)
            assert call(f1.name, "wb") in o.mock_calls
            assert call().write(b'mail one\n') in o.mock_calls
            assert call(f2.name, "wb") in o.mock_calls
            assert call().write(b'mail two\n') in o.mock_calls
            assert call(f1.name, "rb") in o.mock_calls
            assert call().write(b'mail one\n') in o.mock_calls
            hdl = o()
            assert hdl.write.call_count == 2
            assert hdl.read.call_count == 1

            out = ostream.getvalue()
            res = b"\x00\x00\x00\x02" + struct.pack("!I", len(f1name)) + f1name.encode("utf-8") + struct.pack("!I", len(f2name)) + f2name.encode("utf-8")
            res += b"\x00\x00\x00\x0bmail three\n"
            assert res == out

    assert db.add.mock_calls == [
        call(f1.name),
        call(f2.name)
    ]


def test_sync_deletes_local():
    m1 = lambda: None
    m1.messageid = "foo"
    m2 = lambda: None
    m2.messageid = "bar"
    m2.filenames = MagicMock(return_value=["barfile"])
    m2.tags = ["deleted"]
    m2.ghost = False

    db = lambda: None
    db.messages = MagicMock(return_value=[m1, m2])
    db.remove = MagicMock()
    db.find = MagicMock(return_value=m2)

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    with patch("notmuch2.Database", return_value=mock_ctx):
        with patch("pathlib.Path.unlink") as pu:
            istream = io.BytesIO(b"\x00\x00\x00\x01\x00\x00\x00\x03foo")
            ostream = io.BytesIO()
            assert 1 == ns.sync_deletes_local(istream, ostream)
            pu.assert_called_once()

            out = ostream.getvalue()
            assert b"\x00\x00\x00\x00" == out

    db.messages.assert_called_once_with("*")
    db.find.assert_called_once_with("bar")
    db.remove.assert_called_once_with("barfile")
    m2.filenames.assert_called_once()


def test_sync_deletes_local_no_deleted():
    m1 = lambda: None
    m1.messageid = "foo"
    m2 = MagicMock()
    m2.messageid = "bar"
    m2.filenames = MagicMock(return_value=["barfile"])
    mt = MagicMock(spec=list)
    tags = ["foo"]
    mt.__iter__.return_value = iter(tags)
    mt.__len__.return_value = len(tags)
    mt.add = MagicMock()
    mt.discard = MagicMock()
    type(m2).tags = PropertyMock(return_value=mt)
    m2.frozen = MagicMock()
    m2.frozen.__enter__.return_value = None
    m2.frozen.__exit__.return_value = False
    m2.ghost = False

    db = lambda: None
    db.messages = MagicMock(return_value=[m1, m2])
    db.remove = MagicMock()
    db.find = MagicMock(return_value=m2)

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    with patch("notmuch2.Database", return_value=mock_ctx):
        with patch("pathlib.Path.unlink") as pu:
            istream = io.BytesIO(b"\x00\x00\x00\x01\x00\x00\x00\x03foo")
            ostream = io.BytesIO()
            assert 0 == ns.sync_deletes_local(istream, ostream)
            assert pu.call_count == 0

            out = ostream.getvalue()
            assert b"\x00\x00\x00\x00" == out

    db.messages.assert_called_once_with("*")
    db.find.assert_called_once_with("bar")
    assert db.remove.call_count == 0
    assert m2.filenames.call_count == 0
    mt.add.assert_called_once_with("foo")
    mt.discard.assert_called_once_with("foo")


def test_sync_deletes_local_no_deleted_no_check():
    m1 = lambda: None
    m1.messageid = "foo"
    m2 = lambda: None
    m2.messageid = "bar"
    m2.filenames = MagicMock(return_value=["barfile"])
    m2.tags = ["foo"]
    m2.ghost = False

    db = lambda: None
    db.messages = MagicMock(return_value=[m1, m2])
    db.remove = MagicMock()
    db.find = MagicMock(return_value=m2)

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    with patch("notmuch2.Database", return_value=mock_ctx):
        with patch("pathlib.Path.unlink") as pu:
            istream = io.BytesIO(b"\x00\x00\x00\x01\x00\x00\x00\x03foo")
            ostream = io.BytesIO()
            assert 1 == ns.sync_deletes_local(istream, ostream, no_check=True)
            pu.assert_called_once()

            out = ostream.getvalue()
            assert b"\x00\x00\x00\x00" == out

    db.messages.assert_called_once_with("*")
    db.find.assert_called_once_with("bar")
    db.remove.assert_called_once_with("barfile")
    m2.filenames.assert_called_once()


def test_sync_deletes_local_ghost():
    m1 = lambda: None
    m1.messageid = "foo"
    m2 = lambda: None
    m2.messageid = "bar"
    m2.filenames = MagicMock(return_value=["barfile"])
    m2.ghost = True

    db = lambda: None
    db.messages = MagicMock(return_value=[m1, m2])
    db.remove = MagicMock()
    db.find = MagicMock(return_value=m2)

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    with patch("notmuch2.Database", return_value=mock_ctx):
        with patch("pathlib.Path.unlink") as pu:
            istream = io.BytesIO(b"\x00\x00\x00\x01\x00\x00\x00\x03foo")
            ostream = io.BytesIO()
            assert 0 == ns.sync_deletes_local(istream, ostream)
            assert pu.call_count == 0

            out = ostream.getvalue()
            assert b"\x00\x00\x00\x00" == out

    db.messages.assert_called_once_with("*")
    db.find.assert_called_once_with("bar")
    assert db.remove.call_count == 0
    assert m2.filenames.call_count == 0


def test_sync_deletes_local_none():
    m1 = lambda: None
    m1.messageid = "foo"
    m2 = lambda: None
    m2.messageid = "bar"

    db = lambda: None
    db.messages = MagicMock(return_value=[m1, m2])
    db.remove = MagicMock()

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    with patch("notmuch2.Database", return_value=mock_ctx):
        with patch("pathlib.Path.unlink") as pu:
            istream = io.BytesIO(b"\x00\x00\x00\x02\x00\x00\x00\x03foo\x00\x00\x00\x03bar")
            ostream = io.BytesIO()
            assert 0 == ns.sync_deletes_local(istream, ostream)
            assert pu.call_count == 0

            out = ostream.getvalue()
            assert b"\x00\x00\x00\x00" == out

    db.messages.assert_called_once_with("*")
    assert db.remove.call_count == 0


def test_sync_deletes_remote():
    m1 = lambda: None
    m1.messageid = "foo"
    m2 = lambda: None
    m2.messageid = "bar"
    m2.filenames = MagicMock(return_value=["barfile"])
    m2.tags = ["deleted"]
    m2.ghost = False

    db = lambda: None
    db.messages = MagicMock(return_value=[m1, m2])
    db.remove = MagicMock()
    db.find = MagicMock(return_value=m2)

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    with patch("notmuch2.Database", return_value=mock_ctx):
        with patch("pathlib.Path.unlink") as pu:
            istream = io.BytesIO(b"\x00\x00\x00\x01\x00\x00\x00\x03bar")
            ostream = io.BytesIO()
            assert 1 == ns.sync_deletes_remote(istream, ostream)
            pu.assert_called_once()

            out = ostream.getvalue()
            assert b"\x00\x00\x00\x02\x00\x00\x00\x03foo\x00\x00\x00\x03bar" == out

    db.messages.assert_called_once_with("*")
    db.find.assert_called_once_with("bar")
    db.remove.assert_called_once_with("barfile")
    m2.filenames.assert_called_once()


def test_sync_deletes_remote_no_deleted():
    m1 = lambda: None
    m1.messageid = "foo"
    m2 = MagicMock()
    m2.messageid = "bar"
    m2.filenames = MagicMock(return_value=["barfile"])
    mt = MagicMock(spec=list)
    tags = ["foo"]
    mt.__iter__.return_value = iter(tags)
    mt.__len__.return_value = len(tags)
    mt.add = MagicMock()
    mt.discard = MagicMock()
    type(m2).tags = PropertyMock(return_value=mt)
    m2.frozen = MagicMock()
    m2.frozen.__enter__.return_value = None
    m2.frozen.__exit__.return_value = False
    m2.ghost = False

    db = lambda: None
    db.messages = MagicMock(return_value=[m1, m2])
    db.remove = MagicMock()
    db.find = MagicMock(return_value=m2)

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    with patch("notmuch2.Database", return_value=mock_ctx):
        with patch("pathlib.Path.unlink") as pu:
            istream = io.BytesIO(b"\x00\x00\x00\x01\x00\x00\x00\x03bar")
            ostream = io.BytesIO()
            assert 0 == ns.sync_deletes_remote(istream, ostream)
            assert pu.call_count == 0

            out = ostream.getvalue()
            assert b"\x00\x00\x00\x02\x00\x00\x00\x03foo\x00\x00\x00\x03bar" == out

    db.messages.assert_called_once_with("*")
    db.find.assert_called_once_with("bar")
    assert db.remove.call_count == 0
    assert m2.filenames.call_count == 0
    mt.add.assert_called_once_with("foo")
    mt.discard.assert_called_once_with("foo")


def test_sync_deletes_remote_no_deleted_no_check():
    m1 = lambda: None
    m1.messageid = "foo"
    m2 = lambda: None
    m2.messageid = "bar"
    m2.filenames = MagicMock(return_value=["barfile"])
    m2.tags = ["foo"]
    m2.ghost = False

    db = lambda: None
    db.messages = MagicMock(return_value=[m1, m2])
    db.remove = MagicMock()
    db.find = MagicMock(return_value=m2)

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    with patch("notmuch2.Database", return_value=mock_ctx):
        with patch("pathlib.Path.unlink") as pu:
            istream = io.BytesIO(b"\x00\x00\x00\x01\x00\x00\x00\x03bar")
            ostream = io.BytesIO()
            assert 1 == ns.sync_deletes_remote(istream, ostream, no_check=True)
            pu.assert_called_once()

            out = ostream.getvalue()
            assert b"\x00\x00\x00\x02\x00\x00\x00\x03foo\x00\x00\x00\x03bar" == out

    db.messages.assert_called_once_with("*")
    db.find.assert_called_once_with("bar")
    db.remove.assert_called_once_with("barfile")
    m2.filenames.assert_called_once()


def test_sync_deletes_remote_ghost():
    m1 = lambda: None
    m1.messageid = "foo"
    m2 = lambda: None
    m2.messageid = "bar"
    m2.filenames = MagicMock(return_value=["barfile"])
    m2.ghost = True

    db = lambda: None
    db.messages = MagicMock(return_value=[m1, m2])
    db.remove = MagicMock()
    db.find = MagicMock(return_value=m2)

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    with patch("notmuch2.Database", return_value=mock_ctx):
        with patch("pathlib.Path.unlink") as pu:
            istream = io.BytesIO(b"\x00\x00\x00\x01\x00\x00\x00\x03bar")
            ostream = io.BytesIO()
            assert 0 == ns.sync_deletes_remote(istream, ostream)
            assert pu.call_count == 0

            out = ostream.getvalue()
            assert b"\x00\x00\x00\x02\x00\x00\x00\x03foo\x00\x00\x00\x03bar" == out

    db.messages.assert_called_once_with("*")
    db.find.assert_called_once_with("bar")
    assert db.remove.call_count == 0
    assert m2.filenames.call_count == 0


def test_sync_deletes_remote_none():
    m1 = lambda: None
    m1.messageid = "foo"
    m2 = lambda: None
    m2.messageid = "bar"

    db = lambda: None
    db.messages = MagicMock(return_value=[m1, m2])
    db.remove = MagicMock()

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    with patch("notmuch2.Database", return_value=mock_ctx):
        with patch("pathlib.Path.unlink") as pu:
            istream = io.BytesIO(b"\x00\x00\x00\x00")
            ostream = io.BytesIO()
            assert 0 == ns.sync_deletes_remote(istream, ostream)
            assert pu.call_count == 0

            out = ostream.getvalue()
            assert b"\x00\x00\x00\x02\x00\x00\x00\x03foo\x00\x00\x00\x03bar" == out

    db.messages.assert_called_once_with("*")
    assert db.remove.call_count == 0


def test_sync_mbsync_local_nothing():
    def effect(*args, **kwargs):
        yield []
        yield []

    with TemporaryDirectory() as _tmpdir:
        tmpdir = _tmpdir + os.sep
        with patch("pathlib.Path.rglob") as pr:
            pr.side_effect = effect()
            istream = io.BytesIO(b"\x00\x00\x00\x02{}")
            ostream = io.BytesIO()
            ns.sync_mbsync_local(tmpdir, istream, ostream)

            out = ostream.getvalue()
            assert b"\x00\x00\x00\x02[]\x00\x00\x00\x02[]" == out


def test_sync_mbsync_local():
    with TemporaryDirectory() as _tmpdir:
        tmpdir = _tmpdir + os.sep
        m1 = MagicMock()
        m1.__str__ = MagicMock(return_value=(tmpdir + ".uidvalidity"))
        s1 = lambda: None
        s1.st_mtime = 1
        m1.stat = MagicMock(return_value=s1)
        m2 = MagicMock()
        m2.__str__ = MagicMock(return_value=(tmpdir + ".mbsyncstate"))
        s2 = lambda: None
        s2.st_mtime = 0
        m2.stat = MagicMock(return_value=s2)

        def effect(*args, **kwargs):
            yield [m1]
            yield [m2]

        with patch("pathlib.Path.rglob") as pr:
            pr.side_effect = effect()
            istream = io.BytesIO(b"\x00\x00\x00\x23{\".uidvalidity\":0,\".mbsyncstate\":1}\x00\x00\x00\x01b")
            ostream = io.BytesIO()
            with patch("builtins.open", mock_open(read_data=b"a")) as o:
                ns.sync_mbsync_local(tmpdir, istream, ostream)
                assert call(tmpdir + ".uidvalidity", "rb") in o.mock_calls
                assert call(tmpdir + ".mbsyncstate", "wb") in o.mock_calls
                hdl = o()
                hdl.read.assert_called_once()
                hdl.write.assert_called_once()
                args = hdl.write.call_args.args
                assert b"b" == args[0]

            out = ostream.getvalue()
            assert b"\x00\x00\x00\x10[\".mbsyncstate\"]\x00\x00\x00\x10[\".uidvalidity\"]\x00\x00\x00\x01a" == out


def test_sync_mbsync_local_no_changes():
    with TemporaryDirectory() as _tmpdir:
        tmpdir = _tmpdir + os.sep
        m1 = MagicMock()
        m1.__str__ = MagicMock(return_value=(tmpdir + ".uidvalidity"))
        s1 = lambda: None
        s1.st_mtime = 1
        m1.stat = MagicMock(return_value=s1)
        m2 = MagicMock()
        m2.__str__ = MagicMock(return_value=(tmpdir + ".mbsyncstate"))
        s2 = lambda: None
        s2.st_mtime = 1
        m2.stat = MagicMock(return_value=s2)

        def effect(*args, **kwargs):
            yield [m1]
            yield [m2]

        with patch("pathlib.Path.rglob") as pr:
            pr.side_effect = effect()
            istream = io.BytesIO(b"\x00\x00\x00\x23{\".uidvalidity\":1,\".mbsyncstate\":1}")
            ostream = io.BytesIO()
            with patch("builtins.open", mock_open(read_data=b"a")) as o:
                ns.sync_mbsync_local(tmpdir, istream, ostream)
                assert o.call_count == 0

            out = ostream.getvalue()
            assert b"\x00\x00\x00\x02[]\x00\x00\x00\x02[]" == out


def test_sync_mbsync_local_missing():
    with TemporaryDirectory() as _tmpdir:
        tmpdir = _tmpdir + os.sep
        m1 = MagicMock()
        m1.__str__ = MagicMock(return_value=(tmpdir + ".uidvalidity"))
        s1 = lambda: None
        s1.st_mtime = 1
        m1.stat = MagicMock(return_value=s1)

        def effect(*args, **kwargs):
            yield [m1]
            yield []

        with patch("pathlib.Path.rglob") as pr:
            pr.side_effect = effect()
            istream = io.BytesIO(b"\x00\x00\x00\x12{\".mbsyncstate\":1}\x00\x00\x00\x01b")
            ostream = io.BytesIO()
            with patch("builtins.open", mock_open(read_data=b"a")) as o:
                ns.sync_mbsync_local(tmpdir, istream, ostream)
                assert call(tmpdir + ".uidvalidity", "rb") in o.mock_calls
                assert call(tmpdir + ".mbsyncstate", "wb") in o.mock_calls
                hdl = o()
                hdl.read.assert_called_once()
                hdl.write.assert_called_once()
                args = hdl.write.call_args.args
                assert b"b" == args[0]

            out = ostream.getvalue()
            assert b"\x00\x00\x00\x10[\".mbsyncstate\"]\x00\x00\x00\x10[\".uidvalidity\"]\x00\x00\x00\x01a" == out


def test_sync_mbsync_remote_nothing():
    def effect(*args, **kwargs):
        yield []
        yield []

    with TemporaryDirectory() as _tmpdir:
        tmpdir = _tmpdir + os.sep
        with patch("pathlib.Path.rglob") as pr:
            pr.side_effect = effect()
            istream = io.BytesIO(b"\x00\x00\x00\x02[]\x00\x00\x00\x02[]")
            ostream = io.BytesIO()
            ns.sync_mbsync_remote(tmpdir, istream, ostream)

            out = ostream.getvalue()
            assert b"\x00\x00\x00\x02{}" == out


def test_sync_mbsync_remote():
    with TemporaryDirectory() as _tmpdir:
        tmpdir = _tmpdir + os.sep
        m1 = MagicMock()
        m1.__str__ = MagicMock(return_value=(tmpdir + ".uidvalidity"))
        s1 = lambda: None
        s1.st_mtime = 0
        m1.stat = MagicMock(return_value=s1)
        m2 = MagicMock()
        m2.__str__ = MagicMock(return_value=(tmpdir + ".mbsyncstate"))
        s2 = lambda: None
        s2.st_mtime = 1
        m2.stat = MagicMock(return_value=s2)

        def effect(*args, **kwargs):
            yield [m1]
            yield [m2]

        with patch("pathlib.Path.rglob") as pr:
            pr.side_effect = effect()
            istream = io.BytesIO(b"\x00\x00\x00\x10[\".mbsyncstate\"]\x00\x00\x00\x10[\".uidvalidity\"]\x00\x00\x00\x01a")
            ostream = io.BytesIO()
            with patch("builtins.open", mock_open(read_data=b"b")) as o:
                ns.sync_mbsync_remote(tmpdir, istream, ostream)
                assert call(tmpdir + ".uidvalidity", "wb") in o.mock_calls
                assert call(tmpdir + ".mbsyncstate", "rb") in o.mock_calls
                hdl = o()
                hdl.read.assert_called_once()
                hdl.write.assert_called_once()
                args = hdl.write.call_args.args
                assert b"a" == args[0]

                out = ostream.getvalue()
                assert b"\x00\x00\x00\x26{\".uidvalidity\": 0, \".mbsyncstate\": 1}\x00\x00\x00\x01b" == out


def test_sync_mbsync_remote_no_changes():
    with TemporaryDirectory() as _tmpdir:
        tmpdir = _tmpdir + os.sep
        m1 = MagicMock()
        m1.__str__ = MagicMock(return_value=(tmpdir + ".uidvalidity"))
        s1 = lambda: None
        s1.st_mtime = 1
        m1.stat = MagicMock(return_value=s1)
        m2 = MagicMock()
        m2.__str__ = MagicMock(return_value=(tmpdir + ".mbsyncstate"))
        s2 = lambda: None
        s2.st_mtime = 1
        m2.stat = MagicMock(return_value=s2)

        def effect(*args, **kwargs):
            yield [m1]
            yield [m2]

        with patch("pathlib.Path.rglob") as pr:
            pr.side_effect = effect()
            istream = io.BytesIO(b"\x00\x00\x00\x02[]\x00\x00\x00\x02[]")
            ostream = io.BytesIO()
            with patch("builtins.open", mock_open(read_data=b"a")) as o:
                ns.sync_mbsync_remote(tmpdir, istream, ostream)
                assert o.call_count == 0

            out = ostream.getvalue()
            assert b"\x00\x00\x00\x26{\".uidvalidity\": 1, \".mbsyncstate\": 1}" == out


def test_sync_mbsync_remote_missing():
    with TemporaryDirectory() as _tmpdir:
        tmpdir = _tmpdir + os.sep
        m1 = MagicMock()
        m1.__str__ = MagicMock(return_value=(tmpdir + ".uidvalidity"))
        s1 = lambda: None
        s1.st_mtime = 1
        m1.stat = MagicMock(return_value=s1)

        def effect(*args, **kwargs):
            yield [m1]
            yield []

        with patch("pathlib.Path.rglob") as pr:
            pr.side_effect = effect()
            istream = io.BytesIO(b"\x00\x00\x00\x10[\".mbsyncstate\"]\x00\x00\x00\x10[\".uidvalidity\"]\x00\x00\x00\x01b")
            ostream = io.BytesIO()
            with patch("builtins.open", mock_open(read_data=b"a")) as o:
                ns.sync_mbsync_remote(tmpdir, istream, ostream)
                assert call(tmpdir + ".uidvalidity", "wb") in o.mock_calls
                assert call(tmpdir + ".mbsyncstate", "rb") in o.mock_calls
                hdl = o()
                hdl.read.assert_called_once()
                hdl.write.assert_called_once()
                args = hdl.write.call_args.args
                assert b"b" == args[0]

            out = ostream.getvalue()
            assert b"\x00\x00\x00\x13{\".uidvalidity\": 1}\x00\x00\x00\x01a" == out


def test_digest():
    assert "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae" == ns.digest(b"foo")
    assert "578f2f7c0b2e8ea5be4c8d245b07dec37c62ce4644fadb2a5c23839b39d6c260" == ns.digest(b"foo\nbar\nfoobar")
    assert "578f2f7c0b2e8ea5be4c8d245b07dec37c62ce4644fadb2a5c23839b39d6c260" == ns.digest(b"foo\nbar\nX-TUID: bla\nfoobar")
    assert "578f2f7c0b2e8ea5be4c8d245b07dec37c62ce4644fadb2a5c23839b39d6c260" == ns.digest(b"foo\nbar\nX-TUID: blarg\nfoobar")
