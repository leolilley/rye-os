#!/usr/bin/env python3
"""Publisher-only authoring utilities build; never installed or run by workers.

Run in the digest-pinned publisher image, with verified inputs mounted read-only,
network disabled, and /work private. The output is ordinary external content.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile


HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def run(argv: list[str], cwd: Path, env: dict[str, str], log: Path) -> None:
    with log.open("ab") as stream:
        stream.write(("\n$ " + " ".join(argv) + "\n").encode())
        stream.flush()
        result = subprocess.run(argv, cwd=cwd, env=env, stdout=stream, stderr=stream)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}); inspect {log}: {argv}")


def archive_tree(root: Path, output: Path, epoch: int) -> None:
    with output.open("xb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for path in sorted(root.rglob("*")):
                if path.is_symlink() or not (path.is_file() or path.is_dir()):
                    raise ValueError(f"non-regular delivery member: {path}")
                info = archive.gettarinfo(path, arcname=path.relative_to(root).as_posix())
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = epoch
                info.mode = 0o755 if path.is_dir() or path.stat().st_mode & 0o111 else 0o644
                if path.is_file():
                    with path.open("rb") as data:
                        archive.addfile(info, data)
                else:
                    archive.addfile(info)


def static_elf(path: Path) -> None:
    header = subprocess.check_output(["readelf", "-h", str(path)], text=True)
    program = subprocess.check_output(["readelf", "-l", str(path)], text=True)
    dynamic = subprocess.check_output(["readelf", "-d", str(path)], text=True)
    if "ELF64" not in header or "Advanced Micro Devices X86-64" not in header:
        raise ValueError(f"wrong executable architecture: {path}")
    if "INTERP" in program or "(NEEDED)" in dynamic or "(RPATH)" in dynamic or "(RUNPATH)" in dynamic:
        raise ValueError(f"authoring executable requires a loader/library search: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    lock = json.loads((HERE / "inputs.json").read_text())
    if os.environ.get("RYEOS_AUTHORING_PUBLISHER_IMAGE") != lock["publisher_image"]:
        raise ValueError("use the exact pinned publisher image")
    # Fixed paths and a clean build eliminate host checkout/cache path inputs.
    work = Path("/work/build")
    work.mkdir(parents=True, exist_ok=False)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    tree = work / "tree"
    (tree / "bin").mkdir(parents=True)
    (tree / "licenses").mkdir()
    sources = work / "sources"
    sources.mkdir()
    archive_inputs = work / "corresponding-sources"
    archive_inputs.mkdir()
    for notice in lock["publisher_notices"]:
        selected = Path(notice["path"])
        relative = Path(notice["target"])
        if relative.is_absolute() or ".." in relative.parts or relative.parts[0] != "licenses":
            raise ValueError("publisher notice must have a canonical license target")
        if selected.is_symlink() or not selected.is_file() or digest(selected) != notice["sha256"]:
            raise ValueError(f"pinned publisher notice mismatch: {selected}")
        target = tree / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(selected, target)
        target.chmod(0o644)
        shutil.copyfile(selected, archive_inputs / selected.name)
    for source in lock["sources"]:
        selected = args.cache / source["archive"]
        if selected.is_symlink() or not selected.is_file():
            raise ValueError(f"missing regular source archive: {selected}")
        if selected.stat().st_size != source["bytes"] or digest(selected) != source["sha256"]:
            raise ValueError(f"source identity mismatch: {selected}")
        # Only authenticated, publisher-selected archives are extracted here;
        # no acquisition, package manager, or execution-host discovery occurs.
        subprocess.run(["tar", "--extract", "--file", str(selected), "--no-same-owner",
                        "--no-same-permissions", "--directory", str(sources)], check=True)
        shutil.copyfile(selected, archive_inputs / source["archive"])
    by_name = {source["name"]: source for source in lock["sources"]}
    zig = sources / by_name["zig"]["directory"] / "zig"
    env = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": str(work / "home"), "LC_ALL": "C", "LANG": "C", "TZ": "UTC",
        "SOURCE_DATE_EPOCH": str(lock["source_date_epoch"]), "ZERO_AR_DATE": "1",
        "CC": f"{zig} cc -target x86_64-linux-musl -static",
        "AR": f"{zig} ar", "RANLIB": f"{zig} ranlib",
        "CFLAGS": "-Os -g0 -ffile-prefix-map=/work=/usr/src/authoring -fno-ident",
        "LDFLAGS": "-static -Wl,--build-id=none", "PKG_CONFIG": "/bin/false",
        "ZIG_GLOBAL_CACHE_DIR": str(work / "zig-cache"),
        "ZIG_LOCAL_CACHE_DIR": str(work / "zig-local-cache"),
        "FORCE_UNSAFE_CONFIGURE": "1",
    }
    Path(env["HOME"]).mkdir()
    for source in lock["sources"]:
        name = source["name"]
        if name == "zig":
            continue
        print(f"building {name} {source['version']}", flush=True)
        source_dir = sources / source["directory"]
        log = output / f"{name}.log"
        if name == "git":
            zlib = sources / by_name["zlib"]["directory"]
            options = [f"CC={env['CC']}", f"AR={env['AR']}", "NO_CURL=YesPlease",
                       "NO_EXPAT=YesPlease", "NO_OPENSSL=YesPlease", "NO_GETTEXT=YesPlease",
                       "NO_TCLTK=YesPlease", "NO_PERL=YesPlease", "NO_PYTHON=YesPlease",
                       "NO_ICONV=YesPlease", "NO_REGEX=YesPlease", "NO_RUST=YesPlease",
                       "prefix=/nonexistent/authoring-git", "RUNTIME_PREFIX=YesPlease",
                       f"CFLAGS={env['CFLAGS']} -I{zlib}",
                       f"LDFLAGS={env['LDFLAGS']} -L{zlib}"]
            run(["make", "-j2", *options, "git"], source_dir, env, log)
        elif name == "zlib":
            run(["./configure", "--static"], source_dir, env, log)
            run(["make", "-j2", "libz.a"], source_dir, env, log)
        else:
            # These static target binaries run on this x86_64 Linux publisher.
            # Let configure execute its probes, rather than forcing cross mode
            # and supplying guessed libc answers for runnable target programs.
            flags = ["--prefix=/nonexistent/authoring", "--host=x86_64-linux-musl"]
            flags += source["configure"]
            run(["./configure", *flags], source_dir, env, log)
            # Use upstream's all target: direct executable targets may omit
            # generated gnulib headers. Only the finite programs map is shipped.
            run(["make", "-j2", "all"], source_dir, env, log)
        for installed, built in source["programs"].items():
            binary = source_dir / built
            static_elf(binary)
            target = tree / "bin" / installed
            shutil.copyfile(binary, target)
            subprocess.run(["strip", "--strip-all", str(target)], check=True)
            target.chmod(0o755)
        for notice in source["licenses"]:
            target = tree / "licenses" / name / notice
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_dir / notice, target)
            target.chmod(0o644)
    # Zig's musl/compiler-runtime licensing is part of the linked runtime closure.
    for notice in by_name["zig"]["licenses"]:
        target = tree / "licenses" / "zig" / notice
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(sources / by_name["zig"]["directory"] / notice, target)
        target.chmod(0o644)
    shutil.copyfile(HERE / "inputs.json", tree / "inputs.json")
    shutil.copyfile(HERE / "README.md", tree / "README.md")
    for name in ("produce.py", "inputs.json", "README.md", "probe.sh", "fetch.py", "verify.py",
                 "qualify.py", "test_contract.py", "Dockerfile.probe", "Dockerfile.publisher"):
        shutil.copyfile(HERE / name, archive_inputs / name)
    inventory = {}
    for path in sorted(tree.rglob("*")):
        if path.is_file():
            inventory[path.relative_to(tree).as_posix()] = {"sha256": digest(path), "bytes": path.stat().st_size}
    name = lock["artifact"]
    archive = output / f"{name}.tar.gz"
    archive_tree(tree, archive, lock["source_date_epoch"])
    source_archive = output / f"{name}-sources.tar.gz"
    archive_tree(archive_inputs, source_archive, lock["source_date_epoch"])
    report = {
        "artifact": name, "publisher_image": lock["publisher_image"],
        "archive_sha256": digest(archive), "archive_bytes": archive.stat().st_size,
        "source_archive_sha256": digest(source_archive), "source_archive_bytes": source_archive.stat().st_size,
        "producer_sha256": digest(HERE / "produce.py"), "inventory": inventory,
    }
    (output / "artifact.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "inventory"}), flush=True)


if __name__ == "__main__":
    main()
