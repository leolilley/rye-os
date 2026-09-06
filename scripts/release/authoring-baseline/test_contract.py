#!/usr/bin/env python3
"""Focused publisher checks. No Rust build, daemon, credential or model needed."""

import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from produce import HERE, archive_tree, static_elf
from verify import expected_members, materialize
from qualify import ProbeRefused, run_bounded


class AuthoringContractTests(unittest.TestCase):
    def test_probe_collects_bounded_combined_output(self):
        status, output = run_bounded([sys.executable, "-c", "import sys; print('ok'); sys.stderr.write('diagnostic')"])
        self.assertEqual(status, 0)
        self.assertIn(b"ok", output)
        self.assertIn(b"diagnostic", output)

    def test_probe_refuses_output_overflow_with_bounded_diagnostic(self):
        with self.assertRaisesRegex(ProbeRefused, "diagnostic bound") as refused:
            run_bounded([sys.executable, "-c", "print('x' * 4096)"], maximum_output=1024)
        self.assertEqual(len(refused.exception.output), 1024)

    def test_probe_refuses_a_stalled_process(self):
        with self.assertRaisesRegex(ProbeRefused, "duration bound"):
            run_bounded([sys.executable, "-c", "import time; time.sleep(10)"], timeout=0.1)

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="ryeos-authoring-test-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.lock = json.loads((HERE / "inputs.json").read_text())

    def test_inventory_is_finite_and_contains_the_missing_edit_utility(self):
        members = expected_members(self.lock)
        commands = {path.removeprefix("bin/") for path in members if path.startswith("bin/")}
        self.assertEqual(len(commands), 41)
        self.assertTrue({"sed", "awk", "git", "diff", "patch", "find", "xargs"} <= commands)
        self.assertTrue(commands.isdisjoint({"busybox", "ryeos", "rustc", "cargo", "python", "curl", "bwrap"}))
        self.assertTrue(all(not path.startswith("/") and ".." not in Path(path).parts for path in members))

    def test_inputs_are_exact_and_unique(self):
        names = set()
        for source in self.lock["sources"]:
            self.assertNotIn(source["name"], names)
            names.add(source["name"])
            self.assertRegex(source["sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(source["url"].startswith("https://"))
            self.assertEqual(source["url"].rsplit("/", 1)[1], source["archive"])
            self.assertGreater(source["bytes"], 0)
            self.assertTrue(source["licenses"])
        self.assertRegex(self.lock["publisher_image"], r"^docker.io/library/rust@sha256:[0-9a-f]{64}$")

    def test_canonical_archive_ignores_source_times(self):
        tree = self.root / "tree"
        tree.mkdir()
        (tree / "file").write_bytes(b"exact bytes")
        first, second = self.root / "first.tgz", self.root / "second.tgz"
        archive_tree(tree, first, 123)
        (tree / "file").touch()
        archive_tree(tree, second, 123)
        self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_publisher_rejects_links(self):
        tree = self.root / "tree"
        tree.mkdir()
        (tree / "file").symlink_to("/etc/passwd")
        with self.assertRaisesRegex(ValueError, "non-regular"):
            archive_tree(tree, self.root / "bad.tgz", 123)

    def make_archive(self, entries):
        archive = self.root / "input.tgz"
        with tarfile.open(archive, "w:gz") as result:
            for name, kind in entries:
                member = tarfile.TarInfo(name)
                member.type = kind
                member.mode = 0o755 if kind == tarfile.DIRTYPE else 0o644
                member.mtime = self.lock["source_date_epoch"]
                member.linkname = "../../escape" if kind == tarfile.SYMTYPE else ""
                result.addfile(member, io.BytesIO())
        return archive, hashlib.sha256(archive.read_bytes()).hexdigest()

    def test_verifier_rejects_wrong_checksum_before_materialization(self):
        archive, _ = self.make_archive([])
        destination = self.root / "out"
        with self.assertRaisesRegex(ValueError, "checksum"):
            materialize(archive, "0" * 64, destination)
        self.assertFalse(destination.exists())

    def test_verifier_rejects_missing_inventory(self):
        archive, checksum = self.make_archive([])
        with self.assertRaisesRegex(ValueError, "missing entries"):
            materialize(archive, checksum, self.root / "out")

    def test_verifier_rejects_escape_and_extra_members(self):
        archive, checksum = self.make_archive([("../escape", tarfile.REGTYPE)])
        with self.assertRaisesRegex(ValueError, "unexpected"):
            materialize(archive, checksum, self.root / "out")
        self.assertFalse((self.root / "out").exists())

    def test_verifier_rejects_links(self):
        archive, checksum = self.make_archive([("README.md", tarfile.SYMTYPE)])
        with self.assertRaisesRegex(ValueError, "kind/mode"):
            materialize(archive, checksum, self.root / "out")

    def test_verifier_rejects_duplicate_members(self):
        archive, checksum = self.make_archive([("bin", tarfile.DIRTYPE), ("bin", tarfile.DIRTYPE)])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            materialize(archive, checksum, self.root / "out")

    def test_static_gate_rejects_ambient_loader_and_libraries(self):
        for programs, dynamic in (("INTERP", ""), ("", "(NEEDED)"), ("", "(RUNPATH)"), ("", "(RPATH)")):
            with self.subTest(programs=programs, dynamic=dynamic):
                with patch("produce.subprocess.check_output", side_effect=["ELF64 Advanced Micro Devices X86-64", programs, dynamic]):
                    with self.assertRaisesRegex(ValueError, "loader/library"):
                        static_elf(Path("fixture"))


if __name__ == "__main__":
    unittest.main()
