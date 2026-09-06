#!/usr/bin/env python3
"""Acquire only the locked publisher inputs; never used on an execution target."""

import argparse
import json
from pathlib import Path
import tempfile
import urllib.request

from produce import HERE, digest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--assembly", action="store_true",
                        help="fetch the finite assembly notices/source snapshots, not compiler inputs")
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    selection = "assembly-upstreams.json" if args.assembly else "inputs.json"
    for source in json.loads((HERE / selection).read_text())["sources"]:
        path = args.cache / source["archive"]
        if path.is_symlink():
            raise ValueError(f"linked cache member: {path}")
        if not path.exists():
            with tempfile.NamedTemporaryFile(dir=args.cache) as target:
                with urllib.request.urlopen(source["url"], timeout=60) as response:
                    if not response.url.startswith("https://"):
                        raise ValueError("source redirected away from HTTPS")
                    total = 0
                    while chunk := response.read(1024 * 1024):
                        total += len(chunk)
                        if total > source["bytes"]:
                            raise ValueError(f"source exceeds pinned size: {path.name}")
                        target.write(chunk)
                target.flush()
                if total != source["bytes"] or digest(Path(target.name)) != source["sha256"]:
                    raise ValueError(f"download identity mismatch: {path.name}")
                # Exclusive publication: another fetch never gets overwritten.
                with path.open("xb") as published, open(target.name, "rb") as checked:
                    while chunk := checked.read(1024 * 1024):
                        published.write(chunk)
        if not path.is_file() or path.stat().st_size != source["bytes"] or digest(path) != source["sha256"]:
            raise ValueError(f"cache identity mismatch: {path}")
        print(f"verified {path.name}", flush=True)


if __name__ == "__main__":
    main()
