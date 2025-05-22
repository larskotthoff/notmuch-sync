#!/usr/bin/env python

import sys
import os
import struct
import subprocess
import socket
import json

import notmuch2

def get_changes(db, fname):
    """Get changes that happened since the last sync, or everything in the DB if no previous sync."""
    rev_prev = 0
    try:
        with open(fname, 'r', encoding="utf-8") as f:
            tmp = f.read().strip('\n\r').split(' ')
            uuid = db.revision().uuid.decode()
            try:
                if tmp[1] != uuid:
                    sys.exit(f"Last sync with UUID {tmp[1]}, but notmuch DB has UUID {uuid}, aborting...")
                rev_prev = int(tmp[0])
            except Exception:
                sys.exit(f"Sync state file {fname} corrupted, delete to sync from scratch.")
    except FileNotFoundError:
        # no previous sync or sync file broken, leave rev_prev at 0 as this will sync entire DB
        pass

    prefix = os.path.join(str(db.default_path()), '')
    return [ {"id": msg.messageid,
             "tags": list(msg.tags),
             "files": [ str(f).removeprefix(prefix) for f in msg.filenames() ]} for msg in db.messages(f"lastmod:{rev_prev}..") ]


def run_local(args):
    #print("READY", flush=True)
    #while True:
    #    line = sys.stdin.readline()
    #    if not line:
    #        break
    #    line = line.strip()
    #    if line.startswith("SEND_FILE"):
    #        _, filename = line.split(maxsplit=1)
    #        size_data = sys.stdin.buffer.read(4)
    #        size = struct.unpack("!I", size_data)[0]
    #        content = sys.stdin.buffer.read(size)
    #        with open(f"received_{os.path.basename(filename)}", "wb") as f:
    #            f.write(content)
    #        print(f"RECEIVED {filename}", flush=True)
    #    elif line == "BYE":
    #        print("GOODBYE", flush=True)
    #        break

    with notmuch2.Database() as db:
        fname = os.path.join(str(db.default_path()), ".notmuch", f"notmuch-sync-{args.remote or os.getenv('NOTMUCH_SYNC_LOCAL', '')}")
        changes = get_changes(db, fname)
        print(len(changes))
        # process changes
        with open(fname, 'w', encoding="utf-8") as f:
            f.write(f"{db.revision().rev} {db.revision().uuid.decode()}")


def run_remote(args):
    ssh_cmd = [args.ssh_cmd, f"{args.user}{'@' if args.user else ''}{args.remote}", f"NOTMUCH_SYNC_LOCAL={socket.getfqdn()} python {args.path}"]
    proc = subprocess.Popen(
        ssh_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False  # raw binary mode
    )

    stdout = proc.stdout
    stdin = proc.stdin

    ## Wait for "READY"
    #ready_line = stdout.readline()
    #if not ready_line.strip().decode().startswith("READY"):
    #    print("Remote script did not start correctly.")
    #    return

    #for file_path in files:
    #    filename = os.path.basename(file_path)
    #    with open(file_path, "rb") as f:
    #        content = f.read()

    #    # Send metadata
    #    stdin.write(f"SEND_FILE {filename}\n".encode())
    #    stdin.flush()

    #    # Send file length and data
    #    stdin.write(struct.pack("!I", len(content)))
    #    stdin.write(content)
    #    stdin.flush()

    #    # Read acknowledgment
    #    print(stdout.readline().strip().decode())

    #stdin.write(b"BYE\n")
    #stdin.flush()
    #print(stdout.readline().strip().decode())

    stdin.close()
    stdout.close()
    proc.wait()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-r", "--remote", type=str, help="remote host to sync with")
    parser.add_argument("-u", "--user", type=str, help="SSH user to use")
    parser.add_argument("-v", "--progress", action="store_true", help="show progress, not just summary")
    parser.add_argument("-s", "--ssh-cmd", type=str, default="ssh -CTaxq", help="SSH command to use")
    parser.add_argument("-m", "--mbsync", action="store_true", help="sync mbsync files (.mbsyncstate, .uidvalidity)")
    parser.add_argument("-p", "--path", type=str, default=os.path.basename(sys.argv[0]), help="remote script path")
    args = parser.parse_args()

    if args.remote:
        run_remote(args)
    else:
        run_local(args)
