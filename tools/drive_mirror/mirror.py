#!/usr/bin/env python3
"""Mirror /home/user/workspace/odessa-ward-app/ into a Google Drive folder.

Rules (v2, 2026-08-31):
- Skip files whose local MD5 matches the Drive copy (no upload, no revision).
- Update files that differ (same Drive file ID → new revision, history preserved).
- Create brand-new files.
- LEAVE ALONE Drive files that no longer exist in the repo (no trash sweep).
- Date-stamped snapshots (db-snapshots/*.sql, lcr-exports/*) accumulate in Drive.

Bounded per gws-best-practices:
- Cap total gws calls (~500 max)
- Never blind-retry exit-5; report and move on
- Skip .git/, node_modules/, .DS_Store

Run:
    cd /home/user/workspace/odessa-ward-app
    python3 tools/drive_mirror/mirror.py
"""
import os
import subprocess
import json
import sys
import mimetypes
import hashlib

ROOT = "/home/user/workspace/odessa-ward-app"
DEST_FOLDER_ID = "1ktKT-XumyJq808Jkw5EbYg1lfccA6lYh"
STATE_FILE = "/home/user/workspace/drive_mirror_state.json"
MAX_CALLS = 500

SKIP_DIRS = {'.git', 'node_modules'}
SKIP_FILES = {'.DS_Store'}

call_count = 0


def gws(args, params=None, json_body=None, upload=None, upload_content_type=None):
    """Run gws CLI. Returns (exit_code, stdout, stderr)."""
    global call_count
    call_count += 1
    if call_count > MAX_CALLS:
        raise RuntimeError(f"Exceeded max call cap ({MAX_CALLS})")
    cmd = ["gws"] + args
    if params is not None:
        cmd += ["--params", json.dumps(params)]
    if json_body is not None:
        cmd += ["--json", json.dumps(json_body)]
    if upload is not None:
        cmd += ["--upload", upload]
    if upload_content_type is not None:
        cmd += ["--upload-content-type", upload_content_type]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr


def md5_of(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"folders": {"": DEST_FOLDER_ID}, "files": {}, "failures": []}


def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def find_child(parent_id, name, mime_filter=None):
    """List and find a child by name. Returns file dict (with md5Checksum if avail) or None."""
    q_parts = [
        f"'{parent_id}' in parents",
        "trashed=false",
        f"name='{name.replace(chr(39), chr(92)+chr(39))}'",
    ]
    if mime_filter:
        q_parts.append(f"mimeType='{mime_filter}'")
    q = " and ".join(q_parts)
    rc, out, err = gws(
        ["drive", "files", "list"],
        params={"q": q, "pageSize": 5, "fields": "files(id,name,mimeType,md5Checksum,size)"},
    )
    if rc != 0:
        return {"__error__": f"list rc={rc}: {err[:300]}"}
    try:
        data = json.loads(out)
        files = data.get("files", [])
        return files[0] if files else None
    except json.JSONDecodeError as e:
        return {"__error__": f"json decode: {e}"}


def ensure_folder(rel_path, state):
    """Ensure a Drive folder exists at rel_path (posix). Returns its id."""
    if rel_path in state["folders"]:
        return state["folders"][rel_path]
    parent_rel, folder_name = os.path.split(rel_path)
    parent_id = ensure_folder(parent_rel, state) if parent_rel else DEST_FOLDER_ID
    existing = find_child(parent_id, folder_name, mime_filter="application/vnd.google-apps.folder")
    if existing and "__error__" not in existing:
        state["folders"][rel_path] = existing["id"]
        save_state(state)
        return existing["id"]
    if existing and "__error__" in existing:
        raise RuntimeError(f"Failed to list {rel_path}: {existing['__error__']}")
    rc, out, err = gws(
        ["drive", "files", "create"],
        json_body={"name": folder_name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]},
    )
    if rc != 0:
        raise RuntimeError(f"Failed to create folder {rel_path}: rc={rc} err={err[:300]}")
    data = json.loads(out)
    state["folders"][rel_path] = data["id"]
    save_state(state)
    print(f"  [folder] created {rel_path}")
    return data["id"]


