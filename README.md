# notmuch-sync

## Wire Protocol

The communication protocol is binary. This is what the script produces on stdout and expects on stdin.

- 36 bytes UUID of notmuch database
- 4 bytes unsigned int length of JSON-encoded changes
- JSON-encoded changes
- 4 bytes unsigned int number of files requested
- for each of the files requested from the other side:
    - 4 bytes unsigned int length of file name
    - file name
- for each of the files requested by the other side:
    - 4 bytes unsigned int length of requested file
    - requested file
- if --delete is given:
    - 4 bytes unsigned int number of IDs in the DB
    - for each of the IDs:
        - 4 bytes unsigned int length of ID
        - ID
- from remote only: 6 x 4 bytes with number of tag changes, copied/moved files, deleted files, new messages, deleted messages, new files
