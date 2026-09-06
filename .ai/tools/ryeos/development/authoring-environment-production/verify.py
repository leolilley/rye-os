# ryeos:signed:2026-09-06T03:45:22Z:757c078269c15594c29ee2fe635ea162d5b2455d5596799c29cb168348420413:w66lJx1o978KJ9L0yEA12wL34M/qb5fMZ4/HMxIXGdZXe3RYhO9QfwnXAZ6mg9pV0FT3+IHSTCWhq6bUsMbTBQ==:741a8bc609b398aaec0685e5aefb682faf5129a66bd192f888d23bb642c18eea
# ryeos-tool:
#   category: ryeos/development/authoring-environment-production
#   version: "1.0.0"
#   description: Independently reproduce and compare the retained authoring environment
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
    run_operation("verify")
