mod test_state;

use std::sync::Arc;

use ryeos_api::handlers::project_snapshot_status::{DESCRIPTOR, Request};
use ryeos_api::registry::build_service_registry;
use ryeos_app::handler_context::HandlerContext;
use ryeos_app::identity::{AuthorizedKeyPrincipalClass, NodeIdentity};
use serde_json::{Value, json};

const CAP: &str = "ryeos.execute.service.project/snapshot-status";

fn local_operator(state: &ryeos_app::state::AppState) -> HandlerContext {
    let operator = NodeIdentity::load(&state.config.operator_signing_key_path).unwrap();
    HandlerContext::new_with_authority(
        operator.principal_id(),
        vec![CAP.to_owned()],
        true,
        Some(AuthorizedKeyPrincipalClass::LocalClient),
        None,
    )
}

#[test]
fn command_and_service_keep_offline_read_only_ownership_and_authored_scan_default() {
    let command: ryeos_runtime::CommandDef = serde_yaml::from_str(include_str!(
        "../../../../bundles/core/.ai/node/commands/snapshot-status.yaml"
    ))
    .unwrap();
    let service: Value = serde_yaml::from_str(include_str!(
        "../../../../bundles/core/.ai/services/project/snapshot-status.yaml"
    ))
    .unwrap();
    let callback_tool: Value = serde_yaml::from_str(include_str!(
        "../../../../bundles/core/.ai/tools/core/snapshot-status.yaml"
    ))
    .unwrap();
    let ryeos_runtime::CommandDispatch::ExecuteRef {
        execute,
        availability,
    } = &command.dispatch
    else {
        panic!("expected ordinary service dispatch")
    };
    assert_eq!(execute, DESCRIPTOR.service_ref);
    assert_eq!(*availability, ryeos_runtime::CommandAvailability::Both);
    assert_eq!(service["availability"], "both");
    assert_eq!(service["endpoint"], DESCRIPTOR.endpoint);
    assert_eq!(service["state_access"], "read_only_existing");
    assert_eq!(service["record_thread"], false);
    let metadata = serde_json::from_value(service.clone()).unwrap();
    assert_eq!(
        ryeos_app::service_registry::extract_standalone_state_access(&metadata).unwrap(),
        ryeos_app::service_registry::StandaloneStateAccess::ReadOnlyExisting,
    );
    assert!(!ryeos_app::service_registry::extract_record_thread(&metadata).unwrap());
    assert_eq!(service["required_caps"], json!([CAP]));
    assert_eq!(DESCRIPTOR.required_caps, [CAP]);
    assert_eq!(
        DESCRIPTOR.availability,
        ryeos_api::ServiceAvailability::Both
    );
    assert!(service.get("local_execute").is_none());
    assert_eq!(command.defaults["time_budget_ms"], 5000);
    assert_eq!(
        command.defaults["time_budget_ms"],
        callback_tool["config_schema"]["properties"]["time_budget_ms"]["default"]
    );
    assert_eq!(
        callback_tool["requires"]["capabilities"]["manifest"]["runtime_authority"]["project_snapshots"],
        json!(["status"])
    );
    assert_eq!(
        callback_tool["required_caps"],
        json!(["ryeos.read.project.live"])
    );

    let project = command.project.as_ref().unwrap();
    assert_eq!(
        project.resolution,
        ryeos_runtime::CommandProjectResolution::Required
    );
    assert!(project.request_project_path);
    assert_eq!(project.bind_parameter.as_deref(), Some("project_path"));
    let contract =
        ryeos_runtime::InvocationInputContract::from_lightweight_schema_value(&service["schema"])
            .unwrap()
            .unwrap();
    for (argv, expected_budget, include_unchanged) in [
        (vec![], 5000, false),
        (
            vec!["--time-budget-ms", "0", "--include-unchanged"],
            0,
            true,
        ),
    ] {
        let argv = argv.into_iter().map(str::to_owned).collect::<Vec<_>>();
        let mut params =
            ryeos_runtime::arg_binder::bind_argv_with_command(&argv, Some(&command)).unwrap();
        // The signed project policy binds the resolved project independently
        // from option parsing; preserve that exact service parameter.
        params["project_path"] = json!("/project");
        let params =
            ryeos_runtime::arg_binder::normalize_params_with_contract(params, Some(&contract))
                .unwrap();
        let request: Request = serde_json::from_value(params).unwrap();
        assert_eq!(request.time_budget_ms, expected_budget);
        assert_eq!(request.include_unchanged, include_unchanged);
    }
}

