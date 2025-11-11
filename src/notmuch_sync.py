#!/usr/bin/env python3

"""notmuch_sync: Synchronize notmuch email databases and message files between
local and remote systems."""

import argparse
import asyncio
import hashlib
import json
import logging
import os
import shlex
import shutil
import struct
import subprocess
import sys

from typing import Any, Dict, List, Tuple, Callable, IO

from pathlib import Path
from select import select

import notmuch2
import xapian

logging.basicConfig(format="[{asctime}] {message}", style="{")
logger = logging.getLogger(__name__)

transfer = {"read": 0, "write": 0}

def digest(data: bytes) -> str:
    """
    Compute SHA256 digest of data, removing any X-TUID: lines. This is
    nececessary because mbsync adds these lines to keep track of internal
    progress, but they make identical emails that were retrieved separately
    different.

    Args:
        data (bytes): The data to compute the checsum for.

    Returns:
        The computed checksum.
    """
    pat = b"X-TUID: "
    to_digest = data
    start_idx = data.find(pat)
    if start_idx != -1:
        search_start = start_idx + len(pat)
        end_idx = data.find(b"\n", search_start)

        if end_idx != -1:
            to_digest = data[:start_idx] + data[end_idx + 1:]

    return hashlib.new("sha256", to_digest).hexdigest()


def write(data: bytes, stream: IO[bytes] | None) -> None:
    """
    Write data to a stream with a 4-byte length prefix.

    Args:
        data (bytes): The data to write.
        stream: A writable stream supporting .write() and .flush().
    """
    if stream is None:
        return
    stream.write(struct.pack("!I", len(data)))
    transfer["write"] += 4
    written = stream.write(data)
    if written < len(data):
        raise ValueError(f"Tried to write {len(data)} bytes, but wrote only {written}, aborting...")
    transfer["write"] += len(data)
    stream.flush()


def read(stream: IO[bytes] | None) -> bytes:
    """
    Read 4-byte length-prefixed data from a stream.

    Args:
        stream: A readable stream supporting .read().

    Returns:
        bytes: The data read from the stream.
    """
    if stream is None:
        return b''
    size_data = stream.read(4)
    transfer["read"] += 4
    size = struct.unpack("!I", size_data)[0]
    data = stream.read(size)
    if len(data) < size:
        raise ValueError(f"Tried to read {size} bytes, but read only {len(data)}, aborting...")
    transfer["read"] += size
    return data


def run_async(m1: Callable[[], Any], m2: Callable[[], Any]) -> None:
    """
    Run two functions async. Used to read/write to streams at the same time.

    Args:
        m1: One function.
        m2: Other function.
    """
    async def _tmp():
        await asyncio.gather(asyncio.to_thread(m1), asyncio.to_thread(m2))

    asyncio.run(_tmp())


def get_changes(
    db: notmuch2.Database,
    revision: notmuch2.DbRevision,
    prefix: str,
    sync_file: str
) -> Dict[str, Dict[str, Any]]:
    """
    Get changes that happened since the last sync, or everything in the DB if no previous sync.

    Args:
        db: An open notmuch2.Database object.
        revision: Database revision object, must have .uuid and .rev.
        prefix (str): Prefix path for filenames (notmuch config database.path).
        sync_file (str): Path to the file storing the sync state.

    Returns:
        dict: Mapping of message IDs to their tags and files.
    """
    rev_prev = -1
    try:
        with open(sync_file, 'r', encoding="utf-8") as f:
            tmp = f.read().strip('\n\r').split(' ')
            uuid = revision.uuid.decode()
            try:
                if tmp[1] != uuid:
                    raise ValueError(f"Last sync with UUID {tmp[1]}, but notmuch DB has UUID {uuid}, aborting...")
                rev_prev = int(tmp[0])
                if rev_prev > revision.rev:
                    raise ValueError(f"Last sync revision {rev_prev} larger than current DB revision {revision.rev}, aborting...")
            except (AttributeError, IndexError, UnicodeError) as e:
                raise ValueError(f"Sync state file '{sync_file}' corrupted, delete to sync from scratch.") from e
    except FileNotFoundError:
        # no previous sync or sync file broken, leave rev_prev at -1 as this will sync entire DB
        pass

    logger.info("Previous sync revision %s, current revision %s.", rev_prev, revision.rev)
    return {msg.messageid: {"tags": list(msg.tags),
                            "files": [str(f).removeprefix(prefix) for f in msg.filenames()]}
                            for msg in db.messages(f"lastmod:{rev_prev + 1}..")}


