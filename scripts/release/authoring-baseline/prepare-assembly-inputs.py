#!/usr/bin/env python3
"""Offline bootstrap of inputs, NOT the RyeOS artifact producer or publisher.

Select the two reproduced utility archives, exact workload resource archive and
finite files from the already cached publisher image. The emitted inventory is
reviewed/signed before the ordinary RyeOS assemble/verify Tools consume it.
Nothing here writes node state, binds content, or supplies worker authority.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import stat
import subprocess
import tarfile


IMAGE = "docker.io/library/rust@sha256:443dd9a3260cf23c22fc05051dd5661dd7b4028d3d25dbaffab6563b63c3539c"
BOOTSTRAP = "ryeos-authoring-tools-1.0.0-x86_64-linux-musl"
ARCHIVES = {
    BOOTSTRAP + ".tar.gz": (4782852, "7872d73354ffb67c2859c9c58f499c0471902abcc6bb855a1e5e0b5021543479"),
    BOOTSTRAP + "-sources.tar.gz": (82623880, "24e7f72bbd9b026bcbe4d188946702054b24e4062184e103d63baa1a5379f0e2"),
}
CODEX_SHA256 = "bd758d53d56e41dc65e045f4589df79a038ed197a011adcb52a258e6ad64cfda"
PATCHER_SHA256 = "1d39a7973504a4a5eb4101293cca142b83055a5a0f94e1d4286ded2563289b92"
PATCHER_PROGRAM_SHA256 = "db7d1d1be4a257c75a5bae14e68c2bc825a3be3d2bc13a405436bc56272cfc37"
PACKAGE_MEMBERS = {
    "codex-path/rg": "e62198eb19b136b88c330af83647b5a962cb99b6b1f066758568f12de1974849",
    "codex-resources/zsh/bin/zsh": "67faaaa89242c4a332e16e508a1977cffc24bf7fca31d4411cdfd101f3831ef3",
}
# Canonical regular image members -> flattened, explicit input members. The
# image digest is the bootstrap source authority; the emitted signed config
# additionally pins each file's bytes and normalized mode before Tool execution.
LIBRARIES = {
    "ld-linux-x86-64.so.2": "ld-linux-x86-64.so.2",
    "libc.so.6": "libc.so.6", "libm.so.6": "libm.so.6",
    "libtinfo.so.6.5": "libtinfo.so.6",
    "libctf-nobfd.so.0.0.0": "libctf-nobfd.so.0",
    "libz.so.1.3.1": "libz.so.1", "libzstd.so.1.5.7": "libzstd.so.1",
    "libsframe.so.1.0.0": "libsframe.so.1",
    "libstdc++.so.6.0.33": "libstdc++.so.6", "libgcc_s.so.1": "libgcc_s.so.1",
}
RUNTIME_LIBRARIES = {"ld-linux-x86-64.so.2", "libc.so.6", "libm.so.6", "libtinfo.so.6"}
NOTICES = {"libc6": "glibc", "libtinfo6": "ncurses", "binutils": "binutils",
           "libstdc++6": "gcc", "zlib1g": "zlib", "libzstd1": "zstd"}
MEMBERS = {"/usr/lib/x86_64-linux-gnu/" + src: ("elf/lib/" + dest, 0o755 if dest.startswith("ld-") else 0o644)
           for src, dest in LIBRARIES.items()}
MEMBERS["/usr/bin/x86_64-linux-gnu-readelf"] = ("elf/bin/readelf", 0o755)
MEMBERS.update({"/usr/share/doc/" + source + "/copyright": ("notices/" + name + "-COPYRIGHT", 0o644)
                for source, name in NOTICES.items()})
MEMBERS.update({"/usr/share/common-licenses/" + name: ("notices/" + name, 0o644)
                for name in ("GPL-2", "GPL-3", "LGPL-2.1")})


def digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def verified(path: Path, expected: str, size: int | None = None) -> Path:
    if not stat.S_ISREG(path.lstat().st_mode) or path.stat().st_size > 256 * 1024 * 1024:
        raise ValueError("bootstrap input is not a bounded regular file")
    if (size is not None and path.stat().st_size != size) or digest(path) != expected:
        raise ValueError(f"bootstrap input identity mismatch: {path.name}")
    return path


def put(root: Path, name: str, data: bytes, mode: int) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or path.as_posix() != name or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError("invalid selected bootstrap member")
    target = root.joinpath(*path.parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as output:
        output.write(data)
    target.chmod(mode)


def image_members(patcher: Path) -> bytes:
    # This bootstrap uses Python from the exact image. It is not the Tool's
    # runtime. No network, daemon socket, host libraries or writable mount.
    program = r'''
import hashlib, io, json, pathlib, stat, subprocess, sys, tarfile
selection = json.loads(sys.argv[1])
with tarfile.open(fileobj=sys.stdout.buffer, mode="w|") as output:
    def emit(name, data, mode):
        entry = tarfile.TarInfo(name); entry.size = len(data); entry.mode = mode
        output.addfile(entry, io.BytesIO(data))
    for source, (destination, mode) in sorted(selection.items()):
        path = pathlib.Path(source)
        # Documentation directory aliases belong to the exact immutable image;
        # regular payload files themselves must not be symlinks.
        if not stat.S_ISREG(path.lstat().st_mode):
            raise ValueError("selected image member is not regular: " + source)
        emit(destination, path.read_bytes(), mode)
    package = pathlib.Path("/input/patchelf.deb")
    if hashlib.sha256(package.read_bytes()).hexdigest() != sys.argv[2]:
        raise ValueError("patcher archive changed")
    payload = subprocess.check_output(["/usr/bin/ar", "p", str(package), "data.tar.xz"])
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:xz") as archive:
        for source, destination, mode in [
            ("./usr/bin/patchelf", "elf/bin/patchelf", 0o755),
            ("./usr/share/doc/patchelf/copyright", "notices/patchelf-COPYRIGHT", 0o644)]:
            entry = archive.getmember(source)
            if not entry.isfile(): raise ValueError("patcher member is not regular")
            emit(destination, archive.extractfile(entry).read(), mode)
'''
    command = ["docker", "run", "--rm", "--pull=never", "--network=none", "--read-only",
               "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pids-limit=32", "--memory=256m",
               "--mount", f"type=bind,src={patcher.resolve()},dst=/input/patchelf.deb,readonly",
               "--entrypoint", "/usr/bin/python3", IMAGE, "-c", program,
               json.dumps(MEMBERS, sort_keys=True), PATCHER_SHA256]
    # Exact image + finite selected members; an unexpectedly large stream is
    # refused without retaining a plausible successful input tree.
    with subprocess.Popen(command, stdout=subprocess.PIPE) as process:
        try:
            payload = process.stdout.read(32 * 1024 * 1024 + 1)
            if len(payload) > 32 * 1024 * 1024:
                raise ValueError("selected image payload exceeds bootstrap bound")
            if process.wait(timeout=60):
                raise ValueError("pinned image selection failed")
            return payload
        finally:
            if process.poll() is None:
                process.kill(); process.wait()


def input_contract(root: Path, upstreams: list[dict]) -> dict:
    repository = Path(__file__).resolve().parents[3]
    owner = repository / ".ai/tools/ryeos/development/authoring-environment-production/lib/production.py"
    spec = importlib.util.spec_from_file_location("authoring_production", owner)
    production = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(production)
    inputs = production.inventory(root)
    files = {}
    for source in inputs:
        if source.startswith("utilities/bin/"):
            files["environment/bin/" + source.removeprefix("utilities/bin/")] = source
        elif source.startswith("utilities/licenses/"):
            files["environment/licenses/" + source.removeprefix("utilities/licenses/")] = source
        elif source.startswith("notices/"):
            files["environment/licenses/" + source.removeprefix("notices/")] = source
        elif source.startswith("sources/"):
            files["corresponding-sources/" + source.removeprefix("sources/")] = source
    for library in RUNTIME_LIBRARIES:
        files["environment/lib/" + library] = "elf/lib/" + library
    config = {
        "category": "development/ryeos", "name": "authoring-environment-inputs",
        "version": "1.0.0", "schema": production.SCHEMA,
        "source_date_epoch": 1788566400, "inputs": inputs, "files": files,
        "relocate": sorted(["environment/bin/zsh"] + [
            "environment/lib/" + name for name in RUNTIME_LIBRARIES if not name.startswith("ld-")]),
        "provenance": {
            "bootstrap_image": IMAGE,
            "utility_bootstrap_archives": {name: {"bytes": size, "sha256": sha}
                                           for name, (size, sha) in ARCHIVES.items()},
            "workload_package_sha256": CODEX_SHA256,
            "workload_members": PACKAGE_MEMBERS,
            "elf_authoring_package_sha256": PATCHER_SHA256,
            "elf_authoring_program_sha256": PATCHER_PROGRAM_SHA256,
            "runtime_image_members": MEMBERS,
            "source_and_notice_inputs": upstreams,
        },
    }
    production.validate_config(config)
    return config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--second", type=Path, required=True)
    parser.add_argument("--codex-package", type=Path, required=True)
    parser.add_argument("--patchelf-package", type=Path, required=True)
    parser.add_argument("--upstream-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for name, (size, expected) in ARCHIVES.items():
        verified(args.first / name, expected, size)
        verified(args.second / name, expected, size)
    verified(args.codex_package, CODEX_SHA256)
    verified(args.patchelf_package, PATCHER_SHA256, 99720)
    upstreams = json.loads((Path(__file__).parent / "assembly-upstreams.json").read_text())["sources"]
    for source in upstreams:
        verified(args.upstream_cache / source["archive"], source["sha256"], source["bytes"])
    # Select image input before creating output, so missing image/daemon or
    # member identity failures do not look like completed preparation.
    payload = image_members(args.patchelf_package)
    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as archive:
        expected = {dest for dest, _ in MEMBERS.values()} | {"elf/bin/patchelf", "notices/patchelf-COPYRIGHT"}
        seen = set()
        for member in archive:
            if not member.isfile() or member.name not in expected or member.name in seen:
                raise ValueError("unexpected image selection output")
            seen.add(member.name)
            put(args.output, member.name, archive.extractfile(member).read(), member.mode)
        if seen != expected:
            raise ValueError("incomplete image selection")
    verified(args.output / "elf/bin/patchelf", PATCHER_PROGRAM_SHA256)
    with tarfile.open(args.first / (BOOTSTRAP + ".tar.gz"), "r:gz") as archive:
        for member in archive:
            if member.isfile() and member.name.startswith(("bin/", "licenses/")):
                put(args.output, "utilities/" + member.name, archive.extractfile(member).read(), member.mode)
    with tarfile.open(args.codex_package, "r:gz") as archive:
        for source, expected in PACKAGE_MEMBERS.items():
            member = archive.getmember(source)
            if not member.isfile():
                raise ValueError("selected workload resource is not regular")
            data = archive.extractfile(member).read()
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError("selected workload resource identity mismatch")
            put(args.output, "utilities/bin/" + PurePosixPath(source).name, data, 0o755)
    sources = args.first / (BOOTSTRAP + "-sources.tar.gz")
    put(args.output, "sources/" + sources.name, sources.read_bytes(), 0o644)
    # Preserve the historical bootstrap pair honestly, then supply every
    # currently selected notice from its exact corresponding source archives.
    # Adding notices does not pretend the old binary archive was rebuilt.
    lock = json.loads((Path(__file__).parent / "inputs.json").read_text())
    with tarfile.open(sources, "r:gz") as bundle:
        for source in lock["sources"]:
            entry = bundle.getmember(source["archive"])
            if not entry.isfile() or entry.size != source["bytes"]:
                raise ValueError("bootstrap corresponding-source member mismatch")
            data = bundle.extractfile(entry).read()
            if hashlib.sha256(data).hexdigest() != source["sha256"]:
                raise ValueError("bootstrap corresponding-source digest mismatch")
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as archive:
                for notice in source["licenses"]:
                    selected = archive.getmember(source["directory"] + "/" + notice)
                    if not selected.isfile():
                        raise ValueError("upstream notice is not a regular file")
                    content = archive.extractfile(selected).read()
                    destination = "utilities/licenses/" + source["name"] + "/" + notice
                    existing = args.output / destination
                    if existing.exists():
                        if existing.read_bytes() != content:
                            raise ValueError("bootstrap binary notice contradicts its source")
                    else:
                        put(args.output, destination, content, 0o644)
    for source in upstreams:
        put(args.output, source["target"], (args.upstream_cache / source["archive"]).read_bytes(), 0o644)
    config = input_contract(args.output, upstreams)
    with (args.output.parent / "input-config.json").open("x") as output:
        json.dump(config, output, indent=2, sort_keys=True)
        output.write("\n")
    # This is deliberately a bootstrap receipt, not a qualified artifact,
    # input-config signature, RyeOS manifest, import receipt or target binding.
    print(json.dumps({"prepared_inputs": str(args.output), "publisher_image": IMAGE,
                      "production_complete": False, "licenses_complete": False,
                      "input_storage_required": "large_content"}, sort_keys=True))


if __name__ == "__main__":
    main()
