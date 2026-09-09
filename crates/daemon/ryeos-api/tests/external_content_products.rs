//! Application acceptance of previously published product testimony.
//!
//! Fixtures contain actual node-signed product witnesses and their retained
//! bytes, deliberately without historical thread/capsule objects. They exercise
//! the durable lookup/import contract, not admission or first-time capture of a
//! producer. A full producer launch must qualify that separate boundary.
mod test_state;

use std::sync::Arc;

use base64::Engine as _;
use ryeos_api::handlers::{external_content_import, external_content_products};
use ryeos_app::handler_context::HandlerContext;
use ryeos_app::identity::{AuthorizedKeyPrincipalClass, NodeIdentity, WildcardPolicy};
use ryeos_app::node_policy::sections::external_content::{
    ExternalContentImportLimits, ExternalContentImportPolicyRecord, ManagedExternalContentPolicy,
};
use ryeos_app::node_policy::sections::object_closure::NodeObjectClosurePolicy;
use ryeos_app::operator_external_content::products::ProductRequest;
use ryeos_app::operator_external_content::{ImportRequest, RetainedProductImportRequest};
use ryeos_app::state::AppState;
use ryeos_app::state_store::NodeIdentitySigner;
use ryeos_state::external_content::products::publication::{
    ProductCaptureCoordinate, publish_product_witness,
};
use ryeos_state::external_content::products::{
    PRODUCT_DECLARATIONS_SCHEMA, ProductBounds, ProductCaptureEvidence, ProductDeclaration,
    ProductDeclarations, ProductProducerAdmission, ProductShape, ProductStorage,
};
use serde_json::{Value, json};

const ROOT: &str = "T-00000000-0000-0000-0000-000000000001";
const TERMINAL: &str = "T-00000000-0000-0000-0000-000000000002";
const PRODUCT_BYTES: &[u8] = b"exact input";

struct Fixture {
    _directory: tempfile::TempDir,
    state: Arc<AppState>,
    context: HandlerContext,
    evidence: ProductCaptureEvidence,
    witness_hash: String,
}