def sync_tags(
    db: notmuch2.Database,
    changes_mine: Dict[str, Dict[str, Any]],
    changes_theirs: Dict[str, Dict[str, Any]]
) -> int:
    """
    Synchronize tags between local and remote changes. Applies tags from all
    remotely changed IDs to local messages with the same ID, overwriting any
    local tags. If an ID appears both in remote and local changes, take the
    union of all tags. If a message is not found locally, do nothing (will be
    synced later).

    Args:
        db: An open notmuch2.Database object.
        changes_mine (dict): Local changes, mapping message IDs to tags.
        changes_theirs (dict): Remote changes, mapping message IDs to tags.

    Returns:
        int: Number of tag changes made.
    """
    changes = 0
    for mid in changes_theirs:
        tags = changes_theirs[mid]["tags"]
        if mid in changes_mine:
            tags = set(tags) | set(changes_mine[mid]["tags"])
        tags = set(tags)
        try:
            msg = db.find(mid)
            if msg.ghost:
                continue
            if tags != set(msg.tags):
                logger.info("Setting tags %s for %s.", sorted(list(tags)), mid)
                with msg.frozen():
                    changes += 1
                    msg.tags.clear()
                    for tag in sorted(list(tags)):
                        msg.tags.add(tag)
                    msg.tags.to_maildir_flags()
        except LookupError:
            # we don't have this message on our side, it will be added later
            # when syncing files
            pass

    return changes


def record_sync(fname: str, revision: notmuch2.DbRevision) -> None:
    """
    Record last sync revision.

    Args:
        fname: File to write to.
        revision: Revision/UUID to record.
    """
    with open(fname, 'w', encoding="utf-8") as f:
        logger.info("Writing last sync revision %s.", revision.rev)
        f.write(f"{revision.rev} {revision.uuid.decode()}")


def initial_sync(
    dbw: notmuch2.Database,
    prefix: str,
    from_stream: IO[bytes] | None,
    to_stream: IO[bytes] | None
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]], int, str]:
    """
    Perform the initial synchronization of UUIDs and tag changes, which includes
    applying any remote tag changes to messages that exist locally. UUIDs and
    changes are communicated to/from the remote over the respective streams.

    Args:
        dbw: An open writable notmuch2.Database object.
        prefix (str): Prefix path for filenames (notmuch config database.path).
        from_stream: Stream to read from the remote.
        to_stream: Stream to write to the remote.

    Returns:
        tuple: (local changes dict, remote changes dict, number of tag changes,
                name of sync file)
    """
    revision = dbw.revision()
    uuids = {}
    uuids["mine"] = revision.uuid.decode()

    def _send_uuid():
        logger.info("Sending UUID %s...", uuids["mine"])
        to_stream.write(uuids["mine"].encode("utf-8"))
        transfer["write"] += 36
        to_stream.flush()

    def _recv_uuid():
        logger.info("Receiving UUID...")
        uuids["theirs"] = from_stream.read(36).decode("utf-8")
        transfer["read"] += 36

    run_async(_send_uuid, _recv_uuid)

    logger.info("UUIDs synced.")
    logger.debug("Local UUID %s, remote UUID %s.", uuids["mine"], uuids["theirs"])
    fname = os.path.join(prefix, ".notmuch", "notmuch-sync-" + uuids["theirs"])

    changes = {}
    logger.info("Computing local changes...")
    changes["mine"] = get_changes(dbw, revision, prefix, fname)

    def _send_changes():
        logger.info("Sending local changes...")
        write(json.dumps(changes["mine"]).encode("utf-8"), to_stream)

    def _recv_changes():
        logger.info("Receiving remote changes...")
        changes["theirs"] = json.loads(read(from_stream).decode("utf-8"))

    run_async(_send_changes, _recv_changes)

    logger.info("Changes synced.")
    logger.debug("Local changes %s, remote changes %s.", changes["mine"], changes["theirs"])
    tchanges = sync_tags(dbw, changes["mine"], changes["theirs"])
    logger.info("Tags synced.")

    return (changes["mine"], changes["theirs"], tchanges, fname)