def upload_file(abs_path, rel_path, state):
    """Upload/update/skip. Returns (status, message)."""
    rel_dir, filename = os.path.split(rel_path)
    try:
        parent_id = ensure_folder(rel_dir, state) if rel_dir else DEST_FOLDER_ID
    except RuntimeError as e:
        return ("fail", str(e))
    existing = find_child(parent_id, filename)
    if existing and "__error__" in existing:
        return ("fail", existing["__error__"])
    mime, _ = mimetypes.guess_type(filename)
    cwd_rel = os.path.relpath(abs_path, os.getcwd())

    if existing:
        # MD5 skip check
        remote_md5 = existing.get("md5Checksum")
        if remote_md5:
            local_md5 = md5_of(abs_path)
            if local_md5 == remote_md5:
                state["files"][rel_path] = existing["id"]
                save_state(state)
                return ("skip", "md5 match")
        # Different (or no MD5 → assume different, e.g. Google-native files) — update
        rc, out, err = gws(
            ["drive", "files", "update"],
            params={"fileId": existing["id"]},
            upload=cwd_rel,
            upload_content_type=mime,
        )
        if rc != 0:
            return ("fail", f"update rc={rc}: {err[:300]}")
        state["files"][rel_path] = json.loads(out).get("id")
        save_state(state)
        return ("updated", "")
    else:
        rc, out, err = gws(
            ["drive", "files", "create"],
            json_body={"name": filename, "parents": [parent_id]},
            upload=cwd_rel,
            upload_content_type=mime,
        )
        if rc != 0:
            return ("fail", f"create rc={rc}: {err[:300]}")
        state["files"][rel_path] = json.loads(out).get("id")
        save_state(state)
        return ("created", "")


def main():
    os.chdir(ROOT)
    state = load_state()
    files_to_upload = []
    for dirpath, dirnames, filenames in os.walk("."):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            if f in SKIP_FILES:
                continue
            rel = os.path.normpath(os.path.join(dirpath, f))
            if rel.startswith("./"):
                rel = rel[2:]
            files_to_upload.append(rel)
    files_to_upload.sort()
    print(f"Found {len(files_to_upload)} files to mirror")

    stats = {"created": 0, "updated": 0, "skip": 0, "fail": 0}
    for i, rel in enumerate(files_to_upload):
        abs_path = os.path.join(ROOT, rel)
        try:
            status, msg = upload_file(abs_path, rel, state)
        except RuntimeError as e:
            status, msg = "fail", str(e)
        stats[status] = stats.get(status, 0) + 1
        marker = {"created": "+", "updated": "~", "skip": ".", "fail": "!"}[status]
        # Only print non-skip lines to keep output short
        if status != "skip":
            print(f"  [{i+1:3d}/{len(files_to_upload)}] {marker} {rel}" + (f" — {msg}" if status == "fail" else ""))
        if status == "fail":
            state["failures"].append({"path": rel, "error": msg})
            save_state(state)
        if call_count > MAX_CALLS - 5:
            print(f"  Approaching call cap ({call_count}/{MAX_CALLS}), stopping")
            break

    print(f"\n=== Summary ===")
    print(f"Total gws calls: {call_count}")
    print(f"Created: {stats.get('created',0)}")
    print(f"Updated: {stats.get('updated',0)}")
    print(f"Skipped (md5 match): {stats.get('skip',0)}")
    print(f"Failed:  {stats.get('fail',0)}")
    if state["failures"]:
        print(f"\nRecent failures:")
        for f in state["failures"][-10:]:
            print(f"  {f['path']}: {f['error'][:200]}")


if __name__ == "__main__":
    main()
