# ryeos:signed:2026-09-06T04:58:49Z:c0c9168e62ad574fefd366805efee2eefd0b6dc86d29497f46e65e71fdb6ef2c:gQ+gEXQqMNefQ6fFvnWedjLmArjq2DRIVbspX2gEIvCeLnSe/+0WdfcZHPW9W4PHquIGb+PNSPBnb8LOWhiKAQ==:741a8bc609b398aaec0685e5aefb682faf5129a66bd192f888d23bb642c18eea
# ryeos-tool:
#   category: ryeos/development/authoring-environment-production
#   version: "1.0.0"
#   description: Prepare the exact authoring assembly inputs from admitted source archives
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
#     type: multi
#     specs:
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
#     - id: source-inputs
#       kind: tree
#       mode: pinned
#       digest: 449c03919f51d36ca976967b63654c44bdf719c43ae418f716668748fe64863b
#       metadata_hint: ryeos-authoring-source-inputs-v1-large-content
#       mount_root: execution_runtime
#       mount: authoring-source-inputs

from preparation import run_preparation

if __name__ == "__main__":
    run_preparation()