fn fixture(large_tier: bool, import_ceiling: u64, publish: bool) -> Fixture {
    let (directory, mut state) = test_state::build_test_state();
    let closure = state
        .node_policy
        .require::<NodeObjectClosurePolicy>()
        .unwrap()
        .clone();
    state.node_policy = Arc::new(
        ryeos_app::node_policy::NodePolicySnapshot::from_test_records(vec![
            Arc::new(closure),
            Arc::new(ExternalContentImportPolicyRecord {
                schema: 1,
                roots: Default::default(),
                limits: ExternalContentImportLimits {
                    max_depth: 4,
                    max_entries: 16,
                    max_file_bytes: import_ceiling.min(1024),
                    max_total_bytes: import_ceiling,
                    store_budget_bytes: 8192,
                    minimum_free_bytes: 1,
                },
                managed_activation: ManagedExternalContentPolicy {
                    enabled: false,
                    limits: None,
                },
            }),
        ]),
    );
    let operator = NodeIdentity::load(&state.config.operator_signing_key_path).unwrap();
    let scopes = vec![
        "ryeos.execute.service.external-content/capture-product".to_owned(),
        "ryeos.execute.service.external-content/import".to_owned(),
        "ryeos.execute.service.external-content/product".to_owned(),
    ];
    ryeos_app::identity::write_authorized_key_toml(
        &state.config.authorized_keys_dir,
        operator.fingerprint(),
        &base64::engine::general_purpose::STANDARD.encode(operator.verifying_key().as_bytes()),
        &scopes,
        "product test operator",
        state.identity.fingerprint(),
        "2026-09-07T00:00:00Z",
        state.identity.signing_key(),
        WildcardPolicy::Reject,
    )
    .unwrap();
    let context = HandlerContext::new_with_authority(
        operator.principal_id(),
        scopes,
        true,
        Some(AuthorizedKeyPrincipalClass::LocalClient),
        None,
    );
    let authority = state.state_store.pinned_state_authority().unwrap();
    let guard = authority.acquire_exclusive_guard(true).unwrap();
    let cas = authority.cas_store().unwrap();
    let blob = cas.store_blob(PRODUCT_BYTES).unwrap();
    let (kind, schema, storage) = if large_tier {
        (
            ryeos_state::objects::EXTERNAL_LARGE_CONTENT_MANIFEST_KIND,
            ryeos_state::objects::EXTERNAL_LARGE_CONTENT_SCHEMA,
            ProductStorage::LargeContent,
        )
    } else {
        (
            ryeos_state::objects::EXTERNAL_CONTENT_MANIFEST_KIND,
            ryeos_state::objects::EXTERNAL_CONTENT_TREE_SCHEMA,
            ProductStorage::Content,
        )
    };
    let manifest_hash = cas
        .store_object(&json!({
            "kind": kind,
            "schema": schema,
            "entries": [{
                "path": "content", "kind": "file", "mode": 493,
                "blob_hash": blob, "size": PRODUCT_BYTES.len(),
            }],
            "entry_count": 1,
            "total_bytes": PRODUCT_BYTES.len(),
        }))
        .unwrap();
    let declaration = ProductDeclaration {
        name: "runtime".to_owned(),
        source: ryeos_state::external_content::products::ProductSource::RetainedProject {},
        path: "products/runtime".to_owned(),
        shape: ProductShape::Tree,
        storage,
        required: true,
        bounds: ProductBounds {
            maximum_entries: 16,
            maximum_depth: 4,
            maximum_file_bytes: 1024,
            maximum_total_bytes: 4096,
        },
        expected_manifest_hash: None,
    };
    let declarations = ProductDeclarations {
        schema: PRODUCT_DECLARATIONS_SCHEMA.to_owned(),
        output_roots: Vec::new(),
        products: vec![declaration.clone()],
    };
    let evidence = ProductCaptureEvidence {
        schema: ryeos_state::external_content::products::PRODUCT_CAPTURE_EVIDENCE_SCHEMA,
        owner_principal: context.fingerprint.clone(),
        chain_root_id: ROOT.to_owned(),
        thread_id: TERMINAL.to_owned(),
        // Historical coordinates are node testimony. No fake capsule is
        // installed or used to pass first-time producer capture validation.
        admitted_launch_capsule_hash: "a".repeat(64),
        root_producer: ProductProducerAdmission {
            canonical_ref: "graph:test/build".to_owned(),
            effective_definition_digest: "1".repeat(64),
            exact_program_hash: "2".repeat(64),
            producer_project_snapshot_hash: "3".repeat(64),
            launch_authority_digest: "4".repeat(64),
            admitted_parameters_digest: "5".repeat(64),
        },
        producer: ProductProducerAdmission {
            canonical_ref: "graph:test/build".to_owned(),
            effective_definition_digest: "1".repeat(64),
            exact_program_hash: "2".repeat(64),
            producer_project_snapshot_hash: "3".repeat(64),
            launch_authority_digest: "4".repeat(64),
            admitted_parameters_digest: "5".repeat(64),
        },
        result_project_snapshot_hash: "b".repeat(64),
        workspace_output_capture_hash: None,
        producer_partition_identity: None,
        recipe_binding: "product_recipe".to_owned(),
        recipe_ref: "config:test/products".to_owned(),
        recipe_raw_content_digest: "c".repeat(64),
        declarations_hash: declarations.content_hash().unwrap(),
        declarations,
        relationships:
            ryeos_state::external_content::products::composition::ProductRelationships::empty(),
        declaration,
        capture_policy_digest: "d".repeat(64),
        manifest_hash,
        manifest_kind: kind.to_owned(),
        entry_count: 1,
        total_bytes: PRODUCT_BYTES.len() as u64,
    };
    let signer = NodeIdentitySigner::from_identity(&state.identity);
    let attestation = evidence
        .sign_attestation(&signer, "2026-09-07T00:00:00Z".to_owned())
        .unwrap();
    let witness_hash = if publish {
        publish_product_witness(
            &authority,
            &ProductCaptureCoordinate::from_evidence(&evidence).unwrap(),
            &attestation,
            state
                .node_policy
                .require::<NodeObjectClosurePolicy>()
                .unwrap()
                .closure_limits()
                .unwrap(),
            &signer,
            &guard,
        )
        .unwrap()
        .witness
        .attestation_hash
    } else {
        cas.store_object(&attestation.to_value()).unwrap()
    };
    drop(guard);
    Fixture {
        _directory: directory,
        state: Arc::new(state),
        context,
        evidence,
        witness_hash,
    }
}

fn request() -> ProductRequest {
    ProductRequest {
        chain_root_id: ROOT.to_owned(),
        thread_id: TERMINAL.to_owned(),
        recipe_binding: "product_recipe".to_owned(),
        product_name: "runtime".to_owned(),
    }
}

