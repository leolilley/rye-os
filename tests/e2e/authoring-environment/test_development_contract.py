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


if __name__ == "__main__":
    unittest.main()
