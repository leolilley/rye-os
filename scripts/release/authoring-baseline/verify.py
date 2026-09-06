#!/usr/bin/env python3
"""Verify/materialize a closed authoring artifact before explicit RyeOS import.

The archive checksum must come from the authored release selection, not from
untrusted archive contents. This verifier does not grant a target binding.
"""

import argparse
import json
from pathlib import Path, PurePosixPath
import tarfile

from produce import HERE, digest, static_elf


def expected_members(lock: dict) -> dict[str, int]:
    files = {"inputs.json": 0o644, "README.md": 0o644}
    for notice in lock["publisher_notices"]:
        files[notice["target"]] = 0o644
    for source in lock["sources"]:
        for name in source.get("programs", {}):
            if f"bin/{name}" in files:
                raise ValueError("duplicate executable in publisher inventory")
            files[f"bin/{name}"] = 0o755
        for notice in source["licenses"]:
            files[f"licenses/{source['name']}/{notice}"] = 0o644
    members = dict(files)
    for file in files:
        for directory in PurePosixPath(file).parents:
            if str(directory) != ".":
                members[str(directory)] = 0o755
    return members


def materialize(archive: Path, expected_hash: str, destination: Path) -> None:
    if archive.is_symlink() or not archive.is_file() or archive.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("archive is not a bounded regular file")
    if digest(archive) != expected_hash:
        raise ValueError("authoring archive checksum mismatch")
    lock = json.loads((HERE / "inputs.json").read_text())
    expected = expected_members(lock)
    # Inspect all entries before creating the destination. No tar links, special
    # files, duplicates, extra members or path normalization are accepted.
    with tarfile.open(archive, "r:gz") as source:
        seen = set()
        total = 0
        for member in source:
            name = member.name
            if len(seen) >= len(expected) or name in seen or name not in expected:
                raise ValueError(f"unexpected or duplicate archive member: {name}")
            seen.add(name)
            if not (member.isfile() or member.isdir()) or member.mode != expected[name]:
                raise ValueError(f"unsupported member kind/mode: {name}")
            is_directory = any(path.startswith(name + "/") for path in expected)
            if member.isdir() != is_directory or member.uid or member.gid or member.uname or member.gname:
                raise ValueError(f"noncanonical member metadata: {name}")
            if member.mtime != lock["source_date_epoch"] or member.pax_headers:
                raise ValueError(f"noncanonical member timestamp/headers: {name}")
            total += member.size
            if member.size > 16 * 1024 * 1024 or total > 128 * 1024 * 1024:
                raise ValueError("authoring payload exceeds its finite bounds")
        if seen != set(expected):
            raise ValueError("authoring archive has missing entries")
        destination.mkdir(parents=False, exist_ok=False)
        for member in source.getmembers():
            target = destination / member.name
            if member.isdir():
                target.mkdir(mode=0o755)
            else:
                with target.open("xb") as out, source.extractfile(member) as data:
                    while chunk := data.read(1024 * 1024):
                        out.write(chunk)
                target.chmod(member.mode)
                if member.name.startswith("bin/"):
                    static_elf(target)
    if (destination / "inputs.json").read_bytes() != (HERE / "inputs.json").read_bytes():
        raise ValueError("artifact input lock differs from selected publisher inputs")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--materialize", type=Path, required=True)
    args = parser.parse_args()
    materialize(args.archive, args.sha256, args.materialize)
    print("authoring artifact verified and materialized; target binding is still required")


if __name__ == "__main__":
    main()