def get_missing_files(
    dbw: notmuch2.Database,
    prefix: str,
    changes_mine: Dict[str, Dict[str, Any]],
    changes_theirs: Dict[str, Dict[str, Any]],
    from_stream: IO[bytes] | None,
    to_stream: IO[bytes] | None,
    move_on_change: bool = False
) -> Tuple[Dict[str, Dict[str, Any]], int, int]:
    """
    Determine which files are missing locally compared to the remote, and handle
    file moves/copies based on SHA256 checksums. Delete any files that aren't
    there on the remote anymore. This never deletes a message, only duplicate
    files for a message.

    Args:
        dbw: An open writable notmuch2.Database object.
        prefix (str): Prefix path for filenames (notmuch config database.path).
        changes_mine (dict): Local changes.
        changes_theirs (dict): Remote changes.
        from_stream: Stream to read from the remote.
        to_stream: Stream to write to the remote.
        move_on_change: Whether to move file that has local and remote changes.
        This flag is used to prevent infinite loops where local has one file
        name and remote another file name (e.g. when running mbsync independently).

    Returns:
        tuple: (dict of missing files, number of local moves/copies, number of
                local deletions)
    """
    ret = {}
    mcchanges = 0
    dchanges = 0
    hashes: dict[str, List[str]] = {}
    # check which files we need to get digests for to determine if they've
    # been moved/copied
    hashes["req_mine"] = []
    for mid in changes_theirs:
        try:
            msg = dbw.find(mid)
            if msg.ghost:
                continue
            fnames_theirs = changes_theirs[mid]["files"]
            fnames_mine = [ str(f).removeprefix(prefix) for f in msg.filenames() ]
            missing_mine = set(fnames_theirs) - set(fnames_mine)
            if len(missing_mine) > 0:
                hashes["req_mine"].extend(fnames_theirs)
        except LookupError:
            continue

    def _send_hashes_req():
        logger.info("Requesting %s hashes from remote...", len(hashes["req_mine"]))
        logger.debug("Requesting hashes %s", hashes["req_mine"])
        write(json.dumps(hashes["req_mine"]).encode("utf-8"), to_stream)

    def _recv_hashes_req():
        logger.info("Receiving hash requests from remote...")
        hashes["req_theirs"] = json.loads(read(from_stream).decode("utf-8"))
        logger.debug("Hashes requested by remote %s", hashes["req_theirs"])

    run_async(_send_hashes_req, _recv_hashes_req)

    def _send_hashes():
        logger.info("Hashing %s requested files and sending to remote...",
                    len(hashes["req_theirs"]))
        tmp = [digest(Path(os.path.join(prefix, f)).read_bytes()) for f in hashes["req_theirs"]]
        write(json.dumps(tmp).encode("utf-8"), to_stream)

    def _recv_hashes():
        logger.info("Receiving hashes from remote...")
        tmp = json.loads(read(from_stream).decode("utf-8"))
        hashes["theirs"] = dict(zip(hashes["req_mine"], tmp))

    run_async(_send_hashes, _recv_hashes)

    # now actually determine changes and move/copy
    for mid in changes_theirs:
        try:
            msg = dbw.find(mid)
            if msg.ghost:
                ret[mid] = changes_theirs[mid]
                continue
            fnames_theirs = changes_theirs[mid]["files"]
            fnames_mine = [ str(f).removeprefix(prefix) for f in msg.filenames() ]
            missing_mine = set(fnames_theirs) - set(fnames_mine)
            if len(missing_mine) > 0:
                hashes_mine = {str(f).removeprefix(prefix): digest(Path(f).read_bytes()) for f in msg.filenames()}
                for f in changes_theirs[mid]["files"]:
                    if f in missing_mine:
                        # check if it has been moved/copied
                        matches = [x[0] for x in hashes_mine.items() if hashes["theirs"][f] == x[1]]
                        if len(matches) > 0:
                            src = os.path.join(prefix, matches[0])
                            dst = os.path.join(prefix, f)
                            if matches[0] in changes_theirs[mid]["files"]:
                                mcchanges += 1
                                logger.info("Copying %s to %s.", src, dst)
                                Path(dst).parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy(src, dst)
                                fnames_mine.append(f)
                                dbw.add(dst)
                            elif mid not in changes_mine or move_on_change:
                                mcchanges += 1
                                logger.info("Moving %s to %s.", src, dst)
                                Path(dst).parent.mkdir(parents=True, exist_ok=True)
                                shutil.move(src, dst)
                                fnames_mine.append(f)
                                fnames_mine.remove(matches[0])
                                hashes_mine[f] = hashes_mine[matches[0]]
                                del hashes_mine[matches[0]]
                                dbw.add(dst)
                                logger.info("Removing %s from DB.", src)
                                dbw.remove(src)
                            missing_mine.remove(f)
            # check which ones are still missing
            if len(missing_mine) > 0:
                ret[mid] = {"files": [f for f in changes_theirs[mid]["files"] if f in missing_mine]}

            # delete any files that are not there remotely after copy/move
            if mid not in changes_mine:
                if len(set(fnames_mine).intersection(fnames_theirs)) == 0:
                    raise ValueError(f"Message '{mid}' has {fnames_theirs} on remote and different {fnames_mine} locally!")
                to_delete = set(fnames_mine) - set(fnames_theirs)
                for f in to_delete:
                    fname = os.path.join(prefix, f)
                    dchanges += 1
                    logger.info("Removing %s from DB and deleting file.", fname)
                    dbw.remove(fname)
                    Path(fname).unlink()
        except LookupError:
            # don't have this message; all files missing
            ret[mid] = changes_theirs[mid]

    return (ret, mcchanges, dchanges)


