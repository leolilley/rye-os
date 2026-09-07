# ryeos:signed:2026-09-07T08:05:59Z:33132b769edc39bd0f840ec6807a8e0f3e3b19f622a01b0fc441984e5be38a79:P2qcdAoP1z/nAtkBuDT3hjNOE5npBza5Tv49AYjUOfNAPp+fze5SeTDZptvPrc7UZomtDQBItJ3dOfNNVFo1Dg==:741a8bc609b398aaec0685e5aefb682faf5129a66bd192f888d23bb642c18eea
# ryeos-tool:
#   category: ryeos/development/authoring-environment-production
#   version: "1.0.0"
#   description: Build the finite authoring utilities from exact sources using admitted Stage0 and support
#   executor_id: tool:ryeos/development/authoring-environment-production/runtime
#   execution_protocol: protocol:ryeos/core/opaque
#   effects: live
#   workspace_access: immutable_current_generation
#   filesystem_authority: captured_execution
#   network_authority: isolated
#   config_schema:
#     type: object
#     properties: {}
#     additionalProperties: false
#   config_resolve:
#     type: multi
#     specs:
#       - path: development/ryeos/authoring-build-support.yaml
#         mode: first_match
#       - path: development/ryeos/authoring-environment-inputs.yaml
#         mode: first_match
#       - path: development/ryeos/authoring-utility-sources.yaml
#         mode: first_match
#   external_content:
#     - id: producer-python
#       kind: tree
#       mode: pinned
#       digest: 800d4969489634cc3bbc5774bd9e99a330cdc23bbc1fd0fd231ec6a88ca9acdf
#       mount_root: execution_runtime
#       mount: producer-python
#     - id: authoring-build-support
#       kind: tree
#       mode: pinned
#       digest: f6bcd9d28b9bb3da0da3911cc8f021d75c326d38ac05329d38e2246ed7bea477
#       mount_root: execution_runtime
#       mount: authoring-build-support
#     - id: platform
#       kind: tree
#       mode: pinned
#       digest: 98bceddd5b4024d5963eeac8c579e6d4e79c24577980fa9f88bce9ae3151d316
#       mount_root: execution_runtime
#       mount: platform
#     - id: source-inputs
#       kind: tree
#       mode: pinned
#       digest: 449c03919f51d36ca976967b63654c44bdf719c43ae418f716668748fe64863b
#       mount_root: execution_runtime
#       mount: authoring-source-inputs

from utility_production import main

if __name__ == "__main__":
    main()
