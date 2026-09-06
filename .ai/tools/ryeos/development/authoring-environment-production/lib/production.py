# ryeos:signed:2026-09-06T03:45:22Z:079c5c7ac30b9ada49b740f1c1ca388257635d5141936fcc6d7d12689fd2d7ad:6do8rkwaNeVhCtPdEIQxVOh2c8zXTdt8CLDd93NVn97BCxuge9fHeh1qsUzN/MevIawddyXBIiGWPblZH8xJCw==:741a8bc609b398aaec0685e5aefb682faf5129a66bd192f888d23bb642c18eea
"""Finite, offline authoring-environment assembly; no acquisition or publication.

RyeOS owns capture, namespaces, result snapshots and import/binding. This code
only consumes the admitted input tree and writes its private project output.
The existing Python payload supplies the interpreter; selected upstream tools
inspect and relocate ELF files. There is no host PATH or custom ELF rewriter.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys


SCHEMA = "ryeos.development.authoring-environment-inputs.v1"
INPUT_ROOT = Path("/ryeos/realizations/authoring-inputs")
RUNTIME_ROOT = "/ryeos/realizations/authoring-tools"
OUTPUT = PurePosixPath("products/authoring-environment")
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_ENTRIES = 1024
MAX_DIAGNOSTIC_BYTES = 8 * 1024 * 1024
REQUIRED_COMMANDS = frozenset("""
awk basename cat chmod cmp cp cut date diff dirname env find git grep head ln ls
mkdir mktemp mv patch printf pwd readlink realpath rg rm rmdir sed sha256sum sleep
sort stat tail tee test timeout touch tr uniq wc xargs zsh
""".split())
ELF_TOOLS = {"loader": "elf/lib/ld-linux-x86-64.so.2",
             "readelf": "elf/bin/readelf", "patchelf": "elf/bin/patchelf"}
RUNTIME_LOADER = "environment/lib/ld-linux-x86-64.so.2"


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def relative(value: str) -> PurePosixPath:
    if not isinstance(value, str) or len(value) > 1024:
        raise ValueError("invalid member path")
    parts = value.split("/")
    if not parts or len(parts) > 32 or any(
        part in ("", ".", "..") or not re.fullmatch(r"[A-Za-z0-9_.+-]+", part)
        for part in parts
    ):
        raise ValueError(f"noncanonical member path: {value}")
    return PurePosixPath(value)


def ordinary_member(root: Path, member: str, *, directory: bool = False) -> Path:
    path = root
    if not stat.S_ISDIR(path.lstat().st_mode):
        raise ValueError("input/output root must be an ordinary directory")
    parts = relative(member).parts
    for index, part in enumerate(parts):
        path = path / part
        mode = path.lstat().st_mode
        wanted = stat.S_ISDIR if directory or index < len(parts) - 1 else stat.S_ISREG
        if not wanted(mode):
            raise ValueError(f"member is not an ordinary {'directory' if directory else 'file'}: {member}")
    return path


def validate_config(config: dict) -> None:
    keys = {"category", "name", "version", "schema", "source_date_epoch", "inputs",
            "files", "relocate", "provenance"}
    if not isinstance(config, dict) or set(config) != keys or config["schema"] != SCHEMA:
        raise ValueError("unsupported or incomplete authoring input contract")
    if (config["category"] != "development/ryeos" or
            config["name"] != "authoring-environment-inputs" or config["version"] != "1.0.0"):
        raise ValueError("unexpected authoring input identity")
    if type(config["source_date_epoch"]) is not int or not 0 <= config["source_date_epoch"] <= 4_102_444_800:
        raise ValueError("invalid source normalization epoch")
    inputs, files = config["inputs"], config["files"]
    if not isinstance(inputs, dict) or not isinstance(files, dict) or not 1 <= len(inputs) <= MAX_ENTRIES:
        raise ValueError("invalid finite input inventory")
    total = 0
    for name, identity in inputs.items():
        relative(name)
        if not isinstance(identity, dict) or set(identity) != {"bytes", "sha256", "mode"}:
            raise ValueError("incomplete file identity")
        if (type(identity["bytes"]) is not int or not 0 <= identity["bytes"] <= MAX_FILE_BYTES or
                type(identity["mode"]) is not int or identity["mode"] not in (0o644, 0o755) or
                not isinstance(identity["sha256"], str) or
                not re.fullmatch(r"[0-9a-f]{64}", identity["sha256"])):
            raise ValueError("invalid file identity or bounds")
        total += identity["bytes"]
    if total > MAX_TOTAL_BYTES or not 1 <= len(files) <= MAX_ENTRIES:
        raise ValueError("authoring input inventory exceeds its bound")
    for target, source in files.items():
        parts = relative(target).parts
        if ((parts[0] == "environment" and len(parts) >= 3 and parts[1] in ("bin", "lib", "licenses")) or
                (parts[0] == "corresponding-sources" and len(parts) >= 2)):
            if source not in inputs:
                raise ValueError("output selects an undeclared input")
        else:
            raise ValueError("output is outside the finite artifact layout")
    if sum(inputs[source]["bytes"] for source in files.values()) > MAX_TOTAL_BYTES:
        raise ValueError("selected outputs exceed the artifact byte bound")
    commands = {str(PurePosixPath(path).relative_to("environment/bin"))
                for path in files if path.startswith("environment/bin/")}
    if commands != REQUIRED_COMMANDS:
        raise ValueError("authoring command inventory is not the supported exact set")
    if RUNTIME_LOADER not in files:
        raise ValueError("the runtime interpreter must be included in the artifact")
    executable_outputs = {f"environment/bin/{name}" for name in REQUIRED_COMMANDS} | {RUNTIME_LOADER}
    if any(inputs[files[path]]["mode"] != 0o755 for path in executable_outputs):
        raise ValueError("commands and runtime interpreter must have executable mode")
    if not any(path.startswith("corresponding-sources/") for path in files):
        raise ValueError("corresponding source delivery is required")
    if not all(value in inputs for value in ELF_TOOLS.values()):
        raise ValueError("selected ELF authoring tools are missing")
    if any(inputs[path]["mode"] != 0o755 for path in ELF_TOOLS.values()):
        raise ValueError("selected ELF authoring tools must have executable mode")
    for path in files:
        if any(parent.as_posix() in files for parent in PurePosixPath(path).parents):
            raise ValueError("output file/directory collision")
    if (not isinstance(config["relocate"], list) or
            config["relocate"] != sorted(set(config["relocate"])) or
            "environment/bin/zsh" not in config["relocate"]):
        raise ValueError("relocation inventory must be exact, sorted and include the selected shell")
    for member in config["relocate"]:
        if member not in files or not member.startswith(("environment/bin/", "environment/lib/")):
            raise ValueError("relocation target is not an admitted ELF input")
        if member == "environment/lib/ld-linux-x86-64.so.2":
            raise ValueError("the loader itself must retain upstream bytes")
    if not isinstance(config["provenance"], dict) or not config["provenance"]:
        raise ValueError("bootstrap and upstream source provenance is required")


def inventory(root: Path) -> dict:
    if not stat.S_ISDIR(root.lstat().st_mode):
        raise ValueError("artifact is not an ordinary directory")
    result, total = {}, 0
    pending = [(root, 0)]
    visited = 0
    while pending:
        directory, depth = pending.pop()
        if depth > 32:
            raise ValueError("artifact depth limit exceeded")
        for path in sorted(directory.iterdir()):
            visited += 1
            if visited > MAX_ENTRIES:
                raise ValueError("artifact entry limit exceeded")
            info = path.lstat()
            name = path.relative_to(root).as_posix()
            relative(name)
            if stat.S_ISDIR(info.st_mode):
                pending.append((path, depth + 1))
            elif stat.S_ISREG(info.st_mode):
                total += info.st_size
                if info.st_size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
                    raise ValueError("artifact byte limit exceeded")
                result[name] = {"sha256": sha256(path), "bytes": info.st_size,
                                "mode": stat.S_IMODE(info.st_mode)}
            else:
                raise ValueError(f"unselected link or special artifact member: {name}")
    return result


def checked_inputs(root: Path, config: dict) -> None:
    validate_config(config)
    if inventory(root) != config["inputs"]:
        raise ValueError("admitted source bytes or modes differ from the authored input inventory")


class ElfTools:
    """The selected upstream programs, invoked through their exact loader."""

    def __init__(self, inputs: Path):
        self.inputs = inputs

    def run(self, name: str, *args: str) -> str:
        if name not in ("readelf", "patchelf"):
            raise ValueError("not a production ELF operation")
        command = [str(ordinary_member(self.inputs, ELF_TOOLS["loader"])), "--inhibit-cache",
                   "--library-path", str(ordinary_member(self.inputs, "elf/lib", directory=True)),
                   str(ordinary_member(self.inputs, ELF_TOOLS[name])), *map(str, args)]
        # The enclosing RyeOS execution owns the process-group/time/resource
        # ceiling. This reader additionally bounds one upstream diagnostic.
        with subprocess.Popen(command, env={"LANG": "C", "LC_ALL": "C", "PATH": ""},
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT) as process:
            try:
                output = process.stdout.read(MAX_DIAGNOSTIC_BYTES + 1)
                if len(output) > MAX_DIAGNOSTIC_BYTES:
                    raise ValueError("upstream ELF diagnostic exceeds its bound")
                status = process.wait(timeout=30)
                if status:
                    raise ValueError(f"selected {name} refused ({status}): {output[-2048:].decode(errors='replace')}")
                return output.decode("utf-8", errors="strict")
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()

    def facts(self, path: Path) -> dict:
        header = self.run("readelf", "-W", "-h", str(path))
        if "ELF64" not in header or "Advanced Micro Devices X86-64" not in header:
            raise ValueError("artifact executable is not ELF64 x86_64")
        dynamic = self.run("readelf", "-W", "-d", str(path))
        program = self.run("readelf", "-W", "-l", str(path))
        interpreter = re.findall(r"Requesting program interpreter: ([^\]]+)\]", program)
        return {"dynamic": "Dynamic section" in dynamic,
                "interpreter": interpreter,
                "needed": re.findall(r"Shared library: \[([^\]]+)\]", dynamic),
                "runpath": re.findall(r"Library runpath: \[([^\]]*)\]", dynamic),
                "rpath": "(RPATH)" in dynamic, "nodeflib": "NODEFLIB" in dynamic}

    def symbols(self, path: Path) -> tuple:
        # Same upstream readelf projections as the existing Stage-0 producer:
        # compare section ownership and FUNC coordinates, not ELF byte offsets
        # invented by a second binary rewriter.
        sections = dict(re.findall(r"^\s*\[\s*(\d+)\]\s+(\S+)\s", self.run(
            "readelf", "-W", "--section-headers", str(path)), re.MULTILINE))
        owners, functions = [], []
        for line in self.run("readelf", "-W", "--symbols", str(path)).splitlines():
            row = line.split()
            if not row or not re.fullmatch(r"\d+:", row[0]):
                continue
            if len(row) < 7:
                raise ValueError("malformed upstream symbol row")
            index = row[6]
            if index.isdecimal():
                if index not in sections:
                    raise ValueError("upstream symbol names an absent section")
                index = sections[index]
            name = row[7] if len(row) > 7 else ""
            owners.append((*row[3:6], index, name))
            if row[3] == "FUNC":
                functions.append((*row[1:6], name))
        return sorted(owners), sorted(functions)


def check_closure(environment: Path, files: dict, tools: ElfTools, relocated: set[str]) -> None:
    interpreter = ordinary_member(environment, RUNTIME_LOADER.removeprefix("environment/"))
    if stat.S_IMODE(interpreter.stat().st_mode) != 0o755:
        raise ValueError("runtime interpreter is not executable")
    loader_facts = tools.facts(interpreter)
    if loader_facts["interpreter"] or loader_facts["needed"]:
        raise ValueError("runtime interpreter must be independently loadable")
    for member in sorted(files):
        if not member.startswith(("environment/bin/", "environment/lib/")):
            continue
        local = member.removeprefix("environment/")
        path = ordinary_member(environment, local)
        if local.startswith("bin/") and stat.S_IMODE(path.stat().st_mode) != 0o755:
            raise ValueError(f"command is not executable: {local}")
        facts = tools.facts(path)
        loader = local == "lib/ld-linux-x86-64.so.2"
        if facts["interpreter"] not in ([], [RUNTIME_ROOT + "/lib/ld-linux-x86-64.so.2"]):
            raise ValueError(f"unclosed interpreter: {local}")
        # Static PIE executables also have a dynamic section for their own
        # relocations. Only interpreter/library edges require our runtime;
        # do not rewrite an otherwise self-contained upstream executable.
        needs_runtime = bool(facts["interpreter"] or facts["needed"])
        if needs_runtime and not loader:
            if (member not in relocated or facts["runpath"] != [RUNTIME_ROOT + "/lib"] or
                    facts["rpath"] or not facts["nodeflib"]):
                raise ValueError(f"unclosed library search: {local}")
        elif member in relocated:
            raise ValueError(f"unexpected static relocation target: {local}")
        elif facts["runpath"] or facts["rpath"]:
            raise ValueError(f"unexpected search path on a self-contained ELF: {local}")
        for needed in facts["needed"]:
            if "/" in needed or not re.fullmatch(r"[A-Za-z0-9_+.-]+", needed):
                raise ValueError("unsafe library dependency")
            library = ordinary_member(environment, "lib/" + needed)
            with library.open("rb") as content:
                if content.read(4) != b"\x7fELF":
                    raise ValueError("library dependency names non-ELF data")


def assemble(inputs: Path, destination: Path, config: dict, *, tools=None) -> dict:
    checked_inputs(inputs, config)
    if destination.exists() or destination.is_symlink():
        raise ValueError("assembly destination already exists")
    destination.mkdir(mode=0o700)
    tools = tools or ElfTools(inputs)
    transformations = {}
    for target, source in sorted(config["files"].items()):
        selected = ordinary_member(inputs, source)
        output = destination.joinpath(*relative(target).parts)
        output.parent.mkdir(parents=True, exist_ok=True)
        with selected.open("rb") as reader, output.open("xb") as writer:
            shutil.copyfileobj(reader, writer, length=1024 * 1024)
        output.chmod(config["inputs"][source]["mode"])
    for member in config["relocate"]:
        path = ordinary_member(destination, member)
        before, symbols = sha256(path), tools.symbols(path)
        facts = tools.facts(path)
        if not facts["dynamic"] or not (facts["interpreter"] or facts["needed"]):
            raise ValueError("only declared dynamic ELF inputs may be relocated")
        if facts["interpreter"]:
            tools.run("patchelf", "--no-sort", "--set-interpreter",
                      RUNTIME_ROOT + "/lib/ld-linux-x86-64.so.2", str(path))
        tools.run("patchelf", "--no-sort", "--set-rpath", RUNTIME_ROOT + "/lib",
                  "--no-default-lib", str(path))
        if tools.symbols(path) != symbols:
            raise ValueError(f"ELF symbol ownership or function coordinates changed: {member}")
        transformations[member] = {"before": before, "after": sha256(path)}
    check_closure(destination / "environment", config["files"], tools, set(transformations))
    provenance = {"schema": 1, "input_contract_sha256": hashlib.sha256(canonical_json(config)).hexdigest(),
                  "runtime_mount": RUNTIME_ROOT, "transformations": transformations,
                  "sources": config["provenance"]}
    provenance_path = destination / "provenance.json"
    provenance_path.write_bytes(canonical_json(provenance))
    provenance_path.chmod(0o644)
    for path in sorted(destination.rglob("*")):
        if path.is_dir():
            path.chmod(0o755)
        os.utime(path, (config["source_date_epoch"], config["source_date_epoch"]))
    files = inventory(destination)
    index_path = destination / "inventory.json"
    index_path.write_bytes(canonical_json(files))
    index_path.chmod(0o644)
    os.utime(index_path, (config["source_date_epoch"], config["source_date_epoch"]))
    return receipt(destination)


def receipt(destination: Path) -> dict:
    files = inventory(destination)
    return {"inventory_sha256": hashlib.sha256(canonical_json(files)).hexdigest(),
            "files": len(files), "bytes": sum(value["bytes"] for value in files.values())}


def run_operation(operation: str) -> None:
    if operation not in ("assemble", "verify"):
        raise ValueError("unsupported production operation")
    if len(sys.argv) != 3 or sys.argv[1] != "--project-path":
        raise ValueError("missing admitted project context")
    project = Path(sys.argv[2])
    if not project.is_absolute() or not stat.S_ISDIR(project.lstat().st_mode):
        raise ValueError("invalid admitted project context")
    raw = sys.stdin.buffer.read(262145)
    if len(raw) > 262144:
        raise ValueError("production parameters exceed their bound")
    request = json.loads(raw)
    config = request.get("resolved_config") if isinstance(request, dict) else None
    validate_config(config)
    parent = project / "products"
    if not parent.exists():
        parent.mkdir(mode=0o700)
    ordinary_member(project, "products", directory=True)
    destination = project.joinpath(*OUTPUT.parts)
    if operation == "assemble" and (destination.exists() or destination.is_symlink()):
        raise ValueError("authoring output already exists; use a fresh production workspace")
    staging = parent / ("authoring-assembly" if operation == "assemble" else "authoring-verification")
    result = assemble(INPUT_ROOT, staging, config)
    if operation == "assemble":
        # Fail closed on reuse. No existing successful output is overwritten.
        if destination.exists() or destination.is_symlink():
            raise ValueError("authoring output already exists; use a fresh production workspace")
        staging.rename(destination)
    elif operation == "verify":
        actual = receipt(ordinary_member(project, OUTPUT.as_posix(), directory=True))
        if actual != result:
            raise ValueError("authoring output differs from independent reproduction")
    else:
        raise ValueError("unsupported production operation")
    print(json.dumps({"ok": True, "operation": operation, "output_path": OUTPUT.as_posix(),
                      **result, "binding_published": False}, sort_keys=True))