def send_file(fname: str, stream: IO[bytes]) -> None:
    """
    Send a file's contents to a stream with 4-byte length prefix.

    Args:
        fname (str): Path to the file to send.
        stream: Writable stream.
    """
    with open(fname, "rb") as f:
        write(f.read(), stream)


def recv_file(
    fname: str,
    stream: IO[bytes],
    overwrite_raise: bool=True
) -> None:
    """
    Receive a file with a 4-byte length prefix from a stream and write it to
    disk, validating its checksum.

    Args:
        fname (str): Destination file path.
        stream: Readable stream.
        overwrite_raise: Raise error if existing file would be overwritten.

    Raises:
        ValueError: If file to receive already exists or received file's
        checksum does not match expected.
    """
    content = read(stream)
    if Path(fname).exists() and overwrite_raise:
        sha_mine = digest(content)
        sha_exists = digest(Path(fname).read_bytes())
        if sha_exists != sha_mine:
            raise ValueError(f"Receiving '{fname}', but already exists with different content!")
    Path(fname).parent.mkdir(parents=True, exist_ok=True)
    with open(fname, "wb") as f:
        f.write(content)


def sync_files(
    dbw: notmuch2.Database,
    prefix: str,
    missing: Dict[str, Dict[str, Any]],
    from_stream: IO[bytes] | None,
    to_stream: IO[bytes] | None
) -> Tuple[int, int]:
    """
    Synchronize files that are missing locally or remotely.

    Args:
        dbw: An open writable notmuch2.Database object.
        prefix (str): Prefix path for filenames (notmuch config database.path).
        missing (dict): Mapping of missing files by message ID.
        from_stream: Stream to read file names and files from.
        to_stream: Stream to send file names and files to.

    Returns:
        tuple: (number of added messages, number of added files)
    """
    files = {}
    files["mine"] = [ {"name": f, "id": mid} for mid in missing for f in missing[mid]["files"] ]
    changes = {"files": len(files["mine"]), "messages": 0}

    def _send_fnames():
        logger.info("Sending file names missing on local...")
        write(json.dumps([f["name"] for f in files["mine"]]).encode("utf-8"), to_stream)

    def _recv_fnames():
        logger.info("Receiving file names missing on remote...")
        files["theirs"] = json.loads(read(from_stream).decode("utf-8"))

    run_async(_send_fnames, _recv_fnames)

    logger.info("Missing file names synced.")

    def _send_files():
        for idx, fname in enumerate(files["theirs"]):
            logger.info("%s/%s Sending %s...", idx + 1, len(files["theirs"]),
                        fname)
            send_file(os.path.join(prefix, fname), to_stream)

    def _recv_files():
        for idx, f in enumerate(files["mine"]):
            logger.info("%s/%s Receiving %s...", idx + 1, len(files["mine"]), f["name"])
            dst = os.path.join(prefix, f["name"])
            recv_file(dst, from_stream)

        for idx, f in enumerate(files["mine"]):
            dst = os.path.join(prefix, f["name"])
            logger.info("Adding %s to DB.", dst)
            msg, dup = dbw.add(dst)
            if not dup:
                changes["messages"] += 1
                with msg.frozen():
                    logger.info("Setting tags %s for received %s.",
                                sorted(missing[f["id"]]["tags"]),
                                msg.messageid)
                    msg.tags.clear()
                    for tag in missing[f["id"]]["tags"]:
                        msg.tags.add(tag)

    run_async(_send_files, _recv_files)

    logger.info("Missing files synced.")

    return (changes["messages"], changes["files"])


