# notmuch-sync

![Python Tests](https://github.com/larskotthoff/notmuch-sync/actions/workflows/python.yml/badge.svg)
![Integration Tests](https://github.com/larskotthoff/notmuch-sync/actions/workflows/notmuch-ml.yml/badge.svg)
![Integration Tests with IMAP server](https://github.com/larskotthoff/notmuch-sync/actions/workflows/imap.yml/badge.svg)
![Security Scanner](https://github.com/larskotthoff/notmuch-sync/actions/workflows/codeql.yml/badge.svg)

mbsync-compatible syncing of notmuch databases and mail files.

[PyPI page](https://pypi.org/project/notmuch-sync/)

## Installation and Quickstart

Assumes that you have [notmuch](https://notmuchmail.org) installed and working.
Install with e.g. `pip install notmuch-sync`. No configuration is necessary;
everything is picked up from notmuch. You may however need to install your OS'
packages for xapian.

Before you run `notmuch-sync` for the first time, make sure that notmuch is set
up correctly (in particular with the correct database path). It is not necessary
to copy mails and tags; this will be done automatically by `notmuch-sync` on
first run if one of the sides is a new, empty notmuch database.

Run as e.g. `notmuch-sync --verbose --delete --remote my.mail.server --user
user`. This assumes that you can connect to `my.mail.server` using SSH with user
`user` and that `notmuch-sync` is in the $PATH of that user on the remote
machine. See `notmuch-sync --help` for commandline flags. Notmuch databases need
to be set up on both sides; notmuch-sync does not run `notmuch new`.

In a nutshell, here are the steps you would take if you have notmuch set up on
one machine and wish to sync it with another:
1. Copy your notmuch configuration to the new machine (this may be just `.notmuch-config`).
2. Adjust the configuration as necessary, in particular any paths.
3. Run `notmuch new` on the new machine (no need to copy any mail files).
4. Run `notmuch-sync --verbose --delete --remote other.machine`. Add `--mbsync`
   if you're using mbsync.

If you're starting with an empty notmuch database on one side, the first sync
might take a long time. Subsequent syncs should be much faster, unless there are
a lot of changes.


## Commandline Flags

````
usage: notmuch-sync [-h] [-r REMOTE] [-u USER] [-v] [-q] [-s SSH_CMD] [-m] [-p PATH] [-c REMOTE_CMD] [-d] [-x]

options:
  -h, --help            show this help message and exit
  -r, --remote REMOTE   remote host to connect to
  -u, --user USER       SSH user to use
  -v, --verbose         increases verbosity, up to twice (ignored on remote)
  -q, --quiet           do not print any output, overrides --verbose
  -s, --ssh-cmd SSH_CMD
                        SSH command to use (default 'ssh -CTaxq')
  -m, --mbsync          sync mbsync files (.mbsyncstate, .uidvalidity)
  -p, --path PATH       path to notmuch-sync on remote server
  -c, --remote-cmd REMOTE_CMD
                        command to run to sync; overrides --remote, --user, --ssh-cmd, --path; mostly used for testing
  -d, --delete          sync deleted messages (requires listing all messages in notmuch database, potentially expensive)
  -x, --delete-no-check
                        delete missing messages even if they don't have the 'deleted' tag (requires --delete) -- potentially unsafe
````


## Main Features

- sync arbitrary pairs of notmuch databases over SSH or through arbitrary custom
  commands
- leverage notmuch database revision numbers for efficient changeset
  determination
- asynchronous IO for efficient data transfer over networks
- sync state stored as version number and UUID of notmuch database, does not
  depend on size of notmuch database
- compatible with [mbsync](https://isync.sourceforge.io/mbsync.html) and works
  around some of its quirks (X-TUID...)
- extensive unit and integration tests, with the entire archive of the
  [notmuch mailing list](https://nmbug.notmuchmail.org/list/) and a real IMAP
  server and mbsync


### Sync Procedure

notmuch-sync uses the revision number of the notmuch database (`lastmod` search
term) to record the last sync and efficiently determine what has changed since
then. The sync process works as follows:
- The notmuch database is opened in write mode to lock it.
- Both sides get the changes since the last sync, or all changes if there has
  been no sync with the database UUID on the other side.
- Tags are synced on both sides.
  - If a message shows up in the changeset for the other side, its tags are
    applied to the message on this side.
  - If a message shows up in the changesets for both sides, the union of the
    tags of the message from both sides is applied to the message on both sides.
- Files of existing messages are synced as follows, on both local and remote
  sides:
  - Files missing on this side are determined as the file names the other side
    has, but are missing on this side.
  - We try to find these missing files locally by comparing the SHA256
    digests from the other side with the SHA256 digests for the local files.
    Computing the digest does not consider lines starting with "X-TUID: " to
    identify identical files that only differ in the mbsync run (e.g. if
    mbsync was run separately on both sides).
  - Files that are thus identified as the same with different filenames are
    - copied if both filenames are also present on the other side and in the
      other changeset since the last sync,
    - moved from the filename on this side to the filename on the other side if
      they are not in our changeset or the `move_on_change` flag is set,
    - skipped if none of the above applies and the `move_on_change` flag is not
      set.
    The `move_on_change` flag is true on the local machine and false on the
    remote. It is used to disambiguate which changes to adopt and avoids
    creating duplicate messages unnecessarily. This comes up in particular if
    both sides independently run mbsync, which creates the same message with
    different filenames (and different X-TUID headers) and the same UID. Simply
    copying those messages when syncing would create duplicate files, but more
    importantly duplicate UIDs (which mbsync stores in the filenames), which
    would cause an error on the next mbsync run.
  - Duplicate files for the same message that are not present on the other side
    are deleted and removed from the notmuch database. There is a check that
    this does not accidentally remove messages.
  - Any files that are actually missing (don't have files with the same SHA256)
    are transferred between the two sides.
- The sync is recorded with notmuch database version and UUID.
- The notmuch database is closed in write mode -- this unlocks it so that any
  other processes trying to access it should only have to wait for a short time.
- If `--delete` is given, all notmuch message IDs are listed on both sides and
  the messages to be deleted determined by taking the differences between those
  sets. Messages are only deleted if they have the "deleted" tag (see the
  "Deleting Mails" section for further details).
- If `--mbsync` is given, sync mbsync state files (`.uidvalidity`,
  `.mbsyncstate`). The files are listed on both sides and ones with later
  modification dates transferred to the other side. This assumes that both
  machines have (at least somewhat) synchronized clocks.


### Sync State

The sync state for a remote host is saved in the `.notmuch` directory of your
notmuch mail directory in a file of the form `notmuch-sync-<UUID>` where
`<UUID>` is the UUID of the database synced with (not the UUID of the local
notmuch database). The contents of the file are the revision number of the
local notmuch database after the last tag sync followed by a space and the UUID
of the local notmuch database.

This allows for syncs between any number of arbitrary pairs, even if host
names/IP addresses change, only the UUIDs of the notmuch databases have to
remain the same.

Removing a sync state file starts the sync from scratch the next time
notmuch-sync is run. This should generally be safe (i.e. end up with the two
notmuch databases synced as you would expect), but will do a lot of unnecessary
work and communication.


### Differences to [muchsync](https://www.muchsync.org/)

- syncs filenames and mbsync metadata
- does not rely on shadow copy of notmuch database -- more space efficient and
  no sqlite dependency
- probably slower and more memory-hungry
- does not sync notmuch configuration
- no special handling of "unread" tag required as only changes are considered
- does not run `notmuch new` automatically, neither on the local nor the remote
  side
- [glorious](https://github.com/larskotthoff/notmuch-sync/blob/main/test/test.py),
  [glorious](https://github.com/larskotthoff/notmuch-sync/blob/main/test/test-integration.py),
  [glorious](https://github.com/larskotthoff/notmuch-sync/blob/main/.github/workflows/notmuch-ml.yml)
  [tests](https://github.com/larskotthoff/notmuch-sync/blob/main/.github/workflows/imap.yml)


### mbsync Compatibility

notmuch-sync syncs mbsync state under the notmuch mail directory, which requires
`SyncState *` for all channels and synchronized clocks. It should be safe to run
mbsync on any of the synced copies at any time; messages that are retrieved
through mbsync on multiple copies will be synced automatically by moving files
accordingly.


### Deleting Mails

notmuch-sync is very careful about deleting mails. While duplicate *files* for
the same email are always cleaned up as part of the sync (i.e. if duplicates
have been deleted on one side, they will also be deleted on the other side),
*messages* are never deleted unless the user explicitly requests it. To do this,
the `--delete` flag must be given, and even then only messages that have been
tagged "deleted" are actually deleted. To delete messages that do not have the
"deleted" tag, you can specify `--delete-no-check` in addition to `--delete`
(not recommended, use at your own risk).

If `--delete` is given, all message IDs in the notmuch database are listed on
both sides (this is potentially expensive). Then the difference between those
lists is taken to determine what messages should be deleted on the local and
remote sides. If a message ID is slated for deletion but the message does *not*
have the "deleted" tag (on either side), notmuch-sync assumes that something has
gone wrong and creates a dummy transaction for the message that changes nothing,
but will make it appear in the next changeset. This will cause the message to be
added on the side where it's missing the next time sync is run.

This should work well with workflows where messages that have been tagged
"deleted" are kept for a while and only then actually deleted by removing the
files. Note that if the interval between tagging messages "deleted" and actually
deleting them is smaller than the interval between syncs (e.g. one side hasn't
been synced in a long time), deleted messages will reappear when synced. This is
because one side will have no record of the "deleted" tag and will only see
messages not present that are not tagged "deleted".


## Limitations

The size limit for most things that are communicated between hosts is $2^{32}$
bytes, i.e. about 4GB. This includes the size of individual mail files, the
length of changesets (message IDs, tags, files, and SHA256 checksums), and the
length of all message IDs. This is not a fundamental limitation but simply to
avoid additional communication overhead and should be sufficient for most use
cases.

The folder structure under the notmuch mail directory is assumed to be the same
on all copies, in particular this means that the mbsync configuration should be
the same as well.

Changes to the notmuch database and mail files while notmuch-sync is running,
e.g. moving files, will result in error messages. It is safe to simply rerun
notmuch-sync when this happens.

Running `notmuch compact` changes the UUID of the database. This means that
subsequent syncs will abort with an error message.

Like muchsync, notmuch-sync uses xapian directly for some operations for
efficiency reasons. This means in particular that notmuch-sync assumes that
value 1 of a xapian document is the message ID and the term "Tghost" is used to
identify ghost messages.

notmuch-sync assumes that the remote command does not produce any output except
for the output produced by the remote notmuch-sync. If you're running a wrapper
script on the remote or have an SSH banner, make sure to silence/redirect all
respective output.

There are extensive tests, but there is no guarantee that notmuch-sync will
always do the right thing.


## Wire Protocol

The communication protocol is binary. This is what the script produces on stdout and expects on stdin.

- 36 bytes UUID of notmuch database
- 4 bytes unsigned int length of JSON-encoded changes
- JSON-encoded changes
- 4 bytes unsigned int length of JSON-encoded files requested hashes for from other side
- JSON-encoded files requested hashes for from other side
- 4 bytes unsigned int length of JSON-encoded hashes to be sent back
- JSON-encoded hashes to be sent back
- 4 bytes unsigned int length of JSON-encoded file names requested from the other side
- JSON-encoded file names requested from the other side
- for each of the files requested by the other side:
    - 4 bytes unsigned int length of requested file
    - requested file
- if --delete is given:
    - remote to local:
        - 4 bytes unsigned int length of JSON-encoded IDs in the DB
        - JSON-encoded IDs in the DB
    - local to remote:
        - 4 bytes unsigned int length of JSON-encoded IDs to be deleted
        - JSON-encoded IDs to be deleted
- if --mbsync is given:
    - remote to local:
        - 4 bytes unsigned int length of JSON-encoded stat (name and mtime) of
          all .mbsyncstate/.uidvalidity files
        - JSON-encoded stat of all .mbsyncstate/.uidvalidity files
        - 4 bytes unsigned int length of JSON-encoded files to send from remote to local
        - JSON-encoded files to send from remote to local
        - for each file to send from remote to local:
            - 8 bytes last mtime of requested file
            - 4 bytes unsigned int length of requested file
            - requested file
    - local to remote:
        - 4 bytes unsigned int length of JSON-encoded list of files for remote
          to send to local
        - JSON-encoded list of files for remote to send to local
        - 4 bytes unsigned int length of JSON-encoded list of files for local
          to send to remote
        - JSON-encoded list of files for local to send to remote
        - for each file to send from local to remote:
            - 8 bytes last mtime of requested file
            - 4 bytes unsigned int length of requested file
            - requested file
- from remote only: 6 x 4 bytes with number of tag changes, copied/moved files, deleted files, new messages, deleted messages, new files
