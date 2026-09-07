#!/usr/bin/env python3
"""Data contracts for the explicit authoring worker/environment composition."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tomllib
import unittest

import yaml

BUNDLE = Path(__file__).resolve().parent
REPOSITORY = BUNDLE.parent.parent
SOURCE = BUNDLE / ".ai/workers/codex/lib/hosted"
AUTHORING_E2E = REPOSITORY / "tests/e2e/authoring-environment"


def load(relative):
    return yaml.safe_load((BUNDLE / relative).read_text())


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class AuthoringEnvironmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.environment = load(".ai/config/codex/environments/authoring.yaml")
        cls.default = load(".ai/config/codex/environments/default.yaml")
        cls.worker = load(".ai/workers/codex/hosted-authoring.yaml")
        cls.default_worker = load(".ai/workers/codex/hosted.yaml")
        cls.selection = json.loads((AUTHORING_E2E / "selection.json").read_text())

    def test_default_and_login_remain_minimal(self):
        self.assertEqual([item["id"] for item in self.default["external_content"]], ["command-tools"])
        self.assertEqual(self.default["configuration"]["process_environment"], {})
        self.assertNotIn("authoring", json.dumps(load(".ai/worker-executions/codex/login.yaml")))
        self.assertEqual(self.default["worker_ref"], "worker:codex/hosted")

    def test_explicit_worker_uses_existing_environment_contract(self):
        self.assertEqual(self.environment["schema"], "ryeos.worker_environment.v4")
        self.assertEqual(self.environment["worker_ref"], "worker:codex/hosted-authoring")
        for key in ("credential_requirement", "portable_state_contract", "workload_client"):
            self.assertEqual(self.environment[key], self.default[key])
        self.assertIsNone(self.environment["workload_client"])

    def test_one_runtime_tree_and_descriptor_search(self):
        declarations = self.environment["external_content"]
        self.assertEqual(len(declarations), 1)
        content = declarations[0]
        for key, value in {"id": "authoring-tools", "kind": "tree", "mode": "pinned",
                           "mount_root": "execution_runtime", "mount": "authoring-tools"}.items():
            self.assertEqual(content[key], value)
        self.assertNotIn("locator", content)
        self.assertEqual(content["digest"], self.selection["expected_manifests"]["environment"])
        self.assertEqual(self.environment["configuration"]["executable_search"], [
            {"realization_id": "authoring-tools", "relative_directory": "bin"}
        ])

    def test_worker_changes_only_entry_shell_and_captured_filesystem_ceiling(self):
        actual, original = copy.deepcopy(self.worker), copy.deepcopy(self.default_worker)
        self.assertEqual(actual.pop("filesystem_authority"), "captured_execution")
        self.assertNotIn("filesystem_authority", original)
        for item in (actual, original):
            for metadata in ("version", "description"):
                item.pop(metadata)
            item["source"].pop("entry")
        shell = next(item for item in actual["external_content"] if item["id"] == "codex-zsh")
        upstream_shell = next(item for item in original["external_content"] if item["id"] == "codex-zsh")
        self.assertEqual(shell["digest"], self.selection["expected_manifests"]["shell_file"])
        self.assertNotEqual(shell["digest"], upstream_shell["digest"])
        for resource in (shell, upstream_shell):
            resource.pop("digest")
            resource.pop("metadata_hint")
        self.assertEqual(actual, original)

    def test_worker_kind_admits_the_optional_filesystem_narrowing(self):
        kind = yaml.safe_load((REPOSITORY /
            "bundles/core/.ai/node/engine/kinds/worker/worker.kind-schema.yaml").read_text())
        self.assertEqual(kind["execution"]["filesystem_authority_ceiling"], {
            "path": ["filesystem_authority"], "default": "node_policy"
        })
        self.assertEqual(kind["composed_value_contract"]["optional"]["filesystem_authority"], {
            "type": "single", "prim": "string"
        })
        self.assertIn("filesystem_authority", kind["runtime"]["ignored_keys"])

    def test_shared_source_digest_is_recomputed_for_both_workers(self):
        contracts = module("codex_contracts", BUNDLE / "test_contract.py")
        for worker in (self.worker, self.default_worker):
            self.assertEqual(worker["source"]["root"], "lib/hosted")
            self.assertEqual(worker["source"]["digest"], contracts.source_manifest_digest())
        self.assertEqual(self.worker["source"]["entry"], "authoring.profile.json")
        self.assertEqual(self.default_worker["source"]["entry"], "structured-session.profile.json")

    def test_profile_only_selects_baseline_and_exact_read_permission(self):
        actual = json.loads((SOURCE / "authoring.profile.json").read_text())
        original = json.loads((SOURCE / "structured-session.profile.json").read_text())
        self.assertEqual(actual["baseline_config"], "authoring.config.toml")
        actual["baseline_config"] = original["baseline_config"]
        added = ', "/ryeos/realizations/authoring-tools"="read"'
        self.assertEqual(sum(added in arg for arg in actual["workload_args"]), 1)
        actual["workload_args"] = [arg.replace(added, "") for arg in actual["workload_args"]]
        self.assertEqual(actual, original)

    def test_baseline_only_adds_the_exact_read_permission(self):
        actual = tomllib.loads((SOURCE / "authoring.config.toml").read_text())
        original = tomllib.loads((SOURCE / "baseline.config.toml").read_text())
        filesystem = actual["permissions"]["ryeos-workspace-only"]["filesystem"]
        self.assertEqual(filesystem.pop("/ryeos/realizations/authoring-tools"), "read")
        self.assertEqual(actual, original)

    def test_input_selection_is_the_authored_finite_contract(self):
        production = module("authoring_production", REPOSITORY /
            ".ai/tools/ryeos/development/authoring-environment-production/lib/production.py")
        config = yaml.safe_load((REPOSITORY /
            ".ai/config/development/ryeos/authoring-environment-inputs.yaml").read_text())
        production.validate_config(config)
        self.assertEqual(hashlib.sha256(production.canonical_json(config)).hexdigest(),
                         self.selection["input_contract_sha256"])
        self.assertEqual(len(config["inputs"]), self.selection["input_files"])
        self.assertEqual(sum(item["bytes"] for item in config["inputs"].values()),
                         self.selection["input_bytes"])
        self.assertEqual(len(production.REQUIRED_COMMANDS), 43)
        for field in self.selection["expected_manifests"].values():
            self.assertRegex(field, r"^[0-9a-f]{64}$")
        for operation in ("assemble", "verify"):
            text = (REPOSITORY / ".ai/tools/ryeos/development/authoring-environment-production" /
                    (operation + ".py")).read_text()
            self.assertIn(self.selection["expected_manifests"]["assembly_inputs"], text)

    def test_evidence_distinguishes_admitted_production_from_model_qualification(self):
        self.assertTrue(self.selection["qualification"]["independent_reproduction"])
        self.assertTrue(self.selection["qualification"]["offline_empty_root"])
        for gate in ("admitted_prepare", "admitted_assemble", "admitted_verify",
                     "ryeos_production", "retained_result_import", "consumer_binding"):
            self.assertTrue(self.selection["qualification"][gate])
        evidence = self.selection["admitted_production_evidence"]
        graph = evidence["shared_workspace_graph"]
        self.assertRegex(graph["thread_id"], r"^T-[0-9a-f-]+$")
        for field in ("capsule_hash", "base_snapshot_hash", "result_snapshot_hash"):
            self.assertRegex(graph[field], r"^[0-9a-f]{64}$")
        self.assertNotEqual(graph["base_snapshot_hash"], graph["result_snapshot_hash"])
        self.assertEqual(graph["inventory_sha256"], self.selection["inventory_sha256"])
        self.assertTrue(graph["assemble_executed"])
        self.assertTrue(graph["independent_verify_executed"])
        self.assertFalse(graph["cache_hit"])
        self.assertFalse(graph["source_head_advanced"])
        self.assertFalse(graph["binding_published"])
        self.assertEqual(set(evidence["observed_imports"]),
                         {"assembly_inputs", "environment", "production", "shell_file"})
        for binding in evidence["observed_bindings"].values():
            if isinstance(binding, dict):
                self.assertRegex(binding["binding_hash"], r"^[0-9a-f]{64}$")
        for gate in ("hosted_turn", "restart"):
            self.assertFalse(self.selection["qualification"][gate])
        self.assertNotIn("release_url", self.selection)
        self.assertNotIn("staging_id", self.selection)

    def test_no_ambient_runtime_or_client_authority(self):
        self.assertEqual(self.environment["configuration"]["process_environment"], {
            "GIT_CONFIG_NOSYSTEM": {"kind": "literal", "value": "1"},
            "GIT_CONFIG_GLOBAL": {"kind": "literal", "value": "/dev/null"},
            "GIT_PAGER": {"kind": "literal", "value": "cat"},
            "TZ": {"kind": "literal", "value": "UTC"},
        })


if __name__ == "__main__":
    unittest.main()