def get_ids(prefix: str) -> List[str]:
    """
    Get all message IDs from the notmuch database, using Xapian directly (much
    faster).

    Args:
        prefix (str): Prefix path for filenames (notmuch config database.path).

    Returns:
        list: All message IDs.
    """
    db = xapian.Database(os.path.join(prefix, ".notmuch", "xapian"))
    message_ids = []

    logger.info("Getting all message IDs from DB...")
    ghosts = {p.docid for p in db.postlist("Tghost")} # type: ignore[attr-defined]
    all_docs = set(range(1, db.get_lastdocid() + 1))
    for doc_id in all_docs - ghosts:
        try:
            doc = db.get_document(doc_id)
            value = doc.get_value(1)
            if value:
                message_ids.append(value.decode("utf-8"))
        except xapian.DocNotFoundError:
            pass
        except RuntimeError:
            # not entirely sure why, but this seems to happen sometimes
            continue

    db.close()

    return message_ids


# Separate methods for local and remote to avoid sending all IDs both ways --
# have local figure out what needs to be deleted on both sides
def sync_deletes_local(
    prefix: str,
    from_stream: IO[bytes] | None,
    to_stream: IO[bytes] | None,
    no_check: bool = False
) -> int:
    """
    Synchronize deletions for the local database and instruct remote to delete
    messages/files as needed.

    Args:
        prefix (str): Prefix path for filenames (notmuch config database.path).
        from_stream: Stream to read from the remote.
        to_stream: Stream to write to the remote.
        no_check: Delete message not present on other side even if it doesn't
        have the 'deleted' tag.

    Returns:
        int: Number of deletions performed.
    """
    ids = {}
    dels = {'a': 0}

    def _get_ids():
        ids["mine"] = get_ids(prefix)

    def _recv_ids():
        logger.info("Receiving all message IDs from remote...")
        ids["theirs"] = json.loads(read(from_stream).decode("utf-8"))

    run_async(_get_ids, _recv_ids)

    logger.info("Message IDs synced.")

    def _send_del_ids():
        to_del_remote = list(set(ids["theirs"]) - set(ids["mine"]))
        logger.debug("Remote IDs to be deleted %s.", to_del_remote)
        logger.info("Sending message IDs to be deleted to remote...")
        write(json.dumps(to_del_remote).encode("utf-8"), to_stream)

    def _recv_del_ids():
        to_del = set(ids["mine"]) - set(ids["theirs"])
        logger.debug("Local IDs to be deleted %s.", to_del)
        with notmuch2.Database(mode=notmuch2.Database.MODE.READ_WRITE) as dbw:
            for mid in to_del:
                try:
                    msg = dbw.find(mid)
                    if msg.ghost:
                        continue
                    if "deleted" in msg.tags or no_check:
                        dels["a"] += 1
                        logger.info("Removing %s from DB and deleting files.", mid)
                        for f in msg.filenames():
                            logger.debug("Removing %s.", f)
                            dbw.remove(f)
                            Path(f).unlink()
                    else:
                        # not there on remote, but no "deleted" tag -- assume
                        # that something went wrong and set tags again to make
                        # it show up in next changeset to be synced back to
                        # remote
                        logger.info("%s set to be removed, but not tagged 'deleted'!", mid)
                        with msg.frozen():
                            tmp = "".join(msg.tags)
                            msg.tags.add(tmp)
                            msg.tags.discard(tmp)
                except LookupError:
                    # already deleted? doesn't matter
                    pass

    run_async(_send_del_ids, _recv_del_ids)

    return dels["a"]


