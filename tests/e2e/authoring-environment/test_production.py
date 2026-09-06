"""Focused source-level checks; these do not claim namespace/worker acceptance."""

import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
OWNER = ROOT / ".ai/tools/ryeos/development/authoring-environment-production"
SPEC = importlib.util.spec_from_file_location("authoring_production", OWNER / "lib/production.py")
production = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(production)


class FakeElfTools:
    """Deliberately synthetic readelf/patchelf responses, not an ELF execution."""

    def __init__(self, *, corrupt_symbols=False):
        self.changed = set()
        self.corrupt_symbols = corrupt_symbols
        self.calls = []

    def symbols(self, path):
        if self.corrupt_symbols and path in self.changed:
            return ([], [("moved",)])
        return ([], [])

    def facts(self, path):
        shell = path.name == "zsh"
        fixed = path in self.changed
        return {"dynamic": shell, "interpreter": [] if not shell else [
                    production.RUNTIME_ROOT + "/lib/ld-linux-x86-64.so.2" if fixed else "/lib64/ld-linux-x86-64.so.2"],
                "needed": [], "runpath": [production.RUNTIME_ROOT + "/lib"] if fixed else [],
                "nodeflib": fixed, "rpath": False}

    def run(self, name, *args):
        self.calls.append((name, args))
        path = Path(args[-1])
        path.write_bytes(path.read_bytes() + b"\nnormalized relocation")
        self.changed.add(path)
        return ""


