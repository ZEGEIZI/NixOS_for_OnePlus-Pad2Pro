#!/usr/bin/env python3
"""Reject unmet final tristate/disabled requests after Kconfig resolves dependencies."""
import pathlib
import sys

actual = set(pathlib.Path(sys.argv[1]).read_text().splitlines())
enabled = {line.split("=", 1)[0] for line in actual if line.startswith("CONFIG_") and "=" in line}
requested = {}
for fragment in sys.argv[2:]:
    for raw in pathlib.Path(fragment).read_text().splitlines():
        line = raw.split(" #", 1)[0].strip()
        if line.startswith("CONFIG_") and "=" in line:
            key, value = line.split("=", 1)
            requested[key] = (line, fragment)
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            requested[line.split()[1]] = (line, fragment)
missing = []
for key, (line, origin) in requested.items():
    # Kconfig omits disabled symbols whose dependencies hide the entire menu.
    # Omission is still disabled; an explicit enable must never be accepted.
    if line.startswith("# CONFIG_"):
        mismatch = key in enabled
    else:
        mismatch = line not in actual
    if mismatch:
        missing.append((line, origin))
if missing:
    raise SystemExit("Unmet kernel settings:\n" + "\n".join(f"{line} ({origin})" for line, origin in missing))