def sync_deletes_remote(
    prefix: str,
    from_stream: IO[bytes] | None,
    to_stream: IO[bytes] | None,
    no_check: bool = False
) -> int:
    """
    Receive instructions from local to delete messages/files from the remote database.

    Args:
        prefix (str): Prefix path for filenames (notmuch config database.path).
        from_stream: Stream to read from the local.
        to_stream: Stream to write to the local.
        no_check: Delete message not present on other side even if it doesn't
        have the 'deleted' tag.

    Returns:
        int: Number of deletions performed.
    """
    dels = 0
    ids = get_ids(prefix)
    write(json.dumps(ids).encode("utf-8"), to_stream)

    to_del = json.loads(read(from_stream).decode("utf-8"))
    with notmuch2.Database(mode=notmuch2.Database.MODE.READ_WRITE) as dbw:
        for mid in to_del:
            try:
                msg = dbw.find(mid)
                if msg.ghost:
                    continue
                if "deleted" in msg.tags or no_check:
                    dels += 1
                    for f in msg.filenames():
                        dbw.remove(f)
                        Path(f).unlink()
                else:
                    # not on local, but no "deleted" tag -- assume that
                    # something went wrong and set tags again to make it
                    # show up in next changeset to be synced back to local
                    with msg.frozen():
                        tmp = "".join(msg.tags)
                        msg.tags.add(tmp)
                        msg.tags.discard(tmp)
            except LookupError:
                # already deleted? doesn't matter
                pass
    return dels


def sync_mbsync_local(
    prefix: str,
    from_stream: IO[bytes] | None,
    to_stream: IO[bytes] | None
) -> None:
    """
    Synchronize local mbsync files with remote.

    Args:
        prefix (str): Prefix path for filenames (notmuch config database.path).
        from_stream: Stream to read from the remote.
        to_stream: Stream to write to the remote.
    """
    mbsync = {}

    def _get_mbsync():
        logger.info("Getting local mbsync file stats...")
        mbsync["mine"] = { str(f).removeprefix(prefix): f.stat().st_mtime
                           for pat in [".uidvalidity", ".mbsyncstate"]
                           for f in Path(prefix).rglob(pat) }

    def _recv_mbsync():
        logger.info("Receiving mbsync file stats from remote...")
        mbsync["theirs"] = json.loads(read(from_stream).decode("utf-8"))

    run_async(_get_mbsync, _recv_mbsync)

    logger.info("mbsync file stats synced.")

    pull = [ f for f in mbsync["mine"].keys()
            if (f in mbsync["theirs"] and mbsync["theirs"][f] > mbsync["mine"][f]) ]
    pull += list(set(mbsync["theirs"].keys()) - set(mbsync["mine"].keys()))
    logger.debug("Local mbsync files to be updated from remote %s.", pull)
    write(json.dumps(pull).encode("utf-8"), to_stream)

    def _send_mbsync_files():
        push = [ f for f in mbsync["theirs"].keys()
                if (f in mbsync["mine"] and mbsync["mine"][f] > mbsync["theirs"][f]) ]
        push += list(set(mbsync["mine"].keys()) - set(mbsync["theirs"].keys()))

        logger.debug("mbsync files to update on remote %s.", push)
        logger.info("Sending %s mbsync files to remote...", len(push))
        write(json.dumps(push).encode("utf-8"), to_stream)
        for idx, f in enumerate(push):
            logger.debug("%s/%s Sending mbsync file %s to remote...", idx + 1,
                         len(push), f)
            to_stream.write(struct.pack("!d", mbsync["mine"][f]))
            to_stream.flush()
            transfer["write"] += 8
            send_file(os.path.join(prefix, f), to_stream)

    def _recv_mbsync_files():
        logger.info("Receiving %s mbsync files from remote...", len(pull))
        for idx, f in enumerate(pull):
            logger.debug("%s/%s Receiving mbsync file %s from remote...",
                         idx + 1, len(pull), f)
            mtime_data = from_stream.read(8)
            transfer["read"] += 8
            mtime = struct.unpack("!d", mtime_data)[0]
            fname = os.path.join(prefix, f)
            recv_file(fname, from_stream, overwrite_raise=False)
            os.utime(fname, (mtime, mtime))

    run_async(_send_mbsync_files, _recv_mbsync_files)

    logger.info("mbsync files synced.")


