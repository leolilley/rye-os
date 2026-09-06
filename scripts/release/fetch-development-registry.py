#!/usr/bin/env python3
"""Acquire locked public registry inputs; never execute Cargo or write node state.

This is the explicit publisher/operator input acquisition boundary only.
It emits Cargo's documented local-registry format, not Cargo's private cache.
The admitted Stage-0 Cargo owns unpacking and final vendored-source production.
Import/binding and retained-result authority remain RyeOS operations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tempfile
import time
import tomllib
import urllib.parse

import yaml


SCHEMA = "ryeos.development.registry-acquisition.v1"
NAME = re.compile(r"[A-Za-z0-9_-]+\Z")
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.+-]+)?\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def bounded_file(path, maximum):
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError(f"input is not a regular file: {path}")
    with path.open("rb") as source:
        data = source.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError(f"input exceeds its bound: {path}")
    return data


def index_member(name):
    name = name.lower()
    if len(name) < 3:
        return f"{len(name)}/{name}"
    if len(name) == 3:
        return f"3/{name[0]}/{name}"
    return f"{name[:2]}/{name[2:4]}/{name}"


def validate_config(config):
    keys = {"category", "name", "version", "schema", "registry_source", "index_base",
            "archive_template", "allowed_https_hosts", "limits"}
    if not isinstance(config, dict) or set(config) != keys or config["schema"] != SCHEMA:
        raise ValueError("unsupported or incomplete acquisition declaration")
    limits = config["limits"]
    required = {"max_packages", "max_input_file_bytes", "max_index_bytes", "max_archive_bytes",
                "max_total_download_bytes", "request_timeout_seconds", "total_timeout_seconds"}
    if not isinstance(limits, dict) or set(limits) != required:
        raise ValueError("incomplete acquisition limits")
    if any(type(value) is not int or value <= 0 for value in limits.values()):
        raise ValueError("acquisition limits must be positive integers")
    hosts = config["allowed_https_hosts"]
    if not isinstance(hosts, list) or not hosts or any(
        not isinstance(host, str) or not re.fullmatch(r"[a-z0-9.-]+", host) for host in hosts
    ):
        raise ValueError("invalid HTTPS host selection")
    for url in (config["index_base"], config["archive_template"].format(name="crate", version="1.0.0")):
        validate_url(url, hosts)


def validate_url(url, hosts):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in hosts or parsed.port not in (None, 443)
            or parsed.username or parsed.password or parsed.fragment):
        raise ValueError("acquisition URL is outside the explicit HTTPS selection")


class Fetcher:
    def __init__(self, config):
        self.config = config
        self.total = 0
        self.deadline = time.monotonic() + config["limits"]["total_timeout_seconds"]
        self.checked_curl = False

    def __call__(self, url, maximum):
        validate_url(url, self.config["allowed_https_hosts"])
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("acquisition lifetime exhausted")
        limit = self.config["limits"]
        if not self.checked_curl:
            version = subprocess.run(["curl", "--disable", "--version"],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     timeout=remaining, check=True).stdout
            match = re.match(rb"curl (\d+)\.(\d+)\.(\d+) ", version)
            # Since 8.4, max-filesize also stops transfers without a declared
            # Content-Length. This is a required implementation capability,
            # not an optional behavior or a replacement for the byte budget.
            if match is None or tuple(map(int, match.groups())) < (8, 4, 0):
                raise ValueError("bootstrap acquisition requires curl >= 8.4.0")
            self.checked_curl = True
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise ValueError("acquisition lifetime exhausted")
        maximum = min(maximum, limit["max_total_download_bytes"] - self.total)
        if maximum <= 0:
            raise ValueError("acquisition byte bound exhausted")
        request_remaining = min(remaining, limit["request_timeout_seconds"])
        # This explicit bootstrap uses the same host download dependency as
        # Stage-0 acquisition, never host Cargo. Curl disables user config and
        # proxies, accepts HTTPS only and does not follow redirects. Its byte
        # limit bounds captured output; the independent process deadline also
        # covers slow-drip reads and resolver/connect stalls. This is not a
        # worker transport or a new RyeOS process owner.
        result = subprocess.run([
            "curl", "--disable", "--silent", "--show-error", "--fail",
            "--proto", "=https", "--noproxy", "*", "--max-redirs", "0",
            "--max-filesize", str(maximum), "--max-time", str(request_remaining),
            "--connect-timeout", str(request_remaining),
            "--url", url,
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=request_remaining, check=True)
        data = result.stdout
        self.total += len(data)
        if len(data) > maximum or time.monotonic() > self.deadline:
            raise ValueError("acquisition byte or lifetime bound exceeded")
        return data


def selected_packages(lock, config):
    packages = []
    seen = set()
    for package in lock["package"]:
        if "source" not in package:
            continue  # Workspace/path sources remain in the exact project snapshot.
        name, version = package["name"], package["version"]
        checksum = package.get("checksum", "")
        if (package["source"] != config["registry_source"] or not NAME.fullmatch(name)
                or not VERSION.fullmatch(version) or not DIGEST.fullmatch(checksum)):
            raise ValueError("lock contains an unsupported or unpinned registry coordinate")
        if (name, version) in seen:
            raise ValueError("duplicate locked registry coordinate")
        seen.add((name, version))
        packages.append((name, version, checksum))
    if not packages or len(packages) > config["limits"]["max_packages"]:
        raise ValueError("locked registry inventory is empty or exceeds its bound")
    return sorted(packages)


def put(root, relative, data):
    path = PurePosixPath(relative)
    if path.is_absolute() or path.as_posix() != relative or any(p in (".", "..") for p in path.parts):
        raise ValueError("noncanonical output member")
    target = root.joinpath(*path.parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as output:
        output.write(data)
    target.chmod(0o644)


def acquire(lock_bytes, config, output, fetch):
    validate_config(config)
    packages = selected_packages(tomllib.loads(lock_bytes.decode()), config)
    if output.exists() or output.is_symlink():
        raise ValueError("output already exists; refusing overwrite")
    records, sources = {}, {}
    current_name, selected_lines = None, []
    # Stage beside the final output. A failure leaves no partially published
    # registry; there is no cross-filesystem directory rename or node mutation.
    with tempfile.TemporaryDirectory(prefix=".registry-input-", dir=output.parent) as scratch:
        stage = Path(scratch) / "registry"
        stage.mkdir()
        for name, version, checksum in packages:
            if name != current_name:
                if current_name is not None:
                    put(stage, "index/" + index_member(current_name), b"\n".join(selected_lines) + b"\n")
                current_name, selected_lines = name, []
                url = config["index_base"].rstrip("/") + "/" + index_member(name)
                raw = fetch(url, config["limits"]["max_index_bytes"])
                entries = {}
                for line in raw.splitlines():
                    entry = json.loads(line)
                    if entry.get("name") != name or entry.get("vers") in entries:
                        raise ValueError("registry index has contradictory package coordinates")
                    entries[entry["vers"]] = (entry, line)
                records = entries
                sources[url] = hashlib.sha256(raw).hexdigest()
            entry, line = records.get(version, ({}, b""))
            if entry.get("cksum") != checksum:
                raise ValueError("registry index does not match the exact locked checksum")
            selected_lines.append(line)
            url = config["archive_template"].format(name=name, version=version)
            archive = fetch(url, config["limits"]["max_archive_bytes"])
            if hashlib.sha256(archive).hexdigest() != checksum:
                raise ValueError("crate archive does not match Cargo.lock")
            put(stage, f"{name}-{version}.crate", archive)
            sources[url] = checksum
        put(stage, "index/" + index_member(current_name), b"\n".join(selected_lines) + b"\n")
        put(stage, "acquisition.json", (json.dumps({
            "schema": SCHEMA,
            "lock_sha256": hashlib.sha256(lock_bytes).hexdigest(),
            "declaration_sha256": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
            "source_sha256": sources,
            "packages": [{"name": n, "version": v, "sha256": c} for n, v, c in packages],
        }, sort_keys=True, indent=2) + "\n").encode())
        # This operator-owned destination must be exclusively held during
        # acquisition; never invoke it concurrently for one output coordinate.
        if output.exists() or output.is_symlink():
            raise ValueError("output appeared during acquisition")
        stage.rename(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--declaration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = yaml.safe_load(bounded_file(args.declaration, 65536))
    validate_config(config)
    lock = bounded_file(args.lock, config["limits"]["max_input_file_bytes"])
    acquire(lock, config, args.output, Fetcher(config))
    print(f"Acquired locked registry inputs: {args.output}; import/binding and admitted Cargo production remain required")


if __name__ == "__main__":
    main()
