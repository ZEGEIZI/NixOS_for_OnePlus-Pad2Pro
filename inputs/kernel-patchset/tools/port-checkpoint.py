#!/usr/bin/env python3
"""Three-way port the extracted checkpoint into a clean official-source worktree.

Resolve reported conflicts by understanding both changes, then commit each group
in extraction order. Never resolve conflicts by replacing an entire upstream file.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--extraction", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.extraction.read_text())
    status = subprocess.check_output(["git", "-C", str(args.worktree), "status", "--porcelain"])
    if status:
        parser.error("destination must be clean")
    report = {"groups": [], "conflicts": [], "upstream_equivalent": [], "excluded": []}
    with tempfile.TemporaryDirectory(prefix="erhai-merge-") as tmp:
        basefile, theirsfile = Path(tmp) / "base", Path(tmp) / "theirs"

        def blob(rev, path):
            p = subprocess.run(["git", "-C", str(args.repo), "show", f"{rev}:{path}"], capture_output=True)
            if p.returncode:
                if b"does not exist" in p.stderr or b"exists on disk, but not in" in p.stderr:
                    return None
                raise RuntimeError(p.stderr.decode())
            return p.stdout

        for group in data["groups"]:
            if group["name"] == "99-repository-policy":
                report["excluded"].extend(group["paths"])
                continue
            report["groups"].append(group)
            for path in group["paths"]:
                target = args.worktree / path
                base = blob(data["base"], path)
                theirs = blob(data["device"], path)
                ours = target.read_bytes() if target.exists() else None
                if ours == theirs:
                    report["upstream_equivalent"].append(path)
                elif ours == base:
                    if theirs is None:
                        target.unlink()
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(theirs)
                elif theirs is None or ours is None:
                    report["conflicts"].append({"path": path, "type": "modify/delete"})
                else:
                    basefile.write_bytes(base or b"")
                    theirsfile.write_bytes(theirs)
                    p = subprocess.run(["git", "merge-file", "--diff3", "-L", "official-target",
                                        "-L", "extraction-base", "-L", "device-checkpoint",
                                        str(target), str(basefile), str(theirsfile)])
                    if p.returncode:
                        report["conflicts"].append({"path": path, "type": "content", "count": p.returncode})
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Ported {sum(len(g['paths']) for g in report['groups'])} paths; "
          f"{len(report['conflicts'])} conflict files; "
          f"{len(report['upstream_equivalent'])} upstream-equivalent files")


if __name__ == "__main__":
    main()