def sync_mbsync_remote(
    prefix: str,
    from_stream: IO[bytes] | None,
    to_stream: IO[bytes] | None
) -> None:
    """
    Synchronize remote mbsync files with local.

    Args:
        prefix (str): Prefix path for filenames (notmuch config database.path).
        from_stream: Stream to read from the remote.
        to_stream: Stream to write to the remote.
    """
    mbsync = { str(f).removeprefix(prefix): f.stat().st_mtime
               for pat in [".uidvalidity", ".mbsyncstate"]
               for f in Path(prefix).rglob(pat) }
    write(json.dumps(mbsync).encode("utf-8"), to_stream)
    push = json.loads(read(from_stream).decode("utf-8"))

    def _send_mbsync_files():
        for f in push:
            fname = os.path.join(prefix, f)
            to_stream.write(struct.pack("!d", Path(fname).stat().st_mtime))
            to_stream.flush()
            transfer["write"] += 8
            send_file(fname, to_stream)

    def _recv_mbsync_files():
        pull = json.loads(read(from_stream).decode("utf-8"))
        for f in pull:
            mtime_data = from_stream.read(8)
            transfer["read"] += 8
            mtime = struct.unpack("!d", mtime_data)[0]
            fname = os.path.join(prefix, f)
            recv_file(fname, from_stream, overwrite_raise=False)
            os.utime(fname, (mtime, mtime))

    run_async(_send_mbsync_files, _recv_mbsync_files)


def sync_remote(args: argparse.Namespace) -> None:
    """
    Run synchronization in remote mode.

    Args:
        args: Parsed command-line arguments.
    """
    with notmuch2.Database(mode=notmuch2.Database.MODE.READ_WRITE) as dbw:
        prefix = os.path.join(str(dbw.default_path()), '')
        changes_mine, changes_theirs, tchanges, sync_fname = initial_sync(dbw, prefix, sys.stdin.buffer, sys.stdout.buffer)
        missing, fchanges, dfchanges = get_missing_files(dbw, prefix, changes_mine, changes_theirs, sys.stdin.buffer, sys.stdout.buffer, move_on_change=False)
        rmessages, rfiles = sync_files(dbw, prefix, missing, sys.stdin.buffer, sys.stdout.buffer)
        record_sync(sync_fname, dbw.revision())

    dchanges = 0
    if args.delete:
        dchanges = sync_deletes_remote(prefix, sys.stdin.buffer, sys.stdout.buffer, args.delete_no_check)
    if args.mbsync:
        sync_mbsync_remote(prefix, sys.stdin.buffer, sys.stdout.buffer)
    sys.stdout.buffer.write(struct.pack("!IIIIII", tchanges, fchanges, dfchanges,
                                        rmessages, dchanges, rfiles))
    sys.stdout.buffer.flush()


