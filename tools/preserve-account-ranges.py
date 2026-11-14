#!/usr/bin/env python3
"""Keep subordinate ID ranges for accounts managed outside the Nix user spec."""
import argparse
import json
import os
from pathlib import Path
import tempfile


def account_owners(passwd, declared):
    result = set()
    for line in passwd.splitlines():
        if line:
            fields = line.split(":")
            if fields[0] not in declared:
                result.update((fields[0], fields[2]))
    return result


def ranges(text):
    result = []
    for line in text.splitlines():
        if not line:
            continue
        name, start, count = line.split(":")
        start, count = int(start), int(count)
        if not name or start < 0 or count <= 0:
            raise ValueError("Invalid subordinate ID range")
        result.append((name, start, count))
    return result


def merge(current, saved, accounts):
    result = list(current)
    for entry in saved:
        name, start, count = entry
        if name not in accounts or entry in result:
            continue
        for other, other_start, other_count in result:
            if start < other_start + other_count and other_start < start + count:
                raise ValueError(f"Subordinate ID range conflict between {name} and {other}")
        result.append(entry)
    return "".join(f"{name}:{start}:{count}\n" for name, start, count in result)


def atomic_write(path, text, mode):
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w") as output:
            os.fchmod(output.fileno(), mode)
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("save", "restore"))
    parser.add_argument("--declared", type=Path, required=True)
    args = parser.parse_args()
    state = Path("/run/undeclared-account-ranges")
    state.mkdir(mode=0o700, exist_ok=True)
    declared = set(json.loads(args.declared.read_text()))
    accounts = account_owners(Path("/etc/passwd").read_text(), declared)
    if args.action == "save":
        saved = {}
        for name in ("subuid", "subgid"):
            path = Path("/etc") / name
            saved[name] = [entry for entry in ranges(path.read_text() if path.exists() else "")
                           if entry[0] in accounts]
        atomic_write(state / "ranges.json", json.dumps(saved), 0o600)
    else:
        saved = json.loads((state / "ranges.json").read_text())
        # Validate both tables before replacing either one.
        updates = []
        for name in ("subuid", "subgid"):
            path = Path("/etc") / name
            current = path.read_text() if path.exists() else ""
            result = merge(ranges(current), [tuple(entry) for entry in saved[name]], accounts)
            if result != current:
                updates.append((path, result, path.stat().st_mode & 0o777 if path.exists() else 0o644))
        for path, result, mode in updates:
            atomic_write(path, result, mode)
        (state / "ranges.json").unlink()


if __name__ == "__main__":
    main()
