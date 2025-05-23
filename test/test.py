import pytest
import os
import sys
import io
from unittest.mock import MagicMock, mock_open, patch
from tempfile import NamedTemporaryFile

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
    mm.filenames = MagicMock(return_value=["/foo/bar", "/foo/foo"])

    db = lambda: None
    rev = lambda: None
    rev.rev = 124
    rev.uuid = b'abc'
    db.revision = MagicMock(return_value=rev)
    db.default_path = MagicMock(return_value='/foo')
    db.messages = MagicMock(return_value=[mm])

    with NamedTemporaryFile(mode="w+t", prefix="notmuch-sync-test-tmp-") as f:
        f.write("123 abc")
        f.flush()
        changes = ns.get_changes(db, f.name)
        assert changes == {"foo": {"tags": ["foo", "bar"], "files": ["bar", "foo"]}}

    db.revision.assert_called_once()
    db.default_path.assert_called_once()
    db.messages.assert_called_once_with("lastmod:123..")


def test_changes_first_sync():
    mm = lambda: None
    mm.messageid = "foo"
    mm.tags = ["foo", "bar"]
    mm.filenames = MagicMock(return_value=["/foo/bar", "/foo/foo"])

    db = lambda: None
    rev = lambda: None
    db.default_path = MagicMock(return_value='/foo')
    db.messages = MagicMock(return_value=[mm])

    f = NamedTemporaryFile(mode="r", prefix="notmuch-sync-test-tmp-")
    f.close()
    changes = ns.get_changes(db, f.name)
    assert changes == {"foo": {"tags": ["foo", "bar"], "files": ["bar", "foo"]}}

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


def test_sync_tags_empty():
    db = lambda: None
    db.config = {}
    ns.sync_tags(db, {}, {})


def test_sync_server(monkeypatch):
    args = lambda: None
    args.remote = "host"

    db = lambda: None
    rev = lambda: None
    rev.rev = 124
    rev.uuid = b'abd'
    db.revision = MagicMock(return_value=rev)
    db.default_path = MagicMock(return_value='/foo')
    db.config = {}

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
    db.config = {}

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
