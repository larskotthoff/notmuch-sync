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
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            ns.get_changes(db, f.name)
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == "Last sync with UUID abc, but notmuch DB has UUID abd, aborting..."

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
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            ns.get_changes(db, f.name)
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == "Last sync revision 123 larger than current DB revision 122, aborting..."

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
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            ns.get_changes(db, f.name)
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == f"Sync state file {f.name} corrupted, delete to sync from scratch."

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


def test_sync_files_updated():
    m = MagicMock()
    m.filenames = MagicMock(return_value=['/foo/bar'])
    db = lambda: None
    db.default_path = MagicMock(return_value='/foo')

    db.find = MagicMock(return_value=m)

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    changes = {"foo": {"tags": ["foo"], "files": [{"name": "foo", "sha": "abc"}]}}

    with patch("notmuch2.Database", return_value=mock_ctx):
        exp = {"foo": {"type": "add",
                       "files": [{"name": "foo", "sha": "abc"}]}}
        assert exp == ns.get_missing_files(changes)

    db.default_path.assert_called_once()
    db.find.assert_called_once_with("foo")
    m.filenames.assert_called_once()


def test_sync_files_updated_some():
    m = MagicMock()
    m.filenames = MagicMock(return_value=['/foo/bar'])
    db = lambda: None
    db.default_path = MagicMock(return_value='/foo')

    db.find = MagicMock(return_value=m)

    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db
    mock_ctx.__exit__.return_value = False

    changes = {"foo": {"tags": ["foo"], "files": [{"name": "bar", "sha": "abc"},
                                                  {"name": "foo", "sha": "def"}]}}

    with patch("notmuch2.Database", return_value=mock_ctx):
        exp = {"foo": {"type": "add",
                       "files": [{"name": "foo", "sha": "def"}]}}
        assert exp == ns.get_missing_files(changes)

    db.default_path.assert_called_once()
    db.find.assert_called_once_with("foo")
    m.filenames.assert_called_once()