async fn import(
    fixture: &Fixture,
    witness_hash: &str,
    maximum_bytes: u64,
) -> anyhow::Result<Value> {
    external_content_import::handle(
        ImportRequest::RetainedProduct(RetainedProductImportRequest {
            witness_hash: witness_hash.to_owned(),
            witness_source: ryeos_state::external_content::products::transfer::ProductWitnessSource::LocalCapture {},
            maximum_bytes,
        }),
        fixture.context.clone(),
        Arc::clone(&fixture.state),
    )
    .await
}

#[tokio::test]
async fn published_products_remain_exact_without_historical_threads_and_import_fresh_stages() {
    for large_tier in [false, true] {
        let fixture = fixture(large_tier, 4096, true);
        assert!(
            fixture
                .state
                .state_store
                .get_authoritative_thread_snapshot_with_last_event(ROOT, TERMINAL)
                .unwrap()
                .is_none()
        );
        let observed = external_content_products::get(
            request(),
            fixture.context.clone(),
            Arc::clone(&fixture.state),
        )
        .await
        .unwrap();
        assert_eq!(observed["state"], "captured");
        assert_eq!(observed["witness_hash"], fixture.witness_hash);
        assert_eq!(
            observed["evidence"]["producer"],
            serde_json::to_value(&fixture.evidence.producer).unwrap(),
        );
        let retried = external_content_products::capture(
            request(),
            fixture.context.clone(),
            Arc::clone(&fixture.state),
        )
        .await
        .unwrap();
        assert_eq!(retried, observed);
        assert!(import(&fixture, &fixture.witness_hash, 10).await.is_err());
        let first = import(&fixture, &fixture.witness_hash, 11).await.unwrap();
        let second = import(&fixture, &fixture.witness_hash, 11).await.unwrap();
        assert_ne!(first["staging_id"], second["staging_id"]);
        assert_eq!(first["request_digest"], second["request_digest"]);
        assert_eq!(first["manifest_hash"], fixture.evidence.manifest_hash);
        assert_eq!(first["total_bytes"], 11);
        let authority = fixture.state.state_store.pinned_state_authority().unwrap();
        let guard = authority.acquire_shared_guard().unwrap();
        let operator = NodeIdentity::load(&fixture.state.config.operator_signing_key_path).unwrap();
        for response in [&first, &second] {
            let stage = authority
                .require_recovery()
                .unwrap()
                .open_durable_cas_upload_admitted(
                    &guard,
                    response["staging_id"].as_str().unwrap(),
                    operator.fingerprint(),
                )
                .unwrap();
            assert!(stage.admitted_target_hash().is_none());
            stage
                .ensure_protects_object(&fixture.evidence.manifest_hash)
                .unwrap();
        }
        assert!(
            fixture
                .state
                .state_store
                .with_state_db(|db| {
                    db.list_generic_head_refs(
                        ryeos_state::objects::EXTERNAL_CONTENT_BINDING_HEAD_NAMESPACE,
                    )
                })
                .unwrap()
                .is_empty()
        );
    }
}

#[tokio::test]
async fn testimony_is_not_a_new_import_grant_under_stricter_current_policy() {
    let fixture = fixture(false, 5, true);
    let observed = external_content_products::get(
        request(),
        fixture.context.clone(),
        Arc::clone(&fixture.state),
    )
    .await
    .unwrap();
    assert_eq!(observed["witness_hash"], fixture.witness_hash);
    // Historical testimony remains readable; admitting bytes obeys today's
    // narrower policy and the caller's own bound.
    assert!(import(&fixture, &fixture.witness_hash, 11).await.is_err());
    assert!(import(&fixture, &fixture.witness_hash, 5).await.is_err());
}

