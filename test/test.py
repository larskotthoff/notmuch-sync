import pytest
from unittest.mock import MagicMock
from tempfile import NamedTemporaryFile

import notmuch2

import importlib  
ns = importlib.import_module("src.notmuch-sync")

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
        assert changes == [{"id": "foo", "tags": ["foo", "bar"], "files": ["bar", "foo"]}]

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
    assert changes == [{"id": "foo", "tags": ["foo", "bar"], "files": ["bar", "foo"]}]

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
