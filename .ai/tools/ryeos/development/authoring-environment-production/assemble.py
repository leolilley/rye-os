# ryeos:signed:2026-09-06T03:45:22Z:9e5851167a6f4df6c8ff5cf4167c63b560175662e0292a38039cb467f56902c1:MTXZ5YJa0rbeqfYmZbABQSBRET/3PYS1wwY9wvXGHopyJbS2wnkD66fykDxgi5Y6WPaYt6wwUxEW4V9InWNRBw==:741a8bc609b398aaec0685e5aefb682faf5129a66bd192f888d23bb642c18eea
# ryeos-tool:
#   category: ryeos/development/authoring-environment-production
#   version: "1.0.0"
#   description: Assemble the exact authoring environment from admitted immutable inputs
#   executor_id: tool:ryeos/development/authoring-environment-production/runtime
#   execution_protocol: protocol:ryeos/core/opaque
#   effects: live
#   filesystem_authority: captured_execution
#   network_authority: isolated
#   config_schema:
#     type: object
#     properties: {}
#     additionalProperties: false
#   config_resolve:
#     type: single
#     spec:
#       path: development/ryeos/authoring-environment-inputs.yaml
#       mode: first_match
#   external_content:
#     - id: producer-python
#       kind: tree
#       mode: pinned
#       digest: 800d4969489634cc3bbc5774bd9e99a330cdc23bbc1fd0fd231ec6a88ca9acdf
#       mount_root: execution_runtime
#       mount: producer-python
#     - id: assembly-inputs
#       kind: tree
#       mode: pinned
#       digest: cc090b3d53dd41c0351dcd5ea7a18bfd4e37957ae5738569039b9b88ffd9ff80
#       metadata_hint: ryeos-authoring-inputs-v1-large-content
#       mount_root: execution_runtime
#       mount: authoring-inputs

from production import run_operation

if __name__ == "__main__":
    run_operation("assemble")