def sync_local(args: argparse.Namespace) -> None:
    """
    Run synchronization in local mode, communicating with the remote over SSH or
    a custom command.

    Args:
        args: Parsed command-line arguments.
    """
    if args.remote_cmd:
        cmd = shlex.split(args.remote_cmd)
    else:
        rargs = [(f"{args.user}@" if args.user else "") + args.remote, f"{args.path}"]
        if args.delete:
            rargs.append("--delete")
        if args.delete_no_check:
            rargs.append("--delete-no-check")
        if args.mbsync:
            rargs.append("--mbsync")
        cmd = shlex.split(args.ssh_cmd) + rargs

    logger.info("Connecting to remote...")
    logger.debug("Command to connect to remote: %s", cmd)

    with subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            ) as proc:
        to_remote = proc.stdin
        from_remote = proc.stdout
        err_remote = proc.stderr

        data = b''
        try:
            with notmuch2.Database(mode=notmuch2.Database.MODE.READ_WRITE) as dbw:
                prefix = os.path.join(str(dbw.default_path()), '')
                changes_mine, changes_theirs, tchanges, sync_fname = initial_sync(dbw, prefix, from_remote, to_remote)
                missing, fchanges, dfchanges = get_missing_files(dbw, prefix, changes_mine, changes_theirs, from_remote, to_remote, move_on_change=True)
                logger.debug("Missing files %s.", missing)
                rmessages, rfiles = sync_files(dbw, prefix, missing, from_remote, to_remote)
                record_sync(sync_fname, dbw.revision())

            dchanges = 0
            if args.delete:
                dchanges = sync_deletes_local(prefix, from_remote, to_remote, args.delete_no_check)
            if args.mbsync:
                sync_mbsync_local(prefix, from_remote, to_remote)

            logger.info("Getting change numbers from remote...")
            if from_remote is not None:
                remote_changes = struct.unpack("!IIIIII", from_remote.read(6 * 4))
                transfer["read"] += 6 * 4
            else:
                remote_changes = (0,0,0,0,0,0)
        finally:
            ready, _, exc = select([err_remote], [], [], 0)
            if err_remote is not None and ready and not exc:
                data = err_remote.read()
                # getting zero data on EOF
                if len(data) > 0:
                    logger.error("Remote error: %s", data)

            if to_remote is not None:
                to_remote.close()
            if from_remote is not None:
                from_remote.close()
            if err_remote is not None:
                err_remote.close()

    logger.warning("local:  %s new messages,\t%s new files,\t%s files copied/moved,\t%s files deleted,\t%s messages with tag changes,\t%s messages deleted", rmessages, rfiles, fchanges, dfchanges, tchanges, dchanges)
    logger.warning("remote: %s new messages,\t%s new files,\t%s files copied/moved,\t%s files deleted,\t%s messages with tag changes,\t%s messages deleted", remote_changes[3], remote_changes[5], remote_changes[1], remote_changes[2], remote_changes[0], remote_changes[4])
    logger.warning("%s/%s bytes received from/sent to remote.", transfer["read"], transfer["write"])

    if len(data) > 0:
        # error output from remote
        sys.exit(1)


def main() -> None:
    """
    Entry point for the command-line interface. Parses arguments and dispatches
    to local or remote sync.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-r", "--remote", type=str, help="remote host to connect to")
    parser.add_argument("-u", "--user", type=str, help="SSH user to use")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="increases verbosity, up to twice (ignored on remote)")
    parser.add_argument("-q", "--quiet", action="store_true", help="do not print any output, overrides --verbose")
    parser.add_argument("-s", "--ssh-cmd", type=str, default="ssh -CTaxq", help="SSH command to use (default 'ssh -CTaxq')")
    parser.add_argument("-m", "--mbsync", action="store_true", help="sync mbsync files (.mbsyncstate, .uidvalidity)")
    parser.add_argument("-p", "--path", type=str, default=os.path.basename(sys.argv[0]), help="path to notmuch-sync on remote server")
    parser.add_argument("-c", "--remote-cmd", type=str, help="command to run to sync; overrides --remote, --user, --ssh-cmd, --path; mostly used for testing")
    parser.add_argument("-d", "--delete", action="store_true", help="sync deleted messages (requires listing all messages in notmuch database, potentially expensive)")
    parser.add_argument("-x", "--delete-no-check", action="store_true", help="delete missing messages even if they don't have the 'deleted' tag (requires --delete) -- potentially unsafe")
    args = parser.parse_args()

    if args.remote or args.remote_cmd:
        if args.verbose == 1:
            logger.setLevel(level=logging.INFO)
        elif args.verbose == 2:
            logger.setLevel(level=logging.DEBUG)
        else:
            logger.setLevel(level=logging.WARNING)

        if args.quiet:
            logger.disabled = True
        sync_local(args)
    else:
        logger.disabled = True
        sync_remote(args)


if __name__ == "__main__":
    main()