#[tokio::test]
async fn product_services_refuse_foreign_or_remote_operator_contexts() {
    let fixture = fixture(false, 4096, true);
    let mut foreign = fixture.context.clone();
    foreign.fingerprint = format!("fp:{}", "f".repeat(64));
    let mut remote = fixture.context.clone();
    remote.authorized_key_class = Some(AuthorizedKeyPrincipalClass::RemoteOperator);
    remote.authenticated_origin_site_id = Some("site:other".to_owned());
    for context in [foreign, remote] {
        assert!(
            external_content_products::get(request(), context.clone(), Arc::clone(&fixture.state))
                .await
                .is_err()
        );
        assert!(
            external_content_products::capture(
                request(),
                context.clone(),
                Arc::clone(&fixture.state),
            )
            .await
            .is_err()
        );
        let qualification = external_content_products::qualify(
            ryeos_app::operator_external_content::product_qualification::ProductQualificationRequest {
                witness_hash: fixture.witness_hash.clone(),
                witness_source: ryeos_state::external_content::products::transfer::ProductWitnessSource::LocalCapture {},
                relationship_name: "runtime_to_consumer".to_owned(),
                verifier_chain_root_id: "T-00000000-0000-0000-0000-000000000001".to_owned(),
                verifier_thread_id: "T-00000000-0000-0000-0000-000000000002".to_owned(),
            },
            context.clone(),
            Arc::clone(&fixture.state),
        ).await.unwrap_err();
        assert!(
            format!("{qualification:#}").contains("operator"),
            "{qualification:#}"
        );
        let composition = external_content_products::compose(
            ryeos_app::operator_external_content::product_composition::ComposeRetainedProductsRequest {
                consumer_ref: "config:test/environment".to_owned(),
                project_context: Some(ryeos_app::operator_external_content::product_composition::ProductCompositionProjectContext { snapshot_hash: "a".repeat(64) }),
                selections: vec![ryeos_state::external_content::products::composition::ProductSelection {
                    declaration_id: "runtime".to_owned(),
                    witness_hash: fixture.witness_hash.clone(),
                    witness_source: ryeos_state::external_content::products::transfer::ProductWitnessSource::LocalCapture {},
                    qualification_hash: None,
                }],
                maximum_bytes: 4096,
            },
            context.clone(),
            Arc::clone(&fixture.state),
        )
        .await
        .unwrap_err();
        // Authorization must fail before attempting to resolve this deliberately
        // nonexistent consumer generation or publishing an import stage.
        assert!(
            format!("{composition:#}").contains("operator"),
            "{composition:#}"
        );
        assert!(
            external_content_import::handle(
                ImportRequest::RetainedProduct(RetainedProductImportRequest {
                    witness_hash: fixture.witness_hash.clone(),
                    witness_source: ryeos_state::external_content::products::transfer::ProductWitnessSource::LocalCapture {},
                    maximum_bytes: 11,
                }),
                context,
                Arc::clone(&fixture.state),
            )
            .await
            .is_err()
        );
    }
}

#[tokio::test]
async fn exact_import_refuses_unpublished_wrong_owner_and_wrong_node_witnesses() {
    let fixture = fixture(false, 4096, false);
    let observed = external_content_products::get(
        request(),
        fixture.context.clone(),
        Arc::clone(&fixture.state),
    )
    .await
    .unwrap();
    assert_eq!(observed["state"], "missing");
    let missing_producer = external_content_products::capture(
        request(),
        fixture.context.clone(),
        Arc::clone(&fixture.state),
    )
    .await
    .unwrap_err();
    assert!(format!("{missing_producer:#}").contains("producer terminal does not exist"));
    let unpublished = import(&fixture, &fixture.witness_hash, 11)
        .await
        .unwrap_err();
    assert!(format!("{unpublished:#}").contains("not currently published"));

    let (wrong_owner_hash, wrong_node_hash) = {
        let authority = fixture.state.state_store.pinned_state_authority().unwrap();
        let _guard = authority.acquire_shared_guard().unwrap();
        let cas = authority.cas_store().unwrap();
        let mut wrong_owner = fixture.evidence.clone();
        wrong_owner.owner_principal = format!("fp:{}", "f".repeat(64));
        let signer = NodeIdentitySigner::from_identity(&fixture.state.identity);
        let wrong_owner = wrong_owner
            .sign_attestation(&signer, "2026-09-07T00:00:00Z".to_owned())
            .unwrap();
        let other_node =
            NodeIdentity::create(&fixture._directory.path().join("other-node.pem")).unwrap();
        let foreign_signer = NodeIdentitySigner::from_identity(&other_node);
        let wrong_node = fixture
            .evidence
            .sign_attestation(&foreign_signer, "2026-09-07T00:00:00Z".to_owned())
            .unwrap();
        (
            cas.store_object(&wrong_owner.to_value()).unwrap(),
            cas.store_object(&wrong_node.to_value()).unwrap(),
        )
    };
    let wrong_owner = import(&fixture, &wrong_owner_hash, 11).await.unwrap_err();
    assert!(format!("{wrong_owner:#}").contains("not owned"));
    let wrong_node = import(&fixture, &wrong_node_hash, 11).await.unwrap_err();
    assert!(format!("{wrong_node:#}").contains("signature"));
}

