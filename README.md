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
    - remote to local:
        - 4 bytes unsigned int number of IDs in the DB
        - for each of the IDs:
            - 4 bytes unsigned int length of ID
            - ID
    - local to remote:
        - 4 bytes unsigned int number of IDs to delete
        - for each of the IDs:
            - 4 bytes unsigned int length of ID
            - ID
- if --mbsync is given:
    - remote to local:
        - 4 bytes unsigned int length of JSON-encoded stat (name and mtime) of
          all .mbsyncstate/.uidvalidity files
        - JSON-encoded stat of all .mbsyncstate/.uidvalidity files
        - for each file to send from remote to local:
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
            - 4 bytes unsigned int length of requested file
            - requested file
- from remote only: 6 x 4 bytes with number of tag changes, copied/moved files, deleted files, new messages, deleted messages, new files
