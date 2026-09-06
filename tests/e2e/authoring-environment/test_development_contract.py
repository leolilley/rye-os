"""Source composition checks, not a claim of installed worker qualification."""

from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[3]


def load(relative):
    return yaml.safe_load((ROOT / relative).read_text())


class DevelopmentEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.environment = load(".ai/config/development/ryeos/worker-environment.yaml")

    def test_root_composes_authoring_and_restricted_client_not_child_compiler(self):
        baseline = load("bundles/codex/.ai/config/codex/environments/authoring.yaml")
        self.assertEqual(self.environment["schema"], baseline["schema"])
        self.assertEqual(self.environment["worker_ref"], baseline["worker_ref"])
        declarations = {entry["id"]: entry for entry in self.environment["external_content"]}
        self.assertEqual(set(declarations), {"authoring-tools", "workload-client"})
        self.assertEqual(declarations["authoring-tools"]["digest"],
                         baseline["external_content"][0]["digest"])
        client = self.environment["workload_client"]["client"]
        self.assertEqual(client, {"realization_id": "workload-client", "relative_path": "bin/ryeos"})
        self.assertIn({"realization_id": client["realization_id"], "relative_directory": "bin"},
                      self.environment["configuration"]["executable_search"])
        self.assertIsNone(baseline["workload_client"])

    def test_child_grants_match_exact_existing_signed_operations(self):
        routes = self.environment["workload_client"]["executions"]
        refs = [route["item_ref"] for route in routes]
        self.assertEqual(refs, sorted(set(refs)))
        for route in routes:
            self.assertTrue(route["item_ref"].startswith("tool:ryeos/development/"))
            tool = load(".ai/tools/" + route["item_ref"].removeprefix("tool:") + ".yaml")
            self.assertEqual(route["workspace_access"], tool["workspace_access"])
            self.assertEqual(route["effect_classes"], [tool["effects"]])
            self.assertEqual(route["ref_bindings"], {})
            self.assertEqual(route["calls"], [{"kind": "default"}])
            self.assertEqual(tool["network_authority"], "isolated")
            self.assertEqual(tool["filesystem_authority"], "captured_execution")
            self.assertEqual(tool["execution_protocol"], "protocol:ryeos/core/opaque")

    def test_project_bounds_fit_explicit_development_node_ceiling(self):
        request = self.environment["workload_client"]
        policy = load("bundles/.ai/node/init/profiles/development.yaml")["policies"]["execution"]["workload_client"]
        self.assertEqual(request["protocol"], policy["protocol"])
        for bound in ("max_in_flight", "max_invocations_per_boot", "max_lifetime_seconds"):
            self.assertGreater(request[bound], 0)
            self.assertLessEqual(request[bound], policy[bound])
        self.assertLessEqual(len(request["executions"]), policy["max_executions"])

    def test_vendor_uses_exact_inputs_without_network_or_host_cargo(self):
        tool = load(".ai/tools/ryeos/development/cargo-vendor.yaml")
        self.assertEqual(tool["config"]["command"], "realization:platform/rust/bin/cargo")
        self.assertEqual(tool["filesystem_authority"], "captured_execution")
        self.assertEqual(tool["network_authority"], "isolated")
        self.assertEqual(tool["workspace_access"], "immutable_current_generation")
        self.assertFalse(tool["config_schema"]["additionalProperties"])
        self.assertEqual(tool["config_schema"]["properties"], {})
        declarations = {entry["id"]: entry for entry in tool["external_content"]}
        self.assertEqual(set(declarations), {"platform", "registry-inputs"})
        for declaration in declarations.values():
            self.assertEqual(declaration["mode"], "pinned")
            self.assertEqual(declaration["mount_root"], "execution_runtime")
            self.assertRegex(declaration["digest"], r"^[0-9a-f]{64}$")
        args = tool["config"]["args"]
        for required in ("--locked", "--frozen", "--offline", "--respect-source-config", "--versioned-dirs"):
            self.assertIn(required, args)
        self.assertEqual(args[-1], "products/cargo-vendor")
        self.assertEqual(tool["env_config"]["env"]["PATH"], "")
        self.assertEqual(tool["config"]["env"]["CARGO_HOME"], "/tmp/cargo")
        execution = load(".ai/config/execution/execution.yaml")
        self.assertEqual(execution["items"]["tool"]["ryeos/development/cargo-vendor"]["timeout"],
                         tool["config"]["timeout_secs"])
        # Provisioning is operator-driven, not silently added to root worker grants.
        self.assertNotIn("tool:ryeos/development/cargo-vendor",
                         [route["item_ref"] for route in self.environment["workload_client"]["executions"]])

    def test_producer_timeouts_survive_project_execution_config_precedence(self):
        execution = load(".ai/config/execution/execution.yaml")["items"]["tool"]
        runtime = load(".ai/tools/ryeos/development/authoring-environment-production/runtime.yaml")
        for operation in ("prepare", "assemble", "verify"):
            self.assertEqual(execution["ryeos/development/authoring-environment-production/" + operation]["timeout"],
                             runtime["config"]["timeout_secs"])

    def test_python_runtime_uses_admitted_prefix_not_protected_environment(self):
        runtime = load(".ai/tools/ryeos/development/authoring-environment-production/runtime.yaml")
        for environment in (runtime["config"]["env"], runtime["env_config"]["env"],
                            runtime["env_config"]["env_paths"]):
            self.assertNotIn("PYTHONHOME", environment)
            self.assertNotIn("PYTHONPATH", environment)
            self.assertNotIn("LANG", environment)
            self.assertNotIn("LC_ALL", environment)
        args = runtime["config"]["args"]
        for flag in ("-P", "-S", "-B"):
            self.assertIn(flag, args)
        self.assertEqual(args[args.index("-X") + 1], "utf8")
        bootstrap = next(arg["literal"] for arg in args if isinstance(arg, dict))
        self.assertIn('Path(sys.prefix) != Path("/ryeos/realizations/producer-python/python")', bootstrap)


if __name__ == "__main__":
    unittest.main()
