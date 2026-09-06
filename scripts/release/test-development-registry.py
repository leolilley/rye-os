"""Finite input acquisition checks; no network, Cargo, or node operations."""

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch

import yaml


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("registry_inputs", Path(__file__).with_name("fetch-development-registry.py"))
owner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(owner)


class RegistryInputTests(unittest.TestCase):
    def setUp(self):
        self.config = yaml.safe_load((ROOT / ".ai/config/development/ryeos/registry-acquisition.yaml").read_text())
        self.archive = b"verified opaque crate archive; unpacking belongs to Cargo"
        self.checksum = hashlib.sha256(self.archive).hexdigest()
        self.lock = (f'version = 4\n[[package]]\nname = "example"\nversion = "1.0.0"\n'
                     f'source = "{self.config["registry_source"]}"\nchecksum = "{self.checksum}"\n').encode()
        self.row = {"name": "example", "vers": "1.0.0", "cksum": self.checksum,
                    "deps": [], "features": {}, "yanked": False}

    def fetch(self, url, maximum):
        return self.archive if url.endswith(".crate") else json.dumps(self.row).encode() + b"\n"

    def test_writes_public_local_registry_not_private_cargo_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "inputs"
            owner.acquire(self.lock, self.config, output, self.fetch)
            self.assertEqual((output / "example-1.0.0.crate").read_bytes(), self.archive)
            self.assertEqual(json.loads((output / "index/ex/am/example").read_bytes()), self.row)
            receipt = json.loads((output / "acquisition.json").read_bytes())
            self.assertEqual(receipt["lock_sha256"], hashlib.sha256(self.lock).hexdigest())
            self.assertEqual(sorted(p.name for p in output.iterdir()),
                             ["acquisition.json", "example-1.0.0.crate", "index"])
            with self.assertRaisesRegex(ValueError, "already exists"):
                owner.acquire(self.lock, self.config, output, self.fetch)

    def test_checks_both_index_and_archive_against_lock_before_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "inputs"
            self.row["cksum"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "index does not match"):
                owner.acquire(self.lock, self.config, output, self.fetch)
            self.assertFalse(output.exists())
            self.row["cksum"] = self.checksum
            self.archive = b"substitution"
            with self.assertRaisesRegex(ValueError, "archive does not match"):
                owner.acquire(self.lock, self.config, output, self.fetch)
            self.assertFalse(output.exists())
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_rejects_other_sources_and_unselected_urls(self):
        with tempfile.TemporaryDirectory() as directory:
            lock = self.lock.replace(self.config["registry_source"].encode(), b"git+https://example.org/source")
            with self.assertRaisesRegex(ValueError, "unsupported or unpinned"):
                owner.acquire(lock, self.config, Path(directory) / "inputs", self.fetch)
        for url in ("http://index.crates.io/a", "https://user:secret@index.crates.io/a",
                    "https://index.crates.io:444/a", "https://elsewhere.invalid/a"):
            with self.assertRaises(ValueError):
                owner.validate_url(url, self.config["allowed_https_hosts"])

    def test_fetch_has_independent_deadline_and_no_ambient_curl_configuration(self):
        with patch.object(owner.time, "monotonic", return_value=100):
            fetch = owner.Fetcher(self.config)
        fetch.checked_curl = True
        with patch.object(owner.time, "monotonic", return_value=1895):
            with patch.object(owner.subprocess, "run", side_effect=subprocess.TimeoutExpired("curl", 5)) as run:
                with self.assertRaises(subprocess.TimeoutExpired):
                    fetch("https://index.crates.io/ex/am/example", 100)
                args, kwargs = run.call_args
                self.assertEqual(kwargs["timeout"], 5)
                self.assertEqual(args[0][:2], ["curl", "--disable"])
                self.assertNotIn("--location", args[0])
                self.assertIn("--noproxy", args[0])
        with patch.object(owner.time, "monotonic", return_value=1900):
            with patch.object(owner.subprocess, "run") as run:
                with self.assertRaisesRegex(ValueError, "lifetime exhausted"):
                    fetch("https://index.crates.io/ex/am/example", 100)
                run.assert_not_called()
        with patch.object(owner.time, "monotonic", return_value=100):
            with patch.object(owner.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b"", b"")) as run:
                fetch("https://index.crates.io/a", 100)
                self.assertEqual(run.call_args.kwargs["timeout"], 60)

    def test_fetch_accounts_for_aggregate_bytes(self):
        fetch = owner.Fetcher(self.config)
        fetch.checked_curl = True
        fetch.config["limits"]["max_total_download_bytes"] = 2
        with patch.object(owner.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b"ab", b"")):
            self.assertEqual(fetch("https://index.crates.io/a", 100), b"ab")
        with patch.object(owner.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "byte bound exhausted"):
                fetch("https://index.crates.io/b", 100)
            run.assert_not_called()

    def test_fetch_requires_streaming_download_byte_bound_capability(self):
        fetch = owner.Fetcher(self.config)
        with patch.object(owner.subprocess, "run", return_value=subprocess.CompletedProcess(
                [], 0, b"curl 8.3.0 (test)\n", b"")) as run:
            with self.assertRaisesRegex(ValueError, "curl >= 8.4.0"):
                fetch("https://index.crates.io/a", 100)
            self.assertEqual(run.call_count, 1)

    def test_package_bounds_and_public_index_path_rules(self):
        expected = {"a": "1/a", "ab": "2/ab", "abc": "3/a/abc", "AbCd": "ab/cd/abcd"}
        for name, path in expected.items():
            self.assertEqual(owner.index_member(name), path)
        self.config["limits"]["max_packages"] = 0
        with self.assertRaisesRegex(ValueError, "positive integers"):
            owner.validate_config(self.config)


if __name__ == "__main__":
    unittest.main()