#[test]
fn service_request_requires_explicit_budget_and_refuses_unknown_authority() {
    for params in [
        json!({"project_path":"/project"}),
        json!({"project_path":"/project","time_budget_ms":-1}),
        json!({"project_path":"/project","time_budget_ms":0,"principal":"fp:caller"}),
        json!({"project_path":"/project","time_budget_ms":0,"thread_id":"T-synthetic"}),
    ] {
        assert!(serde_json::from_value::<Request>(params).is_err());
    }
}

#[tokio::test]
async fn unauthorized_callers_are_refused_before_project_path_observation() {
    let (_tmp, state) = test_state::build_test_state();
    let local = local_operator(&state);
    let contexts = [
        HandlerContext::anonymous(),
        HandlerContext::new_with_authority(
            local.fingerprint.clone(),
            vec![CAP.to_owned()],
            true,
            Some(AuthorizedKeyPrincipalClass::RemoteOperator),
            Some("site:remote".into()),
        ),
        HandlerContext::new_with_authority(
            local.fingerprint.clone(),
            vec![CAP.to_owned()],
            true,
            Some(AuthorizedKeyPrincipalClass::LocalClient),
            Some("site:remote".into()),
        ),
        HandlerContext::new_with_authority(
            state.identity.principal_id(),
            vec![CAP.to_owned()],
            true,
            Some(AuthorizedKeyPrincipalClass::LocalClient),
            None,
        ),
    ];
    let state = Arc::new(state);
    let registry = build_service_registry();
    for caller in contexts {
        let error = registry.get(DESCRIPTOR.endpoint).unwrap()(
            json!({"project_path":"relative","time_budget_ms":0}),
            caller,
            state.clone(),
        )
        .await
        .unwrap_err();
        let error = format!("{error:#}");
        assert!(
            error.contains("snapshot status requires the configured local operator"),
            "{error}"
        );
        assert!(
            !error.contains("project_path must be an absolute"),
            "{error}"
        );
    }
    let error = registry.get(DESCRIPTOR.endpoint).unwrap()(
        json!({"project_path":"relative","time_budget_ms":0}),
        local,
        state,
    )
    .await
    .unwrap_err();
    assert!(format!("{error:#}").contains("project_path must be an absolute path"));
}

#[tokio::test]
async fn local_operator_status_reuses_principal_head_comparison_without_creating_a_head() {
    let (_tmp, state) = test_state::build_test_state();
    let project = tempfile::tempdir().unwrap();
    std::fs::write(project.path().join("edited.txt"), b"current workspace edit").unwrap();
    let caller = local_operator(&state);
    let expected_principal = ryeos_state::refs::principal_storage_key(&caller.fingerprint)
        .unwrap()
        .to_owned();
    let state = Arc::new(state);
    let registry = build_service_registry();
    let result = registry.get(DESCRIPTOR.endpoint).unwrap()(
        json!({"project_path":project.path(),"time_budget_ms":0}),
        caller,
        state.clone(),
    )
    .await
    .unwrap();
    assert_eq!(result["kind"], "snapshot_status");
    assert_eq!(result["principal_key"], expected_principal);
    assert_eq!(result["baseline"], "principal_head");
    assert_eq!(result["scan_complete"], true);
    assert_eq!(result["dirty"], true);
    assert_eq!(result["counts"]["added"], 1);
    assert_eq!(result["changes"][0]["path"], "edited.txt");
    assert!(result["head_snapshot_hash"].is_null());
    assert!(result["deployed_snapshot_hash"].is_null());
    let head = state
        .state_store
        .with_state_db(|db| {
            db.read_project_head(
                &expected_principal,
                result["project_hash"].as_str().unwrap(),
            )
        })
        .unwrap();
    assert!(head.is_none());
}