#[tokio::test]
async fn malformed_subjects_fail_verification_and_cannot_acquire_import_authority() {
    for large_tier in [false, true] {
        let fixture = fixture(large_tier, 4096, false);
        let lying_witness = {
            let authority = fixture.state.state_store.pinned_state_authority().unwrap();
            let _guard = authority.acquire_shared_guard().unwrap();
            let cas = authority.cas_store().unwrap();
            let mut manifest = cas
                .get_object(&fixture.evidence.manifest_hash)
                .unwrap()
                .unwrap();
            // Internally consistent manifest accounting must not replace
            // verification of the retained blob's actual bytes.
            manifest["entries"][0]["size"] = json!(12);
            manifest["total_bytes"] = json!(12);
            let mut evidence = fixture.evidence.clone();
            evidence.manifest_hash = cas.store_object(&manifest).unwrap();
            evidence.total_bytes = 12;
            let signer = NodeIdentitySigner::from_identity(&fixture.state.identity);
            let attestation = evidence
                .sign_attestation(&signer, "2026-09-07T00:00:00Z".to_owned())
                .unwrap();
            cas.store_object(&attestation.to_value()).unwrap()
        };
        {
            let authority = fixture.state.state_store.pinned_state_authority().unwrap();
            let guard = authority.acquire_shared_guard().unwrap();
            let error = ryeos_state::external_content::products::publication::lookup_product_witness_hash_guarded(
                &authority,
                &ProductCaptureCoordinate::from_evidence(&fixture.evidence).unwrap(),
                &lying_witness,
                fixture.state.identity.verifying_key(),
                fixture.state.node_policy.require::<NodeObjectClosurePolicy>().unwrap().closure_limits().unwrap(),
                &guard,
            ).unwrap_err();
            assert!(format!("{error:#}").contains("size"), "{error:#}");
        }
        // Import requires current publication before scrubbing the payload.
        // An unattached attestation cannot bypass that gate, even when signed
        // by this node. The shared verifier above proves the size refusal.
        let error = import(&fixture, &lying_witness, 12).await.unwrap_err();
        assert!(
            format!("{error:#}").contains("not currently published"),
            "{error:#}"
        );
    }
}

#[tokio::test]
async fn published_retry_survives_abandoned_upload_retirement() {
    let fixture = fixture(false, 4096, true);
    let staging_id = {
        let authority = fixture.state.state_store.pinned_state_authority().unwrap();
        let guard = authority.acquire_shared_guard().unwrap();
        let operator = NodeIdentity::load(&fixture.state.config.operator_signing_key_path).unwrap();
        let mut stage = authority
            .require_recovery()
            .unwrap()
            .begin_durable_cas_upload_admitted(
                &guard,
                operator.fingerprint(),
                "external-content-import",
                &ryeos_state::DurableCasPublicationKey::external_content_import(&"e".repeat(64))
                    .unwrap(),
                None,
            )
            .unwrap();
        stage
            .protect_cas_closure(
                &guard,
                [fixture.evidence.manifest_hash.as_str()],
                std::iter::empty(),
            )
            .unwrap();
        // Equivalent durable state to interruption after product head publication
        // but before capture's old import stage was settled. The witness is the
        // authoritative answer; this unacknowledged stage is cleanup work only.
        stage.staging_id().to_owned()
    };
    let retry = external_content_products::capture(
        request(),
        fixture.context.clone(),
        Arc::clone(&fixture.state),
    )
    .await
    .unwrap();
    assert_eq!(retry["witness_hash"], fixture.witness_hash);
    assert_eq!(retry["idempotent"], true);
    {
        let authority = fixture.state.state_store.pinned_state_authority().unwrap();
        let guard = authority.acquire_exclusive_guard(true).unwrap();
        let recovery = authority.require_recovery().unwrap();
        // An explicit test maintenance cutoff, not a built-in product TTL.
        assert_eq!(
            recovery
                .retire_durable_cas_uploads_created_before("2099-01-01T00:00:00Z", &guard)
                .unwrap(),
            1,
        );
        let operator = NodeIdentity::load(&fixture.state.config.operator_signing_key_path).unwrap();
        assert!(
            recovery
                .open_durable_cas_upload_admitted(&guard, &staging_id, operator.fingerprint())
                .is_err()
        );
    }
    let observed = external_content_products::get(
        request(),
        fixture.context.clone(),
        Arc::clone(&fixture.state),
    )
    .await
    .unwrap();
    assert_eq!(observed["witness_hash"], fixture.witness_hash);
    assert_eq!(
        import(&fixture, &fixture.witness_hash, 11).await.unwrap()["manifest_hash"],
        fixture.evidence.manifest_hash,
    );
}