class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="ryeos-authoring-production-test-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        self.config = {
            "category": "development/ryeos", "name": "authoring-environment-inputs",
            "version": "1.0.0", "schema": production.SCHEMA, "source_date_epoch": 123,
            "inputs": {}, "files": {}, "relocate": ["environment/bin/zsh"],
            "provenance": {"test": "synthetic bytes; not an executable artifact"},
        }
        for command in production.REQUIRED_COMMANDS:
            self.add_file(f"utilities/{command}", f"environment/bin/{command}", mode=0o755)
        self.add_file("licenses/NOTICE", "environment/licenses/NOTICE")
        self.add_file("sources/upstream.tar", "corresponding-sources/upstream.tar")
        for name in production.ELF_TOOLS.values():
            self.add_file(name, mode=0o755)
        self.add_file("lib/ld-linux-x86-64.so.2", "environment/lib/ld-linux-x86-64.so.2", mode=0o755)

    def add_file(self, source, target=None, *, mode=0o644, data=b"synthetic fixture"):
        path = self.inputs / source
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(mode)
        self.config["inputs"][source] = {"sha256": production.sha256(path), "bytes": len(data), "mode": mode}
        if target:
            self.config["files"][target] = source

    def assemble(self, name="output", **kwargs):
        return production.assemble(self.inputs, self.root / name, self.config,
                                   tools=FakeElfTools(**kwargs))

    def test_inventory_requires_the_exact_supported_commands(self):
        production.checked_inputs(self.inputs, self.config)
        self.assertEqual(len(production.REQUIRED_COMMANDS), 43)
        del self.config["files"]["environment/bin/sed"]
        with self.assertRaisesRegex(ValueError, "command inventory"):
            production.validate_config(self.config)

    def test_repeat_production_has_equal_inventory_and_preserves_inputs(self):
        before = production.inventory(self.inputs)
        first = self.assemble("first")
        (self.inputs / "utilities/cat").touch()
        second = self.assemble("second")
        self.assertEqual(first, second)
        self.assertEqual(before, production.inventory(self.inputs))
        self.assertTrue((self.root / "first/corresponding-sources/upstream.tar").is_file())

    def test_corrupt_input_refuses_before_any_output_or_tool_execution(self):
        (self.inputs / "utilities/sed").write_bytes(b"drift")
        tools = FakeElfTools()
        with self.assertRaisesRegex(ValueError, "source bytes or modes"):
            production.assemble(self.inputs, self.root / "out", self.config, tools=tools)
        self.assertFalse((self.root / "out").exists())
        self.assertEqual(tools.calls, [])

    def test_extra_input_and_mode_change_are_identity_changes(self):
        self.add_file("extra")
        self.config["inputs"].pop("extra")
        with self.assertRaises(ValueError):
            production.checked_inputs(self.inputs, self.config)
        (self.inputs / "extra").unlink()
        (self.inputs / "utilities/cat").chmod(0o644)
        with self.assertRaises(ValueError):
            production.checked_inputs(self.inputs, self.config)

    def test_no_output_overwrite(self):
        self.assemble()
        before = production.inventory(self.root / "output")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.assemble()
        self.assertEqual(before, production.inventory(self.root / "output"))

    def test_symbol_changes_fail_before_inventory_success(self):
        with self.assertRaisesRegex(ValueError, "symbol ownership"):
            self.assemble(corrupt_symbols=True)
        self.assertFalse((self.root / "output/inventory.json").exists())

    def test_unclosed_interpreter_or_dependency_refuses(self):
        self.assemble()
        class BadTools(FakeElfTools):
            def facts(self, path):
                result = super().facts(path)
                if path.name == "cat":
                    result["interpreter"] = ["/usr/lib/host-loader"]
                return result
        with self.assertRaisesRegex(ValueError, "unclosed interpreter"):
            production.check_closure(self.root / "output/environment", self.config["files"],
                                     BadTools(), set())

    def test_selected_file_links_and_ancestor_links_are_refused(self):
        selected = self.inputs / "utilities/cat"
        selected.unlink()
        selected.symlink_to("sed")
        with self.assertRaises(ValueError):
            production.checked_inputs(self.inputs, self.config)
        with self.assertRaises(ValueError):
            production.ordinary_member(self.inputs, "utilities/cat")
        self.inputs.rename(self.root / "retained")
        self.inputs.symlink_to(self.root / "retained", target_is_directory=True)
        with self.assertRaises(ValueError):
            production.inventory(self.inputs)

    def test_paths_do_not_normalize_or_escape(self):
        for path in ("/etc/passwd", "../file", "a//b", "a/./b", "a/../b", "a/", "", "a:b"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                production.relative(path)

    def test_unknown_config_fields_and_arbitrary_output_layout_refuse(self):
        changed = copy.deepcopy(self.config)
        changed["command"] = "/bin/sh"
        with self.assertRaises(ValueError):
            production.validate_config(changed)
        self.config["files"]["../../escape"] = "utilities/cat"
        with self.assertRaises(ValueError):
            production.validate_config(self.config)

    def test_missing_sources_or_transformer_is_not_qualified(self):
        changed = copy.deepcopy(self.config)
        del changed["files"]["corresponding-sources/upstream.tar"]
        with self.assertRaisesRegex(ValueError, "corresponding source"):
            production.validate_config(changed)
        del self.config["inputs"][production.ELF_TOOLS["patchelf"]]
        with self.assertRaisesRegex(ValueError, "ELF authoring tools"):
            production.validate_config(self.config)

    def test_payload_bounds_apply_before_copy(self):
        self.config["inputs"]["utilities/cat"]["bytes"] = production.MAX_FILE_BYTES + 1
        with self.assertRaises(ValueError):
            self.assemble()
        self.assertFalse((self.root / "output").exists())

    def test_nonexecutable_commands_and_loaders_refuse_before_assembly(self):
        for source in ("utilities/sed", "lib/ld-linux-x86-64.so.2", production.ELF_TOOLS["loader"]):
            with self.subTest(source=source):
                config = copy.deepcopy(self.config)
                config["inputs"][source]["mode"] = 0o644
                with self.assertRaisesRegex(ValueError, "executable mode"):
                    production.validate_config(config)
        self.assertFalse((self.root / "output").exists())

    def test_loader_is_required_independently_of_needed_libraries(self):
        config = copy.deepcopy(self.config)
        del config["files"][production.RUNTIME_LOADER]
        with self.assertRaisesRegex(ValueError, "interpreter must be included"):
            production.validate_config(config)
        self.assemble()
        (self.root / "output/environment/lib/ld-linux-x86-64.so.2").unlink()
        with self.assertRaises(FileNotFoundError):
            production.check_closure(self.root / "output/environment", self.config["files"],
                                     FakeElfTools(), set())

    def test_loader_cannot_itself_depend_on_another_loader(self):
        class DependentLoader(FakeElfTools):
            def facts(self, path):
                result = super().facts(path)
                if path.name == "ld-linux-x86-64.so.2":
                    result["needed"] = ["libc.so.6"]
                return result
        with self.assertRaisesRegex(ValueError, "independently loadable"):
            production.assemble(self.inputs, self.root / "output", self.config,
                                tools=DependentLoader())

    def test_static_pie_is_not_confused_with_external_runtime_dependencies(self):
        class StaticPieTools(FakeElfTools):
            def facts(self, path):
                result = super().facts(path)
                if path.name == "rg":
                    result["dynamic"] = True
                return result
        before = production.sha256(self.inputs / "utilities/rg")
        production.assemble(self.inputs, self.root / "output", self.config, tools=StaticPieTools())
        self.assertEqual(before, production.sha256(self.root / "output/environment/bin/rg"))
        self.config["relocate"] = ["environment/bin/rg", "environment/bin/zsh"]
        with self.assertRaisesRegex(ValueError, "only declared dynamic ELF"):
            production.assemble(self.inputs, self.root / "bad", self.config, tools=StaticPieTools())

    def test_changed_output_cannot_pass_independent_comparison(self):
        first = self.assemble()
        (self.root / "output/environment/bin/sed").write_bytes(b"modified candidate")
        second = self.assemble("verification")
        self.assertEqual(first, second)
        self.assertNotEqual(production.receipt(self.root / "output"), second)

    def test_operation_and_runtime_contracts_do_not_request_callbacks_or_host_tools(self):
        for name in ("assemble.py", "verify.py"):
            source = (OWNER / name).read_text()
            self.assertIn("effects: live", source)
            self.assertIn("filesystem_authority: captured_execution", source)
            self.assertIn("network_authority: isolated", source)
            self.assertIn("protocol:ryeos/core/opaque", source)
            self.assertIn("800d4969489634cc", source)
            self.assertIn("cc090b3d53dd41c0", source)
            self.assertNotIn("mode: captured", source)
            self.assertNotIn("locator:", source)
            self.assertNotIn("shared_exclusive", source)
        runtime = (OWNER / "runtime.yaml").read_text()
        self.assertIn("source_scope:", runtime)
        self.assertIn("RYEOS_VERIFIED_CODE_MAP", runtime)
        self.assertIn("realization:producer-python/lib/ld-musl-x86_64.so.1", runtime)
        self.assertNotIn("local_binary", runtime)


if __name__ == "__main__":
    unittest.main()
